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
| 2.0 | 0.449 | 254,116 | 503.7 | 4.50 |
| 5.3 | 0.499 | 259,616 | 509.1 | 4.51 |
| 23.1 | 0.524 | 262,323 | 511.8 | 4.51 |
| 100.0 | 0.530 | 262,962 | 512.4 | 4.52 |

**Key finding**: NIIRS barely changes with visibility (4.50 → 4.52 across entire range). MWIR aerosol scattering is negligible because the Angstrom exponent (α ≈ 1.3) causes extinction to scale as λ^(-1.3), making 4.2 µm aerosol extinction ~13× weaker than at 0.55 µm. Visibility affects visible-band sensors far more than MWIR.

### PWV Sweep (visibility = 23 km)
| PWV [cm] | τ_band [—] | Signal [e-] | SNR [—] | NIIRS [—] | ΔNIIRS [—] |
|---|---|---|---|---|---|
| 0.50 | 0.785 | 309,833 | 556.3 | 4.57 | +0.00 |
| 1.46 | 0.509 | 259,791 | 509.3 | 4.51 | -0.06 |
| 3.07 | 0.252 | 219,237 | 467.8 | 4.45 | -0.12 |
| 5.00 | 0.111 | 200,871 | 447.7 | 4.42 | -0.15 |

**Key finding**: PWV has a larger effect than visibility. Band-mean transmittance drops from 0.79 to 0.11 (7× reduction!) as PWV goes from dry desert to tropical humid. But NIIRS only drops 0.15 because NIIRS depends on log₁₀(SNR) — a 7× transmittance reduction causes only a ~19% SNR change (signal and its shot noise both drop, so SNR ∝ √signal moves slowly).

### Named Weather Conditions — Go/No-Go
| Condition | Visibility [km] | PWV [cm] | τ_band [—] | SNR [—] | NIIRS [—] | Status |
|---|---|---|---|---|---|---|
| Arctic dry | 50 | 0.5 | 0.791 | 556.9 | 4.57 | GO |
| Crystal clear | 100 | 0.8 | 0.693 | 540.0 | 4.55 | GO |
| Clear | 50 | 1.0 | 0.632 | 529.7 | 4.54 | GO |
| Standard | 23 | 1.4 | 0.524 | 511.8 | 4.51 | GO |
| Light haze | 10 | 2.0 | 0.394 | 490.7 | 4.49 | GO |
| Moderate haze | 5 | 3.0 | 0.246 | 467.7 | 4.45 | GO |
| Heavy haze | 2 | 4.0 | 0.145 | 453.5 | 4.43 | GO |
| Tropical humid | 10 | 5.0 | 0.108 | 447.6 | 4.42 | GO |

**Result**: All 8 conditions are GO — NIIRS ≥ 4.0 at every weather condition tested. However, **no condition meets the NIIRS ≥ 5.0 goal**. The best case (Arctic dry) only reaches 4.57. The NIIRS goal of 5.0 is unachievable with 7.5 m GSD regardless of weather. Weather-induced NIIRS variation = 0.15.

### 2D NIIRS Grid (Visibility × PWV)
All 36 grid cells meet NIIRS ≥ 4.0 (100% GO rate). The grid shows that PWV drives the variation (columns vary more than rows), confirming that water vapor absorption is the dominant atmospheric effect in MWIR.

### Noise Budget at Baseline (23 km, 1.4 cm)
| Noise Term | σ [e- RMS] | Fraction [%] |
|---|---|---|
| signal_shot | 512.2 | 99.8 |
| read_noise | 18.0 | 0.1 |
| quantization | 9.2 | 0.0 |
| dark_shot | 0.4 | 0.0 |
| nearfield_shot | 0.0 | 0.0 |

Signal shot noise dominates almost entirely (99.8%). Read noise and dark current are negligible at this signal level. There is **no separate background_shot term** — the extended MWIR scene is one radiance field, so its shot noise is `signal_shot` alone (ADR-0002 Decision #13). Removing the previously-equal background term is what raised SNR versus older baselines. **Note**: `nearfield_shot = 0` — scalar-mode refractive-lump assumption does not model mirror self-emission (see Gap 8). Total noise = 512.6 e⁻ RMS, SNR = 511.8, NIIRS = 4.51, RER = 0.6011, MTF@Nyquist = 0.2526.

## Physics Discussion

### Why MWIR Is Robust to Weather
1. **Aerosol scattering**: Aerosol extinction scales as λ^(-α) where α ≈ 1.3 for rural aerosol. At λ = 4.2 µm vs. 0.55 µm (visible), aerosol extinction is reduced by (4.2/0.55)^1.3 ≈ 13×. This makes visibility (which characterizes aerosol at 550 nm) a poor predictor of MWIR performance.

2. **Water vapor absorption**: H₂O has absorption bands at 2.7 µm and 6.3 µm that bracket the MWIR window (3.5–5.0 µm). The 4.3 µm CO₂ band further erodes the window. As PWV increases, band-mean transmittance drops substantially (0.79 → 0.11), but the SNR impact is muted because the system is signal-shot-limited: SNR ∝ √signal, so a 7× transmittance (hence signal) reduction moves SNR by only ~√7 ≈ 2.6× at most — and path radiance partially refills the signal, so the realized change is smaller still (~19%).

3. **GSD dominates NIIRS**: The GIQE-5 equation is NIIRS = 9.57 − 3.32·log₁₀(GSD_inch) + 1.559·log₁₀(SNR) + ... The GSD term (−3.32 coefficient) dominates over the SNR term (1.559 coefficient). At 7.5 m GSD = 295 inches, the GSD penalty is −3.32 × log₁₀(295) = −8.20. Even if SNR could be infinite, NIIRS is capped by GSD. This is why weather barely affects NIIRS — it can only modulate SNR, which has a small influence.

4. **Why the NIIRS goal is unachievable**: NIIRS ≥ 5.0 would require GSD ≤ ~2.5 m at this SNR level. To achieve that with 18 µm pixels at 500 km, the focal length would need to be ~3.6 m (f/12) — a much larger telescope.

### Why SNR Doesn't Track Transmittance Linearly
The system is signal-shot-limited, so SNR ∝ √signal, not signal. At 300 K target in MWIR:
- Signal ∝ τ × L_target — decreases with lower transmittance
- Signal_shot ∝ √signal — so SNR moves as the **square root** of the signal change
- Path radiance adds to the signal — partially compensates the transmittance loss

So a 7× drop in τ (hence signal) produces at most a √7 ≈ 2.6× SNR change, and path-radiance
refill shrinks it further to ~19%. Because NIIRS depends on log₁₀(SNR), that maps to only a
~0.15 NIIRS swing across the full weather range.

### Integration Time Choice
1 ms is appropriate for a staring sensor in 500 km LEO:
- Ground velocity ≈ 7 km/s
- Smear during integration = 7000 m/s × 0.001 s = 7.0 m ≈ 0.93 pixels
- Sub-pixel smear preserves spatial resolution
- Well fill: 248K e- = 50% of 500K FWC (safe)

## Gap Findings

See [gaps.md](gaps.md) for full detail with severity and status.

### Gap Closure Since Last Run
| Gap | Status | Notes |
|-----|--------|-------|
| NIIRS metric exposure | **CLOSED** | `result.metrics["niirs"]` available at `sensor.evaluate()` |
| GSD metric exposure | **CLOSED** | `result.metrics["gsd_geometric_mean_m"]` + cross/along-track variants |

### Open Gaps
- **Gap 1 (NIIRS ceiling not surfaced)**: still open. No GSD-limited NIIRS ceiling metric.
- **Gap 2 (No threshold-crossing finder)**: still open.
- **Gap 3 (No named atmosphere presets)**: still open.
- **Gap 4 (No go/no-go report format)**: still open.
- **Gap 5 (No 2D contour output)**: still open.
- **Gap 6 (Band-mean transmittance not scalar)**: still open.
- **Gap 7 (Visibility-to-aerosol doc missing)**: still open.
- **Gap 8 (NEW — Nearfield = 0 in scalar transmission mode)**: HIGH severity cross-scenario. Mirror self-emission from warm optics (293 K, 4 elements) not modeled. Under-predicts noise; the NIIRS here is slightly optimistic — real-world NIIRS would be ~0.02–0.04 lower depending on nearfield contribution.
