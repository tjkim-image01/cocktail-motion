"""Bar spoon per frame 626-740.  Spoon pixels above the liquid (y < 540) = |frame - frame 630| > 50
(frame 630 = last frame without spoon), opened 3x3 to drop line boil.  Line fit x = m*y + c (RANSAC +
least squares) gives the shaft angle; the topmost pixel along the line gives the ball top,
the ball centre = topmost + R along the shaft.  Bowl (inside the liquid) = ball centre + L along
the shaft, L measured on frames 640-700 where both are visible (bowl found by black-hat ink).
angle: clockwise-positive screen degrees, 0 = vertical, ball on top
       (positive = ball leans right of the bowl).
"""
from glass_common import *

REF, A, B = 630, 626, 740
X0s, X1s = 230, 500
cap = cv2.VideoCapture(str(VIDEO)); fr = {}; i = 0
while i <= B:
    ok, f = cap.read()
    if not ok: break
    if i >= A: fr[i] = f[:, X0s:X1s].copy()
    i += 1
ref = fr[REF].astype(int)
R_BALL = 11.0
K = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
rows = []
for i in range(A, B + 1):
    f = fr[i]
    d = (np.abs(f.astype(int) - ref).sum(2) > 50).astype(np.uint8); d[528:] = 0
    d = cv2.morphologyEx(d, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ys, xs = np.nonzero(d)
    if len(ys) < 60: rows.append({'f': i, 'visible': False}); continue
    # RANSAC on x = m*y + c
    rng = np.random.default_rng(i); best = (0, None)
    for _ in range(300):
        p, q = rng.choice(len(ys), 2, replace=False)
        if abs(ys[p] - ys[q]) < 30: continue
        m = (xs[p] - xs[q]) / (ys[p] - ys[q]); c = xs[p] - m * ys[p]
        inl = np.abs(xs - (m * ys + c)) < 6
        if inl.sum() > best[0]: best = (inl.sum(), inl)
    if best[1] is None: rows.append({'f': i, 'visible': False}); continue
    inl = best[1]; m, c = np.polyfit(ys[inl], xs[inl], 1)
    inl = np.abs(xs - (m * ys + c)) < 7; m, c = np.polyfit(ys[inl], xs[inl], 1)
    # contiguous run along the line, from the lowest inlier upwards (title boil above is not spoon)
    occ = np.zeros(d.shape[0], bool); occ[ys[inl]] = True
    runs = []; start = None; last = None
    for y in np.nonzero(occ)[0]:
        if start is None: start = last = y
        elif y - last > 25: runs.append((start, last)); start = last = y
        else: last = y
    runs.append((start, last))
    yt, yb = max(runs, key=lambda r: r[1] - r[0]); yt, yb = int(yt), int(yb)
    if yb - yt < 60: rows.append({'f': i, 'visible': False}); continue
    inl = inl & (ys >= yt) & (ys <= yb); m, c = np.polyfit(ys[inl], xs[inl], 1)
    ang = float(np.degrees(np.arctan(-m)))            # top leans right -> x decreases with y -> m<0 -> positive
    dirv = np.array([m, 1]) / np.hypot(m, 1)            # unit vector pointing down the shaft
    top = np.array([m * yt + c, yt])
    ball = top + R_BALL * dirv if yt > 1 else None
    low = np.array([m * yb + c, yb])
    rows.append({'f': i, 'visible': True, 'angle': round(ang, 2), 'm': float(m), 'c': float(c) + X0s,
                 'topY': int(yt), 'lowY': int(yb), 'ball': None if ball is None else [round(float(ball[0]) + X0s, 1), round(float(ball[1]), 1)],
                 'lowEnd': [round(float(low[0]) + X0s, 1), round(float(low[1]), 1)], 'n': int(inl.sum())})
# bowl: black-hat ink blob near the shaft line below the surface, frames where ball is visible
Ls = []
for r in rows:
    if not r['visible'] or r['ball'] is None or r['lowY'] < 524: continue
    i = r['f']; f = fr[i]; bh = cv2.morphologyEx(f[:, :, 1], cv2.MORPH_BLACKHAT, K)
    bx, by = r['ball']; dirv = np.array([r['m'], 1]) / np.hypot(r['m'], 1)
    # profile of 'spoon-ness' along the shaft: the bowl is a ~28px oval whose outline crosses the line
    best = None
    for L in np.arange(290, 345, 0.5):
        p = np.array([bx - X0s, by]) + L * dirv; x, y = int(round(p[0])), int(round(p[1]))
        if y + 20 >= f.shape[0]: break
        # oval outline: dark ink at ±7px left/right of the bowl centre
        perp = np.array([dirv[1], -dirv[0]])
        sc = 0
        for s in (-7, 7):
            q = p + s * perp; sc += float(bh[int(round(q[1])) - 4:int(round(q[1])) + 5, int(round(q[0]))].astype(float).mean())
        if best is None or sc > best[0]: best = (sc, L)
    r['bowlL'] = float(best[1]); Ls.append(best[1])
L = float(np.median(Ls)) if Ls else None
for r in rows:
    if not r['visible']: continue
    dirv = np.array([r['m'], 1]) / np.hypot(r['m'], 1)
    if r['lowY'] < 524:   # bowl above the liquid: bowl centre = lowest pixel - 14 along the shaft
        bowl = np.array(r['lowEnd']) - 14 * dirv; ball = bowl - L * dirv
        if r['ball'] is not None: r['ballMeasured'] = r['ball']
        r['ball'] = [round(float(ball[0]), 1), round(float(ball[1]), 1)]; r['ballFrom'] = 'bowl'
    else:
        r['ballFrom'] = 'top'
        bowl = np.array(r['ball']) + L * dirv
    r['bowl'] = [round(float(bowl[0]), 1), round(float(bowl[1]), 1)]
print('L ball->bowl', L, 'n', len(Ls), 'std', np.std(Ls) if Ls else None)
for r in rows:
    if r['visible']: print(r['f'], r['angle'], r['ball'], r['bowl'], r.get('bowlL'), r['topY'], r['lowY'])
    else: print(r['f'], '-')
save_json('spoon_raw.json', {'ref': REF, 'ballRadius': R_BALL, 'L': L, 'rows': rows})
