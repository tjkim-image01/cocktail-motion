"""Local exact-player export service. Open render-v30.html through Aside u2.
Only explicit episode/language jobs can receive data; old editions are preserved.
"""
from pathlib import Path
import os,sys,json,functools,re,subprocess,hashlib,threading,time
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parents[1]/'scripts'))
from serve_site import Handler as ArchiveHandler,SERIES
REV=os.environ.get('SUMUK_REVISION','30');PORT=int(os.environ.get('SUMUK_RENDER_PORT','5186'))
ORDER=['ep06','ep07','ep08','ep09','ep10','ep03','ep02','ep04','ep05','ep11']
FOLDER=ROOT/f'production/v{REV}';FOLDER.mkdir(exist_ok=True,parents=True)
LOCK=threading.Lock()
JOBS=[]
for ep in ORDER:
 for lang in ['ko','en','ja']:
  E=ROOT/'episodes'/ep;D=E/f'output/v{REV}'/lang;D.mkdir(parents=True,exist_ok=True)
  frozen=D/'settings.json'
  if not frozen.exists():frozen.write_bytes((E/'config/player-settings.json').read_bytes())
  JOBS.append(dict(id=ep+'-'+lang,episode=ep,language=lang,settings=json.loads(frozen.read_text()),locale=json.loads((E/f'locales/{lang}.json').read_text()) if lang!='ko' else None))
ENCODERS={}
STATE={j['id']:{'state':'queued'} for j in JOBS}
for j in JOBS:
 p=ROOT/'episodes'/j['episode']/f'output/v{REV}'/j['language']/'manifest.json'
 if p.exists():STATE[j['id']]={'state':'complete','manifest':str(p)}
def save_state():
 with LOCK:
  p=FOLDER/'render-progress.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(STATE,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
def job_paths(jid):
 if not re.fullmatch(r'ep(0[2-9]|1[01])-(ko|en|ja)',jid):raise ValueError('Unknown job')
 ep,lang=jid.split('-');E=ROOT/'episodes'/ep;D=E/f'output/v{REV}'/lang
 return ep,lang,E,D
class Handler(ArchiveHandler):
 def do_GET(self):
  if urlsplit(self.path).path=='/api/render-v30':
   self.json_response({'jobs':JOBS,'status':STATE});return
  super().do_GET()
 def do_POST(self):
  if urlsplit(self.path).path=='/api/render-intro':
   if self.headers.get('Origin') not in {None,f'http://127.0.0.1:{PORT}'}:return self.json_response({'error':'Origin rejected'},403)
   try:
    q=parse_qs(urlsplit(self.path).query);kind=q.get('kind',[''])[0];size=int(self.headers.get('Content-Length','0'))
    if not 0<=size<=20000000:raise ValueError('Invalid intro payload')
    body=self.rfile.read(size);p=FOLDER/'intro.h264'
    if kind=='video':
     offset=int(q.get('offset',['0'])[0]);current=p.stat().st_size if p.exists() else 0
     if offset==0:p.write_bytes(body)
     elif current==offset:
      with p.open('ab') as f:f.write(body)
     else:raise ValueError('Intro offset mismatch')
    elif kind=='preview':(FOLDER/'intro-first-frame.png').write_bytes(body)
    elif kind=='quality':(FOLDER/'ep06-semantic-qa.json').write_bytes(body)
    elif kind in ['figures','background']:(FOLDER/('ep06-'+kind+'.png')).write_bytes(body)
    elif kind=='complete':
     report=json.loads(body);assert report['frames']==180
     subprocess.run(['ffmpeg','-v','error','-y','-r','30','-f','h264','-i',str(p),'-c:v','copy','-t','6',str(FOLDER/'intro.mp4')],check=True)
     report['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();(FOLDER/'intro-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    else:raise ValueError('Unknown intro operation')
    self.json_response({'ok':True});return
   except Exception as exc:self.json_response({'error':str(exc)},500);return
  if urlsplit(self.path).path!='/api/render-v30':return super().do_POST()
  if self.headers.get('Origin') not in {None,f'http://127.0.0.1:{PORT}'}:return self.json_response({'error':'Origin rejected'},403)
  q=parse_qs(urlsplit(self.path).query);jid=q.get('job',[''])[0];kind=q.get('kind',[''])[0]
  try:
   ep,lang,E,D=job_paths(jid);size=int(self.headers.get('Content-Length','0'))
   if not 0<=size<=50000000:raise ValueError('Invalid size')
   body=self.rfile.read(size)
   if kind in ['png','raw']:
    offset=int(q.get('offset',['0'])[0])
    if offset==0:
     prior=ENCODERS.pop(jid,None)
     if prior:prior['proc'].terminate();prior['log'].close()
     log=(D/'ffmpeg-encode.log').open('wb')
     inputs=['-f','rawvideo','-pix_fmt','rgba','-s','1080x1920','-r','30'] if kind=='raw' else ['-f','image2pipe','-vcodec','png','-framerate','30']
     proc=subprocess.Popen(['ffmpeg','-y','-v','error',*inputs,'-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','18','-threads','2','-pix_fmt','yuv420p','-f','h264',str(D/'video.h264')],stdin=subprocess.PIPE,stderr=log)
     ENCODERS[jid]={'proc':proc,'offset':0,'log':log}
    enc=ENCODERS[jid]
    if offset!=enc['offset']:raise ValueError('PNG stream offset mismatch')
    enc['proc'].stdin.write(body);enc['proc'].stdin.flush();enc['offset']+=size
    self.json_response({'saved':size});return
   if kind in ['video','audio']:
    p=D/('video.h264' if kind=='video' else 'mix.wav')
    if kind=='video':
     offset=int(q.get('offset',['0'])[0]);current=p.stat().st_size if p.exists() else 0
     if offset==0:p.write_bytes(body)
     elif current==offset:
      with p.open('ab') as f:f.write(body)
     elif current!=offset+size:raise ValueError(f'Offset mismatch {offset}/{current}')
    else:p.write_bytes(body)
    self.json_response({'saved':size});return
   data=json.loads(body or b'{}')
   if kind=='progress':STATE[jid]=data;save_state();self.json_response({'ok':True});return
   if kind=='complete':
    enc=ENCODERS.pop(jid,None)
    if enc:
     enc['proc'].stdin.close();code=enc['proc'].wait(timeout=120);enc['log'].close()
     if code:raise RuntimeError('PNG stream encoder failed: '+(D/'ffmpeg-encode.log').read_text())
    final=E/f'output/{ep}-short-{lang}-v{REV}-cover.mp4';tmp=final.with_suffix('.rendering.mp4')
    duration=data['seconds'];assert data['frames']==round(duration*30)
    cmd=['ffmpeg','-y','-v','error','-r','30','-f','h264','-i',str(D/'video.h264'),'-i',str(D/'mix.wav'),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','192k','-t',str(duration),'-movflags','+faststart','-metadata:s:a:0','language='+{'ko':'kor','en':'eng','ja':'jpn'}[lang],str(tmp)]
    subprocess.run(cmd,check=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(tmp)]))
    v=next(s for s in probe['streams'] if s['codec_type']=='video');a=next(s for s in probe['streams'] if s['codec_type']=='audio')
    assert (v['width'],v['height'],v['r_frame_rate'],int(v['nb_frames']))==(1080,1920,'30/1',data['frames'])
    assert abs(float(probe['format']['duration'])-duration)<.08
    assert a['tags']['language']=={'ko':'kor','en':'eng','ja':'jpn'}[lang]
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(tmp),'-f','null','-'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    tmp.replace(final)
    manifest=dict(**data,episode=ep,language=lang,path=str(final),sha256=hashlib.sha256(final.read_bytes()).hexdigest(),probe=probe,full_decode=True,settings=json.loads((D/'settings.json').read_text()),renderer='Aside u2 / exact studio canvas / '+data.get('capture','WebCodecs AVC'),body_source_sha256=hashlib.sha256((E/'art/painting.json').read_bytes()).hexdigest())
    (D/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    STATE[jid]={'state':'complete','frames':data['frames'],'elapsed':data['elapsed'],'file':str(final)};save_state()
    (D/'video.h264').unlink();(D/'mix.wav').unlink()
    self.json_response({'complete':True});return
   raise ValueError('Unknown operation')
  except Exception as e:
   STATE[jid]={'state':'error','error':str(e)};save_state();self.json_response({'error':str(e)},500)
if __name__=='__main__':
 save_state();server=ThreadingHTTPServer(('127.0.0.1',PORT),functools.partial(Handler,directory=str(SERIES)));server.allowed_origins={f'http://127.0.0.1:{PORT}'};print(f'RENDER http://127.0.0.1:{PORT}/series/site/render-v30.html',flush=True);server.serve_forever()
