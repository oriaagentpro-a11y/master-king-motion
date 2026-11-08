// Master King Motion runtime. Load after gsap, rm.js, dna.js (window.DNA) and timing.js (window.TIMING).
// A film = the user's plan scenes, each one built from a REFERENCE scene recipe in reference-local seconds
// (exact measured eases / durations), played on the new timeline through the warp knots of retime.py:
// identity on the entrance, linear stretch of the hold only, shift on the exit.
(function () {
  const T = window.TIMING || { stage: { w: 1920, h: 1080, fps: 30 }, scenes: [], total: 0 };
  const DNA = window.DNA || { scenes: [], elements: {}, meta: { format: { w: 1920, h: 1080 } } };
  const W = T.stage.w, H = T.stage.h, FPS = Number(new URLSearchParams(location.search).get('fps')) || T.stage.fps || 30;
  const refScene = id => DNA.scenes.find(s => s.id === id);

  // ---------- time warp (piecewise linear, monotonic) ----------
  function lerpKnots(k, x, a, b) {
    if (x <= k[0][a]) return k[0][b] + (x - k[0][a]);           // before: speed 1
    for (let i = 1; i < k.length; i++) if (x <= k[i][a]) {
      const [p, q] = [k[i - 1], k[i]], span = q[a] - p[a];
      return span <= 1e-9 ? q[b] : p[b] + (x - p[a]) * (q[b] - p[b]) / span;
    }
    const l = k[k.length - 1]; return l[b] + (x - l[a]);          // after: speed 1
  }
  const toRef = (knots, tNewLocal) => lerpKnots(knots, tNewLocal, 1, 0);
  const toNew = (knots, tRefLocal) => lerpKnots(knots, tRefLocal, 0, 1);

  // ---------- deterministic helpers ----------
  function rng(seed) { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

  // ---------- layout ----------
  // Elements are positioned by their CENTRE in stage pixels (left/top 0 + xPercent/yPercent -50), so the
  // normalised centres measured on the reference (cx / width, cy / height) map 1:1 onto the new stage.
  function place(el, cxn, cyn, extra = {}) {
    gsap.set(el, { position: 'absolute', left: 0, top: 0, xPercent: -50, yPercent: -50, x: cxn * W, y: cyn * H, ...extra });
    return el;
  }
  // Fit a text in a box (stage px): biggest size <= maxSize that fits in maxLines lines and the box.
  // Start from the REFERENCE size (spec.size) and only shrink: the typographic scale of the reference is kept.
  // Afterwards the element hugs its text (single line: width = text) so MK.place centres the TEXT, not the box;
  // multi-line keeps the box width with text-align `align` (default centre).
  function fitText(el, { w, h = 1e9, maxLines = 1, size, minSize = 10, lineHeight = null, nowrap = null, align = 'center' } = {}) {
    el.style.width = w + 'px'; el.style.whiteSpace = (nowrap ?? maxLines === 1) ? 'nowrap' : 'normal'; el.style.textAlign = align;
    if (lineHeight) el.style.lineHeight = lineHeight;
    const fits = s => { el.style.fontSize = s + 'px';
      const lh = parseFloat(getComputedStyle(el).lineHeight) || s * 1.2;
      return el.scrollWidth <= w + 0.5 && el.scrollHeight <= h + 0.5 && Math.round(el.scrollHeight / lh) <= maxLines; };
    let hi = size || 400, lo = minSize;
    if (!fits(hi)) {
      for (let i = 0; i < 24; i++) { const m = (lo + hi) / 2; if (fits(m)) lo = m; else hi = m; }
      el.style.fontSize = lo + 'px';
    } else lo = hi;
    if (maxLines === 1) el.style.width = 'max-content';
    return lo;
  }
  // Split a text into spans (letters or words) for measured staggers. Spaces are kept as text nodes.
  function split(el, unit = 'char') {
    const txt = el.textContent; el.textContent = ''; const out = [];
    const parts = unit === 'word' ? txt.split(/(\s+)/) : [...txt];
    for (const p of parts) {
      if (/^\s+$/.test(p)) { el.appendChild(document.createTextNode(p)); continue; }
      const s = document.createElement('span'); s.textContent = p; s.style.display = 'inline-block'; s.style.willChange = 'transform';
      el.appendChild(s); out.push(s);
    }
    return out;
  }
  // Image in a slot box (stage px), object-fit cover/contain, centred on the box centre.
  function image(src, { cx, cy, w, h, fit = 'cover', radius = 0, parent }) {
    const im = document.createElement('img'); im.src = src;
    Object.assign(im.style, { width: w + 'px', height: h + 'px', objectFit: fit, borderRadius: radius + 'px', display: 'block' });
    (parent || document.body).appendChild(im); place(im, cx / W, cy / H); return im;
  }

  // Font size that gives `refText` the ink height measured on the reference (inkH, stage px): the reference's
  // typographic scale is kept exactly, whatever the new text is. Same font family / weight as the new text.
  const _c = document.createElement('canvas').getContext('2d');
  function refFontSize(refText, inkH, weight = 700, family = 'Brand') {
    _c.font = `${weight} 100px ${family}`; const m = _c.measureText(refText);
    return 100 * inkH / (m.actualBoundingBoxAscent + m.actualBoundingBoxDescent);
  }

  // Décalque: value of a measured curve (track_fit --curve) at an ABSOLUTE reference time (s), linear between frames,
  // held before the first / after the last measured frame. Returns {cx, cy, s, angle, opacity} (normalised).
  function curveAt(curve, tAbs) {
    const fr = curve.frames, keys = curve._k || (curve._k = Object.keys(fr).map(Number).sort((a, b) => a - b));
    const f = tAbs * curve.fps; if (f <= keys[0]) return fr[keys[0]]; if (f >= keys[keys.length - 1]) return fr[keys[keys.length - 1]];
    let lo = 0, hi = keys.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (keys[m] <= f) lo = m; else hi = m; }
    const A = fr[keys[lo]], B = fr[keys[hi]], p = (f - keys[lo]) / (keys[hi] - keys[lo]), o = {};
    for (const k of Object.keys(A)) o[k] = B[k] == null ? A[k] : A[k] + (B[k] - A[k]) * p; return o;
  }

  // ---------- motions from the DNA ----------
  // play(tl, el, m, ctx): one measured move -> one tween, in reference-local time (m.start - scene start).
  // prop cx / cy -> x / y in stage px (normalised value x W or H); w / h -> scale relative to the element's
  // rest size; angle -> rotation; scale / opacity as is. ALWAYS with the measured ease and duration.
  function play(tl, el, m, ctx, opt = {}) {
    if (!m || !m.ease || m.duration == null) throw new Error('mouvement sans ease / durée mesurés : ' + JSON.stringify(m));
    const t0 = m.start - (ctx ? ctx.refStart : 0) + (opt.delay || 0);
    const N = v => v;
    let prop, a, b;
    const rest = opt.rest || {};
    switch (m.prop) {
      case 'cx': case 'left': prop = 'x'; a = (m.from_norm ?? m.from / DNA.meta.format.w) * W + (opt.dx || 0); b = (m.to_norm ?? m.to / DNA.meta.format.w) * W + (opt.dx || 0); break;
      case 'cy': case 'top': prop = 'y'; a = (m.from_norm ?? m.from / DNA.meta.format.h) * H + (opt.dy || 0); b = (m.to_norm ?? m.to / DNA.meta.format.h) * H + (opt.dy || 0); break;
      case 'w': prop = opt.independent ? 'scaleX' : 'scale'; a = m.from / (rest.w || m.to); b = m.to / (rest.w || m.to); break;
      case 'h': prop = opt.independent ? 'scaleY' : 'scale'; a = m.from / (rest.h || m.to); b = m.to / (rest.h || m.to); break;
      case 'angle': prop = 'rotation'; a = m.from; b = m.to; break;
      default: prop = m.prop; a = N(m.from); b = N(m.to);
    }
    if (opt.map) [a, b] = [opt.map(a, prop), opt.map(b, prop)];
    tl.fromTo(el, { [prop]: a }, { [prop]: b, duration: m.duration, ease: m.ease, immediateRender: false }, Math.max(0, t0));
    return tl;
  }

  // ---------- finish: grain, vignette ----------
  function grain(parent, { sigma = 2, opacity = 0.06, animated = true, size = 256, seed = 7 } = {}) {
    const tiles = [];
    for (let k = 0; k < (animated ? 8 : 1); k++) {
      const c = document.createElement('canvas'); c.width = c.height = size; const g = c.getContext('2d'); const id = g.createImageData(size, size), r = rng(seed + k);
      for (let i = 0; i < id.data.length; i += 4) { let n = 0; for (let j = 0; j < 4; j++) n += r(); n = (n - 2) * sigma * 40 + 128;
        id.data[i] = id.data[i + 1] = id.data[i + 2] = Math.max(0, Math.min(255, n)); id.data[i + 3] = 255; }
      g.putImageData(id, 0, 0); tiles.push(c.toDataURL());
    }
    const d = document.createElement('div');
    Object.assign(d.style, { position: 'absolute', inset: 0, pointerEvents: 'none', opacity, mixBlendMode: 'overlay', zIndex: 9000 });
    parent.appendChild(d);
    return { el: d, draw(frame) { const k = animated ? frame % tiles.length : 0, r = rng(frame * 31 + 1);
      d.style.backgroundImage = `url(${tiles[k]})`; d.style.backgroundPosition = `${Math.floor(r() * size)}px ${Math.floor(r() * size)}px`; } };
  }
  function vignette(parent, strength = 0.35) {
    const d = document.createElement('div');
    Object.assign(d.style, { position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 8999,
      background: `radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,${strength}) 100%)` });
    parent.appendChild(d); return d;
  }

  // ---------- fonts ----------
  async function loadFonts(list = []) {
    for (const f of list) {
      const ff = new FontFace(f.family, `url(${f.src})`, { weight: f.weight || '100 900', style: f.style || 'normal' });
      document.fonts.add(await ff.load());
    }
    await document.fonts.ready;
  }

  // ---------- image sequences (Blender renders, extracted plates) ----------
  // MK.sequence(img, n => `out/render3d/P3/f_${String(n).padStart(4, '0')}.png`) returns set(n): shows frame n.
  // The decode is awaited by window.__rm.settle() before every capture (render.mjs / render_film.py), so no frame is
  // ever captured half-loaded. n < 1 or > count hides the image.
  const pending = [];
  function sequence(img, pathOf, count = Infinity) {
    let cur = null;
    return n => {
      if (n < 1 || n > count) { img.style.visibility = 'hidden'; return; }
      img.style.visibility = 'visible';
      const src = pathOf(n); if (src === cur) return; cur = src; img.src = src;
      pending.push(img.decode().catch(() => {     /* never ship a broken-image icon: hide it and stop the render */
        img.style.visibility = 'hidden'; window.__mk_error = 'image de séquence manquante ou illisible : ' + src;
      }));
    };
  }

  // ---------- text scramble (exit of a line, MEASURED on A f52-f60, distinct frames) ----------
  // MK.scramble(text, q, seed, opts) -> string, q 0 -> 1 over the effect.
  // Reference: the line stays READABLE ("W/at if your :allet": 2 letters of 18 replaced), loses WHOLE WORDS from the
  // end ("was", then "wallet"), and only the last ~2 frames are a short glyph string ("*h<>:i*"), centred.
  // A replaced letter keeps the SAME glyph from frame to frame (no flicker): substitutions depend on the seed and the
  // character index, never on the frame. Use a constant seed per line.
  function scramble(text, q, seed, o = {}) {
    const G = o.glyphs || '/:*<>;#%', rate = o.rate ?? 0.12, qGlyph = o.qGlyph ?? 0.72, gLen = o.glyphLen ?? 7;
    const pick = (i, k) => { const r = rng(seed * 1009 + i * 7919 + k)(); return r; };
    // exactly round(rate x letters) LETTERS replaced (punctuation and spaces kept), chosen by a fixed hash order
    const sub = (str, rt) => {
      const chars = [...str], letters = chars.map((c, i) => /\p{L}/u.test(c) ? i : -1).filter(i => i >= 0);
      const n = Math.max(1, Math.round(rt * letters.length)), chosen = new Set(letters.sort((a, b) => pick(a, 1) - pick(b, 1)).slice(0, n));
      return chars.map((ch, i) => chosen.has(i) ? G[Math.floor(pick(i, 2) * G.length)] : ch).join('');
    };
    if (q >= qGlyph) {                                    // last frames: short glyph string with a few letters left
      const base = text.replace(/\s+/g, '').slice(0, gLen);
      return sub(base, o.glyphRate ?? 0.7);
    }
    // substitutions decided ONCE on the whole line, then words are dropped: a replaced letter stays where it is
    const full = sub(text, rate).split(' '), nw = full.length;
    const keep = Math.max(1, nw - Math.floor((q / qGlyph) * nw));
    return full.slice(0, keep).join(' ');
  }

  // ---------- 3D probes ----------
  // A recipe that drives an object later rendered in Blender reports its on-screen state every frame:
  // MK.probe('logo', { cx, cy, h, rx, ry, rz })  (cx, cy, h normalised to the stage). scripts/export_probe.py reads it,
  // so the 3D render follows EXACTLY the validated timing of the film (one source of truth).
  window.__mk_probe = {};
  function probe(name, v) { window.__mk_probe[name] = v; }

  // ---------- brand colours ----------
  // color('#FEF6EB') -> brand colour of the nearest key of TIMING.brand.map (within 48 RGB units), else unchanged.
  const rgb = h => { h = String(h).replace('#', ''); if (h.length === 3) h = [...h].map(c => c + c).join(''); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); };
  function color(hex, near = 48) {
    const M = (T.brand && T.brand.map) || {}; let best = null, bd = 1e9; const v = rgb(hex);
    for (const [k, x] of Object.entries(M)) { const c = rgb(k), d = Math.hypot(v[0] - c[0], v[1] - c[1], v[2] - c[2]); if (d < bd) { bd = d; best = x; } }
    return best && bd <= near ? best : hex;
  }

  // ---------- the film ----------
  // MK.film({ scenes: { S01: ctx => tl, ... }, root, grain, vignette, blur, before(t), after(t) })
  // ctx = { id, ref, refStart, D, slots, brand, colors, root, W, H, dna, el(id), motions(id), play(tl, el, m, opt),
  //         replay(tl, el, elementId, opt), voRef(i) (reference-local time of the i-th phrase of this scene) }
  // errors inside the async build would otherwise vanish (unhandled promise): they are logged and kept in
  // window.__mk_error, which render_film.py / storyboard.py print instead of waiting forever.
  function film(o) {
    return filmBuild(o).catch(e => { window.__mk_error = String((e && e.stack) || e); console.error('MK.film :', window.__mk_error); });
  }
  async function filmBuild(o) {
    await loadFonts((T.brand && T.brand.fonts) || []);
    if (o.fonts) await loadFonts(o.fonts);
    const root = o.root || document.getElementById('stage') || document.body;
    Object.assign(root.style, { position: 'relative', width: W + 'px', height: H + 'px', overflow: 'hidden' });
    const items = [];
    for (const [i, ps] of T.scenes.entries()) {
      const recipe = o.scenes[ps.ref];
      if (!recipe) throw new Error(`aucune recette pour la scène de référence ${ps.ref} (plan ${ps.id})`);
      const rs = refScene(ps.ref) || { start: ps.ref_start, duration: ps.ref_end - ps.ref_start, roles: {} };
      const sroot = document.createElement('div'); sroot.className = 'mk-scene'; sroot.dataset.id = ps.id;
      Object.assign(sroot.style, { position: 'absolute', inset: 0, overflow: 'hidden', visibility: 'hidden', zIndex: 10 + i });
      root.appendChild(sroot);
      // colours: each reference role colour goes through brand.map (reference colour -> brand colour, nearest key),
      // so the reference's light / dark / accent rhythm is kept with the brand palette; a plan scene may force roles.
      const colors = Object.fromEntries(Object.entries(rs.roles || {}).map(([k, v]) => [k, color(v)]));
      Object.assign(colors, (ps.slots && ps.slots.colors) || {});
      const ctx = { id: ps.id, ref: ps.ref, index: i, refStart: rs.start, D: rs.duration, slots: ps.slots || {}, brand: T.brand || {}, colors,
        root: sroot, W, H, dna: rs, vo: ps.vo, rhythm: ps.rhythm || null, timing: ps, motif: id => (((DNA.elements[id] || {}).patterns) || [])[0] || null, el: id => sroot.querySelector('#' + CSS.escape(id)) || document.getElementById(id),
        motions: id => ((DNA.elements[id] || {}).motions || []),
        play: (tl, el, m, opt) => play(tl, el, m, ctx, opt),
        replay: (tl, el, id, opt = {}) => { const E = DNA.elements[id] || {}; for (const m of (E.motions || []))
          if (!opt.props || opt.props.includes(m.prop)) play(tl, el, m, ctx, { rest: E.rest && { w: E.rest.w && E.rest.w.px, h: E.rest.h && E.rest.h.px }, ...opt }); return tl; },
        voRef: k => { const p = ps.vo[k]; return p ? toRef(ps.knots, p.start - ps.new_start) : null; },
        // reference-local time at which word j of phrase k is SPOKEN (audio_prep --align): sync a keyword to the voice
        wordRef: (k, j) => { const p = ps.vo[k]; const w = p && p.words && p.words[j]; return w ? toRef(ps.knots, w.start - ps.new_start) : null; },
        words: k => ((ps.vo[k] || {}).words || []) };
      // a recipe returns a paused GSAP timeline (reference-local time, warped), or { tl, frame(tn, tr) } where
      // frame() also runs on every frame with tn = NEW local time (constant-rate moves: rotation, drift, parallax,
      // keep their measured speed whatever the stretch) and tr = reference-local time.
      // NB: a GSAP timeline is a thenable — an async recipe that returns it directly would wait for the end of a
      // paused timeline (forever). Recipes are plain functions returning { tl } (or the timeline); async only with { tl }.
      let got = recipe(ctx);
      if (got && typeof got.seek !== 'function' && typeof got.then === 'function')
        got = await Promise.race([got, new Promise((_, rej) => setTimeout(() => rej(new Error(
          `recette ${ps.ref} : promesse jamais résolue — une fonction async ne doit pas renvoyer la timeline elle-même, renvoyer { tl }`)), 8000))]);
      const tl = got && typeof got.seek === 'function' ? got : got && got.tl;
      if (!tl || typeof tl.seek !== 'function') throw new Error(`la recette ${ps.ref} doit renvoyer une timeline GSAP (ou { tl, frame })`);
      tl.pause(0);
      items.push({ ps, tl, frame: got && got.frame, sroot, pre: ps.overlap_in || 0, post: ps.overlap_out || 0 });
    }
    const gr = o.grain ? grain(root, o.grain) : null;
    if (o.vignette) vignette(root, o.vignette);
    // motion blur: explicit windows (new time) or a constant; [samples, shutter in frames]
    const blurAt = t => { const b = o.blur ?? T.blur; if (!b) return null; if (Array.isArray(b) && typeof b[0] === 'number') return b;
      for (const w of b) if (t >= w.from && t < w.to) return [w.samples || 6, w.shutter ?? 0.5]; return null; };
    window.__mk = { items, toRef, toNew, W, H, FPS };
    const settleAll = () => Promise.all(pending.splice(0).map(p => p.catch(() => null)));
    window.__rm = {
      ready: true,
      seek(t) {
        if (o.before) o.before(t);
        for (const it of items) {
          // a scene owns WHOLE FRAMES (new_start_frame <= k < new_end_frame), like timing.json, the 3D sequences
          // (frame 1 = new_start_frame) and style_compare: a cut at 6.88 s must not leave frame 206 to the previous
          // scene (its first 3D frame was never shown and the cut came one frame late). Overlaps (pre/post) keep time.
          const k = Math.round(t * FPS + 1e-6), local = t - it.ps.new_start;
          const on = (it.pre || it.post || it.ps.new_start_frame == null) ? (local >= -it.pre && local < it.ps.duration + it.post)
            : (k >= it.ps.new_start_frame && k < it.ps.new_end_frame);
          it.sroot.style.visibility = on ? 'visible' : 'hidden';
          if (on) { const tr = Math.max(0, Math.min(it.ps.knots[it.ps.knots.length - 1][0], toRef(it.ps.knots, local)));
            it.tl.seek(tr, false); if (it.frame) it.frame(Math.min(local, it.ps.duration), tr); }
        }
        if (gr) gr.draw(Math.round(t * FPS));
        if (o.after) o.after(t);
      },
      blurAt,
      settle: settleAll,
    };
    window.__rm.seek(0);
  }

  window.MK = { W, H, FPS, T, DNA, color, scramble, refFontSize, curveAt, sequence, probe, toRef, toNew, rng, place, fitText, split, image, play, grain, vignette, loadFonts, film, refScene };
})();
