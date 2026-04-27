# Phase 6 — Sun direction & background marker

**Category:** B (Geometry feature, no new physics)
**Pre-reads:** PLAN.md §8 G1 (sun parameters not yet in legacy schema); Phase 2 stubs
`sun_arrow.py` and `background_marker.py`.

## Hard constraint
**Do not edit `/src/`.** Sun zenith/azimuth live only in this GUI's SceneState — they don't
yet have parameter-schema entries. This is the documented Stage-2 gap (G1).

## Goal
1. Sun arrow rendered in 3D: a long arrow originating at the target, pointing **toward the sun**.
   Direction computed from `solar_zenith_rad` (`theta_s`) and `relative_azimuth_rad` (`delta_phi`)
   in the local horizontal frame at the target.
2. Earth shows a soft terminator hint — a great circle perpendicular to the sun direction,
   shaded slightly differently on the night side. (Visual cue only; not a precise terminator.)
3. Background marker: a colored ring around the target marker, color-coded by `background_kind`:
   - `none` → no ring
   - `cold_space` → dark blue
   - `ground` → tan/brown
   - `at_aperture` → grey
   Tooltip on the ring names the descriptor class (`AtApertureBackground`, `ColdSpaceBackground`,
   `GroundBackground`, `UserSpectralBackground`) — pulled from
   [src/radiant/core/descriptors.py](../../../src/radiant/core/descriptors.py).

## Sun-vector math (in local horizontal frame at the target)
```
n̂_sun = ( sin(θ_s) * cos(Δφ),
          sin(θ_s) * sin(Δφ),
          cos(θ_s) )      # +Z = local zenith
```
Then rotate `n̂_sun` from target's local horizontal frame into the scene-display frame using
the target's position on the (display-scaled) Earth. Document the rotation in the module
docstring.

## Files
- `app/scene_builder/sun_arrow.py` — fill in the stub from Phase 2.
- `app/scene_builder/background_marker.py` — fill in the stub from Phase 2.
- `app/scene_builder/earth_mesh.py` — augment to accept a sun-direction argument and shade
  the night side. (Modification, not a new module — this is the same Earth mesh, just with
  shading.)

## Tests
- `tests/test_sun_arrow.py`:
  - `theta_s = 0`: arrow points along +Z at the target's local frame (sun overhead).
  - `theta_s = π/2, Δφ = 0`: arrow lies in the local horizontal plane along +X (sun on horizon
    in the cross-track direction).
  - Across 50 random (θ_s, Δφ), the arrow vector has unit norm.
- `tests/test_background_marker.py`: each `background_kind` produces a marker of the documented
  color; `none` produces no marker trace.

## Forbidden
- Modeling actual ephemerides. This is a developer tool; θ_s and Δφ are hand-set sliders.
- Computing solar irradiance or any radiometric quantity. This phase is geometry only.
- Reaching into private `_inferrer._build_los_geometry` to grab the sun vector. The GUI builds
  its own.

## Report (Category B)
- File list.
- Test results.
- Screenshots: θ_s = 0° (sun overhead), θ_s = 60° Δφ = 90° (typical illumination), θ_s = 180°
  (eclipse — sun behind Earth, arrow should point downward through the Earth and the
  terminator-shaded hemisphere should be the one facing the camera).
- Confirm the G1 caveat is recorded in the module docstring (so a future reader knows the
  GUI's sun controls are not yet wired to the production parameter schema).
