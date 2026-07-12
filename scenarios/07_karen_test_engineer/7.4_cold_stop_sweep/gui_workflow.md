# Scenario 7.4 GUI Workflow: Cold Stop Leakage Sweep

Refreshed 2026-07-07 (Phase R): parameter renamed to `optics.nearfield_fraction`
(Gap 12), inverse matching now uses `Sensor.solve_for` (Gap 10), scalar-mode
emissivity via `optics.scalar_emissivity` (Gap 37), Stage-7 `geometry.sensor_altitude_m`
precondition surfaced (registry Gap 42).

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
    - Dark current: 80 fA/pixel -> 499,376 e-/s (× 1e-15 ÷ q_e)
    - Band edges: 3700-4800 nm -> 3.70-4.80 µm (÷ 1000)
    - Integration time: 8 ms -> 0.008 s (÷ 1000)
    - Transmission: 68% -> 0.68 (÷ 100)
    - QE: 75% -> 0.75 (÷ 100)
  - **Derived-parameter highlights** (GUI computes and shows the derivation, user confirms):
    - Vendor cold stop efficiency % -> `nearfield_fraction` = 1 − efficiency (convention flip at the boundary)
    - Scalar-mode optics emissivity: ε = 1 − τ = 0.32 (Kirchhoff, Rule 5) -> `optics.scalar_emissivity`. GUI must warn if the user leaves ε = 0 with nearfield analysis enabled — that silently zeroes the nearfield term (old Gap 4).

## Step 2: Review and Validate Parameters
- **GUI components**:
  - Parameter panel organized by subsystem
  - Atmosphere model dropdown: "exo" selected (TVAC / vacuum, no atmospheric path)
  - Altitude field: 0 m (lab test, not orbital)
  - **Sub-case notice** (registry Gap 42): GUI shows that "exo" routes through the `no_atmosphere / space` sub-case and auto-fills the required placeholder `geometry.sensor_altitude_m = 1.0 m` with an explanatory tooltip ("Earth-limb check precondition; no radiometric effect in a lab setup"). When a first-class lab_test path lands, this notice disappears.
  - Nearfield fraction slider: 0.0 to 1.0
  - **Convention tooltip** on nearfield_fraction: η_nf = 0.0 means perfect cold stop (blocks all warm radiation), η_nf = 1.0 means no cold stop. Vendor "100% efficient" = η_nf 0. The rename (from cold_stop_efficiency) makes the value self-describing; the GUI still shows the vendor-equivalent efficiency next to the slider.
  - Nearfield emission toggle: ON (required for cold stop analysis)
  - Unused parameter annotations: source distance and shroud temperature flagged as "not used in extended regime" (background photon term skipped by design — matrix Decision #13)

## Step 3: Run Baseline Evaluations
- **Action**: Click "Evaluate" for two configurations
- **Config A** (blackbody illuminated): target = 308 K blackbody
- **Config B** (shuttered aperture): target = 77 K cold plate
- **GUI shows**:
  - Side-by-side results cards
  - Config A: signal (2,994,945 e-), SNR (1,534 at η_nf = 1.0), nearfield, noise breakdown
  - Config B: nearfield only (cold-plate contribution ≈ 0 at 77 K)
  - Regime badge: "Extended" for both configurations, with a note that background_e = 0 in this regime by design
  - Reference callout: "η_nf = 1.0 gives maximum nearfield (812,493 e-). Your design spec of 100% efficient cold stop corresponds to η_nf ≈ 0."

## Step 4: Nearfield Fraction Sweep
- **Action**: Tools > Parameter Sweep > Nearfield Fraction
- **GUI components**:
  - Sweep parameter: `optics.nearfield_fraction`
  - Range slider: 0.00 to 1.00
  - Scene mode toggle: "Shuttered (background only)" selected — uses 77 K cold plate model
  - Metrics to track: checkboxes for Nearfield Signal [e-], Total Background [e-], SNR
  - Requirements overlay: horizontal threshold line at 40,000 e-
  - "Match lab measurements" toggle: overlay lab data points on the sweep curve

- **Results visualization**:
  - Line chart: η_nf (x-axis) vs. nearfield signal (y-axis) — linear relationship (~8,125 e- per 1% leakage)
  - Requirement threshold line: 40,000 e- (red)
  - Crossover point highlighted: η_nf = 0.0492 where background = 40,000 e- (vendor efficiency ≥ 95.08%)
  - Lab measurement points overlaid as scatter markers with error bars
  - Each lab point annotated with matched η_nf value
  - Pass/fail zones shaded green/red

## Step 5: Lab Data Matching (Inverse Solve)
- **Action**: Compare > Import Reference Data, then "Solve for parameter"
- **GUI components**:
  - Import "Background Measurements" sheet as reference points
  - For each lab measurement, the GUI calls `Sensor.solve_for("optics.nearfield_fraction", measured, bounds=(0,1), metric=<total background>)` — no sweep needed for matching; each point converges in 6–7 forward-model evaluations (show the eval count as a progress detail)
  - Out-of-bracket handling: a measurement outside the model's [0, 1] range shows "above/below model range" instead of a value (SolveBracketError surfaced as a friendly message)
  - Results table: Test Point | Position [mm] | Meas [e-] | Matched η_nf | Evals | Status
  - Scatter plot: cold stop position (mm) vs. matched η_nf (linear trend expected)
  - Statistical summary: η_nf ranges from 0.0437 (nominal) to 0.0686 (2.5 mm offset), ~0.01 per mm
  - Verdict panel: "Nominal alignment (CS-NOM) passes requirement. Offset ≥ 1.0 mm fails."

## Step 6: SNR Impact Assessment
- **Action**: Analysis > Compare Scenarios
- **GUI components**:
  - Side-by-side comparison at nominal η_nf (0.0437) vs. anomalous η_nf (0.0542)
  - Noise budget pie charts showing fraction from each source
  - Key finding callout: "Nearfield contributes 1.2–1.4% of total noise variance. Cold stop misalignment does NOT significantly degrade SNR (1,719 vs 1,717)."
  - Explanation: "The primary impact of cold stop leakage is on absolute background level, not SNR. For this system, signal shot noise (1,731 e- RMS) dominates."

## Step 7: Export Results
- **Action**: File > Export Results
- **Options**:
  - Excel workbook with sweep data, lab comparison, and summary sheets
  - PDF report with charts and conclusions
  - Parameter snapshot (YAML) for reproducibility
- **Auto-generated summary**:
  - "Nominal cold stop leakage: η_nf = 0.0437 (35,500 e- background, PASS)"
  - "1.0 mm offset leakage: η_nf = 0.0542 (44,000 e- background, FAIL)"
  - "Maximum allowed leakage: η_nf ≤ 0.0492 (40,000 e- threshold; vendor efficiency ≥ 95.08%)"

## Step 8: Review Performance Metrics Dashboard

**Script equivalent:** Accessing `result.metrics` for NEDT, NIIRS, GSD, Strehl, Q, MTF budget, well margin

**GUI interaction:**
- **Results Panel > Metrics tab** shows all computed performance metrics in a summary card:
  - SNR, Contrast SNR (dimensionless)
  - NEDT (mK) — via `result.metrics["nedt_K"]`
  - NIIRS (dimensionless) — via `result.metrics["niirs"]` (not produced in this lab geometry; GUI shows "N/A (no ground geometry)")
  - GSD cross-track, along-track, geometric mean (m) — likewise N/A in the lab
  - MTF at Nyquist, Strehl ratio, Q parameter, EE(1x1), EE(3x3), RER
  - Well margin (dB), Dynamic range (dB)
- **MTF Budget sub-tab**: bar chart showing per-component MTF at Nyquist
- **Sweep Metrics tab**: NEDT and NIIRS plotted vs. nearfield_fraction alongside SNR
- Hover any metric for a tooltip showing the equation and intermediate values

**Script window commands:**
```python
result.metrics["nedt_K"]               # NEDT in Kelvin
result.metrics["strehl"]               # Strehl ratio
result.metrics["q_center"]             # sampling parameter
result.metrics["well_margin_dB"]       # well margin in dB
mtf_budget = result.stage_outputs["performance"]["mtf_budget"]
mtf_budget.per_term_at_nyquist         # dict of all MTF component values

# Inverse solve from the script window (Gap 10):
sol = sensor.solve_for(
    "optics.nearfield_fraction", 44_000.0, bounds=(0.0, 1.0),
    metric=lambda r: r.stage_outputs["spectral_integration"]["nearfield_e"]
                   + r.stage_outputs["spectral_integration"]["background_e"],
)
sol.solution, sol.achieved, sol.n_evaluations
```

---

## Key GUI Features Exercised
1. **Non-standard unit conversion** — fA/pixel → e-/s, °C → K, nm → µm, mm → m
2. **Convention disambiguation at the boundary** — vendor "efficiency" → η_nf = 1 − efficiency, shown as a derivation the user confirms
3. **Derived-parameter guardrail** — scalar_emissivity = 1 − τ (Kirchhoff); warn when ε = 0 with nearfield analysis on
4. **Dual-mode evaluation** — illuminated (SNR analysis) vs. shuttered (background characterization)
5. **Parameter sweep with lab data overlay** — visualize model vs. measurements
6. **Inverse problem via Sensor.solve_for** — direct root-finding with eval-count feedback and out-of-bracket messaging
7. **Sub-case transparency** — surface the exo→space masquerade and auto-filled `geometry.sensor_altitude_m` placeholder (registry Gap 42)
8. **Noise budget breakdown** — show that nearfield is not the dominant noise contributor
9. **Metrics dashboard** — NEDT, Strehl, Q, MTF budget, well margin displayed automatically; N/A states explained
