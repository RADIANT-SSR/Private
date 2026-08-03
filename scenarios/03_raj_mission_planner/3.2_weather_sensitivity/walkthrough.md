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
| 2.0 | 0.4737 | 301,539 | 548.8 | 4.55 |
| 5.3 | 0.5256 | 305,985 | 552.8 | 4.56 |
| 23.1 | 0.5517 | 308,240 | 554.8 | 4.56 |
| 100.0 | 0.5579 | 308,779 | 555.3 | 4.56 |

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-07-22). Dominant mover: CU-224 — down-looking path radiance now carries
the `(1−τ)·B(λ,T_eff)` thermal-emission term, which for this extended MWIR
`simple`-atmosphere scene raises the collected signal ~60 % (192,000 → 308,240 e⁻
at baseline) and SNR ~27 %. The τ_band column moved only ~0.5 % downward
(CU-267's C¹ gas-region blend, −0.71 % on 3.0–5.0 µm); the signal and SNR jumps
are CU-224.*

**Key finding**: NIIRS barely changes with visibility (4.55 → 4.56 across entire range). MWIR aerosol scattering is negligible because the Angstrom exponent (α ≈ 1.3) causes extinction to scale as λ^(-1.3), making 4.2 µm aerosol extinction ~13× weaker than at 0.55 µm. Visibility affects visible-band sensors far more than MWIR.

### PWV Sweep (visibility = 23 km)
| PWV [cm] | τ_band [—] | Signal [e-] | SNR [—] | NIIRS [—] | ΔNIIRS [—] |
|---|---|---|---|---|---|
| 0.50 | 0.5930 | 312,015 | 558.2 | 4.56 | +0.00 |
| 1.46 | 0.5491 | 308,004 | 554.6 | 4.56 | -0.00 |
| 3.07 | 0.4930 | 302,972 | 550.1 | 4.55 | -0.01 |
| 5.00 | 0.4397 | 298,261 | 545.8 | 4.55 | -0.02 |

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-07-22). Dominant mover: CU-224 — the new `(1−τ)·B` path-emission term
grows as τ falls, so it now actively refills the signal the water vapour takes
away. That is why the PWV response collapsed from a 0.10 NIIRS swing to 0.02.*

**Key finding**: PWV still edges out visibility as the larger effect, but both are now very small. After the CU-161 curve-of-growth water refit (commit `0aebdda`), band-mean transmittance drops only from 0.59 to 0.44 (≈1.3× reduction) as PWV goes from dry desert to tropical humid — the saturated MWIR H₂O bands grow sub-linearly with absorber amount, not the ∝-PWV optical depth the old linear-Beer model produced (which read a spurious 7× drop). NIIRS falls just 0.02 across the full PWV range: NIIRS depends on log₁₀(SNR), and SNR moves only ~2.2% (558.2 → 545.8) because signal and its shot noise both drop (SNR ∝ √signal) *and* because CU-224's path-emission term rises as τ falls, refilling most of the lost signal.

### Named Weather Conditions — Go/No-Go
| Condition | Visibility [km] | PWV [cm] | τ_band [—] | SNR [—] | NIIRS [—] | Status |
|---|---|---|---|---|---|---|
| Arctic dry | 50 | 0.5 | 0.5977 | 558.6 | 4.56 | GO |
| Crystal clear | 100 | 0.8 | 0.5844 | 557.5 | 4.56 | GO |
| Clear | 50 | 1.0 | 0.5732 | 556.6 | 4.56 | GO |
| Standard | 23 | 1.4 | 0.5517 | 554.8 | 4.56 | GO |
| Light haze | 10 | 2.0 | 0.5188 | 552.2 | 4.55 | GO |
| Moderate haze | 5 | 3.0 | 0.4700 | 548.3 | 4.55 | GO |
| Heavy haze | 2 | 4.0 | 0.4000 | 542.8 | 4.54 | GO |
| Tropical humid | 10 | 5.0 | 0.4314 | 545.1 | 4.55 | GO |

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-07-22). Dominant mover: CU-224 (path emission, MWIR down-looking `simple`);
τ_band shifted ≤ 0.8 % from CU-267.*

**Result**: All 8 conditions are GO — NIIRS ≥ 4.0 at every weather condition tested. However, **no condition meets the NIIRS ≥ 5.0 goal**. The best case (Arctic dry) only reaches 4.56. The NIIRS goal of 5.0 is unachievable with 7.5 m GSD regardless of weather. Weather-induced NIIRS variation = 0.02 — with CU-224's path-emission refill, weather is now an almost undetectable driver in this band.

### 2D NIIRS Grid (Visibility × PWV)
All 36 grid cells meet NIIRS ≥ 4.0 (100% GO rate). The whole grid spans just 4.54–4.56 NIIRS (0.02 total). At that amplitude the two axes are no longer separable — each contributes about 0.01 across its full range — so the earlier "PWV clearly dominates" reading no longer holds. Water vapour is still the larger τ lever in MWIR (see the PWV sweep), but after CU-224's path-emission refill neither axis produces a NIIRS-visible effect.

### Noise Budget at Baseline (23 km, 1.4 cm)
| Noise Term | σ [e- RMS] | Fraction [%] |
|---|---|---|
| signal_shot | 555.2 | 99.9 |
| read_noise | 18.0 | 0.1 |
| quantization | 9.2 | 0.0 |
| dark_shot | 0.4 | 0.0 |
| nearfield_shot | 0.0 | 0.0 |

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-07-22). Dominant mover: CU-224 — the added path-emission signal raises
`signal_shot` ∝ √signal (438.2 → 555.2 e⁻ RMS), pushing the fixed read and
quantization terms further down in the budget.*

Signal shot noise dominates almost entirely (99.9%). Read noise and dark current are negligible at this signal level — even more so than before, since CU-224's extra path-emission signal raised the shot floor without touching them. There is **no separate background_shot term** — the extended MWIR scene is one radiance field, so its shot noise is `signal_shot` alone (ADR-0002 Decision #13). Removing the previously-equal background term is what raised SNR versus older baselines. **Note**: `nearfield_shot = 0` — scalar-mode refractive-lump assumption does not model mirror self-emission (see Gap 8). Baseline signal = 308,238 e⁻, total noise = 555.6 e⁻ RMS, SNR = 554.8, NIIRS = 4.56, RER = 0.5964, MTF@Nyquist = 0.2509 (RER and MTF unchanged — CU-224 is purely radiometric).

## Physics Discussion

### Why MWIR Is Robust to Weather
1. **Aerosol scattering**: Aerosol extinction scales as λ^(-α) where α ≈ 1.3 for rural aerosol. At λ = 4.2 µm vs. 0.55 µm (visible), aerosol extinction is reduced by (4.2/0.55)^1.3 ≈ 13×. This makes visibility (which characterizes aerosol at 550 nm) a poor predictor of MWIR performance.

2. **Water vapor absorption**: H₂O has absorption bands at 2.7 µm and 6.3 µm that bracket the MWIR window (3.5–5.0 µm). The 4.3 µm CO₂ band further erodes the window. As PWV increases, band-mean transmittance drops modestly (0.593 → 0.440 across 0.5–5.0 cm) — the MWIR H₂O bands are already saturated, so added column water grows optical depth sub-linearly (curve of growth, CU-161). The SNR impact is muted three times over: by the shallow τ response; because the system is signal-shot-limited (SNR ∝ √signal); and because CU-224's `(1−τ)·B` path-emission term *grows* exactly as τ shrinks, so the warm atmosphere returns most of the radiance the water vapour absorbed. Net: the ~1.3× transmittance change moves SNR only ~2.2%.

3. **GSD dominates NIIRS**: The GIQE-5 equation is NIIRS = 9.57 − 3.32·log₁₀(GSD_inch) + 1.559·log₁₀(SNR) + ... The GSD term (−3.32 coefficient) dominates over the SNR term (1.559 coefficient). At 7.5 m GSD = 295 inches, the GSD penalty is −3.32 × log₁₀(295) = −8.20. Even if SNR could be infinite, NIIRS is capped by GSD. This is why weather barely affects NIIRS — it can only modulate SNR, which has a small influence.

4. **Why the NIIRS goal is unachievable**: closing the 0.44 NIIRS gap from 4.56 to 5.0 through the −3.32·log₁₀(GSD) term alone needs GSD ≤ ~5.5 m at this SNR level. To achieve that with 18 µm pixels at 500 km, the focal length would need to be ~1.6 m (f/5.4) — a 35% longer telescope than the baselined 1.2 m. (The pre-refresh text quoted ~2.5 m / f/12; that figure did not follow from the GIQE-5 GSD term even at the old NIIRS of 4.40, and CU-224's higher SNR shrinks the required aperture growth further.)

### Why SNR Doesn't Track Transmittance Linearly
The system is signal-shot-limited, so SNR ∝ √signal, not signal. At 300 K target in MWIR:
- Signal ∝ τ × L_target — decreases with lower transmittance
- Signal_shot ∝ √signal — so SNR moves as the **square root** of the signal change
- Path radiance adds to the signal — partially compensates the transmittance loss

So the ~1.3× drop in τ across the full PWV range would at most produce a
√1.3 ≈ 1.14× SNR change even with no compensation. In practice CU-224's path-emission
refill leaves the signal itself only 4.4% lower (312,015 → 298,261 e⁻), so the realized
SNR change is ~2.2%. Because NIIRS depends on log₁₀(SNR), that maps to only a 0.02 NIIRS
swing across the full weather range. (Before the CU-161 water refit the parametric model
produced a spurious 7× τ drop and a correspondingly overstated ~0.15 swing — see the
validation note below.)

### Integration Time Choice
1 ms is appropriate for a staring sensor in 500 km LEO:
- Ground velocity ≈ 7 km/s
- Smear during integration = 7000 m/s × 0.001 s = 7.0 m ≈ 0.93 pixels
- Sub-pixel smear preserves spatial resolution
- Well fill: 308K e- = 62% of 500K FWC (safe, but 12 points fuller than the
  pre-CU-224 baseline of 248K e- / 50% — worth re-checking if the scene or
  target temperature is raised)

## Real-MODTRAN validation note (added 2026-07-17)

The real MODTRAN 6 D-block (2026-07-17 run set: D1 vis=5 km, D4/D5
H₂O ×0.5/×2.0, all us_standard rural, nadir full column; baseline A1)
pins this scenario's two sweep axes. MWIR 3.5–5.0 µm band means:

| Axis | Real MODTRAN | SimpleAtmosphere (post-CU-161) | Verdict |
|---|---|---|---|
| Visibility 23→5 km | τ 0.555→0.511 (−8.0%) | τ 0.552→0.526 (−4.7%) | **Validated** — absolute τ within ~0.5% at 23 km; sensitivity same order (simple mildly under-responds) |
| PWV 0.7→2.8 cm | τ 0.586→0.506 (−0.038/cm) | τ 0.583→0.502 (−0.039/cm) | **Validated** — the CU-161 curve-of-growth refit collapsed the former ~5.5× over-response; the slope still matches MODTRAN |

*τ figures refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-07-22). Mover: CU-267's C¹ gas-region smoothstep blend, which lowers τ by
≤ 0.71 % on 3.0–5.0 µm. Both verdicts are unchanged. CU-224 does not appear
here — it adds path radiance, not transmittance.*

Consequences for this walkthrough's conclusions (updated 2026-07-22 against the
current engine):

- **The visibility go/no-go threshold is trustworthy** — the
  aerosol/visibility response is the physics SimpleAtmosphere always
  got right, and the CU-155/161 recalibration also brought the
  absolute band-mean τ into line with MODTRAN (0.552 vs 0.555 at 23 km).
- **The PWV sensitivity is now correct, not overstated.** The
  earlier note recorded the linear-Beer model over-responding to
  column water by ~5.5× (τ 0.717→0.283 across 0.7→2.8 cm). The
  CU-161 curve-of-growth water refit (commit `0aebdda`) fixed this:
  the current parametric slope is −0.039/cm, matching the real MWIR
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
