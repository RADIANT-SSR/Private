# Phase 4 — Regime toggle & sub-pixel shape selector

**Category:** B/C (architecture-aware feature)
**Pre-reads:** PLAN.md §7; Phase 1 `classify_regime`; CLAUDE.md Rule 10 (Regime finalized in OpticsStage —
this GUI shows the *tentative* SourceStage classification only, since OpticsStage requires PSF).

## Hard constraint
**Do not edit `/src/`.** Do not add scenarios in `scenarios/`. The GUI must classify regime
itself using the math from view-model Phase 1.

## Goal
The user can:
1. Choose `auto` / `extended` / `sub_pixel` / `point_source` via a radio.
2. In `auto` mode, see which Rule-10 branch fired (e.g., `"angular_extent ≥ 2 × IFOV → EXTENDED"`).
3. When sub-pixel is active (override or auto-classified), the shape dropdown enables and the
   relevant size sliders highlight; the unused sliders are visibly de-emphasized (greyed, not hidden —
   the developer needs to see what's ignored).
4. The target mesh in 3D updates to reflect the chosen shape and orientation.

## Specifically scoped behaviors
- **Per-shape relevant size sliders** (the rest grey out):
  | Shape | Relevant |
  |---|---|
  | sphere | radius |
  | cylinder | radius, length |
  | flat_plate | length, width |
  | box | length, width, height |
  | cone | base_radius, height |
- **Orientation sliders** (yaw/pitch/roll) are always relevant for non-sphere shapes.
  For sphere, they are formally inert — grey them out and add a tooltip "Sphere projected
  area is orientation-invariant".
- **Extended-scene mode**: shape dropdown is greyed out — extended scenes do not use a target
  shape; the radiometry uses the GSD cell. The mesh is replaced by a small filled square at the
  target position whose side equals √(GSD²) (i.e., GSD by GSD).
- **Point-source mode**: render target as a single emissive dot. Document that
  `T7IntensityAtSource.REFERENCE_AREA_M2` (1.0 m² fictional reference) is what radiometry uses;
  no projected area is meaningful here. Show "—" for projected area in the readout.

## Files (modified, not created)
- `app/layout/target_controls.py` — add `disabled` logic per shape and per regime.
- `app/layout/mode_controls.py` — regime radio, with the live "reason" string under it.
- `app/layout/readout_panel.py` — show the regime reason inline.

## Tests
- `tests/test_regime_branches.py`: parameterized over five test states, each forcing one of:
  ang_ext ≥ 2*ifov, ang_ext ≤ 0.25*ifov, in-between, fill_fraction<1 override, manual override.
  Confirm the reason string is the documented one for that branch.
- `tests/test_shape_dispatch.py`: every shape choice in the dropdown produces a valid
  `TargetShape` instance via the view-model and a non-empty mesh via the scene builder.

## Forbidden
- Importing `_classify_regime` from `radiant.source.stage`. Re-derive in view-model — already
  done in Phase 1.
- Hiding the irrelevant sliders. Grey them out so the developer can see what is not contributing.

## Report (Category B/C)
- File list (only modifications expected).
- Test results.
- **Numerical truth anchor:** for one extended state and one sub-pixel state, hand-compute
  `angular_extent` and `ifov` and confirm the GUI reports the same to 6 sig figs.
- Screenshot showing the regime reason string under the radio.
- Note the SourceStage-vs-OpticsStage caveat: this GUI only shows tentative SourceStage regime.
