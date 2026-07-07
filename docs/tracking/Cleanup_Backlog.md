# RADIANT Cleanup Backlog

**Purpose**: track technical-debt and follow-up tasks discovered while executing feature work, so they don't get lost and don't contaminate the feature PR scope.

**Usage**: any stage/task that uncovers a latent issue orthogonal to its scope appends an entry here. Entries carry enough context (file paths, commands, symptoms) to be picked up cold. Closed entries move to the "Resolved" section at the bottom with the PR or commit that fixed them.

**Not for**: items inside the current feature's scope (those go in the feature plan), scenario-specific gaps (those go in the scenario's `gaps.md`), or operational/runtime gaps already tracked in `docs/tracking/gaps.md`.

**Numbering note**: CU-026 through CU-041 were never allocated (the GUI-v2 track jumped to CU-042); the gap is intentional, not lost entries. The GUI-v2 README's Phase-7 deferral references to CU-043–046 were phantom numbers (never filed here) that collided with the audit entries now holding those IDs; they were re-filed 2026-07-06 as CU-052–055.

---

## Open


### CU-003 — Pre-existing MTF tolerance warning on `swir_aerial_gas.yaml`

**Discovered**: Option C Stage 0 (2026-04-19)
**Investigated**: Phase 2 Track A (2026-04-24)
**Status**: Open — escalated to a stand-alone Category C task (`docs/reports/cu_tasks/CU-003_Rect_Kernel_Fix_Task.md`) — this entry stays Open until the follow-on lands.

**File**: `examples/templates/swir_aerial_gas.yaml`
**Symptom**: MTF consistency check reports `max_err_x = max_err_y = 0.05196` vs tolerance `0.050` (~4% miss). All other 13 baseline scenarios pass cleanly.

**Reproducer numbers** (Phase 2 investigation, 2026-04-24):
- Aperture 0.12 m, focal 0.36 m (f/3.0), pixel pitch 20 µm, filter 2.0–2.5 µm.
- `Q = λ·F#/pitch ≈ 0.338` at 2.25 µm — the lowest Q in the suite (next-lowest, `vnir_leo_highres`, has Q ≈ 1.0).
- PSF spatial sampling: `sample_spacing = 1.6875 µm` → `pitch / sample_spacing ≈ 11.852` samples per pixel (non-integer).
- Residual peaks near Nyquist (idx 35 of 64), monotonic at low frequency.

**Per-term sensitivity** (drop-one-MTF-term probe on the product side, re-measure `max_err`):
| Term dropped | max_err |
|---|---|
| (none — baseline) | 0.05196 |
| optics | 0.131 |
| pixel_aperture | 0.546 |
| jitter / smear / ipc / diffusion | 0.05196 (no change) |

Only optics × pixel_aperture matter for this scenario. Decisive verification: substituting the *discrete* rect kernel's actual FFT into the product (in place of the analytic `sinc(π·pitch·f)`) collapses `max_err` to **0.00000** (floating-point identity), proving the entire residual is the pixel-aperture term's PSF-path/MTF-product-path discretization mismatch.

**Root cause**: `src/radiant/optics/pixel_kernel.py::_rect_1d` builds a binary mask `np.where(np.abs(x) <= pitch/2, 1.0, 0.0)` at `1.6875 µm` sample spacing. With `11.852` samples per pixel (non-integer), the kernel quantizes the rect's edges, so its FFT has lower roll-off than the analytic `sinc` that the MTF-product path uses. The PSF path therefore over-attenuates near Nyquist relative to the MTF-product path, and the divergence is greatest at low Q (when `pitch/λF#` is small the rect edges dominate).

**Branch classification (per Phase 2 plan §Track A)**:
- **Finding A** (real Rule-4 bug, missing/mis-applied degradation in one path) — **NO**. Both paths apply pixel-aperture; they disagree only on discretization.
- **Finding B** (numerical edge intrinsic to sampling) — **YES**. Q = 0.338 is the suite minimum; the scenario sits at a corner of the sampled-rect's accuracy regime.
- **Finding C** (inconsistent scenario YAML) — **NO**. The scenario inputs are self-consistent.

**Why this is not a Phase-2 inline fix**: a proper fix is Category C (touches optics physics path, requires three numerical truth anchors, dimensional audit, fragility analysis, and golden-snapshot sweep). Two candidate approaches exist:
1. Anti-aliased rect kernel — replace the binary mask in `_rect_1d` with an integrated rect (subpixel-area weighting at the edges, equivalent to convolving the binary rect with a sample-spacing impulse train and integrating). PSF-path FFT will then match the analytic `sinc` to ~1e-6 across all Q.
2. FFT-based product path — compute the pixel-aperture MTF on the product side from `FFT(_rect_1d(...))` instead of the analytic `sinc`. Symmetric: both paths see the same discretization. Cheaper but couples the product path to the PSF sampling grid.

Approach 1 is preferred (preserves the MTF-product path as the analytic reference; fixes the PSF path to match).

**Why it still matters** (supersedes the earlier "low priority unless promoted to a regression anchor" framing, which is no longer accurate): the scenario *is* in `tests/integration/snapshots/option_c_baseline.yaml` and will be re-checked at every Option C stage. The miss is ~4% above tolerance, persistent, and the only failing cell. It needs a real fix before it gets confused with a Stage 6 physics drift.

**Suggested fix**: stand-alone task (Category C, effort M) per `docs/reports/cu_tasks/CU-003_Rect_Kernel_Fix_Task.md` — the two candidate approaches above: (1) anti-aliased rect kernel in `_rect_1d` (preferred — preserves the MTF-product path as the analytic reference and fixes the PSF path to match), or (2) FFT-based product path (cheaper but couples the product path to the PSF sampling grid).

### CU-005 — `theta_o_from_eta` boundary converter is unwired

**Discovered**: Option C Stage 1 (2026-04-19)
**Re-audited**: 2026-04-24 (Stages 7 and 8 have landed); 2026-04-26 (re-scoped — see Status); 2026-04-26 (refreshed after CU-009 escalation)
**Status**: UNBLOCKED 2026-07-06 — CU-009 landed (commit `d846f07`); the forced choice described below is now live. Re-audit and decide: (a) introduce `geometry.sensor_off_nadir_rad` routed through `theta_o_from_eta` (Approach C of CU-009, deferred there), or (b) document the η opt-out as deliberately deferred behind the SensorDescriptor ADR. Re-audit date: 2026-08-15. Prior context: the CU-009 escalated task answers the prerequisite question for CU-005: the canonical schema name for `theta_o` is `geometry.path_zenith_rad` (Approach A in CU-009's doc). When CU-009 lands, CU-005's resolution becomes a forced choice between (a) leaving `theta_o_from_eta` as the boundary converter that user-supplied `geometry.sensor_off_nadir_rad` would route through (Approach C of CU-009, deferred there), or (b) documenting the η opt-out as deliberately deferred behind the SensorDescriptor ADR. Investigation 2026-04-26 found the original "Suggested fix" mis-framed:

- The CU body conflated three things in `core/los_geometry.py`. Only one of them is unwired: the standalone `theta_o_from_eta` function. The `LineOfSightGeometry` class itself is heavily consumed (every atmosphere backend, the source stage, ~10 test files, all source-stage snapshots). `LineOfSightGeometry.intercepts_earth(h_sensor)` is wired into production at [src/radiant/atmosphere/assembly.py:204](../src/radiant/atmosphere/assembly.py#L204), called from `validate_no_atmosphere_subcase` against the already-registered `platform.h_sensor` parameter ([src/radiant/platform/_schema.py:127](../src/radiant/platform/_schema.py#L127), Stage-7 stop-gap).
- Path (a) ("wire into `OpticsStage._finalize_regime()`'s Earth-intercept check") doesn't apply: the Earth-intercept check is `intercepts_earth()` (not `theta_o_from_eta`), it lives in AtmosphereStage (not OpticsStage), and it is already wired.
- Path (b) ("move to `radiant.api.geometry`") is no improvement: the function only depends on `R_EARTH_M` and `ParameterBoundsError`, both already in `core/`. The file's own docstring (lines 22–30) explicitly justifies keeping it in `core/` adjacent to `LineOfSightGeometry`.
- Path (c) ("delete") is premature: 5 unit tests at `core/tests/test_los_geometry.py:204–258` cover spherical-Earth sine-rule inversion with a horizon-tangent floating-point guard. The function is documented, tested, and reserved for the SensorDescriptor follow-on per the file docstring's "**not dead code**" note.

The real reason `theta_o_from_eta` has no consumer: no `source.observer_geometry.eta` (or equivalent) schema parameter exists yet. Today users supply `theta_o` directly via `_inferrer.py::_infer_los`, or accept the hardcoded default `theta_o=0.0` — and that hardcoded default is the subject of **CU-009**. When CU-009 lands the `source.observer_geometry.*` schema parameters, the schema-design question becomes real: "does the user supply `theta_o` directly, or supply `(eta, h_sensor)` and let `theta_o_from_eta` convert?" That is where CU-005 actually gets answered. Solving it before CU-009 lands is solving an imaginary problem (same pattern as CU-011, also blocked on CU-009).

**File**: `src/radiant/core/los_geometry.py::theta_o_from_eta`
**Symptom (verified 2026-04-26)**: standalone `theta_o_from_eta` function has zero non-test callers in `src/radiant/`. Only sites: definition, the 5-test suite at `core/tests/test_los_geometry.py:204–258`, and the `core/__init__.py` export.
**Why it still matters**: tracking, not urgency — once CU-009 lands the schema, this CU's resolution becomes a forced choice (wire in `_inferrer._infer_los`, or document the `eta` opt-out as deliberately deferred behind a SensorDescriptor ADR).
**Suggested fix (deferred to post-CU-009 re-audit)**: when CU-009's escalated task lands and `_inferrer._infer_los` reads from the canonical `geometry.path_zenith_rad`, decide whether to (a) introduce `geometry.sensor_off_nadir_rad` and route through `theta_o_from_eta(eta, h_sensor, h_tgt)` (Approach C of CU-009, deferred there for scope reasons), with an explicit precedence rule against `geometry.path_zenith_rad`, or (b) document the η opt-out as deliberately deferred behind the SensorDescriptor ADR. Note: the CU-009 task doc explicitly defers the sensor-off-nadir surface here rather than co-resolving it. Re-audit date: 2026-08-15 (calendar backstop; earlier if CU-009 lands).

### CU-008 — Stage-2 `GroundBackground` placeholder is grey, not spectral

**Discovered**: Option C Stage 2 (2026-04-19)
**Re-audited**: 2026-04-24 (Stages 3–8 have landed); 2026-04-26 (escalated — see Status)
**Status**: investigated 2026-04-26; escalated to a stand-alone Category C task (`docs/reports/cu_tasks/CU-008_GroundBackground_Spectral_Task.md`) — this entry stays Open until the follow-on lands. Investigation found (a) the placeholder is at [_inferrer.py:1707–1726](../src/radiant/source/_inferrer.py#L1707), (b) **zero baseline scenarios route through it** — every one of the 14 scenarios in `tests/integration/snapshots/option_c_baseline.yaml` and `src/radiant/source/tests/snapshots/*.yaml` is `scene_type: extended` with `background: null` (extended scenes return `None` from `_build_background_descriptor` at line 1701), so the placeholder fires on no live scenario today; (c) the only live consumer is one unit-test fixture at `src/radiant/source/tests/test_inferrer.py:472`. The CU's "still emitted on every sub-pixel scenario" claim was correct in principle but not in the live code base — the placeholder is **dormant production code**, not silently-corrupting code. The fix lights up dormant code rather than refreshing existing snapshots.

**File**: `src/radiant/source/_inferrer.py::_build_background_descriptor`
**Symptom (verified 2026-04-24)**: `_inferrer.py` lines ~1842–1865 still call `_grey_spectraldata(wavelength_um=..., value=bg_eps_scalar, ...)` to construct `GroundBackground(epsilon_g=...)`. The `UserWarning` flagging "placeholder bg, will be replaced in Stage 3" is still emitted on every terrestrial / airborne sub-pixel scenario.
**Why it still matters**: dormant Rule-17 antipattern. Once the first sub-pixel terrestrial / airborne scenario lands (likely soon — CU-009 schema work, future point-target scenarios), the placeholder warning starts firing in production and the silent-grey ε_g(λ) becomes a real radiometry bug for non-grey materials (vegetation NDVI, snow MWIR drop, urban asphalt SWIR). Stage 6's E_sky decomposition consumes ε_g spectrally via `_assemble_ground_background`; the bridge has to be built before a real consumer arrives.
**Suggested fix**: see `docs/reports/cu_tasks/CU-008_GroundBackground_Spectral_Task.md`. Recommended approach (Approach 1 in that task doc): named spectral-library enum (`source.background.material ∈ {grey, vegetation, snow}`) + optional `source.background.emissivity_path` override, with the existing scalar `source.background.emissivity` preserved as the `material="grey"` back-compat path. Three numerical truth anchors (grey-limit identity, vegetation NDVI signature, snow MWIR drop). Zero existing-baseline drift; one or two new sub-pixel test fixtures added.

### CU-011 — MODTRAN backend's `evaluate()` aliases two-leg τ (single-τ adapter)

**Discovered**: Option C Stage 3 (2026-04-19)
**Re-audited**: 2026-04-24 (Stage 6 has landed); 2026-04-26 (refreshed after CU-009 escalation)
**Status**: UNBLOCKED 2026-07-06 — CU-009 landed (commit `d846f07`); the producer side now exists, so the stand-alone Category C task in Suggested fix can be filed. Re-audit date: 2026-08-15. Prior context: the exercise path is now visible (post-CU-009, a YAML can plumb non-zero `geometry.solar_zenith_rad` through `_infer_los` to the MODTRAN backend), so the test fixture for the second TAPE7 invocation finally has somewhere to land. Stage 6 (E_sky decomposition, commit `b9244fd`) landed the consumer side; CU-009 lands the producer side; this CU completes the MODTRAN-backend slice. Currently anchor cells 28/58 use the analytic atmosphere, so the MODTRAN single-τ alias does not affect the pinned values directly — but any MWIR scenario that elects to route through MODTRAN with a non-zero `θ_s` would silently lose the solar-leg attenuation.

**File**: `src/radiant/atmosphere/modtran.py`
**Symptom (verified 2026-04-24)**: `modtran.py` lines 730–752 still emit the `UserWarning` and set `tau_sun = tau`, `tau_up = tau.copy()`, `tau_full_up = tau.copy()`, `L_path_up = lpath`, `L_path_full = lpath.copy()` from a single MODTRAN call. No second TAPE7 run keyed on `θ_s`, no analytic split.
**Why it still matters**: VIS/NIR reflective scenarios that route through MODTRAN now silently lose the solar-zenith dependence that Stage 6's E_sky decomposition was designed to expose. The analytic backend is fine; the MODTRAN backend collapses the split. Mixed-backend test suites can therefore mask real two-leg bugs.
**Suggested fix**: stand-alone Category C task (file post-CU-009 landing) — add a second MODTRAN invocation keyed on `(los.h_tgt, los.theta_s)` to produce `tau_sun` independently from `tau_up`. Cache key must include θ_s. Expect a Cell 28/58 re-baseline conversation if any MWIR snapshot scenario routes through MODTRAN with non-zero θ_s (today both anchors use the analytic atmosphere; this is a no-op for them). Block: requires CU-009 to land first so a YAML can actually exercise non-zero θ_s through the MODTRAN backend. Re-audit date: 2026-08-15 (calendar backstop; earlier if CU-009 lands).

### CU-024 — Sun-zenith readout: `θ_s` (target) and `θ_sun,B` (background) collapse to identical values in flat-ground display

**Discovered**: Geometry GUI Phase 10 (2026-04-26)
**Status**: Open — flagged in PLAN.md §12 Phase-11 plan "Phase-10 CU sweep candidates".

**File**: `dev_tools/geometry_gui/app/view_model.py` (`_READOUT_FORMATTERS` `ro-solar-zenith` row); `dev_tools/geometry_gui/app/scene_builder/{sun_zenith_arc,solar_zenith_arc}.py`
**Symptom**: Both arc helpers (`sun_zenith_at_target_rad(s_unit)` and `solar_zenith_at_b_rad(n_B, s_unit)`) reduce to `arccos(s_z)` whenever the surface normal at B equals `+ẑ` — which is *every* state the GUI currently renders, since the display assumes flat ground. The two on-figure labels (`θₛ` at target and `θ_sun,B` at the background point) sit at different anchors but encode the same numeric angle, and the readout panel shows only one row labeled "Solar zenith" without disambiguating which of the two physically-distinct angles is being read out.
**Why it still matters**: this is a *display* limitation, not a physics bug — the helpers are correct. The audit hit is that the GUI presents two visually-distinct decorations as if they were independent measurements, which would mislead a user driving a non-flat-ground scenario. The moment Phase 12+ adds ground-tilt or oblique-surface support (i.e., `n_B ≠ +ẑ`), `θ_sun,B` will diverge from `θ_s` and the readout panel needs to label them separately.
**Suggested fix**: stand-alone Category B task — (a) add a `target_surface_normal` field to `SceneState` (default `+ẑ`); (b) split the readout row into `Solar zenith at target (θ_s)` and `Solar zenith at B (θ_sun,B)`; (c) on-figure label for `θ_sun,B` becomes redundant when `n_B = +ẑ` exactly — suppress the second arc in that case to avoid visual duplication. Tests: when normal is non-axial, both rows surface, both arcs render, and the values differ. Block on Phase 12+ scope (no current consumer). Re-audit date: 2026-08-15 (calendar backstop; earlier if Phase 12+ ground-tilt/oblique-surface scope lands).

### CU-025 — Camera auto-frame is anchored to default-state geometry constants

**Discovered**: Geometry GUI Phase 11 (2026-04-26)
**Status**: Open — design choice, but the coupling needs to be captured before someone changes one of the display constants in isolation.

**File**: `dev_tools/geometry_gui/app/scene_builder/_camera_frame.py` (`REFERENCE_HALF_EXTENT = 6.0`)
**Symptom**: Phase-11 (d) introduces auto-framing via a bounding-box scan over all base-scene traces; the eye distance scales as `max(1.0, half_extent / REFERENCE_HALF_EXTENT)`. The constant `6.0` was hand-calibrated against the default state's bbox (driven by `OBSERVER_DISPLAY_DISTANCE = 4.0` and `SUN_DISPLAY_DISTANCE = 6.0` in `_display_constants.py`). Any future change to either display distance silently breaks the "default state framing matches Phase-10" invariant guarded by `tests/test_phase11_polish.py::test_camera_default_state_eye_unchanged`.
**Why it still matters**: a developer who bumps `OBSERVER_DISPLAY_DISTANCE` to make the observer chip more readable will trip the camera-frame test, but the failure message will point at `_camera_frame.py` rather than at the display constant they actually edited. The cross-module coupling is correct (the camera *must* track the bbox) but undocumented at the code-comment level.
**Suggested fix**: inline-fix-now — add a one-line comment on `REFERENCE_HALF_EXTENT` linking it to `OBSERVER_DISPLAY_DISTANCE` / `SUN_DISPLAY_DISTANCE` and noting that any change to those constants requires re-calibration. Optional follow-up: derive `REFERENCE_HALF_EXTENT` programmatically from the default-state bbox at import time, eliminating the manual constant. Effort: < 30 LOC; Category A. Re-audit date: 2026-08-15 (calendar backstop; earlier if the next PR touching `dev_tools/geometry_gui/app/scene_builder/` picks up the inline fix).

### CU-043 — Rule 15 error-type migration: 398 bare `raise ValueError/RuntimeError` across core + physics

**Discovered**: architecture audit 2026-07-06, branch `fix/architecture-audit-2026-07`
**Status**: Open

**File**: repo-wide across `src/radiant/` — core 69, source 52, atmosphere 80, optics 96, platform 20, spectral_integration 8, detector 50, readout 16, performance 7 (e.g. `src/radiant/core/units.py:105`, `src/radiant/core/radiometry.py:83`, `src/radiant/core/geometry.py:77`)
**Symptom**: 398 `raise ValueError(...)` / `raise RuntimeError(...)` statements in core and physics modules use bare built-in exceptions rather than `RadiantError` subclasses with the what/why/action/context structure.
**Why it still matters**: user code cannot catch `RadiantError` for framework rejections — the single-`except RadiantError` contract established by CU-018 is hollow wherever a bare built-in is raised. Violates Rule 15's actionable-error contract.
**Suggested fix**: stand-alone task — migrate user-input validation paths first (`core/parameters`, `core/units`, `io/`), then physics invariant guards. Effort L; category A/B.

### CU-044 — Hardcoded tuneable quantities in physics modules (Rule 12)

**Discovered**: architecture audit 2026-07-06, branch `fix/architecture-audit-2026-07`
**Status**: Open

**File**: `src/radiant/source/stage.py:84` and `src/radiant/source/_inferrer.py:200` (regime threshold `0.25 * ifov`, duplicated); `src/radiant/atmosphere/simple.py:92-165` (aerosol coefficient table, H2O band table, `RAYLEIGH_COEFF_KM` / `H2O_CONTINUUM_KM` / lapse rate); `src/radiant/performance/giqe.py:26-31,112` (GIQE-5 coefficients, m→inch conversion); `src/radiant/source/converters/brightness_temperature.py:56` (brightness-temperature threshold); `src/radiant/detector/ipc.py:37,50,90` (IPC coupling ceiling 0.25)
**Symptom**: tuneable physics quantities are hardcoded inline in physics modules rather than registered as `ParameterDef`s in `_schema.py` or named constants; the regime threshold `0.25 * ifov` is duplicated at two sites.
**Why it still matters**: untunable physics constants outside schema/`constants.py` violate Rule 12 ("all tuneable quantities are parameters; nothing is hardcoded in physics modules"); the duplicated regime threshold can silently diverge if one site is edited without the other.
**Suggested fix**: stand-alone task — promote genuinely tuneable quantities to `ParameterDef`s, move fixed physical/empirical constants to module-level named constants with citations, deduplicate the regime threshold. Effort M; category B/C.

### CU-045 — Dual-path consistency check gating: warn-only at tolerance 5e-2

**Discovered**: architecture audit 2026-07-06, branch `fix/architecture-audit-2026-07`
**Status**: Open — blocked by CU-003 (the rect-kernel discretization error sets the tolerance floor). Re-audit date: 2026-08-15 (calendar backstop; earlier if CU-003 lands).

**File**: `src/radiant/performance/consistency_check.py`
**Symptom**: the PSF-path vs MTF-product-path consistency check runs with default tolerance `5e-2`, unconditionally, and only warns on failure. CLAUDE.md Rule 4 previously claimed ~1e-6 gated at `standard` fidelity (doc corrected 2026-07-06 to describe actual behavior).
**Why it still matters**: the Rule-4 consistency invariant is the guard against a spatial degradation landing in one path but not the other; a warn-only 5e-2 gate is too loose to catch small real divergences, and no strict mode exists for configurations that should agree tightly.
**Suggested fix**: stand-alone decision task after CU-003 — decide whether to (a) tighten tolerance per-configuration, (b) add a strict mode that raises, or (c) accept warn-at-5e-2 permanently. Effort S; category C.

### CU-052 — GUI v2 headlining slider work (Phase-7 deferral; formerly README "CU-043")

**Discovered**: Geometry GUI v2 Phase 7 deferral list (2026-05-02); re-filed 2026-07-06 during loose-end cleanup (the README's CU number was never allocated in this registry).
**Status**: Open. Re-audit date: 2026-08-15.
**File**: `dev_tools/geometry_gui_v2/app/panels/parameters.py`
**Symptom**: the parameters panel's slider interaction work ("headlining slider work" per `dev_tools/geometry_gui_v2/README.md` Phase-7 deferrals) is deferred; it gates the performance and memory test passes (CU-053, CU-054).
**Why it still matters**: Phase 7 (hardening + handoff) cannot complete its acceptance bundle without it; two downstream CUs are blocked on it.
**Suggested fix**: stand-alone task per `docs/plans/Geometry_GUI_v2_Plan.md` Phase 7. Effort M; category A (GUI tooling).

### CU-053 — GUI v2 performance pass (Phase-7 deferral; formerly README "CU-044")

**Discovered**: Geometry GUI v2 Phase 7 deferral list (2026-05-02); re-filed 2026-07-06.
**Status**: Open — blocked on CU-052. Re-audit date: 2026-08-15.
**File**: `dev_tools/geometry_gui_v2/` (scene rebuild path)
**Symptom**: no performance test pass exists for interactive scene rebuilds; deferred from Phase 7 pending the slider work that would exercise it.
**Why it still matters**: the tool is the visual-design prototype for the production GUI's geometry tab; rebuild latency regressions land silently without a gate.
**Suggested fix**: stand-alone task per `docs/plans/Geometry_GUI_v2_Plan.md` Phase 7, after CU-052. Effort S–M; category A.

### CU-054 — GUI v2 memory pass (Phase-7 deferral; formerly README "CU-045")

**Discovered**: Geometry GUI v2 Phase 7 deferral list (2026-05-02); re-filed 2026-07-06.
**Status**: Open — blocked on CU-052. Re-audit date: 2026-08-15.
**File**: `dev_tools/geometry_gui_v2/` (actor lifecycle)
**Symptom**: no memory-leak pass over repeated scene rebuilds (VTK actor churn); deferred from Phase 7 pending the slider work that would exercise it.
**Why it still matters**: long-lived desktop sessions with continuous parameter dragging will surface any actor leak; no gate exists.
**Suggested fix**: stand-alone task per `docs/plans/Geometry_GUI_v2_Plan.md` Phase 7, after CU-052. Effort S–M; category A.

### CU-056 — GUI v2 sun glyph uses world-space sizing, not screen-space (formerly docstring "CU-046")

**Discovered**: Geometry GUI v2 round-2 remediation (sun glyph rework); re-filed 2026-07-06 during loose-end cleanup (the docstring's CU number was never allocated in this registry and collided with the README's CI-deferral phantom).
**Status**: Open. Re-audit date: 2026-08-15.
**File**: `dev_tools/geometry_gui_v2/scene/glyphs/sun.py`
**Symptom**: the sun disc + rays are sized in world space (tuned to ~24 px / 8 px at the round-2 default camera distance); zooming scales the glyph with the scene instead of holding fixed pixel size.
**Why it still matters**: icon-style glyphs are meant to read at constant screen size; at extreme zoom the sun either dominates the viewport or vanishes.
**Suggested fix**: stand-alone small task — screen-space sizing via `vtkActor2D` or a camera-change callback, per the file docstring's deferral note. Effort S; category A.

---

## Resolved

### CU-049 — `RadiometricFrame.in_band_value` is `None` on `at_aperture` despite `signal_at("at_aperture")` working — RESOLVED 2026-07-06 (commit `a9b3bca`)

**Discovered**: Scripting-API doc verification pass, architecture audit 2026-07-06, branch `fix/architecture-audit-2026-07`

**File**: `src/radiant/core/radiometry.py` / `src/radiant/io/results.py`
**Symptom**: the `at_aperture` frame's `in_band_value` field is `None`; `ChainResult.signal_at("at_aperture")` nevertheless returns a value by applying transfer factors from a downstream frame.
**Why it still matters**: two access paths to the same physical quantity disagree about whether it exists — a user inspecting frames directly sees `None` where the accessor reports a number; inconsistent inspectability violates the spirit of Rule 16.
**Suggested fix**: stand-alone task — either populate `in_band_value` for all frames at spectral-integration time or document/enforce that `in_band_value` is only defined post-integration and make `signal_at`'s derivation explicit in its docstring. Effort S; category B.
**Resolution**: taken as the CU's document/enforce option — the populate option is architecturally forbidden (RadiometricFrame enforces spectral XOR scalar per Rule 8, so pre-integration frames are spectral-only by design). Contract made explicit in RadiometricFrame docs, signal_at() docstring, and a Scripting API §3.2 callout; pinned by integration test `test_pre_integration_frame_scalar_is_none_but_signal_at_derives`.

### CU-023 — Phase-10 arc trace `name` duplicated across line + label sub-traces — RESOLVED 2026-07-06 (obsolete; commit `3acac3a`)

**Discovered**: Geometry GUI Phase 10 (2026-04-26)

**File**: `dev_tools/geometry_gui/app/scene_builder/{off_nadir_arc,azimuth_arc,elevation_arc,phase_angle_arc,solar_zenith_arc,sun_zenith_arc,sun_azimuth_arc}.py`
**Symptom**: Pre-Phase-11, every arc module emitted *two* plotly traces with identical `name=` (e.g. `off-nadir = 20.0°` for both the lines-mode arc trace and the text-mode label trace). Plotly's legend collapses duplicates silently, but hover tooltips and any future legend-driven test would surface both copies of the same string.
**Why it still matters**: trace `name` is the contract surface for hover text, legend entries, and any test that introspects scene contents by name. Two unrelated traces sharing one name is a lurking ambiguity — a future filter that picks a trace by name returns whichever one happens to be first in the list. Same anti-pattern existed across all seven arc modules so the audit hit is structural, not local.
**Suggested fix**: (a) Phase-11 mitigation already in place — each label sub-trace now uses a distinct `label_name` (`"<key> label (<value> deg)"`) while the lines-mode trace keeps the canonical `arc_name` (`"<key> = <value>°"`). (b) Close-out: re-audit on Phase-11 PR merge and move to Resolved with the merge SHA per R22. (c) Standing guard: a per-arc-module test asserting `arc.name != label.name` would prevent regression — author when filing the close-out.
**Resolution**: closed as obsolete. The subject code (GUI v1, `dev_tools/geometry_gui/app/scene_builder/*`) was deleted entirely in ORG-C (`3acac3a`, owner Decision #1 — v1 closed, git history is the archive), so the planned standing-guard test has no code to guard. The v2 replacement cannot reproduce the pattern: PyVista's actor registry is a dict keyed by name (duplicates replace, never coexist), arc actors get distinct names structurally (`scene/arcs/_arc.py:59,74` — tube `name`, tip `{name}_tip`), labels are a separate subsystem, and existing presence tests (e.g. `test_leader_lines_round2`) catch any clobbering.

### CU-046 — `Sensor.reset()` reaches into `ParameterSet` privates — RESOLVED 2026-07-06 (commit `6edf17c`)

**Discovered**: Scripting-API doc verification pass, architecture audit 2026-07-06, branch `fix/architecture-audit-2026-07`

**File**: `src/radiant/api/sensor.py` (`reset()`)
**Symptom**: `Sensor.reset()` manipulates `ParameterSet._inputs` and `ParameterSet._resolved_flag` directly instead of going through a public API.
**Why it still matters**: any internal refactor of `ParameterSet` state silently breaks `Sensor.reset()`; the private-attribute coupling bypasses the validation/resolution lifecycle the class owns.
**Suggested fix**: stand-alone small task — add a public `ParameterSet.reset()` (or `clear_inputs()`) that owns the invalidation semantics, and have `Sensor.reset()` call it. Effort S; category A.
**Resolution**: public `ParameterSet.clear_input(name)` added (owns invalidation semantics: invalidates only when an input was removed; KeyError + did-you-mean for unknown names). `Sensor.reset()` delegates to it — bonus fix: reset() previously silently no-oped on typo'd dotpaths. Scripting API doc updated in lock-step; 5 new tests.

### CU-050 — Config loader silently strips `_vars` / `_extends` / `_imports` keys — RESOLVED 2026-07-06 (commit `8b66cd8`)

**Discovered**: doc-reconciliation pass, architecture audit 2026-07-06, branch `fix/architecture-audit-2026-07`

**File**: `src/radiant/io/config.py:36`
**Symptom**: `load_config` strips the `_vars`, `_extends`, and `_imports` keys without processing them and without warning. A user config relying on the inheritance/substitution features documented in `RADIANT_Config_Format.md` §1.3–1.5 (now banner-marked unimplemented) loads "successfully" with those directives silently ignored. The XLSX view (§2) is likewise unimplemented.
**Why it still matters**: silent key-stripping is a Rule 17 antipattern — a config that says `_extends: base.yaml` produces physics results from an entirely different parameter set than the user intended, with no diagnostic.
**Suggested fix**: stand-alone task — either implement the three directives or make `load_config` raise `ConfigError` ("_extends is not implemented; inline the base config") when they are present. Interim minimum: warn. Effort S (raise) / M (implement); category A.
**Resolution**: `load_config` now raises an actionable `ConfigError` naming every reserved directive present (all offenders in one error) with the inline-the-values remedy. Config Format §1.3 banner updated in lock-step. 3 parametrized tests + multi-offender test added; grep verified no in-repo config uses the directives.

### CU-055 — GUI v2 test suite not wired into CI (Phase-7 deferral; formerly README "CU-046") — RESOLVED 2026-07-06 (commit `6874139`)

**Discovered**: Geometry GUI v2 Phase 7 deferral list (2026-05-02); re-filed 2026-07-06.
**File**: `.github/workflows/ci.yml`
**Symptom**: `.github/workflows/ci.yml` runs nothing under `dev_tools/`; the 386-test GUI v2 suite (including the golden_phase1 screenshot baseline) relies on manual invocation only.
**Why it still matters**: the repo's only untested-in-CI code surface; a `src/` refactor that breaks the GUI's `radiant` imports would land green.
**Suggested fix**: inline-fix-now — add a `gui-tests` CI job (Linux: Qt offscreen deps + xvfb, `pip install -e . -e dev_tools/geometry_gui_v2`, `pytest dev_tools/geometry_gui_v2 -q`). Note the repo currently has no git remote, so all CI jobs are dormant until one is configured. Effort S; category A.
**Resolution**: `6874139` adds a `gui-tests` job to `.github/workflows/ci.yml` (ubuntu: Qt/VTK system libs, `pip install -e dev_tools/geometry_gui_v2`, `xvfb-run pytest dev_tools/geometry_gui_v2 -q`). Caveat recorded: the repo has no git remote, so the job is dormant until one is configured; on the first real run the golden_phase1 screenshot baselines may need recalibration for llvmpipe rendering per RADIANT_Testing_Validation §5.3 (comment in the job says exactly that).

### CU-051 — `scripts/update_golden.py` uses stale noise-term keys — RESOLVED 2026-07-06 (commit `0729faf`)

**Discovered**: CU-007 close-out on branch `chore/cu-007-mwir-t3mixed-routing` (2026-04-26, as pre-renumbering "CU-047"); the branch's backlog filing never reached main — re-filed and closed 2026-07-06 during loose-end cleanup.
**File**: `scripts/update_golden.py`; `src/radiant/core/radiometry.py` (docstring).
**Symptom**: `update_golden.py` looked up `noise["shot"]` and `noise["read"]`, but the canonical noise-term names (per `radiant.core.noise_budget`) are `signal_shot` and `read_noise` — the golden-regeneration script would KeyError on invocation.
**Resolution**: cherry-picked `83967ed` as `0729faf`: key lookups fixed, `NoiseTerm` docstring updated to the canonical names, and `tests/integration/test_update_golden_keys.py` regression guard added (asserts the script's key set against the live noise budget).

### CU-007 — Stage-2 MWIR-mixed `UserWarning` is globally suppressed inside `_inferrer.py` — RESOLVED 2026-07-06 (commit `45b6671`)

**Discovered**: Option C Stage 2 (2026-04-19)
**Re-audited**: 2026-04-24 (Stage 6 has landed)
**Status**: investigated 2026-04-26; escalated to a stand-alone Category B task with C-level radiometric audit (`docs/reports/cu_tasks/CU-007_MWIR_T3Mixed_Routing_Task.md`) — this entry stays Open until the follow-on lands. Investigation confirmed (a) the suppression wrapper is at [src/radiant/source/_inferrer.py:1542](../src/radiant/source/_inferrer.py#L1542); (b) six baseline scenarios route through the wrapper (`ground_truth_mwir`, `mwir_leo_minimal`, `mwir_aerial_flir`, `mwir_ground_test`, `mwir_leo_pushbroom`, `mwir_leo_starer`); (c) `T3Mixed` adds the reflected-direct-solar + reflected-diffuse-sky terms via Kirchhoff in [atmosphere/assembly.py:786](../src/radiant/atmosphere/assembly.py#L786) — a real radiometric change to those rows' `L_aperture`/`nedt_K`/`snr`; (d) anchor cells 28/58 are bit-invariant (LWIR T1Thermal, ρ≡0). Original "50–100 LOC, Category B (no physics change)" estimate undercounted the snapshot regression burden — escalation matches the CU-003 pattern.

**File**: `src/radiant/source/_inferrer.py::_build_target_descriptor`
**Symptom (verified 2026-04-24)**: `warnings.catch_warnings() / simplefilter("ignore", UserWarning)` still wraps the `T1Thermal(...)` construction at lines ~1670–1687 of `_inferrer.py`. Every MWIR snapshot scenario still triggers the suppression at runtime (silently); the only signal is that *no* warning ever surfaces from those scenarios.
**Why it still matters**: the suppression masks a legitimate modelling flag for any new MWIR cell that lands post-Stage-8 with the legacy scalar surface. With Stage 6's T3Mixed synthesis available, there is no longer a reason to gag the warning — the inferrer should now choose T3 for atmosphere-aware MWIR cases and leave T1 only for the `ρ ≈ 0` cases where the warning is genuinely a false positive.
**Suggested fix**: see `docs/reports/cu_tasks/CU-007_MWIR_T3Mixed_Routing_Task.md`. Recommended approach (Approach 1 in that task doc): MWIR-overlap defaults to `T3Mixed`; new `source.target.is_hot_target` schema parameter as the explicit hot-target opt-out; suppression wrapper removed entirely. Six MWIR snapshot rows refresh; remaining 8 rows + anchor cells 28/58 bit-invariant.
**Resolution**: Approach 1 of the task doc landed as `45b6671` (cherry-picked from branch `chore/cu-007-mwir-t3mixed-routing`, original commit `452cccd`): MWIR-overlap legacy scalar-ε scenarios default to `T3Mixed` (Kirchhoff emit+reflect); new `source.target.is_hot_target` schema parameter is the explicit hot-target opt-out; the `warnings.catch_warnings()` suppression wrapper is removed. Six MWIR snapshot rows and `tests/integration/golden/mwir_leo_minimal.json` + `option_c_baseline.yaml` refreshed per the task's C-level radiometric audit; anchor cells 28/58 bit-invariant. Full suite incl. golden green on merge day.

### CU-009 — Stage-2 `_infer_los` ignores the registered `geometry.*` params (nadir/Kármán hardcode) — RESOLVED 2026-07-06 (commit `d846f07`)

**Discovered**: Option C Stage 2 (2026-04-19)
**Re-audited**: 2026-04-24 (Stage 5 has landed); 2026-04-26 (escalated — see Status)
**Status**: investigated 2026-04-26; escalated to a stand-alone Category B task with C-level radiometric audit ([docs/reports/cu_tasks/CU-009_Observer_Geometry_Schema_Task.md](CU-009_Observer_Geometry_Schema_Task.md)) — this entry stays Open until the follow-on lands. Investigation confirmed (a) the hardcode is at [src/radiant/source/_inferrer.py:286–292](../src/radiant/source/_inferrer.py#L286); (b) the original "register `source.observer_geometry.*` namespace" framing creates redundant parameter names — the equivalent params already exist on AtmosphereStage's schema and are consumed by multiple downstream stages: `geometry.path_zenith_rad` ([atmosphere/_schema.py:144](../src/radiant/atmosphere/_schema.py#L144), default 0.0) ↔ `theta_o`, `geometry.solar_zenith_rad` ([atmosphere/_schema.py:156](../src/radiant/atmosphere/_schema.py#L156), default 0.5 rad) ↔ `theta_s`, `geometry.solar_azimuth_rad` ([atmosphere/_schema.py:168](../src/radiant/atmosphere/_schema.py#L168), default 0.0) ↔ `delta_phi`; (c) the inferrer is the outlier — every other stage that needs LOS geometry already pulls from `geometry.*` (platform smear, performance GSD, MODTRAN, atmosphere assembly); (d) all 14 baseline scenarios take schema defaults for these three params (zero hits in `examples/`) and route through descriptors that don't consume `theta_s`/`delta_phi` (T1Thermal — LWIR/SWIR/VNIR, plus MWIR-under-CU-007-suppression), so the recommended "wire `_infer_los` to the existing `geometry.*` params" approach gives **zero existing-baseline drift**; (e) anchor cells 28/58 bit-invariant by construction (LWIR T1Thermal extended, all geometry defaults, `_assemble_t1` ignores `theta_s`/`delta_phi`); (f) latent finding folded into the task — `_view_direction_from_los` ([_inferrer.py:323](../src/radiant/source/_inferrer.py#L323)) reads `geometry.observer_zenith_rad`, which is unregistered (Rule-12 violation, silent `KeyError → 0.0` fallback); the canonical name is `geometry.path_zenith_rad`.

**File**: `src/radiant/source/_inferrer.py::_infer_los`
**Symptom (verified 2026-04-26)**: `_infer_los` at lines 286–292 still returns `LineOfSightGeometry(h_tgt=h_tgt_m, theta_o=0.0)` with `theta_s` and `delta_phi` unset and `h_atm_top` defaulting to 1e5 m. Only `h_tgt` is read from a parameter (`geometry.target_altitude_m`). The three relevant `geometry.*` params (`path_zenith_rad`, `solar_zenith_rad`, `solar_azimuth_rad`) are registered and consumed elsewhere but ignored by the inferrer.
**Why it still matters**: every reflective / two-leg / sky-decomposition scenario currently fires as nadir-surface-Kármán. Stage 6's E_sky decomposition has the *capability* to use real `θ_s` and `Δφ`, but the inferrer never supplies them, so the per-scenario radiance is computed at sun-overhead-and-on-axis regardless of the YAML's actual scene geometry. Ordering matters: landing CU-009 first means CU-007's MWIR T3Mixed snapshot refresh captures the correct solar geometry on the first cut (no double-shift); CU-005 and CU-011 also depend on a canonical `theta_o`/`theta_s` schema name being decided.
**Suggested fix**: see [docs/reports/cu_tasks/CU-009_Observer_Geometry_Schema_Task.md](CU-009_Observer_Geometry_Schema_Task.md). Recommended approach (Approach A in that task doc): wire `_infer_los` to the already-registered `geometry.path_zenith_rad` / `solar_zenith_rad` / `solar_azimuth_rad` (T1 ⇒ `theta_s = delta_phi = None`, T2/T3 ⇒ populated); fix the latent unregistered `geometry.observer_zenith_rad` reader in the same surgery; zero new schema parameters; zero baseline drift.
**Resolution**: Approach A of the task doc landed as `d846f07` (cherry-picked from branch `chore/cu-009-observer-geometry`, original commit `c2634b6`): `_infer_los` now reads the already-registered `geometry.target_altitude_m` / `path_zenith_rad` / `solar_zenith_rad` / `solar_azimuth_rad` (T1 ⇒ `theta_s = delta_phi = None`; T2/T3 ⇒ populated); the latent unregistered `geometry.observer_zenith_rad` reader in `_view_direction_from_los` fixed in the same surgery. Zero new schema parameters; zero baseline drift (all 14 baselines take defaults); 418-line routing test suite added (`test_inferrer_los_routing.py`).


### CU-042 — `QtInteractor` segfault under `QT_QPA_PLATFORM=offscreen` on Darwin — RESOLVED 2026-05-02 (commit `c972802`)

**Discovered**: Geometry GUI v2 Phase 6 (2026-04-26).
**File**: `dev_tools/geometry_gui_v2/tests/test_interaction_phase5.py`; `dev_tools/geometry_gui_v2/app/main.py`.
**Symptom**: `QtInteractor.__init__` segfaulted (SIGSEGV during construction, exit 139) when the Qt platform plugin was set to `offscreen` on macOS — Python's exception handling cannot recover from that. Eight Qt-window tests skipped behind `RADIANT_GUI_FULL_WINDOW_TESTS=1` env-gate. Visual remediation Round 2 (R9-B3) and Round 3 (S8-B1, S8-B2) all carved out around it. Pixel-level verification of view-cube, gnomon, dock layout, and full-app screenshots was unavailable.
**Why it mattered**: blocked the §10 acceptance bundle for the round-3 visual remediation (the 14 full-app frames + interactive checklist). Carved-out blockers were stacking up.
**Resolution**: switched the platform plugin from `offscreen` to the platform-native plugin per `sys.platform` (`cocoa` / `xcb` / `windows`). The conftest path in `test_interaction_phase5.py` now sets the right plugin by default and `RADIANT_GUI_FULL_WINDOW_TESTS` defaults to `1`. All 8 previously-skipped tests run; `pytest dev_tools/geometry_gui_v2/tests/ -q` now reports **384 passed, 0 skipped**. The 9 full-app canonical-view screenshots have been generated under `dev_tools/geometry_gui_v2/tests/golden/round3/final/<view>_full.png` using `QScreen.grabWindow(win.winId())` — `QWidget.grab()` cannot capture VTK's OpenGL framebuffer.

### CU-022 — Dead `shadow_mode_off` fixture post-Stage-4 narrowing — RESOLVED 2026-04-26 (commit `2d93cd9`)

Resolved by removing the fixture (`src/radiant/atmosphere/tests/test_evaluate.py` lines 119-136), its self-test (`test_shadow_mode_off_fixture_sets_env`), the docstring sentence referencing it, and the now-unused `os` and `Iterator` imports. Kept `test_shadow_mode_symbol_is_gone` — that's a real guard against reintroducing `_shadow_mode_enabled` and remains valuable. Verified pytest 2797/2797 passing (was 2798 pre-removal — one self-test deleted), ruff lint+format clean, mypy --strict clean (53 files), lint-imports 5/5 contracts kept. Initial CU-022 draft also flagged `tests/integration/snapshots/option_c_baseline.yaml` as orphaned but that was wrong: the YAML is the scenario index for `src/radiant/source/tests/test_inferrer.py:49` (`SNAPSHOT_YAML = ...`) and is regenerated by `scripts/capture_option_c_baseline.py`. The YAML's per-cell `classification` field is unused but the file itself is live infrastructure — left in place.

### CU-012 — Shadow-mode classification injection not wired — RESOLVED 2026-04-26 (Stage 4 commit `3680a54`)

Closed by reference to the Stage 4 architectural decision, not by new code. Investigation 2026-04-26 found that Stage 4 (commit `3680a54`, 2026-04-20) deliberately removed the entire shadow-mode mechanism — `_shadow_compare()`, `_SHADOW_ENV_VAR`, `_SHADOW_RTOL`, `_shadow_mode_enabled()`, the dual-path execution in `AtmosphereStage.run()`, and the legacy `build_state()` protocol method are all gone. Per-scenario invariant assertion was not "silently dropped" — it was deliberately superseded. Post-Stage-4 regression gating is narrowed to **two anchor cells (28 and 58)** with hardcoded pinned values in `tests/integration/test_option_c_anchors.py::CELL28_PINNED` and `CELL58_PINNED` (rtol=1e-6, `ANCHOR_TOLERANCE` line 69). The 14-scenario `option_c_baseline.yaml` survives as an orphaned historical artifact (zero consumers — filed as **CU-022**). The post-Stage-6 narrowing is documented in `docs/archive/Option_C_Implementation_Plan.md` lines 31–53 (Regression Invariants section); the doc already carries a top-of-file HISTORICAL banner directing readers to `RADIANT_Master_Architecture.md` for current architecture.

### CU-013 — Shadow-mode `rtol=1e-6` may be too tight for Stage 6 heterogeneous cells — RESOLVED 2026-04-26 (Stage 4 commit `3680a54`)

Closed alongside CU-012, same root cause. The `_SHADOW_RTOL` constant returned zero grep hits because Stage 4 (commit `3680a54`) deleted it along with the rest of the shadow-mode machinery. The Stage-6-tolerance concern is therefore moot — there is no post-Stage-6 tolerance value to recover because the per-scenario heterogeneous-cell comparison no longer runs. The `ANCHOR_TOLERANCE = 1e-6` in `tests/integration/test_option_c_anchors.py:69` survives unchanged because Cells 28 and 58 are both T1Thermal with ρ≡0, making them bit-invariant across Stage 6's `ρ · (E_sky_scattered + E_sky_thermal)` decomposition (`Option_C_Implementation_Plan.md:51`). No tolerance loosening occurred; the assertion scope shrank from "all invariant cells" to "two anchor cells."



### CU-021 — Repo-wide `ruff format` drift (160 files) — RESOLVED 2026-04-26 (commit `1c1c6b7` + CI follow-up `87dfccc`)

Resolved by two commits: (1) `1c1c6b7` ran `ruff format src/` repo-wide, reformatting 160 of 346 files (+2227/-2420 lines, format-only diff with no logic changes), verified by pytest 2798/2798 passing, mypy --strict clean (53 files), lint-imports 5/5 contracts kept, ruff check + ruff format --check both clean post-pass; (2) `87dfccc` added `ruff format --check src/` to the `static` job in `.github/workflows/ci.yml` so formatting drift is now gated alongside ruff lint, mypy --strict, and import-linter. CLAUDE.md "Code Style" requirement (ruff format, line length 100) is now enforceable in CI, completing the gap left by CU-020 slice 5.

### CU-020 — Pytest level0/1/2/golden marker sweep + CI gating — RESOLVED 2026-04-26 (slice 5 commit `f0c2aed`)

Resolved across 5 slices: 1=`4f403c9` (`core/tests/`, 335 level0 + 34 level1), 2=`e18ace1` (`source/` + `atmosphere/tests/`, 318 level0 + 344 level1 + 3 level2), 3=`1925237` (`optics/`/`platform/`/`spectral_integration/`/`detector/`/`readout/`/`performance/tests/`, 612 level0 + 440 level1), 4=`6fedb03` (`io/`/`cli/tests/` + top-level `tests/`, 38 level0 + 82 level1 + 399 level2 + 10 golden), 4b=`4d288d7` (`api/tests/` + `data/tests/` + `source/converters/tests/`, 160 level1 + 19 level2), 5=`f0c2aed` (`.github/workflows/ci.yml` with four jobs: `static`, `fast-tests`, `integration-tests` gated on fast-tests, and `golden` on push-to-main + workflow_dispatch only). `--strict-markers` landed in `addopts` at commit `b021d38`. Final marker coverage: 2798/2798 (1307 level0 + 1060 level1 + 421 level2 + 10 golden); zero unmarked. `ruff format --check` deliberately omitted from CI — repo-wide format drift (160 files) filed as CU-021 for stand-alone fix. Two test files (`platform/tests/test_stage_mtf_term.py`, `performance/tests/test_consistency_check.py`) and one (`api/tests/test_performance.py`) needed an `import pytest` line added alongside the markers. Three slice-2 tests run a full `RadiantSession` and were marked level2 rather than level1; 19 slice-4b api/data tests likewise. Closes Testing_Validation §3 gap that previously left `pytest -m "not level0"` silently skipping un-marked Level-0 tests, making R18 ("Test at Level 0 Before Level 2") unenforceable.

### CU-001 — Pre-existing `lint-imports` contract breakages — RESOLVED 2026-04-24

Resolved by Phase 6 of the technical-debt cleanup (commits 2a70558, 7ab1251, bea406a). `cli/convert.py` was the only direct production violation; routed through new `radiant.api.units` re-export. All transitive cli→api→{core,platform,optics,io} edges enumerated in `pyproject.toml` `ignore_imports`. Test-colocation patterns (`radiant.*.tests.*`) granted explicit ignores with `unmatched_ignore_imports_alerting = "warn"`. All 5 import-linter contracts now KEPT.

### CU-002 — Pre-existing `mypy --strict` errors in non-`core`/`api` modules — RESOLVED 2026-04-24

Resolved by Phases 2–5 of the technical-debt cleanup. `core/responsivity.py` no-any-return wrapped with `np.asarray` (commit `0d361eb`), `api/sweep.py` no-redef collapsed (commit `0e6bb84`), `api/tolerance.py` union-attr asserted (commit 2de6b76), `api/plot.py` × 6 + `api/tests/test_plot.py` × 1 wrapped with `cast(Figure, ...)` at the matplotlib seam (commit f9fcf3c). `mypy --strict src/radiant/core src/radiant/api` is now clean (51 source files).

### CU-010 — `test_inferrer.py` imports from `radiant.api` — RESOLVED 2026-04-24

Resolved by Phase 6.2 (commit 7ab1251). `pyproject.toml` import-linter contracts now exempt `radiant.*.tests.*` patterns from the physics-stage and cross-stage rules, matching CLAUDE.md's intent (Rule 11 governs production code; tests legitimately need api/io to build full-schema fixtures).

### CU-004 — `mwir_ground_test.yaml` classification is ambiguous — RESOLVED 2026-04-24 (commit `a880c94`)

Resolved by Phase 2 Track B via Path A (single-enum vocabulary expansion). Added `expected_to_change_at_stage_6_and_stage_7` to the legal-values list on `ScenarioResult` in `scripts/capture_option_c_baseline.py`, taught `_classify()` to apply the compound classification when the scenario name matches `mwir_ground_test`, and updated the `option_c_baseline.yaml` cell directly with a `classification_reason` justifying the dual-stage drift. Path B (`list[str]`) was rejected: today there are zero live consumers of the YAML's `classification` field (the shadow-mode reader CU-012 is unwired and reads from a different stage-output path), making the list-of-string promotion all churn for no gain. Regression gate green: 2360 src + 381 integration + mypy + ruff + 5/5 import contracts KEPT.

### CU-006 — `LineOfSightGeometry` field ordering diverges from plan text — RESOLVED 2026-04-24 (commit `5f07f76`)

Resolved by Phase 2 Track C. Added `kw_only=True` to the `@dataclass` decorator and re-ordered field declarations to match the plan's textual order `(h_tgt, h_atm_top=1e5, theta_o, theta_s=None, delta_phi=None)`. Positional construction now raises `TypeError` at construction time, closing the silent `h_atm_top ↔ theta_o` misassignment footgun before Stage 2's inferrer expands. All call sites already used keyword form; no test fixes required. Regression gate green: 2360 src + 381 integration, mypy/ruff/import-linter clean.

### CU-014 — Stage-4 `GroundBackground` assembly is thermal-only (deferred reflected terms) — RESOLVED 2026-04-24

Resolved by Stage 6 of Option C (commit `b9244fd`, "feat(option-c): Stage 6 — E_sky decomposition"). [src/radiant/atmosphere/assembly.py](../src/radiant/atmosphere/assembly.py) `_assemble_ground_background` (lines 1122–1158) now returns `(L_self + direct + diffuse) * tau_full_up + L_path_full`, where `L_self = epsilon_g * B(T_g)`, `direct = _direct_solar_term(rho_g, atm, cos_ts)` for the reflected-direct-solar term, and `diffuse = _diffuse_sky_term(rho_g, atm)` for the reflected-diffuse-sky term. Both branches that the original CU said were omitted are now present. Cell 28 and Cell 58 stayed bit-invariant because both anchors are `T1Thermal` with `ρ ≡ 0`, so the `(1−ε_g)` reflectance terms vanish identically — confirmed in [docs/archive/Option_C_Implementation_Plan.md](Option_C_Implementation_Plan.md) Regression Invariants table. Verified during the 2026-04-24 stage-deferred audit.

### CU-015 — `readout.stage` lazy-imports `detector.noise.budget` — RESOLVED 2026-04-24 (commit `621414d`)

Investigation showed the fallback (lines 140–149) was unreachable: `RadiantSession` always runs `DetectorStage` before `ReadoutStage`, and every test that exercises `ReadoutStage` directly populates `noise_budget_raw` itself. Replaced the fallback with a `ValueError` that explicitly tells the caller to populate `stage_outputs['detector']['noise_budget_raw']` (CLAUDE.md Rule 17 — fail loudly, not silently). Removed the corresponding `radiant.readout.stage -> radiant.detector.noise.budget` ignore from `pyproject.toml`. All five import contracts now KEPT without exceptions for production cross-stage imports.

### CU-016 — `from radiant import Sensor` not re-exported at top level — RESOLVED 2026-04-25 (commit `52a1fba`)

**Discovered**: 2026-04-25 audit (audit_2026/) finding tracked as CU-NEW-02 in `Reconciliation_Tasks.md`. Doc examples in `RADIANT_Scripting_API.md` (and ADR-C decision Yes/No/No) showed users were expected to write `from radiant import Sensor`, but `radiant/__init__.py` did not re-export it; the only working path was the longer `from radiant.api.sensor import Sensor`.

**File**: `src/radiant/__init__.py`
**Resolution**: Added `from radiant.api.sensor import Sensor` and `__all__ = ["Sensor", "__version__"]` per ADR-C. SensorConfig / ScenarioConfig / BatchRunner were intentionally left out of the top-level surface — users wanting them go through `radiant.api.*` and accept the same stability contract. New tests in `tests/test_public_api.py` (3 tests, level0 + level1) verify (a) the top-level `Sensor` is the same class as `radiant.api.sensor.Sensor`, (b) `radiant.__all__` matches the ADR-C decision exactly, and (c) the doc-example pattern `Sensor.from_yaml(...).evaluate()` runs end-to-end against `examples/mwir_leo_minimal.yaml`. No doc edits were required because the docs were already written against the new (correct) API — the rename brought code into sync with the existing docs (R20 satisfied as a consequence).

### CU-017 — `ChainResult.{signal,noise}_at_frame` doesn't match documented `{signal,noise}_at` — RESOLVED 2026-04-25 (commit `a548c1e`)

**Discovered**: 2026-04-25 audit, tracked as CU-NEW-03. `RADIANT_Scripting_API.md` and `RADIANT_Signal_Chain_Architecture.md` documented `result.signal_at("dn")` / `result.noise_at("dn", term_name="read_noise")` but the implementation used `signal_at_frame` / `noise_at_frame`. Examples written verbatim from the docs would fail with `AttributeError`.

**File**: `src/radiant/io/results.py`
**Resolution**: Renamed methods to the documented names. Imports of the underlying core helpers were aliased (`from radiant.core.quantity import noise_at as _quantity_noise_at, signal_at as _quantity_signal_at`) to avoid name collision with the new method names. Backward-compat aliases `signal_at_frame` / `noise_at_frame` kept for one minor version, each emitting `DeprecationWarning(stacklevel=2)` with a removal note for RADIANT 0.2.0. Added convenience accessors `result.snr()` / `result.nedt()` (returns Kelvin, reads `metrics["nedt_K"]`) / `result.niirs()` per the documented quick-look pattern; missing keys raise `KeyError` (CLAUDE.md fail-loudly policy) rather than returning a sentinel. Test fixture `src/radiant/io/tests/test_results.py` updated to the new names with two new test classes covering deprecation warnings + value parity (3 tests) and metric accessors + KeyError path (4 tests). Two integration tests (`tests/integration/test_full_system.py`, `tests/integration/test_use_case_shapes.py`) updated to the new method names. Regression gate green: 14/14 io tests + 38/38 integration tests pass; mypy --strict clean on core+api (51 files); 5/5 import-linter contracts KEPT. No doc edits were needed (R20 satisfied — the rename brought code in sync with already-correct docs).

### CU-018 — `RadiantError` referenced in CLAUDE.md / docs but no base class existed in code — RESOLVED 2026-04-25 (commit `12d174d`)

**Discovered**: 2026-04-25 audit, tracked as CU-NEW-01 in `audit_2026/Reconciliation_Tasks.md`. `CLAUDE.md` Rule 15, `RADIANT_Master_Architecture.md` §C12/§7.4, and `RADIANT_Testing_Validation.md` §8.1/§8.5 all referenced `RadiantError` and an exception hierarchy "in `radiant.exceptions`", but no such module or base class existed in `src/`. The six concrete exception classes (`ParameterBoundsError`, `KirchhoffViolationError`, `ModtranUnavailableError`, `Tape7ParseError`, `ConfigError`, `ElementConfigError`) inherited only from built-ins (`ValueError`, `RuntimeError`, `Exception`). User code wanting a single `except RadiantError` clause to catch every framework-defined error had no way to do so.

**File**: `src/radiant/core/exceptions.py` (new); modifications to `src/radiant/__init__.py`, `src/radiant/core/parameters.py`, `src/radiant/optics/element.py`, `src/radiant/atmosphere/modtran.py`, `src/radiant/io/config.py`, `src/radiant/io/element_config.py`.
**Resolution**: Introduced `RadiantError(Exception)` in `radiant.core.exceptions` (placed under `core/` so other core modules can import it without violating the "core has no radiant imports" import-linter contract). Re-exported at the top level — `from radiant import RadiantError` — and added to `radiant.__all__`. Migrated all six concrete subclasses to inherit from `RadiantError`. Built-in co-inheritance (`ValueError`, `RuntimeError`) preserved on five of six classes for back-compat with existing `except ValueError` / `pytest.raises(ValueError, ...)` patterns scattered across the suite; this is documented in CLAUDE.md §15 and Master_Architecture §7.4 as a deliberate carve-out. New Level-0 hierarchy contract test in `tests/test_exceptions.py` (10 tests; lives outside any package boundary because it imports from `radiant.optics`/`radiant.atmosphere`/`radiant.io` and would violate the "core has no radiant imports" contract if placed under `core/tests/`). Pins (a) every concrete class is-a `RadiantError`, (b) back-compat co-inheritance still holds, and (c) top-level re-export is the same object as the core import. Doc updates per R20: CLAUDE.md §15 rewritten, `RADIANT_Master_Architecture.md` §C12 + §7.4 rewritten with concrete subclass inventory and built-in co-inheritance carve-out, `RADIANT_Testing_Validation.md` §8.1 updated to show actual class shape, §8.5 hierarchy regenerated to match code (the aspirational `PhysicsError` / `PluginError` / `ReproductionError` tiers and finer-grained `ParameterTypeError`/`ParameterEnumError`/etc. families were not implemented and are explicitly noted as deferred). Regression gate: 10/10 hierarchy tests + 0 regressions in existing exception-raise sites (`pytest.raises(ValueError, ...)` patterns still match because of co-inheritance).

### CU-019 — `ChainResult.to_provenance_record()` referenced in docs but no implementation existed — RESOLVED 2026-04-25 (commit `70e512d`)

**Discovered**: 2026-04-25 audit, tracked as CU-NEW-04 in `audit_2026/Reconciliation_Tasks.md`. `RADIANT_Master_Architecture.md` §C13, `RADIANT_Signal_Chain_Architecture.md` §7 (`ChainResult` interface listing), and `RADIANT_Parameter_System.md` provenance-audit section all promised that every `ChainResult` exposes a complete provenance record (run ID, RADIANT version, git commit, Python version, dependency versions, resolved parameter set, input file hashes, active models). The actual `radiant.io.results.ChainResult` had no `to_provenance_record()` method — and even if it had, none of the supporting plumbing existed: `ChainState` had no `run_id` field, no helper for `git_commit` / `dependency_versions` lived anywhere in `core/`, `ParameterSet` did not track which YAML files had been loaded, and `RadiantSession.run` did not pass `params` through to the result. A user calling the documented API would get `AttributeError: 'ChainResult' object has no attribute 'to_provenance_record'`.

**File**: `src/radiant/core/provenance.py` (new); modifications to `src/radiant/core/chain.py`, `src/radiant/core/parameters.py`, `src/radiant/io/config.py`, `src/radiant/io/results.py`, `src/radiant/api/session.py`.
**Resolution**: Built the §C13 contract end-to-end in five layers. (1) Pure helpers in `radiant.core.provenance`: `new_run_id()` (UUID4 string), `git_commit()` (short SHA, `"unknown"` outside a repo or with no git binary — never raises), `python_version_string()` (`MAJOR.MINOR.PATCH`), `dependency_versions()` (`{name: version}` for the four declared runtime deps; `"unknown"` for missing packages), `hash_file()` (SHA-256, 64 KiB chunks). Lives in `core/` so any module — including the rest of `core` — can import it without breaking the "core has no radiant imports" contract. (2) `ChainState.run_id: str | None` field; `ChainRunner.run` mints a fresh UUID4 if the caller doesn't supply one. (3) `ParameterSet._loaded_files` list + `record_loaded_file(path, sha256)` method + `loaded_files` property; loaders dedupe identical entries while letting same-path/new-hash through. (4) `radiant.io.config.load_config` calls `params.record_loaded_file(str(path), hash_file(path))` after a successful YAML parse, so every file the run consumed appears in the record. (5) `ChainResult.__init__` takes an optional `params: ParameterSet | None`; `RadiantSession.run` passes the resolved params through; `to_provenance_record() -> dict[str, Any]` returns the JSON-serialisable record with all eight §C13 keys. Provenance helpers degrade to `"unknown"` rather than raising on environmental edge cases — provenance must never block a chain run. While plumbing the field-hash list into `ParameterSet.__init__`, an in-place fix corrected an orphaned consistency-group validation block (the `for g in self._groups` loop sat after a `return` statement and was unreachable). New tests in `tests/test_provenance.py` (36 tests across 8 classes; lives outside any package boundary for the same reason as `tests/test_exceptions.py`): UUID4 shape + uniqueness, `git_commit` happy-path + non-repo + missing-binary fallbacks, Python version format, dependency completeness, `hash_file` known-digest + determinism + chunked-read + missing-file raise, `ChainState.run_id` default + round-trip, `ChainRunner` UUID-mint + caller-passthrough + per-run uniqueness, `ParameterSet.record_loaded_file` dedupe + same-path-new-hash, `load_config` records-on-YAML / records-nothing-on-dict, full §C13 contract from synthetic state, full end-to-end run from `examples/mwir_leo_minimal.yaml`. Doc updates per R20: `RADIANT_Master_Architecture.md` §C13 expanded with the canonical eight-field key table + helper-module pointer, `RADIANT_Signal_Chain_Architecture.md` `ChainState` skeletons gained the `run_id` field, `RADIANT_Parameter_System.md` provenance-audit section now records the `parameter_set` + `input_file_hashes` linkage to `ChainResult.to_provenance_record()` and the `record_loaded_file` plumbing. Regression gate: 36/36 new provenance tests + full suite (see commit body for counts) + 5/5 import-linter contracts kept + mypy --strict on core+api unchanged.
