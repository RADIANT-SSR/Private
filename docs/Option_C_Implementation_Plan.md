# Option C Implementation Plan — Staged with Per-Stage Prompts

**Date**: 2026-04-19
**Status**: Proposed
**Owner ADR**: [ADR-0002 Option C — Source/Atmosphere Split via Descriptors](adr/0002-option-c-source-atmosphere-split.md)
**Coverage target**: [RADIANT_Use_Case_Matrix.md](RADIANT_Use_Case_Matrix.md) — close the gaps in [Use_Case_gaps.md](Use_Case_gaps.md)
**Effort**: 8 PRs, ~16.5 engineering days
**Regression posture**: codebase is never broken. Stages 1–2 are additive; Stages 3–4 use shadow-mode validation; Stages 5–8 are additive expansions on a stable Option C base.

---

## Regression Strategy

We can keep regression coverage along the way. The mechanism per stage:

1. **Stages 1–2 are additive only.** No existing code path is removed; new descriptor classes and new stage_outputs sit alongside the legacy frame. Every existing test continues to pass unchanged. Zero regression risk.
2. **Stages 3–4 are the dangerous window**, mitigated by a **shadow-mode** technique: AtmosphereStage runs the new descriptor-driven assembly *and* the legacy `L·τ + L_path` path, asserts they agree on the trivial-cell goldens, and only then deletes the legacy path. The chain stays runnable end-to-end the whole time.
3. **Stages 5–8 are additive again.** Each unlocks new cells without changing existing ones.

Two known-working golden cells act as **invariant anchors** through every stage:

- **Cell 28** — terrestrial LWIR extended
- **Cell 58** — space LWIR extended

If either anchor moves, **stop and investigate** before proceeding to the next stage.

---

## Regression Invariants (enforced from Stage 0 onward)

These hold continuously and are asserted in `tests/integration/test_option_c_anchors.py`:

| Invariant | Held by | Enforced from | Reference baseline |
|---|---|---|---|
| Cell 28 SNR/NEDT/MTF/L_aperture unchanged within rtol=1e-6 | Stages 0–5 | Stage 0 | Stage 0 baseline |
| Cell 58 SNR/NEDT/MTF/L_aperture unchanged within rtol=1e-6 | Stages 0–5 | Stage 0 | Stage 0 baseline |
| Cell 28 SNR/NEDT/MTF/L_aperture unchanged within rtol=1e-6 | Stages 7–8 | Stage 6 exit | **Post-Stage-6 baseline** |
| Cell 58 SNR/NEDT/MTF/L_aperture unchanged within rtol=1e-6 | Stages 7–8 | Stage 6 exit | **Post-Stage-6 baseline** |
| Shadow-mode snapshot agreement on all "invariant"-classified cells (rtol=1e-6) | Stage 3 | Stage 3 | Stage 0 baseline snapshot |
| Full test suite pass count never decreases | All stages | Stage 0 | — |
| `mypy --strict` clean on `core/` and `api/` | All stages | per CLAUDE.md | — |
| `import-linter` clean (no Rule 11 violations) | All stages | per CLAUDE.md | — |
| Rule 9 (EE_box only on target term in point/sub-pixel; never on bg; never in extended) | All stages — explicit test in Stage 4 | Stage 4 | — |
| Rule 4 (PSF path / MTF product path consistency) | Untouched by Option C | n/a | — |

Stage 6 is the **one** authorized anchor re-baseline in this plan: the LWIR thermal-downwelling approximation becomes exact, so Cell 28/58 values are expected to shift (target: rtol ≤ 1e-3). The re-baseline follows the procedure in Stage 6's constraints section and is tagged `post-stage-6-baseline`. No other stage is permitted to move anchor values.

If any invariant breaks during a stage, **stop**, do not proceed to the next stage, debug the current stage. The shadow-mode in Stage 3 is the primary mechanism for catching regressions before they ship.

---

## Effort and Cell Coverage Summary

| Stage | Days | Category | Cumulative cells reachable |
|---|---|---|---|
| 0 | 0.5 | A | 2 (today's working anchors) |
| 1 | 2 | B | 2 |
| 2 | 2 | B | 2 |
| 3 | 3 | C | ~15 (B-extended cells become correct via assembly) |
| 4 | 1 | D | ~20 (Option C complete; legacy removed) |
| 5 | 3 | C | ~35 (+15 Table C airborne) |
| 6 | 2 | C | ~35 (quality fix on MWIR cells already counted) |
| 7 | 1 | B | ~65 (+30 D-ground + D-lab) |
| 8 | 2 | D | ~80–85 (validation + parametric coverage; rest are v2 deferrals) |

**Stage 4 is the "Option C landed" milestone.** Stages 5/6 and Stage 7 are independent expansions on top and may run in parallel.

---

## Stage 0 — Pre-flight (0.5 day, Category A)

**Regression posture**: pure capture, no code change. Establishes the safety net for all later stages.

### Prompt

> **Category: A**
>
> **Read first**:
> - `docs/RADIANT_Use_Case_Matrix.md` (full)
> - `docs/Use_Case_gaps.md` (full)
> - `docs/adr/0002-option-c-source-atmosphere-split.md` (full)
>
> **Task**:
>
> 1. Tag the current commit on `main` as `pre-option-c-baseline` and push. This is the regression reference point for Stages 1–8.
> 2. Identify the integration test(s) that exercise Cell 28 (terrestrial LWIR extended) and Cell 58 (space LWIR extended). If neither has a clean integration test, write a minimal one for each that runs the full chain end-to-end with deterministic parameters and asserts SNR, NEDT, MTF-at-Nyquist, and at-aperture radiance to 6 significant figures. Place these in `tests/integration/test_option_c_anchors.py`.
> 3. Run the full test suite and capture the pass/fail count to a file `docs/option_c_baseline.md` containing: total tests, passing, failing, the SNR/NEDT/MTF/L_aperture values for the two anchor cells, and the git SHA they were captured at. This file is the regression checklist for all subsequent stages.
> 4. Run `pytest --collect-only` and grep for any test names that mention "at_target", "at_aperture", "L_background", "L_target", or "AtmosphericGeometry" — list them in `docs/option_c_baseline.md` under "Tests likely to need updating during refactor" so we don't get surprised later.
> 5. **Capture the full pre-Option-C golden surface**: write a script `scripts/capture_option_c_baseline.py` that runs every YAML scenario in `scenarios/` through the current pipeline and snapshots each result (SNR, NEDT, MTF-at-Nyquist, at-aperture radiance at a fixed λ grid) to `tests/integration/snapshots/option_c_baseline.yaml`. This snapshot is the **shadow-mode reference** for Stage 3: every cell in it is expected to match within rtol=1e-6 unless explicitly waived with physics justification in Stage 3's "goldens changed" table.
> 6. **Classify each snapshot cell** as either "invariant" (must-match, rtol=1e-6 through Stage 5) or "expected-to-change-at-Stage-3" (legitimate physics correction — e.g., sub-pixel terrestrial cells gain the missing `L_bg,aperture` branch; reflective cells gain the two-leg τ split). Record this classification in `docs/option_c_baseline.md` under "Stage 3 shadow-mode scope". Cells 28 and 58 are always "invariant"; any sub-pixel/reflective/airborne cell is a Stage-3 expected-change candidate.
>
> **Out of scope**: any code change to source/, atmosphere/, or core/. This stage is reconnaissance only.
>
> **Done when**: `pre-option-c-baseline` tag is pushed; `docs/option_c_baseline.md` exists with anchor values; `tests/integration/test_option_c_anchors.py` runs green.
>
> **Report**: structured report per CLAUDE.md template, Category A.

---

## Stage 1 — Core descriptor classes (2 days, Category B)

**Regression posture**: zero risk. New files only; nothing imports them yet.

### Prompt

> **Category: B**
>
> **Read first**:
> - `docs/adr/0002-option-c-source-atmosphere-split.md` (Decision section, full)
> - `docs/RADIANT_Use_Case_Matrix.md` §4 and §7
> - `src/radiant/core/parameters.py` (for ParameterDef style)
> - `src/radiant/core/spectral.py` (for SpectralData type)
> - `src/radiant/core/geometry.py` (for ObserverGeometry pattern — frozen dataclass with `__post_init__` validation)
>
> **Task**: implement the descriptor classes specified in ADR-0002. **Wire nothing.** No stage imports these yet.
>
> Files to create:
> 1. `src/radiant/core/los_geometry.py` — `LineOfSightGeometry` frozen dataclass (h_tgt, h_atm_top=1e5, theta_o, theta_s, delta_phi) with `slant_range_atm` and `path_airmass_up` properties (spherical-Earth secant approximation), and module-level `theta_o_from_eta(eta, h_sensor, h_tgt)` boundary converter. Validation in `__post_init__`: h_tgt ∈ [0, h_atm_top]; θ_o ∈ [0, π/2); θ_s ∈ [0, π] if not None; Δφ ∈ [−π, π] if not None. Use `ParameterBoundsError` per Rule 15. **Note**: `theta_o_from_eta` is not wired into any stage until `h_sensor` lands (Stage 7 for the Earth-intercept check and/or the SensorDescriptor follow-on ADR). Until then it is exercised only by unit tests — add a module-level comment flagging it as a boundary converter for future sensor-side use so it is not mistaken for dead code.
> 2. `src/radiant/core/descriptors.py` — `TargetDescriptor` base + four discriminated payload variants (`T1Thermal`, `T2Reflective`, `T3Mixed`, `T5AtAperture`); `BackgroundDescriptor` base + four variants (`AtApertureBackground`, `ColdSpaceBackground`, `GroundBackground`, `UserSpectralBackground`). All frozen dataclasses. All cross-field validators from ADR-0002 in `__post_init__` (at_aperture⇒extended, no_atmosphere⇒sub_case required, MWIR⇒T3 warn unless ρ≈0, ε both spec rejected, T_g ∈ [150,350] warn outside). **Location**: `core/` (not `source/`) — per ADR-0002 "Location rationale", these are pure cross-stage data contracts analogous to `ChainState`, and placing them in `core/` removes a would-be Rule 11 exception for AtmosphereStage. Class docstrings must state that the point-source angular-size check (√A_t/d > 0.1·PSF_FWHM) is **not** validated at construction — it is deferred to `OpticsStage._finalize_regime()` in Stage 8 because it requires PSF_FWHM from OpticsStage.
>
> Files to create — tests:
> 3. `src/radiant/core/tests/test_los_geometry.py` — at least: bounds tests (each field at edges), airmass against secant approximation truth value, boundary-converter round-trip (`theta_o_from_eta(eta, h_sensor, h_tgt)` then back via inverse), Earth-LOS-intercept property tests for `space` sub-case configurations (raise expected).
> 4. `src/radiant/core/tests/test_descriptors.py` — every matrix §7 invalid combination must have a test that constructs the descriptor and asserts it raises. Every matrix §3.2 valid cell must have a smoke test that constructs the descriptor without error.
>
> **Mandatory deliverables (Category B)**:
> - Dimensional audit table showing every field's units (h in m, θ in rad, ε/ρ dimensionless, T in K, L in W/m²/sr/µm).
> - Failure-modes section covering: zero h_tgt, h_tgt = h_atm_top exactly, θ_o = π/2 exactly, negative T_g, ε > 1, providing both ε and ρ.
> - Serialization round-trip: dataclass → dict (via `dataclasses.asdict`) → reconstruct; verify equality.
>
> **Constraints**:
> - Rule 11: no imports of any physics module (source/, atmosphere/, optics/, etc.) from `core/los_geometry.py` or `core/descriptors.py`. They may import only stdlib + numpy + `radiant.core.parameters` + `radiant.core.spectral`.
> - Rule 19: `los_geometry.py` and `descriptors.py` are their own modules — do not bundle into `geometry.py`.
> - Rule 12: any descriptor field that maps to a tuneable parameter gets a corresponding `ParameterDef` in the owning stage's `_schema.py` (Stage 2 registers the new `source.scene_type`/`source.target_location`/`source.no_atmosphere_subcase` entries). Descriptors in `core/` do not themselves own parameters.
>
> **Done when**: all new tests pass; `mypy --strict src/radiant/core/los_geometry.py src/radiant/core/descriptors.py` is clean; `import-linter` is clean; the full existing test suite still has the same pass count as `docs/option_c_baseline.md`.
>
> **Report**: structured report per CLAUDE.md template, Category B (include dimensional audit + failure-mode tests + serialization).

---

## Stage 2 — SourceStage publishes descriptors alongside legacy frame (2 days, Category B)

**Regression posture**: low. Additive — descriptors join the existing stage_outputs; the legacy `at_target` frame and `L_background` continue to be published. Existing AtmosphereStage continues to consume the legacy frame.

### Prompt

> **Category: B**
>
> **Read first**:
> - `docs/adr/0002-option-c-source-atmosphere-split.md` (Stage boundary contract subsection)
> - `src/radiant/source/stage.py` (full — understand current parameter→radiance flow)
> - `src/radiant/source/_schema.py` (full)
> - `src/radiant/core/descriptors.py` (from Stage 1)
> - `src/radiant/core/los_geometry.py` (from Stage 1)
> - `docs/option_c_baseline.md` (the regression-anchor values)
> - All YAML scenarios in `scenarios/` to understand the parameter shapes that must continue to work
>
> **Task**: SourceStage starts publishing the three new descriptors *alongside* the existing radiance frame and stage_outputs. Nothing downstream changes yet — this is the additive bridge step.
>
> Files to modify:
> 1. `src/radiant/source/_schema.py` — add three new `ParameterDef`s:
>    - `source.scene_type` (enum string, default `"extended"`, allowed `{"extended", "sub_pixel", "point_source"}`)
>    - `source.target_location` (enum string, default `"terrestrial"`, allowed `{"at_aperture", "terrestrial", "airborne", "no_atmosphere"}`)
>    - `source.no_atmosphere_subcase` (enum string or None, default None, allowed `{"space", "ground_test", "lab_test"}` if `target_location == "no_atmosphere"`)
> 2. `src/radiant/source/_inferrer.py` (new file) — back-compat inferrer that maps the legacy parameter set (fill_fraction, projected_area_m2, range_m, target.temperature, target.emissivity, etc.) to the new descriptor inputs. The inferrer must be deterministic and conservative: if user did not set `source.scene_type`, infer `"extended"` when `fill_fraction == 1.0`, `"sub_pixel"` when `0 < fill_fraction < 1`, `"point_source"` when geometry implies it. If user did not set `source.target_location`, infer `"terrestrial"` for atm.model `"simple"|"modtran"|"tabulated"|"interpolated"` and `"no_atmosphere"` (subcase=`"space"`) for atm.model `"exo"`. Document every inference rule with a code comment citing matrix §3.2.
> 3. `src/radiant/source/stage.py` — at the end of `run()`, after the existing radiance computation, build the three descriptors via the inferrer (or from explicit user parameters if provided) and publish them to `state.stage_outputs["source"]["target" | "background" | "los_geometry"]`. **Keep the legacy `with_frame("at_target", ...)` and `L_background` stage_output** — Stage 4 removes them.
>
> Files to create — tests:
> 4. `src/radiant/source/tests/test_inferrer.py` — for every YAML scenario in `scenarios/`, load it, run SourceStage, and assert the inferred descriptors match expected values per matrix §3.2. Snapshot test: serialize each scenario's descriptors via `dataclasses.asdict(...)` → YAML under `src/radiant/source/tests/snapshots/<scenario>.yaml` and use that as a regression target for future PRs. **Do not pickle.** YAML is human-readable, diff-reviewable, and robust to field additions in later stages (a new field appears as a new key, not a deserialization failure).
> 5. `src/radiant/source/tests/test_stage.py` — extend with: existing radiance-frame assertions still pass; new assertion that all three descriptor keys exist in `state.stage_outputs["source"]`; new assertion that descriptor values are consistent with parameters (e.g., target_location parameter == descriptor's target_location field).
>
> **Mandatory deliverables (Category B)**:
> - Dimensional audit on inferrer outputs (no unit conversions inside it — inputs are already canonical).
> - Failure-modes: scenario with explicit user-provided `source.target_location == "no_atmosphere"` but no `no_atmosphere_subcase` should raise; scenario with `target_location == "at_aperture"` and `scene_type == "sub_pixel"` should raise; scenario with `target_location == "terrestrial"` and no GroundBackground (yet — for now warn that bg defaults will change in Stage 3).
> - Round-trip: scenario YAML → params → descriptors → parameters re-derived → equal.
>
> **Constraints**:
> - **Do not** modify AtmosphereStage. **Do not** remove the legacy frame or stage_output. This is the additive bridge.
> - Rule 11: source stage may not import atmosphere module.
>
> **Done when**: `pytest tests/integration/test_option_c_anchors.py` produces the exact same SNR/NEDT/MTF/L_aperture values as `docs/option_c_baseline.md`; full test suite has the same pass count as baseline; every YAML scenario in `scenarios/` produces a populated TargetDescriptor + BackgroundDescriptor + LineOfSightGeometry.
>
> **Report**: Category B with the dimensional audit, failure modes, and serialization sections; include a "scenario coverage" table listing every scenario in `scenarios/` and the descriptors inferred for each.

---

## Stage 3 — AtmosphereStage shadow-mode assembly (3 days, Category C)

**Regression posture**: this is **the stage with risk**. We mitigate with a shadow mode: AtmosphereStage runs both the new and legacy paths and asserts agreement on the LWIR extended cells. Other cells will *legitimately differ*; we capture the new values as new goldens deliberately.

### Prompt

> **Category: C**
>
> **Read first**:
> - `docs/adr/0002-option-c-source-atmosphere-split.md` (Stage boundary contract; cell ↔ assembly-arm mapping)
> - `docs/RADIANT_Use_Case_Matrix.md` §6 (assembly equation) and §3.1 (T-codes, A-codes)
> - `docs/RADIANT_Atmosphere.md` (full)
> - `src/radiant/atmosphere/stage.py` (full)
> - `src/radiant/atmosphere/protocol.py` (current AtmosphericGeometry / AtmosphereBackend contract)
> - `src/radiant/atmosphere/simple.py` (full — current single-τ implementation)
> - `src/radiant/atmosphere/exo.py` (full)
> - `src/radiant/core/descriptors.py` and `src/radiant/core/los_geometry.py` (from Stage 1)
> - `docs/option_c_baseline.md`
>
> **Task**: refactor AtmosphereStage to consume descriptors and run the §6.1 assembly equation, while keeping the legacy `L·τ + L_path` path active under a shadow flag for regression validation.
>
> Files to create:
> 1. `src/radiant/atmosphere/assembly.py` — pure function `assemble_target_at_aperture(target, atm_quantities, los) -> ndarray` and `assemble_background_at_aperture(background, atm_quantities, los) -> ndarray | None`. One match arm per `target_location` and per `BackgroundDescriptor` variant per ADR-0002 cell-mapping table. **At-aperture pass-through arm includes the warn-if-atm-supplied check (Decision #6)**.
> 2. `src/radiant/atmosphere/_quantities.py` — `AtmosphericQuantities` frozen dataclass holding `(tau_sun, tau_up, tau_full_up, E_TOA, E_sky_scattered, E_sky_thermal, L_path_up, L_path_full)`. Stage 6 will populate scattered vs thermal separately; for now both fields are populated but `E_sky_scattered = 0` everywhere except VIS/NIR (placeholder).
>
> Files to modify:
> 3. `src/radiant/atmosphere/protocol.py` — extend `AtmosphereBackend` protocol with `evaluate(los: LineOfSightGeometry, params) -> AtmosphericQuantities`. Keep the legacy `build_state()` method for shadow-mode comparison; remove in Stage 4.
> 4. `src/radiant/atmosphere/exo.py` — implement `evaluate()` returning all-trivial quantities (τ=1, L_path=0, E_sky=0, E_TOA=solar TOA spectrum from existing solar.py).
> 5. `src/radiant/atmosphere/simple.py` — implement `evaluate()`. **A3 partial column is deferred to Stage 5**; for now if `los.h_tgt > 1000 m`, raise `NotImplementedError("A3 partial-column atmosphere is Stage 5")`. For h_tgt = 0 (terrestrial), compute τ_sun and τ_up as separate column integrals (each is a single-leg secant approximation through the column at the appropriate zenith angle); τ_full_up == τ_up when h_tgt = 0. Preserve the existing single-scatter L_path computation; populate L_path_up and L_path_full equal to it for h_tgt = 0.
> 6. `src/radiant/atmosphere/tabulated.py` and `src/radiant/atmosphere/interpolated.py` — implement `evaluate()` via a thin adapter that lifts their existing output (pre-computed τ and L_path tables) into `AtmosphericQuantities`. For h_tgt = 0 only: τ_sun = τ_up = τ_full_up = the tabulated τ (these backends do not split the two-leg geometry); L_path_up = L_path_full = the tabulated L_path; E_sky components = 0 (tables do not carry E_sky). Log a one-time `UserWarning` when these backends are used noting that two-leg τ split and E_sky decomposition are not available — the user gets the legacy single-τ behavior via the new protocol. For h_tgt > 0, raise `NotImplementedError` as in Stage 5. **This adapter is mandatory in Stage 3**: the protocol change would otherwise break every scenario that uses these backends, violating the "test suite runs end-to-end" exit criterion.
> 7. `src/radiant/atmosphere/stage.py` — refactor `run()`: read descriptors from `state.stage_outputs["source"]`; call `backend.evaluate(los, params)` to get `AtmosphericQuantities`; call `assemble_target_at_aperture` and `assemble_background_at_aperture`; publish two new frames `at_aperture_target` and `at_aperture_background`. **Shadow mode**: also run the legacy `L_target · τ + L_path` path on the legacy `at_target` frame and publish `at_aperture_legacy` for comparison.
>
> **Shadow-mode assertion policy** (replaces the prior LWIR-only rule):
> - Shadow mode is controlled by the env var `RADIANT_OPTION_C_SHADOW=1|0` (default `1` in Stage 3, unset/ignored from Stage 4 onward). **Not** a `params` field — this is a test/debug lifecycle flag and has no `ParameterDef` home.
> - When shadow mode is on, AtmosphereStage classifies each run against the Stage-0 baseline snapshot (`tests/integration/snapshots/option_c_baseline.yaml`, field: `classification`):
>   - **"invariant"** cells (including Cells 28 and 58): assert `np.allclose(at_aperture_target, at_aperture_legacy, rtol=1e-6)`. Failure is a hard test failure.
>   - **"expected-to-change"** cells: log the relative difference and record it in the Stage 3 "goldens changed" table. No assertion. Each entry in the table requires a physics justification in the Stage 3 report.
>   - **Unclassified** cells (anything that ran in Stage 0 baseline but is not labeled): treated as invariant by default. The test fails with a message pointing to `docs/option_c_baseline.md` telling the reviewer to either (a) add the cell to the waiver list with justification, or (b) debug the divergence. **Silent drift is not allowed.**
> - Pytest fixture `shadow_mode_off` is available for unit tests that need to exercise the new path in isolation without the legacy comparison (e.g., A3 tests from Stage 5).
>
> Files to create — tests:
> 8. `src/radiant/atmosphere/tests/test_assembly.py` — three truth anchors per Category C:
>    - **Anchor 1 (LWIR extended terrestrial)**: ε=0.95, T_t=300 K, no solar; assembly must reduce to `ε·B(λ,T)·τ_up + L_path_up`. Compare against hand calculation at three wavelengths {8, 10, 12} µm.
>    - **Anchor 2 (VIS reflective extended terrestrial)**: ε=0, ρ=1, θ_s=0, no E_sky; assembly must reduce to `E_TOA·τ_sun·τ_up/π + L_path_up`. With τ_sun = τ_up = τ (zenith), this is `E_TOA·τ²/π + L_path_up` — verifies the **two-leg split** vs the legacy single-τ which would give `E_TOA·τ/π + L_path_up`. Compare against hand calculation.
>    - **Anchor 3 (at-aperture pass-through)**: T5 descriptor with arbitrary user spectrum; assembly must return the user spectrum unmodified; warn-if-atm-supplied must fire if atm params are non-trivial.
> 9. `src/radiant/atmosphere/tests/test_evaluate.py` — `SimpleAtmosphere.evaluate(h_tgt=0, theta_o=0, theta_s=0)` produces τ_sun = τ_up = legacy `tau`; `evaluate(h_tgt=1km)` raises `NotImplementedError`; `ExoAtmosphere.evaluate(...)` produces all-trivial quantities; `TabulatedAtmosphere.evaluate(h_tgt=0)` and `InterpolatedAtmosphere.evaluate(h_tgt=0)` produce τ_sun = τ_up = τ_full_up = the tabulated τ and emit the one-time degraded-capabilities warning.
>
> **Mandatory deliverables (Category C)**:
> - Three truth anchors as above; document expected, actual, abs/rel error.
> - Dimensional audit on the assembly equation (every term in §6.1 with units).
> - Assumptions section: Lambertian target, opaque (Kirchhoff ε+ρ=1), no atmospheric refraction, single-scatter L_path, secant-approximation airmass.
> - Fragility analysis: behavior at θ_s = π/2 (cos→0), at τ→0 (L_path dominates), at extreme T_t (Planck overflow).
> - Cross-model consistency: shadow-mode assertion against legacy on Cells 28 and 58.
>
> **Constraints**:
> - **Cell 28 and Cell 58 anchor values from `docs/option_c_baseline.md` must remain unchanged within rtol=1e-6.** This is non-negotiable.
> - For other cells, expect goldens to change. **Do not delete the legacy `at_target` frame yet** — Stage 4 does that. The shadow-mode comparison stays active.
> - Rule 11: `atmosphere/assembly.py` imports only `radiant.core` (including the descriptor types now in `radiant.core.descriptors`). No imports from `radiant.source`. This is clean under the standard Rule 11 table — no exception needed, because descriptors were relocated to `core/` in Stage 1.
>
> **Done when**: anchor cells unchanged; new VIS reflective and MWIR mixed test cases pass against hand-calculated truth; shadow-mode assertion green on LWIR; test suite still runs end-to-end. Any other golden values that change are documented in the report with the physics reason for the change.
>
> **Report**: Category C with three truth anchors fully documented, dimensional audit, assumptions, fragility, cross-model consistency (shadow-mode results), and a "goldens changed" table listing every test whose golden value moved with the physical justification.

---

## Stage 4 — Remove legacy path; complete Option C (1 day, Category D)

**Regression posture**: low if Stage 3 was clean. Just removes the now-shadowed legacy path.

### Prompt

> **Category: D**
>
> **Read first**:
> - Stage 3's report (especially the "goldens changed" table)
> - `docs/adr/0002-option-c-source-atmosphere-split.md` (Stage 4 milestone)
> - `src/radiant/spectral_integration/stage.py` (full — currently consumes `L_background` stage_output)
> - `src/radiant/source/stage.py` (full — still publishes `at_target` frame)
> - All test files identified in Stage 0's "tests likely to need updating" list
>
> **Task**: complete the Option C transition by removing the legacy code path. After this PR, SourceStage publishes zero radiance and AtmosphereStage owns 100% of assembly.
>
> Files to modify:
> 1. `src/radiant/source/stage.py` — remove the radiance-frame publication (`with_frame("at_target", ...)`); remove the `L_background` stage_output. SourceStage now publishes only descriptors + `regime_tentative`.
> 2. `src/radiant/spectral_integration/stage.py` — refactor to consume `state.frames["at_aperture_target"]` and `state.frames["at_aperture_background"]` (the latter may be None for computed-extended cells, which means skip the background photon term per matrix Decision #13). Remove the `L_background` stage_output dependency. **Preserve Rule 9 exactly**: target frame × EE_box; background frame not weighted by EE_box; no EE_box in extended scenes (regime guard remains in place).
> 3. `src/radiant/atmosphere/stage.py` — remove shadow-mode code: drop the legacy `L·τ + L_path` path, drop the `at_aperture_legacy` frame, drop the shadow-assert. AtmosphereStage now just runs the descriptor-driven assembly.
> 4. `src/radiant/atmosphere/protocol.py` — remove the legacy `build_state()` method from `AtmosphereBackend`. Backends now expose only `evaluate()`.
> 5. Update any tests from Stage 0's "tests likely to need updating" list to consume the new frame names. For tests that asserted shape or content of `L_background` or `at_target`, refactor them to assert on `at_aperture_target` / `at_aperture_background`.
>
> **Mandatory deliverables (Category D)**:
> - Integration tests: full chain runs to completion for Cells 28, 58, plus at minimum one VIS reflective extended terrestrial case (e.g., Cell 16) and one space sub-pixel LWIR case (e.g., Cell 60) with `ColdSpaceBackground`.
> - Regression checks: full test suite pass count matches Stage 3's pass count (no new failures from the cleanup); anchor cells still match `docs/option_c_baseline.md`.
> - Update `docs/option_c_baseline.md` with the post-Stage-4 SHA and a "Stage 4 complete" marker; the anchor values themselves must be unchanged.
>
> **Constraints**:
> - **Do not change physics in this PR.** This is pure removal-of-now-dead-code. Any physics changes are caught at the Stage 3 review.
> - Rule 4 (dual-path spatial): unaffected — this PR doesn't touch the PSF or MTF path.
> - Rule 9 (EE_box): explicitly verified by an integration test that constructs a sub-pixel scene and asserts the bg term in `at_aperture_background` does not get EE_box applied.
>
> **Done when**: SourceStage has zero `with_frame()` calls; `grep -r "at_target" src/` returns zero hits in non-test code; full suite green; anchors match.
>
> **Milestone**: Option C is fully landed. Tag the commit `option-c-landed`.
>
> **Report**: Category D with the integration test results, the regression check (anchor values + full test pass count), and a "files no longer referenced" diff showing the dead code removed.

---

## Stage 5 — A3 partial-column atmosphere (3 days, Category C)

**Regression posture**: low. Adds new code paths gated on `h_tgt > 0`; existing terrestrial scenarios with h_tgt = 0 are untouched.

### Prompt

> **Category: C**
>
> **Read first**:
> - `docs/RADIANT_Use_Case_Matrix.md` Table C, §1.3 (target_location), §6 (assembly equation)
> - `docs/RADIANT_Atmosphere.md` (full)
> - `src/radiant/atmosphere/simple.py` (post-Stage-3)
> - `src/radiant/atmosphere/modtran.py` (full)
> - `src/radiant/atmosphere/_quantities.py` (from Stage 3)
> - Open Question §8.3 in `docs/RADIANT_Use_Case_Matrix.md`
>
> **Task**: implement the A3 partial-column atmosphere path so airborne targets at `0 < h_tgt < h_atm_top` are handled. This unlocks all 15 cells in Table C.
>
> Files to modify:
> 1. `src/radiant/atmosphere/simple.py` — extend `evaluate()` to support arbitrary h_tgt:
>    - τ_sun(h_tgt, θ_s) = exp(−sec(θ_s) · ∫_{h_tgt}^{h_atm_top} k(λ, z) dz) — the column from h_tgt up to TOA along solar zenith
>    - τ_up(h_tgt, θ_o) = exp(−sec(θ_o) · ∫_{h_tgt}^{h_atm_top} k(λ, z) dz) — sensor up-leg from h_tgt
>    - τ_full_up(0, θ_o) = exp(−sec(θ_o) · ∫_0^{h_atm_top} k(λ, z) dz) — for the background branch
>    - L_path_up = single-scatter integral from h_tgt to h_atm_top
>    - L_path_full = single-scatter integral from 0 to h_atm_top (background branch)
>    - E_sky(h_tgt) — degrades to 0 as h_tgt → h_atm_top
>    - Use existing exponential scale-height aerosol + Rayleigh + molecular formulas from `_column_length_km()`; just integrate over a different range.
> 2. `src/radiant/atmosphere/modtran.py` — extend the card-deck builder to set MODTRAN's H1/H2 for partial-column runs at arbitrary h_tgt; add h_tgt as a cache key dependency.
> 3. `src/radiant/atmosphere/tabulated.py` and `interpolated.py` — these already support `h_tgt = 0` via the Stage 3 thin adapter. Stage 5 keeps the `NotImplementedError` raise for `h_tgt > 0` (these backends use precomputed tables that don't have a free h_tgt parameter; fixing them is out of scope for this stage). Ensure the raise message points to Stage 5's open question about tabulated airborne support.
>
> Files to create — tests:
> 4. `src/radiant/atmosphere/tests/test_a3.py` — truth anchors per Category C:
>    - **Anchor 1 (limit h_tgt → 0)**: A3 with h_tgt = 1 m must equal A2 (Stage 3 implementation) within rtol=1e-4.
>    - **Anchor 2 (limit h_tgt → h_atm_top)**: A3 with h_tgt = 99 km must give τ_sun ≈ τ_up ≈ 1 and L_path ≈ 0 (vacuum limit).
>    - **Anchor 3 (intermediate, vs MODTRAN)**: A3 SimpleAtmosphere at h_tgt = 10 km, midlatitude summer, λ = 4 µm vs MODTRAN partial-column run; agreement to within 20% on τ (simple model is order-of-magnitude only).
> 5. `tests/integration/test_table_c_cells.py` — smoke tests for at least 5 of the 15 Table C cells: airborne VIS sub-pixel, airborne MWIR sub-pixel, airborne LWIR sub-pixel, airborne LWIR extended, airborne SWIR extended. Assert each runs to completion and produces finite SNR; do not pin SNR values yet (Category D Stage 8 does the full coverage test).
>
> **Mandatory deliverables (Category C)**:
> - Three truth anchors as above.
> - Dimensional audit of the partial-column integrals.
> - Assumptions: same as Stage 3 plus exponential scale-height extrapolation valid up to h_atm_top.
> - Fragility: behavior at h_tgt = h_atm_top exactly (avoid divide-by-zero in airmass); behavior at θ_o close to π/2 (airmass → ∞); behavior at h_tgt > h_atm_top (raise per Stage 1 validator).
>
> **Constraints**:
> - Stage 3's anchor cells (h_tgt = 0) must continue to match within rtol=1e-6 — A3 must reduce exactly to A2 at h_tgt = 0.
> - Tabulated/Interpolated backends raise on h_tgt > 0 (don't silently fall back).
>
> **Done when**: Table C cells run end-to-end; A3 → A2 limit holds; A3 → A0 limit holds; MODTRAN comparison spot-check passes.
>
> **Report**: Category C with the three anchors and the limit checks.

---

## Stage 6 — E_sky decomposition (2 days, Category C)

**Regression posture**: low. Changes the *internal* E_sky representation but the consumed sum is unchanged for cases where the decomposition was already correct (LWIR all-thermal, VIS all-scattered).

### Prompt

> **Category: C**
>
> **Read first**:
> - `docs/RADIANT_Use_Case_Matrix.md` Open Question §8.6
> - `docs/RADIANT_Use_Case_Matrix.md` §3.2 lines 318–320 (MWIR thermal-downwelling note)
> - `src/radiant/atmosphere/simple.py` `_effective_atmospheric_temperature_K` (current single-graybody approximation)
> - `src/radiant/atmosphere/_quantities.py`
>
> **Task**: separate `E_sky` into scattered-solar and atmospheric-thermal components so MWIR audit (Cells 25–26, 40–41) is correct.
>
> Files to modify:
> 1. `src/radiant/atmosphere/simple.py` — replace the single-graybody E_sky placeholder with two separate computations:
>    - `E_sky_scattered_solar(λ, h_tgt)` = scattered-solar component using single-scatter approximation against E_TOA(λ).
>    - `E_sky_atm_thermal(λ, h_tgt)` = (1 − τ_atm,downward(λ, h_tgt))·B(λ, T_atm_eff(h_tgt)) — what's already there, but tagged as the thermal component only.
> 2. `src/radiant/atmosphere/assembly.py` — assembly equation already consumes the sum (`E_sky = E_sky_scattered + E_sky_thermal`); no math change needed here. Add an optional `report_components: bool` parameter that, when True, also publishes the two components as separate stage_outputs for inspectability per Rule 16.
> 3. `src/radiant/atmosphere/stage.py` — always publish `state.stage_outputs["atmosphere"]["E_sky_scattered"]` and `["E_sky_thermal"]` for diagnostic access.
>
> Files to create — tests:
> 4. `src/radiant/atmosphere/tests/test_e_sky_decomposition.py`:
>    - **Anchor 1 (LWIR limit)**: at λ = 10 µm, `E_sky_scattered / E_sky_thermal < 1e-3` — solar contribution negligible.
>    - **Anchor 2 (VIS limit)**: at λ = 0.5 µm, `E_sky_thermal / E_sky_scattered < 1e-6` — thermal contribution negligible.
>    - **Anchor 3 (MWIR crossover)**: at λ = 4 µm with sun up (θ_s = 30°), both components within an order of magnitude of each other for h_tgt = 0.
> 5. Modify Stage 3's MWIR-mixed truth anchor: previously the diffuse term was a graybody approximation; now assert that E_sky = E_sky_scattered + E_sky_thermal and the per-component values are physically sensible.
>
> **Mandatory deliverables (Category C)**:
> - Three anchors.
> - Cross-model consistency: `assemble_target_at_aperture(...)` with `E_sky` from Stage 3's single-graybody formulation should equal the new sum within ~5% for LWIR and within ~50% for VIS (where the new decomposition is more accurate); document the difference.
> - Fragility: behavior at high optical depth (E_sky_scattered saturates), at low sun (E_sky_scattered → 0).
>
> **Constraints**:
> - Stage 6 is the **only** stage in the plan that legitimately re-baselines the anchor cells. The LWIR thermal-downwelling component is computed exactly here rather than approximated, so Cells 28 and 58 are expected to shift slightly (target bound: rtol ≤ 1e-3).
> - **Mandatory re-baseline procedure**:
>   1. Before editing `simple.py`, confirm anchor values still match the Stage 0 / Stage 4 baseline at rtol=1e-6.
>   2. Land the physics change.
>   3. Capture the new anchor values into a new section of `docs/option_c_baseline.md` titled "Post-Stage-6 anchor values" with: new values, delta from Stage 0 values, physics justification per anchor, and the post-Stage-6 git SHA.
>   4. Tag the post-Stage-6 commit `post-stage-6-baseline`.
>   5. Update `tests/integration/test_option_c_anchors.py` to assert against the new values; update the "Regression Invariants" table (top of this plan) to note that from Stage 6 onward, Cell 28/58 assertions use the post-Stage-6 baseline, not the Stage 0 one.
> - Stages 7 and 8 then enforce rtol=1e-6 against the **post-Stage-6 baseline**. The Stage 0 anchor values are retired at Stage 6 exit; they remain in the baseline doc for historical traceability but are no longer a CI gate.
>
> **Done when**: three anchors pass; per-component values are inspectable from stage_outputs; MWIR mixed cells produce physically defensible numbers; `docs/option_c_baseline.md` contains both Stage 0 and Post-Stage-6 anchor sections; `post-stage-6-baseline` tag is pushed.
>
> **Report**: Category C with the standard sections plus a table comparing single-graybody (Stage 3) vs decomposed (Stage 6) E_sky at λ ∈ {0.5, 1, 4, 10} µm.

---

## Stage 7 — no_atmosphere sub-case presets (1 day, Category B)

**Regression posture**: zero. Adds new code paths gated on the new `no_atmosphere_subcase` parameter; existing scenarios that don't set it are unaffected.

### Prompt

> **Category: B**
>
> **Read first**:
> - `docs/RADIANT_Use_Case_Matrix.md` §3.3 (sub-case presets), Table D-ground, Table D-lab, §7
> - `src/radiant/source/_inferrer.py` (from Stage 2)
> - `src/radiant/core/descriptors.py`
> - `src/radiant/atmosphere/assembly.py`
> - `src/radiant/core/los_geometry.py`
>
> **Task**: wire the three `no_atmosphere` sub-cases (`space`, `ground_test`, `lab_test`) so Tables D-ground (15 cells) and D-lab (15 cells) become reachable.
>
> Files to modify:
> 1. `src/radiant/source/_inferrer.py` — when `target_location == "no_atmosphere"`, dispatch on `no_atmosphere_subcase`:
>    - `"space"` → default BackgroundDescriptor = `ColdSpaceBackground()`; default illumination = solar TOA unattenuated.
>    - `"ground_test"` → `BackgroundDescriptor` is **required** (no default); raise if user did not supply a `UserSpectralBackground`. Illumination is user-supplied.
>    - `"lab_test"` → same as ground_test, plus illumination may be `None` (dark-cal mode).
> 2. `src/radiant/core/descriptors.py` — `BackgroundDescriptor.__post_init__` enforces variant↔sub-case compatibility (already from Stage 1; verify and extend).
> 3. `src/radiant/core/los_geometry.py` — add `intercepts_earth(h_sensor: float) -> bool` method to LineOfSightGeometry. Spherical-Earth ray-sphere intersection. Used by the `space` sub-case to validate that the LOS clears the Earth limb.
> 4. `src/radiant/platform/_schema.py` (or the current home of platform parameters) — register a minimal `platform.h_sensor` ParameterDef (float, meters, no default — required only when `source.no_atmosphere_subcase == "space"` and the Earth-intercept check runs). This is the narrowly-scoped precursor to the full SensorDescriptor ADR; it does **not** attempt to model anything else sensor-side. If `platform/_schema.py` does not exist yet, create it alongside this parameter; do not retrofit `h_sensor` into unrelated schemas. Document in the schema docstring that this ParameterDef is a stop-gap that the SensorDescriptor follow-on ADR will subsume.
> 5. `src/radiant/atmosphere/assembly.py` — `assemble_*` arms for `target_location == "no_atmosphere"` consult `no_atmosphere_subcase` and dispatch. For `space` sub-case: read `params["platform.h_sensor"]`, call `los.intercepts_earth(h_sensor)`, and raise `ParameterBoundsError` per matrix §7 if the LOS hits Earth. If `platform.h_sensor` is not supplied for a `space` sub-case, raise with a clear message pointing the user at the parameter (do not default it — a wrong default here produces a silent non-physical result).
>
> Files to create — tests:
> 6. `src/radiant/source/tests/test_no_atmosphere_subcases.py` — for each of the three sub-cases, smoke-test that the descriptor + assembly path runs end-to-end with a representative cell from Tables D, D-ground, D-lab. Negative tests: ground_test without UserSpectralBackground raises; space with LOS-into-Earth raises (construct with `h_sensor < h_tgt` or grazing geometry); space without `platform.h_sensor` raises; lab_test dark-cal (no illumination) runs to completion.
> 7. `tests/integration/test_no_atm_subcases.py` — full chain integration for one cell from each sub-case (e.g., D-58 LWIR space extended, D-ground G13 LWIR ground-test extended, D-lab L13 LWIR dark-cal blackbody-standard).
>
> **Mandatory deliverables (Category B)**:
> - Failure-mode tests: every "must-raise" combination in matrix §7 for the no_atmosphere sub-cases is asserted.
> - Dimensional audit: confirm UserSpectralBackground inputs are in W/m²/sr/µm and pass through unchanged.
> - Round-trip: lab_test scenario YAML → descriptors → re-derive params → equal.
>
> **Done when**: smoke tests for all three sub-cases pass; negative tests raise as specified; Cell 58 anchor still matches.
>
> **Report**: Category B with failure-mode coverage table.

---

## Stage 8 — §7 validators + 90-cell parametric coverage test (2 days, Category D)

**Regression posture**: validation-only, no physics change. Adds the missing §7 cross-field validators; locks in the matrix-coverage measurement.

### Prompt

> **Category: D**
>
> **Read first**:
> - `docs/RADIANT_Use_Case_Matrix.md` §3.2 (full 90-cell enumeration), §7 (invalid combinations)
> - `docs/Use_Case_gaps.md` §5 (validation gap table)
> - All descriptor classes and assembly arms from Stages 1–7
>
> **Task**: close the remaining matrix §7 validation gaps and build the parametric test sweep that asserts every cell either runs cleanly or raises the expected error.
>
> Files to modify:
> 1. `src/radiant/core/descriptors.py` — add the remaining §7 validators not yet implemented:
>    - MWIR + (T1 or T2 alone, ρ not negligible) → warn (use `warnings.warn` per Rule 17 — don't silently continue but don't raise either; user may know what they're doing).
>    - SWIR + T_t > 700 K + (T1 or T2 alone) → same warn.
>    - Point-source descriptor with `√A_t / d > 0.1 · PSF_FWHM` → raise. Requires PSF_FWHM from OpticsStage; this is a deferred check that runs in OpticsStage's `_finalize_regime()`. Implement the check in `optics/stage.py` against `state.stage_outputs["source"]["target"]`.
>    - Sub-pixel descriptor with `√A_t / d ≪ PSF_FWHM` (e.g., < 0.01) → emit UserWarning suggesting reclassification (matrix §1.1).
>    - θ_s > π/2 with reflective-only target (T2) → warn.
>    - T_g ∉ [150, 350] K → warn (already in Stage 1; verify still fires).
> 2. `src/radiant/optics/stage.py` `_finalize_regime()` — add the two PSF-dependent checks above.
>
> Files to create — tests:
> 3. `tests/integration/test_use_case_matrix.py` — parametric sweep over **every cell in matrix §3.2 and §3.3** (90 cells total). For each cell, construct a representative scenario, run the chain, and assert one of:
>    - Cell is valid → chain runs to completion, produces finite SNR/NEDT/MTF.
>    - Cell is invalid per §7 → constructor or stage raises `ParameterBoundsError` with a message that mentions the violated rule.
>    Each cell is one parametrized test case; xfail any cell that is genuinely deferred (e.g., point_source with E_TOA at-aperture which the matrix marks invalid). Output: a JSON coverage report `tests/integration/_use_case_coverage.json` updated by the test run.
> 4. Update `docs/Use_Case_gaps.md` — replace the "0 of 90 cells passing" headline with the actual count from the coverage JSON; flip the severity tally; mark the resolved gaps (every blocker from Stages 1–7).
>
> **Mandatory deliverables (Category D)**:
> - Integration tests covering all 90 cells.
> - Regression checks: full pre-existing test suite still passes; anchor cells still match `docs/option_c_baseline.md`.
> - New goldens: any cell whose value should be reproducible run-to-run gets a tolerance-tagged golden assertion.
>
> **Done when**: parametric test runs and `tests/integration/_use_case_coverage.json` shows N/90 cells passing for some N ≥ ~80 (the deferred v2 items account for the rest); CI gate added on the new test.
>
> **Report**: Category D with the matrix coverage table and the closed-gaps list.

---

## Risk Register

| Stage | Risk | Mitigation |
|---|---|---|
| 2 | Inferrer maps an existing scenario to wrong descriptor → silent regression | Snapshot test against every YAML in `scenarios/` in the Stage 2 acceptance criteria |
| 3 | Assembly refactor moves goldens beyond rtol=1e-6 on anchor cells | Shadow-mode assertion; if it fires, stop and reconcile before any other change |
| 3 | Other (non-anchor) goldens shift; reviewer can't tell legitimate from regression | Stage 3 report includes a "goldens changed" table with physical justification per shift, reviewed per [RADIANT_Testing_Validation.md §5.3](RADIANT_Testing_Validation.md) |
| 5 | MODTRAN partial-column behavior is version-specific | 0.5-day spike before Stage 5 commit to verify card-deck format on the target MODTRAN version |
| 5 | Tabulated/Interpolated backends silently fall back to wrong h_tgt instead of raising | Explicit `NotImplementedError` with actionable message; integration test asserts the raise |
| 8 | Parametric test takes too long for CI | Mark slow cells with `@pytest.mark.slow` and run a representative subset on every PR; full sweep nightly |

---

## Bottom Line

The codebase is **never broken** in this plan. Each of the 8 stages ends with a runnable, tested chain. Stage 4 is the architectural milestone (Option C complete, ~20 cells correctly handled). Stages 5–8 are independent expansions on a stable Option C base. After Stage 8, RADIANT covers ~80–85 of 90 matrix cells; the remainder are documented v2 deferrals (BRDF reflective, plume emission, earthlimb, etc. — see matrix §9).
