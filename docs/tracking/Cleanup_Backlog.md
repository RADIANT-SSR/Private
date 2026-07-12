# RADIANT Cleanup Backlog

**Purpose**: track technical-debt and follow-up tasks discovered while executing feature work, so they don't get lost and don't contaminate the feature PR scope.

**Usage**: any stage/task that uncovers a latent issue orthogonal to its scope appends an entry here. Entries carry enough context (file paths, commands, symptoms) to be picked up cold. Closed entries move to the "Resolved" section at the bottom with the PR or commit that fixed them.

**Not for**: items inside the current feature's scope (those go in the feature plan), scenario-specific gaps (those go in the scenario's `gaps.md`), or operational/runtime gaps already tracked in `docs/tracking/gaps.md`.

**Numbering note**: CU-026 through CU-041 were never allocated (the GUI-v2 track jumped to CU-042); the gap is intentional, not lost entries. The GUI-v2 README's Phase-7 deferral references to CU-043–046 were phantom numbers (never filed here) that collided with the audit entries now holding those IDs; they were re-filed 2026-07-06 as CU-052–055.

---

## Open

### CU-092 — Signal_Chain §5 claims forward factors are stored under `stage_outputs[stage]["forward_factor"]`

**Discovered**: CU-091 fix (Signal_Chain §5 reconciliation), 2026-07-12
**Status**: Open
**File**: `docs/architecture/RADIANT_Signal_Chain_Architecture.md` §5 ("Forward propagation"); `src/radiant/core/quantity.py` (`_compute_transfer_factors`, `ChainQuantity.to`)
**Symptom**: §5 states "The conversion factors between adjacent frames are computed once per chain run and stored in `state.stage_outputs[stage]["forward_factor"]`." The shipped code writes no `forward_factor` key anywhere; `_compute_transfer_factors(state)` recomputes the factors from `stage_outputs` (`tau_atm`, `tau_opt`, `signal_e`, `signal_e_final`, `signal_dn_final`, `gain_e_per_dn`) on every `ChainQuantity.to()` call. Adjacent to CU-091 but a distinct claim, so left out of that fix's scope.
**Why it still matters**: a reader looking for a cached `forward_factor` in stage outputs will not find one and may add a redundant one; the "computed once and stored" mental model is wrong (factors are query-time, not chain-time). RADIANT_Reference_Frames.md §3 documents the shipped behaviour correctly, but §5 still carries the stale claim.
**Suggested fix**: inline-fix-now (doc-only, Rule 20) — reword §5 to say the factors are extracted from `stage_outputs` at query time by `_compute_transfer_factors`, not stored under a `forward_factor` key. Effort S; category A.

### CU-090 — Altitude duplicate not collapsed: `geometry.sensor_altitude_m` vs `platform.h_sensor`

**Discovered**: Gap 75 work (ground-speed collapse), 2026-07-11
**Status**: Open
**File**: `src/radiant/atmosphere/_schema.py` (`geometry.sensor_altitude_m`), `src/radiant/platform/_schema.py` (`platform.h_sensor`)
**Symptom**: two parameters name the same physical quantity — sensor altitude above MSL. The ground-speed duplicate was collapsed into an identity consistency group (Gap 75, commit pending), but the altitude pair was left independent: `platform.h_sensor` carries stop-gap space-subcase semantics (the atmosphere assembly raises if it is left at its 0.0 default when `source.no_atmosphere_subcase == 'space'`) and is set by 20+ tests/scenarios, several possibly independent of `sensor_altitude_m`.
**Why it still matters**: the two altitude fields can silently disagree, exactly the Gap 75 defect; a GUI would show two altitude widgets for one quantity.
**Suggested fix**: stand-alone task — audit all `h_sensor` call sites, then either (a) collapse via an identity consistency group like the ground-speed pair (verifying no site sets the two to different values), or (b) fold `h_sensor` into `sensor_altitude_m` and delete it once the SensorDescriptor ADR (matrix §4.4) lands. Effort M; category B.

### CU-077 — `readout.read_noise_is_post_cds` is a dead parameter; `cds_1f_suppression` is doc-only

**Discovered**: Capability audit 2026-07 (F-25), 2026-07-11 — verified (only consumer is a "deferred" docstring)
**Status**: Open
**File**: `src/radiant/readout/_schema.py:90`; `src/radiant/readout/read_noise.py:24`; `docs/architecture/RADIANT_Detector_Complete.md` §4.1
**Symptom**: schema + three docs describe a √2 pre-CDS read-noise scaling and a 0.7 flicker-suppression factor; no code reads either.
**Why it still matters**: schema-generated GUI forms render a no-op toggle; users entering pre-CDS datasheet noise are silently ~41 % low.
**Suggested fix**: stand-alone task — implement both or delete parameter and doc claims in lock-step (Rule 20). Effort S-M; category C.

### CU-080 — Reference-data provenance holes (detector QE, solar, emissivity grids, atmospheres README)

**Discovered**: Capability audit 2026-07 (F-23), 2026-07-11
**Status**: Open
**File**: `data/detectors/*.csv` (no manifest/citations); `data/solar/solar_irradiance_am0.csv` (Planck fit labeled AM0, ±5 % TSI-only validation); `data/emissivity/*.csv` (19 materials on one identical synthetic 84-point grid, no committed generator — Rule 26 tension); `data/atmospheres/README.md` (names nonexistent `atmosphere.modtran_file` and `radiant.io.modtran`)
**Symptom**: library dropdowns present untraceable representative curves as reference data; the README sends users to a parameter that raises.
**Why it still matters**: users comparing against vendor datasheets get unexplained deviations; violates the manifest-per-data-family convention.
**Suggested fix**: stand-alone task — manifests naming generator+source per family; fix the README; label or replace synthetic curves. Effort M; category A.

### CU-082 — geometry_gui_v2 records stale; goldens missing vs claims; re-audit CU-052/053/054 at GUI kickoff

**Discovered**: Capability audit 2026-07 (F-26), 2026-07-11
**Status**: Stage-deferred (gating stage: GUI kickoff; re-audit at GUI kickoff)
**File**: `dev_tools/geometry_gui_v2/README.md`, `ARCHITECTURE.md` (claim slider panel deferred per CU-052 — but `app/panels/parameters.py` ships it wired); `tests/` (only golden_phase1 exists vs C8's "every phase" claim; round-3 report references 25 absent PNGs)
**Symptom**: prototype's own records contradict its shipped code and test tree.
**Why it still matters**: GUI-restart planning will double-count done work and mis-sequence CU-052/053/054 (whose gating claims may already be satisfied).
**Suggested fix**: inline-fix-now at GUI kickoff — refresh records, re-render goldens, re-audit the three deferred CUs. Effort S; category A.

### CU-084 — Shadow legacy source system publicly exported but unwired (Rule 27)

**Discovered**: Capability audit 2026-07 (F-22), 2026-07-11
**Status**: Open
**File**: `src/radiant/source/__init__.py` (exports ResolvedTarget, five `resolve_*` paths, CombinedSource, ReflectedSolarSource, SurfaceMaterial, SubPixelSource, CompositeTarget…)
**Symptom**: a complete parallel source system is publicly importable but not connected to the chain; its CombinedSource applies no atmospheric attenuation to the solar term.
**Why it still matters**: two "source systems" in the public API invite integrators (or the GUI) to bind the dead, physically wrong one; violates one-canonical-version.
**Suggested fix**: delete-as-unused (or wire deliberately and document) — decide alongside the CU-079 Source doc reconciliation. Effort S-M; category B.

### CU-085 — Validation-hardening sweep (grouped: eight Rule-16/17 soft spots)

**Discovered**: Capability audit 2026-07 (F-25), 2026-07-11 — grouped as one sweep task; items are individually small and same-shaped
**Status**: NARROWED (2026-07-12, commit `513c9c5`) — 6 of 8 sub-items fixed; 2 remain
**Resolved sub-items (commit `513c9c5`)**: (1) `Tolerance.__post_init__` validates the distribution and required spread params — a parameter-less gaussian raises instead of silently sampling std=0; (2) consistency-group over-spec check picks a free variable that has a derivation rule (was silently skipped when `parameters[0]` lacked one); (4) velocity smear warns instead of returning 0 when altitude/t_int is missing though a velocity was set; (5) `detector.pixel_pitch_y_um` description corrected (required, no "defaults to x pitch" fallback); (6) IPC y-axis MTF uses `pixel_pitch_y` (was `pixel_pitch_x` — wrong for rectangular pixels); (8) `cli/run.py` provenance version reads `radiant.__version__` (was hardcoded "0.1.0").
**Remaining sub-items**: (3) `core/spectral.py` SpectralDataStore.add constant-extrapolates non-covering curves at DEBUG level (should warn — deferred: risks warning noise on legitimate near-edge curves, needs a coverage-fraction threshold); (7) readout digital-TDI branches have zero test coverage (add tests). Effort S; category B.
**Why it still matters**: exactly the silent-failure class Rules 16/17 forbid; a GUI amplifies each into invisible wrong answers.

### CU-087 — MODTRAN import surface residue: parsed tape7 columns dropped; binary-flavor ModtranConfig knobs unwired

**Discovered**: CU-086 re-audit of the landed MODTRAN rework (`d56fd9c`), 2026-07-11
**Status**: Stage-deferred (gating stage: MODTRAN binary flavor / CU-011 remainder; re-audit alongside CU-011's first-real-run check)
**File**: `src/radiant/atmosphere/modtran.py` (`to_radiant_units` returns `ground_reflected`, cached and carried by `Tape7Import`, but `_build_state_from_arrays` (:1147-1155) takes no such argument — verified post-rework); `ModtranConfig` fields `itype`, `iemsct`, `v1_cm1`, `v2_cm1`, `extra_cards` still have no ParameterDef and are never passed by `loaders._build_modtran` (`visibility_km` was wired by the rework)
**Symptom**: MODTRAN component radiances users expect to inspect (ground-reflected et al.) are parsed then silently dropped; deck-rendering knobs are reachable only by constructing `ModtranConfig` in Python.
**Why it still matters**: Rule 16 inspectability for MODTRAN products; a schema-generated GUI cannot express path type, irradiance mode, or spectral range for the binary flavor.
**Suggested fix**: stand-alone task when the binary flavor becomes exercisable — thread `ground_reflected` into stage outputs (inspection-only) and add ParameterDefs for the deck knobs. Effort S-M; category B.

### CU-089 — `ruff check tests/` fails with 18 pre-existing errors (lint gate covers src/ only)

**Discovered**: Gap 67 persistence task (pre-commit gate run), 2026-07-11
**Status**: Open
**File**: `tests/integration/` (e.g. `test_dual_path_mtf.py:178` unused variable, `test_no_atm_subcases.py:32` unsorted imports; 18 errors total, 11 auto-fixable)
**Symptom**: `ruff check tests/` reports 18 errors; the CLAUDE.md gate is `ruff check src/`, so the root `tests/` tree is unlinted and drifting.
**Why it still matters**: lint drift in the integration suite hides real defects (the unused-variable class) and makes new-test review noisier; the gate's src/-only scope is undocumented.
**Suggested fix**: inline-fix-now — run `ruff check tests/ --fix`, hand-fix the remainder, and widen the documented gate (CLAUDE.md "Running Tests Locally") to `ruff check src/ tests/`. Effort S; category A.

### CU-065 — Card 3 ANGLE convention suspect (path zenith written unconverted)

**Discovered**: MODTRAN_Run_Matrix_Plan §6 PW-3 (deck-builder audit), 2026-07-10, commit `fe57c74`
**Status**: DEFERRED, NARROWED 2026-07-11 — the **deck-side conversion is implemented** (commit `2e707c7`): `render_tape5` now converts RADIANT's lower-endpoint path zenith to the believed-correct at-H1 convention (downlooking → `180° − zenith`, nadir-from-space renders 180; uplooking unchanged), with Level-0 tests (180 / 150 / 48.2 cases) and agreement with the run matrix's hand-worked `modtran_angle_at_h1_deg` column on all ITYPE=2 rows; `render_modtran_decks.py` reads ANGLE back from the rendered deck and its manifest caveat now flags only the four Block-E rows (ANGLE driven by solar geometry, not path zenith). **Remaining residue**: confirm the at-H1 convention against the MODTRAN user manual — the run-matrix column it now matches is itself best-effort. Gating condition: MODTRAN access (manual). Re-audit: on access, alongside CU-011 — first real run must start with this check.
**File**: `src/radiant/atmosphere/modtran.py` (`render_tape5`, Card 3)
**Symptom (pre-fix, for the record)**: RADIANT's `path_zenith_rad` was written directly as MODTRAN's ANGLE, but MODTRAN measures ANGLE from zenith **at H1 (the sensor)**: a nadir-looking space sensor needs ANGLE = 180°, not 0°.
**Why it still matters**: the rendered decks in `modtran/decks/` are what will be handed to whoever runs real MODTRAN; a convention error there silently corrupts every slant-path validation run, since tape7 parses fine either way.
**Suggested fix (remaining)**: on manual access, verify the at-H1 convention (and the E-block solar-geometry ANGLE handling) field-by-field; then close. Effort S; category C.

### CU-067 — Card 1's inline field-name comment does not align with its own token positions

**Discovered**: implementing CU-064 (IEMSCT threading), 2026-07-10 — reverse-engineering which token is IEMSCT to add `ModtranConfig.iemsct` surfaced that `render_tape5`'s inline comment (`# Card 1: MODRAN, SPEED, BINARY, LYMOLC, MODEL, T_BEST, ITYPE, IEMSCT, IMULT`) cannot be paired index-for-index with the 14 literal tokens the function writes — e.g. the name-list's 4th entry, LYMOLC (a molecular-band-model flag), would land on the token that is actually the atmosphere `MODEL` code, which is meaningless as LYMOLC.
**Status**: DEFERRED — same gate as CU-065 (needs the MODTRAN manual + a real run to verify Card 1's true field grammar); not urgent because IEMSCT's actual position was independently re-derived from the function's own prose docstring ("ITYPE=2 ... IEMSCT=2 ... IMULT=1"), which uniquely identifies it as the second of two consecutive `2` tokens — CU-064 shipped using that (documented, best-effort) identification, not the stale name list. Gating condition: MODTRAN access. Re-audit: on access, alongside CU-011/CU-065 — verify Card 1 field-by-field against the manual in the same pass.
**File**: `src/radiant/atmosphere/modtran.py` (`render_tape5`, Card 1 comment + token construction)
**Symptom**: the documentation comment above Card 1 is not a reliable map from field name to token index; a future reader (or agent) editing Card 1 by trusting that comment literally risks writing to the wrong field, the same failure class as CU-065's ANGLE bug but for the whole card, not just one field.
**Why it still matters**: Card 1 carries MODEL, ITYPE, IEMSCT, IMULT — the four fields every run in the matrix depends on; an undetected misalignment here is not a niche corner case.
**Suggested fix**: when MODTRAN access arrives, rebuild Card 1 field-by-field against the manual's true FORTRAN format spec, replace the stale inline comment, and add a Level-0 test asserting each field's token position directly (not just substring presence). Effort S; category C.

### CU-070 — MODTRAN cache key omits the binary version (silent stale cache after upgrade)

**Discovered**: CU-068 doc rewrite, 2026-07-11 — the old §5.3 documented `cache_key = sha256(tape5 + modtran_version)`, but the shipped `_cache_key` hashes the tape5 alone.
**Status**: DEFERRED — same gate as CU-011/CU-065/CU-067 (needs a real MODTRAN binary to even obtain a version string; the invocation path has never run). Re-audit on MODTRAN access, alongside the first real run.
**File**: `src/radiant/atmosphere/modtran.py` (`_cache_key`)
**Symptom**: two different MODTRAN versions producing different physics for the same deck hash to the same cache key; after upgrading the binary, RADIANT silently serves results computed by the old version.
**Why it still matters**: violates the reproducibility intent the cache was designed for; a version-driven physics change would be invisible.
**Suggested fix**: include the binary's version string (e.g. `modtran -version` output, or executable hash as a fallback) in the hash input; document the cache-directory flush as the interim workaround (now noted in `RADIANT_Atmosphere.md` §5.4 — renumbered from §5.3 when the tape7-import §5.1 landed). Effort S; category A.

### CU-071 — `ModtranAtmosphere._build_state_from_arrays` clips τ and L_path silently (Rule 17)

**Discovered**: tape7 file-import task (`atmosphere.modtran.tape7_path`), 2026-07-11 — the import path routes through the same array→state builder the cache-hit path uses, which made the existing silent clamp newly reachable from user-supplied files.
**Status**: Open
**File**: `src/radiant/atmosphere/modtran.py` (`_build_state_from_arrays`: `np.clip(source_transmittance, 0.0, 1.0)`, `np.maximum(source_path_radiance, 0.0)`)
**Symptom**: a tape7 (or cached array) with τ > 1 or negative path radiance — a unit-confusion or corrupt-file signature — is silently snapped into range instead of warning or raising. Contrast: `TabulatedAtmosphere.__post_init__` raises `AtmosphereValidationError` on the identical condition, and `AtmosphericQuantities.__post_init__` (Rule 17 note) explicitly forbids silent clipping.
**Why it still matters**: with the tape7 import now a first-class user-facing path, a mis-scaled file (e.g. radiance in W/cm² not converted) would produce a plausible-looking but wrong state with no diagnostic. Rule 17 requires at minimum a `UserWarning` when clipping to valid ranges.
**Suggested fix**: inline-fix-now — validate the arrays before clamping: raise (matching `TabulatedAtmosphere`) for gross violations beyond a float-noise tolerance, keep the clamp only for ≤1e-12-level snap. Effort S; category B.

### CU-011 — MODTRAN backend's `evaluate()` aliases two-leg τ (single-τ adapter)

**Discovered**: Option C Stage 3 (2026-04-19)
**Re-audited**: 2026-04-24 (Stage 6 has landed); 2026-04-26 (refreshed after CU-009 escalation); 2026-07-11 (file-import flavor resolved — see below)
**Status**: DEFERRED, NARROWED 2026-07-11 — the **file-import flavor is resolved** (commit `dc348f7`, on top of the tape7-import base `4f624dc`): `atmosphere.modtran.tape7_sun_path` supplies `tau_sun` from a sun-leg tape7 file independently of `tau_up`, kills the single-τ `UserWarning` for that case, and is integration-tested against the synthetic A1(up)+B1(sun) pair (`tests/integration/test_modtran_tape7_import.py`). What remains deferred: (a) the **binary-invocation flavor** — a second MODTRAN run keyed on `(los.h_tgt, los.theta_s)` with θ_s in the cache key — and (b) **physics parity validation** against real MODTRAN output (synthetic tape7s cannot close this per `modtran/synthetic/README.md`). Gating condition: MODTRAN access. Re-audit: 2026-10-01 or on access, whichever comes first. Prior context: CU-009 landed the producer side (`d846f07`); Stage 6 (E_sky decomposition, `b9244fd`) landed the consumer side.

**File**: `src/radiant/atmosphere/modtran.py`
**Symptom (as of 2026-07-11)**: without a sun-leg file, `evaluate()` still emits the `UserWarning` and sets `tau_sun = tau`, `tau_up = tau.copy()`, `tau_full_up = tau.copy()`, `L_path_up = lpath`, `L_path_full = lpath.copy()` from a single tape7. The binary path has no second-run mechanism.
**Why it still matters**: VIS/NIR reflective scenarios that route through the MODTRAN **binary** flavor (or a single-file import) still lose the solar-zenith dependence that Stage 6's E_sky decomposition exposes. The analytic backend is fine; the file-import flavor is fine when both files are supplied.
**Suggested fix (remaining)**: stand-alone Category C task on MODTRAN access — second MODTRAN invocation keyed on `(los.h_tgt, los.theta_s)`, θ_s in the cache key, plus real-tape7 parity validation. Expect a Cell 28/58 re-baseline conversation if any MWIR snapshot scenario routes through MODTRAN with non-zero θ_s (today both anchors use the analytic atmosphere; no-op for them).

### CU-024 — Sun-zenith readout: `θ_s` (target) and `θ_sun,B` (background) collapse to identical values in flat-ground display

**Discovered**: Geometry GUI Phase 10 (2026-04-26)
**Status**: DEFERRED (refreshed 2026-07-10, Backlog_Closure_Plan Wave 0) — owner: GUI work imminent but not now. Gating condition: Geometry-GUI-v2 track restart. Re-audit: at GUI kickoff or 2026-09-01, whichever comes first. Previously: flagged in PLAN.md §12 Phase-11 plan "Phase-10 CU sweep candidates".

**File**: `dev_tools/geometry_gui/app/view_model.py` (`_READOUT_FORMATTERS` `ro-solar-zenith` row); `dev_tools/geometry_gui/app/scene_builder/{sun_zenith_arc,solar_zenith_arc}.py`
**Symptom**: Both arc helpers (`sun_zenith_at_target_rad(s_unit)` and `solar_zenith_at_b_rad(n_B, s_unit)`) reduce to `arccos(s_z)` whenever the surface normal at B equals `+ẑ` — which is *every* state the GUI currently renders, since the display assumes flat ground. The two on-figure labels (`θₛ` at target and `θ_sun,B` at the background point) sit at different anchors but encode the same numeric angle, and the readout panel shows only one row labeled "Solar zenith" without disambiguating which of the two physically-distinct angles is being read out.
**Why it still matters**: this is a *display* limitation, not a physics bug — the helpers are correct. The audit hit is that the GUI presents two visually-distinct decorations as if they were independent measurements, which would mislead a user driving a non-flat-ground scenario. The moment Phase 12+ adds ground-tilt or oblique-surface support (i.e., `n_B ≠ +ẑ`), `θ_sun,B` will diverge from `θ_s` and the readout panel needs to label them separately.
**Suggested fix**: stand-alone Category B task — (a) add a `target_surface_normal` field to `SceneState` (default `+ẑ`); (b) split the readout row into `Solar zenith at target (θ_s)` and `Solar zenith at B (θ_sun,B)`; (c) on-figure label for `θ_sun,B` becomes redundant when `n_B = +ẑ` exactly — suppress the second arc in that case to avoid visual duplication. Tests: when normal is non-axial, both rows surface, both arcs render, and the values differ. Block on Phase 12+ scope (no current consumer). Re-audit date: 2026-08-15 (calendar backstop; earlier if Phase 12+ ground-tilt/oblique-surface scope lands).

### CU-025 — Camera auto-frame is anchored to default-state geometry constants

**Discovered**: Geometry GUI Phase 11 (2026-04-26)
**Status**: DEFERRED (refreshed 2026-07-10, Backlog_Closure_Plan Wave 0) — owner: GUI work imminent but not now. Gating condition: Geometry-GUI-v2 track restart. Re-audit: at GUI kickoff or 2026-09-01, whichever comes first. Previously: design choice — the coupling needs capturing before the display constants change in isolation.

**File**: `dev_tools/geometry_gui/app/scene_builder/_camera_frame.py` (`REFERENCE_HALF_EXTENT = 6.0`)
**Symptom**: Phase-11 (d) introduces auto-framing via a bounding-box scan over all base-scene traces; the eye distance scales as `max(1.0, half_extent / REFERENCE_HALF_EXTENT)`. The constant `6.0` was hand-calibrated against the default state's bbox (driven by `OBSERVER_DISPLAY_DISTANCE = 4.0` and `SUN_DISPLAY_DISTANCE = 6.0` in `_display_constants.py`). Any future change to either display distance silently breaks the "default state framing matches Phase-10" invariant guarded by `tests/test_phase11_polish.py::test_camera_default_state_eye_unchanged`.
**Why it still matters**: a developer who bumps `OBSERVER_DISPLAY_DISTANCE` to make the observer chip more readable will trip the camera-frame test, but the failure message will point at `_camera_frame.py` rather than at the display constant they actually edited. The cross-module coupling is correct (the camera *must* track the bbox) but undocumented at the code-comment level.
**Suggested fix**: inline-fix-now — add a one-line comment on `REFERENCE_HALF_EXTENT` linking it to `OBSERVER_DISPLAY_DISTANCE` / `SUN_DISPLAY_DISTANCE` and noting that any change to those constants requires re-calibration. Optional follow-up: derive `REFERENCE_HALF_EXTENT` programmatically from the default-state bbox at import time, eliminating the manual constant. Effort: < 30 LOC; Category A. Re-audit date: 2026-08-15 (calendar backstop; earlier if the next PR touching `dev_tools/geometry_gui/app/scene_builder/` picks up the inline fix).

### CU-052 — GUI v2 headlining slider work (Phase-7 deferral; formerly README "CU-043")

**Discovered**: Geometry GUI v2 Phase 7 deferral list (2026-05-02); re-filed 2026-07-06 during loose-end cleanup (the README's CU number was never allocated in this registry).
**Status**: DEFERRED (refreshed 2026-07-10, Backlog_Closure_Plan Wave 0) — owner: GUI work imminent but not now. Gating condition: Geometry-GUI-v2 track restart. Re-audit: at GUI kickoff or 2026-09-01, whichever comes first.
**File**: `dev_tools/geometry_gui_v2/app/panels/parameters.py`
**Symptom**: the parameters panel's slider interaction work ("headlining slider work" per `dev_tools/geometry_gui_v2/README.md` Phase-7 deferrals) is deferred; it gates the performance and memory test passes (CU-053, CU-054).
**Why it still matters**: Phase 7 (hardening + handoff) cannot complete its acceptance bundle without it; two downstream CUs are blocked on it.
**Suggested fix**: stand-alone task per `docs/plans/Geometry_GUI_v2_Plan.md` Phase 7. Effort M; category A (GUI tooling).

### CU-053 — GUI v2 performance pass (Phase-7 deferral; formerly README "CU-044")

**Discovered**: Geometry GUI v2 Phase 7 deferral list (2026-05-02); re-filed 2026-07-06.
**Status**: DEFERRED (refreshed 2026-07-10, Backlog_Closure_Plan Wave 0) — owner: GUI work imminent but not now. Gating condition: Geometry-GUI-v2 track restart. Re-audit: at GUI kickoff or 2026-09-01, whichever comes first. Blocked on CU-052.
**File**: `dev_tools/geometry_gui_v2/` (scene rebuild path)
**Symptom**: no performance test pass exists for interactive scene rebuilds; deferred from Phase 7 pending the slider work that would exercise it.
**Why it still matters**: the tool is the visual-design prototype for the production GUI's geometry tab; rebuild latency regressions land silently without a gate.
**Suggested fix**: stand-alone task per `docs/plans/Geometry_GUI_v2_Plan.md` Phase 7, after CU-052. Effort S–M; category A.

### CU-054 — GUI v2 memory pass (Phase-7 deferral; formerly README "CU-045")

**Discovered**: Geometry GUI v2 Phase 7 deferral list (2026-05-02); re-filed 2026-07-06.
**Status**: DEFERRED (refreshed 2026-07-10, Backlog_Closure_Plan Wave 0) — owner: GUI work imminent but not now. Gating condition: Geometry-GUI-v2 track restart. Re-audit: at GUI kickoff or 2026-09-01, whichever comes first. Blocked on CU-052.
**File**: `dev_tools/geometry_gui_v2/` (actor lifecycle)
**Symptom**: no memory-leak pass over repeated scene rebuilds (VTK actor churn); deferred from Phase 7 pending the slider work that would exercise it.
**Why it still matters**: long-lived desktop sessions with continuous parameter dragging will surface any actor leak; no gate exists.
**Suggested fix**: stand-alone task per `docs/plans/Geometry_GUI_v2_Plan.md` Phase 7, after CU-052. Effort S–M; category A.

### CU-056 — GUI v2 sun glyph uses world-space sizing, not screen-space (formerly docstring "CU-046")

**Discovered**: Geometry GUI v2 round-2 remediation (sun glyph rework); re-filed 2026-07-06 during loose-end cleanup (the docstring's CU number was never allocated in this registry and collided with the README's CI-deferral phantom).
**Status**: DEFERRED (refreshed 2026-07-10, Backlog_Closure_Plan Wave 0) — owner: GUI work imminent but not now. Gating condition: Geometry-GUI-v2 track restart. Re-audit: at GUI kickoff or 2026-09-01, whichever comes first.
**File**: `dev_tools/geometry_gui_v2/scene/glyphs/sun.py`
**Symptom**: the sun disc + rays are sized in world space (tuned to ~24 px / 8 px at the round-2 default camera distance); zooming scales the glyph with the scene instead of holding fixed pixel size.
**Why it still matters**: icon-style glyphs are meant to read at constant screen size; at extreme zoom the sun either dominates the viewport or vanishes.
**Suggested fix**: stand-alone small task — screen-space sizing via `vtkActor2D` or a camera-change callback, per the file docstring's deferral note. Effort S; category A.

## Resolved

### CU-091 — Signal_Chain §5 frame table drifted from the shipped `ReferenceFrame` enum — RESOLVED 2026-07-12 (commit `6a0afce`)

**Discovered**: RADIANT_Spectral_Integration.md / RADIANT_Reference_Frames.md doc-authoring pass, 2026-07-12. **Resolution**: reconciled RADIANT_Signal_Chain_Architecture.md §5's reference-frame table with the shipped six-member `ReferenceFrame` enum — dropped the `at_fpa` row (focal-plane irradiance lives only as the optics stage-outputs `nearfield_irradiance_at_fpa` / `stray_light_irradiance_at_fpa`, not a frame), renamed the post-integration frame `electrons`→`photoelectrons`, clarified the six enum members are *query positions* distinct from the `RadiometricFrame` snapshots in `state.frames`, and noted `at_target` is reachable via the τ_atm factor not a stored snapshot. Fixed the §3 `RadiometricFrame.name` comment and updated the drift notes in the two new docs. Adjacent §5 `forward_factor`-storage claim split out as CU-092.

### CU-076 — String-mode parameters lacked enum validation — RESOLVED 2026-07-12 (commit `513c9c5`)

**Discovered**: Capability audit 2026-07 (F-25), 2026-07-11. **Resolution**: added `enum_values` to `readout.tdi_mode` (`analog`/`digital`) and `detector.noise_regime` (`imaging`/`detection`). A typo (e.g. `tdi_mode='Digital'`, `noise_regime='Detection'`) now raises a `CoreValidationError` at resolve naming the allowed values, instead of silently falling through to analog scaling / imaging (spatial noise dropped). All existing usages verified to use valid values.

### CU-081 — Dark current temperature-inert by default — RESOLVED 2026-07-12 (commit `513c9c5`)

**Discovered**: Capability audit 2026-07 (F-18), 2026-07-11. **Resolution**: `detector.dark_reference_temperature_K` default changed 300 K → 77 K to match the `detector_temperature_K` default, so the default config is self-consistent (no reference/operating mismatch). `DetectorStage` now warns when `detector_temperature_K` differs from the reference while `dark_activation_energy_eV = 0` — the temperature setting (e.g. a GUI slider) is otherwise silently inert. With the default `E_a = 0` the computed `dark_e` is unchanged, so the golden baseline is unaffected. Material-keyed activation-energy presets remain a future enhancement (pairs with Gap 69).

### CU-088 — LWIR aerosol Ångström extrapolation clamp — RESOLVED 2026-07-12 (commit `eb22d5c`)

**Discovered**: Capability audit 2026-07 (F-19), 2026-07-11. **Resolution**: `SimpleAtmosphere._aerosol_extinction_km` clamps the Ångström power law at `AEROSOL_CLAMP_WAVELENGTH_UM = 5.0 µm` (the MWIR–LWIR boundary): for λ > 5 µm the extinction is frozen at its 5 µm value instead of decaying unphysically toward zero, and a `UserWarning` fires once per run when the clamp engages. The boundary was placed at MWIR–LWIR (not the originally-doc-planned SWIR–MWIR / 3 µm) so the "weak but usable" MWIR power law and the flagship MWIR golden are preserved while only the genuinely-wrong long-wave extrapolation is corrected. Doc §12 updated in lock-step.

### CU-079 — "Authoritative" architecture docs described unimplemented systems — RESOLVED 2026-07-12 (commits `c5a77e6`, plus Gap 71/74 banners)

**Discovered**: Capability audit 2026-07 (F-20), 2026-07-11. **Resolution**: reconciliation / DESIGN-TARGET banners added to every listed doc. `RADIANT_Scan_Timing.md` → DESIGN TARGET (Gap 74, `bdc5ca3`); `RADIANT_Metrics.md` §2 MetricResult contract → status banner (Gap 71, `68e1fec`); `RADIANT_GUI_Architecture.md` → DESIGN TARGET, the <100 ms incremental-DAG contract marked DECLINED (owner-ratified) and dot-paths flagged illustrative (`c5a77e6`); `RADIANT_Source_Target_System.md` → DESIGN TARGET, ResolvedTarget noted exported-but-unwired (CU-084) (`c5a77e6`); `RADIANT_Optics.md` §3.1/3.4/3.5 → apodization/PupilDescription/non-circular apertures marked deferred/not-in-schema (`c5a77e6`); `RADIANT_Spatial_Complete.md` → scan/target-motion smear cascade steps marked NOT IMPLEMENTED (`c5a77e6`). Anyone speccing the GUI now sees the design-vs-shipped boundary explicitly; the doc-refresh precedes GUI kickoff as required. The GUI arch dot-path refresh against shipped `_schema.py` (item 12's second half) is subsumed: the banner directs readers to `Sensor.parameter_defs()` rather than transcribing dot-paths.

### CU-075 — `scenarios/README.md` status table stale — RESOLVED 2026-07-12 (commit `268594b`)

**Discovered**: Capability audit 2026-07 (F-21), 2026-07-11. **Resolution**: regenerated the status table. All 35 persona scenarios + the two 08-series interpolation demos carry the `walkthrough.md`/`gaps.md`/`gui_workflow.md` trio and executed `inputs/scripts/outputs` (verified by script); the table now reads 37/37 implemented instead of "14 of 35" with 21 executed scenarios mislabelled "stub" and the 08 series omitted.

### CU-074 — `fill_factor` coupled inconsistently across PSF, MTF, and radiometry — RESOLVED 2026-07-11 (commit `3921e5d`)

**Discovered**: Capability audit 2026-07 (F-11), 2026-07-11. **Resolution**: `fill_factor` is now treated as the areal photosensitive fraction (per schema), so a square photosite has linear width `pitch·√FF`. That width drives BOTH Rule-4 spatial paths — the PSF-path pixel-aperture kernel (`optics/pixel_kernel`) and the MTF-product pixel sinc (`detector/stage`, previously full-pitch → divergent) — and the collecting area `pitch²·FF` scales the radiometric signal via an effective QE·FF collection (`spectral_integration/stage`, also applied to nearfield/stray). `platform/sampling` pixel MTF/kernel updated to √FF for consistency. Dual-path consistency now passes at FF=0.8 (test-enforced). At FF=1 every change is a no-op; golden unchanged. Docs: `spatial_model.md`, `RADIANT_Detector_Complete.md`.

### CU-083 — IPC kernel applied at PSF sample spacing instead of pixel pitch — RESOLVED 2026-07-11 (commit `80f1a79`)

**Discovered**: Capability audit 2026-07 (F-18; scenario 2.3), 2026-07-11. **Resolution**: new `ipc_kernel_pitch_spaced(α, Δx, pitch)` builds the IPC kernel on the PSF sample grid with the α couplings at ±pitch (linearly interpolated so the first moment is exactly at the pitch), replacing the raw 3×3 that placed them one sample away. The detector stage builds it (reading `Δx` from the optics EffectivePSF via stage outputs — no cross-stage import) and stores `ipc_kernel_psf`; the performance stage applies it. PSF-path RER/FWHM/EE/MTF-at-Nyquist now show the correct IPC degradation ((1−4α) at Nyquist) and the dual-path consistency check passes (max_err ~1.6e-3). Raw 3×3 `ipc_kernel` retained for provenance. At `ipc_coupling=0` (default) no kernel is built; golden unchanged. Docs: `RADIANT_Spatial_Complete.md` §6.

### CU-072 — Parallel sweep (`n_workers>1`) crashed with unhandled PicklingError — RESOLVED 2026-07-11 (commit `537a3a8`)

**Discovered**: Capability audit 2026-07 (F-06), 2026-07-11. **Resolution**: pickling failures are now caught at both submit time and `fut.result()` time (`PicklingError`, `BrokenProcessPool`, `TypeError`, `AttributeError`) and the sweep re-runs sequentially with a logged warning — the documented fallback, previously unreachable. Regression tests cover both the unpicklable-callable and the unpicklable-*result* (MappingProxyType ChainResult) cases.

### CU-073 — Unknown-parameter errors were bare `KeyError`, not `RadiantError` — RESOLVED 2026-07-11 (commit `537a3a8`)

**Discovered**: Capability audit 2026-07 (F-07), 2026-07-11. **Resolution**: new `UnknownParameterError(RadiantError, KeyError)` raised by `ParameterSet.set/get/clear_input/set_tolerance/parameter_def`, preserving the did-you-mean suggestion and `except KeyError` back-compat. `Sensor.set` typos now land inside `except RadiantError` (test-enforced in `tests/test_exceptions.py`). CLAUDE.md Rule 15 class list updated.

### CU-078 — Metric registry drifted: declared metrics never computed, zero production consumers — RESOLVED 2026-07-11 (commit `68e1fec`)

**Discovered**: Capability audit 2026-07 (F-04), 2026-07-11. **Resolution**: folded into the Gap 71 metric-contract work as the audit suggested. Registry reconciled to exactly the 32 keys `PerformanceStage` computes (phantoms nedl/nedr/edge_slope/detection_range/csnr and misnamed nedt/ee/saturation_margin/dynamic_range removed; real keys registered with units/descriptions/kinds). Production consumer wired: `ChainResult.metric_records()` reads the registry on every metric render. Drift now fails CI via `tests/integration/test_metric_registry_reconciliation.py` (unregistered computed key, or `can_compute` returning False for a computed key).

### CU-086 — Re-audit PROVISIONAL atmosphere/MODTRAN audit findings after concurrent rework lands — RESOLVED 2026-07-11 (commit `bf70f73`)

**Discovered**: Capability audit 2026-07 (F-19), 2026-07-11. **Resolution**: re-audit executed 2026-07-11 against the landed MODTRAN rework (`d56fd9c`), correction doc `docs/reports/capability_audit_2026-07/2026-07-11_modtran_reaudit.md`; every PROVISIONAL finding dispositioned (grep-verified): **(1) two-leg collapse** — resolved by `tape7_sun_path` (dc348f7). **(2) Downwelling zeroed** — survives → **Gap 81**. **(3) E_sky_scattered zeroed** — survives → folded into **Gap 81**. **(4) Parsed tape7 columns dropped + remaining ModtranConfig knobs unwired** — survives (narrowed: `visibility_km` now wired) → **CU-087**. **(5) No cloud/rain** — survives → **Gap 82**. **(6) LWIR aerosol clamp unimplemented** — survives → **CU-088**. **(7) Uplooking geometry rejection** — Declined, owner-ratified 2026-07-11. **(8) CU-071 silent clamp** — unchanged, stays open. Registry updates and correction doc landed in `bf70f73`.

### CU-068 — `RADIANT_Atmosphere.md` §5.2's `ModtranNativeOutput` code sample doesn't match the shipped dataclass — RESOLVED 2026-07-11 (commit `c349ea1`)

**Discovered**: Rule-20 lock-step check while landing CU-066, 2026-07-10. **Resolution**: §5 rewritten wholesale to match shipped code — the drift was broader than the flagged dataclass sample: nonexistent `radiant.io.modtran_reader` module, phantom `ModtranCardDeck.render()` (actual: `ModtranConfig` + `render_tape5()`), wrong Card 1A/3A1 field claims, wrong cache-key formula (documented tape5+version; actual tape5 only — the version omission filed as CU-070, deferred on MODTRAN access), wrong cache storage (documented raw `.tape7`; actual parsed `.npz` arrays), fictional `radiant atm clear-cache` CLI, wrong `to_radiant_units` return type (documented three `SpectralData`; actual four `np.ndarray`s), and a `ModtranUnavailableWarning` class that never existed. The unimplemented richer radiance decomposition is now explicitly marked future work, and §5 opens with a verification-status caveat (no real deck ever run; CU-065/CU-067 open).

### CU-069 — `ModtranConfig.itype` was hardcoded, blocking Block E irradiance runs — RESOLVED 2026-07-10 (commit `41c3afb`)

**Discovered**: while rendering the full 39-run tape5 deck set from `modtran_run_matrix.csv` (post-CU-064), 2026-07-10. **Resolution**: `ModtranConfig.itype: int = 2` (validated to MODTRAN's defined {1,2,3}) threads to Card 1 alongside `iemsct`; default reproduces the pre-change deck byte-for-byte. Unblocks run-matrix rows E1–E4, which need ITYPE=3 (slant path to space) together with IEMSCT=3.

### CU-066 — `Tape7Reader` column mapping is positional and mismatches the real IEMSCT=2 layout — RESOLVED 2026-07-10 (commit `0927f57`)

**Discovered**: tape7-format review against the MODTRAN 4/5 manual layout (follow-on to MODTRAN_Run_Matrix_Plan §6), 2026-07-10. **Resolution**: `Tape7Reader` locates columns by header label (left-to-right order of appearance, not token index) via `_locate_tape7_columns`; a header missing a required label raises `Tape7ParseError`; data ingestion starts strictly after the located header line so numeric card-echo lines can't be mistaken for data. Headerless files fall back to the pre-fix positional mapping with a `UserWarning`. New regression tests (`TestTape7ReaderNamedColumns`) prove SOL SCAT/GRND RFLT are correctly distinguished from the THRML SCT/SURF EMIS decoys and that card-echo lines are excluded. Final verification against a real tape7 still lands with run A1 (fixture-based coverage only, per the standing no-fabricated-MODTRAN-data constraint).

### CU-063 — `ModtranConfig` has no visibility field (Card 2 hardcodes `VIS 0.000`) — RESOLVED 2026-07-10 (commit `0927f57`)

**Discovered**: MODTRAN_Run_Matrix_Plan §6 PW-1 (deck-builder audit), 2026-07-10, commit `fe57c74`. **Resolution**: `ModtranConfig.visibility_km: float | None = None` threads to Card 2 VIS; `None` preserves the exact pre-change deck (validated byte-for-byte). Unblocks run-matrix rows D1, D3, D6, E4.

### CU-064 — Deck builder has no solar-irradiance mode (IEMSCT = 2 only) — RESOLVED 2026-07-10 (commit `0927f57`)

**Discovered**: MODTRAN_Run_Matrix_Plan §6 PW-2 (deck-builder audit), 2026-07-10, commit `fe57c74`. **Resolution**: `ModtranConfig.iemsct: int = 2` (validated to MODTRAN's defined {0,1,2,3}) threads to Card 1; default reproduces the pre-change deck byte-for-byte. Unblocks run-matrix rows E1–E4. The exact token position was re-derived from `render_tape5`'s prose docstring, not its stale inline name-list comment (see CU-067, filed as a follow-on and deferred to MODTRAN access like CU-065).

### CU-044 — Hardcoded tuneable quantities in physics modules (Rule 12) — RESOLVED 2026-07-10 (commit `c0febaf`)

**Discovered**: architecture audit 2026-07-06, branch `fix/architecture-audit-2026-07`. **Resolution**: Backlog_Closure_Plan Wave 4. IFOV regime decision boundaries deduped into `core/regime.py` (`REGIME_EXTENDED_IFOV_MULTIPLE`, `REGIME_POINT_SOURCE_IFOV_MULTIPLE`), imported by both former literal sites (`source/stage.py`, `source/_inferrer.py`); `optics/stage.py` PSF-FWHM finalization multipliers named locally (different basis, deliberately not shared); `performance/giqe.py` inline `0.0254` → `_M_PER_INCH` (NIST SP 811; GIQE-5 coefficients were already named); `detector/ipc.py` ceiling → `IPC_COUPLING_MAX` with the 1−4α>0 justification. Re-audited already conformant, no change: `atmosphere/simple.py` constant block and `brightness_temperature.py` thresholds (fixed by intervening work since the audit). No new `ParameterDef`s — every audited quantity is a published/definitional constant or a classification convention; user tuneability already exists where relevant (`source.regime_override`). Values unchanged, results bit-exact.

### CU-008 — Stage-2 `GroundBackground` placeholder is grey, not spectral — RESOLVED 2026-07-10 (commit `76b8bd1`)

**Discovered**: Option C Stage 2 (2026-04-19); escalated to `docs/reports/cu_tasks/CU-008_GroundBackground_Spectral_Task.md`. **Resolution**: task-doc Approach 1, adapted — the placeholder is replaced by a spectral ε_g(λ) surface: `source.background.emissivity_path` (CSV, wins) → `source.background.material` (named `radiant.data.SpectralLibrary` entry — the existing 19-material library supersedes the task doc's envisioned 3-entry YAML, Rule 27) → scalar grey back-compat (default, exact pre-CU-008 behavior, placeholder warning removed). Resolution happens in the API layer pre-chain (Rule 6) and injects via `stage_outputs["source_config"]["background_emissivity"]`; the inferrer resamples with a [0,1] validity check. Task-doc anchors A1–A6 covered; stop triggers held (all 14 baselines + Cells 28/58 bit-invariant, 1033 tests).

### CU-003 — Pre-existing MTF tolerance warning on `swir_aerial_gas.yaml` — RESOLVED 2026-07-10 (commit `2d5da44`, investigation option a)

**Discovered**: Option C era (2026-04); investigation completed 2026-07-07 with a three-way owner decision. **Resolution** (owner-directed close-the-backlog directive, Backlog_Closure_Plan Wave 2): option (a) — the pixel-aperture rect kernel is sampled by exact area overlap (anti-aliased edges) instead of a binary mask. Options (b) band-limited kernel and (c) sinc-envelope on the analytic reference were rejected for trading away PSF nonnegativity and path independence respectively. Measured: FFT-vs-analytic-sinc at Nyquist 4.5e-2 → 3.6e-3 (13×, the irreducible sinc(πfΔ) bin-average floor of any nonnegative sampled kernel); worst full-chain dual-path residual 5.8e-2 → 9.5e-3. Option-C MTF@Nyquist anchors repinned with provenance (+5.6%/+7.9% — the binary kernel over-blurred); radiometric goldens unaffected. `swir_aerial_gas`-class configs no longer warn.

### CU-045 — Dual-path consistency check gating: warn-only at tolerance 5e-2 — RESOLVED 2026-07-10 (commit `2d5da44`)

**Discovered**: architecture audit 2026-07-06; blocked on CU-003. **Resolution**: with CU-003 landed, the default tolerance is tightened 5e-2 → 2e-2 (~2× margin over the worst measured full-chain residual, 9.5e-3 at undersampled Q ≈ 0.2 VNIR). Gating decision: the check **stays warn-only by design** — it is a diagnostic invariant guarding the build, and raising would abort user runs whose physics is otherwise valid; the loud `UserWarning` plus the `dual_path_consistency` stage output remain the surfaced contract. Decision recorded in `consistency_check.py`, CLAUDE.md Rule 4, and RADIANT_Spatial_Complete.md. Full corpus passes under the tightened tolerance (784 tests).

### CU-005 — `theta_o_from_eta` boundary converter is unwired — RESOLVED 2026-07-09 (commit `c8a6f70`, resolution option b)

**Discovered**: Option C Stage 1 (2026-04-19); unblocked when CU-009 landed (`d846f07`). **Resolution** (owner-directed, Backlog_Closure_Plan Wave 1): option (b) — the η-input surface (`geometry.sensor_off_nadir_rad` routed through `theta_o_from_eta`, with a precedence rule against `geometry.path_zenith_rad`) is **deliberately deferred behind the SensorDescriptor ADR** rather than adding a second, redundant way to specify the same look geometry today. Users supply the target-side zenith directly via the canonical `geometry.path_zenith_rad` (CU-009). The decision is recorded in the `core/los_geometry.py` module docstring; the converter remains tested (`core/tests/test_los_geometry.py`) and reserved for the SensorDescriptor follow-on.

### CU-043 — Rule 15 error-type migration: 428 bare `raise ValueError/RuntimeError` across core + physics — RESOLVED 2026-07-09 (commit `d9de472`)

**Discovered**: architecture audit 2026-07-06. 428 bare built-in raises (grown from 398 at audit) meant `except RadiantError` missed most framework rejections — the CU-018 contract was hollow. **Resolution**: stage-scoped `<Stage>ValidationError(RadiantError, ValueError)` classes (plus `RuntimeError`-co-inheriting StateError variants for core/atmosphere/spectral_integration) added per package in `errors.py` (`Core*` in `core/exceptions.py`); all 428 sites mechanically migrated with imports. Co-inheritance is the sanctioned Rule 15 back-compat carve-out, so the full suite (3287 tests, including every `pytest.raises(ValueError)`) passes unmodified — zero behavioral change. Regression guard `TestNoBareBuiltinRaises` scans the tree and forbids new bare raises. Gates: mypy --strict core+api, ruff, import-linter 5/5 (one sanctioned edge added: `api.errors → core.exceptions`). Note: messages were migrated as-is; upgrading individual messages to the full structured what/why/action/context payload remains incremental follow-on work at the sites that matter, not a blocking part of this CU.

### CU-058 — Defocus violated Rule 4: scalar-RMS WFE dropped from the MTF product path; two paths used different defocus models — RESOLVED 2026-07-09 (commit `f5c8fda`)

**Discovered**: Scenario 7.3 refresh (Phase R), 2026-07-07. Scalar WFE + defocus configs structurally failed the dual-path consistency check (7.3: max_err 0.169 vs tol 0.05 on every run): the product path's `_add_defocus_to_wfe` discarded the scalar-RMS screen when folding defocus to Z4, and the PSF path modeled defocus as a Gaussian kernel while the product path used pupil Z4. **Resolution**: defocus now folds into the pupil WFE once in `_build_effective_psf` (screen preserved, Z4 alongside), and all pupil-phase construction goes through one shared dispatch (`pupil_phase.make_pupil_phase_for_wfe`) — FFT{PSF} equals the pupil autocorrelation by Wiener–Khinchin, so Rule 4 holds by construction. The Gaussian kernel, the `defocus_sigma_m` output, and the unwired `optics/defocus.py` module were removed (Rule 27); a latent reference-wavelength bug in the Z4 fold was also fixed. Tests: `tests/integration/test_defocus_dual_path.py` (the 7.3 signature passes) + optics-stage tests; 937 passed, goldens unaffected (defocus_um=0 bit-identical). Scenario 7.3 refreshed under the fix (`bc2508d`) as closure evidence; owner approved the canonical model in-session.

### CU-060 — Sub-pixel scenario 1.3 did not set `source.target.fill_fraction` — RESOLVED 2026-07-09 (commit `c45be49`)

**Discovered**: Scenario 4.1 execution (Phase T3), 2026-07-08. The sub-pixel regime weights the target by `fill_fraction` (default 1.0), not `projected_area_m2`; scenario 1.3's 31%-fill hotspot was modeled as pixel-filling, overstating fire signal ~3×. **Resolution**: `build_sensor` now sets `fill_fraction = min(1, A_target/footprint)`; walkthrough/figures/manifest refreshed (600 K SCNR 844→449 MWIR, 123→38 LWIR; saturation ≈800/900 K → ≈1200 K both bands; new finding — LWIR misses 400 K smolders, P_d 0.057). Audit item (b) complete: 4.1 is the only other sub-pixel scenario and already sets it correctly. The framework-side mitigation (derive-or-raise on default fill in sub_pixel) was not filed — one recurrence across two scenarios; re-file if it recurs.

### CU-059 — Executed-scenario outputs and walkthrough numbers predated the current physics — RESOLVED 2026-07-09 (commits `924b9e1`, `9145941`, `55d1c76`, `5e0df97`, `ea4917f`, `84ad9cf`, `a72013e`, `1d35a82`, `da04139`)

**Discovered**: Phase R verification sweep, 2026-07-07. The 10 non-Phase-R executed scenarios (1.4, 2.2, 2.3, 2.5, 3.2, 3.4, 5.2, 5.3, 5.4, 7.1) carried April-era figures/numbers that no longer reproduced under the current physics (column-integrated transmittance fix + Decision #13 extended background-term removal). **Resolution**: reran each script and refreshed figures + walkthrough tables + narrative + MANIFEST SHAs, one commit per scenario. Seven needed table/figure updates (1.4, 3.4, 5.2, 3.2, 5.3, 5.4, plus 2.2/2.3/7.1 walkthrough-only since their committed figures were already current); **2.5 was verified already-current (no change needed)**. Notable physics-narrative corrections: 1.4 SNR/NIIRS now *plateau* (not degrade) past TDI saturation since there is no background_shot to keep growing; 3.4/3.2/2.2/2.3/5.2/5.3/5.4 absolute SNR rose and NEDT fell with the background-term removal; 7.1 predicted NEDT dropped 100.6→74.2 mK (the old shroud background_shot was a double-count — the blackbody fills the target pixel — so its removal is correct and the predicted-vs-measured gap legitimately widens). No new gaps: the 7.1 background removal was confirmed correct, not a missing term.

### CU-061 — `contrast_snr` unreliable when the pixel saturates — RESOLVED 2026-07-09 (commit `636f17f`)

**Discovered**: Scenario 3.5 execution (Phase T4), 2026-07-09. Under saturation the readout caps the signal (and its shot noise) at full well, but the contrast ΔS is not re-derived from the clipped signals, so `contrast_snr = ΔS/σ` was inflated (and could exceed the absolute `snr`). **Resolution**: `compute_contrast_snr` detects the clip param-free (`signal_e_final < signal_e`), emits a `UserWarning`, and sets `failure_reason` on the `contrast_snr_result` (`.ok` → False). The clipped differential is readout physics the metric layer cannot reconstruct (no reference-pixel clip available), so a surfaced `failure_reason` is the honest fix (Rule 17 metric-layer carve-out, ADR-B). Metric value unchanged for unsaturated runs — goldens 10/10 unaffected. Tests: `TestContrastSnrSaturation`.

### CU-062 — Veiling-glare stray light used the pixel IFOV solid angle, not the f-cone — mode was inert — RESOLVED 2026-07-09 (commit `8cb0448`)

**Discovered**: Scenario 5.5 execution (Phase T4), 2026-07-09. `OpticsStage` built the `veiling_glare` in-FOV image-plane irradiance as `L_post_optics × Ω_pixel` (pixel IFOV solid angle `pitch²/focal²`) instead of the f-cone solid angle `Ω_cone = A_collect/focal²`, under-counting stray by `A_collect/A_pixel ≈ (D/pitch)²·π/4` (~1e7–1e8) and making the mode inert. **Resolution**: `optics/stage.py` now uses `omega_fcone = aperture.clear_area_m2 / focal_length_m²`, so `stray_e = vgf·signal_e` for a uniform extended scene. Added chain-level `tests/test_veiling_glare_signal_consistency.py` and an optics-stage assertion; updated `RADIANT_Optics.md` §8 and CHANGELOG (Fixed, Results-affecting). Default fraction 0.0 → goldens unaffected (10/10).

### CU-057 — Scenario scripts import `openpyxl`, which is not a declared dependency — RESOLVED 2026-07-07 (commit `0c14c9b`)

**Discovered**: Gap_Closure_Plan WP-1.1 (scenario 7.4 rerun attempt), 2026-07-07.
**Resolution**: New `[scenarios]` optional-dependency group in `pyproject.toml` (`openpyxl>=3.1`, `matplotlib>=3.8` — matplotlib was equally undeclared for the figure outputs) + install note in `scenarios/README.md`. Verified: scenario 7.4's Excel input parsing loads on the documented install.

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
