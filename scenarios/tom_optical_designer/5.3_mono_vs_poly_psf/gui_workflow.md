# Scenario 5.3 GUI Workflow: Monochromatic vs. Polychromatic PSF

## Persona
Tom, optical designer. He has the selected optical design from scenario 5.2 (f/4, 30 cm aperture, 18 µm pixel, MWIR 3.5–5.0 µm) and wants to understand how much chromaticism affects his spatial metrics.

## Step 1: Load Baseline Configuration
- **Action**: File > Open Configuration (or continue from scenario 5.2)
- **GUI components**:
  - Configuration loaded from 5.2 results: f/4, 30 cm, 18 µm, 3.5–5.0 µm
  - Band summary panel shows: Δλ/λ_center = 35% (wide band — chromaticism likely significant)
  - Sampling summary: Q ranges 0.78 (3.5 µm) to 1.11 (5.0 µm)

## Step 2: Per-Wavelength PSF Viewer
- **Action**: Analysis > Chromatic PSF Analysis
- **GUI components**:
  - Wavelength slider: drag from 3.5 to 5.0 µm, PSF updates in real-time
  - 2D PSF visualization: false-color image with pixel grid overlay
  - Airy ring overlay: shows first dark ring relative to pixel boundaries
  - Side panel: MTF@Nyquist, EE 1×1, EE 3×3, FWHM update as slider moves
  - **Multi-wavelength compare**: select 3–5 wavelengths, display PSFs side-by-side
  - Cross-section plot: 1D slice through PSF center at each wavelength

## Step 3: Mono vs. Poly Comparison
- **Action**: Analysis > PSF Model Comparison
- **GUI components**:
  - Toggle: Monochromatic / Polychromatic with N selector (5, 11, 21)
  - Split-screen PSF view: mono on left, poly on right
  - Difference map: |PSF_mono - PSF_poly| with hot-spots highlighted
  - Metrics comparison table: side-by-side MTF, EE, FWHM with % difference
  - **Convergence plot**: metrics vs. N (auto-generated, shows where N is sufficient)

## Step 4: Chromatic MTF Overlay
- **Action**: View > MTF Charts > Chromatic Overlay
- **GUI components**:
  - MTF(f) curves at each analysis wavelength, color-coded by λ
  - Polychromatic MTF overlaid as thick black curve
  - Monochromatic (band-center) as dashed curve
  - Nyquist frequency marked with vertical line
  - Interactive: hover shows MTF value at any frequency/wavelength

## Step 5: Chromatic Error Assessment
- **Action**: Analysis > Chromaticism Report
- **GUI components**:
  - Error table: each metric with mono value, poly value, % error
  - Traffic-light indicators: green (<2%), yellow (2–5%), red (>5%)
  - Recommendation panel: "Use polychromatic N=11 for design review"
  - Impact assessment: do any requirements change status (pass → fail)?
  - Band-width sensitivity: how error scales with Δλ/λ (helpful for band selection)

## Step 6: Export
- **Action**: File > Export Chromatic Analysis
- **Options**:
  - PDF report with PSF images, MTF overlays, and error summary
  - Excel with per-wavelength metrics and mono/poly comparison
  - PowerPoint slide: "Chromaticism Impact" for design review
  - Per-wavelength PSF arrays (FITS or NumPy) for external analysis

## Key GUI Features Exercised
1. **Real-time wavelength slider** with PSF + metrics updating live
2. **Split-screen PSF comparison** (mono vs. poly) with difference map
3. **Chromatic MTF overlay** — multiple MTF curves color-coded by wavelength
4. **Convergence analysis** — automatic N-sufficiency determination
5. **Traffic-light error assessment** — immediate visual flag for significant chromaticism
6. **Bandwidth sensitivity** — shows how error varies with spectral band width
