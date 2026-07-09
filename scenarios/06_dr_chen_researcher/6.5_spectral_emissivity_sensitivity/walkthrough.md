# Scenario 6.5 — Emissivity Sensitivity for Temperature Retrieval

**Persona:** Dr. Chen, researcher studying LWIR retrieval accuracy.
**Question:** How badly does an error in the *assumed* surface emissivity
bias a retrieved surface temperature, and how does that compare to the
sensor's own NEDT?

First consumer of the new `radiant.performance.temperature_retrieval`
model (retrieval inverse + emissivity/temperature Jacobian).

---

## Inputs (non-RADIANT)

| File | Format | Represents |
|------|--------|-----------|
| `inputs/chen_retrieval_config.xlsx` | Excel workbook | True scene (T, ε), the assumed-ε sweep, band, and the system NEDT |

`inputs/create_spreadsheet.py` regenerates it; values are transcribed into
the run script.

---

## The retrieval and its Jacobian

The sensor measures `L = ε_true · B̄(T_true)`. Retrieval inverts
`ε_assumed · B̄(T) = L` for T (Brent root-find). At the operating point the
Jacobian gives the first-order error law:

```
∂L/∂ε = B̄(T)              ∂L/∂T = ε · ∫ dB/dT dλ
ΔT ≈ −(∂L/∂ε / ∂L/∂T) · Δε
```

---

## Results (T=300 K, ε=0.95, LWIR 8–12 µm, NEDT 50 mK)

**Jacobian at the operating point:** ∂L/∂ε = 38.50 W/m²/sr, ∂L/∂T =
0.598 W/m²/sr/K → **dT/dε = −64.4 K per unit ε (−0.64 K per 0.01 ε)**.

| Assumed ε | ε error | Retrieved T | T error |
|-----------|---------|-------------|---------|
| 0.90 | −0.05 | 303.34 K | **+3.34 K** |
| 0.94 | −0.01 | 300.65 K | +0.65 K |
| 0.96 | +0.01 | 299.36 K | −0.64 K |
| 1.00 | +0.05 | 296.89 K | **−3.11 K** |

- **A lower assumed ε → over-estimated T** (the surface must be hotter to
  emit the same radiance); higher assumed ε → under-estimate. Nearly linear
  at −0.64 K per 0.01 ε, matching the Jacobian.
- **NEDT-equivalent ε uncertainty: ±0.0008 (0.08 %).** To keep the
  retrieval bias below the sensor's own 50 mK resolution, emissivity must be
  known to better than a tenth of a percent.
- **Emissivity knowledge, not detector NEDT, limits retrieval accuracy.**
  Over a realistic ±0.05 ε uncertainty the bias reaches 3.3 K — **67× the
  NEDT floor.** Buying a lower-NEDT detector does nothing for absolute
  temperature accuracy until ε is pinned down.

---

## Physics / modeling notes (house rule)

- **Band-averaged Planck** (`band_planck_radiance`) integrates B(λ,T) over
  the filter; the retrieval and Jacobian are consistent band quantities.
- **The first-order law and the exact inversion agree** to within a few
  percent across ±0.05 ε (fig 2), diverging slightly at the sweep ends
  where the Planck non-linearity in T matters — the exact Brent inversion
  is used for the reported biases.
- **This is a bias, not noise.** The retrieval error is a *systematic*
  offset set by the ε assumption; averaging frames (which beats down NEDT)
  does not reduce it. That is the core lesson for absolute LWIR
  thermometry.

---

## Truth anchors

Verified in `src/radiant/performance/tests/test_temperature_retrieval.py`
(8 Level-0 tests): exact round-trip when the assumed ε equals the true ε;
higher assumed ε lowers retrieved T; ∂L/∂ε = B̄(T); ∂L/∂T matches a finite
difference; the first-order error law matches the exact bias for small Δε.
