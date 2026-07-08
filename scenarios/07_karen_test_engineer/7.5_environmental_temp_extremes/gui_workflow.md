# Scenario 7.5 GUI Workflow: Performance at Temperature Extremes

How this scenario would be completed in the RADIANT GUI.

## Persona
Karen, test engineer. A TVAC temperature sweep, measured J(T) and QE(T)
tables, an acceptance spec, and an operating-point recommendation to sign.

## Step 1: Import Measured TVAC Data
- **File > Import > Measured Curve** for J(T) (`load_measured_curve`,
  T_K → e⁻/s) and QE(T) (T_K → QE) — previews with units confirmed
- The GUI notes: "e⁻/s dark data → generic curve loader; vendor A/cm²
  datasheets → dark-current importer (scenario 2.1)"

## Step 2: Load the As-Built Sensor + Spec
- Unit-aware workbook import (Gap 6); the spec limits (min SNR, max NEDT)
  load into a **compliance panel** the sweep will check against
- Lab-bench preset (exo + `platform.h_sensor`, registry Gap 42)

## Step 3: Temperature Sweep
- "Sweep FPA temperature" runs each set point with **co-varying** J(T) and
  QE(T) auto-set from the measured tables (the GUI does the interpolation;
  registry Gap 48 — no native QE(T) yet)
- Live table: QE, well %, noise terms, SNR, NEDT per temperature, with
  PASS/FAIL cells against the spec

## Step 4: Analysis Views
- **Dark-current panel**: measured vs Arrhenius fit (semilog) with the
  super-Arrhenius knee flagged and the % excess called out — "an Arrhenius
  extrapolation under-predicts 95 K dark current 8×"
- **QE-vs-dark card**: the isolated NEDT-with-QE(T) vs NEDT-frozen-QE
  comparison, headline "dark current dominates; QE(T) is second-order"
- **Noise-budget stack**: variance vs temperature, dark growing
- **SNR/NEDT vs T** with spec lines and the compliant band shaded green

## Step 5: Recommendation
- The GUI reports the warmest compliant set point, its margin, and a
  recommended operating T with a guard band — with a tooltip explaining the
  guard against cooler drift + the knee's steepness

## Step 6: Export
- Acceptance data package: sweep table (PASS/FAIL), the three figures, the
  recommended set point and margin

## Script Window Commands
```python
from radiant.io.measurement import load_measured_curve
jdark = load_measured_curve("karen_dark_current_tvac.csv", x_unit="K")
qe_t = load_measured_curve("karen_qe_vs_temperature.csv", x_unit="K")

import numpy as np
for T, J in zip(jdark.x, jdark.y):
    sensor.set("detector.detector_temperature_K", T)
    sensor.set("detector.dark_rate_e_per_s", J)      # measured, not Arrhenius
    sensor.set("detector.qe_value", float(np.interp(T, qe_t.x, qe_t.y)))
    r = sensor.evaluate()  # SNR, NEDT per point
```

## GUI Requirements Summary

| Requirement | Priority | Gap |
|-------------|----------|-----|
| Measured J(T)/QE(T) curve import | High | **CLOSED** (Gap 30 loader; 2.1 importer for A/cm²) |
| Co-varying J(T)+QE(T) temperature sweep | High | Registry Gap 48 (GUI interpolates QE(T) until native) |
| Measured-vs-Arrhenius panel with knee flag | High | — |
| QE-vs-dark impact card | Medium | — |
| Spec compliance table + margin + recommendation | High | — |
| NEDT output (with Gap 43 caveat chip) | High | **CLOSED** (metrics["nedt_K"]) |
