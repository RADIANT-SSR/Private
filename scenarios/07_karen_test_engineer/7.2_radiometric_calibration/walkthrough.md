# Scenario 7.2 Walkthrough: Radiometric Calibration Verification

Executed 2026-07-08 (Scenario_Execution_Plan Phase T3, priority 18). First
execution.

## The Problem

Karen ran a radiometric calibration: a NIST-traceable blackbody at five set
points (280–360 K), 100-frame mean DN recorded at each. She needs RADIANT's
as-built prediction next to the measurement — in DN, the unit her data
system actually records — plus responsivity, a linearity check, and
per-point calibration uncertainty. The model must include the lab ambient
background and the instrument's own self-emission, because those are what a
calibration's offset term physically is.

## Bench Configuration (as-built)

| Parameter | Value | Unit | Notes |
|-----------|-------|------|-------|
| Aperture / focal length | 15 / 30 | cm | f/2.0 |
| Optical transmission | 72 | % | Witness sample |
| Optics emissivity | 28 | % | 1 − τ (Kirchhoff, reflective train) |
| Nearfield fraction | 0.05 | — | Cold-stop leakage from the 7.4 campaign |
| Optics temperature | 20 | °C | Bench ambient |
| Pixel pitch / QE | 15 µm / 75% | | |
| Dark current | 50,000 | e⁻/s | At 77 K |
| Band | 3.7–4.9 | µm | |
| Integration time | 0.25 | ms | Calibration mode |
| Gain / ADC / well | 125 e⁻/DN / 14 bit / 2 Me⁻ | | Spec values |
| Read noise | 30 | e⁻ RMS | CDS |
| Blackbody emissivity | 0.998 | — | Cavity source |

Set points: 280, 300, 320, 340, 360 K → 5–60% of well. Vendor-unit entry
uses the unit-aware `Sensor.set(..., unit="cm"/"%")` boundary (Gap 6); the
measured-DN CSV loads through `load_measured_curve` (Gap 30).

## How RADIANT Answers It

**DN is a first-class chain output.** The readout stage reports
`signal_dn_final` (electrons ÷ gain, ADC-clipped) — the catalog's "no DN
output" gap was already closed by the readout implementation; the scenario
just consumes it.

**The temperature sweep is `Sensor.sweep`.** One call over the five set
points with `keep_results=True`; predicted DN, signal, nearfield, and the
full noise budget come from the per-point `ChainResult`s.

**Self-emission is modeled physics.** Warm optics at 293 K with the
Kirchhoff-derived ε = 1 − τ = 0.28 (Gap 37 `scalar_emissivity`), leaking
past the cold stop at the 7.4-measured 5% (`nearfield_fraction`),
contribute a constant 3,006 e⁻ = 24.0 DN at every set point. The bench as
vacuum uses the standard exo + `geometry.sensor_altitude_m` placeholder (Gap 42).

**Regime note (unused parameters).** The blackbody fills the aperture →
extended regime, so RADIANT skips the separate scene-background photon term
(matrix Decision #13): the lab-ambient background parameters feed only the
contrast scene. The instrument terms that DO vary the offset — nearfield
and dark — are both modeled.

## Key Results

### Predicted vs Measured DN

| T_BB [K] | Signal [e⁻] | DN pred | DN meas | Δ [DN] | Δ [%] |
|---------:|------------:|--------:|--------:|-------:|------:|
| 280 | 92,759 | 742.1 | 795.5 | −53.4 | −6.72 |
| 300 | 198,940 | 1,591.5 | 1,661.0 | −69.5 | −4.18 |
| 320 | 389,483 | 3,115.9 | 3,214.7 | −98.8 | −3.07 |
| 340 | 706,500 | 5,652.0 | 5,784.8 | −132.8 | −2.30 |
| 360 | 1,201,886 | 9,615.1 | 9,815.0 | −199.9 | −2.04 |

### The Calibration Fit — the two knobs

Fitting `measured = a·predicted + b`:

| Coefficient | Value | Meaning |
|-------------|-------|---------|
| a (gain scale) | **1.0162** | Real responsivity is +1.62% vs the as-built gain spec |
| b (offset) | **+43.6 DN** | Un-modeled instrument offset (on top of RADIANT's modeled 24.0 DN nearfield) |

This is the entire point of a calibration: the raw residuals (−2 to −6.7%)
look alarming, but they decompose into exactly two physical knobs — a gain
scale and an offset. Percent residuals are largest at the COLD end not
because the model is worse there but because a fixed offset is a larger
fraction of a small signal.

### Responsivity

dDN/dT rises from 42.47 DN/K (280 K) to 198.15 DN/K (360 K) — the Planck
derivative steepens with temperature. Radiance responsivity (slope of DN
vs band radiance): **1,059 DN/(W/m²/sr)** predicted.

*Responsivity figures refreshed 2026-08-02 from the unmodified runner
(previous vintage 2026-07-12); the predicted-DN table above was already
current and did not move. No Results-affecting landing accounts for the
change — this is an exo/vacuum bench scene, which every in-window landing's
scope statement excludes (CU-224 leaves exo/vacuum exactly unchanged; CU-267
and CU-253 are `simple`-atmosphere only). The stale pair were local Planck
derivatives; the runner reports the secant dDN/dT across the 20 K set-point
spacing, consistent with the DN table it sits under.*

### Linearity

Measured DN vs Planck band radiance L(T), linear fit: max deviation
**0.107% of full scale** — within the usual 1% budget. RADIANT's own chain
is linear in radiance by construction (predicted-DN fit recovers its slope
to <0.01%), so the curvature seen is the instrument's, isolated by the
comparison.

### Calibration Uncertainty

| T_BB [K] | σ [e⁻] | σ_DN (1 frame) | σ_DN (100-frame) | σ_T (100-frame) |
|---------:|-------:|---------------:|-----------------:|----------------:|
| 280 | 313.0 | 2.50 | 0.250 | 5.9 mK |
| 360 | 1,098.7 | 8.79 | 0.879 | 4.4 mK |

Radiometric noise is not the accuracy limit: 100-frame averaging reaches a
few mK, far below the blackbody standard's uncertainty. The calibration
error budget is dominated by gain/offset knowledge — which is what the fit
above delivers.

## Physics Discussion

**Why the offset matters more than it looks.** The instrument offset
(self-emission + dark + any un-modeled electronics pedestal) enters every
scene measurement identically. RADIANT models 24.0 DN of it from first
principles (Kirchhoff warm-optics emission through the measured cold-stop
leakage); the residual +43.6 DN is what the calibration must carry as an
empirical term. Chasing that residual down is exactly the 7.4 cold-stop /
7.1 nearfield investigation loop.

**Gain in DN vs gain in e⁻/DN.** The fitted +1.62% is a *responsivity*
scale error — it could live in the ADC gain, the QE, the transmission, or
the solid angle. A single-band calibration cannot split those; it can only
scale the product. That is why the fit is reported as a scale on predicted
DN, not as a corrected e⁻/DN.

**Sub-mK noise floors are real but irrelevant.** σ_T of 4–6 mK on the
100-frame means says shot noise is negligible for calibration purposes;
the few-hundred-mK-class accuracy of field radiometry comes from the
standard, stray light, and drift — none of which averaging fixes.

## Gaps Identified

See `gaps.md`. Highlights: "no DN output" and "no multi-temperature sweep"
were already closed (readout `signal_dn_final`; `Sensor.sweep`);
responsivity / linearity / calibration-uncertainty analysis is script-side
(new registry Gap 46 — low severity, the recipes are one-liners on sweep
results).

## Outputs

- `outputs/calibration_results.xlsx` — calibration table + fit coefficients
- `outputs/fig1_dn_predicted_vs_measured.png` — DN curves + percent residuals
- `outputs/fig2_linearity_dn_vs_radiance.png` — DN vs L(T) with linear fit
- `outputs/fig3_responsivity_uncertainty.png` — dDN/dT and σ_T vs set point

## What Karen Would Do Next

1. **Apply the calibration**: scale the model gain by +1.62% and carry the
   +43.6 DN offset; re-verify residuals drop to the noise floor
2. **Chase the offset**: 43.6 DN ≈ 5,450 e⁻ — compare against a shuttered
   dark measurement to split electronics pedestal from stray thermal paths
   (the 7.4 workflow)
3. **Add set points near the operating scene temperature** if the 0.1% FS
   non-linearity matters for her application
4. **Propagate the calibrated gain/offset into the mission model** so
   flight predictions use as-calibrated, not as-designed, responsivity
