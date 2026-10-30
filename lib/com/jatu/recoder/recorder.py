"""시스템 소리 녹음기 — audio_clip(start/stop) 기능을 라이브러리로 옮긴 것.

- start(): 녹음 시작. 백엔드 순서: ScreenCaptureKit(bin/sck_audio_recorder, 컴퓨터 내부 소리)
           → 가상 루프백 장치(BlackHole 등, ffmpeg avfoundation) → 마이크(allow_mic=True 일 때만)
- stop(out=None): 녹음 종료 → 앞뒤 무음 제거(-42dB, 여백 60ms) → MP3(192k) 저장, 경로 반환
- status(): 진행 중이면 상태 dict, 아니면 None
- record(play_fn, out): 녹음 시작 → play_fn() (소리 재생, 끝날 때까지 블록) → 저장

numpy 없이 ffmpeg 만 쓴다. ScreenCaptureKit 은 이 앱(터미널/VS Code)에 macOS '화면 기록' 권한이 있어야 한다.

CLI: python3 -m lib.com.jatu.recoder start | stop [out.mp3] | status
"""
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCK_BIN = HERE / "bin" / "sck_audio_recorder"
STATE_DIR = HERE / ".state"
STATE_FILE = STATE_DIR / "recording.json"
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[4] / "audio_clip"   # /Users/jatu/blog/audio_clip

SILENCE_DB = -42
PAD_SEC = 0.06
LOOPBACK_KEYWORDS = ("blackhole", "loopback", "soundflower", "virtual")


class RecorderError(RuntimeError):
    pass


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _loopback_device():
    """ffmpeg avfoundation 오디오 장치 중 루프백 장치의 번호"""
    out = subprocess.run(["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                         capture_output=True, text=True).stderr
    audio = False
    for line in out.splitlines():
        if "audio devices" in line.lower():
            audio = True
            continue
        if audio and "] [" in line:
            idx, name = line.split("] [", 1)[1].split("] ", 1)
            if any(k in name.lower() for k in LOOPBACK_KEYWORDS):
                return idx, name.strip()
    return None, None


def status():
    if not STATE_FILE.exists():
        return None
    st = json.loads(STATE_FILE.read_text())
    if not _alive(st["pid"]):
        STATE_FILE.unlink(missing_ok=True)
        return None
    st["elapsed"] = round(time.time() - st["start_time"], 1)
    return st


def start(allow_mic: bool = False) -> dict:
    if status():
        raise RecorderError("이미 녹음 중입니다 (stop 먼저)")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    proc, backend, temp = None, None, None

    if SCK_BIN.exists():
        temp = STATE_DIR / f"rec_{stamp}.m4a"
        proc = subprocess.Popen([str(SCK_BIN), str(temp)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        time.sleep(0.8)
        if proc.poll() is None:
            backend = "sck"
        else:
            err = proc.stderr.read().decode(errors="ignore").strip()
            proc = None
            temp.unlink(missing_ok=True)
            print(f"[recoder] ScreenCaptureKit 실패 ({err[:120] or '권한 없음'}) → 다음 백엔드", file=sys.stderr)

    if proc is None:
        idx, name = _loopback_device()
        if idx is None and allow_mic:
            idx, name = "default", "기본 입력(마이크)"
        if idx is not None:
            temp = STATE_DIR / f"rec_{stamp}.wav"
            proc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "avfoundation", "-i", f":{idx}", str(temp)],
                                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.5)
            backend = f"avfoundation:{name}"

    if proc is None or proc.poll() is not None:
        raise RecorderError("시스템 소리를 녹음할 수 없습니다: '시스템 설정 > 개인정보 보호 및 보안 > 화면 기록'에서 "
                            "이 앱(터미널/VS Code)을 허용하거나 BlackHole(brew install blackhole-2ch)을 설치하세요.")
    st = {"pid": proc.pid, "backend": backend, "temp": str(temp), "start_time": time.time(), "stamp": stamp}
    STATE_FILE.write_text(json.dumps(st, ensure_ascii=False))
    return st


def _trim_to_mp3(src: Path, out: Path) -> float:
    """앞뒤 무음 제거 + 짧은 페이드 → MP3. 길이(초) 반환"""
    out.parent.mkdir(parents=True, exist_ok=True)
    trim = (f"silenceremove=start_periods=1:start_threshold={SILENCE_DB}dB:start_silence={PAD_SEC},"
            f"areverse,silenceremove=start_periods=1:start_threshold={SILENCE_DB}dB:start_silence={PAD_SEC},areverse,"
            "afade=t=in:d=0.02")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", trim, "-ar", "44100", "-ac", "2",
                    "-codec:a", "libmp3lame", "-b:a", "192k", str(out)], check=True)
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                       capture_output=True, text=True).stdout.strip()
    return float(d or 0)


def stop(out=None) -> Path:
    st = status()
    if not st:
        raise RecorderError("진행 중인 녹음이 없습니다")
    pid = st["pid"]
    os.kill(pid, signal.SIGINT)
    for _ in range(40):
        if not _alive(pid):
            break
        time.sleep(0.15)
    else:
        os.kill(pid, signal.SIGKILL)
    STATE_FILE.unlink(missing_ok=True)
    time.sleep(0.3)
    temp = Path(st["temp"])
    if not temp.exists() or temp.stat().st_size == 0:
        temp.unlink(missing_ok=True)
        raise RecorderError("녹음 파일이 비어 있습니다 (권한 또는 소리 출력 확인)")
    out = Path(out) if out else DEFAULT_OUT_DIR / f"clip_{st['stamp'][:15]}.mp3"
    dur = _trim_to_mp3(temp, out)
    temp.unlink(missing_ok=True)
    if dur < 0.1:
        raise RecorderError(f"무음만 녹음됨: {out}")
    return out


def record(play_fn, out, tail: float = 0.5, allow_mic: bool = False) -> Path:
    """녹음 시작 → play_fn() 이 끝나면 tail 초 더 기다렸다가 저장"""
    start(allow_mic=allow_mic)
    try:
        play_fn()
        time.sleep(tail)
    except BaseException:
        try:
            stop(Path(out).with_suffix(".failed.mp3"))
        except RecorderError:
            pass
        raise
    return stop(out)


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    cmd = a[0] if a else "status"
    try:
        if cmd == "start":
            st = start(allow_mic="--mic" in a)
            print(f"● 녹음 시작 ({st['backend']}, PID {st['pid']}) — 끝내려면: python3 -m lib.com.jatu.recoder stop")
        elif cmd == "stop":
            p = stop(a[1] if len(a) > 1 else None)
            print(f"✔ 저장: {p}")
        elif cmd == "status":
            st = status()
            print(f"● 녹음 중 ({st['backend']}, {st['elapsed']}초)" if st else "○ 녹음 중 아님")
        else:
            print("사용법: python3 -m lib.com.jatu.recoder start [--mic] | stop [out.mp3] | status")
            return 1
    except RecorderError as e:
        print(f"[오류] {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
