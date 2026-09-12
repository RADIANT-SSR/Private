# Scenario 3.4: Off-Nadir Performance Degradation


> **NIIRS applicability — engine update (CU-166).** Since this walkthrough was written, RADIANT added a metric-applicability gate: when one or more GIQE-5 inputs fall outside the calibration envelope — GSD 1.18–31.5 inch, RER 0.20–0.95, SNR 2–130 — the engine reports **NIIRS as N/A** by default instead of silently extrapolating. This configuration is outside that envelope, so the NIIRS values below are the **extrapolated** GIQE-5-form output: reproduce them with `performance.niirs.allow_extrapolated = true` and read them as a *relative trend, not a calibrated rating*. (The SNR/NEDT figures here predate later physics updates and are indicative; a full numeric refresh is tracked separately in the cleanup backlog. No IR-calibrated IIRS model yet — see `docs/tracking/gaps.md` Gap 100.)

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
   spherical-Earth slant range, independently of the chain — this is now a
   *cross-check* of RADIANT's own `gsd_cross_track_m` rather than a
   substitute for it (see "RADIANT GSD vs. True Off-Nadir GSD" below)
3. NIIRS is read from the chain directly — GIQE-5 consumes the two-axis
   off-nadir GSD (geometric mean internally), so no script-side rescale
   remains (CU-340 retired the old GM/cross rescale, which double-counted)

## Results

### Gap Closure Table

| Gap # | Description | Previous Status | Current Status | Notes |
|-------|-------------|-----------------|----------------|-------|
| 33    | GSD not adjusted for off-nadir angle | OPEN | **CLOSED** | `gsd_cross_track_m` tracks the scenario's independent spherical-Earth cross-track GSD to +0.0 % at every swept angle (owner-ruled retired 2026-09-01) |
| 34    | NIIRS not recomputed with off-nadir GSD | OPEN | **CLOSED** | `result.metrics["niirs"]` consumes the two-axis off-nadir GSD (geometric mean internally); the script's residual rescale was retired by CU-340 (2026-09-07) as a double-count |
| 35    | No along-track vs cross-track GSD at off-nadir | OPEN | **CLOSED** | The chain reports the two axes separately — 1.86 m cross vs 2.63 m along at 45° — plus `gsd_geometric_mean_m` for GIQE-5. The script's own along-track column agrees to round-off since the CU-340 projection fix (see below) |
| 36    | No swath width / access geometry calculator | OPEN | **CLOSED** | `performance/{ground_range,swath_width,access_rate}.py` shipped. This run reads `ground_range_m` (527.2 km at 45°, equal to the script's); `swath_width_m` / `access_rate_m2_per_s` stay `None` only because the config sets neither `detector.n_pixels_cross` nor `geometry.ground_speed_m_s` |

### Additional Metrics Now Available (Nadir Baseline)

| Metric | Value | Unit | Notes |
|--------|-------|------|-------|
| NEDT | 64.0 | mK | Noise-equivalent delta temperature |
| NIIRS | 5.43 | -- | GIQE-5, extrapolated (see banner); nadir point of the sweep |
| GSD (RADIANT) | 1.37 | m | Nadir, cross-track |
| Q (center) | 0.844 | -- | Slightly undersampled |
| Q (min/max) | 0.562 / 1.125 | -- | Over band |
| Strehl | 0.9065 | -- | Near diffraction-limited |
| RER | 0.5372 | -- | Relative edge response |
| EE(1x1) | 0.3634 | -- | |
| Well margin | 26.9 | dB | |
| Dynamic range | 62.4 | dB | |
| Folded MTF@Ny | 0.4544 | -- | ≈ 2× the pre-sampling MTF at Nyquist; alias fraction 0.5000 |
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
| Signal shot | 60.14 |
| Dark shot | 0.12 |
| Read noise | 6.00 |
| Quantization | 1.44 |
| Nearfield shot | 0.00 |

*Signal shot refreshed 2026-09-01 from the unmodified runner: 57.81 → 60.14 e⁻,
tracking `signal_shot ∝ √signal` with the SNR (57.5 → 59.8) the sweep table below
records under **CU-336**. The three signal-independent terms are untouched, which
is the check that this is the same radiometric mover and nothing detector-side.
The 2026-08-31 refresh before it caught the table up on **CU-335**
(86.98 → 57.81 e⁻), which that sweep had missed.*

Note: there is **no separate background_shot term** — this extended scene is one
radiance field, so its shot noise is `signal_shot` alone (ADR-0002 Decision #13).
Removing the (previously equal) background term is what raises the absolute SNR
versus older baselines. Nearfield = 0 in scalar transmission mode (lumped refractive
element has emissivity = 0 by Kirchhoff's law).

### Geometry Reference Table

*Along-track column corrected 2026-09-07 (**CU-340**): the script's projection
re-read the swept target-side angle as a sensor-side η before dividing —
dividing by cos 50.7° instead of cos 45° at the sweep end. The corrected column
matches the chain's `gsd_along_track_m` digit for digit (see the cross-check
section below). Cross-track, slant range, air mass, and ground range are
bit-identical.*

| Angle [deg] | Slant Range [km] | Air Mass | Ground Range [km] | GSD Cross [m] | GSD Along [m] |
|-------------|------------------|----------|-------------------|---------------|---------------|
| 0           | 600.0            | 1.0000   | 0.0               | 1.37          | 1.37          |
| 5           | 602.1            | 1.0035   | 48.0              | 1.38          | 1.38          |
| 10          | 608.4            | 1.0141   | 96.6              | 1.39          | 1.41          |
| 15          | 619.3            | 1.0321   | 146.5             | 1.42          | 1.47          |
| 20          | 634.9            | 1.0582   | 198.5             | 1.45          | 1.54          |
| 25          | 655.9            | 1.0932   | 253.4             | 1.50          | 1.65          |
| 30          | 683.2            | 1.1386   | 312.3             | 1.56          | 1.80          |
| 35          | 717.6            | 1.1960   | 376.4             | 1.64          | 2.00          |
| 40          | 760.8            | 1.2680   | 447.3             | 1.74          | 2.27          |
| 45          | 814.8            | 1.3580   | 527.2             | 1.86          | 2.63          |

**Along-track GSD diverges from cross-track** because of the ground projection
foreshortening.  At 45 deg off-nadir, cross-track GSD is 1.86 m (+36%) but
along-track GSD is 2.63 m (+92%).

### Performance Sweep

*Columns `GSD GM`, `NIIRS`, and `dNIIRS` refreshed 2026-09-07. Sole mover:
**CU-340**, in two parts. (1) The script's along-track projection corrected
(above), so the geometric mean shrinks off-nadir (2.34 → 2.21 m at 45°).
(2) The script's residual NIIRS rescale is **retired**: it subtracted
−3.32·log₁₀(GM/cross) from the chain's NIIRS, but the chain's GIQE-5 has
consumed the two-axis GSD (geometric mean internally) since Gap 34/35 closed —
the rescale was double-counting the along/cross ratio (−0.25 NIIRS at 45°).
The NIIRS column is now the chain's `metrics["niirs"]` directly, and the 45°
penalty reads −0.57 (was −0.90: −0.08 from the projection fix, −0.25 from the
double-count). The chain-side columns (τ, SNR, NEDT) are bit-identical —
nothing in the chain moved.*

*Prior vintage, 2026-09-01, refreshed from the unmodified runner (previous vintage
2026-08-30). Sole mover: **CU-336** — the same fit's grid convention was
corrected. `floor_add` had been subtracting a non-water reference measured on a
uniform-λ grid from a ladder optical depth measured on MODTRAN's wavenumber
grid, so the CU-335 floors came out high; corrected they read 0.1375 and 0.0402.
Nadir band-mean τ on this 450–900 nm band rises 0.6488 → 0.6594 (+1.6 %),
**SNR rises ~4 %** (nadir 57.5 → 59.8), NEDT falls with it (66.0 → 64.0 mK) and
NIIRS follows through the GIQE-5 SNR term (5.32 → 5.35 at nadir, 4.42 → 4.45 at
45°). The geometry columns (slant range, air mass, ground range, GSD) are
bit-identical. Both structural conclusions hold: SNR still *rises* with
off-nadir angle (59.8 → 71.6, +19.8 %) because the growing ground footprint
outruns the path loss, and the NIIRS penalty at 45° is still −0.90.*

*Prior vintage, 2026-08-30. **CU-335** put those two floors on the table for the
first time (0.1597 / 0.0517, against a pre-CU-253 Rayleigh ~8× too large that
had clamped them to zero): nadir τ fell 0.7243 → 0.6488 (−10.4 %), SNR ~34 %
(86.8 → 57.5), NEDT rose 46.5 → 66.0 mK and NIIRS 5.60 → 5.32 at nadir.*

*Prior vintage, for the trend: the 2026-08-02 refresh was dominated by CU-253
(nadir τ 0.4903 → 0.7243, SNR −27 %) with CU-267 −0.12 % underneath.*

| Angle [deg] | Tau (mean) | SNR   | GSD GM [m] | NIIRS | NEDT [mK] | dNIIRS |
|-------------|------------|-------|------------|-------|-----------|--------|
| 0           | 0.6594     | 59.8  | 1.37       | 5.43  | 64.0      | 0.00   |
| 5           | 0.6583     | 61.1  | 1.38       | 5.43  | 62.7      | +0.01  |
| 10          | 0.6552     | 62.5  | 1.40       | 5.42  | 61.3      | -0.00  |
| 15          | 0.6500     | 63.8  | 1.44       | 5.40  | 60.1      | -0.03  |
| 20          | 0.6424     | 65.1  | 1.50       | 5.36  | 58.9      | -0.07  |
| 25          | 0.6322     | 66.4  | 1.57       | 5.30  | 57.8      | -0.13  |
| 30          | 0.6192     | 67.7  | 1.68       | 5.22  | 56.7      | -0.21  |
| 35          | 0.6029     | 69.0  | 1.81       | 5.12  | 55.6      | -0.31  |
| 40          | 0.5828     | 70.3  | 1.99       | 5.00  | 54.6      | -0.43  |
| 45          | 0.5581     | 71.6  | 2.21       | 4.86  | 53.6      | -0.57  |

*NIIRS column refreshed 2026-09-12 (chartered sweep). Sole mover: **CU-355**
— a uniform +0.08 level shift through the GIQE-5 RER term (the scalar-WFE
screen became the deterministic low-order expansion). Every dNIIRS, and
every other column, is unchanged — the agility trade itself did not move.*

### RADIANT GSD vs. True Off-Nadir GSD

*Table refreshed 2026-09-01 from the unmodified runner, under an owner ruling that
also retires this section's finding. The previous vintage read RADIANT GSD
1.47/1.53/1.61/1.71/1.85/2.04 m at 20–45° with a "+9.6 % at 45 deg" overestimate;
those numbers are gone, not merely re-rounded.*

*Table widened 2026-09-07 (**CU-340**): the cross-check now runs on both axes —
the script's corrected along-track projection against the chain's
`gsd_along_track_m` — and both agree to double-precision round-off at every
angle.*

| Angle [deg] | RADIANT GSD_x [m] | True Cross [m] | Err_x [%] | RADIANT GSD_y [m] | True Along [m] | Err_y [%] |
|-------------|-------------------|----------------|-----------|-------------------|----------------|-----------|
| 0           | 1.37              | 1.37           | +0.0      | 1.37              | 1.37           | +0.0      |
| 5           | 1.38              | 1.38           | +0.0      | 1.38              | 1.38           | +0.0      |
| 10          | 1.39              | 1.39           | +0.0      | 1.41              | 1.41           | +0.0      |
| 15          | 1.42              | 1.42           | +0.0      | 1.47              | 1.47           | +0.0      |
| 20          | 1.45              | 1.45           | +0.0      | 1.54              | 1.54           | +0.0      |
| 25          | 1.50              | 1.50           | +0.0      | 1.65              | 1.65           | +0.0      |
| 30          | 1.56              | 1.56           | +0.0      | 1.80              | 1.80           | +0.0      |
| 35          | 1.64              | 1.64           | +0.0      | 2.00              | 2.00           | +0.0      |
| 40          | 1.74              | 1.74           | +0.0      | 2.27              | 2.27           | +0.0      |
| 45          | 1.86              | 1.86           | +0.0      | 2.63              | 2.63           | +0.0      |

**The finding this section used to carry is retired: RADIANT's `gsd_cross_track_m`
now tracks true cross-track GSD exactly.** The "error" column is not a rounded
agreement — at full precision the worst residual across the sweep is
1.4 × 10⁻¹³ %, i.e. the two are the same float to within double-precision
round-off. (The runner's `%+.1f` formatting prints `-0.0` at 20° and 40°, which is
the sign of a −1.4 × 10⁻¹³ % residual, not a real deficit.) That is expected once
you see *why*: the script's own `slant_range_spherical()` and RADIANT's
`core.viewing_triangle` are the same law-of-cosines solution of the same triangle
on the same R_E = 6371 km, both referencing the swept zenith to the path's **lower**
endpoint — the ground target. Two independent implementations of one geometry, so
exact agreement is the correct result, and the cross-check now earns its keep as a
regression guard rather than as a workaround.

**Attribution.** The retired discrepancy was not a rounding drift; it was a
convention error with a signature. The old column is reproduced *digit for digit*
by `p · R(η) / f`, where `R(η)` is the ray-sphere slant range for the swept angle
read as the **sensor-side** off-nadir angle η (1.3714, 1.3772, 1.3946, 1.4246,
1.4687, 1.5290, 1.6093, 1.7148, 1.8540, **2.0409** m) — exactly the θ_o-vs-η
misread that **CU-096 / CU-097** identified. It was closed by
`65720f0d` (2026-07-12), *"downstream stages consume published geometry
(ADR-0006, Phase 2)"*, in which PerformanceStage stopped re-deriving geometry from
`geometry.path_zenith_rad` misread as η and began consuming the slant range and
incidence angle GeometryStage publishes from the canonical target-side θ_o. The
CHANGELOG entry for that landing is flagged *"Results-affecting (off-nadir
configurations only)"* and predicted precisely this: values that scale with slant
range shrink off-nadir. This walkthrough simply was not re-run against it.

**The script-side along-track residue is fixed too (CU-340, 2026-09-07).** Gap 35
is **closed**: the chain reports `gsd_cross_track_m` and `gsd_along_track_m`
separately, and at 45° they read 1.86 m and 2.63 m. The script's `True Along`
column used to disagree (2.94 m at 45°, ≈ 12 % pessimistic) because
`gsd_off_nadir()` carried the same θ_o-vs-η convention split diagnosed above on
its along-track branch: it re-read the swept 45° as a sensor-side η, converted it
to an incidence angle of 50.7° via the sine rule, and divided by cos 50.7° — the
one conversion too many that `65720f0d` removed from the chain. CU-340 deleted
that conversion (the swept angle *is* the path zenith angle at the target, hence
the incidence angle), so the script now divides by cos θ_o and lands on the
chain's value to double-precision round-off. The same commit retired the
script's residual NIIRS rescale, which had been double-counting the
along/cross ratio against a chain GIQE-5 that already consumes the geometric
mean (see the Performance Sweep note); the previous vintage's GM 2.34 m and
dNIIRS −0.90 at 45° now read 2.21 m and −0.57, and the two-axis table above is
a live regression guard on both conventions.

## Physics Discussion

### Why SNR Increases with Off-Nadir Angle

A surprising result: SNR *increases* from 59.8 at nadir to 71.6 at 45 deg.
This is counterintuitive but physically correct.  The mechanism:

1. **Atmospheric transmission decreases** (-15.9% at 45 deg) → fewer target photons
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

NIIRS degrades by -0.57 from nadir to 45 deg.  This is primarily from GSD:

- GSD scaling: dNIIRS = -3.32 × log10(GSD_GM_45/GSD_nadir) = -3.32 × log10(2.21/1.37) = -0.69
- The actual degradation (-0.57) is smaller than the pure geometric-mean GSD
  term because SNR *rises* off-nadir (+19.8% at 45°, the veiling effect above)
  and partially offsets the GSD loss through GIQE-5's SNR term.

The along-track vs cross-track GSD divergence is significant.  At 45 deg:
- Cross-track: 1.86 m (+36%) — scales as slant_range / focal_length
- Along-track: 2.63 m (+92%) — additional cos(theta) ground-projection factor at the target

This asymmetry means the ground sample is rectangular (not square) at off-nadir,
which degrades along-track resolution disproportionately.

### Atmospheric Transmission

Band-mean transmission drops from 0.6488 at nadir to 0.5455 at 45 deg (-15.9%).  The
physics:

- Air mass = sec(theta) at 45 deg = 1.414 (flat-Earth) → 1.358 (spherical)
- τ(45 deg) ≈ τ(nadir)^(air_mass) = 0.6488^1.358 ≈ 0.556, against the 0.546 the
  chain reports — the small shortfall is the band-mean of a λ-dependent τ not being
  exactly the band-mean τ raised to the air mass
- This is consistent with Beer-Lambert exponential absorption

For MWIR bands, the transmission decrease would be more severe due to stronger
H₂O and CO₂ absorption at longer wavelengths.

### Access vs. Quality Trade

The fundamental trade in agile pointing:

*Table refreshed 2026-09-07 — it had been carrying a pre-CU-336 vintage
(nadir NIIRS 5.32, NEDT 66.0 mK) that two sweep-table refreshes above it had
already replaced, plus the CU-340 GM/NIIRS movements of this refresh.*

| Angle [deg] | Ground Range [km] | GSD GM [m] | NIIRS | NEDT [mK] | Access Rate [km^2/s] |
|-------------|-------------------|------------|-------|-----------|----------------------|
| 0           | 0                 | 1.37       | 5.35  | 64.0      | 114                  |
| 30          | 312               | 1.68       | 5.14  | 56.7      | 129                  |
| 45          | 527               | 2.21       | 4.78  | 53.6      | 154                  |

At 45 deg off-nadir, Raj can image a target 527 km from nadir ground track,
but at the cost of -0.57 NIIRS.  Whether this trade is acceptable depends on
the mission's minimum NIIRS requirement.

## Real-MODTRAN validation note (added 2026-07-17)

> **Simple τ column refreshed 2026-08-02; verdict reversed.** The `Real MODTRAN τ`
> column is measured data from the 2026-07-17 staged run set and does not move. The
> `Simple τ` column is re-read from the current runner, and after **CU-253** (the
> 8×-too-large VIS/NIR molecular optical depth, landed 2026-07-28) the parametric
> model is no longer the more absorbing of the two — the sign of the disagreement
> has flipped, so the two findings below are restated accordingly. The 60° row has
> no refreshed Simple value: this scenario's sweep stops at 45°.

The real MODTRAN 6 zenith fan (A1/B1/B2/B3, us_standard, 2026-07-17 run
set) now pins this scenario's atmospheric component. Band-mean total
transmittance in the pan band (0.45–0.90 µm), 100 km nadir column:

| Off-nadir | Real MODTRAN τ [-] | Simple τ [-] | Real τ(θ)/τ(0) | Simple ratio | Ratio error |
|---|---|---|---|---|---|
| 0° | 0.668 | 0.6488 | 1.000 | 1.000 | — |
| 30° | 0.628 | 0.6078 | 0.940 | 0.9368 | −0.3% |
| 45° | 0.565 | 0.5455 | 0.845 | 0.8408 | −0.5% |
| 60° | 0.440 | (not swept) | 0.659 | — | — |

Two findings:

- **The real atmosphere follows textbook Beer–airmass scaling almost
  exactly in this band**: exp(−OD₀·(sec 45° − 1)) predicts 0.846 vs the
  measured 0.845 ratio. The physics this scenario assumed for the
  angular trade is correct. (Unchanged — this row is measured data.)
- **SimpleAtmosphere's absolute pan-band optical depth is now within 8 % of
  the measurement** (τ₀ 0.6488 vs 0.668 measured, i.e. OD 0.433 vs 0.403) —
  the CU-335 re-fit closed most of what remained. Before CU-253 this note
  recorded the model ~1.9× too *absorbing*; between CU-253 and CU-335 it
  swung to ~20 % too *transmissive* (τ₀ 0.7243); it now sits 8 % too
  absorbing, the smallest residual this row has carried. The angular
  *ratio* agrees to better than 0.5 % at both swept angles, so the
  scenario's off-nadir penalty is now essentially unbiased where it used to
  be overstated by ~4 %. The geometry conclusions (GSD foreshortening,
  along/cross asymmetry, access-radius trade) are unaffected — they contain
  no atmosphere. Raj's qualitative answer ("still useful at 45°") holds.

Numbers were not re-baselined into the tables above (the scenario
deliberately demonstrates the parametric-model workflow); this note is
the accuracy context. Validation source:
`tests/integration/test_modtran_real_runs.py` (airmass fan) and the
comparison script in the session record for commit-linked provenance.

## Gaps Identified

| Gap # | Description | Status | Impact |
|-------|-------------|--------|--------|
| 33    | GSD not adjusted for off-nadir angle | **CLOSED** (verified on this scenario 2026-09-01) | None. `gsd_cross_track_m` equals this scenario's independent spherical-Earth cross-track GSD to 1.4e-13 % across 0–45°; closed by `65720f0d` (CU-096/CU-097, ADR-0006 Phase 2) |
| 34    | NIIRS not recomputed with off-nadir GSD | **CLOSED** (verified on this scenario 2026-09-01) | None. `result.metrics["niirs"]` reads the two-axis off-nadir GSD; the script's remaining rescale was retired by CU-340 (2026-09-07) as a double-count against the chain's internal geometric mean |
| 35    | No along-track vs cross-track GSD at off-nadir | **CLOSED** (verified on this scenario 2026-09-01) | None chain-side. `gsd_cross_track_m` and `gsd_along_track_m` are distinct off-nadir (1.86 / 2.63 m at 45°) and `gsd_geometric_mean_m` feeds GIQE-5. The script's own along-track projection carried a θ_o-vs-η convention issue until CU-340 (2026-09-07); both axes now cross-check to round-off |
| 36    | No swath width / access geometry calculator | **CLOSED** (verified on this scenario 2026-09-01) | None. The chain computes `ground_range_m` and matches this script's 527.2 km at 45°; `swath_width_m` and `access_rate_m2_per_s` require `detector.n_pixels_cross` and `geometry.ground_speed_m_s`, which this config does not set, so the script still computes them locally |

**Newly closed gaps (metrics now available):**
- NEDT is now available via `result.metrics["nedt_K"]` -- 64.0 mK at nadir
- NIIRS is now available via `result.metrics["niirs"]` -- 5.32 at nadir
- GSD is now available via `result.metrics["gsd_cross_track_m"]` -- 1.37 m at nadir
- Q is now available via `result.metrics["q_center"]` -- 0.844
- Strehl is now available via `result.metrics["strehl"]` -- 0.9065
- RER is now available via `result.metrics["rer"]` -- 0.5372
- MTF budget is now available via `result.stage_outputs["performance"]["mtf_budget"]`
- Well margin is now available via `result.metrics["well_margin_dB"]` -- 27.6 dB
- Folded MTF is now available via `result.metrics["mtf_folded_at_nyquist"]` -- 0.4544, with
  `alias_fraction_at_nyquist` = 0.5000. Sampling replicates the pre-sampling spectrum at the
  sampling frequency `f_s = 2 × f_Nyquist` (CU-209), so at Nyquist the `k = -1` replica lands
  back on `f_Nyquist` and the folded value is twice the pre-sampling MTF there — half of the
  apparent response at Nyquist is aliased content, which is what the 0.5 alias fraction says.

## Outputs

- `outputs/off_nadir_results.xlsx` — Full sweep results
- `outputs/fig1_snr_transmission_vs_angle.png` — SNR and transmission vs. angle
- `outputs/fig2_gsd_vs_angle.png` — GSD (cross, along, GM) vs. angle
- `outputs/fig3_niirs_vs_angle.png` — NIIRS vs. angle (chain metric)
- `outputs/fig4_summary_panels.png` — Four-panel summary

## What Raj Would Do Next

1. **Set minimum NIIRS requirement** (e.g., NIIRS >= 5.0 for his mission) and
   determine the maximum off-nadir angle that meets it (~55-60 deg based on
   extrapolation)
2. **Evaluate contrast SNR** (not just total SNR) for target detection scenarios
   at off-nadir angles — the atmospheric veiling effect reduces contrast
3. **Compare MWIR performance at off-nadir** — MWIR has stronger atmospheric
   absorption, so the transmission penalty at off-nadir would be more severe
4. ~~Drop the manual GSD correction entirely~~ **Done (CU-340, 2026-09-07)** —
   the NIIRS column now reads `metrics["niirs"]` directly and the script's
   along-track projection is corrected, kept only as a two-axis cross-check
   against `gsd_cross_track_m` / `gsd_along_track_m`
5. **Wire up the access metrics** — set `detector.n_pixels_cross` and
   `geometry.ground_speed_m_s` and the chain returns `swath_width_m` and
   `access_rate_m2_per_s` directly (Gap 36), replacing the script's local versions

**Postscript (2026-07-18):** CU-161 (commit `0aebdda`) recalibrated the gas/water optical depths; the absolute-OD excess noted above is reduced in the IR bands (VIS aerosol untouched). Committed numbers reflect the pre-fix model.
