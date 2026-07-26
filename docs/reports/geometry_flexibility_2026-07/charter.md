# Geometry Flexibility Audit — Charter (Rule 28)

**Status:** Complete (2026-07-26) — findings in `findings.md`; remediation plan at `docs/plans/Geometry_Flexibility_Plan.md` (Draft)
**Chartered by:** Project owner (Jason), 2026-07-26
**Auditor:** Claude (coding agent), single-agent inline sweep
**Folder:** `docs/reports/geometry_flexibility_2026-07/`

## Objective

Deep audit of RADIANT's scene-geometry capability against the owner's target
state: **complete viewing-geometry flexibility** — air-to-air, air-to-ground,
ground-to-air, ground-to-space, space-to-space in either direction, and
horizontal paths — for any observer/target altitude pair. Identify every
place the codebase and GUI assume a down-looking sensor, with explicit
attention to atmospheric-propagation impacts. Deliver a remediation plan.

## Scope

- `src/radiant/geometry/` (stage, modes, schema, manifest) and the geometry
  core (`core/viewing_triangle.py`, `core/los_geometry.py`, `core/geometry.py`,
  `core/solar_geometry.py`, `core/orbit.py`).
- The full atmosphere subsystem: protocol/geometry contracts, all backends
  (simple, exo, exo-target, tabulated, interpolated, MODTRAN), the §6.1
  assembly equation, quantity bundle, and turbulence.
- Downstream geometry consumers: platform (smear), performance (GSD, ground
  range, NIIRS, detection range, access rate), regime classification inputs.
- GUI geometry surfaces: mode form, angle panel/readout, 2D schematic viewer,
  and scenario-type steering.
- Governing documents: ADR-0006, `RADIANT_Geometry.md`,
  `RADIANT_Use_Case_Matrix.md`, `RADIANT_Atmosphere.md`, prior owner rulings.

## Out of scope

Clouds/weather (Gap 82), active imaging (Gap 106), ellipsoidal Earth,
polarization. Refraction is discussed only as it gates near-horizon paths.

## Disposition rule

Per Rule 28, every finding carries exactly one disposition: **CU'd**,
**Planned**, or **Declined** (with rationale). See `findings.md` §5.
