"""Boil displacement field on static ink (title + timeline, frames 640-880): amplitude per
axis and spatial correlation length, so a noise warp of the same size can be applied."""
import json, sys
import cv2, numpy as np
cap = cv2.VideoCapture(sys.argv[1]); G = []
while True:
    ok, f = cap.read()
    if not ok: break
    G.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
change = [f for f in range(641, 880) if int(f / 30 * 8) != int((f - 1) / 30 * 8)]
REG = [(240, 30, 860, 160), (110, 880, 980, 1010)]
dx, dy, corr = [], [], {d: [] for d in (4, 8, 16, 32, 64)}
for f in change:
    a, b = G[f - 1], G[f]
    fl = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 2, 7, 3, 5, 1.1, 0)
    for x0, y0, x1, y1 in REG:
        ink = a[y0:y1, x0:x1] < 110; F = fl[y0:y1, x0:x1]
        v = F[ink]; v = v[np.linalg.norm(v, axis=1) < 6]
        dx += list(v[:, 0]); dy += list(v[:, 1])
        for d in corr:
            m = ink[:, :-d] & ink[:, d:]
            p, q = F[:, :-d][m], F[:, d:][m]
            if len(p) > 30: corr[d].append(float(np.mean(np.sum(p * q, 1)) / np.sqrt(np.mean(np.sum(p * p, 1)) * np.mean(np.sum(q * q, 1)) + 1e-9)))
res = {'frames': len(change), 'std_dx': float(np.std(dx)), 'std_dy': float(np.std(dy)),
       'mean_abs': float(np.mean(np.hypot(dx, dy))), 'p95_abs': float(np.percentile(np.hypot(dx, dy), 95)),
       'correlation_by_px': {d: round(float(np.mean(v)), 3) for d, v in corr.items()}}
print(res); json.dump(res, open(sys.argv[2], 'w'), indent=1)
