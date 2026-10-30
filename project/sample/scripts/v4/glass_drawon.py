"""Glass entrance (frames 80-125): per stroke, how much of it is inked each frame and from
which end it grows; plus fill colour and highlight visibility per frame.

Strokes are sampled along the measured frame-119 glass geometry (analysis-v4/glass).
Output: 01_레퍼런스/analysis-v4/glass/drawon.json"""
import json, sys
import cv2, numpy as np

cap = cv2.VideoCapture('01_레퍼런스/original.mp4'); F = []
while len(F) < 126:
    ok, f = cap.read(); F.append(f)

def line(a, b, n=80): return [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u) for u in np.linspace(0, 1, n)]
def quad(a, c, b, n=80): return [((1-u)**2*a[0] + 2*(1-u)*u*c[0] + u*u*b[0], (1-u)**2*a[1] + 2*(1-u)*u*c[1] + u*u*b[1]) for u in np.linspace(0, 1, n)]
def arc(cx, cy, rx, ry, a0, a1, n=120): return [(cx + rx * np.cos(a), cy + ry * np.sin(a)) for a in np.linspace(a0, a1, n)]
CX, CY, RX, RY = 353.3, 457.0, 142.95, 22.25
STROKES = {
    'left': line((210.4, 457), (233.5, 782)),
    'right': line((496.2, 457), (470.0, 782)),
    'rimBack': arc(CX, CY, RX, RY, np.pi, 2 * np.pi),      # left -> over the top -> right
    'rimFront': arc(CX, CY, RX, RY, np.pi, 0),             # left -> under -> right
    'bottom': quad((233.5, 782), (353, 814), (470, 782)),   # left -> right
    'innerBottom': quad((240, 746.8), (352, 765.2), (463, 747.3)),
}
def inked(g, pts):
    out = []
    for x, y in pts:
        x, y = int(round(x)), int(round(y))
        out.append(bool((g[y - 3:y + 4, x - 3:x + 4] < 130).any()))
    return out

res = {'frames': list(range(80, 126)), 'strokes': {}, 'fill': [], 'highlight': []}
for name, pts in STROKES.items():
    rows = []
    for i in res['frames']:
        g = cv2.cvtColor(F[i], cv2.COLOR_BGR2GRAY)
        if name == 'innerBottom': g = np.where(g < 190, 0, 255).astype(np.uint8)   # grey line
        m = inked(g, pts); idx = [k for k, v in enumerate(m) if v]
        rows.append([i, round(sum(m) / len(m), 3), (round(idx[0] / (len(m) - 1), 3) if idx else None), (round(idx[-1] / (len(m) - 1), 3) if idx else None)])
    res['strokes'][name] = rows
for i in res['frames']:
    f = F[i].astype(int)
    res['fill'].append([i] + [int(v) for v in f[600:640, 330:380].reshape(-1, 3).mean(0)[::-1]] + [int(v) for v in f[765:775, 330:380].reshape(-1, 3).mean(0)[::-1]])
    x = np.array([int(round(234.7 + (257.3 - 234.7) * u)) for u in np.linspace(0.1, 0.9, 20)]); y = np.array([int(round(506.9 + (692.8 - 506.9) * u)) for u in np.linspace(0.1, 0.9, 20)])
    res['highlight'].append([i, int(f[y, x].mean())])
json.dump(res, open('01_레퍼런스/analysis-v4/glass/drawon.json', 'w'), indent=0)
for n, rows in res['strokes'].items():
    print(n, ' '.join(f"{r[0]}:{r[1]:.2f}({r[2]},{r[3]})" for r in rows if 0 < r[1] < 1 or r[0] in (85, 115)))
print('fill', [r for r in res['fill'] if 98 <= r[0] <= 116])
print('highlight', res['highlight'][18:40])
