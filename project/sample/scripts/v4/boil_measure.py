"""Line boil of the reference: when it changes and how far/how smoothly ink moves.

Change frames: ink-pixel difference between consecutive frames inside static regions
(title, timeline).  Displacement: dense Farneback flow between the two boil states,
read only on ink pixels."""
import json, sys
import cv2, numpy as np
cap = cv2.VideoCapture(sys.argv[1]); G = []
while True:
    ok, f = cap.read()
    if not ok: break
    G.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
REG = {'title': (240, 40, 860, 150), 'timeline': (110, 890, 980, 1000)}
changes = []
for i in range(1, len(G)):
    x0, y0, x1, y1 = REG['title']
    a, b = G[i - 1][y0:y1, x0:x1].astype(int), G[i][y0:y1, x0:x1].astype(int)
    changes.append(int((np.abs(a - b) > 40).sum()))
ch = np.array(changes); thr = max(40, np.percentile(ch, 50) * 4)
boil = [i + 1 for i, v in enumerate(ch) if v > thr]
gaps = np.diff(boil)
mags, smooth = [], []
for i in boil[40:120]:
    a, b = G[i - 1], G[i]
    flow = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 9, 3, 5, 1.1, 0)
    ink = (a < 120)
    for name, (x0, y0, x1, y1) in REG.items():
        m = ink[y0:y1, x0:x1]; fl = flow[y0:y1, x0:x1][m]
        if len(fl) < 50: continue
        mags.append(np.linalg.norm(fl, axis=1))
        # spatial correlation: neighbouring ink pixels 8px apart move alike?
        f8 = flow[y0:y1, x0 + 8:x1 + 8][m]
        smooth.append(np.mean(np.sum(fl * f8, 1)) / (np.mean(np.sum(fl * fl, 1)) + 1e-6))
mag = np.concatenate(mags)
res = {'changeFrames': boil, 'periodFrames': {'median': float(np.median(gaps)), 'mean': float(np.mean(gaps)),
       'counts': {int(k): int(v) for k, v in zip(*np.unique(gaps, return_counts=True))}},
       'firstChange': boil[0], 'displacementPx': {'median': float(np.median(mag)), 'p90': float(np.percentile(mag, 90)), 'max': float(mag.max())},
       'correlation8px': float(np.mean(smooth))}
json.dump(res, open(sys.argv[2], 'w'), indent=1)
print({k: v for k, v in res.items() if k != 'changeFrames'}, 'first 20', boil[:20])
