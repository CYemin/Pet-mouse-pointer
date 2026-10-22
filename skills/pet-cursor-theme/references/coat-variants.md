# Extend an approved theme into other coat colors

Use this workflow when the user wants the same pet character and actions in another coat. A different breed, face shape, ear structure or muzzle normally needs new character art.

## Color catalog

The repository's `themes/` and download table identify which variants are complete. The color comparison is a static design overview; a static sample alone does not establish that an installable theme exists. The current ten-color catalog has ten complete animated packages.

| Breed | Coat choices | Distinguishing markings |
|---|---|---|
| Sheltie | sable, dark sable | Golden-to-mahogany sable, white blaze/muzzle/ruff; dark sable has darker tipping |
| Sheltie | bi-black | Black/white, no tan eyebrows or cheeks |
| Sheltie | tricolor | Black/white plus tan eyebrows and cheeks |
| Sheltie | blue merle | Silver-grey/black patches, white regions, tan eyebrows and cheeks |
| Sheltie | bi-blue | Silver-grey/black patches and white, no tan points |
| Golden retriever | cream, light golden, golden, dark golden | Continuous golden shading with lighter feathering; retain the photographed nose and accessory colors |

These are character-design choices. Do not infer a photographed dog's pedigree or genetics from color alone. See [ASSA's Sheltie colors](https://www.americanshetlandsheepdogassociation.org/sheltie-colors/) and [GRCA's breed study guide](https://grca.org/wp-content/uploads/2017/09/GRCA-Study-Guide-2017pdf.pdf) when checking breed references.

## Artwork and consistency

1. Keep the approved theme, source sheets and configuration intact. Create a sibling directory for the new variant.
2. Inspect its character master and a real48px sample. Confirm face/eye/nose contrast on both light and dark backgrounds. Reuse already approved color choices.
3. For each state, inspect the old sheet and edit it with the image-generation tool. Label the old sheet as the edit target and the master as the color reference only. Preserve all frame poses, order, layout, contact points and operation symbols. A sleeping state must keep its sleeping poses even if the color master has an open mouth.
4. Protect non-fur regions: eyes/highlights, nose, mouth, tongue, paw pads, harness/buckle, pencil, arrows, question marks and ZZZ. Global hue or brightness shifts can contaminate these features.
5. Keep a merle pattern attached to landmarks such as ear base, rear crown and mane. The black patches must not randomly appear, vanish or migrate between adjacent frames or at loop closure. Allow the fur and ears to move as designed.
6. Save every prompt and generated sheet. Re-measure new geometry; asking for fixed coordinates does not prove the model kept them.

## Optional registration helper

`register_coat_variant.py` maps old, reviewed source landmarks into edited sheets by alpha-shape registration. It uses a shared scale per state and a translation per frame. This avoids introducing per-frame resizing from changing fur bounds. It preserves the base sequence/ticks and maps `source_frames` into the new full sheet without selecting the old rectangles twice.

Edited files use state IDs as filenames, e.g. `normal.png`, `help.png`, `size-we.png`. Keep the same grid/frame ordering as the base theme.

```powershell
python skills/pet-cursor-theme/scripts/register_coat_variant.py --root projects/my-pet --base-config projects/my-pet/base-theme.json --assets-dir projects/my-pet/assets/blue-merle --name "Blue Merle" --palette 32
```

The helper emits a complete `theme-config.json` when all states are present; otherwise it emits a partial configuration for inspection. It also records registration measurements and a calibration board. Low overlap, clipping, different silhouettes, moving symbols or regenerated poses need manual review or targeted image repair. High overlap is not proof of correct click geometry or stable color patches.

Build the complete configuration with `build_complete_theme.py`, then run `verify_pixel_quality.py`, `verify_cursor_motion.py` and Windows `verify_complete_theme.py`. Inspect every displayed transition at48/96px, normal speed and slowed playback, on both backgrounds, including the return to frame0. Record visual review against the final asset revision.

Palette size is configurable. Use enough colors to preserve clear eyes, pink tongue/nose and small accessories after reduction;32–48 colors may work better for a retriever with a colored harness than a strict16-color budget. A shared palette per state prevents quantizer changes between its frames; it does not itself guarantee consistent markings across states.

## Delivery

Mark design-only colors separately from complete17-state packages. Include real-timing previews, installation/restoration launchers, final configuration/prompts and revision-bound verification. Publishing or applying remains governed by the user's authorization for that task.
