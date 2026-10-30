"""Per-frame difference between the reference and renders (whole frame and per region).

Metric: mean absolute RGB difference after a 5px Gaussian blur (tolerates the 1-2px line
boil), in 0-255 units.  usage: compare_frames.py OUT.json NAME=VIDEO [NAME=VIDEO ...]"""
import json, sys
import cv2, numpy as np

REGIONS = {'all': (0, 0, 1080, 1080), 'title': (0, 0, 1080, 230), 'glass': (180, 380, 600, 840),
           'bottle': (0, 60, 330, 470), 'card': (630, 490, 1060, 790), 'timeline': (100, 880, 1000, 1010)}
def frames(path):
    cap = cv2.VideoCapture(path)
    while True:
        ok, f = cap.read()
        if not ok: return
        yield cv2.GaussianBlur(f, (0, 0), 2.5).astype(np.int16)
ref = list(frames('01_레퍼런스/original.mp4'))
out = {}
for arg in sys.argv[2:]:
    name, path = arg.split('=', 1); rows = []
    for i, f in enumerate(frames(path)):
        d = np.abs(f - ref[i]).mean(2)
        rows.append([i] + [round(float(d[y0:y1, x0:x1].mean()), 2) for x0, y0, x1, y1 in REGIONS.values()])
    out[name] = rows
    a = np.array(rows)
    print(name, 'mean all %.2f' % a[:, 1].mean(), ' '.join(f'{k} {a[:, j + 1].mean():.2f}' for j, k in enumerate(REGIONS)))
    secs = [a[s * 30:(s + 1) * 30, 1].mean() for s in range(30)]
    print('  per second:', ' '.join(f'{v:.1f}' for v in secs))
    worst = a[np.argsort(-a[:, 1])[:12]]
    print('  worst frames:', [(int(r[0]), r[1]) for r in worst])
json.dump({'regions': list(REGIONS), 'metric': 'blurred mean abs RGB diff', 'renders': out}, open(sys.argv[1], 'w'))
