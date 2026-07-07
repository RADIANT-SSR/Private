# RADIANT Geometry — Architecture

The Geometry module of the RADIANT GUI is a three-layer desktop
application: **state → view-model → scene library**. Each layer is a
pure function over the layer above. The Qt shell holds the only mutable
state.

## High-level diagram

```
┌────────────────────────────────────────────────────────────────────┐
│  PySide6 desktop shell  (app/main.py)                              │
│   ─ menu bar (File / View / Frame / Scene / Help)                  │
│   ─ status bar (frame indicator | regime + projected area)         │
│   ─ left dock: parameter panel (sliders deferred — CU-052)         │
│   ─ center: PyVistaQt QtInteractor (the 3D viewport)               │
│   ─ right dock: ReadoutsPanel (objects / vectors / angles / regime)│
│   ─ overlays: view-cube, frame-indicator HUD                       │
│   ─ dialogs: Settings, About, Keyboard shortcuts                   │
│   ─ persistence: QSettings (theme, default frame, dock layout)     │
└────────────────────┬───────────────────────────────────────────────┘
                     │  parameter changes (Qt signals)
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│  app/state.py    — SceneState dataclass (frozen, hashable)         │
│  app/interaction_state.py                                          │
│                  — InteractionState (display_frame, active_edit,   │
│                    last_canonical_view; UI cursor, not physics)    │
└────────────────────┬───────────────────────────────────────────────┘
                     │  build()
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│  app/view_model.py  — pure functions, no UI, no rendering          │
│   ─ build_observer_geometry()                                      │
│   ─ build_target_shape()                                           │
│   ─ classify_regime()                                              │
│   ─ projected_area_m2()  ← calls shape.projected_area(...)         │
│   ─ derived_readout()  → dict of native-unit values                │
│   ─ format_readout()  → dict of formatted, unit-stamped strings    │
│  Imports ONLY from radiant.core.* and radiant.source.shapes        │
│  (Lifted from v1 with minimal changes — the reuse point.)          │
└────────────────────┬───────────────────────────────────────────────┘
                     │  view-model output
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│  scene/  ─ standalone PyVista scene library (the deliverable)      │
│   ─ scene/builder.py        — orchestrator: state → pv.Plotter     │
│   ─ scene/target/           — one file per shape (Rule 19)         │
│   ─ scene/vectors/          — boresight, normal, sun, sun-to-bg    │
│   ─ scene/glyphs/           — observer, sun, background point      │
│   ─ scene/labels/           — leader-line + force-directed layout  │
│   ─ scene/frames/           — body axes, world axes                │
│   ─ scene/ground/           — ground cap, contact shadow, grid     │
│   ─ scene/arcs/             — angle arcs (off-nadir, α_t, θ_s)     │
│   ─ scene/style.py          — palette, line widths, glyph sizes,   │
│                                lighting (single source of truth)   │
│   ─ scene/highlight.py      — active-edit re-stroke registry       │
│   ─ scene/camera_views.py   — canonical-view camera poses          │
│   No Qt imports. No app-shell imports. (See C7.)                   │
└────────────────────────────────────────────────────────────────────┘
```

Data flow is one-way: state → view-model → scene. No mutation. The Qt
shell holds the only mutable state (the `SceneState` held in a single
Qt model object); every parameter change rebuilds an immutable
`SceneState`, runs it through the view-model, and refreshes the scene.
Phase 7's CU-053 promotes incremental actor-update over full rebuild
once sliders land; today every change is a `clear_actors` + `build_scene`.

## Module-by-module summary

### `app/`

| Module | Purpose |
| ------ | ------- |
| `main.py` | `GeometryMainWindow` — assembles the docks, menu bar, status bar, dialogs, keyboard shortcuts, picking, and persistence wiring. Sole `QtInteractor` owner. |
| `state.py` | `SceneState` frozen dataclass — one field per slider. Pure data, no methods beyond `default()`. |
| `interaction_state.py` | `DisplayFrame` enum (World / Body / Sensor), `CanonicalView` enum (front / back / left / right / top / bottom / iso), `InteractionState` frozen dataclass for UI cursor state, plus the 1–6 → CanonicalView keymap. |
| `view_model.py` | Pure-function bridge from `SceneState` to view-model output: observer geometry, target shape, regime classification, projected area, and the formatted readout dict. The C3 invariant lives here: `projected_area_m2(state) == state.target.projected_area`. |
| `theme.py` | qt-material theme registry + `apply_theme(app, theme_xml)` applicator. Three themes (dark teal, light blue, follow OS). |
| `status_bar_text.py` | Pure formatter: `status_bar_right_text(state) -> "REGIME [auto] · A_t = ... m²"`. |
| `window_persistence.py` | `QSettings` wrapper — window geometry / dock state / theme / default frame. Single owner of every persisted key under `RADIANT/Geometry`. |
| `panels/readouts.py` | `ReadoutsPanel(QWidget)` — five collapsible sections (Scene objects / Vectors / Angles / Regime / Multi-facet decomposition); monospace, right-aligned, every numeric row carries its unit. |
| `dialogs/about.py` | About dialog — product name, version, license, attribution. |
| `dialogs/settings.py` | Settings dialog — Theme + Default-frame dropdowns. (Units / font / label-density deferred per CU-040.) |
| `dialogs/shortcuts.py` | Keyboard-shortcuts help dialog — single source of truth (`SHORTCUT_BINDINGS`). |

### `scene/` (Qt-free per C7)

| Module | Purpose |
| ------ | ------- |
| `builder.py` | The orchestrator: walks the per-primitive packages in the documented order (ground → target → frames → vectors → arcs → glyphs → labels) and calls each `add_to_plotter`. |
| `style.py` | Single source of truth for every color, line width, glyph size, and PBR parameter. Six-tier saliency hierarchy (Phase 16 v1 design). |
| `_lighting.py` | Sun light + ambient fill light installed on the plotter. Sun direction comes from `SceneState.solar_zenith_rad` + `relative_azimuth_rad`. |
| `highlight.py` | Active-edit primitive → constituent-actors registry; `apply_highlight(plotter, name)` re-strokes in `ACCENT_COLOR`. |
| `camera_views.py` | `camera_pose_for(view)` returning `(position, focal, up)` for each of the seven canonical views. |
| `target/` | One file per shape (`sphere.py`, `cylinder.py`, `cone.py`, `box.py`, `flat_plate.py`) per Rule 19. |
| `vectors/` | One file per vector (`boresight.py`, `surface_normal.py`, `sun_ray.py`, `sun_to_background.py`) plus `_vector.py` (the not-to-scale arrow + break-mark helper). |
| `arcs/` | One file per arc (`off_nadir.py`, `phase_angle.py`, `sun_zenith.py`) plus `_arc.py` (great-arc + tip-cone helper). |
| `glyphs/` | One file per glyph (`observer.py`, `sun.py`, `background.py`). |
| `labels/` | `_anchors.py` (anchor collector), `layout.py` (force-directed layout solver), `leader_label.py` (per-label `vtkTextActor` + `vtkLeaderActor2D`), `__init__.py` (orchestrator that projects → solves → places). |
| `frames/` | Body axes + world axes triads. |
| `ground/` | Ground cap, contact shadow, grid. |

### `tests/`

`test_*_phase{N}.py` for each phase landing; pure-Python tests run
without a display, Qt-required tests use `QT_QPA_PLATFORM=offscreen`,
and full `QtInteractor`-bearing tests gate behind
`RADIANT_GUI_FULL_WINDOW_TESTS=1` because offscreen-GL contexts segfault
on some platforms during widget construction.

## Hard constraints (C1–C8 from docs/plans/Geometry_GUI_v2_Plan.md §3)

- **C1**: this rewrite must not edit `src/`. RADIANT physics is the load-
  bearing layer; the GUI consumes it.
- **C5**: Rule 19 — every primitive (vector / arc / glyph / shape) gets
  its own file. Bundling shape rendering into one file is a v1 anti-
  pattern that the audit found.
- **C6**: no `from radiant._private` imports. The GUI consumes only
  `radiant.core.*` and `radiant.source.shapes` (the lifted-into-public
  shape API).
- **C7**: the `scene/` library imports nothing from Qt. This is enforced
  by `tests/test_scene_imports_without_qt.py`. The contract guarantees
  the scene library can lift cleanly into `radiant.gui.scene` later
  (decision D5) and supports a future Trame web shell (CU-033) at zero
  refactor cost.
- **C8**: every Phase 1+ rendered scene has a golden screenshot pinned
  in `tests/golden_phase{N}/`. Phase 6 onward also covers themed views;
  the theme × view matrix re-lock is deferred under CU-042.

## Future production-GUI lift

Decision D5 (docs/plans/Geometry_GUI_v2_Plan.md §16) commits to lifting `scene/` cleanly into
`radiant.gui.scene` once the production GUI lands. The package layout
is structured for that lift:

- `dev_tools/geometry_gui_v2/scene/` ⇒ `src/radiant/gui/scene/`
- `dev_tools/geometry_gui_v2/app/` stays in `dev_tools/` as the
  prototype shell; the production GUI builds its own `radiant.gui.app/`
  shell against the lifted `scene/` library.

C7 enforces that this lift is mechanical (no `from PySide6` imports
under `scene/` to chase).
