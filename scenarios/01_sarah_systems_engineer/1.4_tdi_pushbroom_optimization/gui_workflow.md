# Scenario 1.4 GUI Workflow: TDI Pushbroom Optimization

## Overview
Sarah needs to find the optimal N_tdi for her VNIR pushbroom imager. The GUI should let her sweep TDI stages and immediately see the SNR improvement, saturation threshold, and NIIRS peak.

## Step-by-Step GUI Workflow

### Step 1: Load System Configuration
- Load from spreadsheet or enter parameters manually
- Key inputs in user-native units:
  - Aperture: 25 [cm] (not m)
  - Focal length: 250 [cm]
  - Pixel pitch: 7.0 [um]
  - Band: 500--850 [nm]
  - FWC: 60,000 [e-]
  - Read noise: 15 [e- RMS]
- Display unit conversion confirmation panel
- Show derived parameters: GSD [m], IFOV [urad], Q [--], Airy disk [um]

### Step 2: Configure Orbital Parameters
- Input orbital velocity: 7500 [m/s]
- Input orbit altitude: 500 [km]
- GUI auto-computes and displays:
  - Ground velocity: 6954 [m/s]
  - Line period: 0.2013 [ms] (201.3 [us])
  - Smear: 1.0 [pixel/line]
  - Smear MTF@Nyquist: 0.6366 [--]
- Dual-unit display: line period in both ms and us

### Step 3: Configure TDI Parameters
- TDI mode selector: analog / digital
  - Tooltip: "Analog TDI: single readout, read noise constant. Digital: N readouts, read noise x sqrt(N)."
- TDI misalignment: 0.1 [pixels/stage]
  - Slider: 0.0 to 0.5 [pixels]
  - Tooltip: "Cross-track registration error per TDI stage. Typical: 0.05-0.2 pixels."

### Step 4: Run TDI Sweep
- Sweep control:
  - N_tdi values: [1, 2, 4, 8, 16, 32, 64, 96, 128] (editable)
  - "Run Sweep" button
- Progress bar: "Evaluating N_tdi = X / 128..."
- Auto-generate results table with columns:
  - N_tdi [--], Signal [e-], Well Fill [%], SNR [--], NIIRS [--], Status
- Color coding: green (OK), yellow (>80% fill), red (saturated)

### Step 5: SNR vs. N_tdi Plot
- Primary plot: SNR vs N_tdi (log x-axis)
- Overlay reference lines:
  - sqrt(N) scaling (shot-limited reference)
  - N scaling (read-limited reference)
- Vertical line at saturation threshold
- Annotation: "Optimal N_tdi = 16, SNR = 157.8"
- Interactive: hover shows exact values

### Step 6: Signal and Well Fill Plot
- Dual panel:
  - Left: Signal [ke-] vs N_tdi with FWC horizontal line
  - Right: Well Fill [%] vs N_tdi with 80% and 100% threshold lines
- Highlight saturation region in red shading
- Interactive: click to see noise budget at that N_tdi

### Step 7: Noise Budget Visualization
- Stacked bar chart: noise terms vs N_tdi
- Terms: signal_shot, background_shot, read_noise (dominant terms)
- Show how read noise stays constant (analog TDI advantage)
- Show how background_shot grows past saturation

### Step 8: NIIRS vs. N_tdi Plot
- NIIRS vs N_tdi (log x-axis)
- Mark peak NIIRS with green dashed line
- Mark saturated points with red X markers
- Annotation: "Peak NIIRS = 6.05 at N_tdi = 16"
- Secondary annotation: "Conservative: N_tdi = 8, NIIRS = 5.81 (42% fill)"

## Interactive Features

### Sensitivity Controls
- **FWC slider**: adjust FWC from 30,000 to 500,000 e-
  - Auto-recompute: saturation threshold shifts, optimal N_tdi changes
  - Shows: "Theoretical max N_tdi = FWC / signal_per_line"
- **Read noise slider**: adjust from 3 to 50 e- RMS
  - Shows transition from shot-limited to read-limited regime
  - At high read noise, SNR scales closer to N (not sqrt(N))
- **Target reflectance slider**: 0.05 to 0.50
  - Adjusts signal per line, shifts saturation threshold
- **TDI misalignment slider**: 0.0 to 0.5 pixels/stage
  - Real-time MTF budget update

### Analog vs. Digital TDI Comparison
- Toggle button: overlay digital TDI results on same plots
- Digital TDI: read noise scales as sqrt(N), reducing SNR advantage
- Shows regime where digital TDI is preferred (when per-stage correction is needed)

### Design Summary Panel
- Auto-generated recommendation:
  - "Optimal N_tdi: 16 (peak NIIRS = 6.05, 83% well fill)"
  - "Conservative: N_tdi = 8 (NIIRS = 5.81, 42% well fill)"
  - "Saturation onset: N_tdi > 19 (FWC / signal_per_line)"
- Export: PDF report, Excel spreadsheet

## Display Requirements
- All numerical values must include units
- Dual-unit display where applicable:
  - Line period: ms and us
  - GSD: m and ft
  - Signal: e- and ke-
- Log x-axis for N_tdi plots (powers of 2 spacing)
- Color-coded saturation status throughout
