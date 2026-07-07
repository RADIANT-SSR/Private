# Round-2 Pre-Flight Audit — Ground Truth on the Diet-Pass Baseline

**Branch:** `fix/visual-remediation`
**Audit baseline:** commit `19e4077` (Phase-7 diet pass) on top of `080dac7` (ground-fade exclusion fix).
**Audit date:** 2026-04-28.
**Renderer used:** [tests/audit_round2/render_canonical_views.py](tests/audit_round2/render_canonical_views.py) — off-screen `pv.Plotter`, 1920×1080, canonical iso pose from [scene/camera_views.py](scene/camera_views.py).
**Output:** [tests/audit_round2/before/](tests/audit_round2/before/) — one PNG per canonical view.

This audit is the §1 deliverable from `PLAN_v2_remediation_round2.md`. It exists so the round-2 R-tasks can be prioritised against what the diet-pass baseline actually renders, not against the prior round's REMEDIATION_REPORT (which described state that the diet pass has since superseded).

---

## 1. Test-suite status

```
$ pytest dev_tools/geometry_gui_v2/tests/ --no-header -q
253 passed, 8 skipped in 5.30s
```

The 8 skips are the C1-protected QtInteractor-segfault paths (CU-042) — expected. No new failures or errors. Test pass alone is not evidence of correct rendering — that is precisely why this audit reads pixels, not log output.

---

## 2. Off-screen rendering scope (read this before scoring)

The audit screenshots are generated through `pv.Plotter(off_screen=True)`. That bypasses Qt entirely. Three classes of UI surface therefore **cannot show up in these PNGs even if their wiring is correct**:

| Surface | Lives in | Visible in audit PNGs? |
|---|---|---|
| Right-dock readouts panel | `app/main.py::_add_right_dock` | ❌ (Qt shell) |
| Left-dock parameter panel | `app/main.py::_add_left_dock` | ❌ (Qt shell, currently a placeholder) |
| View-cube widget | `app/main.py::_enable_view_cube` (uses pyvistaqt interactor) | ❌ (interactor-bound) |
| World-axis gnomon | `app/main.py::_enable_world_axes_gnomon` | ❌ (interactor-bound) |
| Frame-indicator HUD / status bar / menu bar | `app/main.py` | ❌ (Qt shell) |

Their presence/absence has been audited via grep and code reading instead. R7/R8 acceptance from the plan still requires interactive renders, which this round-2 audit defers to R9's interactive step.

---

## 3. Per-task audit findings (T1 → T10 from round one)

### T1 — Typography helpers + canonical glossary
**Status:** Shipped.
**Evidence:** [scene/labels/typography.py](scene/labels/typography.py), [scene/labels/glossary.yaml](scene/labels/glossary.yaml), [tests/test_typography.py](tests/test_typography.py) — all present. `tests/test_typography_sweep.py` enforces project-wide use (T10). 253 passing tests include both.
**Defect:** None at the typography layer. The visible "α_t", "θ_s = 35 deg", etc. in the PNGs *are* using `panel_label` / `viewport_label` — the rendering issue (small underscores still readable as `_off`) is a font-size + math-text-rendering question, not a routing one.

### T2 — Subdued in-viewport view cube
**Status:** Shipped.
**Evidence:** [scene/widgets/view_cube.py](scene/widgets/view_cube.py) builds a `vtkAnnotatedCubeActor` + `vtkOrientationMarkerWidget`; consumed by `app/main.py:381` via `build_view_cube_widget(interactor)`. Subdued palette in `style.py` (`VIEW_CUBE_FACE_COLOR = #3a3d45`).
**Defect:** Cannot verify in audit PNGs (interactor-bound — see §2). Will be verified at R9's interactive step.

### T3 — Ground plane + grid + outer fade
**Status:** Regressed (intentionally, by the diet pass).
**Evidence:** [scene/ground/__init__.py](scene/ground/__init__.py) docstring lines 23–32: *"Phase-7 diet: only the contact-shadow disc renders by default. The gridded `cap` and the `fade` plane are intentionally not invoked here."* `cap.py` and `fade.py` modules still on disk but uncalled.
**Defect:** Visible in every audit PNG — the target floats in dark space with only a faint elliptical contact shadow. **R4 must reverse the diet decision** (or document a different fallback that still yields a visibly grounded scene). The diet's "engineering plot" objection is real but the round-2 plan §5 is explicit: ground plane must be visible.

### T4 — World-axis gnomon → bottom-left corner widget
**Status:** Shipped.
**Evidence:** [scene/widgets/world_axes_gnomon.py](scene/widgets/world_axes_gnomon.py) exists; `app/main.py:152` calls `self._enable_world_axes_gnomon()`. Constants in `style.py` (`WORLD_AXES_GNOMON_VIEWPORT = (0.01, 0.01, 0.14, 0.22)`).
**Defect:** Cannot verify in audit PNGs (interactor-bound). Verify at R9.

### T5 — Force-directed label deconfliction solver tuning
**Status:** Shipped (mostly).
**Evidence:** [scene/labels/layout.py](scene/labels/layout.py) and [tests/test_scene_phase4.py](tests/test_scene_phase4.py) present. T10 docstring updates `INITIAL_OFFSET_PX → 90`.
**Defect:** In every audit PNG, multiple labels (`Target A_t = ...`, `θ_off = 20 deg`, `θ_s = 35 deg`, `o`, `α_t`, `Observer`) cluster in a narrow horizontal band on the **left side of the target**, with no clear association to which 3D anchor they describe. The boresight-origin `o` label is essentially invisible (single character, no leader). The solver may be working as specified, but the *output* still reads as a label cloud rather than annotation. **R6 (leaders + anchor dots + 240 px max distance) is the correct fix.**

### T6 — Angle arcs widened so they read at default zoom
**Status:** Shipped.
**Evidence:** [scene/arcs/](scene/arcs/) has one file per arc; constants in `style.py` (`ARC_TUBE_RADIUS_M = 0.022`, `ARC_TIP_HEIGHT_M = 0.16`, `ARC_RADIUS_M = 3.4` from `_layout.py`). Visible in every audit PNG as the curved blue/amber arcs at the top.
**Defect:** None at the arcs layer. The arcs read clearly. The off-nadir / α_t / θ_sun arc cluster floats at the top of the canvas because the canonical iso pose places the arc apex near the top of the screen — that is a camera/framing problem (R1, R2), not an arc problem.

### T7 — "Not to scale" break-marks
**Status:** Regressed (intentionally, by the diet pass).
**Evidence:** [scene/vectors/_tube.py](scene/vectors/_tube.py) still defines `_add_break_mark` and accepts `with_break_mark=True`. But [scene/vectors/boresight.py:25](scene/vectors/boresight.py#L25) and [scene/vectors/sun_ray.py:23](scene/vectors/sun_ray.py#L23) explicitly disable it: *"Phase-7 diet: drop the break-mark zigzag."* No callers pass `with_break_mark=True` anywhere in the tree.
**Defect:** No break-marks visible in any of the 9 audit PNGs. **R5 must re-wire `with_break_mark=True` in the boresight / sun_ray paths.** The plumbing exists; only the call sites are turned off.

### T8 — Right-dock structured info panel + scrollbar fix
**Status:** Shipped.
**Evidence:** [app/panels/readouts.py](app/panels/readouts.py) defines `ReadoutsPanel`; `app/main.py:183-207` `_add_right_dock` creates a `QDockWidget`, wraps the panel in a `QScrollArea` with `NoFrame` + always-off horizontal scrollbar, sets minimum width 340 px, adds to `Qt.RightDockWidgetArea`.
**Defect:** Cannot verify in audit PNGs (Qt-shell only). The panel exists and is wired. **R7 should reduce to: re-confirm interactively at R9 that the panel renders with 4 sections populated, all subscripts correct, eye-icons functional.** No new code expected unless interactive run finds a defect.

### T9 — Left-dock parameter panel
**Status:** Missing (gated by CU-043).
**Evidence:** `app/main.py:169-181` `_add_left_dock` adds a `QDockWidget` with a `QLabel` placeholder text *"(Sliders deferred — see CU-043 in docs/tracking/Cleanup_Backlog.md.)"*. The panel itself does not exist. The previous report (REMEDIATION_REPORT.md row T9) confirms: *"T9 gated by CU-043 — skip if not reopened by reviewer."*
**Defect:** **R8 (the round-2 plan) explicitly re-opens this work.** The plan §9 spec says: width 200 px, collapsible Observer/Target/Sun/Sensor/Mode sections, label + slider + spinbox + units per row, debounced `state_changed` signal. CU-043 needs to be re-audited for closure or a new gating reason. Risk: real implementation work, not just wiring.

### T10 — Project-wide subscript typography sweep
**Status:** Shipped.
**Evidence:** [tests/test_typography_sweep.py](tests/test_typography_sweep.py) pins it; commit `61aeb77`.
**Defect:** None at the routing layer. The audit PNGs do show what *looks* like literal underscore characters in `θ_off`, `α_t`, `(sub_pixel)`, `(point_source)`, `(extended)`, but two distinct cases hide here:
  - The angle labels (`$\theta_{off}$` etc.) are math-text — a real subscript glyph, just very small at this resolution. Not a defect.
  - The regime tags `(sub_pixel)`, `(point_source)`, `(extended)` are passed through verbatim from `RegimeOverride` enum values — they are literally the string `sub_pixel`, not math-text. **Latent issue (file as CU during R7/R8 work):** regime-tag display strings should route through a `regime_display(regime)` helper that returns "sub-pixel", "point source", "extended", "auto". Underscores in user-visible labels violate the spirit of T10 even if they're not "subscript" candidates.

---

## 4. Per-view × per-check matrix (20 × 9 = 180 cells)

Legend:
- `✓` Pass  ·  `✗` Fail  ·  `n/a` Not applicable in this view  ·  `Qt` Lives in the Qt shell — cannot audit from off-screen PNG (see §2)

| # | Check | box | cone | cyl | ext | flat | diag | pt-src | sphr | sun-term |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Target is the most visually dominant element | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2 | Scene fills ≥50% of both canvas dimensions | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 3 | Default camera is isometric three-quarter (no degenerate side view) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 4 | Sun renders as small disc + rays glyph, not a sphere, ≤30 px diameter | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 5 | Satellite renders as small diamond glyph at fixed screen size | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 6 | Ground plane visible as subtle grid extending around target | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 7 | Contact shadow visible on the ground plane (not in empty space) | ~ | ~ | ~ | ~ | ~ | ~ | ~ | ~ | ~ |
| 8 | World-axis gnomon present in bottom-left | Qt | Qt | Qt | Qt | Qt | Qt | Qt | Qt | Qt |
| 9 | View-cube present in top-right | Qt | Qt | Qt | Qt | Qt | Qt | Qt | Qt | Qt |
| 10 | Break-mark zigzag visible at midpoint of target → satellite line | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 11 | Break-mark zigzag visible at midpoint of target → sun line | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 12 | Every angle arc visible (curved tube + arrowhead + midpoint label) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 13 | Every label has a visible leader line ending in an anchor dot | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 14 | No label is more than 240 px from its anchor in screen space | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 15 | No two label bounding boxes overlap (Phase 4 hard test) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 16 | All subscripts render as true subscripts (no literal `_`) | ~ | ~ | ~ | ~ | ~ | ~ | ~ | ~ | ~ |
| 17 | Right-dock info panel visible with all four sections populated | Qt | Qt | Qt | Qt | Qt | Qt | Qt | Qt | Qt |
| 18 | Left-dock parameter panel visible with appropriate slider inventory | Qt-✗ | Qt-✗ | Qt-✗ | Qt-✗ | Qt-✗ | Qt-✗ | Qt-✗ | Qt-✗ | Qt-✗ |
| 19 | No scrollbar fragments, stray characters, or layout artifacts | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 20 | Family colors correct: blue/sensor, amber/solar, green/surface, gray/reference | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Legend for `~` annotations:
- **#7 Contact shadow** is rendered (visible faint elliptical patch under the target), but with the ground cap missing it sits in empty space — partial pass at best. Marked `~` to signal "shadow present, ground absent → looks wrong."
- **#16 Subscripts**: math-text subscripts work; regime-tag underscores (`sub_pixel`, `point_source`, `extended`) are the latent issue called out in §3 / T10.
- **#18 Qt-✗**: panel scaffold is wired but holds a placeholder, not a parameter panel — this is the known T9/CU-043 gap that R8 reopens.

### Special-case checks (round-2 plan §10 step 4)

- **`extended_default`:** the pixel-cell footprint as a translucent square on the ground is **not visible** — the regime override changed the *label* tag to `(extended)` but no pixel-cell footprint primitive renders. Open question for R9 / file CU.
- **`geometry_diagram`:** all angle groups (off-nadir, α_t, θ_sun,B) — partial; the off-nadir + α_t + θ_sun arcs render at the top, but az / el / Δφ / θ_sun,B are not separately surfaced. Close to default sphere view in current state.
- **`sun_terminator` (θ_s=60°, Δφ=90°):** the terminator on the sphere is approximately aligned with the sun direction — visible diagonal split between lit (right) and shadowed (left) hemispheres in `before/sun_terminator.png`. ✓ within visual tolerance.
- **`point_source_default`:** the point-source marker is *not* visibly distinguished from the regular sub-pixel target indicator — the regime override only changes the regime-tag string in the `Target A_t = ...` label. No special marker geometry.

---

## 5. R-task work-load summary (what each round-2 task actually has to do)

| Task | Diet-pass impact | Real work needed |
|---|---|---|
| R1 (default camera) | None — diet pass didn't touch camera | Replace iso pose with isometric-three-quarter + scene-extent-driven distance |
| R2 (framing policy) | None | New `scene/framing.py`; recenter shortcut; regression test |
| R3 (sun glyph) | Sun reverted to sphere — need to restore disc + rays + screen-space sizing | Material rewrite of [scene/glyphs/sun.py](scene/glyphs/sun.py) |
| R4 (ground plane) | Ground cap + fade disabled in [ground/__init__.py](scene/ground/__init__.py) — wiring change only | Re-wire cap + fade; reconcile diet-pass "engineering plot" objection (round-2 plan supersedes diet here) |
| R5 (break-marks) | Disabled at the call sites in `boresight.py` / `sun_ray.py` — wiring change only | Set `with_break_mark=True` at the two call sites; re-tune amplitude if needed |
| R6 (leaders) | Existing leaders are 0.75 px / 0.45 opacity / no anchor dots — visible in PNG as nearly invisible | Bump line width + opacity, add anchor-dot vtkActor2D, enforce 240 px max-distance constraint in solver |
| R7 (right panel) | Already shipped & wired | Interactive verification only (no code unless R9 finds defect) |
| R8 (left panel) | Placeholder only | Real implementation — width 200 px, sections, sliders, debounced signal |
| R9 (verify-all) | n/a | Re-render 9 views into `after_R<n>/`, fill 20×9 matrix, write `REMEDIATION_REPORT_round2.md` |

R3, R4, R5, R6, R8 are net-new code; R1, R2 are smaller targeted edits; R7 is verification only. R9 is the gate.

---

## 6. Latent issues uncovered during the audit (must become CUs before this PR merges, per Rule 21)

1. **Regime-tag display strings carry literal underscores** (`sub_pixel`, `point_source`, `extended`) into user-visible labels — see §3 / T10. Suggested fix: `regime_display(regime)` helper in `app/view_model.py` returning hyphenated forms ("sub-pixel", "point source", "extended", "auto"). Category B (one-shot label-string change). Will file as CU-04X under "Open" before this PR closes.
2. **Extended-regime view has no pixel-cell footprint primitive** — `extended_default` is visually identical to `geometry_diagram` apart from the regime tag string. Round-2 plan §10 step 4 explicitly checks for "the pixel-cell footprint as a translucent square on the ground." File as CU; defer the implementation work behind R9 unless the reviewer wants it folded into round 2.
3. **`point_source_default` view has no point-source marker primitive** — same shape as the audit. File as CU.
4. **Diet pass dropped the gridded ground cap and the outer fade plane** but the modules `scene/ground/cap.py` and `scene/ground/fade.py` are still on disk, never imported. Either R4 re-imports them (R4 will), or — if R4 chooses a different fallback — the dead modules need either deletion or a docstring marking them as Phase-7-diet-orphans. Track via R4's resolution and the `Cleanup_Backlog.md` entry it generates.

These will be filed at the CU stage (during/after R8, before the PR merges) per the round-2 plan §12 *"R21 holds: any latent issue you uncover that is orthogonal to the current R-task gets a CU entry in docs/tracking/Cleanup_Backlog.md before this PR merges."*

---

## 7. What success at the audit gate looks like

This audit gates entry to R1. Ground truth captured:
- 9 PNGs in [tests/audit_round2/before/](tests/audit_round2/before/) — frozen baseline.
- This document — the matrix + the per-task findings + the latent-issue list.

**Decisions taken during audit (do not relitigate):**
- The diet-pass commit `19e4077` is the audit baseline. The user authorised this in the contradiction-resolution exchange before §1 began.
- Off-screen PNGs cannot verify Qt-shell surfaces (panels, view-cube, gnomon, frame-indicator). R9's interactive step is the verification path for those.
- The diet pass's "engineering plot" objection to the gridded ground is *overridden* by round-2 plan §5 R4. R4 will re-wire the cap + fade.

R1 starts next.
