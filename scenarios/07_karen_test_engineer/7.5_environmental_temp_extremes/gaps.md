# Scenario 7.5 Gaps: Performance at Temperature Extremes

Executed 2026-07-08 (Phase T3). Registry mirror: `docs/tracking/gaps.md`
(Gaps 30, 42, 43; new Gap 48 for QE(T)).

## Summary
TVAC FPA-temperature sweep 70–95 K imaging a 300 K shroud. Measured J(T)
turns super-Arrhenius above ~88 K (+735.8% over the cold-side Arrhenius fit
at 95 K); dark shot climbs from 0.9 to 466.5 e⁻ RMS, dragging SNR 828.6→683.2
and NEDT 33.44→40.55 mK. QE falls 9% while dark rises 294,612× — dark
dominates. Spec (SNR ≥ 750, NEDT ≤ 35 mK) holds to 88 K (NEDT 34.98 mK);
recommended set point 85 K (3 K guard).

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-07-08); `walkthrough.md` was already current and did not move. No
Results-affecting landing accounts for the change — this is an exo/vacuum
bench scene, which every in-window landing's scope statement excludes (CU-224
leaves exo/vacuum exactly unchanged; CU-267 and CU-253 are `simple`-atmosphere
only). This summary had simply never been refreshed to the compliance edge the
walkthrough already reported.*

## Gap Closure Status (catalog "Gaps revealed" list)

| # | Catalog gap | Status | Evidence |
|---|-------------|--------|----------|
| 1 | No measured J(T) curve input | **CLOSED** | Measured e⁻/s curve via `load_measured_curve` sets `detector.dark_rate_e_per_s` per point (no Arrhenius assumed); vendor A/cm² datasheets use the scenario-2.1 `dark_current_csv` importer |
| 2 | No QE(T) model | Open — **registry Gap 48** | QE is temperature-independent in the schema; worked around by interpolating the QE(T) table and setting the scalar per sweep point |
| 3 | No NEDT output | **Already closed** | `result.metrics["nedt_K"]` (single-λ approximation — Gap 43 caveat) |
| 4 | No temperature-dependent sweep with co-varying parameters | Not filed — script composition | Each point sets J(T) AND QE(T) together; a native "co-varying sweep" would wrap `Sensor.set` loops, no new physics |
| 5 | No "meets spec" threshold checker with margin | Not filed — script analysis | SNR/NEDT vs thresholds + warmest-compliant + guard band, script-side |

## New Gap Found by This Execution

### Registry Gap 48 — QE has no temperature dependence in the chain
`detector.qe_value` (and the QE-curve path) are temperature-independent;
there is no QE(T) or QE(λ,T) model. A TVAC sweep must interpolate a
measured QE(T) table externally and set the scalar per operating point
(this scenario's pattern). Low impact — the scenario shows QE(T) is a
second-order effect vs dark current — but a first-class QE(T) (or a
`detector.qe_temperature_ref_K` + coefficient) would let the chain co-vary
QE with `detector.detector_temperature_K` automatically. Related to Gap 47
(spectral emissivity) and Gap 44 (QE-curve config path).

## Non-Gap Observations

- **The super-Arrhenius knee is the headline** and is only visible because
  the measured curve drives the chain: an Arrhenius extrapolation of the
  cold-side Ea under-predicts 95 K dark current 8×. This validates the
  "measured J(T) input" prerequisite end-to-end.
- **QE(T) is second-order vs dark** (9% vs 294,612×): the scenario answers
  its own "does QE(T) matter?" question — not compared to dark current. A
  scalar-per-point QE(T) is a fully adequate model here.
- **NEDT carries the Gap 43 single-λ caveat** (the reflected-solar
  component of that caveat is absent — exo bench, thermal target); the
  dark-driven NEDT *trend* is robust regardless.
- **The guard band is physics, not padding**: at the 88 K compliance edge the
  margin is ~0 mK (NEDT 34.98 mK against a 35 mK spec) and the NEDT slope
  steepens from ~0.25 mK/K there to ~1.4 mK/K past 92 K, so 85 K (flat part,
  NEDT 34.59 mK) is where real margin lives.
