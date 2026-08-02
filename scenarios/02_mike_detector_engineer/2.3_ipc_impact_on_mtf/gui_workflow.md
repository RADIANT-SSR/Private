# Scenario 2.3 GUI Workflow: IPC Impact on MTF

## Persona
Mike, detector engineer. Has a vendor datasheet, lab IPC measurements on 5 samples, and system-level requirements. Wants to know the maximum tolerable IPC coupling.

## Step 1: Import Detector Data
- **Action**: File > Import Spreadsheet
- **Input**: `mike_detector_ipc_data.xlsx` (3-sheet workbook)
- **GUI components**:
  - Sheet selector: user picks which sheet maps to which parameter group
  - Column mapper: drag-and-drop columns to RADIANT parameters
  - Unit detection: GUI reads "µm", "cm", "%", "ms", "km" from the Unit column and auto-selects conversion
  - Preview panel: shows converted values in RADIANT canonical units with green/red validation indicators
  - "Detector Specs" sheet maps to detector + readout parameters
  - "System Requirements" sheet maps to optics + geometry + source + spectral parameters
  - "IPC Measurements" sheet is stored as reference data (not sensor config)

## Step 2: Review and Validate Parameters
- **GUI components**:
  - Parameter panel organized by subsystem (Source, Atmosphere, Optics, Detector, Readout)
  - Each parameter shows: name, value, canonical unit, source indicator (spreadsheet icon vs. default)
  - Atmosphere model dropdown: "simple" selected (LEO through atmosphere)
  - Altitude shown with icon indicating LEO orbit (500 km)
  - Consistency checks: f/# = focal_length / aperture auto-verified
  - Warning if IPC coupling parameter is set but not wired into chain (gap indicator)
  - Unused parameter annotations: background temp/emissivity flagged as "contrast SNR only" in extended regime

## Step 3: Run Baseline Evaluation
- **Action**: Click "Evaluate" button
- **GUI shows**:
  - Results summary card: SNR, contrast SNR, MTF at Nyquist, EE 1x1, EE 3x3
  - Regime indicator badge: "Extended" with tooltip explaining why
  - Atmosphere transmission indicator: tau range across spectral band
  - IPC gap warning banner: "IPC coupling is not yet applied to system MTF. Use the IPC Sweep tool for analysis."

## Step 4: IPC Sweep Analysis
- **Action**: Tools > Parameter Sweep > IPC Coupling
- **GUI components**:
  - Sweep parameter: `detector.ipc_coupling` (or future dedicated IPC sweep tool)
  - Range slider: 0% to 5%, with vendor typical (1.8%) and vendor max (2.5%) marked
  - Metrics to track: checkboxes for MTF at Nyquist, EE 1x1, EE 3x3, SNR
  - Requirements overlay: horizontal threshold lines from system requirements
  - "Include IPC MTF correction" toggle (applies analytic IPC MTF post-hoc until gap is fixed)

- **Results visualization**:
  - Line chart: IPC coupling (x-axis) vs. metric value (y-axis)
  - Requirement threshold lines: MTF >= 0.15 (green), EE >= 0.60 (green)
  - Crossover points highlighted with callout annotations
  - Vendor typical and vendor max IPC values shown as vertical dashed lines
  - Pass/fail zones shaded green/red
  - Binding constraint identified and labeled

## Step 5: Lab Data Comparison
- **Action**: Compare > Import Reference Data
- **GUI components**:
  - Import the "IPC Measurements" sheet as reference points
  - Overlay lab measurements on the sweep chart as scatter points with error bars
  - Residual panel showing model-vs-measured delta for each sample
  - Statistical summary: mean absolute error, systematic bias direction
  - Tooltip on each lab point showing sample ID and notes

## Step 6: Export Results
- **Action**: File > Export Results
- **Options**:
  - Excel workbook with sweep data, lab comparison, and summary sheets
  - PDF report with charts and conclusions
  - Parameter snapshot (YAML) for reproducibility
- **Auto-generated summary**:
  - "Maximum tolerable IPC: X.XX% (binding constraint: EE 1x1)"
  - "Vendor typical (1.8%): PASS/FAIL"
  - "Vendor max (2.5%): PASS/FAIL"

## Key GUI Features Exercised
1. **Multi-sheet spreadsheet import** with per-sheet parameter mapping
2. **Reference data overlay** (lab measurements on model predictions)
3. **Sweep with requirement thresholds** and crossover detection
4. **Gap awareness** — GUI surfaces known limitations with workaround guidance
5. **Regime explanation** integrated into results display

## Interpolated-atmosphere availability

Switching **Atmosphere → Model** to `interpolated` works first try on this scene. The picker pre-selects **`midlat_summer_sensor_ladder`** (profile `midlat_summer`, down-looking; covers ground targets only (target altitude fixed at 0 km), sensor 3-100 km plus 40000 km (GEO), nadir only (LOS zenith 0 degrees)); *Use this family* writes `atmosphere.interpolation_axes = 'sensor_altitude_m'`. `Sensor.atmosphere_family_suggestion()` is the same answer from a script.
