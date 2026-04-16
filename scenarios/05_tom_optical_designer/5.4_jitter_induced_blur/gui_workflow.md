# Scenario 5.4 GUI Workflow: Jitter Tolerance — Line-of-Sight Stability Requirements

## Persona
Tom, optical designer. He has a VNIR panchromatic imager (50 cm, f/10, 8 um CCD) on a 500 km SSO. He needs to derive the jitter requirement: how much line-of-sight wander degrades NIIRS by 0.5 and 1.0 grades? He thinks in terms of focal-plane blur (pixels and um), not just angular jitter (urad).

## Step 1: Import Sensor Configuration
- **Action**: File > Import Spreadsheet
- **Input**: `tom_jitter_tolerance_data.xlsx` (3-sheet workbook)
- **GUI components**:
  - Sheet selector: "Optical System" maps to optics + geometry + scene
  - "Detector & Readout" maps to detector + readout + spectral_integration
  - "Jitter Sweep" maps to sweep definition, thresholds, and jitter source reference table
  - **Unit conversion highlights**:
    - Aperture diameter: 50.0 cm -> 0.50 m (/ 100)
    - Focal length: 500.0 cm -> 5.00 m (/ 100)
    - Optical transmission: 70% -> 0.70 (/ 100)
    - Optics temperature: 20 C -> 293.15 K (+273.15)
    - Filter cut-on/off: 450/700 nm -> 0.450/0.700 um (/ 1000)
    - QE: 85% -> 0.85 (/ 100)
    - Integration time: 0.5 ms -> 0.0005 s (/ 1000)
    - Sensor altitude: 500 km -> 500,000 m (x 1000)
    - IPC coupling: 0.5% -> 0.005 (/ 100)
    - WFE RMS: 0.05 waves (no conversion)
    - Central obscuration: 30% -> 0.30 (/ 100)
  - **Derived parameter display**: GSD = 0.80 m, Q = 0.72 (undersampled), IFOV = 1.6 urad, Airy = 14.0 um (1.75 pix)

## Step 2: Configure Jitter Sweep
- **Action**: Analysis > Jitter Tolerance Study
- **GUI components**:
  - **Sweep parameters panel**:
    - Jitter RMS range: 0--5.0 urad, 51 points (linear)
    - Slider with dual-unit display: urad and pixels (linked through focal length)
    - "Auto-range" button: runs quick coarse sweep to find the interesting range
  - **Performance thresholds panel**:
    - delta_NIIRS = -0.5 threshold (orange line on preview)
    - delta_NIIRS = -1.0 threshold (red line on preview)
    - NIIRS = 6.0 absolute floor (dark red line)
    - All editable with drag handles on preview axes
  - **Jitter source reference table**: Imported from spreadsheet, showing typical RMS and frequency for each source (reaction wheel, solar array, cryocooler, structural modes, ACS residual, thermal snap). Read-only reference during sweep configuration.
  - **Physics note banner**: "Jitter affects MTF and RER but NOT SNR. NIIRS changes only through the RER and edge sharpness terms."

## Step 3: Run Baseline + Sweep
- **Action**: Click "Run Jitter Tolerance"
- **GUI shows**:
  - Phase 1: RADIANT baseline evaluation (single run, zero jitter) with progress spinner
  - Phase 2: Analytic jitter degradation (51 points, instant -- no RADIANT re-evaluation needed)
  - **Live-updating curves**: NIIRS vs. jitter and MTF vs. jitter populate as phase 2 computes
  - **Threshold crossing markers**: appear on curves as soon as interpolated jitter value is found
  - **Baseline results banner**: SNR = 68.7, GSD = 0.80 m, RER = 0.649, MTF@Nyq = 0.373, NIIRS = 6.49

## Step 4: NIIRS vs. Jitter Visualization
- **Action**: View > NIIRS Degradation
- **GUI components (main chart + sidebar)**:
  1. **NIIRS vs. Jitter RMS**: Line plot with jitter on x-axis (urad) and NIIRS on y-axis. Three horizontal threshold lines: delta_NIIRS = -0.5 (orange), delta_NIIRS = -1.0 (red), NIIRS = 6.0 floor (dark red). Vertical annotation lines at threshold crossings with values labeled.
  2. **Secondary x-axis**: sigma_fp in pixels shown on top axis, so Tom sees both angular jitter and focal-plane blur simultaneously.
  3. **delta_NIIRS annotation**: Text box showing "At 1.0 urad: NIIRS drops 0.51 grades (sigma = 0.62 pixels)"

- **Interactive features**:
  - Hover on curve: tooltip shows "Jitter = 0.8 urad, sigma = 0.50 pix, RER = 0.505, NIIRS = 6.13, delta_NIIRS = -0.36"
  - Drag threshold lines to explore different requirements
  - Toggle x-axis units: urad / pixels / fraction of IFOV
  - "Why is NIIRS so sensitive?" button: explanation panel shows GIQE-5 RER term dominance

## Step 5: MTF and RER Degradation
- **Action**: View > MTF Analysis
- **GUI components (3 panels)**:
  1. **MTF & RER vs. Jitter**: Dual-line plot showing system MTF@Nyquist (blue) and RER (red) vs. jitter. Also shows isolated jitter MTF (green dashed) to separate jitter contribution from system MTF.
  2. **MTF Curves at Selected Jitter Levels**: Family of MTF(f) curves from 0 to 5 urad, showing how the spatial frequency response collapses with jitter. Vertical line at Nyquist frequency. x-axis normalized to f/f_Nyquist.
  3. **MTF Budget Table**: Tabular breakdown showing optics MTF, detector MTF, jitter MTF, and system MTF at Nyquist for each selected jitter level.

- **Interactive features**:
  - Click on any jitter level in the family-of-curves plot: highlights that curve and shows detailed values
  - "Show MTF at..." slider: drag to any jitter value and see the full MTF curve update
  - Hover on MTF curve: tooltip shows "f = 0.5 x f_Nyq, MTF_system = 0.72, MTF_jitter = 0.95, MTF_optics = 0.85"
  - Toggle between linear and log-y MTF display

## Step 6: Jitter in Physical Context
- **Action**: View > Physical Context
- **GUI components**:
  - **Context table**: Shows jitter at key reference points (0.2, 0.5, 1.0, 1.6, 2.0, 3.0, 5.0 urad) with columns for fraction of IFOV, sigma in pixels, MTF@Nyquist, and delta_NIIRS
  - **Jitter source overlay**: Horizontal bars showing typical jitter range for each source (reaction wheel 1--5 urad, solar array 0.5--2 urad, etc.) overlaid on the NIIRS vs. jitter curve. Color-coded by severity relative to the budget.
  - **"Budget ruler"**: Visual bar showing the 1.0 urad total budget with sub-allocations for each source

- **Interactive features**:
  - Click on a jitter source bar: shows its typical range, frequency, and notes
  - "RSS calculator": enter jitter values for each source, see total RSS and resulting delta_NIIRS
  - Drag source allocation sliders: total RSS updates in real time with green/yellow/red indicator

## Step 7: GIQE-5 Decomposition
- **Action**: Analysis > NIIRS Breakdown
- **GUI components**:
  - **Term decomposition bar chart**: Shows contribution of each GIQE-5 term at baseline and at selected jitter level:
    - Constant: +9.57
    - GSD term: -3.32 x log10(GSD_inch) = -3.32 x log10(31.5) = -4.98
    - RER term: +3.32 x log10(RER) varies from -0.62 (baseline) to deeper negative with jitter
    - SNR term: +1.559 x log10(68.7) = +2.86 (unchanged by jitter)
    - H, G terms: small contributions
  - **Side-by-side comparison**: Baseline vs. jittered GIQE-5 breakdown, highlighting that only the RER term changes
  - **Sensitivity panel**: d(NIIRS)/d(RER) = 3.32/(RER x ln(10)) -- shows how steep the RER sensitivity is near the operating point

- **Interactive features**:
  - Jitter slider: adjust jitter and see GIQE-5 terms update in real time
  - "What limits NIIRS?" flag: identifies RER as the jitter-degraded term, GSD as the baseline limiter
  - "What if GSD were...?" slider: shows how the baseline NIIRS changes with GSD (independent of jitter)

## Step 8: Export Results
- **Action**: File > Export Results
- **Options**:
  - Excel workbook: Jitter Sweep (51 rows), Thresholds, Summary (3 sheets)
  - PDF report: NIIRS vs. jitter curve, MTF degradation, threshold table, jitter source context
  - PowerPoint slide: single-slide jitter budget summary for design review
  - CSV of sweep data for external plotting
  - YAML snapshot of sensor configuration (reproducibility)

## Key GUI Features Exercised
1. **Dual-unit display** -- jitter shown simultaneously in urad, pixels, and fraction of IFOV
2. **Analytic computation** -- only 1 RADIANT run needed; jitter degradation is computed analytically, making the sweep essentially instant
3. **Threshold-crossing finder** -- automatic interpolation to find jitter values at delta_NIIRS = -0.5 and -1.0
4. **MTF family of curves** -- visualizing spatial frequency response collapse with increasing jitter
5. **Jitter source overlay** -- mapping typical spacecraft jitter sources onto the tolerance curve
6. **RSS budget calculator** -- interactive allocation of jitter budget across sources
7. **GIQE-5 term decomposition** -- showing which term drives NIIRS and how jitter only affects RER
8. **"Why?" explanation panels** -- contextual physics explanations (long focal length amplification, jitter vs. noise independence)
9. **Auto-range detection** -- automatic sweep range selection based on quick coarse sweep
