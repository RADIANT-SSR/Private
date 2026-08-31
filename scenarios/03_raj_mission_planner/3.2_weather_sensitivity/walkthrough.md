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
| 2.0 | 0.4736 | 240,667 | 490.2 | 4.47 |
| 5.3 | 0.5256 | 248,242 | 497.8 | 4.48 |
| 23.1 | 0.5516 | 251,988 | 501.6 | 4.49 |
| 100.0 | 0.5578 | 252,874 | 502.5 | 4.49 |

*Numbers refreshed 2026-08-30. One mover across all four tables in this
document: **CU-335** re-fitted the calibrated gas table's VIS/NIR/SWIR rows
against the post-CU-253 Rayleigh. This is a 3–5 µm scene, so its reach is the
λ⁻⁴ tail in the 2.40–5.00 µm floors (+0.0010 / +0.0005 / +0.0001 OD): band-mean
τ falls in the fourth decimal (0.5517 → 0.5516 at the standard condition),
signal by 14 e⁻ in 252,000, SNR and NIIRS unmoved at the quoted precision. Every
GO/NO-GO verdict, every ΔNIIRS and the whole 36-cell grid are unchanged. Recorded
because the table moved, not because the scenario did.*

*Composed with CU-335 on the merged tree, 2026-08-31: CU-335 and CU-324 item 2 were
each measured against a tree that did not contain the other, and on `main` with both
present the fourth decimal moves once more — PWV-sweep τ 0.5929 → 0.5930 at 0.50 cm
and 0.4929 → 0.4930 at 3.07 cm, and the baseline noise-budget signal 251,999 →
251,985 e⁻ (≈ 6 × 10⁻⁵ relative). The visibility sweep, the named-condition table,
the 36-cell grid and every GO verdict are unchanged.*

*Prior vintage, 2026-08-29 (pre-CU-324). Numbers from the unmodified runner (previous vintage
2026-08-02, pre-CU-324). One mover: **CU-324** — `E_sky_thermal`'s
flux-diffusivity exponent is now the geometric `sec 48.2° = 1.50030` (the secant
of the angle the up-looking MODTRAN downwelling decks were run at) rather than
the CU-155 fitted `D = 1.1`, so the sky this ε < 1 ground scene reflects is
brighter: signal 251,214 → 252,002 e⁻ at baseline (+0.31 %) and SNR
500.8 → 501.6 (+0.16 %, the √signal scaling). The τ_band column is
bit-identical — the swap changes the downwelling emissivity and no optical
depth, which is the check that this move is the sky term and nothing else.
NIIRS moves in the third decimal and rounds unchanged at every visibility.*

*Prior vintage, for the trend: the 2026-08-02 refresh was dominated by CU-321
(height-resolved path-emission temperature), signal 308,240 → 251,214 e⁻ and
SNR 554.8 → 500.8.*

**Key finding**: NIIRS barely changes with visibility (4.47 → 4.49 across entire range). MWIR aerosol scattering is negligible because the Angstrom exponent (α ≈ 1.3) causes extinction to scale as λ^(-1.3), making 4.2 µm aerosol extinction ~13× weaker than at 0.55 µm. Visibility affects visible-band sensors far more than MWIR.

### PWV Sweep (visibility = 23 km)
| PWV [cm] | τ_band [—] | Signal [e-] | SNR [—] | NIIRS [—] | ΔNIIRS [—] |
|---|---|---|---|---|---|
| 0.50 | 0.5930 | 259,167 | 508.7 | 4.50 | +0.00 |
| 1.46 | 0.5490 | 251,533 | 501.1 | 4.49 | -0.01 |
| 3.07 | 0.4930 | 241,647 | 491.2 | 4.48 | -0.02 |
| 5.00 | 0.4396 | 232,030 | 481.3 | 4.46 | -0.04 |

*Numbers refreshed 2026-08-29 from the unmodified runner (previous vintage
2026-08-02, pre-CU-324). One mover: **CU-324**'s geometric downwelling exponent
lifts every row by +0.15 to +0.31 % in signal. It does not change the *shape* of
the PWV response — the NIIRS swing across 0.5 → 5.0 cm is still 0.04 (against
0.02 before CU-321 and 0.10 before CU-224) — because the sky term rises across
the whole sweep rather than differentially with column water.*

**Key finding**: PWV still edges out visibility as the larger effect, but both are still small. After the CU-161 curve-of-growth water refit (commit `0aebdda`), band-mean transmittance drops only from 0.59 to 0.44 (≈1.3× reduction) as PWV goes from dry desert to tropical humid — the saturated MWIR H₂O bands grow sub-linearly with absorber amount, not the ∝-PWV optical depth the old linear-Beer model produced (which read a spurious 7× drop). NIIRS falls 0.04 across the full PWV range: NIIRS depends on log₁₀(SNR), and SNR moves only ~5.4% (507.9 → 480.6) because signal and its shot noise both drop (SNR ∝ √signal) *and* because the path-emission term rises as τ falls, refilling part of the lost signal — less of it since CU-321 put that emission at a colder height-resolved temperature.

### Named Weather Conditions — Go/No-Go
| Condition | Visibility [km] | PWV [cm] | τ_band [—] | SNR [—] | NIIRS [—] | Status |
|---|---|---|---|---|---|---|
| Arctic dry | 50 | 0.5 | 0.5976 | 509.3 | 4.50 | GO |
| Crystal clear | 100 | 0.8 | 0.5844 | 507.0 | 4.50 | GO |
| Clear | 50 | 1.0 | 0.5731 | 505.2 | 4.49 | GO |
| Standard | 23 | 1.4 | 0.5516 | 501.6 | 4.49 | GO |
| Light haze | 10 | 2.0 | 0.5188 | 496.1 | 4.48 | GO |
| Moderate haze | 5 | 3.0 | 0.4700 | 487.8 | 4.47 | GO |
| Heavy haze | 2 | 4.0 | 0.4000 | 476.0 | 4.45 | GO |
| Tropical humid | 10 | 5.0 | 0.4314 | 480.0 | 4.46 | GO |

*Numbers refreshed 2026-08-29 from the unmodified runner (previous vintage
2026-08-02, pre-CU-324). One mover: **CU-324** (geometric `sec 48.2°`
downwelling exponent, +0.7 to +0.9 SNR counts per row); τ_band is
bit-identical, and every GO/NO-GO verdict is unchanged.*

**Result**: All 8 conditions are GO — NIIRS ≥ 4.0 at every weather condition tested. However, **no condition meets the NIIRS ≥ 5.0 goal**. The best case (Arctic dry) only reaches 4.50. The NIIRS goal of 5.0 is unachievable with 7.5 m GSD regardless of weather. Weather-induced NIIRS variation = 0.05 — with the path-emission term partly refilling what the atmosphere absorbs, weather remains a very weak driver in this band.

### 2D NIIRS Grid (Visibility × PWV)
All 36 grid cells meet NIIRS ≥ 4.0 (100% GO rate). The whole grid spans just 4.45–4.50 NIIRS (0.05 total). At that amplitude the two axes are still barely separable — PWV contributes about 0.04 across its full range and visibility about 0.02 — so the earlier "PWV clearly dominates" reading remains retired, though PWV is now visibly the larger of the two again. Water vapour is the larger τ lever in MWIR (see the PWV sweep); the path-emission term refills part of what it absorbs, so neither axis produces a decision-relevant NIIRS effect.

### Noise Budget at Baseline (23 km, 1.4 cm)
| Noise Term | σ [e- RMS] | Fraction [%] |
|---|---|---|
| signal_shot | 502.0 | 99.8 |
| read_noise | 18.0 | 0.1 |
| quantization | 9.2 | 0.0 |
| dark_shot | 0.4 | 0.0 |
| nearfield_shot | 0.0 | 0.0 |

*Numbers refreshed 2026-08-29 from the unmodified runner (previous vintage
2026-08-02, pre-CU-324). One mover: **CU-324** — the brighter reflected sky
raises the signal and with it `signal_shot` ∝ √signal (501.2 → 502.0 e⁻ RMS);
the fixed read and quantization terms are untouched and so fall very slightly
as a fraction, which the 99.8 % rounding does not resolve.*

Signal shot noise dominates almost entirely (99.8%). Read noise and dark current are negligible at this signal level. There is **no separate background_shot term** — the extended MWIR scene is one radiance field, so its shot noise is `signal_shot` alone (ADR-0002 Decision #13). Removing the previously-equal background term is what raised SNR versus older baselines. **Note**: `nearfield_shot = 0` — scalar-mode refractive-lump assumption does not model mirror self-emission (see Gap 8). Baseline signal = 251,985 e⁻, total noise = 502.4 e⁻ RMS, SNR = 501.6, NIIRS = 4.49, RER = 0.5964, MTF@Nyquist = 0.2509 (RER and MTF unchanged — CU-324, like CU-321 and CU-224 before it, is purely radiometric).

## Physics Discussion

### Why MWIR Is Robust to Weather
1. **Aerosol scattering**: Aerosol extinction scales as λ^(-α) where α ≈ 1.3 for rural aerosol. At λ = 4.2 µm vs. 0.55 µm (visible), aerosol extinction is reduced by (4.2/0.55)^1.3 ≈ 13×. This makes visibility (which characterizes aerosol at 550 nm) a poor predictor of MWIR performance.

2. **Water vapor absorption**: H₂O has absorption bands at 2.7 µm and 6.3 µm that bracket the MWIR window (3.5–5.0 µm). The 4.3 µm CO₂ band further erodes the window. As PWV increases, band-mean transmittance drops modestly (0.593 → 0.440 across 0.5–5.0 cm) — the MWIR H₂O bands are already saturated, so added column water grows optical depth sub-linearly (curve of growth, CU-161). The SNR impact is muted three times over: by the shallow τ response; because the system is signal-shot-limited (SNR ∝ √signal); and because the `(1−τ)·B` path-emission term *grows* exactly as τ shrinks, so the atmosphere returns part of the radiance the water vapour absorbed — part, not most, since CU-321 put that emission at the column's true (colder) emission altitude. Net: the ~1.3× transmittance change moves SNR only ~5.4%.

3. **GSD dominates NIIRS**: The GIQE-5 equation is NIIRS = 9.57 − 3.32·log₁₀(GSD_inch) + 1.559·log₁₀(SNR) + ... The GSD term (−3.32 coefficient) dominates over the SNR term (1.559 coefficient). At 7.5 m GSD = 295 inches, the GSD penalty is −3.32 × log₁₀(295) = −8.20. Even if SNR could be infinite, NIIRS is capped by GSD. This is why weather barely affects NIIRS — it can only modulate SNR, which has a small influence.

4. **Why the NIIRS goal is unachievable**: closing the 0.51 NIIRS gap from 4.49 to 5.0 through the −3.32·log₁₀(GSD) term alone needs GSD ≤ ~5.4 m at this SNR level. To achieve that with 18 µm pixels at 500 km, the focal length would need to be ~1.7 m (f/5.6) — a 40% longer telescope than the baselined 1.2 m. (The pre-refresh text quoted ~2.5 m / f/12; that figure did not follow from the GIQE-5 GSD term even at the older NIIRS of 4.40.)

### Why SNR Doesn't Track Transmittance Linearly
The system is signal-shot-limited, so SNR ∝ √signal, not signal. At 300 K target in MWIR:
- Signal ∝ τ × L_target — decreases with lower transmittance
- Signal_shot ∝ √signal — so SNR moves as the **square root** of the signal change
- Path radiance adds to the signal — partially compensates the transmittance loss

So the ~1.3× drop in τ across the full PWV range would at most produce a
√1.3 ≈ 1.14× SNR change even with no compensation. In practice the path-emission
refill leaves the signal itself 10.4% lower (258,362 → 231,395 e⁻), so the realized
SNR change is ~5.4%. Because NIIRS depends on log₁₀(SNR), that maps to only a 0.04 NIIRS
swing across the full weather range. (Before the CU-161 water refit the parametric model
produced a spurious 7× τ drop and a correspondingly overstated ~0.15 swing — see the
validation note below.)

### Integration Time Choice
1 ms is appropriate for a staring sensor in 500 km LEO:
- Ground velocity ≈ 7 km/s
- Smear during integration = 7000 m/s × 0.001 s = 7.0 m ≈ 0.93 pixels
- Sub-pixel smear preserves spatial resolution
- Well fill: 251K e- = 50% of 500K FWC (safe; CU-321's colder emission
  temperature brings this back to the pre-CU-224 level of 248K e- / 50%, from
  the 62% CU-224 had pushed it to)

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
