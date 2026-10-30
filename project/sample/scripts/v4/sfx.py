"""Procedural sound effects mixed onto measured animation events.

usage: uv run --with numpy --with scipy python scripts/v4/sfx.py EVENTS.json OUT.wav
EVENTS.json: {"duration": 30, "events": [{"t": seconds, "type": name, ...params}]}
Every sound is synthesised here (no samples, no music).  Seeded, so the same events
always give the same file.
"""
import json, sys
import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
rng = np.random.default_rng(7)

def env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)

def band(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], 'bandpass', fs=SR, output='sos'), x)

def low(x, f, order=2):
    return sosfilt(butter(order, f, 'lowpass', fs=SR, output='sos'), x)

def tone(freq, dur, decay, attack=0.002, chirp=0.0):
    n = int(dur * SR); t = np.arange(n) / SR
    ph = 2 * np.pi * np.cumsum(freq * (1 + chirp * t / dur)) / SR
    return np.sin(ph) * env(n, attack, decay)

def noise(dur):
    return rng.standard_normal(int(dur * SR))

# --- sounds -----------------------------------------------------------------
def pop(pitch=1.0, gain=1.0):
    """Cartoon pop for letters / card / headline: falling sine blip + tiny click."""
    s = tone(520 * pitch, 0.12, 0.035, 0.001, chirp=-0.55) + 0.25 * tone(1040 * pitch, 0.12, 0.015)
    c = band(noise(0.012), 1500, 6000) * env(int(0.012 * SR), 0.0005, 0.003) * 0.4
    s[:len(c)] += c
    return s * gain

def whoosh(dur=0.45, lo=300, hi=2400, gain=1.0, rising=True):
    """Air swish: band-limited noise whose band sweeps, swelling then fading."""
    n = int(dur * SR); x = noise(dur); out = np.zeros(n); seg = 512
    for k in range(0, n, seg):
        u = k / n; f = lo + (hi - lo) * (u if rising else 1 - u)
        out[k:k + seg] = band(x[max(0, k - 2048):k + seg], f * 0.7, f * 1.3)[-len(out[k:k + seg]):]
    shape = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.6
    return out * shape * 0.6 * gain

def clink(strength=1.0, dull=0.0):
    """Ice cube on glass: inharmonic partials with fast decay plus a hard transient.
    dull>0 = under liquid (lower, shorter, softer)."""
    base = rng.uniform(0.94, 1.06) * (1 - 0.35 * dull)
    parts = [(2350, .9, .09), (3720, .6, .07), (5480, .45, .05), (7900, .25, .035), (1180, .35, .12)]
    s = sum(a * tone(f * base, 0.35, d * (1 - 0.5 * dull)) for f, a, d in parts)
    tr = band(noise(0.01), 2000, 9000) * env(int(0.01 * SR), 0.0003, 0.002)
    s[:len(tr)] += 1.2 * tr
    if dull: s = low(s, 2600)
    return s * 0.35 * strength

def thunk(strength=1.0):
    """Cube landing on cubes: short woody body + clink overtone."""
    s = tone(190, 0.18, 0.045, 0.001, chirp=-0.3) * 0.8 + clink(0.35)[:int(0.18 * SR)]
    return s * strength

def pour(dur, rise=(380, 900), thick=0.0, gain=1.0):
    """Liquid pour: splashy filtered noise with a resonance that rises as the glass
    fills, plus bubble blips.  thick>0 = syrupy (Campari/vermouth): lower, darker."""
    n = int(dur * SR); x = noise(dur); out = np.zeros(n); seg = 1024
    for k in range(0, n, seg):
        u = k / n; f = rise[0] + (rise[1] - rise[0]) * u
        chunk = x[max(0, k - 4096):k + seg]
        out[k:k + seg] = (band(chunk, f * 0.8, f * 1.25) * 0.9 + band(chunk, 2500, 7000) * (0.25 - 0.15 * thick))[-len(out[k:k + seg]):]
    # gurgle: slow amplitude wobble
    t = np.arange(n) / SR
    out *= 0.75 + 0.25 * np.sin(2 * np.pi * (6.5 - 2 * thick) * t + 3 * np.sin(2 * np.pi * 1.3 * t))
    for b in np.sort(rng.uniform(0, dur, int(dur * (14 - 6 * thick)))):
        f = rng.uniform(450, 1100) * (1 - 0.3 * thick) * (1 + 0.6 * b / dur)
        blip = tone(f, 0.05, 0.012, 0.001, chirp=0.8) * rng.uniform(0.2, 0.5)
        i = int(b * SR); out[i:i + len(blip)] += blip[:n - i]
    fade = np.minimum(1, np.minimum(t / 0.06, (dur - t) / 0.18))
    return out * fade * 0.5 * gain

def drip(gain=1.0):
    return (tone(1300, 0.08, 0.02, 0.001, chirp=0.9) * 0.5 + tone(700, 0.08, 0.015)) * 0.4 * gain

def tick(gain=1.0, done=True):
    """Timeline node: soft wooden tock, plus a bright ding when it becomes done."""
    s = tone(880, 0.25, 0.02, 0.001) * 0.4
    if done: s = s + tone(1760, 0.25, 0.06) * 0.5
    return s * gain

def ding(gain=1.0, pitch=1.0):
    return sum(a * tone(f * pitch, 0.6, d) for f, a, d in [(1568, .6, .25), (2349, .35, .18), (3136, .2, .12)]) * 0.5 * gain

def swish(dur=0.3, gain=1.0):
    """Liquid swirl while stirring."""
    x = low(noise(dur), 900); n = len(x)
    return x * np.sin(np.pi * np.linspace(0, 1, n)) * 0.5 * gain

def squeak(dur=0.35, gain=1.0):
    """Peel twist: rubbery chirps."""
    n = int(dur * SR); t = np.arange(n) / SR
    f = 900 + 500 * np.sin(2 * np.pi * 7 * t)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / dur) ** 2
    return band(s + 0.3 * noise(dur), 600, 3000) * 0.25 * gain

def spritz(gain=1.0):
    x = band(noise(0.16), 3500, 11000); return x * env(len(x), 0.004, 0.045) * 0.35 * gain

def cheers(gain=1.0):
    """Two glasses touching: bright bell partials, long ring, slight beating."""
    out = 0
    for f, a, d in [(2637, .7, .9), (2650, .5, .85), (3951, .35, .6), (5274, .2, .4), (1318, .25, 1.1)]:
        out = out + a * tone(f, 1.8, d, 0.001)
    tr = band(noise(0.008), 3000, 10000) * env(int(0.008 * SR), 0.0002, 0.002)
    out[:len(tr)] += tr
    return out * 0.32 * gain

def sparkle(dur=1.0, gain=1.0):
    n = int(dur * SR); out = np.zeros(n)
    for b in np.sort(rng.uniform(0, dur * 0.8, 9)):
        s = tone(rng.uniform(3000, 6500), 0.25, 0.06) * rng.uniform(0.2, 0.45)
        i = int(b * SR); out[i:i + len(s)] += s[:n - i]
    return out * gain

def scribble(dur=0.3, gain=1.0):
    """Pencil line being drawn (glass entrance strokes): grainy band noise with stroke tremor."""
    n = int(dur * SR); t = np.arange(n) / SR
    x = band(noise(dur), 1800, 6500) * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 23 * t)))
    return x * np.minimum(1, np.minimum(t / 0.02, (dur - t) / 0.05)) * 0.22 * gain

SOUNDS = {'scribble': scribble,'pop': pop, 'whoosh': whoosh, 'clink': clink, 'thunk': thunk, 'pour': pour, 'drip': drip,
          'tick': tick, 'ding': ding, 'swish': swish, 'squeak': squeak, 'spritz': spritz,
          'cheers': cheers, 'sparkle': sparkle}

def render(events, duration):
    mix = np.zeros((int(duration * SR) + SR, 2))
    for e in events:
        p = {k: v for k, v in e.items() if k not in ('t', 'type', 'pan', 'note')}
        s = SOUNDS[e['type']](**p); pan = e.get('pan', 0.0)
        i = int(round(e['t'] * SR)); s = s[:len(mix) - i]
        mix[i:i + len(s), 0] += s * np.sqrt((1 - pan) / 2) * 1.414
        mix[i:i + len(s), 1] += s * np.sqrt((1 + pan) / 2) * 1.414
    mix = mix[:int(duration * SR)]
    peak = np.abs(mix).max()
    mix = np.tanh(mix / max(peak, 1e-9) * 1.4) / np.tanh(1.4) * 0.89   # gentle limiter, -1 dBFS
    return mix

if __name__ == '__main__':
    import wave
    spec = json.load(open(sys.argv[1]))
    mix = render(spec['events'], spec['duration'])
    with wave.open(sys.argv[2], 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype('<i2').tobytes())
    print('events', len(spec['events']), 'duration', spec['duration'], 'peak', float(np.abs(mix).max()))
