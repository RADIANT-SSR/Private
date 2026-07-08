# Scenario 7.5 Walkthrough: Performance at Temperature Extremes

Executed 2026-07-08 (Scenario_Execution_Plan Phase T3, priority 22). First
execution.

## The Problem

Karen runs a thermal-vacuum sweep of the FPA operating temperature
(70–95 K), imaging the 300 K chamber shroud. She measured dark current at
each temperature — it deviates *super-Arrhenius* above ~85 K — and QE at
three temperatures. She needs SNR/NEDT vs temperature, the noise budget
with dark current growing, the measured-vs-Arrhenius story, the
QE(T)-vs-dark split, and an operating-temperature recommendation with
margin against the acceptance spec (SNR ≥ 750, NEDT ≤ 35 mK).

## How RADIANT Answers It

**Measured J(T) drives the chain directly.** The TVAC curve loads via
`load_measured_curve` (the lab already reduced to e⁻/s; the scenario-2.1
`dark_current_csv` importer is the right reader for *vendor* A/cm²
datasheets — noted in the script) and its value sets
`detector.dark_rate_e_per_s` at each sweep point — **no Arrhenius model is
assumed**, which is the whole point: the measured super-Arrhenius knee is
what the test exists to catch.

**Co-varying QE(T).** QE is interpolated from the three measured points and
set per temperature. To isolate its effect, every point is also run with QE
frozen at its 77 K value.

**Regime.** The 300 K shroud fills the aperture → extended regime
(background photon term skipped, Decision #13); the noise budget is
signal-shot + dark-shot + read + nearfield + quantization.

## Key Results

### Measured Dark Current vs Arrhenius Fit

| T [K] | Measured [e⁻/s] | Arrhenius fit [e⁻/s] | Excess |
|------:|----------------:|---------------------:|-------:|
| 70 | 1,343 | 1,343 | +0.0% |
| 77 | 50,000 | 50,000 | +0.0% |
| 82 | 453,732 | 453,723 | +0.0% |
| 85 | 1,654,727 | 1,504,512 | +10.0% |
| 88 | 8,735,214 | 4,597,318 | **+90.0%** |
| 90 | 28,034,927 | 9,288,454 | **+201.8%** |
| 95 | 395,723,319 | 47,345,161 | **+735.8%** |

The Arrhenius line (fit to the three lowest points, Ea = 0.240 eV)
reproduces the low-temperature data and then **catastrophically
under-predicts** above the ~88 K knee. A Rule-07 Arrhenius extrapolation
would call 95 K eight times better than it is — the reason a *measured*
J(T) input matters.

### Performance vs FPA Temperature (t_int = 0.55 ms)

| T [K] | QE | well % | signal_shot | dark_shot | SNR | NEDT [mK] |
|------:|----|-------:|------------:|----------:|----:|----------:|
| 70 | 0.78 | 46.4 | 834.5 | 0.9 | 828.6 | 32.08 |
| 85 | 0.73 | 43.4 | 807.3 | 30.2 | 801.0 | 33.19 |
| 88 | 0.72 | 42.7 | 800.6 | 69.3 | 792.0 | 33.57 |
| 90 | 0.71 | 42.3 | 796.2 | 124.2 | 781.1 | 34.03 |
| 92 | 0.71 | 42.3 | 796.2 | 216.7 | 763.1 | 34.84 |
| 95 | 0.71 | 42.3 | 796.2 | 466.5 | 683.2 | 38.91 |

Dark shot noise climbs from ~1 e⁻ (70 K) to 467 e⁻ (95 K) — from
negligible to the second-largest term — and drags SNR down and NEDT up.

### QE(T) vs Dark Current

Over 70–95 K, QE falls **9%** while dark current rises **294,612×**. NEDT
with QE(T) vs QE frozen at 77 K differs by only a few percent: **dark
current is the dominant temperature effect; QE(T) is a second-order
correction.** The scenario's "does QE(T) matter?" question has a clear
answer — not compared to dark.

### Spec Compliance and Recommendation

SNR ≥ 750 and NEDT ≤ 35 mK hold through **92 K** (NEDT 34.8 mK, 0.2 mK
margin); 95 K fails both. **Recommendation: operate at 89 K** — a 3 K guard
band below the compliance edge, protecting against cooler drift and the
super-Arrhenius knee at ~88 K where dark current climbs steeply.

## Physics Discussion

**Why the knee is dangerous.** Below ~85 K the diode is diffusion-limited
(clean Arrhenius, Ea ≈ Eg-related). Above it a second mechanism
(defect-assisted / trap-assisted tunneling) switches on and dominates,
turning the curve super-Arrhenius. Because it is a *different* physical
process, no single activation energy fits both regimes — extrapolating the
cold-side Ea is exactly the failure mode. The measured curve is the only
safe input above the knee.

**NEDT is dark-driven at the warm end, QE-insensitive.** NEDT ∝
σ_total / (dS/dT). QE scales both signal and its derivative, so a 9% QE
change barely moves NEDT; dark shot adds to σ_total without touching dS/dT,
so a 300,000× dark increase drives NEDT directly. This is why cooling budget
(dark), not QE(T), sets the operating point.

**The guard band is against two things.** Cooler drift (a few K of
set-point wander) and the knee's steepness: at 92 K the margin is 0.2 mK,
but the NEDT slope is ~2 mK/K and rising, so a 1 K warm excursion blows the
spec. 89 K sits on the flat part of the curve with real margin.

## Gaps Identified

See `gaps.md`. Highlights: measured J(T) input **closed** via
`load_measured_curve` / the 2.1 `dark_current_csv` importer; QE(T)
temperature dependence has no chain model (QE is T-independent) — worked
around by setting the interpolated scalar per point (registry **Gap 48**);
NEDT carries the Gap 43 single-λ caveat; the spec/margin checker and the
co-varying-parameter sweep are script-side (composition of `Sensor.set`,
no new gap).

## Outputs

- `outputs/environmental_test_results.xlsx` — sweep table with PASS/FAIL
- `outputs/fig1_snr_nedt_vs_temperature.png` — SNR/NEDT vs T with spec lines
- `outputs/fig2_dark_current_arrhenius.png` — measured vs Arrhenius (semilog)
- `outputs/fig3_noise_budget_vs_temperature.png` — variance stack, dark growing

## What Karen Would Do Next

1. **Set the flight operating point at 89 K** and document the 3 K guard
   band and the 88 K knee in the acceptance data package
2. **Investigate the knee mechanism** (bias dependence, pixel-to-pixel
   spread) — a defect-assisted onset often has an operability tail worse
   than the mean curve shows
3. **Re-run with the flight scene** (not the 300 K bench shroud) — the
   dark/photon ratio, hence the knee's operational impact, shifts with
   scene brightness
4. **Add a QE(λ,T) map** if a wide-band or spectral product needs the
   second-order QE(T) correction this scenario found negligible
