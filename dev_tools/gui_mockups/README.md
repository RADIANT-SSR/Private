# GUI Mockups — notional design sketches

**Status:** Working sketches / exploratory. **Not** shipped code, **not** a spec.

This folder holds pre-implementation design artifacts for a notional RADIANT GUI,
produced with Claude's design tooling. They are here as a reference for what the
interface could look like — snapshots of an exploration, not a contract. Nothing
in this folder is imported by `src/radiant/`, tested, or bound by the lock-step
doc rule (Rule 20). The normative GUI spec, when it exists, lives in
`docs/architecture/` under a DEFERRED banner (see `RADIANT_GUI_Architecture.md`).

These are static HTML/JSX mockups meant to be opened in a browser or read as
source — they are not wired to the RADIANT chain.

> **Note (2026-07-12):** these mockups predate the geometry-first chain
> (ADR-0006) — they open at the Source screen. The next design iteration
> adds a **Geometry** screen ahead of Source (scene setup: sensor / target /
> sun, input-mode picker per `docs/architecture/RADIANT_Geometry.md`), and
> the stage strip becomes 9 stages.

## Contents

### `radiant_ui/` — full-application mockup
Mid-fidelity HTML mockups of the main workspace, per-stage screens (source →
performance), and the scripting/command window.

- `radiant_mid_fi.html`, `radiant_wireframes.html`, `radiant_screens.html`,
  `radiant_stage_screens.html`, `radiant_source_stage.html`,
  `radiant_scripting.html` — open in a browser.
- `radiant_screens.pdf` — exported screen set.
- `pdf_shots/` — per-stage PNG renders (`00-workspace` … `08-scripting`).
- `uploads/` — the architecture/context docs that were fed to the design tool as
  input (copies of `RADIANT_Master_Architecture.md`, the GUI architecture draft,
  and the target/use-case matrices). Reference copies only — the live versions
  live in `docs/architecture/`.

### `geometry_viewer/` — 3D imaging-geometry viewer sketch
A React/JSX sketch of an interactive satellite/target/sun geometry viewer. Related
in intent to the working `dev_tools/geometry_gui_v2/` tool, but a separate
design exploration.

- `radiant_geometry_viewer.html` — standalone rendered mockup.
- `app.jsx`, `scene.jsx`, `shapes.jsx`, `tweaks_panel.jsx`, `geometry.js` —
  component source for the sketch.
- `radiant_geometry_handoff.md` — the design handoff notes.
- `uploads/` — reference renders (regimes, target primitives).

## Provenance

Imported 2026-07-12 from Claude design exports (`~/Downloads/RADIANT` and
`~/Downloads/Radient Geometry Viewer`). Filenames were normalized (spaces removed,
lowercased) to satisfy `scripts/check_org_rules.py`; content is unchanged.
