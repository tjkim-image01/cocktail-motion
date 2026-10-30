"""대본 → Typecast 음성 자동 생성.

project/*/video/03_대본.md (배역 표 + 대사 표)를 찾아, 음성이 없거나 대본이 바뀐 프로젝트만
lib.com.jatu.aside.connector.typecast 로 화자별 음성을 만든다.

- 결과: <video>/voice/typecast/<화자>/<숏>_<n>.wav, lines.json
- 영상용 길이표: <video>/voice/tts/durations.json (make_video.py 가 읽는 형식)
- 대본이 바뀌었는지는 voice/typecast/.script_hash 로 판단

실행: cd /Users/jatu/blog && python3 -m lib.com.jatu.voice_auto [대본 경로 ...] [--force] [--capture record] [--out 음성폴더]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from lib.com.jatu.aside.connector.typecast import TypecastConnector, parse_script

ROOT = Path(__file__).resolve().parents[3]          # /Users/jatu/blog
GAP = 0.35                                          # 같은 숏 안 대사 사이 쉼
PAD = (0.25, 0.45)                                  # 숏 앞뒤 여백 (말 사이 숨)
PAD_LAST = (0.15, 1.2)


def durations(lines: list, out_dir: Path) -> Path:
    """typecast lines.json → make_video.py 용 숏 길이표"""
    shots = {}
    for ln in lines:
        shots.setdefault(ln["shot"], []).append(ln)
    info, keys = [], list(shots)
    for k in keys:
        pre, post = PAD_LAST if k == keys[-1] else PAD
        t, rows = pre, []
        for ln in shots[k]:
            rows.append({"who": ln["who"], "text": ln["sub"], "file": "../typecast/" + ln["file"],
                         "speech": ln["speech"], "at": round(t, 2), "emotion": ln.get("emotion_applied")})
            t += ln["speech"] + GAP
        info.append({"shot": k, "len": round(t - GAP + post, 2), "lines": rows})
    f = out_dir.parent / "tts" / "durations.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(info, ensure_ascii=False, indent=1))
    return f


def run_one(script: Path, force=False, capture="cdn", account="u2", out: Path = None) -> bool:
    out = Path(out) if out else script.parent / "voice" / "typecast"
    h = hashlib.sha1(script.read_bytes()).hexdigest()
    stamp = out / ".script_hash"
    if not force and stamp.exists() and stamp.read_text() == h and (out / "lines.json").exists():
        print(f"[voice_auto] 그대로 (대본 변경 없음): {script}")
        return False
    cast, lines = parse_script(script)
    print(f"[voice_auto] 생성: {script} — {len(lines)}줄, 배역 {cast}")
    lines = TypecastConnector(account=account).run(cast, lines, out, capture)
    f = durations(lines, out)
    stamp.write_text(h)
    total = sum(s["len"] for s in json.loads(f.read_text()))
    print(f"[voice_auto] 완료: {out} / 길이표 {f} (합계 {total:.1f}초)")
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("scripts", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--capture", choices=["cdn", "record"], default="cdn")
    ap.add_argument("--account", default="u2")
    ap.add_argument("--out", help="음성 저장 폴더 (대본 하나일 때만, 기본: 대본 폴더/voice/typecast). 길이표는 그 옆 tts/durations.json")
    a = ap.parse_args(argv)
    scripts = [Path(s).resolve() for s in a.scripts] or sorted(ROOT.glob("project/*/video/03_대본.md"))
    if not scripts:
        print("[voice_auto] 대본(project/*/video/03_대본.md)이 없습니다")
        return 0
    for s in scripts:
        run_one(s, a.force, a.capture, a.account, a.out if len(scripts) == 1 else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
