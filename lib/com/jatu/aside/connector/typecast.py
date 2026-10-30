"""Typecast 커넥터 — Aside 브라우저로 studio.typecast.ai 프로젝트에 대본을 넣고, 단락(대사)마다 성우·감정을 바꿔 음성을 받는다.

흐름 (화면 조작만 한다. 로그인 토큰은 다루지 않는다)
  1. 프로젝트 열기 → 기존 글 전부 지우기
  2. 대사마다 단락 입력 → 단락의 성우 칩(actor-selector)에서 이름으로 검색해 성우 지정 → 문단을 선택해 감정 지정
  3. 음성 받기
     - capture="cdn"(기본): 편집기 재생 → 페이지가 받는 미리듣기 wav(CDN) 주소를 가로채 저장. 다운로드 버튼을 쓰지 않아 크레딧이 줄지 않는다
     - capture="record": 단락을 하나씩 재생하면서 lib.com.jatu.recoder 로 시스템 소리를 녹음
  4. 결과: <out>/<화자>/<숏>_<n>.wav (+ lines.json)

대본 형식 (03_대본.md) — 표 두 개
  | 배역 | 성우 | ... |            ← 배역 → Typecast 성우 이름
  | 숏 | 화자 | 감정 | 대사 | 자막 |   ← 감정: 일반·기쁨·슬픔·화남·높은 톤·낮은 톤·속삭임 (성우에 없으면 일반)
                                     자막 칸이 비면 대사를 그대로 자막으로 쓴다 (TTS 용 한글 숫자 ↔ 자막 숫자)

CLI
  python3 -m lib.com.jatu.aside.connector.typecast --script project/jatu001/video/03_대본.md
  python3 -m lib.com.jatu.aside.connector.typecast --audition 예나,나윤 --text "테스트 문장" --out <폴더>
"""
import argparse
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

ASIDE_BIN = str(Path.home() / ".local/bin/aside")
ROOT_DIR = Path(__file__).resolve().parents[5]          # /Users/jatu/blog
DEFAULT_PROJECT = "https://studio.typecast.ai/text-to-speech/6ac87c1e1f8041c699fbae84"
EMOTIONS = ["일반", "기쁨", "슬픔", "화남", "높은 톤", "낮은 톤", "속삭임"]


class TypecastError(RuntimeError):
    pass


# 모든 REPL 호출 앞에 붙는 공통부: 프로젝트 탭을 찾거나 열고, 네트워크 응답 기록 훅을 건다
_JS_TAB = r"""
const __url = %(url)s;
const __id = __url.split('/').pop();
const __all = (await listBrowserTabs()).filter(x => (x.url || '').includes(__id));
let __t = __all.find(x => x.active) || __all[0];
const tc = __t ? await attachBrowserTab(__t.targetId) : await openTab(__url);
if (!__t) await sleep(6000);
// 같은 Aside 계정을 다른 작업이 쓰면 이 탭이 뒤로 밀려 키 입력이 안 먹는다 → 매번 앞으로
if (__t && !__t.active) { await tc.bringToFront().catch(() => {}); await sleep(800); }
for (let i = 0; i < 30 && !(await tc.locator('[data-slate-editor=true]').count()); i++) await sleep(1000);
await tc.evaluate(() => {
  if (window.__tcHook) return; window.__tcHook = true; window.__tcLog = [];
  const oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u) { this.__tu = u; return oo.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function (b) {
    this.addEventListener('load', () => { const u = String(this.__tu || '');
      if (/\/api\/speak\/batch\/(post|get)|\/files\/speak\//.test(u)) window.__tcLog.push({ u, b: String(b || ''), r: String(this.responseText || ''), t: Date.now() }); });
    return os.apply(this, arguments); };
  const of = window.fetch;
  window.fetch = async function (i, o) { const u = typeof i === 'string' ? i : (i && i.url) || ''; const r = await of.apply(this, arguments);
    if (/\/api\/speak\/batch\/(post|get)|\/files\/speak\//.test(u)) r.clone().text().then(x => window.__tcLog.push({ u, b: String((o && o.body) || ''), r: x, t: Date.now() }));
    return r; };
});
const tcText = () => tc.evaluate(() => [...document.querySelectorAll('[data-slate-editor=true] p')].map(p => p.innerText.replace(/\n/g, '').trim()));
// 단락별 성우 이름 (앞 단락과 같은 성우면 칩에 이름이 비어 있어 앞 이름을 물려받는다)
const tcChips = () => tc.evaluate(() => { let prev = ''; return [...document.querySelectorAll('button.actor-selector')].map(b => (prev = b.innerText.trim() || prev)); });
"""


class TypecastConnector:
    def __init__(self, project_url: str = DEFAULT_PROJECT, account: str = "u2"):
        self.url = project_url
        self.account = account

    # ------------------------------------------------------------------ repl
    def _repl(self, body: str, timeout: int = 115) -> str:
        code = (_JS_TAB % {"url": json.dumps(self.url)}) + body
        try:
            p = subprocess.run([ASIDE_BIN, "--account", self.account, "repl", code],
                               capture_output=True, text=True, timeout=timeout + 10)
        except subprocess.TimeoutExpired:
            raise TypecastError("Aside REPL 시간 초과")
        out = p.stdout + ("\n" + p.stderr if p.stderr else "")
        if "[error" in out and "OK:" not in out:
            raise TypecastError(out.strip()[-800:])
        return out

    @staticmethod
    def _marker(out: str, key: str):
        for line in out.splitlines():
            if line.startswith(key):
                return line[len(key):].strip()
        return None

    def state(self) -> dict:
        out = self._repl("console.log('STATE:' + JSON.stringify({ text: await tcText(), chips: await tcChips() }));")
        return json.loads(self._marker(out, "STATE:"))

    # ------------------------------------------------------------------ 편집
    def reopen(self) -> None:
        """뒤로 밀린(비활성) Typecast 탭은 키 입력이 안 먹으므로 닫고 새 탭(활성)으로 다시 연다"""
        code = r"""
const __id = %s;
if (!(await listBrowserTabs()).some(x => (x.url || '').includes(__id) && x.active)) { await openTab(%s); await sleep(7000); }
console.log('OK:');
""" % (json.dumps(self.url.split("/")[-1]), json.dumps(self.url))
        subprocess.run([ASIDE_BIN, "--account", self.account, "repl", code], capture_output=True, text=True, timeout=120)

    def clear(self) -> None:
        """프로젝트의 기존 글을 모두 지운다 (단락 1개, 빈 상태)"""
        self.reopen()
        for _ in range(3):
            self._repl(r"""
await tc.bringToFront().catch(() => {});
await tc.locator('[data-slate-editor=true]').first().click(); await sleep(300);
await tc.keyboard.press('Meta+a'); await sleep(200); await tc.keyboard.press('Backspace'); await sleep(400);
await tc.keyboard.press('Meta+a'); await sleep(200); await tc.keyboard.press('Backspace'); await sleep(600);
console.log('OK:');
""")
            st = self.state()
            if not "".join(st["text"]).strip():
                return
        raise TypecastError(f"글을 다 지우지 못했습니다: {st['text'][:3]}")

    def type_paragraphs(self, texts: list) -> None:
        """빈 편집기에 단락을 순서대로 입력 (단락 사이 Enter)"""
        body = r"""
const __texts = %s;
await tc.locator('[data-slate-editor=true]').first().click(); await sleep(300);
await tc.keyboard.press('Meta+ArrowDown'); await sleep(200);
for (let i = 0; i < __texts.length; i++) {
  if (i > 0) { await tc.keyboard.press('Enter'); await sleep(250); }
  await tc.keyboard.insertText(__texts[i]); await sleep(250);
}
await sleep(800);
console.log('OK:' + JSON.stringify(await tcText()));
""" % json.dumps(texts, ensure_ascii=False)
        out = self._repl(body, timeout=115)
        got = json.loads(self._marker(out, "OK:"))
        norm = lambda s: re.sub(r"\s+", "", s)
        if [norm(x) for x in got] != [norm(x) for x in texts]:
            raise TypecastError(f"입력 결과가 대본과 다릅니다: {got}")

    def set_actor(self, idx: int, name: str) -> None:
        """idx 번째 단락의 성우를 이름으로 지정"""
        out = self._repl(r"""
const __i = %d, __name = %s;
const chips0 = await tcChips();
if (chips0[__i] !== __name) {
  await tc.keyboard.press('Escape').catch(() => {}); await sleep(300);
  await tc.evaluate((i) => document.querySelectorAll('button.actor-selector')[i].click(), __i); await sleep(1800);
  await tc.evaluate(() => { const b = [...document.querySelectorAll('[role=dialog] button')].find(x => x.getAttribute('aria-label') === '보이스 찾기' || x.innerText.trim() === '보이스 찾기'); b && b.click(); }); await sleep(900);
  await tc.locator('[role=dialog] input[type=search]').fill(__name); await sleep(2200);
  const ok = await tc.evaluate((n) => {
    const bs = [...document.querySelectorAll('[role=dialog] button.text-left')].filter(b => (b.querySelector('span.font-semibold') || {}).innerText?.trim() === n);
    if (!bs.length) return false; bs[bs.length - 1].click(); return true; }, __name);
  await sleep(1500);
  if (!ok) { await tc.keyboard.press('Escape'); console.log('NOVOICE:' + __name); }
}
console.log('OK:' + JSON.stringify(await tcChips()));
""" % (idx, json.dumps(name, ensure_ascii=False)))
        if self._marker(out, "NOVOICE:"):
            raise TypecastError(f"성우를 찾지 못했습니다: {name}")
        chips = json.loads(self._marker(out, "OK:"))
        if idx >= len(chips) or chips[idx] != name:
            raise TypecastError(f"{idx}번 단락 성우 지정 실패: {chips}")

    def set_emotion(self, idx: int, label: str) -> str:
        """idx 번째 단락 전체를 선택하고 감정을 지정. 실제로 적용된 감정을 돌려준다(없으면 일반)"""
        out = self._repl(r"""
const __i = %d, __label = %s;
await tc.evaluate((i) => {
  const p = document.querySelectorAll('[data-slate-editor=true] p')[i];
  const ss = p.querySelectorAll('[data-slate-string]'); const a = ss[0].firstChild, b = ss[ss.length - 1].firstChild;
  const r = document.createRange(); r.setStart(a, 0); r.setEnd(b, b.textContent.length);
  const s = window.getSelection(); s.removeAllRanges(); s.addRange(r); document.dispatchEvent(new Event('selectionchange'));
}, __i);
await sleep(500);
await tc.getByRole('button', { name: '감정' }).click(); await sleep(1200);
const avail = await tc.evaluate(() => [...document.querySelectorAll('[role=dialog] button')].map(b => b.innerText.trim()).filter(Boolean));
const pick = avail.includes(__label) ? __label : '일반';
await tc.evaluate((l) => { const b = [...document.querySelectorAll('[role=dialog] button')].find(x => x.innerText.trim() === l); b && b.click(); }, pick);
await sleep(900);
await tc.keyboard.press('Escape').catch(() => {});
console.log('OK:' + JSON.stringify({ pick, avail }));
""" % (idx, json.dumps(label, ensure_ascii=False)))
        return json.loads(self._marker(out, "OK:"))["pick"]

    # ------------------------------------------------------------------ 음성
    def _play(self, idx: int = 0) -> None:
        """idx 번째 단락 맨 앞에 커서를 두고 재생 시작.
        기록은 비우지 않는다 — 한 번 만든 음성은 다시 재생해도 네트워크 요청이 없어서, 처음 만들 때의 기록으로 찾는다"""
        self._repl(r"""
await tc.locator('[data-slate-editor=true] p').nth(%d).click(); await sleep(200);
await tc.keyboard.press('Home'); await sleep(200);
await tc.getByRole('button', { name: 'Play' }).click(); await sleep(500);
console.log('OK:');
""" % idx)

    def _pause(self) -> None:
        self._repl("await tc.getByRole('button', { name: 'Pause' }).click().catch(() => {}); console.log('OK:');")

    def _log(self) -> list:
        out = self._repl("console.log('LOG:' + JSON.stringify(await tc.evaluate(() => window.__tcLog || [])));")
        return json.loads(self._marker(out, "LOG:") or "[]")

    @staticmethod
    def _speaks(log: list) -> list:
        """batch/get 응답 → 만들어진 speak 목록 (만든 순서): text, file_key, duration, emotion"""
        res = {}
        for e in log:
            if "batch/get" not in e["u"]:
                continue
            try:
                items = json.loads(e["r"])["result"]
            except Exception:
                continue
            for it in items:
                if it.get("status") != "done":
                    continue
                q = it.get("query", {})
                m = re.search(r"/files/speak/([A-Za-z0-9=_-]+)", json.dumps(it.get("audio", {})))
                res[it["_id"]["$oid"]] = {"text": q.get("text", ""), "file_key": m.group(1) if m else None,
                                          "duration": it.get("duration"), "emotion": q.get("emotion_label"),
                                          "created": it["_id"].get("created_date", 0)}
        return sorted(res.values(), key=lambda x: x["created"])

    @staticmethod
    def _cdn(log: list) -> dict:
        """files/speak/<key>/cloudfront 응답 → key: CDN wav 주소"""
        out = {}
        for e in log:
            m = re.search(r"/files/speak/([A-Za-z0-9=_-]+)/cloudfront", e["u"])
            if m:
                try:
                    out[m.group(1)] = json.loads(e["r"])["result"]
                except Exception:
                    pass
        return out

    @staticmethod
    def _match(line_text: str, speaks: list):
        """대사 하나 = speak 하나, 또는 문장별로 나뉜 speak 여러 개(순서대로 이어 붙이면 대사)"""
        norm = lambda s: re.sub(r"[\s.,!?…~'\"]", "", s)
        want = norm(line_text)
        for i in range(len(speaks) - 1, -1, -1):          # 가장 최근 것부터
            acc, seq = "", []
            for s in speaks[i:]:
                acc += norm(s["text"])
                seq.append(s)
                if acc == want:
                    return seq
                if not want.startswith(acc):
                    break
        return None

    def render_cdn(self, lines: list, out_dir: Path, max_wait: int = 300) -> list:
        """편집기를 처음부터 재생하면서 미리듣기 wav(CDN)를 받아 lines[i]['file'] 에 저장"""
        self._play(0)
        t0, done = time.time(), {}
        while time.time() - t0 < max_wait:
            time.sleep(8)
            log = self._log()
            speaks, cdn = self._speaks(log), self._cdn(log)
            for i, ln in enumerate(lines):
                if i in done:
                    continue
                seq = self._match(ln["text"], speaks)
                if seq and all(s["file_key"] in cdn for s in seq):
                    done[i] = [cdn[s["file_key"]] for s in seq]
                    ln["emotion_typecast"] = seq[0]["emotion"]
            print(f"[typecast] 받은 대사 {len(done)}/{len(lines)}", flush=True)
            if len(done) == len(lines):
                break
        self._pause()
        missing = [ln["text"] for i, ln in enumerate(lines) if i not in done]
        if missing:
            raise TypecastError(f"음성을 받지 못한 대사: {missing}")
        for i, ln in enumerate(lines):
            f = out_dir / ln["file"]
            f.parent.mkdir(parents=True, exist_ok=True)
            parts = []
            for k, url in enumerate(done[i]):
                part = f.with_suffix(f".part{k}.wav") if len(done[i]) > 1 else f
                urllib.request.urlretrieve(url, part)
                parts.append(part)
            if len(parts) > 1:   # 문장별 조각을 0.25초 쉼으로 잇기
                gap = f.with_suffix(".gap.wav")
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.25", str(gap)], check=True)
                seq = [x for p in parts for x in (p, gap)][:-1]
                inputs = sum((["-i", str(x)] for x in seq), [])
                subprocess.run(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex",
                                "".join(f"[{k}:a]aresample=44100,aformat=channel_layouts=mono[a{k}];" for k in range(len(seq))) +
                                "".join(f"[a{k}]" for k in range(len(seq))) + f"concat=n={len(seq)}:v=0:a=1[o]",
                                "-map", "[o]", str(f)], check=True)
                for x in parts + [gap]:
                    x.unlink(missing_ok=True)
        return lines

    def render_record(self, lines: list, out_dir: Path) -> list:
        """단락을 하나씩 재생하며 시스템 소리를 녹음 (lib.com.jatu.recoder). 먼저 render_cdn 으로 길이를 알아 둔다"""
        from lib.com.jatu.recoder import record
        tmp = out_dir / "_cdn"
        probe = [dict(ln, file=f"{i:02d}.wav") for i, ln in enumerate(lines)]
        self.render_cdn(probe, tmp)
        for i, ln in enumerate(lines):
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                        str(tmp / probe[i]["file"])], capture_output=True, text=True).stdout or 0)

            def play(i=i, dur=dur):
                self._play(i)
                time.sleep(dur + 0.3)
                self._pause()
            f = (out_dir / ln["file"]).with_suffix(".mp3")
            f.parent.mkdir(parents=True, exist_ok=True)
            record(play, f, tail=0.2)
            ln["file"] = str(Path(ln["file"]).with_suffix(".mp3"))
            print(f"[typecast] 녹음 {i + 1}/{len(lines)} {f.name}", flush=True)
        return lines

    # ------------------------------------------------------------------ 한 번에
    def run(self, cast: dict, lines: list, out_dir: Path, capture: str = "cdn") -> list:
        """cast: 화자→성우, lines: [{shot, who, emotion, text, sub}] → 음성 저장 후 lines 반환"""
        print(f"[typecast] 프로젝트 비우기: {self.url}", flush=True)
        self.clear()
        print(f"[typecast] 단락 {len(lines)}개 입력", flush=True)
        self.type_paragraphs([ln["text"] for ln in lines])
        count = {}
        for i, ln in enumerate(lines):
            actor = cast[ln["who"]]
            self.set_actor(i, actor)
            ln["actor"] = actor
            ln["emotion_applied"] = self.set_emotion(i, ln.get("emotion") or "일반")
            count[(ln["shot"], ln["who"])] = count.get((ln["shot"], ln["who"]), 0) + 1
            n = sum(1 for x in lines[: i + 1] if x["shot"] == ln["shot"])
            ln["file"] = f"{ln['who']}/{ln['shot']}_{n}.wav"
            print(f"[typecast] {i + 1:02d} {ln['shot']} {ln['who']}={actor} [{ln['emotion_applied']}] {ln['text']}", flush=True)
        print(f"[typecast] 음성 받기 ({capture})", flush=True)
        lines = self.render_cdn(lines, out_dir) if capture == "cdn" else self.render_record(lines, out_dir)
        for ln in lines:
            f = out_dir / ln["file"]
            ln["speech"] = round(float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                capture_output=True, text=True).stdout.strip() or 0), 2)
        (out_dir / "lines.json").write_text(json.dumps(lines, ensure_ascii=False, indent=1))
        return lines


# ---------------------------------------------------------------------- 대본 읽기
def _table(md: str, first_col: str) -> list:
    rows, head = [], None
    for line in md.splitlines():
        if not line.strip().startswith("|"):
            head = None if not line.strip() else head
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if head is None:
            if cells and cells[0] == first_col:
                head = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append(dict(zip(head, cells)))
    return rows


def parse_script(path: Path):
    md = Path(path).read_text(encoding="utf-8")
    cast = {r["배역"]: r["성우"] for r in _table(md, "배역")}
    lines = []
    for r in _table(md, "숏"):
        text = r.get("대사", "").strip()
        if not text:
            continue
        emo = r.get("감정", "").strip() or "일반"
        if emo not in EMOTIONS:
            emo = "일반"
        lines.append({"shot": r["숏"], "who": r["화자"], "emotion": emo, "text": text,
                      "sub": (r.get("자막") or "").strip() or text})
    if not cast or not lines:
        raise TypecastError(f"대본 표를 읽지 못했습니다 (배역 표 {len(cast)}, 대사 {len(lines)}): {path}")
    unknown = {ln["who"] for ln in lines} - set(cast)
    if unknown:
        raise TypecastError(f"배역 표에 성우가 없는 화자: {unknown}")
    return cast, lines


def main(argv=None):
    ap = argparse.ArgumentParser(description="Typecast 대본 → 화자별 음성")
    ap.add_argument("--script", help="03_대본.md (배역 표 + 대사 표)")
    ap.add_argument("--out", help="저장 폴더 (기본: 대본 폴더/voice/typecast)")
    ap.add_argument("--project", default=DEFAULT_PROJECT)
    ap.add_argument("--account", default="u2")
    ap.add_argument("--capture", choices=["cdn", "record"], default="cdn")
    ap.add_argument("--audition", help="성우 이름들(쉼표) — 같은 문장으로 비교 녹음")
    ap.add_argument("--text", help="--audition 에 쓸 문장")
    ap.add_argument("--emotion", default="일반")
    a = ap.parse_args(argv)
    tc = TypecastConnector(a.project, a.account)

    if a.audition:
        names = [x.strip() for x in a.audition.split(",") if x.strip()]
        out = Path(a.out or ROOT_DIR / "audition")
        lines = [{"shot": "A", "who": n, "emotion": a.emotion, "text": a.text} for n in names]
        # 같은 문장이면 CDN 매칭이 겹치므로 끝에 번호 공백을 달리하지 않고 한 명씩 진행
        for ln in lines:
            r = tc.run({ln["who"]: ln["who"]}, [dict(ln)], out, a.capture)[0]
            print(f"AUDITION {r['actor']} {r['speech']}s → {out / r['file']}")
        return 0

    script = Path(a.script)
    cast, lines = parse_script(script)
    out = Path(a.out or script.parent / "voice" / "typecast")
    lines = tc.run(cast, lines, out, a.capture)
    print(f"완료: {len(lines)}줄 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
