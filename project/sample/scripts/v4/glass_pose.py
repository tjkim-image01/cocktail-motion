"""Glass pose per frame: outline ink of the empty glass (frame 119) matched with translation
+ independent x/y scale.  Output maps reference-frame-119 coordinates to frame coordinates:
x' = sx*(x - cx0) + cx,  y' = sy*(y - cy0) + cy  (cx0,cy0 = template centre in frame 119).
"""
import sys
from glass_common import *

REF = 119
fr = load(100, 899)
def blur(m): return cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.5)
# template: glass outline only, bbox in the region crop
gx0, gx1, gy0, gy1 = 190 - X0, 515 - X0, 420 - Y0, 815 - Y0
T = ink(fr[REF])[gy0:gy1, gx0:gx1]
T = blur(T); th, tw = T.shape
cx0, cy0 = X0 + gx0 + tw / 2, Y0 + gy0 + th / 2
cache = {}
def tpl(sx, sy):
    k = (round(sx, 3), round(sy, 3))
    if k not in cache:
        w, h = int(round(tw * sx)) | 1, int(round(th * sy)) | 1
        cache[k] = cv2.resize(T, (w, h), interpolation=cv2.INTER_LINEAR)
    return cache[k]

def search(img, cx, cy, sxs, sys_, win):
    best = (-1,)
    for sx in sxs:
        for sy in sys_:
            t = tpl(sx, sy); h, w = t.shape
            x0 = int(round(cx - X0 - w / 2 - win)); y0 = int(round(cy - Y0 - h / 2 - win))
            roi = img[max(0, y0):y0 + h + 2 * win, max(0, x0):x0 + w + 2 * win]
            if roi.shape[0] < h or roi.shape[1] < w: continue
            r = cv2.matchTemplate(roi, t, cv2.TM_CCORR_NORMED); _, mv, _, (px, py) = cv2.minMaxLoc(r)
            if mv > best[0]:
                dx = dy = 0.0
                if 0 < px < r.shape[1] - 1:
                    a, b, c = r[py, px-1], r[py, px], r[py, px+1]; dx = 0.5 * (a - c) / (a - 2*b + c + 1e-9)
                if 0 < py < r.shape[0] - 1:
                    a, b, c = r[py-1, px], r[py, px], r[py+1, px]; dy = 0.5 * (a - c) / (a - 2*b + c + 1e-9)
                best = (float(mv), X0 + max(0, x0) + px + dx + w / 2, Y0 + max(0, y0) + py + dy + h / 2, sx, sy)
    return best

rows = []
for i in range(100, 900):
    img = blur(ink(fr[i]))
    best = (-1,)
    for s in np.arange(0.92, 1.141, 0.02):
        r = search(img, cx0, cy0, [s], [s], 24)
        if r[0] > best[0]: best = r
    r = search(img, best[1], best[2], np.arange(best[3] - 0.03, best[3] + 0.031, 0.01), np.arange(best[4] - 0.03, best[4] + 0.031, 0.01), 4)
    r = search(img, r[1], r[2], np.arange(r[3] - 0.008, r[3] + 0.0081, 0.004), np.arange(r[4] - 0.008, r[4] + 0.0081, 0.004), 2)
    rows.append([i, round(float(r[1]), 2), round(float(r[2]), 2), round(float(r[3]), 3), round(float(r[4]), 3), round(r[0], 3)])
    if i % 50 == 0: print(rows[-1], flush=True)
save_json('glass_pose_raw.json', {'ref': REF, 'center0': [round(cx0, 2), round(cy0, 2)], 'columns': ['frame', 'cx', 'cy', 'sx', 'sy', 'score'], 'rows': rows})
