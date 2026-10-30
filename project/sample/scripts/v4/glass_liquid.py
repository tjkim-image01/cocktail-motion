"""Liquid per frame 180-899: surface ellipse (back arc + front arc), level, tilt/waves, colours.

Surface model (screen px): back arc  yb(x) = yc - b*sqrt(1-u^2), front arc yf(x) = yc + b*sqrt(1-u^2),
u = (x - XC)/a(yc), a(y) = liquid half-width at row y (measured from deep-red frames:
a = 122.5 - 0.075*(y-580), XC = 349).  Line candidates = new thin dark lines (black-hat of the
green channel > 12, minus the empty-glass lines of frame 119), ice boxes masked out.
Grid search (yc, b) maximising the fraction of visible columns whose two arcs land on a line,
then per-column residuals (back/front arc taken as nearest candidate within ±4px) give tilt
(left vs right midline) and waviness.
"""
from glass_common import *

XC = 349.0
def half_w(y): return 122.5 - 0.075 * (y - 580)
fr = load(119, 899)
ice = json.loads((OUT / 'ice_raw.json').read_text())['tracks']
icef = {n: {r[0]: r for r in rows} for n, rows in ice.items()}
K = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
def lines(bgr): return cv2.morphologyEx(bgr[:, :, 1], cv2.MORPH_BLACKHAT, K)
base = cv2.dilate((lines(fr[119]) > 12).astype(np.uint8), np.ones((3, 3)))
XS = np.arange(246, 461, 2)
YC = np.arange(470, 766, 0.5); BS = np.arange(2, 32, 0.5)

def ice_mask(i, pad=5):
    m = np.zeros(fr[119].shape[:2], np.uint8)
    for n, t in icef.items():
        if i in t:
            _, x, y, ang, sc, _ = t[i]; s = 71 * sc + 2 * pad
            box = cv2.boxPoints(((x - X0, y - Y0), (s, s), ang)).astype(np.int32); cv2.fillPoly(m, [box], 1)
    return m

rows = []
for i in range(180, 900):
    f = fr[i]; ln = ((lines(f) > 12) & (base == 0)).astype(np.uint8)
    im = ice_mask(i); ln[im > 0] = 0
    lnd = cv2.dilate(ln, np.ones((3, 1)))                          # ±1px vertical tolerance
    cols = XS - X0
    best = (0, None, None)
    # vectorised over b for each yc
    for yc in YC[::2]:
        a = half_w(yc); u = np.clip((XS - XC) / a, -0.999, 0.999); s = np.sqrt(1 - u * u)
        yb = (yc - BS[:, None] * s[None]).round().astype(int) - Y0
        yf = (yc + BS[:, None] * s[None]).round().astype(int) - Y0
        visb = im[yb, cols[None].repeat(len(BS), 0)] == 0; visf = im[yf, cols[None].repeat(len(BS), 0)] == 0
        hb = lnd[yb, cols[None].repeat(len(BS), 0)] * visb; hf = lnd[yf, cols[None].repeat(len(BS), 0)] * visf
        sc = (hb.sum(1) + hf.sum(1)) / np.maximum(visb.sum(1) + visf.sum(1), 1) * np.minimum(1, (visb.sum(1) + visf.sum(1)) / 40)
        k = int(np.argmax(sc))
        if sc[k] > best[0]: best = (float(sc[k]), float(yc), float(BS[k]))
    sc0, yc0, b0 = best
    if yc0 is None:
        rows.append([i, None]); continue
    # fine search ±1.5 px
    for yc in np.arange(yc0 - 1.5, yc0 + 1.51, 0.5):
        for b in np.arange(max(2, b0 - 2), b0 + 2.01, 0.5):
            a = half_w(yc); u = np.clip((XS - XC) / a, -0.999, 0.999); s = np.sqrt(1 - u * u)
            yb = (yc - b * s).round().astype(int) - Y0; yf = (yc + b * s).round().astype(int) - Y0
            vb = im[yb, cols] == 0; vf = im[yf, cols] == 0
            sc = ((lnd[yb, cols] * vb).sum() + (lnd[yf, cols] * vf).sum()) / max(vb.sum() + vf.sum(), 1) * min(1, (vb.sum() + vf.sum()) / 40)
            if sc > best[0]: best = (float(sc), float(yc), float(b))
    sc0, yc0, b0 = best
    # per-column measured arcs (nearest line pixel within ±4 of model)
    a = half_w(yc0); u = np.clip((XS - XC) / a, -0.999, 0.999); s = np.sqrt(1 - u * u)
    mb, mf = [], []
    for x, sx in zip(XS, s):
        c = x - X0
        for arr, y0 in ((mb, yc0 - b0 * sx), (mf, yc0 + b0 * sx)):
            ys = np.arange(int(y0) - 4, int(y0) + 5)
            hit = [y for y in ys if ln[y - Y0, c] and not im[y - Y0, c]]
            arr.append(float(np.mean(hit)) if hit else np.nan)
    mb, mf = np.array(mb), np.array(mf)
    rb = mb - (yc0 - b0 * s); rf = mf - (yc0 + b0 * s)
    mid = (mb + mf) / 2
    L = XS < XC - 50; R = XS > XC + 50
    yl = float(np.nanmedian(mid[L])) if np.isfinite(mid[L]).sum() >= 3 else None
    yr = float(np.nanmedian(mid[R])) if np.isfinite(mid[R]).sum() >= 3 else None
    res = np.concatenate([rb[np.isfinite(rb)], rf[np.isfinite(rf)]])
    # colours: body (below front arc), band (between arcs), sampled at visible pixels away from lines
    yy, xx = np.mgrid[0:f.shape[0], 0:f.shape[1]]
    X = xx + X0; Y = yy + Y0; aa = half_w(Y); uu = (X - XC) / aa
    inside = np.abs(uu) < 0.9; ss = np.sqrt(np.clip(1 - uu * uu, 0, 1))
    clean = (im == 0) & (cv2.dilate(ln, np.ones((5, 5))) == 0)
    body = inside & (Y > yc0 + b0 * ss + 4) & (Y < 748) & clean
    band = inside & (Y > yc0 - b0 * ss + 3) & (Y < yc0 + b0 * ss - 3) & clean
    bc = np.median(f[body], 0) if body.sum() > 50 else None
    nc = np.median(f[band], 0) if band.sum() > 30 else None
    nvis = int(np.isfinite(mb).sum() + np.isfinite(mf).sum())
    rows.append([i, round(yc0, 1), round(b0, 1), round(sc0, 3), yl and round(yl, 1), yr and round(yr, 1),
                 round(float(np.nanstd(res)), 2) if len(res) else None, round(float(np.nanmax(np.abs(res))), 1) if len(res) else None, nvis,
                 hexc(bc) if bc is not None else None, hexc(nc) if nc is not None else None,
                 [None if not np.isfinite(v) else round(float(v), 1) for v in mb], [None if not np.isfinite(v) else round(float(v), 1) for v in mf]])
    if i % 30 == 0: print(rows[-1][:11], flush=True)
save_json('liquid_raw.json', {'XC': XC, 'halfWidth': 'a(y)=122.5-0.075*(y-580)', 'xs': XS.tolist(),
    'columns': ['frame', 'yc', 'b', 'score', 'yMidLeft', 'yMidRight', 'residStd', 'residMax', 'nVisible', 'bodyHex', 'bandHex', 'backArcY', 'frontArcY'], 'rows': rows})
