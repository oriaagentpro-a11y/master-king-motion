"""Procedural 3D icons ("tokens") for orbits / floating badges: clean glossy plastic, brand colours, decorated on BOTH
faces so they can spin freely (a token seen from behind must still read as the icon).

build(kind, colors) -> parent empty; the model fits a 1 x 1 box in X/Y (largest side = 1, centred), thickness on Z.
Kinds: 'coin_fcfa' (coin + raised franc sign), 'plane' (rounded tile + folded paper plane), 'card' (bank card: chip,
wave, contactless, two discs), 'wifi' (rounded tile + wifi arcs and dot), 'padlock' (glossy body, chrome tube shackle
as a SEPARATE child 'Shackle' moved by the per-frame 'shackle' value 1 open .. 0 closed, one-outline keyhole; the OPEN
padlock is 1 unit tall). New object = new kind here, modelled from the user's image (proportions, colours, parts that
move), checked with a test still against that image, never the image itself in the film.
Used by render_job.py with "object": "tokens" (one pose per token and per frame).
"""
import bpy, bmesh, math
import phone_build as pb

DEF = {'yellow': '#FFCC00', 'blue': '#064A8C', 'blue_dark': '#043A6E', 'light_blue': '#1E9BE9', 'white': '#F4F7FA',
       'gold': '#E2B33C'}


def plastic(name, hexc, rough=0.26, coat=0.55):
    return pb.mat(name, pb.srgb(hexc), metallic=0.0, rough=rough, coat=coat, coat_rough=0.08, spec=0.5)


def _obj(me, name, parent, m):
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob); ob.parent = parent
    ob.data.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def bevel(ob, w, seg=4):
    b = ob.modifiers.new('bevel', 'BEVEL'); b.width = w; b.segments = seg; b.limit_method = 'ANGLE'; b.harden_normals = False
    return ob


def prism(name, poly, z0, depth, parent, m, bev=0.012):
    """Extrude a 2D polygon (list of (x, y), counter-clockwise) from z0 to z0 + depth (depth < 0 = towards -Z)."""
    bm = bmesh.new(); vs = [bm.verts.new((x, y, z0)) for x, y in poly]; f = bm.faces.new(vs)
    if depth < 0:
        f.normal_flip()
    r = bmesh.ops.extrude_face_region(bm, geom=[f]); top = [e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, depth)); bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = _obj(me, name, parent, m)
    if bev:
        bevel(ob, bev, 3)
    return ob


def rrect(cx, cy, w, h, r, n=8):
    pts = []
    for (qx, qy, a0) in ((cx + w / 2 - r, cy + h / 2 - r, 0), (cx - w / 2 + r, cy + h / 2 - r, 90), (cx - w / 2 + r, cy - h / 2 + r, 180),
                         (cx + w / 2 - r, cy - h / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n); pts.append((qx + r * math.cos(a), qy + r * math.sin(a)))
    return pts


def arc(cx, cy, r0, r1, a0, a1, n=24):
    """Annulus sector with ROUND caps (wifi / contactless strokes)."""
    out = [(cx + r1 * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r1 * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
    rc, rm = (r1 - r0) / 2, (r0 + r1) / 2
    ex, ey = cx + rm * math.cos(math.radians(a1)), cy + rm * math.sin(math.radians(a1))
    out += [(ex + rc * math.cos(math.radians(a1 + 180 * i / 8)), ey + rc * math.sin(math.radians(a1 + 180 * i / 8))) for i in range(1, 8)]
    out += [(cx + r0 * math.cos(math.radians(a1 - (a1 - a0) * i / n)), cy + r0 * math.sin(math.radians(a1 - (a1 - a0) * i / n))) for i in range(n + 1)]
    sx, sy = cx + rm * math.cos(math.radians(a0)), cy + rm * math.sin(math.radians(a0))
    out += [(sx + rc * math.cos(math.radians(a0 + 180 + 180 * i / 8)), sy + rc * math.sin(math.radians(a0 + 180 + 180 * i / 8))) for i in range(1, 8)]
    return out


def disc(cx, cy, r, n=40):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def both_faces(fn, d):
    """Decorate the front (z = +d/2) and the back (mirrored, z = -d/2)."""
    fn(+1, d / 2); fn(-1, -d / 2)


def build(kind, colors=None):
    C = {**DEF, **(colors or {})}
    root = bpy.data.objects.new('Token_' + kind, None); bpy.context.collection.objects.link(root)
    Y, B, BD = plastic('Yellow', C['yellow'] if kind != 'padlock' else '#FFD21F'), plastic('Blue', C['blue']), plastic('BlueDark', C['blue_dark'])
    if kind == 'coin_fcfa':
        d = 0.15
        body = pb.cyl('Coin', 0.5, d, 128); bevel(body, 0.045, 6); body.parent = root; body.data.materials.append(Y)   # a TRUE disc
        for s, z in ((1, d / 2), (-1, -d / 2)):
            bpy.ops.mesh.primitive_torus_add(major_radius=0.395, minor_radius=0.024, major_segments=96, minor_segments=16, location=(0, 0, z))
            ring = bpy.context.active_object; ring.name = 'Rim'; ring.scale = (1, 1, 0.7); ring.parent = root; ring.data.materials.append(Y)
            bpy.ops.object.shade_smooth()
            # franc sign: stem, top bar, middle bar, crossing bar (raised, blue)
            for nm, poly in (('Stem', rrect(-0.07, 0.0, 0.115, 0.56, 0.045)), ('Top', rrect(0.065, 0.225, 0.33, 0.11, 0.045)),
                             ('Mid', rrect(0.04, 0.035, 0.27, 0.1, 0.045)), ('Cross', rrect(-0.05, -0.115, 0.29, 0.09, 0.04))):   # bold, rounded (user's icon)
                if s < 0:
                    poly = [(-x, y) for x, y in poly][::-1]
                prism(nm, poly, z, s * 0.035, root, B, 0.012)
    elif kind in ('plane', 'wifi'):
        d = 0.2; base = Y if kind == 'wifi' else B
        tile = pb.rounded_slab('Tile', 1.0, 1.0, d, 0.25, 0.07, seg=24, profile=0.62); tile.parent = root; tile.data.materials.append(base)
        for s, z in ((1, d / 2), (-1, -d / 2)):
            if kind == 'plane':
                A, Bp, Cp, Dp = (0.34, 0.34), (-0.38, 0.03), (-0.04, -0.08), (-0.12, -0.38)   # big folded plane (user's icon)
                for nm, tri, h in (('WingL', [A, Bp, Cp], 0.03), ('WingR', [A, Cp, Dp], 0.05), ('Fold', [Cp, (-0.07, -0.12), Dp], 0.07)):
                    if s < 0:
                        tri = [(-x, y) for x, y in tri][::-1]
                    prism(nm, tri, z, s * h, root, Y, 0.01)
            else:
                pieces = [arc(0, -0.29, 0.115 + 0.135 * i, 0.21 + 0.135 * i, 42, 138) for i in range(3)] + [disc(0, -0.29, 0.075)]   # bold strokes
                for i, poly in enumerate(pieces):
                    if s < 0:
                        poly = [(-x, y) for x, y in poly][::-1]
                    prism('Wifi%d' % i, poly, z, s * 0.045, root, B, 0.014)
    elif kind == 'card':
        d = 0.075; w, h = 1.0, 0.64
        body = pb.rounded_slab('Card', w, h, d, 0.085, 0.025, seg=16, profile=0.6); body.parent = root; body.data.materials.append(B)
        gold = pb.mat('Chip', pb.srgb(C['gold']), metallic=1.0, rough=0.3, coat=0.3)
        LB, W_ = plastic('LightBlue', C['light_blue']), plastic('White', C['white'])
        for s, z in ((1, d / 2), (-1, -d / 2)):
            m_ = (lambda P: [(-x, y) for x, y in P][::-1]) if s < 0 else (lambda P: P)
            # wave: bottom-left area, following the rounded corner, bounded by a falling curve (user's icon)
            wave = [(-0.415 + 0.085 * math.cos(math.radians(a)), -0.235 + 0.085 * math.sin(math.radians(a))) for a in range(180, 271, 10)]
            wave += [(-0.5 + 0.62 * t, -0.32 + 0.21 * (1 - t) ** 1.6) for t in [1 - i / 20 for i in range(21)]]
            prism('Wave', m_(wave), z, s * 0.008, root, Y, 0.0)
            prism('Chip', m_(rrect(-0.27, 0.07, 0.17, 0.13, 0.025)), z, s * 0.014, root, gold, 0.004)
            groove = pb.mat('ChipGroove', (0.25, 0.17, 0.04), metallic=1.0, rough=0.45)
            for gx, gy, gw, gh in ((-0.27, 0.07, 0.17, 0.008), (-0.31, 0.07, 0.008, 0.13), (-0.23, 0.07, 0.008, 0.13)):
                prism('Groove', m_(rrect(gx, gy, gw, gh, 0.003, 2)), z + s * 0.014, s * 0.002, root, groove, 0.0)
            for i, poly in enumerate([arc(0.24, 0.18, 0.03 + 0.045 * k, 0.05 + 0.045 * k, -40, 40, 12) for k in range(3)]):
                prism('NFC%d' % i, m_(poly), z, s * 0.012, root, W_, 0.003)
            prism('DiscY', m_(disc(0.19, -0.16, 0.07)), z, s * 0.012, root, Y, 0.004)
            prism('DiscB', m_(disc(0.29, -0.16, 0.07)), z, s * 0.016, root, LB, 0.004)
    elif kind == 'padlock':
        # user's padlock: glossy yellow rounded body, chrome tube shackle (left leg long, stays in the body; right leg
        # comes out when open), teal keyhole inlay. The shackle is a separate child 'Shackle' (moved down to close).
        d = 0.36; bw, bh = 0.86, 0.68; top = 0.0
        body = pb.rounded_slab('LockBody', bw, bh, d, 0.19, 0.1, seg=28, profile=0.6); body.location = (0, top - bh / 2, 0)
        body.parent = root; body.data.materials.append(Y)
        chrome = pb.mat('Chrome', pb.srgb('#DCE0E6'), metallic=1.0, rough=0.2, coat=0.2)   # bright satin silver (user's design)
        cv = bpy.data.curves.new('ShackleCurve', 'CURVE'); cv.dimensions = '3D'; cv.bevel_depth = 0.078; cv.bevel_resolution = 8
        sp = cv.splines.new('POLY'); R = 0.235; legL, legR = 0.57, 0.30   # chunky tube, wide low arch (user's design)
        pts = [(-R, -legL + 0.2, 0)] + [(-R * math.cos(math.radians(a)), 0.2 + R * math.sin(math.radians(a)), 0) for a in range(0, 181, 6)] + [(R, 0.0, 0)]
        pts[-1] = (R, -0.08, 0)        # right leg end: just inside the body when closed, out of it when open
        sp.points.add(len(pts) - 1)
        for i, (x, y, z) in enumerate(pts):
            sp.points[i].co = (x, y, z, 1)
        sh = bpy.data.objects.new('Shackle', cv); bpy.context.collection.objects.link(sh); sh.parent = root
        sh.data.materials.append(chrome); cv.use_fill_caps = True
        # keyhole inlay (front), slightly sunk, teal matte
        teal = pb.mat('Keyhole', pb.srgb('#0B4F6C'), rough=0.5, spec=0.2)
        # ONE outline (round top + flared slot): two overlapping pieces showed a seam
        cy_, r_ = top - bh * 0.38, 0.105; a0 = math.degrees(math.asin(0.05 / r_))
        kh = [(r_ * math.cos(math.radians(a)), cy_ + r_ * math.sin(math.radians(a))) for a in [-90 + a0 + (360 - 2 * a0) * i / 48 for i in range(49)]]
        kh += [(-0.085, top - bh * 0.82), (0.085, top - bh * 0.82)]   # flared slot, counter-clockwise
        prism('Keyhole', kh, d / 2 + 0.001, -0.035, root, teal, 0.004)
        root['open_raise'] = 0.30      # shackle lift when open: free end clearly above the body (user's design); closed = 0
        root.scale = (1 / 1.49,) * 3     # OPEN padlock = 1 unit tall (like the 2D asset the film sizes)
        root['shackle_obj'] = 'Shackle'
    else:
        raise ValueError('token inconnu : ' + kind)
    return root
