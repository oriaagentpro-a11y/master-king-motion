"""Place the voice-over lines one after another, each starting on a music beat (rules 85, 111, 122).

Usage: python vo_layout.py
Reads assets/voix/l*.wav, analysis/music_plan.json. Writes assets/voix_calee.wav (film clock, starts at 0)
and analysis/vo_layout.json {music_start, duration, lines:[{id, start, end, file, trim0}]}.
"""
import json, glob, os
import numpy as np, librosa, soundfile as sf

SR = 24000
GAPS = {  # minimum silence before each line (s): longer gaps where the story changes chapter
    'l01': 0, 'l02': 0.25, 'l03': 0.25, 'l04': 0.45, 'l05': 0.25, 'l06': 0.5,
    'l07': 0.25, 'l08': 0.5, 'l09': 0.25, 'l10': 0.2, 'l11': 0.6}
FIRST = 1.0      # film time of the first word (opening dot grows first: R2 S01 dot visible from 0.0 s)
TAIL = 3.0       # logo hold after the last word
MUSIC_END = 65.295  # section change measured by audio_prep (natural ending of the track)

mp = json.load(open('analysis/music_plan.json'))['music']
beats = np.array([b['t'] for b in mp['beats']])
# audio_prep lists beats only up to 49.3 s; the track stays at a steady 120 BPM until its ending (65.3 s):
# extend at the measured interval (beat_s) so late lines also land on the grid
beats = np.concatenate([beats, beats[-1] + mp['beat_s'] * np.arange(1, int((mp['duration'] - beats[-1]) / mp['beat_s']))])

lines = []
for f in sorted(glob.glob('assets/voix/l*.wav')):
    y, _ = librosa.load(f, sr=SR)
    _, (a, b) = librosa.effects.trim(y, top_db=38)
    a = max(0, a - int(0.03 * SR)); b = min(len(y), b + int(0.08 * SR))
    lines.append({'id': os.path.basename(f)[:-4], 'y': y[a:b], 'file': f, 'trim0': a / SR})

# provisional layout on a 0.5 s grid to know the film duration, then exact layout on the real beats
def layout(beat_film):
    t = None; out = []
    for L in lines:
        want = FIRST if t is None else t + GAPS[L['id']]
        s = beat_film[beat_film >= want - 1e-6][0]
        e = s + len(L['y']) / SR
        out.append((s, e)); t = e
    return out

grid = np.arange(0, 80, 0.5) + 0.0
prov = layout(grid)
D = prov[-1][1] + TAIL
# music start: the film ends where the track ends; snap so that film t=FIRST sits exactly on a music beat
ms0 = MUSIC_END - D
j = np.argmin(np.abs((beats - FIRST) - ms0))
ms = beats[j] - FIRST
beat_film = beats - ms
beat_film = beat_film[beat_film >= 0]
pos = layout(beat_film)
D = pos[-1][1] + TAIL
for k, ((s, e), L) in enumerate(zip(pos, lines)):
    if k:
        assert s >= pos[k - 1][1] + 0.08, 'chevauchement'
out = np.zeros(int((D + 0.5) * SR), dtype=np.float32)
for (s, e), L in zip(pos, lines):
    i = int(round(s * SR)); out[i:i + len(L['y'])] += L['y']
sf.write('assets/voix_calee.wav', out, SR)
res = {'music_start': round(float(ms), 4), 'duration': round(float(D), 3),
       'lines': [{'id': L['id'], 'start': round(float(s), 3), 'end': round(float(e), 3), 'trim0': round(L['trim0'], 3)}
                 for (s, e), L in zip(pos, lines)]}
json.dump(res, open('analysis/vo_layout.json', 'w'), indent=1)
print(f"musique depuis {ms:.3f} s, film {D:.2f} s")
for r in res['lines']:
    print(r['id'], r['start'], r['end'])
