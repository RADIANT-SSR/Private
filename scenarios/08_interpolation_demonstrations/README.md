# 08 — Interpolation Demonstrations (supplementary, outside the 35-scenario catalog)

`docs/guides/scenario_catalog.md` defines a closed set of 35 scenarios,
5 per persona (personas 01–07). This folder is a **deliberate addition
beyond that catalog**, not a renumbering or extension of any existing
persona — added to demonstrate
`scripts/synth_modtran/family_interpolate.py` (the per-family MODTRAN
atmosphere interpolator) with realistic, runnable examples, per an
explicit request to build "a few additional new scenarios that require
the interpolation."

It follows the same scenario trio convention (`walkthrough.md`,
`gui_workflow.md`, `gaps.md`, `inputs/`/`scripts/`/`outputs/`) as the
catalog scenarios, but is not itself part of the catalog and does not
get a persona name — there is no persona here, just a tool
demonstration.

## Contents

- **8.1 — Off-nadir angle interpolation.** Query 37.5° against the
  `zenith_fan_us_standard` family (0/30/45/60°), quantified against
  naive nearest-neighbor selection.
- **8.2 — Target-altitude interpolation.** Query 15 km against the
  `altitude_ladder_stratospheric` family (0/1/5/10/20/29 km), same
  method, different axis type, showing the tool generalizes.
- **8.3 — Boost-phase target-altitude sweep (skeleton).** A missile-
  defense LEO MWIR tracker sweeps a booster's target altitude 0→300 km
  against the *shipped interpolated* library, crossing three regimes:
  interpolated (0–29 km), PENDING (29–100 km — data-limited, gated on the
  boost-ladder run set), and the Gap 95 vacuum leg (≥ 100 km). Unlike 8.1
  and 8.2, it uses the shipped `midlat_summer_ladders` (real MODTRAN data,
  not synthetic) and demonstrates graceful handling of a data-limited band.

Both use *synthetic* (not real MODTRAN) atmosphere data — see
`modtran/synthetic/README.md`. They demonstrate the interpolation
*method*, which is independent of whether the underlying data is real
or synthetic; only the absolute numbers are provisional.
