# RADIANT Geometry GUI — Master Plan v2 (PyVista Rewrite)

**Owner:** Jason Forsyth
**Status:** Draft v2, 2026-04-26 — supersedes Plan v1
**Scope change:** This is no longer a developer-only diagnostic tool. **It is the visual-design prototype for what will eventually ship as the production RADIANT GUI.** Hold it to that bar.
**Prior plan:** `PLAN.md` (v1, Plotly Dash, Phases 0–16). v1 is closed. No further work lands against it.

---

## 0. Read this first — what's changing and why

Plan v1 produced a working developer tool but hit an unfixable visual ceiling. The Phase 8–16 redesign work (target-centric framing, label deconfliction, visual hierarchy, PBR shading, contact shadows, view-cube) is exactly the right product direction. The problem is that **the rendering library cannot deliver it.** Plotly's `Mesh3d` does not support real lighting; its annotations have no leader-line or collision-avoidance primitive; its legend cannot be replaced with a structured panel; its glyphs cannot be sized in screen-space; its interaction model has no picking or drag handles. Six phases of polish on Plotly produced screenshots that are visually almost identical to Phase 7. We have evidence the ceiling is real.

We are switching the rendering and UI stack to **PyVista + PyQt** for v2. Same Python language, same team, same RADIANT integration boundary, different rendering engine. PyVista is a Pythonic wrapper over VTK (the engine that powers ParaView). It gives us real PBR materials, real directional lighting, real shadows, screen-space billboarded labels, picking and drag handles, a built-in view-cube widget, and a native desktop window via Qt. Everything Plan v1 Phases 8–16 wanted is a first-class primitive in this stack.

This plan is also a scope change. **We are no longer building a developer-only tool.** We are building the visual-design prototype of the future production GUI. That means:

- Aesthetic quality is now a hard requirement, not a stretch goal.
- The tool gets a real product name, a real window chrome, a real menu bar, a real settings system.
- Constraint C1 from v1 ("zero edits to `/src/`") still applies during v2 — we are not yet integrating into the production codebase. But the architecture must be ready for that integration when the time comes.
- The reusable scene-rendering layer must be packaged so the production GUI can import it later without modification. Treat the scene library as a deliverable, not a script.

**On reuse from v1.** Roughly 80% of v1 code is tied to Plotly and Dash and will be discarded. Roughly 20% is platform-neutral and ports cleanly: the view-model layer, the regime classifier, the projected-area handoff, the slider inventory, the readout-panel content, and the SceneState dataclass. Phase 1 of v2 explicitly identifies and lifts that code. Engineers should expect to write most rendering and UI code from scratch, but should not rewrite the physics. The goal is one canonical view-model that both v1 and v2 could have used; v2 just gets a vastly better presentation layer.

---

## 1. Goal

Build the **visual-design prototype of the production RADIANT geometry GUI** as a native desktop application in Python. The application lets a user manipulate every geometric parameter the RADIANT pipeline consumes (observer altitude / look-angle / attitude, target altitude / shape / size / orientation, sun zenith / azimuth, regime selector, sensor focal length & pixel pitch) and watch a high-fidelity, target-centric 3D scene update in real time. The tool must:

1. Render observer, ground, target, target body axes, sun direction, and a background marker in a rotatable, target-centric 3D scene with real PBR lighting, soft contact shadows, and screen-space label management.
2. Compute and display the projected target area used by the radiometry by calling `TargetShape.projected_area(view_direction)` directly. The displayed value is the value used downstream — no re-derivation.
3. Toggle between extended and sub-pixel target regimes, plus an `auto` mode that shows which Rule-10 branch fired.
4. Provide a shape selector (Sphere, Cylinder, FlatPlate, Box, Cone — matching `radiant.source.shapes`) with size and orientation controls per shape.
5. Display derived geometry (slant range, ground range, GSD, IFOV, angular extent, fill fraction, projected area, regime, solar angles) in a structured panel with units on every value.
6. Look and feel like a 2026 scientific instrument, not a plotting library output. This is the bar.

## 2. Non-goals for v2

- Not yet wired into `radiant.api` or `radiant.cli`. The integration boundary is the same as v1: `radiant.core.geometry` and `radiant.source.shapes` only.
- No radiance / SNR / NEDT computation. Geometry only. The projected-area handoff to radiometry remains the single numeric link surfaced.
- No scenario YAML loading in v2. Sliders only.
- No persistence (save / load) of user sessions in v2. Window state is fine to persist; scene parameters are not.
- No web / browser deployment in v2. Native desktop only. (See section 13 for the deferred Trame web-deployment path.)
- No multi-target or constellation views.

## 3. Hard constraints

| # | Rule | Enforcement |
|---|------|-------------|
| C1 | Zero edits to `/src/`. | CI check: `git diff --name-only origin/main...HEAD \| grep -q '^src/' && exit 1` runs in every phase. |
| C2 | All v2 code lives under `dev_tools/geometry_gui_v2/`. v1 code under `dev_tools/geometry_gui/` is frozen and not deleted; it remains as reference until v2 reaches Phase 6 acceptance, then it is archived to `dev_tools/_archive/geometry_gui_v1/`. | Reviewed at end of each phase. |
| C3 | Projected area shown on screen comes from `TargetShape.projected_area(...)`. No re-derivation anywhere. | Phase 4 acceptance test (parity vs direct shape call across 50 random states, machine precision). |
| C4 | Units on every numeric label. | Snapshot test of the readout panel in Phase 4. |
| C5 | Rule 19 (one computation, one module) applies. The scene library has one file per primitive — one for the target mesh dispatcher, one for the boresight ray, one for the sun ray, one for the body axes, etc. No file builds two different primitives. | Reviewer check each phase. |
| C6 | No private `/src` symbols (anything starting with `_`). Re-implement small math (regime classifier, ZYX transpose) in the view-model layer. | Grep check: `grep -rn 'from radiant.*import.*_' dev_tools/geometry_gui_v2/` returns empty. |
| C7 | The scene library (`scene/` package) has zero dependencies on the UI shell (Qt widgets, menu bar, settings). It must be importable from a Jupyter notebook with only PyVista installed and produce a renderable scene. The UI shell depends on the scene library, never the reverse. | Phase 2 acceptance: `python -c "from geometry_gui_v2.scene import build_scene; build_scene(default_state())"` runs without importing PyQt. |
| C8 | Aesthetic-quality regression tests. Each phase that touches rendering produces golden screenshots at 1920×1080 for all six target geometries (sphere, cylinder, cone, box, flat-plate, extended-cell) plus the geometry-diagram view. Goldens are reviewed by Jason before merge and locked. | CI check via `pytest --image-baseline`. |

## 4. Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  PySide6 desktop shell                                             │
│   ─ menu bar, status bar, dockable panels, settings dialog         │
│   ─ left dock: parameter panel (sliders, dropdowns)                │
│   ─ center: PyVistaQt QtInteractor (the 3D viewport)               │
│   ─ right dock: structured info panel (objects / vectors /         │
│                 angles / regime, all live readouts)                │
│   ─ overlays: view-cube gizmo, frame indicator, axis triad         │
└────────────────────┬───────────────────────────────────────────────┘
                     │  parameter changes (Qt signals)
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│  app/state.py   — SceneState dataclass (frozen, hashable)          │
│                   one field per slider value, identical to v1      │
└────────────────────┬───────────────────────────────────────────────┘
                     │  build()
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│  app/view_model.py  — pure functions, no UI, no rendering          │
│   ─ build_observer_geometry()                                      │
│   ─ build_target_shape()                                           │
│   ─ compute_view_direction()                                       │
│   ─ classify_regime()                                              │
│   ─ projected_area()  ← calls shape.projected_area(...)            │
│   ─ derived_readouts()  → dict of labeled, unit-stamped values     │
│  Imports ONLY from radiant.core.* and radiant.source.shapes        │
│  PORTED FROM v1 with minimal changes — this is the reuse point.    │
└────────────────────┬───────────────────────────────────────────────┘
                     │  view-model output
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│  scene/  ─ standalone PyVista scene library (the deliverable)      │
│   ─ scene/builder.py        — orchestrator: state → pv.Plotter     │
│   ─ scene/target/           — one file per shape (Rule 19)         │
│   ─ scene/vectors/          — boresight, normal, sun, sun-to-bg    │
│   ─ scene/glyphs/           — observer, sun, background point      │
│   ─ scene/labels/           — leader-line + slot layout system     │
│   ─ scene/frames/           — body axes, world axes                │
│   ─ scene/ground/           — ground cap, contact shadow, grid     │
│   ─ scene/arcs/             — angle arcs (off-nadir, α_t, etc.)    │
│   ─ scene/style.py          — palette, line widths, glyph sizes,   │
│                                lighting dict (single source of     │
│                                truth, ported from v1 Phase 16)     │
│   No Qt imports. No app-shell imports. (See C7.)                   │
└────────────────────────────────────────────────────────────────────┘
```

Data flow is one-way: state → view-model → scene. No mutation. The Qt shell holds the only mutable state (the SceneState held in a single Qt model object); every parameter change rebuilds an immutable SceneState, runs it through the view-model, and refreshes the scene incrementally via PyVista's actor-update API (no full re-render on every slider tick).

## 5. Tech stack — committed choice for v2

**PyVista + PyVistaQt + PySide6**, all free and pip-installable. (D1 resolved 2026-04-26 — see §16.)

| Component | Role | License |
|---|---|---|
| `pyvista` | High-level 3D scene API. PBR materials, lighting, picking, callbacks. | MIT |
| `vtk` | Underlying engine (pulled in by PyVista). | BSD |
| `pyvistaqt` | Embeds the PyVista renderer in a Qt widget (`QtInteractor`). Supports both PyQt and PySide. | MIT |
| `PySide6` | Native desktop window, menu bar, dockable panels, sliders. Official Qt-for-Python binding, current Qt 6, modern HiDPI / Apple Silicon support. | LGPL |
| `numpy` | Already a transitive dep of RADIANT. | BSD |
| `qt-material` or `qdarkstyle` | Modern Qt theme so the shell does not look like a 1998 X11 application. | BSD / MIT |

Install command for engineers:

```bash
pip install "pyvista>=0.43" "pyvistaqt>=0.11" "PySide6>=6.7" numpy "qt-material>=2.14" pytest "pytest-qt>=4" pytest-image-diff
```

**Python version pin.** PySide6 6.7+ is the floor for Python 3.12; 6.5.x requires `<3.12`. PyVista 0.43+ has reliable 3.12 wheels. Recommended interpreter: **Python 3.12** (3.13 also works; avoid 3.14 until upstream wheel coverage stabilizes).

**`pytest-image-diff` has no pin.** Max published version on PyPI is `0.0.14`; an earlier draft of this plan specified `>=0.1`, which doesn't exist and breaks the install (pip's all-or-nothing resolver fails the whole transaction).

Alternatives considered and rejected:

- **Three.js + React (Path A):** Top-tier polish but requires a frontend engineer and a JavaScript build pipeline. Not justified for a Python-shop scientific instrument.
- **Plotly Dash (the v1 stack):** Hit the ceiling that prompted this rewrite. Out.
- **Matplotlib mpl_toolkits:** No interactive 3D worth using. Out.
- **Mayavi:** Same VTK engine as PyVista but stale, less Pythonic, smaller community. PyVista is strictly better.
- **Vispy:** Lower-level, would require us to write our own scene-graph and label manager. Solving the wrong problem.
- **Trame (web-served PyVista):** Tempting because it gives us browser deployment, but introduces an extra rendering hop and a JavaScript/Vue layer that fights us on label management. v2 stays native; Trame is filed as the deferred web-deployment path (section 13).

## 6. What survives from v1 (the salvage list)

Engineers must not rewrite physics. Before writing any new code, lift the following modules verbatim into v2 and adjust only their imports:

- `app/state.py` — `SceneState` dataclass. **Lift as-is.** Rename module path to `geometry_gui_v2/app/state.py`.
- `app/view_model.py` — all pure functions. **Lift as-is.** Verify all unit tests still pass under v2's test directory.
- `app/scene_builder/visual_hierarchy.py` — palette, line widths, glyph sizes, lighting dict. **Lift, then port:** drop the Plotly-specific `TARGET_LIGHTING` keys and remap to PyVista's `add_mesh(pbr=True, metallic=..., roughness=...)` parameter names. Acceptance: every numeric constant in v1's `visual_hierarchy.py` has a corresponding constant in v2's `scene/style.py`, and a unit test pins each value.
- The slider inventory in PLAN v1 §6 — **lift verbatim.** Same ranges, units, RADIANT field bindings.
- The readout-panel contents in PLAN v1 §7 — **lift verbatim.** Same labels, same units, same number of lines. The presentation changes (it goes into a structured Qt panel instead of a Plotly text block) but the content does not.
- The regime-classifier truth table tests — **lift verbatim.** They are pure logic and should pass unchanged.
- The Phase 5 projected-area parity test — **lift verbatim.** Most important test in the codebase.

What does NOT survive:

- Everything in `app/scene_builder/` other than `visual_hierarchy.py` and the Phase 5 silhouette helper. Rebuild against PyVista.
- `app/main.py` — the Dash app wiring. Rebuild as a PyQt application.
- All Plotly Figure assembly, layout dictionaries, `dcc.Slider` wiring, `uirevision` workarounds, label-collision workarounds, view-cube SVG hacks. Discard.
- The `_arc_palette.py` file — the *colors* lift but the trace-construction code does not. Rebuild against `pyvista.Spline` and `pv.add_mesh` with `style='wireframe'`.
- The Phase 13 leader-line label system — discard the implementation, keep the design intent. PyVista has a native screen-space label primitive (`pv.Plotter.add_point_labels` with `always_visible=True` and a 2D label actor); the leader-line rendering becomes a thin wrapper around `vtk.vtkLeaderActor2D` instead of a Plotly annotation hack.

## 7. Phase plan

Eight phases. Each is one engineer-week of focused work for a single engineer, give or take. Each phase produces a working, runnable application — the team should be able to demo every phase to Jason. No phase produces dead code.

| Phase | Title | Deliverable | Acceptance |
|---|---|---|---|
| 0 | Scaffold + salvage | Empty PyQt app opens with embedded PyVista viewport showing a single test cube. v1 view-model + state ported and tests passing under v2's test directory. | `python -m dev_tools.geometry_gui_v2.app.main` opens a window. All ported v1 view-model tests green. |
| 1 | Scene library skeleton | `scene/` package with stub modules for every primitive (target, vectors, glyphs, frames, ground, arcs, labels). `scene.build_scene(state)` returns a `pv.Plotter` populated with placeholder geometry for every primitive. No styling yet. | Importable without Qt (C7). All six target shapes render as identifiable meshes. Golden screenshots locked at low fidelity. |
| 2 | PBR target rendering + ground | Real PBR lighting on the target. Soft contact shadow disc. Ground cap with subtle grid. Sun-direction directional light wired to view-model output (lit / dark sides are physically correct). | Visual: each of the six target shapes shows visible terminator. Screenshot test confirms lit hemisphere matches sun direction within 2° tolerance. |
| 3 | Vectors, arcs, glyphs | Boresight, surface normal, sun rays, sun-to-background ray as anti-aliased tubes with proper line widths from `scene/style.py`. Angle arcs (off-nadir, α_t, θ_sun_B) as curved tubes with arrowheads. Observer diamond glyph and sun disc-with-rays glyph at fixed screen-space size. Break-mark on the not-to-scale connecting line. | Visual: arcs visibly connect the two vectors they measure. Glyph screen size constant under zoom (regression test: render at zoom 1× and 4×, glyph pixel diameter equal within 1px). |
| 4 | Labels with leader lines + readouts | Screen-space label system. Every annotation has a leader line to its anchor. Force-directed deconfliction so no two labels overlap. Right-side dock panel with structured readout panel (Scene objects / Vectors / Angles / Regime) showing live values from view-model. Projected-area readout calling `shape.projected_area(view_dir)`. | Hard test: render all 9 canonical scenes, OCR the screenshot, confirm no two label bounding boxes intersect. Parity test: A_t shown equals `shape.projected_area(view_dir)` to machine precision across 50 random states. |
| 5 | Interaction + view-cube + frame switcher | View-cube gizmo (top-right of viewport) with click-to-snap canonical views (+X/-X/+Y/-Y/+Z/-Z/iso). Click-to-select on any vector or angle highlights it with the accent color and pulses the dashed stroke. Hover tooltips on every glyph. Keyboard shortcuts (R = recenter, 1–6 = canonical views, ? = help overlay). Coordinate-frame indicator with dropdown to switch between world / body / sensor frames; the entire scene re-expresses vectors in the chosen frame with a smooth animated transition. | Manual: every keyboard shortcut works. Frame switch animates over ~400 ms. Click-to-select activates the highlight on at least the boresight, surface normal, and α_t arc. |
| 6 | App shell polish + theme | Dark + light theme via `qt-material`. Real menu bar (File, View, Frame, Scene, Help). Real status bar showing the active frame and current regime. Settings dialog for theme, default frame, and display unit choices (km vs m, deg vs rad). About dialog with version and license. Window state persists between sessions. App icon. Window title `RADIANT — Geometry`; About dialog `RADIANT Geometry Module` (D2 resolved — this is a module of the larger RADIANT GUI, not a standalone product). | Manual: app looks like a 2026 scientific instrument when shown to a stranger. Goldens locked for both themes across all 9 canonical views. |
| 7 | Hardening + handoff package | Performance pass: slider drag at 60 fps for the default scene, ≥30 fps for the most expensive scene (extended cell + box target + all vectors visible). Memory: no leak across 100 slider sweeps (test via `tracemalloc`). Documentation: `README.md` with screenshot, install commands, run command, architecture diagram, glossary of every angle and vector. Packaging: `pip install -e .` from `dev_tools/geometry_gui_v2/` works. CI runs all tests headlessly. | All targets met. Jason demos the tool to one external stakeholder; that stakeholder can identify every angle and vector without help. |

## 8. Phase 0 — Scaffold + salvage (engineer prompt)

> **Goal:** Stand up the v2 application skeleton. Lift v1's view-model and state intact. Do not write any rendering code yet.
>
> **Steps:**
>
> 1. Create `dev_tools/geometry_gui_v2/` with this structure:
>    ```
>    dev_tools/geometry_gui_v2/
>      pyproject.toml              # package metadata + entry points
>      README.md                   # one-line stub for now
>      app/
>        __init__.py
>        main.py                   # PyQt entry point
>        state.py                  # ← lifted from v1
>        view_model.py             # ← lifted from v1
>      scene/
>        __init__.py               # exposes build_scene
>        style.py                  # ← lifted from v1 visual_hierarchy.py, ported
>      tests/
>        __init__.py
>        test_view_model.py        # ← lifted from v1
>        test_state.py             # ← lifted from v1
>    ```
> 2. Lift `state.py` and `view_model.py` from v1 verbatim, adjusting only the import paths. Run the lifted tests; they must pass.
> 3. Port `visual_hierarchy.py` to `scene/style.py`. Drop the Plotly-specific `TARGET_LIGHTING` dict (`ambient`/`diffuse`/`specular`/`roughness`/`fresnel`) and replace with PyVista PBR keys: `metallic`, `roughness`, `diffuse_color`. Keep every color hex unchanged. Keep every line width and glyph size unchanged. Pin every constant in a unit test.
> 4. Build `app/main.py`: a PySide6 `QMainWindow` with a `pyvistaqt.QtInteractor` filling the central widget, a placeholder left dock (empty), a placeholder right dock (empty), and a menu bar with File → Quit. The viewport renders a single `pv.Cube()` so we can confirm rendering works. Set `os.environ["QT_API"] = "pyside6"` before importing `pyvistaqt` so the binding selection is unambiguous.
> 5. Add `pyproject.toml` with dependencies pinned to versions known to work together: `pyvista>=0.43`, `pyvistaqt>=0.11`, `PySide6>=6.7` (Python 3.12 floor — 6.5.x requires `<3.12`), `numpy>=1.24`, `pytest>=7`, `pytest-qt>=4`, `pytest-image-diff` (no version floor — max on PyPI is `0.0.14`).
> 6. Add a smoke test that imports `radiant.core.geometry` and `radiant.source.shapes` and constructs each shape. This is the integration-boundary canary.
>
> **Acceptance:**
> - `python -m dev_tools.geometry_gui_v2.app.main` opens a window with a rotatable cube.
> - `pytest dev_tools/geometry_gui_v2/tests/` is green.
> - `grep -rn 'from radiant.*import.*_' dev_tools/geometry_gui_v2/` returns nothing (C6).
> - No file in `dev_tools/geometry_gui_v2/` imports `plotly` or `dash`.

## 9. Phase 1 — Scene library skeleton (engineer prompt)

> **Goal:** Build the `scene/` package as a standalone, Qt-free library that, given a `SceneState`, returns a populated `pv.Plotter`. Every primitive has a stub. Styling is minimal — the goal is structure, not beauty.
>
> **Steps:**
>
> 1. Create the full `scene/` directory tree per section 4. One file per primitive (Rule 19 / C5).
> 2. `scene/builder.py` exports `build_scene(state: SceneState, plotter: pv.Plotter | None = None) -> pv.Plotter`. If `plotter` is None, create a fresh `pv.Plotter(off_screen=False)`. Iterate primitives in fixed order (ground → contact shadow → target → frames → vectors → arcs → glyphs → labels) and call each module's `add_to_plotter(plotter, state)` function. Return the plotter.
> 3. Implement each shape's `add_to_plotter` with `pv.Sphere`, `pv.Cylinder`, `pv.Cone`, `pv.Box`, `pv.Plane` (for FlatPlate), and a `pv.Plane` with grid texture (for the extended cell). No PBR yet — flat shading is fine for Phase 1.
> 4. Vectors: `pv.Tube` from `pv.Spline` with two points. Hard-code line width from `style.py`. No arrows yet.
> 5. Arcs: `pv.Spline` along a circular arc between the two relevant vectors at unit radius. Hard-code line width.
> 6. Glyphs: `pv.Sphere` for sun (no rays yet), `pv.Cube` for observer (no diamond yet). Sized in world units for now (Phase 3 will move them to screen-space).
> 7. Labels: `plotter.add_point_labels()` with default placement. Phase 4 replaces this.
> 8. Frames: three short tubes per frame triad, in `BODY_AXES_COLOR` / `WORLD_AXES_COLOR`. Tip text via `add_point_labels`.
> 9. Ground: `pv.Plane` for the cap. `pv.Disc` for the contact shadow stub (will become PBR shadow in Phase 2). No grid texture yet.
> 10. C7 enforcement: write a test `tests/test_scene_imports_without_qt.py` that blocks all Qt bindings (`PySide6`, `PySide2`, `PyQt5`, `PyQt6`) via `unittest.mock.patch.dict(sys.modules, {name: None for name in ("PySide6", "PySide2", "PyQt5", "PyQt6")})`, then runs `from dev_tools.geometry_gui_v2.scene import build_scene` and asserts no Qt module was loaded.
>
> **Acceptance:**
> - `python -c "from dev_tools.geometry_gui_v2.scene import build_scene; from dev_tools.geometry_gui_v2.app.state import default_state; p = build_scene(default_state()); p.show()"` opens a window with all primitives visible.
> - All six target shapes render and are visually distinguishable.
> - `tests/test_scene_imports_without_qt.py` passes (C7).
> - Golden screenshots locked at low fidelity for the 6 shapes + the geometry-diagram view.

## 10. Phase 2 — PBR target rendering + ground (engineer prompt)

> **Goal:** Make the target look like a 3D object. Real PBR lighting from the actual sun direction. Soft contact shadow. Subtle grid on the ground cap.
>
> **Steps:**
>
> 1. Replace `plotter.add_mesh(target_mesh)` with `plotter.add_mesh(target_mesh, pbr=True, metallic=0.1, roughness=0.45, diffuse_color=TARGET_COLOR, smooth_shading=...)`. Faceted shapes (box, flat-plate) set `smooth_shading=False`; smooth shapes (sphere, cylinder, cone) set `smooth_shading=True`.
> 2. Add a directional light pointing along `-s_t` (i.e., from sun toward target) via `plotter.add_light(pv.Light(position=sun_position, focal_point=target_centroid, light_type='scene light'))`. Intensity 1.0. Add a faint ambient fill light so the dark side is not pitch black: `pv.Light(light_type='headlight', intensity=0.15)`.
> 3. Verify lit hemisphere matches the sun direction. Move the sun slider; the terminator on the sphere target should rotate accordingly.
> 4. Contact shadow: replace the Phase 1 `pv.Disc` stub with a `pv.Disc` of radius `1.05 * target_half_extent`, `pv.add_mesh(disc, color='black', opacity=0.18, lighting=False)`. Place at `z = ground_plane_z + 0.001` to avoid z-fighting.
> 5. Ground cap: `pv.Plane` with a procedural checker or grid texture at `GRID_OPACITY = 0.08`. Use `pv.Texture` from a generated 512×512 numpy array (alternating gray squares with 8% alpha). The grid teaches scale without dominating.
> 6. Re-lock the Phase 1 golden screenshots — they all change in this phase. Document the diff in the commit message.
>
> **Acceptance:**
> - Sphere target shows a clear terminator that rotates with the sun slider.
> - Box and flat-plate targets show flat-shaded faces with sharp edges.
> - Contact shadow visible under each target on the ground cap.
> - Image diff vs Phase 1 goldens shows the expected lighting and shadow changes; no other unexplained pixel movement.

## 11. Phase 3 — Vectors, arcs, glyphs (engineer prompt)

> **Goal:** All non-target geometry rendered to spec. Anti-aliased tubes for lines. Real arrowheads. Curved arcs for angles. Screen-space-sized glyphs that stay the same pixel size at every zoom level. Break-marks on the not-to-scale connecting lines to satellite and sun.
>
> **Steps:**
>
> 1. Replace each `pv.Tube` from Phase 1 with the proper helper: `vector_with_arrow(start, end, color, width)` builds a tube + a `pv.Cone` arrowhead at the tip. One helper, used by every vector module.
> 2. Angle arcs: `arc_between_vectors(v1, v2, radius, color, width, with_arrowhead=True)` returns a curved tube along the great arc on the unit sphere from `v1` to `v2`, with a small cone at the `v2` end. Used by every arc module (off-nadir, α_t, θ_sun_B, az, el).
> 3. Glyph screen-space sizing: PyVista does not have native screen-space sizing for meshes, so we use `pv.PolyData` with `add_mesh(..., render_points_as_spheres=True, point_size=SAT_GLYPH_SIZE)` for the observer (point size IS in pixels). For the sun disc + rays, use a `vtk.vtkBillboardTextActor3D` or `vtk.vtkActor2D` overlay positioned at the projected sun location each frame. Wire the camera-update callback to keep the position in sync.
> 4. Break-mark: on the connecting line between the target and the satellite glyph, render a small zigzag `pv.Spline` (3 zig-zag points) at the midpoint, in the same color as the connecting line. Same for the target-to-sun connecting line. Indicates "not to scale."
> 5. Sun glyph: a small `pv.Disc` for the body + 8 short `pv.Tube` rays at 45° increments. All sized in screen-space pixels per `SUN_DISC_SIZE` and `SUN_RAY_TIP_SIZE`. Wrap in a single helper that returns a `vtkAssembly`.
> 6. Observer glyph: a `vtk.vtkRegularPolygonSource` with 4 sides (a diamond) sized to `SAT_GLYPH_SIZE`. Outline in `SATELLITE_FAMILY` color, fill white.
>
> **Acceptance:**
> - Each angle arc visibly connects the two vectors it measures.
> - Glyphs are exactly `SAT_GLYPH_SIZE` / `SUN_DISC_SIZE` pixels at zoom 1×, 2×, and 4× (regression test).
> - Break-marks present on the satellite-target and sun-target connecting lines.
> - Sun rays rotate around the disc at 45° increments.

## 12. Phase 4 — Labels with leader lines + readouts panel (engineer prompt)

> **Goal:** Solve the label-collision problem v1 could not solve, and ship the structured readouts panel.
>
> **Steps:**
>
> 1. Build `scene/labels/leader_label.py`: a class wrapping `vtk.vtkLeaderActor2D` (a leader line in screen space) plus a `vtkTextActor` (the label text). The pair shares a 3D anchor point in world coordinates; the line and text live in 2D screen space, computed each render via the camera projection.
> 2. Build `scene/labels/layout.py`: a force-directed slot solver. Inputs: list of `(anchor_world_xyz, label_text, family_color)` tuples. Outputs: `(label_screen_xy, leader_line_path)` per label. Run on every camera change. Algorithm: place each label initially at a 60-pixel offset along the projected anchor's outward normal from the scene centroid; iterate a force simulation (anchor-attraction + label-label repulsion + viewport-edge repulsion) for 30 steps or until convergence. This is the v1 Phase 13 design intent, finally implementable now that we have a real screen-space layer.
> 3. Wire every label-emitting primitive (vectors, arcs, glyphs, frame tips, background point) to `LeaderLabel`. Default behavior: show only the active angle group's labels; others render as faded numeric chips that expand on hover.
> 4. Right-side dock panel: build a `QWidget` with four collapsible `QGroupBox` sections (Scene objects / Vectors / Angles / Regime). Wire each row to a live readout from `view_model.derived_readouts(state)`. Use a monospace font (Inter Mono, JetBrains Mono, or system fallback) for numeric values. Right-align numbers. Pad to a tabular grid.
> 5. Add the projected-area readout: `Projected area A_t : 12.57 m²    [from shape.projected_area]`. The trailing tag is literal — it tells the user this number is the radiometry handoff.
> 6. Hard test for label deconfliction: render all 9 canonical scenes at 1920×1080. For each, extract every text actor's screen-space bounding box. Assert no two boxes intersect by more than 1 pixel.
>
> **Acceptance:**
> - Zero label overlaps across the 9 canonical views (hard test).
> - Right panel shows live values for every readout in v1 PLAN §7, with units, in monospace, right-aligned.
> - Projected-area parity test green: GUI value equals `shape.projected_area(view_dir)` to machine precision across 50 random states.

## 13. Phase 5 — Interaction (engineer prompt)

> **Goal:** Make it a tool, not a picture. View-cube gizmo. Click-to-select. Drag handles. Hover tooltips. Keyboard shortcuts. Frame switcher.
>
> **Steps:**
>
> 1. View-cube gizmo: PyVista has `plotter.add_camera_orientation_widget()` (a 2D widget showing camera orientation, but limited). For a true clickable view-cube, wrap `vtk.vtkAxesActor` or build a custom widget using `vtk.vtkAnnotatedCubeActor`. On click of a face, animate the camera to that canonical view over 400 ms via `plotter.fly_to`.
> 2. Click-to-select: use `plotter.enable_picking(callback=on_pick, show_message=False, picker='point')`. The callback resolves the picked actor to a primitive name (boresight / α_t / surface normal / etc.) and pushes it to a `Qt signal active_edit_changed`. Subscribers (the right-panel rows + the highlight overlay) update accordingly.
> 3. Highlight overlay: when an active edit is set, re-stroke the matching primitive at `ACCENT_COLOR`, `ACCENT_LINE_WIDTH`, with an animated dashed pulse via a `QTimer` updating the dash offset every 60 ms. (This is v1's CU-031, finally shipped.)
> 4. Hover tooltips: `plotter.enable_point_picking(callback=on_hover, show_message=False, ...)` triggers a `QToolTip.showText` near the cursor with the primitive's full parametric definition.
> 5. Keyboard shortcuts: register on the `QMainWindow`. `R` calls `plotter.reset_camera()`, `1`–`6` snap to canonical views, `Space` toggles a parameter-sweep animation, `?` opens a help overlay (`QDialog` with a key-binding table).
> 6. Frame switcher: a `QComboBox` in the toolbar with options World / Body / Sensor. On change, the view-model recomputes all vectors in the new frame and `build_scene` re-runs. Animate the transition by interpolating each vector's endpoint over 400 ms.
> 7. Coordinate-frame indicator: top-left overlay reads `Frame: Body  ·  Origin: Target centroid`. Updates on frame switch.
>
> **Acceptance:**
> - Every keyboard shortcut works.
> - Frame switch produces a smooth 400 ms animation, not a hard cut.
> - Click on the boresight tube highlights it in `ACCENT_COLOR`; click elsewhere clears.
> - View-cube faces clickable and navigate to canonical views.

## 14. Phase 6 — App-shell polish + theme (engineer prompt)

> **Goal:** Make this look like a 2026 scientific instrument.
>
> **Steps:**
>
> 1. Apply `qt-material` theme. Default: `dark_teal.xml`. Settings dialog lets the user switch to a light theme (`light_blue.xml`) or follow OS appearance.
> 2. Real menu bar:
>    - File → New scene, Save screenshot, Quit
>    - View → Reset camera, Toggle right panel, Toggle left panel, Toggle view cube
>    - Frame → World, Body, Sensor (mirrors the toolbar combo)
>    - Scene → Toggle each vector / arc / frame triad / background marker (one menu item per primitive, all checkable)
>    - Help → Keyboard shortcuts, About
> 3. Status bar: left side shows `Frame: Body  ·  Origin: Target centroid`; right side shows current regime (`SUB_PIXEL [auto]` etc.) and the projected area `A_t = 12.57 m²`.
> 4. Settings dialog (`QDialog`): Theme dropdown, default frame, display units (km/m, deg/rad), font size, label-density (low / medium / high — controls the leader-label hover-expand behavior). Settings persist via `QSettings`.
> 5. About dialog: product name, version, build date, license, link to RADIANT documentation, credits to PyVista / VTK / Qt.
> 6. Window state persistence: window position, size, dock visibility, splitter ratios, current theme — all saved via `QSettings` and restored on next launch.
> 7. App icon: commission a simple icon (target reticle inside a viewing-frustum frame). Bundle as `.icns` (macOS), `.ico` (Windows), `.png` (Linux).
> 8. Naming (D2 resolved 2026-04-26): this is the **Geometry module** of the larger RADIANT GUI, not a standalone product. Window title: `RADIANT — Geometry`. About dialog leads with `RADIANT Geometry Module`. Console-script entry point (Phase 7) is `radiant-geometry`, not `radiant-vision-studio`. The "Vision Studio" name from earlier drafts is dropped.
> 9. Re-lock golden screenshots for both themes across all 9 canonical views.
>
> **Acceptance:**
> - Show the app to one person on the team who has not seen it before. They cannot tell whether it is a commercial product or an internal tool. (This is the bar.)
> - Theme switch is instant.
> - Window state survives a quit/relaunch.

## 15. Phase 7 — Hardening + handoff package (engineer prompt)

> **Goal:** Production-ready. Performance, memory, docs, packaging.
>
> **Steps:**
>
> 1. Performance pass:
>    - Slider drag must produce ≥60 fps for the default scene. Profile via `cProfile` and `pyinstrument`. Identify and fix the top three hotspots.
>    - The most expensive scene (extended cell + box target + all vectors visible + all labels visible) must produce ≥30 fps.
>    - Where possible, use PyVista actor-update APIs (`actor.GetMapper().GetInput().Modified()`) instead of full scene rebuilds.
> 2. Memory pass: run 100 slider-sweep cycles via a `pytest-qt` script. Track memory with `tracemalloc`. Net allocation after the sweep must be under 5 MB.
> 3. Documentation:
>    - `README.md` with screenshot, install command, run command, architecture diagram, and a glossary table defining every angle and vector (source the glossary from a single YAML file so readout tooltips, the help overlay, and the README all read from one source).
>    - `ARCHITECTURE.md` with the full diagram from section 4 and a paragraph per module.
>    - `CONTRIBUTING.md` with the Rule 19, C7, and golden-screenshot conventions.
> 4. Packaging:
>    - `pyproject.toml` properly declares the package, entry points, and dependencies.
>    - `pip install -e dev_tools/geometry_gui_v2/` works.
>    - Console script entry: `radiant-geometry` launches `app.main:main`.
> 5. CI:
>    - Headless test run via `xvfb-run` on Linux, `pyvistaqt`'s off-screen mode on macOS / Windows.
>    - All golden screenshots regenerate cleanly in CI; diffs flagged.
>    - C1 / C6 / C7 checks enforced in CI.
> 6. Demo: Jason demos the tool to one external stakeholder unfamiliar with RADIANT. Stakeholder must be able to identify every angle and every vector with no help, in under 5 minutes.
>
> **Acceptance:**
> - All performance targets met.
> - All docs present.
> - `pip install -e .` and `radiant-geometry` work on a fresh venv on Linux, macOS, and Windows.
> - External-stakeholder demo succeeds.

## 16. Resolved decisions (closed 2026-04-26)

All six pre-Phase-0 decisions are resolved. Originals preserved for traceability.

| # | Question | Resolution |
|---|---|---|
| D1 | PyQt5 (GPL/Commercial) or PySide6 (LGPL)? | **PySide6.** LGPL avoids commercial-license footgun if RADIANT is shared externally; Qt 6 gives modern HiDPI / Apple Silicon behavior; the historical PyQt5 advantage in `pyvistaqt` has largely closed. |
| D2 | Provisional product name **RADIANT Vision Studio** — accept, modify, or replace? | **Replaced.** This is the Geometry module of the larger RADIANT GUI, not a standalone product. Window title `RADIANT — Geometry`; About dialog `RADIANT Geometry Module`; console entry `radiant-geometry`. The "Vision Studio" naming is dropped. |
| D3 | Target operating systems for the v2 deliverable? | **All three** (Linux + macOS + Windows). CI runs on all three. |
| D4 | Is v1 (`dev_tools/geometry_gui/`) deleted at v2 Phase 6 acceptance, or kept indefinitely as reference? | **Archive.** Move to `dev_tools/_archive/geometry_gui_v1/` at Phase 6 acceptance; do not delete. |
| D5 | Should the scene library be importable by the future production GUI as a separate package? | **Yes.** Scene library structured to lift cleanly into `radiant.gui.scene` later without modification (C7 enforces). |
| D6 | Trame (web-deployable PyVista) — v3 goal or out of scope? | **Deferred** — filed as **CU-033** in `docs/Cleanup_Backlog.md`. Architecture stays compatible at zero cost because the scene library is already Qt-free (C7). |

## 17. Deferred (out-of-v2 scope)

Only CU-033 is filed in `docs/Cleanup_Backlog.md` (per Rule 21, "next available; never reuse" — the speculative CU-100 numbering used in earlier drafts is replaced). The remaining four items are scope-cuts of the v2 plan, tracked here until promoted to the backlog when active work begins.

- **CU-033** — Trame web deployment. The scene library (per C7) is Qt-free, so a parallel `app_web/` shell using `trame` is feasible without touching `scene/`. Effort: B. Category: presentation-only. **Filed in `docs/Cleanup_Backlog.md` 2026-04-26.**
- **(Plan-internal)** Scenario YAML loading. Snap all sliders to a loaded scenario file. Touches `state.py` to add a `from_scenario` classmethod. Effort: A. Category: state. Promote to backlog if/when work starts.
- **(Plan-internal)** Multi-target / constellation views. Architectural change to `SceneState` (one target → list of targets). Effort: C. Category: architecture. Promote to backlog if/when work starts.
- **(Plan-internal)** Session save / load. Serialize `SceneState` to JSON, restore on launch. Effort: A. Category: state. Promote to backlog if/when work starts.
- **(Plan-internal)** Custom shape import (STL / OBJ). PyVista reads both natively, but `radiant.source.shapes` does not yet have an arbitrary-mesh shape class. Effort: C. Category: integration. Promote to backlog if/when work starts.

## 18. What the manager should communicate to the team

This is a rewrite of the rendering and UI layers, not of RADIANT and not of the physics. The team's view-model work from v1 is correct and survives. The team's visual design intent from v1 Phases 8–16 is correct and survives — it is exactly what v2 ships, on a stack that can actually deliver it. The team did not waste their time; they proved out the design against a stack that turned out to be too limiting, which is how you find out a stack is too limiting. v2 takes their design and gives it the renderer it deserves.

The expected timeline is roughly 8 engineer-weeks for one engineer working alone, or 5 engineer-weeks for two engineers pairing on the rendering and the UI shell in parallel. Phases 0, 1, and 2 are the highest risk because they validate the stack choice; if PyVista PBR and screen-space labels do not behave as expected, that surfaces by end of Phase 2. After Phase 2 is green, the remaining phases are execution rather than discovery.

The deliverable at v2 Phase 6 is a tool that, when shown to a stakeholder, looks like a real product. That is the bar, and it is achievable on this stack.
