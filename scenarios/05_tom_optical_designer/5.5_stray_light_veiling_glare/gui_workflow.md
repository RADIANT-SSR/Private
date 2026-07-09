# Scenario 5.5 — GUI Workflow Requirements

How Tom would run the stray-light study in the RADIANT GUI.
(Per the house rule; the GUI is not yet built.)

## Workflow

1. **Load the scene + FRED numbers** (`tom_straylight.xlsx`): scene
   reflectances, VGI, out-of-field irradiance, sensor config.
2. **Stray-light panel:** pick the mode (veiling glare / absolute irradiance)
   and see the resulting stray_e, SNR, contrast SNR, and NIIRS side-by-side
   with the clean baseline. **The GUI must warn that `veiling_glare` mode is
   currently inert (CU-062)** and offer the VGI→absolute-irradiance
   conversion until the fix lands.
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
>>> s.set("optics.stray.input_mode", "absolute_irradiance")   # NOT veiling_glare (CU-062)
>>> s.set("optics.stray.absolute_irradiance_W_m2", 2.5)
>>> m = s.evaluate().metrics
>>> m["snr"], m["niirs"]
(124.3, 10.068)
```

Requirements: stray-light mode + magnitude callable from the window; a
sweep primitive over the stray level; NIIRS and contrast SNR in the returned
metrics; a noise-term breakdown accessor.

## GUI-specific gaps

- **VGI-mode correctness warning** (CU-062): the GUI must not silently let a
  user run the broken `veiling_glare` mode and read a clean-optics result.
- **2-D stray-light PSF ingestion + MTF impact** (Gap 60): the spatial half
  of the stray-light story that the scalar model omits.
