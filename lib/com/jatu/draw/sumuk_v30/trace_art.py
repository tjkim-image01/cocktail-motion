"""Build editable vector pigments and independent ink strokes from each cleaned plate.
The initial canvas is one paper colour, never a prepared full drawing.
"""
import argparse,json,math,heapq
from pathlib import Path
import numpy as np,cv2
from PIL import Image,ImageDraw
from skimage.morphology import skeletonize
P=Path(__file__).resolve().parents[1];W,H=1000,652;PAPER=(248,245,234)
ORDER=['sketch','background','left','center','right','detail']
BUDGET={'sketch':2.2,'background':11,'left':10.5,'center':12,'right':11,'detail':2.3}

def trace_paths(mask):
 sk=skeletonize(mask>0);ys,xs=np.nonzero(sk);pixels=set(zip(xs.tolist(),ys.tolist()));neighbors={}
 for x,y in pixels:
  ns=[]
  for dx,dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
   q=(x+dx,y+dy)
   if q not in pixels:continue
   if dx and dy and ((x+dx,y) in pixels or (x,y+dy) in pixels):continue
   ns.append(q)
  neighbors[x,y]=ns
 visited=set();paths=[]
 def edge(a,b):return (a,b) if a<b else (b,a)
 def walk(a,b):
  pts=[a,b];visited.add(edge(a,b));prev,cur=a,b
  while len(neighbors[cur])==2:
   nxt=next(p for p in neighbors[cur] if p!=prev)
   if edge(cur,nxt) in visited:break
   visited.add(edge(cur,nxt));pts.append(nxt);prev,cur=cur,nxt
  if len(pts)>=3:
   approx=cv2.approxPolyDP(np.array(pts,dtype=np.float32).reshape(-1,1,2),.75,False).reshape(-1,2).tolist()
   length=sum(math.dist(pts[i],pts[i+1]) for i in range(len(pts)-1))
   if len(approx)>1 and length>=2:paths.append((length,approx))
 for a in pixels:
  if len(neighbors[a])!=2:
   for b in neighbors[a]:
    if edge(a,b) not in visited:walk(a,b)
 for a in pixels:
  for b in neighbors[a]:
   if edge(a,b) not in visited:walk(a,b)
 return paths

def group(cx,cy,area=0):
 if area>25000 or cy<180:return 'background'
 if cy>540:return 'detail'
 if cx<430:return 'left'
 if cx>670:return 'right'
 return 'center'

def paths_d(contours,hierarchy):
 parts=[]
 for c in contours:
  pts=cv2.approxPolyDP(c,.85,True).reshape(-1,2)
  if len(pts)<3:continue
  parts.append('M '+' L '.join(f'{int(x)} {int(y)}' for x,y in pts)+' Z')
 return ' '.join(parts)

def build(ep):
 E=P/'episodes'/ep;A=E/'art';S=A/'strokes';S.mkdir(exist_ok=True)
 original=Image.open(A/'original-clean.png').convert('RGB');original.thumbnail((928,604),Image.Resampling.LANCZOS);plate=Image.new('RGB',(W,H),PAPER);offset=((W-original.width)//2,(H-original.height)//2);plate.paste(original,offset)
 # The untouched cleanup plate is separately retained for the end dissolve.
 rgb=np.array(plate);bgr=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR);blur=cv2.bilateralFilter(bgr,5,28,28);lum=cv2.cvtColor(blur,cv2.COLOR_BGR2GRAY);ink=(lum<142).astype('uint8')*255
 smooth=cv2.inpaint(blur,ink,4,cv2.INPAINT_TELEA);smooth=cv2.medianBlur(smooth,7);smooth=cv2.GaussianBlur(smooth,(5,5),.9);lab=cv2.cvtColor(smooth,cv2.COLOR_BGR2LAB);samples=lab.reshape(-1,3).astype('float32');cv2.setRNGSeed(37)
 _,labels,centers=cv2.kmeans(samples,18,None,(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,40,.4),2,cv2.KMEANS_PP_CENTERS)
 labels=labels.reshape(H,W);colors=cv2.cvtColor(np.uint8(centers)[None,:,:],cv2.COLOR_LAB2RGB)[0]
 candidates=[]
 for index,color in enumerate(colors):
  if min(color)>217 and max(color)-min(color)<44:continue
  mask=(labels==index).astype('uint8')*255;mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
  contours0,hier0=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
  if hier0 is not None:
   for ci,c0 in enumerate(contours0):
    if hier0[0,ci,3]>=0 and cv2.contourArea(c0)<260:cv2.drawContours(mask,[c0],-1,255,-1)
  n,cc,stats,cent=cv2.connectedComponentsWithStats(mask)
  for j in range(1,n):
   area=stats[j,cv2.CC_STAT_AREA]
   if area<90:continue
   l,t,w,h=stats[j,:4];component=(cc[t:t+h,l:l+w]==j).astype('uint8')*255
   candidates.append(dict(area=int(area),bounds=(int(l),int(t),int(l+w),int(t+h)),mask=component,color=tuple(int(v) for v in color),center=cent[j]))
 candidates=sorted(candidates,key=lambda c:c['area'],reverse=True)[:130]
 thick=cv2.morphologyEx(ink,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
 n,cc,stats,cent=cv2.connectedComponentsWithStats(thick)
 for j in range(1,n):
  area=stats[j,cv2.CC_STAT_AREA]
  if area<80:continue
  l,t,w,h=stats[j,:4];component=(cc[t:t+h,l:l+w]==j).astype('uint8')*255
  candidates.append(dict(area=int(area),bounds=(int(l),int(t),int(l+w),int(t+h)),mask=component,color=(77,75,62),center=cent[j],inkfill=True))
 strokes=[];svg=[]
 def add(mask,bounds,pts,width,phase,g,label,color,cost,shape):
  if len(pts)<2:return
  l,t,r,b=bounds;im=Image.new('RGBA',(r-l,b-t),tuple(color)+(0,));im.putalpha(Image.fromarray(mask));fn=f'strokes/{len(strokes):03d}.png';im.save(A/fn)
  strokes.append(dict(id=len(strokes),file=fn,bounds=[l,t,r,b],points=pts,width=width,phase=phase,element=g,label=label,cost=cost))
  svg.append(shape)
 # Sparse guides, three strokes only. No human or completed composition underlay.
 for pts in [[(90,170),(460,160),(900,175)],[(110,550),(490,570),(875,550)],[(490,210),(505,500)]]:
  pad=4;l=max(0,min(p[0] for p in pts)-pad);t=max(0,min(p[1] for p in pts)-pad);r=min(W,max(p[0] for p in pts)+pad);b=min(H,max(p[1] for p in pts)+pad);m=Image.new('L',(r-l,b-t));ImageDraw.Draw(m).line([(x-l,y-t) for x,y in pts],fill=75,width=1)
  add(np.array(m),(l,t,r,b),pts,1,'ink','sketch','옅은 구도선',(190,179,155),1,'')
 for c in candidates:
  l,t,r,b=c['bounds'];m=c['mask'];width=24;rows=np.linspace(0,b-t-1,max(2,math.ceil((b-t)/17)+1));pts=[]
  for yy in rows:
   xs=np.flatnonzero(m[min(b-t-1,round(yy))]);
   if not len(xs):continue
   pair=[(l+int(xs[0]),t+round(yy)),(l+int(xs[-1]),t+round(yy))]
   if len(pts)//2%2:pair.reverse()
   pts+=pair
  if len(pts)<2:continue
  contours,hierarchy=cv2.findContours(m,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE);global_contours=[c0+np.array([[[l,t]]]) for c0 in contours];d=paths_d(global_contours,hierarchy);color=c['color'];g=group(*c['center'],c['area']);phase='ink' if c.get('inkfill') else 'wash'
  add(m,(l,t,r,b),pts,width,phase,g,'머리와 도구의 먹색' if phase=='ink' else '옷과 풍경의 색면',color,max(.5,math.sqrt(c['area'])/30),f'<path d="{d}" fill="rgb{color}" fill-rule="evenodd"/>')
 thin=cv2.bitwise_and(ink,cv2.bitwise_not(cv2.dilate(thick,np.ones((3,3),np.uint8))))
 # Follow all surviving ink in small local regions; no face is discarded by
 # a global longest-line cutoff. Each region remains a separate pigment layer.
 for yy in range(0,H,82):
  for xx in range(0,W,82):
   r=min(W,xx+82);b=min(H,yy+82);tile=thin[yy:b,xx:r];paths=trace_paths(tile)
   if not paths:continue
   segments=[]
   for length,localpts in paths:
    segments.append((length,[(px+xx,py+yy) for px,py in localpts]))
   # A nearest-endpoint route keeps travel among nearby contour fragments short.
   remaining=segments[:];ordered=[];cursor=(xx,yy)
   while remaining:
    i=min(range(len(remaining)),key=lambda i:min(math.dist(cursor,remaining[i][1][0]),math.dist(cursor,remaining[i][1][-1])))
    length,pts=remaining.pop(i)
    if math.dist(cursor,pts[-1])<math.dist(cursor,pts[0]):pts=pts[::-1]
    ordered.append((length,pts));cursor=pts[-1]
   pts=[p0 for _,points in ordered for p0 in points];mask=Image.new('L',(r-xx,b-yy));dr=ImageDraw.Draw(mask)
   for length,points in ordered:
    local=[(px-xx,py-yy) for px,py in points];dr.line(local,fill=235,width=2,joint='curve')
    for px,py in local:dr.ellipse((px-1,py-1,px+1,py+1),fill=235)
   g=group(xx+41,yy+41);shape=''.join('<path d="M '+' L '.join(f'{px:.1f} {py:.1f}' for px,py in points)+'" fill="none" stroke="#514f41" stroke-width="2" stroke-linecap="round"/>' for _,points in ordered)
   add(np.array(mask),(xx,yy,r,b),pts,2.4,'ink',g,'얼굴·손·도구의 이어지는 먹선',(81,79,65),max(.5,math.sqrt(sum(length for length,_ in ordered))/7),shape)
 strokes.sort(key=lambda m:(ORDER.index(m['element']),0 if m['phase']=='wash' else 1,m['id']))
 cursor=.8
 for g in ORDER:
  ms=[m for m in strokes if m['element']==g]
  if not ms:continue
  budget=BUDGET[g];weights=sum(m['cost'] for m in ms)
  for m in ms:
   alloc=budget*m['cost']/weights;pause=min(.07,alloc*.12);m.update(start=cursor,end=cursor+alloc-pause,move_end=cursor+alloc);cursor+=alloc
 # The total may have an empty group; normalize all after the guides to 49.8s.
 scale=49/(cursor-.8)
 for m in strokes:
  for k in ['start','end','move_end']:m[k]=.8+(m[k]-.8)*scale
 im=Image.new('RGBA',(W,H),PAPER+(255,))
 for m in strokes:im.alpha_composite(Image.open(A/m['file']),tuple(m['bounds'][:2]))
 im.save(A/'complete.png');plate.save(A/'original-layout.png');Image.new('RGB',(W,H),PAPER).save(A/'initial.png')
 (A/'drawing.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 652">\n'+f'<rect width="1000" height="652" fill="#f8f5ea"/>\n'+'\n'.join(svg)+'</svg>')
 data=dict(width=W,height=H,pixel_scale=1,duration=60,draw_end=49.8,strokes=strokes,initial='blank paper',method='native vector tracing; flat color polygons and separately traced ink paths',original='original-layout.png',group_order=ORDER)
 (A/'painting.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
 report=dict(episode=ep,strokes=len(strokes),wash=sum(m['phase']=='wash' for m in strokes),initial_blank=True,duration=60,draw_end=49.8,source_resolution=Image.open(A/'original-clean.png').size)
 (E/'qa/art.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('episodes',nargs='*');a=p.parse_args()
 for e in a.episodes or [x['id'] for x in json.loads((P/'manifest.json').read_text())]:build(e)
