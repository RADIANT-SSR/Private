# Scenario 2.2 GUI Workflow: 1/f Noise Corner Frequency Impact on LWIR Staring Array

## Persona
Mike, detector engineer. He has a 640×512 LWIR HgCdTe staring array with measured 1/f noise characteristics (K = 2.5×10⁴ e⁻², corner frequency 200 Hz). He wants to understand how 1/f noise impacts NEDT at three operating frame rates (30, 60, 120 Hz).

## Step 1: Import Detector Data
- **Action**: File > Import Spreadsheet
- **Input**: `mike_1f_noise_data.xlsx` (3-sheet workbook)
- **GUI components**:
  - Sheet selector: "Detector Specs" maps to detector + readout parameters
  - "1-f Characterization" maps to flicker noise parameters (K, f_corner)
  - "System Configuration" maps to optics + spectral + scene
  - **Unit conversion highlights**:
    - Aperture diameter: 15.0 cm → 0.15 m (÷ 100)
    - Focal length: 30.0 cm → 0.30 m (÷ 100)
    - Optical transmission: 85% → 0.85 (÷ 100)
    - Optics temperature: 20°C → 293.15 K (+273.15)
    - Filter edges: 8000/10000 nm → 8.0/10.0 µm (÷ 1000)
    - QE: 55% → 0.55 (÷ 100)
    - Integration time: 0.1 ms → 0.0001 s (÷ 1000)
    - IPC coupling: 0.8% → 0.008 (÷ 100)
  - **1/f parameter mapping panel**: GUI shows how flicker_K, flicker_f_low_hz, flicker_f_high_hz are derived from the characterization data and frame rate
  - **Frame rate table import**: GUI recognizes the 3-row frame rate table and creates a parametric sweep

## Step 2: Configure 1/f Frequency Bands
- **Action**: Configure > 1/f Noise Settings
- **GUI components**:
  - Frame rate selector: dropdown or input for each test rate [Hz]
  - Auto-derived frequency band display:
    - f_low = frame rate [Hz] (with explanation tooltip)
    - f_high = 1/(2 × t_int) [Hz] (with explanation tooltip)
  - Corner frequency input: f_c = 200 Hz
  - Model selector: "Full band (RADIANT default)" vs. "Corner-limited (cap at f_c)"
  - **Visual PSD diagram**: log-log plot showing K/f line, white noise floor, f_c transition, shaded integration band for each frame rate
  - Warning badge: "f_high (5000 Hz) >> f_corner (200 Hz) — RADIANT will overestimate 1/f"

## Step 3: Run Frame Rate Sweep
- **Action**: Click "Evaluate at All Frame Rates"
- **GUI shows**:
  - Progress bar: evaluating 3 frame rates × 3 temperature runs × with/without 1/f = 18 evaluations
  - Toggle: "Include 1/f" checkbox (run both for comparison)
  - Results table: Frame Rate [Hz], f_low [Hz], f_high [Hz], σ_1f [e⁻], σ_total [e⁻], NEDT (no 1/f) [mK], NEDT (w/ 1/f) [mK], Δ NEDT [mK]
  - Well fill indicator: bar showing signal/FWC at each frame rate
  - LWIR regime note: "Integration time FWC-limited (100 µs), not frame-rate-limited"

## Step 4: Noise Visualization
- **Action**: View > Noise Analysis
- **GUI components (4 interactive charts)**:
  1. **Noise Breakdown (stacked bar)**: All noise terms at selected frame rate, 1/f highlighted in distinct color. Toggle with/without 1/f side-by-side.
  2. **NEDT vs. Frame Rate**: Line plot with and without 1/f, Δ NEDT annotated. Secondary y-axis for σ_1f [e⁻].
  3. **1/f Noise vs. f_low (sweep)**: σ_1f curve from 1 Hz to 500 Hz, with vertical markers at 30/60/120 Hz. Overlay corner-limited curve for comparison.
  4. **Noise PSD Plot**: Log-log power spectral density showing K/f line, white noise floor, corner frequency transition, and integration bands for each frame rate.

- **Interactive features**:
  - Frame rate slider: drag to see noise breakdown update continuously
  - Hover on any noise bar: tooltip shows σ [e⁻ RMS], NEDT_i [mK], fraction [%]
  - Click 1/f bar: expands to show formula with current K, f_low, f_high values
  - Toggle "Corner-limited model" to compare RADIANT vs. physically accurate 1/f
  - Dual-cursor on PSD plot: drag f_low and f_high bounds to see σ_1f update

## Step 5: Corner Frequency Analysis
- **Action**: Analysis > Corner Frequency Impact
- **GUI components**:
  - Comparison table: σ_1f (full band) vs. σ_1f (corner-limited) at each frame rate, with overestimate %
  - Visual PSD with shaded overestimate region (area between f_corner and f_high that shouldn't be integrated as 1/f)
  - Recommendation panel: "For this system, 1/f is 2.3% of noise variance — negligible for NEDT. BLIP-limited by photon noise."
  - "When does 1/f matter?" reference: conditions where 1/f would be significant (low signal, very low frame rate, large K)

## Step 6: Performance Metrics Dashboard
- **Action**: View > Performance Metrics
- **Script window commands**:
  ```
  >> result.metrics["nedt_K"] * 1000         # total NEDT in mK
  >> [(nt.name, nt.value_e) for nt in result.noise_terms if nt.name == "flicker_1f"]
  >> result.metrics["q_center"]               # sampling factor
  >> result.metrics["well_margin_dB"]         # headroom before saturation
  ```
- **GUI components**:
  - Metric cards: NEDT (mK) with/without 1/f, Signal (e⁻), Well fill (%)
  - 1/f NEDT contribution gauge
  - Corner frequency model toggle (full band vs. capped at f_c)

## Step 7: Export Results
- **Action**: File > Export Results
- **Options**:
  - Excel workbook: NEDT vs Frame Rate, Noise Breakdown 60 Hz, Frame Rate Sweep, Summary (4 sheets)
  - PDF report with all 4 noise charts
  - CSV of sweep data for external plotting
  - YAML snapshot of each frame rate configuration

## Key GUI Features Exercised
1. **1/f frequency band configurator** — visual mapping of frame rate → f_low/f_high with PSD diagram
2. **With/without comparison toggle** — run same config with and without a noise source to isolate its impact
3. **Continuous frame rate sweep** — not just discrete points, but analytic sweep curve with markers
4. **Noise PSD visualization** — frequency-domain view of noise contributions (not just integrated σ)
5. **Corner frequency model comparison** — showing RADIANT's overestimate vs. physically accurate result
6. **BLIP assessment** — automatic detection that photon noise dominates, 1/f is negligible
7. **LWIR-specific guidance** — FWC-limited integration time, large background flux context

## Interpolated-atmosphere availability

No bundled interpolated-atmosphere family serves this scene: 'midlat_summer_sensor_ladder' covers sensor_altitude 3 km to 40000 km; this scene asks for 1 m, below the family's runs. Switching **Atmosphere → Model** to `interpolated` therefore produces exactly one Messages-rail advisory saying so — not a sequence of refusals — and the scene stays on `atmosphere.model = 'simple'`, which serves any geometry.
