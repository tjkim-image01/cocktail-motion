"""Overlay ice tracks (ice_raw.json) on reference frames -> contact sheets for checking."""
import sys
from glass_common import *
D = json.loads((OUT / 'ice_raw.json').read_text()); side = 71
a, b, step, name = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
col = {'ice1': (0, 0, 255), 'ice2': (0, 160, 0), 'ice3': (255, 0, 0)}
tr = {n: {r[0]: r for r in rows} for n, rows in D['tracks'].items()}
cap = cv2.VideoCapture(str(VIDEO)); i = 0; tiles = []
while i <= b:
    ok, f = cap.read()
    if not ok: break
    if i >= a and (i - a) % step == 0:
        for n, t in tr.items():
            if i not in t: continue
            _, x, y, ang, sc, s = t[i]
            box = cv2.boxPoints(((x, y), (side * sc, side * sc), ang)).astype(np.int32)
            cv2.polylines(f, [box], True, col[n], 1, cv2.LINE_AA)
            # highlight corner = top-right of the axis-aligned cube, rotated clockwise by ang
            th = np.radians(ang); hx, hy = side * sc * 0.35, -side * sc * 0.35
            cv2.circle(f, (int(x + hx * np.cos(th) - hy * np.sin(th)), int(y + hx * np.sin(th) + hy * np.cos(th))), 4, col[n], -1)
            cv2.putText(f, '%.2f' % s, (int(x) - 14, int(y) + 4), 0, 0.35, col[n], 1)
        c = f[540:800, 200:500]; c = cv2.resize(c, None, fx=0.7, fy=0.7, interpolation=cv2.INTER_AREA)
        cv2.putText(c, str(i), (3, 13), 0, 0.45, (0, 0, 0), 1); tiles.append(c)
    i += 1
cols = 10
while len(tiles) % cols: tiles.append(np.full_like(tiles[0], 255))
cv2.imwrite(str(OUT / name), np.vstack([np.hstack(tiles[k:k + cols]) for k in range(0, len(tiles), cols)]), [cv2.IMWRITE_JPEG_QUALITY, 80])
