"""Raw 30fps ice track -> intro-motion-v3.json (title data copied from v2).

Cleaning only: outlier x (low-score frames while a cube crosses ink it hides) -> median x,
settled jitter (<=1.5px, <=2deg) -> frozen pose, impact-mark segments -> cube-relative
offsets.  Every other sample is the measured value at that video frame.
"""
import json, math, statistics
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v2 = json.loads((root / '03_모션제작/intro-motion-v2.json').read_text())
track = json.loads((root / '01_레퍼런스/analysis-01/ice-track-30fps.json').read_text())
LATER = {'ice1': 'ice1', 'ice2': 'ice3', 'ice3': 'ice2'}   # motion.json names after 6s

ice = []
for name, rows in track['tracks'].items():
    rows = [r for r in rows if r[0] <= 180]
    mx = statistics.median(r[1] for r in rows)
    scale = round(statistics.median(r[4] for r in rows), 3)
    frames = [[r[0], mx if abs(r[1] - mx) > 3 else r[1], r[2], r[3]] for r in rows]
    # settle = first frame after which the cube never moves more than 1.5px / 2deg again
    settle = next(i for i in range(len(frames)) if all(abs(f[2] - frames[i][2]) <= 1.5 and abs(f[3] - frames[i][3]) <= 2 for f in frames[i:]))
    rest = frames[settle:]
    pose = [statistics.median(f[k] for f in rest) for k in (1, 2, 3)]
    frames = frames[:settle] + [[f[0], *pose] for f in rest]
    ice.append({'id': name, 'later': LATER[name], 'scale': scale, 'startFrame': frames[0][0],
                'settleFrame': frames[settle][0], 'frames': [[f[0]] + [round(v, 1) for v in f[1:]] for f in frames]})

# Impact marks: thick short strokes above a cube inside the glass, stored relative to that cube
by_frame = {i['id']: {f[0]: f for f in i['frames']} for i in ice}
marks = {}
for key, segs in track['marks'].items():
    fr = int(key); keep = []
    for x1, y1, x2, y2, w in segs:
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        cand = [(math.hypot(cx - p[1], cy - p[2]), n, p) for n, t in by_frame.items() if fr in t for p in [t[fr]]]
        if not cand: continue
        d, n, p = min(cand); ang = math.degrees(math.atan2(cy - p[2], cx - p[1])); length = math.hypot(x2 - x1, y2 - y1)
        if 45 <= d <= 75 and -160 <= ang <= -20 and length <= 30 and w >= 1.25 and p[2] > 450:
            keep.append([n, round(x1 - p[1], 1), round(y1 - p[2], 1), round(x2 - p[1], 1), round(y2 - p[2], 1), round(min(w, 2.8), 1)])
    if keep: marks[fr] = keep

out = {k: v for k, v in v2.items() if k != 'ice'}
out['version'] = 3
out['method'] = (v2['method'] + '; v3 ice: per-frame (30fps) rotated-template track of the reference, '
                 'scripts/track_ice.py -> scripts/make_ice_v3.py, linear between frames')
out['ice'] = ice
# Render calibration: tracking the v3 render against the reference gave a constant screen-space
# bias (cube drawn 0.8px left, 1.9px high) at every angle, so it belongs to the art, not the motion.
out['iceArtOffset'] = [0.8, 1.9]
out['iceMarks'] = {str(k): v for k, v in sorted(marks.items())}
(root / '03_모션제작/intro-motion-v3.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
for i in ice: print(i['id'], 'start', i['startFrame'], 'settle', i['settleFrame'], 'pose', i['frames'][-1], 'scale', i['scale'])
print('mark frames', sorted(marks))
