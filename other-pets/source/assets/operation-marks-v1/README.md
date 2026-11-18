# Frozen operation symbols, template revision 2

These six transparent symbols come from the original golden cursor sprite sheets,
aligned through the normal compiler at native240 with its existing pixel/palette
conversion. Extraction copies those prepared pixels; it draws no replacement art.
The renderer uses nearest-neighbour resizing and composites symbols after the pet
palette conversion. The directory name remains stable for the portable API.

`sources.json` records each reviewed source frame, its SHA256, extracted bounding
rectangle, and opaque-pixel count. It also records the original sprite-sheet hash
and preparation settings. The `*-frozen-source.png` files preserve complete240px
source frames. Symbols use isolated four-connected alpha components, except WE
and Move whose arrow/nose contact requires reviewed rectangle exclusions.

All six symbols now come from `assets/golden-cream-pixel`. The original native48
extractions and provenance remain under `versions/v1/`. Runtime rendering only
needs the six symbol PNG files. Source metadata and frozen frames are provenance
records, with no runtime dependency.

Use `operation_mark_config(spec)` to opt a supported state into the renderer,
then call `apply_operation_marks(frames, anchor, spec, options, root)` after native
pixel quantization. Config geometry uses the original 48px canvas. Unsupported
states are unchanged unless explicitly opted in, in which case they are rejected.

The local development tool `scripts/preview_operation_marks.py --verify` builds
`output/arrow-upgrade/prototype-v2.png` and checks all six themes at five native
sizes. That project preview tool is separate from the portable renderer.
