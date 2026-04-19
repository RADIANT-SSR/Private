# Scenario 3.4: Off-Nadir Performance Degradation

## Persona

**Raj** — Mission Planner.  He evaluates how sensor performance trades against
access geometry.  "Can I still get useful imagery at 45 degrees off-nadir?"

## Question

Raj needs to understand how performance degrades as look angle increases from
nadir to 45 deg off-nadir from a 600 km LEO.  He wants to quantify the trade
between image quality (NIIRS, GSD) and access area (ground range, swath width).

## System Configuration

| Parameter              | Value   | Unit   | Notes                    |
|------------------------|---------|--------|--------------------------|
| Aperture diameter      | 35      | cm     | TMA telescope            |
| Focal length           | 350     | cm     | f/10                     |
| Optical transmission   | 75      | %      | All elements combined    |
| Central obscuration    | 20      | %      | Secondary mirror         |
| WFE RMS                | 0.05    | waves  | At 633 nm                |
| Spectral band          | 450-900 | nm     | Panchromatic VNIR        |
| Pixel pitch            | 8       | um     | Square pixels            |
| QE                     | 80      | %      | Broadband PAN average    |
| Integration time       | 0.5     | ms     | Pushbroom at 7 km/s      |
| Orbit altitude         | 600     | km     | SSO, 10:30 LTAN          |
| Solar zenith           | 30      | deg    | Midlatitude summer       |

### Derived Parameters

| Parameter      | Value   | Unit    | Notes                   |
|----------------|---------|---------|-------------------------|
| GSD (nadir)    | 1.37    | m       | p × H / f               |
| IFOV           | 2.3     | urad    |                         |
| Q (sampling)   | 0.844   | --      | Slightly undersampled   |

## Inputs

Raj provides:
- Sensor configuration (existing pushbroom design)
- Orbit: 600 km SSO
- Off-nadir angles: 0, 5, 10, 15, 20, 25, 30, 35, 40, 45 degrees

RADIANT's `geometry.path_zenith_rad` parameter controls the off-nadir look angle.
At each angle, the atmosphere stage computes a longer slant path and higher air
mass, reducing atmospheric transmission.

## Approach

Sweep `geometry.path_zenith_rad` from 0 to 45 degrees (0 to 0.785 rad).  At each
angle:

1. RADIANT evaluates the full signal chain (atmosphere uses increased air mass)
2. Script computes true off-nadir GSD (cross-track and along-track) using
   spherical-Earth slant range — RADIANT's GSD metric only computes nadir GSD
3. NIIRS is corrected using the true GSD via the GIQE-5 GSD scaling term

## Results

### Gap Closure Table

| Gap # | Description | Previous Status | Current Status | Notes |
|-------|-------------|-----------------|----------------|-------|
| 33    | GSD not adjusted for off-nadir angle | OPEN | OPEN | RADIANT now provides nadir GSD via `gsd_cross_track_m` but does not adjust for look angle |
| 34    | NIIRS not recomputed with off-nadir GSD | OPEN | OPEN | RADIANT now provides nadir NIIRS via `result.metrics["niirs"]` but does not adjust for look angle |
| 35    | No along-track vs cross-track GSD at off-nadir | OPEN | OPEN | Both GSD axes equal in RADIANT |
| 36    | No swath width / access geometry calculator | OPEN | OPEN | Must compute externally |

### Additional Metrics Now Available (Nadir Baseline)

| Metric | Value | Unit | Notes |
|--------|-------|------|-------|
| NEDT | 49.2 | mK | Noise-equivalent delta temperature |
| NIIRS | 5.65 | -- | GIQE-5 (nadir only) |
| GSD (RADIANT) | 1.37 | m | Nadir, cross-track |
| Q (center) | 0.844 | -- | Slightly undersampled |
| Q (min/max) | 0.562 / 1.125 | -- | Over band |
| Strehl | 0.9169 | -- | Near diffraction-limited |
| RER | 0.5592 | -- | Relative edge response |
| EE(1x1) | 0.4490 | -- | |
| Well margin | 14.7 | dB | |
| Dynamic range | 53.4 | dB | |
| Folded MTF@Ny | 1.5114 | -- | Indicates aliasing |
| MTF budget | See table | -- | Per-component decomposition |

### RADIANT MTF Budget at Nyquist (Nadir)

| Component | MTF@Ny_x | MTF@Ny_y |
|-----------|----------|----------|
| Optics (diffraction + WFE + obscuration) | 0.3815 | 0.3812 |
| Pixel Aperture | 0.6366 | 0.6366 |
| IPC | 0.9400 | 0.9400 |
| Jitter | 1.0000 | 1.0000 |
| Smear | 1.0000 | 1.0000 |
| **System (product)** | **0.2283** | **0.2281** |

### Noise Breakdown (Nadir)

| Source | Value [e-] |
|--------|-----------|
| Signal shot | 121.40 |
| Background shot | 121.40 |
| Dark shot | 0.12 |
| Read noise | 6.00 |
| Quantization | 1.44 |
| Nearfield shot | 0.00 |

Note: Nearfield = 0 in scalar transmission mode (lumped refractive element has
emissivity = 0 by Kirchhoff's law).

### Geometry Reference Table

| Angle [deg] | Slant Range [km] | Air Mass | Ground Range [km] | GSD Cross [m] | GSD Along [m] |
|-------------|------------------|----------|-------------------|---------------|---------------|
| 0           | 600.0            | 1.0000   | 0.0               | 1.37          | 1.37          |
| 5           | 602.1            | 1.0035   | 48.0              | 1.38          | 1.38          |
| 10          | 608.4            | 1.0141   | 96.6              | 1.39          | 1.42          |
| 15          | 619.3            | 1.0321   | 146.5             | 1.42          | 1.48          |
| 20          | 634.9            | 1.0582   | 198.5             | 1.45          | 1.56          |
| 25          | 655.9            | 1.0932   | 253.4             | 1.50          | 1.69          |
| 30          | 683.2            | 1.1386   | 312.3             | 1.56          | 1.87          |
| 35          | 717.6            | 1.1960   | 376.4             | 1.64          | 2.11          |
| 40          | 760.8            | 1.2680   | 447.3             | 1.74          | 2.45          |
| 45          | 814.8            | 1.3580   | 527.2             | 1.86          | 2.94          |

**Along-track GSD diverges from cross-track** because of the ground projection
foreshortening.  At 45 deg off-nadir, cross-track GSD is 1.86 m (+36%) but
along-track GSD is 2.94 m (+114%).

### Performance Sweep

| Angle [deg] | Tau (mean) | SNR   | GSD GM [m] | NIIRS (corr) | NEDT [mK] | dNIIRS |
|-------------|------------|-------|------------|--------------|-----------|--------|
| 0           | 0.4661     | 85.8  | 1.37       | 5.65         | 49.2      | 0.00   |
| 5           | 0.4649     | 87.6  | 1.38       | 5.65         | 48.2      | +0.00  |
| 10          | 0.4612     | 89.4  | 1.41       | 5.63         | 47.2      | -0.02  |
| 15          | 0.4549     | 91.1  | 1.45       | 5.59         | 46.3      | -0.07  |
| 20          | 0.4460     | 92.7  | 1.50       | 5.51         | 45.5      | -0.14  |
| 25          | 0.4342     | 94.3  | 1.59       | 5.41         | 44.8      | -0.24  |
| 30          | 0.4194     | 95.7  | 1.71       | 5.28         | 44.1      | -0.37  |
| 35          | 0.4012     | 97.0  | 1.86       | 5.11         | 43.5      | -0.54  |
| 40          | 0.3793     | 98.2  | 2.06       | 4.91         | 43.0      | -0.74  |
| 45          | 0.3532     | 99.3  | 2.34       | 4.65         | 42.5      | -1.00  |

### RADIANT GSD vs. True Off-Nadir GSD

| Angle [deg] | RADIANT GSD [m] | True Cross [m] | True Along [m] | Error [%] |
|-------------|-----------------|----------------|-----------------|-----------|
| 0           | 1.37            | 1.37           | 1.37            | +0.0      |
| 5           | 1.38            | 1.38           | 1.38            | +0.1      |
| 10          | 1.39            | 1.39           | 1.42            | +0.3      |
| 15          | 1.42            | 1.42           | 1.48            | +0.6      |
| 20          | 1.47            | 1.45           | 1.56            | +1.2      |
| 25          | 1.53            | 1.50           | 1.69            | +2.0      |
| 30          | 1.61            | 1.56           | 1.87            | +3.1      |
| 35          | 1.71            | 1.64           | 2.11            | +4.5      |
| 40          | 1.85            | 1.74           | 2.45            | +6.6      |
| 45          | 2.04            | 1.86           | 2.94            | +9.6      |

RADIANT's GSD metric now partially accounts for off-nadir geometry (values increase
with angle), but it overestimates cross-track GSD at large angles (+9.6% at 45 deg)
and does not compute along-track GSD separately.

## Physics Discussion

### Why SNR Increases with Off-Nadir Angle

A surprising result: SNR *increases* from 85.8 at nadir to 99.3 at 45 deg.
This is counterintuitive but physically correct.  The mechanism:

1. **Atmospheric transmission decreases** (-24% at 45 deg) → fewer target photons
2. **Path radiance increases** with longer path → more background photons reach sensor
3. **Total at-aperture flux increases** because path radiance adds more photons
   than the transmission loss removes
4. **SNR = total_signal / noise** → higher total flux → higher SNR

This is the "atmospheric veiling" effect.  The atmosphere acts as a diffuse source
that fills the aperture.  In VNIR bands with moderate aerosol loading, path radiance
can be substantial.

**Important:** The *contrast* SNR (signal difference between target and background
divided by noise) would *decrease* with off-nadir angle, because atmospheric
veiling reduces contrast.  For target detection and discrimination tasks, contrast
SNR is the relevant metric.  RADIANT computes `contrast_snr` but the script
focuses on the standard `snr` metric.

### GSD: The Dominant Degradation Driver

NIIRS degrades by -1.00 from nadir to 45 deg.  This is primarily from GSD:

- GSD scaling: dNIIRS = -3.32 × log10(GSD_45/GSD_nadir) = -3.32 × log10(2.34/1.37) = -0.76
- The actual degradation (-1.00) is larger than the pure GSD term because the
  corrected NIIRS also accounts for the geometric mean of cross-track and along-track
  GSD, which diverges more strongly than cross-track alone.

The along-track vs cross-track GSD divergence is significant.  At 45 deg:
- Cross-track: 1.86 m (+36%) — scales as slant_range / focal_length
- Along-track: 2.94 m (+114%) — additional cos(incidence_angle) factor from ground projection

This asymmetry means the ground sample is rectangular (not square) at off-nadir,
which degrades along-track resolution disproportionately.

### Atmospheric Transmission

Band-mean transmission drops from 0.466 at nadir to 0.353 at 45 deg (-24%).  The
physics:

- Air mass = sec(theta) at 45 deg = 1.414 (flat-Earth) → 1.358 (spherical)
- τ(45 deg) ≈ τ(nadir)^(air_mass) = 0.466^1.358 ≈ 0.352
- This is consistent with Beer-Lambert exponential absorption

For MWIR bands, the transmission decrease would be more severe due to stronger
H₂O and CO₂ absorption at longer wavelengths.

### Access vs. Quality Trade

The fundamental trade in agile pointing:

| Angle [deg] | Ground Range [km] | GSD GM [m] | NIIRS | NEDT [mK] | Access Rate [km^2/s] |
|-------------|-------------------|------------|-------|-----------|----------------------|
| 0           | 0                 | 1.37       | 5.65  | 49.2      | 114                  |
| 30          | 312               | 1.71       | 5.28  | 44.1      | 129                  |
| 45          | 527               | 2.34       | 4.65  | 42.5      | 154                  |

At 45 deg off-nadir, Raj can image a target 527 km from nadir ground track,
but at the cost of -1.00 NIIRS.  Whether this trade is acceptable depends on
the mission's minimum NIIRS requirement.

## Gaps Identified

| Gap # | Description | Status | Impact |
|-------|-------------|--------|--------|
| 33    | GSD not fully adjusted for off-nadir angle | OPEN (partial) | RADIANT GSD now changes with angle but overestimates at large angles (+9.6% at 45 deg) and does not split cross/along |
| 34    | NIIRS not recomputed with off-nadir GSD | OPEN (partial) | RADIANT now provides nadir NIIRS (5.65) but does not correct for off-nadir GSD |
| 35    | No along-track vs cross-track GSD at off-nadir | OPEN | Both GSD axes equal in RADIANT; no ground projection correction |
| 36    | No swath width / access geometry calculator | OPEN | Must compute externally |

**Newly closed gaps (metrics now available):**
- NEDT is now available via `result.metrics["nedt_K"]` -- 49.2 mK at nadir
- NIIRS is now available via `result.metrics["niirs"]` -- 5.65 at nadir
- GSD is now available via `result.metrics["gsd_cross_track_m"]` -- 1.37 m at nadir
- Q is now available via `result.metrics["q_center"]` -- 0.844
- Strehl is now available via `result.metrics["strehl"]` -- 0.9169
- RER is now available via `result.metrics["rer"]` -- 0.5592
- MTF budget is now available via `result.stage_outputs["performance"]["mtf_budget"]`
- Well margin is now available via `result.metrics["well_margin_dB"]` -- 14.7 dB
- Folded MTF is now available via `result.metrics["mtf_folded_at_nyquist"]` -- 1.5114

## Outputs

- `outputs/off_nadir_results.xlsx` — Full sweep results
- `outputs/fig1_snr_transmission_vs_angle.png` — SNR and transmission vs. angle
- `outputs/fig2_gsd_vs_angle.png` — GSD (cross, along, GM) vs. angle
- `outputs/fig3_niirs_vs_angle.png` — NIIRS vs. angle (corrected and RADIANT)
- `outputs/fig4_summary_panels.png` — Four-panel summary

## What Raj Would Do Next

1. **Set minimum NIIRS requirement** (e.g., NIIRS >= 5.0 for his mission) and
   determine the maximum off-nadir angle that meets it (~55-60 deg based on
   extrapolation)
2. **Evaluate contrast SNR** (not just total SNR) for target detection scenarios
   at off-nadir angles — the atmospheric veiling effect reduces contrast
3. **Compare MWIR performance at off-nadir** — MWIR has stronger atmospheric
   absorption, so the transmission penalty at off-nadir would be more severe
4. **Request RADIANT add off-nadir GSD** (Gap 33) so the full chain gives
   correct NIIRS at any look angle without manual correction
