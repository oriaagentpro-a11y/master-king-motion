// Render an HTML/GSAP scene frame by frame, then encode it with ffmpeg.
// Usage: node render.mjs <scene.html> <out.mp4> --fps 30 --start 0 --end 5 --w 736 --h 414 [--frames-dir dir] [--audio src.mp4] [--brand brand.js]
// The page must expose window.__rm = { seek(t) } that puts every animation at time t (seconds).
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync, existsSync, writeFileSync, readdirSync } from 'node:fs';
import os from 'node:os';
import { PNG } from 'pngjs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
// Tools installed during this session (winget / Chocolatey / Homebrew) are not yet on an open terminal's PATH.
{
  const extra = process.platform === 'win32'
    ? [path.join(process.env.LOCALAPPDATA || '', 'Microsoft', 'WinGet', 'Links'), 'C:\\ProgramData\\chocolatey\\bin']
    : ['/opt/homebrew/bin', '/usr/local/bin'];
  const cur = (process.env.PATH || '').split(path.delimiter);
  process.env.PATH = [...extra.filter(d => existsSync(d) && !cur.includes(d)), ...cur].join(path.delimiter);
}

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const [html, out] = args;
const fps = Number(opt('fps', 30)), start = Number(opt('start', 0)), end = Number(opt('end', 5));
const W = Number(opt('w', 736)), H = Number(opt('h', 414));
const framesDir = opt('frames-dir', out.replace(/\.mp4$/, '_frames'));
const audio = opt('audio', null);
const holes = args.includes('--holes'); // foreground-only render used to punch plate holes (implies transparent)
const transparent = args.includes('--transparent') || holes;
const hash = opt('hash', ''); // JSON overrides passed to the scene (#...), e.g. which elements to show // PNG frames with alpha, for layering (no mp4 when out ends with /)
const exe = findChrome();

// Browser: $CHROME_PATH, else Playwright's own Chromium, else any installed Chromium / Chrome / Edge.
function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  try { const p = chromium.executablePath(); if (p && existsSync(p)) return p; } catch { /* not installed */ }
  const home = os.homedir(), roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, path.join(home, '.cache/ms-playwright'),
    path.join(home, 'Library/Caches/ms-playwright'), process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'ms-playwright'), '/opt/pw-browsers'];
  const inner = ['chrome-linux64/chrome', 'chrome-linux/chrome', 'chrome-win/chrome.exe', 'chrome-win64/chrome.exe',
    'chrome-mac/Chromium.app/Contents/MacOS/Chromium', 'chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium'];
  for (const r of roots) { if (!r || !existsSync(r)) continue;
    for (const d of readdirSync(r).filter(n => n.startsWith('chromium-')).sort().reverse())
      for (const i of inner) { const p = path.join(r, d, i); if (existsSync(p)) return p; } }
  const sys = ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/snap/bin/chromium',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'];
  return sys.find(existsSync); // undefined -> Playwright reports a clear error
}

rmSync(framesDir, { recursive: true, force: true });
mkdirSync(framesDir, { recursive: true });
const browser = await chromium.launch({ executablePath: exe, args: ['--force-color-profile=srgb', '--disable-lcd-text', '--font-render-hinting=none', '--allow-file-access-from-files', '--ignore-gpu-blocklist', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: Number(opt('scale', 1)) });   // --scale 2.6087 : scène 736x414 rendue en 1920x1080 (tout est en code : aucune perte)
page.on('pageerror', e => console.error('page error:', e.message));
// --brand brand.js : the brand file is injected before any scene script (window.BRAND), no scene edit needed
const brand = opt('brand', null);
if (brand) await page.addInitScript({ path: path.resolve(brand) });
await page.goto(pathToFileURL(path.resolve(html)).href + `?fps=${fps}` + (holes ? '&holes=1' : (transparent ? '&transparent=1' : '')) + (hash ? '#' + encodeURIComponent(hash) : ''));
await page.waitForFunction(() => window.__rm && window.__rm.ready === true, null, { timeout: 30000 });
await page.evaluate(() => document.fonts.ready);
const f0 = Math.round(start * fps), f1 = Math.round(end * fps);
// Motion blur: a scene may expose window.__rm.blurAt(t) -> [samples, shutter] (shutter in frames, 0.5 = 180 deg).
// The frame is then the average of `samples` renders spread over the shutter, like a camera / After Effects.
let blurred = 0;
async function settleOrDie() {   /* image sequences decoded before the shot; a missing one stops the render */
  await page.evaluate(() => (window.__rm.settle ? window.__rm.settle() : null));
  const e = await page.evaluate(() => window.__mk_error || null);
  if (e) { console.error('erreur dans le film : ' + e); process.exit(1); }
  // image cassée (fichier absent, mauvais chemin) : arrêt immédiat — un logo manquant ne doit JAMAIS passer inaperçu
  const broken = await page.evaluate(() => [...document.images].filter(i => i.getAttribute('src') && i.complete && i.naturalWidth === 0
    && getComputedStyle(i).visibility !== 'hidden').map(i => i.getAttribute('src')));
  if (broken.length) { console.error('image introuvable dans le film : ' + [...new Set(broken)].join(', ')); process.exit(1); }
}
// --warp "t1:extra1,t2:extra2" (secondes, temps global) : PAUSES de respiration. Autour de chaque instant ti, le temps
// de la scène ralentit en douceur jusqu'à 10 % de sa vitesse (rampes en cosinus de 0,2 s) le temps d'ajouter extra_i
// secondes de film : les animations gardent leur vitesse et leurs courbes, seuls les moments de repos s'allongent.
const TIMES = (() => { const W = (opt('warp', '') || '').split(',').filter(Boolean).map(x => x.split(':').map(Number));
  const t0 = f0 / fps, t1 = f1 / fps, extra = W.filter(([t]) => t >= t0 && t < t1).reduce((a, [, e]) => a + e, 0);
  if (!extra) { const r = []; for (let f = f0; f < f1; f++) r.push([f / fps, 1]); return r; }
  const dT = 1 / (fps * 20), R = 0.2, SMIN = 0.1;
  const holds = W.filter(([t]) => t >= t0 && t < t1).map(([t, e]) => { const L = (e - 2 * R * (1 - SMIN) / 2) / (1 - SMIN); return { t, L: Math.max(0, L), e }; });
  const sp = (tSrc, inHold) => 1;   // vitesse calculée en temps de sortie ci-dessous
  const out = []; let tS = t0, T = 0, h = 0, phase = null, pT = 0;
  const N = Math.round((t1 - t0 + extra) * fps);
  const dips = []; // fenêtres en temps de sortie, construites à la volée
  let next = 0, tOut = 0, cur = null;
  for (let j = 0; j < N; j++) {
    const target = j / fps;
    while (tOut < target - 1e-9) {
      if (!cur && next < holds.length && tS >= holds[next].t) { cur = { start: tOut, L: holds[next].L }; next++; }
      let s = 1;
      if (cur) { const u = tOut - cur.start, tot = 2 * R + cur.L;
        if (u >= tot) cur = null;
        else s = u < R ? 1 - (1 - SMIN) * (1 - Math.cos(Math.PI * u / R)) / 2 : (u < R + cur.L ? SMIN : SMIN + (1 - SMIN) * (1 - Math.cos(Math.PI * (u - R - cur.L) / R)) / 2); }
      const step = Math.min(dT, target - tOut); tS += s * step; tOut += step; cur && (cur.s = s);
    }
    out.push([Math.min(tS, t1 - 1e-6), cur ? (cur.s || 1) : 1]);
  }
  console.log(`pauses : +${extra.toFixed(2)} s (${N} images au lieu de ${f1 - f0})`); return out; })();
for (let j = 0; j < TIMES.length; j++) {
  const f = f0 + j, [tSrc, spd] = TIMES[j];
  const out = path.join(framesDir, `f_${String(j).padStart(5, '0')}.png`);
  const mb = await page.evaluate(t => (window.__rm.blurAt ? window.__rm.blurAt(t) : null), tSrc);
  if (!mb || mb[0] <= 1) {
    await page.evaluate(t => { window.__rm.seek(t); }, tSrc);
    await settleOrDie();   // image sequences decoded before the shot
    await page.screenshot({ path: out, omitBackground: transparent });
    continue;
  }
  const [n, shutter] = mb; let acc = null, w = 0, h = 0;
  for (let i = 0; i < n; i++) {
    const t = tSrc + ((i + 0.5) / n - 0.5) * shutter * spd / fps;   // obturateur à l'échelle de la vitesse (pause = moins de flou)
    await page.evaluate(tt => { window.__rm.seek(tt); }, t);
    await settleOrDie();
    const img = PNG.sync.read(await page.screenshot({ omitBackground: transparent }));
    if (!acc) { w = img.width; h = img.height; acc = new Float32Array(img.data.length); }
    if (transparent) { for (let k = 0; k < img.data.length; k += 4) { const a = img.data[k + 3] / 255;
        acc[k] += img.data[k] * a; acc[k + 1] += img.data[k + 1] * a; acc[k + 2] += img.data[k + 2] * a; acc[k + 3] += img.data[k + 3]; } }
    else for (let k = 0; k < img.data.length; k++) acc[k] += img.data[k];
  }
  const png = new PNG({ width: w, height: h });
  for (let k = 0; k < acc.length; k += 4) {
    if (transparent) { const a = acc[k + 3] / n; const inv = a > 0 ? 255 / (a * n) : 0;
      png.data[k] = Math.round(acc[k] * inv); png.data[k + 1] = Math.round(acc[k + 1] * inv); png.data[k + 2] = Math.round(acc[k + 2] * inv); png.data[k + 3] = Math.round(a); }
    else { png.data[k] = Math.round(acc[k] / n); png.data[k + 1] = Math.round(acc[k + 1] / n); png.data[k + 2] = Math.round(acc[k + 2] / n); png.data[k + 3] = 255; }
  }
  writeFileSync(out, PNG.sync.write(png)); blurred++;
}
if (blurred) console.log(`motion blur on ${blurred} frames`);
await browser.close();
if (transparent) { console.log(`rendered ${f1 - f0} transparent frames -> ${framesDir}`); process.exit(0); }
const enc = ['-y', '-v', 'error', '-framerate', String(fps), '-i', path.join(framesDir, 'f_%05d.png')];
if (audio) enc.push('-ss', String(start), '-t', String(end - start), '-i', audio, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-shortest');
enc.push('-c:v', 'libx264', '-preset', 'veryfast', '-crf', '12', '-pix_fmt', 'yuv420p', out);
execFileSync('ffmpeg', enc, { stdio: 'inherit' });
// the PNG frames are only a step towards the mp4: removed unless asked for (--frames-dir or --keep-frames)
if (!args.includes('--frames-dir') && !args.includes('--keep-frames')) rmSync(framesDir, { recursive: true, force: true });
console.log(`rendered ${f1 - f0} frames -> ${out}`);
