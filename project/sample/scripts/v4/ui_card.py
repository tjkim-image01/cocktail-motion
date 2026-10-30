"""Card geometry per frame (tree002 v4 UI measurement).
For each frame: filled outer ink contour of the card -> side-line fits (top/bottom/left/right)
=> width, height, center, rotation; opacity proxies; pink shadow extents.
Output: _card.json (list per frame)."""
import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from ui_common import *
X0,Y0,X1,Y1 = 560,430,1080,830

def fitline(xs, ys):
    A=np.vstack([xs,np.ones_like(xs)]).T
    m,c=np.linalg.lstsq(A,ys,rcond=None)[0]
    return m,c

res=[]
for i,f in frames():
    R=f[Y0:Y1,X0:X1].astype(np.int16)
    b,g,r=R[...,0],R[...,1],R[...,2]
    gray=(0.299*r+0.587*g+0.114*b)
    ink=(248-gray>45).astype(np.uint8)
    cl=cv2.morphologyEx(ink,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7)))
    cnts,_=cv2.findContours(cl,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    out=dict(i=i,visible=False)
    if cnts:
        c=max(cnts,key=cv2.contourArea)
        x,y,w,h=cv2.boundingRect(c)
        if w>250 and h>150:
            fill=np.zeros_like(ink); cv2.drawContours(fill,[c],-1,1,-1)
            cols=np.arange(x+int(0.15*w), x+int(0.85*w))
            top=np.array([np.argmax(fill[:,cc]>0) for cc in cols],float)
            bot=np.array([fill.shape[0]-1-np.argmax(fill[::-1,cc]>0) for cc in cols],float)
            rows=np.arange(y+int(0.2*h), y+int(0.8*h))
            lef=np.array([np.argmax(fill[rr,:]>0) for rr in rows],float)
            rig=np.array([fill.shape[1]-1-np.argmax(fill[rr,::-1]>0) for rr in rows],float)
            mt,ct=fitline(cols,top); mb,cb=fitline(cols,bot)
            ml,cl_=fitline(rows,lef); mr,cr=fitline(rows,rig)
            cx=(x+w/2); cy=(y+h/2)
            topy=mt*cx+ct; boty=mb*cx+cb; lefx=ml*cy+cl_; rigx=mr*cy+cr
            ang_tb=np.degrees(np.arctan((mt+mb)/2)); ang_lr=-np.degrees(np.arctan((ml+mr)/2))
            ring=fill-cv2.erode(fill,np.ones((7,7),np.uint8))
            ringg=gray[ring>0]
            inner=cv2.erode(fill,np.ones((21,21),np.uint8))
            bodyR=R[inner>0].reshape(-1,3)
            gi=gray[inner>0]
            body=np.median(bodyR[gi>200],axis=0)[::-1]
            # pink shadow outside the card fill
            pink=((r-g>15)&(g>165)&(r>215)).astype(np.uint8)
            pink[cv2.dilate(fill,np.ones((3,3),np.uint8))>0]=0
            pink=cv2.morphologyEx(pink,cv2.MORPH_OPEN,np.ones((2,2),np.uint8))
            ys_,xs_=np.nonzero(pink)
            sh=None
            if len(xs_)>200:
                # right strip: pixels right of card -> x max ; bottom strip -> y max; shadow left = min x among bottom-strip pixels
                rs=xs_>rigx; bs=ys_>boty
                sh=dict(xmax=float(np.percentile(xs_[rs],99.5))+X0 if rs.sum()>20 else None,
                        ymax=float(np.percentile(ys_[bs],99.5))+Y0 if bs.sum()>20 else None,
                        xmin_bottom=float(np.percentile(xs_[bs],0.5))+X0 if bs.sum()>20 else None,
                        ymin_right=float(np.percentile(ys_[rs],0.5))+Y0 if rs.sum()>20 else None,
                        npx=int(len(xs_)))
            out=dict(i=i,visible=True,bbox=[x+X0,y+Y0,w,h],
                     left=round(lefx+X0,2),right=round(rigx+X0,2),top=round(topy+Y0,2),bottom=round(boty+Y0,2),
                     w=round(rigx-lefx,2),h=round(boty-topy,2),cx=round((lefx+rigx)/2+X0,2),cy=round((topy+boty)/2+Y0,2),
                     ang_tb=round(float(ang_tb),3),ang_lr=round(float(ang_lr),3),
                     slopes=[round(float(v),5) for v in (mt,mb,ml,mr)],
                     ring_p30=round(float(np.percentile(ringg,30)),1),
                     body_rgb=[round(float(v),1) for v in body],
                     text_p1=round(float(np.percentile(gi,0.5)),1),
                     shadow=sh)
    res.append(out)
json.dump(res,open(os.path.join(OUT,'_card.json'),'w'))
