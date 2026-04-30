# RADIANT Vision Studio — Round 3 Remediation Tasks for Coding Agent

**Target executor:** Claude (coding agent session, continuation of prior work)
**Repository:** RADIANT, working tree at `dev_tools/geometry_gui_v2/`
**Authority:** This document is the work order. It follows `PLAN_v2_remediation_agent.md` (round 1) and `PLAN_v2_remediation_round2.md` (round 2). Read both before starting.
**Source of defects:** Round-three viewport-only export reel showing 16 parameter-sweep frames (target altitude 0–2000 km; box and cone orientation sweeps). The right and left dock panels are confirmed shipped per the prior agent's report; the defects below are all in the 3D viewport itself.
**Critical context:** The prior round's PNGs were viewport-only exports, not full-app screenshots. The Qt panels exist. Do not re-implement them. Defects in this round are in-viewport defects only.

---

## 0. Read this first — what the round-three reel actually showed

The round-three export reel demonstrated three good things and six bad things.

**Good things, do not break these:**

1. The altitude sweep works. Target rises off the ground correctly from 0 km through 2000 km. The slant-range readout updates correctly. The regime flips from `sub_pixel` to `extended` between 10 km and 100 km as expected.
2. The orientation sweeps for box and cone work. Yaw, pitch, and roll each rotate the target as expected.
3. The sun glyph, satellite diamond, ground plane, isometric camera, contact shadow, PBR target shading, and isometric three-quarter view all survived from the prior round and look correct.

**Bad things, this document fixes them:**

1. The label cluster around the target collapses to a pile in the center of every viewport. `θ_off`, `s_t`, `θ_s`, `α_t`, `o`, and `n_B` all stack on top of each other. The force-directed solver does not handle the case where many anchors project to nearly the same screen point.
2. The `Target` text label sits inside the target geometry at altitudes ≥10 km. The label has no enforced offset; as the target screen-size grows, the label gets buried inside it.
3. Data-readout text is being rendered in the 3D viewport. `Sensor alt = 600 km slant = X km` and `Target alt = X km A_t = X m² (regime)` are panel content, not viewport content. They duplicate the right-panel readouts and crowd the viewport.
4. Break-marks (the small zigzags on the target → satellite and target → sun connecting lines) are still missing despite shipping in round 1 (T7) and being re-targeted in round 2 (R5). The connecting lines are unbroken solid lines in every frame of the reel.
5. The satellite display position breaks at high target altitude. In the alt=600 km frame the satellite glyph appears below the target on screen, even though target alt = sat alt = 600 km, slant = 0 km. The not-to-scale compression policy is anchoring the satellite glyph relative to the target without accounting for the target having a non-trivial altitude.
6. At target altitude = 0 km, the sphere target is half-buried in the ground because its centroid sits at z=0. Visually this reads as a clipping bug.

There is also one minor open item:

7. The `point_source` regime tag is appearing on physically large targets in some orientation-sweep frames. Either the regime classifier is wrong, the orientation sweep hardcoded the regime, or the rendered target is below the sub-pixel threshold despite looking large. Investigate and either fix or document.

This document is structured to fix all seven. Execute in order.

---

## 1. Operating principles

These are the same rules from rounds one and two. They apply to every task. If you have read the prior rounds' documents, skim and continue. If you have not, read this section in full.

**Read before you write.** For every file you intend to modify, run `view` first. Do not assume the codebase matches your priors.

**Verify visually before declaring a task done.** Render the relevant scene with the off-screen renderer, save a PNG, view it. Code-compiling-and-tests-passing is not the same as the rendered output looking right.

**All visual tasks are verified across all 9 canonical views, not just one.** This is the rule that round one violated and that round two formalized. The 9 views are: `box_default`, `cone_default`, `cylinder_default`, `extended_default`, `flat_plate_default`, `geometry_diagram`, `point_source_default`, `sphere_default`, `sun_terminator`. Plus, for tasks that involve altitude or orientation, run the round-three sweep set as well.

**Respect Rule 19 (one computation, one module).** Every primitive lives in its own file. Do not consolidate.

**Respect constraint C7 (scene library has no Qt imports).** Files under `scene/` must not import Qt.

**Respect constraint C1 (no edits to /src/).** All work happens under `dev_tools/geometry_gui_v2/`.

**Use the typography helpers.** Every user-facing label goes through `viewport_label()` or `panel_label()`. No raw strings with underscores.

**One task, one commit.** Do not bundle. Commit messages start with the task ID (e.g., `S1: separate viewport labels from data readouts`).

**If a task cannot be completed because of a missing dependency, a platform issue, or an ambiguity, stop and report.** Write findings to `dev_tools/geometry_gui_v2/REMEDIATION_BLOCKERS.md`. Do not invent a workaround that violates the spec.

---

## 2. Pre-flight audit

Before starting any task, verify the panels really did ship and the prior rounds' deliverables are still in place. Round two had a regression on T7 (break-marks) and parts of T3 (ground plane); audit before doing new work.

### Audit steps

1. View the round-two task tracker. Identify which tasks were marked complete.

2. Verify the panels exist:
   - `view dev_tools/geometry_gui_v2/app/panels/info_panel.py` — file should exist and define `InfoPanel(QWidget)`.
   - `view dev_tools/geometry_gui_v2/app/panels/parameter_panel.py` — file should exist and define `ParameterPanel(QWidget)`.
   - View `app/main.py` and confirm both panels are added as `QDockWidget` instances on the right and left of the main window.
   - Run the app: `python -m dev_tools.geometry_gui_v2.app.main`. Take a full-window screenshot (not just viewport). Confirm both panels are visible.

3. Verify the round-one and round-two artifacts that are upstream of this round's work:
   - `view dev_tools/geometry_gui_v2/scene/glyphs/break_mark.py` — file should exist.
   - Grep usages: `grep -rn "break_mark" dev_tools/geometry_gui_v2/scene/`. There should be calls from `scene/vectors/boresight_ray.py` (or equivalent) and `scene/vectors/sun_ray_target.py` (or equivalent). If grep returns only the definition, **the module is unwired** — note that for Task S4.
   - `view dev_tools/geometry_gui_v2/scene/labels/layout.py` — confirm the force-directed solver exists and is being called on camera changes.
   - `view dev_tools/geometry_gui_v2/scene/labels/typography.py` — confirm the helpers from round one exist.

4. Run the test suite: `pytest dev_tools/geometry_gui_v2/tests/ -v`. Note any failures.

5. Render the round-three sweep frames yourself with the off-screen renderer:
   - Altitude sweep: 0, 1, 10, 100, 600, 2000 km, otherwise default state.
   - Box orientation sweep: yaw/pitch/roll combinations as in the round-three reel.
   - Cone orientation sweep: same.
   Save PNGs to `tests/golden/round3_audit/`. View at least 4 of them and confirm you see the same defects described in §0. If you do not, the codebase has changed since the reel was generated; report this as a blocker.

6. Write `dev_tools/geometry_gui_v2/AUDIT_round3.md` summarizing:
   - Panel status (shipped / partial / missing).
   - Break-marks status (wired / module-only / missing).
   - Label-solver status (running / not running).
   - Test suite status (green / failures listed).
   - Whether you reproduced the round-three defects locally.

7. Commit the audit: `audit: round-three pre-flight verification`.

Only proceed to Task S1 after the audit is committed. If the audit reveals that the panels are NOT actually shipped — contradicting the prior agent's report — stop and report that finding to the human reviewer before doing anything else.

---

## 3. Task S1 — Separate viewport labels from data readouts

**Why this is first:** This task removes ~50% of the in-viewport text crowding by moving data readouts out. After it ships, all subsequent label-layout work is operating on a much smaller set of labels and the cluster problem becomes tractable.

### What's wrong

The round-three reel shows two text labels rendered as 3D-anchored labels in the viewport that should not be there:

- `Sensor alt = 600 km  slant = 639 km` — anchored to the satellite glyph.
- `Target alt = 0 km  A_t = 3.14 m²  (sub_pixel)` — anchored to the target.

These are **data readouts**: numeric values, units, regime tags. They belong in the right-dock info panel (which exists per the audit). Rendering them in the viewport duplicates the panel content and crowds the scene.

### What stays in the viewport

After this task, the only labels in the 3D viewport are:

- **Symbol labels** for vectors and angles: `s_t`, `s_B`, `n_B`, `o`, `θ_off`, `θ_s`, `α_t`, `θ_sun,B`.
- **Minimal object names**: `Satellite`, `Sun`, `Target`, `Background`. No altitudes, no slant ranges, no projected areas, no regime tags. Just the noun.

Everything else moves to the right panel.

### Steps

1. Grep for the offending label strings:
   ```bash
   grep -rn "Sensor.*alt" dev_tools/geometry_gui_v2/scene/
   grep -rn "slant" dev_tools/geometry_gui_v2/scene/
   grep -rn "Target.*alt" dev_tools/geometry_gui_v2/scene/
   grep -rn "A_t.*=.*m" dev_tools/geometry_gui_v2/scene/
   grep -rn "(sub_pixel)" dev_tools/geometry_gui_v2/scene/
   grep -rn "(extended)" dev_tools/geometry_gui_v2/scene/
   grep -rn "(point_source)" dev_tools/geometry_gui_v2/scene/
   ```
   Identify every place where these strings are constructed and emitted as a label.

2. For each match:
   - If it's emitting a viewport label: replace with a minimal label (`Satellite`, `Target`, `Sun`, `Background`).
   - The data the old label carried (altitude, slant, area, regime) is **already** in the right panel via `view_model.derived_readouts`. Verify this by viewing `app/panels/info_panel.py` and confirming the panel reads slant range, target altitude, A_t, and regime. If any are missing from the panel, add them — they are now the only place those values live.

3. Remove any code paths that build the long composite label strings (`f"Sensor alt = {alt} km slant = {slant} km"` and similar). Replace with calls to `viewport_label()` for the symbol or with the literal string `"Satellite"` / `"Target"` / `"Sun"` / `"Background"`.

4. Update `scene/labels/glossary.yaml` to add minimal-name keys if not already present:
   ```yaml
   object_satellite:
     latex: "Satellite"
     html: "Satellite"
     description: "Sensor satellite at the configured altitude"
   object_sun:
     latex: "Sun"
     html: "Sun"
     description: "Sun position (direction only; not to scale)"
   object_target:
     latex: "Target"
     html: "Target"
     description: "Imaging target"
   object_background:
     latex: "Background"
     html: "Background"
     description: "Background reference point"
   ```

5. Render the round-three sweep frames again with the off-screen renderer. Save PNGs to `tests/golden/round3/s1_after/`. View them. Confirm:
   - No `slant = X km`, `alt = X km`, `A_t = X m²`, `(sub_pixel)`, `(extended)`, `(point_source)` text appears in the viewport.
   - The satellite glyph is labeled simply `Satellite`.
   - The target is labeled simply `Target`.
   - The right panel still shows all the values that were removed from the viewport.

6. Add a regression test `tests/test_no_data_readouts_in_viewport.py`:
   ```python
   import re
   from itertools import product
   import pytest

   FORBIDDEN_PATTERNS = [
       r"alt\s*=\s*\d",
       r"slant\s*=\s*\d",
       r"A_t\s*=",
       r"\(sub_pixel\)",
       r"\(extended\)",
       r"\(point_source\)",
   ]

   @pytest.mark.parametrize("view_name", CANONICAL_VIEWS)
   def test_viewport_has_no_data_readouts(view_name, render_canonical):
       label_texts = render_canonical(view_name).get_label_texts()
       for text in label_texts:
           for pattern in FORBIDDEN_PATTERNS:
               assert not re.search(pattern, text), (
                   f"{view_name}: viewport label '{text}' contains "
                   f"forbidden pattern '{pattern}'"
               )
   ```

### Acceptance for S1

- The regression test passes for all 9 canonical views.
- Viewport screenshots from the round-three sweep set show only symbol labels and minimal object names. No altitudes, no slant ranges, no projected areas, no regime tags.
- The right panel still displays all the data that was removed from the viewport. Verify by running the app interactively and changing the altitude slider; the panel readouts must update correctly.
- Updated golden screenshots locked.

### Commit message

`S1: separate viewport labels from data readouts; data values now panel-only`

---

## 4. Task S2 — Enforce label/anchor non-overlap constraint

**Why this matters:** The `Target` text label currently sits inside the target sphere at altitudes ≥10 km because the label is anchored to the target centroid with no offset and the deconfliction solver doesn't know to push it out. This is a hard rule the layout solver must enforce, not just a tuning issue.

### The hard rule

**A label's bounding box must never overlap the projected screen-space bounding box of its own anchor's mesh.**

This is in addition to the existing label-label repulsion rule from round one's T5. It applies to every label whose anchor is a mesh (target, satellite glyph, sun glyph, ground feature). It does NOT apply to anchors that are points or vectors with no mesh — those stay anchored to a screen-space dot per the existing leader-line rules.

### Steps

1. View `dev_tools/geometry_gui_v2/scene/labels/layout.py`. Locate the force-computation function.

2. Add a per-label "anchor mesh exclusion zone" computed each render:
   - For each label whose anchor is a mesh, compute the projected screen-space axis-aligned bounding box of that mesh, with 8 px padding on each side.
   - The label's own bounding box must not intersect this exclusion zone.
   - If it does, apply a strong repulsive force directed from the exclusion-zone center to the label's center, with magnitude 200.0 (much higher than label-label repulsion, since this is a hard constraint).

3. Add a fallback: if after solver convergence the label's box still overlaps its anchor's exclusion zone, **forcibly push it out** along the same direction by the minimum distance needed to separate the boxes. This ensures the constraint always holds, even if the soft force fails to converge in time.

4. The leader line from the label to its anchor must originate from the bounding-box edge of the label and terminate at the anchor's mesh surface (or centroid if the centroid is closer than any surface point). It must NOT pass through the label's own text. If the label is now outside the mesh and the leader line crosses the mesh, that's expected — the leader is a 2D screen-space line that overlays the 3D scene.

5. Add a hard test `tests/test_label_never_overlaps_anchor_mesh.py`:
   ```python
   @pytest.mark.parametrize("view_name", CANONICAL_VIEWS + ALTITUDE_SWEEP_VIEWS)
   def test_label_never_overlaps_anchor_mesh(view_name, render_view):
       result = render_view(view_name)
       for label in result.get_labels():
           if label.anchor_mesh is None:
               continue  # vector / point anchors don't have this constraint
           anchor_bbox = result.get_projected_mesh_bbox(label.anchor_mesh)
           label_bbox = label.screen_bbox
           assert not _bboxes_intersect(label_bbox, anchor_bbox), (
               f"{view_name}: label '{label.text}' overlaps its anchor "
               f"mesh '{label.anchor_mesh}'"
           )
   ```

6. Re-render the altitude sweep (0, 1, 10, 100, 600, 2000 km). Confirm visually that the `Target` label is OUTSIDE the target sphere at every altitude.

### Acceptance for S2

- The hard test passes for all 9 canonical views and all 6 altitude-sweep frames.
- Visual: at altitude=2000 km, the `Target` label sits adjacent to the sphere with a leader line, never overlapping the sphere itself.
- The leader line is visible and connects label edge to mesh surface.

### Commit message

`S2: enforce label/anchor mesh non-overlap constraint`

---

## 5. Task S3 — Re-tune the label-deconfliction solver for the central cluster

**Why this matters:** Even after S1 removes the data readouts and S2 pushes the `Target` label off the target, the central cluster (`θ_off`, `s_t`, `θ_s`, `α_t`, `o`, `n_B`) is still piled up because all those anchors project to nearly the same screen point — the target centroid. The solver's current weights cannot pull labels apart when their anchors are co-located.

### Diagnosis first

1. View `scene/labels/layout.py`. Document the current weights (anchor attraction, label-label repulsion, edge repulsion, line-crossing penalty). Round-one T5 set these to (1.0, 8.0, 4.0, 2.0). The round-three defect suggests these are too weak for the co-located-anchor case.

2. Render the default cylinder view with `DEBUG_LABEL_LAYOUT = True` (this flag was added in T5; if it has been removed, re-add it). The debug overlay shows label bounding boxes and leader lines. Save the PNG and view it. Confirm whether the solver is even running or whether labels are at their initial positions.

3. Project the anchors of the central cluster to screen space. Measure how close they are. Round-three frames show them within ~30 px of each other. The solver needs to handle this.

### Tuning steps

1. Increase the **initial outward offset** from 120 px (round one) to **180 px**, and bias the initial direction to spread labels evenly around a circle rather than along the radial-from-centroid axis. When N labels share a near-co-located anchor, place them at angles `(360°/N) * i` around their anchor at the increased offset distance. This breaks the symmetry that causes pile-up.

2. Increase **label-label repulsion** from 8.0 to **15.0** for the first 20 iterations of the solver, then decay to 8.0 over the remaining 40 iterations. The high initial weight pushes co-located labels apart aggressively; the decay lets them settle without oscillation.

3. Add **anchor-cluster detection**: at the start of each solver run, compute a clustering of anchors in screen space. Anchors within 40 px of each other are flagged as a cluster. Labels whose anchors are in the same cluster get an additional **inter-cluster repulsion force** of 5.0 to spread them out more aggressively than the default.

4. Reduce **anchor attraction** from 1.0 to 0.5 for labels whose anchors are in a cluster. The attraction pulls labels back toward the pile-up; weakening it helps them stay spread out.

5. Increase the **max iteration count** from 60 to 120, with the same 0.5 px convergence threshold. The harder problem of co-located anchors needs more iterations to settle.

6. Document the final tuned weights in the module docstring of `scene/labels/layout.py`. Include the rationale for each value, so the next person who touches this can understand the reasoning.

### Verification

1. Render all 9 canonical views plus the altitude sweep plus the box and cone orientation sweeps. For each, save the PNG and view it.

2. Run the existing label-overlap hard test (`test_no_label_overlap` from round one's T5) on all of these views. It must pass.

3. Add a stronger test: for the cluster of central labels (`θ_off`, `s_t`, `θ_s`, `α_t`, `o`, `n_B`), measure the standard deviation of their final screen positions. It must be at least 60 px (i.e., labels are spread out, not piled up).

   ```python
   def test_central_cluster_is_spread_out():
       # The central cluster has 6 labels whose anchors project near
       # the target centroid. After deconfliction, they should be
       # distributed around the target, not piled up.
       result = render_default_view()
       central_label_keys = [
           "off_nadir_angle", "sun_vector_target", "solar_zenith_target",
           "phase_angle_target", "boresight", "surface_normal_background",
       ]
       positions = [result.get_label_position(k) for k in central_label_keys]
       xs = [p[0] for p in positions]
       ys = [p[1] for p in positions]
       std_distance = np.sqrt(np.var(xs) + np.var(ys))
       assert std_distance > 60.0, (
           f"central cluster labels are piled up; "
           f"std distance = {std_distance:.1f} px (need > 60)"
       )
   ```

### Acceptance for S3

- The label-overlap hard test from T5 still passes for all 9 canonical views (no regression).
- The new central-cluster spread test passes.
- Visual: in every frame of the altitude sweep, the central cluster of 6 angle/vector labels is distributed around the target rather than piled up.
- All goldens updated.

### Commit message

`S3: re-tune label solver for co-located-anchor cluster case`

---

## 6. Task S4 — Wire in the break-marks (third attempt)

**Why this matters:** Break-marks were spec'd in round-one T7 and re-targeted in round-two R5. Both rounds reportedly shipped them. Round three shows they are still missing from the connecting lines. This task finds and fixes whatever wiring is broken.

### Diagnostic steps

1. Grep for the module: `find dev_tools/geometry_gui_v2/ -name "break_mark*"`. Confirm `scene/glyphs/break_mark.py` exists. View it. Confirm it defines a function that draws a zigzag.

2. Grep for callers: `grep -rn "break_mark" dev_tools/geometry_gui_v2/`. The expected callers are `scene/vectors/boresight_ray.py` and `scene/vectors/sun_ray_target.py` (or whatever the actual filenames are — view `scene/vectors/` to see).

3. **Likely failure modes** (rank by likelihood):
   - The break-mark module exists but is not imported anywhere. Fix: add the import and call.
   - The break-mark is being called but with arguments that put it off-screen or at zero size. Fix: verify p1 and p2 arguments.
   - The break-mark is being added but the connecting line is drawn over the top of it (z-fighting / draw-order issue). Fix: split the connecting line at the midpoint into two halves with a gap, and draw the break-mark in the gap.
   - The break-mark is being drawn but at a tiny size relative to the connecting line. Fix: make the zigzag size scale with the visible portion of the connecting line, not the total length (because the not-to-scale compression makes the visible line short).
   - The break-mark uses world units that are being clipped by the camera. Fix: anchor the break-mark in screen space.

4. Make a one-line test render: render the default cylinder view, save PNG, view it. Look at the line from target to satellite. Is there a visible zigzag at the midpoint? If not, the wiring is broken.

### Repair steps

1. The connecting line must be **drawn in two halves** with a small gap (5% of total visible length). The break-mark zigzag fills the gap. Do NOT draw the zigzag on top of an unbroken line — that defeats the visual purpose.

2. Update the line-rendering code in `scene/vectors/boresight_ray.py` (target → satellite) and `scene/vectors/sun_ray_target.py` (target → sun):
   ```python
   # Pseudocode for the fix:
   midpoint = 0.5 * (p_target + p_observer)
   gap_half = 0.025 * np.linalg.norm(p_observer - p_target)
   direction = (p_observer - p_target) / np.linalg.norm(p_observer - p_target)
   line_a_end = midpoint - gap_half * direction
   line_b_start = midpoint + gap_half * direction

   # Draw two segments:
   add_line_segment(p_target, line_a_end, color, name="boresight_segment_a")
   add_line_segment(line_b_start, p_observer, color, name="boresight_segment_b")

   # Draw the zigzag in the gap:
   break_mark.add_to_plotter(
       plotter, line_a_end, line_b_start, color, name="boresight_break_mark"
   )
   ```

3. Verify the zigzag is visible at all camera distances. If it disappears at high zoom-out, increase its amplitude relative to gap length.

4. Make the break-mark color match the connecting line color exactly. `SATELLITE_FAMILY` for boresight, `SOLAR_FAMILY` for sun ray.

### Verification

1. Render all 9 canonical views plus the altitude sweep plus the orientation sweeps. View each PNG. **Confirm visually that every frame shows zigzag break-marks at the midpoint of both the target → satellite and target → sun connecting lines.**

2. Add a regression test that asserts the break-mark actors exist and are visible:
   ```python
   def test_break_marks_present_in_default_view():
       plotter = build_scene(default_state(), off_screen=True)
       actor_names = [a.name for a in plotter.actors.values() if a.name]
       assert "boresight_break_mark" in actor_names
       assert "sun_ray_break_mark" in actor_names
   ```

### Acceptance for S4

- Break-marks visible at the midpoint of both connecting lines in every frame of every sweep.
- Connecting lines have a visible gap where the break-mark sits.
- The regression test passes.
- The commit message documents the **root cause** of why this missed in two prior rounds. (Required.)

### Commit message

`S4: wire break-marks into connecting lines (third attempt; root cause: <X>)`

---

## 7. Task S5 — Fix the satellite display position at high target altitude

**Why this matters:** When the target is at altitude 600 km (image 5 of the round-three reel), the satellite at altitude 600 km should be at the same vertical screen position as the target. Instead it appears below the target. The not-to-scale compression policy is breaking down because it anchors the satellite glyph relative to the target without accounting for the target's altitude.

### Diagnosis

1. View `scene/glyphs/observer_glyph.py` (or wherever the satellite glyph is positioned). Find the code that computes the satellite's display position.

2. Round-two R3 specified: `display_position = target_centroid + 3 × target_max_extent × satellite_direction_unit`. This is correct *when the target is at altitude 0*. When target altitude is non-trivial, the satellite-direction unit vector still points correctly, but the magnitude of the offset (3 × target_max_extent) is much smaller than the true target-to-satellite distance. So the satellite glyph ends up just barely above the target, not at the satellite's actual relative altitude.

### The new policy

The not-to-scale compression should compress **distance**, not **direction**. The display position must:

1. Preserve the direction vector from target to satellite exactly. (Already correct.)
2. Use a display distance that is **at least** large enough to put the satellite glyph clearly above the target on screen, even when target altitude is high.

**New formula:**

```python
# True direction from target to satellite (unit vector):
direction = (true_satellite_position - target_position)
direction = direction / np.linalg.norm(direction)

# Display distance: max of (3 × target_max_extent) and (a fraction of the
# total scene extent that includes the target altitude).
target_max_extent = max_dimension(target_mesh)
scene_extent = max(target_max_extent, target_altitude_m / 50)
display_distance = 3.0 * scene_extent

# Display position:
display_position = target_position + display_distance * direction
```

The factor `target_altitude_m / 50` is a heuristic that scales the display distance with target altitude. At target altitude 0, it reduces to the original `3 × target_max_extent`. At target altitude 600 km, it scales the display distance to `3 × 12 m = 36 m`, which puts the satellite glyph well above the target on screen.

### Steps

1. Update the satellite display-position code with the new formula.

2. Update the sun display-position code with the same formula (the sun is also not-to-scale).

3. Update the framing policy from round-two R2 to recompute scene extent using the new display positions. The camera distance is `scene_extent * 2.5` where `scene_extent = max(bounds_size) / 2`, and `bounds` includes the satellite display position.

4. Render the altitude sweep frames (0, 1, 10, 100, 600, 2000 km). For each, view the PNG and confirm:
   - The satellite glyph is visibly above the target at all altitudes.
   - The satellite glyph appears at roughly the same screen-space distance from the target across all altitudes (because the display distance scales with altitude).
   - The connecting line between target and satellite still has its break-mark visible.
   - The scene fills the canvas appropriately at all altitudes (the framing policy handles the larger scene extent).

5. Add a regression test:
   ```python
   @pytest.mark.parametrize("alt_km", [0, 1, 10, 100, 600, 2000])
   def test_satellite_above_target_at_all_target_altitudes(alt_km):
       state = default_state()
       state = state.replace(target_alt_m=alt_km * 1000)
       result = render_view(state)
       sat_screen = result.get_actor_screen_position("satellite_glyph")
       target_screen = result.get_actor_screen_position("target_centroid")
       # In screen coords, smaller y is higher on screen.
       assert sat_screen[1] < target_screen[1], (
           f"alt={alt_km} km: satellite y={sat_screen[1]} is not above "
           f"target y={target_screen[1]}"
       )
   ```

### Acceptance for S5

- The regression test passes for all 6 altitude values.
- Visual altitude sweep shows the satellite glyph clearly above the target at every altitude.
- The break-mark from S4 is still visible at every altitude.
- The framing policy keeps the full scene visible at every altitude.

### Commit message

`S5: scale not-to-scale display distance with target altitude`

---

## 8. Task S6 — Fix the alt=0 sphere-burying

**Why this matters:** At target altitude = 0 km the sphere centroid sits at z=0 and half the sphere is below the ground plane. This is geometrically what the code says to do, but visually it reads as a clipping bug.

### The fix

Two options. Pick whichever the team prefers. **Default to option A unless the math team explicitly requests option B.**

**Option A — render the target sitting ON the ground at alt=0.**

Treat target altitude as the altitude of the *bottom* of the target mesh, not the centroid. When alt = 0, the target sits on the ground with its bottom at z = 0. When alt > 0, the bottom of the target is at z = alt and the centroid is at z = alt + half_height.

Pros: looks correct visually. Common convention for objects sitting on a surface.
Cons: changes the geometric interpretation of `target_alt`. The math team must agree.

**Option B — keep the current centroid convention, add a clear visual treatment.**

Render the part of the target below the ground as a translucent dashed-edge wireframe instead of being clipped. This makes it clear that the target's centroid is at the configured altitude and the target extends both above and below.

Pros: preserves the math.
Cons: harder to implement; some users may still find it confusing.

### Steps for option A (default)

1. View `scene/target/<shape>.py` for each target shape. Identify where the mesh is positioned relative to `state.target_alt_m`.

2. Currently: `mesh.translate(0, 0, target_alt_m)` (centroid at target_alt).

3. Change to: `mesh.translate(0, 0, target_alt_m + half_height)` where `half_height` is computed from the mesh's bounding box.

4. **Update the view-model** to reflect this convention change. `view_model.target_centroid_position` must return `(0, 0, target_alt_m + half_height)` to match the new rendering. All downstream computations (slant range, view direction, etc.) must use this new centroid.

5. Verify with the math team or by checking the existing tests: which value of target_alt do downstream computations expect? If they expect centroid altitude, you have two options: (a) keep `target_alt` as centroid altitude internally and add a separate `target_bottom_alt` for rendering, or (b) flip the convention and update everything. Default: (a), additive change, less risk.

   ```python
   # In view_model:
   def target_render_position(state):
       half_height = compute_half_height(state.target_shape, ...)
       z = state.target_alt_m + half_height
       return (state.target_x_m, state.target_y_m, z)
   # target_centroid stays unchanged for downstream math.
   ```

6. Update the contact-shadow position to sit at z = ground (just above), independent of target altitude:
   ```python
   shadow_z = ground_z + 0.001  # always just above the ground plane
   ```

7. Render the alt=0 frame. Confirm visually that the target sits ON the ground without any part being below it.

8. Render alt=1, 10, 100 km frames. Confirm the target rises off the ground correctly.

### Verification

1. Render the altitude sweep. View each frame.

2. Add a regression test:
   ```python
   def test_target_sits_on_ground_at_alt_zero():
       state = default_state().replace(target_alt_m=0.0)
       plotter = build_scene(state, off_screen=True)
       target_actor = plotter.actors["target"]
       bbox = target_actor.GetBounds()  # (xmin, xmax, ymin, ymax, zmin, zmax)
       z_min = bbox[4]
       assert z_min >= -0.01, (
           f"target z_min = {z_min}; should be ≥ 0 at alt=0"
       )
   ```

### Acceptance for S6

- The regression test passes.
- Visual alt=0 frame shows the sphere sitting cleanly on the ground.
- Visual alt>0 frames show the target rising off the ground correctly.
- Downstream slant-range and view-direction computations still produce correct values (verify by comparing right-panel readouts before and after).
- Choice of Option A or B documented in the commit message.

### Commit message

`S6: render target sitting on ground at alt=0 (Option A; centroid convention preserved)`

---

## 9. Task S7 — Investigate point_source regime tag on large targets

**Why this matters:** The round-three reel shows multiple frames (orientation sweeps, images 9, 11, 13, 14, 15) where the target is large in the viewport but tagged `point_source`. After S1 ships, the regime tag won't be in the viewport, but the underlying behavior may still be wrong — the tag will just be in the right panel instead.

### Diagnosis

1. View `app/view_model.py`. Find `classify_regime`. Note its inputs (target angular extent, IFOV, etc.) and the threshold conditions.

2. View the orientation-sweep fixtures. What state is being set? Specifically:
   - What is `state.target_alt_m`?
   - What is `state.target_size_m` (or whatever defines the target physical size)?
   - What is `state.sensor_focal_length_m` and `state.sensor_pixel_pitch_m`?

3. Compute by hand: at the configured target physical size, target altitude, and sensor parameters, what angular extent does the target subtend? What IFOV does the sensor have? What does Rule 10 produce?

4. Three possibilities:
   - **The regime classifier is wrong.** Then you found a real bug; fix it and add a test.
   - **The orientation sweep state has the target at high altitude or small physical size**, such that it correctly classifies as point_source. Then the visual is misleading because the rendered target is artificially scaled up for visibility (which is a separate issue — the rendered target size in the viewport should reflect the real target's apparent size, or there should be a clear "rendered at N× true scale" indicator).
   - **The orientation sweep deliberately overrides the regime to point_source** to test rendering. Then it's a test fixture choice, not a bug.

### Steps

1. Determine which possibility is real. Document your finding in `dev_tools/geometry_gui_v2/AUDIT_round3.md` (extending the audit from §2).

2. If possibility 1 (classifier bug): fix and add a test against a known-correct regime computation.

3. If possibility 2 (rendering-vs-reality mismatch): add a small "rendered at N× true scale" indicator in the right panel when the rendered target size differs from the true apparent size by more than 2×. This makes it explicit when the user is looking at an artificially-scaled rendering.

4. If possibility 3 (test fixture override): document the override in the fixture file with a comment, and continue.

5. Add a parametrized regression test that exercises the regime classifier across a range of (target size, target altitude, sensor params) and asserts the expected regime in each case. Use values from the existing PLAN documents where available.

### Acceptance for S7

- The root cause is identified and documented in `AUDIT_round3.md`.
- One of the three fixes above is applied.
- The new regression test passes.

### Commit message

`S7: investigate point_source regime tag; root cause was <X>; fix: <Y>`

---

## 10. Task S8 — End-to-end visual verification

After S1–S7 are merged, do the full-app visual verification.

### Required artifacts

For this task to be complete, the following PNGs must exist under `tests/golden/round3/final/`:

1. **All 9 canonical views**, full app (window chrome + both panels + viewport). Filename: `<view_name>_full.png`. Size: 1920×1080 minimum.
2. **All 9 canonical views**, viewport-only (for regression). Filename: `<view_name>_viewport.png`.
3. **Altitude sweep**, viewport-only, 6 frames at 0, 1, 10, 100, 600, 2000 km. Filename: `altitude_<km>km.png`.
4. **Orientation sweep, box**, viewport-only, 5 frames matching round-three reel. Filename: `box_y<yaw>_p<pitch>_r<roll>.png`.
5. **Orientation sweep, cone**, viewport-only, 5 frames matching round-three reel. Filename: `cone_y<yaw>_p<pitch>_r<roll>.png`.
6. **Two slider-drag sequences**, full app, 4 frames each, demonstrating that panel readouts update in lockstep with viewport changes:
   - Drag observer altitude from 400 to 800 km.
   - Drag solar zenith from 0° to 60°.
   Filenames: `slider_alt_<n>.png`, `slider_zenith_<n>.png`.

That's 39 PNGs minimum. Generate them via the off-screen renderer for the viewport-only frames; for the full-app frames, run the app on a virtual display (xvfb-run or equivalent) and take real screenshots.

### The verification table

For each of the 9 canonical views, fill in this table in `dev_tools/geometry_gui_v2/REMEDIATION_REPORT_round3.md`. Twenty checks per view, 180 cells total. Do not skip cells.

| # | Check | Pass / Fail | Notes |
|---|---|---|---|
| 1 | Target is the most visually dominant element | | |
| 2 | Scene fills ≥50% of viewport in both dimensions | | |
| 3 | Camera is isometric three-quarter, no degenerate angle | | |
| 4 | Sun renders as small disc + rays glyph at fixed screen size | | |
| 5 | Satellite renders as small diamond glyph at fixed screen size | | |
| 6 | Ground plane visible as subtle grid extending around target | | |
| 7 | Contact shadow visible on ground plane | | |
| 8 | World-axis gnomon in bottom-left, neutral gray | | |
| 9 | View-cube in top-right, subdued | | |
| 10 | Break-mark visible at midpoint of target → satellite line (S4) | | |
| 11 | Break-mark visible at midpoint of target → sun line (S4) | | |
| 12 | Every angle arc visible (curved tube + arrowhead + midpoint label) | | |
| 13 | Every label has visible leader line ending in anchor dot | | |
| 14 | No label more than 240 px from its anchor | | |
| 15 | No two label bounding boxes overlap (T5 hard test) | | |
| 16 | No label overlaps its own anchor's mesh (S2 hard test) | | |
| 17 | Central cluster labels are spread out, not piled up (S3) | | |
| 18 | No data-readout text in viewport (S1) — no "alt = X", "slant = X", "A_t = X", regime tags | | |
| 19 | All subscripts render properly (no literal `_` in any label) | | |
| 20 | Family colors correct: blue/sensor, amber/solar, green/surface, gray/reference | | |

### Special-case checks

- Full-app frames: right and left dock panels visible with all expected content. Slider drag updates panel readouts.
- Altitude sweep frame at 0 km: target sits cleanly on ground, no burying (S6).
- Altitude sweep frames at all altitudes: satellite is clearly above target (S5).
- Orientation sweeps: target rotates correctly, regime tag (in panel) is documented and correct (S7).

### Steps

1. Run the full test suite. All tests pass. If any fail, fix or file as blocker.

2. Generate all 39 PNGs. View each one. Do not bulk-process — actually look at each frame.

3. Fill in the 180-cell table. Every cell. No blanks.

4. For every Fail entry: either fix and re-test until it passes, or file in `REMEDIATION_BLOCKERS.md` with a detailed explanation.

5. Run the app interactively on a real desktop. Drag sliders. Confirm:
   - Slider drags produce 60 fps viewport updates for the default scene.
   - Slider drags produce ≥30 fps updates for the most expensive scene (extended cell + box + all vectors visible).
   - Right-panel readouts update in lockstep with slider drags, no lag.
   - View-cube clicks animate the camera over 400 ms.
   - Frame-switcher dropdown re-expresses vectors with smooth transition.
   - Help overlay (`?` key) opens.

6. Write `REMEDIATION_REPORT_round3.md`:
   - Summary of S1–S7 commits with hashes.
   - The full 180-cell verification table.
   - The special-case results.
   - Interactive-test results.
   - Side-by-side thumbnail comparison with the round-three reel: each round-three reel frame next to the corresponding S8 frame.
   - A bullet list of any deferred items or known issues.

### Acceptance for S8

- All 39 PNGs generated, saved, and visually inspected.
- The 180-cell table is fully populated. Every cell either Pass or has a filed blocker.
- Interactive test passes.
- `REMEDIATION_REPORT_round3.md` is written and complete.
- A side-by-side comparison shows the round-three defects (label cluster, data readouts in viewport, missing break-marks, satellite at wrong altitude, sphere half-buried) are all resolved.

### Commit message

`S8: end-to-end visual verification of round-three remediation`

---

## 11. Task tracker

Maintain this table. Update after every task. Commit hash = SHA of the single commit produced by that task.

| ID | Title | Status | Commit | Notes |
|---|---|---|---|---|
| Audit | Round-three pre-flight audit | ☐ |  |  |
| S1 | Separate viewport labels from data readouts | ☐ |  |  |
| S2 | Enforce label/anchor non-overlap | ☐ |  |  |
| S3 | Re-tune label solver for cluster case | ☐ |  |  |
| S4 | Wire in break-marks (third attempt) | ☐ |  |  |
| S5 | Fix satellite display at high target altitude | ☐ |  |  |
| S6 | Fix alt=0 sphere-burying | ☐ |  |  |
| S7 | Investigate point_source regime tag | ☐ |  |  |
| S8 | End-to-end visual verification | ☐ |  |  |

---

## 12. Operating reminders (rules from prior rounds that still apply)

**Render and view every screenshot before declaring a task done.** Round-one and round-two failures both included tasks declared done that hadn't been visually verified.

**Verify across all 9 canonical views, not just cylinder.** This is the rule that produced rounds two and three. Do not break it again. Plus, for tasks involving altitude or orientation, run the round-three sweep set as well (the sweeps surfaced defects the canonical views missed).

**If a task says "wire it into the builder," confirm the wiring with a grep.** Round-three reel showed break-marks were unwired despite shipping in two prior rounds. Module exists ≠ module runs.

**One task, one commit.** Do not bundle. Do not amend across tasks. Do not squash.

**If you cannot make a task's acceptance pass, stop and report.** Add to `REMEDIATION_BLOCKERS.md`. Do not silently ship a partial fix.

**S1 is the highest-priority task in this round.** It removes ~50% of in-viewport text and makes everything downstream tractable. Do it first.

**S4 is the most embarrassing task in this round.** Break-marks have shipped in two prior rounds and are still missing. Do not let this happen a third time. The S4 commit message must include the root-cause analysis.

**The audit step in §2 is not optional.** If the panels are NOT actually shipped (contradicting the prior agent's report), surface that finding to the human reviewer before doing any of S1–S7. Do not silently re-implement the panels.

---

## 13. What success looks like

After S1–S8 ship, the rendered default scene shows:

- An isometric three-quarter view.
- Target at center, PBR-shaded, sitting cleanly on the ground at alt=0, with visible terminator and contact shadow.
- Subtle gray-grid ground plane fading to viewport background at the edges.
- Small white satellite diamond glyph above the target at fixed screen size, with target → satellite line broken by a visible zigzag at the midpoint.
- Small amber sun disc + rays glyph above the target at fixed screen size, with target → sun line broken by a visible zigzag at the midpoint.
- Small green sphere for the background point.
- Visible angle arcs (off-nadir, α_t, θ_sun,B) as curved tubes connecting the relevant vectors, each with arrowhead and midpoint label.
- Six central-cluster labels (`θ_off`, `s_t`, `θ_s`, `α_t`, `o`, `n_B`) **distributed around the target**, not piled up at the center. Each with a visible leader line ending at an anchor dot.
- `Target` / `Satellite` / `Sun` / `Background` text labels positioned away from their respective meshes.
- **No** `alt = X km`, `slant = X km`, `A_t = X m²`, or regime tags in the viewport. All those values live in the right panel.
- Subdued view-cube top-right.
- Neutral world-axis gnomon bottom-left.
- 240 px right-dock panel showing four collapsible sections with all live readouts including everything that was removed from the viewport in S1.
- 200 px left-dock panel with the full slider inventory.
- Slider drag updates viewport at 60 fps and panel readouts in lockstep.

That's the bar. When you achieve it, write the final report and stop.

---

## 14. What is and isn't in scope for this round

**In scope:** S1–S8. Anything that blocks an acceptance criterion in those tasks. Bug fixes in code touched by those tasks. The pre-flight audit.

**Not in scope:** Project-wide Phase 5 interaction polish (drag handles on glyphs, hover-fade-others, animated dashed-pulse on selection), Phase 6 app-shell polish (theme switching, settings dialog, app icon), Phase 7 hardening, Trame web deployment, scenario YAML loading, multi-target views, anything in `/src/`. (Note: the project-wide phase numbering is distinct from this round's task IDs S5/S6/S7, which ARE in scope.)

If you find yourself wanting to do something out of scope, stop and file it as a deferred item in the final remediation report.

---

## 15. Reporting back

When you finish, your report to the human reviewer must include:

- The completed task tracker from §11.
- The 180-cell verification table from S8.
- Path to `REMEDIATION_REPORT_round3.md`.
- Path to all 39 generated PNGs.
- Contents of `REMEDIATION_BLOCKERS.md` (empty if everything went well).
- The audit findings from §2.
- A one-paragraph summary of what changed.

If anything failed acceptance and you could not resolve it, say so plainly. Optimistic status reports are worse than accurate failure reports.
