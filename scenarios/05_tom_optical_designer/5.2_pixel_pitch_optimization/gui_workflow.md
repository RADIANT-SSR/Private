# Scenario 5.2 GUI Workflow: Pixel Pitch / Q-Parameter Trade Study

## Persona
Tom, optical designer. He has a Zemax optical design (f/4, 30 cm aperture, MWIR) and six candidate detectors with pixel pitches from 8 to 30 µm. He wants to find the pixel pitch that balances spatial resolution (GSD), sampling adequacy (Q), and sensitivity (SNR).

## Step 1: Import Optical Design and Detector Data
- **Action**: File > Import Spreadsheet
- **Input**: `tom_pixel_pitch_trade.xlsx` (3-sheet workbook)
- **GUI components**:
  - Sheet selector: "Optical Design Summary" maps to optics + scene + geometry
  - "Candidate Detectors" is a comparison table — GUI creates a sweep over pixel pitch
  - "Performance Requirements" maps to threshold definitions
  - **Unit conversion highlights**:
    - Entrance pupil diameter: 300 mm -> 0.30 m (÷ 1000, Zemax convention)
    - Effective focal length: 1200 mm -> 1.20 m (÷ 1000)
    - Filter edges: 3500/5000 nm -> 3.50/5.00 µm (÷ 1000)
    - Transmission: 72% -> 0.72 (÷ 100)
    - QE: 70-75% -> 0.70-0.75 (÷ 100)
    - Integration time: 2 ms -> 0.002 s (÷ 1000)
    - Orbit altitude: 500 km -> 500,000 m (× 1000)
  - **Multi-detector import**: GUI recognizes the tabular format (one column per candidate) and creates a parametric sweep with matched detector specs per pitch

## Step 2: Review Sampling Configuration
- **GUI components**:
  - Automatic Q parameter calculation: Q = λ·f/# / p displayed for each pitch
  - Sampling regime badges: "oversampled" / "well-sampled" / "undersampled" / "ALIASED"
  - Airy disk overlay: shows Airy disk diameter (41.6 µm) relative to each pixel pitch
  - Visual pitch comparator: pixel grid overlaid on PSF for each candidate
  - GSD calculator: GSD = p × h / f displayed with requirement threshold

## Step 3: Run Parametric Sweep
- **Action**: Click "Evaluate All Candidates"
- **GUI shows**:
  - Progress bar: evaluating 6 configurations
  - Each candidate gets: SNR, MTF at Nyquist, EE 1×1, EE 3×3, signal, noise breakdown
  - Results table with color-coded pass/fail against requirements
  - Regime indicator: all "Extended" (310 K target fills pixel)

## Step 4: Trade Study Visualization
- **Action**: View > Trade Charts
- **GUI components (4 interactive charts)**:
  1. **Q and GSD vs. Pitch**: Dual-axis plot with sampling regime bands (green/yellow/red)
  2. **MTF and EE vs. Pitch**: Spatial metrics with requirement thresholds, Q on secondary x-axis
  3. **SNR and Signal vs. Pitch**: Sensitivity with p² scaling visible, SNR requirement line
  4. **Trade Space (SNR vs. GSD)**: Scatter plot color-coded by Q, compliant region shaded

- **Interactive features**:
  - Hover over any point: tooltip shows full parameter set
  - Click a point: opens detailed noise breakdown for that candidate
  - Drag requirement threshold lines to explore sensitivity
  - Toggle between extended-scene SNR and contrast SNR

## Step 5: Optimal Selection
- **Action**: Analysis > Optimize
- **GUI components**:
  - Figure-of-merit selector: SNR/GSD (default), or custom weighting
  - Compliance filter: only show candidates passing all requirements
  - Recommendation panel: "18 µm — best SNR/GSD among compliant options"
  - Warning flags: "8 µm fails MTF, EE, and SNR" / "24 and 30 µm fail GSD"

## Step 6: Export Results
- **Action**: File > Export Results
- **Options**:
  - Excel workbook: Trade Study Results, Noise Breakdown, Summary
  - PDF report with all 4 trade charts
  - PowerPoint slide deck (for design review)
  - YAML snapshot of each candidate configuration (reproducibility)

## Step 7: Review Performance Metrics Dashboard

**Script equivalent:** Accessing `result.metrics` for each candidate

**GUI interaction:**
- **Results Panel > Metrics tab** shows per-candidate comparison table:
  - Q (center, min, max) — from `result.metrics["q_center"]`
  - GSD cross-track, along-track, geometric mean — from `result.metrics["gsd_cross_track_m"]`
  - NEDT (mK) — from `result.metrics["nedt_K"]`
  - NIIRS — from `result.metrics["niirs"]`
  - Strehl ratio — from `result.metrics["strehl"]`
  - RER — from `result.metrics["rer"]`
  - Well margin (dB), Dynamic range (dB)
- **MTF Budget sub-tab**: per-component MTF at Nyquist for each candidate
- **Folded MTF tab**: shows aliased MTF for undersampled configurations (Q < 1)

**Script window commands:**
```python
result.metrics["q_center"]             # Q at band center
result.metrics["gsd_cross_track_m"]    # GSD in meters
result.metrics["nedt_K"]               # NEDT in Kelvin
result.metrics["niirs"]                # NIIRS rating
result.metrics["strehl"]               # Strehl ratio
result.metrics["rer"]                  # Relative edge response
result.metrics["well_margin_dB"]       # well margin in dB
# Full MTF curves:
result.stage_outputs["performance"]["mtf_freq_x"]   # frequency array
result.stage_outputs["performance"]["mtf_x"]         # MTF values
result.stage_outputs["performance"]["folded_mtf_x"]  # aliased MTF
```

---

## Key GUI Features Exercised
1. **Multi-candidate parametric sweep** — one evaluation per detector option with matched specs
2. **Automatic Q parameter and GSD computation** from optical design parameters
3. **Trade space visualization** — SNR vs. GSD with Q color coding
4. **Multi-requirement compliance checking** — GSD, MTF, EE, SNR evaluated simultaneously
5. **Figure-of-merit optimization** with configurable weighting
6. **Zemax-convention unit handling** — mm for focal length (not cm or m)
7. **Metrics dashboard** — NEDT, NIIRS, Strehl, RER, folded MTF per candidate
