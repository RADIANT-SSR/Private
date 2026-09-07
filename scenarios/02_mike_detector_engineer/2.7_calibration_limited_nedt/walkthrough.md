# Scenario 2.7 Walkthrough: Calibration-Limited NEDT — LWIR Staring, Two-Point NUC

## Persona
Mike, detector engineer. His LWIR staring camera's datasheet NEDT (~25 mK) comes
from the temporal noise budget — the number RADIANT used to report. But every
staring LWIR system he has fielded is limited by the residual fixed-pattern
noise the two-point NUC leaves behind, not by temporal noise. With the Gap 120
calibration model he can finally model the calibration process itself: where
the cal points sit, what the detector nonlinearity leaves behind, how fast the
correction decays, and what the blackbody source's own uncertainty does to
absolute accuracy.

## System Configuration
| Parameter | Value | Unit |
|---|---|---|
| Aperture diameter | 10 | cm |
| Focal length (f/1.5) | 15 | cm |
| Spectral band | 8–12 | µm |
| Optical transmission | 85 | % |
| Quantum efficiency | 65 | % |
| Pixel pitch | 12 | µm |
| Dark current (60 K) | 5×10⁵ | e-/s |
| Full well | 20 | Me- |
| Read noise | 350 | e- RMS |
| Integration time | 120 | µs (~50 % fill at 300 K) |

| Calibration parameter | Value | Unit |
|---|---|---|
| Scheme | two-point NUC | — |
| Cal points | 290 / 310 | K |
| Nonlinearity dispersion (1σ) | 1.0 | % of full scale |
| Pre-cal PRNU / DSNU (1σ) | 2.0 % / 300 e- | — |
| Gain drift | 0.005 | %/hour |
| Offset drift | 720 | e-/hour |
| Cal source: ε, ΔT(1σ), Δε(1σ) | 0.98, 0.5 K, 0.005 | — |

## Key Results (from `scripts/run_calibration_limited_nedt.py`)

### 1. Scene sweep — the parabolic calibration floor

| T_scene [K] | NEDT old [mK] | NEDT uncal [mK] | NEDT 2-pt [mK] | Cal floor [mK] |
|---|---|---|---|---|
| 280 | 26.84 | 1086.54 | 30.73 | 14.96 |
| **290 (cal)** | 26.13 | 1161.49 | **26.13** | **0.00** |
| 300 | 25.54 | 1238.73 | 26.02 | 4.94 |
| **310 (cal)** | 25.06 | 1318.21 | **25.06** | **0.00** |
| 320 | 24.67 | 1399.90 | 28.84 | 14.94 |
| 330 | 24.34 | 1483.77 | 46.97 | 40.17 |
| 340 | 24.08 | 1569.78 | **79.86** | 76.15 |

- **NEDT old** (scheme `none`, imaging regime) is the pre-Gap-120 answer: FPN
  assumed perfectly calibrated away — the tool reports the temporal floor and
  flatters the design everywhere.
- **NEDT uncal** (scheme `none`, detection regime) is the other extreme: the
  raw 2 % PRNU in the budget, ~1.2 K class — no calibration at all.
- **NEDT 2-pt** is the honest achieved number: **exactly** the temporal floor
  at the cal points (the two-point correction is exact there), degrading
  parabolically outside the span to 3.3× the datasheet number at 340 K. Cal
  point *placement* is now a design trade the tool can answer.

### 2. Drift — the cal-cadence trade (T_scene = 340 K)

| Time since cal [h] | NEDT [mK] | Gain drift [e- RMS] | Offset drift [e- RMS] |
|---|---|---|---|
| 0 | 79.86 | 0 | 0 |
| 6 | 88.90 | 3 263 | 4 320 |
| 24 | 175.47 | 13 053 | 17 280 |
| 72 | 475.49 | 39 159 | 51 840 |

The NUC residual itself is drift-free (set by nonlinearity); the gain/offset
corrections decay time-linearly (ratified D4), so the floor re-grows between
cal events — recalibration cadence in one table.

### 3. Precision vs accuracy (T_scene = 300 K) — ratified D3/D6

| Deliverable | Value | Unit |
|---|---|---|
| NEDT (precision) | 26.02 | mK |
| Radiometric accuracy (bias) | 0.955 | % of radiance |
| Radiometric accuracy (bias) | 591.5 | mK at scene temperature |

The cal-source uncertainty (ΔT = 0.5 K through the 8–12 µm Planck
log-derivative ≈ 1.6 %/K, plus Δε/ε = 0.51 %) moves the whole radiometric
*scale*. It is a **bias**, reported beside NEDT and never RSS'd into it
(`BiasTerm` path, contract-tested): a temperature-retrieval product carries
both numbers — a ±26 mK spread around a possible 0.59 K offset. This is the
temperature-retrieval accuracy demo folded in per ratified D6.

## Physics Notes
- Residual formula (ratified D1): σ_NUC = σ_β·|(S−S₁)(S−S₂)|/S_ref — the
  classical two-point correctability shape (Schulz & Caldwell 1995); exact
  algebra and Monte-Carlo anchors in `calibration/tests/test_nuc_residual.py`.
- The residual is added **after** readout scaling: correlated errors do not
  average down (ADR-0012 ordering guarantee) — invisible here (no TDI) but
  decisive in scenario 1.4's TDI variant.
- `detector.noise_regime = "imaging"` excludes the *pre-cal* FPN as
  "calibrated out"; the calibration model quantifies exactly what that
  assumption leaves behind, so the floor appears in the imaging-regime NEDT.
- Unused-parameter note: `analog_roic.adc_resolution_bits` participates only
  through quantization noise (negligible at 1300 e-/DN against a 2.5 ke-
  temporal floor); the DSNU pre-cal value is removed by the correction and
  re-enters only through the offset-drift rate.

## Files
- `inputs/mike_calibration_specs.yaml` — vendor-style spec (cm, %, nm, °C, hours)
- `scripts/run_calibration_limited_nedt.py` — the sweep runner
- `outputs/calibration_limited_nedt_results.csv` — all rows (three schemes × sweep)
- `gui_workflow.md` — the same study through the Calibration screen
