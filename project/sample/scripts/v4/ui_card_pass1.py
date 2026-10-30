"""Pass 1: per-frame card outline (minAreaRect of filled outer ink contour), darkest-ink opacity proxy,
and red headline components. Writes card_pass1.json"""
import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from ui_common import *
X0,Y0,X1,Y1 = 560,430,1080,830
res=[]
for i,f in frames():
    R=f[Y0:Y1,X0:X1].astype(np.int16)
    b,g,r=R[...,0],R[...,1],R[...,2]
    gray=(0.299*r+0.587*g+0.114*b)
    ink=(248-gray>45).astype(np.uint8)  # anything clearly darker than bg (ink, red, text)
    k=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7))
    cl=cv2.morphologyEx(ink,cv2.MORPH_CLOSE,k)
    cnts,_=cv2.findContours(cl,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    card=None
    if cnts:
        c=max(cnts,key=cv2.contourArea)
        x,y,w,h=cv2.boundingRect(c)
        if w>250 and h>150:
            (cx,cy),(rw,rh),ang=cv2.minAreaRect(c)
            if rw<rh: rw,rh=rh,rw; ang=ang-90
            if ang<-45: ang+=90
            if ang>45: ang-=90
            fill=np.zeros_like(ink); cv2.drawContours(fill,[c],-1,1,-1)
            inner=cv2.erode(fill,np.ones((15,15),np.uint8))
            gin=gray[inner>0]
            # body colour = median of interior pixels that are near-white-ish
            body=np.median(R[inner>0].reshape(-1,3),axis=0)[::-1].tolist()
            card=dict(bbox=[x+X0,y+Y0,w,h],center=[round(cx+X0,2),round(cy+Y0,2)],size=[round(rw,2),round(rh,2)],angle=round(ang,2),
                      p1=float(np.percentile(gin,0.5)), body_rgb_median=body)
    # red pixels (headline fill etc): strong red
    red=((r>180)&(g<150)&(r-g>70)).astype(np.uint8)
    n,lab,st,cen=cv2.connectedComponentsWithStats(red)
    comps=[[int(st[k,0]+X0),int(st[k,1]+Y0),int(st[k,2]),int(st[k,3]),int(st[k,4])] for k in range(1,n) if st[k,4]>30]
    res.append(dict(i=i,card=card,red=comps))
json.dump(res,open(os.path.join(OUT,'_card_pass1.json'),'w'))
