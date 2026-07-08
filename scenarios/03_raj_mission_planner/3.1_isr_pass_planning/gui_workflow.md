# Scenario 3.1 — GUI Workflow Requirements

How Raj would run orbit geometry and pass planning in the RADIANT GUI, and
what the GUI must provide. (Per the house rule that every scenario
documents its GUI requirements. The GUI is not yet built; this is a
requirements capture.)

---

## Raj's workflow in the GUI

1. **Load the mission config.** Import `raj_orbit_sensor.xlsx`. The GUI
   shows the orbit altitude, the sensor summary, and the collection
   constraints (max slew, NIIRS floor).
2. **Orbit dashboard.** The GUI calls `radiant.core.orbit` and displays
   period, orbital velocity, ground-track speed, and orbits/day as a small
   read-out panel — the numbers Raj quotes in a tasking review.
3. **Off-nadir trade.** Raj drags an off-nadir-angle slider; the GUI
   re-runs the chain and live-updates GSD, NIIRS, SNR, ground range, and
   swath, with the NIIRS floor drawn as a horizontal line. He immediately
   sees the angle where NIIRS crosses the floor.
4. **Access corridor.** The GUI plots ground range vs off-nadir angle
   (`fig2`) with the agility limit and the NIIRS-quality limit marked, so
   Raj reads the usable corridor half-width directly.
5. **Coverage read-out.** Nadir swath × ground-track speed → area-coverage
   rate and per-pass coverage, shown in mission-friendly units (km²/s,
   km²/pass).

---

## MATLAB-like script/command window (standing GUI requirement)

Raj's core ask is an interactive command window (per the GUI vision memo):

```python
>>> from radiant.core.orbit import orbital_period_s, ground_track_speed_m_s
>>> orbital_period_s(600e3) / 60          # minutes
96.54
>>> ground_track_speed_m_s(600e3)         # m/s, sub-satellite
6910.9

# Off-nadir image quality at a glance
>>> s = load("raj_orbit_sensor")
>>> s.set("geometry.path_zenith_rad", radians(42))
>>> r = s.evaluate()
>>> r.metrics["niirs"], r.metrics["gsd_geometric_mean_m"]
(6.00, 1.11)

# Coverage rate composed from orbit + swath
>>> from radiant.performance.access_rate import compute_access_rate_m2_s
>>> compute_access_rate_m2_s(r.metrics["swath_width_m"], ground_track_speed_m_s(600e3)) / 1e6
```

Requirements this implies:
- **Orbit helpers callable from the command window** with unit-labeled
  numeric echo.
- **A pointing-angle sweep primitive** that re-runs the chain and returns
  the imaging-quality metrics as arrays for plotting.
- **Composition helpers surfaced** (access_rate) so coverage can be built
  from orbit + chain outputs without leaving the window.

---

## GUI-specific gaps

- The GUI should offer a **revisit / repeat-ground-track** panel once that
  model exists (see `gaps.md`, Gap 51) — orbits/day is a coarse proxy; a
  planner wants target-specific revisit time.
- The GUI needs a **"see vs image" distinction** in the access-corridor
  view: shade the agility-reachable corridor differently from the
  NIIRS-quality corridor, since the takeaway of this scenario is that they
  differ.
