# Scenario 3.3 — GUI Workflow Requirements

How Raj would run the procurement comparison in the RADIANT GUI. (Per the
house rule; the GUI is not yet built.)

## Workflow

1. **Load proposals** (`raj_sensor_proposals.xlsx`): three vendor columns,
   requirements, common operating point.
2. **Comparison table:** the GUI evaluates all three through the chain and
   shows SNR/NIIRS/NEDT/MTF/GSD side by side, best-per-metric highlighted.
3. **Compliance matrix:** green/red PASS/FAIL per requirement per vendor,
   with a fully-compliant flag (here: none — GSD binds).
4. **Radar chart:** normalised multi-metric view (the `fig1` spider plot).
5. **Leverage analysis:** the GUI shows, per vendor, which +10 % parameter
   improvement buys the most NIIRS (from `giqe5_sensitivity`).

## MATLAB-like command window

```python
>>> a = evaluate("Vendor A"); b = evaluate("Vendor B")   # -> metric dicts
>>> compare([a, b, c], metrics=["snr","niirs","nedt","gsd","mtf_at_nyquist"])
>>> from radiant.performance.giqe_sensitivity import giqe5_sensitivity
>>> giqe5_sensitivity(a["gsd"], a["rer"], a["snr"]).per_percent
{'gsd': ..., 'rer': ..., 'snr': ...}
```

Requirements: a multi-config compare primitive (evaluate N sensors, tabulate
metrics), a compliance-matrix helper (metrics vs thresholds), a radar-chart
view, and the sensitivity leverage read-out.

## GUI-specific gaps

- A **compliance-matrix panel** (metrics × requirements → PASS/FAIL + totals)
  should be first-class for procurement.
- A **PDF spec-sheet importer** (Gap 55) would remove the manual
  transcription step; until then a structured workbook is the input.

## Interpolated-atmosphere availability

Switching **Atmosphere → Model** to `interpolated` works first try on this scene. The picker pre-selects **`midlat_summer_sensor_ladder`** (profile `midlat_summer`, down-looking; covers ground targets only (target altitude fixed at 0 km), sensor 3-100 km plus 40000 km (GEO), nadir only (LOS zenith 0 degrees)); *Use this family* writes `atmosphere.interpolation_axes = 'sensor_altitude_m'`. `Sensor.atmosphere_family_suggestion()` is the same answer from a script.
