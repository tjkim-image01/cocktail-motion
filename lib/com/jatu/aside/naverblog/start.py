"""네이버 블로그 시작 세팅(기본 정보·카테고리·스킨·타이틀·프로필) — Aside Browser 버전.

2026-10-09 jatu 블로그를 '건강 팩트노트'로 꾸미면서 실측한 내용을 기록하고 재사용하려고 만든 모듈.
브라우저 조작은 `aside --account <id> repl` 로 직접 한다 (exec/에이전트는 쓰지 않는다 — 월 500회 한도).
기본 계정은 u3 (네이버 로그인되어 있는 프로필).

사용 예 (/Users/jatu/blog 루트):
    PYTHONPATH=. python3 -m lib.com.jatu.aside.naverblog.start --config project/blog-design/blog.json
    PYTHONPATH=. python3 -m lib.com.jatu.aside.naverblog.start --config project/blog-design/blog.json --steps info,categories
    PYTHONPATH=. python3 -m lib.com.jatu.aside.naverblog.start --config project/blog-design/blog.json --state

설정 파일(JSON) 예: project/blog-design/blog.json
    {"blog_id": "jatu", "account": "u3",
     "info": {"name": "...", "nickname": "...", "intro": "...", "topic": "건강·의학"},
     "categories": {"add": ["..."], "hide_and_bottom": ["프로그램메모"]},
     "skin": "비율의 정석",
     "title": {"image": "img/title.png", "height": 300, "show_text": false},
     "profile_image": "img/profile.png"}
    이미지 경로는 설정 파일이 있는 폴더 기준.

=============================== 조사 기록 (2026-10-09 실측) ===============================
관리 페이지 주소 (blogId=jatu 기준, 다른 블로그는 아이디만 바꾼다)
    기본 정보        https://admin.blog.naver.com/<id>/config/bloginfo
    카테고리         https://admin.blog.naver.com/<id>/config/blog      (본문 iframe: AdminCategoryView.naver)
    상단 메뉴        https://admin.blog.naver.com/<id>/config/topmenu
    스킨 선택        https://admin.blog.naver.com/<id>/skin/list        (본문 iframe: NaverSkin.naver)
    레이아웃·위젯    https://admin.blog.naver.com/LayoutSelect.naver?blogId=<id>
    리모콘(세부 디자인) https://admin.blog.naver.com/Remocon.naver?blogId=<id>&loadType=admin&Redirect=Remocon
    타이틀 꾸미기    위 리모콘 주소 + &SelectedMenu=title
    글·댓글 스타일   위 리모콘 주소 + &SelectedMenu=poststyle
    프롤로그         https://admin.blog.naver.com/<id>/config/prologue
    통계             https://admin.blog.naver.com/<id>/stat/today

입력 제한·규격
    블로그명 25자, 별명 10자, 소개글 200자 (한글 기준). 소개글의 이모지는 저장 시 지워진다.
    주제: '주제를 선택해주세요.' 버튼 → 드롭다운 label (건강·의학 등 32개)
    프로필 이미지: 가로 161px 섬네일로 생성. '네이버 프로필에도 적용' 체크가 기본 ON.
    타이틀 직접등록: 가로 966px, 세로 50~600px. 영역 높이 슬라이더/입력칸 50~600 (기본 300).
    리모콘은 '적용'을 누르지 않고 다른 페이지로 가면 작업이 사라진다.

REPL 동작 주의
    - `aside repl "..."` 한 번 호출이 끝나면 그 호출에서 openTab 한 탭은 닫힌다 → 입력~저장은 한 호출 안에서 끝낸다.
      사용자가 직접 연 탭은 남아 있으므로 listBrowserTabs()+attachBrowserTab() 으로 붙을 수 있다.
    - 관리 화면은 iframe 안에 있다. page.frames().find(f => f.url().includes('AdminCategoryView')) 처럼 프레임을 잡고
      frame.locator / frame.evaluate 를 쓰면 된다. snapshot ref(f2e3 등)로도 iframe 안 요소를 누를 수 있다.
    - page.screenshot({path}) 은 안 되고 Buffer 를 받아 fs.writeFile 로 저장 → ~/.aside/u/<n>/sessions/*/artifacts/ 에 생긴다.
    - page.setViewportSize, pwd() 는 없다.

화면별 실측
    기본 정보: textbox "블로그명"/"별명"/"소개글" fill → 주제 버튼 클릭 → label "<주제>" 클릭 → button "확인". fill 로 저장된다.
    카테고리 (AdminCategoryView 프레임):
        목록 #tree li, 이름 span._categoryName, 선택된 항목 li.tree-selected
        추가 img._addCategoryView — 새 항목은 '게시판' 이름으로 생긴다.
            !! 다른 카테고리를 선택한 채로 추가하면 그 아래 '하위 카테고리'로 들어갈 수 있다 → 매번 '카테고리 전체보기'를 먼저 클릭.
        이름 #category_name — fill 만으로는 반영이 안 됐다. click → fill('') → type(name) → input/keyup/change/blur 이벤트 발생.
        공개설정 radio 공개/비공개, 정렬 img[alt=위|아래|맨위|맨아래]
        삭제 #deleteBtn → 레이어(.chl_ly_cont: '카테고리에 속한 N개의 글이 모두 삭제됩니다') → .chl_ly_btn a '삭제'
            !! 글이 0개일 때만 지운다 (아래 코드도 그렇게 막아 둠).
        저장 #submit_button (input type=submit, value=확인). 저장 뒤 페이지가 바뀌어 REPL 이 웹소켓 오류를 낼 수 있음 → 새 호출로 확인.
    스킨 (NaverSkin 프레임): li(스킨명) 안 radio check → input._skinSave('스킨 적용') → 바깥 페이지에 미리보기 레이어
        → button._skinSaveForPreview('바로 적용') 클릭(DOM click) → blog.naver.com/<id> 로 이동하며 적용.
        첫 페이지 스킨: 라인, 와이드, 도큐먼트, Me Myself, 하늘하늘, 정적인 프레임, 비율의 정석, 화이트 라벨, 솜사탕, 민트핑크, 가을 숲, 옐로우 라인 (9페이지까지 있음)
        썸네일: https://ssl.pstatic.net/static/blog/skin/<skinId>/thumb_skin.png (비율의 정석=103)
    타이틀(리모콘): 왼쪽 '타이틀' 탭 → 블로그 제목 '표시' 체크, 폰트/크기/색/위치, 영역 높이 slider+textbox,
        디자인 탭: 스타일 / 컬러 / 직접등록 → '파일 등록' 버튼, '무료 이미지'(OGQ). 마지막에 button '적용'.
        '직접등록' 링크는 locator('a', hasText) 클릭이 '준비 안 됨' 시간 초과 → snapshot ref 로 클릭하면 된다.
        파일 input: #titleInputFile (CDP DOM.setFileInputFiles), 높이 input: #title_height (스킨 기본이 500일 수 있음).
        '적용' a.btn_submit._showConfirmLayer → 확인 레이어의 a._submit 까지 눌러야 저장된다 (첫 시도에서 이걸 빠뜨려 미저장).
    프로필 이미지: a._btnProfileImageUpload → 팝업 AddProfileImageView → input[name=file1] → #submitBtn
        → 결과가 opener.postMessage 로 넘어와 #profile_161 이 바뀜 → input._btnConfirm('확인') 으로 저장.
        이전 시도의 팝업 탭이 남아 있으면 반영이 안 됐다 → 먼저 닫는다.

홈페이지형 디자인 (2026-10-09, 배짱이 blog.naver.com/1978mm 스타일 / 업체들이 쓰는 방식)
    원리: 디자인 전체(로고·배너·카테고리 카드)를 '스킨배경 > 직접등록 > 상단 영역' 이미지 한 장(가로 최대 3000px)에 그리고,
          카드 위치에 '투명 위젯'(위젯 직접등록 HTML: <a href=... target="_top" style="display:block;width:170px;height:160px"></a>)을 겹친다.
    레이아웃: LayoutSelect _param(9|4) = 타이틀 → 메뉴 → 위젯 한 줄(left_menu_l) → 글 → 아래 위젯(left_menu_r).
          위젯 이동은 드래그 대신 DOM 이동 후 #doApplyConfirm: left_menu_l.insertBefore(ex_N, ...). 위젯 최대 170x600, 코드 2000byte.
          위젯 수정: 오른쪽 목록 li#op_N a._btnEdit → textarea._widgetCode → a._btnPreview → a._btnSubmit. 이모지는 지워진다.
    리모콘: 타이틀·전체/구성/그룹 박스·메뉴·프로필 컬러 = 투명(li#transparent_<panel> 클릭), 타이틀 높이 #title_height.
          스킨배경 상단 이미지: #input_top_file → #head-skin 에 'background: 50% 0 repeat-x' 로 깔린다(페이지 가운데 기준, 1 이미지 px = 1 CSS px).
          스킨배경 컬러 팔레트 #backgroundPalette li._colorSwatches[_param(#FFFFFF)].
    실측 좌표(뷰포트 1440, 본문 966 가운데, x는 페이지 기준 / 이미지 x = 페이지 x - 720 + W/2):
          타이틀 y 41~481(높이 440) / 메뉴 y 481~517 / 위젯 y 533~693, x 245·431·617·803·989 (170x160, 간격 186)
    이미지 만들기: project/blog-design/v2/make_skin.py (2560x760, 세리프 로고 AppleMyungjo + 카드 5개). 결과 v2/img/skin.png
    블로그씨 질문 끄기: config/mrblog → '배달중지' radio → 확인.
    기본 서체: config/defaulteditor → 서체 label '바른고딕', 크기 label '16' → 확인.

타이틀 이미지 만들기 (project/blog-design/make_title.py, Pillow = youtube3/.venv-tts)
    사진을 좌우 반전 → 966 폭으로 줄여 300 높이 띠로 자름 → 왼쪽 흰 그라데이션 위에 블로그명(AppleSDGothicNeo Bold 58)
    + 초록 밑줄 + 부제 2줄. 같은 사진에서 물컵 중심 600x600 을 잘라 프로필로 씀.
    ChatGPT(lib/com/jatu/aside/connector/chatgpt.py)로 배경 사진을 새로 만들려 했으나 2026-10-09 오후
    '이 ChatGPT 대화를 불러올 수 없습니다'로 대화가 열리지 않았다. 원인은 커넥터가 전송 직후의 임시 주소
    (/c/local-chatgpt%3A…)를 대화 주소로 기록해 다시 연 것 → chatgpt.py 수정(진짜 /c/<uuid> 를 기다림) 후 u0 로 생성 성공.
    현재 타이틀: img/title-v2.png = make_title.py img/title-bg.png img/title-v2.png - --no-mirror --top=0.20 --alpha=150
=========================================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

ASIDE_BIN = os.path.expanduser("~/.local/bin/aside")
if not os.path.exists(ASIDE_BIN):
    ASIDE_BIN = shutil.which("aside") or "aside"

ADMIN = "https://admin.blog.naver.com"


class NaverBlogError(RuntimeError):
    pass


# 모든 REPL 코드 앞에 붙는 공통 도우미. dialog 는 자동 수락, snapshot 에서 ref 를 정규식으로 찾는다.
_JS_HEAD = """
const __open = async (u) => { await openTab(u); await sleep(2500); page.on('dialog', d => { console.log('DIALOG', d.message()); d.accept(); }); };
let __q = null;
const __snap = async () => { __q = await snapshot(page); return __q; };
const __ref = (re) => { const m = __q.tree.match(re); if (!m) throw new Error('ref not found: ' + re); return m[1]; };
const __frame = (part) => page.frames().find(f => f.url().includes(part));
"""


class NaverBlogAdmin:
    def __init__(self, blog_id: str, account: str = "u3"):
        self.blog_id = blog_id
        self.account = account
        self.work_dir = Path(tempfile.mkdtemp(prefix="aside-naverblog-"))

    def url(self, path: str) -> str:
        return f"{ADMIN}/{self.blog_id}/{path}"

    # ------------------------------------------------------------------ repl
    def _repl(self, body: str, timeout: int = 170, tolerate_nav: bool = False) -> str:
        cmd = [ASIDE_BIN, "--account", self.account, "repl", _JS_HEAD + body]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=self.work_dir)
        except subprocess.TimeoutExpired:
            raise NaverBlogError("Aside REPL 시간 초과")
        out = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
        if "[error" in out and not tolerate_nav:
            raise NaverBlogError(out.strip()[-800:])
        return out

    @staticmethod
    def _marker(out: str, key: str) -> Optional[str]:
        for line in out.splitlines():
            if line.startswith(key):
                return line[len(key):].strip()
        return None

    # ------------------------------------------------------------------ state
    def state(self) -> dict:
        """현재 블로그명·별명·소개글·주제·카테고리·스킨을 읽는다 (확인용)."""
        body = f"""
await __open({json.dumps(self.url('config/bloginfo'))}); await __snap();
const info = {{}};
for (const k of ['블로그명','별명','소개글']) {{ const m = __q.tree.match(new RegExp('textbox "' + k + '" \\\\[ref=\\\\w+\\\\]: "([^"]*)"')); info[k] = m ? m[1] : ''; }}
const tm = __q.tree.match(/- button "([^"]+)" \\[ref=f\\w+\\]\\n\\s*- text: "내 블로그에서 다루는 주제/); info['주제'] = tm ? tm[1] : '';
await __open({json.dumps(self.url('config/blog'))});
const cf = __frame('AdminCategoryView');
info['카테고리'] = await cf.evaluate(() => [...document.querySelectorAll('#tree li')].map(li => (li.parentElement.closest('li') ? '└' : '') + li.querySelector('label').innerText.replace(/\\s+/g,'') + (li.querySelector('img[alt=비공개]') ? '[비공개]' : '')));
await __open({json.dumps(self.url('skin/list'))}); await __snap();
const sm = __q.tree.match(/사용중인 스킨 \\| ([^"]+)"/); info['스킨'] = sm ? sm[1] : '';
console.log('STATE:' + JSON.stringify(info));
"""
        raw = self._marker(self._repl(body), "STATE:")
        if not raw:
            raise NaverBlogError("상태를 읽지 못했습니다")
        return json.loads(raw)

    # ------------------------------------------------------------------ info
    def set_blog_info(self, name: str, nickname: str, intro: str, topic: Optional[str] = None) -> None:
        topic_js = ""
        if topic:
            topic_js = f"""
await page.locator(__ref(/button "[^"]+" \\[ref=(f\\w+)\\]\\n\\s*- text: "내 블로그에서 다루는 주제/)).click(); await sleep(1200); await __snap();
await page.locator(__ref(/label "{topic}" \\[ref=(\\w+)\\]/)).click(); await sleep(800); await __snap();
"""
        body = f"""
await __open({json.dumps(self.url('config/bloginfo'))}); await __snap();
await page.locator(__ref(/textbox "블로그명" \\[ref=(\\w+)\\]/)).fill({json.dumps(name)});
await page.locator(__ref(/textbox "별명" \\[ref=(\\w+)\\]/)).fill({json.dumps(nickname)});
await page.locator(__ref(/textbox "소개글" \\[ref=(\\w+)\\]/)).fill({json.dumps(intro)});
{topic_js}
await page.locator(__ref(/button "확인" \\[ref=(f\\w+)\\]/)).click(); await sleep(3000);
console.log('DONE:info');
"""
        self._repl(body, tolerate_nav=True)

    # ------------------------------------------------------------ categories
    def setup_categories(self, add: list[str], hide_and_bottom: list[str] = (), remove_empty: list[str] = ("게시판",)) -> None:
        body = f"""
await __open({json.dumps(self.url('config/blog'))});
const f = __frame('AdminCategoryView');
const st = () => f.evaluate(() => [...document.querySelectorAll('#tree li')].map(li => (li.parentElement.closest('li') ? '└' : '') + li.querySelector('label').innerText.replace(/\\s+/g,'')));
const del = async (name) => {{
  await f.locator('#tree span._categoryName', {{ hasText: name }}).last().click(); await sleep(400);
  await f.locator('#deleteBtn').click(); await sleep(800);
  const msg = await f.evaluate(() => document.querySelector('.chl_ly_cont')?.innerText || '');
  if (!/속한\\s*0\\s*개의 글/.test(msg)) {{ await f.locator('.chl_ly_btn a', {{ hasText: '취소' }}).click(); throw new Error('글이 있는 카테고리는 지우지 않음: ' + msg); }}
  await f.locator('.chl_ly_btn a', {{ hasText: '삭제' }}).click(); await sleep(1000);
}};
for (const n of {json.dumps(list(remove_empty))}) for (let i = 0; i < 5 && (await st()).some(x => x.replace('└','').startsWith(n + '(')); i++) await del(n);
const have = await st();
for (const name of {json.dumps(add)}) {{
  if (have.some(x => x.replace('└','').startsWith(name.replace(/\\s+/g,'') + '('))) continue;
  await f.locator('#tree label', {{ hasText: '카테고리 전체보기' }}).click(); await sleep(400);
  await f.locator('img._addCategoryView').click(); await sleep(700);
  const box = f.locator('#category_name');
  await box.click(); await box.fill(''); await box.type(name);
  await f.evaluate(() => {{ const i = document.querySelector('#category_name'); ['input','keyup','change','blur'].forEach(e => i.dispatchEvent(new Event(e, {{ bubbles: true }}))); }});
  await sleep(400);
}}
for (const name of {json.dumps(list(hide_and_bottom))}) {{
  await f.locator('#tree span._categoryName', {{ hasText: name }}).click(); await sleep(400);
  await f.evaluate(() => {{ const r = [...document.querySelectorAll('input[type=radio]')].find(r => (r.nextElementSibling?.innerText || '').trim() === '비공개' || (r.closest('label')?.innerText || '').trim() === '비공개'); if (r) r.click(); }});
  await f.locator('img[alt="맨아래"]').click(); await sleep(400);
}}
console.log('BEFORE_SAVE:' + JSON.stringify(await st()));
await f.locator('#submit_button').click(); await sleep(4000);
console.log('DONE:categories');
"""
        out = self._repl(body, timeout=200, tolerate_nav=True)
        print("[naverblog] 카테고리:", self._marker(out, "BEFORE_SAVE:"), flush=True)

    # ------------------------------------------------------------------ skin
    def apply_skin(self, skin_name: str) -> None:
        body = f"""
await __open({json.dumps(self.url('skin/list'))});
const f = __frame('NaverSkin');
await f.locator('li', {{ hasText: {json.dumps(skin_name)} }}).locator('input[type=radio]').check(); await sleep(500);
await f.locator('input._skinSave').click(); await sleep(3000);
await page.evaluate(() => document.querySelector('button._skinSaveForPreview').click()); await sleep(4000);
console.log('DONE:skin ' + page.url());
"""
        self._repl(body, tolerate_nav=True)

    # ----------------------------------------------------------------- title
    def upload_title(self, image: str, height: int = 300, show_text: bool = False) -> None:
        """리모콘 타이틀 '직접등록'으로 이미지(966 x 50~600)를 올리고 적용한다."""
        img = str(Path(image).resolve())
        body = f"""
await __open({json.dumps(ADMIN + '/Remocon.naver?blogId=' + self.blog_id + '&loadType=admin&Redirect=Remocon&SelectedMenu=title')}); await sleep(2000);
await __snap();
const showOn = () => page.evaluate(() => {{ const lab = [...document.querySelectorAll('label')].find(l => l.innerText.trim() === '표시'); const cb = lab && (lab.querySelector('input[type=checkbox]') || document.getElementById(lab.htmlFor)); return cb ? cb.checked : null; }});
if ((await showOn()) !== {json.dumps(show_text)}) {{ await page.locator(__ref(/label \\[ref=(\\w+)\\]:\\n\\s*- checkbox "표시 표시"/)).click(); await sleep(600); await __snap(); }}
await page.locator(__ref(/link "직접등록" \\[ref=(\\w+)\\]/)).click(); await sleep(1200);
const {{ root }} = await page._sendToTarget('DOM.getDocument', {{ depth: -1, pierce: true }});
const {{ nodeId }} = await page._sendToTarget('DOM.querySelector', {{ nodeId: root.nodeId, selector: '#titleInputFile' }});
await page._sendToTarget('DOM.setFileInputFiles', {{ files: [{json.dumps(img)}], nodeId }});
await sleep(7000);
const hbox = page.locator('#title_height'); await hbox.click(); await hbox.fill(''); await hbox.type('{int(height)}'); await page.keyboard.press('Enter');
await page.evaluate(() => {{ const i = document.querySelector('#title_height'); ['input','keyup','change','blur'].forEach(e => i.dispatchEvent(new Event(e, {{ bubbles: true }}))); }});
await sleep(800);
// '적용'(a.btn_submit._showConfirmLayer)은 확인 레이어만 연다 → 레이어 안 a._submit 을 눌러야 저장된다
await page.evaluate(() => document.querySelector('a.btn_submit._showConfirmLayer').click()); await sleep(1500);
await page.evaluate(() => [...document.querySelectorAll('a._submit')].find(a => a.offsetParent).click()); await sleep(5000);
console.log('DONE:title ' + page.url());
"""
        self._repl(body, tolerate_nav=True)

    # --------------------------------------------------------------- profile
    def upload_profile(self, image: str) -> str:
        """기본 정보 > 블로그 프로필 이미지 '등록' 팝업으로 올리고 확인까지 누른다. 저장된 이미지 주소를 돌려준다.

        팝업(AddProfileImageView) → input[name=file1] → #submitBtn → upload.blog.naver.com 결과 페이지가
        opener.postMessage 로 원래 화면에 넘겨 준다. 이전 시도에서 남은 팝업 탭이 있으면 전달이 엇갈려
        반영되지 않았다 → 시작 전에 남은 팝업을 모두 닫는다.
        """
        img = str(Path(image).resolve())
        body = f"""
for (const t of (await listBrowserTabs()).filter(t => /AddProfileImage/.test(t.url))) {{ try {{ const x = await attachBrowserTab(t.targetId); await x.evaluate(() => window.close()); }} catch (e) {{}} }}
await __open({json.dumps(self.url('config/bloginfo'))});
const main = page;
const f = __frame('AdminUserBasic');
await f.locator('a._btnProfileImageUpload').click(); await sleep(4000);
const pt = (await listBrowserTabs()).find(t => t.url.includes('AddProfileImageView'));
const pop = await attachBrowserTab(pt.targetId); await sleep(800);
const {{ root }} = await pop._sendToTarget('DOM.getDocument', {{ depth: -1, pierce: true }});
const {{ nodeId }} = await pop._sendToTarget('DOM.querySelector', {{ nodeId: root.nodeId, selector: 'input[name=file1]' }});
await pop._sendToTarget('DOM.setFileInputFiles', {{ files: [{json.dumps(img)}], nodeId }});
await sleep(800);
await pop.evaluate(() => document.getElementById('submitBtn').click());
await sleep(6000);
const f2 = main.frames().find(x => x.url().includes('AdminUserBasic'));
const src = await f2.evaluate(() => document.getElementById('profile_161').src);
if (/no_image/.test(src)) throw new Error('프로필 이미지가 반영되지 않았습니다');
await f2.evaluate(() => [...document.querySelectorAll('input._btnConfirm')].find(e => e.offsetParent).click()); await sleep(4000);
console.log('PROFILE:' + src);
"""
        out = self._repl(body, tolerate_nav=True)
        return self._marker(out, "PROFILE:") or ""

    # 모바일앱 커버(a._btnMobileTitleImageUpload): 팝업 SimplePhotoUploadForm.naver?imageUploadType=mobileTitle,
    # input[name=image] + 확인 이미지 버튼. 2026-10-09 시도에서는 올린 뒤 REPL 웹소켓이 끊기고 #mobile_title_image 가
    # 바뀌지 않아 미완 — 필요하면 블로그 앱/PC 화면에서 직접 등록한다.


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="네이버 블로그 시작 세팅 (Aside repl)")
    ap.add_argument("--config", required=True, help="설정 JSON (project/blog-design/blog.json)")
    ap.add_argument("--steps", default="info,categories,skin,title,profile", help="info,categories,skin,title,profile 중 쉼표로")
    ap.add_argument("--state", action="store_true", help="현재 상태만 출력")
    a = ap.parse_args(argv)

    cfg_path = Path(a.config).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    nb = NaverBlogAdmin(cfg["blog_id"], cfg.get("account", "u3"))
    if a.state:
        print(json.dumps(nb.state(), ensure_ascii=False, indent=2))
        return 0
    steps = [s.strip() for s in a.steps.split(",") if s.strip()]
    if "info" in steps and cfg.get("info"):
        i = cfg["info"]
        nb.set_blog_info(i["name"], i["nickname"], i["intro"], i.get("topic"))
        print("[naverblog] 기본 정보 저장", flush=True)
    if "categories" in steps and cfg.get("categories"):
        c = cfg["categories"]
        nb.setup_categories(c.get("add", []), c.get("hide_and_bottom", []))
    if "skin" in steps and cfg.get("skin"):
        nb.apply_skin(cfg["skin"])
        print(f"[naverblog] 스킨 적용: {cfg['skin']}", flush=True)
    base = cfg_path.parent
    if "title" in steps and cfg.get("title"):
        tt = cfg["title"]
        nb.upload_title(str(base / tt["image"]), tt.get("height", 300), tt.get("show_text", False))
        print("[naverblog] 타이틀 이미지 적용", flush=True)
    if "profile" in steps and cfg.get("profile_image"):
        print("[naverblog] 프로필:", nb.upload_profile(str(base / cfg["profile_image"])), flush=True)
    print(json.dumps(nb.state(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
