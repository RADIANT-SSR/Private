# Scenario 6.3: GUI Workflow — Noise Model Verification

How this scenario would be completed in the RADIANT GUI.

Refreshed 2026-07-07 (Phase R): the unit-aware import below is now backed by
real API — `Sensor.set(value, unit="cm"/"%"/"ms"/"km")` (Gap 6) — so the GUI
mapping dialog delegates conversion to the framework instead of converting
itself.

---

## Step 1: Import Parameters

**Script equivalent:** Read Excel, then `sensor.set(param, raw_value, unit=...)` (Gap 6) — RADIANT converts at the boundary; the script cross-checks the conversions

**GUI interaction:**
- **File > Import Spreadsheet** — user selects their `.xlsx` file
- GUI reads the parameter table and presents a **mapping dialog**:
  - Left column: spreadsheet parameter names (e.g., "Aperture diameter")
  - Right column: dropdown of RADIANT parameter dot-paths (e.g., `optics.aperture_diameter_m`)
  - Center column: detected unit + target unit with auto-conversion preview
    - e.g., `30 cm` -> `0.30 m` (green checkmark)
    - e.g., `70 %` -> `0.70` (green checkmark)
    - e.g., `5 ms` -> `0.005 s` (green checkmark)
  - The conversion itself is `Sensor.set(..., unit=)` — the GUI passes the
    raw vendor value + unit string through; provenance records both
    (`user [30.0 'cm']`), so the audit trail keeps the original entry
- **Smart matching**: GUI auto-matches obvious pairs ("Aperture diameter" -> `optics.aperture_diameter_m`) and highlights unmatched rows in yellow
- User confirms or adjusts mappings, then clicks **Import**
- Imported values populate the **Parameter Panel** (see below)

**Key GUI requirement:** Unit-aware import with conversion preview, delegating to the Gap 6 boundary. The user should never have to manually convert cm to m — and neither should the GUI.

---

## Step 2: Review / Edit Parameters

**Script equivalent:** The printed "Converted to RADIANT canonical units" block

**GUI interaction:**
- **Parameter Panel** shows all parameters grouped by stage (Optics, Detector, Readout, Scene, Spectral)
- Each row: parameter name, value, unit, source indicator (imported / default / derived)
- Imported values highlighted to distinguish from defaults
- Derived values (e.g., focal length from f/# x aperture) shown as read-only with tooltip showing the derivation
- User can edit any value inline; changes propagate through consistency groups in real time

**Key GUI requirement:** Visual distinction between user-supplied, default, and derived values.

---

## Step 3: Run Evaluation

**Script equivalent:** `sensor.evaluate()`

**GUI interaction:**
- **Run** button (or Ctrl+Enter)
- Progress indicator while chain executes
- Results populate the **Results Panel** automatically

---

## Step 4: Inspect Noise Budget

**Script equivalent:** Iterating `result.noise_terms` and printing the table

**GUI interaction:**
- **Results Panel > Noise Budget tab**
- **Bar chart** showing all 16 noise terms sorted by magnitude (log scale option)
- **Table** below the chart with columns: Term, Value (e-), % of Total Variance
- Terms with value = 0 collapsed/hidden by default (toggle to show all)
- Dominant term highlighted
- **Pie chart** option for fractional contribution view

**Key GUI requirement:** Interactive noise budget visualization with sort/filter. This is the most-used view for detector engineers.

---

## Step 5: Compare to Hand Calculations

**Script equivalent:** The comparison table with % error

**GUI interaction:**
- **Tools > Verification Mode** or a "Compare" button on the Noise Budget tab
- Opens a **side-by-side panel**:
  - Left column: RADIANT values (auto-populated)
  - Right column: editable cells where user enters hand-calc values
  - Center: auto-computed % error with color coding (green < 5%, yellow < 20%, red > 20%)
- User can paste values from their spreadsheet
- **Export** button generates the comparison report (Excel or PDF)

**Key GUI requirement:** Built-in verification/comparison workflow. This is a common use case for researchers and test engineers.

---

## Step 6: Export Results

**Script equivalent:** Writing the output spreadsheet

**GUI interaction:**
- **File > Export Results** with format options:
  - Excel (noise budget + comparison table on separate sheets)
  - CSV
  - PDF report (formatted with charts)
- Default export includes: parameter summary, noise budget table, noise bar chart, metrics summary

---

## GUI Components Identified

| Component | Used in this scenario | Reusable? |
|-----------|----------------------|-----------|
| Spreadsheet import with unit mapping | Step 1 | Yes — all import workflows |
| Parameter panel with source indicators | Step 2 | Yes — core UI element |
| Noise budget bar chart | Step 4 | Yes — any evaluation |
| Noise budget table with filtering | Step 4 | Yes — any evaluation |
| Verification comparison panel | Step 5 | Yes — test engineer scenarios |
| Results export (multi-format) | Step 6 | Yes — all workflows |

## Step 7: Review Performance Metrics Dashboard

**Script equivalent:** Accessing `result.metrics` for SNR, NEDT, NIIRS, GSD, Strehl, Q, MTF, etc.

**GUI interaction:**
- **Results Panel > Metrics tab** shows all computed performance metrics in a summary card:
  - SNR, Contrast SNR (dimensionless)
  - NEDT (mK) with hand-calc comparison column
  - NIIRS (dimensionless) with GIQE-5 breakdown
  - GSD cross-track, along-track, geometric mean (m)
  - MTF at Nyquist, Strehl ratio, Q parameter, EE(1x1), EE(3x3), RER
  - Well margin (dB), Dynamic range (dB)
- **MTF Budget sub-tab**: bar chart showing per-component MTF at Nyquist (optics, pixel aperture, jitter, smear, IPC, diffusion, TDI)
- Hover any metric for a tooltip showing the equation and intermediate values
- Click any metric to drill down into stage outputs

**Script window commands:**
```python
result.metrics["nedt_K"]          # 0.02818 K
result.metrics["niirs"]           # 10.89
result.metrics["gsd_geometric_mean_m"]  # 0.12 m
result.metrics["q_center"]        # 0.9444
mtf_budget = result.stage_outputs["performance"]["mtf_budget"]
mtf_budget.per_term_at_nyquist    # dict of all MTF terms
```

---

## Pain Points the GUI Solves

1. **Unit conversion** — the script required manual cm->m, %->fraction, ms->s. GUI handles this automatically.
2. **Parameter name discovery** — the script failed on `atmosphere.mode` vs `atmosphere.model`, `operating_temp_K` vs `detector_temperature_K`. GUI uses dropdowns, no guessing.
3. **Noise visualization** — the script prints a text table. GUI shows an interactive chart.
4. **Comparison workflow** — the script required writing ~50 lines of comparison code. GUI has it built in.
5. **Metrics dashboard** — NEDT, NIIRS, GSD, Q, MTF budget are now computed by RADIANT but require explicit code to access. GUI displays all metrics in a unified dashboard automatically.

## Interpolated-atmosphere availability

Switching **Atmosphere → Model** to `interpolated` works first try on this scene. The picker pre-selects **`midlat_summer_sensor_ladder`** (profile `midlat_summer`, down-looking; covers ground targets only (target altitude fixed at 0 km), sensor 3-100 km plus 40000 km (GEO), nadir only (LOS zenith 0 degrees)); *Use this family* writes `atmosphere.interpolation_axes = 'sensor_altitude_m'`. `Sensor.atmosphere_family_suggestion()` is the same answer from a script.
