# Scenario 2.5 GUI Workflow: Well Capacity Optimization — Integration Time vs. Dynamic Range

## Persona
Mike, detector engineer. He has a 640x512 MWIR HgCdTe FPA with 2M e- FWC in an f/2 ground-based surveillance system. He wants to find the optimal integration time that gives adequate SNR on cold sky targets (200 K) without saturating on hot jet exhaust plumes (1500 K).

## Step 1: Import Detector & System Data
- **Action**: File > Import Spreadsheet
- **Input**: `mike_well_capacity_data.xlsx` (3-sheet workbook)
- **GUI components**:
  - Sheet selector: "Detector Specs" maps to detector + readout parameters
  - "Optics & Scene" maps to optics, spectral band, and scene configuration
  - "Trade Requirements" maps to sweep definition and performance requirements
  - **Unit conversion highlights**:
    - Aperture diameter: 20.0 cm → 0.20 m (÷ 100)
    - Focal length: 40.0 cm → 0.40 m (÷ 100)
    - Optical transmission: 80% → 0.80 (÷ 100)
    - Optics temperature: 20°C → 293.15 K (+273.15)
    - Filter edges: 3500/5000 nm → 3.50/5.00 µm (÷ 1000)
    - QE: 72% → 0.72 (÷ 100)
    - Integration time range: 0.001/50 ms → 1e-6/0.05 s (÷ 1000)
    - IPC coupling: 1.0% → 0.01 (÷ 100)
  - **Scene temperature table import**: GUI recognizes the 10-row temperature table and creates a multi-target sweep
  - **Trade requirements panel**: Shows extracted SNR threshold (10), max well fill (70%), saturation limit (90%), sweep definition (50 log-spaced points)

## Step 2: Configure Trade Study
- **Action**: Analysis > Integration Time Trade Study
- **GUI components**:
  - Sweep parameter selector: "Integration time" (pre-selected from spreadsheet)
  - Range inputs: min = 1 µs, max = 50 ms (from spreadsheet, editable)
  - Spacing toggle: "Log-spaced" (selected) / "Linear"
  - Number of points slider: 50
  - Scene temperature list: 10 temperatures from spreadsheet, checkboxes to include/exclude
  - **Performance constraints panel**:
    - Min SNR for cold target: 10 (with temperature selector: 200 K)
    - Max well fill for hot target: 70% (with temperature selector: 1500 K)
    - Saturation limit: 90%
  - **Evaluation count preview**: "10 temperatures × 50 integration times = 500 evaluations"
  - **Estimated time**: progress indicator based on single-eval timing

## Step 3: Run Sweep
- **Action**: Click "Run Trade Study"
- **GUI shows**:
  - Progress bar: 500 evaluations with temperature × t_int matrix visualization
  - Live-updating heatmap: well fill [%] colored by saturation status (green < 70%, yellow 70-90%, red > 90%)
  - **Real-time results** as each temperature column completes:
    - Well fill vs. t_int curve
    - SNR vs. t_int curve
  - Abort button: stops sweep, keeps completed results
  - ETA based on completed evaluations

## Step 4: Well Fill Visualization
- **Action**: View > Well Fill Analysis
- **GUI components (3 interactive charts)**:
  1. **Well Fill Heatmap**: t_int (x-axis) vs. scene temperature (y-axis), color = well fill [%]. Saturation boundary (90%) shown as contour line. 70% boundary shown as dashed contour.
  2. **Well Fill vs. t_int (line plot)**: One curve per scene temperature, colored by temperature. Horizontal lines at 70% and 90% thresholds. Vertical line at user-selected operating point.
  3. **Well Fill Bar Chart**: At selected t_int, bar chart showing well fill for each temperature. Bars colored green/yellow/red by saturation status. FWC = 2M e- labeled on y-axis.

- **Interactive features**:
  - Click on heatmap cell: tooltip shows "400 K at 100 µs → 63.5% well fill (1,270,000 e- / 2,000,000 e-)"
  - Drag vertical cursor on line plot to select operating t_int — bar chart updates in real time
  - Click any temperature curve to highlight it and dim others
  - Toggle "Show signal [e-]" vs. "Show well fill [%]" on y-axis
  - Saturation indicator: cells/bars that hit FWC show skull icon with "SATURATED"

## Step 5: SNR Analysis
- **Action**: View > SNR Analysis
- **GUI components (2 interactive charts)**:
  1. **SNR vs. t_int for Cold Target**: SNR curve for 200 K with horizontal threshold line at SNR = 10. Intersection point annotated: "SNR ≥ 10 at t_int ≥ 2.83 ms". Shaded region below threshold = "insufficient SNR".
  2. **Dynamic Range Window**: For each t_int, shows the range of temperatures that satisfy BOTH constraints (SNR ≥ 10 on coldest AND well fill < 90% on hottest). Window width = achievable dynamic range.

- **Interactive features**:
  - Drag SNR threshold line up/down to explore different requirements
  - Hover on dynamic range window: shows "At 1 ms: can detect 200–300 K (Δ = 100 K)"
  - Temperature range selector: choose which temperature defines "cold" and "hot" ends
  - Toggle between SNR [—] and NEDT [mK] y-axis (dual metrics)

## Step 6: Noise Budget Comparison
- **Action**: View > Noise Breakdown
- **GUI components (2 interactive charts)**:
  1. **Stacked Bar — Noise by Term**: Side-by-side comparison of cold target (200 K) and warm target (400 K) at selected t_int. Each noise term as a separate color. Background_shot and signal_shot highlighted as the two that swap dominance.
  2. **Noise Regime Transition**: Signal_shot fraction [%] vs. scene temperature curve. Horizontal lines at 50% (mixed), crossover temperature annotated. Regions labeled: "BLIP (background-limited)" and "Signal-shot-limited".

- **Interactive features**:
  - Temperature slider: drag to see noise breakdown evolve from BLIP → signal-limited
  - Click any noise bar: expands to show formula, parameter values, and σ [e- RMS]
  - Integration time selector: switch between t_int values and see noise bars update
  - Hover on regime transition curve: tooltip shows "At 350 K: signal_shot = 45% of noise variance"
  - "What if FWC were larger?" slider: increase FWC and see saturation boundary move

## Step 7: Optimal Operating Point
- **Action**: Analysis > Find Optimal Integration Time
- **GUI components**:
  - **Trade-off summary table**:
    | Scene Temp [K] | t_int for 70% fill | SNR at that t_int [—] |
    |---|---|---|
    | 200 | ~256 ms (extrapolated) | — |
    | 280 | 3.53 ms | 841 |
    | 400 | 103 µs | 1231 |
    | 1000 | < 1 µs (saturated) | — |
  - **Feasibility indicator**: Green checkmark for temperatures that can be imaged, red X for always-saturated
  - **Recommendation panel**: "At t_int = 1 ms: SNR(200 K) = 6.6 (FAIL). At t_int = 2.83 ms: SNR(200 K) = 11.1 (PASS), but max unsaturated temp = 280 K."
  - **Solution suggestions**: expandable cards for HDR, dual-integration, spectral narrowing, gain switching — each with a "Simulate this" button that opens a new analysis mode

## Step 8: Performance Metrics Dashboard
- **Action**: View > Performance Metrics
- **Script window commands**:
  ```
  >> result.metrics["well_margin_dB"]    # headroom before saturation
  >> result.metrics["dynamic_range_dB"]  # sensor dynamic range
  >> result.metrics.get("niirs")          # None for ground-based
  >> [(nt.name, nt.value_e) for nt in result.noise_terms]
  ```
- **GUI components**:
  - Well margin gauge (dB headroom, color-coded)
  - Dynamic range display (dB)
  - Per-pixel saturation map (if available)
  - Noise-term bar chart with BLIP indicator

## Step 9: Export Results
- **Action**: File > Export Results
- **Options**:
  - Excel workbook: Well Fill Sweep, SNR Sweep, Noise Comparison, Summary (4 sheets)
  - PDF report with heatmap, SNR curves, noise breakdown, and recommendation
  - CSV of full sweep data (500 rows) for external plotting
  - YAML snapshot of system configuration (reproducibility)
  - PNG/SVG of individual charts for presentations

## Key GUI Features Exercised
1. **Multi-parameter sweep engine** — 500 evaluations across 2 dimensions (t_int × temperature) with live progress
2. **Heatmap visualization** — 2D parameter space with saturation contours and interactive cell tooltips
3. **Dynamic range window** — visual representation of achievable temperature range vs. integration time
4. **Noise regime transition** — interactive visualization of BLIP → signal-limited crossover
5. **Feasibility assessment** — automatic detection of physically impossible operating points (always-saturated)
6. **Side-by-side noise comparison** — contrasting noise budgets at different scene temperatures
7. **"What-if" sliders** — drag FWC, SNR threshold, well fill limit to explore design space
8. **Solution recommendation cards** — suggesting HDR modes, spectral narrowing when single-frame DR is insufficient
9. **Spreadsheet-driven trade study** — importing sweep definition, requirements, and scene temperatures from Excel

## Interpolated-atmosphere availability

No bundled interpolated-atmosphere family serves this scene: 'midlat_summer_sensor_ladder' covers sensor_altitude 3 km to 40000 km; this scene asks for 1 m, below the family's runs. Switching **Atmosphere → Model** to `interpolated` therefore produces exactly one Messages-rail advisory saying so — not a sequence of refusals — and the scene stays on `atmosphere.model = 'simple'`, which serves any geometry.
