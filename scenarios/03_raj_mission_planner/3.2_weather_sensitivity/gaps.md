# Scenario 3.2 Gaps: Weather Sensitivity

## Summary
MWIR sensor at 500 km LEO, 7.5 m GSD.
Baseline (visibility = 23 km, PWV = 1.4 cm): NIIRS = 4.49, SNR = 500.8, τ_band = 0.5517.
All 8 named weather conditions meet NIIRS ≥ 4.0. Weather-induced NIIRS variation = 0.05.
None reach the NIIRS ≥ 5.0 goal — GSD, not weather, is the binding constraint.

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-08-02, pre-CU-321). Dominant mover: **CU-321** — the `(1−τ)·B` path
emission is now emitted at a height-resolved `T_eff(λ)` over the column, so the
MWIR signal falls ~18 % and SNR ~10 % from where CU-224 had put them. τ_band is
bit-identical.*

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
signal_shot:      555.2 e⁻ RMS (99.9%)
read_noise:        18.0 e⁻ RMS ( 0.1%)
nearfield_shot:     0.0 e⁻ RMS ( 0.0%)  ← should be ~200–300 e⁻
```
(The separate `background_shot` term shown in earlier vintages of this file no
longer exists — the extended MWIR scene is one radiance field, ADR-0002 #13.)

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
- NIIRS ≥ 5.0 unachievable at 7.5 m GSD regardless of weather. Reaching it requires GSD ≤ ~5.4 m — a longer telescope (f ~ 1.7 m vs current 1.2 m). (Earlier vintages of this line quoted ~2.5 m / f ~3.6 m; that did not follow from the GIQE-5 GSD term.)
- Photon-noise-limited budget (`signal_shot` alone = 99.9%) correctly identified.
- Weather effect on NIIRS enters entirely through SNR term (GIQE coefficient 1.559) — GSD and RER are fixed by geometry/optics.

---

## Real-data validation (2026-07-17)

D-block anchors validated the visibility axis (sensitivity same order,
absolute τ within 6%) and falsified the PWV axis magnitude: simple's
MWIR water response is ~5.5× too steep vs real MODTRAN (τ slope
−0.207/cm vs −0.038/cm) — saturated-band curve-of-growth physics that
linear-Beer PWV scaling cannot capture. This scenario's PWV go/no-go
conclusions are overstated accordingly; visibility conclusions stand.
Mirrored to `docs/tracking/Cleanup_Backlog.md` CU-161.
