"""Delivery: mix the user's sound (voice-over + music ducked under the voice + optional SFX) and encode.

Usage: python3 finalize.py <silent.mp4> <final.mp4> [--music m.mp3] [--voice v.wav] [--sfx sfx.wav]
                           [--timing timing.json] [--voice-offset s] [--music-offset s] [--music-start s]
                           [--music-db -6] [--voice-db 0] [--sfx-db -4] [--duck 8] [--fade-out 1.5]
                           [--lufs -14] [--crf 16] [--copy-video]
- voice: high-pass 80 Hz, gentle compression, placed at --voice-offset (default: timing.json voice_offset)
- music: starts at --music-offset in the video (from --music-start inside the file), ducked by the voice
  (sidechain, ratio --duck, 0 = off), faded out over the last --fade-out seconds
- everything normalised to --lufs integrated (-14 = YouTube / Facebook / Instagram), true peak -1 dBTP,
  48 kHz AAC 320 kb/s, cut exactly to the video length
- video: H.264 High, CRF --crf (16 = visually lossless), preset slow, yuv420p, BT.709 tags, +faststart
  (or --copy-video to keep the rendered stream).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 3:
        sys.exit(__doc__)
    src, out = a[1], a[2]
    V = mk.probe(src); dur = V['frames'] / V['fps']
    T = json.load(open(mk.arg(a, 'timing'))) if mk.arg(a, 'timing') else {}
    music, voice, sfx = mk.arg(a, 'music'), mk.arg(a, 'voice'), mk.arg(a, 'sfx')
    vo_off = mk.arg(a, 'voice-offset', T.get('voice_offset', 0.0), float)
    mu_off = mk.arg(a, 'music-offset', T.get('music_offset', 0.0), float)
    mu_start = mk.arg(a, 'music-start', T.get('music_start') or 0.0, float)
    duck = mk.arg(a, 'duck', 8.0, float); fade = mk.arg(a, 'fade-out', 1.5, float); lufs = mk.arg(a, 'lufs', -14.0, float)
    inputs, filt, mix = ['-i', src], [], []
    k = 1
    if voice:
        inputs += ['-i', voice]; vi = k; k += 1
        filt.append(f"[{vi}:a]aresample=48000,aformat=channel_layouts=stereo,highpass=f=80,"
                    f"acompressor=threshold=0.125:ratio=3:attack=5:release=120:makeup=1.5,volume={mk.arg(a, 'voice-db', 0.0, float)}dB,"
                    f"adelay={int(vo_off * 1000)}|{int(vo_off * 1000)},apad,atrim=0:{dur:.4f},asplit=2[vo][key]")
    if music:
        inputs += ['-ss', f'{mu_start}', '-i', music]; mi = k; k += 1
        filt.append(f"[{mi}:a]aresample=48000,aformat=channel_layouts=stereo,volume={mk.arg(a, 'music-db', -6.0, float)}dB,"
                    f"adelay={int(mu_off * 1000)}|{int(mu_off * 1000)},apad,atrim=0:{dur:.4f},"
                    + ("afade=t=in:st=0:d=0.25," if mu_start > 0 else '')
                    + f"afade=t=out:st={max(0, dur - fade):.4f}:d={fade:.4f}[mu0]")
        if voice and duck > 0:
            filt.append(f'[mu0][key]sidechaincompress=threshold=0.04:ratio={duck}:attack=25:release=450:makeup=1[mu]')
        else:
            filt.append('[mu0]anull[mu]')
            if voice:
                filt.append('[key]anullsink')
        mix.append('[mu]')
    elif voice:
        filt.append('[key]anullsink')
    if voice:
        mix.append('[vo]')
    if sfx:
        inputs += ['-i', sfx]; si = k; k += 1
        filt.append(f"[{si}:a]aresample=48000,aformat=channel_layouts=stereo,volume={mk.arg(a, 'sfx-db', -4.0, float)}dB,apad,atrim=0:{dur:.4f}[fx]")
        mix.append('[fx]')
    cmd = ['ffmpeg', '-y', '-v', 'error'] + inputs
    if mix:
        filt.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=longest,"
                    f"loudnorm=I={lufs}:TP=-1:LRA=11,aresample=48000,atrim=0:{dur:.4f}[aout]")
        cmd += ['-filter_complex', ';'.join(filt), '-map', '0:v', '-map', '[aout]', '-c:a', 'aac', '-b:a', '320k', '-ar', '48000']
    else:
        cmd += ['-map', '0:v']
    if '--copy-video' in a:
        cmd += ['-c:v', 'copy']
    else:
        cmd += ['-c:v', 'libx264', '-preset', 'slow', '-crf', str(mk.arg(a, 'crf', 16, int)), '-profile:v', 'high', '-pix_fmt', 'yuv420p',
                '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-g', str(int(round(V['fps'] * 2)))]
    cmd += ['-movflags', '+faststart', '-t', f'{dur:.4f}', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit('ffmpeg : ' + r.stderr[-1500:])
    F = mk.probe(out)
    ad = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=duration', '-of', 'csv=p=0', out],
                        capture_output=True, text=True).stdout.strip()
    print(f"{out} : {F['w']}x{F['h']} {F['fps']:g} i/s, {F['frames']} images ({dur:.3f} s)"
          + (f", son {float(ad):.3f} s" if ad else ', sans son'))


if __name__ == '__main__':
    main()
