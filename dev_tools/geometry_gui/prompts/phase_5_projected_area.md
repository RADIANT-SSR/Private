# Phase 5 — Projected area readout & visual confirmation

**Category:** C (Physics surface — the one numeric link to radiometry)
**Pre-reads:** Phase 1 `projected_area_m2`; [src/radiant/source/shape.py](../../../src/radiant/source/shape.py)
TargetShape protocol; [src/radiant/source/shapes/](../../../src/radiant/source/shapes/) for each
shape's `projected_area` implementation.

## Hard constraint
**Do not edit `/src/`.** This phase is the C3 invariant gate: the GUI's reported A_t MUST equal
`shape.projected_area(view_dir)` exactly. No re-implementation, no parallel formula.

## Goal
1. The readout's `Projected area A_t` line shows the live value from
   `view_model.projected_area_m2(state)`, with units (m²), updated every callback.
2. A **translucent silhouette** appears in the 3D scene: a flat disk at the target position,
   oriented perpendicular to the line-of-sight (target→observer), with area exactly equal to A_t.
   This is a visual confirmation that the number on screen and the physical projection on screen
   are the same projection.
3. Hover tooltip on the silhouette shows the same A_t value.
4. Below the readout, a small explainer line names the contributing facets when the shape is
   multi-facet (Cone, Box, Cylinder side+caps), pulled from each shape's docstring or
   re-derived from the geometry. For Sphere and FlatPlate, just say "single-projection".

## Files
- `app/scene_builder/silhouette_disk.py` — new module per Rule 19. Generates a circle mesh with
  area A_t, centered at the target, normal = unit vector observer→target in scene frame.
- `app/layout/readout_panel.py` — wire the live value and the explainer line.

## C3 invariant test (this is the gate)
```python
# tests/test_projected_area_invariant.py
@pytest.mark.parametrize("seed", range(50))
def test_projected_area_matches_shape_call(seed):
    state = random_state(seed)                      # any valid SceneState
    shape = build_target_shape(state)               # from view_model
    v_body = view_direction_body(state)             # from view_model
    expected = shape.projected_area(v_body)         # the radiometry call
    actual = projected_area_m2(state)               # what the GUI displays
    assert actual == expected                        # exact equality, not approx
```
Failure here means the GUI is showing a number radiometry would not use. Block merge.

## Numerical truth anchors (Category C — three required)

| # | Anchor | Expected |
|---|---|---|
| 1 | Sphere of radius 1 m, any view direction | π m² (analytic) |
| 2 | Flat plate 2×3 m², view normal to surface | 6 m² (analytic) |
| 3 | Flat plate 2×3 m², view at 60° to normal | 3 m² (analytic, A·cos 60°) |

For each, build the corresponding `SceneState`, call `projected_area_m2(state)`, and report
absolute / relative error.

## Failure modes to test
- Shape with zero size (radius=0, plate length=0): expect 0.0 m², no NaN.
- View direction parallel to flat plate (edge-on): expect 0.0 m².
- View direction reversed (observer behind plate): document the shape's behavior — `FlatPlate`
  uses `|cos θ|`, so the answer is the same as front-on. Confirm the GUI shows that.
- Cone tip-on view: nontrivial; just confirm the value matches `Cone(...).projected_area(v)`.

## Forbidden
- Computing A_t any other way ("for performance", "for cleanliness"). The displayed number IS
  the radiometry number.
- Skipping the silhouette-disk visual — it is the visual proof for the developer.

## Report (Category C)
- Files modified.
- C3 invariant test result (must pass for all 50 seeds).
- Three truth anchors with absolute & relative error.
- Dimensional audit for projected_area_m2 (re-state from Phase 1, refreshed if anything changed).
- Failure modes results.
- Screenshot showing the readout panel with units on every line, and the silhouette disk
  visible in the 3D scene.
- Confirm Jason's units-on-outputs rule (memory) is satisfied: every numeric label in the
  readout has explicit units.
