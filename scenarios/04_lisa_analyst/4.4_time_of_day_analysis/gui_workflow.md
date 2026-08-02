# Scenario 4.4 — GUI Workflow Requirements

How Lisa would run a diurnal detectability analysis in the RADIANT GUI,
and what the GUI must provide. (Per the house rule that every scenario
documents its GUI requirements. The GUI is not yet built; this is a
requirements capture.)

---

## Lisa's workflow in the GUI

1. **Load the diurnal profile.** Import `diurnal_thermal_profile.csv`. The
   GUI plots the target and background temperature curves and their ΔT,
   marking where the curves cross.
2. **Load the sensor.** Import `lisa_lwir_sensor.xlsx`; the GUI shows the
   LWIR configuration and flags the well-fill at the hottest profile point
   (a saturation warning Lisa must resolve by lowering integration time).
3. **Run the temporal sweep.** The GUI runs the chain over every time step
   and builds the contrast-SNR-vs-time curve, shading the washout windows
   and drawing the detectability threshold.
4. **Read the washouts.** Lisa reads the two daily washout windows off the
   plot and — critically — sees they are offset from the ΔT = 0 crossings
   because of the emissivity difference.
5. **Replan.** She adjusts the detectability threshold or emissivities and
   re-runs to see how the washout windows move.

---

## MATLAB-like script/command window (standing GUI requirement)

Lisa's core ask is an interactive command window (per the GUI vision memo)
where she can drive a temporal sweep and difference two pixels:

```python
>>> prof = load_csv("diurnal_thermal_profile.csv")
>>> def contrast(hour):
...     tt, tb = prof.interp(hour)          # target, background temps
...     St, Nt = pixel(tt, 0.92)            # signal, noise of target pixel
...     Sb, Nb = pixel(tb, 0.95)
...     return (St - Sb) / hypot(Nt, Nb)
>>> plot([contrast(h) for h in prof.hours], x=prof.hours)
>>> crossings(contrast, prof.hours)         # -> [5.2, 18.8] h
```

Requirements this implies:
- **A temporal-sweep primitive** that maps a time axis onto a swept
  parameter (temperature here) from an input profile.
- **A two-pixel differencing helper** (or, better, a first-class extended
  target-vs-background contrast — see `gaps.md` Gap 52) so the analyst does
  not have to hand-build the differential.
- **Zero-crossing / threshold-crossing finders** returning the times, so
  washout windows come back as numbers, not just a plot.
- **Well-fill / saturation warnings surfaced live** — the LWIR
  integration-time trap should be caught by the GUI, not discovered by a
  flat contrast curve.

---

## GUI-specific gaps

- The GUI needs a **profile-driven sweep mode** (sweep a parameter along a
  loaded time series), distinct from the uniform linspace sweep used in
  other scenarios.
- The GUI should distinguish **temperature crossover from radiance
  crossover** in the plot legend — the whole analytic point is that they
  differ when emissivities differ.

## Interpolated-atmosphere availability

Switching **Atmosphere → Model** to `interpolated` works first try on this scene. The picker pre-selects **`midlat_summer_sensor_ladder`** (profile `midlat_summer`, down-looking; covers ground targets only (target altitude fixed at 0 km), sensor 3-100 km plus 40000 km (GEO), nadir only (LOS zenith 0 degrees)); *Use this family* writes `atmosphere.interpolation_axes = 'sensor_altitude_m'`. `Sensor.atmosphere_family_suggestion()` is the same answer from a script.
