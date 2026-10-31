# Catalog releases and platform packages

Use one catalog for gallery order, color names, download lists, collection selectors and validation counts. Include only current reviewed themes; exclude superseded artwork. Do not silently replace newer installed helpers with older compiler templates.

## This repository's gallery convention

For Pet-mouse-pointer, show eight breeds at the beginning of README, in this order: 喜乐蒂 / 金毛 / 比熊 / 泰迪 / 柯基 / 瑞牧 / 二哈 / 西高地. Use one representative color each. Follow with all coat colors, one breed per row, then animated examples covering every breed and color. This is a project-specific convention; preserve a different user's requested ordering elsewhere. Derive pictures from the actual exported frames, preserve nearest-neighbor scaling and original timing, and verify every local image/download target.

## Windows

Package each theme and collections containing all themes or one breed. A batch launcher must preflight every target and expose `--check` / `-WhatIf` without changing settings. Register each style as a saved scheme; only one can be active. Describe which theme is active after the batch (the last installed). Stop on the first failure and report partial progress. Preserve the original restore baseline across consecutive project themes. Keep a restore launcher in the collection and single-theme package. Test Chinese/spaced paths, both invalid and valid selection, missing assets, PowerShell parsing and dry runs. Native artwork checks do not constitute desktop application testing.

Current packaged launchers default to 32px and open the Windows Pointers page. Advanced installation supports 32/48/64/96/128px. Follow the actual shipped helper behavior when writing instructions.

## macOS

Use `scripts/build_macos_theme.py` with built Windows theme directories that include `frames/` and manifests, then `scripts/verify_macos_theme.py`. Read [macOS format and testing limits](macOS.md). The exporter provides 32pt/48pt capes with 1x/2x strips, maps 13 source actions to 17 Mac entries and records omitted Windows roles. Mousecape accepts at most 24 equally timed frames; record exact timing expansion versus sampling. Test every embedded pixel, frame order, alpha, hotspot and loop duration against the reviewed source.

Offer whole-catalog and per-breed Mac archives. A double-click `.command` may batch-open capes in an already installed Mousecape; clearly call this **import**, and instruct the user to select a cape and Apply. Do not claim it installs Mousecape or applies multiple themes simultaneously. Verify command syntax and preserve the executable ZIP mode. Do not bypass Gatekeeper or modify login helpers. When working on Windows, mark Mac import/application and Retina/multi-monitor behavior as pending real-device testing.

## Publication

Keep release files below the remote host's size limit, validate ZIP CRC and SHA-256, and strip private local paths and photos. Publish only when requested. Update skill sources and downloadable skill archive together. Verify the pushed commit and the public README after upload; do not claim a local commit was published.
