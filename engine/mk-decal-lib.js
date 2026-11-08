/* s2_lib.js — moteur commun des décalques s2-s5 (lute, images 46-279).
   Rejoue, image par image, les paramètres MESURÉS sur l'original (tracks/sN.js) :
   - text   : mot Inter vivant (runs + décalages en em mesurés), taille fs, plume (x, ligne de base y),
              flou gaussien directionnel (sx, sy) mesuré, opacité op, découpe par une forme (clip)
   - rect   : rectangle arrondi (pilule, panneau, volet) x, y, w, h, r, flou sx, sy, angle a (deg, centre)
   - quad   : rectangle posé sur 4 coins mesurés (pilule penchée) via matrix3d
   - circle : disque cx, cy, r
   - sprite : image (logo, matte) posée en x, y, échelle s, flou, opacité
   - plate  : image par image (effets irréguliers : fouets, sphères de verre), posée en x, y
   Fond : plaque par image assets/s2_bg/NNNN.jpg (inpaint) ou aplat menthe mesuré #00FEB6. */
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  window.S2LIB = function (DATA, opt = {}) {
    const st = document.getElementById('st'), bg = document.getElementById('bg');
    const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('width', 0); svg.setAttribute('height', 0);
    svg.style.position = 'absolute'; const defs = document.createElementNS(NS, 'defs'); svg.appendChild(defs); st.appendChild(svg);
    const els = {}, order = Object.entries(DATA.els).sort((a, b) => (a[1].z || 0) - (b[1].z || 0));
    let baseK = null;
    function mkFilter(id) {
      const f = document.createElementNS(NS, 'filter'); f.setAttribute('id', 'fb_' + id);
      f.setAttribute('x', '-50%'); f.setAttribute('y', '-50%'); f.setAttribute('width', '200%'); f.setAttribute('height', '200%');
      f.setAttribute('color-interpolation-filters', 'sRGB');
      const g = document.createElementNS(NS, 'feGaussianBlur'); f.appendChild(g); defs.appendChild(f); return g;
    }
    for (const [id, e] of order) {
      const wrap = document.createElement('div'); wrap.className = 'wrap'; st.appendChild(wrap);
      const inner0 = document.createElement('div'); inner0.className = 'inner'; wrap.appendChild(inner0);
      const inner = document.createElement('div'); inner.className = 'inner'; inner.style.transformOrigin = '0 0'; inner0.appendChild(inner);
      const o = { e, wrap, inner: inner0, tf: inner, blur: mkFilter(id), parts: [] };
      if (e.type === 'text') {
        for (const r of e.runs) {
          const s = document.createElement('span'); s.className = 'tx'; s.textContent = r;
          s.style.color = e.color; s.style.fontVariationSettings = `'wght' ${e.wght}, 'opsz' ${e.opsz}`;
          inner.appendChild(s); o.parts.push(s);
        }
      } else if (e.type === 'rect' || e.type === 'circle' || e.type === 'quad') {
        const d = document.createElement('div'); d.className = 'shape'; d.style.background = e.color; inner.appendChild(d); o.parts.push(d);
      } else if (e.type === 'coin') {   // pièce de verre : ellipse + dégradés CSS mesurés + logo SVG vectoriel (repère normalisé)
        const d = document.createElement('div'); d.className = 'shape'; d.style.borderRadius = '50%'; d.style.overflow = 'hidden';
        // liseré de verre mesuré (image 225 : anneau clair ~3 px + lueur cyan)
        d.style.boxShadow = opt.rim || 'none';
        const sv = document.createElementNS(NS, 'svg'); sv.setAttribute('viewBox', '-1 -1 2 2'); sv.setAttribute('preserveAspectRatio', 'none');
        sv.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%';
        sv.innerHTML = (e.logo || []).map(dd => `<path d="${dd}" fill="#FFFFFF"/>`).join(''); d.appendChild(sv); inner.appendChild(d); o.parts.push(d, sv);
      } else if (e.type === 'vec') {   // formes vectorielles mesurées : lueur (flou s2, gain g) + cœur (flou s1)
        const sv = document.createElementNS(NS, 'svg'); sv.setAttribute('width', 736); sv.setAttribute('height', 414); sv.style.position = 'absolute'; sv.style.overflow = 'visible';
        const df = document.createElementNS(NS, 'defs');
        df.innerHTML = `<filter id="vg_${id}" x="-50%" y="-50%" width="200%" height="200%" color-interpolation-filters="sRGB"><feGaussianBlur stdDeviation="4"/><feComponentTransfer><feFuncA type="linear" slope="0.3"/></feComponentTransfer></filter>` +
          `<filter id="vc_${id}" x="-50%" y="-50%" width="200%" height="200%" color-interpolation-filters="sRGB"><feGaussianBlur stdDeviation="0.5"/></filter>`;
        const gg = document.createElementNS(NS, 'g'), gc = document.createElementNS(NS, 'g');
        gg.setAttribute('filter', `url(#vg_${id})`); gc.setAttribute('filter', `url(#vc_${id})`);
        sv.appendChild(df); sv.appendChild(gg); sv.appendChild(gc); inner.appendChild(sv); o.parts.push(sv, gg, gc, df);
      } else if (e.type === 'sprite' || e.type === 'plate') {
        const im = document.createElement('img'); im.className = 'shape'; if (e.src) im.src = e.src; inner.appendChild(im); o.parts.push(im);
      }
      els[id] = o;
    }
    function baseline() {   // ligne de base réelle d'un span Inter (line-height 1) à 100 px, mesurée dans la page
      const s = document.createElement('span'); s.className = 'tx'; s.style.fontSize = '100px'; s.style.visibility = 'visible'; s.textContent = 'H';
      const p = document.createElement('span'); p.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline';
      s.appendChild(p); st.appendChild(s); const k = (p.getBoundingClientRect().top - s.getBoundingClientRect().top) / 100; s.remove(); return k;
    }
    // valeur interpolée d'une piste {f: obj} à la position fp (sous-images)
    function at(fr, fp) {
      if (!fr) return null; const f0 = Math.floor(fp + 1e-6), k = fp - f0, a = fr[f0], b = fr[f0 + 1];
      if (a == null) return (k > 0.5 && b != null) ? b : null;
      if (b == null || k < 1e-6 || typeof a !== 'object' || Array.isArray(a) !== Array.isArray(b)) return a;
      if (Array.isArray(a)) return a.map((v, i) => typeof v === 'number' ? v + (b[i] - v) * k : v);
      const o = {}; for (const key in a) o[key] = (typeof a[key] === 'number' && typeof b[key] === 'number') ? a[key] + (b[key] - a[key]) * k : a[key]; return o;
    }
    function clipCss(c, fp) {
      if (!c) return '';
      const src = els[c] ? els[c].e : null; if (!src) return '';
      const p = at(src.frames, fp); if (!p) return 'inset(50%)';
      if (src.type === 'circle') return `circle(${p.r.toFixed(2)}px at ${p.cx.toFixed(2)}px ${p.cy.toFixed(2)}px)`;
      if (src.type === 'rect') return `inset(${p.y.toFixed(2)}px ${(736 - p.x - p.w).toFixed(2)}px ${(414 - p.y - p.h).toFixed(2)}px ${p.x.toFixed(2)}px round ${(p.r || 0).toFixed(2)}px)`;
      if (src.type === 'quad') return `polygon(${p.q.map(v => v[0].toFixed(2) + 'px ' + v[1].toFixed(2) + 'px').join(',')})`;
      return '';
    }
    function setBlur(o, p) {
      const sx = p.sx || 0, sy = p.sy || 0;
      if (sx > 0.25 || sy > 0.25) { o.blur.setAttribute('stdDeviation', `${sx.toFixed(2)} ${sy.toFixed(2)}`); o.inner.style.filter = `url(#fb_${o.blurId || ''})`; }
      else o.inner.style.filter = '';
    }
    function render(t) {
      const fp = t * 25 + 1e-6, f = Math.floor(fp);
      if (baseK == null) baseK = baseline();
      const B = DATA.bg[f] || 'plate';
      if (B === 'mint') { bg.style.visibility = 'hidden'; st.style.background = DATA.mint; }
      else { bg.style.visibility = 'visible'; bg.src = `../assets/s2_bg/${String(f + 1).padStart(4, '0')}.jpg`; st.style.background = '#021012'; }
      for (const id in els) {
        const o = els[id], e = o.e;
        if (e.type === 'group') { o.wrap.style.visibility = 'hidden'; continue; }
        let p = at(e.frames, fp), g = null;
        if (e.group) { g = at(DATA.els[e.group].frames, fp); if (!g) p = null; else if (p) p = Object.assign({}, p, { sx: g.sx || 0, sy: g.sy || 0, op: (g.op == null ? 1 : g.op) * (p.op == null ? 1 : p.op) }); }
        if (!p || (opt.hide && opt.hide.includes(id))) { o.wrap.style.visibility = 'hidden'; continue; }
        if (g) { const G = DATA.els[e.group], pv = G.pivot;
          o.tf.style.transform = `translate(${g.x.toFixed(3)}px, ${g.y.toFixed(3)}px) rotate(${(g.a || 0).toFixed(4)}deg) scale(${(g.s || 1).toFixed(5)}, ${((g.s || 1) * (g.k == null ? 1 : g.k)).toFixed(5)}) translate(${-pv[0]}px, ${-pv[1]}px)`; }
        else o.tf.style.transform = 'none';
        o.wrap.style.visibility = 'visible';
        o.wrap.style.clipPath = clipCss(p.clip !== undefined ? p.clip : e.clip, fp);
        o.inner.style.opacity = p.op == null ? 1 : Math.max(0, Math.min(1, p.op));
        const sx = p.sx || 0, sy = p.sy || 0;
        if (sx > 0.25 || sy > 0.25) { o.blur.setAttribute('stdDeviation', `${sx.toFixed(3)} ${sy.toFixed(3)}`); o.inner.style.filter = `url(#fb_${id})`; }
        else o.inner.style.filter = 'none';
        if (e.type === 'text') {
          o.parts.forEach((s, i) => {   // corps fixe 100 px + échelle : ligne de base exacte au sous-pixel (Chrome arrondit la ligne de base en mise en page)
            s.style.fontSize = '100px'; const k = p.fs / 100;
            const a = p.a || 0, ca = Math.cos(a * Math.PI / 180), sa = Math.sin(a * Math.PI / 180), d = e.offs[i] * p.fs;
            const x = p.x + d * ca, y = p.y + d * sa;   // plume du run (sur la ligne de base tournée)
            s.style.transform = `translate(${x.toFixed(3)}px, ${y.toFixed(3)}px)` + (a ? ` rotate(${a.toFixed(4)}deg)` : '') + ` translate(0px, ${(-baseK * p.fs).toFixed(3)}px) scale(${k.toFixed(5)})`;
          });
        } else if (e.type === 'rect') {
          const d = o.parts[0]; Object.assign(d.style, { left: p.x + 'px', top: p.y + 'px', width: Math.max(0, p.w) + 'px', height: Math.max(0, p.h) + 'px', borderRadius: (p.r || 0) + 'px',
            transform: p.a ? `rotate(${p.a}deg)` : 'none', background: p.color || e.color });
        } else if (e.type === 'circle') {
          const d = o.parts[0]; Object.assign(d.style, { left: (p.cx - p.r) + 'px', top: (p.cy - p.r) + 'px', width: 2 * p.r + 'px', height: 2 * p.r + 'px', borderRadius: '50%' });
        } else if (e.type === 'quad') {
          const d = o.parts[0]; Object.assign(d.style, { left: '0px', top: '0px', width: '736px', height: '414px', clipPath: `polygon(${p.q.map(v => v[0].toFixed(2) + 'px ' + v[1].toFixed(2) + 'px').join(',')})` });
        } else if (e.type === 'coin') {
          const [d, sv] = o.parts, logo = p.face === 'logo';
          Object.assign(d.style, { left: (p.cx - p.w / 2) + 'px', top: (p.cy - p.h / 2) + 'px', width: Math.max(0.5, p.w) + 'px', height: p.h + 'px',
            background: logo ? e.bgLogo : e.bgGlass, transform: p.ang ? `rotate(${p.ang}deg)` : 'none' });
          sv.style.display = logo ? 'block' : 'none';
        } else if (e.type === 'vec') {
          const [sv, gg, gc, df] = o.parts, f0 = Math.round(fp), q = e.frames[f0] || p;
          if (o.last !== f0) { o.last = f0;
            const h = q.paths.map(([k, d]) => `<path d="${d}" fill="${k === 'w' ? '#FFFFFF' : (k === 'd' ? '#002626' : '#00FEB6')}"/>`).join('');
            gg.innerHTML = h; gc.innerHTML = h;
            const fg = df.querySelector(`#vg_${id}`), fc = df.querySelector(`#vc_${id}`);
            fg.querySelector('feGaussianBlur').setAttribute('stdDeviation', Math.max(0.3, q.s2)); fg.querySelector('feFuncA').setAttribute('slope', q.g);
            fc.querySelector('feGaussianBlur').setAttribute('stdDeviation', Math.max(0.05, q.s1)); }
        } else if (e.type === 'sprite') {
          const d = o.parts[0]; Object.assign(d.style, { left: '0px', top: '0px', transform: `translate(${p.x.toFixed(3)}px, ${p.y.toFixed(3)}px) scale(${(p.s || 1).toFixed(5)}, ${(p.sy_ || p.s || 1).toFixed(5)})` });
        } else if (e.type === 'plate') {
          const d = o.parts[0]; const src = p.src; if (d.getAttribute('src') !== src) d.src = src;
          Object.assign(d.style, { left: '0px', top: '0px', transform: `translate(${p.x || 0}px, ${p.y || 0}px)` });
        }
        if (o.e.children) for (const c of o.e.children) {}
      }
    }
    return { render, els, at };
  };
})();
