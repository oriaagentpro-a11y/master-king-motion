"""Premium, soft sound design synthesised in numpy/scipy (no samples, nothing taken from the reference).

Usage: python3 sfx_premium.py cues.json out.wav --duration 33.4 [--seed 7]
cues.json = [{"t": 1.71, "type": "key"}, {"t": 6.95, "type": "whoosh", "dur": 0.5, "pan": -0.2, "gain": 0.7}, ...]
Types (all soft, low-passed, no beeps):
  key      mechanical keyboard tap (filtered noise click + small body), random micro-variation per hit
  tick     tiny detent click (wheel / list steps)
  pop      soft rounded bloop (sine glide + air), for cards / tiles appearing
  whoosh   air swell (filtered noise, band moves up then down), length = dur, ends at t + dur
  sub      deep felt "vibration" (52-70 Hz glide, 0.35 s), for impacts and reveals
  shimmer  light glassy sparkle (high partials, slow decay), for logo / magic moments
  riser    rising air + tone towards t + dur
  select   soft UI confirm (two quiet partials), for chips / choices
Times are film seconds; whoosh/riser END at t + dur (so they land on the event). 48 kHz stereo, exactly --duration long.
Method (rule 123): measure WHEN the reference has SFX (percussive onsets by band), never extract them; recreate the
character (typing taps, ticks, soft pops, sub impacts, air whooshes), cue each one on its visual event, mix under the
voice (-14 dB around speech) and above the ducked music.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, json, wave
import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], btype='band', fs=SR, output='sos'), x)


def lp(x, fc, order=2):
    return sosfilt(butter(order, fc, btype='low', fs=SR, output='sos'), x)


def edecay(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def make(kind, dur, rng):
    if kind == 'key':
        n = int(0.06 * SR); x = rng.standard_normal(n) * edecay(n, 0.006 + 0.002 * rng.random())
        click = bp(x, 1800 + 600 * rng.random(), 6500) * 0.9
        body = np.sin(2 * np.pi * (150 + 40 * rng.random()) * np.arange(n) / SR) * edecay(n, 0.012) * 0.35
        return (click + body) * (0.75 + 0.5 * rng.random())
    if kind == 'tick':
        n = int(0.03 * SR); x = rng.standard_normal(n) * edecay(n, 0.003)
        return bp(x, 2500, 8000) * 0.6
    if kind == 'pop':
        n = int(0.16 * SR); t = np.arange(n) / SR; f = 420 + 380 * (1 - np.exp(-t / 0.03))
        tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * edecay(n, 0.045)
        air = bp(rng.standard_normal(n), 2000, 7000) * edecay(n, 0.02) * 0.15
        return lp(tone, 2400) * 0.55 + air
    if kind == 'whoosh':
        n = int(dur * SR); u = np.linspace(0, 1, n); x = rng.standard_normal(n)
        lo_band = lp(x, 900); hi_band = bp(x, 1200, 5200)
        mix = lo_band * (1 - u) + hi_band * np.sin(np.pi * u) * 0.9
        envl = np.sin(np.pi * np.clip(u, 0, 1)) ** 1.6 * (0.4 + 0.6 * u)
        return mix * envl * 0.35
    if kind == 'sub':
        n = int(0.42 * SR); t = np.arange(n) / SR; f = 48 + 24 * np.exp(-t / 0.06)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * edecay(n, 0.12) * (1 - np.exp(-t / 0.004)) * 0.9
    if kind == 'shimmer':
        n = int(1.1 * SR); t = np.arange(n) / SR; y = np.zeros(n)
        for k, f in enumerate([2093, 2637, 3136, 4186, 5274]):
            y += np.sin(2 * np.pi * f * t + rng.random() * 6.28) * np.exp(-t / (0.25 + 0.08 * k)) * (1 - np.exp(-t / 0.01)) / (1 + k)
        return y * 0.18
    if kind == 'riser':
        n = int(dur * SR); u = np.linspace(0, 1, n); x = rng.standard_normal(n)
        y = bp(x, 600, 6000) * u ** 2 * 0.25 + np.sin(2 * np.pi * np.cumsum(180 + 420 * u ** 2) / SR) * u ** 3 * 0.12
        return y
    if kind == 'select':
        n = int(0.22 * SR); t = np.arange(n) / SR
        y = (np.sin(2 * np.pi * 880 * t) + 0.6 * np.sin(2 * np.pi * 1320 * t)) * edecay(n, 0.05) * (1 - np.exp(-t / 0.003))
        return lp(y, 3000) * 0.22
    raise ValueError(kind)


def main():
    a = sys.argv[1:]
    cues = json.load(open(a[0])); out = a[1]
    D = float(a[a.index('--duration') + 1]); seed = int(a[a.index('--seed') + 1]) if '--seed' in a else 7
    rng = np.random.default_rng(seed); buf = np.zeros((2, int(D * SR) + SR))
    for c in cues:
        k = c['type']; dur = c.get('dur', 0.4); s = make(k, dur, rng) * c.get('gain', 1.0)
        start = c['t'] - (dur if k in ('whoosh', 'riser') else 0)
        i = int(max(0, start) * SR); pan = c.get('pan', 0.0)
        for ch, g in ((0, np.sqrt(0.5 * (1 - pan))), (1, np.sqrt(0.5 * (1 + pan)))):
            buf[ch, i:i + len(s)] += s[:max(0, buf.shape[1] - i)] * g
    buf = buf[:, :int(D * SR)]; pk = np.abs(buf).max()
    if pk > 0.95:
        buf *= 0.95 / pk
    pcm = (buf.T * 32767).astype('<i2')
    with wave.open(out, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    print(f'{len(cues)} effets -> {out} ({D:.2f} s)')


if __name__ == '__main__':
    main()
