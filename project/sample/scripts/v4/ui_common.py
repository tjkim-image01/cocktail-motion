"""Shared helpers for UI measurement (tree002 v4). Measurement only."""
import cv2, numpy as np, os, json
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VIDEO = os.path.join(ROOT, '01_레퍼런스', 'original.mp4')
OUT = os.path.join(ROOT, '01_레퍼런스', 'analysis-v4', 'ui')
os.makedirs(OUT, exist_ok=True)

def frames(start=0, end=900):
    """Yield (i, bgr) by sequential read (0-based)."""
    cap = cv2.VideoCapture(VIDEO)
    i = 0
    while True:
        ok, f = cap.read()
        if not ok or i >= end:
            break
        if i >= start:
            yield i, f
        i += 1
    cap.release()

def load(idxs):
    s = set(idxs); d = {}
    for i, f in frames(0, max(idxs) + 1):
        if i in s: d[i] = f
    return d

def sheet(imgs, labels, cols=8, scale=1.0, path=None):
    ims = []
    for im, lb in zip(imgs, labels):
        if scale != 1.0:
            im = cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_NEAREST)
        if im.ndim == 2: im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
        strip = np.zeros((16, im.shape[1], 3), np.uint8)
        cv2.putText(strip, str(lb), (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        im = np.vstack([strip, im])
        ims.append(im)
    h = max(i.shape[0] for i in ims); w = max(i.shape[1] for i in ims)
    rows = (len(ims) + cols - 1) // cols
    S = np.full((rows * (h + 2), cols * (w + 2), 3), 128, np.uint8)
    for k, im in enumerate(ims):
        r, c = divmod(k, cols)
        S[r*(h+2):r*(h+2)+im.shape[0], c*(w+2):c*(w+2)+im.shape[1]] = im
    if path: cv2.imwrite(path, S)
    return S
