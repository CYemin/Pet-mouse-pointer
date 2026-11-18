"""Extracted operation symbols and a reversible post-quantization compositor.

Only specs containing ``operation_mark`` opt in. All geometry in the config is
expressed on a 48px canvas; it is scaled for other native pixel sizes. Pet pixels
are only erased in the reviewed old-symbol region, then moved/scaled with nearest
neighbour sampling. The extracted symbol RGB pixels are never redrawn/recoloured.
"""
from pathlib import Path
from PIL import Image


KINDS = ('size-ns', 'size-we', 'size-nwse', 'size-nesw', 'move', 'alternate')
MARKER_SIZES = dict(zip(KINDS, ((9, 21), (26, 13), (19, 19), (19, 19), (21, 21), (12, 18))))
PET_BOXES = {kind: (16, 16, 47, 47) for kind in KINDS}
PET_BOXES.update({'size-ns': (14, 13, 47, 47), 'size-we': (15, 19, 47, 47),
                  'size-nwse': (17, 17, 47, 47), 'alternate': (15, 14, 47, 47)})
# Boxes are absolute coordinates in reviewed reference 48px frames. Reference
# hotspots are recorded alongside them for optional anchor-relative calibration.
REMOVAL = {
    'sheltie': {
        'size-ns': ((3, 3, 10, 16), (6, 10), ((8, 10, 10, 14),)),
        'size-we': ((6, 3, 21, 11), (13, 7), ((19, 9, 21, 11),)),
        'size-nwse': ((3, 3, 15, 15), (9, 9), ()),
        'size-nesw': ((3, 3, 14, 14), (9, 8), ((8, 13, 14, 14),)),
        'move': ((4, 3, 16, 16), (10, 10), ((7, 15, 16, 16),)),
        'alternate': ((3, 3, 11, 15), (7, 4), ((9, 12, 11, 14), (8, 14, 11, 15))),
    },
    'golden': {
        'size-ns': ((3, 4, 11, 18), (7, 11), ((9, 16, 11, 18),)),
        'size-we': ((8, 3, 31, 14), (20, 8), ((26, 13, 31, 14), (30, 10, 31, 14))),
        'size-nwse': ((3, 3, 15, 15), (9, 9), ()),
        'size-nesw': ((3, 3, 15, 16), (9, 9), ((9, 14, 15, 15), (14, 10, 15, 15), (7, 15, 15, 16))),
        'move': ((3, 3, 16, 15), (10, 9), ((15, 13, 16, 15),)),
        'alternate': ((3, 3, 11, 11), (7, 3), ((10, 10, 11, 11),)),
    },
}


def _components(frame):
    points = {(x, y) for y in range(frame.height) for x in range(frame.width)
              if frame.getpixel((x, y))[3]}
    result = []
    while points:
        point = points.pop()
        todo, component = [point], {point}
        while todo:
            x, y = todo.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                other = x + dx, y + dy
                if other in points:
                    points.remove(other)
                    todo.append(other)
                    component.add(other)
        result.append(component)
    return result


def _inside(point, box):
    x, y = point
    return box[0] <= x < box[2] and box[1] <= y < box[3]


def _scale_box(box, scale, offset=(0, 0)):
    return tuple(round((value + offset[index % 2]) * scale) for index, value in enumerate(box))


def _remove_old(frame, box, protect, component_limit):
    """An isolated mark is removed exactly; touching marks use reviewed cutouts."""
    frame = frame.copy()
    components = _components(frame)
    candidates = [part for part in components
                  if 8 <= len(part) <= component_limit and all(_inside(p, box) for p in part)]
    if candidates:
        # All eligible components are old-symbol pixels. Tiny detached pet
        # pixels are protected by the reviewed per-state regions below.
        remove = set().union(*candidates)
    else:
        remove = {(x, y) for y in range(max(0, box[1]), min(frame.height, box[3]))
                  for x in range(max(0, box[0]), min(frame.width, box[2]))
                  if not any(_inside((x, y), keep) for keep in protect)}
    # Small disconnected outline fragments can accompany an isolated mark.
    # Keep reviewed nose-edge pixels even if they are individually disconnected.
    remove.update(p for part in components if len(part) < 8 and all(_inside(p, box) for p in part)
                  for p in part if not any(_inside(p, keep) for keep in protect))
    for point in remove:
        frame.putpixel(point, (0, 0, 0, 0))
    return frame


def operation_mark_config(spec):
    """Minimal opt-in config; explicit keys in spec.operation_mark override it."""
    family = 'golden' if 'golden' in str(spec.get('source', '')) else 'sheltie'
    return {'kind': spec['id'], 'family': family}


def apply_operation_marks(frames, anchor, spec, options, root):
    """Return new frames and symbol hotspot, or unchanged inputs when disabled.

    Config keys: kind, family, removal_box, removal_relative_to_anchor,
    reference_anchor, protect_boxes, pet_box, marker_size, marker_pos, and
    frame_overrides (frame-index strings mapping removal/protection overrides).
    Default removal coordinates are absolute. A reference_anchor opts into
    following the original hotspot delta; relative-to-anchor boxes are supported.
    """
    settings = spec.get('operation_mark')
    if not settings:
        return frames, anchor
    config = operation_mark_config(spec)
    if isinstance(settings, dict):
        config.update(settings)
    kind = config['kind']
    if kind not in KINDS:
        raise ValueError('Unsupported operation mark: ' + str(kind))
    if not frames or any(f.size != frames[0].size or f.mode != 'RGBA' for f in frames):
        raise ValueError('Operation marks require equally sized RGBA frames')
    native = frames[0].width
    if frames[0].height != native:
        raise ValueError('Operation marks require a square native canvas')
    scale = native / 48
    old_box, reference, keeps = REMOVAL[config['family']][kind]
    if 'removal_box' in config:
        old_box = config['removal_box']
        reference = config.get('reference_anchor')
    reference = config.get('reference_anchor')
    if config.get('removal_relative_to_anchor'):
        offset = anchor[0] / scale, anchor[1] / scale
    elif reference is not None:
        offset = anchor[0] / scale - reference[0], anchor[1] / scale - reference[1]
    else:
        offset = (0, 0)
    keeps = config.get('protect_boxes', keeps)
    cleaned = []
    for index, frame in enumerate(frames):
        override = config.get('frame_overrides', {}).get(str(index), {})
        box = _scale_box(override.get('removal_box', old_box), scale, offset)
        protect = [_scale_box(keep, scale, offset)
                   for keep in override.get('protect_boxes', keeps)]
        cleaned.append(_remove_old(frame, box, protect, round(250 * scale * scale)))
    bounds = [f.getchannel('A').getbbox() for f in cleaned]
    if any(box is None for box in bounds):
        raise ValueError('Removal erased the pet: ' + kind)
    union = (min(b[0] for b in bounds), min(b[1] for b in bounds),
             max(b[2] for b in bounds), max(b[3] for b in bounds))
    pet_box = _scale_box(config.get('pet_box', PET_BOXES[kind]), scale)
    ratio = min((pet_box[2] - pet_box[0]) / (union[2] - union[0]),
                (pet_box[3] - pet_box[1]) / (union[3] - union[1]))
    pet_size = (max(1, round((union[2] - union[0]) * ratio)),
                max(1, round((union[3] - union[1]) * ratio)))
    pet_pos = (pet_box[2] - pet_size[0], pet_box[3] - pet_size[1])
    marker_size = tuple(max(1, round(n * scale))
                        for n in config.get('marker_size', MARKER_SIZES[kind]))
    marker_pos = tuple(round(n * scale) for n in config.get('marker_pos', (3, 3)))
    if (min(*pet_pos, *marker_pos) < 0 or pet_pos[0] + pet_size[0] > native
            or pet_pos[1] + pet_size[1] > native
            or marker_pos[0] + marker_size[0] > native
            or marker_pos[1] + marker_size[1] > native):
        raise ValueError('Operation geometry clips the canvas: ' + kind)
    source = Image.open(Path(__file__).resolve().parents[1] / 'assets/operation-marks-v1' / (kind + '.png')).convert('RGBA')
    marker = source.resize(marker_size, Image.Resampling.NEAREST)
    result = []
    for pet in cleaned:
        canvas = Image.new('RGBA', (native, native))
        art = pet.crop(union).resize(pet_size, Image.Resampling.NEAREST)
        canvas.alpha_composite(art, pet_pos)
        if any(marker.getpixel((x, y))[3] and canvas.getpixel((marker_pos[0] + x, marker_pos[1] + y))[3]
               for y in range(marker.height) for x in range(marker.width)):
            raise ValueError('Operation mark overlaps pet pixels: ' + kind)
        canvas.alpha_composite(marker, marker_pos)
        result.append(canvas)
    new_anchor = (marker_pos[0] + marker_size[0] // 2,
                  marker_pos[1] if kind == 'alternate' else marker_pos[1] + marker_size[1] // 2)
    return result, new_anchor
