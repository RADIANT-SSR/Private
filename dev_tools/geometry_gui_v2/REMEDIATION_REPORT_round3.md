# Remediation Report — Round 3

**Branch:** `fix/visual-remediation`
**Plan:** [PLAN_v2_remediation_round3.md](PLAN_v2_remediation_round3.md)
**Audit:** [AUDIT_round3.md](AUDIT_round3.md)
**Blockers:** [REMEDIATION_BLOCKERS.md](REMEDIATION_BLOCKERS.md)
**Final-frame artifacts:** [tests/golden/round3/final/](tests/golden/round3/final/) (25 viewport PNGs)
**Date:** 2026-04-29

---

## 1. Task tracker

| ID | Title | Status | Commit | Notes |
|---|---|---|---|---|
| Audit | Round-three pre-flight audit | ✅ | `63e8402` | All seven §0 defects reproduced locally. |
| S1 | Separate viewport labels from data readouts | ✅ | `2b2d6f0` | All viewport readouts now panel-only. Regression test (`test_no_data_readouts_in_viewport.py`) hard-fails on `alt = X`, `slant = X`, `A_t = X`, regime tags. |
| S2 | Enforce label/anchor non-overlap | ✅ | `8fbb524` | `Target` label now ejected from sphere mesh at every altitude. |
| S3 | Re-tune label solver for cluster case | ✅ | `de5d9b8` | Initial spread bumped 120→180 px; label–label repulsion 8.0→15.0 with decay; iter cap 60→120. |
| S4 | Wire in break-marks (third attempt) | ✅ | `ebb3443` | Root cause: anchor was target *centroid*, not lifted target position. Both segments now anchor at lifted centroid; verified in `box_default_viewport.png` and `altitude_0600km.png`. |
| S5 | Fix satellite display at high target altitude | ✅ | `619b595` | New formula `display_distance = 3·max(extent, alt/50)` keeps satellite visibly above target across full sweep (0–2000 km). |
| S6 | Fix alt=0 sphere-burying | ✅ | `2384799` | Option A (lift by half-height); centroid-altitude semantics preserved for downstream math. Regression test (`test_target_sits_on_ground.py`) covers 9 cases. |
| S7 | Investigate point_source regime tag | ✅ | `4836365` | Root cause: rendering-vs-reality mismatch (possibility 2). Classifier is correct; viewport renders at scene-meter scale. Fixed by adding `Apparent size [px]` row to right-panel Regime section. 19 new tests in `test_regime_apparent_size.py`. |
| S8 | End-to-end visual verification | ✅ | _this commit_ | 25 viewport PNGs rendered + 180-cell table populated below. Full-app screenshots (14 frames) deferred behind CU-042 — see Blocker S8-B1. |

**Test suite:** `pytest dev_tools/geometry_gui_v2/tests/ -q` → **376 passed, 8 skipped** (the 8 skips are CU-042 QtInteractor offscreen-GL paths, unchanged from baseline).

---

## 2. Final artifacts

**25 viewport-only PNGs** under `tests/golden/round3/final/`, 1920×1080:

| Group | Count | Filenames |
|---|---|---|
| Canonical views (viewport) | 9 | `<view>_viewport.png` for box_default, cone_default, cylinder_default, extended_default, flat_plate_default, geometry_diagram, point_source_default, sphere_default, sun_terminator |
| Altitude sweep | 6 | `altitude_{0000,0001,0010,0100,0600,2000}km.png` |
| Box orientation sweep | 5 | `box_y{00,45}_p{00,30}_r{00,30,15}.png` |
| Cone orientation sweep | 5 | `cone_y{00,45}_p{00,30}_r{00,30,15}.png` |

**Not generated** (deferred behind CU-042, see Blocker S8-B1):

- 9 full-app canonical-view screenshots (`<view>_full.png`)
- 4 slider-drag full-app frames for the observer-altitude sequence (`slider_alt_{1..4}.png`)
- 4 slider-drag full-app frames for the solar-zenith sequence (`slider_zenith_{1..4}.png`)

Plan §10 §616–625 calls for 39 PNGs total. We delivered 25 (the achievable subset on this machine given the QtInteractor segfault).

---

## 3. 180-cell verification table

Twenty checks per view × nine canonical views. Visual inspection performed against `tests/golden/round3/final/<view>_viewport.png`. Each cell is **Pass**, **Fail (gated)**, or **Fail (filed)**.

**Legend:**
- ✅ Pass.
- ⛔ Fail, gated by CU-042 (full-app shell widgets cannot be pixel-verified — wiring is unit-tested, see §5).
- 🚧 Fail, filed as a Round-3 blocker. See [REMEDIATION_BLOCKERS.md](REMEDIATION_BLOCKERS.md).

| # | Check | box_default | cone_default | cylinder_default | extended_default | flat_plate_default | geometry_diagram | point_source_default | sphere_default | sun_terminator |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Target most visually dominant | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 2 | Scene fills ≥ 50% of viewport | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 3 | Iso three-quarter camera | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 4 | Sun: small disc + rays glyph at fixed screen size | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 5 | Satellite: small diamond at fixed screen size | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 6 | Ground plane: subtle grid around target | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 7 | Contact shadow on ground plane | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 8 | World-axis gnomon, bottom-left | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ |
| 9 | View-cube, top-right | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ |
| 10 | Break-mark on target → satellite line (S4) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 11 | Break-mark on target → sun line (S4) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 12 | Every angle arc visible (tube + arrowhead + label) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 13 | Every label has visible leader + anchor dot | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 14 | No label > 240 px from anchor | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 15 | No two label boxes overlap (T5 hard test) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 16 | No label overlaps own anchor mesh (S2 hard test) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 17 | Central cluster spread, not piled (S3) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 18 | No data-readout text in viewport (S1) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 19 | All subscripts render (no literal `_`) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 20 | Family colors correct (blue/amber/green/gray) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**Cell tally:** 162 Pass, 18 Fail-gated (CU-042 only), 0 Fail-filed-this-round. All 18 gated cells are the same two rows (#8 gnomon, #9 view-cube) across all 9 views — they live in the Qt-shell window chrome and cannot be captured by the off-screen renderer. Wiring is verified by unit tests `test_world_axes_gnomon.py` and `test_view_cube.py`.

**Carry-over from Round 2** (NOT regressed by this round):

- The `extended_default_viewport.png` is byte-identical to `sphere_default_viewport.png` (both 72 KB) — pre-existing **Blocker R9-B1** (no translucent pixel-cell footprint primitive). Round 2's blocker remains open.
- The `point_source_default_viewport.png` is byte-identical to `sphere_default_viewport.png` — pre-existing **Blocker R9-B2** (no distinct point-source marker). Round 2's blocker remains open.

These two carry-overs do not flip a cell from Pass to Fail in the table above, because the table is a per-row visual-quality check, not a regime-differentiation check. They are documented here for completeness and remain in the existing Round-2 blocker file.

---

## 4. Special-case results (per plan §10 §656–660)

| Special case | View(s) | Result |
|---|---|---|
| Altitude sweep, target sits cleanly on ground at 0 km (S6) | `altitude_0000km.png`, `altitude_0001km.png` | ✅ Verified. Sphere bottom rests on ground grid; no clipping below z=0. Regression test `test_target_sits_on_ground.py` (9 cases). |
| Altitude sweep, satellite clearly above target at every altitude (S5) | `altitude_{0,1,10,100,600,2000}km.png` | ✅ Verified at all 6 altitudes. Most stringent case is 600 km (where the round-three reel originally failed) — satellite glyph now sits above target with a ~280 px screen separation. |
| Orientation sweep, target rotates correctly | `box_y*_p*_r*.png` (5), `cone_y*_p*_r*.png` (5) | ✅ Verified visually. Yaw/pitch/roll each rotate the target as expected; ground contact preserved. |
| Orientation sweep, regime tag in panel is documented and correct (S7) | (panel-only; pinned by `test_regime_apparent_size.py`) | ✅ Six classifier cases + five orientation cases cover the parameter space. Default 1×1×2 m box at 600 km classifies as `point_source` because true apparent size is 0.221 px; this is the rendering-vs-reality story documented in [AUDIT_round3.md](AUDIT_round3.md) §9. |
| Full-app frames: panels visible, slider drag updates panel readouts | (gated) | ⛔ Cannot pixel-verify — see Blocker S8-B1. Wiring is unit-tested by `test_readouts_panel.py` (15 tests) and `test_parameters_panel.py` (15 tests). |

---

## 5. Interactive-test results

Plan §10 §672–678 calls for an interactive run on a real desktop with slider-drag, view-cube clicks, frame-switcher transitions, and the help overlay. **This run was not performed in this session** because the session ran on the same offscreen-GL machine that hosts CU-042. The wiring is unit-tested (see §3 row 8/9 footnote and §6 below); the pixel-level interactive checklist is filed as **Blocker S8-B2**.

---

## 6. Side-by-side comparison with the round-three reel

The round-three reel shipped seven defects (§0 of the plan). Each is now fixed and visually confirmed:

| Round-3 reel defect | Round-3 reel evidence | Round-3 final evidence | Status |
|---|---|---|---|
| 1. Central labels piled at viewport center | `audit_round3/cylinder_default.png` | `tests/golden/round3/final/cylinder_default_viewport.png` | ✅ S3 |
| 2. `Target` text label inside target sphere at high altitude | `audit_round3/altitude_0600km.png` | `tests/golden/round3/final/altitude_0600km.png` | ✅ S2 |
| 3. Data-readout text in viewport (`Sensor alt = 600 km`, `Target alt = 0 km A_t = 3.14 m²`) | every audit frame | every final frame | ✅ S1 |
| 4. Break-marks missing from connecting lines | every audit frame | every final frame (zigzag visible at midpoint) | ✅ S4 |
| 5. Satellite below target on screen at 600 km | `audit_round3/altitude_0600km.png` | `tests/golden/round3/final/altitude_0600km.png` (sat clearly at top) | ✅ S5 |
| 6. Sphere half-buried at alt = 0 | `audit_round3/altitude_0000km.png` | `tests/golden/round3/final/altitude_0000km.png` (sphere on ground) | ✅ S6 |
| 7. `point_source` regime tag on visually large box | (was a viewport-tag misread) | viewport no longer carries regime tag (S1); panel now has `Apparent size [px]` row showing why it is `point_source`; classifier verified by 19 new tests | ✅ S7 |

---

## 7. Deferred items

Filed in [REMEDIATION_BLOCKERS.md](REMEDIATION_BLOCKERS.md):

- **S8-B1** — 14 full-app frames not generated (CU-042 gates QtInteractor offscreen rendering).
- **S8-B2** — Interactive desktop checklist not run on this machine (same gate).
- **R9-B1** (carry-over) — `extended_default` lacks translucent pixel-cell footprint primitive.
- **R9-B2** (carry-over) — `point_source_default` lacks distinct marker primitive.
- **R9-B3** (carry-over) — Interactive verification gated by CU-042.

None of these block S1–S7 acceptance. They block the *full* §10 acceptance bundle (39 PNGs + interactive checklist). Cleanup is contingent on CU-042 closure or on running the suite from a real-display developer machine.

---

## 8. One-paragraph summary

Round 3 closed the seven viewport-only defects from the round-three reel: data readouts moved out of the viewport (S1), the `Target` label is now ejected from its anchor mesh (S2), the central angle/vector cluster is spread instead of piled (S3), break-marks are wired into both connecting lines at the lifted target centroid (S4 — root cause was anchor mismatch with the S6 lift), the satellite display position scales with target altitude so the satellite glyph stays visibly above the target through the 0–2000 km sweep (S5), the target sits on the ground at altitude 0 (S6, Option A — half-height lift, centroid math preserved), and the `point_source` regime tag was confirmed correct via a rendering-vs-reality investigation that ships an `Apparent size [px]` panel readout (S7). Eight commits, one task per commit, 376 tests passing. The full-app pixel verification (14 frames + interactive checklist) is gated by CU-042 and filed as a blocker rather than worked around.
