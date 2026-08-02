# Scenario 5.5 — GUI Workflow Requirements

How Tom would run the stray-light study in the RADIANT GUI.
(Per the house rule; the GUI is not yet built.)

## Workflow

1. **Load the scene + FRED numbers** (`tom_straylight.xlsx`): scene
   reflectances, VGI, out-of-field irradiance, sensor config.
2. **Stray-light panel:** pick the mode (veiling glare / absolute irradiance)
   and see the resulting stray_e, SNR, contrast SNR, and NIIRS side-by-side
   with the clean baseline. (Both modes are now correct — CU-062, the
   veiling-glare solid-angle bug, is fixed.)
3. **Tolerance slider:** sweep VGI (or absolute irradiance) and watch
   contrast SNR and ΔNIIRS cross their budgets live; the tolerance band is
   shaded and Tom's FRED value is marked.
4. **Noise budget:** a stacked/side-by-side bar of the noise terms (shot,
   read+dark, stray shot) clean vs with stray — the design conversation.
5. **(Future) 2-D PSF import** (Gap 60): drop a FRED/Zemax stray-light PSF
   and see its MTF impact, not just the noise pedestal.

## MATLAB-like command window

```python
>>> from radiant.api import Sensor
>>> s = Sensor(); s.set("source.scene_type", "extended")
>>> s.set("source.target.reflectance", 0.30)
>>> s.set("optics.stray.input_mode", "veiling_glare")   # fixed in CU-062
>>> s.set("optics.stray.veiling_glare_fraction", 0.03)
>>> m = s.evaluate().metrics   # (full scene config elided; illustrative)
>>> m["snr"], m["niirs"]       # 3% VGI: ~4% SNR nick, 0.03 NIIRS
(520.3, 11.037)
```

Requirements: stray-light mode + magnitude callable from the window; a
sweep primitive over the stray level; NIIRS and contrast SNR in the returned
metrics; a noise-term breakdown accessor.

## GUI-specific gaps

- **2-D stray-light PSF ingestion + MTF impact** (Gap 60): the spatial half
  of the stray-light story that the scalar model omits — the remaining
  stray-light gap now that the veiling-glare radiometry (CU-062) is fixed.

## Interpolated-atmosphere availability

Switching **Atmosphere → Model** to `interpolated` works first try on this scene. The picker pre-selects **`midlat_summer_sensor_ladder`** (profile `midlat_summer`, down-looking; covers ground targets only (target altitude fixed at 0 km), sensor 3-100 km plus 40000 km (GEO), nadir only (LOS zenith 0 degrees)); *Use this family* writes `atmosphere.interpolation_axes = 'sensor_altitude_m'`. `Sensor.atmosphere_family_suggestion()` is the same answer from a script.
