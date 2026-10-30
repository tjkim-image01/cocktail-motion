import argparse
from pathlib import Path
import json,math,wave,subprocess
import numpy as np
import stable_whisper
from scipy.ndimage import gaussian_filter1d

def _project_path():
 parser=argparse.ArgumentParser(description='M013 reference recipe; character-specific coordinates must be adapted for a new character')
 parser.add_argument('project',type=Path)
 return parser.parse_args().project

P=Path(_project_path()).resolve();A=P/'audio';text=(A/'dialogue.txt').read_text().strip()
model=stable_whisper.load_faster_whisper('small',device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
syllables=[c for c in text if '\uac00'<=c<='\ud7a3']
result=model.align(str(A/'eunsol-dialogue.wav'),' '.join(syllables),language='ko',regroup=False,suppress_silence=True,min_word_dur=.025,verbose=False)
data=result.to_dict();(P/'qa/speech-alignment-raw.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
units=[]
for seg in data['segments']:
 for w in seg.get('words',[]):
  chars=[c for c in w['word'] if '\uac00'<=c<='\ud7a3']
  for j,c in enumerate(chars):units.append({'text':c,'start':w['start']+(w['end']-w['start'])*j/len(chars),'end':w['start']+(w['end']-w['start'])*(j+1)/len(chars)})
# Use actual WAV energy for silence/closure and normalized phonetic articulation.
raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(A/'eunsol-dialogue.wav'),'-ac','1','-ar','16000','-f','f32le','-']);a=np.frombuffer(raw,dtype='<f4');sr=16000;fps=60;duration=len(a)/sr
VOWELS=['A','E','A','E','A','E','A','E','O','A','E','E','O','U','A','E','I','U','I','I','I']
SHAPES={'REST':[0,1,0],'M':[0,1,0],'A':[.86,1,0],'E':[.42,1.17,0],'I':[.22,1.2,0],'O':[.70,.92,.85],'U':[.38,.82,1]}
samples=[]
for f in range(math.ceil(duration*fps)+1):
 t=f/fps;shape='REST';syllable='';amp=float(np.sqrt(np.mean(a[max(0,int((t-.015)*sr)):min(len(a),int((t+.025)*sr))]**2))) if t<duration else 0
 for u in units:
  if u['start']-.025<=t<u['end']:
   c=u['text'];n=ord(c)-0xac00;initial=n//588;v=n//28%21;final=n%28;shape=VOWELS[v];syllable=c
   if initial in [6,7,8,17] and t<u['start']+.028:shape='M'
   if final in [16,17,18,26] and t>u['end']-.028:shape='M'
   if v in [9,10,11,14,15,16] and t<u['start']+(u['end']-u['start'])*.28:shape='O' if v<12 else 'U'
   break
 if amp<.006:shape='REST'
 op,wide,rnd=SHAPES[shape];op*=.55+.45*min(1,amp/.1)
 samples.append({'open':op,'width':wide,'round':rnd,'syllable':syllable,'shape':shape,'rms':round(amp,5)})
# 25ms coarticulation on each curve coordinate; topology remains identical.
for name in ['open','width','round']:
 vals=gaussian_filter1d([r[name] for r in samples],.75)
 for r,v in zip(samples,vals):r[name]=round(float(v),4)
(A/'lipsync.json').write_text(json.dumps({'text':text,'voice':'은솔','duration':duration,'fps':fps,'method':'Known Korean syllables forced aligned with local stable-ts/faster-whisper small + 60Hz WAV RMS + bilabial closures + smoothed Bezier viseme parameters','syllables':units,'samples':samples},ensure_ascii=False,separators=(',',':')))
print('Aligned',len(units),'syllables,',len(samples),'lip keys,',duration,'seconds',flush=True)
