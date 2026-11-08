/* mk-kinetic.js — vrai motion (règle 87) : typographie lettre par lettre, caméra jamais immobile, coups de musique,
   curseur qui clique VRAIMENT sa cible. À charger après gsap. Usage :
     const K = MKK(tl);                       // tl = la timeline GSAP du film (en pause)
     const chs = K.split(el);                  // lettres en <span class="ch"> (CSS : .ch{display:inline-block;white-space:pre})
     K.charsIn(chs, t, {order:'center', rx:-95, y:24, z:-120, blur:10, st:0.018, d:0.6, ease:'circ.out'});
     K.charsOut(chs, t, {y:-40, blur:10, st:0.012, d:0.3});
     K.drift(camEl, t, {s:1.2, kick:0.025, beats:window.BEATS});   // à appeler à CHAQUE image (frame(t))
     K.cursorTo(curEl, targetEl, t, {arrive:t0, dur:0.5667, from:[1900,1150], hot:[20,6], leave:t1});  // chaque image
     K.click(curEl, t) ; K.press(buttonEl, t, rippleEl)            // dans la timeline
   Pièges vérifiés (Master Skills v2) :
   - un texte en dégradé (background-clip:text) découpé en lettres : mettre le dégradé sur CHAQUE lettre et l'ENLEVER
     du parent, sinon le parent peint la forme non tournée des lettres (tache blanche sur la 1re lettre) ;
   - fromTo dans une timeline qu'on « seek » au hasard : immediateRender:false + un tl.set(...,0) de l'état initial ;
   - la cible d'un clic se lit dans la page À L'IMAGE du clic (getBoundingClientRect), jamais en coordonnées tapées :
     la caméra bouge, la cible aussi ; le point chaud de la main (bout du doigt) est décalé de hot=[x,y] px. */
(function () {
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x)), lerp = (a, b, k) => a + (b - a) * k;
  window.MKK = function (tl) {
    const E = n => gsap.parseEase(n);
    function split(el) {
      const out = [];
      const walk = node => { for (const c of [...node.childNodes]) {
        if (c.nodeType === 3) { const frag = document.createDocumentFragment();
          for (const ch of c.textContent) { const s = document.createElement('span'); s.className = 'ch'; s.textContent = ch; frag.appendChild(s); out.push(s); }
          c.replaceWith(frag); } else walk(c); } };
      walk(el); return out;
    }
    function order(o, i, n) { const mid = (n - 1) / 2;
      return o.order === 'center' ? Math.abs(i - mid) : o.order === 'rev' ? n - 1 - i : o.order === 'rand' ? ((i * 7919) % n) : i; }
    function charsIn(chs, t, o = {}) {
      chs.forEach((c, i) => {
        tl.set(c, { opacity: 0 }, 0);
        tl.fromTo(c, { opacity: 0, x: o.x || 0, y: o.y || 0, z: o.z || 0, rotationX: o.rx || 0, rotationY: o.ry || 0, rotation: o.r || 0, scale: o.s ?? 1, filter: `blur(${o.blur ?? 8}px)` },
          { opacity: 1, x: 0, y: 0, z: 0, rotationX: 0, rotationY: 0, rotation: 0, scale: 1, filter: 'blur(0px)', duration: o.d || 0.55, ease: o.ease || 'expo.out', immediateRender: false },
          t + order(o, i, chs.length) * (o.st ?? 0.022));
      });
    }
    function charsOut(chs, t, o = {}) {
      chs.forEach((c, i) => tl.to(c, { opacity: 0, x: o.x || 0, y: o.y || 0, z: o.z || 0, rotationX: o.rx || 0, rotation: o.r ? o.r * (i % 2 ? 1 : -1) : 0,
        scale: o.s ?? 1, filter: `blur(${o.blur ?? 10}px)`, duration: o.d || 0.3, ease: o.ease || 'power3.in' }, t + order(o, i, chs.length) * (o.st ?? 0.012)));
    }
    function beatKick(t, beats) { let k = 0; for (const [bt, s] of beats || []) { const d = t - bt; if (d >= 0 && d < 0.35) k += s * Math.exp(-d * 9); } return k; }
    function drift(el, t, o = {}) {   // dérive continue : jamais une image immobile ; petit zoom sur chaque temps fort
      const k = beatKick(t, o.beats || window.BEATS) * (o.kick ?? 0.025);
      gsap.set(el, { x: (o.x || 0) + (o.ax ?? 14) * Math.sin(t * 0.37 + (o.p || 0)), y: (o.y || 0) + (o.ay ?? 9) * Math.sin(t * 0.29 + 1 + (o.p || 0)),
        rotationY: (o.ry || 0) + 1.2 * Math.sin(t * 0.21), rotationX: (o.rx || 0) + 0.8 * Math.sin(t * 0.17 + 2), scale: (o.s || 1) * (1 + k), transformPerspective: 1600 });
    }
    function cursorTo(cur, target, t, o) {   // arrivée circ.out 0,5667 s (mesurée R2) SUR la cible lue dans la page
      const b = target.getBoundingClientRect(), hot = o.hot || [20, 6];
      const tx = b.left + b.width / 2 - hot[0], ty = b.top + b.height / 2 - hot[1];
      const k = E(o.ease || 'circ.out')(clamp((t - o.arrive) / (o.dur || 0.5667)));
      const out = o.leave ? E('power3.in')(clamp((t - o.leave) / 0.4)) : 0, from = o.from || [1900, 1150];
      gsap.set(cur, { x: lerp(from[0], tx, k) + out * 800, y: lerp(from[1], ty, k) + out * 700, opacity: (t >= o.arrive ? 1 : 0) * (1 - out) });
    }
    function click(cur, t) {   // clic mesuré R2 : x0,73 pendant 6 images
      tl.to(cur, { scale: 0.73, duration: 2 / 30, ease: 'power2.in' }, t).to(cur, { scale: 1, duration: 4 / 30, ease: 'power2.out' }, t + 2 / 30);
    }
    function press(btn, t, ripple) {   // la cible réagit : enfoncement, rebond, onde
      tl.to(btn, { scale: 0.84, duration: 2 / 30, ease: 'power2.in' }, t).to(btn, { scale: 1, duration: 0.3, ease: 'back.out(3)' }, t + 2 / 30);
      if (ripple) { tl.set(ripple, { opacity: 0 }, 0); tl.fromTo(ripple, { scale: 1, opacity: 0.9 }, { scale: 3.2, opacity: 0, duration: 0.5, ease: 'expo.out', immediateRender: false }, t + 1 / 30); }
    }
    return { split, charsIn, charsOut, drift, beatKick, cursorTo, click, press, clamp, lerp };
  };
})();
