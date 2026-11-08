"""Render a 3D job with Blender Cycles: the photoreal phone (phone_build.py) at the MEASURED pose of every frame.

Usage: blender/app/blender -b -P blender/render_job.py -- job.json
job.json (written by scripts/export_3d.py from the film, or by hand):
{ "W": 1920, "H": 1080, "fps": 30, "fov": 30, "out": "out/render3d/P3/f_####.png",
  "samples": 96, "motion_blur": 0.5, "hdri": ".../studio_small_08_2k.hdr", "hdri_strength": 1.0, "hdri_rot": 0,
  "colors": {"frame": "#4A5260", "back": "#24324A"}, "shadow": {"z": -0.7, "opacity": 0.35} | null,
  "screen": {"pattern": "screens/s_%05d.png", "first": 1} | {"image": "home.png"},
  "cards": [{"image": "cards/c0.png", "w": 0.42, "h": 0.15, "y": 0.18}],
  "frames": [{"f": 1, "pose": {"x":..,"y":..,"z":..,"rx":..,"ry":..,"rz":..}, "cards": [{"z": 0.0, "rx": 0}]}, ...] }
Pose convention = engine/mk-phone3d.js: camera at the origin looking down -Z, Y up, phone 1 unit tall, Euler YXZ deg.
Output: RGBA PNG frames (transparent film), composited by the film over its own backdrop.
"""
import bpy, sys, os, json, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phone_build as pb  # noqa: E402

job_path = sys.argv[sys.argv.index('--') + 1]
J = json.load(open(job_path)); base = os.path.dirname(os.path.abspath(job_path))
P = lambda p: p if os.path.isabs(p) else os.path.join(base, p)

# fresh scene
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = J.get('samples', 96); sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True
try:
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception:
    pass
sc.cycles.max_bounces = 8; sc.cycles.glossy_bounces = 4; sc.cycles.transmission_bounces = 6
sc.render.resolution_x, sc.render.resolution_y = J['W'], J['H']; sc.render.resolution_percentage = 100
sc.render.fps = int(round(J['fps'])); sc.render.film_transparent = True
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'; sc.render.image_settings.color_depth = '8'
sc.view_settings.view_transform = 'Standard'   # UI colours must stay exact (AgX/Filmic desaturate brand colours)
sc.view_settings.look = 'None'; sc.view_settings.exposure = J.get('exposure', 0.0)
mb = J.get('motion_blur', 0.5)
sc.render.use_motion_blur = bool(mb); sc.render.motion_blur_shutter = mb or 0.5

# world: studio HDRI
w = bpy.data.worlds.new('World'); sc.world = w; w.use_nodes = True; nt = w.node_tree
env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(P(J['hdri']))
mp = nt.nodes.new('ShaderNodeMapping'); tc = nt.nodes.new('ShaderNodeTexCoord')
mp.inputs['Rotation'].default_value[2] = math.radians(J.get('hdri_rot', 0))
nt.links.new(tc.outputs['Generated'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
bgn = nt.nodes['Background']; bgn.inputs['Strength'].default_value = J.get('hdri_strength', 1.0)
nt.links.new(env.outputs['Color'], bgn.inputs['Color'])

# camera (same as the film: origin, looking -Z, vertical fov)
cam_data = bpy.data.cameras.new('Cam'); cam_data.sensor_fit = 'VERTICAL'; cam_data.angle_y = math.radians(J.get('fov', 30))
cam_data.clip_start = 0.01; cam_data.clip_end = 100
cam = bpy.data.objects.new('Cam', cam_data); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (0, 0, 0); cam.rotation_euler = (0, 0, 0)

# extra key / rim lights for the metal edges (studio look), optional
if J.get('object', 'phone') == 'icon':
    import icon_build
    phone = icon_build.build(P(J['icon']['face']), depth=J['icon'].get('depth', 0.16), radius=J['icon'].get('radius', 0.23),
                             side=J['icon'].get('side', '#00375F'))
elif J.get('object') == 'padlock':     # tokens_build 'padlock': per-frame 'shackle' = 0 closed .. 1 open
    import tokens_build
    phone = tokens_build.build('padlock', J.get('token_colors'))
    shackle = [c for c in phone.children if c.name.startswith('Shackle')][0]; raise_ = phone['open_raise']
    for fr in J['frames']:
        shackle.location.y = raise_ * fr.get('shackle', 1.0); shackle.keyframe_insert('location', frame=fr['f'])
    for fc in shackle.animation_data.action.fcurves:
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'
elif J.get('object') == 'tokens':
    import tokens_build
    toks = [tokens_build.build(k, J.get('token_colors')) for k in J['tokens']]
    for t_ in toks:
        t_.rotation_mode = 'ZXY'
    phone = toks[0]     # lights aim at the first token's track; every token is keyed below
else:
    phone = pb.build(colors=J.get('colors'))
phone.rotation_mode = 'ZXY'     # = Three.js Euler 'YXZ' (R = Ry . Rx . Rz)
# studio lights placed AROUND THE OBJECT (offsets in object heights from its mean position, aimed at it), never near
# the camera: with a long lens the object is far away and a light near the lens sits in the screen's mirror direction
# and veils it white (measured: header #004B6E rendered (122,142,168) before the fix, (2,75,109) face-on).
vis = [f['pose'] for f in J['frames'] if f['pose']['z'] < 40]
cx_ = sum(p['x'] for p in vis) / max(1, len(vis)); cy_ = sum(p['y'] for p in vis) / max(1, len(vis)); cz_ = sum(p['z'] for p in vis) / max(1, len(vis))
for name, off, energy, size in J.get('lights', [('Key', (-1.6, 2.2, 0.6), 90, 1.6), ('Fill', (2.2, -0.4, 1.2), 30, 2.4), ('Rim', (1.6, 1.4, -2.2), 110, 1.2)]):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.size = size
    lo = bpy.data.objects.new(name, ld); sc.collection.objects.link(lo); lo.location = (cx_ + off[0], cy_ + off[1], cz_ + off[2])
    tr = lo.constraints.new('TRACK_TO'); tr.target = phone; tr.track_axis = 'TRACK_NEGATIVE_Z'; tr.up_axis = 'UP_Y'
scr = J.get('screen', {})
n = len(J['frames'])
if 'pattern' in scr:
    first = scr.get('first', 1)
    pb.set_screen(P(scr['pattern'] % first), sequence=True, frames=n, start=J['frames'][0]['f'], offset=first - 1)
elif 'image' in scr:
    pb.set_screen(P(scr['image']))
cards = []
for i, c in enumerate(J.get('cards', [])):
    g = pb.add_card('Card%d' % i, P(c['image']), c['w'], c['h'], c.get('r', c['h'] * 0.16), phone)
    t = c.get('t', 0.025 * c['w'])
    g.location = (0, c.get('y', 0), pb.D / 2 + 0.235 * pb.MM + t / 2 + 0.0004); cards.append((g, g.location.z))
if J.get('shadow'):
    bpy.ops.mesh.primitive_plane_add(size=20); sp = bpy.context.active_object; sp.location = (0, 0, J['shadow']['z'])
    sp.is_shadow_catcher = True

if J.get('object') == 'tokens':   # one pose per token and per frame (far away = hidden)
    for fr in J['frames']:
        for t_, p in zip(toks, fr['poses']):
            t_.location = (p['x'], p['y'], p['z'])
            t_.rotation_euler = (math.radians(p.get('rx', 0)), math.radians(p.get('ry', 0)), math.radians(p.get('rz', 0)))
            t_.keyframe_insert('location', frame=fr['f']); t_.keyframe_insert('rotation_euler', frame=fr['f'])
    for t_ in toks:
        for fc in t_.animation_data.action.fcurves:
            for k in fc.keyframe_points:
                k.interpolation = 'LINEAR'
for fr in ([] if J.get('object') == 'tokens' else J['frames']):
    f = fr['f']; p = fr['pose']
    phone.location = (p['x'], p['y'], p['z'])
    phone.rotation_euler = (math.radians(p.get('rx', 0)), math.radians(p.get('ry', 0)), math.radians(p.get('rz', 0)))
    phone.keyframe_insert('location', frame=f); phone.keyframe_insert('rotation_euler', frame=f)
    for (g, z0), cs in zip(cards, fr.get('cards', [])):
        g.location.z = z0 + cs.get('z', 0); g.rotation_euler[0] = math.radians(cs.get('rx', 0))
        g.keyframe_insert('location', frame=f); g.keyframe_insert('rotation_euler', frame=f)
for ob in [phone] + [g for g, _ in cards]:
    if ob.animation_data and ob.animation_data.action:
        for fc in ob.animation_data.action.fcurves:
            for k in fc.keyframe_points:
                k.interpolation = 'LINEAR'     # the poses are already per frame (measured / computed): no extra easing

sc.frame_start = J['frames'][0]['f']; sc.frame_end = J['frames'][-1]['f']
if J.get('render_frames'):   # re-render only a range, with ALL keyframes kept (motion blur continuity)
    sc.frame_start, sc.frame_end = J['render_frames']
sc.render.filepath = P(J['out'])
if J.get('still') is not None:
    sc.frame_set(J['still']); sc.render.filepath = P(J['out']).replace('####', '%04d' % J['still'])
    bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
print('MKM_DONE', sc.frame_start, sc.frame_end)
