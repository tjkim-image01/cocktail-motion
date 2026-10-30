"""Ice cubes 1-3, frames 180-899, continuing analysis-01/ice-track-30fps.json.

Feature image = morphological black-hat of the green channel (thin dark lines darker than
their surroundings).  Works on clear, pink and deep-red liquid where a fixed grey threshold
fails.  Template = isolated cube at frame 124 (same as scripts/track_ice.py), its absolute
angle there is taken from the v3 track so angles stay in the same convention
(clockwise-positive screen degrees; 0 = axis-aligned cube, grey highlight corner top-right).
Search per frame: angle prev±10 (2°) x position window around constant-velocity guess,
then angle ±2 (0.5°) x scale 0.94-1.10; sub-pixel parabola on the score peak.
"""
import sys
from glass_common import *

TF, BASEF = 124, 117
v3 = json.loads((ROOT / '01_레퍼런스/analysis-01/ice-track-30fps.json').read_text())
ang124 = {r[0]: r[3] for r in v3['tracks']['ice1']}[TF]
start = {n: next(r for r in v3['tracks'][n] if r[0] == 180) for n in ('ice1', 'ice2', 'ice3')}

cap = cv2.VideoCapture(str(VIDEO)); frames = {}; i = 0
while True:
    ok, f = cap.read()
    if not ok: break
    if i in (TF, BASEF) or i >= 180: frames[i] = f[300:900, 120:600].copy()   # y 300.., x 120..
    i += 1
OX, OY = 120, 300
K = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
def feat(bgr):
    g = bgr[:, :, 1]
    bh = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, K).astype(np.float32)
    return cv2.GaussianBlur(np.clip(bh, 0, 50) / 50, (0, 0), 1.2)

# template: frame 124 cube near (297,176) is outside our crop -> read it separately
cap = cv2.VideoCapture(str(VIDEO)); cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
full = {}
for j in range(TF + 1):
    ok, f = cap.read()
    if j in (TF, BASEF): full[j] = f
def featfull(f):
    g = f[:, :, 1]; return np.clip(cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, K).astype(np.float32), 0, 50) / 50
d = np.clip(featfull(full[TF]) - cv2.dilate(featfull(full[BASEF]), np.ones((3, 3))), 0, 1)
cx, cy = 297, 176; R = 52
patch = d[cy - R:cy + R + 1, cx - R:cx + R + 1].copy()
# keep only the cube's connected ink (drop impact marks)
m = (patch > 0.25).astype(np.uint8); n, lab, st, cen = cv2.connectedComponentsWithStats(m)
k = 1 + int(np.argmax(st[1:, 4])); keep = cv2.dilate((lab == k).astype(np.uint8), np.ones((5, 5)))
# inner highlight lines may be separate components: keep everything within the cube's bbox
x, y, w, h = st[k, :4]; box = np.zeros_like(m); box[y:y+h, x:x+w] = 1
patch = patch * np.maximum(keep, box)
ys, xs = np.nonzero(patch > 0.3); pc = np.array([xs.mean(), ys.mean()])     # ink centroid offset
SC = 2 * R + 41; canvas = np.zeros((SC, SC), np.float32); o = (SC - patch.shape[0]) // 2
canvas[o:o + patch.shape[0], o:o + patch.shape[1]] = patch
canvas = cv2.GaussianBlur(canvas, (0, 0), 1.2)
cache = {}
def tpl(rel, sc):
    key = (round(rel * 2) / 2, round(sc, 3))
    if key not in cache:
        M = cv2.getRotationMatrix2D((SC / 2, SC / 2), -key[0], key[1]); cache[key] = cv2.warpAffine(canvas, M, (SC, SC))
    return cache[key]

def search(img, x, y, rels, scales, win):
    best = (-1, 0, 0, 0, 1); hs = SC / 2
    for rel in rels:
        for sc in scales:
            t = tpl(rel, sc)
            x0, y0 = int(round(x - OX - hs - win)), int(round(y - OY - hs - win))
            roi = img[max(0, y0):y0 + SC + 2 * win, max(0, x0):x0 + SC + 2 * win]
            if roi.shape[0] < SC or roi.shape[1] < SC: continue
            r = cv2.matchTemplate(roi, t, cv2.TM_CCORR_NORMED); _, mv, _, (px, py) = cv2.minMaxLoc(r)
            if mv > best[0]:
                dx = dy = 0.0
                if 0 < px < r.shape[1] - 1:
                    a, b, c = r[py, px-1], r[py, px], r[py, px+1]; dx = 0.5 * (a - c) / (a - 2*b + c + 1e-9)
                if 0 < py < r.shape[0] - 1:
                    a, b, c = r[py-1, px], r[py, px], r[py+1, px]; dy = 0.5 * (a - c) / (a - 2*b + c + 1e-9)
                best = (float(mv), OX + max(0, x0) + px + dx + hs, OY + max(0, y0) + py + dy + hs, rel, sc)
    return best

imgs = {}
def F(i):
    if i not in imgs: imgs[i] = feat(frames[i])
    return imgs[i]
tracks = {}
for name, r0 in start.items():
    rel0 = r0[3] - ang124
    g = search(F(180), r0[1], r0[2], np.arange(rel0 - 3, rel0 + 3.1, 0.5), [0.97, 1.0, 1.03], 4)
    rows = [[180, g[1], g[2], g[3] + ang124, g[4], g[0]]]; prev = g; vel = np.zeros(2); sc = g[4]
    for i in range(181, 900):
        px, py = prev[1] + 0.5 * vel[0], prev[2] + 0.5 * vel[1]
        win = int(8 + 1.5 * np.abs(vel).max())
        r = search(F(i), px, py, np.arange(prev[3] - 10, prev[3] + 10.1, 2), [prev[4]], win)
        r = search(F(i), r[1], r[2], np.arange(r[3] - 2, r[3] + 2.1, 0.5), np.arange(prev[4] - 0.02, prev[4] + 0.021, 0.01), 2)
        vel = np.array([r[1] - prev[1], r[2] - prev[2]]); prev = r
        rows.append([i, r[1], r[2], r[3] + ang124, r[4], r[0]])
    tracks[name] = [[int(a), round(b, 2), round(c, 2), round(d, 2), round(e, 3), round(s, 3)] for a, b, c, d, e, s in rows]
    sc_ = [r[5] for r in tracks[name]]
    print(name, tracks[name][0], tracks[name][-1], 'score min/med', min(sc_), np.median(sc_), flush=True)
save_json('ice_raw.json', {'templateFrame': TF, 'templateAngle': ang124, 'columns': ['frame', 'x', 'y', 'angle', 'scale', 'score'], 'tracks': tracks})
