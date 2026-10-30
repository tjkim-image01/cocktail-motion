"""Finale rays/dashes around the glass, frames 800-899.
Candidates = saturated pink/red or orange pixels (HSV s > 60, hue <= 30 or >= 160, v > 120) that differ
from frame 800 (|diff| > 40) and lie outside the glass (outline polygon dilated), the peel and the oz
labels (static, compared with frame 800).  Pale fading-in rays are caught with a lower saturation
threshold (s > 25) when |diff| > 25.  Each elongated component -> segment (PCA end points, width =
area/length, median colour).  Segments are linked across frames by nearest midpoint -> ray ids.
"""
from glass_common import *

A, B, BASEF = 800, 899, 800
cap = cv2.VideoCapture(str(VIDEO)); fr = {}; i = 0
while i <= B:
    ok, f = cap.read()
    if not ok: break
    if i >= A: fr[i] = f.copy()
    i += 1
pose = {r[0]: r for r in json.loads((OUT / 'glass_pose_raw.json').read_text())['rows']}
peel = {r[0]: r for r in json.loads((OUT / 'peel_raw.json').read_text())['rows'] if r[1] is not None}
# glass silhouette (frame 119 outline filled) for exclusion
cap = cv2.VideoCapture(str(VIDEO)); cap.set(cv2.CAP_PROP_POS_FRAMES, 119); _, g119 = cap.read()
ink = (g119.max(2) < 110).astype(np.uint8); ink[:400] = 0; ink[830:] = 0; ink[:, :180] = 0; ink[:, 530:] = 0
cnts, _ = cv2.findContours(cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
hull = cv2.convexHull(np.vstack(cnts))
def glass_mask(i):
    _, cx, cy, sx, sy, _ = pose[i]; cx0, cy0 = 352.5, 617.5
    h = hull.reshape(-1, 2).astype(float); h[:, 0] = cx + sx * (h[:, 0] - cx0); h[:, 1] = cy + sy * (h[:, 1] - cy0)
    m = np.zeros((1080, 1080), np.uint8); cv2.fillPoly(m, [h.astype(np.int32)], 1); return cv2.dilate(m, np.ones((9, 9), np.uint8))
base = fr[BASEF].astype(int)
out = {}
for i in range(A, B + 1):
    f = fr[i]; h = cv2.cvtColor(f, cv2.COLOR_BGR2HSV); d = np.abs(f.astype(int) - base).sum(2)
    hue = h[:, :, 0]; col = (hue <= 30) | (hue >= 160)
    c = col & (h[:, :, 2] > 120) & (((h[:, :, 1] > 60) & (d > 40)) | ((h[:, :, 1] > 25) & (d > 25)))
    c = c.astype(np.uint8); c[:300] = 0; c[880:] = 0; c[:, :60] = 0; c[:, 615:] = 0
    c[glass_mask(i) > 0] = 0
    o = ((hue >= 8) & (hue <= 28) & (h[:, :, 1] > 110) & (h[:, :, 2] > 150)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.morphologyEx(o, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)))
    if n > 1:
        k = 1 + int(np.argmax(st[1:, 4]))
        if st[k, 4] > 2000: c[cv2.dilate((lab == k).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0] = 0
    c = cv2.morphologyEx(c, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(c); segs = []
    for k in range(1, n):
        if st[k, 4] < 12: continue
        ys, xs = np.nonzero(lab == k); P = np.stack([xs, ys], 1).astype(float); m = P.mean(0)
        u, s, vt = np.linalg.svd(P - m, full_matrices=False); dv = vt[0]; pr = (P - m) @ dv
        L = float(np.ptp(pr)) + 1
        if L < 6 or s[0] < 1.8 * (s[1] + 1e-6): continue
        a, b = m + dv * pr.min(), m + dv * pr.max()
        if a[1] > b[1]: a, b = b, a
        colr = np.median(f[lab == k], 0); sat = float(np.median(h[:, :, 1][lab == k]))
        segs.append([round(float(a[0]), 1), round(float(a[1]), 1), round(float(b[0]), 1), round(float(b[1]), 1),
                     round(float(st[k, 4] / L), 1), hexc(colr), int(sat)])
    out[i] = segs
# link into rays by nearest midpoint (<= 18 px) to the previous frame's rays
rays = []; prev = []
for i in range(A, B + 1):
    cur = []
    for s in out[i]:
        mx, my = (s[0] + s[2]) / 2, (s[1] + s[3]) / 2
        best = None
        for rid, (px, py) in prev:
            dd = np.hypot(mx - px, my - py)
            if dd < 18 and (best is None or dd < best[0]): best = (dd, rid)
        if best is None:
            rid = len(rays); rays.append({'id': rid, 'frames': []})
        else: rid = best[1]
        rays[rid]['frames'].append([i] + s); cur.append((rid, (mx, my)))
    # keep rays alive for 2 frames of misses
    alive = {r for r, _ in cur}
    prev = cur + [(rid, p) for rid, p in prev if rid not in alive and rays[rid]['frames'][-1][0] >= i - 2]
rays = [r for r in rays if len(r['frames']) >= 3]
for r in rays:
    fs = r['frames']; L = [np.hypot(x[3] - x[1], x[4] - x[2]) for x in fs]
    print(r['id'], 'frames', fs[0][0], '-', fs[-1][0], 'n', len(fs), 'mid', round((fs[-1][1] + fs[-1][3]) / 2), round((fs[-1][2] + fs[-1][4]) / 2),
          'len min/med/max', round(min(L)), round(float(np.median(L))), round(max(L)), 'w', np.median([x[5] for x in fs]), fs[len(fs) // 2][6])
save_json('rays_raw.json', {'columns': ['frame', 'x1', 'y1', 'x2', 'y2', 'width', 'hex', 'satMedian'], 'perFrame': {str(k): v for k, v in out.items()}, 'rays': rays})
