// Master King Motion — a phone built in code (CSS 3D), so app screens can be shown, tilted, orbited and
// animated piece by piece without a rendered 3D model. Load after mkm.js.
// const ph = MKPhone.create(parent, { h: 0.78 * MK.H, color: '#1b1d22', island: true, radius: 0.16 })
//   ph.el        outer element: place it with MK.place(ph.el, cx, cy), animate rotationY/rotationX/z with GSAP
//   ph.screen    the screen element (overflow hidden, size ph.sw x ph.sh px): put screenshots / rebuilt UI inside
//   ph.light(a)  sweep of the glass reflection, a in 0..1 (drive it from the timeline for a premium glint)
//   ph.shot(src) full-screen screenshot layer (img), returns it
// Depth: give the parent `perspective` (MKPhone.stage(parent, 2200)). Shadow follows the tilt.
(function () {
  function stage(el, p = 2200) { el.style.perspective = p + 'px'; el.style.perspectiveOrigin = '50% 45%'; return el; }
  function create(parent, o = {}) {
    const H = o.h || 0.78 * (window.MK ? MK.H : 1080), W = H * (o.ratio || 0.4615), R = (o.radius ?? 0.16) * W;
    const bez = o.bezel ?? 0.028 * W, color = o.color || '#1b1d22';
    const el = document.createElement('div');
    Object.assign(el.style, { width: W + 'px', height: H + 'px', position: 'absolute', transformStyle: 'preserve-3d' });
    // side thickness: stacked layers give a real edge when the phone turns
    const depth = o.depth ?? 0.045 * W, layers = 10;
    for (let i = 0; i < layers; i++) {
      const s = document.createElement('div');
      Object.assign(s.style, { position: 'absolute', inset: 0, borderRadius: R + 'px', background: i === 0 || i === layers - 1 ? color : shade(color, -10 + i),
        transform: `translateZ(${-depth * i / (layers - 1)}px)` });
      el.appendChild(s);
    }
    const body = document.createElement('div');
    Object.assign(body.style, { position: 'absolute', inset: 0, borderRadius: R + 'px', background: color,
      boxShadow: `inset 0 0 0 ${Math.max(1, W * 0.006)}px rgba(255,255,255,.18), inset 0 0 ${W * 0.03}px rgba(0,0,0,.6)`, transform: 'translateZ(0.5px)' });
    el.appendChild(body);
    const screen = document.createElement('div');
    const sw = W - 2 * bez, sh = H - 2 * bez;
    Object.assign(screen.style, { position: 'absolute', left: bez + 'px', top: bez + 'px', width: sw + 'px', height: sh + 'px', borderRadius: (R - bez) + 'px',
      overflow: 'hidden', background: o.screenBg || '#000', transform: 'translateZ(1px)' });
    el.appendChild(screen);
    if (o.island !== false) {
      const isl = document.createElement('div');
      Object.assign(isl.style, { position: 'absolute', left: '50%', top: sh * 0.012 + 'px', width: sw * 0.3 + 'px', height: sw * 0.085 + 'px', marginLeft: -sw * 0.15 + 'px',
        borderRadius: sw + 'px', background: '#000', zIndex: 50 });
      screen.appendChild(isl);
    }
    const glass = document.createElement('div');
    Object.assign(glass.style, { position: 'absolute', inset: 0, borderRadius: 'inherit', pointerEvents: 'none', zIndex: 60, mixBlendMode: 'screen',
      background: 'linear-gradient(115deg, rgba(255,255,255,0) 35%, rgba(255,255,255,.22) 45%, rgba(255,255,255,0) 55%)', backgroundSize: '300% 100%' });
    screen.appendChild(glass);
    const shadow = document.createElement('div');
    Object.assign(shadow.style, { position: 'absolute', left: '8%', right: '8%', bottom: -H * 0.06 + 'px', height: H * 0.05 + 'px', borderRadius: '50%',
      background: 'radial-gradient(closest-side, rgba(0,0,0,.35), rgba(0,0,0,0))', transform: `translateZ(${-depth}px) rotateX(90deg)`, filter: `blur(${H * 0.01}px)` });
    el.appendChild(shadow);
    (parent || document.body).appendChild(el);
    return {
      el, screen, sw, sh, W, H,
      light(a) { glass.style.backgroundPosition = `${100 - a * 100}% 0`; },
      shot(src, fit = 'cover') { const im = document.createElement('img'); im.src = src;
        Object.assign(im.style, { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: fit, objectPosition: 'top' }); screen.insertBefore(im, glass); return im; },
    };
  }
  function shade(hex, d) { const n = parseInt(hex.slice(1), 16); const c = [n >> 16, n >> 8 & 255, n & 255].map(v => Math.max(0, Math.min(255, v + d)));
    return '#' + c.map(v => v.toString(16).padStart(2, '0')).join(''); }
  window.MKPhone = { create, stage };
})();
