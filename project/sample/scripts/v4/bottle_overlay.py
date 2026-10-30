"""Verification contact sheets: tracked bottle outline + mouth-tip anchor + axis, stream polyline
(with width ticks) and droplets drawn on the original frames.

usage: uv run -q --with opencv-python-headless --with numpy python scripts/v4/bottle_overlay.py
"""
import json
from pathlib import Path
import cv2, numpy as np

ROOT = Path(__file__).resolve().parents[2]
VIDEO = str(ROOT / '01_레퍼런스/original.mp4')
OUT = ROOT / '01_레퍼런스/analysis-v4/bottles'
TR = json.loads((OUT / '.cache-bottle-track.json').read_text())
ST = json.loads((OUT / '.cache-streams.json').read_text()) if (OUT / '.cache-streams.json').exists() else {}
CROP = (0, 100, 600, 840)


def outline(name, r):
    art = np.load(str(OUT / f'.cache-art-{name}.npy')); W = (art[..., 3] > 127).astype(np.uint8)
    cs, _ = cv2.findContours(W, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    P = max(cs, key=len)[:, 0, :].astype(float) - TR[name]['art_canvas'] / 2
    a = np.radians(r[3]); R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]]) * r[4]
    return (P @ R.T + [r[7], r[8]])


def draw(f, name, i, rows, streams):
    if i in rows:
        r = rows[i]
        cv2.polylines(f, [np.round(outline(name, r) * 4).astype(np.int32)], True, (255, 0, 255), 1, cv2.LINE_AA, shift=2)
        a = np.radians(r[3]); ax = np.array([np.sin(a), -np.cos(a)])
        tip = np.array([r[1], r[2]]); tail = tip - ax * 270 * r[4]
        cv2.line(f, tuple(np.round(tip).astype(int)), tuple(np.round(tail).astype(int)), (0, 160, 0), 1, cv2.LINE_AA)
        cv2.circle(f, tuple(np.round(tip).astype(int)), 4, (0, 0, 255), -1)
    s = streams.get(str(i), {})
    if 'stream' in s:
        P = np.array([q[:3] for q in s['stream']['pts']], float)
        cv2.polylines(f, [np.round(P[:, :2] * 4).astype(np.int32)], False, (0, 200, 255) if s['stream']['attached'] else (255, 120, 0), 1, cv2.LINE_AA, shift=2)
        for k in range(len(P)):
            if 0 < k < len(P) - 1: d = P[k + 1, :2] - P[k - 1, :2]
            else: d = P[min(k + 1, len(P) - 1), :2] - P[max(k - 1, 0), :2]
            d = d / (np.linalg.norm(d) + 1e-9); n = np.array([-d[1], d[0]]) * P[k, 2] / 2
            a, b = P[k, :2] - n, P[k, :2] + n
            cv2.line(f, tuple(np.round(a).astype(int)), tuple(np.round(b).astype(int)), (0, 120, 255), 1)
    for d in s.get('drops', []):
        cv2.circle(f, (int(round(d[0])), int(round(d[1]))), int(round(d[2])) + 3, (0, 255, 0) if d[4] == 'drop' else (255, 255, 0), 1, cv2.LINE_AA)


def main():
    rng = {n: (TR[n]['rows'][0][0] - 2, TR[n]['rows'][-1][0] + 2) for n in TR}
    want = set(); [want.update(range(a, b + 1)) for a, b in rng.values()]
    cap = cv2.VideoCapture(VIDEO); fr = {}; i = 0
    while i <= max(want):
        ok, f = cap.read()
        if not ok: break
        if i in want: fr[i] = f
        i += 1
    x0, y0, x1, y1 = CROP
    for name, (a, b) in rng.items():
        rows = {r[0]: r for r in TR[name]['rows']}; streams = ST.get(name, {}).get('frames', {})
        for part, (fa, fb, step, sc) in {'all': (a, b, 2, 0.28)}.items():
            tiles = []
            for i in range(fa, fb + 1, step):
                f = fr[i].copy(); draw(f, name, i, rows, streams)
                t = cv2.resize(f[y0:y1, x0:x1], None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
                cv2.putText(t, str(i), (3, 14), 0, 0.45, (0, 0, 200), 1, cv2.LINE_AA); tiles.append(t)
            cols = 10
            while len(tiles) % cols: tiles.append(np.full_like(tiles[0], 255))
            sheet = np.vstack([np.hstack(tiles[k:k + cols]) for k in range(0, len(tiles), cols)])
            cv2.imwrite(str(OUT / f'overlay-{name}-sheet.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
        # 1:1 close-ups of the tracked outline at entry / tilt / pour / return / exit moments
        off = {'gin': 0, 'campari': 150, 'vermouth': 300}[name]
        tiles = []
        for i in [190 + off, 197 + off, 206 + off, 209 + off, 212 + off, 230 + off, 299 + off, 302 + off, 305 + off, 316 + off]:
            f = fr[i].copy(); draw(f, name, i, rows, {})
            r = rows[i]; cx, cy = int(r[7]), int(r[8])
            x0_, y0_ = max(0, cx - 150), max(0, cy - 150)
            t = np.full((300, 300, 3), 255, np.uint8); c = f[y0_:y0_ + 300, x0_:x0_ + 300]; t[:c.shape[0], :c.shape[1]] = c
            cv2.putText(t, str(i), (3, 16), 0, 0.5, (0, 0, 200), 1, cv2.LINE_AA); tiles.append(t)
        cv2.imwrite(str(OUT / f'overlay-{name}-closeup.jpg'), np.vstack([np.hstack(tiles[k:k + 5]) for k in (0, 5)]), [cv2.IMWRITE_JPEG_QUALITY, 90])
        # full-res close-ups of key moments (pour) for stream checking
        pour = sorted(int(k) for k, v in streams.items() if 'stream' in v)
        if pour:
            picks = np.linspace(pour[0], pour[-1], 12).round().astype(int)
            tiles = []
            for i in picks:
                f = fr[i].copy(); draw(f, name, i, rows, streams)
                t = cv2.resize(f[300:820, 150:520], None, fx=0.6, fy=0.6, interpolation=cv2.INTER_AREA)
                cv2.putText(t, str(i), (3, 16), 0, 0.5, (0, 0, 200), 1, cv2.LINE_AA); tiles.append(t)
            sheet = np.vstack([np.hstack(tiles[k:k + 6]) for k in range(0, 12, 6)])
            cv2.imwrite(str(OUT / f'overlay-{name}-stream.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])


if __name__ == '__main__':
    main()
