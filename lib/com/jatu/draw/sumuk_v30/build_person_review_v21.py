"""EP06: one complete person's wash, then hair/contours, then the next person.

Hand-directed anatomical sweeps replace disconnected head/hand/body stages.
The approved image is untouched. No SVG, completion fill, MP4 or settings edits.
"""
from pathlib import Path
import copy,json,math,shutil
import cv2,numpy as np
from PIL import Image
from scipy.ndimage import binary_fill_holes
from scipy.spatial import cKDTree
from .trace_art import trace_paths

P=Path(__file__).resolve().parents[1];E=P/'episodes/ep06';A=E/'art';O=A/'raster-v21';W,H=2000,1304

def curve(nodes):
 p=np.array(nodes,float);out=[]
 for i in range(len(p)-1):
  a=p[max(0,i-1)];b=p[i];c=p[i+1];d=p[min(len(p)-1,i+2)]
  for t in np.linspace(0,1,max(3,math.ceil(np.linalg.norm(c-b)/2)),endpoint=False):
   out.append((.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)).tolist())
 return out+[p[-1].tolist()]

def support(paths,width):
 out=np.zeros((H,W),np.uint8);thickness=max(1,round(width*2*.94))
 for pts in paths:
  q=np.rint(np.array(pts)*2).astype(np.int32);cv2.polylines(out,[q],False,255,thickness,cv2.LINE_AA)
  for pt in [q[0],q[-1]]:cv2.circle(out,tuple(pt),max(1,thickness//2),255,-1,cv2.LINE_AA)
 return out

def polygon(points):
 out=np.zeros((H,W),np.uint8);cv2.fillPoly(out,[np.rint(np.array(points)*2).astype(np.int32)],255);return out

PERSON={
 'left_woman':[(363,174),(361,157),(371,141),(392,130),(414,129),(432,137),(443,152),(446,169),(459,174),(476,179),(483,194),(478,202),(493,226),(503,270),(518,322),(523,340),(544,348),(555,368),(551,391),(534,418),(500,433),(464,436),(462,447),(450,459),(434,453),(417,437),(414,466),(398,481),(395,512),(383,531),(369,528),(364,511),(364,480),(341,476),(324,465),(317,445),(298,451),(269,452),(249,444),(221,442),(199,443),(176,438),(177,430),(202,418),(236,401),(266,381),(285,370),(291,335),(312,287),(337,249),(365,226),(382,212),(370,192)],
 'right_woman':[(625,243),(623,225),(630,211),(646,201),(664,197),(684,201),(700,215),(708,232),(715,243),(724,243),(736,252),(744,267),(771,281),(795,306),(817,344),(832,383),(839,422),(839,443),(859,420),(888,420),(907,438),(909,462),(892,483),(865,498),(835,497),(815,500),(794,515),(778,519),(765,512),(771,487),(741,486),(697,487),(650,487),(609,489),(580,503),(560,501),(547,514),(535,511),(537,488),(520,486),(516,472),(530,461),(520,460),(501,453),(521,433),(536,404),(549,375),(566,363),(600,371),(618,324),(634,294),(642,282),(633,265)]}

def person_mask(who,rgb):
 # Keep the figure's actual pigments. The earlier semantic polygons included
 # strips of yellow wall/floor beside the neck and wrists.
 small=cv2.resize(rgb,(W,H),interpolation=cv2.INTER_AREA);hsv=cv2.cvtColor(small,cv2.COLOR_RGB2HSV);gray=cv2.cvtColor(small,cv2.COLOR_RGB2GRAY)
 envelope=polygon(PERSON[who]);lo,hi=(17,31) if who=='left_woman' else (14,24);background=(hsv[:,:,0]>=lo)&(hsv[:,:,0]<=hi)&(hsv[:,:,1]>65)&(gray>150)
 fg=((envelope>0)&~background).astype(np.uint8)
 fg=cv2.morphologyEx(fg,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
 fg=binary_fill_holes(fg).astype(np.uint8)*255
 return cv2.min(envelope,cv2.dilate(fg,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3))))

HAIR={
 'left_woman':[
  [(363,177),(361,158),(370,144),(384,134),(403,129),(420,131),(433,138),(441,148),(435,151),(434,163),(438,171),(431,169),(426,161),(412,156),(403,155),(394,157),(383,161),(375,169),(369,182)],
  [(449,176),(460,173),(476,178),(483,189),(481,201),(472,194),(459,189),(450,182)]],
 'right_woman':[
  [(626,244),(623,229),(629,215),(640,205),(654,199),(669,197),(683,201),(695,209),(703,218),(698,222),(696,227),(701,238),(696,239),(690,230),(675,225),(659,222),(647,224),(637,231),(630,242)],
  [(708,247),(719,243),(731,247),(739,257),(743,268),(730,262),(718,256)]]}

WASH={
 'left_woman':[
  (18,[(389,161),(381,179),(394,199),(414,211)]),(18,[(409,158),(424,179),(433,203),(435,218)]),(17,[(398,173),(402,192),(419,209)]),
  (18,[(434,207),(443,222),(437,242)]),
  (28,[(408,221),(389,247),(375,282),(364,322)]),(26,[(441,225),(429,254),(418,282),(414,316)]),
  (26,[(462,216),(476,246),(485,280),(500,329)]),(25,[(387,233),(360,254),(343,285),(327,327),(313,370)]),
  (24,[(372,248),(355,286),(339,330),(320,369)]),(22,[(448,236),(456,268),(472,305),(481,330)]),
  (14,[(314,368),(315,389),(307,409),(314,420)]),(13,[(310,382),(301,403),(304,417)]),
  (25,[(418,284),(440,291),(465,289)]),(25,[(416,303),(439,314),(471,308)]),
  (30,[(411,313),(394,344),(383,378),(386,416),(402,431)]),(28,[(432,322),(440,352),(465,387),(459,421)]),
  (28,[(408,321),(374,346),(349,376),(326,417),(298,441)]),(28,[(388,335),(351,360),(306,398),(267,428),(224,437)]),
  (26,[(366,357),(333,390),(297,423),(260,446)]),(28,[(437,332),(477,340),(503,347)]),
  (30,[(490,354),(522,355),(541,376),(526,401),(499,420)]),(28,[(495,370),(516,384),(503,406),(480,423)]),
  (27,[(346,416),(360,435),(379,450),(393,465)]),(25,[(326,426),(340,449),(361,462),(380,478)]),
  (25,[(374,468),(381,493),(382,516)]),(22,[(463,422),(453,438),(445,448)]),
  (16,[(419,311),(433,335),(441,370),(435,407)]),(16,[(406,244),(400,274),(394,314),(397,342)])],
 'right_woman':[
  (17,[(645,225),(641,243),(655,261),(674,280)]),(17,[(665,225),(683,242),(696,267),(691,284)]),(17,[(654,241),(665,257),(682,276)]),
  (18,[(695,274),(700,292),(689,312)]),
  (28,[(676,285),(655,311),(643,343),(627,373)]),(28,[(702,285),(699,313),(691,343)]),(28,[(717,279),(731,310),(739,340)]),
  (28,[(744,277),(771,296),(786,328),(801,366),(811,406),(811,444)]),
  (27,[(658,302),(640,337),(621,371),(598,411),(568,452)]),(27,[(650,333),(627,369),(605,409),(582,446)]),
  (27,[(682,308),(673,340),(656,367),(635,392)]),(26,[(764,298),(774,338),(792,378),(797,420),(800,446)]),
  (15,[(569,450),(570,468),(562,484),(557,496)]),(13,[(564,469),(552,484),(549,495)]),
  (15,[(802,447),(795,467),(783,489),(777,505)]),(14,[(812,450),(809,471),(793,496)]),
  (29,[(701,350),(700,381),(690,420),(678,465)]),(28,[(727,349),(744,380),(754,421),(741,466)]),
  (29,[(679,354),(659,385),(638,424),(614,469)]),(29,[(651,369),(620,387),(593,415),(567,455),(540,476)]),
  (28,[(605,376),(578,387),(561,421),(540,451),(518,466)]),(29,[(760,363),(778,401),(802,437),(836,470)]),
  (29,[(834,429),(866,430),(889,446),(885,465),(864,480)]),(26,[(805,429),(828,446),(851,463)]),
  (27,[(602,448),(629,462),(664,473),(707,475)]),(23,[(805,480),(834,483),(854,483)]),
  (16,[(705,355),(695,384),(681,423),(674,463)]),(14,[(680,292),(680,325),(668,353),(647,379)])]}

def union_masks(data,prefix,phase):
 out=np.zeros((H,W),np.uint8)
 for m in data['strokes']:
  if not m['element'].startswith(prefix) or m['phase']!=phase:continue
  l,t,r,b=m['bounds'];a=np.array(Image.open(A/m['file']))[:,:,3];a=cv2.resize(a,((r-l)*2,(b-t)*2),interpolation=cv2.INTER_AREA)
  swept=support(m.get('brush_paths',[m['points']]),m.get('reveal_width',m['width']))
  a=cv2.min(a,swept[t*2:b*2,l*2:r*2])
  out[t*2:b*2,l*2:r*2]=np.maximum(out[t*2:b*2,l*2:r*2],a)
 return out

def recover(target,program,width,max_passes,seed_only=False):
 covered=np.zeros_like(target);samples=[];directions=[]
 for entry in program:
  pts=entry['paths'][0]
  if not seed_only:covered|=support(entry['paths'],entry['width'])
  for a,b in zip(pts,pts[1:]):
   d=np.array(b)-a
   if np.linalg.norm(d)>.1:samples.append(a);directions.append(d/np.linalg.norm(d))
 tree=cKDTree(samples);baseline=max(1,np.count_nonzero(target>12));extra=0
 for _ in range(max_passes):
  missing=((target>12)&(covered<64)).astype(np.uint8)
  if np.count_nonzero(missing)/baseline<.003:break
  distance=cv2.distanceTransform(missing,cv2.DIST_L2,5);y,x=np.unravel_index(distance.argmax(),distance.shape);center=np.array([x/2,y/2]);_,near=tree.query(center)
  direction=np.array(directions[int(near)]);half=max(width*1.25,9)
  pts=curve([center-direction*half,center,center+direction*half]);entry={'paths':[pts],'width':width,'label':'머릿결 보충' if width<5 else '연결된 색면 보충','recovery':True}
  program.append(entry);covered|=support([pts],width);extra+=1
 return {'coverage':float(np.count_nonzero((target>12)&(covered>=64)))/baseline,'extra_passes':extra}

def hair_routes(who):
 out=[]
 if who=='left_woman':
  for d in np.linspace(0,23,12):out.append(curve([(415,131+d*.55),(395,133+d*.65),(376,143+d*.55),(365,161+d*.65)]))
  for d in np.linspace(0,18,10):out.append(curve([(414,133+d*.65),(424,136+d*.75),(431,147+d*.7),(435,153+d)]))
  for d in np.linspace(0,11,5):out.append(curve([(450,177+d*.3),(463,177+d*.6),(476,186+d*.6),(479,192+d*.65)]))
 else:
  for d in np.linspace(0,22,12):out.append(curve([(670,199+d*.6),(651,204+d*.6),(635,216+d*.7),(627,230+d*.65)]))
  for d in np.linspace(0,18,10):out.append(curve([(671,200+d*.7),(682,206+d*.7),(691,218+d*.7),(699,221+d)]))
  for d in np.linspace(0,11,5):out.append(curve([(708,247+d*.3),(719,248+d*.6),(731,255+d*.5),(738,260+d*.6)]))
 return [{'paths':[pts],'width':3.2,'label':'가르마에서 머릿결을 따라','brush_kind':'fine'} for pts in out]

def clip_paths(paths,mask):
 out=[]
 for pts in paths:
  run=[]
  for a,b in zip(pts,pts[1:]):
   for u in np.linspace(0,1,max(2,math.ceil(math.dist(a,b)*2)),endpoint=False):
    p=np.array(a)+(np.array(b)-a)*u;x,y=np.rint(p*2).astype(int);inside=0<=x<W and 0<=y<H and mask[y,x]>16
    if inside:run.append(p.tolist())
    else:
     if len(run)>=3:out.append(run)
     run=[]
  if len(run)>=3:out.append(run)
 return out

def main():
 O.mkdir(exist_ok=True);(O/'strokes').mkdir(exist_ok=True)
 backup=E/'versions/before-raster-v21';backup.mkdir(exist_ok=True)
 for f in [A/'painting.json',E/'episode.json']:
  if not (backup/f.name).exists():shutil.copy2(f,backup/f.name)
 data=json.loads((backup/'painting.json').read_text());ep=json.loads((backup/'episode.json').read_text())
 rgb=np.array(Image.open(A/'raster-v19/working-reference-4000.png').convert('RGB'));wash=np.array(Image.open(A/'raster-v19/wash-working-4000.png').convert('RGB'))
 gray=cv2.cvtColor(cv2.resize(rgb,(W,H)),cv2.COLOR_RGB2GRAY)
 marks=[];reports=[];shots=[]
 def add(entry,target,phase,group):
  allowed=cv2.min(target,support(entry['paths'],entry['width']));ys,xs=np.nonzero(allowed>1)
  if len(xs)<3:return None
  l=max(0,int(xs.min())//2-2);t=max(0,int(ys.min())//2-2);r=min(1000,math.ceil((xs.max()+1)/2)+2);b=min(652,math.ceil((ys.max()+1)/2)+2)
  alpha=cv2.resize(allowed[t*2:b*2,l*2:r*2],((r-l)*4,(b-t)*4),interpolation=cv2.INTER_LINEAR)
  rgba=np.zeros((*alpha.shape,4),np.uint8);rgba[:,:,:3]=(wash if phase=='wash' and not entry.get('reference_pixels') else rgb)[t*4:b*4,l*4:r*4];rgba[:,:,3]=alpha
  fn=f'raster-v21/strokes/{len(marks):04d}.png';Image.fromarray(rgba).save(A/fn)
  pts=[p for path in entry['paths'] for p in path];cost=sum(sum(math.dist(a,b) for a,b in zip(path,path[1:])) for path in entry['paths'])
  m={'id':len(marks),'file':fn,'bounds':[l,t,r,b],'points':pts,'brush_paths':entry['paths'],'width':entry['width'],'reveal_width':entry['width'],'pixel_scale':4,'phase':phase,'element':group,'label':entry['label'],'brush_kind':entry.get('brush_kind','flat' if phase=='wash' and entry['width']>20 else 'medium' if phase=='wash' else 'fine'),'cost':max(5,cost)**.65}
  marks.append(m);return m
 def schedule(ms,start,end):
  total=sum(m['cost'] for m in ms);cursor=start
  for m in ms:
   dt=(end-start)*m['cost']/total;m.update(start=cursor,end=cursor+dt*.94,move_end=cursor+dt);cursor+=dt
 for n,who in enumerate(['left_woman','right_woman']):
  start=.8+n*14.6;wash_end=start+7.6;hair_end=wash_end+4.2;end=start+14.6
  matte=person_mask(who,rgb);person_wash=matte.copy();person_ink=cv2.min(union_masks(data,who,'ink'),matte)
  hair=np.zeros((H,W),np.uint8)
  for poly in HAIR[who]:
   region=polygon(poly);dark=(gray<185)&(region>0);dark=cv2.morphologyEx(dark.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8));filled=binary_fill_holes(dark).astype(np.uint8)*255;hair|=filled
  hair=cv2.dilate(hair,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3)))
  person_wash[hair>0]=0;person_ink[hair>0]=0
  wash_program=[{'paths':[curve(pts)],'width':width,'label':'인물 전체 · 몸을 따라 연결해 채색'} for width,pts in WASH[who]]
  wash_report=recover(person_wash,wash_program,18,70)
  wash_marks=[m for entry in wash_program if (m:=add(entry,person_wash,'wash',who))]
  schedule(wash_marks,start,wash_end)
  hair_program=hair_routes(who);hair_report=recover(hair,hair_program,3.2,36)
  hair_marks=[m for entry in hair_program if (m:=add(entry,hair,'ink',who))]
  for m in hair_marks:m['hair_pass']=who
  schedule(hair_marks,wash_end,hair_end)
  contour_program=[]
  for m in data['strokes']:
   if not m['element'].startswith(who) or m['phase']!='ink':continue
   paths=clip_paths(m.get('brush_paths',[m['points']]),person_ink)
   if paths:contour_program.append({'paths':paths,'width':min(6,max(4.8,m.get('reveal_width',m['width']))),'label':'인물 전체 · 옷선과 손·표정 정리','brush_kind':'fine'})
  contour_program.sort(key=lambda p:min(pt[1] for path in p['paths'] for pt in path))
  contour_report=recover(person_ink,contour_program,4.8,48)
  contours=[m for entry in contour_program if (m:=add(entry,person_ink,'ink',who))]
  schedule(contours,hair_end,end)
  person_box=[153,100,568,559] if n==0 else [488,175,925,545]
  head_box=[350,116,510,244] if n==0 else [610,185,765,310]
  shots.extend([{'element':who,'start':start,'end':wash_end,'box':person_box},{'element':who,'start':wash_end,'end':hair_end,'box':head_box},{'element':who,'start':hair_end,'end':end,'box':person_box}])
  # Count newly exposed hair pixels per pass: no broad one-shot hair fill.
  covered=np.zeros_like(hair);increments=[]
  for entry in hair_program:
   cur=cv2.min(hair,support(entry['paths'],entry['width']));increments.append(np.count_nonzero((cur>16)&(covered<16)));covered|=cur
  reports.append({'person':who,'wash':wash_report,'hair':hair_report,'contours':contour_report,'hair_passes':len(hair_marks),'max_new_hair_fraction':max(increments)/max(1,np.count_nonzero(hair>16)),'timing':{'wash':[start,wash_end],'hair':[wash_end,hair_end],'contours':[hair_end,end]}})
 for key,start,end in [('objects',30,38.8),('background',38.8,49.8)]:
  old=[copy.deepcopy(m) for m in data['strokes'] if m['element']==key];a=min(m['start'] for m in old);b=max(m.get('move_end',m['end']) for m in old)
  for m in old:
   for field in ['start','end','move_end']:
    if field in m:m[field]=start+(m[field]-a)/(b-a)*(end-start)
   m['id']=len(marks);marks.append(m)
  shots.append({'element':key,'start':start,'end':end,'box':[141,0,956,652] if key=='objects' else [0,0,1000,652]})
 # The old background masks assumed the old polygonal person outlines. Give
 # newly exposed gaps real background touch-up passes, rather than a completion
 # fill or a white seam around the improved silhouettes.
 coverage=np.zeros((H,W),np.uint8)
 for m in marks:
  l,t,r,b=m['bounds'];alpha=np.array(Image.open(A/m['file']))[:,:,3];alpha=cv2.resize(alpha,((r-l)*2,(b-t)*2),interpolation=cv2.INTER_AREA)
  swept=support(m.get('brush_paths',[m['points']]),m.get('reveal_width',m['width']))
  alpha=cv2.min(alpha,swept[t*2:b*2,l*2:r*2]);coverage[t*2:b*2,l*2:r*2]=np.maximum(coverage[t*2:b*2,l*2:r*2],alpha)
 content=np.any(np.abs(cv2.resize(rgb,(W,H),interpolation=cv2.INTER_AREA).astype(float)-[248,245,234])>2,axis=2)
 missing=(content&(coverage<4)).astype(np.uint8)*255
 seeds=[{'paths':[path],'width':1} for m in marks if m['element']=='background' for path in m.get('brush_paths',[m['points']])]
 initial=len(seeds);background_report=recover(missing,seeds,14,70,seed_only=True);corrections=[]
 for entry in seeds[initial:]:
  entry.update(label='배경 · 인물 주변 여백 정리',reference_pixels=True,brush_kind='medium')
  m=add(entry,missing,'wash','background')
  if m:m['cost']=min(2,max(.5,m['cost']/20));corrections.append(m)
 existing=[m for m in marks if m['element']=='background' and m not in corrections]
 bg_wash=[m for m in existing if m['phase']=='wash']+corrections;bg_ink=[m for m in existing if m['phase']=='ink']
 schedule(bg_wash,38.8,47);schedule(bg_ink,47,49.8)
 marks=[m for m in marks if m['element']!='background']+bg_wash+bg_ink
 for i,m in enumerate(marks):m['id']=i
 new={**data,'strokes':marks,'group_order':['left_woman','right_woman','objects','background'],'group_labels':{'left_woman':'인물 1 · 전체 채색 후 선 정리','right_woman':'인물 2 · 전체 채색 후 선 정리','objects':'물건 · 생활의 도구','background':'배경 · 이곳의 하루'},'method':'Hand-directed whole-person anatomical washes, then directional hair strokes and contours; next person only after completion','raster_paint':{**data['raster_paint'],'version':21,'whole_person_wash_then_ink':True,'hair_directional_passes':True,'choreography_source':'scripts/build_person_review_v21.py'}}
 (A/'painting.json').write_text(json.dumps(new,ensure_ascii=False,separators=(',',':')))
 ep['player_director']['shots']=shots;ep.update(player_revision='raster-v21-review',player_only=True,review_status='awaiting-user',drawing_order='한 인물 전체를 연결해 채색 → 머릿결·표정·옷선 정리 → 다음 인물 → 물건 → 배경')
 (E/'episode.json').write_text(json.dumps(ep,ensure_ascii=False,indent=2)+'\n')
 report={'strokes':len(marks),'people':reports,'background_gap_touchups':len(corrections),'background_gap_coverage':background_report,'approved_image_unchanged':True,'saved_settings_unchanged':True,'MP4_created':False}
 (O/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
