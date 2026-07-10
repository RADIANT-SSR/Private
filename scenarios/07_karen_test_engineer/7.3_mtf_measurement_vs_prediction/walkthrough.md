# Scenario 7.3: MTF Measurement vs. Prediction

Refreshed 2026-07-07 (Scenario_Execution_Plan Phase R): measured data now
imported via `load_measured_curve` and compared via `compare_mtf` (Gap 30);
electronics MTF (Gap 32) and TIS scatter (Gap 31) exercised as residual
explainers — both rejected by the data. The refresh also uncovered two
framework defects: an odd-kernel crash (fixed, commit 8a5d9e8) and a Rule 4
dual-path violation for scalar-WFE + defocus configs (filed as CU-058,
**fixed 2026-07-09** — defocus is now pupil Z4 on both paths and the
consistency check passes on every run of this scenario; numbers below
re-transcribed under the fixed physics).

## Persona

**Karen Martinez** — Integration & Test Engineer.  She measures sensor performance
in the lab and compares against model predictions.  "Does our sensor match the
model?"

## Question

Karen measured system MTF using a slanted-edge target (ISO 12233) in the lab at
650 nm.  She has as-built WFE from interferometry (0.07 waves RMS at 633 nm) and
knows the detector is 5 um defocused from best focus.  She wants to:

1. Overlay RADIANT's predicted MTF curve on her measured data
2. See per-component MTF decomposition (diffraction, pixel, IPC, defocus)
3. Compute the residual (predicted minus measured) at each frequency
4. Understand how sensitive MTF is to defocus

## System Configuration

| Parameter                 | Value      | Unit   | Notes                           |
|---------------------------|------------|--------|---------------------------------|
| Aperture diameter         | 20         | cm     | Cassegrain                      |
| Focal length              | 60         | cm     | Measured via collimator         |
| f-number                  | 3.0        | --     | Derived                         |
| Optical transmission      | 82         | %      | Measured at 650 nm              |
| Central obscuration       | 25         | %      | Secondary mirror                |
| Spectral band             | 550-750    | nm     | VNIR                            |
| MTF test wavelength       | 650        | nm     | Quasi-monochromatic collimator  |
| Pixel pitch               | 10         | um     | Square pixels, silicon CCD      |
| Fill factor               | 100        | %      | Full-frame CCD                  |
| IPC coupling              | 1.0        | %      | Measured                        |
| WFE RMS                   | 0.07       | waves  | At 633 nm HeNe reference        |
| Defocus from best focus   | 5          | um     | Through-focus scan measurement  |

### Derived Parameters

| Parameter            | Value   | Unit    | Notes                                |
|----------------------|---------|---------|--------------------------------------|
| f_Nyquist            | 50.0    | cy/mm   | 1/(2 * 10 um) = 50,000 cy/m         |
| f_cutoff (diffr.)    | 512.8   | cy/mm   | 1/(650 nm * 3.0)                     |
| Q (sampling)         | 0.195   | --      | Heavily undersampled                 |
| Airy disk diameter   | 4.8     | um      | 0.48 pixels                          |
| f_Ny / f_cutoff      | 0.098   | --      | Nyquist at ~10% of cutoff            |

**Sampling context:** Q = 0.195 means the system is heavily undersampled.  The
Airy disk fits within a single pixel, so the pixel aperture is the dominant MTF
contributor, not diffraction.  At Nyquist, the diffraction MTF is still 0.876 --
the optics are far from the diffraction limit spatially.

## Inputs

Karen provides:

- **Lab spreadsheet** (`karen_mtf_lab_data.xlsx`) containing:
  - System Configuration sheet: optics, spectral, detector, test setup parameters
  - Measured MTF sheet: 50-point slanted-edge MTF from 0 to 100 cy/mm (human review copy)
  - As-Built WFE sheet: interferometric measurement (0.07 waves at 633 nm)
  - Focus Position sheet: defocus measurement (5 um) and sweep values

- **Slanted-edge tool CSV export** (`karen_measured_mtf.csv`) — the same 50
  points in the edge-analysis tool's native format (comment header + two
  columns). The script reads this with `radiant.io.measurement.load_measured_curve`
  (Gap 30): auto header/comment detection, ascending-x and numeric validation,
  unit tag `cy/mm` attached at the boundary.

- **Key unit conversions at the boundary:**
  - Aperture: 20 cm -> 0.20 m
  - Focal length: 60 cm -> 0.60 m
  - Transmission: 82% -> 0.82
  - Temperature: 22 C -> 295.15 K
  - Pixel pitch: 10 um -> 1.0e-5 m
  - Frequency: cy/mm -> cy/m (multiply by 1000)
  - Integration time: 2 ms -> 0.002 s

- **Atmosphere model:** `"exo"` (vacuum/lab -- tau = 1, no path radiance).  There
  is no atmosphere in a bench test, so this zeroes out atmospheric effects.

## Approach

The script runs a single RADIANT evaluation with the as-built parameters, then
compares against the measurement with `radiant.api.compare_mtf` (Gap 30): the
measured cy/mm axis is converted to canonical cy/m, the predicted curve is
interpolated onto the measured points (overlap only — never extrapolated), and
the result carries residual statistics plus a formatted `.table()`.

It then runs a **residual-explainer grid**: candidate physical effects RADIANT
now models — electronics blur (`readout.electronics_sigma_um`, Gap 32) and TIS
surface-roughness scatter (`optics.surface_roughness_nm`, Gap 31) — are swept
over a small grid, each re-compared via `compare_mtf`, and ranked by residual
RMS. A hypothesis that does not reduce the residual is rejected.

RADIANT also provides the MTF budget decomposition via
`result.stage_outputs["performance"]["mtf_budget"]` (Gap 19 closed).  Defocus is
modeled natively via `optics.defocus_um` (Gap 29 closed).

Component MTF curves are also computed analytically for comparison:

1. **Diffraction MTF:** Circular aperture formula
   `MTF(f) = (2/pi)[arccos(f/fc) - (f/fc)*sqrt(1-(f/fc)^2)]`
   Note: does not include central obscuration (RADIANT's ePSF does).

2. **Pixel aperture MTF:** `|sinc(pi * f * p * FF)|`

3. **IPC MTF:** `(1-4a) + 2a[cos(2*pi*f*p) + 1]` (1-D, other axis = 0)

4. **Defocus MTF:** `exp(-2*pi^2*sigma^2*f^2)` with sigma = |delta|/(4*f/#*sqrt(3)).
   Now modeled in RADIANT via `optics.defocus_um` (Gap 29 closed).

## Results

### Gap Closure Table

| Gap # | Description | Previous Status | Current Status | Notes |
|-------|-------------|-----------------|----------------|-------|
| 19    | No MTF budget decomposition API | OPEN | **CLOSED** | `mtf_budget.per_term_at_nyquist` dict now available |
| 29    | No defocus model | OPEN | **CLOSED** | `optics.defocus_um` — pupil Z4 on both spatial paths (CU-058 fixed) |
| 30    | No measurement data import API | OPEN | **CLOSED** | `load_measured_curve` + `compare_mtf`, exercised here |
| 31    | No scatter/TIS model | OPEN | **CLOSED** | `optics.surface_roughness_nm`, exercised (and rejected) as residual explainer |
| 32    | No electronics MTF model | OPEN | **CLOSED** | `readout.electronics_sigma_um`, exercised (and rejected) as residual explainer |

### Additional Metrics Now Available

| Metric | Value | Unit | Notes |
|--------|-------|------|-------|
| Strehl | 0.8259 | -- | Degraded-PSF peak over diffraction-limited reference |
| RER | 0.6719 | -- | Relative edge response |
| Q (center) | 0.195 | -- | Sampling parameter |
| Q (min/max) | 0.165 / 0.225 | -- | Over band |
| FWHM_x | 10.79 | um | PSF full-width half-max |
| Well margin | 429.6 | dB | Very large: lab test, near-zero signal |
| Dynamic range | 83.2 | dB | |
| GSD | N/A | -- | Lab test (altitude = 0) |
| NIIRS | N/A | -- | Lab test (altitude = 0) |
| NEDT | N/A | -- | Lab test (no thermal scene in VNIR) |

### RADIANT MTF Budget at Nyquist (from API)

| Component | MTF@Ny_x | MTF@Ny_y |
|-----------|----------|----------|
| Optics (diffraction + obscuration + WFE screen + defocus-Z4, one pupil) | 0.6699 | 0.6694 |
| Pixel Aperture | 0.6364 | 0.6364 |
| IPC | 0.9602 | 0.9602 |
| Jitter | 1.0000 | 1.0000 |
| Smear | 1.0000 | 1.0000 |
| Charge Diffusion | 1.0000 | 1.0000 |
| TDI | 1.0000 | 1.0000 |
| Electronics | 1.0000 | 1.0000 |
| **System (product)** | **0.4095** | **0.4092** |

**CU-058 resolved (2026-07-09)**: this scenario originally exposed the Rule 4
violation — the product path dropped the scalar-RMS screen when folding
defocus to Z4 (Optics term read 0.8115, WFE-less) while the PSF path used a
Gaussian defocus kernel, and the consistency check failed at 0.169 vs 0.05
on every run. Defocus is now pupil Z4 alongside the preserved screen on
**both** paths: the budget's Optics term carries diffraction + obscuration +
WFE + defocus from one pupil (0.6699), the product-path system (0.4095) now
agrees with the PSF path (0.3962) to within the rect-kernel discretization
floor, and the consistency check passes.

### MTF at Nyquist (50 cy/mm)

| Source                    | MTF@Ny   | Notes                                    |
|---------------------------|----------|------------------------------------------|
| Measured (slanted-edge)   | 0.4441   | Karen's lab data                         |
| RADIANT predicted         | 0.3962   | Includes defocus (pupil Z4), WFE, obscuration |
| Analytic (with defocus)   | 0.5339   | Includes all 4 analytic components       |

### MTF Comparison at Selected Frequencies

| Freq [cy/mm] | Measured | RADIANT  | Analytic | Resid(R)  | Resid(A)  |
|---------------|----------|----------|----------|-----------|-----------|
| 0             | 1.0000   | 1.0000   | 1.0000   | +0.0000   | +0.0000   |
| 10            | 0.9304   | 0.7790   | 0.9554   | -0.1514   | +0.0250   |
| 20            | 0.8669   | 0.7111   | 0.8763   | -0.1558   | +0.0094   |
| 30            | 0.7284   | 0.6165   | 0.7728   | -0.1118   | +0.0445   |
| 40            | 0.5922   | 0.5075   | 0.6559   | -0.0848   | +0.0636   |
| 50 (Nyquist)  | 0.4441   | 0.3962   | 0.5339   | -0.0480   | +0.0897   |
| 60            | 0.3322   | 0.2836   | 0.4123   | -0.0486   | +0.0801   |
| 70            | 0.2114   | 0.1813   | 0.2946   | -0.0301   | +0.0831   |
| 80            | 0.1185   | 0.0917   | 0.1837   | -0.0268   | +0.0652   |
| 90            | 0.0444   | 0.0197   | 0.0839   | -0.0247   | +0.0395   |
| 100           | 0.0010   | 0.0346   | 0.0000   | +0.0336   | -0.0010   |

### Residual Statistics (Predicted - Measured)

| Model     | RMS    | Max    |
|-----------|--------|--------|
| RADIANT   | 0.0921 | 0.1876 |
| Analytic  | 0.0606 | 0.1092 |

(Computed by `compare_mtf`: 50 measured points compared, 0 excluded as
outside the predicted frequency grid.)

### Residual Explainers (Gap 32 electronics, Gap 31 scatter) — Both Rejected

Karen has no independent measurement of the amplifier bandwidth or the mirror
micro-roughness, so the script tests each hypothesis by re-running the chain
over a candidate grid and ranking by `compare_mtf` residual RMS:

| σ_elec [µm] | Roughness [nm] | Resid RMS [--] | MTF@Ny [--] |
|-------------|----------------|----------------|-------------|
| 0.0 (as-built) | 0.0 | **0.0921** | 0.3962 |
| 0.0 | 5.0 | 0.0962 | 0.3925 |
| 1.0 | 0.0 | 0.0991 | 0.3773 |
| 2.0 | 0.0 | 0.1222 | 0.3262 |

**Both hypotheses are rejected** — every added blur makes the fit worse. The
diagnosis comes from the residual sign: the as-built prediction already sits
*below* the measurement over most of the band (mean predicted − measured =
−0.070), so additional blur can only widen the gap. The discrepancy is not a
missing degradation; it is the **shape ambiguity of the scalar-WFE input**: a
single RMS number fixes the Strehl but not where the aberrated energy lands.
RADIANT's random-phase-screen model puts it in a compact halo (immediate
low-frequency MTF drop toward the Strehl plateau ≈ 0.83), while the actual
system's smooth aberrations keep low frequencies near 1. The fix is to feed
RADIANT the as-built Zernike prescription via `io.load_zemax_zernike`
(Gap 26 — exercised in scenario 5.1) so the pupil carries the true aberration
shape and the ambiguity disappears.

Testing and *rejecting* a hypothesis is the point of the residual-explainer
workflow — the grid discriminates between "unmodeled blur" and "wrong WFE
shape" from the residual's sign and spectral signature alone.

### Analytic MTF Budget at Nyquist

| Component         | MTF@Ny   | Notes                                  |
|-------------------|----------|----------------------------------------|
| Diffraction       | 0.8761   | Circular, no obscuration               |
| Pixel aperture    | 0.6366   | sinc(pi * 50e3 * 10e-6) -- dominant    |
| IPC (boost)       | 0.9600   | 1% coupling -- slight boost            |
| Defocus (5 um)    | 0.9971   | Negligible at this defocus level       |
| **Product**       | **0.5338** |                                      |

### Noise Breakdown (Lab Test)

| Source | Value [e-] |
|--------|-----------|
| Dark shot | 0.32 |
| Read noise | 8.00 |
| Quantization | 2.31 |

Note: Signal shot and background shot noise are ~0 in this lab test because there
is negligible photon flux from a room-temperature thermal scene in the VNIR band.
Nearfield = 0 because the optics use scalar transmission mode (emissivity = 0 by
Kirchhoff's law).

### Defocus Sensitivity

| Defocus [um] | Spot Radius [um] | MTF@Ny (system) | dMTF [%]  |
|--------------|------------------|-----------------|-----------|
| 0            | 0.000            | 0.3962          | 0.0       |
| 1            | 0.167            | 0.3960          | -0.0      |
| 2            | 0.333            | 0.3956          | -0.1      |
| 5            | 0.833            | 0.3928          | -0.9      |
| 10           | 1.667            | 0.3828          | -3.4      |
| 15           | 2.500            | 0.3668          | -7.4      |

Karen's 5 um defocus causes < 1% MTF loss at Nyquist — it is NOT the dominant
contributor to the measurement gap. (Sweep now runs through the pupil-Z4
defocus model, CU-058; the fractional degradation profile is essentially
unchanged from the Gaussian approximation at these small defocus values.)

## Physics Discussion

### RADIANT vs. Measured MTF

The RADIANT prediction (MTF@Ny = 0.3962) is close to the measurement
(0.4441), with a residual RMS of 0.092.  This is a significant improvement over
the pre-Phase-R version (which reported 0.6893 without defocus or proper WFE/
obscuration modeling).

1. **Defocus now included — as pupil Z4 (CU-058):** RADIANT folds
   `optics.defocus_um` into the complex pupil as Zernike Z4, identically on
   the PSF and MTF product paths (exact defocus OTF, Rule 4 by
   construction).  At 5 um defocus this causes only 0.9% MTF loss at
   Nyquist -- confirming defocus is not a dominant contributor.

2. **Obscuration and WFE included:** RADIANT's optical MTF (0.6699) is lower
   than the ideal unobscured diffraction MTF (0.8761) because it includes the
   25% central obscuration, the 0.07-wave WFE screen, AND the defocus Z4 in
   one pupil autocorrelation (pre-CU-058 the budget's optics term read
   0.8115 because the WFE screen was dropped).

3. **The synthetic measurement includes additional degradation:** The "measured"
   MTF (generated by `create_spreadsheet.py`) includes diffusion blur (sigma =
   2 um) and WFE effects modeled differently than RADIANT's EffectivePSF.

4. **RADIANT slightly underpredicts** at mid-frequencies (10-40 cy/mm) and is
   close at Nyquist.  The analytic model (RMS = 0.061) tracks the measurement
   differently because it uses ideal unobscured diffraction.

### Key Insight: Pixel Aperture Dominates

At Q = 0.195, the pixel aperture sinc rolloff is by far the dominant MTF
contributor.  The diffraction MTF at Nyquist is still 0.876 (10% of diffraction
cutoff), but the pixel sinc is only 0.637 at Nyquist.  This means:

- Improving optics (reducing WFE) has marginal benefit on system MTF
- Pixel pitch is the limiting factor for spatial resolution
- For this system, MTF improvement requires smaller pixels or image restoration

### IPC: Apparent MTF Boost

The 1% IPC coupling gives MTF_ipc = 0.96 at Nyquist.  Despite being < 1.0, the
IPC MTF actually *boosts* apparent MTF relative to the true image MTF.  This is
because IPC cross-talk between adjacent pixels acts like a sharpening filter --
it correlates pixel values, creating artificial contrast at high frequencies.

This is a well-known effect in infrared FPAs with measurable IPC.  Karen should
be aware that the "true" optical MTF is lower than the measured MTF due to this
IPC boost -- the measured slanted-edge MTF includes the IPC effect.

### Defocus: Modest Impact at f/3

The defocus sensitivity shows that 5 um defocus at f/3 has very little impact
(< 1% MTF loss at Nyquist).  This is because the geometric defocus spot radius
scales as delta/(2*f/#), giving only 0.83 um -- much smaller than the 10 um
pixel pitch.  At faster f-numbers (f/1.5 or lower), defocus would matter much
more.

## Gaps and Defects Identified

| # | Description | Status | Impact |
|---|-------------|--------|--------|
| Gap 19 | No MTF budget decomposition API | **CLOSED** | `mtf_budget.per_term_at_nyquist` |
| Gap 29 | No defocus model (focus-shift parameter) | **CLOSED** | `optics.defocus_um` — pupil Z4 on both paths |
| Gap 30 | No measurement data import/overlay API | **CLOSED** | `load_measured_curve` + `compare_mtf` |
| Gap 31 | No scatter/surface roughness (TIS) model | **CLOSED** | `optics.surface_roughness_nm` |
| Gap 32 | No electronics MTF model (amplifier bandwidth) | **CLOSED** | `readout.electronics_sigma_um` |
| CU-058 | Scalar WFE + defocus violated Rule 4 (product path dropped the WFE screen; two paths used different defocus models) | **FILED** (this refresh) → **RESOLVED** 2026-07-09 | Defocus unified as pupil Z4 alongside the preserved screen; consistency check now passes on every run of this scenario |
| 8a5d9e8 | Scatter/defocus kernel sizing crashed on even PSF grids when the 6σ span exceeded the grid | **FIXED** (this refresh) | Blocked the Gap 31 explainer run in this VNIR configuration |
| — | Scalar `wfe_rms_waves` under-determines MTF shape | Inherent | Use Zernike input (`load_zemax_zernike`, Gap 26) when comparing to measured MTF |

## Outputs

- `outputs/mtf_comparison_results.xlsx` — Full comparison table + defocus sweep
- `outputs/fig1_mtf_measured_vs_predicted.png` — Measured vs. RADIANT overlay
- `outputs/fig2_mtf_component_decomposition.png` — Per-component MTF curves
- `outputs/fig3_mtf_residual.png` — Residual plot (predicted - measured)
- `outputs/fig4_defocus_sensitivity.png` — MTF@Nyquist vs. defocus

## What Karen Would Do Next

1. **Request the as-built Zernike prescription** from the optical shop and feed
   it to RADIANT via `io.load_zemax_zernike` (Gap 26) — this replaces the
   scalar-RMS shape assumption that dominates the current residual
2. ~~Track CU-058~~ — **resolved 2026-07-09**: the budget's Optics term now
   carries the full pupil (WFE screen + defocus Z4) and agrees with the
   PSF path; either path's outputs are trustworthy for defocused
   scalar-WFE configs
3. **Corroborate the rejected hypotheses**: the explainer grid bounds the
   electronics blur below ~1 µm and roughness below ~5 nm for this system —
   worth a one-line check against the amplifier bandwidth spec and mirror
   witness-sample data
4. **Refocus the sensor** to within 2 um of best focus (reduces defocus MTF loss
   to < 0.1%, though this is already small)
5. **Verify IPC coupling** independently and confirm whether the slanted-edge
   measurement should be corrected for IPC before comparing to the model
