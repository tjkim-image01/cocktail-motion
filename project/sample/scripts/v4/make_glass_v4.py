"""Glass-content measurements (01_레퍼런스/analysis-v4/glass/data.json) -> 03_모션제작/glass-v4.json.

Kept as measured, per frame.  Cleaning: missing liquid colours carried from the nearest
measured frame; ice/spoon/peel low-score frames get a 3-frame median (boil-level jitter);
the intro ice (frames 120-180) comes from intro-motion-v3.json so the hand-off at 180 is exact."""
import json, statistics
from pathlib import Path

root = Path(__file__).resolve().parents[2]
d = json.loads((root / '01_레퍼런스/analysis-v4/glass/data.json').read_text())
intro = json.loads((root / '03_모션제작/intro-motion-v3.json').read_text())
r1 = lambda v: round(float(v), 1)

# liquid: [frame, yc, b, body, band]
rows = [r for r in d['liquid']['rows'] if r[1] is not None]
body = band = None; liquid = []
for r in rows:
    body = r[6] or body or r[7]; band = r[7] or band or body
    liquid.append([r[0], r1(r[1]), 16, body, band])          # README: use b = 16 (measured b jitters ±2)

def median3(track, cols):
    out = [list(t) for t in track]
    for i in range(1, len(track) - 1):
        for c in cols: out[i][c] = statistics.median([track[i - 1][c], track[i][c], track[i + 1][c]])
    return out

ice = {}
for k, tr in d['ice']['tracks'].items():
    later = median3([r for r in tr if r[0] > 180], (1, 2, 3))
    early = [f for f in next(i for i in intro['ice'] if i['id'] == k)['frames'] if f[0] <= 180]
    ice[k] = [[f[0], r1(f[1]), r1(f[2]), r1(f[3])] for f in early] + [[r[0], r1(r[1]), r1(r[2]), r1(r[3])] for r in later]

spoon = [[r[0], r1(r[1]), r1(r[2]), round(r[3], 2)] for r in d['spoon']['rows']]
peel = [[r[0], r1(r[6]), r1(r[7]), r1(r[8]), round(r[9], 3), round(r[10], 3)] for r in d['peel']['rows']]
pose = d['glass']['pose']['rows']
scale = [[r[0], round((r[3] + r[4]) / 2, 4)] for r in pose if r[0] >= 815]
# Glass entrance, read from scripts/v4/glass_drawon.py (frames 80-85 are hidden by the moving title).
# Each stroke: keys [frame, drawn fraction]; 'from' = which end the line starts at.
dr = json.loads((root / '01_레퍼런스/analysis-v4/glass/drawon.json').read_text())
fill = {r[0]: r for r in dr['fill']}
entrance = {
    'strokes': {
        'left': {'from': 'start', 'keys': [[85, 0], [86, .11], [87, .2], [88, .38], [89, .46], [90, .55], [91, .64], [92, .74], [93, .82], [94, .91], [96, 1]]},
        'right': {'from': 'start', 'keys': [[89, 0], [90, .1], [91, .29], [92, .38], [93, .57], [94, .66], [95, .75], [96, .85], [98, .94], [100, 1]]},
        'rimFrontL': {'from': 'start', 'keys': [[92, 0], [93, .56], [94, 1]]},
        'rimBack': {'from': 'start', 'keys': [[94, 0], [95, .1], [96, .42], [97, .65], [98, .88], [99, 1]]},
        'bottom': {'from': 'end', 'keys': [[93, 0], [94, .09], [95, .28], [96, .45], [97, .61], [98, .79], [99, .85], [100, .95], [101, 1]]},
        'innerBottom': {'from': 'end', 'keys': [[97, 0], [98, .15], [99, .33], [100, .5], [101, .7], [102, .79], [103, .86], [104, .93], [105, .97], [106, 1]]},
        'rimFrontR': {'from': 'end', 'keys': [[98, 0], [99, .18], [100, .3], [101, .54], [102, .64], [103, .76], [104, .92], [105, 1]]},
    },
    'fill': [[f, round(min(1, max(0, (249 - fill[f][1]) / 28)), 2)] for f in range(99, 115)],
    'base': [[f, round(min(1, max(0, (249 - fill[f][4]) / 55)), 2)] for f in range(99, 115)],
    'highlight': [[104, 0], [114, 1]],
}
out = {
    'source': '01_레퍼런스/analysis-v4/glass (every frame 180-899); scripts/v4/make_glass_v4.py',
    'entrance': entrance, 'glassPivot': [352.5, 617.5], 'glassScale': scale,
    'liquid': liquid, 'stir': [631, 733], 'iceMix': 0.62, 'iceMixStir': 0.83,
    'ice': ice, 'spoon': {'L': d['spoon']['L_ballToBowl'], 'rows': spoon},
    'peel': {'centroid': d['peel']['art']['centroid'], 'rows': peel,
             'spritz': {k: [[r1(a), r1(b), r1(c), h] for a, b, c, h in v] for k, v in d['peel']['spritz'].items()}},
    'bubbles': {k: [[r1(a), r1(b), r1(c), kind, h] for a, b, c, kind, h in v] for k, v in d['bubbles'].items()},
    'rays': [{'hex': r['coreHex'], 'frames': [[f[0], r1(f[1]), r1(f[2]), r1(f[3]), r1(f[4]), r1(f[5]), f[6]] for f in r['frames']]} for r in d['rays']],
}
(root / '03_모션제작/glass-v4.json').write_text(json.dumps(out, separators=(',', ':')))
print('liquid', liquid[0], liquid[-1], 'ice', {k: (v[0][0], v[-1]) for k, v in ice.items()})
print('spoon', spoon[0][0], spoon[-1][0], 'peel', peel[0][0], peel[-1][0], 'rays', len(out['rays']), 'scale', scale[-1])
