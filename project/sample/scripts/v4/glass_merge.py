"""Merge the raw glass measurements into data.json + verification overlays.
Inputs (same folder): glass_pose_raw, ice_raw, liquid_raw, spoon_raw, peel_raw, rays_raw, bubbles_raw, glass_art.
"""
from glass_common import *

J = lambda n: json.loads((OUT / n).read_text())
pose, ice, liq, sp, peel, rays, bub, art = (J(n) for n in ('glass_pose_raw.json', 'ice_raw.json', 'liquid_raw.json', 'spoon_raw.json',
                                                         'peel_raw.json', 'rays_raw.json', 'bubbles_raw.json', 'glass_art.json'))
cap = cv2.VideoCapture(str(VIDEO)); V = {}
need = set(range(180, 900))
i = 0
while True:
    ok, f = cap.read()
    if not ok: break
    if i in need: V[i] = f
    i += 1

# ---------- liquid: presence + phases ----------
lrows = []
for r in liq['rows']:
    i = r[0]
    present = r[1] is not None and r[3] is not None and r[3] >= 0.8 and r[8] >= 30 and i >= 228
    lrows.append([i, r[1] if present else None, r[2] if present else None, r[4] if present else None, r[5] if present else None,
                  r[6] if present else None, r[9] if present else None, r[10] if present else None, round(r[3], 3) if r[3] is not None else None])
# ice colour inside each cube (box shrunk to 60%) vs liquid body, for opacity estimate
icef = {n: {r[0]: r for r in rows} for n, rows in ice['tracks'].items()}
def inner(i, n, frac=0.55):
    _, x, y, a, s, _ = icef[n][i]; m = np.zeros((1080, 1080), np.uint8)
    cv2.fillPoly(m, [cv2.boxPoints(((x, y), (71 * s * frac, 71 * s * frac), a)).astype(np.int32)], 1); return m > 0
ice_col = {}
for i in (200, 300, 420, 470, 600, 620, 660, 700, 740, 800, 880):
    ice_col[i] = {n: hexc(np.median(V[i][inner(i, n)], 0)) for n in icef}

# ---------- spoon ----------
srows = []
fix = {732: 220.0, 733: 217.0}            # bowl centre y measured separately (lowest spoon pixel 234/231 - 14)
L = sp['L']
for r in sp['rows']:
    i = r['f']
    if i < 631 or i > 733: continue
    if not r['visible'] or i in fix:
        if i in fix:
            ang = 3.6; d = np.array([-np.sin(np.radians(ang)), np.cos(np.radians(ang))])
            bowl = np.array([350.0, fix[i]]); ball = bowl - L * d
            srows.append([i, round(float(ball[0]), 1), round(float(ball[1]), 1), ang, round(float(bowl[0]), 1), round(float(bowl[1]), 1), 'bowl(manual-check)'])
        continue
    srows.append([i, r['ball'][0], r['ball'][1], r['angle'], r['bowl'][0], r['bowl'][1], r['ballFrom']])

# ---------- peel ----------
prow = [r for r in peel['rows'] if r[1] is not None]
f = V[830]; h = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
o = ((h[:, :, 0] >= 8) & (h[:, :, 0] <= 28) & (h[:, :, 1] > 110) & (h[:, :, 2] > 150)).astype(np.uint8)
o[:300] = 0; o[520:] = 0; o[:, :360] = 0; o[:, 620:] = 0
oc = cv2.morphologyEx(o, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
n, lab, st, _ = cv2.connectedComponentsWithStats(oc); k = 1 + int(np.argmax(st[1:, 4])); body = (lab == k).astype(np.uint8)
ink = (f.max(2) < 110).astype(np.uint8)
full = cv2.morphologyEx(body | (ink & cv2.dilate(body, np.ones((9, 9), np.uint8))), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
cnts, hier = cv2.findContours(full, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
polys = [{'hole': bool(hier[0][j][3] >= 0), 'pts': [[int(p[0][0]), int(p[0][1])] for p in cv2.approxPolyDP(c, 0.8, True)]} for j, c in enumerate(cnts) if cv2.contourArea(c) > 15]
dt = cv2.distanceTransform(full, cv2.DIST_L2, 5); dtb = cv2.distanceTransform(body, cv2.DIST_L2, 5)
fillc = f[(body > 0) & (dtb > 2.5)]; Lf = fillc.astype(int).sum(1)
peel_art = {'frame': 830, 'contours': polys, 'tubeWidthPx(with outline)': round(float(2 * np.percentile(dt[dt > 0], 97)), 1),
            'orangeCoreWidthPx': round(float(2 * np.percentile(dtb[dtb > 0], 97)), 1),
            'fillHex': hexc(np.median(fillc[Lf > np.percentile(Lf, 30)], 0)), 'speckleHex': hexc(np.median(fillc[Lf < np.percentile(Lf, 3)], 0)),
            'outlineHex': hexc(np.median(f[(ink > 0) & (cv2.dilate(body, np.ones((7, 7), np.uint8)) > 0)], 0)),
            'centroid': peel['refCentroid']}
spritz = {k: [d for d in v if 300 <= d[1] <= 480 and 280 <= d[0] <= 470] for k, v in peel['dots'].items() if 750 <= int(k) <= 782}
spritz = {k: v for k, v in spritz.items() if v}

# ---------- rays ----------
REAL = []
for r in rays['rays']:
    fs = r['frames']; mx = np.median([(x[1] + x[3]) / 2 for x in fs]); my = np.median([(x[2] + x[4]) / 2 for x in fs])
    if 495 <= mx <= 560 and any(abs(my - yy) < 12 for yy in (558, 621, 684)): continue      # oz label dashes / text
    if len(fs) < 30: continue
    REAL.append(r)
f = V[850]; hs = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
ray_out = []
for j, r in enumerate(REAL):
    fr850 = next((x for x in r['frames'] if x[0] == 850), r['frames'][len(r['frames']) // 2])
    p1, p2 = np.array(fr850[1:3]), np.array(fr850[3:5]); best = None
    for t in np.linspace(0.2, 0.8, 13):
        p = (p1 + (p2 - p1) * t).astype(int); pix = f[p[1] - 1:p[1] + 2, p[0] - 1:p[0] + 2].reshape(-1, 3)
        sat = hs[p[1] - 1:p[1] + 2, p[0] - 1:p[0] + 2, 1].reshape(-1)
        k = int(np.argmax(sat))
        if best is None or sat[k] > best[0]: best = (int(sat[k]), pix[k])
    ray_out.append({'id': j, 'firstFrame': r['frames'][0][0], 'coreHex': hexc(best[1]),
                    'frames': [[x[0], x[1], x[2], x[3], x[4], x[5], x[7]] for x in r['frames']]})

# ---------- bubbles ----------
bubbles = {}
for k, v in bub['frames'].items():
    i = int(k); keep = []
    for x, y, r, kind, hx in v:
        if not (250 <= x <= 455 and y > 475): continue
        if 226 <= i <= 300 and kind == 'ring': keep.append([x, y, r, 'gin-bubble-ring', hx])
        if 372 <= i <= 450 and kind == 'drop': keep.append([x, y, r, 'campari-drop', hx])
        if 522 <= i <= 596 and kind == 'drop': keep.append([x, y, r, 'vermouth-drop', hx])
    if keep: bubbles[i] = keep

data = {
 'schema': {
  'units': 'pixels in the 1080x1080 reference, origin top-left, y down; frame = 0-based index from sequential cv2.VideoCapture reads, t = frame/30',
  'angles': 'degrees, clockwise-positive on screen',
  'glass.pose.rows': '[frame, cx, cy, sx, sy, score]: map frame-119 glass coords p -> (cx + sx*(px-352.5), cy + sy*(py-617.5)); score = NCC of outline ink',
  'glass.art': 'frame-119 empty glass geometry/colours (see glass_art.json for per-frame boil spread)',
  'liquid.rows': '[frame, yc, b, yMidLeft, yMidRight, residStd, bodyHex, bandHex, fitScore]: surface ellipse centre y (x centre 349), half-height b; back arc y = yc - b*sqrt(1-u^2), front arc y = yc + b*sqrt(1-u^2), u=(x-349)/a, a = 122.5-0.075*(yc-580); yMidLeft/Right = measured midline at x<299 / x>399 (tilt check); null = no liquid',
  'liquid.halfWidth': 'liquid body half-width at row y: a(y) = 122.5 - 0.075*(y-580), centre x 349; body bottom ≈ y 757 at x 352 (dark rounded bottom edge)',
  'ice.tracks': '{ice1|ice2|ice3: [[frame, x, y, angle, scale, score]]} same convention as analysis-01 (0° = axis-aligned, grey highlight corner top-right), cube side 71*scale',
  'spoon.rows': '[frame, ballX, ballY, angle, bowlX, bowlY, ballFrom]: ball = ball-top sphere centre; angle 0 = vertical, + = ball leans right of bowl; bowl = ball + L*(−sin a, cos a); ballFrom top = measured, bowl = derived from the bowl end',
  'peel.rows': '[frame, cx, cy, areaPx, bbox, principalAxisDeg, x, y, angle, sx, sy, score]: x,y,angle,sx,sy map the frame-830 peel (art.contours, centroid art.centroid) -> scale (sx along screen x, sy along y, about centroid), rotate clockwise by angle, translate centroid to x,y',
  'peel.spritz': '{frame: [[x, y, r, hex]]}',
  'bubbles': '{frame: [[x, y, r, kind, hex]]}  kind gin-bubble-ring (grey outline circle) | campari-drop | vermouth-drop (filled)',
  'rays[].frames': '[frame, x1, y1, x2, y2, widthPx, satMedian]; satMedian ramps up while the ray fades in',
 },
 'glass': {'pose': {'rows': pose['rows']}, 'art': art},
 'liquid': {'rows': lrows, 'iceInsideColour': ice_col},
 'ice': {'tracks': ice['tracks']},
 'spoon': {'L_ballToBowl': round(L, 1), 'rows': srows},
 'peel': {'rows': prow, 'art': peel_art, 'spritz': spritz},
 'bubbles': {str(k): v for k, v in sorted(bubbles.items())},
 'rays': ray_out,
}
(OUT / 'data.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'), default=float))
print('rays', [(r['firstFrame'], r['coreHex'], len(r['frames'])) for r in ray_out])
print('peel art', {k: v for k, v in peel_art.items() if k != 'contours'}, 'contours', [(p['hole'], len(p['pts'])) for p in polys])
print('spritz frames', sorted(map(int, spritz)), sum(len(v) for v in spritz.values()))
print('bubbles frames', len(bubbles), sum(len(v) for v in bubbles.values()))
print('ice colours', ice_col)

# ---------- overlays ----------
def sheet(frames, draw, crop, sc, cols, name):
    tiles = []
    for i in frames:
        im = V[i].copy(); draw(im, i); x0, y0, x1, y1 = crop
        c = cv2.resize(im[y0:y1, x0:x1], None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
        cv2.putText(c, str(i), (3, 13), 0, 0.45, (0, 0, 0), 1); tiles.append(c)
    while len(tiles) % cols: tiles.append(np.full_like(tiles[0], 255))
    cv2.imwrite(str(OUT / name), np.vstack([np.hstack(tiles[k:k + cols]) for k in range(0, len(tiles), cols)]), [cv2.IMWRITE_JPEG_QUALITY, 82])
LQ = {r[0]: r for r in lrows}
def draw_liq(im, i):
    r = LQ.get(i)
    if not r or r[1] is None: return
    yc, b = r[1], r[2]; a = 122.5 - 0.075 * (yc - 580)
    cv2.ellipse(im, (349, int(round(yc))), (int(round(a)), int(round(b))), 0, 0, 360, (0, 255, 0), 1, cv2.LINE_AA)
    cv2.line(im, (330, int(yc)), (368, int(yc)), (255, 0, 0), 1)
sheet(range(228, 900, 12), draw_liq, (200, 500, 510, 790), 0.5, 10, 'verify_liquid.jpg')
SP = {r[0]: r for r in srows}
def draw_sp(im, i):
    r = SP.get(i)
    if not r: return
    cv2.circle(im, (int(r[1]), int(r[2])), 11, (0, 200, 0), 1, cv2.LINE_AA); cv2.line(im, (int(r[1]), int(r[2])), (int(r[4]), int(r[5])), (0, 0, 255), 1, cv2.LINE_AA)
    cv2.ellipse(im, ((r[4], r[5]), (16, 30), -r[3]), (255, 0, 0), 1, cv2.LINE_AA)
sheet(range(630, 736, 3), draw_sp, (230, 180, 500, 720), 0.4, 12, 'verify_spoon.jpg')
PR = {r[0]: r for r in prow}; c0 = np.array(peel_art['centroid'])
def draw_peel(im, i):
    r = PR.get(i)
    if r:
        x, y, ang, sx, sy = r[6:11]; th = np.radians(ang); R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        for p in polys:
            P = (np.array(p['pts'], float) - c0) * [sx, sy]; P = P @ R.T + [x, y]
            cv2.polylines(im, [P.astype(np.int32)], True, (255, 0, 255), 1, cv2.LINE_AA)
    for d in spritz.get(str(i), []): cv2.circle(im, (int(d[0]), int(d[1])), max(2, int(d[2]) + 2), (0, 160, 0), 1)
sheet(list(range(738, 800, 2)) + list(range(800, 900, 10)), draw_peel, (250, 300, 620, 520), 0.55, 8, 'verify_peel.jpg')
RF = {}
for r in ray_out:
    for x in r['frames']: RF.setdefault(x[0], []).append((r['id'], x))
def draw_rays(im, i):
    for rid, x in RF.get(i, []):
        cv2.line(im, (int(x[1]), int(x[2])), (int(x[3]), int(x[4])), (0, 160, 0), 1, cv2.LINE_AA); cv2.putText(im, str(rid), (int(x[3]) + 3, int(x[4])), 0, 0.4, (0, 120, 0), 1)
sheet(range(812, 900, 4), draw_rays, (90, 360, 620, 720), 0.5, 6, 'verify_rays.jpg')
PS = {r[0]: r for r in pose['rows']}
def draw_glass(im, i):
    _, cx, cy, sx, sy, _ = PS[i]; e = art['perFrameBoil']['119']['rimEllipse']
    cv2.ellipse(im, ((cx + sx * (e['cx'] - 352.5), cy + sy * (e['cy'] - 617.5)), (e['w'] * sx, e['h'] * sy), 0), (0, 0, 255), 1, cv2.LINE_AA)
    for side in ('leftSide', 'rightSide'):
        (ya, xa), (yb, xb) = art['perFrameBoil']['119'][side]['x_at_y']
        cv2.line(im, (int(cx + sx * (xa - 352.5)), int(cy + sy * (ya - 617.5))), (int(cx + sx * (xb - 352.5)), int(cy + sy * (yb - 617.5))), (0, 0, 255), 1, cv2.LINE_AA)
    bp = art['perFrameBoil']['119']['bottomParabola']['coef']
    xs = np.arange(240, 466, 4); P = np.stack([cx + sx * (xs - 352.5), cy + sy * (np.polyval(bp, xs) - 617.5)], 1)
    cv2.polylines(im, [P.astype(np.int32)], False, (0, 0, 255), 1, cv2.LINE_AA)
sheet([180, 400, 640, 800, 815, 822, 826, 830, 834, 838, 842, 846, 850, 870, 899], draw_glass, (180, 410, 530, 830), 0.6, 5, 'verify_glass_pose.jpg')
def draw_bub(im, i):
    for x, y, r, k, hx in bubbles.get(i, []): cv2.circle(im, (int(x), int(y)), int(r) + 3, (0, 200, 0), 1)
sheet([i for i in range(226, 600, 3) if i in bubbles][:60], draw_bub, (230, 500, 470, 760), 0.6, 10, 'verify_bubbles.jpg')
