"""Verification images for the UI measurements (writes verify_*.jpg into analysis-v4/ui)."""
import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from ui_common import *
D=json.load(open(os.path.join(OUT,'data.json')))
C=D['card']['per_frame']; H=D['headline']['per_frame']; P=D['progress']['per_frame']; T=D['timeline']['per_frame']; O=D['oz']['per_frame']
rest=D['card']['rest']
def draw_card(img,i,ox=0,oy=0,col=(0,200,0)):
    if not C['visible'][i]: return
    cx,cy,w,h,a=C['cx'][i]-ox,C['cy'][i]-oy,C['w'][i],C['h'][i],C['angle_deg'][i]
    box=cv2.boxPoints(((cx,cy),(w,h),a)).astype(np.int32); cv2.polylines(img,[box],True,col,1)
def draw_hl(img,i,ox=0,oy=0):
    if H['present'][i] and H['red_bbox'][i]:
        x,y,w,h=H['red_bbox'][i]; cv2.rectangle(img,(x-ox,y-oy),(x+w-ox,y+h-oy),(255,0,255),1)
want=set(range(178,195))|{150,260,420,560,700,790,880}|set(range(296,310))|set(range(284,301))|set(range(586,601))
F=load(sorted(want))
# 1 card entry
ims=[];labs=[]
for i in range(178,195):
    im=F[i][470:800,600:1080].copy(); draw_card(im,i,600,470); draw_hl(im,i,600,470)
    ims.append(im); labs.append(f"{i} s={C['scale'][i]} r={C['rot_rel_deg'][i]} a={C['alpha_est'][i]} | hl s={H['scale'][i]} r={H['rot_deg'][i]}")
sheet(ims,labs,cols=3,scale=0.75,path=os.path.join(OUT,'verify_card_entry_178-194.jpg'))
# 2 full-frame overlays
cols={0:(180,180,180),1:(160,160,160),2:(0,0,0),3:(0,0,255)}
ims=[];labs=[]
for i in (150,260,420,560,700,790,880):
    im=F[i].copy(); draw_card(im,i); draw_hl(im,i)
    if P['fill_x0'][i] is not None: cv2.rectangle(im,(P['fill_x0'][i],P['fill_y0'][i]),(P['fill_x1'][i],P['fill_y1'][i]),(255,128,0),1)
    for k in range(6):
        r=T['radius'][i][k]
        if r: cv2.circle(im,(150+156*k,927),int(round(r)),(0,255,0) if T['state'][i][k]==2 else (255,0,0) if T['state'][i][k]==3 else (0,200,200),1)
    for lv in '123':
        rb=O[lv]['red_bbox'][i]
        if rb: cv2.rectangle(im,(rb[0],rb[1]),(rb[0]+rb[2],rb[1]+rb[3]),(0,140,255),1)
    cv2.putText(im,f"f{i} counter={P['counter'][i]} states={T['state'][i]}",(10,1060),cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,0,0),2)
    ims.append(im); labs.append(str(i))
sheet(ims,labs,cols=4,scale=0.45,path=os.path.join(OUT,'verify_overlay_frames.jpg'))
# 3 timeline done pop (node 2, D=298)
ims=[F[i][927-40:927+70,306-60:306+90] for i in range(296,310)]
sheet(ims,[f"{i} r={T['radius'][i][1]} chk={T['check_white_px'][i][1]} seg2x1={T['seg_red_x1'][i][1]}" for i in range(296,310)],cols=7,scale=2.0,path=os.path.join(OUT,'verify_timeline_done_node2.jpg'))
# 4 oz label completion
ims=[F[i][650:715,200:600] for i in range(284,301)]+[F[i][530:595,200:600] for i in range(586,601)]
labs=[f"{i} L1 grey_a={O['1']['grey_alpha_est'][i]} red={O['1']['red_bbox'][i]}" for i in range(284,301)]+[f"{i} L3 grey_a={O['3']['grey_alpha_est'][i]} red={O['3']['red_bbox'][i]}" for i in range(586,601)]
sheet(ims,labs,cols=4,scale=1.0,path=os.path.join(OUT,'verify_oz_completion.jpg'))
# 5 counter readings: first frame of each reading segment with the string assigned
cnt=P['counter']; segs=[];s=None
for i in range(900):
    if cnt[i]!=(segs[-1][2] if segs else None) or (segs and i!=segs[-1][1]+1):
        if cnt[i] is not None: segs.append([i,i,cnt[i]])
    elif cnt[i] is not None: segs[-1][1]=i
G=load(sorted({a for a,b,s in segs}))
sheet([G[a][716:752,922:1042] for a,b,s in segs],[f"{a}-{b} '{s}'" for a,b,s in segs],cols=6,scale=1.5,path=os.path.join(OUT,'verify_counter_readings.jpg'))
