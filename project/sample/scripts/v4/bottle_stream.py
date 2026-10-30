"""Pour streams + droplets/bubbles of the three bottles, per frame, from the reference MP4.

Stream pixels = pixels new against BOTH a pre-pour frame and a post-pour frame (so the rising
liquid, which matches the pre frame above the surface and the post frame below it, cancels),
each compared with a boil-tolerant minimum over a 5×5 neighbourhood of the base frame, minus the
tracked bottle silhouette.  The stream is then traced from the bottle mouth (or, once detached,
from its top end) with perpendicular run profiles: centre + outer width (ink outline included)
every 3 px, resampled to 12 points by arc length.  Small round leftovers near the stream end are
droplets (solid colour) or bubbles (ink ring).

usage: uv run -q --with opencv-python-headless --with numpy python scripts/v4/bottle_stream.py
(needs 01_레퍼런스/analysis-v4/bottles/.cache-bottle-track.json from bottle_track.py)
"""
import json
from pathlib import Path
import cv2, numpy as np

ROOT = Path(__file__).resolve().parents[2]
VIDEO = str(ROOT / '01_레퍼런스/original.mp4')
OUT = ROOT / '01_레퍼런스/analysis-v4/bottles'
TR = json.loads((OUT / '.cache-bottle-track.json').read_text())

# pre: last frame without any stream; post: first frame after stream + drops are gone
STREAMS = {'gin': dict(pre=216, post=301), 'campari': dict(pre=366, post=451), 'vermouth': dict(pre=516, post=601)}
X0, X1, Y0, Y1 = 150, 560, 250, 830          # stream region (mouth → glass bottom)
THR = 30
NPTS = 12


def read(frames_needed):
    cap = cv2.VideoCapture(VIDEO); fr = {}; i = 0; last = max(frames_needed)
    while i <= last:
        ok, f = cap.read()
        if not ok: break
        if i in frames_needed: fr[i] = f[Y0:Y1, X0:X1].astype(np.int16)
        i += 1
    return fr


def newness(I, B, r=2):
    best = None
    Bp = np.pad(B, ((r, r), (r, r), (0, 0)), mode='edge')
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r * r + 1: continue
            Bs = Bp[r + dy:r + dy + I.shape[0], r + dx:r + dx + I.shape[1]]
            d = np.abs(I - Bs).max(2)
            best = d if best is None else np.minimum(best, d)
    return best


def bottle_mask(name, i, shape):
    art = np.load(str(OUT / f'.cache-art-{name}.npy')); W = art[..., 3] / 255.0
    rows = {r[0]: r for r in TR[name]['rows']}
    if i not in rows: return np.zeros(shape, bool), None
    r = rows[i]; D = TR[name]['art_canvas']; a = np.radians(r[3]); s = r[4]
    R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]]) * s
    c = np.array([r[7], r[8]]) - [X0, Y0]
    t = c - R @ np.array([D / 2, D / 2])
    M = np.hstack([R, t[:, None]]).astype(np.float32)
    m = cv2.warpAffine(W.astype(np.float32), M, (shape[1], shape[0])) > 0.2
    tip = np.array([r[1] - X0, r[2] - Y0]); axis = np.array([np.sin(a), -np.cos(a)])
    return cv2.dilate(m.astype(np.uint8), np.ones((7, 7))) > 0, (tip, axis)


def profile_run(C, q, n, half=16, near=8):
    ts = np.arange(-half, half + 1)
    P = q[None, :] + ts[:, None] * n[None, :]
    xi, yi = np.round(P[:, 0]).astype(int), np.round(P[:, 1]).astype(int)
    ok = (xi >= 0) & (yi >= 0) & (xi < C.shape[1]) & (yi < C.shape[0])
    v = np.zeros(len(ts), bool); v[ok] = C[yi[ok], xi[ok]]
    runs = []; k = 0
    while k < len(v):
        if v[k]:
            j = k
            while j + 1 < len(v) and v[j + 1]: j += 1
            runs.append((ts[k], ts[j])); k = j + 1
        else: k += 1
    if not runs: return None
    best = min(runs, key=lambda r: 0 if r[0] <= 0 <= r[1] else min(abs(r[0]), abs(r[1])))
    if not (best[0] <= 0 <= best[1]) and min(abs(best[0]), abs(best[1])) > near: return None
    return best


def trace(C, p, d):
    pts, ws = [], []
    r = profile_run(C, p, np.array([-d[1], d[0]]))
    if r is None: return None
    n = np.array([-d[1], d[0]]); p = p + n * (r[0] + r[1]) / 2; pts.append(p.copy()); ws.append(r[1] - r[0] + 1)
    miss, wide, gap = 0, 0, 0
    for _ in range(400):
        found = None
        tries = ((0, 12, -12, 25, -25, 40) if len(pts) < 8 else (0, 8, -8, 15, -15)) if gap == 0 else (0, 8, -8)
        for dt in tries:
            a = np.radians(dt); dd = np.array([d[0] * np.cos(a) - d[1] * np.sin(a), d[0] * np.sin(a) + d[1] * np.cos(a)])
            q = p + 3 * (gap + 1) * dd; n = np.array([-dd[1], dd[0]]); r = profile_run(C, q, n, near=8)
            if r is not None:
                w = r[1] - r[0] + 1
                if gap and len(ws) >= 4 and not (0.5 * np.median(ws) <= w <= 1.6 * np.median(ws) + 2): continue
                found = (q, n, r, dd); break
        if found is None:
            gap += 1
            if gap > 7: break                                   # bridge ≤ 21 px (ink lines hidden by rim/ice ink)
            continue
        gap = 0
        q, n, r, dd = found; w = r[1] - r[0] + 1
        wm = np.median(ws[-12:]) if len(ws) >= 4 else None
        if wm is not None and w > max(2.2 * wm + 3, 26):
            wide += 1
            if wide >= 5: break                                 # >15 px of wide runs = liquid body, not a crossing line
            c = q                                              # crossing a horizontal mark: keep heading
        elif wm is not None and len(ws) >= 6 and w < 0.6 * wm:
            c = q                                              # band broken by a crossing ink line: keep heading
        else:
            wide = 0; c = q + n * (r[0] + r[1]) / 2
            ws.append(w)
        nd = c - p; nd /= np.linalg.norm(nd) + 1e-9
        if len(pts) > 6 and nd[1] < 0.3: break                 # a falling stream never turns back up
        d = 0.5 * d + 0.5 * nd; d /= np.linalg.norm(d)
        pts.append(c.copy()); p = c
    while wide and len(pts) > 1: pts.pop(); wide -= 1           # drop the trailing wide probe
    # prune a sideways hook at the end (surface ring, drops or an ice edge grabbed by the probe)
    while len(pts) > 8:
        P = np.array(pts); seg = np.diff(P, axis=0); seg /= np.linalg.norm(seg, axis=1)[:, None] + 1e-9
        ref = seg[-7:-2].mean(0); ref /= np.linalg.norm(ref)
        if np.degrees(np.arccos(np.clip(seg[-1] @ ref, -1, 1))) > 20: pts.pop(); ws.pop() if len(ws) > 2 else None
        else: break
    P = np.array(pts)
    if len(P) >= 7:                                            # light smoothing (5-tap) of the centre line
        Q = P.copy()
        for k in range(2, len(P) - 2): Q[k] = P[k - 2:k + 3].mean(0)
        pts = list(Q)
    d = pts[-1] - pts[-3] if len(pts) >= 3 else d; d = d / (np.linalg.norm(d) + 1e-9)
    pts.append(pts[-1] + d * 0.01)                         # keep final heading for extend_raw
    widths = np.interp(np.arange(len(pts)), np.linspace(0, len(pts) - 1, len(ws)), ws) if len(ws) > 1 else np.full(len(pts), ws[0])
    return np.array(pts), widths


def cross_section(I, c, n, half=12.0, step=0.25):
    """Perpendicular profile of the raw frame at c (region px): ink edges, core, colours.
    n points to the stream's left when looking downstream (left = -n side is reported as 'a')."""
    ts = np.arange(-half, half + 1e-6, step)
    P = c[None, :] + ts[:, None] * n[None, :]
    mx = np.float32(P[:, 0]).reshape(1, -1); my = np.float32(P[:, 1]).reshape(1, -1)
    prof = cv2.remap(I.astype(np.float32), mx, my, cv2.INTER_LINEAR)[0]          # BGR
    gray = prof @ np.array([0.114, 0.587, 0.299]); sat = prof.max(1) - prof.min(1)
    ink = (gray < 115) & (sat < 60)
    k0 = int(np.argmin(np.abs(ts)))
    # nearest ink run on each side of the centre (search outward up to 10 px)
    def side(sgn):
        idx = range(k0, len(ts)) if sgn > 0 else range(k0, -1, -1)
        start = None
        for j in idx:
            if abs(ts[j]) > 10: break
            if ink[j] and start is None: start = j
            if start is not None and not ink[j]: return start, j - sgn
        return (start, start) if start is not None else None
    L, R = side(-1), side(1)
    if L is None or R is None: return None
    outer = (ts[R[1]] - ts[L[1]]) + step                   # outer edge to outer edge
    inkA = abs(ts[L[1]] - ts[L[0]]) + step; inkB = abs(ts[R[1]] - ts[R[0]]) + step
    core = max(0.0, ts[R[0]] - ts[L[0]] - step)
    cm = (ts > ts[L[0]] + 0.5) & (ts < ts[R[0]] - 0.5)
    if cm.sum() < 2: return None
    cp = prof[cm]; cg = gray[cm]
    return dict(outer=outer, core=core, inkA=inkA, inkB=inkB, centre_off=(ts[L[1]] + ts[R[1]]) / 2,
                fill=np.median(cp, 0), light=cp[np.argmax(cg)], light_pos=float((ts[cm][np.argmax(cg)] - ts[L[0]]) / max(core, 1e-3)),
                ink=np.median(prof[ink & (np.abs(ts) <= 10)], 0))


def extend_raw(I, pts, ws, ref_fill, max_steps=40):
    """Continue the traced band on the raw frame (inside liquid / over ice the new-pixel mask fails):
    accept steps whose cross-section shows two ink edges 9-17 px apart around a core of stream colour."""
    pts = list(pts); ws = list(ws)
    d = pts[-1] - pts[-3] if len(pts) >= 3 else np.array([0, 1.0]); d = d / (np.linalg.norm(d) + 1e-9)
    p = pts[-1]; fails = 0; added = 0
    for _ in range(max_steps):
        q = p + 2 * d; n = np.array([-d[1], d[0]])
        cs = cross_section(I, q, n)
        if cs is None or not (9 <= cs['outer'] <= 17) or abs(cs['centre_off']) > 3 or np.linalg.norm(cs['fill'] - ref_fill) > 70:
            fails += 1
            if fails >= 2: break
            p = q; continue
        fails = 0; c = q + n * cs['centre_off']
        nd = c - pts[-1]; nd /= np.linalg.norm(nd) + 1e-9
        if nd[1] < 0.5: break
        d = 0.7 * d + 0.3 * nd; d /= np.linalg.norm(d)
        pts.append(c); ws.append(cs['outer']); p = c; added += 1
    return np.array(pts), np.array(ws), added


def resample(pts, ws, n=NPTS):
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    if seg[-1] < 1: return None
    t = np.linspace(0, seg[-1], n)
    x, y = np.interp(t, seg, pts[:, 0]), np.interp(t, seg, pts[:, 1])
    k = max(1, len(ws) // n); wsm = np.convolve(ws, np.ones(k) / k, mode='same') if len(ws) > k else ws
    w = np.interp(t, seg, wsm)
    return np.stack([x, y, w], 1), float(seg[-1])


XS = {n: [] for n in STREAMS}


def main():
    allres = {}
    for name, sp in STREAMS.items():
        rows = TR[name]['rows']; fs = [r[0] for r in rows]
        need = set(range(sp['pre'] - 2, sp['post'] + 3)) | {sp['pre'], sp['post']}
        fr = read(need)
        Bpre, Bpost = fr[sp['pre']], fr[sp['post']]
        res = {}; last_end = [None]; last_fill = [None]; last_entry = [None]
        for i in range(sp['pre'] - 2, sp['post'] + 3):
            I = fr[i]
            S = (newness(I, Bpre) > THR) & (newness(I, Bpost) > THR)
            bm, tipax = bottle_mask(name, i, S.shape)
            S &= ~bm
            S = cv2.morphologyEx(S.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2)))
            C = cv2.morphologyEx(S, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))) > 0
            n, lab, st, cen = cv2.connectedComponentsWithStats(C.astype(np.uint8))
            comps = [k for k in range(1, n) if st[k, 4] >= 12]
            stream, attached = None, False
            # 1) attached stream: band starting at the mouth
            if tipax is not None:
                tip, ax = tipax
                yy, xx = np.nonzero(C)
                if len(xx):
                    dist = np.hypot(xx - tip[0], yy - tip[1]); j = int(np.argmin(dist))
                    if dist[j] < 14:
                        k = lab[yy[j], xx[j]]
                        tr = trace(C, np.array([xx[j], yy[j]], float), ax / np.linalg.norm(ax))   # whole mask: bridges ink gaps
                        if tr is not None and len(tr[0]) >= 2: stream, attached, sk = tr, True, k
            # 1b) attached trace broke off early: continue from the top of the tallest band below its end
            if stream is not None and attached:
                pe = stream[0][-1]
                cand = [k for k in comps if st[k, 3] >= 40 and st[k, 1] > pe[1] - 5 and st[k, 1] - pe[1] < 60
                        and abs(cen[k][0] - pe[0]) < 60]
                L0 = np.sum(np.linalg.norm(np.diff(stream[0], axis=0), axis=1))
                if cand and L0 < 120:
                    k = max(cand, key=lambda k: st[k, 3]); ys, xs = np.nonzero(lab == k); j = int(np.argmin(ys))
                    tr2 = trace(C, np.array([xs[j], ys[j]], float), np.array([0.2, 1.0]) / np.hypot(0.2, 1.0))
                    if tr2 is not None and len(tr2[0]) >= 4:
                        stream = (np.vstack([stream[0], tr2[0]]), np.r_[stream[1], tr2[1]])
            # 2) detached piece: tallest elongated component in the glass mouth→surface band
            if stream is None:
                cand = [k for k in comps if st[k, 3] >= 14 and st[k, 3] >= 2.0 * st[k, 2]]
                if cand:
                    k = max(cand, key=lambda k: st[k, 3]); ys, xs = np.nonzero(lab == k); j = int(np.argmin(ys))
                    tr = trace(lab == k, np.array([xs[j], ys[j]], float), np.array([0.0, 1.0]))
                    if tr is not None and len(tr[0]) >= 2: stream, sk = tr, k
            rec = {}
            end = None
            fills = []
            if stream is not None:
                pts, ws = stream
                for k in range(2, len(pts) - 2, 3):
                    t_ = pts[k + 1] - pts[k - 1]; t_ /= np.linalg.norm(t_) + 1e-9
                    cs_ = cross_section(I, pts[k], np.array([-t_[1], t_[0]]))
                    if cs_ is not None: fills.append(cs_['fill'])
                ext = 0; entry = pts[-1] + [X0, Y0]               # where the new-pixel band ends = surface entry
                if len(fills) >= 3 and len(pts) >= 4:
                    pts, ws, ext = extend_raw(I, pts, ws, np.median(fills, 0))
                rs = resample(pts, ws)
                if rs is not None:
                    poly, L = rs
                    xs_ = []
                    for k in range(len(poly)):
                        a_, b_ = poly[max(k - 1, 0), :2], poly[min(k + 1, len(poly) - 1), :2]
                        t_ = (b_ - a_) / (np.linalg.norm(b_ - a_) + 1e-9); n_ = np.array([-t_[1], t_[0]])
                        cs_ = cross_section(I, poly[k, :2], n_) if 0 < k < len(poly) - 1 else None
                        xs_.append(cs_)
                        if cs_ is not None: XS[name].append(cs_)
                    pts_out = []
                    for k in range(len(poly)):
                        cs_ = xs_[k]
                        pts_out.append([round(float(poly[k, 0] + X0), 1), round(float(poly[k, 1] + Y0), 1), round(float(poly[k, 2]), 1),
                                        None if cs_ is None else round(float(cs_['outer']), 2),
                                        None if cs_ is None else round(float(cs_['core']), 2),
                                        None if cs_ is None else round(float((cs_['inkA'] + cs_['inkB']) / 2), 2)])
                    poly[:, 0] += X0; poly[:, 1] += Y0; end = poly[-1, :2]
                    rec['stream'] = dict(attached=attached, length=round(L, 1), raw_extension_px=2 * ext,
                                         band_end=[round(float(entry[0]), 1), round(float(entry[1]), 1)], pts=pts_out)
                    last_entry[0] = entry
            # droplets / bubbles: small compact blobs (not the stream), near the stream end / mouth-surface band
            drops = []
            gray = I[..., 0] * 0.114 + I[..., 1] * 0.587 + I[..., 2] * 0.299
            sat = I.max(2) - I.min(2)
            band = np.zeros(S.shape, np.uint8)
            if 'stream' in rec:                                     # cut the stream band out (drops touch it)
                Pp = np.array([q_[:3] for q_ in rec['stream']['pts']], float)
                cv2.polylines(band, [np.round(Pp[:, :2] - [X0, Y0]).astype(np.int32)], False, 1, max(3, int(round(np.median(Pp[:, 2]))) - 4))
            if end is not None: last_end[0] = end
            ref = end if end is not None else last_end[0]
            # blob detector: normalised correlation of the darkness map with discs (drops) and rings (bubbles)
            dk = np.clip((215 - gray) / 160, 0, 1).astype(np.float32) * (cv2.dilate(S, np.ones((3, 3))) > 0)
            if 'stream' in rec: dk[band > 0] = 0
            best = np.full(dk.shape, -1, np.float32); kind = np.zeros(dk.shape, np.int8); rad = np.zeros(dk.shape, np.float32)
            for kd, rr in [(0, 1.5), (0, 2.5), (0, 3.5), (0, 4.5), (0, 5.5), (1, 2.5), (1, 3.5), (1, 4.5)]:
                R = int(np.ceil(rr)) + 3; yy_, xx_ = np.mgrid[-R:R + 1, -R:R + 1]; rho = np.hypot(xx_, yy_)
                T = np.clip(rr + 0.5 - rho, 0, 1) if kd == 0 else np.clip(1 - np.abs(rho - rr) / 0.9, 0, 1)
                Rm = cv2.matchTemplate(dk, T.astype(np.float32), cv2.TM_CCOEFF_NORMED)
                full = np.full(dk.shape, -1, np.float32); full[R:R + Rm.shape[0], R:R + Rm.shape[1]] = Rm
                upd = full > best; best[upd] = full[upd]; kind[upd] = kd; rad[upd] = rr
            peaks = (best >= cv2.dilate(best, np.ones((7, 7)))) & (best > 0.7)
            if name != 'gin': peaks[:] = False                         # red drops: distance-transform detector below
            for cy, cx in zip(*np.nonzero(peaks)):
                if ref is None or np.hypot(cx + X0 - ref[0], cy + Y0 - ref[1]) > 75 or cy + Y0 > ref[1] + 20: continue
                r0 = rad[cy, cx]; kd = kind[cy, cx]
                ring = kd == 1
                if name == 'gin' and not ring: continue                    # gin: only ink-ring bubbles
                if name != 'gin':
                    if ring: continue
                    pm = (np.hypot(*np.mgrid[-3:4, -3:4]) <= r0)
                    patch = sat[max(cy - 3, 0):cy + 4, max(cx - 3, 0):cx + 4]
                    if patch.shape != pm.shape or (patch[pm] > 45).mean() < 0.4: continue   # red drop, not grey ink
                    cc_ = I[cy - 1:cy + 2, cx - 1:cx + 2].reshape(-1, 3).mean(0)          # BGR at the centre
                    if cc_[2] - cc_[1] < 40: continue                                    # centre must be red, not ink
                    yy_, xx_ = np.mgrid[-8:9, -8:9]; rho = np.hypot(xx_, yy_)
                    gp = gray[max(cy - 8, 0):cy + 9, max(cx - 8, 0):cx + 9]
                    if gp.shape != rho.shape: continue
                    inner, ann = gp[rho <= max(r0 - 0.5, 1)].mean(), gp[(rho >= r0 + 2) & (rho <= r0 + 4.5)]
                    if np.median(ann) - inner < 35: continue                 # must be a dark dot on lighter ground
                # refine radius from the darkness mass (discs) or keep ring radius
                if not ring:
                    win = dk[max(cy - 7, 0):cy + 8, max(cx - 7, 0):cx + 8]
                    lab_, n_ = None, None
                    m_ = (win > 0.35).astype(np.uint8); nn, ll, ss, cc = cv2.connectedComponentsWithStats(m_)
                    kk = ll[min(cy, 7), min(cx, 7)]
                    if kk == 0: continue
                    area = ss[kk, 4]
                    if area > 120 or max(ss[kk, 2], ss[kk, 3]) > 1.7 * min(ss[kk, 2], ss[kk, 3]) + 1: continue
                    r0 = float(np.sqrt(area / np.pi)); ccx, ccy = cc[kk] + [max(cx - 7, 0), max(cy - 7, 0)]
                else:
                    ccx, ccy = float(cx), float(cy)
                if 'stream' in rec:                                       # centre outside the stream band
                    sd = min(np.hypot(*(a_ + np.clip(np.dot([ccx + X0, ccy + Y0] - a_, b_ - a_) / (np.dot(b_ - a_, b_ - a_) + 1e-9), 0, 1) * (b_ - a_) - [ccx + X0, ccy + Y0]))
                             for a_, b_ in zip(Pp[:-1, :2], Pp[1:, :2]))
                    if sd < np.median(Pp[:, 2]) / 2 - 0.5: continue
                col = I[int(round(ccy)), int(round(ccx))][::-1]
                drops.append([round(float(ccx + X0), 1), round(float(ccy + Y0), 1), round(float(r0), 2),
                              '#%02x%02x%02x' % tuple(int(v) for v in col), 'bubble' if ring else 'drop', round(float(best[cy, cx]), 2)])
            if name != 'gin' and ref is not None:
                # solid dark-red dots: pixels at least as dark as the stream fill, new vs both bases, outside the
                # stream band; touching dots are split by distance-transform peaks (each peak = one disc).
                if fills: last_fill[0] = np.median(fills, 0)
                fref = last_fill[0]
                if fref is not None:
                    fg = float(fref @ np.array([0.114, 0.587, 0.299]))
                    band2 = np.zeros(S.shape, np.uint8)
                    if 'stream' in rec:
                        cv2.polylines(band2, [np.round(Pp[:, :2] - [X0, Y0]).astype(np.int32)], False, 1, int(round(np.median(Pp[:, 2]))) + 1)
                    Md = (cv2.dilate(S, np.ones((3, 3))) > 0) & (gray <= fg + 18) & (band2 == 0)
                    Md = cv2.morphologyEx(Md.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2)))
                    DT = cv2.distanceTransform(Md, cv2.DIST_L2, 5)
                    pk = (DT >= cv2.dilate(DT, np.ones((5, 5)))) & (DT >= 2.0)
                    taken = []
                    for cy, cx in sorted(zip(*np.nonzero(pk)), key=lambda q: -DT[q]):
                        ent = last_entry[0] if last_entry[0] is not None else ref
                        if np.hypot(cx + X0 - ent[0], cy + Y0 - ent[1]) > 75 or cy + Y0 > ent[1] + 8: continue
                        r0 = float(DT[cy, cx]) + 0.5
                        if any(np.hypot(cx - tx, cy - ty) < max(r0, tr) for tx, ty, tr in taken): continue
                        yy_, xx_ = np.mgrid[-8:9, -8:9]; rho = np.hypot(xx_, yy_)
                        mp = Md[max(cy - 8, 0):cy + 9, max(cx - 8, 0):cx + 9]
                        if mp.shape != rho.shape: continue
                        ring_ = (rho >= r0 + 1.5) & (rho <= r0 + 4)
                        if mp[ring_].mean() > 0.5: continue                 # part of a larger dark area, not a dot
                        gp = gray[cy - 8:cy + 9, cx - 8:cx + 9]
                        if np.median(gp[ring_ & (mp == 0)]) - gp[rho <= max(r0 - 1, 1)].mean() < 30 if (ring_ & (mp == 0)).any() else True: continue
                        cc_ = I[cy - 1:cy + 2, cx - 1:cx + 2].reshape(-1, 3).mean(0)
                        if cc_[2] - cc_[1] < 30: continue                     # dark ink (ice edge), not red liquid
                        taken.append((cx, cy, r0))
                        drops.append([round(float(cx + X0), 1), round(float(cy + Y0), 1), round(r0, 2),
                                      '#%02x%02x%02x' % tuple(int(v) for v in cc_[::-1]), 'drop', round(float(DT[cy, cx]), 2)])
            if drops: rec['drops'] = drops
            if rec: res[i] = rec
        xs = XS[name]
        hexs = lambda bgr: '#%02x%02x%02x' % tuple(int(round(v)) for v in np.asarray(bgr)[::-1])
        summ = dict(n_cross_sections=len(xs),
                    outer_width_median=round(float(np.median([x['outer'] for x in xs])), 2),
                    outer_width_p10_p90=[round(float(np.percentile([x['outer'] for x in xs], q)), 2) for q in (10, 90)],
                    core_width_median=round(float(np.median([x['core'] for x in xs])), 2),
                    ink_thickness_median=round(float(np.median([(x['inkA'] + x['inkB']) / 2 for x in xs])), 2),
                    ink_colour=hexs(np.median([x['ink'] for x in xs if not np.isnan(x['ink']).any()], 0)),
                    fill_colour=hexs(np.median([x['fill'] for x in xs], 0)),
                    highlight_colour=hexs(np.median([x['light'] for x in xs], 0)),
                    highlight_pos_in_core_median=round(float(np.median([x['light_pos'] for x in xs])), 2))
        print(name, summ)
        allres[name] = dict(pre=sp['pre'], post=sp['post'], cross_section_summary=summ, frames=res)
        on = sorted(k for k, v in res.items() if 'stream' in v)
        att = sorted(k for k, v in res.items() if v.get('stream', {}).get('attached'))
        print(name, 'stream frames', on[:1], on[-1:], len(on), 'attached', att[:1], att[-1:], len(att))
    (OUT / '.cache-streams.json').write_text(json.dumps(allres, indent=0))


if __name__ == '__main__':
    main()
