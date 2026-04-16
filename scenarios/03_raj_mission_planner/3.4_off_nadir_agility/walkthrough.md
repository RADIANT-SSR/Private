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

| Angle [deg] | Tau (mean) | SNR   | GSD GM [m] | NIIRS (corr) | dNIIRS |
|-------------|------------|-------|------------|--------------|--------|
| 0           | 0.4661     | 85.8  | 1.37       | 5.86         | 0.00   |
| 5           | 0.4649     | 87.6  | 1.38       | 5.86         | +0.01  |
| 10          | 0.4612     | 89.4  | 1.41       | 5.85         | -0.01  |
| 15          | 0.4549     | 91.1  | 1.45       | 5.82         | -0.03  |
| 20          | 0.4460     | 92.7  | 1.50       | 5.78         | -0.08  |
| 25          | 0.4342     | 94.3  | 1.59       | 5.71         | -0.15  |
| 30          | 0.4194     | 95.7  | 1.71       | 5.62         | -0.24  |
| 35          | 0.4012     | 97.0  | 1.86       | 5.50         | -0.36  |
| 40          | 0.3793     | 98.2  | 2.06       | 5.36         | -0.50  |
| 45          | 0.3532     | 99.3  | 2.34       | 5.19         | -0.67  |

### RADIANT GSD vs. True Off-Nadir GSD

| Angle [deg] | RADIANT GSD [m] | True Cross [m] | True Along [m] | Error [%] |
|-------------|-----------------|----------------|-----------------|-----------|
| 0           | 1.37            | 1.37           | 1.37            | 0.0       |
| 15          | 1.37            | 1.42           | 1.48            | -3.1      |
| 30          | 1.37            | 1.56           | 1.87            | -12.2     |
| 45          | 1.37            | 1.86           | 2.94            | -26.4     |

RADIANT's GSD metric always reports the nadir value (1.37 m) regardless of
`path_zenith_rad`.  At 45 deg, this is 26% too optimistic.

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

NIIRS degrades by -0.67 from nadir to 45 deg.  This is almost entirely from GSD:

- GSD scaling: dNIIRS = -3.32 × log10(GSD_45/GSD_nadir) = -3.32 × log10(2.34/1.37) = -0.76
- The actual degradation (-0.67) is slightly less because RADIANT's SNR increases,
  which partially compensates through the SNR term in GIQE-5.

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

| Angle [deg] | Ground Range [km] | GSD GM [m] | NIIRS | Access Rate [km²/s] |
|-------------|-------------------|------------|-------|---------------------|
| 0           | 0                 | 1.37       | 5.86  | 114                 |
| 30          | 312               | 1.71       | 5.62  | 129                 |
| 45          | 527               | 2.34       | 5.19  | 154                 |

At 45 deg off-nadir, Raj can image a target 527 km from nadir ground track,
but at the cost of -0.67 NIIRS.  Whether this trade is acceptable depends on
the mission's minimum NIIRS requirement.

## Gaps Identified

| Gap # | Description | Impact |
|-------|-------------|--------|
| 33    | GSD not adjusted for off-nadir angle | RADIANT reports nadir GSD even with path_zenith_rad > 0 |
| 34    | NIIRS not recomputed with off-nadir GSD | GIQE-5 uses nadir GSD, overpredicting NIIRS at off-nadir |
| 35    | No along-track vs cross-track GSD at off-nadir | Both GSD axes equal in RADIANT; no projection correction |
| 36    | No swath width / access geometry calculator | Must compute externally |

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
