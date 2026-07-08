# Scenario 4.3 GUI Workflow: Camouflage Effectiveness Analysis

How this scenario would be completed in the RADIANT GUI.

## Persona
Lisa, analyst. One ASTER spectrum, three camo-net emissivity files in
different forms, one FLIR — and a "which net?" recommendation.

## Step 1: Import Emissivity Sources
- **File > Import > Material Spectrum (ASTER)** for the bare vehicle
  (`load_aster_spectrum`, ε = 1 − ρ preview)
- **File > Import > Emissivity Curve (CSV)** for nets A and B
  (`load_measured_curve`, x_unit µm), and net C (3 points) — the GUI
  flags "sparse: 3 points, linear interpolation assumed" and overlays the
  interpolated curve so the user sees the assumption
- All ε(λ) overlaid with the scrub-background ε line and the sensor band
  shaded (fig3 equivalent)

## Step 2: Configure the Scene
- Vehicle surface temperature (engine deck, 380 K); net drape temperature
  (310 K, near-ambient) with a tooltip that the net is thermally
  decoupled from the vehicle — "camouflage models the net's own emission,
  not the vehicle's"
- Background: scrub 305 K / ε 0.96, clutter σ 0.03
- **Spectral-emissivity note (Gap 47)**: the GUI composes
  L_t(λ) = ε(λ)·B(λ,T) and feeds the S8 radiance path, with a status chip
  "spectral ε → radiance (user-owned physics)" until a first-class
  emissivity-path input exists

## Step 3: Run the Comparison
- "Compare Camouflage" runs each option as a pixel-filling (extended)
  target and differences it against a scrub pixel
- Signature card per option: contrast [e⁻], SCNR, well fill, and
  **signature reduction vs bare [%]** as the headline number
- Callout: "Camouflage is radiance MATCHING — net C (ε≈0.93 near the 0.96
  scrub) wins; the low-ε net A over-corrects to a cold signature"

## Step 4: Spectral / Sub-band Views
- ΔL(λ) plot with all options and the zero line
- Sub-band table (8–10 vs 10–12 µm) showing net B's spectral-shaping
  split — with a "half-band seeker" toggle that re-ranks the nets

## Step 5: Detection Range
- Range-vs-option bars with the "edge-limited at 3 km" annotation and the
  explanatory note that camo reduces signature, not detectability here

## Step 6: Export
- Camo trade report: signature table, ΔL figure, emissivity inputs,
  recommendation

## Script Window Commands
```python
from radiant.io.aster_library import load_aster_spectrum
from radiant.io.measurement import load_measured_curve
steel = load_aster_spectrum("steel_oxidized_aster.txt")
net_c = load_measured_curve("camo_net_c.csv", x_unit="um")  # 3 pts → interp

# spectral ε → radiance → S8 (Gap 47 workaround):
L = eps_of_lambda * planck(T_surface)
np.savetxt("L_option.csv", ...)   # wavelength_um, L_W_m2_sr_um
sensor.set("source.target.user_radiance_path", "L_option.csv")
sensor.set("source.regime_override", "extended")
```

## GUI Requirements Summary

| Requirement | Priority | Gap |
|-------------|----------|-----|
| ASTER + measured-ε import with overlay | High | **CLOSED** (io/aster_library, io/measurement) |
| Sparse-spectral interpolation with visible assumption | Medium | np.interp wrapper; documented |
| Spectral ε → radiance composition (S8) | High | Registry Gap 47 (GUI composes until a real ε path exists) |
| Signature card (SCNR + reduction %) as headline | High | — |
| ΔL(λ) and sub-band views | Medium | — |
| Detection-range panel with edge-limit note | Low | — |
