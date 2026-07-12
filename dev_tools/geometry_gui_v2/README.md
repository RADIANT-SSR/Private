# RADIANT Geometry

PyVista + PySide6 desktop module of the RADIANT GUI — the visual-design
prototype that will lift into the production GUI's geometry tab once
CI / packaging settle.

This is the geometry-only module of a larger RADIANT GUI (decision D2 in
[Geometry_GUI_v2_Plan.md](../../docs/archive/Geometry_GUI_v2_Plan.md) §16); the "Vision Studio" naming
that appeared in early drafts is dropped.

## Quick start

```bash
pip install -e dev_tools/geometry_gui_v2
radiant-geometry      # console-script entry point (Phase 7)
# or:
python -m dev_tools.geometry_gui_v2.app.main
```

The first launch opens the dark-teal qt-material theme. Switch via
**Help → Settings… → Theme**.

## Keyboard shortcuts

| Key      | Action                                      |
| -------- | ------------------------------------------- |
| `R`      | Reset camera                                |
| `1`–`6`  | Snap to canonical view (front / back / left / right / top / bottom) |
| `?`      | Open the keyboard-shortcuts help dialog     |
| `Ctrl+N` | New scene (resets to default `SceneState`)  |
| `Ctrl+S` | Save screenshot                             |
| `Ctrl+Q` | Quit                                        |

## What this tool shows

The right-dock readouts panel reports **every angle and vector the
RADIANT signal chain consumes**, in canonical units, with the literal
`[from shape.projected_area]` handoff tag on the projected-area row so
the user knows where the radiometric chain reads it from. The status
bar's right side mirrors the regime + projected area for visibility
when the dock is hidden.

The viewport renders, in a single canonical frame:

- **Boresight** (`b̂`) with not-to-scale break-mark
- **Surface normal** (`n̂`)
- **Sun rays** to the target (`ŝ_t`) and to the background (`ŝ_B`)
- **Off-nadir angle arc** (`θ_o`)
- **Phase angle arc** (`α_t`)
- **Sun zenith angle arc** (`θ_s`)
- Observer / Sun / Background **glyphs**
- The **target body** with PBR shading

Every primitive is labelled with a force-directed leader line so labels
never overlap. See [glossary.yaml](scene/labels/glossary.yaml) for the parametric
definition of every primitive (the single source of truth that
tooltips, the help overlay, and this README all read from).

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full diagram and the
per-module design. The one-liner: state → view-model → scene library,
each layer a pure function over the previous, with the Qt shell holding
the only mutable state.

## Status

| Phase | Topic                                      | State    |
| ----- | ------------------------------------------ | -------- |
| 0     | Scaffold + salvage from v1                 | Shipped  |
| 1     | Scene library skeleton                     | Shipped  |
| 2     | PBR target rendering + lighting            | Shipped  |
| 3     | Vectors / arcs / glyphs polish             | Shipped  |
| 4     | Force-directed labels + readouts panel     | Shipped  |
| 5     | Interaction (keyboard, picking, frame switcher) | Shipped  |
| 6     | App-shell polish (theme, menu, dialogs, persistence) | Shipped  |
| 7     | Hardening + handoff (this PR)              | In progress |

Phase-7 deferrals are tracked in
[../../docs/tracking/Cleanup_Backlog.md](../../docs/tracking/Cleanup_Backlog.md):
performance pass (CU-053), memory pass (CU-054), CI integration
(CU-055), and the headlining slider work (CU-052) that unblocks the
performance / memory tests.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the Rule 19 (one-computation-
one-module) convention, the C7 constraint (scene library is Qt-free),
and the golden-screenshot review protocol.
