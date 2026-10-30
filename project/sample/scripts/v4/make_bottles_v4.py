"""Bottle/stream measurements (01_레퍼런스/analysis-v4/bottles/data.json) -> 03_모션제작/bottles-v4.json.

Tracks and stream centre lines are used as measured, per frame.  Stream ends that stop on an
ice cube or were traced short (README: 'surface-entry y jumps by up to ~25px') are kept; only
the 12 centre points and the attached flag are stored."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
d = json.loads((root / '01_레퍼런스/analysis-v4/bottles/data.json').read_text())
r1 = lambda v: round(float(v), 1)
out = {'source': '01_레퍼런스/analysis-v4/bottles (every frame); scripts/v4/make_bottles_v4.py', 'bottles': {}, 'streams': {}}
LABEL = {'gin': ('GIN', 'london dry', '#2c3a5e'), 'campari': ('CAMPARI', 'bitter', '#c81c2e'), 'vermouth': ('ROSSO', 'vermouth', '#591924')}
for name, b in d['bottles'].items():
    a = d['art'][name]
    out['bottles'][name] = {
        'first': b['choreography']['first_visible'], 'last': b['choreography']['last_visible'],
        'track': [[r[0], r1(r[1]), r1(r[2]), round(r[3], 2)] for r in b['track']],
        'ink': a['ink']['colour'], 'fill': a['fill']['body'], 'fillDx': round(a['fill']['fill_minus_outline_centroid_dx'] * 1.3, 1),
        'highlight': (a['highlight'] or {'colour': '#e8f4f7'})['colour'],
        'label': {'bg': a['label']['bg'], 'border': a['label']['border'], 'text': LABEL[name]},
    }
for name, s in d['streams'].items():
    cs = s['cross_section']; frames = {}
    for f, fr in s['frames'].items():
        st = fr.get('stream')
        if st and st.get('pts'): frames[f] = {'a': bool(st['attached']), 'p': [[r1(p[0]), r1(p[1])] for p in st['pts']]}
        drops = [[r1(x), r1(y), r1(r), h, k] for x, y, r, h, k, _ in fr.get('drops', [])]
        if drops: frames.setdefault(f, {})['d'] = drops
    out['streams'][name] = {'first': s['first_frame'], 'last': s['last_frame'], 'outer': cs['outer_width_median'],
                            'core': cs['core_width_median'], 'ink': cs['ink_colour'], 'fill': cs['fill_colour'],
                            'highlight': cs['highlight_colour'], 'hlPos': cs['highlight_pos_in_core_median'], 'frames': frames}
(root / '03_모션제작/bottles-v4.json').write_text(json.dumps(out, separators=(',', ':')))
print({n: (b['first'], b['last'], len(b['track'])) for n, b in out['bottles'].items()}, {n: (s['first'], s['last'], len(s['frames'])) for n, s in out['streams'].items()})
