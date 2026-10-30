"""EP06: move wall-board pixels outside both right sleeves into background passes.

Keep the approved source, figure timing and every unaffected asset. Exclusion
follows source sleeve color boundaries; pink skirt/white cuff stay foreground.
"""
from pathlib import Path
import json,copy,math,hashlib
import cv2,numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter1d
from build_person_review_v21 import clip_paths,support
from build_series_raster_v24 import pigment_routes
from reorder_head_first_v24 import schedule
ROOT=Path(__file__).resolve().parents[1];E=ROOT/'episodes/ep06';A=E/'art';O=A/'raster-v31';O.mkdir(exist_ok=True);(O/'strokes').mkdir(exist_ok=True)
B=E/'versions/before-arm-background-v31';data=json.loads((B/'painting.json').read_text());source=np.array(Image.open(A/data['raster_paint']['reference']).convert('RGB'));hsv=cv2.cvtColor(source,cv2.COLOR_RGB2HSV)
mask=np.zeros(source.shape[:2],np.uint8);edges={}
for who,x0,x1,lo,hi,sat in [('left_woman',277,347,65,135,12),('right_woman',595,677,26,75,60)]:
 ys=range(294*4,366*4);curve=[]
 for y in ys:
  row=hsv[y,x0*4:x1*4];good=((row[:,0]>=lo)&(row[:,0]<=hi)&(row[:,1]>sat)&(row[:,2]>80)).astype(np.uint8)
  runs=np.convolve(good,np.ones(12,dtype=np.uint8),mode='valid');hits=np.flatnonzero(runs==12)
  if not len(hits):raise ValueError((who,y/4,'No sleeve color found'))
  curve.append(float(x0*4+hits[0]))
 curve=np.array(curve);offsets=np.full(len(curve),np.nan)
 gray=cv2.cvtColor(source,cv2.COLOR_RGB2GRAY)
 for n,(y,cx) in enumerate(zip(ys,curve)):
  cx=int(round(cx));lo_x=max(x0*4,cx-28);line=gray[y,lo_x:cx+2]<145
  runs=np.flatnonzero(np.diff(np.r_[False,line,False].astype(np.int8)))
  for start,end in zip(runs[::2],runs[1::2]):
   if start>0 and end>=len(line)-13:offsets[n]=cx-(lo_x+start-1)
 valid=np.flatnonzero(np.isfinite(offsets))
 if len(valid)<10:raise ValueError((who,'Insufficient clean silhouette samples'))
 offsets=np.interp(np.arange(len(curve)),valid,offsets[valid]);curve=gaussian_filter1d(curve-offsets,1.2)
 # Horizontal wall rails join the sleeve outline. Infer the curved silhouette
 # across those rows from clean neighboring rows rather than retaining a spur.
 clean=[]
 for n,(y,edge) in enumerate(zip(ys,curve)):
  x=int(round(edge));outside=gray[y,max(x0*4,x-20):max(x0*4+1,x-8)]
  if len(outside) and float(np.median(outside))>170:clean.append(n)
 if len(clean)<10:raise ValueError((who,'No clean rail-free silhouette rows'))
 curve=np.interp(np.arange(len(curve)),clean,curve[clean]);curve=gaussian_filter1d(curve,1.0)
 for y,edge in zip(ys,curve):
  low=x0*4;cut=int(math.floor(edge-1))
  if who=='right_woman':
   row=hsv[y,low:cut];pink=np.flatnonzero((row[:,0]>155)&(row[:,1]>45)&(row[:,2]>90))
   if len(pink):low+=int(pink[-1])+8
  if cut>low:mask[y,low:cut]=255
 edges[who]={str(y/4):round(float(edge/4),3) for y,edge in zip(ys,curve) if y%40==0}
Image.fromarray(mask).save(O/'arm-background-mask.png')
old_people=Image.open(B/'people-before.png').convert('RGBA');overlay=Image.new('RGBA',old_people.size,(255,0,0,0));overlay.putalpha(Image.fromarray(mask//3));Image.alpha_composite(old_people,overlay).convert('RGB').resize((2000,1304)).save(O/'exclusion-review.jpg')
kept=[];moved=[];changed=[]
mask2=cv2.resize(mask,(2000,1304),interpolation=cv2.INTER_NEAREST)
for m in data['strokes']:
 if m['element'] not in ['left_woman','right_woman']:kept.append(copy.deepcopy(m));continue
 l,t,r,b=m['bounds'];rgba=np.array(Image.open(A/m['file']).convert('RGBA'));region=mask[t*4:b*4,l*4:r*4]>0;hit=region&(rgba[:,:,3]>0)
 if not np.any(hit):kept.append(copy.deepcopy(m));continue
 fg=rgba.copy();fg[:,:,3][region]=0;bg=rgba.copy();bg[:,:,3][~region]=0
 index=m['id'];fgfile=f'raster-v31/strokes/figure-{index:04}.png';bgfile=f'raster-v31/strokes/background-{index:04}.png';Image.fromarray(fg).save(A/fgfile);Image.fromarray(bg).save(A/bgfile)
 retained=copy.deepcopy(m);retained['file']=fgfile
 paths=copy.deepcopy(m.get('brush_paths',[m['points']]))
 if np.any(fg[:,:,3]) and paths:retained.update(points=[p for path in paths for p in path],brush_paths=paths);kept.append(retained)
 # Derive local routes from this pigment's real transferred pixels. Offsets
 # remain in logical coordinates; no whole-area fill is introduced.
 area=np.zeros((1304,2000),np.uint8);alpha2=cv2.resize(bg[:,:,3],((r-l)*2,(b-t)*2),interpolation=cv2.INTER_AREA);area[t*2:b*2,l*2:r*2]=np.where(alpha2>0,255,0)
 width=3.2 if m['phase']=='ink' else 5.5;routes=pigment_routes(area,width)
 paths=[path for route in routes for path in route['paths']]
 if not paths:
  yy,xx=np.nonzero(area);cx=float(xx.mean())/2;cy=float(yy.mean())/2
  width=max(1.8,min(5.5,max(float(xx.max()-xx.min()),float(yy.max()-yy.min()))/2+1))
  routes=[dict(paths=[[[cx-.3,cy],[cx+.3,cy]]],width=width)];paths=routes[0]['paths']
 deferred=copy.deepcopy(m);deferred.update(file=bgfile,element='background',anatomical_stage='background',points=[p for path in paths for p in path],brush_paths=paths,width=max(route['width'] for route in routes),reveal_width=max(route['width'] for route in routes),brush_kind='fine' if m['phase']=='ink' else 'medium',deferred_background=True,source_person=m['element'],source_v24_id=index,pigment_name='배경 · 팔 바깥 나무판 · '+m['pigment_name'])
 moved.append(deferred);changed.append(dict(source_id=index,person=m['element'],phase=m['phase'],pixels=int(np.count_nonzero(hit))))
# Keep all figure/object clock values. Reallocate only the final background stage.
figures=[m for m in kept if m['element']!='background'];background=[m for m in kept if m['element']=='background']
wash=[m for m in background+moved if m['phase']=='wash'];ink=[m for m in background+moved if m['phase']=='ink']
priority=['window_paper','wall_yellow','floor_ochre','wood_gold','wood_brown'];extra=list(dict.fromkeys(m['pigment_id'] for m in wash if m['pigment_id'] not in priority));priority+=extra
wash.sort(key=lambda m:priority.index(m['pigment_id']));ink.sort(key=lambda m:m['pigment_id'])
schedule(wash,38.8,47.5,figures[-1],lift=.2);schedule(ink,47.5,49.8,wash[-1],lift=.13)
marks=figures+wash+ink
for i,m in enumerate(marks):m['id']=i
data['strokes']=marks;spec=data['raster_paint'];spec.update(version=31,background_exclusion_mask='raster-v31/arm-background-mask.png',semantic_background_deferred=True,arm_background_source_sha256=hashlib.sha256(source.tobytes()).hexdigest())
passes=[]
for pid in dict.fromkeys(m['pigment_id'] for m in wash):
 ms=[m for m in wash if m['pigment_id']==pid];passes.append(dict(pigment_id=pid,name=ms[0]['pigment_name'],rgb=ms[0]['pigment_rgb'],start=ms[0]['start'],end=ms[-1]['move_end'],strokes=len(ms)))
spec['background_color_passes']=passes
target=np.zeros(mask.shape,np.uint8)
for mark in moved:
 l,t,r,b=mark['bounds'];alpha=np.array(Image.open(A/mark['file']).convert('RGBA'))[:,:,3]
 target[t*4:b*4,l*4:r*4]=np.maximum(target[t*4:b*4,l*4:r*4],alpha)
interior=cv2.erode(mask,np.ones((21,21),np.uint8));target=np.where((target>20)&(interior>0),255,0).astype(np.uint8)
Image.fromarray(target).save(O/'deferred-target-interior.png');spec['semantic_background_target_mask']='raster-v31/deferred-target-interior.png'
(A/'painting.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
report=dict(source='before-arm-background-v31/painting.json',changed=changed,moved_strokes=len(moved),moved_pixels=sum(x['pixels'] for x in changed),edges=edges,figure_and_object_timing_preserved=True,background_start=38.8,background_ink_start=47.5)
(O/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
# Asset-level proof: no positive foreground alpha remains in the exclusions.
for m in marks:
 if m['element'] not in ['left_woman','right_woman']:continue
 l,t,r,b=m['bounds'];im=np.array(Image.open(A/m['file']).convert('RGBA'));assert not np.any((im[:,:,3]>0)&(mask[t*4:b*4,l*4:r*4]>0)),m['id']
print('PASS: no arm-side background pigment appears in either figure')
