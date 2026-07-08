# Scenario 7.2 Gaps: Radiometric Calibration Verification

Executed 2026-07-08 (Phase T3). Registry mirror: `docs/tracking/gaps.md`
(Gaps 6, 30, 37, 42, 46).

## Summary
Five-point blackbody calibration (280–360 K) against the as-built bench
sensor. The predicted-vs-measured fit recovers the planted truth-model
imperfections: gain scale +1.62% (truth: +1.8%, the difference absorbed by
the truth model's non-linearity), offset +43.6 DN (truth: 46 DN un-modeled
offset; RADIANT separately models 24.0 DN of Kirchhoff nearfield
self-emission). Linearity 0.107% FS max deviation; calibration σ_T
4.2–6.1 mK on 100-frame means.

## Gap Closure Status (catalog "Gaps revealed" list)

| # | Catalog gap | Status | Evidence |
|---|-------------|--------|----------|
| 1 | No DN output | **Already closed** (readout stage) | `stage_outputs["readout"]["signal_dn_final"]` — electrons ÷ gain, ADC-clipped; consumed directly by this scenario |
| 2 | No multi-temperature calibration sweep mode | **Already closed** (Sensor.sweep) | One `sensor.sweep("source.target.temperature", temps, keep_results=True)` call |
| 3 | No responsivity metric | Open — **registry Gap 46** | dDN/dT by finite difference on the sweep; dDN/dL against the Planck band radiance — both script-side one-liners |
| 4 | No non-linearity analysis | Open — **registry Gap 46** | Linear fit of DN vs L(T) + % FS residuals, script-side |
| 5 | No calibration uncertainty propagation | Open — **registry Gap 46** | σ_DN = σ_e/gain, σ_T = σ_e/(gain·dDN/dT), N-frame scaling — script-side |

## Supporting Capabilities Exercised

- **Gap 6** (unit-aware set): as-built workbook values entered in cm/%/ms.
- **Gap 30** (`load_measured_curve`): the measured-DN CSV with `x_unit="K"`.
- **Gap 37** (`scalar_emissivity`): instrument self-emission from Kirchhoff
  ε = 1 − τ through the 7.4-measured cold-stop leakage — 24.0 DN of modeled
  offset, printed and folded into the calibration interpretation.
- **Gap 42** (bench masquerade): exo + `platform.h_sensor = 1.0` m, same as
  the other 7.x scenarios.

## Non-Gap Observations

- **Percent residuals mislead at the cold end** (−6.7% at 280 K vs −2.0% at
  360 K): a fixed offset is a larger fraction of a small signal. The
  gain/offset fit is the correct decomposition; raw percent tables are not.
- **The chain is linear in radiance by construction** — fitting PREDICTED
  DN vs L(T) recovers the slope to <0.01%, so any measured curvature is the
  instrument's. A calibration scenario can therefore use RADIANT as the
  linear reference without circularity.
- **The extended-regime background skip (Decision #13) is correct here
  too**: the calibration source fills the aperture, so lab-ambient
  background photons never reach the signal path; the ambient parameters
  affect only the contrast scene. The offset physics lives in nearfield +
  dark, both modeled.
