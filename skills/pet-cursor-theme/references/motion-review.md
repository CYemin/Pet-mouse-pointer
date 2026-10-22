# Review animation stability

Run this review after each finished theme and after artwork, crop, landmark or timing changes. Do not infer motion quality from FPS, different-frame counts or native cursor loading.

`python scripts/verify_cursor_motion.py OUTPUT` reads the exported manifest and frames. It compares adjacent displayed frames, including the wrap from the final displayed frame back to the first, and writes `OUTPUT/motion-review/automatic-report.json` plus visual evidence. Treat estimated translations and scale changes as candidates for inspection, not as proof of a defect or of stability: blinking, moving paws, floating letters and fur all change image measurements.

The helper also exports every displayed frame on light/dark sequence sheets, including the loop return, and normal-speed and quarter-speed GIFs for every state at48px and96px. Use those artifacts to review unflagged frames as well as candidates.

Visually inspect every state's full sequence at native size (48px for the pixel theme) and at an integer enlargement such as96px. Watch normal playback and slowed playback on both light and dark backgrounds. In flagged or uncertain transitions, compare the two frames side by side and in an overlay. Also inspect loop closure; it can jump even when all intermediate frames look smooth.

The visible click feature must stay fixed: foremost nose edge, pencil tip, arrow intersection, insertion-line center or crosshair center. Separately follow stable body features such as the eye socket, muzzle contour and harness buckle. A head that shifts several native pixels around an unchanged hotspot is still jitter. A whole head suddenly changing size or a single bad pose appearing for one frame also fails. Deliberate tilts, breathing, eyelid motion, ear movement and wind-blown fur should read as continuous purposeful motion, not a sudden placement change.

For a defect, identify state and displayed frame transition before editing. Check the source crop and measured landmark first. Fix incorrect registration without moving the intended contact point. If alignment is correct but the generated anatomy or scale is inconsistent, use image generation to repair the affected artwork rather than claiming the jitter is intentional. Re-export, review every affected transition and its neighbors, including wrap, and rerun native validation. A change to a shared compiler or registration rule requires review of all states it changes.

Write `OUTPUT/motion-review/visual-review.json` with the reviewed asset revision, sizes, backgrounds, frame/transition coverage, candidate decisions, remaining issues and final status. Only record `passed` after visual review finds no severe unintended jumps. Keep mild texture drift distinct from severe positional jitter and disclose any residual visible limitation. Include the report with the package. If any state remains unreviewed, record that gap instead of claiming the full theme passed.
