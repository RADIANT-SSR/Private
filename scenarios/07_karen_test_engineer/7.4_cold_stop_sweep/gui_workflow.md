# Scenario 7.4 GUI Workflow: Cold Stop Efficiency Sweep

## Persona
Karen, test engineer. Running a TVAC background characterization test. She has an instrument spec sheet, lab background measurements at several cold stop positions (recorded in DN and e-), and system performance requirements. She wants to determine the effective cold stop leakage and whether it meets requirements.

## Step 1: Import Instrument Data
- **Action**: File > Import Spreadsheet
- **Input**: `karen_cold_stop_data.xlsx` (3-sheet workbook)
- **GUI components**:
  - Sheet selector: user picks which sheet maps to which parameter group
  - Column mapper: drag-and-drop columns to RADIANT parameters
  - Unit detection: GUI reads "cm", "mm", "%", "°C", "fA/pixel", "nm", "ms" from the Unit column and auto-selects conversion
  - Preview panel: shows converted values in RADIANT canonical units with green/red validation indicators
  - "Instrument Spec Sheet" maps to optics + detector + readout + source parameters
  - "Background Measurements" is stored as reference data (not sensor config)
  - "Performance Requirements" is stored as threshold definitions
  - **Unit conversion highlights**:
    - Aperture: 25 cm -> 0.25 m (÷ 100)
    - Focal length: 1000 mm -> 1.0 m (÷ 1000)
    - Optics temp: 20 °C -> 293.15 K (+ 273.15)
    - Dark current: 80 fA/pixel -> 499 e-/s (× 1e-15 ÷ q_e)
    - Band edges: 3700-4800 nm -> 3.70-4.80 µm (÷ 1000)
    - Integration time: 8 ms -> 0.008 s (÷ 1000)
    - Transmission: 68% -> 0.68 (÷ 100)
    - QE: 75% -> 0.75 (÷ 100)

## Step 2: Review and Validate Parameters
- **GUI components**:
  - Parameter panel organized by subsystem
  - Atmosphere model dropdown: "exo" selected (TVAC / vacuum, no atmospheric path)
  - Altitude field: 0 m (lab test, not orbital)
  - Cold stop efficiency slider: 0.0 to 1.0
  - **Convention warning**: tooltip on cold_stop_efficiency explaining that η = 0.0 means perfect cold stop (blocks all warm radiation), η = 1.0 means no cold stop (all warm radiation reaches FPA). This is opposite to the vendor convention where "100% efficient" means complete blocking.
  - Nearfield emission toggle: ON (required for cold stop analysis)
  - Unused parameter annotations: source distance flagged as "not used in extended regime"

## Step 3: Run Baseline Evaluations
- **Action**: Click "Evaluate" for two configurations
- **Config A** (blackbody illuminated): target = 308 K blackbody, background = 293 K shroud
- **Config B** (shuttered aperture): target = 77 K cold plate, background = 77 K cold plate
- **GUI shows**:
  - Side-by-side results cards
  - Config A: signal, SNR, nearfield, background, noise breakdown
  - Config B: nearfield only (scene contribution ≈ 0 at 77 K)
  - Regime badge: "Extended" for both configurations
  - Convention callout: "η_cold = 1.0 gives maximum nearfield (812,493 e-). Your design spec of 100% efficient cold stop corresponds to η_cold ≈ 0."

## Step 4: Cold Stop Sweep
- **Action**: Tools > Parameter Sweep > Cold Stop Efficiency
- **GUI components**:
  - Sweep parameter: `optics.cold_stop_efficiency`
  - Range slider: 0.00 to 1.00
  - Scene mode toggle: "Shuttered (background only)" selected — uses 77 K cold plate model
  - Metrics to track: checkboxes for Nearfield Signal [e-], Total Background [e-], SNR
  - Requirements overlay: horizontal threshold line at 40,000 e-
  - "Match lab measurements" toggle: overlay lab data points on the sweep curve

- **Results visualization**:
  - Line chart: η_cold (x-axis) vs. nearfield signal (y-axis) — linear relationship
  - Requirement threshold line: 40,000 e- (red)
  - Crossover point highlighted: η_cold = 0.049 where background = 40,000 e-
  - Lab measurement points overlaid as scatter markers with error bars
  - Each lab point annotated with matched η_cold value
  - Pass/fail zones shaded green/red

## Step 5: Lab Data Matching
- **Action**: Compare > Import Reference Data
- **GUI components**:
  - Import "Background Measurements" sheet as reference points
  - For each lab measurement, find the η_cold that produces matching background
  - Results table: Test Point | Position [mm] | Meas [e-] | Matched η_cold | Status
  - Scatter plot: cold stop position (mm) vs. matched η_cold (linear trend expected)
  - Statistical summary: η ranges from 0.044 (nominal) to 0.069 (2.5 mm offset)
  - Verdict panel: "Nominal alignment (CS-NOM) passes requirement. Offset ≥ 1.0 mm fails."

## Step 6: SNR Impact Assessment
- **Action**: Analysis > Compare Scenarios
- **GUI components**:
  - Side-by-side comparison at nominal η vs. anomalous η
  - Noise budget pie charts showing fraction from each source
  - Key finding callout: "Nearfield contributes < 1% of total noise variance at nominal alignment. Cold stop misalignment does NOT significantly degrade SNR."
  - Explanation: "The primary impact of cold stop leakage is on absolute background level, not SNR. For this system, signal shot noise and scene background noise dominate."

## Step 7: Export Results
- **Action**: File > Export Results
- **Options**:
  - Excel workbook with sweep data, lab comparison, and summary sheets
  - PDF report with charts and conclusions
  - Parameter snapshot (YAML) for reproducibility
- **Auto-generated summary**:
  - "Nominal cold stop leakage: η = 0.044 (35,500 e- background, PASS)"
  - "1.0 mm offset leakage: η = 0.054 (44,000 e- background, FAIL)"
  - "Maximum allowed leakage: η ≤ 0.049 (40,000 e- threshold)"

## Step 8: Review Performance Metrics Dashboard

**Script equivalent:** Accessing `result.metrics` for NEDT, NIIRS, GSD, Strehl, Q, MTF budget, well margin

**GUI interaction:**
- **Results Panel > Metrics tab** shows all computed performance metrics in a summary card:
  - SNR, Contrast SNR (dimensionless)
  - NEDT (mK) — now available via `result.metrics["nedt_K"]`
  - NIIRS (dimensionless) — now available via `result.metrics["niirs"]`
  - GSD cross-track, along-track, geometric mean (m)
  - MTF at Nyquist, Strehl ratio, Q parameter, EE(1x1), EE(3x3), RER
  - Well margin (dB), Dynamic range (dB)
- **MTF Budget sub-tab**: bar chart showing per-component MTF at Nyquist
- **Sweep Metrics tab**: NEDT and NIIRS plotted vs. cold_stop_efficiency alongside SNR
- Hover any metric for a tooltip showing the equation and intermediate values

**Script window commands:**
```python
result.metrics["nedt_K"]               # NEDT in Kelvin
result.metrics["niirs"]                # NIIRS rating
result.metrics["gsd_geometric_mean_m"] # GSD in meters
result.metrics["q_center"]             # sampling parameter
result.metrics["strehl"]               # Strehl ratio
result.metrics["well_margin_dB"]       # well margin in dB
mtf_budget = result.stage_outputs["performance"]["mtf_budget"]
mtf_budget.per_term_at_nyquist         # dict of all MTF component values
```

---

## Key GUI Features Exercised
1. **Non-standard unit conversion** — fA/pixel → e-/s, °C → K, nm → µm, mm → m
2. **Convention disambiguation** — vendor "100% efficient" ≠ RADIANT η = 1.0
3. **Dual-mode evaluation** — illuminated (SNR analysis) vs. shuttered (background characterization)
4. **Parameter sweep with lab data overlay** — match model to measurements
5. **Inverse problem** — find parameter value that matches a measured quantity
6. **Noise budget breakdown** — show that nearfield is not the dominant noise contributor
7. **Metrics dashboard** — NEDT, NIIRS, GSD, Strehl, Q, MTF budget, well margin displayed automatically
