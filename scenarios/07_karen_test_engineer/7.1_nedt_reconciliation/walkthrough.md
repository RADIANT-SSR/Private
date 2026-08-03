# Scenario 7.1 Walkthrough: Predicted vs. Measured NEDT Reconciliation

## The Problem

Karen is a test engineer who has just completed TVAC testing of an as-built MWIR sensor. She measured NEDT at seven blackbody temperatures from 15°C to 50°C. Her primary measurement at 25°C gave NEDT = 127.0 mK, but RADIANT predicts 74.17 mK with the as-built parameters. Where does the 52.83 mK discrepancy come from?

This is the classic test-engineer question: **does the model match the measurement, and if not, what explains the gap?**

## The Physics

### What Is NEDT?

NEDT (Noise-Equivalent Differential Temperature) is the minimum temperature difference a sensor can resolve at 1σ:

```
NEDT = σ_total / (dS/dT)
```

where:
- σ_total is the RSS of all noise terms [e⁻ RMS]
- dS/dT is the signal derivative with respect to target temperature [e⁻/K]

Lower NEDT = better thermal sensitivity. For a photon-noise-limited detector:

```
NEDT ∝ 1 / √(signal) ∝ 1 / √(t_int)
```

So NEDT improves (decreases) with longer integration time, up to the point where the well saturates or other noise sources dominate.

### Why dS/dT Matters

dS/dT is how fast the signal changes with temperature — the "responsivity" of the sensor to temperature differences. It comes from the derivative of the Planck function integrated over the spectral band, multiplied by the sensor's throughput chain:

```
dS/dT = d/dT [∫ L(λ,T) × τ_atm × τ_opt × QE × A_pix × Ω × t_int dλ]
```

In the script, dS/dT is computed via finite difference: `(S(T+0.5) - S(T-0.5)) / 1.0`, which is accurate to <0.1% for δT = 0.5 K.

### NEDT Per Noise Term

Each noise term contributes independently to NEDT:

```
NEDT_i = σ_i / (dS/dT)
NEDT_total = √(Σ NEDT_i²)    [RSS]
```

This decomposition tells Karen which noise source dominates and where to focus improvement efforts.

## How RADIANT Solves This

### Step 1: Read Karen's Lab Notebook

Karen's data arrives in an Excel spreadsheet with three sheets:

**System Configuration:**
- 30 cm aperture, f/4.05 (as-built, slightly slower than f/4 nominal)
- 71% optical transmission at 4.25 µm (73% nominal)
- 3.5–5.0 µm bandpass, cold filter at 77 K
- Optics at 22°C (295.15 K) — lab ambient
- CI Systems SR-800R blackbody, ε = 0.995

**As-Built Detector:**
- 18 µm HgCdTe FPA, 640×512
- QE = 68% (72% nominal — 4% degradation)
- Dark current = 135 e⁻/s (100 nominal — 35% higher)
- Read noise = 14.2 e⁻ RMS (12 nominal — 18% higher)
- Integration time = 0.5 ms (lab test; 8 ms orbital)
- IPC = 1.5%

**NEDT Measurements:** 7 temperatures from 15°C to 50°C, 500 frames each.

### Step 2: Unit Conversion

The script converts Karen's spreadsheet units to RADIANT canonical units at the boundary:

| Parameter | Lab Value | Canonical | Conversion |
|-----------|-----------|-----------|------------|
| Aperture | 30.0 cm | 0.300 m | cm ÷ 100 |
| Focal length | 121.5 cm | 1.215 m | cm ÷ 100 |
| Transmission | 71.0 % | 0.710 fraction | % ÷ 100 |
| Optics temp | 22.0 °C | 295.15 K | +273.15 |
| Band | 3500–5000 nm | 3.5–5.0 µm | nm ÷ 1000 |
| QE | 68.0 % | 0.680 fraction | % ÷ 100 |
| Integration time | 0.5 ms | 0.0005 s | ms ÷ 1000 |
| IPC | 1.5 % | 0.015 fraction | % ÷ 100 |

### Step 3: Atmosphere and Regime

RADIANT runs in **exo** (vacuum) mode — `"atmosphere": {"model": "exo"}` — because the sensor is in a TVAC chamber. This sets τ_atm = 1, L_path = 0, L_atm_down = 0. The only thermal emission sources are the blackbody target, the shroud (background at 295.15 K), and the warm optics (nearfield at 295.15 K).

The **extended regime** applies because the blackbody overfills the FOV — every pixel sees blackbody radiance directly.

### Step 4: Predicted vs. Measured NEDT

At each of Karen's seven measurement temperatures, the script runs RADIANT three times (at T, T+0.5, T-0.5) to compute dS/dT via finite difference:

| BB T [°C] | BB T [K] | Meas [mK] | Pred [mK] | Δ [mK] | Signal [e⁻] | dS/dT [e⁻/K] |
|-----------|----------|-----------|-----------|--------|-------------|---------------|
| 15.0 | 288.15 | 160.0 | 83.86 | 76.14 | 99,144 | 3,759 |
| 20.0 | 293.15 | 142.0 | 78.76 | 63.24 | 119,491 | 4,393 |
| **25.0** | **298.15** | **127.0** | **74.17** | **52.83** | **143,203** | **5,106** |
| 30.0 | 303.15 | 114.0 | 70.03 | 43.97 | 170,688 | 5,903 |
| 35.0 | 308.15 | 104.0 | 66.28 | 37.72 | 202,383 | 6,791 |
| 40.0 | 313.15 | 95.0 | 62.87 | 32.13 | 238,756 | 7,775 |
| 50.0 | 323.15 | 81.0 | 56.93 | 24.07 | 327,553 | 10,057 |

The predicted NEDT is systematically lower than measured by 24–76 mK (30–48%), with the gap larger at lower temperatures. Both curves show the expected 1/√(signal) behavior — NEDT decreases as the blackbody temperature increases because higher temperatures produce more signal. **The gap is larger than in older baselines** because the prediction no longer includes a spurious shroud `background_shot` term (Decision #13 — see the noise breakdown below); the cleaner prediction exposes the true model-vs-measurement discrepancy.

### Step 5: Noise Breakdown at Primary Test Point (25°C)

RADIANT's noise budget at the primary test point:

| Noise Term | σ [e⁻ RMS] | NEDT_i [mK] | Fraction [%] |
|------------|-----------|-------------|-------------|
| signal_shot | 378.42 | 74.12 | 99.9 |
| read_noise | 14.20 | 2.78 | 0.1 |
| quantization | 3.46 | 0.68 | <0.1 |
| dark_shot | 0.26 | 0.05 | <0.1 |
| background_shot | 0.00 | 0.00 | 0.0 |
| nearfield_shot | 0.00 | 0.00 | 0.0 |
| **RSS TOTAL** | **378.70** | **74.17** | **100.0** |

The noise is now dominated almost entirely by **signal photon shot noise (99.9%)**. Read noise and dark current are negligible at this signal level.

**Important — the shroud background shot noise is no longer counted, and that is correct.** Older baselines added a `background_shot` term (≈ 349 e⁻, 46 % of the budget) from the 295 K shroud. But during a NEDT measurement the large-area blackbody **fills the target pixel** — the shroud is not in that pixel — so there is no separable background there. Under ADR-0002 Decision #13 the extended-regime pixel is a single radiance field and `background_shot = 0`, removing what was a spurious double-count. This drops the *predicted* NEDT from ≈ 100 mK to 74 mK. The predicted-vs-measured gap therefore **widens** — not because a real term went missing, but because the old prediction was artificially inflated toward the measurement by a background that should not have been in the target pixel. The residual gap is now the *true* model-vs-measurement discrepancy.

**Note**: `nearfield_shot = 0` is a known limitation (Gap 6 below). In scalar transmission mode, the lumped optical element is treated as refractive (ε = 0 by Kirchhoff's law: T + R = 1, ε = 1 − T − R = 0). Mirror self-emission requires `key_elements` or `full_prescription` mode.

### Step 6: Gap Analysis

The gap between predicted and measured NEDT implies additional noise sources:

```
σ_measured  = NEDT_meas × dS/dT = 127.0 mK × 5,106 e⁻/K = 648.4 e⁻ RMS
σ_predicted = 378.7 e⁻ RMS
σ_missing   = √(648.4² − 378.7²) = 526.3 e⁻ RMS
```

This missing noise of 526 e⁻ RMS is large — 139% of the predicted noise. (It is larger than in older baselines because the prediction no longer includes the spurious shroud `background_shot`; the gap now reflects only genuinely unmodeled sources.) The most likely explanations:

1. **Unmodeled ROIC glow** (5 e⁻/s in the spreadsheet, not currently modeled as a noise source in RADIANT)
2. **Spatial non-uniformity in the NEDT measurement** — Karen measures NEDT as the spatial σ across a 100×100 ROI, which includes pixel-to-pixel responsivity variations (PRNU/DSNU) that inflate the measured temporal NEDT
3. **Blackbody temperature calibration uncertainty** — the CI Systems SR-800R has ±0.02°C stability, which at dS/dT ≈ 5,100 e⁻/K contributes ~100 e⁻ of uncertainty
4. **Stray light and chamber reflections** — the TVAC shroud (ε = 0.95) reflects 5% of the blackbody emission back to the sensor

### Step 7: Sensitivity Analysis

Perturbing each parameter by ±1% reveals which parameters have the largest impact on NEDT:

| Parameter | Sensitivity [mK / 1% change] | Direction |
|-----------|-------------------------------|-----------|
| f-number (via focal length) | 0.7428 | ↑f/# → ↑NEDT |
| QE | 0.3714 | ↑QE → ↓NEDT |
| Optical transmission | 0.3714 | ↑τ → ↓NEDT |
| Integration time | 0.3714 | ↑t_int → ↓NEDT |
| Read noise | 0.0010 | negligible |
| Dark current | 0.0000 | negligible |

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-07-09). No Results-affecting landing moved this scenario — it runs on
`atmosphere.model = "exo"`, and every in-window landing's own scope statement
excludes it (CU-224 leaves exo/vacuum paths exactly unchanged; CU-267 and
CU-253 are `simple`-atmosphere only). These sensitivities scale with the
predicted NEDT and had been left carrying the pre-Decision-#13 ≈ 100.6 mK
vintage while the rest of the walkthrough was refreshed to 74.17 mK.*

f-number and optical transmission dominate because they directly scale the photon flux reaching the detector. In the shot-noise-limited regime, NEDT ∝ 1/√(signal), and signal ∝ τ/f#². Read noise and dark current are irrelevant because they are 1000× smaller than the photon shot noise.

### Step 8: Nominal vs. As-Built Comparison

| Configuration | NEDT at 25°C [mK] |
|---------------|-------------------|
| Nominal design | 70.19 |
| As-built | 74.17 |
| Measured | 127.0 |

The as-built parameters explain 3.98 mK of NEDT degradation from nominal (QE dropped 4%, transmission dropped 2%, f/# increased 1.25%, read noise increased 18%, dark current increased 35%). The remaining 52.83 mK gap is not explained by the known parameter deviations — it comes from noise sources not in the model, chiefly the shroud background shot noise the extended-regime model no longer counts (Decision #13) plus unmodeled mirror self-emission (see Gap 6).

## Key Takeaways

1. **The sensor is signal-shot-limited (as modeled).** 99.9% of the predicted noise comes from signal photon shot noise. Read noise and dark current are completely negligible. Further improvements require cold optics, cold shielding, or spectral narrowing — not better detectors.

2. **The old prediction was inflated by a spurious shroud background term.** Because the blackbody fills the target pixel, there is no separable background there; the ~349 e⁻ `background_shot` older baselines added was a double-count that Decision #13 correctly removed. This lowered the predicted NEDT to 74 mK and, honestly, *widened* the gap to the 127 mK measurement — the cleaner prediction exposes the true discrepancy.

3. **The 52.83 mK gap is a real measurement-model discrepancy**, not a parameter error and not the shroud. No ±1% parameter perturbation explains it. Likely causes: (a) unmodeled mirror self-emission from warm optics (nearfield_shot = 0 in scalar mode — see Gap 6), (b) spatial non-uniformity in the measurement (PRNU/DSNU inflating the temporal NEDT), and (c) unmodeled stray light and chamber reflections.

4. **NEDT improves (decreases) at higher blackbody temperatures** because dS/dT increases faster than noise. This is the Planck function effect: ∂L/∂T increases with T in the Wien regime (for MWIR at 288–323 K), while shot noise grows only as √signal.

5. **The as-built parameter deviations explain only 3.98 mK** of degradation. This tells Karen that the as-built sensor is performing close to its as-built specification — the gap is in the test setup or measurement method, not the sensor itself.

## Gaps Identified

See [gaps.md](gaps.md) for full detail with severity and status.

### Gaps Closed Since Last Run
| Gap | Status | Notes |
|-----|--------|-------|
| Gap 1 (per-term NEDT breakdown) | **CLOSED** | `result.metrics["nedt_K"]` now available; per-term breakdown computed via `σ_i / (dS/dT)` |
| Gap 3 (lab/TVAC mode documentation) | **CLOSED** | `atmosphere.model: "exo"` is the documented recommended approach |

### Open Gaps
- **Gap 2 (No built-in reconcile method)**: still open. Script computes σ_missing manually.
- **Gap 4 (Internal dS/dT not exposed)**: still open. Finite-difference workaround used.
- **Gap 5 (ROIC glow not modeled)**: still open. `glow_shot` noise term is always zero.
- **Gap 6 (NEW — Nearfield = 0 in scalar mode)**: HIGH severity. Mirror self-emission not modeled in scalar transmission mode. `nearfield_shot = 0` even with warm optics at 295 K. Workaround: `key_elements` or `full_prescription` optical mode. This likely explains part of the 52.83 mK gap between predicted and measured NEDT.
