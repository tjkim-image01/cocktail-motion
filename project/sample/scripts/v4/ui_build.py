"""Assemble tree002 v4 UI measurements into data.json (+ fits). Reads the _*.json passes in analysis-v4/ui.
Counter strings are visual readings of the crop sheets (see README); everything else is measured."""
import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
import json, os, math
import numpy as np
from ui_common import OUT
L=lambda n: json.load(open(os.path.join(OUT,n)))
card=L('_card.json'); hl=L('_headline.json'); prog=L('_progress.json'); tl=L('_timeline.json'); oz=L('_oz.json'); misc=L('_misc.json'); txt=L('_text.json')
N=900
ENTRIES=[108,180,330,480,630,735,810]   # frame N: card hidden, new headline alone
# ---------- counter readings (frame ranges inclusive, read visually from crop sheets) ----------
CNT=[(109,142,'0 / 3'),(143,152,'1 / 3'),(153,163,'2 / 3'),(164,179,'3 / 3'),
     (181,237,'0.0 / 1 oz'),(238,245,'0.1 / 1 oz'),(246,250,'0.2 / 1 oz'),(251,253,'0.3 / 1 oz'),(254,256,'0.4 / 1 oz'),
     (257,259,'0.5 / 1 oz'),(260,262,'0.6 / 1 oz'),(263,265,'0.7 / 1 oz'),(266,270,'0.8 / 1 oz'),(271,278,'0.9 / 1 oz'),(279,329,'1.0 / 1 oz'),
     (331,387,'0.0 / 1 oz'),(388,395,'0.1 / 1 oz'),(396,400,'0.2 / 1 oz'),(401,403,'0.3 / 1 oz'),(404,406,'0.4 / 1 oz'),(407,409,'0.5 / 1 oz'),
     (410,412,'0.6 / 1 oz'),(413,415,'0.7 / 1 oz'),(416,420,'0.8 / 1 oz'),(421,428,'0.9 / 1 oz'),(429,479,'1.0 / 1 oz'),
     (481,537,'0.0 / 1 oz'),(538,545,'0.1 / 1 oz'),(546,550,'0.2 / 1 oz'),(551,553,'0.3 / 1 oz'),(554,556,'0.4 / 1 oz'),(557,559,'0.5 / 1 oz'),
     (560,562,'0.6 / 1 oz'),(563,565,'0.7 / 1 oz'),(566,570,'0.8 / 1 oz'),(571,578,'0.9 / 1 oz'),(579,629,'1.0 / 1 oz'),
     (631,646,'20 s')]+[(647+4*j,650+4*j,f'{19-j} s') for j in range(19)]+[(723,734,'0 s'),(736,785,'twist…'),(786,809,'done!')]
counter=[None]*N
for a,b,s in CNT:
    for i in range(a,b+1): counter[i]=s
# ---------- card ----------
REST_W=float(np.median([c['w'] for c in card if c['visible'] and all(not(e<=c['i']<e+14) for e in ENTRIES)]))
REST_H=float(np.median([c['h'] for c in card if c['visible'] and all(not(e<=c['i']<e+14) for e in ENTRIES)]))
REST_A=float(np.median([c['ang_tb'] for c in card if c['visible'] and all(not(e<=c['i']<e+14) for e in ENTRIES)]))
REST_C=[float(np.median([c[k] for c in card if c['visible'] and all(not(e<=c['i']<e+14) for e in ENTRIES)])) for k in ('cx','cy')]
def alpha_ring(p): return max(0.0,min(1.0,(248-p)/(248-45)))
C=dict(visible=[],cx=[],cy=[],w=[],h=[],scale=[],angle_deg=[],rot_rel_deg=[],alpha_est=[],shadow_xmax=[],shadow_ymax=[])
for c in card:
    v=c['visible']; C['visible'].append(1 if v else 0)
    if not v:
        for k in C:
            if k!='visible': C[k].append(None)
        continue
    C['cx'].append(c['cx']);C['cy'].append(c['cy']);C['w'].append(c['w']);C['h'].append(c['h'])
    C['scale'].append(round((c['w']/REST_W+c['h']/REST_H)/2,4));C['angle_deg'].append(c['ang_tb']);C['rot_rel_deg'].append(round(c['ang_tb']-REST_A,3))
    C['alpha_est'].append(round(alpha_ring(c['ring_p30']),3))
    sh=c['shadow'] or {}; C['shadow_xmax'].append(sh.get('xmax')); C['shadow_ymax'].append(sh.get('ymax'))
# entry profile (k = frames after N); k=0 from headline (card invisible)
H=hl['frames']
prof=[]
for k in range(0,16):
    sc=[];ro=[];al=[];hs=[];hr=[]
    for e in ENTRIES:
        i=e+k
        if C['visible'][i]: sc.append(C['scale'][i]); ro.append(C['rot_rel_deg'][i]); al.append(C['alpha_est'][i])
        if H[i]['present'] and H[i]['score']>0.9: hs.append(H[i]['scale']); hr.append(H[i]['rot'])
    prof.append(dict(k=k,card_scale=round(float(np.mean(sc)),4) if sc else None,card_scale_sd=round(float(np.std(sc)),4) if sc else None,
                     card_rot_rel_deg=round(float(np.mean(ro)),3) if ro else None,card_alpha=round(float(np.mean(al)),3) if al else 0.0,
                     headline_scale=round(float(np.mean(hs)),4),headline_rot_deg=round(float(np.mean(hr)),3)))
# fit easeOutBack: s(k)=s0+(1-s0)*E((k-t0)/D), rot(k)=r0*(1-E)
def eob(u,c1):
    u=min(max(u,0.0),1.0); c3=c1+1; return 1+c3*(u-1)**3+c1*(u-1)**2
ks=np.arange(0,16)
target=np.array([prof[0]['headline_scale']]+[p['card_scale'] for p in prof[1:]])
best=None
for s0 in np.arange(0.86,0.94,0.005):
    for c1 in np.arange(1.2,2.6,0.05):
        for D in np.arange(9,16,0.25):
            for t0 in np.arange(-0.6,0.61,0.1):
                pred=np.array([s0+(1-s0)*eob((k-t0)/D,c1) for k in ks])
                err=float(((pred-target)**2).sum())
                if best is None or err<best[0]: best=(err,s0,c1,D,t0)
err,s0,c1,D,t0=best
E=np.array([eob((k-t0)/D,c1) for k in ks])
rot_t=np.array([prof[0]['headline_rot_deg']]+[p['card_rot_rel_deg'] for p in prof[1:]])
r0=float((rot_t*(1-E)).sum()/((1-E)**2).sum())
fit=dict(model='scale = s0 + (1-s0)*easeOutBack((k-t0)/D, c1); rot_rel = r0*(1-easeOutBack(...)); k = frames after N (headline-alone frame)',
         s0=round(float(s0),3),c1=round(float(c1),2),D_frames=round(float(D),2),t0_frames=round(float(t0),2),r0_deg=round(r0,2),
         rms_scale_err=round(math.sqrt(err/len(ks)),4),
         rot_rms_err_deg=round(float(np.sqrt(((r0*(1-E)-rot_t)**2).mean())),3),
         pred_scale=[round(float(s0+(1-s0)*e),4) for e in E],pred_rot=[round(float(r0*(1-e)),3) for e in E])
# ---------- headline ----------
HL=dict(present=[],word=[],scale=[],rot_deg=[],dx=[],dy=[],cx=[],cy=[],red_bbox=[],score=[])
for e in H:
    HL['present'].append(1 if e['present'] else 0)
    for k in ('word','scale','dx','dy','cx','cy','red_bbox','score'): HL[k].append(e.get(k) if e['present'] else None)
    HL['rot_deg'].append(e.get('rot') if e['present'] else None)
# ---------- progress ----------
P=dict(fill_x0=[],fill_x1=[],fill_w=[],fill_y0=[],fill_y1=[],counter=counter)
for e in prog:
    f=e['fill']
    for k in ('x0','x1','w','y0','y1'): P['fill_'+k].append(f[k] if f else None)
# ---------- timeline ----------
def nstate(n):
    if n['inner_red']>0.45: return 3
    if n['ring_dark']>0.2: return 2
    if n['ring_grey']>0.12: return 1
    return 0
T=dict(state=[],radius=[],label_rgb=[],ring_min_gray=[],check_white_px=[],seg_red_x1=[],seg_red_frac=[])
for e,m in zip(tl,misc):
    T['state'].append([nstate(n) for n in e['nodes']]); T['radius'].append([n['radius'] for n in e['nodes']])
    T['label_rgb'].append([n['label_rgb'] for n in e['nodes']]); T['ring_min_gray'].append([n['ring_min_gray'] for n in e['nodes']])
    T['check_white_px'].append(m['check_white']); T['seg_red_x1'].append([s['red_x1'] for s in e['segs']]); T['seg_red_frac'].append([s['red_frac'] for s in e['segs']])
# fix fade-in node 1: before ring dark appears it is 'empty-looking' while fading in as current
# state change events
tev=[]
for k in range(6):
    prev=0
    for i in range(N):
        s=T['state'][i][k]
        if s!=prev: tev.append(dict(frame=i,node=k+1,state=['none','empty','current','done'][s]))
        prev=s
# pulse fit for current nodes (global clock)
fr=[];rv=[]
for i in range(N):
    for k in range(6):
        if T['state'][i][k]==2 and T['radius'][i][k] and i>131:
            # skip first 2 frames after becoming current
            if all(T['state'][j][k]==2 for j in range(i-2,i+1)): fr.append(i); rv.append(T['radius'][i][k])
fr=np.array(fr,float); rv=np.array(rv,float)
bestp=None
for Pp in np.arange(26,40,0.02):
    X=np.vstack([np.ones_like(fr),np.sin(2*np.pi*fr/Pp),np.cos(2*np.pi*fr/Pp)]).T
    coef,res_,_,_=np.linalg.lstsq(X,rv,rcond=None); r=float(((X@coef-rv)**2).mean())
    if bestp is None or r<bestp[0]: bestp=(r,Pp,coef)
r,Pp,coef=bestp; amp=float(math.hypot(coef[1],coef[2])); ph=math.atan2(coef[2],coef[1])
# first max frame: sin(2pi f/P + ph)=1
fmax=((math.pi/2-ph)/(2*math.pi))*Pp
fmax=fmax%Pp
pulse=dict(model='radius(f) = mean + amp*sin(2*pi*f/P + phase)  (f = absolute frame; ring outer radius incl. stroke, px)',
           P_frames=round(float(Pp),2),P_seconds=round(float(Pp)/30,3),mean_px=round(float(coef[0]),2),amp_px=round(amp,2),phase_rad=round(ph,3),
           first_peak_frame=round(fmax,2),rms_px=round(math.sqrt(r),3),n=int(len(fr)))
# ---------- oz ----------
O={}
for k in '123':
    g=[];rb=[];st=[]
    for e in oz:
        Lk=e[k]; gp=Lk['grey_p1']; red=Lk.get('red_bbox')
        a=None
        if gp is not None and (red is None or Lk['red_n']<10): a=round(max(0,min(1,(248-gp)/(248-75))),3)
        g.append(a); rb.append(red)
    O[k]=dict(grey_alpha_est=g,red_bbox=rb)
# ---------- misc ----------
M=dict(title_red_bbox=[m.get('title_red_bbox') for m in misc],subtitle_bbox=[m.get('sub_bbox') for m in misc],subtitle_p1_gray=[m.get('sub_p1') for m in misc])
schema={
 'frame':'all per-frame arrays have 900 entries indexed by 0-based frame i (t=i/30 s); null = not present/not measurable',
 'coords':'pixels in the 1080x1080 frame, origin top-left, y down; angles in degrees, + = clockwise on screen',
 'card.visible':'1 if the card outline (white body + ink border) is detected',
 'card.cx/cy/w/h':'centre and size from straight-line fits to the OUTER edge of the ink border (top/bottom/left/right sides, corners excluded). Includes border stroke (~2.5px).',
 'card.scale':'mean of w/REST_W and h/REST_H',
 'card.angle_deg':'mean slope of top+bottom border fits; card.rot_rel_deg = angle - rest angle',
 'card.alpha_est':'opacity proxy from border darkness: (248 - p30 gray of border ring)/(248-45). ~1 at rest',
 'card.shadow_xmax/ymax':'outer extent (99.5 pct) of pink shadow pixels right of / below the card',
 'card.rest':'medians over non-transition frames',
 'card.entry_profile':'average over the 7 entries (N = '+str(ENTRIES)+'); k = frames after N. k=0: card invisible, headline alone',
 'card.entry_fit':'easeOutBack fit to entry profile (see model string)',
 'headline.*':'big red word. scale/rot_deg/dx/dy = similarity transform of this step\'s rest template (frame N+30) matched on a redness map (R-G-40)/100; dx,dy = shift of template centre; red_bbox = bbox of strong red fill (x,y,w,h); score = TM_CCOEFF_NORMED',
 'progress.fill_*':'red fill bbox inside the track (x 672..922, y 722..746); w in px; null = empty',
 'progress.counter':'counter text right of the bar, read visually from crops (null = no card / transition frame N)',
 'timeline.state':'per node [6]: 0 none (not yet faded in), 1 empty (grey ring+grey number), 2 current (black ring, red number, red label), 3 done (red disc + white check)',
 'timeline.radius':'per node: median over 48 rays of farthest ink (gray<225) within 32px of centre (150+156k, 927); px',
 'timeline.label_rgb':'per node: median RGB of the darkest 30% label ink',
 'timeline.ring_min_gray':'2nd percentile gray in annulus r17-26 (fade-in proxy)',
 'timeline.check_white_px':'white px inside a done node (check-mark draw-on); null if node not red',
 'timeline.seg_red_x1':'per segment k->k+1: rightmost red column of the connecting line within x (cx_k+30 .. cx_k+126); null = no red',
 'timeline.events':'frames where node state code changes',
 'timeline.pulse_fit':'sine fit of current-node radius (global clock)',
 'oz.levels':'1 oz yc=682, 2 oz yc=620, 3 oz yc=559',
 'oz.N.grey_alpha_est':'pending (grey) label opacity proxy (248 - p1 gray)/(248-75); dashed target line pulses with it; null = no grey label',
 'oz.N.red_bbox':'bbox (x,y,w,h) of the red (reached) tick+label; null = not shown',
 'misc.title_red_bbox':'bbox of red title ink above y=175',
 'misc.subtitle_bbox/p1':'bbox / darkest gray of grey subtitle ink (y 165..235)',
 'text_rows':'per card state: rows of ink in the median rest image: y0,y1,x0,x1, baseline (lowest dense row), top_dense, ink_height, colours',
}
data=dict(schema=schema,meta=dict(video='01_레퍼런스/original.mp4',fps=30,frames=N,size=[1080,1080]),
          entries_N=ENTRIES,
          card=dict(rest=dict(w=round(REST_W,2),h=round(REST_H,2),angle_deg=round(REST_A,3),cx=round(REST_C[0],2),cy=round(REST_C[1],2)),
                    entry_profile=prof,entry_fit=fit,per_frame=C),
          headline=dict(templates=hl['templates'],per_frame=HL),
          progress=dict(track=dict(x0=677.5,x1=916,y_top_outer=725.5,y_bot_outer=742,stroke_px=2,end_radius_px=8,fill_x0=680,fill_rest_full_w=234),per_frame=P),
          timeline=dict(node_cx=[150+156*k for k in range(6)],node_cy=927,events=tev,pulse_fit=pulse,per_frame=T),
          oz=dict(levels={'1':682,'2':620,'3':559},per_frame=O),
          misc=M,text_rows=txt)
json.dump(data,open(os.path.join(OUT,'data.json'),'w'),separators=(',',':'))
print('fit',fit); print('pulse',pulse); print('rest',data['card']['rest'])
for p in prof: print(p)
print(tev)
