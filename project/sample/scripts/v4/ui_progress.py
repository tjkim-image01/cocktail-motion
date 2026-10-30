"""Progress bar fill per frame + counter text change segmentation.
Fill: red pixels (R-G>60, R>190) inside track box x 672..922, y 722..746 -> xmin,xmax,width; also per-row extents.
Counter: crop x 922..1040, y 716..752, ink mask gray<170; change metric = pixels of A not in dilate(B,2) + vice versa
relative to previous frame. Segments of stable content get a crop sheet for visual reading.
Outputs _progress.json, counter_segments.png"""
import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from ui_common import *
res=[]; crops={}
prev=None
for i,f in frames():
    R=f.astype(np.int16)
    sub=R[722:747,672:923]; b,g,r=sub[...,0],sub[...,1],sub[...,2]
    red=(r-g>60)&(r>190)
    cols=np.nonzero(red.sum(0)>=3)[0]
    fill=None
    if len(cols):
        # largest contiguous run
        runs=np.split(cols,np.nonzero(np.diff(cols)>3)[0]+1)
        run=max(runs,key=len)
        rows=np.nonzero(red[:,run[0]:run[-1]+1].any(1))[0]
        fill=dict(x0=int(run[0]+672),x1=int(run[-1]+672),w=int(run[-1]-run[0]+1),y0=int(rows.min()+722),y1=int(rows.max()+722),npx=int(red.sum()))
    c=f[714:754,920:1045]
    gray=cv2.cvtColor(c,cv2.COLOR_BGR2GRAY)
    ink=(gray<170).astype(np.uint8)
    diff=None
    if prev is not None:
        k=np.ones((5,5),np.uint8)
        a=int((ink & (1-cv2.dilate(prev,k))).sum()); bb=int((prev & (1-cv2.dilate(ink,k))).sum())
        diff=a+bb
    prev=ink
    crops[i]=c
    res.append(dict(i=i,fill=fill,counter_ink=int(ink.sum()),counter_diff=diff))
json.dump(res,open(os.path.join(OUT,'_progress.json'),'w'))
# segments
segs=[];start=0
for e in res[1:]:
    if e['counter_diff'] is not None and e['counter_diff']>12:
        segs.append((start,e['i']-1)); start=e['i']
segs.append((start,899))
json.dump(segs,open(os.path.join(OUT,'_counter_segs.json'),'w'))
print(len(segs))
imgs=[crops[a] for a,b in segs]; labs=[f'{a}-{b}' for a,b in segs]
for k in range(0,len(imgs),60):
    sheet(imgs[k:k+60],labs[k:k+60],cols=6,scale=1.0,path=os.path.join(OUT,f'_counter_segments_{k//60}.png'))
