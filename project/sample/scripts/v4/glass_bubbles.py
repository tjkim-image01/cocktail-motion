"""Bubbles / splash drops near the pour entry, frames 200-620.
Gin (clear): hollow grey rings = small closed components of the black-hat line mask (G channel > 22),
  bbox 5-15 px, near square, not on an ice box / glass line / surface arc.
Campari / vermouth: filled red drops = R-G > 45 & R-B > 25 blobs (area 4-160, bbox <= 16) lying above the
  liquid's back arc (in the glass-tint area) and off the ice boxes; long components (streams) are dropped.
Output per frame: [x, y, r, kind, hex].
"""
from glass_common import *

A, B = 200, 620
fr = load(A, B)
cap = cv2.VideoCapture(str(VIDEO)); cap.set(cv2.CAP_PROP_POS_FRAMES, 119); _, g119 = cap.read(); g119 = g119[Y0:Y1, X0:X1]
ice = {n: {r[0]: r for r in rows} for n, rows in json.loads((OUT / 'ice_raw.json').read_text())['tracks'].items()}
liq = {r[0]: r for r in json.loads((OUT / 'liquid_raw.json').read_text())['rows']}
K = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
def bh(f): return cv2.morphologyEx(f[:, :, 1], cv2.MORPH_BLACKHAT, K)
base = cv2.dilate((bh(g119) > 22).astype(np.uint8), np.ones((5, 5), np.uint8))
def half_w(y): return 122.5 - 0.075 * (y - 580)
def icem(i, pad):
    m = np.zeros(g119.shape[:2], np.uint8)
    for t in ice.values():
        if i in t:
            _, x, y, a, s, _ = t[i]; S = 71 * s + 2 * pad
            cv2.fillPoly(m, [cv2.boxPoints(((x - X0, y - Y0), (S, S), a)).astype(np.int32)], 1)
    return m
out = {}
yy, xx = np.mgrid[0:g119.shape[0], 0:g119.shape[1]]; XX = xx + X0; YY = yy + Y0
inside = (XX > 232) & (XX < 470) & (YY > 470) & (YY < 760)
for i in range(A, B + 1):
    f = fr[i]; im = icem(i, 4); found = []
    r = liq.get(i)
    surf_ok = r is not None and len(r) > 2 and r[3] is not None and r[3] > 0.5
    # rings
    ln = ((bh(f) > 22) & (base == 0) & (im == 0) & inside).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(ln)
    for k in range(1, n):
        x, y, w, h, a = st[k]
        if not (5 <= w <= 15 and 5 <= h <= 15 and a >= 8 and abs(w - h) <= 4): continue
        if a > 0.8 * w * h: continue                               # filled -> not a ring
        cx, cy = cen[k][0] + X0, cen[k][1] + Y0
        found.append([round(float(cx), 1), round(float(cy), 1), round((w + h) / 4, 1), 'ring', hexc(np.median(f[lab == k], 0))])
    # red drops above the back arc
    fi = f.astype(int); red = ((fi[:, :, 2] - fi[:, :, 1] > 45) & (fi[:, :, 2] - fi[:, :, 0] > 25) & (im == 0)).astype(np.uint8)
    red[YY < 380] = 0; red[(XX < 225) | (XX > 480)] = 0
    if surf_ok:
        yc, b = r[1], r[2]; u = np.clip((XX - 349) / half_w(yc), -1, 1)
        red[(YY > yc - b * np.sqrt(1 - u * u) - 2) & (np.abs(u) < 1)] = 0
        red[YY > yc + b] = 0
    n, lab, st, cen = cv2.connectedComponentsWithStats(red)
    for k in range(1, n):
        x, y, w, h, a = st[k]
        if not (4 <= a <= 160 and w <= 16 and h <= 16 and max(w, h) <= 2.2 * min(w, h) + 1): continue
        found.append([round(float(cen[k][0] + X0), 1), round(float(cen[k][1] + Y0), 1), round(float(np.sqrt(a / np.pi)), 1), 'drop', hexc(np.median(f[lab == k], 0))])
    if found: out[i] = found
print('frames with dots', len(out))
for i in sorted(out):
    if i % 3 == 0: print(i, out[i])
save_json('bubbles_raw.json', {'columns': ['x', 'y', 'r', 'kind', 'hex'], 'frames': {str(k): v for k, v in out.items()}})
