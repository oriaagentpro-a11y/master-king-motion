// Master King Motion — a REAL 3D phone (Three.js, WebGL), rendered frame by frame like the rest of the film.
// Load after three-bundle.js. Physically based materials (brushed titanium frame, glass, camera lenses), image-based
// lighting (RoomEnvironment + PMREM), soft contact shadow, a live screen texture (canvas: screenshot + rebuilt UI),
// and 3D UI cards that really leave the screen. A licensed .glb model can replace the procedural body (opts.glb).
//
// const P = await MKPhone3D.create(parentEl, { W, H, fov: 30, color: '#2b2d31', shadow: true })
//   P.pose({ x, y, z, rx, ry, rz })     world units: the phone is 1.0 tall; x/y in screen-normalised units (see toWorld)
//   P.place(cx, cy, hNorm, rx, ry, rz)  place by the MEASURED values: centre (0..1 of the frame) and height (share of
//                                       the frame height), rotations in degrees -> solves the distance for that size
//   P.screen                            canvas (1170x2532) drawn into the screen; call P.screenDirty() after drawing
//   P.card(i, canvas, {y, h})           a 3D card above the screen (P.cards[i].z / .rx animatable), canvas = its face
//   P.render()                          draw now (MK.film after() hook)
(function () {
  const T = () => window.THREE;
  function roundedRectShape(w, h, r) {
    const s = new (T().Shape)(), x = -w / 2, y = -h / 2;
    s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r); s.lineTo(x + w, y + h - r);
    s.quadraticCurveTo(x + w, y + h, x + w - r, y + h); s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
    s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y); return s;
  }
  function planeUV(geo) { // ShapeGeometry UVs -> 0..1 over its bounding box
    geo.computeBoundingBox(); const b = geo.boundingBox, uv = geo.attributes.uv, p = geo.attributes.position;
    for (let i = 0; i < uv.count; i++) uv.setXY(i, (p.getX(i) - b.min.x) / (b.max.x - b.min.x), (p.getY(i) - b.min.y) / (b.max.y - b.min.y));
    uv.needsUpdate = true; return geo;
  }
  async function create(parent, o = {}) {
    const THREE = T(); if (!THREE) throw new Error('three-bundle.js non chargé');
    const W = o.W || 1920, H = o.H || 1080;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(o.pixelRatio || 1); renderer.setSize(W, H); renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = o.exposure || 1.0;
    renderer.shadowMap.enabled = !!o.shadow; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    Object.assign(renderer.domElement.style, { position: 'absolute', left: 0, top: 0, width: W + 'px', height: H + 'px', pointerEvents: 'none' });
    parent.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new THREE.RoomEnvironment(), 0.04).texture;
    const fov = o.fov || 30, camera = new THREE.PerspectiveCamera(fov, W / H, 0.05, 100); camera.position.set(0, 0, 6); camera.lookAt(0, 0, 0);
    const key = new THREE.DirectionalLight(0xffffff, o.key ?? 1.4); key.position.set(-2.5, 3.5, 4); key.castShadow = !!o.shadow;
    key.shadow.mapSize.set(2048, 2048); key.shadow.radius = 6; Object.assign(key.shadow.camera, { left: -2, right: 2, top: 2, bottom: -2 });
    scene.add(key); scene.add(new THREE.AmbientLight(0xffffff, 0.25));
    // ---- body (procedural) : proportions of a modern 6.1" phone, height = 1 world unit
    const hh = 1, ww = hh * 0.4815, dd = hh * 0.052, rr = ww * 0.17;
    const phone = new THREE.Group(); scene.add(phone);
    const frameMat = new THREE.MeshPhysicalMaterial({ color: new THREE.Color(o.color || '#2b2d31'), metalness: 1, roughness: 0.32, clearcoat: 0.6, clearcoatRoughness: 0.25, envMapIntensity: 1.25 });
    // body = extruded rounded rectangle with a rounded bevel (RoundedBoxGeometry caps the corner radius at depth/2:
    // a phone needs corner radius >> thickness, hence extrusion)
    const bev = dd * 0.42;
    const bodyGeo = new THREE.ExtrudeGeometry(roundedRectShape(ww - 2 * bev, hh - 2 * bev, Math.max(0.001, rr - bev)),
      { depth: dd - 2 * bev, bevelEnabled: true, bevelThickness: bev, bevelSize: bev, bevelSegments: 10, curveSegments: 48 });
    bodyGeo.translate(0, 0, -(dd - 2 * bev) / 2);
    const body = new THREE.Mesh(bodyGeo, frameMat); body.castShadow = true; phone.add(body);
    const backMat = new THREE.MeshPhysicalMaterial({ color: new THREE.Color(o.back || '#3b3e44'), metalness: 0.35, roughness: 0.42, clearcoat: 1, clearcoatRoughness: 0.18, envMapIntensity: 1.4 });  // frosted glass back
    const back = new THREE.Mesh(planeUV(new THREE.ShapeGeometry(roundedRectShape(ww - 2 * bev * 0.9, hh - 2 * bev * 0.9, rr - bev * 0.9), 32)), backMat);
    back.position.z = -dd / 2 - 0.0005; back.rotation.y = Math.PI; phone.add(back);
    // camera plateau + 3 lenses + flash (back)
    const plat = new THREE.Mesh(new THREE.RoundedBoxGeometry(ww * 0.42, ww * 0.42, dd * 0.2, 6, dd * 0.09), new THREE.MeshPhysicalMaterial({ color: '#232428', metalness: 0.4, roughness: 0.25, clearcoat: 1 }));
    plat.position.set(ww * 0.255, hh * 0.385, -dd / 2 - dd * 0.1); phone.add(plat);
    const ring = new THREE.MeshPhysicalMaterial({ color: '#3a3c40', metalness: 1, roughness: 0.2 });
    const glass = new THREE.MeshPhysicalMaterial({ color: '#05070a', metalness: 0, roughness: 0.02, clearcoat: 1, clearcoatRoughness: 0, envMapIntensity: 2.2 });
    // lenses on the plateau (seen from the back the plateau sits top-left: x > 0 in phone space)
    [[0.18, 0.445], [0.18, 0.325], [0.335, 0.385]].forEach(([lx, ly]) => {
      const c = new THREE.Mesh(new THREE.CylinderGeometry(ww * 0.062, ww * 0.066, dd * 0.32, 64), ring); c.rotation.x = Math.PI / 2; c.position.set(lx * ww, ly * hh, -dd / 2 - dd * 0.32); phone.add(c);
      const g = new THREE.Mesh(new THREE.CircleGeometry(ww * 0.047, 64), glass); g.position.set(lx * ww, ly * hh, -dd / 2 - dd * 0.485); g.rotation.y = Math.PI; phone.add(g);
      const r2 = new THREE.Mesh(new THREE.RingGeometry(ww * 0.047, ww * 0.056, 64), new THREE.MeshPhysicalMaterial({ color: '#111', metalness: 1, roughness: 0.15 }));
      r2.position.set(lx * ww, ly * hh, -dd / 2 - dd * 0.483); r2.rotation.y = Math.PI; phone.add(r2);
    });
    const fl = new THREE.Mesh(new THREE.CircleGeometry(ww * 0.022, 32), new THREE.MeshStandardMaterial({ color: '#f3ead2', roughness: 0.4 }));
    fl.position.set(0.335 * ww, 0.465 * hh, -dd / 2 - dd * 0.31); fl.rotation.y = Math.PI; phone.add(fl);
    // side buttons
    const btn = (y, h, side) => { const b = new THREE.Mesh(new THREE.RoundedBoxGeometry(dd * 0.35, h, dd * 0.55, 3, dd * 0.12), frameMat); b.position.set(side * (ww / 2 + dd * 0.08), y, 0); phone.add(b); };
    btn(hh * 0.22, hh * 0.1, 1); btn(hh * 0.28, hh * 0.06, -1); btn(hh * 0.18, hh * 0.06, -1);
    // front glass (black bezel) + screen (live canvas texture, unlit) + island
    const bez = ww * 0.045;
    const front = new THREE.Mesh(new THREE.ShapeGeometry(roundedRectShape(ww - 2 * bev * 0.9, hh - 2 * bev * 0.9, rr - bev * 0.9), 32),
      new THREE.MeshPhysicalMaterial({ color: '#030405', metalness: 0, roughness: 0.04, clearcoat: 1, clearcoatRoughness: 0.02, envMapIntensity: 1.6 }));
    front.position.z = dd / 2 + 0.0004; phone.add(front);
    const sc = document.createElement('canvas'); sc.width = o.screenW || 1170; sc.height = o.screenH || 2532;
    const tex = new THREE.CanvasTexture(sc); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
    const sw = ww - 2 * bez, sh = hh - 2 * bez;
    const scr = new THREE.Mesh(planeUV(new THREE.ShapeGeometry(roundedRectShape(sw, sh, rr - bez * 0.9), 48)), new THREE.MeshBasicMaterial({ map: tex, toneMapped: false }));
    scr.position.z = dd / 2 + 0.0012; phone.add(scr);
    const isl = new THREE.Mesh(new THREE.ShapeGeometry(roundedRectShape(sw * 0.3, sw * 0.085, sw * 0.0425), 16), new THREE.MeshBasicMaterial({ color: '#000' }));
    isl.position.set(0, sh / 2 - sw * 0.075, dd / 2 + 0.0016); phone.add(isl);
    // glass reflection layer over the screen (additive sheen, follows the environment)
    const sheen = new THREE.Mesh(scr.geometry, new THREE.MeshPhysicalMaterial({ color: '#000', transparent: true, opacity: 0.12, roughness: 0.03, metalness: 0, clearcoat: 1, envMapIntensity: 2.4, blending: THREE.AdditiveBlending, depthWrite: false }));
    sheen.position.z = dd / 2 + 0.002; phone.add(sheen);
    // optional licensed model: replaces the procedural body, the screen stays ours (fitted on the model's screen size)
    if (o.glb) {
      const g = await new THREE.GLTFLoader().loadAsync(o.glb);
      [body, back, plat, front].forEach(m => (m.visible = false));
      const box = new THREE.Box3().setFromObject(g.scene), size = box.getSize(new THREE.Vector3()); const k = hh / size.y;
      g.scene.scale.setScalar(k); g.scene.position.sub(box.getCenter(new THREE.Vector3()).multiplyScalar(k)); phone.add(g.scene);
    }
    // soft contact shadow catcher (only when the reference shows one)
    if (o.shadow) { const sp = new THREE.Mesh(new THREE.PlaneGeometry(6, 6), new THREE.ShadowMaterial({ opacity: o.shadowOpacity ?? 0.22 }));
      sp.position.z = -0.6; sp.receiveShadow = true; scene.add(sp); }
    const cards = [];
    function card(i, canvas, { y = 0, h = 0.16, w = 0.92 } = {}) {
      const t = new THREE.CanvasTexture(canvas); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
      const cw = sw * w, ch = sh * h;
      const m = new THREE.Mesh(planeUV(new THREE.ShapeGeometry(roundedRectShape(cw, ch, ch * 0.16), 16)), new THREE.MeshBasicMaterial({ map: t, toneMapped: false, side: THREE.DoubleSide, transparent: true }));
      const g = new THREE.Group(); g.add(m); g.position.set(0, y * sh / 2, dd / 2 + 0.003); phone.add(g);
      const edge = new THREE.Mesh(new THREE.RoundedBoxGeometry(cw, ch, 0.006, 3, ch * 0.12), new THREE.MeshPhysicalMaterial({ color: '#dfe6ea', metalness: 0.1, roughness: 0.3 }));
      edge.position.z = -0.0035; g.add(edge);
      const c = { g, z: 0, rx: 0, tex: t, baseZ: dd / 2 + 0.003 }; cards[i] = c; return c;
    }
    // placement from measured screen values: centre (cx, cy in 0..1), apparent height hNorm (share of frame height)
    const vfov = fov * Math.PI / 180;
    function place(cx, cy, hNorm, rx = 0, ry = 0, rz = 0) {
      const dist = hh / (hNorm * 2 * Math.tan(vfov / 2));          // distance at which the phone is hNorm of the frame tall
      const vh = 2 * dist * Math.tan(vfov / 2), vw = vh * W / H;
      phone.position.set((cx - 0.5) * vw, (0.5 - cy) * vh, camera.position.z - dist);
      phone.rotation.set(rx * Math.PI / 180, ry * Math.PI / 180, rz * Math.PI / 180, 'YXZ');
    }
    // measured pose (pose_from_quad.py): camera space, phone height 1, degrees, Euler YXZ — camera must use the same fov
    function setPose(p) {
      phone.position.set(p.x, p.y, camera.position.z + p.z);
      phone.rotation.set((p.rx || 0) * Math.PI / 180, (p.ry || 0) * Math.PI / 180, (p.rz || 0) * Math.PI / 180, 'YXZ');
    }
    function setFov(f) { camera.fov = f; camera.updateProjectionMatrix(); }
    // studio HDRI (Poly Haven CC0 .hdr) for photoreal reflections, instead of the procedural RoomEnvironment
    async function hdri(url, { background = false, intensity = 1 } = {}) {
      const t = await new THREE.RGBELoader().loadAsync(url); const env = pmrem.fromEquirectangular(t).texture; t.dispose();
      scene.environment = env; scene.environmentIntensity = intensity; if (background) scene.background = env;
    }
    function render() {
      for (const c of cards) { c.g.position.z = c.baseZ + c.z; c.g.rotation.x = c.rx * Math.PI / 180; }
      renderer.render(scene, camera);
    }
    return { renderer, scene, camera, phone, screen: sc, screenDirty: () => { tex.needsUpdate = true; }, card, cards, place, setPose, setFov, hdri, render,
             size: { ww, hh, dd, sw, sh }, cardDirty: i => { cards[i].tex.needsUpdate = true; } };
  }
  window.MKPhone3D = { create };
})();
