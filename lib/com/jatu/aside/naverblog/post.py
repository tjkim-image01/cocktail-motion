"""네이버 블로그 글 올리기 (마크다운 → SmartEditor ONE) — Aside Browser 버전.

2026-10-09 jatu001 '공복 소금물' 글을 비공개로 올리면서 실측한 방법. 브라우저 조작은 `aside --account u3 repl` 로 직접 한다.

사용 예 (/Users/jatu/blog 루트):
    PYTHONPATH=. python3 -m lib.com.jatu.aside.naverblog.post \\
        --md project/jatu001/naver-morning-saltwater.md --category "건강상식 팩트체크" --private
    --dry-run 을 붙이면 마크다운을 어떻게 나눴는지만 보여 준다.

마크다운 규칙 (blog-post-workflow 형식)
    첫 줄 = 제목. `![설명](img/파일.png)` = 사진 (md 파일 기준 경로). `**굵게**` 지원.
    빈 줄·제로폭 공백(​) 줄은 빈 문단 하나로 합친다. `#태그 #태그` 줄은 본문에서 빼고 발행 태그로 넣는다.

=============================== 조사 기록 (2026-10-09 실측) ===============================
글쓰기 주소   https://blog.naver.com/<id>/postwrite  (iframe 없이 본문에 에디터가 있다)
제목          .se-documentTitle .se-text-paragraph 클릭 → CDP Input.insertText
본문 입력     본문 문단(.se-components-wrap > .se-component:not(.se-documentTitle) .se-text-paragraph) 클릭하면
              포커스가 숨은 입력용 iframe(url '' 또는 about:blank 또는 postwrite, body.isContentEditable — 순서는 바뀌므로 매번 찾는다) 으로 간다.
              그 iframe body 에 ClipboardEvent('paste', {clipboardData: DataTransfer(text/html)}) 를 보내면
              <b> 까지 살아서 붙는다.
사진          툴바 button.se-image-toolbar-button 은 숨은 input[type=file] 을 만들어 .click() 으로 파일창을 띄운다.
              → 미리 HTMLInputElement.prototype.click 을 바꿔 file input 을 잡아 body 에 붙이고(id=__capfile)
              CDP DOM.setFileInputFiles 로 절대경로를 넣으면 바로 업로드·삽입된다 (change 이벤트를 따로 보내지 말 것 — input 이 사라져 오류).
              삽입 뒤 사진 아래에 빈 텍스트 컴포넌트가 생기고 커서가 그리로 간다.
              REPL 의 fs 는 프로젝트/세션 폴더 밖 파일을 못 읽어서 붙여넣기(File) 방식은 쓸 수 없었다.
사진 크기     사진 클릭 → button.se-object-arrangement-extend-toolbar-button(옆트임) / -fit-(문서 너비)
인용구        툴바 button.se-document-toolbar-select-option-button(인용구 선택) → button.se-toolbar-option-insert-quotation-<style>-button
              style: default(1) quotation_line(2, 왼쪽 세로줄) quotation_bubble(3) quotation_underline(4) quotation_postit(5) quotation_corner(6)
              넣으면 커서가 인용구 안에 있다 → 입력용 iframe 에 paste → ArrowDown 두 번(출처 칸 → 인용구 밖 새 문단).
탭 유지       REPL 한 번 호출은 120초 제한 + 그 호출에서 openTab 한 탭은 끝나면 닫힌다. window.open 은 팝업 차단.
              → 이미 열려 있던 blog.naver.com 탭에 attach 해서 goto(postwrite) 하면 호출이 끝나도 남는다.
              진행 상황은 그 페이지의 window.__nbp 에 기록하고 여러 번 나눠 호출한다.
=========================================================================================
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

ASIDE_BIN = os.path.expanduser("~/.local/bin/aside")
if not os.path.exists(ASIDE_BIN):
    ASIDE_BIN = shutil.which("aside") or "aside"

BODY_PARA = ".se-components-wrap > .se-component:not(.se-documentTitle) .se-text-paragraph"


class NaverPostError(RuntimeError):
    pass


# ------------------------------------------------------------------ markdown
def parse_markdown(md_path: str) -> dict:
    """제목·본문 조각(html/img)·태그로 나눈다."""
    p = Path(md_path).resolve()
    lines = p.read_text(encoding="utf-8").splitlines()
    title = lines[0].strip().lstrip("# ").strip()
    segs: list[dict] = []
    tags: list[str] = []
    buf: list[str] = []

    def flush():
        # 앞뒤 빈 문단 제거, 연속 빈 문단은 하나로
        out, prev_blank = [], True
        for s in buf:
            blank = s is None
            if blank and prev_blank:
                continue
            out.append("<p><br></p>" if blank else f"<p>{s}</p>")
            prev_blank = blank
        while out and out[-1] == "<p><br></p>":
            out.pop()
        if out:
            # 마지막 문단 끝에 '서식 없는' 제로폭 공백을 붙여 커서 서식을 초기화한다.
            # 안 그러면 형광펜으로 끝난 문단 뒤에 넣은 사진/다음 글이 형광펜을 이어받는다 (2026-10-09 실측)
            out[-1] = out[-1][:-4] + '<span style="color:#141414;background-color:#ffffff;font-weight:normal">\u200b</span></p>'
            segs.append({"type": "html", "html": "".join(out)})
        buf.clear()

    quote: list[str] = []

    def flush_quote():
        if quote:
            segs.append({"type": "quote", "html": "".join(f"<p>{q}</p>" if q else "<p><br></p>" for q in quote)})
            quote.clear()

    def fmt(s: str) -> str:
        # 표시: **굵게** ==연두 형광펜== !!분홍 굵게!! ^^보라 굵게^^ (겹쳐 쓰기 가능: ==**굵은 형광**==)
        # 일반 글자도 색·배경·굵기를 명시한다 — 안 그러면 앞 붙여넣기의 끝 서식(형광펜 등)이 이어져 번진다 (2026-10-09 실측)
        PLAIN = "color:#141414;background-color:transparent;font-weight:normal"
        styles = {"==": "background-color:#e3fdc8", "!!": "color:#ff008c;font-weight:bold",
                  "^^": "color:#aa1f91;font-weight:bold", "**": "font-weight:bold"}
        out, stack, i = [], [], 0
        def cur_style():
            st = {"color": "#141414", "background-color": "#ffffff", "font-weight": "normal"}
            for m in stack:
                for kv in styles[m].split(";"):
                    k, v = kv.split(":"); st[k] = v
            return ";".join(f"{k}:{v}" for k, v in st.items())
        buf = ""
        def emit():
            nonlocal buf
            if buf:
                st = cur_style(); txt = html.escape(buf, quote=False)
                if "font-weight:bold" in st:
                    out.append(f'<span style="{st.replace(";font-weight:bold", "")}"><b>{txt}</b></span>')
                else:
                    out.append(f'<span style="{st}">{txt}</span>')
                buf = ""
        while i < len(s):
            tok = s[i:i + 2]
            if tok in styles:
                emit()
                if stack and stack[-1] == tok:
                    stack.pop()
                elif tok in stack:
                    stack.remove(tok)
                else:
                    stack.append(tok)
                i += 2
                continue
            buf += s[i]; i += 1
        emit()
        return "".join(out)

    for raw in lines[1:]:
        line = raw.strip().replace("​", "")
        if line.startswith("## "):
            flush(); flush_quote()
            segs.append({"type": "quote", "style": "quotation_underline", "html": f"<p>{fmt(line[3:].strip())}</p>"})
            continue
        if line.startswith(">"):
            flush()
            quote.append(fmt(line[1:].strip()))
            continue
        flush_quote()
        m = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        if m:
            flush()
            segs.append({"type": "img", "path": str((p.parent / m.group(2)).resolve()), "alt": m.group(1)})
            continue
        if line and all(w.startswith("#") and len(w) > 1 and not w.startswith("##") for w in line.split()):
            tags += [w.lstrip("#") for w in line.split()]
            continue
        if not line:
            buf.append(None)
            continue
        buf.append(fmt(line))
    flush_quote()
    flush()
    for s in segs:
        if s["type"] == "img" and not os.path.exists(s["path"]):
            raise NaverPostError(f"사진 파일이 없습니다: {s['path']}")
    return {"title": title, "segments": segs, "tags": tags}


# ---------------------------------------------------------------------- repl
class NaverBlogPoster:
    def __init__(self, blog_id: str, account: str = "u3"):
        self.blog_id = blog_id
        self.account = account
        self.work_dir = Path(tempfile.mkdtemp(prefix="aside-naverpost-"))
        self.write_url = f"https://blog.naver.com/{blog_id}/postwrite"

    def _repl(self, body: str, timeout: int = 170) -> str:
        head = f"""
const __W = {json.dumps(self.write_url)};
const __tabs = await listBrowserTabs();
let __t = __tabs.find(t => t.url.startsWith(__W));
if (!__t) throw new Error('NO_EDITOR_TAB');
const page = await attachBrowserTab(__t.targetId);
page.on('dialog', d => {{ console.log('DIALOG', d.message()); d.accept(); }});
"""
        cmd = [ASIDE_BIN, "--account", self.account, "repl", head + body]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=self.work_dir)
        except subprocess.TimeoutExpired:
            raise NaverPostError("Aside REPL 시간 초과")
        out = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
        if "[error" in out:
            raise NaverPostError(out.strip()[-800:])
        return out

    @staticmethod
    def _marker(out: str, key: str) -> Optional[str]:
        for line in out.splitlines():
            if line.startswith(key):
                return line[len(key):].strip()
        return None

    def open_editor(self) -> None:
        """이미 열려 있는 blog.naver.com 탭(호출이 끝나도 남는 탭)을 글쓰기 화면으로 보낸다."""
        body = f"""
const tl = await listBrowserTabs();
const base = tl.find(t => t.url.startsWith({json.dumps(self.write_url)})) || tl.find(t => /^https:\\/\\/(blog|admin\\.blog|section\\.blog|www)\\.naver\\.com/.test(t.url));
if (!base) throw new Error('네이버 탭이 하나도 없습니다 — Aside 에서 naver.com 을 한 번 열어 두세요');
const bp = await attachBrowserTab(base.targetId);
bp.on('dialog', d => {{ console.log('DIALOG', d.message()); d.accept(); }});
await bp.goto({json.dumps(self.write_url)}); await sleep(7000);
// '작성 중인 글이 있습니다' 복원 팝업은 취소, 도움말 패널은 닫기
await bp.evaluate(() => {{ const c = document.querySelector('.se-popup-button-cancel'); if (c) c.click(); }}); await sleep(800);
await bp.evaluate(() => {{ const b = [...document.querySelectorAll('button')].find(b => b.innerText.trim() === '닫기' && b.closest('[class*=help]')); if (b) b.click(); }});
await bp.evaluate(() => {{ window.__nbp = 0; }});
console.log('EDITOR:' + bp.url());
"""
        cmd = [ASIDE_BIN, "--account", self.account, "repl", body]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=self.work_dir).stdout
        if "EDITOR:" not in out:
            raise NaverPostError("글쓰기 화면을 열지 못했습니다: " + out[-400:])

    def set_title(self, title: str) -> None:
        self._repl(f"""
await page.locator('.se-documentTitle .se-text-paragraph').first().click(); await sleep(300);
await page._sendToTarget('Input.insertText', {{ text: {json.dumps(title)} }}); await sleep(300);
console.log('TITLE:' + await page.evaluate(() => document.querySelector('.se-documentTitle').innerText.trim()));
""")

    def add_segments(self, segs: list[dict], start: int = 0, budget_s: int = 85) -> int:
        """start 번째부터 시간 안에 넣을 수 있는 만큼 넣고 다음 번호를 돌려준다."""
        body = f"""
const segs = {json.dumps(segs, ensure_ascii=False)};
const t0 = Date.now();
let i = {start};
const focusEnd = async () => {{
  // 인용구 안 문단을 고르지 않도록 '일반 텍스트 컴포넌트'의 마지막 문단만 본다
  const paras = page.locator('.se-components-wrap > .se-component.se-text .se-text-paragraph');
  const n = await paras.count();
  // 긴 문단은 여러 줄로 감긴다 → End 키는 '현재 줄 끝'까지만 간다. 마지막 문단의 오른쪽 아래 끝을 직접 클릭한다.
  const box = await paras.nth(n - 1).boundingBox();
  if (box) {{ await page.mouse.click(box.x + box.width - 2, box.y + box.height - 4); }} else {{ await paras.nth(n - 1).click(); }}
  await sleep(250);
  await page.keyboard.press('End'); await sleep(100);
}};
const imgCount = () => page.evaluate(() => document.querySelectorAll('.se-components-wrap .se-component.se-image').length);
await page.evaluate(() => {{
  if (window.__capPatched) return; window.__capPatched = true;
  const orig = HTMLInputElement.prototype.click;
  HTMLInputElement.prototype.click = function () {{ if (this.type === 'file') {{ document.getElementById('__capfile')?.removeAttribute('id'); this.id = '__capfile'; this.style.display = 'none'; if (!this.isConnected) document.body.appendChild(this); return; }} return orig.apply(this, arguments); }};
}});
while (i < segs.length && Date.now() - t0 < {budget_s * 1000}) {{
  const s = segs[i];
  await focusEnd();
  if (s.type === 'quote') {{
    // 인용구 2 = quotation_line (왼쪽 세로줄). 넣으면 커서가 인용구 안 → 붙여넣기 → 아래 방향키 2번(출처 칸 → 밖)
    await page.locator('button.se-document-toolbar-select-option-button').first().click(); await sleep(700);
    await page.locator('button.se-toolbar-option-insert-quotation-' + (s.style || 'quotation_line') + '-button').click(); await sleep(1200);
    let fq = null;
    for (const f of page.frames().slice(1)) {{ if (await f.evaluate(() => !!document.body && document.body.isContentEditable).catch(() => false)) {{ fq = f; break; }} }}
    await fq.evaluate((h) => {{ const dt = new DataTransfer(); dt.setData('text/html', h); dt.setData('text/plain', h.replace(/<[^>]+>/g, '\\n')); document.body.dispatchEvent(new ClipboardEvent('paste', {{ clipboardData: dt, bubbles: true, cancelable: true }})); }}, s.html);
    await sleep(900);
    await page.keyboard.press('ArrowDown'); await page.keyboard.press('ArrowDown'); await sleep(400);
    // 인용구 밖에 빈 문단을 하나 만들어 둔다 — 안 그러면 다음 글이 인용구 안으로 들어간다
    await fq.evaluate(() => {{ const dt = new DataTransfer(); dt.setData('text/html', '<p><br></p>'); dt.setData('text/plain', ' '); document.body.dispatchEvent(new ClipboardEvent('paste', {{ clipboardData: dt, bubbles: true, cancelable: true }})); }});
    await sleep(600);
    const lastIsText = await page.evaluate(() => {{ const c = [...document.querySelectorAll('.se-components-wrap > .se-component')].pop(); return c.classList.contains('se-text'); }});
    if (!lastIsText) throw new Error('인용구 뒤에 텍스트 문단이 생기지 않았습니다');
  }} else if (s.type === 'html') {{
    // 입력용 iframe 은 순서가 바뀐다(광고 iframe 등) → body 가 편집 가능한 프레임을 찾는다
    let fr = null;
    for (const f of page.frames().slice(1)) {{ if (await f.evaluate(() => !!document.body && document.body.isContentEditable).catch(() => false)) {{ fr = f; break; }} }}
    if (!fr) throw new Error('입력용 iframe 을 찾지 못했습니다');
    await fr.evaluate((h) => {{ const dt = new DataTransfer(); dt.setData('text/html', h); dt.setData('text/plain', h.replace(/<[^>]+>/g, '\\n')); document.body.dispatchEvent(new ClipboardEvent('paste', {{ clipboardData: dt, bubbles: true, cancelable: true }})); }}, s.html);
    await sleep(900);
  }} else {{
    const before = await imgCount();
    await page.locator('button.se-image-toolbar-button').click(); await sleep(1200);
    const {{ root }} = await page._sendToTarget('DOM.getDocument', {{ depth: -1, pierce: true }});
    const {{ nodeId }} = await page._sendToTarget('DOM.querySelector', {{ nodeId: root.nodeId, selector: '#__capfile' }});
    if (!nodeId) throw new Error('사진 input 을 잡지 못했습니다');
    await page._sendToTarget('DOM.setFileInputFiles', {{ files: [s.path], nodeId }});
    for (let k = 0; k < 30 && (await imgCount()) <= before; k++) await sleep(1000);
    if ((await imgCount()) <= before) throw new Error('사진 업로드 시간 초과: ' + s.path);
    await sleep(1500);
    // 사진 크기: 옆트임(본문보다 넓게, content-extend). 기본은 '문서 너비'(content-fit)
    if ((s.size || 'extend') === 'extend') {{
      await page.locator('.se-components-wrap .se-component.se-image img').last().click(); await sleep(600);
      await page.evaluate(() => {{ const b = [...document.querySelectorAll('button.se-object-arrangement-extend-toolbar-button')].find(b => b.offsetParent); if (b) b.click(); }});
      await sleep(600);
    }}
  }}
  i++;
  await page.evaluate((n) => {{ window.__nbp = n; }}, i);
  console.log('SEG ' + i + '/' + segs.length + ' ' + s.type);
}}
console.log('NEXT:' + i);
"""
        out = self._repl(body, timeout=170)
        nxt = self._marker(out, "NEXT:")
        if nxt is None:
            raise NaverPostError("진행 번호를 받지 못했습니다: " + out[-400:])
        return int(nxt)

    def publish(self, category: Optional[str] = None, private: bool = True, tags: list[str] = ()) -> str:
        """발행 레이어: 카테고리 → 공개 설정 → 태그 → 발행. 발행된 글 주소를 돌려준다.

        레이어(2026-10-09): button '카테고리 목록 버튼'(현재 카테고리명 표시), label 전체공개/이웃공개/서로이웃공개/비공개,
        checkbox 댓글·공감·검색허용 등, combobox '태그 입력 (최대 30개)', 발행 시간 현재/예약, 레이어 안 button '발행'.
        """
        body = f"""
const inLayer = (b) => !!b.closest('[class*=layer i], [class*=publish i]');
if (!(await page.evaluate(() => !!document.querySelector('[class*=layer] input[placeholder*=태그], [class*=publish] input[placeholder*=태그]')))) {{
  await page.evaluate(() => [...document.querySelectorAll('button')].find(b => b.innerText.trim() === '발행').click()); await sleep(2000);
}}
let q = await snapshot(page);
const ref = (re) => {{ const m = q.tree.match(re); if (!m) throw new Error('ref not found: ' + re); return m[1]; }};
const cat = {json.dumps(category)};
if (cat) {{
  const cur = (q.tree.match(/button "카테고리 목록 버튼" \\[ref=\\w+\\]: "([^"]*)"/) || [])[1];
  if (cur !== cat) {{
    await page.locator(ref(/button "카테고리 목록 버튼" \\[ref=(\\w+)\\]/)).click(); await sleep(800);
    q = await snapshot(page);
    const m = q.tree.match(new RegExp('(?:option|label|button|link|listitem)[^\\\\n]*"' + cat.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + '"[^\\\\n]*\\\\[ref=(\\\\w+)\\\\]'));
    if (!m) throw new Error('카테고리를 찾지 못했습니다: ' + cat);
    await page.locator(m[1]).click(); await sleep(800); q = await snapshot(page);
  }}
}}
const visLabel = {json.dumps('비공개' if private else '전체공개')};
await page.locator(ref(new RegExp('label "' + visLabel + '" \\\\[ref=(\\\\w+)\\\\]'))).click(); await sleep(500);
const tagBox = page.locator('input[placeholder*="태그 입력"]');
for (const t of {json.dumps(list(tags), ensure_ascii=False)}) {{
  await tagBox.click(); await page._sendToTarget('Input.insertText', {{ text: t }}); await sleep(200); await page.keyboard.press('Enter'); await sleep(300);
}}
q = await snapshot(page);
const vis = (q.tree.match(/radio "(전체공개|이웃공개|서로이웃공개|비공개)" \\[ref=\\w+\\] \\[hidden\\] \\[checked\\]/) || [])[1];
const curCat = (q.tree.match(/button "카테고리 목록 버튼" \\[ref=\\w+\\]: "([^"]*)"/) || [])[1];
console.log('CHECK:' + JSON.stringify({{ vis, cat: curCat }}));
if (vis !== {json.dumps('비공개' if private else '전체공개')}) throw new Error('공개 설정이 맞지 않습니다: ' + vis);
const btns = q.tree.match(/button "발행" \\[ref=(\\w+)\\]/g); const last = btns[btns.length - 1].match(/ref=(\\w+)/)[1];
await page.locator(last).click();
for (let k = 0; k < 20 && page.url().includes('postwrite'); k++) await sleep(1000);
await sleep(2000);
console.log('POSTED:' + page.url());
"""
        out = self._repl(body, timeout=170)
        print("[naverpost] 발행 확인:", self._marker(out, "CHECK:"), flush=True)
        url = self._marker(out, "POSTED:") or ""
        if "postwrite" in url:
            raise NaverPostError("발행 후 주소가 바뀌지 않았습니다: " + url)
        return url

    def summary(self) -> dict:
        out = self._repl("""
console.log('SUM:' + JSON.stringify(await page.evaluate(() => ({
  title: document.querySelector('.se-documentTitle')?.innerText.trim(),
  images: document.querySelectorAll('.se-components-wrap .se-component.se-image').length,
  texts: document.querySelectorAll('.se-components-wrap .se-component.se-text').length,
  chars: (document.querySelector('.se-components-wrap')?.innerText || '').length }))));
""")
        return json.loads(self._marker(out, "SUM:") or "{}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="마크다운 글을 네이버 블로그에 올린다 (Aside repl)")
    ap.add_argument("--md", required=True)
    ap.add_argument("--blog", default="jatu")
    ap.add_argument("--account", default="u3")
    ap.add_argument("--category")
    ap.add_argument("--private", action="store_true", help="비공개로 발행")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-publish", action="store_true", help="본문만 넣고 발행 단계는 하지 않음")
    ap.add_argument("--publish-only", action="store_true", help="이미 채워 둔 글쓰기 탭을 발행만 한다")
    a = ap.parse_args(argv)

    doc = parse_markdown(a.md)
    if a.dry_run:
        print(json.dumps({"title": doc["title"], "tags": doc["tags"],
                          "segments": [s if s["type"] == "img" else {"type": "html", "chars": len(s["html"]), "head": s["html"][:80]} for s in doc["segments"]]},
                         ensure_ascii=False, indent=2))
        return 0
    nb = NaverBlogPoster(a.blog, a.account)
    if a.publish_only:
        print("[naverpost] 발행:", nb.publish(category=a.category, private=a.private, tags=doc["tags"]), flush=True)
        return 0
    nb.open_editor()  # 주의: 글쓰기 화면을 새로 연다 (작성 중 내용은 복원하지 않음)
    nb.set_title(doc["title"])
    i = 0
    while i < len(doc["segments"]):
        i = nb.add_segments(doc["segments"], i)
        print(f"[naverpost] {i}/{len(doc['segments'])}", flush=True)
    print("[naverpost] 본문 완료:", nb.summary(), flush=True)
    if not a.no_publish:
        print("[naverpost] 발행:", nb.publish(category=a.category, private=a.private, tags=doc["tags"]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
