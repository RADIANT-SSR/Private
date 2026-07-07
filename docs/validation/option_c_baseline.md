# Option C Baseline — Stage 0 Capture

**Captured-at SHA**: `4953c90489db4734d33bd2ae16c4735ea78a0aae`
**Tag**: `pre-option-c-baseline` (local only — not pushed; `git push origin pre-option-c-baseline` when ready)
**Captured**: 2026-04-19
**Plan reference**: [docs/archive/Option_C_Implementation_Plan.md](Option_C_Implementation_Plan.md) Stage 0

---

## Test-suite state at the tag

| Metric | Value |
|---|---|
| `pytest -q` total tests | 2103 |
| Passing | 2103 |
| Failing | 0 |
| Runtime | 431 s (≈7 min) |
| Warnings | 3 (pre-existing — field-sample nearest-neighbor + 2× thin-filter 3-sample integration warnings) |

Plus 8 new anchor tests added in this task → post-Stage-0 pass count: **2111 / 2111** (see [Task 7 verification](#task-7-verification)).

---

## Anchor cell values (rtol = 1e-6 for Stages 0–5)

These are the **invariant-through-Stage-5** values. Stage 6 is the sole authorized re-baseline event per the "Regression Invariants" table at the top of the plan.

### Cell 28 — terrestrial LWIR extended

Scenario definition — see [tests/integration/test_option_c_anchors.py::TestCell28TerrestrialLWIRExtended](../tests/integration/test_option_c_anchors.py):

- Target: 300 K graybody, ε = 0.95
- Atmosphere: `simple` backend, `midlat_summer` standard profile
- Sensor altitude: 2 000 m (airborne survey; h_tgt = 0 surface target)
- Optics: D = 0.08 m, f = 0.20 m (f/2.5), τ_opt = 0.60
- Detector: 17 µm pitch, QE = 0.55, dark rate 1 000 e⁻/s
- Spectral: 8.0 – 13.0 µm, t_int = 15 ms
- Readout: 20 e⁻ RMS read noise, 14-bit ADC, 2 e⁻/DN

Wavelength grid: 501 samples linearly spaced on **[8.0, 13.0] µm** (0.01 µm step).

| Quantity | Value (6 sig figs) |
|---|---|
| SNR | 5.52081 |
| NEDT | 11.7734 K |
| MTF @ Nyquist | 0.0758782 |
| L_aperture @ 8.0 µm | 5.86053 W·m⁻²·sr⁻¹·µm⁻¹ |
| L_aperture @ 9.0 µm | 7.92246 W·m⁻²·sr⁻¹·µm⁻¹ |
| L_aperture @ 10.0 µm | 8.59494 W·m⁻²·sr⁻¹·µm⁻¹ |
| L_aperture @ 11.0 µm | 8.56133 W·m⁻²·sr⁻¹·µm⁻¹ |
| L_aperture @ 12.0 µm | 8.15243 W·m⁻²·sr⁻¹·µm⁻¹ |
| L_aperture @ 13.0 µm | 7.55736 W·m⁻²·sr⁻¹·µm⁻¹ |

Note: these are modest SNR / high NEDT numbers for LWIR — the scenario uses a short integration time on a small 0.08 m aperture, and the 14-bit ADC quantization noise dominates. The goal here is a deterministic regression anchor, not a high-performance reference design.

### Cell 58 — space LWIR extended

Scenario definition — see [tests/integration/test_option_c_anchors.py::TestCell58SpaceLWIRExtended](../tests/integration/test_option_c_anchors.py):

- Target: 285 K graybody (Earth surface), ε = 0.98
- Atmosphere: `exo` (vacuum: τ ≡ 1, L_path ≡ 0)
- Sensor altitude: 800 000 m (800 km LEO nadir)
- Optics: D = 0.15 m, f = 0.45 m (f/3.0), τ_opt = 0.62
- Detector: 20 µm pitch, QE = 0.55, dark rate 800 e⁻/s
- Spectral: 8.0 – 13.0 µm, t_int = 10 ms
- Readout: 12 e⁻ RMS read noise, 14-bit ADC, 2 e⁻/DN

Wavelength grid: 501 samples linearly spaced on **[8.0, 13.0] µm** (0.01 µm step).

| Quantity | Value (6 sig figs) |
|---|---|
| SNR | 6.47050 |
| NEDT | 9.08630 K |
| MTF @ Nyquist | 0.0669077 |
| L_aperture @ 8.0 µm | 6.48501 W·m⁻²·sr⁻¹·µm⁻¹ |
| L_aperture @ 9.0 µm | 7.26878 W·m⁻²·sr⁻¹·µm⁻¹ |
| L_aperture @ 10.0 µm | 7.54196 W·m⁻²·sr⁻¹·µm⁻¹ |
| L_aperture @ 11.0 µm | 7.43830 W·m⁻²·sr⁻¹·µm⁻¹ |
| L_aperture @ 12.0 µm | 7.09101 W·m⁻²·sr⁻¹·µm⁻¹ |
| L_aperture @ 13.0 µm | 6.60627 W·m⁻²·sr⁻¹·µm⁻¹ |

Same caveat as Cell 28 on SNR/NEDT magnitudes: this is a regression anchor, not a performance reference.

---

## Tests likely to need updating during refactor

Grep results over `pytest --collect-only` names and all `test_*.py` sources for the strings `at_target | at_aperture | L_background | L_target | AtmosphericGeometry`. These tests assert on frame names or internal atmosphere types that Option C renames or removes (Stage 4 cleanup).

### Test IDs surfaced by `pytest --collect-only`

| Test | File |
|---|---|
| `test_produces_at_aperture_frame` | [src/radiant/atmosphere/tests/test_stage.py](../src/radiant/atmosphere/tests/test_stage.py) |
| `test_produces_at_target_frame` | [src/radiant/source/tests/test_stage.py](../src/radiant/source/tests/test_stage.py) |
| `test_L_at_aperture_formula` | [tests/integration/test_chain_extended.py](../tests/integration/test_chain_extended.py) |
| `test_L_at_aperture_equals_target` | [tests/integration/test_ground_truth_mwir.py](../tests/integration/test_ground_truth_mwir.py) |

### Additional test files whose bodies mention these strings (source-level grep)

Any assertion on a frame named `at_target`, the `L_background` stage_output, or the `AtmosphericGeometry` class will need a Stage-4 refactor update.

- [tests/integration/test_ground_truth_mwir.py](../tests/integration/test_ground_truth_mwir.py)
- [tests/integration/test_mwir_leo_minimal.py](../tests/integration/test_mwir_leo_minimal.py)
- [tests/integration/test_chain_extended.py](../tests/integration/test_chain_extended.py)
- [tests/integration/test_regime_continuity.py](../tests/integration/test_regime_continuity.py)
- [tests/integration/test_option_c_anchors.py](../tests/integration/test_option_c_anchors.py) *(new — uses `at_aperture` legitimately; will need to read `at_aperture_target` post-Stage-4)*
- [src/radiant/atmosphere/tests/test_simple.py](../src/radiant/atmosphere/tests/test_simple.py)
- [src/radiant/atmosphere/tests/test_interpolated.py](../src/radiant/atmosphere/tests/test_interpolated.py)
- [src/radiant/atmosphere/tests/test_modtran.py](../src/radiant/atmosphere/tests/test_modtran.py)
- [src/radiant/atmosphere/tests/test_tabulated.py](../src/radiant/atmosphere/tests/test_tabulated.py)
- [src/radiant/atmosphere/tests/test_stage.py](../src/radiant/atmosphere/tests/test_stage.py)
- [src/radiant/atmosphere/tests/test_exo.py](../src/radiant/atmosphere/tests/test_exo.py)
- [src/radiant/source/tests/test_stage.py](../src/radiant/source/tests/test_stage.py)
- [src/radiant/source/tests/test_sub_pixel.py](../src/radiant/source/tests/test_sub_pixel.py)
- [src/radiant/source/tests/test_solar.py](../src/radiant/source/tests/test_solar.py)
- [src/radiant/core/tests/test_chain.py](../src/radiant/core/tests/test_chain.py)
- [src/radiant/core/tests/test_quantity.py](../src/radiant/core/tests/test_quantity.py)
- [src/radiant/optics/tests/test_stage_mtf_term.py](../src/radiant/optics/tests/test_stage_mtf_term.py)
- [src/radiant/optics/tests/test_stage.py](../src/radiant/optics/tests/test_stage.py)

Stage 4 will need to touch every file in this list, at minimum to rename `at_target` → `at_aperture_target` and `L_background` → `at_aperture_background` frame references. The list is explicit here so reviewers can cross-check Stage 4's scope.

---

## Full-scenario baseline snapshot

Generated by [scripts/capture_option_c_baseline.py](../scripts/capture_option_c_baseline.py) and stored at [tests/integration/snapshots/option_c_baseline.yaml](../tests/integration/snapshots/option_c_baseline.yaml).

### Coverage and discovery

- `scenarios/` YAML discovery: **0 files** — the `scenarios/` tree is organized around user-persona walkthroughs (`walkthrough.md`, `*.xlsx` inputs, `run_*.py` scripts) rather than YAML configs. This is expected given the current scenario workflow (per `feedback_scenario_workflow.md`).
- `examples/` YAML discovery: **14 files** — these are the runnable YAML configs today. The capture script picks them up so Stage 3's shadow-mode has real regression anchors beyond just Cells 28 / 58. Rationale documented in the script docstring.

### Scenario count

**14 / 14 runnable YAML configs captured; 0 errors; 0 skipped.**

All scenarios ran the full chain to completion. One (`swir_aerial_gas.yaml`) logs a dual-path MTF consistency warning (max_err_x = 0.052 vs tolerance 0.050) — not a failure, and orthogonal to Option C.

### Fixed λ grid

```
[0.5, 0.7, 1.0, 1.6, 2.2, 3.5, 4.0, 4.5, 8.0, 10.0, 12.0]  µm
```

Each scenario samples only the subset of this grid that falls inside its own `filter_min_um/filter_max_um` band; out-of-band entries are stored as `null`.

---

## Stage 3 shadow-mode scope

Classification per Stage 0 step 6 of the plan. These buckets are the gate for the Stage 3 shadow-mode assertion:

- **invariant** — must match at rtol=1e-6 through Stage 5; any divergence during Stage 3 is a hard test failure.
- **expected_to_change_at_stage_3** — legitimate physics correction in Stage 3 (two-leg τ_sun/τ_up, L_bg,aperture branch). Each eventual delta requires a Stage 3 "goldens changed" entry with physical justification.
- **expected_to_change_at_stage_6** — MWIR scenarios; Stage 6 separates E_sky into scattered-solar vs. atm-thermal components, which is where MWIR downwelling gets corrected.
- **unclassified** — cannot be decided mechanically from the YAML; needs manual review before Stage 3.

### Classification summary (14 scenarios)

| Classification | Count |
|---|---|
| invariant | 3 |
| expected_to_change_at_stage_3 | 5 |
| expected_to_change_at_stage_6 | 6 |
| unclassified | 0 |

### Per-scenario table

| Scenario | Classification | Cell Ref | Justification |
|---|---|---|---|
| [examples/templates/lwir_aerial_survey.yaml](../examples/templates/lwir_aerial_survey.yaml) | invariant | Cell 28 | Terrestrial LWIR extended, h_tgt = 0, `simple` atm → handled correctly today. |
| [examples/templates/lwir_geo.yaml](../examples/templates/lwir_geo.yaml) | invariant | Cell 28 | Same as above, GEO altitude but still terrestrial LWIR extended with `simple` atm. |
| [examples/templates/lwir_leo_sounder.yaml](../examples/templates/lwir_leo_sounder.yaml) | invariant | Cell 28 | Same as above, LEO sensor, ground target, `simple` atm. |
| [examples/templates/swir_leo.yaml](../examples/templates/swir_leo.yaml) | expected_to_change_at_stage_3 | — | SWIR — Stage 3 adds two-leg τ_sun/τ_up; today's single-τ under-attenuates the down-leg. |
| [examples/templates/swir_aerial_gas.yaml](../examples/templates/swir_aerial_gas.yaml) | expected_to_change_at_stage_3 | — | SWIR aerial; same Stage 3 two-leg concern. Also has a pre-existing MTF consistency warning orthogonal to Option C. |
| [examples/templates/vnir_aerial.yaml](../examples/templates/vnir_aerial.yaml) | expected_to_change_at_stage_3 | — | VNIR reflective — Stage 3 adds two-leg τ split + E_sky scattered-solar term. |
| [examples/templates/vnir_leo_highres.yaml](../examples/templates/vnir_leo_highres.yaml) | expected_to_change_at_stage_3 | — | Same as above. |
| [examples/templates/vnir_leo_multispectral.yaml](../examples/templates/vnir_leo_multispectral.yaml) | expected_to_change_at_stage_3 | — | Same as above. |
| [examples/ground_truth_mwir.yaml](../examples/ground_truth_mwir.yaml) | expected_to_change_at_stage_6 | — | MWIR mixed — Stage 6 separates E_sky scattered vs. thermal; today's single-graybody approximation will shift. |
| [examples/mwir_leo_minimal.yaml](../examples/mwir_leo_minimal.yaml) | expected_to_change_at_stage_6 | — | Same as above. |
| [examples/templates/mwir_aerial_flir.yaml](../examples/templates/mwir_aerial_flir.yaml) | expected_to_change_at_stage_6 | — | Same as above. |
| [examples/templates/mwir_leo_pushbroom.yaml](../examples/templates/mwir_leo_pushbroom.yaml) | expected_to_change_at_stage_6 | — | Same as above. |
| [examples/templates/mwir_leo_starer.yaml](../examples/templates/mwir_leo_starer.yaml) | expected_to_change_at_stage_6 | — | Same as above. |
| [examples/templates/mwir_ground_test.yaml](../examples/templates/mwir_ground_test.yaml) | expected_to_change_at_stage_6 | — | MWIR ground test — band-rule bucketed here. Note: this is a candidate `no_atmosphere (ground_test)` sub-case that will ultimately land in **Stage 7** with the sub-case presets. The coarse classifier uses wavelength only; manual reviewer should upgrade this entry's `classification` field before Stage 3 exits if a cleaner Stage-7 label is desired. |

### Known classifier caveats

- The classifier is conservative: it routes on wavelength band + atmosphere model, not on descriptor fields (which do not exist pre-Option-C). A reviewer with more context can tighten labels by editing the `classification` field in the YAML snapshot directly before Stage 3 runs.
- The `mwir_ground_test.yaml` entry, as noted, is probably a Stage 7 no_atmosphere/ground_test cell but the heuristic prefers the coarser Stage 6 bucket. Flag for manual reclassification if needed.
- None of the scenarios sets `h_tgt > 0` explicitly, so no Table C (airborne target-at-altitude) scenarios appear — the capture script would surface them as Stage 3 or Stage 5 deltas once they exist.

---

## Task 7 verification

After new anchor tests were added:

| Gate | Value |
|---|---|
| Pre-existing test pass count | 2103 |
| New anchor tests added | 8 |
| Expected new pass count | ≥ 2111 |
| Observed new pass count | 2111 |

All pre-existing tests still pass; no regressions introduced.

---

## Files changed / added in Stage 0

- Added tag `pre-option-c-baseline` at `4953c90` (local only).
- Created [tests/integration/test_option_c_anchors.py](../tests/integration/test_option_c_anchors.py) — 8 anchor tests.
- Created [scripts/capture_option_c_baseline.py](../scripts/capture_option_c_baseline.py) — snapshot capture driver.
- Created [tests/integration/snapshots/option_c_baseline.yaml](../tests/integration/snapshots/option_c_baseline.yaml) — the Stage 0 snapshot.
- Created this document — [docs/validation/option_c_baseline.md](option_c_baseline.md).

No changes to `src/radiant/source/`, `src/radiant/atmosphere/`, or `src/radiant/core/` (reconnaissance-only constraint).

---

## Stage 4 landing — descriptor-only Source, Atmosphere owns assembly

**Landed**: 2026-04-19
**Reference**: ADR-0002 Decision #13 (no BackgroundDescriptor in extended
terrestrial/airborne), Decision #15 (`source.background.*` is adjacent-scene
only).

Stage 4 completes the Option C transition. `SourceStage.run()` now publishes
only descriptors (`target`, `background`, `los_geometry`) and regime
classification — it no longer emits a radiance `at_target` frame or an
`L_background` stage_output. `AtmosphereStage.run()` owns 100% of the
ε·B(T_t) and background-arm assembly via `assemble_target_at_aperture` /
`assemble_background_at_aperture`, and publishes `at_aperture_target`
and (when a descriptor exists) `at_aperture_background` frames. The
canonical `at_aperture` frame is aliased to `at_aperture_target` so the
OpticsStage contract stays stable.

### Pinned anchor values — Stage 4 revision

The Cell 28 and Cell 58 SNRs / NEDTs moved: extended scenes no longer
synthesise a `L_background` that was previously double-counted in the
noise RSS via the `background_shot` term. `L_aperture(λ)` is unchanged
(target-arm radiance transport is unchanged).

| Scenario | Quantity | Stage 0 value | Stage 4 value | Change |
|---|---|---|---|---|
| Cell 28 (terrestrial LWIR) | SNR | 5.52081 | 315.549 | +5615% (bg_shot → 0) |
| Cell 28 | NEDT | 11.7734 K | 0.205986 K | −98.25% |
| Cell 28 | L_aperture grid | unchanged | unchanged | 0 |
| Cell 58 (space LWIR exo) | SNR | 6.47050 | 315.975 | +4783% |
| Cell 58 | NEDT | 9.08630 K | 0.186069 K | −97.95% |
| Cell 58 | L_aperture grid | unchanged | unchanged | 0 |
| MWIR LEO minimal (golden) | SNR | 666.214 | 866.114 | +30.0% |
| MWIR LEO minimal (golden) | noise_rss | 1126.16 | 866.24 | −23.1% |
| ground_truth_mwir (exo) | SNR | 12.79 | 14.22 | +11.2% |

**Why the SNR jumps**: pre-Stage-4, SpectralIntegrationStage computed a
`background_e` from the (scalar) `L_background` stage_output produced
by SourceStage for every scenario — including extended terrestrial and
`exo` space scenarios where that scalar carried no physical meaning
(it was user-set `source.background.temperature/emissivity`, an
adjacent-scene concept). The shot-noise on that background
(`background_shot = √background_e`) then appeared in the RSS, dragging
the SNR down. Stage 4 correctly returns `BackgroundDescriptor=None`
for extended terrestrial (Decision #13) and `ColdSpaceBackground()`
with `L_bg≡0` for `no_atmosphere` + `space`, both of which yield
`background_e=0` and eliminate the spurious noise contribution.
Decision #15 additionally warns (Rule 17) when users supply
`source.background.*` in a scene where those parameters are ignored.

### Rule 9 preservation

EE_box remains applied exactly once and only in the right regimes:

- **Extended** — `background_e=0` (no bg reference); EE_box≡1 guarded.
- **Point source** — target-only photon rate uses `at_aperture_target −
  L_path_up` to isolate ε·B(T_t)·τ_up, then multiplied by EE_box after
  integration (unchanged semantics).
- **Sub-pixel** — `L_mixed = ff·L_target_through·EE_box +
  (1−ff)·L_bg_through + L_path_through` decomposed from the new frames
  by subtracting `L_path_up` and `L_path_full` respectively; EE_box
  applied only to the target contribution (unchanged semantics).

### Files touched in Stage 4

Source code:
- `src/radiant/source/stage.py` — removed `at_target` frame emission and
  `L_background` stage_output; now publishes descriptors + regime only.
- `src/radiant/source/_inferrer.py` — added Decision #15 UserWarning
  when `source.background.*` is user-set in an extended
  terrestrial/airborne scene.
- `src/radiant/atmosphere/stage.py` — shadow-mode removed; authoritative
  descriptor-driven assembly with `at_aperture_target` /
  `at_aperture_background` frames (and an `at_aperture` alias for
  OpticsStage compatibility).
- `src/radiant/atmosphere/protocol.py` — removed `build_state` from
  the Protocol (implementations retain it as an impl detail for
  MODTRAN fallback).
- `src/radiant/spectral_integration/stage.py` — reads the new frames
  and decomposes target-only / background-only / path-only radiance
  via `L_path_up` and `L_path_full`.

Tests / goldens:
- `src/radiant/atmosphere/tests/test_stage.py` — rewritten for
  descriptor-driven contract.
- `src/radiant/atmosphere/tests/test_evaluate.py` — shadow-mode symbol
  assertion removed.
- `src/radiant/source/tests/test_stage.py` — removed `at_target` /
  `L_background` legacy assertions; added descriptor-publication
  tests.
- `tests/integration/test_chain_extended.py`,
  `tests/integration/test_ground_truth_mwir.py`,
  `tests/integration/test_mwir_leo_minimal.py` — replaced `at_target`
  reads with `at_aperture_target`; updated SNR expectation for
  `ground_truth_mwir` (12.79 → 14.22).
- `tests/integration/test_option_c_anchors.py` — Cell 28 and Cell 58
  pinned values updated with Stage 4 physics justification.
- `tests/integration/test_chain_spatial.py` — golden SNR updated
  (666.21 → 866.11) with justification.
- `tests/integration/golden/mwir_leo_minimal.json` — regenerated
  (noise_rss, snr) with provenance note.

### Test-suite state after Stage 4

Full suite: **2269 passed / 0 failed** (442 s). No regressions; anchor
tests and all reclassified scenarios match their Stage 4 pinned values.
Tag the commit `option-c-landed`.

---

## Stage 6 landing — E_sky decomposition (scattered-solar vs atm-thermal)

**Landed**: 2026-04-20
**Reference**: ADR-0002 / [Option C plan §6](Option_C_Implementation_Plan.md)
**Tag**: `post-stage-6-baseline` (annotated).

Stage 6 replaces the single-graybody `E_sky` placeholder with two
physically-distinct components. The *consumed* sum (fed to
`_diffuse_sky_term` in `assembly.py`) is unchanged, so the §6.1
assembly math does not change — only the decomposition unlocks
per-component MWIR audits (matrix cells 25/26/40/41).

Formulas (both on the h_tgt→h_sensor vertical slab):

```
E_sky_scattered(λ, h_tgt) = E_TOA(λ) · cos(θ_s) · ω₀(λ) · (1 − τ_down,vert(λ))
E_sky_thermal(λ, h_tgt)   = (1 − τ_down,vert(λ)) · π · B(λ, T_atm_eff(h_tgt))
```

Physics properties:

- VIS/NIR (λ ≲ 1 µm): E_TOA large (~1000 W/m²/µm), Planck(T_atm) tiny
  (Wien tail at T ≈ 290 K) → `E_sky_thermal / E_sky_scattered < 1e-6`.
- LWIR (λ ≳ 8 µm): E_TOA tiny (Wien tail at T ≈ 5778 K), Planck(T_atm)
  moderate → `E_sky_scattered / E_sky_thermal < 1e-3`.
- MWIR (λ ≈ 4 µm): both components within one order of magnitude
  (crossover regime).
- `cos(θ_s) ≤ 0` (sun at or below horizon): `E_sky_scattered = 0`
  exactly (matches the `_direct_solar_term` sentinel behaviour).
- `ω₀ ≤ 1` and `(1 − τ_down) ≤ 1` ⇒ `E_sky_scattered ≤ E_TOA · cos(θ_s)`
  (single-scatter energy-conservation ceiling).

### Post-Stage-6 anchor values

Cell 28 and Cell 58 are **extended-scene T1Thermal** scenarios
(ρ ≡ 0 — pure thermal graybody with no reflective coupling). The
assembly's diffuse-sky branch multiplies by ρ, so neither Stage-6
component reaches the at-aperture radiance on those cells.
Consequently the Cell 28 / Cell 58 anchor values are **bit-invariant**
post-Stage-6:

| Scenario | Quantity | Stage 4 value | Stage 6 value | Δ |
|---|---|---|---|---|
| Cell 28 (terrestrial LWIR) | SNR | 315.54933814882156 | 315.54933814882156 | 0 |
| Cell 28 | NEDT | 0.20598616453385415 K | 0.20598616453385415 K | 0 |
| Cell 28 | MTF @ Nyquist | 0.07587823 | 0.07587823 | 0 |
| Cell 28 | L_aperture grid | unchanged | unchanged | 0 |
| Cell 58 (space LWIR exo) | SNR | 315.9745217365823 | 315.9745217365823 | 0 |
| Cell 58 | NEDT | 0.18606860088514812 K | 0.18606860088514812 K | 0 |
| Cell 58 | MTF @ Nyquist | 0.06690769 | 0.06690769 | 0 |
| Cell 58 | L_aperture grid | unchanged | unchanged | 0 |

No `CELL28_PINNED` / `CELL58_PINNED` edit was required. The anchors
remain at rtol = 1e-6 vs Stage 4.

MWIR mixed / reflective scenarios — where `E_sky_scattered` and
`E_sky_thermal` do couple through a nonzero ρ — will exercise the new
decomposition; those truth anchors live in
`src/radiant/atmosphere/tests/test_e_sky_decomposition.py` (3 Category-C
anchors + 6 fragility / sum-preservation / inspectability tests).

### Test-suite state after Stage 6

Full suite: **2316 passed / 0 failed** (≈ 7 min). +13 tests vs Stage 4
(12 Stage-6 Category-C anchors + 1 `AssemblyComponents`
report-components test in `test_assembly.py`). No regressions; zero
golden-file edits.

### Files touched in Stage 6

Source code:
- `src/radiant/atmosphere/simple.py` — replaced
  `E_sky_scattered = zeros_like(lam)` placeholder with the single-scatter
  formula; added `cos θ_s` horizon-tolerance guard to the existing
  `L_path_up` / `L_path_full` scatter-geom blocks (prevents
  `AtmosphericGeometry` from raising when `θ_s` rounds through π/2 on
  the IEEE-754 grid).
- `src/radiant/atmosphere/assembly.py` — added `AssemblyComponents`
  dataclass and `report_components: bool = False` kwarg to
  `assemble_target_at_aperture`; split `_diffuse_sky_term` into
  scattered / thermal helper functions (consumed sum unchanged).
- `src/radiant/atmosphere/stage.py` — publishes `E_sky_scattered` and
  `E_sky_thermal` stage_outputs for Rule-16 inspectability.

Tests / goldens:
- `src/radiant/atmosphere/tests/test_e_sky_decomposition.py` — new,
  12 Category-C tests (3 anchors + 6 fragility/sum/inspect tests +
  3 parametrised at-or-below-horizon cases).
- `src/radiant/atmosphere/tests/test_assembly.py` — added Stage-6
  MWIR-mixed anchor assertion (`E_sky = E_sky_scattered + E_sky_thermal`
  consumption) and a new `AssemblyComponents` round-trip test.
- `src/radiant/atmosphere/tests/test_evaluate.py` — renamed
  `test_E_sky_scattered_is_zero_in_v1` → `test_E_sky_scattered_non_negative`
  (the zero precondition no longer holds — the scattered component is
  now physically populated).

