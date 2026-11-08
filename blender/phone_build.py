"""Master King Motion — photoreal smartphone built procedurally in Blender (bpy), for Cycles.

Generic modern flagship (no brand logo, no copied trade dress). Real millimetre proportions, scaled so the
phone is 1.0 unit tall (same convention as engine/mk-phone3d.js and pose_from_quad.py):
  - body: continuous rounded corners (bevel profile 0.62), flat titanium frame with micro-chamfers, antenna bands
  - buttons in machined recesses (action, volume +/-, power), USB-C port, speaker grille, microphones
  - front: black glass slab, emissive screen (image / image sequence) under a glossy clear coat, dynamic island
  - back: frosted coloured glass, raised polished-glass camera plateau, 3 lens stacks (anodised ring, black cell,
    coated sapphire glass, inner rings), flash, sensor
Usage (inside Blender):  import phone_build; phone = phone_build.build(colors={...}); phone_build.set_screen(img)
"""
import bpy, bmesh, math
from mathutils import Vector

MM = 1.0 / 147.0          # 1 unit = phone height (147 mm)
W, H, D = 71.5 * MM, 147 * MM, 8.25 * MM
R_CORNER = 10.6 * MM


def mat(name, base=(0.1, 0.1, 0.1), metallic=0.0, rough=0.4, coat=0.0, coat_rough=0.05, aniso=0.0, transmission=0.0,
        emission=None, ior=1.5, spec=0.5):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*base, 1)
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = rough
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Coat Roughness'].default_value = coat_rough
    p.inputs['Anisotropic'].default_value = aniso
    p.inputs['Transmission Weight'].default_value = transmission
    p.inputs['IOR'].default_value = ior
    p.inputs['Specular IOR Level'].default_value = spec
    if emission:
        p.inputs['Emission Color'].default_value = (*emission, 1); p.inputs['Emission Strength'].default_value = 1.0
    return m


def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)


def rounded_slab(name, w, h, d, r, edge_bevel, seg=28, profile=0.62, edge_seg=6):
    """Box w x h x d (XY plane, depth along Z) with continuous rounded corners and bevelled faces' perimeters."""
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * w, v.co.y * h, v.co.z * d))
    vert = [e for e in bm.edges if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-9 and abs(e.verts[0].co.y - e.verts[1].co.y) < 1e-9]
    bmesh.ops.bevel(bm, geom=vert, offset=r, segments=seg, profile=profile, affect='EDGES', clamp_overlap=True)
    if edge_bevel > 0:
        caps = [f for f in bm.faces if abs(f.normal.z) > 0.99]
        edges = list({e for f in caps for e in f.edges})
        bmesh.ops.bevel(bm, geom=edges, offset=edge_bevel, segments=edge_seg, profile=0.5, affect='EDGES', clamp_overlap=True)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    try:  # Blender 4.1+: smooth by angle
        bpy.context.view_layer.objects.active = ob; ob.select_set(True)
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
        ob.select_set(False)
    except Exception:
        pass
    return ob


def rounded_plane(name, w, h, r, seg=24):
    """Flat rounded rectangle built from its exact outline (4 quarter arcs), UV = position in the rectangle."""
    r = min(r, w / 2 - 1e-6, h / 2 - 1e-6)
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(seg + 1):
            t = math.radians(a0 + 90 * k / seg); pts.append((cx + r * math.cos(t), cy + r * math.sin(t), 0))
    bm = bmesh.new(); vs = [bm.verts.new(p) for p in pts]; f = bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=[f])
    uv = bm.loops.layers.uv.new('UVMap')
    for fa in bm.faces:
        for l in fa.loops:
            l[uv].uv = (l.vert.co.x / w + 0.5, l.vert.co.y / h + 0.5)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob); return ob


def cyl(name, r, depth, seg=96):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=depth)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def boolean_cut(target, cutter):
    m = target.modifiers.new('cut', 'BOOLEAN'); m.operation = 'DIFFERENCE'; m.object = cutter; m.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def pill(name, length, height, out, r):
    """Button: rounded box, length along Y, height along Z (phone depth), protruding `out` along X."""
    ob = rounded_slab(name, out, length, height, min(r, out * 0.49, length * 0.49), 0, seg=8)
    ob.rotation_euler = (0, 0, 0); return ob


def build(colors=None, screen_image=None):
    c = {'frame': '#2B2F36', 'back': '#24324A', 'plateau': '#1E2A3E', 'band': '#3A4150', 'ring': '#5A6170', **(colors or {})}
    root = bpy.data.objects.new('Phone', None); bpy.context.collection.objects.link(root)
    M = {
        'frame': mat('Frame', srgb(c['frame']), metallic=1.0, rough=0.34, aniso=0.3, coat=0.0, coat_rough=0.2),   # graphite: edges must not glow white (ref A f371-f393)
        'band': mat('AntennaBand', srgb(c['band']), metallic=0.0, rough=0.55),
        'glass_front': mat('FrontGlass', (0.002, 0.002, 0.0025), rough=0.18, coat=0.0, coat_rough=0.0, spec=0.12),   # black bezel stays black at grazing angles (a mirror coat reflected the white studio as a white band)
        'back': mat('BackFrosted', srgb(c['back']), metallic=0.25, rough=0.42, coat=1.0, coat_rough=0.22),
        'plateau': mat('CameraPlateau', srgb(c['plateau']), metallic=0.3, rough=0.08, coat=1.0, coat_rough=0.02),
        'ring': mat('LensRing', srgb(c['ring']), metallic=1.0, rough=0.16, aniso=0.6),
        'cell': mat('LensCell', (0.004, 0.004, 0.005), rough=0.3),
        'lens': mat('LensGlass', (0.006, 0.008, 0.016), metallic=0.0, rough=0.02, coat=1.0, coat_rough=0.0, spec=1.0),
        'flash': mat('Flash', srgb('#E9DDBE'), rough=0.35, transmission=0.3),
        'hole': mat('Hole', (0.002, 0.002, 0.002), rough=0.8),
        'island': mat('Island', (0.0, 0.0, 0.0), rough=0.45, coat=0.0, spec=0.05),   # matte black pill (ref): a glossy one turned white
    }
    # ---------- body + recesses / ports (booleans)
    body = rounded_slab('Body', W, H, D, R_CORNER, 0.7 * MM, seg=32, profile=0.62)
    body.data.materials.append(M['frame'])
    btns = [('Action', -1, 38.5, 7.0), ('VolUp', -1, 26.0, 10.5), ('VolDown', -1, 13.5, 10.5), ('Power', 1, 22.0, 17.5)]
    for nm, side, y, L in btns:
        cut = rounded_slab('cut_' + nm, 1.2 * MM, (L + 0.7) * MM, 3.1 * MM, 1.5 * MM, 0, seg=8)
        cut.location = (side * (W / 2), y * MM, 0); boolean_cut(body, cut)
    usb = rounded_slab('cut_usb', 8.6 * MM, 6 * MM, 2.7 * MM, 1.3 * MM, 0, seg=12)
    usb.location = (0, -H / 2, 0); boolean_cut(body, usb)
    for i in range(6):
        h_ = cyl('cut_spk%d' % i, 0.55 * MM, 6 * MM, 24); h_.rotation_euler = (math.pi / 2, 0, 0)
        h_.location = ((9.0 + i * 1.75) * MM, -H / 2, 0); boolean_cut(body, h_)
    for i in range(3):
        h_ = cyl('cut_mic%d' % i, 0.5 * MM, 6 * MM, 24); h_.rotation_euler = (math.pi / 2, 0, 0)
        h_.location = (-(9.0 + i * 1.75) * MM, -H / 2, 0); boolean_cut(body, h_)
    body.parent = root
    # port interiors (dark) so the holes read as holes
    inner = rounded_slab('USBInner', 7.6 * MM, 1.0 * MM, 1.9 * MM, 0.9 * MM, 0, seg=8); inner.location = (0, -H / 2 + 2.6 * MM, 0)
    inner.data.materials.append(M['hole']); inner.parent = root
    # ---------- buttons
    for nm, side, y, L in btns:
        b = rounded_slab(nm, 0.9 * MM, L * MM, 2.6 * MM, 1.25 * MM, 0.15 * MM, seg=10)
        b.location = (side * (W / 2 + 0.05 * MM), y * MM, 0); b.data.materials.append(M['frame']); b.parent = root
    # ---------- antenna bands (side + top/bottom)
    for sx, sy in ((-1, 1), (1, 1), (-1, -1), (1, -1)):
        a = rounded_slab('band', 0.5 * MM, 0.9 * MM, 6.0 * MM, 0.2 * MM, 0, seg=2)
        a.location = (sx * (W / 2 - 0.12 * MM), sy * (H / 2 - 15 * MM), 0); a.data.materials.append(M['band']); a.parent = root
    for sx in (-1, 1):
        for sy in (-1, 1):
            a = rounded_slab('band', 0.9 * MM, 0.5 * MM, 6.0 * MM, 0.2 * MM, 0, seg=2)
            a.location = (sx * 22 * MM, sy * (H / 2 - 0.12 * MM), 0); a.data.materials.append(M['band']); a.parent = root
    # ---------- front glass + screen + island
    fg = rounded_slab('FrontGlass', W - 0.9 * MM, H - 0.9 * MM, 0.55 * MM, R_CORNER - 0.45 * MM, 0.25 * MM, seg=32)
    fg.location = (0, 0, D / 2 - 0.05 * MM); fg.data.materials.append(M['glass_front']); fg.parent = root
    bez = 2.05 * MM
    scr = rounded_plane('Screen', W - 2 * bez, H - 2 * bez, R_CORNER - 1.9 * MM, 32)
    scr.location = (0, 0, D / 2 + 0.235 * MM); scr.parent = root
    smat = bpy.data.materials.new('ScreenMat'); smat.use_nodes = True; nt = smat.node_tree
    p = nt.nodes['Principled BSDF']; p.inputs['Base Color'].default_value = (0, 0, 0, 1); p.inputs['Roughness'].default_value = 0.03
    # screen: emissive UI under a LIGHT clear coat — a full-strength coat mirrors the white studio HDRI and washes
    # the brand colours out (checked against the reference: its screen stays saturated)
    p.inputs['Roughness'].default_value = 0.12   # soft reflections: a flipping card must not mirror crisply in the screen
    p.inputs['Coat Weight'].default_value = 0.06; p.inputs['Coat Roughness'].default_value = 0.1; p.inputs['Emission Strength'].default_value = 1.0
    p.inputs['Specular IOR Level'].default_value = 0.03   # grazing angles stay saturated; no mirror of the cards above (ref A)
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.name = 'ScreenTex'; tex.interpolation = 'Cubic'
    nt.links.new(tex.outputs['Color'], p.inputs['Emission Color'])
    scr.data.materials.append(smat)
    isl = rounded_plane('Island', 19 * MM, 5.6 * MM, 2.8 * MM, 16); isl.location = (0, H / 2 - bez - 5.2 * MM, D / 2 + 0.24 * MM)
    isl.data.materials.append(M['island']); isl.parent = root
    # front camera lens inside the island, right side (ref A f383: dark lens with a faint grey ring)
    for nm, r_, z_, m_ in (('FrontCamRing', 1.35 * MM, 0.255, mat('FrontCamRing', (0.05, 0.055, 0.065), metallic=0.6, rough=0.35, spec=0.2)),
                           ('FrontCamLens', 0.95 * MM, 0.26, mat('FrontCamLens', (0.008, 0.01, 0.02), rough=0.15, spec=0.35))):
        ln = cyl(nm, r_, 0.02 * MM, 48); ln.location = (5.6 * MM, H / 2 - bez - 5.2 * MM, D / 2 + z_ * MM); ln.data.materials.append(m_); ln.parent = root
    slit = rounded_plane('Earpiece', 13 * MM, 0.5 * MM, 0.25 * MM, 6); slit.location = (0, H / 2 - 1.1 * MM, D / 2 + 0.23 * MM)
    slit.data.materials.append(M['hole']); slit.parent = root
    # ---------- back glass + camera plateau + lenses
    bg = rounded_slab('BackGlass', W - 0.9 * MM, H - 0.9 * MM, 0.55 * MM, R_CORNER - 0.45 * MM, 0.25 * MM, seg=32)
    bg.location = (0, 0, -D / 2 + 0.05 * MM); bg.data.materials.append(M['back']); bg.parent = root
    px, py = W / 2 - 3.6 * MM - 17 * MM, H / 2 - 3.6 * MM - 17 * MM    # seen from the back: top-left = +x
    pl = rounded_slab('Plateau', 34 * MM, 34 * MM, 1.3 * MM, 7.8 * MM, 0.45 * MM, seg=24)
    pl.location = (px, py, -D / 2 - 0.5 * MM); pl.data.materials.append(M['plateau']); pl.parent = root
    zt = -D / 2 - 1.15 * MM
    for (lx, ly) in ((-7.6, 7.6), (-7.6, -7.6), (7.6, 7.6)):
        cx, cy = px + lx * MM, py + ly * MM
        ring = cyl('LensRing', 7.1 * MM, 1.9 * MM); ring.location = (cx, cy, zt - 0.55 * MM); ring.data.materials.append(M['ring']); ring.parent = root
        bev = ring.modifiers.new('bev', 'BEVEL'); bev.width = 0.35 * MM; bev.segments = 4
        cell = cyl('LensCell', 6.2 * MM, 0.2 * MM); cell.location = (cx, cy, zt - 1.52 * MM); cell.data.materials.append(M['cell']); cell.parent = root
        gl = cyl('LensGlass', 5.3 * MM, 0.25 * MM); gl.location = (cx, cy, zt - 1.6 * MM); gl.data.materials.append(M['lens']); gl.parent = root
        for k, rr in enumerate((3.6, 2.4, 1.3)):
            ir = cyl('LensInner', rr * MM, 0.05 * MM); ir.location = (cx, cy, zt - 1.45 * MM + k * 0.25 * MM)
            ir.data.materials.append(M['ring'] if k % 2 == 0 else M['cell']); ir.parent = root
    fl = cyl('Flash', 2.4 * MM, 0.3 * MM); fl.location = (px + 7.6 * MM, py - 5.2 * MM, zt - 0.1 * MM); fl.data.materials.append(M['flash']); fl.parent = root
    se = cyl('Sensor', 1.9 * MM, 0.3 * MM); se.location = (px + 7.6 * MM, py - 10.6 * MM, zt - 0.1 * MM); se.data.materials.append(M['cell']); se.parent = root
    mic = cyl('MicBack', 0.45 * MM, 0.3 * MM); mic.location = (px + 1.5 * MM, py - 1.0 * MM, zt - 0.05 * MM); mic.data.materials.append(M['hole']); mic.parent = root
    for ob in (fl, se, mic):
        pass
    # orientation: cylinders are along Z already (lens axis = phone depth)
    if screen_image:
        set_screen(screen_image)
    return root


def set_screen(path, sequence=False, frames=1, start=1, offset=0):
    tex = bpy.data.materials['ScreenMat'].node_tree.nodes['ScreenTex']
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = 'sRGB'
    if sequence:
        img.source = 'SEQUENCE'
        tex.image_user.frame_duration = frames; tex.image_user.frame_start = start; tex.image_user.frame_offset = offset
        tex.image_user.use_auto_refresh = True
    tex.image = img
    return img


def add_card(name, image_path, w, h, r, parent, thickness=None):
    """Real 3D UI card (measured on reference A: thickness ~2.5 % of its width, polished silver edge, glossy BLACK back,
    image face). The group pivots on its centre (rotationX flips it over, z lifts it off the screen)."""
    t = thickness or 0.025 * w
    g = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(g); g.parent = parent
    face = rounded_plane(name + '_face', w * 0.999, h * 0.999, r, 20); face.parent = g; face.location = (0, 0, t / 2 + 0.00015)
    m = bpy.data.materials.new(name + '_mat'); m.use_nodes = True; nt = m.node_tree; p = nt.nodes['Principled BSDF']
    tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(image_path, check_existing=True); tx.interpolation = 'Cubic'
    nt.links.new(tx.outputs['Color'], p.inputs['Base Color']); nt.links.new(tx.outputs['Color'], p.inputs['Emission Color'])
    p.inputs['Emission Strength'].default_value = 0.95; p.inputs['Roughness'].default_value = 0.4; p.inputs['Coat Weight'].default_value = 0.12
    p.inputs['Specular IOR Level'].default_value = 0.25
    p.inputs['Coat Roughness'].default_value = 0.05
    face.data.materials.append(m)
    edge = rounded_slab(name + '_edge', w, h, t, r, min(t * 0.35, 0.004), seg=14); edge.parent = g
    edge.data.materials.append(mat('CardEdge', srgb('#D9DEE2'), metallic=1.0, rough=0.26, coat=0.2))
    back = rounded_plane(name + '_back', w * 0.999, h * 0.999, r, 20); back.parent = g; back.location = (0, 0, -t / 2 - 0.00015)
    back.rotation_euler = (math.pi, 0, 0)
    back.data.materials.append(mat('CardBack', (0.006, 0.006, 0.007), rough=0.38, coat=0.6, coat_rough=0.3))   # satin black (ref f370)
    return g
