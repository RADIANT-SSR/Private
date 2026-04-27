# Phase 3 — Controls panel & Dash wiring

**Category:** A/D (UX integration)
**Pre-reads:** PLAN.md §6 (slider inventory); Phase 1 view-model; Phase 2 scene-builder.

## Hard constraint
**Do not edit `/src/`.** All UI lives under `app/`.

## Goal
Every slider in PLAN.md §6 is on screen, every change updates the 3D figure, and the readout
panel from PLAN.md §7 is rendered (with placeholder values — Phase 5 wires it to real numbers).

## Files

```
app/main.py             — full Dash app: layout, single callback
app/layout/
  __init__.py
  controls_panel.py     — assembles all sliders/dropdowns/radios into a Div
  observer_controls.py  — Rule 19: each control group is its own module
  target_controls.py
  sun_controls.py
  sensor_controls.py
  mode_controls.py
  readout_panel.py      — placeholder labels for every line in §7
```

## Callback wiring
- ONE callback: `update_scene(*all_slider_values) -> figure`.
- It builds a `SceneState`, calls `view_model.derived_readout(state)` (from Phase 1), and
  passes the state to `scene_builder.build_scene(state)` (from Phase 2). Output: a single
  `go.Figure(data=traces, layout=...)`.
- Layout: `scene = dict(aspectmode="data", camera=dict(...))`. Lock the up-vector so rotation
  feels natural.

## Slider notes (per PLAN.md §6)
- Angle sliders are in **degrees** in the UI (developer ergonomics) but converted to radians
  inside `SceneState`. Keep all internal SceneState fields in radians (RADIANT canonical units).
- Pixel pitch slider in **µm** in the UI; stored as meters in SceneState.
- Altitude in **km** in the UI; meters in SceneState.

## Tests
- `tests/test_layout.py`: import `app.main`, assert the layout has exactly the expected slider
  count (count from PLAN.md §6 — should be 19 sliders + 2 radios + 1 dropdown).
- `tests/test_callback_smoke.py`: invoke the callback function directly with default values;
  assert it returns a `go.Figure` with > 0 traces.

## Manual acceptance
1. `python -m dev_tools.geometry_gui.app.main` opens the app.
2. Every slider visibly moves something on the figure.
3. The shape dropdown changes the target mesh.
4. Camera rotation/zoom/pan work.

## Forbidden
- Multiple Dash callbacks. One callback keeps the data flow single-direction (PLAN.md §4).
- Storing state in module globals. SceneState is reconstructed from slider values on every
  callback fire.

## Report (Category A/D)
- File list, test results.
- Screenshot of the running app with default state.
- Confirmation each slider in §6 is present.
