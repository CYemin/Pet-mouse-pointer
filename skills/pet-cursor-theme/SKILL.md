---
name: pet-cursor-theme
description: Create personalized Windows CUR/ANI mouse cursor themes from a user's pet photos, with expressive pet-specific poses, deliberate click hotspots, previews, native validation and reversible installation packages.
---

# Pet cursor theme

Create a usable Windows mouse scheme that looks like the user's own pet. Default to the complete 17-role scheme unless the user asks for samples or a smaller set. A theme is finished when the files, hotspots, role mapping, preview, installation and restoration instructions are present and verified to the extent the environment permits.

## Establish the character and pointing geometry

Inspect the supplied photo; identify a few distinguishing features (markings, ear folds, muzzle shape). Use the available image generation tool for the artwork, preserving transparency. A pet photo is identity reference, not necessarily the final rendering style. Generate the style the user actually requests rather than defaulting to detailed fur portraits.

For a new visual direction, a small static sample or the normal/link pair is usually enough to settle it. Reuse already approved artwork and preferences. Do not repeatedly request confirmation after the user has approved a direction.

When the user chooses pixel art, redraw a simple small-grid character rather than applying a mosaic filter to a detailed portrait. Compile with `pixel_art: true`, `native_pixel_size: 48`, `pixel_alpha_threshold: 128` and optionally `pixel_palette_colors: 16`. This uses nearest-neighbour resizing and one undithered palette across each state's frames; preserve pixel edges in the browser too. A48px native design scales most evenly to96px.

Design for actual cursor size. At48px, keep the main head roughly30–36px wide, use a clear black open-eye cluster with a white glint and a distinct eyebrow, and simplify fur into broad colour clusters. Oversized operation symbols shrink the pet until its eyes become indistinct. Prefer compact marks, then inspect the compiled48px pixels on both backgrounds; a detailed source preview alone does not prove readability.

For nose-first pointers, show a largely side-on head with the nose protruding toward the upper left. The foremost visible nose edge must coincide with the actual click hotspot. Ears and ruff trail behind; a front-facing avatar with an invisible hotspot makes users guess where a click lands. If the animal's anatomy needs another design, choose an equally obvious contact point with the user.

## Design distinct actions

Keep the identity and style consistent, but let each function change the animal's expression or pose. Examples: puzzled head tilt for Help; chin resting on paws for Wait; concentrated squint for Crosshair; looking away and a raised paw for No; pulling a rope for resizing. Do not simply paste every status symbol onto the same neutral face.

Retain clear operation marks for text, precision, resizing and move. Their hotspot is the insertion-line center, crosshair center or arrow intersection. Handwriting uses the pencil tip. Dynamic point-select frames keep the same nose contact point while eyes/ears/cheeks move. Animation should leave the contact point stationary.

When the user requests animated operation states, keep the operation geometry fixed while animating the pet's eyes, ears, fur or paws. All17roles can use ANI. Measure each frame's marker or nose from the actual source rectangle, because generated sheets can have uneven spacing. Preserve already approved states when revising the rest. Rebuilding a static role as animated must remove its superseded CUR files from the deliverable.

The Windows role list and configurable source format are in [references/configuration.md](references/configuration.md). Use one image generation call per distinct state asset; a state's animation can be a sprite sheet with a known grid. Save prompts and generated assets in the working project. Do not include a user's original photos in a public repository by default.

If animation feels choppy, increase meaningful intermediate drawings as well as playback cadence. Twelve distinct frames with3-tick ANI transitions give20fps action segments, while intentional resting holds remain longer. Report real unique-frame counts and distinguish active transition peaks from whole-loop average visual FPS; duplicating a few pictures does not create smoother animation. Inspect native-size motion for jitter and keep the nose anchored across every frame.

## Compile and verify

1. Save a config with reviewed per-frame landmarks. Landmarks refer to the source cell before compiler alignment; do not assume the generator obeyed requested coordinates.
2. Run `python PATH_TO_SKILL/scripts/build_complete_theme.py --config CONFIG --output OUTPUT --root PROJECT_ROOT`. It compiles five sizes, per-role CUR or ANI files, a 17-state overview, an interactive preview, reversible installation scripts and three double-click CMD launchers (48px, 96px, restore). `PROJECT_ROOT` resolves the config's relative source image paths. Templates and installation helpers are loaded from the skill's own scripts directory, so an independent project does not need to copy them.
3. Inspect the overview at real cursor sizes on light and dark backgrounds. Correct missing directions, indistinguishable states, clipped artwork and vague click points. Adjust incorrect source landmarks and rebuild; do not shift the actual clicking point arbitrarily to accommodate a bad picture.
4. After every build or revision, inspect **every displayed animation transition, including last-to-first**, for severe jitter or offsets before packaging. Run `python scripts/verify_cursor_motion.py OUTPUT` to produce review candidates and overlays, then visually review all states at their real native size and an integer enlargement, at normal and slowed playback. Check the visible nose/operation mark and stable head, eye-socket and chest features; an opaque fixed hotspot alone does not establish stable artwork. Distinguish intended blinking, fur/ear movement, question-mark scaling and sleep poses from accidental translation, scale jumps or one-frame pops. Correct bad registration at the source landmarks; redraw incoherent artwork when needed. Rebuild and repeat the affected motion checks plus native validation. Record actual reviewed states, transitions and unresolved limitations in `motion-review/visual-review.json`; never present the automatic heuristic report alone as a passed visual review. See [motion review](references/motion-review.md).
5. On Windows run `python scripts/verify_complete_theme.py OUTPUT`. This checks every embedded frame and role's hotspot plus native loading/drawing. It does not apply the scheme. Off Windows, state that native validation remains pending; do not claim it passed.
6. Parse the generated PowerShell scripts and run installation with `-WhatIf`; the CMD launchers accept `--check` for this dry-run mode without pausing. Test Chinese paths, spaces and exit codes. Applying a theme is a separate user-requested action. The installer backs up changed cursor values before writing them; restoration retains backups and installed files. Repeated Apply should keep the pre-theme restore baseline while this theme remains active, so the Restore launcher returns to the original scheme.

Use fixed-size ANI files as the compatible baseline. Multi-size CUR frames within ANI were rejected by the native loader in this project's tested configuration, even though static multi-size CURs loaded. Do not promise cross-DPI behavior from container structure alone.

## Deliver

Provide the complete theme ZIP, a readable preview, installation/recovery instructions, source prompts and the validation report. Distinguish structural/native checks from actual desktop installation, click feel and multi-monitor testing. Be explicit about any visible animation texture drift or untested compatibility. Do not publish, push to a remote repository, or change system cursors merely because a local package is ready.

Dependencies: Python 3.10+, Pillow12.3+; Windows is required for native validation and applying the scheme. Image generation depends on the host's available tool and any associated service conditions; this skill does not bundle a model or API credentials.
