"""Replace the visual intro while retaining every coded painting frame after 8s.

The first half-second of the body precedes the first pigment at .8s. The old
body resumes on its exact 8s IDR. All original AAC packets are copied unchanged.
"""
from pathlib import Path
import subprocess,json,hashlib,shutil,re,argparse,time
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'production/v31'
def run(args):return subprocess.run(['ffmpeg','-nostdin','-y','-v','error',*map(str,args)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def frame(p,t):return hashlib.sha256(run(['-ss',t,'-i',p,'-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'])).hexdigest()
def slices(p):
 b=p.read_bytes();starts=list(re.finditer(b'\x00\x00(?:\x00)?\x01',b));out=[]
 for i,m in enumerate(starts):
  nal=b[m.end():starts[i+1].start() if i+1<len(starts) else len(b)].rstrip(b'\x00')
  if nal and nal[0]&31 in [1,5]:out.append(nal)
 return out
ENC=['-c:v','libx264','-preset','veryfast','-crf','14','-threads','2','-bf','0','-g','60','-keyint_min','60','-sc_threshold','0','-profile:v','high','-level','4.2','-pix_fmt','yuv420p','-color_primaries','bt709','-color_trc','iec61966-2-1','-colorspace','bt709','-color_range','tv']
def patch(ep,lang):
 E=ROOT/'episodes'/ep;D=E/'output/v31'/lang;D.mkdir(parents=True,exist_ok=True);mp4=E/f'output/{ep}-short-{lang}-v31-cover.mp4';manifest=D/'manifest.json'
 if manifest.exists():return
 source=E/f'output/{ep}-short-{lang}-v30-cover.mp4';assert (E/f'output/v30/{lang}/manifest.json').exists()
 cover=D/'cover.h264';start=D/'body-first.h264';tail=D/'body-tail.h264';joined=D/'joined.h264';check=D/'check-tail.h264';tmp=mp4.with_suffix('.rendering.mp4')
 run(['-loop','1','-framerate','30','-i',E/f'art/covers-v18/{lang}.png','-frames:v','45','-an',*ENC,'-f','h264',cover])
 run(['-ss','7.5','-i',source,'-frames:v','15','-an',*ENC,'-f','h264',start])
 run(['-ss','8','-i',source,'-map','0:v','-an','-c:v','copy','-bsf:v','h264_mp4toannexb','-f','h264',tail])
 with joined.open('wb') as f:
  for p in [cover,P/'intro.h264',start,tail]:
   with p.open('rb') as g:shutil.copyfileobj(g,f)
 run(['-r','30','-f','h264','-i',joined,'-i',source,'-map','0:v','-map','1:a','-c','copy','-t','67.5','-map_metadata','1','-metadata:s:a:0','language='+{'ko':'kor','en':'eng','ja':'jpn'}[lang],'-movflags','+faststart',tmp])
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(tmp)]));v=next(x for x in probe['streams'] if x['codec_type']=='video')
 assert (v['width'],v['height'],v['r_frame_rate'],int(v['nb_frames']))==(1080,1920,'30/1',2025),(ep,lang,v)
 assert abs(float(probe['format']['duration'])-67.5)<.03
 run(['-xerror','-i',tmp,'-f','null','-'])
 run(['-ss','8','-i',tmp,'-map','0:v','-an','-c:v','copy','-bsf:v','h264_mp4toannexb','-f','h264',check])
 original=slices(tail);changed=slices(check);assert len(original)==1785 and original==changed,(ep,lang,'Coded body changed',len(original),len(changed))
 pixels={str(t):frame(source,t)==frame(tmp,t) for t in [8.3,30,65]};assert all(pixels.values()),(ep,lang,pixels)
 assert frame(tmp,1.5)==frame(P/'intro.mp4',0),(ep,lang,'First post-cover frame differs from immediate brush')
 a=run(['-i',source,'-map','0:a','-c:a','copy','-f','adts','-']);b=run(['-i',tmp,'-map','0:a','-c:a','copy','-f','adts','-']);assert a==b,(ep,lang,'AAC packets changed')
 tmp.replace(mp4)
 settings=json.loads((E/'config/player-settings.json').read_text());(D/'settings.json').write_text(json.dumps(settings,ensure_ascii=False,indent=2)+'\n')
 report=dict(episode=ep,language=lang,path=str(mp4.resolve()),sha256=sha(mp4),frames=2025,seconds=67.5,full_decode=True,probe=probe,cover_seconds=1.5,body_seconds=66,settings=settings,source_v30_sha256=sha(source),intro_first_brush_seconds=0,unchanged_body_from_seconds=8,copied_picture_slices=len(original),body_pixel_checks=pixels,audio_packets_identical=True,renderer='Approved native intro plus stream-copied painting body',body_source_sha256=sha(E/'art/painting.json'))
 manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 for p in [cover,start,tail,joined,check]:p.unlink()
 print('PATCH_READY',ep,lang,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--one',nargs=2);a=p.parse_args()
 if a.one:patch(*a.one)
 else:
  for i in range(2,12):
   if i==6:continue
   for lang in ['ko','en','ja']:patch(f'ep{i:02}',lang)
