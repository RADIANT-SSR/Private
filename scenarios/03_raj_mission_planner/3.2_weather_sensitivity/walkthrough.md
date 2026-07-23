# Scenario 3.2 Walkthrough: Weather Sensitivity — How Bad Can the Weather Get?


> **NIIRS applicability — engine update (CU-166).** Since this walkthrough was written, RADIANT added a metric-applicability gate: when one or more GIQE-5 inputs fall outside the calibration envelope — GSD 1.18–31.5 inch, RER 0.20–0.95, SNR 2–130 — the engine reports **NIIRS as N/A** by default instead of silently extrapolating. This configuration is outside that envelope, so the NIIRS values below are the **extrapolated** GIQE-5-form output: reproduce them with `performance.niirs.allow_extrapolated = true` and read them as a *relative trend, not a calibrated rating*. (SNR/τ/NIIRS figures were refreshed 2026-07-22 against the current engine, CU-176. No IR-calibrated IIRS model yet — see `docs/tracking/gaps.md` Gap 100.)

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
| 2.0 | 0.4759 | 166,369 | 407.4 | 4.35 |
| 5.3 | 0.5281 | 183,455 | 427.8 | 4.38 |
| 23.1 | 0.5542 | 191,998 | 437.7 | 4.40 |
| 100.0 | 0.5604 | 194,027 | 440.0 | 4.40 |

**Key finding**: NIIRS barely changes with visibility (4.35 → 4.40 across entire range). MWIR aerosol scattering is negligible because the Angstrom exponent (α ≈ 1.3) causes extinction to scale as λ^(-1.3), making 4.2 µm aerosol extinction ~13× weaker than at 0.55 µm. Visibility affects visible-band sensors far more than MWIR.

### PWV Sweep (visibility = 23 km)
| PWV [cm] | τ_band [—] | Signal [e-] | SNR [—] | NIIRS [—] | ΔNIIRS [—] |
|---|---|---|---|---|---|
| 0.50 | 0.5945 | 206,202 | 453.6 | 4.42 | +0.00 |
| 1.46 | 0.5517 | 191,098 | 436.7 | 4.40 | -0.03 |
| 3.07 | 0.4965 | 171,698 | 413.9 | 4.36 | -0.06 |
| 5.00 | 0.4435 | 153,141 | 390.8 | 4.32 | -0.10 |

**Key finding**: PWV still edges out visibility as the larger effect, but both are small. After the CU-161 curve-of-growth water refit (commit `0aebdda`), band-mean transmittance drops only from 0.59 to 0.44 (≈1.3× reduction) as PWV goes from dry desert to tropical humid — the saturated MWIR H₂O bands grow sub-linearly with absorber amount, not the ∝-PWV optical depth the old linear-Beer model produced (which read a spurious 7× drop). NIIRS falls just 0.10 across the full PWV range, because NIIRS depends on log₁₀(SNR) and the muted transmittance change moves SNR only ~14% (signal and its shot noise both drop, so SNR ∝ √signal moves slowly).

### Named Weather Conditions — Go/No-Go
| Condition | Visibility [km] | PWV [cm] | τ_band [—] | SNR [—] | NIIRS [—] | Status |
|---|---|---|---|---|---|---|
| Arctic dry | 50 | 0.5 | 0.5991 | 455.3 | 4.42 | GO |
| Crystal clear | 100 | 0.8 | 0.5863 | 450.3 | 4.42 | GO |
| Clear | 50 | 1.0 | 0.5753 | 446.0 | 4.41 | GO |
| Standard | 23 | 1.4 | 0.5542 | 437.7 | 4.40 | GO |
| Light haze | 10 | 2.0 | 0.5218 | 424.8 | 4.38 | GO |
| Moderate haze | 5 | 3.0 | 0.4733 | 404.7 | 4.34 | GO |
| Heavy haze | 2 | 4.0 | 0.4033 | 374.6 | 4.29 | GO |
| Tropical humid | 10 | 5.0 | 0.4352 | 387.4 | 4.31 | GO |

**Result**: All 8 conditions are GO — NIIRS ≥ 4.0 at every weather condition tested. However, **no condition meets the NIIRS ≥ 5.0 goal**. The best case (Arctic dry) only reaches 4.42. The NIIRS goal of 5.0 is unachievable with 7.5 m GSD regardless of weather. Weather-induced NIIRS variation = 0.13.

### 2D NIIRS Grid (Visibility × PWV)
All 36 grid cells meet NIIRS ≥ 4.0 (100% GO rate). The grid shows that PWV drives the variation (columns vary more than rows), confirming that water vapor absorption is the dominant atmospheric effect in MWIR.

### Noise Budget at Baseline (23 km, 1.4 cm)
| Noise Term | σ [e- RMS] | Fraction [%] |
|---|---|---|
| signal_shot | 438.2 | 99.8 |
| read_noise | 18.0 | 0.2 |
| quantization | 9.2 | 0.0 |
| dark_shot | 0.4 | 0.0 |
| nearfield_shot | 0.0 | 0.0 |

Signal shot noise dominates almost entirely (99.8%). Read noise and dark current are negligible at this signal level. There is **no separate background_shot term** — the extended MWIR scene is one radiance field, so its shot noise is `signal_shot` alone (ADR-0002 Decision #13). Removing the previously-equal background term is what raised SNR versus older baselines. **Note**: `nearfield_shot = 0` — scalar-mode refractive-lump assumption does not model mirror self-emission (see Gap 8). Total noise = 438.6 e⁻ RMS, SNR = 437.7, NIIRS = 4.40, RER = 0.5964, MTF@Nyquist = 0.2509.

## Physics Discussion

### Why MWIR Is Robust to Weather
1. **Aerosol scattering**: Aerosol extinction scales as λ^(-α) where α ≈ 1.3 for rural aerosol. At λ = 4.2 µm vs. 0.55 µm (visible), aerosol extinction is reduced by (4.2/0.55)^1.3 ≈ 13×. This makes visibility (which characterizes aerosol at 550 nm) a poor predictor of MWIR performance.

2. **Water vapor absorption**: H₂O has absorption bands at 2.7 µm and 6.3 µm that bracket the MWIR window (3.5–5.0 µm). The 4.3 µm CO₂ band further erodes the window. As PWV increases, band-mean transmittance drops modestly (0.59 → 0.44 across 0.5–5.0 cm) — the MWIR H₂O bands are already saturated, so added column water grows optical depth sub-linearly (curve of growth, CU-161). The SNR impact is muted twice over: by the shallow τ response, and because the system is signal-shot-limited (SNR ∝ √signal), so the ~1.3× transmittance change moves SNR only ~14% once path radiance partially refills the signal.

3. **GSD dominates NIIRS**: The GIQE-5 equation is NIIRS = 9.57 − 3.32·log₁₀(GSD_inch) + 1.559·log₁₀(SNR) + ... The GSD term (−3.32 coefficient) dominates over the SNR term (1.559 coefficient). At 7.5 m GSD = 295 inches, the GSD penalty is −3.32 × log₁₀(295) = −8.20. Even if SNR could be infinite, NIIRS is capped by GSD. This is why weather barely affects NIIRS — it can only modulate SNR, which has a small influence.

4. **Why the NIIRS goal is unachievable**: NIIRS ≥ 5.0 would require GSD ≤ ~2.5 m at this SNR level. To achieve that with 18 µm pixels at 500 km, the focal length would need to be ~3.6 m (f/12) — a much larger telescope.

### Why SNR Doesn't Track Transmittance Linearly
The system is signal-shot-limited, so SNR ∝ √signal, not signal. At 300 K target in MWIR:
- Signal ∝ τ × L_target — decreases with lower transmittance
- Signal_shot ∝ √signal — so SNR moves as the **square root** of the signal change
- Path radiance adds to the signal — partially compensates the transmittance loss

So the ~1.3× drop in τ (hence signal) across the full PWV range produces at most a
√1.3 ≈ 1.14× SNR change, and path-radiance refill keeps the realized change near ~14%.
Because NIIRS depends on log₁₀(SNR), that maps to only a ~0.13 NIIRS swing across the full
weather range. (Before the CU-161 water refit the parametric model produced a spurious 7× τ
drop and a correspondingly overstated ~0.15 swing — see the validation note below.)

### Integration Time Choice
1 ms is appropriate for a staring sensor in 500 km LEO:
- Ground velocity ≈ 7 km/s
- Smear during integration = 7000 m/s × 0.001 s = 7.0 m ≈ 0.93 pixels
- Sub-pixel smear preserves spatial resolution
- Well fill: 248K e- = 50% of 500K FWC (safe)

## Real-MODTRAN validation note (added 2026-07-17)

The real MODTRAN 6 D-block (2026-07-17 run set: D1 vis=5 km, D4/D5
H₂O ×0.5/×2.0, all us_standard rural, nadir full column; baseline A1)
pins this scenario's two sweep axes. MWIR 3.5–5.0 µm band means:

| Axis | Real MODTRAN | SimpleAtmosphere (post-CU-161) | Verdict |
|---|---|---|---|
| Visibility 23→5 km | τ 0.555→0.511 (−8.0%) | τ 0.554→0.526 (−5.1%) | **Validated** — absolute τ now within ~0.2% at 23 km; sensitivity same order (simple mildly under-responds) |
| PWV 0.7→2.8 cm | τ 0.586→0.506 (−0.038/cm) | τ 0.585→0.505 (−0.038/cm) | **Validated** — the CU-161 curve-of-growth refit collapsed the former ~5.5× over-response; the slope now matches MODTRAN |

Consequences for this walkthrough's conclusions (updated 2026-07-22 against the
current engine):

- **The visibility go/no-go threshold is trustworthy** — the
  aerosol/visibility response is the physics SimpleAtmosphere always
  got right, and the CU-155/161 recalibration also brought the
  absolute band-mean τ into line with MODTRAN (0.554 vs 0.555 at 23 km).
- **The PWV sensitivity is now correct, not overstated.** The
  earlier note recorded the linear-Beer model over-responding to
  column water by ~5.5× (τ 0.717→0.283 across 0.7→2.8 cm). The
  CU-161 curve-of-growth water refit (commit `0aebdda`) fixed this:
  the current parametric slope is −0.038/cm, matching the real MWIR
  band's saturated-H₂O response (−0.038/cm) essentially exactly. Raj's
  humidity-related margin conclusions from this refreshed run are
  sound; PWV and visibility are both weak weather drivers at this band.

Numbers were re-baselined 2026-07-22 (CU-176) against the current engine.
Note the D-block anchors are us_standard while this scenario runs
midlat_summer — the *axis sensitivities* transfer directly; the
close absolute agreement partly reflects the profile effect quantified
in scenario 6.2.

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

**Postscript (2026-07-22):** all sweep tables, the noise budget, and the real-MODTRAN validation note above were refreshed against the current engine (CU-176). The PWV over-response is resolved (CU-161 curve-of-growth water refit, commit `0aebdda`): the parametric PWV slope now matches MODTRAN (−0.038/cm). The visibility-axis validation stands, and the absolute band-mean τ also now agrees with MODTRAN after the CU-155/161 recalibration.
