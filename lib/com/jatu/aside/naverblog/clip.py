"""Inspect an existing Naver post and execute audited Clip UI steps via Aside MCP.

Never creates a new blog post. No upload/publish selectors are assumed: inspect
first, then run a JS step built from the actual editor snapshot. Every step is
recorded beside the video. A timeout is not a successful edit; inspect before
retrying any upload or final save.

python3 -m lib.com.jatu.aside.naverblog.clip --video <mp4> --inspect
python3 -m lib.com.jatu.aside.naverblog.clip --video <mp4> --post-id <id> --inspect
python3 -m lib.com.jatu.aside.naverblog.clip --video <mp4> --post-id <id> --step <js>
"""
from __future__ import annotations
import argparse
import base64
import json
from pathlib import Path
import select
import shutil
import subprocess
import time
from urllib.parse import parse_qs, urlparse


class AsideMCP:
    def __init__(self, account: str, work: Path):
        self.work = work
        self.proc = subprocess.Popen([shutil.which('aside') or 'aside', 'mcp', '--account', account],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, cwd=work)
        self.seq = 0
        self.call('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
            'clientInfo': {'name': 'naverblog-clip', 'version': '1.0'}})
        self.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    def send(self, message):
        self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + '\n')
        self.proc.stdin.flush()

    def call(self, method, params, timeout=150):
        self.seq += 1
        request_id = self.seq
        self.send({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not select.select([self.proc.stdout], [], [], min(1, deadline-time.monotonic()))[0]:
                if self.proc.poll() is not None:
                    raise RuntimeError('Aside MCP exited before responding')
                continue
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError('Aside MCP output closed')
            try: message = json.loads(line)
            except ValueError: continue
            if 'method' in message:
                if 'id' in message:
                    self.send({'jsonrpc':'2.0','id':message['id'],'error':{
                        'code':-32601,'message':'Client does not support this server request'}})
                continue
            if message.get('id') != request_id: continue
            if 'error' in message: raise RuntimeError(str(message['error']))
            return message['result']
        raise TimeoutError('Aside MCP timeout; check the browser before retrying')

    def repl(self, code, title='네이버 기존 포스트 클립 반영'):
        result = self.call('tools/call', {'name':'repl','arguments':{'title':title,'code':code}})
        texts=[]
        for i,item in enumerate(result.get('content', [])):
            if item.get('type') == 'text': texts.append(item['text'])
            elif item.get('type') == 'image':
                image=self.work/f'mcp-{self.seq}-{i}.png'
                image.write_bytes(base64.b64decode(item['data']))
                texts.append(f'IMAGE: {image}')
        text='\n'.join(texts)
        (self.work/f'step-{self.seq}.txt').write_text(text,encoding='utf-8')
        if result.get('isError'): raise RuntimeError(text)
        return text

    def close(self):
        self.proc.terminate()
        try:self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
        for stream in (self.proc.stdin,self.proc.stdout,self.proc.stderr): stream.close()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--account',default='u3')
    ap.add_argument('--blog-id',default='jatu')
    ap.add_argument('--post-id')
    ap.add_argument('--video',required=True,type=Path)
    group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--inspect',action='store_true')
    group.add_argument('--step',type=Path,help='Reviewed UI JavaScript based on the current snapshot')
    args=ap.parse_args()
    video=args.video.resolve()
    if not video.is_file():ap.error(f'Video not found: {video}')
    if args.step and not args.post_id:ap.error('--step requires an explicit --post-id')
    work=video.parent/'naver-clip-work';work.mkdir(exist_ok=True)
    run_dir=work/time.strftime('%Y%m%d-%H%M%S');run_dir.mkdir(exist_ok=True)
    payload={'account':args.account,'blog_id':args.blog_id,'post_id':args.post_id,
        'video':str(video),'status':'inspecting' if args.inspect else 'step-running'}
    manifest=run_dir/'result.json'
    manifest.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    client=None
    try:
        client=AsideMCP(args.account,run_dir)
        raw=client.repl("console.log('TABS:'+JSON.stringify(await listBrowserTabs()));")
        tabs=json.loads(next(line[5:] for line in raw.splitlines() if line.startswith('TABS:')))
        candidates=[]
        for tab in tabs:
            u=urlparse(tab['url']);q=parse_qs(u.query)
            if u.hostname!='blog.naver.com':continue
            if q.get('blogId')!=[args.blog_id] or not q.get('logNo'):continue
            if args.post_id and q['logNo']!=[args.post_id]:continue
            candidates.append(tab)
        payload['candidates']=candidates
        if len(candidates)!=1:
            payload['status']='needs-post-selection'
            print(json.dumps(candidates,ensure_ascii=False,indent=2))
            print('Specify --post-id for exactly one existing post; no post was changed.')
            return
        tab=candidates[0]
        payload['post_id']=parse_qs(urlparse(tab['url']).query)['logNo'][0]
        head='await attachBrowserTab('+json.dumps(tab['targetId'])+');\n'
        code="console.log((await snapshot(page,{interactive:true})).tree);" if args.inspect else args.step.read_text(encoding='utf-8')
        (run_dir/'step.js').write_text(head+code,encoding='utf-8')
        print(client.repl(head+code))
        payload['status']='inspected' if args.inspect else 'step-executed-unverified'
    except Exception as exc:
        payload['status']='failed';payload['error']=str(exc)
        raise
    finally:
        manifest.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
        if client:client.close()


if __name__=='__main__':main()
