// Captures du film à des instants donnés (storyboard, contrôle image par image) : node engine/snap.mjs page.html out_dir t1 t2 ...
// La page expose window.__rm.seek(t) et window.__scene (nom de la scène) ; les erreurs de la console sont listées à la fin.
import { chromium } from 'playwright';
import path from 'node:path'; import { pathToFileURL } from 'node:url'; import fs from 'node:fs';
const [html, out, ...ts] = process.argv.slice(2); fs.mkdirSync(out, { recursive: true });
const b = await chromium.launch({ args: ['--use-gl=angle', '--enable-webgl', '--ignore-gpu-blocklist', '--allow-file-access-from-files'] });
const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
const logs = []; p.on('console', m => logs.push(m.type() + ': ' + m.text())); p.on('pageerror', e => logs.push('ERR ' + e.message));
await p.goto(pathToFileURL(path.resolve(html)).href); await p.waitForFunction(() => window.__rm && window.__rm.ready, null, { timeout: 60000 }).catch(() => {});
if (!(await p.evaluate(() => !!(window.__rm && window.__rm.ready)))) { console.log('PAGE NON PRÊTE — console : ' + logs.join(' | ')); await b.close(); process.exit(1); }
for (const t of ts) { await p.evaluate(t => window.__rm.seek(+t), t); await p.waitForTimeout(60);
  const name = await p.evaluate(() => window.__scene); await p.screenshot({ path: path.join(out, `t${(+t).toFixed(2)}.png`) }); console.log(t, name); }
console.log(logs.slice(0, 20).join('\n')); await b.close();
