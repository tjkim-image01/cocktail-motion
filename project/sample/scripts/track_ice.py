"""Frame-exact ice track from the reference MP4 (rotoscope track).

Each 30fps frame: new dark ink (frame ink minus empty-glass ink) is matched against a
rotated/scaled outline template of one isolated cube.  Output per frame and cube:
centre x/y, absolute angle, scale.  Leftover small ink strokes near cubes are saved as
line segments (impact marks) so the player can redraw them as vectors at the same frames.

usage: uv run --with opencv-python-headless --with numpy python scripts/track_ice.py VIDEO OUT.json
"""
import json, sys
import cv2, numpy as np

VIDEO, OUT = sys.argv[1], sys.argv[2]
BASE, TEMPLATE_FRAME, FIRST, LAST = 117, 124, 117, 180     # 3.9s empty glass, 4.133s isolated cube
# (id, frame where the cube is fully visible and alone, rough centre there) — from visual check
SEEDS = [('ice1', 124, (297, 176), 70), ('ice2', 140, (402, 608), 50), ('ice3', 147, (350, 351), 100)]   # + rough |vy| px/frame
INK = 180   # grey inner highlight lines count as ink: breaks the outline's 90° symmetry
PAD = 160                                                  # cubes enter above the frame

cap = cv2.VideoCapture(VIDEO); frames = []
while len(frames) <= LAST + 1:
    ok, f = cap.read()
    if not ok: break
    frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
base_ink = cv2.dilate((frames[BASE] < INK).astype(np.uint8), np.ones((3, 3))) > 0

def new_ink(i):
    m = ((frames[i] < INK) & ~base_ink).astype(np.float32)
    m[:, :170] = 0; m[:, 530:] = 0; m[820:] = 0
    return np.pad(m, ((PAD, 0), (0, 0)))

def soft(m): return cv2.GaussianBlur(m, (0, 0), 1.6)

# Template: ink of the isolated cube, its own angle from the outline's min-area rectangle.
ink = new_ink(TEMPLATE_FRAME); n, lab, st, cen = cv2.connectedComponentsWithStats(ink.astype(np.uint8))
k = 1 + int(np.argmax(st[1:, 4])); x, y, w, h = st[k, :4]
tmpl = (lab[y-8:y+h+8, x-8:x+w+8] == k).astype(np.float32)
pts = cv2.findNonZero((lab == k).astype(np.uint8)); (_, _), (rw, rh), ra = cv2.minAreaRect(pts)
T_CENTER = np.array([x - 8 + tmpl.shape[1] / 2, y - 8 + tmpl.shape[0] / 2 - PAD])
SIDE = float((rw + rh) / 2)
side_c = max(tmpl.shape) + 40
canvas = np.zeros((side_c, side_c), np.float32); oy, ox = (side_c - tmpl.shape[0]) // 2, (side_c - tmpl.shape[1]) // 2
canvas[oy:oy+tmpl.shape[0], ox:ox+tmpl.shape[1]] = tmpl

def rotated(rel, sc):
    M = cv2.getRotationMatrix2D((side_c / 2, side_c / 2), -rel, sc)   # image y down → negate for clockwise-positive
    return soft(cv2.warpAffine(canvas, M, (side_c, side_c)))

cache = {}
def tpl(rel, sc):
    key = (round(rel), round(sc, 2))
    if key not in cache: cache[key] = rotated(*key)
    return cache[key]

def search(img, cx, cy, rels, scales, win, winx=None):
    winx = win if winx is None else winx
    best = (-1, 0, 0, 0, 1)
    for rel in rels:
        for sc in scales:
            t = tpl(rel, sc); hs = side_c // 2
            x0, y0 = int(cx - winx - hs), int(cy + PAD - win - hs)
            x0c, y0c = max(0, x0), max(0, y0)
            roi = img[y0c:y0 + 2 * win + side_c, x0c:x0 + 2 * winx + side_c]
            if roi.shape[0] < side_c or roi.shape[1] < side_c: continue
            r = cv2.matchTemplate(roi, t, cv2.TM_CCORR_NORMED); _, mv, _, ml = cv2.minMaxLoc(r)
            if mv > best[0]:
                # sub-pixel parabola on the score peak
                px, py = ml; dx = dy = 0.0
                if 0 < px < r.shape[1] - 1:
                    a, b, c = r[py, px-1], r[py, px], r[py, px+1]; dx = 0.5 * (a - c) / (a - 2*b + c + 1e-9)
                if 0 < py < r.shape[0] - 1:
                    a, b, c = r[py-1, px], r[py, px], r[py+1, px]; dy = 0.5 * (a - c) / (a - 2*b + c + 1e-9)
                best = (mv, x0c + px + dx + hs, y0c + py + dy + hs - PAD, rel, sc)
    return best

tracks = {}
imgs = {i: soft(new_ink(i)) for i in range(FIRST, LAST + 1)}
for name, seed, (sx, sy), vy0 in SEEDS:
    g = search(imgs[seed], sx, sy, range(-45, 46, 3), [1.0], 40)
    g = search(imgs[seed], g[1], g[2], np.arange(g[3] - 3, g[3] + 4), [0.94, 0.97, 1.0, 1.03, 1.06], 6)
    rec = {seed: g}
    for direction in (1, -1):
        prev, vel, i = g, np.array([0.0, vy0 * direction]), seed + direction
        while FIRST <= i <= LAST:
            # constant-velocity guess; a bounce can reverse it, so the window grows with speed
            px, py = prev[1] + vel[0], prev[2] + vel[1]; win = int(30 + 1.6 * np.abs(vel).max())
            r = search(imgs[i], px, py, np.arange(prev[3] - 20, prev[3] + 21, 2), [1.0], win, 14)
            r = search(imgs[i], r[1], r[2], np.arange(r[3] - 2, r[3] + 3), [0.94, 0.97, 1.0, 1.03, 1.06], 4)
            if r[0] < 0.25 or r[2] < -40: break            # cube left the frame (going back in time)
            vel = np.array([r[1] - prev[1], r[2] - prev[2]]); prev = r; rec[i] = r; i += direction
    tracks[name] = {i: rec[i] for i in sorted(rec)}

# Impact marks: leftover ink strokes outside every matched cube, close to a cube.
def cube_mask(shape, r):
    m = np.zeros(shape, np.uint8); s = SIDE * r[4] / 2 + 7
    box = cv2.boxPoints(((r[1], r[2] + PAD), (2 * s, 2 * s), r[3] + ra)); cv2.fillPoly(m, [box.astype(np.int32)], 1); return m
marks = {}
for i in range(FIRST, LAST + 1):
    ink = new_ink(i).astype(np.uint8); cover = np.zeros_like(ink)
    live = [t[i] for t in tracks.values() if i in t]
    for r in live: cover |= cube_mask(ink.shape, r)
    rest = ink & (1 - cover); n, lab, st, cen = cv2.connectedComponentsWithStats(rest); segs = []
    for k in range(1, n):
        if not 6 <= st[k, 4] <= 260: continue
        ys, xs = np.nonzero(lab == k); P = np.stack([xs, ys - PAD], 1).astype(float); c = P.mean(0)
        if not live or min(np.hypot(c[0] - r[1], c[1] - r[2]) for r in live) > SIDE * 1.4: continue
        u, s_, vt = np.linalg.svd(P - c); d = vt[0]; proj = (P - c) @ d
        if s_[0] < 2.2 * (s_[1] + 1e-6): continue            # keep stroke-like blobs only
        a, b = c + d * proj.min(), c + d * proj.max()
        segs.append([round(float(v), 1) for v in (*a, *b)] + [round(float(st[k, 4] / max(1, np.ptp(proj))), 1)])
    marks[i] = segs

out = {'source': 'reference MP4 frames %d-%d @30fps, template frame %d' % (FIRST, LAST, TEMPLATE_FRAME),
       'templateAngle': round(float(ra), 2), 'side': round(SIDE, 1),
       'columns': ['frame', 'x', 'y', 'angle', 'scale', 'score'],
       'tracks': {n: [[i, round(float(r[1]), 1), round(float(r[2]), 1), round(float(r[3] + ra), 1), round(float(r[4]), 2), round(float(r[0]), 3)]
                      for i, r in t.items()] for n, t in tracks.items()},
       'marks': {str(i): s for i, s in marks.items() if s}}
open(OUT, 'w').write(json.dumps(out, indent=1, default=float))
for n, t in out['tracks'].items(): print(n, len(t), t[0], t[-1], 'min score', min(r[5] for r in t))
print('template angle', ra, 'side', SIDE, 'mark frames', len(out['marks']))
