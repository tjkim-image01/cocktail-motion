"""Instagram Reel upload through the signed-in Aside MCP browser.

Run from repository root:
python3 -m lib.com.jatu.aside.upload.instagram --video VIDEO --cover JPG --caption TXT
Add --execute to publish. Inspect the browser before retrying an interrupted run.
"""
from __future__ import annotations
import argparse
import json
import re
import time
from pathlib import Path
from lib.com.jatu.aside.naverblog.clip import AsideMCP


class InstagramFlow:
    def __init__(self, client):
        self.client = client

    def js(self, code):
        return self.client.repl(code, title='Instagram 릴스 업로드')

    def snapshot(self):
        return self.js("console.log((await snapshot(page,{interactive:true})).tree);")

    def wait(self, marker, seconds=90):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            state = self.snapshot()
            if marker in state:
                return state
            time.sleep(2)
        raise TimeoutError(f'Expected UI state not reached: {marker}. Inspect before retrying.')

    def click_ref(self, state, pattern):
        match = re.search(pattern, state)
        if not match:
            raise RuntimeError(f'UI changed; selector not found: {pattern}')
        self.js(f"await page.locator({json.dumps(match.group(1))}).click();")

    def named(self, state, name):
        self.click_ref(state, r'- button "' + re.escape(name) + r'" \[ref=(\w+)\]')

    def file(self, path, selector):
        self.js("var uploadDoc=await page._sendToTarget('DOM.getDocument',{depth:-1,pierce:true});"
                "var uploadNode=await page._sendToTarget('DOM.querySelector',"
                "{nodeId:uploadDoc.root.nodeId,selector:" + json.dumps(selector) + "});"
                "if(!uploadNode.nodeId)throw Error('File input missing');"
                "await page._sendToTarget('DOM.setFileInputFiles',{nodeId:uploadNode.nodeId,files:["
                + json.dumps(str(path)) + "]});")

    def connect(self, username):
        raw = self.js("console.log('TABS:'+JSON.stringify(await listBrowserTabs()));")
        tabs = json.loads(next(line[5:] for line in raw.splitlines() if line.startswith('TABS:')))
        candidates = [t for t in tabs if t.get('url', '').startswith('https://www.instagram.com/')]
        if candidates:
            self.js('await attachBrowserTab(' + json.dumps(candidates[0]['targetId']) + ');')
        else:
            self.js("await openTab('https://www.instagram.com/');")
        state = self.snapshot()
        if username not in state:
            raise RuntimeError('Expected account not visible; open the signed-in Instagram home first.')
        if '새 게시물 만들기' in state:
            raise RuntimeError('An unfinished upload is open. Inspect it before starting another upload.')
        return state

    def post_links(self, username):
        self.js('await openTab(' + json.dumps('https://www.instagram.com/' + username + '/') + ');')
        self.wait(username)
        raw = self.js("console.log('POSTS:'+JSON.stringify(await page.locator('a[href]').evaluateAll(es=>es.map(e=>e.href).filter(u=>/\\/(p|reel)\\//.test(new URL(u).pathname)))));")
        return list(dict.fromkeys(json.loads(next(line[6:] for line in raw.splitlines() if line.startswith('POSTS:')))))

    def upload(self, state, video, cover, caption):
        self.click_ref(state, r'- link \[ref=(\w+)\]:\n\s+- img "새로운 게시물"')
        self.wait('컴퓨터에서 선택')
        self.file(video, 'input[type=file]')
        state = self.snapshot()
        deadline = time.monotonic() + 90
        while '자르기' not in state:
            if '이제 동영상 게시물이 릴스로 공유됩니다' in state:
                self.named(state, '확인')
            if time.monotonic() > deadline:
                raise TimeoutError('Video import timed out; inspect the existing draft.')
            time.sleep(2)
            state = self.snapshot()
        self.click_ref(state, r'- button \[ref=(\w+)\]:\n\s+- img "자르기 선택"')
        state = self.snapshot()
        self.click_ref(state, r'- button \[ref=(\w+)\]:\n\s+- text: "9:16"')
        self.named(self.snapshot(), '다음')
        self.wait('커버 사진')
        self.file(cover, 'input[type=file][accept="image/jpeg,image/png"]')
        self.named(self.snapshot(), '다음')
        state = self.wait('캡션 추가...')
        self.js("await page.getByRole('textbox',{name:'캡션 추가...',exact:true}).fill("
                + json.dumps(caption, ensure_ascii=False) + ");")
        state = self.snapshot()
        match = re.search(r'- switch \[ref=(\w+)\]([^\n]*)', state)
        if not match:
            raise RuntimeError('AI label switch missing')
        if '[checked]' not in match.group(2):
            self.js('await page.locator(' + json.dumps(match.group(1)) + ').click();')
        state = self.snapshot()
        if '[checked]' not in re.search(r'- switch \[ref=\w+\]([^\n]*)', state).group(1):
            raise RuntimeError('AI label was not enabled')
        # Snapshot ref is essential: global role/name can resolve another Share control.
        self.named(state, '공유하기')
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            state = self.snapshot()
            if '공유되었습니다' in state:
                return state
            if '다시 시도' in state or '공유할 수 없' in state:
                raise RuntimeError(state)
            time.sleep(3)
        raise TimeoutError('Publish result unknown. Check profile before retrying.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account', default='u5')
    parser.add_argument('--username', default='jfktwo5')
    parser.add_argument('--video', required=True, type=Path)
    parser.add_argument('--cover', required=True, type=Path)
    parser.add_argument('--caption', required=True, type=Path)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    paths = [p.resolve() for p in (args.video, args.cover, args.caption)]
    for path in paths:
        if not path.is_file():
            parser.error(f'File missing: {path}')
    video, cover, caption_file = paths
    caption = caption_file.read_text(encoding='utf-8').strip()
    if not caption or len(caption) > 2200:
        parser.error('Caption must contain 1–2200 characters')
    manifest = video.with_suffix('.instagram-upload.json')
    if manifest.exists():
        previous = json.loads(manifest.read_text())
        if previous.get('status') in ('published', 'verified', 'publishing', 'unknown'):
            parser.error('Existing publication record requires inspection; duplicate upload blocked.')
    data = dict(account=args.account, username=args.username, video=str(video),
                cover=str(cover), caption=caption, status='planned')
    if not args.execute:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    work = video.parent / 'instagram-work' / time.strftime('%Y%m%d-%H%M%S')
    work.mkdir(parents=True, exist_ok=True)
    client = None
    try:
        client = AsideMCP(args.account, work)
        flow = InstagramFlow(client)
        state = flow.connect(args.username)
        data['status'] = 'publishing'
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        proof = flow.upload(state, video, cover, caption)
        data.update(status='published', evidence=proof, work=str(work))
        data['profile_post_urls'] = flow.post_links(args.username)
    except Exception as exc:
        data.update(status='unknown', error=str(exc), work=str(work))
        raise
    finally:
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        if client:
            client.close()
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
