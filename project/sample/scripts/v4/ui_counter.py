"""Counter text (right of progress bar) per frame.
1) split timeline into segments at every frame whose counter crop changes (mean abs diff > 0.5: boil or content).
2) cluster segment crops (Gaussian-blurred ink, best NCC over +-3px shifts); a new cluster when NCC < THR.
3) sheet of cluster exemplars (read visually) -> labels in COUNTER_LABELS (filled after reading) -> per-frame string.
Outputs _counter_clusters.json, counter_clusters.png"""
import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from ui_common import *
THR=0.955
crops={};prev=None;cuts=[0]
for i,f in frames():
    c=cv2.cvtColor(f[716:754,922:1042],cv2.COLOR_BGR2GRAY)
    if prev is not None and np.abs(c.astype(int)-prev).mean()>0.5: cuts.append(i)
    prev=c.astype(int); crops[i]=c
cuts.append(900)
segs=[(cuts[k],cuts[k+1]-1) for k in range(len(cuts)-1)]
def feat(c):
    ink=np.clip((235-c.astype(np.float32))/150,0,1)
    return cv2.GaussianBlur(ink,(0,0),0.9)
def ncc(a,b):
    best=-1
    for dy in range(-3,4):
        for dx in range(-3,4):
            bb=np.roll(np.roll(b,dy,0),dx,1)
            A=a[4:-4,4:-4];B=bb[4:-4,4:-4]
            if A.sum()<1 and B.sum()<1: return 1.0
            na=np.linalg.norm(A);nb=np.linalg.norm(B)
            if na<1e-6 or nb<1e-6: continue
            best=max(best,float((A*B).sum()/(na*nb)))
    return best
clusters=[]  # [feat, exemplar_frame, [segs]]
assign=[]
for a,b in segs:
    m=(a+b)//2; F=feat(crops[m][:, :46])
    if F.sum()<5: key='EMPTY'
    sc=[(ncc(F,c[0]),k) for k,c in enumerate(clusters)]
    if F.sum()<5:
        k=-1
    elif sc and max(sc)[0]>=THR:
        k=max(sc)[1]; clusters[k][2].append((a,b))
    else:
        clusters.append([F,m,[(a,b)]]); k=len(clusters)-1
    assign.append((a,b,k))
json.dump(dict(segments=assign,clusters=[dict(k=k,exemplar=c[1],segs=c[2]) for k,c in enumerate(clusters)]),open(os.path.join(OUT,'_counter_clusters.json'),'w'))
sheet([crops[c[1]] for c in clusters],[f'c{k} f{c[1]}' for k,c in enumerate(clusters)],cols=6,scale=1.5,path=os.path.join(OUT,'_counter_clusters.png'))
print(len(segs),'segments',len(clusters),'clusters')
for k,c in enumerate(clusters): print(k,c[1],c[2][0],c[2][-1],len(c[2]))
