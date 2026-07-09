# Scenario 3.5 — GUI Workflow Requirements

How Raj would run the nighttime-feasibility study in the RADIANT GUI.
(Per the house rule; the GUI is not yet built.)

## Workflow

1. **Load the scene** (`raj_scene.xlsx`): target/terrain temperatures and
   emissivities, the tropical-atmosphere column, and the dual-band sensor
   config. The GUI should **warn** that selecting a climate preset does not
   set its humidity — prompt for `precipitable_water_cm` (Gap 57).
2. **Load the LST map** (GeoTIFF, once Gap 58 lands): the GUI renders the
   terrain-temperature field and reads the background envelope from it.
3. **Dual-band panel:** MWIR and LWIR side by side — SNR, contrast SNR,
   NEDT, MRT-at-Nyquist, and the ΔT/NEDT detectability margin, with a
   pass/fail against the confident-detection threshold.
4. **Day/night toggle** (Gap 59): flip solar illumination on/off and watch
   the reflected-solar term appear/vanish; the panel reports the
   thermal-vs-solar ratio per band and flags MWIR daytime solar
   contamination.
5. **Background sweep:** a slider on terrain temperature (or a draw-region
   on the LST map) re-drives the contrast SNR envelope live.

## MATLAB-like command window

```python
>>> from radiant.api import Sensor
>>> s = Sensor(); s.set("source.scene_type", "extended")
>>> s.set("source.target.temperature", 295, unit="K")
>>> s.set("source.contrast_reference.temperature", 288, unit="K")  # terrain
>>> s.set("atmosphere.standard_atmosphere", "tropical")
>>> s.set("atmosphere.precipitable_water_cm", 4.1)   # must set humidity too
>>> m = s.evaluate().metrics
>>> m["contrast_snr"], m["nedt_K"], m["mrt_at_nyquist_K"]
(133.7, 0.0269, 0.399)
```

Requirements: contrast-reference scene callable from the window; NEDT/MRT in
the returned metrics; a solar-term helper for the day/night comparison; a
humidity prompt tied to the atmosphere preset.

## GUI-specific gaps

- **Preset-humidity coupling** (Gap 57): the GUI should either couple the
  climate preset to a default PWV or force the user to set it, so a
  "tropical" selection can't silently run at US-standard humidity.
- **Raster map ingestion** (Gap 58) and a **day/night solar mode** (Gap 59)
  are the two GUI features this scenario most wants.
