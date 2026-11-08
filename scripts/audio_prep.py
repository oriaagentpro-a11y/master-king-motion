"""Measure the user's audio: music beat grid + voice-over phrases. The new video is timed on THEM.

Usage: python3 audio_prep.py <out audio_plan.json> [--music music.mp3] [--voice voix.wav] [--script script.txt]
                             [--fps 30] [--min-silence 0.35] [--silence-db -38]
music  -> tempo, beats, downbeats, strong accents (librosa), duration, loudness (LUFS)
voice  -> phrases [{i, start, end, text}] split on silences (>= --min-silence s under --silence-db),
          duration, loudness. --script: one line per phrase (or blank-line separated paragraphs); lines are
          assigned to the phrases in order and a count mismatch is reported (then adjust --min-silence).
--align  (with --script): local speech recognition (pip install faster-whisper; model MK_WHISPER=small, MK_LANG=fr)
          aligns EACH script line on the voice with word timings, boundaries snapped to real silences — use it
          when the voice-over runs phrases together. Words are kept (phrases[i].words) to sync keywords.
retime.py reads this file to give every scene the time its words need and to cut on the music.
"""
import sys, os, json, subprocess, tempfile, re
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def loudness(path):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    i = re.findall(r'I:\s+(-?[\d.]+) LUFS', r); tp = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', r)
    return {'lufs': float(i[-1]) if i else None, 'true_peak_db': float(tp[-1]) if tp else None}


def load(path, sr=22050):
    import librosa
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, 'a.wav')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', path, '-vn', '-ac', '1', '-ar', str(sr), wav], check=True)
        y, _ = librosa.load(wav, sr=sr)
    return y, sr


def music(path, fps):
    import librosa
    y, sr = load(path)
    env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, bf = librosa.beat.beat_track(onset_envelope=env, sr=sr)
    bt = librosa.frames_to_time(bf, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    if len(bt) > 8:
        tempo = 60.0 / float(np.polyfit(np.arange(len(bt)), bt, 1)[0])
    # phase check: beat trackers often lock on the off-beat (hi-hats are sharper than the kick). The kick / bass
    # live under 200 Hz: if the low-band onsets are stronger half a beat later, shift the whole grid.
    phase_shift = 0.0
    if len(bt) > 4 and tempo:
        M = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=16, fmax=200)
        low = librosa.onset.onset_strength(S=librosa.power_to_db(M), sr=sr)
        lt = librosa.frames_to_time(np.arange(len(low)), sr=sr)
        at = lambda ts: float(np.mean([low[min(len(low) - 1, int(np.searchsorted(lt, x)))] for x in ts]))
        half = 30.0 / tempo
        on, off_e, off_l = at(bt), at([x + half for x in bt]), at([x - half for x in bt if x - half >= 0])
        if max(off_e, off_l) > 1.3 * on:
            phase_shift = half if off_e >= off_l else -half
            bt = np.array([x + phase_shift for x in bt if x + phase_shift >= 0])
            if phase_shift < 0 and bt[0] - 60 / tempo >= -0.02:
                bt = np.concatenate([[max(0.0, bt[0] - 60 / tempo)], bt])
            bf = librosa.time_to_frames(bt, sr=sr)
    peak = float(env.max()) or 1.0
    bf = np.clip(bf, 0, len(env) - 1)
    beats = [{'t': round(float(t), 4), 'frame': int(round(t * fps)), 'strength': round(float(env[f]) / peak, 3)} for t, f in zip(bt, bf)]
    on = librosa.onset.onset_detect(onset_envelope=env, sr=sr)
    ons = [{'t': round(float(librosa.frames_to_time(f, sr=sr)), 4), 'strength': round(float(env[f]) / peak, 3)} for f in on]
    thr = float(np.percentile([o['strength'] for o in ons], 80)) if ons else 1
    phase = max(range(4), key=lambda k: sum(b['strength'] for b in beats[k::4])) if len(beats) >= 4 else 0
    # sections: big changes of RMS energy (drop, break) - useful to place the hero moment
    rms = librosa.feature.rms(y=y)[0]; rt = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    win = max(1, int(len(rms) / max(1, len(y) / sr) * 2))
    sm = np.convolve(rms, np.ones(win) / win, mode='same')
    d = np.abs(np.diff(sm)); sec = []
    if len(d):
        for i in mk.local_peaks(d, np.percentile(d, 99.5), gap=win * 2):
            sec.append(round(float(rt[i]), 3))
    return {'file': os.path.abspath(path), 'duration': round(len(y) / sr, 3), 'tempo': round(tempo, 2), 'phase_shift_s': round(phase_shift, 4),
            'beat_s': round(60 / tempo, 4) if tempo else None, 'beats': beats, 'downbeats': beats[phase::4],
            'accents': [o for o in ons if o['strength'] >= thr], 'section_changes': sec, **loudness(path)}


def voice(path, min_sil, db, script):
    import librosa
    y, sr = load(path)
    top_db = -db
    iv = librosa.effects.split(y, top_db=top_db, frame_length=1024, hop_length=256)
    segs = [[s / sr, e / sr] for s, e in iv]
    merged = []
    for s, e in segs:  # merge pauses shorter than min_sil (breaths inside a phrase)
        if merged and s - merged[-1][1] < min_sil:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    merged = [m for m in merged if m[1] - m[0] >= 0.12]
    lines = []
    if script:
        txt = open(script, encoding='utf-8').read().strip()
        lines = [l.strip() for l in (re.split(r'\n\s*\n', txt) if '\n\n' in txt else txt.splitlines()) if l.strip()]
    ph = [{'i': i, 'start': round(s, 3), 'end': round(e, 3), 'duration': round(e - s, 3),
           'text': lines[i] if i < len(lines) else None} for i, (s, e) in enumerate(merged)]
    res = {'file': os.path.abspath(path), 'duration': round(len(y) / sr, 3), 'phrases': ph, **loudness(path)}
    if lines and len(lines) != len(ph):
        res['warning'] = (f'{len(lines)} lignes de script pour {len(ph)} phrases détectées : '
                          f'ajuster --min-silence (plus grand = moins de phrases) ou découper le script autrement')
    return res


def align(path, script, res_voice, db=-30, min_sil=0.18):
    """Script lines aligned on the voice with word timings (faster-whisper, local), boundaries snapped to the
    real silences. Fills res_voice['phrases'] (one per script line, with its words) and res_voice['words']."""
    import difflib, unicodedata, librosa
    from faster_whisper import WhisperModel
    y, sr = load(path, 16000)
    m = WhisperModel(os.environ.get('MK_WHISPER', 'small'), device='cpu', compute_type='int8')
    segs, _ = m.transcribe(y, language=os.environ.get('MK_LANG', 'fr'), word_timestamps=True)
    W = [{'w': w.word.strip(), 'start': round(w.start, 3), 'end': round(w.end, 3)} for sg in segs for w in sg.words]
    norm = lambda t: ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if c.isalnum())
    txt = open(script, encoding='utf-8').read().strip()
    lines = [l.strip() for l in (re.split(r'\n\s*\n', txt) if '\n\n' in txt else txt.splitlines()) if l.strip()]
    sw = [(li, norm(x)) for li, l in enumerate(lines) for x in re.findall(r"[\w']+", l)]
    sw = [(li, x) for li, x in sw if x]
    ww = [norm(w['w']) for w in W]
    # character-level alignment is robust to small ASR mistakes (envoyer/envoyez, un geste/ingeste)
    sa = ''.join(x for _, x in sw); wa = ''.join(ww)
    s_owner = [li for li, x in sw for _ in x]; w_owner = [i for i, x in enumerate(ww) for _ in x]
    mp = {}
    for a0, b0, n in difflib.SequenceMatcher(None, sa, wa, autojunk=False).get_matching_blocks():
        for k in range(n):
            mp.setdefault(s_owner[a0 + k], []).append(w_owner[b0 + k])
    iv = librosa.effects.split(y, top_db=-db, frame_length=1024, hop_length=256)
    gaps = [(iv[i][1] / sr, iv[i + 1][0] / sr) for i in range(len(iv) - 1) if (iv[i + 1][0] - iv[i][1]) / sr >= min_sil * 0.6]
    def snap(t, side):
        best = None
        for g0, g1 in gaps:
            edge = g1 if side == 'start' else g0
            if abs(edge - t) <= 0.35 and (best is None or abs(edge - t) < abs(best - t)):
                best = edge
        return round(best if best is not None else t, 3)
    ph = []
    for li, l in enumerate(lines):
        idx = sorted(set(mp.get(li, [])))
        if not idx:
            ph.append({'i': li, 'start': None, 'end': None, 'text': l, 'words': []}); continue
        st, en = W[idx[0]]['start'], W[idx[-1]]['end']
        ph.append({'i': li, 'start': snap(st, 'start'), 'end': snap(en, 'end'), 'text': l, 'words': [W[i] for i in idx]})
    for k in range(len(ph)):  # lines never overlap
        if k and ph[k]['start'] is not None and ph[k - 1]['end'] is not None and ph[k]['start'] < ph[k - 1]['end']:
            ph[k]['start'] = ph[k - 1]['end']
        if ph[k]['start'] is not None:
            ph[k]['duration'] = round(ph[k]['end'] - ph[k]['start'], 3)
    res_voice['phrases'] = ph; res_voice['words'] = W; res_voice['aligned'] = 'faster-whisper + silences'
    res_voice.pop('warning', None)


def main():
    a = sys.argv
    if len(a) < 2 or a[1].startswith('--'):
        sys.exit(__doc__)
    out = a[1]; fps = mk.arg(a, 'fps', 30, float)
    res = {'fps': fps}
    m = mk.arg(a, 'music'); v = mk.arg(a, 'voice')
    if m:
        res['music'] = music(m, fps)
        M = res['music']
        print(f"musique : {M['duration']} s, {M['tempo']} BPM ({M['beat_s']} s par temps), {len(M['beats'])} temps, "
              f"{len(M['accents'])} accents, changements de section {M['section_changes']}, {M['lufs']} LUFS")
    if v:
        res['voice'] = voice(v, mk.arg(a, 'min-silence', 0.35, float), mk.arg(a, 'silence-db', -38, float), mk.arg(a, 'script'))
        if '--align' in a and mk.arg(a, 'script'):
            align(v, mk.arg(a, 'script'), res['voice'], mk.arg(a, 'silence-db', -30, float), mk.arg(a, 'min-silence', 0.18, float))
        Vv = res['voice']
        print(f"voix off : {Vv['duration']} s, {len(Vv['phrases'])} phrases, {Vv['lufs']} LUFS")
        for p in Vv['phrases']:
            print(f"  #{p['i']:02d} {p['start']:7.2f}–{p['end']:7.2f} s  {p['text'] or ''}" if p['start'] is not None else f"  #{p['i']:02d} NON TROUVÉE  {p['text']}")
        if 'warning' in Vv:
            print('  ATTENTION :', Vv['warning'])
    if not (m or v):
        sys.exit('donner --music et/ou --voice')
    mk.save_json(res, out)
    print('->', out)


if __name__ == '__main__':
    main()
