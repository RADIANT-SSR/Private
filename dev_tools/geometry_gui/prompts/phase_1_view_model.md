# Phase 1 — View-model layer

**Category:** B (Core abstraction with dimensional audit)
**Pre-reads:** PLAN.md §4, §6, §8; [src/radiant/core/geometry.py](../../../src/radiant/core/geometry.py),
[src/radiant/source/shape.py](../../../src/radiant/source/shape.py),
[src/radiant/source/shapes/](../../../src/radiant/source/shapes/),
[src/radiant/core/los_geometry.py](../../../src/radiant/core/los_geometry.py),
[src/radiant/core/regime.py](../../../src/radiant/core/regime.py).

## Hard constraint
**Do not edit `/src/`.** Re-implement small math (Rule-10 regime decision) in this layer
rather than reaching into private `/src` symbols.

## Goal
A pure-Python view-model: `SceneState` (frozen dataclass) → derived geometry & projected area,
no plotly, no Dash. This is the layer the rest of the GUI builds on, and the layer that gets
unit-tested.

## Files to create

### `app/state.py` — one frozen dataclass
```python
@dataclass(frozen=True)
class SceneState:
    # Observer
    observer_altitude_m: float
    observer_look_angle_rad: float
    observer_yaw_rad: float
    observer_pitch_rad: float
    observer_roll_rad: float
    # Target
    target_altitude_m: float
    target_shape: Literal["sphere","cylinder","flat_plate","box","cone"]
    target_radius_m: float
    target_length_m: float
    target_width_m: float
    target_height_m: float
    target_base_radius_m: float
    target_yaw_rad: float
    target_pitch_rad: float
    target_roll_rad: float
    target_fill_fraction: float
    # Sensor
    focal_length_m: float
    pixel_pitch_m: float
    # Sun
    solar_zenith_rad: float
    relative_azimuth_rad: float
    # Mode
    regime_override: Literal["auto","extended","sub_pixel","point_source"]
    background_kind: Literal["none","cold_space","ground","at_aperture"]
```
Provide one `default()` classmethod that returns a sensible LEO-ish baseline.

### `app/view_model.py` — pure functions (Rule 19: one calc, one function; bundle only when truly coupled)
- `build_scene_geometry(state) -> SceneGeometry` — wraps `ObserverGeometry`/`TargetGeometry`.
- `build_target_shape(state) -> TargetShape` — instantiates one of `Sphere/Cylinder/FlatPlate/Box/Cone`
  using `state.target_*` fields. Confirm the actual constructor signatures before writing
  (read the shape source files).
- `compute_view_direction_scene(state) -> np.ndarray` — unit 3-vector target→observer in **scene frame**
  (+Z toward target from observer's POV ⇒ observer→target = +Z, so target→observer = −Z, then
   rotated by observer attitude). Document the convention in the docstring.
- `view_direction_body(state) -> np.ndarray` — same vector transformed into the **target body frame**
  using the target's yaw/pitch/roll (ZYX). Re-implement the 4-line transpose locally; do not
  import `radiant.source.shapes._helpers`.
- `projected_area_m2(state) -> float` — calls `build_target_shape(state).projected_area(view_direction_body(state))`.
  This is the canonical handoff to radiometry.
- `classify_regime(state) -> tuple[RadiometricRegime, str]` — returns the regime *and* a
  one-line human-readable reason ("ang_ext ≥ 2*ifov", "fill_fraction override", "user override: extended", …).
  Mirror the Rule-10 logic from `CLAUDE.md` and from `SourceStage._classify_regime` —
  re-derive, do not import.
- `derived_readout(state) -> dict[str, tuple[float, str]]` — returns each labeled value with its
  units string. Used by the readout panel in Phase 5. Keys: `slant_range`, `ground_range`, `gsd`,
  `ifov`, `angular_extent`, `pixel_area`, `projected_area`, `fill_fraction_effective`.

### `tests/test_view_model.py`
1. `test_scene_geometry_matches_core_class`: build a SceneState, confirm slant range and GSD
   equal `SceneGeometry`'s own `.slant_range_m` / `.gsd_m`.
2. `test_projected_area_parity`: for each of the five shapes, build a shape directly and
   confirm `view_model.projected_area_m2(state)` equals `shape.projected_area(v_body)` exactly
   (machine precision, `abs=0.0`, `rel=1e-15`). This is the C3 invariant.
3. `test_regime_truth_table`: a table of (angular_extent, ifov, fill_fraction, override) →
   expected regime. Cover all five Rule-10 branches plus the override.
4. `test_view_direction_unit_norm`: across 50 random states, ‖view_direction‖ = 1.0 ± 1e-12
   in both frames.

## Forbidden
- Importing private symbols (`_underscored`) from `radiant.*`. If you need the math, re-implement.
- Calling `ParameterSet` / `shape_factory.build_shape()`. Construct shapes directly.
- Writing any plotly or Dash code in this phase.

## Report (Category B)
- File list.
- Test results.
- **Dimensional audit** for `projected_area_m2`: input units → output units, every step.
- **Failure modes tested**: zero-size shape, view direction parallel to plate normal,
  view direction perpendicular to plate normal, fill_fraction = 0, fill_fraction > 1.
- Confirmation that the C3 invariant test (`test_projected_area_parity`) passes.
