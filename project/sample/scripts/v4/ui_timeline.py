"""Timeline (6 nodes at x=150+156k, y=927) per frame.
Per node: ring dark/grey coverage (annulus r17-26), inner red fraction (r<15), white-on-red fraction (check mark),
outer radius (median over 48 rays of farthest ink<=32px), label ink colour. Per segment k->k+1: red / grey column
fractions along y 921..933 and red extent. Output _timeline.json"""
import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from ui_common import *
YC=927
yy,xx=np.mgrid[-34:35,-34:35]; rr=np.hypot(xx,yy)
ann=(rr>=17)&(rr<=26); inn=rr<14
angs=np.linspace(0,2*np.pi,48,endpoint=False)
res=[]
for i,f in frames():
    F=f.astype(np.int16); b,g,r=F[...,0],F[...,1],F[...,2]
    gray=(0.299*r+0.587*g+0.114*b)
    sat=np.max(F,2)-np.min(F,2)
    nodes=[];segs=[]
    for k in range(6):
        cx=150+156*k
        sl=(slice(YC-34,YC+35),slice(cx-34,cx+35))
        G=gray[sl];R=r[sl];Gg=g[sl];S=sat[sl]
        red=(R-Gg>60)&(R>170)
        dark=(G<110)
        grey=(G>=110)&(G<225)&(S<25)
        white_in_red=(G>235)&inn
        ink=(G<225)
        # radius: farthest ink along rays within 32
        rad=[]
        for a in angs:
            ts=np.arange(10,33,0.5); px=(34+ts*np.cos(a)).round().astype(int); py=(34+ts*np.sin(a)).round().astype(int)
            hit=np.nonzero(ink[py,px])[0]
            if len(hit): rad.append(ts[hit.max()])
        lab=(slice(963,995),slice(cx-62,cx+62))
        LG=gray[lab]; LI=LG<215
        lc=None
        if LI.sum()>15:
            px=F[lab][LG<np.percentile(LG[LI],30)]
            lc=[int(v) for v in np.median(px,axis=0)[::-1]]
        nodes.append(dict(ring_dark=round(float(dark[ann].mean()),3),ring_grey=round(float(grey[ann].mean()),3),
                          inner_red=round(float(red[inn].mean()),3),inner_dark=round(float(dark[inn].mean()),3),
                          inner_white=round(float(white_in_red.sum()/max(1,inn.sum())),3),
                          ring_min_gray=round(float(np.percentile(G[ann],2)),1),
                          radius=round(float(np.median(rad)),2) if rad else None,
                          label_ink=int(LI.sum()),label_rgb=lc))
        if k<5:
            x0=cx+30;x1=cx+156-30
            band=(slice(919,936),slice(x0,x1))
            Rb=r[band];Gb=g[band];Gy=gray[band];Sb=sat[band]
            redc=((Rb-Gb>50)&(Rb>180)).any(0); greyc=((Gy<232)&(Sb<20)).any(0)
            rx=np.nonzero(redc)[0]
            segs.append(dict(red_frac=round(float(redc.mean()),3),grey_frac=round(float(greyc.mean()),3),
                             red_x0=int(rx.min()+x0) if len(rx) else None,red_x1=int(rx.max()+x0) if len(rx) else None))
    res.append(dict(i=i,nodes=nodes,segs=segs))
json.dump(res,open(os.path.join(OUT,'_timeline.json'),'w'))
