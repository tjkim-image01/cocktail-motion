"""Oz scale labels (tick + 'n oz', right of glass) and dashed target line inside the glass, per frame.
Levels: 1 oz yc=682, 2 oz yc=620, 3 oz yc=559.  Label region x XL[k]..605, y yc-16..yc+16 (XL = right of glass wall).
 grey label: non-red ink (gray<232, R-G<30) -> p1 gray (core darkness) -> alpha ~ (248-p1)/(248-P1_FULL)
 red label : red ink (R-G>50, R>150) bbox -> width/height (scale vs rest).
Dash: d(x)=mean(gray rows yc+-[4..6]) - mean(gray rows yc-1..yc+1), x 225..XL-6; dash cols d>12;
 periodicity = max normalised autocorrelation of d at lag 17..22; coverage; extents.  Output _oz.json"""
import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from ui_common import *
LV={1:682,2:620,3:559}; XL={1:484,2:489,3:492}
res=[]
for i,f in frames():
    F=f.astype(np.int16); g=(0.299*F[...,2]+0.587*F[...,1]+0.114*F[...,0])
    e=dict(i=i)
    for k,yc in LV.items():
        sl=(slice(yc-16,yc+17),slice(XL[k],605))
        G=g[sl]; R=F[sl][...,2]; Gg=F[sl][...,1]
        red=(R-Gg>50)&(R>150)
        grey=(G<232)&((R-Gg)<30)
        L=dict()
        L['grey_n']=int(grey.sum()); L['grey_p1']=round(float(np.percentile(G[grey],1)),1) if grey.sum()>15 else None
        L['red_n']=int(red.sum())
        if red.sum()>3:
            ys,xs=np.nonzero(red); L['red_bbox']=[int(xs.min()+XL[k]),int(ys.min()+yc-16),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)]
            px=F[sl][red]; L['red_rgb']=[int(v) for v in np.median(px[(px[:,2]-px[:,1])>np.percentile(px[:,2]-px[:,1],50)],axis=0)[::-1]]
        if grey.sum()>15:
            ys,xs=np.nonzero(grey); L['grey_bbox']=[int(xs.min()+XL[k]),int(ys.min()+yc-16),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)]
        x1=XL[k]-6
        top=g[yc-6:yc-3,225:x1].mean(0); bot=g[yc+4:yc+7,225:x1].mean(0); mid=g[yc-1:yc+2,225:x1].mean(0)
        ds=(top+bot)/2-mid; dash=ds>12
        v=ds-ds.mean(); den=float((v*v).mean())+1e-6
        per=[float((v[:-lag]*v[lag:]).mean())/den for lag in range(17,23)]
        xs=np.nonzero(dash)[0]+225
        L['dash']=dict(period_score=round(max(per),3),lag=17+int(np.argmax(per)),cov=round(float(dash.mean()),3),
                       contrast=round(float(np.median(ds[dash])) if dash.any() else 0.0,1),
                       x0=int(xs.min()) if len(xs) else None,x1=int(xs.max()) if len(xs) else None)
        e[str(k)]=L
    res.append(e)
json.dump(res,open(os.path.join(OUT,'_oz.json'),'w'))
