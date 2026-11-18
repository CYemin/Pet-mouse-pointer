# Frozen operation symbols, version 1

These six transparent symbols are extracted pixels from the existing native48
cursor artwork. No pixels were drawn, generated, recoloured, or interpolated.
The renderer uses nearest-neighbour resizing and composites the symbols after
pet palette conversion.

`sources.json` records each reviewed source frame, its SHA256, extracted bounding
rectangle, and opaque-pixel count. The `*-frozen-source.png` files preserve those
complete source frames. Each symbol PNG contains only the selected isolated
four-connected alpha component, so dog pixels inside its bounding rectangle are
excluded.

The five resize/move symbols come from `output/pet-pixel-complete`; the up arrow
comes from `output/golden-cream-pixel`. Runtime rendering only needs the six
symbol PNG files. The source metadata and frozen frames are provenance records.

Use `operation_mark_config(spec)` to opt a supported state into the renderer,
then call `apply_operation_marks(frames, anchor, spec, options, root)` after native
pixel quantization. Config geometry uses the original 48px canvas. Unsupported
states are unchanged unless explicitly opted in, in which case they are rejected.
