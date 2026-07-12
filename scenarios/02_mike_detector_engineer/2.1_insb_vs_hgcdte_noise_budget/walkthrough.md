# Scenario 2.1 Walkthrough: InSb vs. HgCdTe Noise Budget Shootout at 77 K

Executed 2026-07-08 (Scenario_Execution_Plan Phase T3, priority 15). First
execution; prerequisite importers landed in commit 1de9cf4
(`radiant.io.qe_csv`, `radiant.io.dark_current_csv`).

## The Problem

Mike is choosing between an InSb FPA and an HgCdTe FPA for a space-mission
MWIR sensor. The two vendors sent him:

- **QE curves in two different CSV conventions** — InSb as
  `wavelength_nm, QE_pct`, HgCdTe as `lambda_um, quantum_efficiency`
- **Measured dark current vs. temperature** (`T_K, Jdark_A_cm2`) for both
- **ROIC acceptance data**: read noise 18 e⁻ (InSb) vs 12 e⁻ (HgCdTe) on the
  same 15 µm, 33 fF, CDS-mode ROIC with 5 e⁻/s glow

He wants a like-for-like noise budget on a common bench (flat 300 K
blackbody filling the aperture, 3.5–5.0 µm cold filter, no atmosphere, no
scene), and the three numbers that actually decide the cooler budget:
dark-current crossover temperature, BLIP temperature, and NEI.

## Bench Configuration

| Parameter | Value | Unit | Notes |
|-----------|-------|------|-------|
| Blackbody temperature | 300 | K | Flat plate filling the aperture |
| Blackbody emissivity | 0.995 | — | Cavity source |
| Collimator aperture | 2.5 | cm | f/2.3 |
| Collimator focal length | 5.75 | cm | |
| Optical transmission | 90 | % | Collimator + window |
| Cold filter passband | 3.5–5.0 | µm | Common band for the trade |
| Pixel pitch | 15 | µm | Same ROIC, both FPAs |
| Node capacitance | 33 | fF | |
| CDS | ON | — | kTC suppressed |
| ROIC glow | 5 | e⁻/s | |
| Full well / ADC / gain | 5 Me⁻ / 14 bit / 305 e⁻/DN | | |
| Integration time | 1.0 | ms | |
| Operating temperature | 77 | K | Nominal; trade explores warmer |

## How the Vendor Data Gets In

**QE (Gap closed — `radiant.io.qe_csv`).** `load_qe_csv` reads both vendor
conventions with the same call: units resolve from the header tokens
(`wavelength_nm` / `QE_pct` → nm and percent; `lambda_um` /
`quantum_efficiency` → µm and fraction), and everything lands in canonical
µm/fraction. QE > 1 after conversion is a hard error pointing at
`qe_unit="percent"` — no silent unphysical curves.

**Dark current (Gap closed — `radiant.io.dark_current_csv`).**
`load_dark_current_csv` reads the `T_K, Jdark_A_cm2` files; the A/cm² →
e⁻/s conversion happens once, in the loader (Rule 2):
`rate = J·(pitch·100)²/q`. Interpolation is Arrhenius-faithful — ln(J)
linear in 1/T, exact between nodes for `J ∝ exp(−Ea/kT)` — and the loader
refuses to extrapolate outside the measured range (the first run of this
scenario tripped that guard: the BLIP temperatures lie above 110 K, so the
vendor tables were extended to 130 K rather than extrapolated).

**Spectral QE into the chain.** There is no config path for a QE curve
(`detector.qe_table_path` exists in the schema but nothing reads it —
registry Gap 44). The curve is evaluated onto the chain wavelength grid by
`QeCurve.evaluate` and injected via
`RadiantSession.run(extra_stage_outputs={"spectral_integration":
{"qe_curve": ...}})` — the Rule 6 route. A second run per detector uses the
band-averaged scalar `detector.qe_value` for comparison.

**Bench as vacuum.** The 300 K plate fills the aperture → extended regime;
`atmosphere.model = "exo"` with the `geometry.sensor_altitude_m = 1.0` m bench
placeholder (registry Gap 42, same as the 7.x lab scenarios).

## Key Results

### Side-by-Side Noise Budget at 77 K (spectral QE, t_int = 1 ms)

| Noise Term | InSb [e⁻ RMS] | HgCdTe [e⁻ RMS] | Comment |
|------------|--------------:|----------------:|---------|
| signal_shot | 1033.69 | 985.31 | √(photon e⁻) — dominant |
| quantization | 88.05 | 88.05 | gain/√12 at 305 e⁻/DN |
| read_noise | 18.00 | 12.00 | vendor CDS values |
| dark_shot | 16.76 | 2.65 | √(dark rate × t_int) |
| glow_shot | 0.07 | 0.07 | 5 e⁻/s ROIC glow |
| ktc_reset | 0.00 | 0.00 | suppressed by CDS |
| background_shot | 0.00 | 0.00 | 0 by design (extended regime, Decision #13) |
| nearfield_shot | 0.00 | 0.00 | scalar mode, ε = 0 |
| **TOTAL (RSS)** | **1037.73** | **989.32** | |
| Signal [e⁻] | 1,068,522 | 970,841 | |
| SNR [--] | 1029.7 | 981.3 | |

### Cooler-Budget Trade (exact Arrhenius inversion, no sweep)

| Quantity | InSb | HgCdTe | Definition |
|----------|-----:|-------:|------------|
| Dark rate at 77 K [e⁻/s] | 280,868 | 7,022 | J(77 K)·A_pix/q |
| Crossover T [K] | **77.3** | **84.1** | dark shot = read noise (rate = RN²/t) |
| BLIP T [K] | **101.7** | **115.4** | dark rate = photon rate |
| NEI [photons/s/cm²] | 5.363e+11 | 5.620e+11 | σ_total/(QE·A_pix·t) |
| NEI [W/cm²] (approx) | 2.507e-08 | 2.627e-08 | × E_photon at 4.25 µm |

Both temperatures come from `DarkCurrentCurve.temperature_at_rate` — the
exact inverse of the loader's Arrhenius interpolation, so no temperature
sweep or root-finder is needed.

### Spectral vs. Band-Averaged QE

| Detector | Signal (spectral) [e⁻] | Signal (scalar) [e⁻] | Δ |
|----------|-----------------------:|---------------------:|----:|
| InSb | 1,068,522 | 1,055,678 | +1.22% |
| HgCdTe | 970,841 | 960,476 | +1.08% |

The spectral run photon-weights QE(λ) against the 300 K Planck spectrum
(in-band photons concentrate at the long-wavelength end, where both QE
curves are near their peaks); a flat average cannot capture that
correlation. ~1% here, but it grows with steeper QE slopes or wider bands.

## Physics Discussion

**Both FPAs are photon-noise-dominated at 77 K.** Signal shot noise
(~1000 e⁻) dwarfs every other term, so at the nominal set point the SNR
ratio is simply the √(signal) ratio, which tracks the QE ratio — InSb's
higher, flatter QE (0.860 vs 0.782 band-averaged) buys it ~10% more signal
and ~5% more SNR. The dark-current difference (281 vs 7 e⁻ accumulated) is
irrelevant *at 77 K on a bright bench*.

**The trade separates at warmer set points.** HgCdTe's 40× lower J_dark
means its dark shot noise reaches the read-noise floor at 84.1 K vs 77.3 K
for InSb, and it stays background-limited to 115.4 K vs 101.7 K. That
~7–14 K of set-point margin is cooler mass, power, and lifetime at the
mission level — the classic InSb (QE/uniformity) vs HgCdTe (operability
margin) trade, now with vendor-data-derived numbers.

**Quantization is the #2 noise term.** At 305 e⁻/DN (5 Me⁻ well over 14
bits), gain/√12 = 88 e⁻ RMS — larger than either FPA's read noise. On this
bright bench it costs nothing (photon noise dominates), but for
low-background scenes Mike should ask the ROIC vendor for a low-gain /
dual-gain mode; otherwise the ADC, not the detector, sets the floor.

**kTC cross-check.** With CDS off, reset noise would be √(k_B·T·C)/q =
37.0 e⁻ RMS at 33 fF / 77 K (hand calculation); RADIANT reports
ktc_reset = 0 with `readout.cds_enabled = 1` — suppressed, as configured.

**Unused parameters.** In the extended regime RADIANT skips the separate
scene-background photon term (matrix Decision #13): `background_shot = 0`
by design and the bench-ambient background temperature feeds only the
contrast scene. `nearfield_shot = 0` because scalar transmission mode
defaults the lumped train to ε = 0 (set `optics.scalar_emissivity` to model
warm-optics emission — not needed on this cold-filtered bench).

## Gaps Identified

See `gaps.md`. Highlights: the two vendor-CSV import gaps from the catalog
are **closed** by `radiant.io.qe_csv` / `radiant.io.dark_current_csv`;
`detector.qe_table_path` is schema-only and unwired (new registry Gap 44);
BLIP/crossover/NEI remain script-side computations (new registry Gap 45,
low severity now that the loaders make them one-liners); the
"detector-only bench mode" ask folds into registry Gap 42.

## Outputs

- `outputs/detector_shootout_results.xlsx` — noise budget + cooler-trade sheets
- `outputs/fig1_jdark_vs_temperature.png` — vendor J_dark(T) with crossover/BLIP markers
- `outputs/fig2_qe_curves.png` — both vendor QE curves in canonical units
- `outputs/fig3_noise_budget.png` — side-by-side noise budget (log scale)
- `outputs/fig4_dark_shot_vs_temperature.png` — dark shot noise vs T against read-noise floors

## What Mike Would Do Next

1. **Push the cooler set point in the model**: re-run at 85–110 K to
   quantify SNR erosion vs cooler savings (the J_dark tables now cover it)
2. **Ask the ROIC vendor about a low-gain mode** — 88 e⁻ quantization noise
   would dominate a low-background scene
3. **Repeat with mission optics and scene** instead of the bench: the
   f/2.3 bright bench flatters both detectors; a slower, colder system
   moves the BLIP temperatures down
4. **Feed the QE curves into the dual-band trade** (scenario 1.3 uses the
   same importer)
