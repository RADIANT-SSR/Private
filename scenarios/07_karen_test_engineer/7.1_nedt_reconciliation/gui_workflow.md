# Scenario 7.1 GUI Workflow: Predicted vs. Measured NEDT Reconciliation

## Persona
Karen, test engineer. She has TVAC NEDT measurements from an as-built MWIR sensor at seven blackbody temperatures. She wants to compare predicted vs. measured NEDT, break down the noise budget, identify the gap source, and determine which parameters have the most impact.

## Step 1: Import Lab Data
- **Action**: File > Import Spreadsheet
- **Input**: `karen_nedt_lab_data.xlsx` (3-sheet workbook)
- **GUI components**:
  - Sheet selector: "System Configuration" maps to optics + test setup
  - "As-Built Detector" maps to detector + readout parameters
  - "NEDT Measurements" maps to validation target data (measured NEDT at each temperature)
  - **Unit conversion highlights**:
    - Aperture diameter: 30.0 cm → 0.300 m (÷ 100)
    - Focal length: 121.5 cm → 1.215 m (÷ 100)
    - Optical transmission: 71% → 0.71 (÷ 100)
    - Optics temperature: 22°C → 295.15 K (+273.15)
    - Filter edges: 3500/5000 nm → 3.50/5.00 µm (÷ 1000)
    - QE: 68% → 0.68 (÷ 100)
    - Integration time: 0.5 ms → 0.0005 s (÷ 1000)
    - IPC coupling: 1.5% → 0.015 (÷ 100)
  - **Nominal vs. as-built table**: GUI highlights parameter deviations with color coding (red = degraded, green = improved)
  - **Atmosphere auto-detect**: GUI recognizes TVAC/lab context and suggests `"model": "exo"` (vacuum)

## Step 2: Configure Test Mode
- **Action**: Mode > Lab / TVAC Test
- **GUI components**:
  - Test mode selector: "Lab Blackbody" (sets atmosphere = exo, geometry = bench)
  - Blackbody configuration panel: temperature, emissivity, fill factor
  - Shroud/background panel: temperature, emissivity
  - Regime indicator: "Extended — blackbody fills pixel FOV"
  - Measurement import: table of (temperature, measured NEDT, σ, N frames)

## Step 3: Run NEDT Prediction
- **Action**: Click "Predict NEDT at All Temperatures"
- **GUI shows**:
  - Progress bar: evaluating 7 temperatures × 3 runs each (T, T+δ, T−δ for dS/dT)
  - Results table: BB Temp [K], Signal [e⁻], dS/dT [e⁻/K], σ_total [e⁻ RMS], Predicted NEDT [mK], Measured NEDT [mK], Δ [mK]
  - Well fill indicator per temperature (bar chart showing % FWC)
  - Warning if any temperature saturates the well

## Step 4: NEDT Comparison Visualization
- **Action**: View > NEDT Charts
- **GUI components (3 interactive charts)**:
  1. **NEDT vs. Temperature**: Predicted and measured curves with error bars (±σ), gap shaded between curves
  2. **Noise Breakdown (stacked bar)**: Per-term noise at selected temperature, click any bar to see NEDT_i contribution
  3. **Noise Pie Chart**: Fraction of total noise variance by term at selected temperature

- **Interactive features**:
  - Temperature slider: drag to see noise breakdown update in real time
  - Hover on gap region: tooltip shows Δ NEDT [mK] and σ_missing [e⁻ RMS]
  - Click any noise term: expands to show formula, parameter values, and what would change it
  - Toggle between NEDT [mK] and noise [e⁻ RMS] y-axis

## Step 5: Gap Analysis
- **Action**: Analysis > Reconcile with Measurement
- **GUI components**:
  - Input field: measured NEDT at primary test point (auto-filled from spreadsheet)
  - Gap computation panel:
    - σ_predicted [e⁻ RMS], σ_measured [e⁻ RMS], σ_missing [e⁻ RMS]
    - NEDT_missing [mK]
  - "What explains the gap?" table: each noise term with current σ, required σ to close gap, increase %, plausibility rating
  - Candidate explanation checklist: PRNU/DSNU, stray light, ROIC glow, calibration uncertainty — user checks which apply

## Step 6: Sensitivity Analysis
- **Action**: Analysis > Parameter Sensitivity
- **GUI components**:
  - Tornado chart: |Δ NEDT / 1% change| for each parameter, sorted by impact
  - Parameter perturbation slider: adjust ±range (default ±1%) and see updated sensitivities
  - Direction indicators: ↑ param → ↑ or ↓ NEDT
  - "What-if" mode: drag any parameter value and see NEDT update live
  - Nominal vs. as-built comparison panel: side-by-side NEDT with degradation breakdown

## Step 7: Export Results
- **Action**: File > Export Results
- **Options**:
  - Excel workbook: NEDT Comparison, Noise Breakdown, Sensitivity, Summary (4 sheets)
  - PDF report with NEDT curves, noise breakdown, tornado chart
  - CSV of predicted vs. measured for external plotting
  - YAML snapshot of as-built configuration (reproducibility)

## Key GUI Features Exercised
1. **Lab/TVAC test mode** — automatic exo atmosphere, bench geometry, blackbody configuration
2. **Predicted vs. measured overlay** — comparing model output against lab data with gap visualization
3. **Per-term NEDT breakdown** — drilling into which noise source dominates and by how much
4. **Gap analysis workflow** — computing missing noise σ and identifying candidate explanations
5. **Sensitivity tornado chart** — ranking parameters by NEDT impact for design guidance
6. **Nominal vs. as-built comparison** — quantifying performance degradation from spec deviations
7. **Unit conversion from lab conventions** — cm, %, nm, ms, °C all converted at import
