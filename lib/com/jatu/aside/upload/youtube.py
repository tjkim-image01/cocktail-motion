"""Upload a video to YouTube Studio through Aside, saving it PRIVATE.

Verified u2 flow on 2026-10-08:
만들기 → 동영상 업로드 → video file → Markdown 제목/설명 →
다음 (동영상 요소) → 다음 (검토) → 다음 (공개 상태) → 비공개 → 저장.
YouTube calls the final private action '저장', rather than '게시'.
An optional --thumbnail attaches a selected long-form image. Tags, playlists,
comments, and public publishing are not performed.

Example from repository root:
  python lib/com/jatu/aside/upload/youtube.py --account u2 \
    --video project/jatu009/result/jatu009_shorts.mp4 \
    --metadata project/jatu009/result/업로드자료-v2.md --execute

Without --execute, only validate and print the upload payload. Executed runs
write snapshots and a result JSON beside the input video. An interrupted upload
must be inspected in Studio before rerunning, to avoid duplicate uploads.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import pty
import re
import select
import shutil
import subprocess
import termios
import time

ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')


def read_metadata(path: Path) -> dict[str, str]:
    text = path.read_text(encoding='utf-8')
    def section(name: str) -> str:
        match = re.search(r'^##\s+' + re.escape(name) + r'\s*\n(.*?)(?=^##\s|\Z)', text, re.M | re.S)
        if not match or not match.group(1).strip():
            raise ValueError(f'Missing Markdown section: {name}')
        return match.group(1).strip()
    result = {'title': section('제목'), 'description': section('설명')}
    if len(result['title']) > 100 or len(result['description']) > 5000:
        raise ValueError('YouTube title/description length exceeded')
    return result


class AsideRepl:
    """Persistent REPL; local files are staged in its declared session directory."""
    def __init__(self, account: str, log: Path):
        self.log = log
        self.master, slave = pty.openpty()
        attrs = termios.tcgetattr(slave)
        attrs[3] &= ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        self.proc = subprocess.Popen([shutil.which('aside') or 'aside', '--account', account, 'repl'], stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        startup = self._read()
        match = re.search(r'sessionDir:\s*(.+)', startup)
        if not match:
            self.close()
            raise RuntimeError('Aside did not report its session directory')
        self.directory = Path(match.group(1).strip())

    def _read(self, timeout: int = 120) -> str:
        end = time.monotonic() + timeout
        data = b''
        while time.monotonic() < end:
            ready, _, _ = select.select([self.master], [], [], 1)
            if ready:
                try:
                    block = os.read(self.master, 65536)
                except OSError:
                    break
                if not block:
                    break
                data += block
                text = ANSI.sub('', data.decode('utf-8', errors='replace')).replace('\r', '')
                if re.search(r'repl\s*>\s*$', text):
                    with self.log.open('a', encoding='utf-8') as f:
                        f.write(text + '\n')
                    return text
            if self.proc.poll() is not None:
                break
        raise RuntimeError('Aside REPL timed out or exited; inspect Studio before retrying')

    def js(self, code: str) -> str:
        os.write(self.master, (code + '\n').encode())
        result = self._read()
        if '[error |' in result:
            raise RuntimeError(result)
        return result

    def snap(self) -> str:
        return self.js("console.log((await snapshot(page,{selector:'ytcp-uploads-dialog'})).tree)")

    def close(self):
        if self.proc.poll() is None:
            os.write(self.master, b'exit\n')
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
        os.close(self.master)


def upload(video: Path, metadata: dict[str, str], account: str, log: Path, thumbnail: Path | None = None) -> dict:
    repl = AsideRepl(account, log)
    try:
        # Aside setInputFiles accepts only session-local paths.
        shutil.copy2(video, repl.directory / video.name)
        if thumbnail is not None:
            shutil.copy2(thumbnail, repl.directory / ('thumbnail' + thumbnail.suffix))
        (repl.directory / 'youtube-metadata.json').write_text(json.dumps(metadata, ensure_ascii=False), encoding='utf-8')
        result = repl.js("await (async()=>{ const t = (await listBrowserTabs()).find(t=>t.url.startsWith('https://studio.youtube.com/')); if(t) await attachBrowserTab(t.targetId); else await openTab('https://studio.youtube.com'); console.log((await snapshot(page,{interactive:true})).tree); })()")
        if '만들기' not in result:
            raise RuntimeError('Studio create button not available; inspect login/channel')
        repl.js("await page.getByRole('button',{name:'만들기',exact:true}).click(); console.log((await snapshot(page,{selector:'[role=dialog]'})).tree)")
        repl.js("await page.getByRole('menuitem',{name:'동영상 업로드',exact:true}).click(); console.log((await snapshot(page,{selector:'ytcp-uploads-dialog'})).tree)")
        for _ in range(20):
            if '파일 선택' in repl.snap():
                break
            time.sleep(1)
        else:
            raise RuntimeError('File selection dialog did not open')
        # Inspect the actual file input rather than invoking a native picker.
        repl.js("console.log(await page.locator('input').evaluateAll(es=>es.map(e=>({type:e.type,name:e.name}))))")
        repl.js(f"await page.locator('input[type=file][name=Filedata]').setInputFiles({json.dumps('./'+video.name)}); console.log((await snapshot(page,{{selector:'ytcp-uploads-dialog'}})).tree)")
        for _ in range(60):
            state = repl.snap()
            if '동영상을 설명하는 제목 추가' in state:
                break
            time.sleep(2)
        else:
            raise RuntimeError('Details did not open; do not upload again without checking Studio')
        repl.js("await (async()=>{const m=JSON.parse(await fs.readFile('./youtube-metadata.json','utf8')); await page.getByRole('textbox',{name:'동영상을 설명하는 제목 추가(채널을 멘션하려면 @ 입력)',exact:true}).fill(m.title); await page.getByRole('textbox',{name:'시청자에게 동영상에 대해 설명해 주세요(채널을 멘션하려면 @ 입력)',exact:true}).fill(m.description); console.log((await snapshot(page,{selector:'ytcp-uploads-dialog'})).tree);})()")
        if thumbnail is not None:
            # Use the observed Studio file-upload button and its file chooser.
            image_path = './thumbnail' + thumbnail.suffix
            repl.js("await (async()=>{ const chooserPromise = page.waitForEvent('filechooser'); await page.getByRole('button',{name:'파일 업로드',exact:true}).click(); const chooser = await chooserPromise; await chooser.setFiles(" + json.dumps(image_path) + "); console.log((await snapshot(page,{selector:'ytcp-uploads-dialog'})).tree); })()")
        state = ''
        for heading in ('동영상 요소', '검토', '공개 상태'):
            state = repl.js("await page.getByRole('button',{name:'다음',exact:true}).click(); console.log((await snapshot(page,{selector:'ytcp-uploads-dialog'})).tree)")
            if not re.search(r'tab "' + re.escape(heading) + r'"[^\n]*\[selected\]', state):
                raise RuntimeError(f'Unexpected upload step: {heading}')
        state = repl.js("await page.getByRole('radio',{name:'비공개',exact:true}).click(); console.log((await snapshot(page,{selector:'ytcp-uploads-dialog'})).tree)")
        if not re.search(r'radio "비공개"[^\n]*\[checked\]', state):
            raise RuntimeError('Private visibility not confirmed; final save refused')
        links = re.findall(r'https://(?:www\.)?youtube\.com/(?:shorts/|watch\?v=)[A-Za-z0-9_-]+', state)
        # Private uploads show 저장. Do not ever choose the public radio.
        state = repl.js("await page.getByRole('button',{name:'저장',exact:true}).click(); console.log((await snapshot(page,{selector:'ytcp-uploads-dialog'})).tree)")
        for _ in range(30):
            state = repl.js("console.log((await snapshot(page,{selector:'ytcp-uploads-dialog'})).tree)")
            if '- dialog' not in state:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Save dialog did not close; inspect Studio before retrying')
        if not links:
            raise RuntimeError('No uploaded video URL captured')
        video_id = re.split(r'/|v=', links[0])[-1]
        tab = 'Shorts' if '/shorts/' in links[0] else '동영상'
        repl.js(f"await page.getByRole('tab',{{name:{json.dumps(tab)},exact:true}}).click(); console.log((await snapshot(page,{{selector:'[role=tablist]'}})).tree)")
        selector = f'ytcp-video-row:has(a[href="/video/{video_id}/edit"])'
        state = ''
        for _ in range(15):
            try:
                state = repl.js(f"console.log((await snapshot(page,{{selector:{json.dumps(selector)}}})).tree)")
                if '비공개' in state and metadata['title'] in state:
                    break
            except RuntimeError as exc:
                if 'matched no elements' not in str(exc):
                    raise
            time.sleep(1)
        if '비공개' not in state or metadata['title'] not in state:
            raise RuntimeError('Saved private content row was not confirmed')
        return {'account': account, 'video': str(video), 'visibility': 'private', 'url': links[0] if links else None, 'thumbnail': str(thumbnail) if thumbnail else None, **metadata}
    finally:
        repl.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--account', default='u2')
    ap.add_argument('--video', required=True, type=Path)
    ap.add_argument('--metadata', required=True, type=Path)
    ap.add_argument('--thumbnail', type=Path, help='Selected long-form thumbnail; omit for video-only Shorts')
    ap.add_argument('--execute', action='store_true', help='Perform the upload and private save')
    args = ap.parse_args()
    video = args.video.resolve()
    if not video.is_file():
        ap.error(f'Video not found: {video}')
    thumbnail = args.thumbnail.resolve() if args.thumbnail else None
    if thumbnail and not thumbnail.is_file():
        ap.error(f'Thumbnail not found: {thumbnail}')
    metadata = read_metadata(args.metadata.resolve())
    if not args.execute:
        print(json.dumps({'video':str(video),'account':args.account,'visibility':'private','thumbnail':str(thumbnail) if thumbnail else None,**metadata}, ensure_ascii=False, indent=2))
        return
    log = video.with_suffix('.youtube-upload.log')
    result = upload(video, metadata, args.account, log, thumbnail)
    out = video.with_suffix('.youtube-upload.json')
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
