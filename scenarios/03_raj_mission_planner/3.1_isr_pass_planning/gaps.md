# Scenario 3.1 — Gaps and Friction

Issues encountered building/running the orbit-geometry / pass-planning
scenario. Registry items are mirrored into `docs/tracking/gaps.md`.

---

## RESOLVED during this scenario

### Orbit-kinematics calculator (was the primary gap)
The catalog flagged "no orbit → geometry calculator, pass planning".
**Built as `radiant.core.orbit`** (committed e32188e):
`orbital_velocity_m_s`, `orbital_period_s`, `ground_track_speed_m_s` for a
circular LEO altitude. 10 Level-0 tests, published truth anchors (500 km,
ISS). Added the Earth gravitational parameter `mu_earth_m3_s2` to
`core.constants`. This closes the gap that made `performance.access_rate`
un-runnable end-to-end: the chain cannot compute platform ground speed, so
`access_rate` took it as a free input with no producer. The orbit model is
that producer.

The chain already had the off-nadir *imaging* geometry Raj needed —
`gsd_cross_track_m`, `gsd_along_track_m`, `gsd_geometric_mean_m`,
`ground_range_m`, `swath_width_m`, and off-nadir-corrected `niirs` are all
surfaced (Gaps 5, 33–36, closed in earlier phases). So 3.1 needed only the
orbital-kinematics layer above the imaging chain, not new imaging physics.

---

## Framework gaps (mirrored to docs/tracking/gaps.md)

### Gap — no revisit / repeat-ground-track model
This scenario reports orbits/day (86400 / period) as a coverage proxy, but
true **revisit time** for a given target latitude needs the sun-sync nodal
regression, the repeat-cycle (J2) ground-track spacing, and the swath /
access-corridor overlap — none of which the orbit model covers (it is
single-orbit kinematics only). A repeat-ground-track / revisit calculator
is the natural next layer. Filed as Gap 51. Medium effort; not blocking
(orbits/day + access corridor answer the sizing question here).

### Note — access_rate is not surfaced as a chain metric (by design)
`performance.access_rate` is a standalone function, not wired into
`performance/stage.py`, because it needs platform velocity the chain does
not carry. Composing it script-side (swath metric × orbit ground speed) is
the intended pattern, now that the orbit model exists. No change proposed.

---

## Friction / lessons

- **`detector.n_pixels_cross`, not `n_pixels_cross_track`.** The
  cross-track array width parameter is `n_pixels_cross`; the longer name
  raises with a helpful suggestion. Noted for the next scenario author.
- **NIIRS extrapolation warnings at large off-nadir angles** (GSD beyond
  the GIQE-5 calibration range) fire correctly (Gap 22 flagging). For a
  pointing sweep this means the NIIRS-floor crossing near the agility limit
  is an extrapolation — the scenario reports it as approximate rather than
  treating the GIQE-5 value as exact there.
