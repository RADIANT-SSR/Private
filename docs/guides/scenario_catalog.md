# RADIANT Scenario Catalog — Persona-Driven Test Cases

**Date:** 2026-04-15
**Purpose:** 35 realistic usage scenarios (5 per persona) designed to stress-test
RADIANT, reveal gaps, and guide prioritization of improvements.

---

## Recommended Execution Order

Ordered by number of modules touched. Earlier scenarios build capabilities
that unlock later ones.

### Tier 1 — Executable today with scripting only (0 code changes)

These scenarios can be run with the current API by writing Python scripts
that combine existing capabilities.

| Priority | Scenario | Persona | Why first |
|----------|----------|---------|-----------|
| 1 | 6.3 | Dr. Chen | Verify noise model against hand calcs. All 16 noise terms already output. Pure validation. |
| 2 | 2.3 | Mike | Sweep ipc_coupling (exists). Compose with existing MTF/EE outputs. |
| 3 | 7.4 | Karen | Sweep cold_stop_efficiency (exists). Compare background signal. |
| 4 | 5.2 | Tom | Sweep pixel pitch. Q = λf/#/p is a trivial computation on existing outputs. |
| 5 | 5.3 | Tom | Polychromatic PSF already implemented. Script to compare mono vs. poly. |

### Tier 2 — Need 1-2 metric additions (performance stage only)

These scenarios are unlocked by adding NEDT, NIIRS, GSD, Strehl, and
full MTF curve to `result.metrics` or `result.stage_outputs`. All changes
are in `src/radiant/performance/` — no signal chain modifications.

| Priority | Scenario | Persona | New metric needed |
|----------|----------|---------|-------------------|
| 6 | 7.1 | Karen | NEDT (+ lab/exo atmosphere mode, which already exists) |
| 7 | 2.2 | Mike | NEDT, noise breakdown vs. frame rate |
| 8 | 2.5 | Mike | Well fill fraction (trivial: signal_e / FWC) |
| 9 | 3.2 | Raj | NIIRS (GIQE-5 code exists, just not surfaced), GSD |
| 10 | 5.4 | Tom | NIIRS, jitter sweep (platform params may need additions) |
| 11 | 1.4 | Sarah | NIIRS, saturation check, TDI sweep (n_tdi exists) |
| 12 | 5.1 | Tom | Strehl ratio, full MTF curve, field-dependent WFE |
| 13 | 7.3 | Karen | Full MTF curve export, defocus model |
| 14 | 3.4 | Raj | GSD (along/cross-track), NIIRS, off-nadir geometry |

### Tier 3 — Need input parsers / format converters (io/ module only)

These scenarios require reading data from non-RADIANT formats. Changes
concentrated in `src/radiant/io/` — no physics modifications.

| Priority | Scenario | Persona | Parser needed |
|----------|----------|---------|---------------|
| 15 | 2.1 | Mike | QE CSV (nm/pct → µm/frac), J_dark CSV (A/cm² → e⁻/s) |
| 16 | 6.2 | Dr. Chen | MODTRAN tape7 (wavenumber), libRadtran (nm/mW) |
| 17 | 1.1 | Sarah | MODTRAN tape7, ocean emissivity model |
| 18 | 4.1 | Lisa | Excel target library, batch scenario matrix |
| 19 | 7.2 | Karen | Lab calibration CSV, DN output |
| 20 | 1.3 | Sarah | ASTER spectral library, Excel detector specs |
| 21 | 4.3 | Lisa | Spectral emissivity input (curve, not scalar) |
| 22 | 7.5 | Karen | Measured J(T) curve, QE(T) table |

### Tier 4 — Need new models or capabilities (new modules)

These require new physics models, analysis modes, or architectural
additions beyond metric reporting and I/O.

| Priority | Scenario | Persona | New capability |
|----------|----------|---------|----------------|
| 23 | 1.2 | Sarah | Solar geometry calculator (LTAN/date/lat → zenith) |
| 24 | 3.1 | Raj | Orbit → geometry calculator, pass planning |
| 25 | 4.4 | Lisa | Time-varying scenario (diurnal temperature sweep) |
| 26 | 4.2 | Lisa | Johnson criteria / DRI range model |
| 27 | 1.5 | Sarah | Arbitrary pupil mask (spider vanes), Strehl |
| 28 | 4.5 | Lisa | Microbolometer noise model (NETD-specified) |
| 29 | 3.3 | Raj | Multi-sensor comparison framework, compliance matrix |
| 30 | 6.1 | Dr. Chen | D* / NETD / NEP → component noise converters |
| 31 | 2.4 | Mike | Multi-frame persistence model (temporal sequence) |
| 32 | 6.5 | Dr. Chen | Temperature retrieval (inverse), Jacobian |
| 33 | 6.4 | Dr. Chen | Multi-target scene, per-pixel simulation, ROC curve |
| 34 | 3.5 | Raj | Tropical atmosphere, GeoTIFF reader, MRT metric |
| 35 | 1.3 | Sarah | Detection probability model, dual-band comparison |

### Key metric additions and how many scenarios they unlock

| Metric / Feature | Scenarios unlocked | Effort |
|------------------|--------------------|--------|
| **NEDT** | 7.1, 7.4, 7.5, 2.2, 2.5, 3.5, 4.5, 6.5, 1.1, 1.3 (10) | Small — σ/∂L/∂T |
| **NIIRS** (surface GIQE-5) | 3.1, 3.2, 3.4, 5.1, 5.4, 1.1, 1.2, 1.4, 4.1, 4.2, 4.5 (11) | Small — code exists |
| **GSD** | 3.2, 3.4, 1.2, 4.5 (4) | Trivial — p×h/f |
| **Full MTF curve** | 5.1, 5.2, 5.3, 7.3 (4) | Medium — array output |
| **Strehl ratio** | 5.1, 1.5 (2) | Trivial — max(PSF)/max(Airy) |
| **Detection range** | 1.1, 4.1, 4.2, 4.3 (4) | Medium — range-SNR solver |
| **Lab/exo mode docs** | 7.1, 7.2, 2.1, 2.2 (4) | Zero — already exists |

---

## Persona 1: Sarah — Systems Engineer

### Scenario 1.1: MWIR Maritime Surveillance Trade Study

**Context**: Sarah is on a proposal team designing a ship-detection sensor
for a 500 km SSO. The customer wants to detect a 30 m fishing vessel (steel
hull, partially rusted) against open ocean background at 20 deg off-nadir.

**Inputs she has**:
- A vendor spec sheet for an InSb FPA (PDF with QE curve as a graph, not
  data points — she'll need to digitize it)
- Ship hull emissivity: "about 0.7-0.85 depending on paint" — she has no
  spectral curve, just a range
- Ocean background: she knows it's ~0.98 emissivity, ~288 K, but she needs
  wind-state-dependent emissivity (calm vs. sea state 3)
- Atmosphere: a MODTRAN tape7 file from a colleague — it's in wavenumber
  (cm-1), not wavelength
- Aperture range: 15-45 cm (customer constraint), f/2.5 (fast optics)
- Pixel pitch: 15 um InSb, 640x512 array

**Desired outputs**:
- SNR vs. aperture diameter at 20 deg off-nadir
- Minimum detectable target delta-T (i.e., NEDT) vs. aperture
- Detection range (km) at SNR=5 threshold
- NIIRS vs. aperture
- A summary table for a PowerPoint slide deck

**Gaps revealed**:
- No MODTRAN tape7 parser for wavenumber-domain data
- No wind-state-dependent ocean emissivity model
- No NEDT in result.metrics
- No detection range calculator
- No NIIRS in result.metrics (GIQE-5 exists but isn't surfaced)
- No PowerPoint/table export format

---

### Scenario 1.2: VNIR Pan-sharpened Imager — GSD vs. Aperture vs. Altitude

**Context**: Sarah is designing a commercial Earth observation satellite. She
needs to hit 0.5 m GSD in panchromatic (450-700 nm) from a sun-synchronous
orbit. The constraint space is aperture (20-80 cm), altitude (400-600 km),
and focal length (derived from GSD requirement).

**Inputs she has**:
- Silicon CCD QE curve from a datasheet (JPEG plot — needs digitization)
- Solar illumination geometry: she knows the orbit's LTAN is 10:30 AM but
  doesn't know how to convert that to solar zenith angle for her target
  latitude
- She wants to evaluate at 4 different seasons to check lighting variation

**Desired outputs**:
- 2D contour plot: SNR as function of aperture and altitude, with GSD
  contour overlay
- GSD as function of altitude and focal length
- MTF at Nyquist vs. aperture
- Diffraction-limited GSD — smallest GSD regardless of pixel pitch
- Indication of whether system is diffraction-limited or detector-limited

**Gaps revealed**:
- No solar geometry calculator (LTAN/date/latitude to solar zenith)
- No GSD in result.metrics
- No diffraction-limited resolution metric
- No "detector-limited vs. diffraction-limited" regime indicator
- No contour plot with overlaid constraint lines

---

### Scenario 1.3: Dual-Band MWIR/LWIR Sensor Comparison

**Context**: Sarah needs to decide between MWIR (3.5-5.0 um) and LWIR
(8-12 um) for a wildfire detection mission at 10 km altitude (airborne).
The target is a 5 m^2 hotspot at 600 K against a 300 K forest background.

**Inputs she has**:
- Two detector options: HgCdTe MWIR (cutoff 5.0 um) and HgCdTe LWIR
  (cutoff 12 um) — vendor datasheets with noise specs at different operating
  temperatures in an Excel comparison table, not YAML
- Forest emissivity: an ASTER spectral library CSV with non-RADIANT column
  headers
- Hotspot emissivity: unsure — partially burning vegetation, partially
  exposed soil

**Desired outputs**:
- Side-by-side comparison: SNR, contrast SNR, NEDT for both bands
- Target-to-background contrast (delta-L) in each band, spectral
- Optimal band recommendation based on contrast and noise
- Noise budget comparison between the two bands
- Fire detection probability at different hotspot temperatures (400-1200 K)

**Gaps revealed**:
- No multi-band comparison workflow
- No delta-L (spectral contrast) output
- No detection probability model
- No ASTER spectral library importer
- No Excel-to-YAML converter for detector specs

---

### Scenario 1.4: TDI Pushbroom Design — Line Rate vs. SNR

**Context**: Sarah is designing a pushbroom MWIR sensor for a 500 km LEO
orbit. Ground velocity sets the maximum integration time per TDI line. She
needs to find the optimal number of TDI stages (8, 16, 32, 64, 128).

**Inputs she has**:
- Orbital velocity: 7.5 km/s — she needs to convert to ground velocity and
  then to max integration time per line given pixel pitch and focal length
- Target well depth of 250,000 e- and worries about saturation at high
  TDI counts

**Desired outputs**:
- SNR vs. TDI stages (integration time constrained by ground velocity)
- Saturation check: at what TDI count does signal exceed full-well?
- MTF at Nyquist vs. TDI (alignment error degrades MTF)
- Along-track smear MTF as function of TDI count
- NIIRS vs. TDI count — optimal number where NIIRS peaks

**Gaps revealed**:
- No orbital velocity to integration time calculator
- No automatic saturation/well-fill warning in sweep outputs
- No TDI alignment MTF model
- No NIIRS vs. TDI sweep output

---

### Scenario 1.5: Obscured Aperture — Three-Mirror Anastigmat with Spider Vanes

**Context**: Sarah is evaluating a Cassegrain variant with 33% linear central
obscuration and 4-vane spider support structure. She wants to understand how
obscuration and spiders affect PSF, EE, and MTF vs. a clear aperture.

**Inputs she has**:
- Aperture: 40 cm diameter, 13.2 cm secondary (33% linear obscuration)
- Spider vanes: 4 vanes, each 3 mm wide — she doesn't have a pupil mask
  file, just these dimensions
- Wants to compare: clear aperture, obscured-only, and obscured+spiders

**Desired outputs**:
- 2D PSF images for all three pupil configurations
- EE vs. box size for all three
- MTF curves (x, y, and 45 deg for spider case) for all three
- Diffraction spike intensity and angular extent from spider vanes
- Strehl ratio for each configuration

**Gaps revealed**:
- No spider vane support in pupil model (only circular obscuration)
- No arbitrary pupil mask input (FITS/PNG/array)
- No Strehl ratio in result.metrics
- No off-axis MTF (only x/y, not arbitrary angle)
- No PSF comparison/overlay mode

---

## Persona 2: Mike — Detector Engineer

### Scenario 2.1: InSb vs. HgCdTe Noise Budget Shootout at 77 K

**Context**: Mike is choosing between InSb and HgCdTe MWIR detectors for a
space mission. He has measured dark current vs. temperature data for both from
the vendor (CSV files with columns: T_K, Jdark_A_cm2). He needs to convert
from current density to e-/s using pixel area.

**Inputs he has**:
- InSb: measured J_dark(T) CSV, QE(lambda) CSV from vendor (columns:
  wavelength_nm, QE_pct — note nm and percent, not um and fraction)
- HgCdTe: same format but different columns (lambda_um, quantum_efficiency)
- Both: read noise = 18 e- (InSb) vs. 12 e- (HgCdTe)
- ROIC: 33 fF node cap, CDS mode, 5 e-/s glow
- Does NOT want atmosphere or target — flat 300 K blackbody filling aperture

**Desired outputs**:
- Side-by-side noise budget tables (all 16 terms for each detector)
- Dark current crossover temperature — at what T does dark current equal
  read noise?
- BLIP temperature — at what T is detector background-limited?
- Noise equivalent irradiance (NEI)
- Dark current vs. temperature curve for both detectors

**Gaps revealed**:
- No J_dark(T) CSV importer (A/cm^2 to e-/s conversion)
- No QE import from nm/percent format
- No BLIP temperature calculation
- No NEI metric
- No dark current crossover temperature finder
- No "detector-only" mode (lab/calibration blackbody source)

---

### Scenario 2.2: 1/f Noise Corner Frequency Impact on LWIR Staring Array

**Context**: Mike has a 640x512 LWIR HgCdTe staring array with known 1/f
noise. The corner frequency is 200 Hz. He needs to evaluate how 1/f noise
impacts NEDT at different frame rates (30, 60, 120 Hz).

**Inputs he has**:
- Measured 1/f noise coefficient K = 2.5e4 (electrons^2)
- Corner frequency: 200 Hz
- Frame rates: 30, 60, 120 Hz -> f_low = 1/t_frame, f_high = 1/(2*t_int)
- Confused about how RADIANT's flicker_f_low_hz and flicker_f_high_hz map
  to frame-rate-dependent calculation

**Desired outputs**:
- 1/f noise contribution (e-) vs. frame rate
- Total noise vs. frame rate with 1/f highlighted
- Noise power spectral density plot
- NEDT vs. frame rate
- Guidance on how f_low and f_high should be set given a frame rate

**Gaps revealed**:
- No NEDT metric
- No noise PSD output
- No frame-rate-aware 1/f bandwidth calculator
- Ambiguity in how flicker parameters map to system timing

---

### Scenario 2.3: IPC Characterization — How Much MTF Loss Can I Tolerate?

**Context**: Mike measured IPC coupling of alpha = 0.02 on his HgCdTe MWIR
detector. He wants to understand impact on MTF and whether IPC correction
in post-processing can recover the loss.

**Inputs he has**:
- Measured IPC alpha = 0.02 (nearest-neighbor coupling fraction)
- Also has a 5x5 IPC kernel from knife-edge test (not just nearest-neighbor)
  — wants to feed the full kernel
- Pixel pitch: 18 um, f/3.0 optics at lambda_center = 4.2 um

**Desired outputs**:
- MTF at Nyquist vs. IPC coupling alpha (sweep 0 to 0.05)
- MTF curve with and without IPC correction applied
- Pixel-level signal redistribution map showing point source spread
- EE(1x1) vs. IPC coupling — at what alpha does EE drop below 50%?
- System MTF decomposition showing IPC contribution isolated

**Gaps revealed**:
- No support for arbitrary IPC kernel (only scalar nearest-neighbor alpha)
- No IPC correction/deconvolution model
- No pixel-level signal redistribution visualization
- No way to isolate a single MTF component in the output

---

### Scenario 2.4: Persistence Characterization — Bright Source Recovery

**Context**: Mike has a Type-II superlattice LWIR detector that exhibits
persistence. After imaging a hot source (800 K calibration body), the
detector shows residual signal for several frames.

**Inputs he has**:
- Measured persistence: 1.5% of signal remains after one frame at 60 Hz
- Decay time constant: tau = 50 ms
- Prior frame signal: 150,000 e- from hot calibration source
- Current frame integration time: 10 ms
- Wants to see persistence noise evolve over 20 frames

**Desired outputs**:
- Persistence noise (e- RMS) vs. frame number after bright exposure
- Residual signal (not just noise) — actual ghost image level in e-
- Number of frames to decay below 1 LSB (= gain_e_per_dn)
- SNR of current scene with and without persistence contamination
- Time-domain persistence model (not just single-frame)

**Gaps revealed**:
- No multi-frame temporal model (only single-frame persistence noise)
- No residual signal calculation (only persistence noise)
- No "frames to clear" metric
- No frame-sequence simulation capability

---

### Scenario 2.5: Well Capacity Optimization — Integration Time vs. Dynamic Range

**Context**: Mike needs to set integration time for a MWIR sensor viewing a
scene with both cold sky (200 K) and hot exhaust plume (1500 K) in the same
frame.

**Inputs he has**:
- Scene dynamic range: 200 K to 1500 K
- Detector: HgCdTe MWIR, 15 um pitch, FWC = 2M e- (large well)
- Optics: f/2.0, D = 20 cm, lambda = 3.5-5.0 um
- Wants to sweep integration time from 0.1 ms to 50 ms

**Desired outputs**:
- Well fill fraction vs. integration time for both 200 K and 1500 K targets
- SNR vs. integration time for cold target (200 K)
- Dynamic range in scene temperature — largest delta-T before saturation
- Integration time that gives well_fill = 70% on hot source
- Dual-target comparison: noise budget hot vs. cold at same integration time

**Gaps revealed**:
- No well fill fraction reported (only well_margin_dB)
- No multi-target-in-same-scene analysis
- No scene dynamic range (in temperature) metric
- No automatic "find integration time for target well fill" solver

---

## Persona 3: Raj — Mission Planner

### Scenario 3.1: ISR Pass Planning — Can We See the Target on This Orbit?

**Context**: Raj has a specific tasking: image a vehicle staging area at
34.5 N, 69.2 E on April 20 at 09:15 local time from a 500 km SSO with
10:30 AM LTAN. He needs NIIRS >= 5 for vehicle identification.

**Inputs he has**:
- Sensor: baselined MWIR config YAML
- Target coordinates and date/time — needs to compute solar zenith, solar
  azimuth, and slant range from the orbit
- TLE for the satellite — wants automatic access geometry
- Atmosphere: midlat_summer, but wants sensitivity to visibility

**Desired outputs**:
- SNR and NIIRS for this specific observation geometry
- Pass/fail traffic light: green if NIIRS >= 5, yellow if 4-5, red if < 4
- Sensitivity table: NIIRS at visibility = {5, 10, 23, 50} km
- Time window: during the pass, at what off-nadir angles is NIIRS >= 5?
- Elevation angle profile during the pass

**Gaps revealed**:
- No TLE/orbit propagation to geometry (no SGP4)
- No lat/lon/date/time to solar angles calculator
- No NIIRS in result.metrics
- No traffic-light/threshold reporting
- No time-varying geometry (pass profile)

---

### Scenario 3.2: Weather Sensitivity — How Bad Can the Weather Get?

**Context**: Raj needs a "go/no-go" weather threshold. At what visibility
does NIIRS drop below the mission requirement (NIIRS >= 4)?

**Inputs he has**:
- Sensor: existing YAML config
- Target: 300 K, emissivity = 0.95, extended scene
- Sweep visibility from 2 km (heavy haze) to 100 km (crystal clear)
- Also check precipitable water vapor (0.5 to 5 cm)

**Desired outputs**:
- NIIRS vs. visibility
- Critical visibility threshold — visibility at which NIIRS = 4.0
- SNR vs. visibility and vs. precipitable water
- 2D contour: NIIRS as function of visibility and water vapor
- Go/no-go table: for each atmosphere condition, is requirement met?

**Gaps revealed**:
- No NIIRS output
- No threshold-crossing finder for arbitrary metrics
- No named atmosphere presets (clear=50km, haze=10km, etc.)
- No fog/cloud model (visibility < ~2 km)

---

### Scenario 3.3: Multi-Sensor Comparison for Procurement

**Context**: Raj is evaluating three competing sensor proposals. Each vendor
provided a spec sheet (PDF) with different parameter formats.

**Inputs he has**:
- Vendor A: 30 cm, f/4, 18 um HgCdTe MWIR, 3.7-4.8 um, QE "typical 70%",
  dark current "< 200 e-/s at 80 K", read noise "< 25 e- CDS"
- Vendor B: 25 cm, f/3, 24 um InSb, 3.0-5.0 um, QE as spectral curve
  (PNG in PDF), dark current at 77 K
- Vendor C: 35 cm, f/5, 10 um pitch, dual-band MWIR/LWIR
- All specs are in PDFs

**Desired outputs**:
- Comparison table: SNR, NIIRS, NEDT, MTF at Nyquist, GSD for all three
- Rank ordering by each metric
- Spider/radar chart showing relative strengths
- Cost-performance trade: which single 10% improvement gives most NIIRS gain?
- Compliance matrix: does each sensor meet each requirement?

**Gaps revealed**:
- No PDF spec sheet parser
- No NEDT, NIIRS, GSD outputs
- No radar/spider chart visualization
- No compliance matrix / requirements-checking mode
- No "which single improvement matters most" analysis

---

### Scenario 3.4: Off-Nadir Performance Degradation

**Context**: Raj needs to understand how performance degrades as look angle
increases from nadir to 45 deg off-nadir from a 600 km LEO.

**Inputs he has**:
- Sensor: existing YAML config
- Off-nadir angles: 0 to 45 deg in 5 deg steps
- Needs to compute slant range and atmospheric path length (accounting for
  Earth curvature at large angles)

**Desired outputs**:
- SNR vs. off-nadir angle
- GSD vs. off-nadir angle (along-track and cross-track diverge)
- NIIRS vs. off-nadir angle
- Atmospheric transmission vs. off-nadir angle
- Swath width vs. off-nadir angle

**Gaps revealed**:
- No off-nadir to slant range calculator (with Earth curvature)
- No along-track vs. cross-track GSD distinction
- No atmospheric path length calculation from zenith angle
- No swath width calculation
- No NIIRS output

---

### Scenario 3.5: Nighttime MWIR Imaging Feasibility

**Context**: Raj needs to know if the MWIR sensor can achieve useful imagery
at night. Target is a building complex at 295 K against 288 K background.

**Inputs he has**:
- Sensor: existing MWIR config
- Atmosphere: "tropical" standard atmosphere — RADIANT may not have this
- Unsure whether "no solar illumination" changes anything in MWIR
- Background temperature from a NOAA land surface temperature map (GeoTIFF)

**Desired outputs**:
- SNR and contrast SNR for the 7 K delta-T scene
- NEDT — is 7 K detectable given system NEDT?
- Minimum resolvable delta-T for this configuration
- Confirmation that MWIR performance is solar-independent
- Comparison: same scenario in LWIR (8-12 um)

**Gaps revealed**:
- No "tropical" standard atmosphere preset
- No GeoTIFF reader for surface temperature maps
- No NEDT output
- No minimum resolvable temperature difference (MRT) metric
- No solar-dependence analysis mode

---

## Persona 4: Lisa — Detection/Targeting Analyst

### Scenario 4.1: Target Detection Matrix — 12 Targets x 4 Atmospheres x 3 Sensors

**Context**: Lisa needs a quarterly program review briefing showing detection
range for a target set across atmospheric conditions.

**Inputs she has**:
- Target library (Excel): columns target_name, length_m, width_m, height_m,
  temperature_K, emissivity, material. 12 rows. Needs projected_area_m2 =
  length x width computed.
- Sensor library: 3 YAML configs (may have outdated parameter names)
- Atmosphere conditions: "clear" (vis=50 km), "haze" (vis=10 km),
  "tropical_haze" (vis=5 km), "arctic_clear" (vis=100 km)
- Geometry: overhead look, altitude 500 km

**Desired outputs**:
- Detection range matrix: 12x4x3 table showing max range (km) at SNR >= 5
- NIIRS at each operating point
- Color-coded Excel output (green/yellow/red)
- 144 evaluations — batch automated
- Worst-case target: which target is hardest to detect?

**Gaps revealed**:
- No Excel input parser for target libraries
- No projected area calculator from dimensions
- No detection range calculator
- No batch execution from scenario matrix definition
- No Excel output with conditional formatting
- No NIIRS output

---

### Scenario 4.2: Maritime Domain Awareness — Ship Classification Ranges

**Context**: Lisa needs to determine at what range a MWIR sensor can classify
ship types (detection NIIRS >= 3, recognition >= 4, identification >= 5).

**Inputs she has**:
- Ship library (CSV): ship_class, beam_m, length_m, freeboard_m,
  typical_stack_temp_K, hull_material
- Hull materials map to emissivity: painted_steel=0.85, aluminum=0.15, etc.
- Sensor: airborne MWIR FLIR at 5 km altitude
- Range sweep: 5-100 km
- Sea state: calm vs. rough

**Desired outputs**:
- For each ship class: detection, recognition, identification range
- Range-NIIRS curves per ship class
- Probability of detection vs. range (Johnson criteria)
- Classification matrix: ship_class x {detect, recognize, identify} -> range
- Briefing-ready format

**Gaps revealed**:
- No Johnson criteria model (cycles-on-target for DRI)
- No NIIRS output
- No ship-class to projected area converter
- No material name to emissivity mapper
- No DRI (Detect-Recognize-Identify) range calculator

---

### Scenario 4.3: Camouflage Effectiveness Analysis

**Context**: Lisa wants to evaluate thermal camouflage effectiveness. She has
emissivity spectra for a bare vehicle and three types of camo netting.

**Inputs she has**:
- Bare vehicle: T = 310 K, emissivity from ASTER library ("oxidized steel")
- Camo net A: measured emissivity(lambda) spectrum (CSV, 8-14 um, 100 pts)
- Camo net B: different spectrum (lower emissivity in 8-10, higher in 10-12)
- Camo net C: emissivity at only 3 discrete wavelengths (needs interpolation)
- Background: scrub vegetation, T = 305 K

**Desired outputs**:
- SNR and contrast SNR for each camo option vs. bare vehicle
- Spectral contrast plot: delta-L(lambda) between target and background
- Optimal detection band for each camo
- Reduction in detection range (%) for each camo vs. bare
- Recommendation: most effective camo against this sensor

**Gaps revealed**:
- No spectral contrast (delta-L vs. lambda) output
- No optimal band finder
- No detection range reduction analysis
- No sparse spectral data interpolation
- Limited spectral emissivity input (scalar only, not spectral curve)

---

### Scenario 4.4: Time-of-Day Analysis for Intelligence Collection

**Context**: Lisa needs the best time of day to collect imagery. Temperature
difference between target and background varies with solar heating.

**Inputs she has**:
- Diurnal temperature curves (CSV): columns hour, target_temp_K,
  background_temp_K. 24 rows.
- Sensor: fixed LWIR config
- Wants SNR vs. time of day and optimal collection window

**Desired outputs**:
- SNR vs. time of day (24-point curve)
- Contrast SNR vs. time of day — when does delta-T = 0 (crossover)?
- Thermal crossover times — hours when target and background equalize
- Best collection window: time range when contrast SNR > threshold
- NIIRS vs. time of day

**Gaps revealed**:
- No time-varying scenario (diurnal temperature input)
- No thermal crossover detection
- No "optimal collection window" finder
- No temporal sweep (sweep over CSV table of time-varying inputs)

---

### Scenario 4.5: Altitude Trade for UAV-Mounted Sensor

**Context**: Lisa evaluates an LWIR sensor on a UAV at different altitudes
(500-5000 m AGL). Lower altitude = better GSD but more jitter from turbulence.

**Inputs she has**:
- Jitter data (CSV): columns altitude_m, jitter_rms_urad. 10 rows. Jitter
  increases at lower altitude.
- Sensor: compact LWIR, 8 cm aperture, f/1.4, 17 um VOx microbolometer
- Microbolometer: NETD = 50 mK (not component-level noise in e-)
- Target: 3x3 m concrete pad at 310 K against grass at 295 K

**Desired outputs**:
- SNR vs. altitude (with altitude-dependent jitter)
- GSD vs. altitude
- NIIRS vs. altitude — find the sweet spot
- MTF at Nyquist vs. altitude (jitter degrades MTF at low altitude)
- Dwell time vs. altitude for a given FOV

**Gaps revealed**:
- No microbolometer noise model (NETD-specified)
- No altitude-dependent jitter input (lookup table)
- No GSD, NIIRS outputs
- No dwell time calculation
- No VOx microbolometer detector template

---

## Persona 5: Tom — Optical Designer

### Scenario 5.1: Zernike WFE Budget — How Much Aberration Can I Tolerate?

**Context**: Tom has a Zernike decomposition from Zemax. He wants to input
the first 15 coefficients and see the impact on system MTF, EE, and NIIRS.

**Inputs he has**:
- Zernike coefficients Z4-Z15 (Zemax .ZMX export — not RADIANT format)
- Units: waves at 633 nm reference wavelength
- Field positions: on-axis and 3 off-axis (separate Zernike sets)
- Pupil: 40 cm, 14 cm secondary (35% linear obscuration)

**Desired outputs**:
- 2D PSF at each field position
- MTF vs. spatial frequency for each field position
- EE(1x1) and EE(3x3) vs. WFE RMS (sweep 0 to 0.25 waves)
- MTF vs. field angle
- NIIRS vs. WFE RMS
- Strehl ratio vs. WFE RMS

**Gaps revealed**:
- No Zemax Zernike importer
- No field-dependent WFE/PSF (only on-axis)
- No MTF vs. spatial frequency curve output
- No Strehl ratio metric
- No NIIRS output
- No field-angle-dependent analysis

---

### Scenario 5.2: Detector Sampling — Q-Parameter Analysis

**Context**: Tom wants to evaluate how pixel pitch affects image quality for
his f/4 MWIR system. Q = lambda*f/#/pitch determines under- vs. over-sampled.

**Inputs he has**:
- Optics: D = 30 cm, f = 120 cm (f/4), lambda_center = 4.2 um
- Pixel pitches: 8, 12, 15, 18, 24, 30 um
- Wants to see aliasing effects when Q < 1

**Desired outputs**:
- Q parameter for each pixel pitch
- MTF at Nyquist vs. pixel pitch
- EE(1x1) vs. pixel pitch
- Aliased MTF — system MTF folded at Nyquist
- Noise-equivalent angle (NEA)
- System MTF curve showing detector MTF x optical MTF

**Gaps revealed**:
- No Q parameter calculation or reporting
- No aliased/folded MTF model
- No noise-equivalent angle metric
- No MTF vs. frequency curve output
- No sampling analysis mode

---

### Scenario 5.3: Polychromatic PSF — How Much Does Chromaticism Matter?

**Context**: Tom wants to understand how much the PSF changes across his MWIR
band (3.5-5.0 um). Diffraction scales with wavelength so PSF at 3.5 um is
sharper than at 5.0 um.

**Inputs he has**:
- System: f/4, D = 30 cm, MWIR 3.5-5.0 um
- Source spectrum: 300 K blackbody (heavily weighted toward 5 um)
- Wants to compare PSFs at 3.5, 4.0, 4.5, 5.0 um individually, plus
  polychromatic (all 4 weighted)
- Also wants non-blackbody source spectrum (reflected sunlight)

**Desired outputs**:
- 2D PSF at each individual wavelength
- Polychromatic PSF for blackbody weighting vs. solar weighting
- PSF FWHM vs. wavelength
- EE(1x1) vs. wavelength
- Chromatic MTF: system MTF curve at each wavelength overlaid
- Polychromatic MTF vs. monochromatic

**Gaps revealed**:
- No per-wavelength PSF output (intermediate monochromatic PSFs not exposed)
- No arbitrary source spectrum for PSF weighting
- No FWHM vs. wavelength output
- No per-wavelength MTF curve output
- Limited monochromatic vs. polychromatic comparison

---

### Scenario 5.4: Jitter Tolerance — Line-of-Sight Stability Requirements

**Context**: Tom needs to derive the jitter requirement. He wants to sweep
jitter RMS from 0 to 50 urad and find where NIIRS drops by 1 full grade.

**Inputs he has**:
- System: f/10 VNIR, D = 50 cm, 8 um pitch silicon CCD, 450-700 nm
- Jitter: RMS 0 to 50 urad (1-sigma, each axis)
- Knows jitter is correlated between x and y (elliptical jitter cone) —
  has separate x and y values
- Has a jitter PSD from spacecraft team, wants to convert to effective RMS

**Desired outputs**:
- NIIRS vs. jitter RMS
- MTF at Nyquist vs. jitter RMS
- Jitter budget: at what jitter does NIIRS degrade by 0.5? by 1.0?
- Separate x/y jitter analysis
- PSD to RMS converter
- RER vs. jitter

**Gaps revealed**:
- No NIIRS output
- No separate x/y jitter inputs (only isotropic)
- No jitter PSD to RMS converter
- No threshold-finding ("at what jitter does metric = X?")
- Jitter may not be in platform parameters yet

---

### Scenario 5.5: Stray Light Analysis — Veiling Glare Impact on Contrast

**Context**: Tom has stray light analysis from FRED. VGI is 3% and he has
out-of-field stray irradiance. He wants to evaluate the contrast and NIIRS
impact.

**Inputs he has**:
- Veiling glare fraction: 0.03
- Out-of-field stray irradiance: 2.5 W/m^2
- Full stray light PSF (2D array from FRED) — RADIANT only accepts scalar VGI

**Desired outputs**:
- Contrast SNR with and without stray light
- NIIRS reduction due to stray light
- MTF impact of veiling glare
- Stray light SNR budget
- Sweep VGI 0-10% to find tolerance

**Gaps revealed**:
- No NIIRS output
- No stray light PSF input (only scalar VGI and absolute irradiance)
- No MTF impact of stray light modeled
- No "with vs. without" toggle for individual effects
- No FRED/Zemax stray light PSF importer

---

## Persona 6: Dr. Chen — Researcher

### Scenario 6.1: Validating Against Published SNR Benchmark

**Context**: Dr. Chen is writing a paper comparing RADIANT against three
published SNR models (Holst, Driggers, IEEE paper). He needs to replicate
their exact configurations.

**Inputs he has**:
- Published parameters (PDF tables) — each uses different conventions:
  - Holst: uses D* (specific detectivity, cm*sqrt(Hz)/W) instead of QE and
    dark current
  - Driggers: uses NETD specification instead of component-level noise
  - IEEE paper: uses NEP (noise equivalent power, W/sqrt(Hz))
- Each paper uses different atmospheric transmission conventions

**Desired outputs**:
- RADIANT's SNR for each benchmark configuration
- Percentage difference from each published result
- Intermediate comparison at each stage to pinpoint discrepancies
- Assumptions audit: which RADIANT assumptions differ from each paper
- Sensitivity to assumptions: if RADIANT assumed X but paper assumed Y

**Gaps revealed**:
- No D* to QE/dark current converter
- No NETD to component noise decomposition
- No NEP input mode
- No stage-by-stage comparison tool
- No assumption documentation per-run

---

### Scenario 6.2: Atmospheric Model Intercomparison

**Context**: Dr. Chen wants to compare RADIANT's Beer-Lambert model against
MODTRAN 6 and libRadtran for the same path geometry.

**Inputs he has**:
- MODTRAN tape7: wavenumber (cm-1), transmittance, path radiance
  (W/cm^2/sr/cm-1) — non-SI units
- libRadtran output: wavelength (nm), direct transmittance, diffuse
  transmittance, path radiance (mW/m^2/sr/nm)
- Both at 10 deg off-nadir, 500 km path, midlatitude summer

**Desired outputs**:
- Spectral transmittance overlay: RADIANT simple vs. MODTRAN vs. libRadtran
- In-band average transmittance for each model
- SNR from each atmospheric model (same sensor, different atmo)
- Spectral residuals: RADIANT minus MODTRAN, RADIANT minus libRadtran
- Band-by-band error analysis: where does the simple model break down?

**Gaps revealed**:
- No libRadtran parser (nm, mW/m^2/sr/nm format)
- No MODTRAN tape7 parser for wavenumber domain
- No spectral comparison/overlay tool
- No per-band error analysis
- No "swap atmosphere model, keep everything else" workflow

---

### Scenario 6.3: Noise Model Verification — Analytic vs. RADIANT

**Context**: Dr. Chen wants to verify RADIANT's noise model by computing
each term analytically (Rogalski's textbook equations) and comparing.

**Inputs he has**:
- Fully specified detector with all 16 noise parameters non-zero
- Hand-derived expected noise for each term
- Wants each noise term individually for comparison

**Desired outputs**:
- All 16 noise terms in electrons
- Total noise: RSS vs. linear sum vs. RADIANT — verify RSS
- Units verification: each term in e- RMS
- Sensitivity matrix: d(sigma_i)/d(p_j) for each noise term vs. parameter
- Noise term scaling with integration time — verify shot as sqrt(t), read
  as constant, etc.

**Gaps revealed**:
- No noise sensitivity matrix (partial derivatives of individual noise terms)
- No per-term output at each sweep point (only total)
- No verification mode with intermediate calculations

---

### Scenario 6.4: Synthetic Scene Generation for Algorithm Testing

**Context**: Dr. Chen is developing a target detection algorithm and needs
RADIANT to generate pixel-level signal and noise for a synthetic scene
with multiple targets at different ranges.

**Inputs he has**:
- 5 targets at ranges 10, 20, 50, 100, 200 km, each different T and emissivity
- Background: uniform 290 K terrain
- Wants a 1D "strip" of pixels showing signal level across all targets

**Desired outputs**:
- Per-pixel signal array (e-) for each target and background
- Per-pixel noise array (e-) — different for target vs. background pixels
- Simulated image: 1D row of pixel values with noise (Poisson + Gaussian)
- SNR map — SNR at each target's pixel
- ROC curve: detection probability vs. false alarm rate

**Gaps revealed**:
- No multi-target scene model
- No per-pixel signal/noise simulation
- No simulated image output with realistic noise
- No ROC curve generator
- No spatial scene layout

---

### Scenario 6.5: Spectral Emissivity Sensitivity for Retrieval

**Context**: Dr. Chen studies how errors in assumed emissivity affect
temperature retrieval accuracy in LWIR remote sensing.

**Inputs he has**:
- True scene: T = 300 K, emissivity = 0.95
- "Retrieved" scenes: same T but emissivity 0.90 to 1.00 in 0.01 steps
- Sensor: LWIR, 8-12 um
- Wants to compute what temperature would be retrieved if wrong emissivity
  is assumed

**Desired outputs**:
- Retrieved temperature vs. assumed emissivity
- Temperature error (K) vs. emissivity error
- NEDT-equivalent emissivity uncertainty
- Signal electrons vs. emissivity
- Jacobian: dL/d(emissivity) and dL/dT at operating point

**Gaps revealed**:
- No temperature retrieval model (inverse problem)
- No Jacobian output (more granular than sensitivity analysis)
- No NEDT output
- No emissivity-temperature coupling analysis
- No retrieval error propagation model

---

## Persona 7: Karen — Test Engineer

### Scenario 7.1: Predicted vs. Measured NEDT Reconciliation

**Context**: Karen measured NEDT = 22 mK at a 25 C blackbody on the as-built
sensor. RADIANT predicts 18 mK. She needs to find which noise term explains
the 4 mK discrepancy.

**Inputs she has**:
- Lab config: 298.15 K blackbody filling aperture, no atmosphere, lab
  ambient 22 C
- As-built parameters (measured): QE = 0.68, dark current = 135 e-/s at
  77 K, read noise = 14.2 e- post-CDS, t_int = 8 ms, actual f/# = 4.05
- These are in a lab notebook (Excel), not YAML

**Desired outputs**:
- Predicted NEDT with as-built parameters
- NEDT breakdown: each noise term's contribution to total NEDT
- Gap analysis: which term, if increased by how much, explains the 4 mK gap?
- Predicted vs. measured comparison table
- Sensitivity: d(NEDT)/d(each noise parameter)

**Gaps revealed**:
- No NEDT output
- No NEDT breakdown by noise term
- No "gap analysis" / root cause mode
- No lab mode documentation (exo atmosphere exists but isn't documented for
  this use case)
- No predicted-vs-measured comparison framework

---

### Scenario 7.2: Radiometric Calibration Verification

**Context**: Karen is performing radiometric calibration. She has a
calibrated blackbody at 5 temperatures and measured DN at each.

**Inputs she has**:
- Blackbody temperatures: [280, 300, 320, 340, 360] K
- Measured DN values at each (CSV)
- Sensor: as-built parameters
- Needs to account for lab ambient background and instrument self-emission

**Desired outputs**:
- Predicted signal (e-) and DN at each blackbody temperature
- Predicted vs. measured DN plot with residuals
- Responsivity (DN/K or DN/(W/m^2/sr))
- Non-linearity check: predicted vs. linear fit
- Calibration uncertainty: noise at each temperature -> calibration accuracy

**Gaps revealed**:
- No DN output (RADIANT stops at electrons, gain converts but isn't reported)
- No multi-temperature calibration sweep mode
- No responsivity metric
- No non-linearity analysis
- No calibration uncertainty propagation

---

### Scenario 7.3: MTF Measurement vs. Prediction

**Context**: Karen measured system MTF using a slanted-edge target in the lab
and wants to overlay the RADIANT prediction.

**Inputs she has**:
- Measured MTF (CSV): spatial_frequency_cy_mm, MTF_measured. 50 points.
- Note: frequency in cycles/mm — RADIANT uses cycles/m internally
- As-built WFE: 0.07 waves RMS at 633 nm
- Focus: 5 um defocus from best focus

**Desired outputs**:
- Predicted MTF curve (DC to 2x Nyquist, not just Nyquist value)
- Measured vs. predicted MTF overlay
- Per-component MTF curves: diffraction, WFE, detector, electronics
- MTF residual: predicted minus measured at each frequency
- Defocus sensitivity: how much does 5 um defocus degrade MTF?

**Gaps revealed**:
- No full MTF curve output (only MTF at Nyquist)
- No MTF vs. spatial frequency data export
- No measurement import/overlay capability
- No defocus model (as linear focus shift, not Zernike Z4)
- No cycles/mm to cycles/m conversion helper

---

### Scenario 7.4: Cold Shield Efficiency Test

**Context**: Karen suspects the cold shield is misaligned, allowing excess
thermal background. She measured higher-than-expected background signal.

**Inputs she has**:
- Designed cold stop efficiency: 100%
- Suspected actual: 85-95%
- Background signal measured: 45,000 e- (expected: 35,000 e- with perfect
  cold stop)
- Wants to sweep cold_stop_efficiency 0.80 to 1.00

**Desired outputs**:
- Background signal (e-) vs. cold_stop_efficiency
- Best-fit efficiency matching measured 45,000 e-
- SNR and NEDT at measured vs. designed efficiency
- Thermal background breakdown: scene vs. optics vs. cold stop leakage
- Noise budget with cold stop leakage vs. without

**Gaps revealed**:
- No "find parameter value that matches measurement" solver
- No thermal background breakdown (scene vs. optics vs. cold stop)
- No NEDT output

---

### Scenario 7.5: Environmental Test — Performance at Temperature Extremes

**Context**: Karen is performing thermal-vacuum testing, measuring performance
at detector temperatures of 70, 77, 80, 85, 90 K.

**Inputs she has**:
- Measured dark current at each temperature (CSV): T_K, dark_current_e_per_s
- Rule 07 parameters but measured J(T) deviates from Arrhenius at high T
- FPA temperature also affects QE — has QE(T) at 3 temperatures
- Background: 300 K blackbody (chamber shroud)

**Desired outputs**:
- SNR vs. detector operating temperature
- NEDT vs. detector operating temperature
- Noise budget at each temperature showing dark current growing
- Predicted vs. measured dark current (Arrhenius vs. measured)
- QE impact: how much does QE(T) variation matter vs. dark current?
- Operating temperature recommendation with margin

**Gaps revealed**:
- No measured J(T) curve input (only Arrhenius model)
- No QE(T) model (QE is temperature-independent)
- No NEDT output
- No temperature-dependent parameter sweep with co-varying parameters
- No "meets spec" threshold checker with margin

---

## Consolidated Gap Analysis

### Metrics not yet surfaced (highest leverage — each unlocks many scenarios)

| Gap | Scenarios affected | Implementation location |
|-----|--------------------|------------------------|
| NEDT | 1.1, 1.3, 2.2, 3.3, 3.5, 4.5, 6.5, 7.1, 7.4, 7.5 | performance/ |
| NIIRS | 1.1, 1.2, 1.4, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.4, 4.5, 5.1, 5.4, 5.5 | performance/ (GIQE-5 exists) |
| GSD | 1.2, 3.2, 3.3, 3.4, 4.5 | performance/ |
| Full MTF curve | 5.1, 5.2, 5.3, 7.3 | performance/ or optics/ |
| Strehl ratio | 1.5, 5.1 | optics/ |
| Well fill fraction | 2.5 | performance/ |
| DN output | 7.2 | readout/ |

### Input format converters

| Gap | Scenarios | Module |
|-----|-----------|--------|
| MODTRAN tape7 (wavenumber) | 1.1, 6.2 | io/ |
| QE CSV (nm/pct) | 2.1 | io/ |
| J_dark CSV (A/cm^2) | 2.1 | io/ |
| ASTER spectral library | 1.3, 4.3 | io/ |
| libRadtran output | 6.2 | io/ |
| Excel target/detector specs | 1.3, 4.1, 7.1 | io/ |
| Spectral emissivity input | 4.3 | source/ |

### New models and capabilities

| Gap | Scenarios | Complexity |
|-----|-----------|------------|
| Detection range solver | 1.1, 4.1, 4.2, 4.3 | Medium |
| Johnson criteria / DRI | 4.2 | Medium |
| Solar geometry (LTAN/date/lat) | 1.2, 3.1 | Medium |
| Off-nadir geometry (Earth curvature) | 3.4 | Medium |
| Lab/exo mode documentation | 2.1, 7.1, 7.2 | Small |
| Microbolometer noise model | 4.5 | Medium |
| Multi-target scene | 6.4 | Large |
| Temporal sequence model | 2.4, 4.4 | Large |
| Temperature retrieval (inverse) | 6.5 | Large |
| Arbitrary pupil mask | 1.5 | Medium |
| Separate x/y jitter | 5.4 | Small |
| D* / NEP / NETD converters | 6.1 | Small |
