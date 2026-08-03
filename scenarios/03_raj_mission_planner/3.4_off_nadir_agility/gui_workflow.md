# Scenario 3.4: GUI Workflow — Off-Nadir Performance Degradation

## Overview

Raj needs to sweep off-nadir angle and see how SNR, GSD, NIIRS, and atmospheric
transmission change.  The GUI must support angle sweeps and display corrected
off-nadir GSD.

## Step-by-Step GUI Workflow

### Step 1: Load Sensor Configuration

1. Open RADIANT GUI
2. Load VNIR pushbroom sensor config:
   - Optics: 35 cm, f/10, 75% transmission, 20% obscuration
   - Detector: 8 um pixels, 80% QE
   - Spectral: 450-900 nm PAN
   - Geometry: 600 km SSO

### Step 2: Configure Off-Nadir Sweep

1. Navigate to "Sweep" or "Parameter Study" panel
2. Select sweep parameter: `geometry.path_zenith_rad`
3. Set range: 0 to 0.785 rad (0 to 45 deg)
4. Steps: 10
5. **GUI requirement:** Angle input in degrees with automatic conversion to radians
6. **GUI requirement:** Display field label as "Off-Nadir Angle" not "Path Zenith"

### Step 3: Run Sweep

1. Click "Run Sweep"
2. Progress bar shows 10/10 evaluations
3. Results populate in the sweep results table

### Step 4: View Results

1. **SNR vs. Angle tab:** Line plot showing SNR increasing (note: path radiance
   adds flux). GUI should also show contrast SNR on same plot.
2. **GSD vs. Angle tab:** Shows corrected cross-track and along-track GSD
   - **GUI requirement:** Must compute off-nadir GSD using slant range, not altitude
   - Show RADIANT GSD (nadir) as dashed reference line for comparison
3. **NIIRS vs. Angle tab:** Shows corrected NIIRS using true GSD
   - Horizontal threshold lines for mission requirements
4. **Transmission vs. Angle tab:** Band-mean atmospheric transmission
5. **Summary table:** All metrics at each angle point

### Step 5: Access Geometry Overlay

1. Click "Show Access Geometry" button
2. Map view or schematic showing:
   - Nadir ground track
   - Ground range to target at each off-nadir angle
   - Swath width at each angle
3. **GUI requirement:** Swath width / ground range calculator (Gap 36)

### Step 6: Trade Space Explorer

1. Click "NIIRS vs. Access Trade" button
2. 2-D plot: NIIRS (y-axis) vs. ground range (x-axis)
3. User clicks on curve to see angle and all metrics at that point
4. Overlay mission requirement lines (e.g., NIIRS >= 5.0, range >= 300 km)
5. Feasible region highlighted

### Step 7: Export

1. "Export Results" saves sweep table as Excel
2. Right-click any plot to save as PNG/SVG
3. "Generate Report" creates summary document

## Script Window Commands

```python
# Configure and run sweep
sensor = Sensor.from_dict(config)

# Sweep off-nadir angle
import math
angles_deg = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45]
for angle in angles_deg:
    sensor.set("geometry.path_zenith_rad", angle * math.pi / 180)
    result = sensor.evaluate()
    print(f"{angle} deg: SNR={result.metrics['snr']:.1f}, "
          f"tau={result.stage_outputs['atmosphere']['tau_atm'].mean():.4f}")

# Compute off-nadir GSD (not available natively — Gap 33)
slant_range_m = altitude_m / math.cos(angle_rad)
gsd_cross = pixel_pitch_m * slant_range_m / focal_length_m
```

### Step 8: Performance Metrics Dashboard

1. Navigate to "Performance Dashboard" tab
2. Dashboard displays all available metrics for nadir baseline:

**Spatial Metrics Panel:**
- Strehl: 0.9065 [--]
- RER: 0.5372 [--]
- FWHM_x: 8.95 [um]
- EE(1x1): 0.3634 [--]
- Q (center/min/max): 0.844 / 0.562 / 1.125 [--]

**MTF Budget Panel:**
- Per-component MTF at Nyquist: Optics 0.3815, Pixel 0.6366, IPC 0.9400
- System product: 0.2283 [--]
- Folded MTF at Nyquist: 0.4544 [--] (≈ 2× the pre-sampling MTF there)
- Alias fraction: 0.5000 [--] (half the apparent response at Nyquist is aliased)

**Radiometric Metrics Panel:**
- SNR: 86.8 [--]
- NEDT: 46.5 [mK]
- Well margin: 20.5 [dB]
- Dynamic range: 59.3 [dB]

**Image Quality Panel:**
- GSD (cross/along): 1.37 / 1.37 [m]
- NIIRS: 5.60 [--]

*(Panel values refreshed 2026-08-02 from the unmodified runner — this file had
been carrying an older run vintage than `walkthrough.md`. Dominant mover:
**CU-253**; see the walkthrough's sweep-table note.)*

**Noise Panel:**
- Signal shot: 121.40 [e-], Background shot: 121.40 [e-]
- Read noise: 6.00 [e-], Quantization: 1.44 [e-]
- Nearfield: 0.00 [e-] (scalar transmission mode)

3. **Script window commands:**
```python
# Performance metrics dashboard
result = sensor.evaluate()

# Spatial metrics
print(f"Strehl: {result.metrics['strehl']:.4f} [--]")
print(f"RER: {result.metrics['rer']:.4f} [--]")
print(f"Q: {result.metrics['q_center']:.3f} [--]")

# Radiometric metrics
print(f"SNR: {result.metrics['snr']:.1f} [--]")
print(f"NEDT: {result.metrics['nedt_K'] * 1000:.1f} [mK]")
print(f"Well margin: {result.metrics['well_margin_dB']:.1f} [dB]")

# Image quality
print(f"GSD: {result.metrics['gsd_cross_track_m']:.2f} [m]")
print(f"NIIRS: {result.metrics['niirs']:.2f} [--]")

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

# Folded MTF (aliasing)
print(f"Folded MTF@Ny: {result.metrics['mtf_folded_at_nyquist']:.4f} [--]")

# Noise breakdown
for nt in result.noise_terms:
    if nt.value_e > 0.001:
        print(f"  {nt.name}: {nt.value_e:.4f} [e-]")
```

## GUI Requirements Summary

| Requirement | Priority | Gap |
|-------------|----------|-----|
| Off-nadir GSD computation (slant range) | High | Gap 33 |
| NIIRS with off-nadir GSD | High | Gap 34 |
| Along-track vs cross-track GSD | High | Gap 35 |
| Swath width / access geometry | Medium | Gap 36 |
| Angle input in degrees (auto-convert) | Medium | Gap 6 |
| Performance metrics dashboard | High | -- |
| Contrast SNR display alongside total SNR | Medium | -- |
| Access vs. quality trade plot | Medium | -- |
| Map view of ground coverage | Low | -- |

## Interpolated-atmosphere availability

Switching **Atmosphere → Model** to `interpolated` works first try on this scene. The picker pre-selects **`midlat_summer_sensor_ladder`** (profile `midlat_summer`, down-looking; covers ground targets only (target altitude fixed at 0 km), sensor 3-100 km plus 40000 km (GEO), nadir only (LOS zenith 0 degrees)); *Use this family* writes `atmosphere.interpolation_axes = 'sensor_altitude_m'`. `Sensor.atmosphere_family_suggestion()` is the same answer from a script.
