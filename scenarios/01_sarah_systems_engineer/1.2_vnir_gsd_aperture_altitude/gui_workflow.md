# Scenario 1.2 — GUI Workflow Requirements

How Sarah would run this GSD-vs-aperture-vs-altitude trade in the RADIANT
GUI, and what the GUI must provide to support it. (Per the house rule that
every scenario documents its GUI requirements. The GUI is not yet built;
this is a requirements capture.)

---

## Sarah's workflow in the GUI

1. **Load design + orbit inputs.** Import `sarah_vnir_design.xlsx` and
   `silicon_ccd_qe.csv`. The GUI shows the QE curve plotted, with the
   450–700 nm pan band shaded and the band-averaged QE annotated.
2. **Set the orbit.** Enter LTAN (10:30) and target latitude (35°N). The
   GUI calls `radiant.core.solar_geometry` and displays a small table or
   annual curve of **solar zenith vs season** — Sarah immediately sees
   winter is the worst case (θ_z = 62°).
3. **Define the trade.** Pick the two sweep axes (aperture 20–80 cm,
   altitude 400–600 km) and the fixed constraint (GSD = 0.5 m). The GUI
   must understand that focal length is *derived* from the GSD constraint,
   not an independent axis.
4. **Run and view the contour.** The GUI renders the SNR contour over the
   aperture × altitude plane with the SNR-spec line and the
   diffraction-limit line overlaid (the two constraint curves from
   `fig1`). Sarah drags a marker across the plane and reads SNR, Q, f/#,
   and diffraction-GSD at the cursor.
5. **Check seasons.** At a chosen design point, the GUI shows the seasonal
   SNR bars (`fig2`) so Sarah confirms the design passes in winter, not
   just at the annual mean.

---

## MATLAB-like script/command window (standing GUI requirement)

Sarah's core ask is an interactive command window (per the GUI vision
memo) where she can, without editing a script:

```python
# Solar geometry at a glance
>>> from radiant.core.solar_geometry import solar_zenith_angle_rad
>>> import math
>>> math.degrees(solar_zenith_angle_rad(35.0, 355, 10.5))   # winter, 10:30
62.19

# Sweep aperture at fixed altitude, plot SNR
>>> s = load("sarah_vnir_design")           # returns a configured Sensor
>>> sweep = s.sweep("optics.aperture_diameter_m", linspace(0.2, 0.8, 13))
>>> plot(sweep, x="optics.aperture_diameter_m", y="snr")
```

Requirements this implies:
- **Solar-geometry helpers callable from the command window** with live
  numeric echo (units shown).
- **Derived-parameter awareness:** when Sarah sweeps aperture at fixed
  GSD, the window must recompute focal length per point automatically — a
  "constraint" concept, not just free parameters.
- **Inline contour + overlay plotting** (`contour(sweep2d, ...)`) with
  named constraint lines (spec, diffraction limit).
- **Cursor read-out** returning all derived quantities (SNR, Q, f/#,
  diffraction-GSD) at a point on the trade surface.

---

## GUI-specific gaps

- The GUI needs a **two-axis sweep + one-constraint** run mode. The
  current `Sensor.sweep` is single-axis; a 2-D trade with a derived
  constraint (GSD → focal) is what this scenario exercises, and the GUI
  should expose it as a first-class "trade study" panel.
- The GUI should surface the **sampling regime** (detector- vs
  diffraction-limited) as a color band or annotation, since it is the
  qualitative takeaway of the trade — see the framework gap in `gaps.md`.
