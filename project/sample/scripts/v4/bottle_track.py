"""Frame-exact rigid track of the three liquor bottles in the reference MP4.

Per bottle: an upright "art" template (RGB + soft mask) is cut from a frame where the bottle
stands alone (diff vs a frame without it), derotated so its long axis is exactly vertical.
Every frame is matched with a masked colour MSE

    E(x, y) = sum_M V (I - T)^2 / sum_M V           (V = 1 inside the frame, 0 in the padding)

computed with matchTemplate(TM_CCORR) terms, so a bottle half outside the left/top edge is
matched on its visible part only.  Search = angle x scale x position around a constant-velocity
prediction (window grows with speed), then a fine angle/scale pass and a sub-pixel parabola.

Pose convention (all px, image y down):
  anchor (x, y)  = mouth tip = centre of the top edge of the lip ring of the upright art
  angle          = long-axis angle in degrees, 0 = upright (neck up), positive = clockwise on screen
  frame_point    = anchor + scale * R(angle) * art_point,  R = [[cos,-sin],[sin,cos]],
                   art_point relative to the mouth tip in upright art (x right, y down; body is +y)

usage: uv run -q --with opencv-python-headless --with numpy python scripts/v4/bottle_track.py
"""
import json, sys, time
from pathlib import Path
import cv2, numpy as np

ROOT = Path(__file__).resolve().parents[2]
VIDEO = str(ROOT / '01_레퍼런스/original.mp4')
OUT = ROOT / '01_레퍼런스/analysis-v4/bottles'
OUT.mkdir(parents=True, exist_ok=True)

# name: base (bottle absent, same scene), template frame (upright, alone), scan range
BOTTLES = {
    # first/last = first/last frame with any changed pixel at the bottle (diff vs base, checked
    # separately: 188/318, 338/468, 488/618 show nothing at the bottle)
    'gin':      dict(base=186, tmpl=200, first=189, last=317),
    'campari':  dict(base=336, tmpl=350, first=339, last=467),
    'vermouth': dict(base=486, tmpl=500, first=489, last=617),
}
ROI_W, ROI_H = 720, 720          # bottles live in the top-left; stream analysed elsewhere
PADL, PADT = 330, 140            # bottles enter/leave through the left edge (and may poke up)
F0, F1 = 175, 640


def read_frames():
    cap = cv2.VideoCapture(VIDEO); fr = {}; i = 0
    while i <= F1:
        ok, f = cap.read()
        if not ok: break
        if i >= F0: fr[i] = f[:ROI_H, :ROI_W].copy()
        i += 1
    return fr


def axis_of(mask):
    ys, xs = np.nonzero(mask); P = np.stack([xs, ys], 1).astype(float); c = P.mean(0)
    _, _, vt = np.linalg.svd(P - c, full_matrices=False); d = vt[0]
    if d[1] > 0: d = -d                                  # point toward the neck (up)
    return c, d


def make_art(frames, b):
    f, base = frames[b['tmpl']].astype(np.float32), frames[b['base']].astype(np.float32)
    d = (np.abs(f - base).max(2) > 30).astype(np.uint8); d[:, 330:] = 0; d[470:] = 0
    n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.morphologyEx(d, cv2.MORPH_CLOSE, np.ones((5, 5))))
    k = 1 + int(np.argmax(st[1:, 4])); comp = (lab == k).astype(np.uint8)
    cs, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    fill = np.zeros_like(comp); cv2.drawContours(fill, cs, -1, 1, -1)
    c, dvec = axis_of(fill)
    a0 = float(np.degrees(np.arctan2(dvec[0], -dvec[1])))  # clockwise from up
    # derotate to exactly upright about the centroid, onto a canvas centred on the centroid
    D = 340; M = cv2.getRotationMatrix2D((float(c[0]), float(c[1])), a0, 1.0)  # +a0 = CCW in cv2 → undo clockwise tilt
    M[:, 2] += (D / 2 - c[0], D / 2 - c[1])
    art = cv2.warpAffine(f, M, (D, D), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    am = cv2.warpAffine(fill.astype(np.float32), M, (D, D), flags=cv2.INTER_LINEAR)
    hard = am > 0.5
    ys, xs = np.nonzero(hard)
    top = ys.min()
    row = np.nonzero(hard[top + 1])[0]
    tip = np.array([(row.min() + row.max()) / 2.0, float(top)])   # art-canvas px
    # soft mask with 2px margin so the outline's outer anti-aliased edge vs background counts
    soft = cv2.GaussianBlur(cv2.dilate(hard.astype(np.uint8), np.ones((5, 5))).astype(np.float32), (0, 0), 1.0)
    return dict(art=art, mask=soft, hard=hard, tip=tip, a0=a0, centroid=c, D=D, fill=fill)


def warp_tpl(A, angle, sx=1.0, sy=1.0, size=330):
    """Canvas (size×size) with the art rotated/scaled about the art canvas centre → canvas centre."""
    D = A['D']; a = np.radians(angle); R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    L = R @ np.diag([sx, sy]); t = np.array([size / 2, size / 2]) - L @ np.array([D / 2, D / 2])
    M = np.hstack([L, t[:, None]]).astype(np.float32)
    T = cv2.warpAffine(A['art'], M, (size, size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    W = cv2.warpAffine(A['mask'], M, (size, size), flags=cv2.INTER_LINEAR)
    return T, W


class Frame:
    def __init__(self, img):
        I = np.zeros((ROI_H + PADT, ROI_W + PADL, 3), np.float32); I[PADT:, PADL:] = img / 255.0
        V = np.zeros(I.shape[:2], np.float32); V[PADT:, PADL:] = 1
        self.V, self.VI, self.VI2 = V, [I[..., c] for c in range(3)], [I[..., c] ** 2 for c in range(3)]


def score_map(F, T, W, x0, y0, x1, y1):
    """E over template-centre positions (x0..x1, y0..y1) in padded coords."""
    s = W.shape[0]; h = s // 2
    ys, ye, xs, xe = y0 - h, y1 - h + s, x0 - h, x1 - h + s
    if ys < 0 or xs < 0 or ye > F.V.shape[0] or xe > F.V.shape[1]: return None
    Vr = F.V[ys:ye, xs:xe]
    N = cv2.matchTemplate(Vr, W, cv2.TM_CCORR)
    E = np.zeros_like(N)
    for c in range(3):
        Tc = T[..., c] / 255.0
        E += cv2.matchTemplate(F.VI2[c][ys:ye, xs:xe], W, cv2.TM_CCORR) \
             - 2 * cv2.matchTemplate(F.VI[c][ys:ye, xs:xe], W * Tc, cv2.TM_CCORR) \
             + cv2.matchTemplate(Vr, W * Tc * Tc, cv2.TM_CCORR)
    vis = N / W.sum()
    E = E / (3 * np.maximum(N, 1e-3))
    E[vis < 0.04] = 9.0
    return E, vis


def search(F, A, cx, cy, angles, scales, win, size=330, aniso=False):
    best = None
    x0, x1 = int(round(cx)) + PADL - win[0], int(round(cx)) + PADL + win[0]
    y0, y1 = int(round(cy)) + PADT - win[1], int(round(cy)) + PADT + win[1]
    x0, y0 = max(x0, size // 2), max(y0, size // 2)
    x1 = min(x1, F.V.shape[1] - size + size // 2); y1 = min(y1, F.V.shape[0] - size + size // 2)
    for ang in angles:
        for sc in scales:
            sx, sy = (sc if not aniso else sc[0]), (sc if not aniso else sc[1])
            T, W = warp_tpl(A, ang, sx, sy, size)
            r = score_map(F, T, W, x0, y0, x1, y1)
            if r is None: continue
            E, vis = r; py, px = np.unravel_index(np.argmin(E), E.shape); e = E[py, px]
            if best is None or e < best[0]:
                dx = dy = 0.0
                if 0 < px < E.shape[1] - 1:
                    a, b_, c = E[py, px - 1], e, E[py, px + 1]; den = a - 2 * b_ + c
                    if den > 1e-9: dx = 0.5 * (a - c) / den
                if 0 < py < E.shape[0] - 1:
                    a, b_, c = E[py - 1, px], e, E[py + 1, px]; den = a - 2 * b_ + c
                    if den > 1e-9: dy = 0.5 * (a - c) / den
                best = (float(e), x0 + px + dx - PADL, y0 + py + dy - PADT, float(ang), sc, float(vis[py, px]))
    return best


def refine_angle(F, A, g, step, span, scales, win=(3, 3)):
    angs = np.arange(g[3] - span, g[3] + span + 1e-6, step)
    r = search(F, A, g[1], g[2], angs, scales, win)
    # parabola over angle at the best position/scale
    es = []
    for a in (r[3] - step, r[3], r[3] + step):
        rr = search(F, A, r[1], r[2], [a], [r[4]], (1, 1)); es.append(rr[0])
    den = es[0] - 2 * es[1] + es[2]
    da = 0.5 * (es[0] - es[2]) / den * step if den > 1e-12 else 0.0
    return (r[0], r[1], r[2], r[3] + float(np.clip(da, -step, step)), r[4], r[5])


def track(frames, name, b, A):
    Fc = {}
    def F(i):
        if i not in Fc: Fc[i] = Frame(frames[i])
        return Fc[i]
    seed = b['tmpl']
    c = A['centroid']
    g = search(F(seed), A, c[0], c[1], np.arange(-6, 7, 2), [1.0], (12, 12))
    g = refine_angle(F(seed), A, g, 0.5, 2, [0.98, 1.0, 1.02])
    rec = {seed: g}
    for direction in (1, -1):
        prev, vel, om, i = g, np.zeros(2), 0.0, seed + direction
        while b['first'] <= i <= b['last']:
            px, py, pa = prev[1] + vel[0], prev[2] + vel[1], prev[3] + om
            sp = float(np.abs(vel).max()); win = (int(14 + 1.5 * sp), int(14 + 1.5 * sp))
            span = 8 + 1.2 * abs(om)
            r = search(F(i), A, px, py, np.arange(pa - span, pa + span + 1e-6, 2.0), [1.0], win)
            r = refine_angle(F(i), A, r, 0.5, 1.5, [1.0])
            if r[5] < 0.05: break
            vel = np.array([r[1] - prev[1], r[2] - prev[2]]); om = r[3] - prev[3]
            prev = r; rec[i] = r; i += direction
            Fc.pop(i - 3 * direction, None)
    return {i: rec[i] for i in sorted(rec)}


def to_anchor(A, r):
    """template-centre pose → mouth-tip anchor."""
    a = np.radians(r[3]); R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    off = A['tip'] - np.array([A['D'] / 2, A['D'] / 2])
    p = np.array([r[1], r[2]]) + r[4] * (R @ off)
    return p, off


def main():
    t0 = time.time(); frames = read_frames(); print('frames', len(frames), time.time() - t0)
    res = {}
    for name, b in BOTTLES.items():
        A = make_art(frames, b)
        cv2.imwrite(str(OUT / f'art-{name}-upright-raw.png'), np.clip(A['art'], 0, 255).astype(np.uint8))   # clip: cubic overshoot
        np.save(str(OUT / f'.cache-art-{name}.npy'), np.dstack([A['art'], A['mask'] * 255]).astype(np.float32))
        t0 = time.time(); tr = track(frames, name, b, A); print(name, len(tr), 'frames tracked', round(time.time() - t0, 1), 's')
        rows = []
        for i, r in tr.items():
            p, off = to_anchor(A, r)
            rows.append([i, round(float(p[0]), 2), round(float(p[1]), 2), round(r[3], 2), round(float(r[4]), 3),
                         round(float(np.sqrt(r[0]) * 255), 2), round(r[5], 3), round(r[1], 2), round(r[2], 2)])
        # squash/stretch check: anisotropic scale (sx across, sy along the axis) at the tracked pose
        aniso = []
        for i, r in list(tr.items())[::2]:
            if r[5] < 0.97: continue
            Fi = Frame(frames[i]); combos = [(a, b) for a in (0.96, 0.98, 1.0, 1.02, 1.04) for b in (0.96, 0.98, 1.0, 1.02, 1.04)]
            best = search(Fi, A, r[1], r[2], [r[3]], combos, (3, 3), aniso=True)
            aniso.append([i, best[4][0], best[4][1], round(float(np.sqrt(r[0]) * 255), 2), round(float(np.sqrt(best[0]) * 255), 2)])
        res_aniso = aniso
        res[name] = dict(aniso_check=res_aniso, art_canvas=A['D'], art_tip=A['tip'].tolist(), template_axis_deg=round(A['a0'], 3),
                         tip_from_centre=(A['tip'] - A['D'] / 2).tolist(), rows=rows, **{k: b[k] for k in b})
        print(name, rows[0], rows[-1], 'max rmse', max(r[5] for r in rows))
    (OUT / '.cache-bottle-track.json').write_text(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
