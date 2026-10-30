"""Glass art for vector redraw, measured on the empty glass (frame 119; also 110/118 for boil spread).
Rim ellipse = cv2.fitEllipse on the centre points of the top & front rim arcs (per column ink runs);
sides = least-squares lines x = a + b*y through the centre of the outermost ink runs;
bottom = parabola through the centre of the lowest ink run; inner bottom line = grey line (max channel
110-215, black-hat) between the sides; highlight streaks = pixels lighter than the fill by > 7.
"""
from glass_common import *

cap = cv2.VideoCapture(str(VIDEO)); F = {}
for i in range(121):
    ok, f = cap.read()
    if i in (110, 114, 118, 119, 120): F[i] = f
def runs(col):
    r = []; s = None
    for y, v in enumerate(col):
        if v and s is None: s = y
        if not v and s is not None: r.append((s, y - 1)); s = None
    if s is not None: r.append((s, len(col) - 1))
    return r
res = {}
for fi in (110, 114, 118, 119):
    f = F[fi]; ink = f.max(2) < 110
    top, front, thick = [], [], []
    for x in range(205, 500):
        rr = [(a, b) for a, b in runs(ink[420:500, x]) if b - a < 10]
        if rr: top.append((x, 420 + (rr[0][0] + rr[0][1]) / 2)); thick.append(rr[0][1] - rr[0][0] + 1)
        if len(rr) >= 2: front.append((x, 420 + (rr[1][0] + rr[1][1]) / 2))
    pts = np.array(top + front, np.float32)
    (ecx, ecy), (MA, ma), eang = cv2.fitEllipse(pts)
    left, right, sth = [], [], []
    for y in range(495, 770):
        rr = runs(ink[y, 180:530])
        if not rr: continue
        a, b = rr[0]; left.append((180 + (a + b) / 2, y)); sth.append(b - a + 1)
        a, b = rr[-1]; right.append((180 + (a + b) / 2, y)); sth.append(b - a + 1)
    L = np.array(left); R = np.array(right)
    lb, la = np.polyfit(L[:, 1], L[:, 0], 1); rb, ra = np.polyfit(R[:, 1], R[:, 0], 1)
    bot = []
    for x in range(240, 466):
        rr = runs(ink[760:830, x])
        if rr: a, b = rr[-1]; bot.append((x, 760 + (a + b) / 2)); thick.append(b - a + 1)
    Bt = np.array(bot); pc = np.polyfit(Bt[:, 0], Bt[:, 1], 2)
    xv = -pc[1] / (2 * pc[0]); yv = np.polyval(pc, xv)
    # inner bottom line
    g = f[:, :, 1]; bh = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    grey = (bh > 15) & (f.max(2) >= 110) & (f.max(2) < 215)
    ib = []
    for x in range(240, 466):
        ys = np.nonzero(grey[730:775, x])[0]
        if len(ys): ib.append((x, 730 + ys.mean()))
    IB = np.array(ib); ipc = np.polyfit(IB[:, 0], IB[:, 1], 2)
    res[fi] = {'rimEllipse': {'cx': round(ecx, 2), 'cy': round(ecy, 2), 'w': round(max(MA, ma), 2), 'h': round(min(MA, ma), 2), 'angle': round(eang, 2)},
               'rimTopY_at_cx': round(ecy - min(MA, ma) / 2, 1), 'rimFrontY_at_cx': round(ecy + min(MA, ma) / 2, 1),
               'leftSide': {'x_at_y': [[495, round(la + lb * 495, 1)], [770, round(la + lb * 770, 1)]]},
               'rightSide': {'x_at_y': [[495, round(ra + rb * 495, 1)], [770, round(ra + rb * 770, 1)]]},
               'sideResidStd': round(float(np.std(L[:, 0] - (la + lb * L[:, 1]))), 2),
               'bottomParabola': {'vertex': [round(float(xv), 1), round(float(yv), 1)], 'y_at_x240': round(float(np.polyval(pc, 240)), 1), 'y_at_x465': round(float(np.polyval(pc, 465)), 1), 'coef': [float(c) for c in pc]},
               'innerBottomLine': {'x_range': [int(IB[0, 0]), int(IB[-1, 0])], 'y_at_ends': [round(float(np.polyval(ipc, IB[0, 0])), 1), round(float(np.polyval(ipc, IB[-1, 0])), 1)],
                                   'y_at_352': round(float(np.polyval(ipc, 352)), 1), 'hex': hexc(np.median(f[grey[:, :] & (np.arange(1080)[:, None] > 730) & (np.arange(1080)[:, None] < 775) & (np.arange(1080)[None] > 240) & (np.arange(1080)[None] < 466)], 0))},
               'outlineThicknessPx': {'rim': float(np.median(thick)), 'sides_horizontalRun': float(np.median(sth))}}
f = F[119]
ink = f.max(2) < 110
core = f[(f.max(2) < 70)]
fill = np.median(f[520:700, 300:420].reshape(-1, 3), 0)
base = np.median(f[770:790, 300:420].reshape(-1, 3), 0)
rim_in = np.median(f[452:470, 300:400].reshape(-1, 3), 0)
bg = np.median(f[300:380, 60:160].reshape(-1, 3), 0)
# highlight streaks: lighter than fill
L = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(int); fl = int(np.median(L[520:700, 300:420]))
hl = ((L > fl + 7) & ~ink).astype(np.uint8); hl[:480] = 0; hl[800:] = 0; hl[:, :215] = 0; hl[:, 490:] = 0
n, lab, st, cen = cv2.connectedComponentsWithStats(hl); streaks = []
for k in range(1, n):
    if st[k, 4] < 40: continue
    xl = lambda y: 212.7 + (232.2 - 212.7) * (y - 495) / 275; xr = lambda y: 491.8 + (471.2 - 491.8) * (y - 495) / 275
    if not (xl(cen[k][1]) + 1 < cen[k][0] < xr(cen[k][1]) - 1): continue
    ys, xs = np.nonzero(lab == k); P = np.stack([xs, ys], 1).astype(float); m = P.mean(0)
    u, s, vt = np.linalg.svd(P - m, full_matrices=False); d = vt[0]; pr = (P - m) @ d; a, b = m + d * pr.min(), m + d * pr.max()
    if a[1] > b[1]: a, b = b, a
    streaks.append({'p1': [round(a[0], 1), round(a[1], 1)], 'p2': [round(b[0], 1), round(b[1], 1)], 'widthPx': round(st[k, 4] / (np.ptp(pr) + 1), 1),
                    'hex': hexc(np.median(f[lab == k], 0)), 'areaPx': int(st[k, 4])})
art = {'frame': 119, 'perFrameBoil': res, 'colors': {'outlineCore': hexc(np.median(core, 0)), 'glassFill': hexc(fill), 'baseFill(below inner bottom line)': hexc(base),
       'rimInterior': hexc(rim_in), 'background': hexc(bg), 'highlightStreak': [s['hex'] for s in streaks]}, 'highlightStreaks': streaks}
save_json('glass_art.json', art)
print(json.dumps(art, indent=1, default=float))
cv2.imwrite(str(OUT / 'glass_f119_x3.png'), cv2.resize(f[420:815, 190:515], None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC))
