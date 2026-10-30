"""Export one prepared edition through the actual Aside u2 browser.

The local render service performs file capture, mux and complete decode checking.
A persistent CLI REPL avoids its 120-second per-command evaluation limit.
"""
from pathlib import Path
import argparse,json,subprocess,sys,urllib.request,time,pty,os,select,re
ROOT=Path(__file__).resolve().parents[1]
REV=os.environ.get('SUMUK_REVISION','30');PORT=os.environ.get('SUMUK_RENDER_PORT','5186')
def export(episode,language,settings=None):
 E=ROOT/'episodes'/episode;D=E/f'output/v{REV}'/language;D.mkdir(parents=True,exist_ok=True)
 saved=json.loads((settings or E/'config/player-settings.json').read_text());frozen=D/'settings.json'
 if frozen.exists() and json.loads(frozen.read_text())!=saved:raise ValueError('Production settings are already frozen; use a new production revision for changed settings')
 frozen.write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n')
 result=E/f'output/{episode}-short-{language}-v{REV}-cover.mp4'
 if (D/'manifest.json').exists():return result
 try:urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/render-v30',timeout=3).close()
 except OSError:
  log=(ROOT/f'production/v{REV}/cli-server.log').open('ab');subprocess.Popen([sys.executable,str(ROOT/'scripts/render_v30_server.py')],stdout=log,stderr=log,start_new_session=True)
  for _ in range(50):
   try:urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/render-v30',timeout=1).close();break
   except OSError:time.sleep(.1)
 plan=json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/render-v30'))
 job=next(j for j in plan['jobs'] if j['id']==episode+'-'+language)
 if job['settings']!=saved:raise ValueError('Restart the render service to reload the frozen settings')
 master,slave=pty.openpty();proc=subprocess.Popen(['/Users/jatu/.local/bin/aside','--account','u2','repl'],stdin=slave,stdout=slave,stderr=slave,close_fds=True);os.close(slave)
 url=f'http://127.0.0.1:{PORT}/series/site/render-v30.html?job='+episode+'-'+language
 output='';next_poll=time.monotonic()+10;deadline=time.monotonic()+3600
 try:
  os.write(master,('var exportPage=await openTab('+json.dumps(url)+');var exportTarget=exportPage.targetId;\n').encode())
  while time.monotonic()<deadline:
   if select.select([master],[],[],1)[0]:
    data=os.read(master,65536)
    if not data:raise RuntimeError('Aside REPL exited')
    output+=data.decode(errors='replace');output=output[-200000:]
    matches=list(re.finditer(r'SUMUK_STATE(\{[^\r\n]+\})',output))
    if matches:
     state=json.loads(matches[-1][1])
     if state.get('state')=='error':raise RuntimeError(state['error'])
     if state.get('state')=='complete':
      assert (D/'manifest.json').exists() and result.exists();return result
   if time.monotonic()>=next_poll:
    os.write(master,b"var exportPage=await attachBrowserTab(exportTarget);console.log('SUMUK_STATE'+JSON.stringify(await exportPage.evaluate(()=>window.renderV30)))\n");next_poll=time.monotonic()+5
   if proc.poll() is not None:raise RuntimeError('Aside REPL stopped: '+output[-1000:])
  raise TimeoutError('One-hour export timeout; inspect production/v30/render-progress.json')
 finally:
  try:os.write(master,b'await closeTab(exportPage);\nexit\n');proc.wait(timeout=5)
  except Exception:proc.terminate()
  os.close(master)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('language',choices=['ko','en','ja']);p.add_argument('--settings',type=Path);a=p.parse_args();print(export(a.episode,a.language,a.settings))
