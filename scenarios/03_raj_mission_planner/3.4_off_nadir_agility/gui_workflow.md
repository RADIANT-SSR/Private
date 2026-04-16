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

## GUI Requirements Summary

| Requirement | Priority | Gap |
|-------------|----------|-----|
| Off-nadir GSD computation (slant range) | High | Gap 33 |
| NIIRS with off-nadir GSD | High | Gap 34 |
| Along-track vs cross-track GSD | High | Gap 35 |
| Swath width / access geometry | Medium | Gap 36 |
| Angle input in degrees (auto-convert) | Medium | Gap 6 |
| Contrast SNR display alongside total SNR | Medium | -- |
| Access vs. quality trade plot | Medium | -- |
| Map view of ground coverage | Low | -- |
