"""Écrit scenes/sN.html (coquille commune) ; usage : python3 mkscene.py sN f0 f1"""
import sys
sc, f0, f1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
D = '/home/user/projets/master-skills-launch/decal/'
html = f'''<!doctype html><html><head><meta charset="utf-8"><title>Décalque {sc.upper()} lute</title>
<!-- Décalque mesuré images {f0}-{f1} (t = {f0/25:.2f}-{(f1+1)/25:.2f} s, temps global de la source). Aucune valeur posée à l'œil :
     tout vient de tracks/{sc}.js (mesures fitlib/track.py, formes, plaques). Rejoué par tracks/s2_lib.js. -->
<style>
@font-face{{font-family:Inter;src:url(../fonts/Inter[opsz,wght].ttf);font-weight:100 900}}
html,body{{margin:0;background:#000;overflow:hidden}}
#st{{position:relative;width:736px;height:414px;overflow:hidden;background:#021012}}
#bg{{position:absolute;left:0;top:0;width:736px;height:414px}}
.wrap{{position:absolute;left:0;top:0;width:736px;height:414px;visibility:hidden}}
.inner{{position:absolute;left:0;top:0;width:736px;height:414px}}
.tx{{position:absolute;left:0;top:0;transform-origin:0 0;white-space:pre;font-family:Inter;line-height:1;font-optical-sizing:none;font-kerning:normal;will-change:transform}}
.shape{{position:absolute;left:0;top:0;transform-origin:0 0}}
</style></head><body><div id="st"><img id="bg"></div>
<script src="../tracks/{sc}.js"></script><script src="../tracks/s2_lib.js"></script>
<script>
const P = Object.assign({{ hide: [] }}, JSON.parse(decodeURIComponent(location.hash.slice(1) || '{{}}')));
let L;
window.__rm = {{ ready: false,
  seek(t) {{ try {{ L.render(t); }} catch (e) {{ window.__mk_error = String(e.stack || e); }} }},
  settle() {{ return Promise.all([...document.images].filter(i => i.getAttribute('src') && i.style.visibility !== 'hidden').map(i => i.decode().catch(() => {{}}))); }} }};
document.fonts.load("500 20px Inter").then(() => document.fonts.ready).then(() => {{ L = S2LIB({sc.upper()}, P); L.render({f0}/25); window.__rm.ready = true; }});
</script></body></html>
'''
open(D + f'scenes/{sc}.html', 'w').write(html); print('ok')
