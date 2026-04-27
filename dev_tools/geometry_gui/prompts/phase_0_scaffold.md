# Phase 0 — Scaffold

**Category:** A (Pure infrastructure)
**Estimated effort:** 30 min
**Pre-reads:** `dev_tools/geometry_gui/PLAN.md`, `CLAUDE.md` §"Hard rules"

## Hard constraint
**Do not edit anything under `/src/`.** This phase only creates files under
`dev_tools/geometry_gui/`. If you find yourself wanting to change `/src`, stop and report.

## Goal
Stand up an empty, importable Python package and an empty Dash app. No physics yet.

## Tasks
1. Create the package skeleton:
   ```
   dev_tools/geometry_gui/
     app/__init__.py
     app/main.py
     tests/__init__.py
     tests/test_smoke.py
     requirements.txt
   ```
2. `requirements.txt`: pin `dash`, `plotly`, `numpy`. Use the same numpy version range as `pyproject.toml`.
3. `app/main.py`: a Dash app with a placeholder `dcc.Graph(id="scene")` and no callbacks.
   `if __name__ == "__main__": app.run(debug=True, port=8050)`. Use `app.run`, not the deprecated
   `app.run_server`.
4. `tests/test_smoke.py`: assert that
   - `from radiant.core.geometry import ObserverGeometry, SceneGeometry, TargetGeometry` succeeds
   - `from radiant.source.shapes.sphere import Sphere` succeeds (or whatever the actual
     module path is — verify with `python -c` first; do not invent paths)
   - `from dev_tools.geometry_gui.app.main import app` succeeds
5. Run `pytest dev_tools/geometry_gui/tests/ -v` — all green.

## Forbidden
- Adding any physics, geometry math, or plotly figure content. Phase 1 owns the view-model;
  Phase 2 owns scene meshes. This phase is just plumbing.
- Importing from `radiant` private modules (anything `_underscored`).

## Report (Category A)
- Files created (list).
- `pytest` output.
- One sentence confirming `python -m dev_tools.geometry_gui.app.main` opens a blank Dash page
  on `localhost:8050`.
