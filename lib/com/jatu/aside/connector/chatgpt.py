"""ChatGPT 이미지 생성(chatgpt.com/images) 커넥터 — Aside Browser 버전.

webtoon2/lib/com/jatu/connector/chatgpt.py (agent-browser 버전)를 Aside로 옮긴 것.
브라우저 조작은 `aside --account <id> repl` (Aside MCP의 repl 도구와 같은 엔진)로 한다.
기본 계정은 u1 = hwangjiyoung1977 프로필 (ChatGPT 로그인되어 있음).

목적: **같은 대화(conversation) 안에서 계속 이미지를 생성**해 캐릭터·화풍의 일관성을 유지한다.

동작:
    1. 최초 생성은 https://chatgpt.com/ 새 채팅에서 이미지 생성을 요청해 시작한다.
    2. 첫 프롬프트를 보내면 URL 이 https://chatgpt.com/c/<대화 ID> 로 바뀐다.
    3. 그 ID 를 project/<name>/session.json 의 projects["chatgpt-<thread>"] 에 기록한다.
    4. 다음 생성부터는 기록된 대화 URL 로 다시 들어가 이어서 생성한다.

Aside REPL은 한 번에 120초까지만 돌기 때문에 한 컷을 짧은 호출로 나눈다:
    send(프롬프트 입력 + 참조 첨부 + 전송) → poll(생성 중/새 이미지 확인, 반복) → save(이미지 저장)
탭이 닫혀도 대화 URL 로 다시 열어 이어 간다.

사용 예 (youtube3 루트):
    PYTHONPATH=. python3 -m lib.com.jatu.aside.connector.chatgpt \\
        --project jatu002 --thread cuts --json project/jatu002/prompts/image-prompts.json --skip-existing
    PYTHONPATH=. python3 -m lib.com.jatu.aside.connector.chatgpt \\
        --project jatu002 --prompt-file p.txt --ref res/basic2.jpeg --out res/test.png

UI 셀렉터(2026-09-30 실측, 바뀌면 여기만 고친다):
    입력창      .ProseMirror (contenteditable)
    보내기      form button[aria-label="보내기"] (예전: data-testid="send-button")
    중지(생성중) form button[aria-label*="중지"] (예전: data-testid="stop-button")
    파일 첨부   input[type=file][accept="image/*"] (숨김, multiple)
    결과 이미지 마지막 사용자 메시지 뒤의 큰 img (estuary / oaiusercontent)
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[5]
ASIDE_BIN = os.path.expanduser("~/.local/bin/aside")
if not os.path.exists(ASIDE_BIN):
    ASIDE_BIN = shutil.which("aside") or "aside"

# /images 화면은 전송해도 /c/ 주소가 생기지 않아(2026-09-30 실측) 탭이 닫히면 이어 갈 수 없다.
# 그래서 일반 채팅에서 이미지 생성을 요청한다 → 첫 전송 뒤 /c/<id> 대화가 생긴다.
HOME_URL = "https://chatgpt.com/"
IMAGE_PREFIX = "Generate ONE image (use the image generation tool, do not reply with text only):\n"
SEL_COMPOSER = ".ProseMirror"
SEL_SEND = 'button[data-testid="send-button"], form button[aria-label="보내기"], form button[aria-label="Send prompt"]'
SEL_STOP = 'button[data-testid="stop-button"], form button[aria-label*="중지"], form button[aria-label*="Stop"]'


class ChatGPTError(RuntimeError):
    pass


# 대화 탭을 찾아 붙거나(없으면 연다) 목표 URL 로 맞춘다. 모든 REPL 코드 앞에 붙는다.
_JS_TAB = """
const __TARGET__ = %(target)s;
const __tabs = await listBrowserTabs();
let __t = __tabs.find(t => __TARGET__.includes('/c/') ? t.url.includes(__TARGET__.split('/c/')[1]) : false);
const page = __t ? await attachBrowserTab(__t.targetId) : await openTab(__TARGET__);
if (!__t) await sleep(5000);
if (!(await page.evaluate(() => location.href)).startsWith(__TARGET__.replace(/[/]$/, ''))) { await page.goto(__TARGET__); await sleep(5000); }
for (let i = 0; i < 20 && !(await page.locator('%(composer)s').count()); i++) await sleep(1000);
"""

_JS_STATE = """
const __state = await page.evaluate(() => {
  // 2026-09-30: data-message-author-role 이 사라짐 → 화면 낭독용 제목 '내가 한 말:' 로 사용자 턴을 찾는다
  const users = [...document.querySelectorAll('main h4, main h5, main h6')]
    .filter(h => /^(내가 한 말|You said)/.test((h.textContent || '').trim()) || h.getAttribute('data-conversation-role') === 'user');
  const boxes = users.map(h => h.parentElement);  // .group 은 두 턴을 함께 감싸므로 제목 바로 위 블록만
  const last = users[users.length - 1];
  const userSrc = new Set(boxes.flatMap(u => [...u.querySelectorAll('img')].map(i => i.src)));
  const imgs = [...document.querySelectorAll('main img')]
    .filter(i => !boxes.some(b => b.contains(i)) && !userSrc.has(i.src))
    .filter(i => !i.closest('form'))  // 2026-10-01: 입력창에 첨부한 참조 미리보기(blob:)가 결과로 잡히던 문제
    .filter(i => (i.naturalWidth || 0) >= 400 && /^blob:|estuary|oaiusercontent|public_content/.test(i.src || ''))
    .filter(i => !last || (last.compareDocumentPosition(i) & Node.DOCUMENT_POSITION_FOLLOWING))
    .map(i => ({ src: i.src, w: i.naturalWidth, h: i.naturalHeight }));
  let gen = !!document.querySelector('%(stop)s');
  if (!gen && users.length) {
    // 2026-10-27: 사용자 프롬프트 속 '숫자+퍼센트' 글자를 진행률로 오인하지 않게 마지막 사용자 메시지 뒤의 글자만 본다
    const all = document.querySelector('main')?.innerText || '';
    const mine = (last?.parentElement?.innerText || '').trim().slice(-200);
    const at = mine ? all.lastIndexOf(mine) : -1;
    const t = (at >= 0 ? all.slice(at + mine.length) : all).slice(-800);
    gen = /생성하는 중|이미지 생성 중|만들고 있|생각 중|Creating image|Generating|Planned the image|[0-9]{1,3}%%/.test(t);
  }
  return { url: location.href, users: users.length, gen, imgs,
           login: !!document.querySelector('%(composer)s') };
});
console.log('STATE:' + JSON.stringify(__state));
"""


class AsideChatGPTConnector:
    name = "aside-chatgpt"
    GEN_TIMEOUT_S = 480
    IDLE_LIMIT_S = 600   # 2026-10-01: 응답이 5분 넘게 늦게 시작하는 경우가 있어 300 → 600
    orientation = "portrait"   # 결과 이미지 방향: portrait / landscape / any

    def __init__(self, project: str, thread: Optional[str] = None, account: str = "u1"):
        self.project = project
        self.account = account
        self.platform_key = f"chatgpt-{thread}" if thread else "chatgpt"
        self.session_file = ROOT_DIR / "project" / project / "session.json"
        self.conversation_id = self._read_session().get("projects", {}).get(self.platform_key)
        self.work_dir = Path(tempfile.mkdtemp(prefix="aside-chatgpt-"))

    # ---------------------------------------------------------------- session
    def _read_session(self) -> dict:
        try:
            return json.loads(self.session_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _remember(self, url: str) -> None:
        # 2026-10-09: 전송 직후 /c/local-chatgpt%3A<uuid> 같은 임시 주소가 잠깐 생긴다.
        # 이걸 기록해 다시 열면 '이 ChatGPT 대화를 불러올 수 없습니다'가 되므로 진짜 대화 주소만 기록한다.
        if "/c/" not in url or "local-chatgpt" in url:
            return
        cid = url.split("/c/", 1)[1].split("?", 1)[0].split("#", 1)[0].strip("/")
        if not cid or cid == self.conversation_id:
            return
        self.conversation_id = cid
        data = self._read_session()
        data.setdefault("projects", {})[self.platform_key] = cid
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        self.session_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[chatgpt] 대화 기록: {self.project}/{self.platform_key} → {cid}", flush=True)

    def new_conversation(self) -> None:
        self.conversation_id = None

    @property
    def target_url(self) -> str:
        return f"https://chatgpt.com/c/{self.conversation_id}" if self.conversation_id else HOME_URL

    # ------------------------------------------------------------------ repl
    def _repl(self, body: str, timeout: int = 150) -> str:
        code = (_JS_TAB % {"target": json.dumps(self.target_url), "composer": SEL_COMPOSER}) + body
        cmd = [ASIDE_BIN, "--account", self.account, "repl", code]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=self.work_dir)
        except subprocess.TimeoutExpired:
            raise ChatGPTError("Aside REPL 시간 초과")
        out = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
        if proc.returncode != 0 and "STATE:" not in out and "SENT:" not in out and "SAVED:" not in out:
            raise ChatGPTError(out.strip()[-600:])
        return out

    @staticmethod
    def _marker(out: str, key: str) -> Optional[str]:
        for line in out.splitlines():
            if line.startswith(key):
                return line[len(key):].strip()
        return None

    def state(self) -> dict:
        out = self._repl(_JS_STATE % {"stop": SEL_STOP, "composer": SEL_COMPOSER}, timeout=90)
        raw = self._marker(out, "STATE:")
        if not raw:
            raise ChatGPTError("상태를 읽지 못했습니다: " + out[-300:])
        st = json.loads(raw)
        self._remember(st.get("url", ""))
        return st

    # ------------------------------------------------------------------ send
    def _send(self, prompt: str, refs: list[str]) -> None:
        files = [str(Path(r).resolve()) for r in refs]
        for f in files:
            if not os.path.exists(f):
                raise ChatGPTError(f"참조 파일이 없습니다: {f}")
        body = f"""
if (!(await page.locator('{SEL_COMPOSER}').count())) throw new Error('입력창이 없습니다 (로그인 확인 필요)');
const __href = () => page.evaluate(() => location.href);
const __start = await __href();
// 이전 시도가 남긴 초안(첨부·글자)을 지운다 — ChatGPT 는 보내지 못한 입력을 초안으로 남긴다
for (let i = 0; i < 10; i++) {{
  const rm = await page.evaluate(() => {{ const b = [...document.querySelectorAll('form button')].find(x => /제거$|^Remove/.test(x.getAttribute('aria-label') || '')); if (b) {{ b.click(); return true; }} return false; }});
  if (!rm) break; await sleep(400);
}}
// 남은 글자 지우기 (Aside 에서는 Cmd+A 같은 단축키가 먹지 않아 선택 API 로 지운다)
await page.evaluate(() => {{ const c = document.querySelector('{SEL_COMPOSER}'); if (c && c.innerText.trim()) {{ c.focus(); const r = document.createRange(); r.selectNodeContents(c); const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); document.execCommand('delete'); }} }});
await sleep(300);
if (await page.evaluate(() => (document.querySelector('{SEL_COMPOSER}')?.innerText || '').trim().length)) throw new Error('입력창의 이전 글자를 지우지 못했습니다');
await page.locator('{SEL_COMPOSER}').first().click(); await sleep(200);
await page._sendToTarget('Input.insertText', {{ text: {json.dumps(prompt)} }});
await sleep(800);
if (!(await page.evaluate(() => (document.querySelector('{SEL_COMPOSER}')?.innerText || '').trim().length))) {{
  await page.locator('{SEL_COMPOSER}').first().click(); await page.keyboard.type({json.dumps(prompt)}); await sleep(800);
}}
if (!(await page.evaluate(() => (document.querySelector('{SEL_COMPOSER}')?.innerText || '').trim().length))) throw new Error('프롬프트가 입력되지 않았습니다');
const files = {json.dumps(files)};
if (files.length) {{
  const {{ root }} = await page._sendToTarget('DOM.getDocument', {{ depth: -1, pierce: true }});
  const {{ nodeIds }} = await page._sendToTarget('DOM.querySelectorAll', {{ nodeId: root.nodeId, selector: 'input[type=file]' }});
  const accepts = await page.evaluate(() => [...document.querySelectorAll('input[type=file]')].map(f => f.accept));
  const idx = accepts.findIndex(a => a === 'image/*');
  if (idx < 0 || !nodeIds[idx]) throw new Error('이미지 첨부 input 을 찾지 못했습니다');
  await page._sendToTarget('DOM.setFileInputFiles', {{ files, nodeId: nodeIds[idx] }});
  // 첨부 썸네일(제거 버튼)이 파일 수만큼 생길 때까지 기다린 뒤, 업로드가 끝나도록 조금 더 둔다
  for (let i = 0; i < 60; i++) {{
    const n = await page.evaluate(() => [...document.querySelectorAll('form button')].filter(x => /제거$|^Remove/.test(x.getAttribute('aria-label') || '')).length);
    if (n >= files.length) break; await sleep(1000);
  }}
  await sleep(6000);
}}
// 보내기 → 주소가 바뀌거나 사용자 턴이 생길 때까지 확인, 안 되면 다시 보낸다 (업로드 중이면 전송이 무시됨)
let sent = false;
for (let t = 0; t < 6 && !sent; t++) {{
  const enabled = await page.evaluate(() => {{ const b = document.querySelector('{SEL_SEND}'); return !!(b && !b.disabled); }});
  // Enter·locator 클릭은 전송되지 않고, DOM click 은 된다 (2026-09-30 실측)
  if (enabled) await page.evaluate(() => {{ const b = document.querySelector('{SEL_SEND}'); if (b) b.click(); }});
  for (let i = 0; i < 10; i++) {{
    await sleep(1000);
    const left = await page.evaluate(() => (document.querySelector('{SEL_COMPOSER}')?.innerText || '').trim().length);
    if ((await __href()) !== __start || !left) {{ sent = true; break; }}
  }}
}}
if (!sent) throw new Error('전송되지 않았습니다 (입력이 그대로 남아 있음)');
// 임시 주소(/c/local-chatgpt%3A…)가 진짜 대화 주소(/c/<uuid>)로 바뀔 때까지 기다린다 (2026-10-09)
const __real = (h) => h.includes('/c/') && !h.includes('local-chatgpt');
for (let i = 0; i < 60 && !__real(await __href()); i++) await sleep(1000);
await sleep(2000);
console.log('SENT:' + (await __href()));
"""
        out = self._repl(body, timeout=170)
        url = self._marker(out, "SENT:")
        if not url:
            raise ChatGPTError("전송 실패: " + out.strip()[-500:])
        print(f"[chatgpt] 전송 완료: {url}", flush=True)
        self._remember(url)
        if "/c/" not in url and not self.conversation_id:
            raise ChatGPTError("전송 후 대화 주소(/c/)를 얻지 못했습니다: " + url)

    # ------------------------------------------------------------------ save
    def _orient_js(self) -> str:
        """결과 이미지로 인정할 방향 (portrait=세로만, landscape=가로만, any=모두). 16:9 롱폼은 landscape"""
        return {"portrait": "i.naturalHeight > i.naturalWidth", "landscape": "i.naturalWidth > i.naturalHeight"}.get(self.orientation, "true")

    def save_image(self, src: str, out_path: str) -> str:
        body = f"""
// blob: 주소는 그 페이지 안에서만 유효하다. 탭을 새로 열면 주소가 바뀌므로,
// 주소로 못 찾으면 마지막 사용자 턴 뒤의 마지막 이미지(orientation 방향)를 다시 고른다 (2026-09-30)
for (let i = 0; i < 20; i++) {{
  const ready = await page.evaluate(() => [...document.querySelectorAll('main img')].some(i => i.naturalWidth >= 400 && {self._orient_js()}));
  if (ready) break; await sleep(1000);
}}
const data = await page.evaluate(async (src0) => {{
  const users = [...document.querySelectorAll('main h4, main h5, main h6')]
    .filter(h => /^(내가 한 말|You said)/.test((h.textContent || '').trim()) || h.getAttribute('data-conversation-role') === 'user');
  const boxes = users.map(h => h.parentElement);
  const last = users[users.length - 1];
  const cands = [...document.querySelectorAll('main img')]
    .filter(i => !boxes.some(b => b.contains(i)) && !i.closest('form') && i.naturalWidth >= 400 && {self._orient_js()})
    .filter(i => !last || (last.compareDocumentPosition(i) & Node.DOCUMENT_POSITION_FOLLOWING));
  const byId = [...document.querySelectorAll('img')].find(i => i.src === src0);
  const src = byId ? src0 : (cands.length ? cands[cands.length - 1].src : src0);
  try {{
    const r = await fetch(src); const b = await r.blob();
    if (b.type && b.type.startsWith('image/')) return await new Promise(res => {{ const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(b); }});
  }} catch (e) {{}}
  const img = [...document.querySelectorAll('img')].find(i => i.src === src);
  if (img && img.naturalWidth) {{ const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight; c.getContext('2d').drawImage(img, 0, 0); return c.toDataURL('image/png'); }}
  return 'err';
}}, {json.dumps(src)});
console.log('SAVED:' + data);
"""
        out = self._repl(body, timeout=120)
        data_url = self._marker(out, "SAVED:") or ""
        if not data_url.startswith("data:"):
            raise ChatGPTError("이미지 fetch 실패")
        head, b64 = data_url.split(",", 1)
        raw = base64.b64decode(b64)
        out_file = Path(out_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        if out_file.suffix.lower() == ".png" and "image/png" not in head:
            tmp = self.work_dir / ("src" + (".webp" if "webp" in head else ".jpg"))
            tmp.write_bytes(raw)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), str(out_file)], check=True)
        else:
            out_file.write_bytes(raw)
        return str(out_file)

    @staticmethod
    def _dhash(path: str) -> int:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", "scale=9:8,format=gray",
                              "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
        bits = 0
        for y in range(8):
            for x in range(8):
                bits = (bits << 1) | (1 if raw[y * 9 + x] > raw[y * 9 + x + 1] else 0)
        return bits

    def _echo_of(self, saved: str, refs: list[str]) -> Optional[str]:
        """저장한 이미지가 첨부 참조와 거의 같으면 그 파일명 (ChatGPT 가 첨부만 되돌려 준 경우)."""
        try:
            h = self._dhash(saved)
        except Exception:
            return None
        for r in refs:
            try:
                if bin(h ^ self._dhash(r)).count("1") <= 8:
                    return os.path.basename(r)
            except Exception:
                continue
        return None

    # -------------------------------------------------------------- generate
    def generate(self, prompt: str, refs: Optional[list[str]] = None, out_path: str = "",
                 timeout_s: Optional[int] = None, portrait: bool = True, echo_check: bool = True) -> str:
        refs = refs or []
        timeout_s = timeout_s or self.GEN_TIMEOUT_S
        # 이전 응답이 아직 생성 중이면 기다린다
        for _ in range(60):
            if not self.state().get("gen"):
                break
            time.sleep(10)
        self._send(IMAGE_PREFIX + prompt.strip(), refs)
        sent_at = last_activity = time.monotonic()
        hard_cap = sent_at + timeout_s + 1200
        last_src, stable_since, new_src = None, 0.0, None
        while time.monotonic() < hard_cap:
            time.sleep(8)
            try:
                st = self.state()
            except ChatGPTError as e:
                print(f"[chatgpt] 상태 확인 실패(재시도): {str(e)[:120]}", flush=True)
                continue
            orient = self.orientation if portrait else "any"
            imgs = [i for i in st["imgs"] if orient == "any" or not (i["w"] and i["h"])
                    or (i["h"] > i["w"] if orient == "portrait" else i["w"] > i["h"])]
            if imgs or st["gen"]:
                last_activity = time.monotonic()
            elif time.monotonic() - last_activity > self.IDLE_LIMIT_S:
                raise ChatGPTError(f"{self.IDLE_LIMIT_S}s 동안 생성 표시도 이미지도 없음 — 무응답")
            if imgs:
                cur = imgs[-1]["src"]
                if cur != last_src:
                    last_src, stable_since = cur, time.monotonic()
                if not st["gen"] or time.monotonic() - stable_since >= 20:
                    new_src = cur
                    break
        if not new_src:
            raise ChatGPTError(f"이미지가 {timeout_s + 1200}s 안에 생성되지 않았습니다")
        time.sleep(2)
        out_path = out_path or str(self.work_dir / f"chatgpt-{int(time.time())}.png")
        saved = self.save_image(new_src, out_path)
        # 일부러 참조와 같은 구도를 요청한 컷(allow_similar)은 첨부 되돌림 검사를 건너뛴다
        echo = self._echo_of(saved, refs) if echo_check else None
        if echo:
            os.replace(saved, saved + ".attachment-echo")
            raise ChatGPTError(f"첨부 파일({echo})이 결과로 저장되려 했습니다 — 생성 실패로 처리")
        print(f"[chatgpt] 저장: {saved}", flush=True)
        return saved


ChatGPTConnector = AsideChatGPTConnector


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="chatgpt.com/images 이미지 생성 (Aside)")
    ap.add_argument("--project", required=True, help="대화 ID를 기록할 프로젝트 (project/<name>/session.json)")
    ap.add_argument("--thread", help="프로젝트 안의 대화 이름 (예: cuts, sheets)")
    ap.add_argument("--account", default="u1", help="Aside 계정 (기본 u1 = hwangjiyoung1977)")
    ap.add_argument("--new", action="store_true", help="기록된 대화를 버리고 새 대화로 시작")
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file")
    ap.add_argument("--ref", action="append", default=[])
    ap.add_argument("--out")
    ap.add_argument("--json", help="panels[].name/prompt/reference_images/out")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--timeout", type=int, default=None)
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--orientation", choices=["portrait", "landscape", "any"], default="portrait",
                    help="결과로 인정할 이미지 방향 (16:9 롱폼은 landscape)")
    a = ap.parse_args(argv)

    g = AsideChatGPTConnector(a.project, a.thread, a.account)
    g.orientation = a.orientation
    if a.new:
        g.new_conversation()
    root = ROOT_DIR / "project" / a.project

    def jobs():
        if a.json:
            spec = json.load(open(a.json, encoding="utf-8"))
            for p in spec.get("panels", []):
                if a.only and p["name"] not in a.only:
                    continue
                # 참조는 생성 직전에 해석한다 → 앞에서 만든 컷을 뒤 컷의 참조로 쓸 수 있다
                refs = [str(r if os.path.isabs(r) else root / r) for r in p.get("reference_images", [])]
                missing = [r for r in refs if not os.path.exists(r)]
                if missing:
                    print(f"[chatgpt] {p['name']}: 없는 참조 제외 {missing}", flush=True)
                refs = [r for r in refs if os.path.exists(r)]
                out = p.get("out") or f"result/{p['name']}.png"
                yield p["name"], p["prompt"], refs, str(out if os.path.isabs(out) else root / out), not p.get("allow_similar")
        else:
            prompt = a.prompt or (open(a.prompt_file, encoding="utf-8").read() if a.prompt_file else "")
            if not prompt:
                ap.error("--prompt, --prompt-file 또는 --json 중 하나가 필요합니다.")
            yield "prompt", prompt, a.ref, a.out or "", True

    def mark(name, **kw):
        if not a.json:
            return
        spec = json.load(open(a.json, encoding="utf-8"))
        for p in spec.get("panels", []):
            if p["name"] == name:
                p.update(kw)
        json.dump(spec, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    for name, prompt, refs, out, echo_check in jobs():
        if a.skip_existing and out and os.path.exists(out):
            print(f"[chatgpt] 건너뜀(이미 있음): {name}", flush=True)
            continue
        print(f"[chatgpt] 생성 시작: {name} (참조 {len(refs)}장)", flush=True)
        saved = None
        for attempt in range(a.retries + 1):
            try:
                saved = g.generate(prompt, refs=refs, out_path=out, timeout_s=a.timeout, echo_check=echo_check)
                break
            except Exception as e:  # noqa: BLE001
                print(f"[chatgpt] 실패 {name} (시도 {attempt + 1}): {e}", flush=True)
                time.sleep(10)
        mark(name, generated=bool(saved), saved=saved, conversation_id=g.conversation_id,
             generator="chatgpt.com/images (aside)") if saved else mark(name, generated=False, error="generation failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
