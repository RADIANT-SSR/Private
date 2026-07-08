# Scenario 4.1 GUI Workflow: Target Detection Matrix

How this scenario would be completed in the RADIANT GUI.

## Persona
Lisa, analyst. A 12-target library, three sensor configs, four atmospheres,
and a quarterly-review detection matrix to brief.

## Step 1: Import the Target Library
- **File > Import > Target Library** (`load_target_library`): the 12-row
  workbook (name/dims/temperature/emissivity/material); the GUI shows the
  derived `projected_area_m2 = length × width` column and flags duplicate
  names or non-numeric cells before accepting

## Step 2: Load the Sensor Library
- Import the three sensor YAMLs; sensor C's outdated
  `optics.cold_stop_efficiency` surfaces a **deprecation banner** ("mapped
  to optics.nearfield_fraction") rather than an error — the config still
  runs

## Step 3: Define the Matrix Axes
- **Matrix builder**: target axis (from the library), atmosphere axis
  (clear / haze / tropical_haze / arctic_clear with visibility + profile),
  sensor axis — backed by `radiant.api.batch.BatchRunner`
- Detection settings: SCNR ≥ 5 (clutter-inclusive — the GUI labels this the
  detection number, distinct from noise-only SNR), scene clutter σ, swath
  edge zenith

## Step 4: Run and View the Matrix
- "Run Matrix" evaluates all 144 cells (BatchRunner); a **progress grid**
  fills in, with any failed cell shown red (Rule 17 — recorded, never
  dropped)
- Result heatmap per sensor: detection range [km], green/yellow/red, with
  "not detectable" and swath-edge (*) states; NIIRS-at-nadir column with the
  GIQE-extrapolation caveat chip
- **Worst-case panel**: the hardest target, with the EE_box-occlusion
  explanation ("detectability is how far the target pixel departs from
  background after EE_box weighting, not ε·B·A")

## Step 5: Export
- Color-coded Excel workbook (per-sensor sheets + summary), the matrix
  heatmap, the nadir-SCNR bar chart

## Script Window Commands
```python
from radiant.io.target_library import load_target_library
from radiant.api.batch import BatchRunner
targets = load_target_library("lisa_target_library.xlsx")

axes = [("target", {t.target_name: {...} for t in targets}),
        ("atmosphere", {...})]
result = BatchRunner({}, axes, sensor_factory=lambda _c: Sensor.from_yaml(path)).run(
    evaluate_cell)          # per-cell SCNR + detection-range bisection
result.pivot("detection_range_km", rows="target", cols="atmosphere")
```

## GUI Requirements Summary

| Requirement | Priority | Gap |
|-------------|----------|-----|
| Target-library import with derived area | High | **CLOSED** (io/target_library) |
| Matrix builder + batch runner | High | **CLOSED** (api/batch) |
| Deprecation banner for outdated params | Medium | **CLOSED** (Gap 12 alias) |
| SCNR (clutter-inclusive) as the detection metric | High | script-side (metrics exclude clutter — see gaps.md) |
| Per-cell failure surfacing | High | **CLOSED** (BatchRunner error column) |
| Color-coded matrix heatmap + Excel | High | — |
| Worst-case / hardest-target panel | Medium | — |
