# Scenario 7.1 Walkthrough: Predicted vs. Measured NEDT Reconciliation

## The Problem

Karen is a test engineer who has just completed TVAC testing of an as-built MWIR sensor. She measured NEDT at seven blackbody temperatures from 15°C to 50°C. Her primary measurement at 25°C gave NEDT = 127.0 mK, but RADIANT predicts 110.1 mK with the as-built parameters. Where does the 16.9 mK discrepancy come from?

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
| 15.0 | 288.15 | 160.0 | 138.7 | 21.3 | 97,857 | 3,759 |
| 20.0 | 293.15 | 142.0 | 123.0 | 19.0 | 118,204 | 4,393 |
| **25.0** | **298.15** | **127.0** | **110.1** | **16.9** | **141,916** | **5,106** |
| 30.0 | 303.15 | 114.0 | 99.3 | 14.7 | 169,401 | 5,903 |
| 35.0 | 308.15 | 104.0 | 90.2 | 13.8 | 201,096 | 6,791 |
| 40.0 | 313.15 | 95.0 | 82.5 | 12.5 | 237,468 | 7,775 |
| 50.0 | 323.15 | 81.0 | 70.3 | 10.7 | 326,266 | 10,057 |

The predicted NEDT is systematically lower than measured by 10–21 mK (13–15%), with the gap larger at lower temperatures. Both curves show the expected 1/√(signal) behavior — NEDT decreases as the blackbody temperature increases because higher temperatures produce more signal.

### Step 5: Noise Breakdown at Primary Test Point (25°C)

RADIANT's noise budget at the primary test point:

| Noise Term | σ [e⁻ RMS] | NEDT_i [mK] | Fraction [%] |
|------------|-----------|-------------|-------------|
| signal_shot | 376.7 | 73.8 | 44.9 |
| background_shot | 348.6 | 68.3 | 38.5 |
| nearfield_shot | 228.6 | 44.8 | 16.5 |
| read_noise | 14.2 | 2.8 | 0.1 |
| quantization | 3.5 | 0.7 | <0.1 |
| dark_shot | 0.3 | 0.1 | <0.1 |
| **RSS TOTAL** | **562.0** | **110.1** | **100.0** |

The noise is overwhelmingly dominated by photon shot noise (signal + background + nearfield = 99.9%). This is expected for a BLIP (Background-Limited Infrared Photodetector) system in MWIR with warm optics. Read noise and dark current are negligible at this signal level.

The three photon noise sources:
- **signal_shot** (44.9%): Shot noise from the blackbody photons — the fundamental limit
- **background_shot** (38.5%): Shot noise from the shroud (295.15 K, ε = 0.95) filling the rest of the FOV
- **nearfield_shot** (16.5%): Shot noise from thermal emission of the warm optics (295.15 K, 4 elements)

### Step 6: Gap Analysis

The gap between predicted and measured NEDT implies additional noise sources:

```
σ_measured  = NEDT_meas × dS/dT = 127.0 mK × 5,106 e⁻/K = 648.4 e⁻ RMS
σ_predicted = 562.0 e⁻ RMS
σ_missing   = √(648.4² − 562.0²) = 323.4 e⁻ RMS
```

This missing noise of 323 e⁻ RMS is significant — it's 58% of the predicted noise. No single modeled noise term, if increased alone, could plausibly explain this gap. The most likely explanations are:

1. **Unmodeled ROIC glow** (5 e⁻/s in the spreadsheet, not currently modeled as a noise source in RADIANT)
2. **Spatial non-uniformity in the NEDT measurement** — Karen measures NEDT as the spatial σ across a 100×100 ROI, which includes pixel-to-pixel responsivity variations (PRNU/DSNU) that inflate the measured temporal NEDT
3. **Blackbody temperature calibration uncertainty** — the CI Systems SR-800R has ±0.02°C stability, which at dS/dT ≈ 5,100 e⁻/K contributes ~100 e⁻ of uncertainty
4. **Stray light and chamber reflections** — the TVAC shroud (ε = 0.95) reflects 5% of the blackbody emission back to the sensor

### Step 7: Sensitivity Analysis

Perturbing each parameter by ±1% reveals which parameters have the largest impact on NEDT:

| Parameter | Sensitivity [mK / 1% change] | Direction |
|-----------|-------------------------------|-----------|
| f-number (via focal length) | 1.10 | ↑f/# → ↑NEDT |
| Optical transmission | 0.86 | ↑τ → ↓NEDT |
| QE | 0.55 | ↑QE → ↓NEDT |
| Integration time | 0.55 | ↑t_int → ↓NEDT |
| Read noise | 0.001 | negligible |
| Dark current | 0.000 | negligible |

f-number and optical transmission dominate because they directly scale the photon flux reaching the detector. In the BLIP regime, NEDT ∝ 1/√(signal), and signal ∝ τ/f#². Read noise and dark current are irrelevant because they are 1000× smaller than the photon shot noise.

### Step 8: Nominal vs. As-Built Comparison

| Configuration | NEDT at 25°C [mK] |
|---------------|-------------------|
| Nominal design | 103.4 |
| As-built | 110.1 |
| Measured | 127.0 |

The as-built parameters explain 6.7 mK of NEDT degradation from nominal (QE dropped 4%, transmission dropped 2%, f/# increased 1.25%, read noise increased 18%, dark current increased 35%). The remaining 16.9 mK gap is not explained by the known parameter deviations — it comes from noise sources not in the model.

## Key Takeaways

1. **The sensor is BLIP-dominated.** 99.9% of the noise comes from photon shot noise (signal + background + nearfield). Read noise and dark current are completely negligible. This means further improvements require cold optics, cold shielding, or spectral narrowing — not better detectors.

2. **Background shot noise is almost as large as signal shot noise** (38.5% vs. 44.9%) because the shroud at 295 K is nearly as warm as the 298 K blackbody. In the MWIR band, a 3 K temperature difference produces only a small radiance contrast. The warm shroud also contributes nearfield emission from the optics.

3. **The 16.9 mK gap is a real measurement-model discrepancy**, not a parameter error. The sensitivity analysis shows that no ±1% parameter perturbation can explain the gap. The most likely cause is spatial non-uniformity in the measurement (PRNU/DSNU inflating the temporal NEDT), combined with unmodeled stray light from the TVAC chamber.

4. **NEDT improves (decreases) at higher blackbody temperatures** because dS/dT increases faster than noise. This is the Planck function effect: ∂L/∂T increases with T in the Wien regime (for MWIR at 288–323 K), while shot noise grows only as √signal.

5. **The as-built parameter deviations explain only 6.7 mK** of degradation. This tells Karen that the as-built sensor is performing close to its as-built specification — the gap is in the test setup or measurement method, not the sensor itself.

## Gaps Identified

- **Gap 1 (No per-term NEDT breakdown)**: RADIANT computes total NEDT via `result.metrics["nedt_K"]` but does not break it down by individual noise term. The script must manually compute `NEDT_i = σ_i / (dS/dT)` for each NoiseTerm. A native `result.nedt_breakdown` attribute would save Karen significant effort.

- **Gap 2 (No gap analysis mode)**: RADIANT has no built-in capability to compare predicted vs. measured NEDT and compute the missing noise σ. The script computes `σ_missing = √(σ_meas² − σ_pred²)` manually. A built-in `reconcile(measured_nedt_mK=...)` method would be useful for test engineers.

- **Gap 3 (No lab/TVAC mode documentation)**: Using `"atmosphere": {"model": "exo"}` for a lab/TVAC test works correctly but is not documented as the recommended approach for laboratory testing. A "lab mode" alias or documentation section would help test engineers like Karen.

- **Gap 4 (dS/dT via finite difference only)**: The script computes dS/dT by running RADIANT three times (at T, T±δ). RADIANT's native NEDT uses an internal Planck derivative, but the finite-difference approach is more accurate because it captures the full signal chain (optics, QE, etc.) — not just the Planck function. Exposing the internal dS/dT value would allow cross-checking.

- **Gap 5 (ROIC glow not modeled as noise source)**: The spreadsheet lists ROIC glow at 5 e⁻/s, but RADIANT does not include a `glow_shot` noise term (it exists in the noise term list but is always zero). Adding ROIC glow as a modeled noise contributor would improve accuracy for low-signal scenarios, though for this BLIP-dominated case the impact is negligible (√(5 × 0.0005) ≈ 0.05 e⁻ RMS).
