# Option C Baseline — Stage 0 Capture

**Captured-at SHA**: `4953c90489db4734d33bd2ae16c4735ea78a0aae`
**Tag**: `pre-option-c-baseline` (local only — not pushed; `git push origin pre-option-c-baseline` when ready)
**Captured**: 2026-04-19
**Plan reference**: [docs/Option_C_Implementation_Plan.md](Option_C_Implementation_Plan.md) Stage 0

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
- Created this document — [docs/option_c_baseline.md](option_c_baseline.md).

No changes to `src/radiant/source/`, `src/radiant/atmosphere/`, or `src/radiant/core/` (reconnaissance-only constraint).
