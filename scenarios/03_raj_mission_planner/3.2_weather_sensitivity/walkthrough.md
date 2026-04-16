# Scenario 3.2 Walkthrough: Weather Sensitivity — How Bad Can the Weather Get?

## Persona
Raj, mission planner. He has a baselined MWIR reconnaissance sensor on a 500 km SSO and needs a "go/no-go" weather threshold. At what visibility does performance drop below mission requirement (NIIRS ≥ 4.0)? How does precipitable water vapor affect imagery quality?

## System Configuration
| Parameter | Value | Unit |
|---|---|---|
| Aperture diameter | 30 | cm |
| Focal length | 120 | cm |
| f-number | 4.0 | — |
| Optical transmission | 75 | % |
| Pixel pitch | 18 | µm |
| QE | 70 | % |
| Dark current | 150 | e-/s |
| Read noise | 18 | e- RMS |
| FWC | 500,000 | e- |
| Integration time | 1.0 | ms |
| Orbit altitude | 500 | km |
| Spectral band | 3.5–5.0 | µm |
| Target temperature | 300 | K |
| Background temperature | 290 | K |
| Standard atmosphere | midlat_summer | — |
| GSD | 7.5 | m |

## Trade Study Design
- **Visibility sweep**: 2–100 km (25 points, log-spaced) at PWV = 1.4 cm
- **PWV sweep**: 0.5–5.0 cm (15 points, linear) at visibility = 23 km
- **Named conditions**: 8 realistic weather scenarios (crystal clear to heavy haze)
- **2D grid**: 6 visibility × 6 PWV = 36 evaluations
- **Total evaluations**: 25 + 15 + 8 + 36 = 84
- **NIIRS requirement**: ≥ 4.0 (threshold), ≥ 5.0 (goal)

## Key Results

### Visibility Sweep (PWV = 1.4 cm)
| Visibility [km] | τ_band [—] | Signal [e-] | SNR [—] | NIIRS [—] |
|---|---|---|---|---|
| 2.0 | 0.449 | 241,571 | 331.4 | 4.46 |
| 5.3 | 0.499 | 245,618 | 335.8 | 4.47 |
| 23.1 | 0.524 | 247,589 | 337.9 | 4.47 |
| 100.0 | 0.530 | 248,053 | 338.4 | 4.47 |

**Key finding**: NIIRS barely changes with visibility (4.46 → 4.47 across entire range). MWIR aerosol scattering is negligible because the Angstrom exponent (α ≈ 1.3) causes extinction to scale as λ^(-1.3), making 4.2 µm aerosol extinction ~13× weaker than at 0.55 µm. Visibility affects visible-band sensors far more than MWIR.

### PWV Sweep (visibility = 23 km)
| PWV [cm] | τ_band [—] | Signal [e-] | SNR [—] | NIIRS [—] | ΔNIIRS [—] |
|---|---|---|---|---|---|
| 0.50 | 0.785 | 287,663 | 374.1 | 4.54 | +0.00 |
| 1.40 | 0.524 | 247,589 | 337.9 | 4.47 | -0.07 |
| 3.00 | 0.252 | 212,027 | 302.4 | 4.39 | -0.14 |
| 5.00 | 0.111 | 197,614 | 286.7 | 4.36 | -0.18 |

**Key finding**: PWV has a larger effect than visibility. Band-mean transmittance drops from 0.79 to 0.11 (7× reduction!) as PWV goes from dry desert to tropical humid. But NIIRS only drops 0.18 because NIIRS depends on log₁₀(SNR) — a 7× transmittance reduction causes only a ~30% SNR change (signal drops but noise floor remains dominated by background/nearfield photons).

### Named Weather Conditions — Go/No-Go
| Condition | Visibility [km] | PWV [cm] | τ_band [—] | SNR [—] | NIIRS [—] | Status |
|---|---|---|---|---|---|---|
| Arctic dry | 50 | 0.5 | 0.791 | 374.6 | 4.54 | GO |
| Crystal clear | 100 | 0.8 | 0.693 | 360.9 | 4.51 | GO |
| Clear | 50 | 1.0 | 0.632 | 352.4 | 4.50 | GO |
| Standard | 23 | 1.4 | 0.524 | 337.9 | 4.47 | GO |
| Light haze | 10 | 2.0 | 0.394 | 320.8 | 4.43 | GO |
| Moderate haze | 5 | 3.0 | 0.246 | 302.4 | 4.39 | GO |
| Heavy haze | 2 | 4.0 | 0.145 | 291.2 | 4.37 | GO |
| Tropical humid | 10 | 5.0 | 0.108 | 286.6 | 4.36 | GO |

**Result**: All 8 conditions are GO — NIIRS ≥ 4.0 at every weather condition tested. However, **no condition meets the NIIRS ≥ 5.0 goal**. The best case (Arctic dry) only reaches 4.54. The NIIRS goal of 5.0 is unachievable with 7.5 m GSD regardless of weather.

### 2D NIIRS Grid (Visibility × PWV)
All 36 grid cells meet NIIRS ≥ 4.0 (100% GO rate). The grid shows that PWV drives the variation (columns vary more than rows), confirming that water vapor absorption is the dominant atmospheric effect in MWIR.

### Noise Budget at Baseline (23 km, 1.4 cm)
| Noise Term | σ [e- RMS] | Fraction [%] |
|---|---|---|
| signal_shot | 497.6 | 46.1 |
| background_shot | 448.0 | 37.4 |
| nearfield_shot | 297.1 | 16.4 |
| read_noise | 18.0 | 0.1 |
| quantization | 9.2 | 0.0 |
| dark_shot | 0.4 | 0.0 |

Signal shot noise dominates (46%), followed by background (37%) and nearfield from warm optics (16%). Read noise and dark current are negligible at this signal level.

## Physics Discussion

### Why MWIR Is Robust to Weather
1. **Aerosol scattering**: Aerosol extinction scales as λ^(-α) where α ≈ 1.3 for rural aerosol. At λ = 4.2 µm vs. 0.55 µm (visible), aerosol extinction is reduced by (4.2/0.55)^1.3 ≈ 13×. This makes visibility (which characterizes aerosol at 550 nm) a poor predictor of MWIR performance.

2. **Water vapor absorption**: H₂O has absorption bands at 2.7 µm and 6.3 µm that bracket the MWIR window (3.5–5.0 µm). The 4.3 µm CO₂ band further erodes the window. As PWV increases, band-mean transmittance drops substantially (0.79 → 0.11), but the SNR impact is muted because noise is dominated by photon noise from background and nearfield emission — atmospheric attenuation reduces both signal AND background proportionally.

3. **GSD dominates NIIRS**: The GIQE-5 equation is NIIRS = 9.57 − 3.32·log₁₀(GSD_inch) + 1.559·log₁₀(SNR) + ... The GSD term (−3.32 coefficient) dominates over the SNR term (1.559 coefficient). At 7.5 m GSD = 295 inches, the GSD penalty is −3.32 × log₁₀(295) = −8.20. Even if SNR could be infinite, NIIRS is capped by GSD. This is why weather barely affects NIIRS — it can only modulate SNR, which has a small influence.

4. **Why the NIIRS goal is unachievable**: NIIRS ≥ 5.0 would require GSD ≤ ~2.5 m at this SNR level. To achieve that with 18 µm pixels at 500 km, the focal length would need to be ~3.6 m (f/12) — a much larger telescope.

### Why SNR Doesn't Track Transmittance Linearly
Signal is proportional to atmospheric transmittance, but noise is NOT. At 300 K target in MWIR:
- Signal_shot ∝ √(τ × L_target) — decreases with lower transmittance
- Background_shot ∝ √(τ × L_background) — also decreases
- Nearfield_shot ∝ √(L_optics) — **independent** of atmosphere
- Path radiance adds to signal — partially compensates transmittance loss

So when τ drops, both signal and photon noise decrease, but nearfield noise stays constant. The net effect on SNR is muted.

### Integration Time Choice
1 ms is appropriate for a staring sensor in 500 km LEO:
- Ground velocity ≈ 7 km/s
- Smear during integration = 7000 m/s × 0.001 s = 7.0 m ≈ 0.93 pixels
- Sub-pixel smear preserves spatial resolution
- Well fill: 248K e- = 50% of 500K FWC (safe)

## Gap Findings

### Gap 1: NIIRS Never Reaches Goal — GSD Limit Not Surfaced
RADIANT computes NIIRS correctly, but doesn't proactively flag that GSD is the binding constraint and no amount of atmospheric improvement can reach the NIIRS goal. A "GSD-limited NIIRS ceiling" metric would help mission planners understand this immediately.

### Gap 2: No Threshold-Crossing Finder
The script manually interpolates to find the visibility at NIIRS = 4.0. RADIANT should have a `Sensor.find_threshold(sweep_param, metric, target_value)` method that returns the parameter value at which a metric crosses a threshold.

### Gap 3: No Named Atmosphere Presets
Raj thinks in terms of "clear", "haze", "tropical" — not numerical visibility and PWV values. RADIANT should offer named atmosphere presets that set visibility, PWV, aerosol type, and standard atmosphere profile together.

### Gap 4: No Go/No-Go Report Format
RADIANT could generate a structured go/no-go assessment given a metric threshold — traffic-light tables with green/yellow/red cells, automatic pass/fail labels, and a summary.

### Gap 5: No 2D Contour Output
The 2D visibility × PWV sweep generates a grid of NIIRS values. RADIANT should support 2D contour plot output with constraint lines (NIIRS = 4.0, NIIRS = 5.0 contours overlaid).

### Gap 6: Band-Mean Transmittance Not in Standard Outputs
`tau_atm` is a spectral array in `stage_outputs["atmosphere"]`, but there's no scalar `tau_band_mean` for quick reference. This required manual averaging in the script.

### Gap 7: No Visibility-to-Aerosol Mapping Documentation
The relationship between meteorological visibility (at 550 nm) and MWIR aerosol extinction is non-obvious. RADIANT should document that visibility is a visible-band concept and its impact at MWIR is reduced by the Angstrom exponent.
