# Scenario 7.2 GUI Workflow: Radiometric Calibration Verification

How this scenario would be completed in the RADIANT GUI.

## Persona
Karen, test engineer. Five calibrated blackbody set points, measured mean
DN at each, an as-built sensor spec — and a calibration report to write.

## Step 1: Load the As-Built Sensor
- **File > Import Spreadsheet** with the unit-aware mapping dialog (cm, %,
  °C, ms — conversions delegated to `Sensor.set(..., unit=)`, Gap 6)
- "Lab bench / flat-field source" preset sets exo atmosphere + the
  `platform.h_sensor` placeholder (registry Gap 42) behind one checkbox
- **Self-emission panel**: shows the Kirchhoff derivation ε = 1 − τ = 0.28
  feeding `optics.scalar_emissivity` (Gap 37) and the cold-stop leakage
  (`nearfield_fraction = 0.05` from the 7.4 campaign) with the resulting
  modeled offset in DN (24.0 DN) — visible BEFORE the calibration run so
  the user knows what part of the offset is physics

## Step 2: Import the Calibration Run
- **File > Import > Measured Curve** (`load_measured_curve`, Gap 30):
  `T_K, DN_measured` CSV; preview table with units confirmed
- Metadata fields: frames averaged (100), blackbody standard identity

## Step 3: Run the Calibration Sweep
- One click: GUI calls `Sensor.sweep("source.target.temperature",
  set_points, keep_results=True)`
- Progress: 5 chain evaluations; results table fills in DN (the readout
  stage's `signal_dn_final` — DN is a first-class output)

## Step 4: Calibration Report View
- **Predicted vs measured plot** with percent-residual subplot
- **Fit card** (the headline): `measured = a·predicted + b` with
  - a − 1 → gain-scale error chip (+1.62%)
  - b → offset chip (+43.6 DN), displayed NEXT to the modeled nearfield
    offset (24.0 DN) so the user sees modeled vs un-modeled offset split
- **Responsivity panel**: dDN/dT vs set point; dDN/dL slope
- **Linearity panel**: DN vs L(T) with linear fit and % FS deviation bars
  against a configurable linearity budget line (1% FS default)
- **Uncertainty panel**: σ_DN and σ_T per set point, 1-frame and N-frame
- **Advisory callouts**:
  - "Percent residuals are offset-dominated at the cold end — read the
    fit coefficients, not the raw percentages"
  - "Apply calibration" button: stores a·gain and b as the calibration
    pair on the sensor config (provenance-tracked)

## Step 5: Export
- Calibration report (workbook + PDF): fit coefficients, linearity,
  uncertainty, applied-calibration verification

## Script Window Commands
```python
from radiant.io.measurement import load_measured_curve
cal = load_measured_curve("karen_calibration_dn.csv", x_unit="K")

sweep = sensor.sweep("source.target.temperature", cal.x, keep_results=True)
dn_pred = [r.stage_outputs["readout"]["signal_dn_final"] for r in sweep.results]

import numpy as np
a, b = np.polyfit(dn_pred, cal.y, 1)   # gain scale, offset [DN]
```

## GUI Requirements Summary

| Requirement | Priority | Gap |
|-------------|----------|-----|
| Unit-aware spreadsheet import | High | **CLOSED** (Gap 6) |
| Measured-curve import | High | **CLOSED** (Gap 30) |
| DN-domain results everywhere in this view | High | **CLOSED** (readout `signal_dn_final`) |
| Temperature-sweep calibration mode | High | **CLOSED** (`Sensor.sweep`) |
| Gain/offset fit card with modeled-offset context | High | Registry Gap 46 (GUI computes) |
| Responsivity / linearity / uncertainty panels | Medium | Registry Gap 46 (GUI computes) |
| Self-emission derivation panel (ε = 1 − τ) | Medium | **CLOSED** (Gap 37) |
| "Apply calibration" provenance-tracked action | Medium | — |
