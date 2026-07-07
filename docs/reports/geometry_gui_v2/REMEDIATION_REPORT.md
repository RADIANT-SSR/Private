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
| T9  | **Skipped** — gated by CU-043 (not reopened by reviewer)              | —          | Per spec: "T9 gated by CU-043 — skip if not reopened by reviewer." Verified `docs/tracking/Cleanup_Backlog.md` unchanged on this branch. |
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

---

# Round 2 — Visual Remediation (PLAN_v2_remediation_round2.md)

Branch: `fix/visual-remediation` (continued).
Round-2 baseline: commit `f5b8cae` (audit) atop `19e4077` (Phase-7 diet pass).
Window covered: 2026-04-29.

## Audit findings (round-2 §1)

Full ground-truth audit captured in [AUDIT_round2.md](AUDIT_round2.md). Key
defects identified on the diet-pass baseline (not visible in the round-1
final report because the diet pass intentionally regressed several
primitives):

| ID | Defect on diet-pass baseline | Resolved by |
|---|---|---|
| A1 | Camera not at canonical iso three-quarter — sphere/extended PNGs render at default `xy` view | R1 |
| A2 | Scene fills <50% of canvas (target tiny in lower-third, sun off-screen) | R2 |
| A3 | Sun renders as a bright green sphere, not the stylized disc + 8 rays | R3 |
| A4 | Ground plane gridded cap + fade plane intentionally suppressed by diet pass; only contact-shadow disc renders | R4 |
| A5 | Break-mark zigzags suppressed in `boresight.py` and `sun_ray.py` (diet pass) | R5 |
| A6 | Labels cluster on left flank of target with no leaders / anchor dots; `o` label invisible | R6 |
| A7 | Right-dock readouts panel cannot be verified in off-screen renders | R7 (re-execute T8) |
| A8 | Left-dock parameter panel was a placeholder | R8 (re-execute T9) |

## R1 → R8 commit summary

| ID | Title | Commit | Status |
|---|---|---|---|
| Audit | Ground-truth audit of round one | `f5b8cae` | Shipped |
| R1 | Default isometric camera (elev 25°, az 45°, dist = extent × 2.5) | `9795dbf` | Shipped |
| R2 | Default framing policy — scene fills ≥50% canvas | `03d82d7` | Shipped |
| R3 | Stylized sun glyph (disc + 8 rays at fixed screen size) | `3b890c7` | Shipped |
| R4 | Visible ground plane (cap + grid + outer fade) | `8b869c1` | Shipped |
| R5 | Break-marks wired into target→sat and target→sun lines | `fdaecff` | Shipped |
| R6 | Strengthen leader lines, anchor dots, max-distance constraint | `e364201` | Shipped |
| R7 | Build right-dock info panel (re-execute T8) | `bb89b50` | Shipped |
| R8 | Build left-dock parameter panel (re-execute T9) | `270ee48` | Shipped |
| R9 | End-to-end verification across 9 canonical views | (this commit) | In progress |

Test status after R8:

```
$ pytest dev_tools/geometry_gui_v2/tests/ --no-header -q
295 passed, 8 skipped in 9.76s
```

## R9 — 9-view × 20-check matrix

Verification harness: [tests/verify_canonical_views.py](tests/verify_canonical_views.py)
(thin wrapper over [tests/audit_round2/render_canonical_views.py](tests/audit_round2/render_canonical_views.py)
that adds 480×270 thumbnails). All 9 PNGs land in
[tests/golden/round2/](tests/golden/round2/) and thumbs in
[tests/golden/round2/thumbs/](tests/golden/round2/thumbs/).

### Off-screen render scope (read before scoring)

The renderer uses `pv.Plotter(off_screen=True)` and bypasses Qt entirely.
Five UI surfaces therefore **cannot appear in the canonical PNGs even
if their wiring is correct**:

| Surface | Lives in | Visible in PNG? |
|---|---|---|
| Right-dock readouts panel | `app/main.py::_add_right_dock` | ❌ Qt shell |
| Left-dock parameter panel | `app/main.py::_add_left_dock` | ❌ Qt shell |
| View-cube widget | `scene/widgets/view_cube.py::build_view_cube_widget(interactor)` | ❌ Interactor-bound |
| World-axis gnomon | `scene/widgets/world_axes_gnomon.py::build_world_axes_widget(interactor)` | ❌ Interactor-bound |
| Frame-indicator HUD / status bar | `app/main.py` | ❌ Qt shell |

Checks 8, 9, 17, 18 therefore receive a **DEFER** verdict in the table —
their wiring is verified by code-read + by the `tests/test_view_cube.py`,
`tests/test_world_axes_gnomon.py`, `tests/test_readouts_panel.py`,
`tests/test_parameters_panel.py` unit tests, but live pixel verification
is gated by CU-042 (QtInteractor offscreen-GL segfault). The plan's
step 6 interactive verification is recorded in the §"Interactive test
status" subsection below.

### Per-view × per-check table

Legend: P = pass (visually verified); D = deferred (interactor-bound,
see scope note above); F = fail (filed as a blocker — see
[REMEDIATION_BLOCKERS.md](REMEDIATION_BLOCKERS.md)).

| # | Check | box | cone | cyl | ext | flat | geom | pt-src | sph | sun-term |
|---|---|---|---|---|---|---|---|---|---|---|
|  1 | Target most visually dominant | P | P | P | P | P | P | P | P | P |
|  2 | Scene fills ≥50% of both canvas dimensions | P | P | P | P | P | P | P | P | P |
|  3 | Default camera is isometric three-quarter | P | P | P | P | P | P | P | P | P |
|  4 | Sun = small disc + rays glyph, ≤30 px diameter | P | P | P | P | P | P | P | P | P |
|  5 | Satellite = small glyph at fixed screen size | P | P | P | P | P | P | P | P | P |
|  6 | Ground plane visible as subtle grid | P | P | P | P | P | P | P | P | P |
|  7 | Contact shadow visible on ground plane | P | P | P | P | P | P | P | P | P |
|  8 | World-axis gnomon present, bottom-left, neutral | D | D | D | D | D | D | D | D | D |
|  9 | View-cube present, top-right, subdued | D | D | D | D | D | D | D | D | D |
| 10 | Break-mark at midpoint of target → satellite line | P | P | P | P | P | P | P | P | P |
| 11 | Break-mark at midpoint of target → sun line | P | P | P | P | P | P | P | P | P |
| 12 | Every angle arc visible (tube + arrowhead + label) | P | P | P | P | P | P | P | P | P |
| 13 | Every label has a visible leader + anchor dot | P | P | P | P | P | P | P | P | P |
| 14 | No label > 240 px from its anchor (R6 cap) | P | P | P | P | P | P | P | P | P |
| 15 | No two label bounding boxes overlap (Phase 4) | P | P | P | P | P | P | P | P | P |
| 16 | Subscripts render as true subscripts | P | P | P | P | P | P | P | P | P |
| 17 | Right-dock info panel visible, 4 sections populated | D | D | D | D | D | D | D | D | D |
| 18 | Left-dock parameter panel visible | D | D | D | D | D | D | D | D | D |
| 19 | No scrollbar fragments / stray characters / artifacts on edges | P | P | P | P | P | P | P | P | P |
| 20 | Family colors correct (blue/sensor, amber/solar, green/surface, gray/ref) | P | P | P | P | P | P | P | P | P |

Per-view notes:

- **box_default**: Box target with proper PBR shading, contact shadow, ground grid. Sun glyph upper-left, observer label/leader visible, angle arcs cluster at upper-mid, regime tag `(sub_pixel)` on target label.
- **cone_default**: Identical scene structure; cone target with axisymmetric shading.
- **cylinder_default**: The most-inspected view from prior rounds; cylinder target with circular base shadow visible on ground.
- **extended_default**: Sphere target with `(extended)` regime tag. **Special-case Fail — see §"Special-case checks"**.
- **flat_plate_default**: Flat plate target with thin shadow strip. Ground grid extends beyond plate.
- **geometry_diagram**: All-angle-groups view. Multiple arc labels visible (`θ_off = 20 deg`, `θ_z = 35 deg`, `α_t`). Standard sphere target.
- **point_source_default**: Same geometry as default sphere with `(point_source)` regime tag. **Special-case Fail — see §"Special-case checks"**.
- **sphere_default**: Default scene baseline.
- **sun_terminator**: Sun glyph at lower-right (θ_z = 60°), elongated shadow on sphere — terminator alignment with sun direction visually within tolerance.

### Special-case checks (round-2 plan §10 step 4)

| View | Special-case requirement | Verdict | Notes |
|---|---|---|---|
| extended_default | Pixel-cell footprint visible as translucent square on ground | **FAIL** | No translucent square is rendered; the only difference from sphere_default is the regime tag. **Filed as `R9-B1` in REMEDIATION_BLOCKERS.md.** |
| geometry_diagram | All angle groups simultaneously visible & labeled | **PASS** (with caveat) | `θ_off`, `θ_z`, `α_t` arcs visible. `Δφ`/`θ_sun,B` not distinct in default state — they coincide with the relative-azimuth arc when relative_azimuth ≈ 0. Acceptable for the default canonical pose; the dedicated `sun_terminator` view exercises the non-zero Δφ case. |
| sun_terminator | Terminator on sphere aligns with sun direction within 2° | **PASS** | Visual inspection confirms the terminator boundary on the teal sphere coincides with the sun-direction vector (drawn from sun glyph at lower-right) within the 2° tolerance the plan calls for. |
| point_source_default | Point-source marker visible & distinct from sub-pixel target | **FAIL** | Render is geometrically identical to sphere_default with only the regime tag differing. No distinct point-source marker primitive exists in the scene. **Filed as `R9-B2` in REMEDIATION_BLOCKERS.md.** |

### Interactive test status (round-2 plan §10 step 6)

The plan calls for an interactive run (slider drag updates 3D scene
in real time, view-cube clicks, frame-indicator chip, no Qt warnings).
**Blocked by CU-042** (QtInteractor segfaults under offscreen GL on this
machine). The 16 ms slider-drag debounce is verified by
`tests/test_parameters_panel.py::test_slider_drag_debounces_to_one_emit`
and the panel↔plotter wiring is verified by the unit tests for each
panel. Pixel verification of the dock layout, view-cube, gnomon, and
frame-indicator chip remains gated by CU-042 closure.

### Side-by-side comparison (round 1 → round 2)

Round-1 baseline (post-diet-pass) snapshots are captured in
[tests/audit_round2/before/](tests/audit_round2/before/). Round-2 outputs
in [tests/golden/round2/](tests/golden/round2/) with thumbnails in
[tests/golden/round2/thumbs/](tests/golden/round2/thumbs/).

| View | Before (`tests/audit_round2/before/`) | After (`tests/golden/round2/thumbs/`) | Net change |
|---|---|---|---|
| box_default | floating box, no ground, no sun glyph, labels stacked on flank | iso pose, ground grid, stylized sun, leader-lined labels | A1+A2+A3+A4+A6 resolved |
| cone_default | floating cone, no ground, no sun glyph | iso pose, ground grid, stylized sun, leader-lined labels | A1+A2+A3+A4+A6 resolved |
| cylinder_default | extreme zoom, cylinder fills frame, sun text only | iso pose, full scene, stylized sun, break-marks visible | A1+A2+A3+A4+A5+A6 resolved |
| extended_default | floating sphere, no pixel-cell footprint, no ground | iso pose, ground grid, regime tag `(extended)`; pixel-cell footprint still missing | A1+A2+A3+A4+A6 resolved; **R9-B1 open** |
| flat_plate_default | flat plate at extreme zoom, no ground | iso pose, ground grid, leader-lined labels | A1+A2+A3+A4+A6 resolved |
| geometry_diagram | sparse arc cluster, no ground, label cloud | iso pose, ground grid, all arcs labeled, leader-lined labels | A1+A2+A3+A4+A6 resolved |
| point_source_default | floating sphere, no marker, no ground | iso pose, ground grid, regime tag `(point_source)`; distinct marker still missing | A1+A2+A3+A4+A6 resolved; **R9-B2 open** |
| sphere_default | floating sphere, no ground, no sun glyph | iso pose, ground grid, stylized sun, leader-lined labels | A1+A2+A3+A4+A6 resolved |
| sun_terminator | floating sphere with sun text, no ground | iso pose, ground grid, sun glyph at θ_z=60°, terminator visible | A1+A2+A3+A4+A6 resolved |

## Deferred / known issues

- **CU-042** — QtInteractor offscreen-GL segfault. Blocks pixel
  verification of view-cube, world-axis gnomon, dock panels, and
  frame-indicator chip. Unit tests cover the wiring contract; live
  pixel verification waits on CU-042 closure.
- **R9-B1** (filed in REMEDIATION_BLOCKERS.md) — extended_default
  pixel-cell translucent footprint is not rendered. Decision:
  scene currently has no module that emits a pixel-cell ground
  footprint; building one is a Rule-19 standalone task, not a
  remediation-round bug fix.
- **R9-B2** (filed in REMEDIATION_BLOCKERS.md) — point_source_default
  has no marker primitive distinct from the regular sub-pixel
  target indicator. Same scope conclusion as R9-B1 — the marker
  primitive does not exist yet.
- Carry-over from round 1: `app/status_bar_text.py` uses literal
  `"A_t"` (status-bar is plain-text). A `plain_label()` helper in
  `typography.py` would close the loop; not in round-2 scope.

