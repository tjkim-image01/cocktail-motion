"""Orange peel + spritz dots, frames 736-899.
Peel mask = orange pixels (HSV h 8-28, s > 110, v > 150) closed 5x5, largest component, plus its dark
outline (ink within 4px).  Per frame: centroid, area, bbox, principal-axis angle, and a rotated /
anisotropically scaled template match against the rest-pose peel (frame 830) to give
pose (x, y, angle, sx, sy) + score; low score = shape not a rigid copy of the rest pose.
Spritz dots = small orange/yellow blobs outside the peel (area 3-400), centre, radius, colour.
Crops of every peel frame are saved to peel_frames.png (contact sheet) for redrawing key shapes.
"""
from glass_common import *

A, B, REF = 736, 899, 830
cap = cv2.VideoCapture(str(VIDEO)); fr = {}; i = 0
PX0, PX1, PY0, PY1 = 150, 760, 250, 620
while i <= B:
    ok, f = cap.read()
    if not ok: break
    if i >= A: fr[i] = f[PY0:PY1, PX0:PX1].copy()
    i += 1
bg = fr[A].copy()
def orange(f):
    h = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    return ((h[:, :, 0] >= 8) & (h[:, :, 0] <= 28) & (h[:, :, 1] > 110) & (h[:, :, 2] > 150)).astype(np.uint8)
def peel_mask(f):
    o = orange(f); oc = cv2.morphologyEx(o, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(oc)
    if n < 2: return None, o
    k = 1 + int(np.argmax(st[1:, 4]))
    if st[k, 4] < 300: return None, o
    body = (lab == k).astype(np.uint8)
    ink = (f.max(2) < 110).astype(np.uint8)
    full = cv2.morphologyEx(body | (ink & cv2.dilate(body, np.ones((9, 9), np.uint8))), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return full, o

# reference template (rest pose)
refm, _ = peel_mask(fr[REF])
ys, xs = np.nonzero(refm); rc = np.array([xs.mean(), ys.mean()])
x0, x1, y0, y1 = xs.min() - 30, xs.max() + 31, ys.min() - 30, ys.max() + 31
S = int(max(x1 - x0, y1 - y0) * 1.5) | 1
canvas = np.zeros((S, S), np.float32)
ox, oy = int(S / 2 - rc[0]), int(S / 2 - rc[1])
canvas[ys + oy, xs + ox] = 1
canvas = cv2.GaussianBlur(canvas, (0, 0), 1.5)
cache = {}
def tpl(a, sx, sy):
    k = (round(a, 1), round(sx, 3), round(sy, 3))
    if k not in cache:
        M = cv2.getRotationMatrix2D((S / 2, S / 2), -a, 1.0)
        Sm = np.array([[sx, 0, S / 2 * (1 - sx)], [0, sy, S / 2 * (1 - sy)]])
        t = cv2.warpAffine(canvas, Sm, (S, S)); cache[k] = cv2.warpAffine(t, M, (S, S))
    return cache[k]
def match(img, cx, cy, angs, sxs, sys_, win):
    best = (-1,)
    for a in angs:
        for sx in sxs:
            for sy in sys_:
                t = tpl(a, sx, sy); xa, ya = int(cx - S / 2 - win), int(cy - S / 2 - win)
                pad = np.pad(img, S)
                roi = pad[ya + S:ya + S + S + 2 * win, xa + S:xa + S + S + 2 * win]
                r = cv2.matchTemplate(roi, t, cv2.TM_CCORR_NORMED); _, mv, _, (px, py) = cv2.minMaxLoc(r)
                if mv > best[0]: best = (float(mv), xa + px + S / 2, ya + py + S / 2, a, sx, sy)
    return best

rows, dots, crops = [], {}, []
prev = None
for i in range(A, B + 1):
    f = fr[i]; m, o = peel_mask(f)
    # dots: small orange-ish blobs (incl. pale, semi-transparent ones) not touching the peel
    h = cv2.cvtColor(f, cv2.COLOR_BGR2HSV); bgd = np.abs(f.astype(int) - bg.astype(int)).sum(2)
    cand = ((h[:, :, 0] >= 8) & (h[:, :, 0] <= 32) & (h[:, :, 1] > 45) & (bgd > 25)).astype(np.uint8)
    if m is not None: cand[cv2.dilate(m, np.ones((7, 7), np.uint8)) > 0] = 0
    n, lab, st, cen = cv2.connectedComponentsWithStats(cand); dl = []
    for k in range(1, n):
        a = st[k, 4]
        if not 3 <= a <= 400: continue
        w, hh = st[k, 2], st[k, 3]
        if max(w, hh) > 2.6 * min(w, hh) + 2: continue          # elongated = ray, not a dot
        col = np.median(f[lab == k], 0)
        dl.append([round(float(cen[k][0]) + PX0, 1), round(float(cen[k][1]) + PY0, 1), round(float(np.sqrt(a / np.pi)), 1), hexc(col)])
    if dl: dots[i] = dl
    if m is None: rows.append([i, None]); continue
    ys, xs = np.nonzero(m); c = np.array([xs.mean(), ys.mean()])
    mu = cv2.moments(m, True); th = 0.5 * np.degrees(np.arctan2(2 * mu['mu11'], mu['mu20'] - mu['mu02']))
    img = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.5)
    if prev is None:
        g = match(img, c[0], c[1], np.arange(-30, 31, 3), [0.6, 0.8, 1.0], [0.6, 0.8, 1.0], 6)
    else:
        g = match(img, c[0], c[1], np.arange(prev[3] - 12, prev[3] + 12.1, 3), [prev[4]], [prev[5]], 6)
    g = match(img, g[1], g[2], np.arange(g[3] - 3, g[3] + 3.1, 1), np.arange(g[4] - 0.08, g[4] + 0.081, 0.04), np.arange(g[5] - 0.08, g[5] + 0.081, 0.04), 3)
    g = match(img, g[1], g[2], np.arange(g[3] - 1, g[3] + 1.1, 0.5), np.arange(g[4] - 0.02, g[4] + 0.021, 0.01), np.arange(g[5] - 0.02, g[5] + 0.021, 0.01), 2)
    prev = g
    rows.append([i, round(float(c[0]) + PX0, 1), round(float(c[1]) + PY0, 1), int(m.sum()),
                 [int(xs.min()) + PX0, int(ys.min()) + PY0, int(xs.max()) + PX0, int(ys.max()) + PY0], round(float(th), 1),
                 round(g[1] + PX0, 1), round(g[2] + PY0, 1), round(g[3], 1), round(g[4], 3), round(g[5], 3), round(g[0], 3)])
    print(rows[-1], len(dots.get(i, [])), flush=True)
    if i <= 800 or i % 10 == 0:
        cx, cy = int(c[0]), int(c[1]); cr = f[max(0, cy - 60):cy + 60, max(0, cx - 120):cx + 120].copy()
        cr = cv2.copyMakeBorder(cr, 0, 120 - cr.shape[0], 0, 240 - cr.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
        cv2.putText(cr, str(i), (3, 13), 0, 0.45, (255, 0, 0), 1); crops.append(cr)
cols = 8
while len(crops) % cols: crops.append(np.full_like(crops[0], 255))
cv2.imwrite(str(OUT / 'peel_frames.jpg'), np.vstack([np.hstack(crops[k:k + cols]) for k in range(0, len(crops), cols)]), [cv2.IMWRITE_JPEG_QUALITY, 85])
# rest-pose template crop (upscaled) for redraw
f = fr[REF]; xs_, ys_ = np.nonzero(refm.T)
cv2.imwrite(str(OUT / 'peel_rest_x3.png'), cv2.resize(f[y0:y1, x0:x1], None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC))
save_json('peel_raw.json', {'refFrame': REF, 'refCentroid': [round(float(rc[0]) + PX0, 1), round(float(rc[1]) + PY0, 1)],
    'columns': ['frame', 'cx', 'cy', 'areaPx', 'bbox', 'principalAxisDeg', 'x', 'y', 'angle', 'sx', 'sy', 'score'],
    'note': 'x,y,angle,sx,sy map the frame-830 peel (centroid refCentroid) to this frame: scale in the peel local axes, then rotate clockwise by angle, then place centroid at x,y',
    'rows': rows, 'dots': {str(k): v for k, v in dots.items()}})
