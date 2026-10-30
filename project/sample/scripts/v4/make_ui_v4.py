"""UI measurements (01_레퍼런스/analysis-v4/ui/data.json) -> compact player data 03_모션제작/ui-v4.json.

Per-frame series are stored as runs [[startFrame, value], ...] (value holds until the next run).
Nothing is re-fitted here except where the measurement README names a fit (card entry, pulse)."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
d = json.loads((root / '01_레퍼런스/analysis-v4/ui/data.json').read_text())

def runs(seq, key=lambda v: v):
    out = []
    for f, v in enumerate(seq):
        v = key(v)
        if not out or out[-1][1] != v: out.append([f, v])
    return out

texts = {108: ('STEP 1 OF 6', 'FILL', 'ICE', 'big cubes · rocks glass'),
         180: ('STEP 2 OF 6', '1 oz', 'GIN', 'London dry · 30 ml'),
         330: ('STEP 3 OF 6', '1 oz', 'CAMPARI', 'the bitter one · 30 ml'),
         480: ('STEP 4 OF 6', '1 oz', 'SWEET VERMOUTH', 'vermouth rosso · 30 ml'),
         630: ('STEP 5 OF 6', '20 sec', 'STIR', 'until nice and cold'),
         735: ('STEP 6 OF 6', '1', 'ORANGE PEEL', 'express the oils, drop it in'),
         810: ("THAT'S A NEGRONI", 'CIN CIN!', '1:1:1', 'gin · Campari · sweet vermouth')}
pf = d['progress']['per_frame']; tl = d['timeline']['per_frame']
done = sorted(e['frame'] for e in d['timeline']['events'] if e['state'] == 'done')
oz = {}
for k, yc in d['oz']['levels'].items():
    p = d['oz']['per_frame'][k]
    # event frames from the measurement README (the raw arrays have stray early detections)
    g0, r0 = {'1': (212, 288), '2': (361, 438), '3': (514, 588)}[k]
    oz[k] = {'y': yc, 'greyFrom': g0, 'greyTo': r0 - 1,
             'grey': [round(a, 3) if a is not None else 0 for a in p['grey_alpha_est'][g0:r0]],
             'redFrom': r0,
             # red tick+label width per frame from its first frame until it settles (pop), then rest width
             'redW': [b[2] if b else 0 for b in p['red_bbox'][r0:r0 + 24]]}
out = {
    'source': '01_레퍼런스/analysis-v4/ui (measured every frame); scripts/v4/make_ui_v4.py',
    'card': {'rest': d['card']['rest'], 'shadow': [8, 8], 'radius': 14, 'entries': d['entries_N'],
             'fit': {k: d['card']['entry_fit'][k] for k in ('s0', 'c1', 'D_frames', 't0_frames', 'r0_deg')},
             'alpha': [0, 0.58, 0.98, 1]},
    'texts': {str(k): v for k, v in texts.items()},
    'headlineRest': {str(k): v['red_bbox'] for k, v in d['headline']['templates'].items()},
    'progress': {'track': d['progress']['track'], 'fillW': runs(pf['fill_w'], lambda v: v or 0),
                 'counter': runs(pf['counter'])},
    'timeline': {'x': d['timeline']['node_cx'], 'y': d['timeline']['node_cy'],
                 'state': [runs([s[n] for s in tl['state']]) for n in range(6)],
                 'done': done, 'pulse': d['timeline']['pulse_fit'], 'fadeIn': [115, 129],
                 'pop': [25.0, 25.75, 27, 27.5, 27.5, 27, 26.5, 25.3, 24.5, 23.5, 23.5],
                 'segFront': {'3': 39, '4': 45, '5': 55, '6': 70, '7': 87, '8': 102, '9': 113, '10': 120, '11': 123, '13': 156},
                 'checkFull': 5},
    'oz': oz,
    'subtitle': {'from': 101, 'to': 111, 'rise': 6},
}
(root / '03_모션제작/ui-v4.json').write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')))
print('entries', out['card']['entries'], 'done', done, {k: (v['greyFrom'], v['greyTo'], v['redFrom']) for k, v in oz.items()})
print('counter runs', len(out['progress']['counter']), 'fill runs', len(out['progress']['fillW']))
