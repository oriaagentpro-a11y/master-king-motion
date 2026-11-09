"""NE PAS UTILISER TEL QUEL (règle 123) : sons « par défaut » interdits ; chaque film a sa palette conçue sur mesure.
Sound design cues synthesised with numpy (no third-party samples): whoosh, hit, pop, click, riser, shimmer, sub.

Usage: python3 sfx.py <out.wav> --duration 32.5 (--cues cues.json | --auto timing.json) [--seed 3]
cues.json = [{"t": 2.40, "type": "whoosh", "dur": 0.45, "gain": 0.8, "pan": -0.3}, {"t": 2.85, "type": "hit"}, ...]
--auto timing.json: one whoosh ending on each cut + a soft hit on the cut (the reference's transitions).
Only add SFX when the reference has them, or when the user asks: the music and the voice come first.
Times are in the NEW video. The file is 48 kHz stereo, exactly --duration long; finalize.py mixes it.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json, wave
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402

SR = 48000


def env(n, a, r):
    e = np.ones(n); na, nr = max(1, int(a * n)), max(1, int(r * n))
    e[:na] = np.linspace(0, 1, na) ** 2; e[-nr:] *= np.linspace(1, 0, nr) ** 2
    return e


def lowpass(x, fc):
    a = np.exp(-2 * np.pi * fc / SR); y = np.empty_like(x); s = 0.0
    for i, v in enumerate(x):
        s = (1 - a) * v + a * s; y[i] = s
    return y


def sweep_noise(n, f0, f1, rng):
    x = rng.standard_normal(n)
    out = np.zeros(n); blk = 512
    for i in range(0, n, blk):
        fc = f0 + (f1 - f0) * (i / n)
        a = np.exp(-2 * np.pi * fc / SR); s = out[i - 1] if i else 0.0
        for j in range(i, min(n, i + blk)):
            s = (1 - a) * x[j] + a * s; out[j] = s
    return out / (np.abs(out).max() + 1e-9)


def make(kind, dur, rng):
    n = int(dur * SR); t = np.arange(n) / SR
    if kind == 'whoosh':
        x = sweep_noise(n, 300, 5000, rng) * np.sin(np.pi * t / dur) ** 2
    elif kind == 'whoosh_out':
        x = sweep_noise(n, 5000, 300, rng) * np.sin(np.pi * t / dur) ** 2
    elif kind == 'hit':
        x = np.sin(2 * np.pi * (90 * t - 30 * t ** 2)) * np.exp(-t * 9) + 0.25 * lowpass(rng.standard_normal(n), 2500) * np.exp(-t * 30)
    elif kind == 'sub':
        x = np.sin(2 * np.pi * (55 * t - 10 * t ** 2)) * np.exp(-t * 3.5)
    elif kind == 'pop':
        x = np.sin(2 * np.pi * (900 * t - 1600 * t ** 2)) * np.exp(-t * 40)
    elif kind == 'click':
        x = lowpass(rng.standard_normal(n), 6000) * np.exp(-t * 180)
    elif kind == 'riser':
        f = 200 + 1800 * (t / dur) ** 2
        x = (np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.4 + sweep_noise(n, 500, 9000, rng) * 0.6) * (t / dur) ** 2
    elif kind == 'shimmer':
        x = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f in (1760, 2217, 2637, 3520)) / 4 * np.exp(-t * 2.5) * env(n, 0.05, 0.3)
    else:
        raise SystemExit(f'type inconnu : {kind}')
    return x / (np.abs(x).max() + 1e-9)


DEF = {'whoosh': 0.45, 'whoosh_out': 0.45, 'hit': 0.6, 'sub': 1.2, 'pop': 0.12, 'click': 0.05, 'riser': 1.5, 'shimmer': 1.2}


def main():
    a = sys.argv
    if len(a) < 2:
        sys.exit(__doc__)
    out = a[1]; dur = mk.arg(a, 'duration', None, float); rng = np.random.default_rng(mk.arg(a, 'seed', 3, int))
    if mk.arg(a, 'auto'):
        T = json.load(open(mk.arg(a, 'auto'))); dur = dur or T['total']
        cues = []
        for s in T['scenes'][1:]:
            c = s['new_start']; cues += [{'t': c - 0.42, 'type': 'whoosh', 'dur': 0.45, 'gain': 0.55}, {'t': c, 'type': 'hit', 'gain': 0.35}]
    else:
        cues = json.load(open(mk.arg(a, 'cues')))
    if not dur:
        sys.exit('--duration requis')
    buf = np.zeros((int(dur * SR) + 1, 2))
    for c in cues:
        d = c.get('dur', DEF.get(c['type'], 0.5)); x = make(c['type'], d, rng) * c.get('gain', 0.7)
        i0 = int(max(0, c['t']) * SR); i1 = min(len(buf), i0 + len(x)); x = x[:i1 - i0]
        p = c.get('pan', 0.0)
        buf[i0:i1, 0] += x * np.sqrt((1 - p) / 2) * 1.414; buf[i0:i1, 1] += x * np.sqrt((1 + p) / 2) * 1.414
    pk = np.abs(buf).max()
    if pk > 0.95:
        buf *= 0.95 / pk
    with wave.open(out, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((buf * 32767).astype('<i2').tobytes())
    print(f'{len(cues)} effets sonores, {dur:.2f} s -> {out}')


if __name__ == '__main__':
    main()
