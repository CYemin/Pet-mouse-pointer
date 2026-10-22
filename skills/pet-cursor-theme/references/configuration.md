# Cursor source configuration

`states` must contain each of the 17 roles exactly once:

| Registry role | Meaning | Functional contact point |
|---|---|---|
| Arrow | Normal select | Nose / chosen obvious tip |
| Help | Help select | Nose / tip |
| AppStarting | Working in background | Nose / tip |
| Wait | Busy | Obvious fixed point in resting design |
| Crosshair | Precision | Crosshair center |
| IBeam | Text select | Insertion-line center |
| NWPen | Handwriting | Pencil tip |
| No | Unavailable | Prohibition-mark center |
| SizeNS | Vertical resize | Arrow midpoint |
| SizeWE | Horizontal resize | Arrow midpoint |
| SizeNWSE | Backslash diagonal resize | Arrow midpoint |
| SizeNESW | Forward-slash diagonal resize | Arrow midpoint |
| SizeAll | Move | Four-way intersection |
| UpArrow | Alternate select | Up-arrow tip |
| Hand | Link select | Nose / chosen obvious tip |
| Pin | Location select | Nose / clearly designed tip |
| Person | Person select | Nose / clearly designed tip |

Example single-state entry (include all roles in the final config):

```json
{
  "id": "help",
  "role": "Help",
  "label": "帮助选择",
  "idea": "疑惑歪头、抬起一边眉毛",
  "source": "assets/my-pet/help.png",
  "grid": [2, 2],
  "landmarks": [[0.09,0.21],[0.095,0.21],[0.09,0.215],[0.09,0.21]],
  "sequence": [0,1,2,1,3],
  "ticks": [100,12,14,12,60]
}
```

- `source` is relative to `--root`. Use a transparent RGBA PNG.
- `grid` gives columns and rows, with frame indices in row-major order.
- `source_frames` optionally selects a subset of grid cells, such as `[0,1,2,3]`.
- `source_rects` optionally supplies explicit `[left, top, right, bottom]` rectangles in source-image pixels, one per selected frame. Use these when generated sprites have uneven spacing or cross nominal grid lines. Do not crop through the pet or include a neighboring sprite. Landmarks are relative to these actual rectangles, not the nominal grid cells; use pixel coordinates to preserve the measured nose location when changing bounds.
- `landmarks` contains a coordinate for every selected cell. Coordinates default to normalized cell width/height. `landmark_units: "pixels"` uses source-cell pixels instead.
- `hotspot_overrides` optionally maps an exported size to a reviewed integer point, e.g. `{"32":[4,4]}`. Use only when nearest-neighbour sampling makes a thin marker's rendered junction differ from the scaled coordinate. Inspect every frame at that size; retain the actual junction or tip, rather than moving the point for convenience.
- Measure landmarks from the actual generated image. Requested prompt positions are not evidence of actual geometry.
- `sequence` indexes the selected frames, not the original sheet. `ticks` uses 1/60 second units, one value per sequence step.
- A one-frame state exports as CUR; multiple frames export as ANI. Precision states may animate the pet while retaining stable operation marks and a fixed hotspot. All17roles can be animated when requested.
- The compiler aligns all frames to a common contact point and common square, retaining source-frame scale. It emits 32/48/64/96/128 variants plus default 48px copies.
- A raw source border should be fully transparent. Inspect faint background washes or halos before encoding; request image-tool cleanup if needed.

## Larger operation arrows

For pixel-art themes, `operation_mark` optionally extracts the old small mark from each aligned native frame and places an enlarged, fixed symbol beside the pet. This technical composition preserves the pet's animation with a shared crop/scale per state. All ordinary point-select roles remain unchanged when the property is absent.

```json
{
  "id": "size-we",
  "operation_mark": {"kind": "size-we", "family": "golden"}
}
```

The six supported kinds are `size-ns`, `size-we`, `size-nwse`, `size-nesw`, `move` and `alternate`. At native48px their standard symbol extents are9×21,26×13,19×19,19×19,21×21 and12×18px. Symbols use a consistent brown/cream pixel style; their centers are the click points, except `alternate`, which uses the up-arrow tip.

The bundled `sheltie` and `golden` families are reviewed extraction/layout presets for this repository's example source geometry. Do not apply them blindly to a different drawing. For another layout, review `removal_box`, `protect_boxes`, per-frame overrides, `pet_box`, `marker_pos` and `marker_size` in `operation_marks.py`. Removal coordinates use the pre-composition48px canvas; optional `reference_anchor` or `removal_relative_to_anchor` controls coordinate adjustment. The helper rejects overlap between the new symbol and pet pixels or geometry outside the canvas.

Templates load from the Skill's own `assets/operation-marks-v1/`; independent projects do not need to copy them. After changing a mark, inspect all frames on both backgrounds, verify the rendered mark and contact point at each exported size, and run motion/native checks again. A large bounding box alone does not prove an arrowhead is readable.

The generated preview embeds its manifest, so it can be opened locally with its `frames/` folder retained. A local HTTP server is convenient for testing but is not required to install the native cursor files.

## Pixel themes and animation cadence

Theme-wide defaults, overridable per state:

```json
{
  "pixel_art": true,
  "native_pixel_size": 48,
  "pixel_alpha_threshold": 128,
  "pixel_palette_colors": 16,
  "states": []
}
```

The compiler first aligns source landmarks, converts to the canonical pixel grid using nearest-neighbour, snaps alpha to0/255 and optionally maps all frames of one state to a shared palette without dithering. Exports and previews retain hard edges. `pixel_art` defaults tofalse, preserving smooth-art behavior.

For twelve new drawings at20fps action cadence, use a12-step sequence and twelve tick values of3. Increase an individual tick value only for an intentional hold. Manifest fields include `unique_frame_count`, `peak_fps`, `visual_fps`, `cycle_ms` and `animation_stats_by_size`; they are measured from the actual exported pixels and the ANI sequence. Native size48 and its96px integer multiple usually give the most even block sizes.
