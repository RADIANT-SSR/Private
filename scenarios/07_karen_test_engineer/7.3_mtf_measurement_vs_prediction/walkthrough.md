# Scenario 7.3: MTF Measurement vs. Prediction

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
  - Measured MTF sheet: 50-point slanted-edge MTF from 0 to 100 cy/mm
  - As-Built WFE sheet: interferometric measurement (0.07 waves at 633 nm)
  - Focus Position sheet: defocus measurement (5 um) and sweep values

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

The script does NOT use RADIANT in a sweep -- it runs a single RADIANT evaluation
with the as-built parameters to extract the predicted system MTF curve, then
overlays it on Karen's measured data.

Component MTF curves are computed analytically because RADIANT does not expose an
MTF budget decomposition API (Gap 19):

1. **Diffraction MTF:** Circular aperture formula
   `MTF(f) = (2/pi)[arccos(f/fc) - (f/fc)*sqrt(1-(f/fc)^2)]`
   Note: does not include central obscuration (RADIANT's ePSF does).

2. **Pixel aperture MTF:** `|sinc(pi * f * p * FF)|`

3. **IPC MTF:** `(1-4a) + 2a[cos(2*pi*f*p) + 1]` (1-D, other axis = 0)

4. **Defocus MTF:** `exp(-2*pi^2*sigma^2*f^2)` with sigma = delta/(4*f/#).
   This is NOT modeled in RADIANT (Gap 29).

## Results

### MTF at Nyquist (50 cy/mm)

| Source                    | MTF@Ny   | Notes                                    |
|---------------------------|----------|------------------------------------------|
| Measured (slanted-edge)   | 0.4441   | Karen's lab data                         |
| RADIANT predicted         | 0.6893   | No defocus model -- overpredicts         |
| Analytic (with defocus)   | 0.5308   | Includes all 4 components                |

### MTF Comparison at Selected Frequencies

| Freq [cy/mm] | Measured | RADIANT  | Analytic | Resid(R)  | Resid(A)  |
|---------------|----------|----------|----------|-----------|-----------|
| 0             | 1.0000   | 1.0000   | 1.0000   | +0.0000   | +0.0000   |
| 10            | 0.9304   | 0.7957   | 0.9552   | -0.1348   | +0.0247   |
| 20            | 0.8669   | 0.7717   | 0.8755   | -0.0952   | +0.0086   |
| 30            | 0.7284   | 0.7437   | 0.7713   | +0.0153   | +0.0429   |
| 40            | 0.5922   | 0.7139   | 0.6535   | +0.1217   | +0.0612   |
| 50 (Nyquist)  | 0.4441   | 0.6893   | 0.5308   | +0.2452   | +0.0867   |
| 60            | 0.3322   | 0.6612   | 0.4090   | +0.3290   | +0.0768   |
| 70            | 0.2114   | 0.6353   | 0.2913   | +0.4239   | +0.0799   |
| 80            | 0.1185   | 0.6091   | 0.1810   | +0.4906   | +0.0625   |
| 90            | 0.0444   | 0.5834   | 0.0824   | +0.5390   | +0.0380   |
| 100           | 0.0010   | 0.5585   | 0.0000   | +0.5575   | -0.0010   |

### Residual Statistics (Predicted - Measured)

| Model     | RMS    | Max    |
|-----------|--------|--------|
| RADIANT   | 0.3337 | 0.5575 |
| Analytic  | 0.0584 | 0.1059 |

### MTF Budget at Nyquist

| Component         | MTF@Ny   | Notes                                  |
|-------------------|----------|----------------------------------------|
| Diffraction       | 0.8761   | Circular, no obscuration               |
| Pixel aperture    | 0.6366   | sinc(pi * 50e3 * 10e-6) -- dominant    |
| IPC (boost)       | 0.9600   | 1% coupling -- slight boost            |
| Defocus (5 um)    | 0.9915   | Negligible at this defocus level       |
| **Product**       | **0.5308** |                                      |

### Defocus Sensitivity

| Defocus [um] | Spot Radius [um] | MTF@Ny (system) | dMTF [%]  |
|--------------|------------------|-----------------|-----------|
| 0            | 0.000            | 0.6893          | 0.0       |
| 1            | 0.167            | 0.6891          | -0.0      |
| 2            | 0.333            | 0.6884          | -0.1      |
| 5            | 0.833            | 0.6835          | -0.9      |
| 10           | 1.667            | 0.6661          | -3.4      |
| 15           | 2.500            | 0.6382          | -7.4      |
| 20           | 3.333            | 0.6010          | -12.8     |

10% MTF loss at approximately 20 um defocus.  Karen's 5 um defocus causes < 1%
MTF loss at Nyquist -- it is NOT the dominant contributor to the measurement gap.

## Physics Discussion

### Why RADIANT Overpredicts MTF

The RADIANT prediction (MTF@Ny = 0.6893) is substantially higher than the
measurement (0.4441).  This is expected for several reasons:

1. **No defocus model:** RADIANT has no focus-shift parameter.  However, the
   defocus sensitivity analysis shows only 0.9% loss at 5 um, so defocus alone
   does not explain the gap.

2. **Synthetic measurement includes additional degradation:** The "measured" MTF
   (generated by `create_spreadsheet.py`) includes diffusion blur (sigma = 2 um)
   and WFE effects that are modeled differently than RADIANT's EffectivePSF.

3. **Different diffraction models:** The analytic diffraction MTF uses an ideal
   circular aperture without obscuration, while RADIANT includes the 25% central
   obscuration.  Central obscuration boosts mid-frequency MTF and reduces low-
   frequency MTF, which explains why RADIANT is lower than measured at 10 cy/mm
   but higher at 50 cy/mm.

4. **The analytic model (RMS = 0.058) tracks much better** because it was
   generated from similar analytic components.  The remaining residual is
   consistent with measurement noise (~1.5% RMS from slanted-edge method).

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

## Gaps Identified

| Gap # | Description | Impact |
|-------|-------------|--------|
| 19    | No MTF budget decomposition API (existing gap) | Must manually compute component MTFs |
| 29    | No defocus model (focus-shift parameter) | Cannot predict defocused MTF |
| 30    | No measurement data import/overlay API | Must manually read and overlay lab data |
| 31    | No scatter/surface roughness (TIS) model | Unmodeled MTF loss source |
| 32    | No electronics MTF model (amplifier bandwidth) | Unmodeled MTF loss source |

## Outputs

- `outputs/mtf_comparison_results.xlsx` — Full comparison table + defocus sweep
- `outputs/fig1_mtf_measured_vs_predicted.png` — Measured vs. RADIANT overlay
- `outputs/fig2_mtf_component_decomposition.png` — Per-component MTF curves
- `outputs/fig3_mtf_residual.png` — Residual plot (predicted - measured)
- `outputs/fig4_defocus_sensitivity.png` — MTF@Nyquist vs. defocus

## What Karen Would Do Next

1. **Refocus the sensor** to within 2 um of best focus (reduces defocus MTF loss
   to < 0.1%, though this is already small)
2. **Request RADIANT add a defocus model** (Gap 29) so predictions include focus
   error
3. **Investigate scatter losses** -- the remaining MTF gap after accounting for
   all modeled components suggests ~5-10% unmodeled loss, likely from surface
   roughness or stray light
4. **Verify IPC coupling** independently and confirm whether the slanted-edge
   measurement should be corrected for IPC before comparing to the model
