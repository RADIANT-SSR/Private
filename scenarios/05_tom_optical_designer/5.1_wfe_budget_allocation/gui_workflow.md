# Scenario 5.1 GUI Workflow: WFE Budget Allocation

Refreshed 2026-07-07 (Phase R): Zemax import (Gap 26), ErrorBudget allocation
panel (Gaps 23+28), and Zernike-mode evaluation are now real API and change
Steps 2, 3, and the allocation tool below.

## Overview
Tom needs to determine how much wavefront error his 40 cm Cassegrain can tolerate before image quality degrades unacceptably. The GUI should let him sweep WFE RMS and immediately see the impact on Strehl, MTF, EE, RER, and NIIRS — and run his actual Zernike prescription, not just the scalar total.

## Step-by-Step GUI Workflow

### Step 1: Load System Configuration
- Load from spreadsheet or enter parameters manually
- Key inputs in user-native units:
  - Aperture: 40 [cm]
  - Focal length: 400 [cm]
  - Pixel pitch: 10.0 [um]
  - Band: 500--800 [nm]
  - Central obscuration: 35 [%]
  - WFE reference wavelength: 633 [nm]
- Display unit conversion confirmation panel
- Show derived parameters: GSD [m], IFOV [urad], Q [--], Airy disk [um]

### Step 2: Configure WFE Reference
- WFE reference wavelength: 633 [nm] (HeNe interferometry default)
- WFE input mode selector: Scalar RMS / Zernike / OPD Map
  - Tooltip: "Scalar RMS: total WFE as single number. Zernike: individual coefficient input. OPD Map: measured wavefront."
  - Scalar RMS and Zernike are functional (Zernike via API-level `WavefrontError` injection; the GUI performs the injection — no YAML path yet); OPD Map is future
- Operating wavelength display: auto-computed from filter band center
- Show Marechal Strehl formula: S = exp(-(2*pi*OPD_rms/lambda)^2)

### Step 3: Import Zernike Coefficients (Gap 26 closed)
- **Import from Zemax button** (live): calls
  `radiant.io.zemax_zernike.load_zemax_zernike` on the "Zernike Standard
  Coefficients" .txt export (`tom_zernike_zemax.txt`); handles UTF-16/UTF-8
  encodings, validates Noll indices, captures the reference wavelength;
  parse errors surface as actionable dialogs
- Table view of parsed terms Z4–Z15:
  - Columns: Index, Name, Coefficient [waves], Variance share [%]
  - Auto-compute RSS total at bottom (0.0513 waves)
- **ErrorBudget panel** (Gaps 23+28): allocation input (λ/14 = 0.0714 waves),
  live RSS total, within/over-budget status, linear margin (+0.0201), and RSS
  headroom (`remaining_allocation()` = 0.0497 waves) with a tooltip explaining
  why the quadrature headroom exceeds the linear margin
- Run mode: "Zernike (as-built)" evaluates the actual prescription; "Scalar
  RMS" uses the total for the budget sweep

### Step 4: Configure WFE Sweep
- Sweep control:
  - WFE RMS range: 0.000 to 0.250 [waves] (editable)
  - Sweep points: [0, 0.02, 0.04, 0.06, 0.071, 0.08, 0.10, 0.12, 0.14, 0.16, 0.18, 0.20, 0.25]
  - Add/remove custom points
  - Highlight lambda/14 = 0.071 in green
- "Run Sweep" button
- Progress bar: "Evaluating WFE = X / 0.250 waves..."

### Step 5: Strehl vs WFE Plot
- Primary plot: Strehl ratio vs WFE RMS
- Two curves:
  - RADIANT Strehl (at operating wavelength)
  - Marechal reference (at 633 nm)
- Horizontal line: Strehl = 0.80 (diffraction-limited threshold)
- Vertical line: WFE = lambda/14 = 0.071 waves
- Tom's Zernike point marked with star: "Tom's design: 0.051 waves, S = 0.90"
- Interactive: hover shows exact values, click to see full result

### Step 6: Spatial Metrics Panel (MTF, EE, RER)
- Three-panel plot:
  - Left: MTF@Nyquist vs WFE RMS
  - Center: EE(1x1) and EE(3x3) vs WFE RMS
  - Right: RER vs WFE RMS
- Color-coded quality regions:
  - Green: diffraction-limited (WFE < 0.071)
  - Yellow: acceptable (0.071--0.10)
  - Orange: degraded (0.10--0.15)
  - Red: severe (> 0.15)
- Interactive: click any point to see full MTF curve at that WFE

### Step 7: MTF Curve Family Plot
- Full MTF vs spatial frequency at selected WFE values
- Overlaid curves with color gradient (viridis):
  - WFE = 0, 0.04, 0.071, 0.10, 0.15, 0.20, 0.25
- Nyquist frequency marked with vertical dashed line
- Diffraction-limited envelope for reference
- Interactive: slider to select WFE and highlight that curve

### Step 8: NIIRS vs WFE Plot
- NIIRS vs WFE RMS
- Baseline NIIRS marked with green line
- Threshold lines: -0.5 NIIRS (orange), -1.0 NIIRS (red)
- Lambda/14 vertical line
- Annotation: "WFE budget for < 0.5 NIIRS loss: X waves"
- Tom's Zernike point marked

## Interactive Features

### WFE Budget Calculator
- **Target NIIRS input**: "I need NIIRS > X" → auto-compute max WFE
- **Target Strehl input**: "I need Strehl > 0.80" → shows WFE < 0.071
- **Reverse lookup**: given NIIRS requirement, show WFE allocation

### Sensitivity Sliders
- **f-number slider**: adjust from f/4 to f/16
  - Shows how Q changes, affecting MTF and EE sensitivity to WFE
- **Pixel pitch slider**: 5--30 um
  - Shows sampling regime transition
- **Obscuration slider**: 0--50%
  - Shows MTF impact of central obscuration combined with WFE
- **Operating wavelength slider**: shows Strehl at different bands
  - Same WFE in waves, different impact at different wavelengths

### Wavelength Sensitivity Panel
- Show Strehl vs WFE at multiple operating wavelengths:
  - 500 nm (VNIR short), 650 nm (VNIR center), 800 nm (VNIR long), 4.0 um (MWIR)
- Demonstrates why the same WFE is more damaging at shorter wavelengths
- Toggle: "Show at reference wavelength" vs "Show at operating wavelength"

### Zernike Allocation Tool (now feasible — Zernike-to-PSF closed)
- Individual coefficient sliders (Z4-Z15), real-time PSF update from the
  actual modal mix
- ErrorBudget variance shares show which Zernike term dominates (spherical
  34.2%, coma-Y 23.7% for Tom's prescription)
- "What if I reduce coma by 0.01 waves?" → NIIRS change
- Comparison card: "Zernike (actual) vs scalar screen at same RMS" — the
  Step 5b table (ΔRER +0.0285, ΔNIIRS +0.07), so users see what the shape
  assumption costs

### Design Summary Panel
- Auto-generated recommendation:
  - "Diffraction limit: WFE < 0.071 waves (Strehl > 0.80)"
  - "NIIRS-driven budget: WFE < 0.100 waves (dNIIRS < 0.5)"
  - "Tom's current design: 0.0513 waves (Zernike mode: Strehl = 0.92, dNIIRS = −0.08; 0.0497 waves RSS headroom vs λ/14)"
- Export: PDF report, Excel spreadsheet

### Performance Metrics Dashboard
- **Script window commands**:
  ```
  >> result.metrics["strehl"]          # Marechal Strehl at operating band center
  >> result.metrics["mtf_at_nyquist"]
  >> result.metrics["rer"]              # relative edge response
  >> result.metrics["fwhm_x_m"]         # PSF FWHM (meters on detector)
  >> result.metrics["niirs"]            # GIQE-5 NIIRS
  >> result.metrics["q_center"]         # sampling factor
  >> [(nt.name, nt.value_e) for nt in result.noise_terms]
  ```
- Metric cards: Strehl, MTF@Nyquist, RER, EE(1x1), EE(3x3), NIIRS, SNR
- Dual-path consistency indicator: FFT of convolved PSF vs MTF product (must agree to ~1e-6)

## Display Requirements
- All numerical values must include units
- Dual-unit display where applicable:
  - WFE: waves and nm OPD
  - GSD: m and ft
  - Pixel pitch: um and mm
- Color-coded quality bands throughout
- Strehl scale always 0--1.0
- NIIRS shows absolute value and delta from baseline

## Interpolated-atmosphere availability

Switching **Atmosphere → Model** to `interpolated` works first try on this scene. The picker pre-selects **`midlat_summer_sensor_ladder`** (profile `midlat_summer`, down-looking; covers ground targets only (target altitude fixed at 0 km), sensor 3-100 km plus 40000 km (GEO), nadir only (LOS zenith 0 degrees)); *Use this family* writes `atmosphere.interpolation_axes = 'sensor_altitude_m'`. `Sensor.atmosphere_family_suggestion()` is the same answer from a script.
