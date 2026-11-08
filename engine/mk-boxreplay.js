/* mk-boxreplay.js — rejoue des boîtes mesurées image par image (scripts/box_tracker.py), règle 91.
   Chaque élément du film est posé, à chaque image, sur la boîte de l'élément correspondant de la référence :
   même image, même taille, même partie visible. Les sous-images (flou de mouvement) sont interpolées.
     const RB = MKRB({fps: 25});
     RB.box(track, fpos)            -> [x, y, w, h] interpolée, ou null si l'élément est caché
     RB.val(series, fpos)           -> valeur interpolée d'une série {frame: v}
     RB.glyph(el, b, ref, o)        -> pose une lettre : échelle o.s (sinon b.w/ref.w), haut à b.y, bord gauche à o.x ?? b.x,
                                       découpée sous o.clip (ligne de masque) ; ref = boîte d'encre de la lettre entière à l'échelle 1
     RB.stretch(el, b, ref)         -> étire un sprite / une forme dans la boîte (pièces de logo, formes qui s'ouvrent)
   L'élément HTML doit avoir position:absolute; left:0; top:0; transform-origin:0 0, et sa propre boîte d'encre à
   l'échelle 1 égale à ref (calée une fois par RB.calibrate : on mesure l'encre réelle du texte dans la page). */
(function () {
  window.MKRB = function (o) {
    const fps = o.fps || 25;
    function box(tr, fpos) {
      if (!tr) return null;
      const f0 = Math.floor(fpos + 1e-6), k = fpos - f0, a = tr[f0], b = tr[f0 + 1];
      if (!a && !b) return null;
      if (!a) return k > 0.5 ? b : null;
      if (!b || k === 0) return a;
      return a.map((v, i) => v + (b[i] - v) * k);
    }
    function val(se, fpos, dflt = null) {
      if (!se) return dflt;
      const f0 = Math.floor(fpos + 1e-6), k = fpos - f0, a = se[f0], b = se[f0 + 1];
      if (a == null && b == null) return dflt;
      if (a == null) return b; if (b == null) return a;
      return a + (b - a) * k;
    }
    // encre réelle d'un élément texte à l'échelle 1 (getBoundingClientRect d'une boîte ≠ encre : on mesure les pixels)
    function inkBox(el) {
      const r = el.getBoundingClientRect(), c = document.createElement('canvas'); c.width = Math.ceil(r.width) + 4; c.height = Math.ceil(r.height) + 4;
      const g = c.getContext('2d'), cs = getComputedStyle(el);
      g.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`; g.textBaseline = 'alphabetic'; g.fillStyle = '#fff';
      const m = g.measureText(el.textContent);
      return { left: -m.actualBoundingBoxLeft, top: -m.actualBoundingBoxAscent, w: m.actualBoundingBoxLeft + m.actualBoundingBoxRight,
               h: m.actualBoundingBoxAscent + m.actualBoundingBoxDescent, ascent: m.fontBoundingBoxAscent };
    }
    function calibrate(el, ref) {   // taille de police telle que la HAUTEUR d'encre de la lettre entière = ref.h
      el.style.fontSize = '100px'; el.style.lineHeight = '1';
      let ib = inkBox(el); const fs = 100 * ref[3] / ib.h; el.style.fontSize = fs + 'px'; ib = inkBox(el);
      // position RÉELLE de la ligne de base dans la boîte CSS (dépend de line-height) : mesurée dans la page
      const probe = document.createElement('span'); probe.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline';
      const t0 = el.style.transform; el.style.transform = 'none'; el.appendChild(probe);
      ib.base = probe.getBoundingClientRect().top - el.getBoundingClientRect().top; probe.remove(); el.style.transform = t0;
      el._ink = ib; el._ref = ref; return ib;
    }
    function glyph(el, b, o = {}) {
      if (!b) { el.style.visibility = 'hidden'; return; }
      const ib = el._ink, ref = el._ref, s = o.s ?? (b[2] / ref[2]);
      const x = o.x ?? b[0], y = b[1];
      // le texte est posé par sa ligne de base : origine de la boîte CSS = haut de la boîte de police (ascent)
      const ox = x - ib.left * s, oy = y - (ib.base + ib.top) * s;
      el.style.visibility = 'visible';
      el.style.transform = `translate(${ox.toFixed(2)}px, ${oy.toFixed(2)}px) scale(${s.toFixed(4)})`;
      if (o.clip != null) { const vis = (o.clip - oy) / s; el.style.clipPath = `inset(0 -50% calc(100% - ${vis.toFixed(2)}px) -50%)`; }
      else el.style.clipPath = '';
    }
    function stretch(el, b, ref) {
      if (!b) { el.style.visibility = 'hidden'; return; }
      el.style.visibility = 'visible';
      el.style.transform = `translate(${b[0].toFixed(2)}px, ${b[1].toFixed(2)}px) scale(${(b[2] / ref[2]).toFixed(4)}, ${(b[3] / ref[3]).toFixed(4)})`;
    }
    return { fps, box, val, inkBox, calibrate, glyph, stretch };
  };
})();
