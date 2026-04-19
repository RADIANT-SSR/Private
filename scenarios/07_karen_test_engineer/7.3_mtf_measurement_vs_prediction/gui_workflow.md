# Scenario 7.3: GUI Workflow — MTF Measurement vs. Prediction

## Overview

Karen needs to overlay lab-measured MTF on RADIANT predictions, decompose the
MTF into components, and assess defocus sensitivity.  The GUI must support
importing measurement data and interactive comparison.

## Step-by-Step GUI Workflow

### Step 1: Configure As-Built System

1. Open RADIANT GUI
2. Load system configuration:
   - Optics: 20 cm aperture, f/3, 82% transmission, 25% obscuration
   - Detector: 10 um pixels, 85% QE, 1% IPC coupling, fill factor 100%
   - Spectral: 550-750 nm VNIR band
   - WFE: 0.07 waves RMS at 633 nm reference
3. Set atmosphere model to "exo" (vacuum/lab mode)
4. Set geometry to lab (altitude = 0)
5. **GUI requirement:** "Lab mode" preset that zeroes atmosphere and geometry

### Step 2: Import Measured MTF Data

1. Click "Import Measurement Data" (or File > Import > MTF Measurement)
2. Select Karen's CSV/Excel with columns: spatial_frequency_cy_mm, MTF_measured
3. GUI auto-detects frequency units (cy/mm) and converts to cy/m internally
4. Preview the imported data as a scatter plot
5. **GUI requirement:** Measurement import dialog with unit selection dropdown
   (cy/mm, cy/m, cy/pixel, normalized to Nyquist)

### Step 3: Run Prediction

1. Click "Evaluate" to run the RADIANT signal chain
2. System returns predicted MTF curve (128 points, 0 to ~510 cy/mm)
3. GUI auto-displays predicted MTF overlaid on imported measurement
4. Summary panel shows: MTF@Nyquist = 0.6893, Strehl = 0.8324, RER = 0.7767

### Step 4: MTF Overlay Plot

1. Navigate to "MTF Analysis" tab (or Results > Spatial > MTF)
2. GUI displays:
   - Predicted MTF curve (solid blue line)
   - Measured MTF data points (black circles)
   - Nyquist frequency marker (vertical dashed line at 50 cy/mm)
   - Diffraction cutoff marker (vertical line at 512.8 cy/mm)
3. Controls:
   - X-axis units toggle: cy/mm | cy/m | cy/pixel | normalized
   - Frequency range slider (0 to 2x Nyquist for typical view)
   - Log/linear Y-axis toggle
4. **GUI requirement:** Interactive MTF overlay with unit-switchable frequency axis

### Step 5: MTF Component Decomposition

1. Click "Decompose MTF" button (or right-click MTF plot > Show Components)
2. GUI displays individual component curves:
   - Diffraction MTF (from EffectivePSF, optics-only)
   - Pixel aperture MTF (sinc)
   - IPC MTF
   - System MTF (product of all)
3. Each component can be toggled on/off via checkboxes
4. Hover tooltip shows MTF value at cursor frequency for each component
5. **GUI requirement:** MTF budget decomposition view with toggleable components

### Step 6: Residual Analysis

1. Click "Show Residual" toggle below the MTF plot
2. Bottom sub-panel appears showing (Predicted - Measured) vs. frequency
3. Horizontal reference lines at +/-0.02 (measurement noise floor)
4. Summary statistics in corner: RMS = 0.3337, Max = 0.5575
5. **GUI requirement:** Residual sub-plot synchronized with main MTF plot

### Step 7: Defocus Sensitivity Sweep

1. Navigate to "Sensitivity" tab or click "Sweep Parameter"
2. Select sweep parameter: "Focus position [um]" (when implemented)
3. Set sweep range: 0 to 20 um, 9 points
4. Click "Run Sweep"
5. GUI displays: MTF@Nyquist vs. defocus, with Karen's current position marked
6. Read off: 10% MTF loss at ~20 um, Karen's 5 um causes < 1% loss
7. **GUI requirement:** Defocus parameter must exist in RADIANT (Gap 29)

### Step 8: Export and Report

1. Click "Export Results" to save comparison table as Excel
2. Right-click plots to save as PNG/SVG
3. "Generate Report" produces a summary with all plots and tables
4. **GUI requirement:** One-click export of comparison results

## Script Window Commands

In the MATLAB-like script/command window:

```python
# Load system and run
sensor = Sensor.from_dict(config)
result = sensor.evaluate()

# Get predicted MTF curve
freq, mtf = result.stage_outputs["performance"]["mtf_freq_x"], result.stage_outputs["performance"]["mtf_x"]

# Import measured data
import numpy as np
meas = np.loadtxt("measured_mtf.csv", delimiter=",", skiprows=1)
meas_freq_cy_mm, meas_mtf = meas[:, 0], meas[:, 1]
meas_freq_cy_m = meas_freq_cy_mm * 1000.0  # cy/mm -> cy/m

# Overlay plot
plot(freq / 1000, mtf, "b-", label="RADIANT")  # cy/m -> cy/mm
plot(meas_freq_cy_mm, meas_mtf, "ko", label="Measured")
xlabel("Spatial Frequency [cy/mm]")
ylabel("MTF [--]")

# Residual
pred_interp = np.interp(meas_freq_cy_m, freq, mtf)
residual = pred_interp - meas_mtf
print(f"Residual RMS: {np.sqrt(np.mean(residual**2)):.4f} [--]")

# Component MTF at specific frequency
from radiant.platform.sampling import pixel_aperture_mtf_1d
mtf_pixel = pixel_aperture_mtf_1d(meas_freq_cy_m, 10e-6)  # 10 um pixel
```

### Step 9: Performance Metrics Dashboard

1. Navigate to "Performance Dashboard" tab
2. Dashboard displays all available metrics in organized panels:

**Spatial Metrics Panel:**
- Strehl: 0.8324 [--]
- RER: 0.6825 [--]
- FWHM_x: 10.79 [um]
- EE(1x1): 0.6580 [--]
- Q (center/min/max): 0.195 / 0.165 / 0.225 [--]

**MTF Budget Panel:**
- Table showing per-component MTF at Nyquist (x and y axes)
- Optics: 0.8115, Pixel: 0.6364, IPC: 0.9602
- System product: 0.4961 [--]
- Bar chart of MTF contributions (log scale)

**Noise Panel:**
- Bar chart of noise sources: dark_shot (0.32 e-), read_noise (8.00 e-), quantization (2.31 e-)
- Note: Signal/background shot noise ~0 for lab test

**Radiometric Panel:**
- GSD: N/A (lab test, altitude = 0)
- NIIRS: N/A (lab test, altitude = 0)
- NEDT: N/A (lab test, no thermal scene in VNIR)
- Well margin: 429.6 [dB] (near-zero signal)
- Dynamic range: 83.2 [dB]

3. **Script window commands:**
```python
# Performance metrics dashboard
result = sensor.evaluate()

# Strehl, RER, Q
print(f"Strehl: {result.metrics['strehl']:.4f} [--]")
print(f"RER: {result.metrics['rer']:.4f} [--]")
print(f"Q: {result.metrics['q_center']:.3f} [--]")
print(f"FWHM_x: {result.metrics['fwhm_x_m'] * 1e6:.2f} [um]")

# MTF budget decomposition
mtf_budget = result.stage_outputs["performance"]["mtf_budget"]
per_term = mtf_budget.per_term_at_nyquist
seen = set()
for key in per_term:
    base = key.rsplit("_", 1)[0]
    if base in seen: continue
    seen.add(base)
    val_x = per_term.get(f"{base}_x", 1.0)
    val_y = per_term.get(f"{base}_y", 1.0)
    print(f"  {base}: x={val_x:.4f}, y={val_y:.4f}")
print(f"System: x={mtf_budget.system_mtf_at_nyquist_x:.4f} [--]")

# Noise breakdown
for nt in result.noise_terms:
    if nt.value_e > 0.001:
        print(f"  {nt.name}: {nt.value_e:.4f} [e-]")

# Well margin and dynamic range
print(f"Well margin: {result.metrics['well_margin_dB']:.1f} [dB]")
print(f"Dynamic range: {result.metrics['dynamic_range_dB']:.1f} [dB]")

# GSD/NIIRS (None for lab tests)
print(f"GSD: {result.metrics.get('gsd_cross_track_m', 'N/A')} [m]")
print(f"NIIRS: {result.metrics.get('niirs', 'N/A')} [--]")
```

## GUI Requirements Summary

| Requirement | Priority | Gap |
|-------------|----------|-----|
| Measurement data import dialog | High | Gap 30 |
| MTF overlay with measured data | High | Gap 30 |
| Frequency unit switching (cy/mm, cy/m, cy/px) | Medium | Gap 27 |
| MTF component decomposition view | High | **CLOSED** (Gap 19) |
| Residual sub-plot | Medium | -- |
| Defocus sweep parameter | High | **CLOSED** (Gap 29) |
| Lab mode preset (no atmosphere) | Medium | -- |
| Performance metrics dashboard | High | -- |
| Interactive hover tooltips on MTF curves | Low | -- |
| One-click comparison report export | Low | -- |
