"""Bottle art measurements for vector re-drawing (upright, mouth tip = origin, x right, y down).

Input: upright art canvases cut by bottle_track.py (template frame derotated by the measured axis
angle, full resolution).  Output: art-<name>-upright-x4.png (4x nearest-neighbour crop),
art-<name>-spec.png (annotated 4x), and .cache-art.json with silhouette width profile, outline
contour, ink thickness, colour clusters, label/highlight/text geometry.

usage: uv run -q --with opencv-python-headless --with numpy python scripts/v4/bottle_art.py
"""
import json
from pathlib import Path
import cv2, numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '01_레퍼런스/analysis-v4/bottles'
TR = json.loads((OUT / '.cache-bottle-track.json').read_text())
BG = np.array([0xf5, 0xf9, 0xfa], float)   # BGR of the cream paper
hexs = lambda bgr: '#%02x%02x%02x' % tuple(int(round(v)) for v in np.asarray(bgr)[::-1])


def measure(name):
    a = np.load(str(OUT / f'.cache-art-{name}.npy'))
    img = np.clip(a[..., :3], 0, 255).astype(np.uint8); region = a[..., 3] > 60
    tip = np.array(TR[name]['art_tip'])
    f = img.astype(float)
    dist = np.linalg.norm(f - BG, axis=2)
    sil = (dist > 22) & region
    sil = cv2.morphologyEx(sil.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3)))
    cs, _ = cv2.findContours(sil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    S = np.zeros_like(sil); cv2.drawContours(S, [c], -1, 1, -1); S = S > 0
    ys, xs = np.nonzero(S)
    wrow = S.sum(1); top = int(np.argmax(wrow >= 20)); bot = int(len(wrow) - 1 - np.argmax(wrow[::-1] >= 20))
    S[:top] = False; S[bot + 1:] = False
    tipx = float(tip[0])                                     # same x as the tracking anchor
    O = np.array([tipx, top], float)                       # origin = silhouette top centre
    # width profile along the axis
    prof = []
    for y in range(top, bot + 1):
        row = np.nonzero(S[y])[0]
        if len(row): prof.append([int(y - top), round(float(row.min() - tipx), 1), round(float(row.max() - tipx), 1)])
    W = np.array([p[2] - p[1] + 1 for p in prof])
    # features from the width profile
    yy = np.array([p[0] for p in prof])
    lipH = int(np.argmax(W[:30] < W[:6].max() - 3)) if np.any(W[:30] < W[:6].max() - 3) else None
    neck_zone = (yy > (lipH or 10)) & (yy < 100)
    neck_w = float(np.median(W[neck_zone][:25])) if neck_zone.any() else None
    bodyW = float(np.median(W[(yy > 150) & (yy < 240)]))
    sh0 = int(yy[np.argmax((yy > 30) & (W > neck_w + 4))])          # shoulder starts widening
    sh1 = int(yy[np.argmax((yy > 30) & (W > bodyW - 3))])           # reaches body width
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(float)
    sat = f.max(2) - f.min(2)
    ink = (gray < 85) & (sat < 45) & S
    # ink thickness on the body sides (rows 160-250): run lengths of ink touching each side
    th = []
    for y in range(top + 160, top + 250, 3):
        row = ink[y]; xsr = np.nonzero(S[y])[0]
        if not len(xsr): continue
        for side in (0, 1):
            seq = row[xsr.min():xsr.min() + 12] if side == 0 else row[xsr.max() - 11:xsr.max() + 1][::-1]
            k = np.nonzero(seq)[0]
            if len(k):
                run = 0; j = k[0]
                while j < len(seq) and seq[j]: run += 1; j += 1
                th.append((side, k[0], run))
    th = np.array(th)
    # interior classes
    er = cv2.erode(S.astype(np.uint8), np.ones((7, 7))) > 0
    er11 = cv2.erode(S.astype(np.uint8), np.ones((13, 13))) > 0
    rowsY = np.arange(S.shape[0])[:, None]
    colsX = np.arange(S.shape[1])[None, :]
    label_px = er11 & (f.min(2) > 200) & (sat < 45) & (rowsY > top + 140) & (rowsY < top + 245) & (np.abs(colsX - tipx) < 38)
    n, lab, st, cen = cv2.connectedComponentsWithStats(cv2.morphologyEx(label_px.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9))))
    k = 1 + int(np.argmax(st[1:, 4]))
    L = lab == k
    Lc, _ = cv2.findContours(L.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    rect = cv2.minAreaRect(max(Lc, key=cv2.contourArea))
    lx, ly, lw, lh = cv2.boundingRect(max(Lc, key=cv2.contourArea))
    Lfill = np.zeros_like(S, np.uint8); cv2.drawContours(Lfill, Lc, -1, 1, -1); Lfill = Lfill > 0
    label_bg = np.median(f[L & label_px], 0)
    # text = non-label-bg pixels well inside the label rect
    inner = cv2.erode(Lfill.astype(np.uint8), np.ones((9, 9))) > 0
    txt = inner & (np.linalg.norm(f - label_bg, axis=2) > 60)
    n2, lab2, st2, cen2 = cv2.connectedComponentsWithStats(txt.astype(np.uint8))
    glyphs = [st2[j] for j in range(1, n2) if st2[j, 4] >= 4]
    lines = []
    if glyphs:
        gy = sorted(glyphs, key=lambda s: s[1] + s[3] / 2)
        cur = [gy[0]]
        for s in gy[1:]:
            if (s[1] + s[3] / 2) - (cur[-1][1] + cur[-1][3] / 2) > 8: lines.append(cur); cur = [s]
            else: cur.append(s)
        lines.append(cur)
    text_lines = []
    for ln in lines:
        x0 = min(s[0] for s in ln); y0 = min(s[1] for s in ln); x1 = max(s[0] + s[2] for s in ln); y1 = max(s[1] + s[3] for s in ln)
        m = np.zeros_like(txt); m[y0:y1, x0:x1] = txt[y0:y1, x0:x1]
        darkest = f[m][np.argsort(gray[m])[:max(3, m.sum() // 3)]]
        text_lines.append(dict(bbox_xywh=[round(x0 - tipx, 1), int(y0 - top), int(x1 - x0), int(y1 - y0)],
                               cap_height_px=int(y1 - y0), colour=hexs(np.median(darkest, 0))))
    # label border ink (ring just outside the label bg)
    ring = (cv2.dilate(Lfill.astype(np.uint8), np.ones((7, 7))) > 0) & ~Lfill
    border = ring & (gray < np.median(gray[ring]) - 20)
    body_fill_zone = er & ~cv2.dilate(Lfill.astype(np.uint8), np.ones((9, 9))).astype(bool) & ~ink
    body_rows = (np.arange(S.shape[0])[:, None] > top + 100) & (np.arange(S.shape[0])[:, None] < bot - 10)
    fz = body_fill_zone & body_rows
    fill = np.median(f[fz], 0)
    # highlight stripe: brighter than fill inside the body (left side), elongated vertically
    brighter = fz & (gray > np.median(gray[fz]) + 18) & (colsX < tipx - 10)      # stripe sits on the left half
    n3, lab3, st3, _ = cv2.connectedComponentsWithStats(brighter.astype(np.uint8))
    hl = None
    cands = [j for j in range(1, n3) if st3[j, 3] >= 15 and st3[j, 3] >= 3 * st3[j, 2] and st3[j, 2] <= 8]
    if cands:
        j = max(cands, key=lambda j: st3[j, 3]); x, y, w, h, ar = st3[j]
        hl = dict(x_from_axis=round(float(x + w / 2 - tipx), 1), y0=int(y - top), y1=int(y + h - top), width=int(w),
                  colour=hexs(np.median(f[lab3 == j], 0)))
    # neck fill + lip ring fill
    neckz = er & (np.arange(S.shape[0])[:, None] > top + 25) & (np.arange(S.shape[0])[:, None] < top + 80) & ~ink
    # fill-vs-outline misregistration: centroid of fill-coloured pixels vs centroid of silhouette, body rows
    fillcol = (np.linalg.norm(f - fill, axis=2) < 40) & body_rows & ~Lfill
    fx = float(np.nonzero(fillcol)[1].mean() - np.nonzero(S & body_rows)[1].mean())
    # k-means colour clusters inside the silhouette
    P = f[S].astype(np.float32)
    _, lb, centers = cv2.kmeans(P, 7, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 3, cv2.KMEANS_PP_CENTERS)
    share = np.bincount(lb.ravel(), minlength=7) / len(lb)
    clusters = sorted([[hexs(centers[j]), round(float(share[j]), 3)] for j in range(7)], key=lambda r: -r[1])
    # outline contour (outer edge of ink), tip-relative, simplified
    poly = cv2.approxPolyDP(c, 0.8, True)[:, 0, :].astype(float) - O
    res = dict(
        origin_note='art px, origin = mouth tip (top centre of lip ring), +y toward the base, upright',
        tip_in_track_vs_silhouette=[round(float(tip[0] - tipx), 2), round(float(tip[1] - top), 2)],
        total_length=int(bot - top + 1), body_width=round(bodyW, 1),
        lip_ring=dict(height=lipH, width=float(W[:max(lipH or 6, 1)].max())),
        neck=dict(y0=lipH, y1=sh0, width=neck_w),
        shoulder=dict(y0=sh0, y1=sh1),
        body=dict(y0=sh1, y1=int(bot - top), width=bodyW),
        width_profile_every_2px=[p for p in prof if p[0] % 2 == 0],
        outline_polygon=[[round(float(x), 1), round(float(y), 1)] for x, y in poly],
        ink=dict(colour=hexs(np.median(f[ink], 0)), side_thickness_px_median=float(np.median(th[:, 2])) if len(th) else None,
                 left_px=float(np.median(th[th[:, 0] == 0, 2])) if len(th) else None, right_px=float(np.median(th[th[:, 0] == 1, 2])) if len(th) else None),
        fill=dict(body=hexs(fill), neck=hexs(np.median(f[neckz], 0)) if neckz.any() else None,
                  fill_minus_outline_centroid_dx=round(fx, 2)),
        highlight=hl,
        label=dict(rect_center=[round(float(rect[0][0] - tipx), 1), round(float(rect[0][1] - top), 1)],
                   rect_size=[round(float(rect[1][0]), 1), round(float(rect[1][1]), 1)], rect_angle_cv=round(float(rect[2]), 1),
                   bbox_xywh=[round(float(lx - tipx), 1), int(ly - top), int(lw), int(lh)],
                   bg=hexs(label_bg), border=hexs(np.median(f[border], 0)) if border.any() else None),
        text_lines=text_lines,
        colour_clusters=clusters)
    # crops: 4x nearest-neighbour upright crop + annotated spec
    x0, x1, y0, y1 = int(tipx - 60), int(tipx + 60), max(0, top - 8), min(img.shape[0], bot + 9)
    crop = img[y0:y1, x0:x1]
    big = cv2.resize(crop, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(str(OUT / f'art-{name}-upright-x4.png'), big)
    spec = cv2.resize(crop, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    to = lambda x, y: (int(round((x + tipx - x0) * 4)), int(round((y + top - y0) * 4)))
    cv2.polylines(spec, [np.array([to(*p) for p in poly])], True, (255, 0, 255), 1, cv2.LINE_AA)
    cv2.circle(spec, to(0, 0), 5, (0, 0, 255), -1)
    for yv, col in ((lipH, (0, 160, 0)), (sh0, (0, 160, 0)), (sh1, (0, 160, 0))):
        if yv is not None: cv2.line(spec, to(-50, yv), to(50, yv), col, 1)
    bx = res['label']['bbox_xywh']; cv2.rectangle(spec, to(bx[0], bx[1]), to(bx[0] + bx[2], bx[1] + bx[3]), (255, 120, 0), 1)
    for tl in text_lines:
        b = tl['bbox_xywh']; cv2.rectangle(spec, to(b[0], b[1]), to(b[0] + b[2], b[1] + b[3]), (0, 200, 255), 1)
    if hl: cv2.line(spec, to(hl['x_from_axis'], hl['y0']), to(hl['x_from_axis'], hl['y1']), (0, 255, 0), 1)
    for yv in range(0, int(bot - top), 20):
        cv2.putText(spec, str(yv), (2, to(0, yv)[1] + 4), 0, 0.4, (90, 90, 90), 1, cv2.LINE_AA)
    cv2.imwrite(str(OUT / f'art-{name}-spec.png'), spec)
    return res, S, O


def main():
    out = {}; masks = {}
    for name in TR:
        r, S, O = measure(name); out[name] = r; masks[name] = (S, O)
        print(name, json.dumps({k: r[k] for k in ('total_length', 'body_width', 'lip_ring', 'neck', 'shoulder', 'ink', 'fill', 'highlight', 'label', 'text_lines')}))
    # silhouette agreement between bottles (aligned at the tip)
    ref, Or = masks['gin']
    for name, (S, O) in masks.items(): print(name, 'origin', O, S.sum())
    for name, (S, O) in masks.items():
        M = np.float32([[1, 0, Or[0] - O[0]], [0, 1, Or[1] - O[1]]])
        Sw = cv2.warpAffine(S.astype(np.uint8), M, (S.shape[1], S.shape[0])) > 0
        out[name]['silhouette_iou_vs_gin'] = round(float((Sw & ref).sum() / (Sw | ref).sum()), 3)
        print(name, 'IoU vs gin', out[name]['silhouette_iou_vs_gin'])
    (OUT / '.cache-art.json').write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
