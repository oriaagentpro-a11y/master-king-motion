// Export, image par image, du téléphone d'un film pour le rendu Blender Cycles (règle 135).
// node engine/export_phone.mjs page.html out_dir [--fps 30] [--from 0] [--to <durée>]
// La page appelle, pour chaque image où un téléphone est visible, window.__phoneRec = {shot, f, fov, pose:{x,y,z,rx,ry,rz},
// screen: clé} et garde les écrans dans window.__screens[clé] (canevas). Sortie :
//   out_dir/phone_track.json  {fps, frames: {n: {shot, fov, pose, screen}}}   (n = image du film)
//   out_dir/screens/<clé>.png  chaque écran une fois (texture de l'écran dans Blender)
import { chromium } from 'playwright';
import path from 'node:path'; import { pathToFileURL } from 'node:url'; import fs from 'node:fs';
const args = process.argv.slice(2); const [html, out] = args; const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? +args[i + 1] : d; };
fs.mkdirSync(path.join(out, 'screens'), { recursive: true });
const b = await chromium.launch({ args: ['--use-gl=angle', '--enable-webgl', '--ignore-gpu-blocklist', '--allow-file-access-from-files'] });
const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
await p.goto(pathToFileURL(path.resolve(html)).href); await p.waitForFunction(() => window.__rm && window.__rm.ready, null, { timeout: 60000 });
const fps = opt('fps', 30), dur = await p.evaluate(() => window.__rm.duration || 0), f0 = Math.round(opt('from', 0) * fps), f1 = Math.round(opt('to', dur) * fps);
const frames = {}, saved = new Set();
for (let n = f0; n <= f1; n++) {
  const rec = await p.evaluate(t => { window.__rm.seek(t); return window.__phoneRec; }, n / fps);
  if (!rec) continue;
  frames[n] = rec;
  if (!saved.has(rec.screen)) {
    const url = await p.evaluate(k => window.__screens[k].toDataURL('image/png'), rec.screen);
    fs.writeFileSync(path.join(out, 'screens', rec.screen.replace(/[^\w.-]+/g, '_') + '.png'), Buffer.from(url.split(',')[1], 'base64')); saved.add(rec.screen);
  }
}
fs.writeFileSync(path.join(out, 'phone_track.json'), JSON.stringify({ fps, frames }));
console.log(Object.keys(frames).length, 'images avec téléphone,', saved.size, 'écrans ->', out); await b.close();
