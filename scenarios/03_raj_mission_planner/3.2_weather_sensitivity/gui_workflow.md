# Scenario 3.2 GUI Workflow: Weather Sensitivity — How Bad Can the Weather Get?

## Persona
Raj, mission planner. He has a baselined MWIR reconnaissance sensor on a 500 km SSO. He needs a "go/no-go" weather table: at what visibility and water vapor does NIIRS drop below 4.0? He thinks in named weather conditions (clear, haze, tropical) and wants traffic-light tables for briefings.

## Step 1: Import Sensor Configuration
- **Action**: File > Import Spreadsheet
- **Input**: `raj_weather_sensitivity_data.xlsx` (3-sheet workbook)
- **GUI components**:
  - Sheet selector: "Sensor Configuration" maps to optics + detector + readout
  - "Atmosphere & Geometry" maps to observation geometry + atmosphere baseline + scene
  - "Sweep Definition" maps to sweep ranges, requirements, and named conditions table
  - **Unit conversion highlights**:
    - Aperture diameter: 30.0 cm → 0.30 m (÷ 100)
    - Focal length: 120.0 cm → 1.20 m (÷ 100)
    - Optical transmission: 75% → 0.75 (÷ 100)
    - Optics temperature: 20°C → 293.15 K (+273.15)
    - QE: 70% → 0.70 (÷ 100)
    - Integration time: 1.0 ms → 0.001 s (÷ 1000)
    - Sensor altitude: 500 km → 500,000 m (× 1000)
    - Off-nadir angle: 0° → 0 rad (× π/180)
    - IPC coupling: 1.5% → 0.015 (÷ 100)
  - **Named conditions table import**: GUI recognizes the 8-row weather table and creates named presets
  - **Derived parameter display**: GSD = 7.5 m, Q = 0.93 (undersampled), Airy disk = 41 µm

## Step 2: Configure Weather Sweep
- **Action**: Analysis > Weather Sensitivity Study
- **GUI components**:
  - **Sweep parameters panel**:
    - Visibility range: 2–100 km, 25 points (log-spaced toggle)
    - PWV range: 0.5–5.0 cm, 15 points (linear toggle)
    - Standard atmosphere profile selector: midlat_summer (dropdown)
    - Aerosol type selector: rural (dropdown)
  - **Performance requirements panel**:
    - NIIRS threshold: 4.0 (red line on plots)
    - NIIRS goal: 5.0 (green line on plots)
    - Both editable with drag handles on preview axes
  - **Named conditions list**: Imported from spreadsheet, each with checkbox for include/exclude
  - **2D grid configuration**: Select which visibility and PWV values for the 2D contour
  - **Evaluation count preview**: "25 + 15 + 8 + 36 = 84 evaluations"

## Step 3: Run Sweep
- **Action**: Click "Run Weather Sensitivity"
- **GUI shows**:
  - Progress bar: 84 evaluations with 4 phases (vis sweep → PWV sweep → named conditions → 2D grid)
  - Live-updating curves: NIIRS vs. visibility and NIIRS vs. PWV plots populate in real time
  - Intermediate results: table rows appear as each evaluation completes
  - **Go/No-Go counter**: "32/36 GO" updating as 2D grid fills in

## Step 4: Visibility Sensitivity Visualization
- **Action**: View > Visibility Analysis
- **GUI components (3 interactive charts)**:
  1. **NIIRS vs. Visibility**: Line plot with log-x axis. Horizontal lines at NIIRS = 4.0 (red, labeled "threshold") and 5.0 (green, labeled "goal"). Intersection point annotated if it exists. Shaded green region above threshold.
  2. **SNR vs. Visibility**: Secondary plot showing how SNR varies with visibility. Annotation: "SNR varies only 2% across full visibility range."
  3. **Transmittance vs. Visibility**: Band-mean τ_atm plotted on same x-axis, showing atmospheric transmission curve.

- **Interactive features**:
  - Hover on NIIRS curve: tooltip shows "At 10 km visibility: NIIRS = 4.47, SNR = 337.1, τ = 0.515"
  - Drag threshold line up/down to explore different requirements
  - Click "Why is NIIRS flat?" button: explanation panel shows that MWIR aerosol extinction is ~13× weaker than visible due to Angstrom exponent
  - Toggle between visibility units: km, miles, nautical miles

## Step 5: PWV Sensitivity Visualization
- **Action**: View > Water Vapor Analysis
- **GUI components (3 interactive charts)**:
  1. **NIIRS vs. PWV**: Line plot showing NIIRS degradation with increasing water vapor. ΔNIIRS annotation from driest to wettest.
  2. **Transmittance vs. PWV**: Band-mean τ drops from 0.79 to 0.11 — dramatic 7× reduction. Highlighted as the dominant atmospheric effect.
  3. **Signal Breakdown vs. PWV**: Stacked area chart showing how target signal, background signal, and path radiance change with PWV.

- **Interactive features**:
  - PWV slider: drag to see all metrics update in real time
  - Hover on τ curve: "At PWV = 3.0 cm, τ = 0.25 — 75% of target signal absorbed"
  - "Why doesn't NIIRS track τ?" button: explanation that NIIRS ∝ log₁₀(SNR), and noise also decreases with τ, muting the effect
  - Named condition markers overlaid on curve (vertical lines at PWV = 0.5, 0.8, 1.0, 1.4, etc.)

## Step 6: Go/No-Go Weather Table
- **Action**: View > Go/No-Go Assessment
- **GUI components**:
  - **Traffic-light table**: Named conditions as rows, with green/yellow/red cells for NIIRS
    - Green: NIIRS ≥ goal (5.0)
    - Yellow: NIIRS ≥ threshold (4.0) but < goal
    - Red: NIIRS < threshold
  - **2D heatmap**: Visibility (y-axis) × PWV (x-axis), cells colored by NIIRS value. Contour lines at NIIRS = 4.0 and 5.0 overlaid.
  - **Summary banner**: "GO at all 8 named conditions. NIIRS goal (5.0) NOT achievable — limited by 7.5 m GSD."
  - **Weather-robustness score**: "Total NIIRS variation: 0.18 across all conditions — sensor is weather-robust"

- **Interactive features**:
  - Click any table cell: drill down to full noise budget at that condition
  - Toggle "Show SNR" / "Show NIIRS" / "Show τ" in heatmap
  - Drag contour lines to explore different thresholds
  - Export traffic-light table as PowerPoint slide (briefing format)

## Step 7: NIIRS Budget Analysis
- **Action**: Analysis > NIIRS Breakdown
- **GUI components**:
  - **GIQE-5 term decomposition bar chart**: Shows contribution of each term:
    - Constant: +9.57
    - GSD term: −3.32 × log₁₀(295.3 in) = −8.20 ← dominates
    - RER term: +3.32 × log₁₀(0.708) = −0.50
    - SNR term: +1.559 × log₁₀(338) = +3.94
    - H term: −0.334 × H
    - G term: −0.01 × G
  - **"What limits NIIRS?" panel**: Highlights GSD as the binding constraint. Shows that even infinite SNR can only reach NIIRS ≈ 4.9 at this GSD.
  - **"How to reach NIIRS = 5.0" recommendation**: "Reduce GSD to ≤ 2.5 m (requires focal length ≥ 3.6 m or lower orbit)"

- **Interactive features**:
  - "What if GSD were...?" slider: adjust GSD and see NIIRS update
  - "What if SNR were...?" slider: shows diminishing returns of SNR improvement
  - Side-by-side: best weather vs. worst weather NIIRS breakdown

## Step 8: Export Results
- **Action**: File > Export Results
- **Options**:
  - Excel workbook: Visibility Sweep, PWV Sweep, Named Conditions (with traffic-light formatting), 2D NIIRS Grid (4 sheets)
  - PDF briefing report: go/no-go table, NIIRS vs. visibility/PWV curves, 2D heatmap
  - PowerPoint slide: single-slide traffic-light summary for program review
  - CSV of all sweep data for external plotting
  - YAML snapshot of sensor configuration (reproducibility)

## Key GUI Features Exercised
1. **Named weather presets** — importing and using descriptive condition names (clear, haze, tropical) instead of raw numbers
2. **Traffic-light go/no-go table** — automatic pass/fail assessment with color-coded cells
3. **2D heatmap with contour overlay** — visibility × PWV parameter space with NIIRS contours
4. **GIQE-5 term decomposition** — showing which term dominates NIIRS and what limits improvement
5. **"Why?" explanation panels** — contextual physics explanations for non-obvious results (MWIR weather robustness)
6. **Threshold-crossing finder** — automatic detection of critical parameter values
7. **Briefing-ready export** — PowerPoint-formatted traffic-light table for program reviews
8. **Weather-robustness score** — quantifying how much NIIRS varies across weather conditions
9. **"What-if" sliders** — exploring GSD and SNR impact on NIIRS without rerunning evaluations
