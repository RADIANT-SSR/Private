# Scenario 4.2 — Maritime Ship Classification (Johnson DRI)

**Persona:** Lisa, image analyst planning maritime collections.
**Question:** With an airborne MWIR sensor, at what range can each ship
class be Detected, Recognized, and Identified?

This scenario is the first consumer of the new
`radiant.performance.johnson_criteria` model, which turns the Johnson
resolved-cycle criteria (Detection 1, Recognition 4, Identification 6.4
cycles across the target) into ranges.

---

## Inputs (intelligence / vendor formats — non-RADIANT)

| File | Format | Represents |
|------|--------|-----------|
| `inputs/lisa_ship_classes.xlsx` | Excel workbook (`ShipClasses` + `SensorConfig` sheets) | Ship lengths/heights and the MWIR UAV sensor configuration |

`inputs/create_spreadsheet.py` regenerates it. The critical dimension for
each ship is derived in the run script as √(length · height), the standard
2-D-target convention.

---

## The two limits

1. **Resolution (Johnson):** `R_task = √(L·H) / (2 · IFOV · N50_task)`.
   The range at which the sensor resolves the task's required cycles across
   the ship. IFOV here = 15 µm / 1.2 m = **12.5 µrad**.
2. **Horizon:** `√(2·R_E·h) = 253 km` for the 5 km platform. An airborne
   sensor cannot see a sea-level waterline beyond this, at any resolution.

The **binding range** for each task is `min(resolution range, horizon)`.

---

## Results (MWIR UAV, 12.5 µrad IFOV, 5 km altitude)

Identification range (the hardest task) and its binding limit:

| Ship class | Critical dim | ID resolution range | Binding limit |
|-----------|--------------|---------------------|---------------|
| Small boat | 3.5 m | 22 km | **resolution** (close to 22 km) |
| Patrol craft | 13.4 m | 84 km | **resolution** (close to 84 km) |
| Corvette | 30.0 m | 188 km | **resolution** (close to 188 km) |
| Frigate | 44.2 m | 276 km | **horizon** (253 km) |
| Destroyer | 52.8 m | 330 km | **horizon** (253 km) |
| Container ship | 94.9 m | 593 km | **horizon** (253 km) |

- **The fleet splits at the frigate.** Ships with a critical dimension
  above ~44 m are **horizon-limited** for identification — the sensor has
  ample resolution, and line-of-sight is the wall. Smaller craft are
  **resolution-limited** — even when they are within the 253 km horizon,
  they subtend too few pixels to identify, so Lisa must close range.
- For **detection**, every ship except the small boat is horizon-limited:
  a UAV can detect any patrol-craft-or-larger vessel out to the horizon.
- The **small boat** is resolution-limited at every task (detection 139 km,
  recognition 35 km, ID 22 km) — small, fast craft are the hard maritime
  ISR problem, and this quantifies why.

---

## Physics / modeling notes (house rule: explain the non-obvious)

- **Johnson criteria are a resolution/interpretability model, not a
  radiometric one.** The DRI range says whether *enough cycles* fall across
  the target; it assumes the target has adequate contrast to see those
  cycles. On a cold-sea MWIR background a warm ship usually does, but at
  the resolution-limited ranges a contrast/MTF (MRC/MRT) treatment would
  pull the ranges in — see the fragility note. (Filed as Gap 53.)
- **Critical dimension = √(L·H).** The 2-D-target convention: the geometric
  mean of the two principal dimensions, rather than the length alone (which
  would over-count a long, low hull) or the height alone (which would
  under-count).
- **The horizon is geometric.** `√(2·R_E·h)` neglects atmospheric
  refraction (~+8 %) and the ship's freeboard (a 30 m container stack is
  visible ~20 km beyond a waterline). Both *extend* the true horizon, so
  the 253 km figure is a conservative floor.
- **No chain run is needed.** DRI ranges are pure geometry (target size,
  IFOV, N50); the signal chain would only enter through a contrast/MTF
  extension. This is an analysis scenario over the new model.

---

## Fragility

- **Contrast-blind.** At the resolution-limited ranges (small craft), the
  true range also depends on target-vs-sea contrast and the system MTF at
  the relevant frequency. A low-contrast target at dusk would identify at
  shorter range than the geometric Johnson value. The model is the
  optimistic (high-contrast) bound.
- **Aspect-dependent.** √(L·H) assumes a broadside view; a bow-on aspect
  presents a much smaller critical dimension and shortens every range.
- **N50 is a 50 %-probability figure.** Reliable (>90 %) identification
  needs ~1.5× the N50 cycles, shrinking the ranges by ~1/3.

---

## Truth anchors for the Johnson model

Verified in `src/radiant/performance/tests/test_johnson_criteria.py`
(11 Level-0 tests) before this scenario consumed the model:

1. 3 m target, 50 µrad IFOV: detection 30 km, recognition 7.5 km,
   identification 4.6875 km (hand calc of `D/(2·IFOV·N50)`).
2. Range ordering detection > recognition > identification.
3. Resolved-cycles round-trip: `resolved_cycles` at `R_task` returns N50.
