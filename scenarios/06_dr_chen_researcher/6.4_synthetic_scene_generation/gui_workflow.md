# Scenario 6.4 — GUI Workflow Requirements

How Dr. Chen would build and test against a synthetic scene in the RADIANT
GUI. (Per the house rule; the GUI is not yet built.)

## Workflow

1. **Load the scene** (`chen_scene.xlsx`): the target table (range/T/ε/size)
   and the uniform background, plus the LWIR sensor config.
2. **Per-target radiometry panel:** for each target the GUI shows filled-pixel
   signal, background signal, noise σ, fill fraction, and contrast SNR — with
   a flag when the target is resolved (ff = 1) vs. sub-pixel.
3. **Scene-strip view:** a 1-D pixel strip with a live noise realization
   (re-roll button, seed field) and the contrast-SNR map beneath it.
4. **Detection-range sweep:** a slider on range (or ΔT, or target size)
   updates the contrast SNR and the ROC curve live; the panel reports the
   P_d ≥ 0.9 and 50/50 ranges as the design-driving numbers.
5. **ROC panel:** ROC curves for the selected operating points with the P_fa
   budget marked, and AUC vs. operating-point P_d shown side by side.

## MATLAB-like command window

```python
>>> from radiant.performance.roc import roc_curve, detection_probability, roc_auc
>>> detection_probability(3.7, 1e-4)      # SNR 3.7, strict false-alarm budget
0.495
>>> roc_auc(3.7)                          # separation is still excellent
0.9956
>>> pfa, pd = roc_curve(3.7, n_points=300)
>>> plot(pfa, pd); xscale('log')          # ROC at the detection floor
```

Requirements: ROC + detection-probability callable from the window; a sweep
primitive over range / ΔT / size that re-drives contrast SNR; a noisy-strip
generator with a settable seed; a read-out of the reliable-detection and
50/50 ranges.

## GUI-specific gaps

- A **2-D scene canvas** (place targets spatially, PSF-convolve, render the
  mixed-radiance image) is the natural GUI home for the multi-target scene
  capability that the framework still lacks (see `gaps.md`). Until then the
  GUI can only show the 1-D scripted strip.
- **Bias between AUC and operating-point P_d** should be shown together so a
  user doesn't read a high AUC as "will detect at my P_fa budget."

## Interpolated-atmosphere availability

Switching **Atmosphere → Model** to `interpolated` works first try on this scene. The picker pre-selects **`midlat_summer_sensor_ladder`** (profile `midlat_summer`, down-looking; covers ground targets only (target altitude fixed at 0 km), sensor 3-100 km plus 40000 km (GEO), nadir only (LOS zenith 0 degrees)); *Use this family* writes `atmosphere.interpolation_axes = 'sensor_altitude_m'`. `Sensor.atmosphere_family_suggestion()` is the same answer from a script.
