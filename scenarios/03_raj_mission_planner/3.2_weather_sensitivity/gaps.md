# Scenario 3.2 Gaps: Weather Sensitivity

## Summary
MWIR sensor at 500 km LEO, 7.5 m GSD.
Baseline (visibility = 23 km, PWV = 1.4 cm): NIIRS = 4.29, SNR = 369.6, τ_band = 0.524.
All 8 named weather conditions meet NIIRS ≥ 4.0. Weather-induced NIIRS variation = 0.17.
None reach the NIIRS ≥ 5.0 goal — GSD, not weather, is the binding constraint.

## Gap Closure Status

| # | Gap | Severity | Status | Evidence |
|---|-----|----------|--------|----------|
| 1 | NIIRS ceiling not surfaced (GSD-limited) | Medium | Open | No `niirs_ceiling_from_gsd` metric; user must reason about GIQE |
| 2 | No threshold-crossing finder | Low | Open | Script manually interpolates NIIRS = 4.0 crossing |
| 3 | No named atmosphere presets | Low | Open | Raj must specify visibility + PWV numerically |
| 4 | No go/no-go report format | Low | Open | Script builds table manually |
| 5 | No 2D contour output | Low | Open | 2D grid of NIIRS values not rendered with constraint contours |
| 6 | Band-mean transmittance not in scalar outputs | Low | Open | `tau_atm` is spectral array; no scalar `tau_band_mean` |
| 7 | Visibility-to-aerosol mapping doc missing | Low | Open | No documentation that visibility is a visible-band concept |
| 8 | **NEW — Nearfield emission = 0 in scalar transmission mode** | **HIGH** | Open | Mirror self-emission not modeled; noise under-predicted by ~15–20% for warm-optics MWIR systems |
| — | NIIRS metric not exposed | Medium | **CLOSED** | `result.metrics["niirs"]` now available |
| — | GSD metric not exposed | Low | **CLOSED** | `result.metrics["gsd_geometric_mean_m"]` + cross/along-track |

## Gap 8 Detail — Nearfield Emission Missing (HIGH)

### Observation
Noise budget at baseline:
```
signal_shot:      497.6 e⁻ RMS (55.2%)
background_shot:  448.0 e⁻ RMS (44.7%)
nearfield_shot:     0.0 e⁻ RMS (0.0%)  ← should be ~200–300 e⁻
```

### Root Cause
Scalar transmission mode lumps all optics into a single τ and applies Kirchhoff for a **refractive** element (ε = 1 − T − R = 0). Mirrors have ε = 1 − R and should contribute self-emission at 293 K in the 3.5–5.0 µm band.

### Impact
- NIIRS is slightly optimistic (all baseline values likely 0.02–0.04 higher than real-world)
- Doesn't change go/no-go decision at NIIRS ≥ 4.0 (plenty of margin)
- Does affect quantitative noise budget comparisons with TVAC measurements

### Workaround
- Use `optics.mode: "key_elements"` with per-mirror ε = 1 − R

## Non-Gap Observations

- MWIR robustness to weather is real physics — Angstrom exponent α ≈ 1.3 makes aerosol extinction ~13× weaker in MWIR than visible.
- NIIRS ≥ 5.0 unachievable at 7.5 m GSD regardless of weather. Reaching it requires GSD ≤ ~2.5 m — a larger telescope (f ~ 3.6 m vs current 1.2 m).
- Photon-noise-limited budget (signal + background = 99.9%) correctly identified.
- Weather effect on NIIRS enters entirely through SNR term (GIQE coefficient 1.559) — GSD and RER are fixed by geometry/optics.
