"""App icon as a REAL 3D object (thick rounded tile, bevelled glossy edges, printed face) for Cycles.
build(face_image, depth=0.16, radius=0.23): tile 1.0 x 1.0 (height 1 unit, like the phone), face texture on the front,
sides and back in the face's dominant colour (sampled), clear-coated plastic like a premium 3D icon render."""
import bpy, math
import phone_build as pb


def build(face_image, depth=0.16, radius=0.23, side='#00375F'):
    root = bpy.data.objects.new('Icon', None); bpy.context.collection.objects.link(root)
    bev = depth * 0.32
    body = pb.rounded_slab('IconBody', 1.0, 1.0, depth, radius, bev, seg=32, profile=0.6, edge_seg=10)
    body.data.materials.append(pb.mat('IconSide', pb.srgb(side), metallic=0.0, rough=0.28, coat=1.0, coat_rough=0.06, spec=0.6))
    body.parent = root
    face = pb.rounded_plane('IconFace', 1.0 - 2 * bev * 0.92, 1.0 - 2 * bev * 0.92, radius - bev * 0.92, 40)
    face.location = (0, 0, depth / 2 + 0.0008); face.parent = root
    m = bpy.data.materials.new('IconFaceMat'); m.use_nodes = True; nt = m.node_tree; p = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(face_image); t.interpolation = 'Cubic'
    nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.3; p.inputs['Coat Weight'].default_value = 0.35; p.inputs['Coat Roughness'].default_value = 0.2; p.inputs['Specular IOR Level'].default_value = 0.35   # satin: a mirror coat put a white light rectangle over the logo in 3/4 view
    face.data.materials.append(m)
    return root
