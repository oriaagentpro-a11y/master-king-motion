"""Download a reference video from a share link (Pinterest pin.it / pinterest.com/pin, or a direct .mp4 / .m3u8 URL)
at the BEST resolution available, with its sound (rule 81).

Usage: python3 fetch_reference.py <url> out.mp4
- Pinterest: the page holds an HLS master playlist (…/hls/…/<id>.m3u8) and a 720w .mp4. The master lists several
  variants (256x144 … 736x414 for the 720w). Plain `ffmpeg -i master.m3u8` takes the FIRST (lowest: 256x144):
  unusable for measuring. This tool reads every RESOLUTION, takes the largest, adds the separate audio playlist.
- Prints the final size, fps and duration. Pinterest caps at 736x414 for 16:9 videos: say so in the report (all
  pixel measurements are then at 736x414, like reference A of the MTN case).
"""
import sys, re, subprocess, json, urllib.request


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.geturl(), r.read().decode('utf-8', 'replace')


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    url, out = sys.argv[1], sys.argv[2]
    master = None
    if url.endswith('.m3u8'):
        master = url
    elif not url.endswith('.mp4'):
        final, html = get(url)
        m = re.findall(r'https://v1\.pinimg\.com/videos/[^"\\ ]+?/hls/[^"\\ ]+?\.m3u8', html)
        mp4 = re.findall(r'https://v1\.pinimg\.com/videos/[^"\\ ]+?\.mp4', html)
        if m:
            master = sorted(set(m), key=len)[0]
        elif mp4:
            url = sorted(set(mp4))[-1]
        else:
            sys.exit('aucune vidéo trouvée sur la page : ' + final)
    if master:
        _, M = get(master); base = master.rsplit('/', 1)[0]
        lines = M.splitlines(); variants = []
        for i, l in enumerate(lines):
            r = re.search(r'RESOLUTION=(\d+)x(\d+)', l)
            if r and i + 1 < len(lines):
                variants.append((int(r.group(1)) * int(r.group(2)), lines[i + 1].strip()))
        if not variants:
            sys.exit('playlist sans variantes : ' + master)
        best = max(variants)[1]
        aud = re.search(r'TYPE=AUDIO[^\n]*URI="([^"]+)"', M)
        cmd = ['ffmpeg', '-v', 'error', '-y', '-i', f'{base}/{best}']
        if aud:
            cmd += ['-i', f'{base}/{aud.group(1)}', '-map', '0:v:0', '-map', '1:a:0']
        subprocess.run(cmd + ['-c', 'copy', out], check=True)
    else:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', url, '-c', 'copy', out], check=True)
    p = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height,r_frame_rate:format=duration',
                                   '-of', 'json', out], capture_output=True, text=True).stdout)
    v = next(s for s in p['streams'] if s['codec_type'] == 'video')
    print(f"{out} : {v['width']}x{v['height']} {v['r_frame_rate']} i/s, {float(p['format']['duration']):.2f} s, "
          f"son {'oui' if any(s['codec_type'] == 'audio' for s in p['streams']) else 'non'}")


if __name__ == '__main__':
    main()
