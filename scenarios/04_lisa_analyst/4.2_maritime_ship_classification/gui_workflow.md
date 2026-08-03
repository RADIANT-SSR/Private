# Scenario 4.2 — GUI Workflow Requirements

How Lisa would run maritime DRI classification in the RADIANT GUI, and
what the GUI must provide. (Per the house rule that every scenario
documents its GUI requirements. The GUI is not yet built; this is a
requirements capture.)

---

## Lisa's workflow in the GUI

1. **Load the ship table and sensor.** Import `lisa_ship_classes.xlsx`.
   The GUI shows the ship list with derived critical dimensions √(L·H) and
   the sensor's IFOV and horizon range computed and displayed.
2. **DRI matrix.** The GUI renders the Detection/Recognition/Identification
   range table, color-coding each cell by its binding limit (resolution
   vs horizon).
3. **Range bars.** A horizontal bar chart per ship (the `fig1` view) with
   the horizon drawn as a vertical line, so Lisa sees at a glance which
   ships are horizon-limited.
4. **Cycles-vs-range.** A drill-down plot (the `fig2` view) showing
   resolved cycles falling with range and crossing the N50 thresholds, for
   a selected ship.
5. **What-if.** Lisa changes the platform altitude (moving the horizon) or
   the focal length (moving the IFOV) and the matrix updates live.

---

## MATLAB-like script/command window (standing GUI requirement)

Lisa's core ask is an interactive command window (per the GUI vision memo):

```python
>>> from radiant.performance.johnson_criteria import johnson_range_m, JOHNSON_N50
>>> ifov = 15e-6 / 1.2                       # pitch / focal
>>> crit = sqrt(130 * 15)                    # frigate √(L·H)
>>> johnson_range_m(crit, ifov, JOHNSON_N50["identification"]) / 1e3
276.0
>>> from radiant.core.constants import R_EARTH_M
>>> sqrt(2 * R_EARTH_M * 5000) / 1e3         # horizon at 5 km
252.4
```

Requirements this implies:
- **Johnson helpers callable from the command window**, with the N50 table
  discoverable.
- **A horizon helper** (or a geometry namespace) so the binding-limit
  comparison is one call, not a hand-coded √(2·R_E·h).
- **A target-table sweep**: apply `johnson_range_m` across a loaded ship
  list and return a matrix for tabulation/plotting.

---

## GUI-specific gaps

- The GUI should expose the **binding-limit concept** as a first-class
  overlay (resolution vs horizon vs — once Gap 53 lands — contrast/MRC),
  since "which limit binds" is the analytic takeaway.
- A **target-library panel** (ship classes with dimensions) would let Lisa
  pick from a catalog rather than re-enter dimensions — parallel to the
  target-library importer built for scenario 4.1.
