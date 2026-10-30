"""Sound-effect cue sheet from the measured motion (no hand-placed times).

Reads 03_모션제작/{intro-motion-v3,ui-v4,glass-v4}.json and, if present, bottles-v4.json;
writes 05_음악동기화/sfx-v4-events.json for scripts/v4/sfx.py.
Every cue lists the measurement it comes from in 'note'."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
M = root / '03_모션제작'
intro = json.loads((M / 'intro-motion-v3.json').read_text())
ui = json.loads((M / 'ui-v4.json').read_text())
G = json.loads((M / 'glass-v4.json').read_text())
B = json.loads((M / 'bottles-v4.json').read_text()) if (M / 'bottles-v4.json').exists() else None
ev = []
def add(frame, kind, note, **p): ev.append({'t': round(frame / 30, 4), 'type': kind, 'note': note, **p})

# title letters pop (measured letter start times), slide up, subtitle
for i, s in enumerate(intro['title']['starts']):
    add(s * 30 + 2, 'pop', f'title letter {i+1} appears', pitch=0.9 + 0.07 * i, gain=0.55)
add(86, 'whoosh', 'title slides to the top (frames 88-98)', dur=0.4, lo=500, hi=1800, gain=0.5)
# glass is drawn line by line (glass-v4 entrance strokes)
for name, s in G['entrance']['strokes'].items():
    k = s['keys']; add(k[0][0], 'scribble', f'glass stroke {name} drawn', dur=(k[-1][0] - k[0][0]) / 30, gain=0.8, pan=-0.3)
# card entries and counter / node / oz events (ui-v4)
for n in ui['card']['entries']:
    add(n, 'pop', f'card entry frame {n}', pitch=0.75, gain=0.8, pan=0.4)
for f in (143, 153, 164):
    add(f, 'tick', f'ice counter steps at {f}', done=False, gain=0.45, pan=0.4)
for i, f in enumerate(ui['timeline']['done']):
    add(f, 'ding', f'timeline node {i+1} done', pitch=1 + 0.06 * i, gain=0.5)
for k, L in ui['oz'].items():
    add(L['redFrom'] + 8, 'pop', f'{k} oz reached, red label pops', pitch=1.4, gain=0.35, pan=0.1)

# ice impacts: lowest screen point where the cube's vertical velocity flips (glass-v4 ice tracks)
for cid, rows in G['ice'].items():
    hits = 0
    for a, b, c in zip(rows, rows[1:], rows[2:]):
        if b[0] > 240: break
        vin, vout = b[2] - a[2], c[2] - b[2]
        if vin > 3 and vout < 0:
            hits += 1
            add(b[0] - 0.5, 'clink' if hits == 1 else 'thunk', f'{cid} impact {hits} at frame {b[0]} (in {vin:.0f}px/f)',
                strength=min(1.0, vin / 90) * (1 if hits == 1 else 0.55), pan=(b[1] - 350) / 400)

# pours: stream frames from bottle data, else the measured liquid rise windows
rise = {'gin': (228, 285), 'campari': (381, 440), 'vermouth': (530, 585)}
for i, name in enumerate(('gin', 'campari', 'vermouth')):
    if B and name in B.get('streams', {}):
        f0, f1 = B['streams'][name]['first'], B['streams'][name]['last']; src = 'bottle stream frames'
    else:
        f0, f1 = rise[name][0] - 8, rise[name][1] + 4; src = 'liquid level rise'
    add(f0, 'pour', f'{name} pour {f0}-{f1} ({src})', dur=(f1 - f0) / 30, thick=[0, 0.55, 0.8][i], rise=[[420, 900], [360, 760], [320, 700]][i], gain=0.9, pan=-0.2)
    add(f1 + 1, 'drip', f'{name} last drop', gain=0.6)
    if B and name in B.get('bottles', {}):
        bb = B['bottles'][name]; add(bb['first'], 'whoosh', f'{name} bottle enters', dur=0.35, gain=0.45, pan=-0.7)
        add(bb['last'] - 8, 'whoosh', f'{name} bottle leaves', dur=0.35, rising=False, gain=0.4, pan=-0.7)

# stir (glass-v4 spoon rows): spoon drops in, swish every half cycle, dull taps at angle extremes
sp = G['spoon']['rows']
add(sp[0][0] + 6, 'clink', 'spoon lands in the glass', strength=0.5, dull=0.7)
ang = [(r[0], r[3]) for r in sp]; mid = sum(v for _, v in ang) / len(ang); last = -99
for (fa, a), (fb, b), (fc, c) in zip(ang, ang[1:], ang[2:]):
    # real turns only: away from the mean swing angle, ≥9 frames apart (24-frame stir cycle)
    if 641 <= fb <= 721 and ((b > a and b >= c) or (b < a and b <= c)) and abs(b - mid) > 3.5 and fb - last >= 9:
        last = fb
        add(fb, 'clink', f'spoon turns at angle extreme {b:.1f} deg (frame {fb})', strength=0.35, dull=0.8, pan=(b - 4) / 20)
        add(fb - 6, 'swish', 'stir sweep', dur=0.38, gain=0.8)
add(722, 'whoosh', 'spoon lifted out (frames 722-733)', dur=0.35, gain=0.35)
add(728, 'drip', 'spoon drips', gain=0.5)
# peel (glass-v4 peel rows, spritz)
add(739, 'pop', 'peel pops in', pitch=1.1, gain=0.6)
add(751, 'squeak', 'peel twist (frames 751-767)', dur=0.55, gain=0.8)
for f in sorted(int(k) for k in G['peel']['spritz'] if 754 <= int(k) <= 771)[::3]:
    add(f, 'spritz', f'oil spritz frame {f}', gain=0.55)
add(771, 'thunk', 'peel lands on the rim', strength=0.35)
# finale
add(810, 'cheers', 'CIN CIN! card', gain=1.0)
add(814, 'sparkle', 'rays appear (814-821)', dur=1.2, gain=0.7)
add(822, 'whoosh', 'glass grows 822-848', dur=0.9, lo=200, hi=900, gain=0.35)

ev.sort(key=lambda e: e['t'])
(root / '05_음악동기화').mkdir(exist_ok=True)
(root / '05_음악동기화/sfx-v4-events.json').write_text(json.dumps({'duration': 30, 'events': ev}, ensure_ascii=False, indent=1))
print(len(ev), 'cues;', sum(e['type'] == 'clink' for e in ev), 'clinks;', 'bottle data' if B else 'NO bottle data yet (fallback pours)')
