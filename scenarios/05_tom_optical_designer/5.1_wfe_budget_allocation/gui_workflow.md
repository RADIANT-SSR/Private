# Scenario 5.1 GUI Workflow: WFE Budget Allocation

## Overview
Tom needs to determine how much wavefront error his 40 cm Cassegrain can tolerate before image quality degrades unacceptably. The GUI should let him sweep WFE RMS and immediately see the impact on Strehl, MTF, EE, RER, and NIIRS.

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
  - Note: only Scalar RMS is currently functional
- Operating wavelength display: auto-computed from filter band center
- Show Marechal Strehl formula: S = exp(-(2*pi*OPD_rms/lambda)^2)

### Step 3: Enter Zernike Coefficients (Reference Panel)
- Table input for Zernike terms Z4--Z15:
  - Columns: Index, Name, Coefficient [waves], Contribution [%]
  - Auto-compute RSS total at bottom
- Import from Zemax button (grayed out — not yet implemented)
- Tooltip: "Individual Zernike-to-PSF not yet implemented. Total RMS is used for scalar mode."
- Display: "Total Zernike RMS = 0.0513 waves → use this as scalar input"

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

### Zernike Allocation Tool (Future)
- When Zernike-to-PSF is implemented:
  - Individual coefficient sliders (Z4-Z15)
  - Real-time PSF update
  - Show which Zernike term dominates performance loss
  - "What if I reduce coma by 0.01 waves?" → NIIRS change

### Design Summary Panel
- Auto-generated recommendation:
  - "Diffraction limit: WFE < 0.071 waves (Strehl > 0.80)"
  - "NIIRS-driven budget: WFE < X waves (dNIIRS < 0.5)"
  - "Tom's current design: 0.051 waves (Strehl = 0.90, well within spec)"
- Export: PDF report, Excel spreadsheet

## Display Requirements
- All numerical values must include units
- Dual-unit display where applicable:
  - WFE: waves and nm OPD
  - GSD: m and ft
  - Pixel pitch: um and mm
- Color-coded quality bands throughout
- Strehl scale always 0--1.0
- NIIRS shows absolute value and delta from baseline
