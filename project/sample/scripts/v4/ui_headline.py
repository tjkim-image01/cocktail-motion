"""Headline (big red word) tracking per frame.
Template = rest headline of each step (frame start+30), redness map. For every frame where the headline exists,
search scale x rotation x translation (TM_CCOEFF_NORMED), refine with sub-step search & parabolic peak.
Reports transform relative to rest: dx, dy (of template centre), scale, rot (deg, + = clockwise on screen),
plus red-fill bbox and colour stats. Output _headline.json"""
import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from ui_common import *
STEPS=[(108,180,'FILL'),(180,330,'1 oz'),(330,480,'1 oz'),(480,630,'1 oz'),(630,735,'20 sec'),(735,810,'1'),(810,900,'CIN CIN!')]
SX0,SY0,SX1,SY1=620,563,1075,676
def redness(f):
    R=f.astype(np.float32); b,g,r=R[...,0],R[...,1],R[...,2]
    return np.clip((r-g-40)/100.0,0,1)
def rot_scale(t,s,a):
    h,w=t.shape; M=cv2.getRotationMatrix2D((w/2,h/2),-a,s)
    # enlarge canvas
    W=int(w*s)+16; H=int(h*s)+12
    M[0,2]+= (W-w)/2; M[1,2]+=(H-h)/2
    return cv2.warpAffine(t,M,(W,H),flags=cv2.INTER_LINEAR), (W,H)
need=set()
for a,b,_ in STEPS: need|=set(range(a,b)); need.add(a+30)
F={}
for i,f in frames():
    F[i]=redness(f[SY0:SY1,SX0:SX1]) ; 
    if i==0: pass
tpl={}
for a,b,word in STEPS:
    m=F[a+30]; ys,xs=np.nonzero(m>0.3)
    x0,x1,y0,y1=xs.min()-4,xs.max()+5,ys.min()-4,ys.max()+5
    tpl[a]=(m[y0:y1,x0:x1].copy(), (float((x0+x1)/2+SX0),float((y0+y1)/2+SY0)), [int(xs.min()+SX0),int(ys.min()+SY0),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)])
def match(img,t,s,a):
    tt,(W,H)=rot_scale(t,s,a)
    if tt.shape[0]>img.shape[0] or tt.shape[1]>img.shape[1]: return -1,(0,0)
    r=cv2.matchTemplate(img,tt,cv2.TM_CCOEFF_NORMED)
    _,mx,_,loc=cv2.minMaxLoc(r)
    # parabolic subpixel
    x,y=loc; dx=dy=0.0
    if 0<x<r.shape[1]-1:
        l,c,rr=r[y,x-1],r[y,x],r[y,x+1]; den=l-2*c+rr; dx=0.5*(l-rr)/den if den!=0 else 0
    if 0<y<r.shape[0]-1:
        u,c,d=r[y-1,x],r[y,x],r[y+1,x]; den=u-2*c+d; dy=0.5*(u-d)/den if den!=0 else 0
    return mx,(x+dx+W/2,y+dy+H/2)
out=[]
for i in range(900):
    st=[s for s in STEPS if s[0]<=i<s[1]]
    if not st: out.append(dict(i=i,present=False)); continue
    a,b,word=st[0]; t,(tcx,tcy),rb=tpl[a]
    img=F[i]
    if img.sum()<50: out.append(dict(i=i,present=False)); continue
    full = (i-a)<16 or i%15==0
    best=(-2,None,None,None)
    if full:
        for s in np.arange(0.80,1.12,0.02):
            for ang in np.arange(-6,6.1,1.0):
                sc,c=match(img,t,s,ang)
                if sc>best[0]: best=(sc,s,ang,c)
        s0,a0=best[1],best[2]
        for s in np.arange(s0-0.02,s0+0.021,0.005):
            for ang in np.arange(a0-1,a0+1.01,0.25):
                sc,c=match(img,t,s,ang)
                if sc>best[0]: best=(sc,s,ang,c)
    else:
        for s in (0.99,1.0,1.01):
            for ang in (-0.5,0,0.5):
                sc,c=match(img,t,s,ang)
                if sc>best[0]: best=(sc,s,ang,c)
    sc,s,ang,(cx,cy)=best; cx=float(cx); cy=float(cy)
    cx+=SX0; cy+=SY0
    ys,xs=np.nonzero(img>0.3)
    bbox=[int(xs.min()+SX0),int(ys.min()+SY0),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)] if len(xs) else None
    out.append(dict(i=i,present=True,word=word,score=round(float(sc),4),scale=round(float(s),3),rot=round(float(ang),2),
                    cx=round(cx,2),cy=round(cy,2),dx=round(cx-tcx,2),dy=round(cy-tcy,2),red_bbox=bbox,
                    red_mean=round(float(img[img>0.05].mean()),3) if (img>0.05).any() else 0))
json.dump(dict(templates={str(a):dict(word=w,center=tpl[a][1],red_bbox=tpl[a][2]) for a,_,w in STEPS},frames=out),open(os.path.join(OUT,'_headline.json'),'w'))
