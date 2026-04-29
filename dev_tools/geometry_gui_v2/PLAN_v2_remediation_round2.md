# RADIANT Vision Studio — Second-Round Remediation Tasks for Coding Agent

**Target executor:** Claude (coding agent session, continuation of prior remediation work)
**Repository:** RADIANT, working tree at `dev_tools/geometry_gui_v2/`
**Authority:** This document is the work order. It is a follow-up to `PLAN_v2_remediation_agent.md` (the first-round remediation) which is now believed to be incomplete. Read both documents before starting.
**Source of defects:** Second-cut PyVista screenshot taken after the first-round remediation. Visual inspection by the human reviewer revealed regressions and missed tasks.

---

## 0. Read this first — what went wrong

The first-round remediation produced partial results. Subscript typography (T1) shipped correctly. The view-cube changes (T2) and world-axis gnomon move (T4) appear to have shipped. But the rest of the work either regressed, was skipped, or was implemented in a way that does not pass acceptance criteria.

Specifically, when the human reviewer inspected the second-cut screenshot, they saw:

1. The ground plane is **missing**. T3 either did not ship or is rendering at zero opacity. There is no visible grid texture under the target. The target appears to float in empty dark space.
2. The Sun is rendering as a **large solid sphere at literal sun-scale**, not as a stylized fixed-screen-size glyph. This violates `PLAN_v2.md` §11 step 4 and indicates the original Phase 3 sun-glyph work has regressed.
3. The **break-marks (T7) are missing** from the target → sun and target → satellite connecting lines.
4. The **right-dock info panel (T8) is missing**. The viewport is full-bleed.
5. The **left-dock parameter panel (T9) is missing**. There are no controls visible.
6. The **default camera angle is degenerate** — a near-orthographic side view that projects all the 3D geometry onto a single vertical column. Sun is directly above target, observer is to the upper-left, all the vectors collapse onto roughly the same 2D line. This is not what the user should see when they open the app.
7. **Labels no longer collide with each other** (T5 worked) but they now float in large empty regions with weak or missing leader lines. `θ_s = 35 deg` and `α_t` overlap each other near the center. `θ_off = 20 deg` is positioned to the left of the geometry it describes with no leader connecting it back. The boresight label `o` is barely visible.
8. The **scene occupies roughly 25% of the canvas area**. The remaining 75% is empty dark space because the camera is too far back and the panels are missing.

Before doing anything else, you need to understand: this is not primarily a label problem. The label solver from T5 is mostly working. The bigger problems are missed tasks (T3, T7, T8, T9), a regression on the sun glyph, a bad default camera, and a missing default-zoom policy.

There is also a **process root cause** that produced this state and that you must not repeat: the round-one agent verified acceptance by rendering and inspecting only one view (cylinder default). That is how regressions in extended-cell, in sun_terminator, and in geometry_diagram went undetected; how a sun glyph that's broken in every view passed; and how missing dock panels were not noticed until the human reviewer saw the cylinder screenshot. **This round you must verify every visual task across all 9 canonical views before declaring it complete.** §12 makes this a binding rule. R9 makes it a structured checklist. Read both before starting R1.

This document is structured to fix all of these. Execute in order. Do not skip ahead.

---

## 1. First, audit what actually shipped from round one

Before you write any new code, you need ground truth on what the first-round agent actually did. Trust nothing — verify everything. Write your audit findings to `dev_tools/geometry_gui_v2/AUDIT.md` before proceeding to Task R1.

### Audit steps

1. **View the task tracker** in the previous remediation document. What did the prior agent mark as complete?

2. **Look for the artifacts of each task:**

   For T1 (typography):
   - Does `scene/labels/glossary.yaml` exist?
   - Does `scene/labels/typography.py` exist?
   - Does `tests/test_typography.py` pass?

   For T2 (view-cube):
   - Does `scene/widgets/view_cube.py` exist? View it. Does it use `vtkAnnotatedCubeActor`?
   - Are there any references to spheres or saturated colors in that file?

   For T3 (ground plane):
   - Does `scene/ground/ground_cap.py` exist? View it.
   - Does it actually call `plotter.add_mesh(...)` with the texture?
   - Is `add_to_plotter` actually being called from `scene/builder.py`? Grep for it.
   - **If T3 shipped but the screenshot shows no ground, the bug is in the wiring, not the implementation. Find the wiring bug.**

   For T4 (axis gnomon):
   - View `scene/frames/world_axes_triad.py`. Are the viewport coords set to bottom-left?

   For T5 (label solver):
   - View `scene/labels/layout.py`. What are the final tuned weights documented in the docstring?
   - Does `tests/test_label_deconfliction.py` exist and pass?

   For T6 (angle arcs):
   - View `scene/arcs/`. Is there one file per arc? Do they produce visible tubes with arrowheads?

   For T7 (break-marks):
   - Does `scene/glyphs/break_mark.py` exist? View it.
   - Is it being called from the boresight ray and sun ray modules? Grep for `break_mark` in `scene/vectors/`.

   For T8 (right panel):
   - Does `app/panels/info_panel.py` exist? View it.
   - Is it being added to the main window as a `QDockWidget`? View `app/main.py`.

   For T9 (left panel):
   - Does `app/panels/parameter_panel.py` exist?
   - Is it added to the main window?

   For T10 (typography sweep):
   - Does `tests/test_no_underscore_labels.py` exist and pass?

3. **Run the test suite:** `pytest dev_tools/geometry_gui_v2/tests/ -v`. Note which tests pass, fail, error, or are skipped.

4. **Render the default scene yourself** with the off-screen renderer and save a PNG. View it. Compare against the second-cut screenshot the human shared. Are you seeing the same defects?

5. **Write `AUDIT.md`** with one section per task (T1–T10), each containing:
   - **Status:** `Shipped`, `Partial`, `Missing`, or `Regressed`.
   - **Evidence:** specific file paths, grep results, or test output.
   - **Defect (if any):** what the defect is and where it lives.

6. **Commit the audit** with message `audit: ground-truth status of round-one remediation`.

Only proceed to Task R1 after the audit is committed.

---

## 2. Task R1 — Fix the default camera

**Why this is first:** Every subsequent task is going to be evaluated by rendering and visually inspecting a screenshot. If the default camera is degenerate, every screenshot will look bad regardless of how correct the underlying scene is. Fix the camera first so you can see what you're actually doing.

### What's wrong

The current default camera is a near-orthographic side view. The sun is directly above the target, the observer is to the upper-left, and every vector in the 3D scene projects onto roughly the same vertical column. This means the boresight, the sun ray, and the surface normal — three vectors that point in genuinely different 3D directions — all overlap each other in the rendered 2D image. There is no way to make this scene legible from this camera angle.

The default camera must be an **isometric three-quarter view** that separates the major vectors into distinct screen-space directions.

### Steps

1. View `scene/builder.py`, `app/main.py`, and any file that calls `plotter.camera_position`, `plotter.view_isometric()`, `set_position`, or `reset_camera`. Find where the default camera is being set.

2. Set the default camera to an isometric-style view. The convention for this kind of remote-sensing scene is:
   - **Position:** `(distance * cos(elev) * cos(az), distance * cos(elev) * sin(az), distance * sin(elev))` from the target, where `elev = 25°` and `az = 45°`.
   - **Focal point:** the target centroid.
   - **View-up:** `(0, 0, 1)` (world Z up).
   - **Distance:** chosen so the scene fits with appropriate framing — see Task R2 below for the framing policy.

   Example implementation:

   ```python
   import numpy as np

   def set_default_camera(plotter, target_centroid, scene_extent):
       elev = np.deg2rad(25.0)
       az = np.deg2rad(45.0)
       distance = scene_extent * 2.5
       offset = distance * np.array([
           np.cos(elev) * np.cos(az),
           np.cos(elev) * np.sin(az),
           np.sin(elev),
       ])
       plotter.camera_position = [
           tuple(np.asarray(target_centroid) + offset),  # camera position
           tuple(target_centroid),                       # focal point
           (0.0, 0.0, 1.0),                              # view-up
       ]
   ```

3. Wire this into the scene-build path so it runs after all primitives are added but before the first render. **Do not call `plotter.reset_camera()` after this**, or it will undo your work.

4. Make sure the view-cube's "iso" face click also uses these same angles, so clicking the iso face restores the default camera.

5. Add a test that confirms the default view is isometric:

   ```python
   def test_default_camera_is_isometric():
       state = default_state()
       plotter = build_scene(state, off_screen=True)
       cam_pos = np.array(plotter.camera_position[0])
       focal = np.array(plotter.camera_position[1])
       view_dir = focal - cam_pos
       view_dir = view_dir / np.linalg.norm(view_dir)
       # In an isometric three-quarter view, all three components of view_dir
       # have non-trivial magnitude (none is near zero).
       assert all(abs(c) > 0.2 for c in view_dir), \
           f"camera is not isometric: view_dir={view_dir}"
   ```

### Acceptance for R1

- The default-camera test passes.
- Render the default cylinder scene to a PNG and view it. The target is visible at the center, the sun glyph is clearly to one side (not directly above), the observer is clearly to a different side, and the vectors point in visibly different screen-space directions.
- Clicking the view-cube's iso face restores this exact view.

### Commit message

`R1: set default camera to isometric three-quarter view`

---

## 3. Task R2 — Establish a default framing policy

**Why this matters:** Even with the right camera angle, the scene currently occupies ~25% of the canvas area. The framing policy is missing or wrong.

### What's wrong

The "scene extent" computation that determines camera distance must include all of: the target, the observer glyph (at its display position, not its physical position), the sun glyph (at its display position), the ground cap, and the background point. Currently it appears to be including only the target, leaving the camera too far back and the scene too small.

### Steps

1. Define a function `scene_bounds(state) -> tuple[Bounds, Centroid]` in `scene/framing.py`:
   - Computes the axis-aligned bounding box of every primitive that will render.
   - For the observer and sun, uses their *display* positions (after the not-to-scale compression), not their physical positions.
   - Returns the bounding box and its centroid.

2. The display position for the observer and the sun is fixed at `3 × target_max_extent` from the target along their respective true direction vectors. This is the same compression policy from PLAN_v2 §10. Confirm or implement this in `scene/glyphs/observer_glyph.py` and `scene/glyphs/sun_glyph.py`.

3. The camera distance from R1 should be `scene_extent * 2.5` where `scene_extent = max(bounds_size) / 2`. With margins of ~10%, the scene should occupy roughly 70% of the viewport's smaller dimension.

4. Add a "Recenter on target" action that re-runs `set_default_camera` with the current state. Wire it to the `R` keyboard shortcut and to a "View → Recenter" menu item if the menu exists.

5. Add a regression test:

   ```python
   def test_default_framing_uses_majority_of_canvas():
       state = default_state()
       img = render_off_screen(state, width=1920, height=1080)
       # Compute the bounding box of all non-background pixels.
       non_bg = np.where(img.sum(axis=-1) > 30)
       y_extent = non_bg[0].max() - non_bg[0].min()
       x_extent = non_bg[1].max() - non_bg[1].min()
       assert y_extent / 1080 > 0.5, "scene fills <50% of canvas height"
       assert x_extent / 1920 > 0.5, "scene fills <50% of canvas width"
   ```

### Acceptance for R2

- The framing-uses-majority test passes.
- Render the default scene. The target, both glyphs, the ground cap, and the background point are all visible without zooming or panning.
- The scene occupies at least 50% of both the canvas width and height.

### Commit message

`R2: establish default framing policy, scene fills majority of canvas`

---

## 4. Task R3 — Fix the regressed sun glyph

**Why this matters:** The current sun is rendering as a literal-scale solid sphere larger than the target. This violates the original Phase 3 design and is a regression from earlier shots.

### What's wrong

PLAN_v2 §11 step 5 specifies:

> Sun glyph: a small `pv.Disc` for the body + 8 short `pv.Tube` rays at 45° increments. All sized in screen-space pixels per `SUN_DISC_SIZE` and `SUN_RAY_TIP_SIZE`.

The current sun is none of these things. It's a fully-shaded sphere at world-scale. Either the original Phase 3 work shipped a sphere instead of a disc-with-rays, or someone replaced it later, or the screen-space sizing was abandoned.

### Steps

1. View `scene/glyphs/sun_glyph.py`. Confirm what it currently produces.

2. Replace the sphere with a stylized sun glyph:
   - A small `pv.Disc` (filled circle) at the sun's display position, sized via screen-space billboard so it's always 24 px in diameter regardless of zoom.
   - 8 short ray segments at 45° intervals (0°, 45°, 90°, ..., 315°), each rendered as a `pv.Tube` of length 8 px and width 2 px.
   - Color: `SOLAR_FAMILY` amber from `scene/style.py`.
   - Fill color of the disc: a slightly brighter amber than the rays.
   - All elements assembled into a single `vtkAssembly` so they move and scale together.

3. The right way to keep this at fixed screen-space size in PyVista/VTK is to use a `vtkBillboardTextActor3D` or to wire a camera-change callback that scales the assembly's transform inversely to the camera distance. The simpler approach: make the sun a 2D `vtkActor2D` with a `vtkPolyDataMapper2D` and position it via projecting the world-space sun-direction-anchor into screen space on each render. Use whichever approach you find more robust; document the choice.

4. Sun glyph must NOT be PBR-shaded. It is an icon, not a physical object. Use `lighting=False`.

5. The sun's *position in the scene* is at `target_centroid + 3 × target_max_extent × s_t_unit_vector`. Not at any cosmologically-correct distance. The connecting line from target to sun goes between target and this display position, with the break-mark from R5 at the midpoint.

6. Update or add `tests/test_sun_glyph.py`:

   ```python
   def test_sun_glyph_is_screen_space_sized():
       state = default_state()
       img_zoom1 = render_off_screen(state, zoom=1.0)
       img_zoom4 = render_off_screen(state, zoom=4.0)
       d1 = measure_sun_disc_diameter_px(img_zoom1)
       d4 = measure_sun_disc_diameter_px(img_zoom4)
       assert abs(d1 - d4) <= 1, f"sun glyph not screen-space sized: {d1} vs {d4}"
   ```

### Acceptance for R3

- Render the default scene. The sun appears as a small disc with 8 rays, not as a sphere.
- Sun is visibly smaller than the target on screen.
- Zoom in 4×; the sun stays the same size in pixels.
- The screen-space-sized test passes.

### Commit message

`R3: replace sphere sun glyph with stylized disc + rays at fixed screen size`

---

## 5. Task R4 — Restore the ground plane (T3 follow-through)

**Why this matters:** The ground plane was supposed to ship in T3 but is not visible in the current screenshot. Either the implementation is broken, or the wiring is broken, or the rendering order is wrong.

### Steps

1. View `scene/ground/ground_cap.py`. Confirm `add_to_plotter` exists and constructs the `pv.Plane` with the procedural texture.

2. View `scene/builder.py`. Confirm `ground.ground_cap.add_to_plotter(plotter, state)` is called. If not, add it.

3. Confirm the render order. The ground must render *first* (before everything else) so other primitives composit on top. Order: `ground_cap → ground_fade → contact_shadow → target → frames → vectors → arcs → glyphs → labels`.

4. Render the default scene. Look for the ground.

5. **If you still don't see the ground**, the most likely causes are:
   - The plane is below the camera frustum's far clip. Check the plane's z-coordinate against the camera's near/far.
   - The plane is being culled by backface culling. Add `mesh.plane.flip_normals()` if needed, or use `add_mesh(..., culling=False)`.
   - The texture is alpha-zero everywhere because of an off-by-one in the procedural-texture generator. Save the texture array as a PNG (`Image.fromarray(arr).save("/tmp/grid.png")`) and view it. Confirm the grid lines are actually visible in the saved texture.
   - The plane is opaque-but-black because the texture's RGB channels weren't initialized. View the procedural texture function and confirm `arr[..., :3]` is set to a non-zero value.

6. The ground plane must be visible in the rendered output. If the procedural texture isn't working after debugging, fall back to a solid color plane (`color="#2a2d35"`, `opacity=0.4`) with a separate set of `pv.Line` actors drawing the grid as 1 px lines. Document the fallback choice.

7. If you fix any of the above, ensure the test for ground-plane presence covers the failure mode you found:

   ```python
   def test_ground_plane_is_visible_in_render():
       state = default_state()
       img = render_off_screen(state, width=1920, height=1080)
       # Sample the bottom 20% of the image where the ground should be.
       bottom_strip = img[864:, :, :]
       # The ground should produce non-background pixels with a grid pattern.
       non_bg_pixels = np.sum(bottom_strip.sum(axis=-1) > 30)
       total_pixels = bottom_strip.shape[0] * bottom_strip.shape[1]
       assert non_bg_pixels / total_pixels > 0.1, \
           "ground plane invisible in bottom 20% of canvas"
   ```

### Acceptance for R4

- Ground plane visible in the rendered output extending around the target.
- The ground-visible test passes.
- Contact shadow visibly falls *on* the ground plane, not in empty space.
- If a fallback was used (solid color + line grid instead of procedural texture), document the reason in `AUDIT.md`.

### Commit message

`R4: restore visible ground plane; document any fallback`

---

## 6. Task R5 — Restore break-marks (T7 follow-through)

### Steps

1. View `scene/glyphs/break_mark.py`. Confirm it exists.

2. Grep for usages: `grep -rn "break_mark" dev_tools/geometry_gui_v2/scene/`. If there are no callers, the module is dead code — wire it in.

3. The break-marks must be applied to:
   - The target → satellite connecting line. Find this in `scene/vectors/boresight_ray.py` or wherever the satellite-position-to-target line is drawn.
   - The target → sun connecting line. Find this in `scene/vectors/sun_ray_target.py` or equivalent.

4. The connecting line must be split into two segments with a small gap. The break-mark zigzag goes in the gap. Do NOT just draw the zigzag on top of an unbroken line — that loses the "not to scale" semantic.

5. Render the default scene. Visible break-marks at the midpoints of both connecting lines.

### Acceptance for R5

- Render the default scene. Visible zigzag break-marks at the midpoints of target → satellite and target → sun connecting lines.
- Connecting lines have visible gaps where the break-marks sit.

### Commit message

`R5: wire break-marks into satellite and sun connecting lines`

---

## 7. Task R6 — Strengthen leader lines and label-anchor coupling

**Why this matters:** The current screenshot's labels float in space with weak or absent leader lines. `θ_off = 20 deg` floats to the left of any geometry it could be describing. `θ_s = 35 deg` and `α_t` are clustered near the center with no clear visual connection to which arcs they label.

### Steps

1. View `scene/labels/leader_label.py` (or wherever leader lines are rendered).

2. Confirm every label has a leader line that:
   - Starts at the label's bounding-box edge nearest the anchor.
   - Ends at the anchor in 3D world space (projected to screen).
   - Is rendered as a 1 px line in `LEADER_LINE_COLOR = #6a6d75` (subtle but visible against the dark background).
   - Ends in a small dot (3 px diameter, same color) at the anchor — this disambiguates which point the label refers to.

3. If labels currently have *no* leader lines, this is a missing implementation, not a tuning issue. Implement it now.

4. Do not let labels sit more than 240 px from their anchor in screen space. If the deconfliction solver tries to push a label further away (which can happen in cluttered scenes), constrain it. A label that's 400 px from the thing it labels is worse than a label that overlaps slightly.

5. Increase leader-line visibility on hover: when a label is hovered, its leader line thickens to 2 px and brightens to `#bcd0f0` for the hover duration. Wire via `Qt signal label_hovered(label_id)`. The signal can be a no-op for now if the panel work isn't done yet.

6. Add a per-label tooltip that shows the full description from `glossary.yaml`. For example, hovering on `α_t` shows "Phase angle at the target (sun-target-observer)".

7. Visual test: render the default scene and view it. For every label in the image, you should be able to trace a clear leader line from the label to the geometry it describes.

### Acceptance for R6

- Every label has a visible leader line connecting it to its anchor.
- Leader lines end in a small dot at the anchor point.
- No label is more than 240 px from its anchor.
- Tooltips show glossary descriptions on hover (verify by running interactively).
- Re-render all 9 canonical views and confirm leader lines are readable in each.

### Commit message

`R6: enforce visible leader lines, anchor dots, max distance constraint`

---

## 8. Task R7 — Build the right-dock info panel (T8, properly this time)

**Why this matters:** The right panel was supposed to ship in T8 but is not visible in the current screenshot. Without it, the user has no readouts, no projected-area display, no regime indicator. The viewport is full-bleed.

This task is the same as the original T8. Re-execute it. The original spec from `PLAN_v2_remediation_agent.md` Task T8 is the source of truth; do not deviate from it. Key reminders:

- Width 240 px, minimum 200 px.
- Four collapsible sections: Scene objects / Vectors / Angles / Regime.
- All subscripted labels via `panel_label()`.
- Wired to `view_model.derived_readouts(state)`.
- Eye-icon visibility toggles emit `visibility_changed(primitive, is_visible)`.
- Placed in a `QDockWidget` on the right side of the main window.

### Why it failed the first time

Audit `AUDIT.md` from §1 of this document. If T8 is marked Missing, you are starting from scratch. If T8 is marked Partial, identify what was built and complete it. If T8 is marked Shipped but the screenshot shows no panel, the panel exists but is not being added to the main window — find and fix the wiring.

### Acceptance for R7

- Render the app to a screenshot. Right dock panel visible, four collapsible sections, all readouts populated.
- All subscripted labels render with proper subscripts (no literal `_` characters).
- Toggling an eye icon hides or shows the corresponding scene element.

### Commit message

`R7: build right-dock info panel (re-execute T8)`

---

## 9. Task R8 — Build the left-dock parameter panel (T9, properly this time)

Same as the original T9 from `PLAN_v2_remediation_agent.md`. Re-execute. Key reminders:

- Width 200 px.
- Collapsible sections: Observer / Target / Sun / Sensor / Mode.
- Each parameter row: label + slider + spinbox + units.
- Emits `state_changed(SceneState)` on any change, debounced to 16 ms during drag.
- Placed in a `QDockWidget` on the left side.

### Acceptance for R8

- Render the app, screenshot it. Left dock panel visible with all sliders.
- Drag any slider; the 3D scene updates in real time.
- Right-panel readouts update in lockstep.

### Commit message

`R8: build left-dock parameter panel (re-execute T9)`

---

## 10. Task R9 — End-to-end visual verification across all 9 canonical views

**This task is non-negotiable. Acceptance requires evidence from all 9 canonical views, not just one.**

### Why this is explicit

Prior rounds passed acceptance by rendering and inspecting only the default cylinder view. That is not sufficient. The canonical view set has been part of every plan since v1, and the entire point of having 9 canonical views is that defects appear in some views but not others. A label-deconfliction solver that works for cylinder may stack labels in the box view. A camera framing that works for the sphere may clip the extended-cell pixel grid. A sun glyph that looks correct in one view may overlap the satellite in another.

You must render and visually inspect every one of the 9 views before you can mark this task done. No shortcuts.

### The 9 canonical views

The view set is defined by the existing PLAN_v2 §3 / C8 specification:

1. `box_default`
2. `cone_default`
3. `cylinder_default`
4. `extended_default`
5. `flat_plate_default`
6. `geometry_diagram` (Phase 10 all-angle-groups view)
7. `point_source_default`
8. `sphere_default`
9. `sun_terminator` (θ_s=60°, Δφ=90°)

Each has a corresponding `SceneState` factory in `tests/fixtures/canonical_views.py` (or wherever the fixtures live; if missing, build them — view names map to the original gallery filenames).

### Steps

1. Run the full test suite. `pytest dev_tools/geometry_gui_v2/tests/ -v`. All tests must pass before this task can proceed. If any test fails, stop and fix it.

2. Build a verification harness in `tests/verify_canonical_views.py` that:
   - Iterates the 9 view fixtures.
   - For each, renders at 1920×1080 with the off-screen renderer.
   - Saves the PNG to `tests/golden/round2/<view_name>.png`.
   - Saves a thumbnail (480×270) to `tests/golden/round2/thumbs/<view_name>.png`.
   - Returns a structured result the agent can iterate over.

3. **For each of the 9 views**, view the saved PNG and complete the per-view checklist below. Write the results to `REMEDIATION_REPORT.md` as a table with one row per view and one column per check. Do not summarize. Do not skip views. Do not assume that what's true for cylinder is true for the others.

   The per-view checklist:

   | # | Check | Pass / Fail | Notes |
   |---|---|---|---|
   | 1 | Target is the most visually dominant element | | |
   | 2 | Scene fills ≥50% of both canvas dimensions | | |
   | 3 | Default camera is isometric three-quarter (no degenerate side view) | | |
   | 4 | Sun renders as small disc + rays glyph, not a sphere, ≤30 px diameter | | |
   | 5 | Satellite renders as small diamond glyph at fixed screen size | | |
   | 6 | Ground plane visible as subtle grid extending around target | | |
   | 7 | Contact shadow visible on the ground plane (not in empty space) | | |
   | 8 | World-axis gnomon present in bottom-left, neutral gray, no overlap with view-cube | | |
   | 9 | View-cube present in top-right, subdued, no saturated colors or spheres | | |
   | 10 | Break-mark zigzag visible at midpoint of target → satellite line | | |
   | 11 | Break-mark zigzag visible at midpoint of target → sun line | | |
   | 12 | Every angle arc in the view is visible (curved tube + arrowhead + midpoint label) | | |
   | 13 | Every label has a visible leader line ending in an anchor dot | | |
   | 14 | No label is more than 240 px from its anchor in screen space | | |
   | 15 | No two label bounding boxes overlap (Phase 4 hard test, automated) | | |
   | 16 | All subscripts render as true subscripts (no literal `_` in any label) | | |
   | 17 | Right-dock info panel visible with all four sections populated | | |
   | 18 | Left-dock parameter panel visible with appropriate slider inventory | | |
   | 19 | No scrollbar fragments, stray characters, or layout artifacts on viewport edges | | |
   | 20 | Family colors are correct: blue/sensor, amber/solar, green/surface, gray/reference | | |

   Twenty checks × nine views = 180 line items. Do them all.

4. **Special-case checks for specific views**, in addition to the standard 20:
   - `extended_default`: the pixel-cell footprint must be visible as a translucent square on the ground, not as an opaque orange block hiding the geometry beneath.
   - `geometry_diagram`: all angle groups (off-nadir, az, el, α_t, θ_s, Δφ, θ_sun,B) must be simultaneously visible and labeled.
   - `sun_terminator`: the terminator on the sphere target must align with the sun direction within 2°.
   - `point_source_default`: the point-source marker must be visible and clearly distinguished from the regular sub-pixel target indicator.

5. **For every check that fails**, you must do one of two things:
   - Fix the defect, re-render, re-inspect, and update the table.
   - File the defect in `REMEDIATION_BLOCKERS.md` with the view name, check number, what you saw, and what you tried.

   You may not mark R9 complete with any unresolved Fail entries unless they are filed as blockers with detailed explanations.

6. **Run the app interactively** (not via off-screen render). Confirm:
   - Default scene loads to the isometric camera.
   - Dragging a slider in the left panel updates the 3D scene in real time.
   - Right-panel readouts update in lockstep with slider drags.
   - View-cube clicks navigate to canonical views and animate smoothly.
   - Frame indicator chip in the top-left updates if you change frames.
   - No flickering, no scrollbar artifacts, no Qt warnings in the console.

7. **Write the final remediation report** to `REMEDIATION_REPORT.md` with:
   - The audit findings from §1.
   - A summary of all R1–R8 commits.
   - The 9-view × 20-check table from step 3.
   - The special-case results from step 4.
   - The interactive-test results from step 6.
   - A side-by-side comparison: thumbnail of each view from `tests/golden/round2/thumbs/` next to the corresponding view from the prior round (if available) so the human reviewer can see the delta.
   - Any deferred items or known issues.

### Acceptance for R9

- All 9 canonical views rendered, saved, and visually inspected.
- The 20-check table is fully populated for every view (180 cells, no blanks).
- Every Fail in the table is either resolved or filed as a blocker with detailed explanation.
- All 4 special-case checks pass.
- Interactive test passes.
- Final report written with thumbnails and side-by-side comparison.
- No view is missing from the report. No check is missing from any view.

### Commit message

`R9: end-to-end visual verification across all 9 canonical views`

---

## 11. Task tracker

| ID | Title | Status | Commit | Notes |
|---|---|---|---|---|
| Audit | Ground-truth audit of round one | ☐ |  |  |
| R1 | Default isometric camera | ☐ |  |  |
| R2 | Default framing policy | ☐ |  |  |
| R3 | Restore stylized sun glyph | ☐ |  |  |
| R4 | Restore ground plane | ☐ |  |  |
| R5 | Restore break-marks | ☐ |  |  |
| R6 | Strengthen leader lines | ☐ |  |  |
| R7 | Build right panel (re-execute T8) | ☐ |  |  |
| R8 | Build left panel (re-execute T9) | ☐ |  |  |
| R9 | End-to-end verification | ☐ |  |  |

---

## 12. Operating reminders

These are the same as round one but worth repeating because round one missed them.

**Render and view every screenshot before declaring a task done.** Do not declare R3 done because the sun glyph code looks right. Render the scene, save a PNG, view it, confirm visually that the sun is small and stylized. The first round skipped this step on multiple tasks and that is why we are here.

**Every task with visual acceptance must be verified across ALL 9 canonical views, not just cylinder_default.** This is the most important rule in this document. Defects appear in some views but not others — a label solver that works for cylinder may stack labels for box; a camera framing that works for sphere may clip extended-cell. Round one passed acceptance by checking only the default view, and that is precisely why this round-two remediation is necessary. The 9 views are: `box_default`, `cone_default`, `cylinder_default`, `extended_default`, `flat_plate_default`, `geometry_diagram`, `point_source_default`, `sphere_default`, `sun_terminator`. For every task that says "render the scene and view the PNG," that means render and view all 9, not one. R9 formalizes this with a per-view checklist; earlier tasks must follow the same discipline informally. If you take a shortcut and check only one view, you are reproducing the exact failure that produced the round-two screenshot.

**If a task says "wire it into the builder," confirm the wiring with a grep.** The first round shipped code modules that were never called. Module exists ≠ module runs.

**One task, one commit.** Do not bundle. Do not amend across tasks. Do not squash.

**If you cannot make a task's acceptance pass, stop and report.** Add to `REMEDIATION_BLOCKERS.md`. Do not silently ship a partial fix.

**The dock panels (R7, R8) are the most visible missing pieces.** A user looking at the app sees "no panels" before they see "the sun is wrong." Prioritize completing R7 and R8 over polishing earlier tasks. If you have to choose between perfect and shipped on the panels, ship.

**The audit step in §1 is not optional.** Skipping it and going straight to R1 will lead to re-implementing things that already exist or skipping wiring fixes that would resolve "missing" features. Do the audit first. Commit it. Then start R1.

---

## 13. What success looks like

After all tasks are complete, the rendered default scene should show:

- An isometric three-quarter view of the scene.
- A teal cylinder target at the center, PBR-shaded with a clear lit/dark terminator.
- A subtle gray-grid ground plane below the target with a soft contact shadow.
- A small white satellite diamond glyph to the upper-right at fixed screen size, connected to the target by a thin blue line with a midpoint break-mark.
- A small amber sun disc with 8 rays to the upper-left at fixed screen size, connected to the target by a thin amber line with a midpoint break-mark.
- A small green sphere for the background point with its own labeled position.
- Visible angle arcs (off-nadir, α_t, θ_sun,B) as curved tubes connecting the relevant vectors, each with an arrowhead and a midpoint label.
- Every label connected to its anchor by a thin gray leader line ending in a small dot.
- All labels using proper subscripts.
- A subdued view-cube in the top-right.
- A neutral world-axis gnomon in the bottom-left.
- A 240 px right-dock panel showing four collapsible sections of live readouts.
- A 200 px left-dock panel showing all parameter sliders.

That's the bar. When you achieve it, write the final report and stop.
