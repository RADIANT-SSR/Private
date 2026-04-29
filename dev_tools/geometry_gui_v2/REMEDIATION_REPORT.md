# Visual Remediation Report

Branch: `fix/visual-remediation` (off `main`, baseline `a2fb700`)
Window covered: 2026-04-27 first-cut screenshot → 2026-04-28 T10 landing.

## Task tracker

| ID  | Task                                                                  | Commit     | Notes |
|-----|-----------------------------------------------------------------------|------------|-------|
| —   | Phase 0–7 baseline lift (PLAN_v2.md)                                  | `a2fb700`  | One-shot lift of the previously untracked v2 tree. Resolved BLOCKER B0 (see `REMEDIATION_BLOCKERS.md`). |
| T1  | Typography helpers + canonical glossary                               | `063683d`  | `scene/labels/typography.py` + `glossary.yaml`. Three-form entries (`latex` / `html` / `description`). LRU-cached YAML load. |
| T2  | Subdued in-viewport view cube (replaces orange axis triad)            | `f7b561e`  | `vtkAnnotatedCubeActor` + `vtkOrientationMarkerWidget`. C7-clean (`scene/widgets/view_cube.py` imports `vtk` only). |
| T3  | Ground plane + subtle grid + outer fade                               | `3e546bb`  | New `scene/ground/fade.py`; procedural 1 m / 5 m grid texture; `GROUND_CAP_RADIUS_M` 4 → 10. Phase-1 goldens relocked. |
| T4  | World-axis gnomon → bottom-left corner widget                         | `aa4b11c`  | New `scene/widgets/world_axes_gnomon.py`. Deleted `scene/frames/world_axes.py`. Removed dead constants `WORLD_AXES_COLOR`, `WORLD_AXES_LENGTH_FRACTION`. |
| T5  | Force-directed label deconfliction solver tuning                      | `2e6296f`  | Per-anchor radial offset replaces centroid-ring init; `INITIAL_OFFSET_PX` 60 → 90; `LABEL_REPULSION_K` 4000 → 2500; `ANCHOR_ATTRACTION_K` 0.02 → 0.05. New layout-stability test. |
| T6  | Angle arcs widened so they read at default zoom                       | `be965af`  | Arc tube + tip-cone constants moved to `scene/style.py`; `ARC_TUBE_RADIUS_M = 0.025`, `ARC_TIP_HEIGHT_M = 0.18`, `ARC_TIP_RADIUS_M = 0.09`; `ARC_RADIUS_M` 2.0 → 2.6. |
| T7  | "Not to scale" break-marks sharpened                                  | `363a91c`  | Smoothed 4-point spline → sharp Z polyline (3 line tubes via `pv.MultiBlock`). Wider amplitude so the kink reads at canonical camera distance. |
| T8  | Right-dock structured info panel + scrollbar artifact fix             | `06f30cf`  | `QScrollArea` `NoFrame` + scrollbar-policy override. Dock width 320 → 340 px. |
| T9  | **Skipped** — gated by CU-043 (not reopened by reviewer)              | —          | Per spec: "T9 gated by CU-043 — skip if not reopened by reviewer." Verified `docs/Cleanup_Backlog.md` unchanged on this branch. |
| T10 | Project-wide subscript typography sweep                               | `61aeb77`  | Every viewport label routes through `viewport_label()`; `Projected area` panel row routes through `panel_label()`. `LeaderLabel.estimated_screen_size_px` made math-text-aware so the new `$\theta_{off}$` strings don't blow up the deconfliction box. New `tests/test_typography_sweep.py` pins the sweep. Phase-1 goldens relocked. |

## Recovery note (2026-04-28)

A parallel agent on `chore/cu-047-update-golden-noise-keys` left the
T10 work-in-progress in three stashes on `fix/visual-remediation`
labelled `CU-047 sequence: …`. The recovery sequence:

1. Snapshotted stash contents into `/tmp/stash{0,1,2}.diff`.
2. `git switch fix/visual-remediation` (worktree CU-047 edits to
   `scripts/update_golden.py` and `src/radiant/core/radiometry.py`
   travelled across, deliberately left out of T10's commit).
3. Applied `stash@{1}` cleanly (panel + 6 relocked goldens).
4. Extracted only the `_anchors.py` portion of `stash@{2}` via
   `git checkout stash@{2} -- dev_tools/geometry_gui_v2/scene/labels/_anchors.py`,
   leaving the CU-047 edits in the stash for that branch's own work.
5. Discovered the math-text width bug in `estimated_screen_size_px`
   when phase-4 overlap tests failed → added `_rendered_char_count`.
6. Relocked goldens, ran full v2 suite (254 passed, 8 skipped).

Stashes `stash@{0}`, `stash@{1}`, `stash@{2}` remain in place — drop
them only after verifying the CU-047 worktree edits are committed
on the `chore/cu-047-update-golden-noise-keys` branch.

## Test results (post T10, full v2 suite)

```
$ pytest dev_tools/geometry_gui_v2/tests/ --no-header -q
254 passed, 8 skipped in 7.83s
```

The 8 skips are the C1-protected QtInteractor-segfault paths (CU-042) —
expected to remain skipped until that CU is closed.

## Constraints honoured

- **C1** (no `/src` edits): T10 staging deliberately excluded the
  `src/radiant/core/radiometry.py` modification that was sitting in
  the working tree (it belongs to CU-047).
- **C7** (no Qt imports under `scene/`): every primitive added during
  T2/T3/T4 imports `vtk` only. Verified by the existing
  `tests/test_scene_imports_without_qt.py`.
- **Rule 19** (one primitive per file): each new primitive has its own
  module — `scene/ground/fade.py`, `scene/widgets/world_axes_gnomon.py`,
  `scene/widgets/view_cube.py`. Bundling exception applies only to the
  `scene/labels/_anchors.py` registry per the file's docstring carve-out.
- **Rule 21/22** (CU discipline): no new CU was opened or closed during
  the remediation; CU-042 and CU-043 deferral status preserved.

## Known follow-ups (file as CUs if not already)

- `app/status_bar_text.py` keeps the literal `"A_t"` because
  `QStatusBar.showMessage` is plain-text. If we want a single
  source of truth across all three rendering channels (VTK math-text /
  Qt HTML / status-bar plain text), add a `plain_label()` helper to
  `typography.py` with a Unicode-subscript form.
- `LeaderLabel._rendered_char_count` collapses any `\command` to one
  glyph. Sufficient for the current glossary (`\theta`, `\alpha`,
  `\Delta`, `\varphi`); revisit if multi-character math-text commands
  enter the glossary.

## Screenshot

To regenerate the post-remediation reference screenshot:

```
python -m dev_tools.geometry_gui_v2.app.main --screenshot \
    /tmp/visual_remediation_post_t10.png
```

(Skipped in this report because QtInteractor cannot run headless
under CU-042; the engineer must capture interactively.)
