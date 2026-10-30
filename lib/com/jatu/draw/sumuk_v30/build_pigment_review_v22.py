"""Single loaded pigment per stroke. Never reveal a multicolor photograph.

Keep the approved base, anatomical routes, whole-person order and hair passes.
Split color regions into separate pigment passes, separated by explicit lifts.
Source textures determine pigment density (alpha), never per-pixel RGB colors.
"""
import copy,json,math,shutil,hashlib
from pathlib import Path
import cv2,numpy as np
from PIL import Image
from .build_person_review_v21 import clip_paths,polygon

P=Path(__file__).resolve().parents[1];E=P/'episodes/ep06';A=E/'art';O=A/'raster-v22'
PAPER=np.array([248,245,234],np.float32)
PALETTE={
 'blue':('청록색',[83,137,147]),'green':('연두색',[139,157,43]),
 'orange':('주홍색',[227,83,16]),'pink':('분홍색',[205,100,116]),
 'ivory':('담황색',[181,165,131]),'skin':('살구색',[224,156,122]),
 'blush':('연지색',[180,88,86]),'ochre':('황토색',[207,145,40]),
 'wood':('나무빛 갈색',[168,124,68]),'earth':('짙은 갈색',[115,81,46]),
 'ink':('먹색',[43,42,36]),'umber_ink':('갈색 먹',[74,57,36])}
FAMILY=['ivory','skin','blue','green','orange','pink','ochre','wood','earth']
SKIN=[
 [(370,158),(435,155),(458,181),(451,216),(440,241),(413,223),(383,212)],
 [(286,364),(332,365),(344,396),(327,431),(291,427)],
 [(624,220),(687,217),(716,245),(715,284),(706,318),(678,299),(642,281)],
 [(536,455),(600,450),(605,484),(570,517),(530,512)],
 [(758,438),(831,439),(839,477),(803,522),(762,526)]]

def classify(wash):
 small=cv2.resize(wash,(2000,1304),interpolation=cv2.INTER_AREA)
 smooth=cv2.bilateralFilter(small,9,20,7);hsv=cv2.cvtColor(smooth,cv2.COLOR_RGB2HSV);h,s,v=cv2.split(hsv)
 labels=np.zeros(h.shape,np.uint8);labels[(s>65)&(v>190)]=6;labels[(s>65)&(v<=190)]=7;labels[v<125]=8
 labels[(h>=60)&(h<=115)&(s>22)]=2
 labels[(h>=24)&(h<=60)&(s>65)]=3
 labels[(h<19)&(s>120)]=4
 labels[((h>150)|(h<7))&(s>38)&(s<190)]=5
 skin=np.zeros(h.shape,np.uint8)
 for poly in SKIN:skin|=polygon(poly)
 labels[(skin>0)&(h<25)&(s>20)&(s<120)&(v>150)]=1
 return cv2.medianBlur(labels,5),small

def density(target,pigment):
 delta=PAPER-np.array(pigment,np.float32)
 return np.clip(np.sum((PAPER-target.astype(np.float32))*delta,axis=2)/max(1,float(delta@delta)),0,1)

def main():
 O.mkdir(exist_ok=True);(O/'strokes').mkdir(exist_ok=True)
 backup=E/'versions/before-raster-v22';backup.mkdir(exist_ok=True)
 for f in [A/'painting.json',E/'episode.json']:
  if not (backup/f.name).exists():shutil.copy2(f,backup/f.name)
 data=json.loads((backup/'painting.json').read_text());ep=json.loads((backup/'episode.json').read_text())
 reference=np.array(Image.open(A/'raster-v19/working-reference-4000.png').convert('RGB'))
 wash=np.array(Image.open(A/'raster-v19/wash-working-4000.png').convert('RGB'))
 families,small=classify(wash);ref_gray=cv2.cvtColor(reference,cv2.COLOR_RGB2GRAY).astype(np.float32);wash_gray=cv2.cvtColor(wash,cv2.COLOR_RGB2GRAY).astype(np.float32)
 marks=[];coverage_pixels=0
 def emit(old,pid,alpha,paths):
  nonlocal coverage_pixels
  if not paths or np.count_nonzero(alpha>5)<12:return None
  l,t,r,b=old['bounds'];ys,xs=np.nonzero(alpha>1)
  if not len(xs):return None
  x0=max(0,int(xs.min())//4*4);y0=max(0,int(ys.min())//4*4)
  x1=min(alpha.shape[1],math.ceil((xs.max()+1)/4)*4);y1=min(alpha.shape[0],math.ceil((ys.max()+1)/4)*4)
  a=alpha[y0:y1,x0:x1];color=PALETTE[pid][1]
  rgba=np.zeros((*a.shape,4),np.uint8);rgba[:,:,:3]=color;rgba[:,:,3]=a
  fn=f'raster-v22/strokes/{len(marks):04d}.png';Image.fromarray(rgba).save(A/fn)
  m=copy.deepcopy(old);m.update(id=len(marks),source_v21_id=old['id'],file=fn,bounds=[l+x0//4,t+y0//4,l+x1//4,t+y1//4],brush_paths=paths,points=[pt for path in paths for pt in path],pigment_id=pid,pigment_name=PALETTE[pid][0],pigment_rgb=color,single_pigment=True)
  m['cost']=max(3,sum(sum(math.dist(a,b) for a,b in zip(path,path[1:])) for path in paths))**.65
  m['label']=PALETTE[pid][0]+' · '+old.get('label','붓질')
  marks.append(m);coverage_pixels+=int(np.count_nonzero(a));return m
 def wash_parts(old):
  l,t,r,b=old['bounds'];source=np.array(Image.open(A/old['file']))[:,:,3]
  ids=cv2.resize(families[t*2:b*2,l*2:r*2],(source.shape[1],source.shape[0]),interpolation=cv2.INTER_NEAREST)
  target=wash[t*4:b*4,l*4:r*4];result=[]
  for k,pid in enumerate(FAMILY):
   if np.count_nonzero((ids==k)&(source>4))<12:continue
   mask2=np.zeros((1304,2000),np.uint8);local=cv2.resize(((ids==k)&(source>4)).astype(np.uint8)*255,((r-l)*2,(b-t)*2),interpolation=cv2.INTER_NEAREST);mask2[t*2:b*2,l*2:r*2]=local
   paths=clip_paths(old.get('brush_paths',[old['points']]),mask2)
   alpha=np.rint(source.astype(float)*density(target,PALETTE[pid][1])*(ids==k)).astype(np.uint8)
   m=emit(old,pid,alpha,paths)
   if m:result.append(m)
   if pid=='skin':
    # A separate loaded rose pigment, after the flesh wash. It never appears
    # as a second color within the flesh-colored stroke itself.
    rg=target[:,:,0].astype(float)-target[:,:,1].astype(float)
    blush=np.clip((rg-28)/115,0,.32)
    aa=np.rint(source.astype(float)*blush*(ids==k)).astype(np.uint8)
    m=emit(old,'blush',aa,paths)
    if m:result.append(m)
  return result
 def ink_part(old):
  l,t,r,b=old['bounds'];source=np.array(Image.open(A/old['file']))[:,:,3]
  pid='ink' if old['element'].startswith(('left_woman','right_woman')) else 'umber_ink'
  ink_luma=float(np.array(PALETTE[pid][1])@np.array([.299,.587,.114]))
  if old.get('hair_pass'):
   strength=np.clip((245-ref_gray[t*4:b*4,l*4:r*4])/(245-ink_luma),0,1)
  else:
   base=wash_gray[t*4:b*4,l*4:r*4];desired=ref_gray[t*4:b*4,l*4:r*4]
   strength=np.clip((base-desired)/np.maximum(25,base-ink_luma),0,1);strength[strength<.025]=0
  alpha=np.rint(source.astype(float)*strength).astype(np.uint8)
  return emit(old,pid,alpha,old.get('brush_paths',[old['points']]))
 def schedule(ms,start,end,previous=None):
  if not ms:return
  changes=sum(m['pigment_id']!=p['pigment_id'] for p,m in zip(ms,ms[1:]))
  initial=.13 if previous and previous['pigment_id']!=ms[0]['pigment_id'] else 0
  paint_time=end-start-initial-.13*changes
  if paint_time<=0:raise ValueError('Not enough time for visible pigment changes')
  total=sum(m['cost'] for m in ms);cursor=start+initial
  for i,m in enumerate(ms):
   if i and m['pigment_id']!=ms[i-1]['pigment_id']:cursor+=.13
   duration=paint_time*m['cost']/total;m.update(start=cursor,end=cursor+duration*.94,move_end=cursor+duration);cursor+=duration
 # Keep the user's whole-person sequence; finish a loaded wash color before
 # loading the next. Clothing first keeps palms attached to colored sleeves.
 stage_specs=[]
 for n,who in enumerate(['left_woman','right_woman']):
  start=.8+n*14.6
  stage_specs.extend([(who,'wash',start,start+7.6),(who,'hair',start+7.6,start+11.8),(who,'ink',start+11.8,start+14.6)])
 stage_specs.extend([('objects','wash',30,35.8),('objects','ink',35.8,38.8),('background','wash',38.8,47),('background','ink',47,49.8)])
 ordered=[];stages=[]
 for group,phase,start,end in stage_specs:
  chosen=[m for m in data['strokes'] if m['element']==group and (m['phase']=='wash' if phase=='wash' else bool(m.get('hair_pass')) if phase=='hair' else m['phase']=='ink' and not m.get('hair_pass'))]
  new=[]
  for old in chosen:
   if phase=='wash':new.extend(wash_parts(old))
   else:
    m=ink_part(old)
    if m:new.append(m)
  if phase=='wash':
   order=['blue','orange','ivory','skin','blush','ochre','wood','earth','green','pink'] if group=='left_woman' else ['green','pink','ivory','skin','blush','ochre','wood','earth','blue','orange'] if group=='right_woman' else ['ivory','wood','ochre','earth','skin','blue','green','orange','pink','blush']
   new.sort(key=lambda m:(order.index(m['pigment_id']),m['source_v21_id']))
  schedule(new,start,end,ordered[-1] if ordered else None);ordered.extend(new)
  stages.append({'group':group,'phase':phase,'start':start,'end':end,'strokes':len(new),'pigments':list(dict.fromkeys(m['pigment_id'] for m in new))})
 for i,m in enumerate(ordered):m['id']=i
 out={**data,'strokes':ordered,'method':'One constant RGB pigment per stroke; source image influences density only. Lift and reload between pigment colors. Whole-person wash before ink.', 'raster_paint':{**data['raster_paint'],'version':22,'single_pigment_per_stroke':True,'color_change_lift_seconds':.13,'pigments':{k:{'name':v[0],'rgb':v[1]} for k,v in PALETTE.items()},'choreography_source':'scripts/build_pigment_review_v22.py'}}
 (A/'painting.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')))
 ep.update(player_revision='raster-v22-review',player_only=True,review_status='awaiting-user',drawing_order='한 획 한 안료색, 색 교체 시 붓 들기 · 한 사람 전체 채색 → 머릿결·표정·옷선 → 다음 사람 → 물건 → 배경')
 (E/'episode.json').write_text(json.dumps(ep,ensure_ascii=False,indent=2)+'\n')
 report={'strokes':len(ordered),'stages':stages,'rule':'one constant RGB pigment per stroke; texture and dilution in alpha only','color_change_lift_seconds':.13,'approved_base_sha256':hashlib.sha256((A/'raster-v19/imagegen-base-1536.png').read_bytes()).hexdigest(),'MP4_created':False,'saved_settings_unchanged':True}
 (O/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
