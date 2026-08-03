# Scenario 7.1 Gaps: Predicted vs. Measured NEDT Reconciliation

## Summary
Predicted NEDT at 25°C = 74.17 mK, measured = 127.0 mK, gap = 52.83 mK.
Noise is signal-shot-dominated (signal_shot 99.9%; `background_shot` = 0 in
the extended regime under Decision #13 — the blackbody fills the target pixel,
so the 295 K shroud is not separably present there).
f-number is the most sensitive parameter (0.7428 mK per 1% change).

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-07-08). No Results-affecting landing moved this scenario — it runs on
`atmosphere.model = "exo"`, which every in-window landing's scope statement
excludes (CU-224 leaves exo/vacuum paths exactly unchanged; CU-267 and CU-253
are `simple`-atmosphere only). This summary had simply never been refreshed to
the post-Decision-#13 prediction that `walkthrough.md` already carried.*

## Gap Closure Status (since previous run)

| # | Gap | Severity | Status | Evidence |
|---|-----|----------|--------|----------|
| 1 | No per-term NEDT breakdown | Medium | **CLOSED** | `result.metrics["nedt_K"]` and `result.noise_terms` both available; script computes `NEDT_i = σ_i / (dS/dT)` |
| 2 | No built-in `reconcile(measured)` method | Low | Open | Script computes σ_missing = √(σ_meas² − σ_pred²) manually |
| 3 | No lab/TVAC mode documentation | Low | **CLOSED** | `atmosphere.model: "exo"` is the documented approach; works correctly |
| 4 | dS/dT not exposed (finite-difference workaround) | Low | Open | Script runs RADIANT at T, T±δ and computes derivative numerically |
| 5 | ROIC glow not modeled as noise source | Low | Open | `glow_shot` noise term exists but always evaluates to 0 |
| 6 | **NEW — Nearfield emission = 0 in scalar transmission mode** | **HIGH** | Open | In scalar mode, lumped element is refractive (ε = 1 − T − R = 0 by Kirchhoff); no mirror self-emission |

## Gap 6 Detail — Nearfield Emission Missing (HIGH)

### Observation
In the 25°C noise breakdown:
```
nearfield_shot:   0.00 e⁻ RMS (0.0%)
```
With warm optics at 295.15 K and a 3.5–5.0 µm band, mirror self-emission should be a significant contributor — Planck radiance from ε_mirror ≈ 0.02 per surface × 4 surfaces gives a non-negligible photon flux.

### Root Cause
RADIANT's scalar transmission mode lumps all optical elements into a single τ, and applies Kirchhoff's law for a **refractive** element:
```
T + R = 1   →   ε = 1 − T − R = 0
```
Mirrors have ε = 1 − R directly, not ε = 1 − T − R. The scalar mode cannot distinguish refractive from reflective elements.

### Impact
- Warm-optics MWIR/LWIR systems under-predict total background and total NEDT
- Explains a portion of the 52.83 mK gap for Karen's TVAC test (primary optics at 22 °C)
- Cold-stop sweeps (scenario 7.4) are non-functional in scalar mode — no nearfield to reduce

### Workarounds
- Use `optics.mode: "key_elements"` with per-surface emissivity derived from R
- Use `optics.mode: "full_prescription"` for Zemax-exported designs

### Recommended Fix
- Expose an `optics.scalar_emissivity` parameter for users who want a lumped ε estimate in scalar mode
- Document the refractive-lump assumption clearly in scalar-mode help

## Non-Gap Observations

- `nearfield_shot` = 0 in scalar transmission mode is **correct physics** under the refractive-lump assumption — it is a modeling-scope limitation, not a bug.
- Measurements vs. prediction gap (52.83 mK at 25°C) most likely combines: (a) missing mirror self-emission (Gap 6), (b) spatial PRNU/DSNU inflating temporal NEDT, (c) TVAC chamber stray light, (d) blackbody calibration uncertainty (±0.02°C × dS/dT ≈ 100 e⁻).
- NEDT trend vs. BB temperature is correct (1/√signal behavior confirmed).

## Drift Fix 2026-07-07 — Stage-7 h_sensor precondition (registry Gap 42)

The script raised in `validate_no_atmosphere_subcase` after the Stage-7
landing: `atmosphere.model = "exo"` auto-infers the `no_atmosphere / space`
sub-case, which requires a positive user-set `platform.h_sensor` for the
Earth-limb intercept check (the `lab_test` sub-case has no `Sensor.from_dict`
path — registry Gap 42). Fixed in the Phase R sweep pass by adding the
placeholder `platform.h_sensor = 1.0` m (bench height); no radiometric
effect. Remove the placeholder when Gap 42 lands a first-class lab path.
