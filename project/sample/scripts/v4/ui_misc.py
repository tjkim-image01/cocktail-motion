"""Misc UI per frame: title (red ink, y<170) and subtitle (grey ink, y 170..225) bboxes / darkness;
check-mark white pixels inside done nodes (light px within r<15 surrounded by red). Output _misc.json"""
import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from ui_common import *
yy,xx=np.mgrid[-34:35,-34:35]; rr=np.hypot(xx,yy)
res=[]
for i,f in frames():
    F=f.astype(np.int16); b,g,r=F[...,0],F[...,1],F[...,2]
    gray=(0.299*r+0.587*g+0.114*b)
    e=dict(i=i)
    T=(r[0:175]-g[0:175]>60)&(r[0:175]>150)
    if T.sum()>50:
        ys,xs=np.nonzero(T); e['title_red_bbox']=[int(xs.min()),int(ys.min()),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)]; e['title_red_n']=int(T.sum())
    S=(gray[165:235,250:830]<200)&((r[165:235,250:830]-g[165:235,250:830])<30)
    if S.sum()>30:
        ys,xs=np.nonzero(S); e['sub_bbox']=[int(xs.min()+250),int(ys.min()+165),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)]
        e['sub_p1']=round(float(np.percentile(gray[165:235,250:830][S],1)),1); e['sub_n']=int(S.sum())
    chk=[]
    for k in range(6):
        cx=150+156*k
        G=gray[927-34:927+35,cx-34:cx+35]; R=r[927-34:927+35,cx-34:cx+35]; Gg=g[927-34:927+35,cx-34:cx+35]
        red=((R-Gg>60)&(R>170)).astype(np.uint8)
        if red[rr<14].mean()<0.4: chk.append(None); continue
        hull=cv2.morphologyEx(red,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8))
        wh=(G>215)&(hull>0)&(red==0)&(rr<17)
        chk.append(int(wh.sum()))
    e['check_white']=chk
    res.append(e)
json.dump(res,open(os.path.join(OUT,'_misc.json'),'w'))
