# Scenario 7.3: GUI Workflow — MTF Measurement vs. Prediction

Refreshed 2026-07-07 (Phase R): measurement import + comparison are now backed
by real API (`load_measured_curve` / `compare_mtf`, Gap 30); a residual-explainer
workflow (Gaps 31/32) and the CU-058 consistency-warning surfacing are added.

## Overview

Karen needs to overlay lab-measured MTF on RADIANT predictions, decompose the
MTF into components, test candidate residual explainers, and assess defocus
sensitivity.  The GUI must support importing measurement data and interactive
comparison.

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
2. Select the slanted-edge tool's CSV export (`karen_measured_mtf.csv`) — the
   GUI calls `radiant.io.measurement.load_measured_curve` (Gap 30): comment
   lines and the header row are auto-detected; ascending/numeric/duplicate-x
   validation errors surface as actionable dialogs
3. User selects the frequency unit (cy/mm here) — stored as the curve's
   `x_unit` tag; conversion to canonical cy/m happens at comparison time
4. Preview the imported data as a scatter plot (source file + point count shown)
5. **GUI requirement:** Measurement import dialog with unit selection dropdown
   (cy/mm, cy/m, cy/mrad, cy/pixel) backed by `load_measured_curve`

### Step 3: Run Prediction

1. Click "Evaluate" to run the RADIANT signal chain
2. System returns predicted MTF curve (128 points, 0 to ~510 cy/mm)
3. GUI auto-displays predicted MTF overlaid on imported measurement
4. Summary panel shows: MTF@Nyquist = 0.4080, Strehl = 0.8256, RER = 0.6825
5. **Warning surfacing (CU-058):** this configuration (scalar WFE + defocus)
   fires the Rule 4 dual-path consistency warning on every run. The GUI must
   show it as a banner with a plain-language explanation and a "which output
   should I trust?" note (PSF-path curves/metrics), not bury it in a log

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

1. Click "Show Residual" toggle below the MTF plot — backed by
   `compare_mtf(result, curve, frequency_unit="cy/mm")` (Gap 30)
2. Bottom sub-panel appears showing (Predicted - Measured) vs. frequency,
   overlap-only (points outside the predicted grid are counted and shown as
   "excluded", never extrapolated)
3. Horizontal reference lines at +/-0.02 (measurement noise floor)
4. Summary statistics in corner: RMS = 0.0881, Max = 0.1871, 50 compared / 0 excluded
5. **GUI requirement:** Residual sub-plot synchronized with main MTF plot

### Step 6b: Residual Explainer Grid (Gaps 31/32)

1. Click "Explain Residual" — GUI offers candidate effects with parameter
   grids: electronics blur (`readout.electronics_sigma_um`: 0–3 µm) and
   surface-roughness scatter (`optics.surface_roughness_nm`: 0–5 nm)
2. GUI re-runs the chain per grid point and ranks by `compare_mtf` residual RMS
3. Result table highlights the best fit — here the as-built config (both
   hypotheses REJECTED: every added blur worsens the fit because the
   prediction already sits below the measurement)
4. Diagnosis panel explains the residual sign: negative mean residual →
   blur-type hypotheses cannot help → points to scalar-WFE shape ambiguity;
   suggests importing the as-built Zernike prescription (`load_zemax_zernike`,
   Gap 26)
5. **GUI requirement:** hypothesis-grid runner with rank table and a
   plain-language diagnosis of the residual's sign/shape

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

# Import measured data (Gap 30)
from radiant.io.measurement import load_measured_curve
curve = load_measured_curve("karen_measured_mtf.csv", x_unit="cy/mm")

# Overlay plot
plot(freq / 1000, mtf, "b-", label="RADIANT")  # cy/m -> cy/mm
plot(curve.x, curve.y, "ko", label="Measured")
xlabel("Spatial Frequency [cy/mm]")
ylabel("MTF [--]")

# Residual via compare_mtf (Gap 30) — unit-aware, overlap-only
from radiant.api import compare_mtf
cmp = compare_mtf(result, curve, axis="x", frequency_unit="cy/mm")
print(cmp.table())
print(f"Residual RMS: {cmp.rms_residual:.4f} [--] "
      f"({cmp.n_compared} compared, {cmp.n_excluded} excluded)")

# Component MTF at specific frequency
from radiant.platform.sampling import pixel_aperture_mtf_1d
mtf_pixel = pixel_aperture_mtf_1d(meas_freq_cy_m, 10e-6)  # 10 um pixel
```

### Step 9: Performance Metrics Dashboard

1. Navigate to "Performance Dashboard" tab
2. Dashboard displays all available metrics in organized panels:

**Spatial Metrics Panel:**
- Strehl: 0.8256 [--]
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
| Measurement data import dialog | High | **CLOSED** (Gap 30 — `load_measured_curve`) |
| MTF overlay + residual with measured data | High | **CLOSED** (Gap 30 — `compare_mtf`) |
| Residual-explainer hypothesis grid | High | **CLOSED** (Gaps 31/32 — params exist; GUI runner needed) |
| Consistency-warning banner with trust guidance | High | CU-058 (surface, don't bury) |
| Frequency unit switching (cy/mm, cy/m, cy/px) | Medium | **CLOSED** (Gap 27) |
| MTF component decomposition view | High | **CLOSED** (Gap 19) |
| Residual sub-plot | Medium | -- |
| Defocus sweep parameter | High | **CLOSED** (Gap 29) |
| Lab mode preset (no atmosphere) | Medium | -- (see registry Gap 42: lab_test sub-case needs a config path) |
| Performance metrics dashboard | High | -- |
| Interactive hover tooltips on MTF curves | Low | -- |
| One-click comparison report export | Low | -- |

## Interpolated-atmosphere availability

No bundled interpolated-atmosphere family serves this scene: 'midlat_summer_sensor_ladder' covers sensor_altitude 3 km to 40000 km; this scene asks for 1 m, below the family's runs. Switching **Atmosphere → Model** to `interpolated` therefore produces exactly one Messages-rail advisory saying so — not a sequence of refusals — and the scene stays on `atmosphere.model = 'simple'`, which serves any geometry.
