"""Card text rows per step: median rest image -> horizontal ink bands -> bbox, baseline, cap height, colours.
Output _text.json and crops text_rows_step*.png"""
import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from ui_common import *
STEPS=[(108,180),(180,330),(330,480),(480,630),(630,735),(735,810),(810,900)]
need=set()
for a,b in STEPS: need|=set(range(a+14,a+34))
F={}
for i,f in frames():
    if i in need: F[i]=f[505:775,640:1055].copy()
X0,Y0=640,505
res=[]
for si,(a,b) in enumerate(STEPS):
    med=np.median(np.stack([F[i] for i in range(a+14,a+34)]),axis=0).astype(np.uint8)
    cv2.imwrite(os.path.join(OUT,f'_med_step{si+1}.png'),med)
    R=med.astype(np.int16); bl,g,r=R[...,0],R[...,1],R[...,2]
    gray=0.299*r+0.587*g+0.114*bl
    ink=(gray<200)
    # exclude card border: keep interior x 20..385, y 18..250 of crop
    inner=np.zeros_like(ink); inner[22:245,22:385]=True
    ink&=inner
    rows=ink.sum(1)
    bands=[];cur=None
    for y,v in enumerate(rows):
        if v>0 and cur is None: cur=[y,y]
        elif v>0: cur[1]=y
        elif cur is not None:
            bands.append(cur); cur=None
    if cur: bands.append(cur)
    # merge bands separated by <=2 rows
    mb=[]
    for bd in bands:
        if mb and bd[0]-mb[-1][1]<=3: mb[-1][1]=bd[1]
        else: mb.append(bd)
    out=[]
    for y0,y1 in mb:
        if y1-y0<4: continue
        sub=ink[y0:y1+1]; cols=np.nonzero(sub.any(0))[0]
        x0,x1=cols.min(),cols.max()
        prof=sub.sum(1); thr=0.35*prof.max()
        base=y0+np.nonzero(prof>thr)[0].max()
        top=y0+np.nonzero(prof>thr)[0].min()
        px=R[y0:y1+1,x0:x1+1][sub[:,x0:x1+1]]
        gpx=(0.299*px[:,2]+0.587*px[:,1]+0.114*px[:,0])
        dark=px[gpx<np.percentile(gpx,20)]
        # red-ish fill pixels
        rr=px[:,2].astype(int); gg=px[:,1].astype(int)
        redpx=px[(rr-gg>70)&(rr>200)]
        out.append(dict(y0=int(y0+Y0),y1=int(y1+Y0),x0=int(x0+X0),x1=int(x1+X0),top_dense=int(top+Y0),baseline=int(base+Y0),
                        ink_height=int(base-top+1),
                        dark_rgb=[int(v) for v in np.median(dark,axis=0)[::-1]],
                        bright_red_rgb=[int(v) for v in np.median(redpx,axis=0)[::-1]] if len(redpx)>20 else None,
                        npx=int(sub.sum())))
    res.append(dict(step=si+1,frames=[a+14,a+33],rows=out))
    print('step',si+1)
    for o in out: print('  ',o)
json.dump(res,open(os.path.join(OUT,'_text.json'),'w'),indent=0)
