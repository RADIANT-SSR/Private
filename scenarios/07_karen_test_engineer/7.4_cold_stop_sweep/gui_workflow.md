# Scenario 7.4 GUI Workflow: Cold-Stop Undersizing Sweep

Rebuilt 2026-09-09 under Gap 128: `optics.nearfield_fraction` is deleted (a cold
stop cannot attenuate in-cone emission), and the swept variable is
`optics.cold_stop_undersize_frac` [-] — the fractional pupil-diameter reduction
the cold stop imposes as the aperture stop. Warm-train emissivity comes from a
defined element list (ε = 1 − R per mirror; Gap 127), Stage-7
`geometry.sensor_altitude_m` precondition surfaced (registry Gap 42).

## Persona
Karen, test engineer, running a TVAC background characterization. She has an instrument spec sheet, lab background measurements at several cold-stop positions (in DN and e-), and system performance requirements. She wants to know what undersizing margin the camera can afford, and what her measurements say about the warm train.

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
    - Vendor cold stop efficiency % -> **no parameter** (Gap 128). The import preview must say so explicitly: a blocked-fraction figure has no model home, because in-cone emission cannot be blocked and out-of-cone structure is blocked completely. The GUI offers `optics.cold_stop_undersize_frac` [-] instead.
    - Optics emissivity: the workbook's single ε = 32 % is the ε = 1 − τ fallacy and must NOT be entered. The train is an element list — three mirrors at R = 0.98 [-] (ε = 1 − R = 0.02 [-] each, Kirchhoff, Rule 5, read-only) plus an AR cold window at T = 0.7225 [-] (ε = 0 [-]) — whose net throughput is the workbook's τ = 0.68 [-] exactly. GUI must warn if no emitting element is defined with nearfield analysis enabled — that silently zeroes the nearfield term (old Gap 4; Gap 127 makes an element list the only way to emit).

## Step 2: Review and Validate Parameters
- **GUI components**:
  - Parameter panel organized by subsystem
  - Atmosphere model dropdown: "exo" selected (TVAC / vacuum, no atmospheric path)
  - Altitude field: 0 m (lab test, not orbital)
  - **Sub-case notice** (registry Gap 42): GUI shows that "exo" routes through the `no_atmosphere / space` sub-case and auto-fills the required placeholder `geometry.sensor_altitude_m = 1.0 m` with an explanatory tooltip ("Earth-limb check precondition; no radiometric effect in a lab setup"). When a first-class lab_test path lands, this notice disappears.
  - Cold-stop undersizing slider: `optics.cold_stop_undersize_frac` [-], 0.00 to 0.49
  - **Effective-pupil readout** beside the slider, live: D_eff [m], f/#_eff [-], A_collect [m²], Ω_cone [sr]. This is the whole point of the parameter — one number moves all four, so the operator must see them move together.
  - **Tooltip**: "The cold stop IS the aperture stop, built slightly smaller than the primary so tolerances cannot let the FPA see past it. u = 0.05 collects (1 − 0.05)² = 90 % of the light. It cannot attenuate in-cone warm-optics emission — it shrinks the cone instead, and the signal with it."
  - Nearfield emission toggle: ON (required for cold stop analysis)
  - Unused parameter annotations: source distance and shroud temperature flagged as "not used in extended regime" (background photon term skipped by design — matrix Decision #13)

## Step 3: Run Baseline Evaluations
- **Action**: Click "Evaluate" for two configurations
- **Config A** (blackbody illuminated): target = 308 K blackbody
- **Config B** (shuttered aperture): target = 77 K cold plate
- **GUI shows**:
  - Side-by-side results cards
  - Config A: signal (2,994,945 e-), SNR (1,699 at u = 0), nearfield (106,631 e-), noise breakdown
  - Config B: nearfield only (cold-plate contribution ≈ 0 at 77 K)
  - Regime badge: "Extended" for both configurations, with a note that background_e = 0 in this regime by design
  - Reference callout: "At u = 0 the stop matches the primary: Ω_cone = 0.048520 sr at f/4.0. Undersizing shrinks the cone and the collecting area together."

## Step 4: Undersizing Sweep
- **Action**: Tools > Parameter Sweep > Cold-stop undersizing
- **GUI components**:
  - Sweep parameter: `optics.cold_stop_undersize_frac` [-]
  - Range slider: 0.00 to 0.10 (the tolerancing range a cold-stop design lives in)
  - Scene mode toggle: "Illuminated (SNR)" / "Shuttered (background only)"
  - Metrics to track: Signal [e-], Nearfield [e-], SNR [-], NEDT [mK], MTF at Nyquist [-], A_collect [m²], Ω_cone [sr]
  - Requirements overlay: horizontal threshold line at 40,000 e-

- **Results visualization**:
  - **Twin-axis chart, signal and near-field on one plot** — the load-bearing display: both fall together (−19.0 % and −18.8 % over 0–10 %), which is what the deleted leakage knob concealed.
  - Second chart: SNR (−10.0 %) and MTF at Nyquist (−11.6 %) — the cost of margin.
  - Third chart: shuttered background vs. u, with the 40,000 e- requirement and Karen's measurements as horizontal reference lines.
  - Pass/fail zones shaded green/red

## Step 5: What the Lab Measurements Bound
- **Action**: Compare > Import Reference Data
- **GUI components**:
  - Import "Background Measurements" sheet as reference points
  - **Explicit refusal panel** (Gap 128): the GUI must state that cold-stop POSITION has no model parameter to invert onto. A cold stop cannot manufacture background. Offering a fit here would reintroduce the deleted knob.
  - Instead: near-field scales linearly with the emitting emissivity Σ(1 − R) at fixed Ω_cone and T_optics, so each measurement inverts to an **implied per-mirror reflectance** — shown as a column, with the assumed R = 0.98 [-] marked for contrast.
  - Results table: Test Point | Position [mm] | Meas [e-] | Model [e-] | Δ [%] | implied ε [-] | implied R [-] | Status
  - Verdict panel: "All six readings sit below the model: the real train is better than R = 0.98 (implied R ≈ 0.990–0.993), or the barrel is colder than 20 °C. The 57 % spread across positions is outside the model — a shifted stop that is no longer the aperture stop (accepted Gap 128 limitation)."

## Step 6: The Cost of Margin
- **Action**: Analysis > Compare Scenarios
- **GUI components**:
  - Side-by-side comparison at u = 0.00 and u = 0.10
  - Noise budget pie charts showing fraction from each source
  - Key finding callout: "Ten percent of undersizing costs 19.0 % of collecting area, 10.0 % of SNR (1,699 → 1,529) and 11.6 % of MTF at Nyquist (0.3017 → 0.2668). Near-field falls 18.8 % at the same time — margin is bought with photons, not for free."
  - Explanation: "Near-field shot noise is 326.5 e- RMS against signal shot 1,730.6 e- RMS, so the background is a calibration concern rather than the SNR driver; the SNR loss under undersizing comes from the lost aperture."

## Step 7: Export Results
- **Action**: File > Export Results
- **Options**:
  - Excel workbook with sweep data, lab comparison, and summary sheets
  - PDF report with charts and conclusions
  - Parameter snapshot (YAML) for reproducibility
- **Auto-generated summary**:
  - "Baseline (u = 0): D_eff = 0.25000 m, f/#_eff = 4.0000, Ω_cone = 0.048520 sr, near-field 106,631 e-, SNR 1,699.3"
  - "At u = 0.10: SNR 1,529.1 (−10.0 %), MTF at Nyquist 0.2668 (−11.6 %), near-field 86,561 e- (−18.8 %)"
  - "Requirement (40,000 e- shuttered) is not met at any undersizing: the near-field is set by the train emissivity and barrel temperature, not by the stop."

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
- **Sweep Metrics tab**: NEDT and NIIRS plotted vs. `cold_stop_undersize_frac` alongside SNR
- Hover any metric for a tooltip showing the equation and intermediate values

**Script window commands:**
```python
result.metrics["nedt_K"]               # NEDT in Kelvin
result.metrics["strehl"]               # Strehl ratio
result.metrics["q_center"]             # sampling parameter
result.metrics["well_margin_dB"]       # well margin in dB
mtf_budget = result.stage_outputs["performance"]["mtf_budget"]
mtf_budget.per_term_at_nyquist         # dict of all MTF component values

# The effective pupil the cold stop leaves (Gap 128):
opt = result.stage_outputs["optics"]
opt["D_eff_m"], opt["f_number_eff"], opt["obscuration_eff"], opt["Omega_cone"]

# Per-element near-field breakdown [W/m^2/um] (which mirror dominates):
opt["nearfield_per_element"]
```

---

## Key GUI Features Exercised
1. **Non-standard unit conversion** — fA/pixel → e-/s, °C → K, nm → µm, mm → m
2. **Refusing a vendor number that has no model home** — "cold stop efficiency %" maps to nothing (Gap 128), and the import must say so rather than inventing a mapping
3. **Derived-parameter guardrail** — element ε = 1 − R (Kirchhoff); warn when no emitting element is defined with nearfield analysis on; refuse a single end-to-end ε = 1 − τ entry
4. **Dual-mode evaluation** — illuminated (SNR analysis) vs. shuttered (background characterization)
5. **Parameter sweep with lab data overlay** — visualize model vs. measurements
6. **Live effective-pupil readout** — one slider moving D_eff, f/#_eff, A_collect and Ω_cone together, so the coupling is visible rather than asserted
7. **Sub-case transparency** — surface the exo→space masquerade and auto-filled `geometry.sensor_altitude_m` placeholder (registry Gap 42)
8. **Noise budget breakdown** — show that nearfield is not the dominant noise contributor
9. **Metrics dashboard** — NEDT, Strehl, Q, MTF budget, well margin displayed automatically; N/A states explained

## Interpolated-atmosphere availability

No bundled interpolated-atmosphere family serves this scene: 'midlat_summer_sensor_ladder' covers sensor_altitude 3 km to 40000 km; this scene asks for 1 m, below the family's runs. Switching **Atmosphere → Model** to `interpolated` therefore produces exactly one Messages-rail advisory saying so — not a sequence of refusals — and the scene stays on `atmosphere.model = 'simple'`, which serves any geometry.
