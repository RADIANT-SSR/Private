# GUI Development Plan — RADIANT Desktop GUI v1

**Status:** Draft (becomes Active on owner ratification)
**Date:** 2026-07-12
**Owner decisions record:** §2 (ratified by owner 2026-07-12 in plan-scoping session)
**Depends on:** `docs/plans/Geometry_Stage_Plan.md` (must be Complete and archived before
Phase 1 of this plan starts), `docs/architecture/RADIANT_GUI_Architecture.md`
**Executes as:** one phase = one agent task = one conversation (per CLAUDE.md task discipline)

---

## 1. Goal

Ship RADIANT GUI v1: a PySide6 desktop application that is a *view over the scripting
API* — every GUI action maps to exactly one `Sensor` / `ChainResult` call, no physics in
GUI code. v1 delivers the core evaluate loop (open YAML → edit parameters → evaluate →
metrics + plots), the geometry-first workflow (stage-0 forms + 3D schematic viewer), the
per-stage detail tabs, and the embedded scripting console.

The plan is deliberately incremental: **every phase ends with something the owner can
launch and click**, followed by a feedback round before the next phase starts. The owner
is not a software developer; acceptance is by using the app, not by reading code.

---

## 2. Ratified Decisions (owner, 2026-07-12)

These four decisions were put to the owner explicitly and are binding for v1:

| # | Decision | Ruling |
|---|----------|--------|
| D1 | Technology | **PySide6 / Qt6 native**, confirming the 2026-04-07 architecture decision. The HTML/React mockups in `dev_tools/gui_mockups/` are the *visual spec*, ported to Qt — not the implementation medium. |
| D2 | First runnable milestone | **Evaluate loop first**: open YAML → parameter tree → Evaluate → metric badges + plot, end-to-end, before any other panel is built out. |
| D3 | Geometry stage-0 dependency | **Wait for stage 0.** No GUI *implementation* (Phase 1+) starts until the Geometry_Stage_Plan is complete and merged. Phase 0 (doc-only spec work) may run before that. |
| D4 | v1 must-haves beyond the core | **3D geometry viewer** and **scripting console** are in v1. **Sweep tab** and **Batch / Monte Carlo dialogs** are deferred to v1.1 (they remain in the architecture doc's layout as disabled/absent tabs; the backend already supports them via script). |

---

## 3. Scope

### In scope (v1)

1. Application shell: main window, menus, stage strip (9 stages, geometry first),
   dockable parameter panel, central plot canvas, tabbed detail panel, status bar.
2. Schema-driven parameter panel generated from `Sensor.parameter_defs()` — never a
   transcribed parameter list (Gap 70 lesson; see arch-doc reconciliation banner).
3. Evaluate loop: background-thread `sensor.evaluate()`, metric badges, actionable
   error dialogs (`RadiantError` what/why/action), debounced re-evaluation.
4. Detail tabs: Spectral, MTF, Noise Budget, Variable Explorer, YAML.
5. Geometry screen: input-mode forms bound to the stage-0 `geometry.*` schema, with
   live derived-angle readout from `stage_outputs["geometry"]`.
6. 3D geometry viewer: the not-to-scale schematic from
   `dev_tools/gui_mockups/geometry_viewer/` (sun/sensor/target glyphs, vectors,
   click-to-reveal angle annotations, target shape library).
7. Scripting console: embedded IPython with live `sensor` / `result` objects
   (the MATLAB-style command window).
8. File round-trip: Open/Save/Recent YAML via `Sensor.load()` / `sensor.save()`;
   undo/redo of parameter edits.

### Out of scope (v1) — do not implement, even partially

- Sweep tab UI, Batch / Monte Carlo dialogs (v1.1 — D4).
- Everything in arch-doc §7 "Deferred to Phase 2" (image simulator, library browser,
  report generator, comparison mode, plugin UI, remote compute).
- PyInstaller / standalone-binary packaging (v1.x; v1 runs from the repo venv).
- Incremental / stale-DAG re-evaluation (DECLINED for v1, CU-079 — full re-runs only).
- Any change to physics, schemas, or golden results. The GUI is results-neutral by
  construction; a golden-test diff in any GUI PR is a defect.

---

## 4. Architecture Ground Rules (binding on every phase)

1. **Backend is the scripting API** (arch doc §3.1). One GUI action ↔ one API call.
   If the API lacks a hook the GUI needs, the phase *stops* and files the gap in
   `docs/tracking/gaps.md` — GUI code never reaches into stage internals or
   re-implements a computation.
2. **Package location:** `src/radiant/gui/`. Layout:

   ```
   src/radiant/gui/
   ├── __init__.py        # launch_gui(sensor: Sensor | None) entry
   ├── app.py             # QApplication bootstrap
   ├── main_window.py     # RADIANTMainWindow(QMainWindow)
   ├── widgets/           # one widget class per file (Rule 19 spirit)
   ├── workers.py         # QThread evaluation worker
   ├── themes/            # QSS stylesheets (dark default, light)
   └── tests/             # pytest-qt tests
   ```

3. **Import rules amendment** (lands in Phase 1, in lock-step with docs — Rule 20):
   `gui/` may import `radiant.api` + `radiant.core` (+ PySide6, matplotlib, qtconsole);
   `cli/` gains `radiant.gui` (for the `radiant gui` subcommand, imported lazily so the
   CLI works without the gui extra installed). No physics stage may import `gui`, and
   `gui` may not import any physics stage directly. Update: import-linter contracts in
   `pyproject.toml`, the import table in `CLAUDE.md`, and
   `docs/architecture/RADIANT_File_Tree.md` — same PR.
4. **Dependencies:** new optional group in `pyproject.toml`:
   `gui = ["PySide6>=6.6", "matplotlib>=3.8", "qtconsole>=5.5"]` (exact pins set in
   Phase 1). Core RADIANT must remain importable and fully functional without the
   `gui` extra.
5. **Threading:** Qt main thread never runs the chain. Evaluations run in a worker
   `QThread`; results delivered by signal. Note the arch doc's `EvaluationWorker`
   sketch shows an `on_stage_complete` callback that `Sensor.evaluate()` does **not**
   have — full-chain evaluation is ~0.22 s, so the worker emits only
   started/finished/failed, and the status bar shows a busy indicator. Per-point
   `progress`/cancel callbacks exist on `sweep()`/`sweep_2d()` (Gap 72) for v1.1.
6. **Units on every displayed value — no exceptions.** Every numeric shown anywhere in
   the GUI (badge, table cell, tooltip, axis, readout) carries its unit, sourced from
   the `ParameterDef` / result metadata, never hardcoded. This is an owner hard rule
   and an acceptance criterion for every phase.
7. **Errors are shown, never swallowed** (Rules 15/17). `RadiantError` → modal dialog
   rendering what/why/action/context verbatim. Unexpected exceptions → error dialog
   with traceback in a details fold. No `except Exception: pass` anywhere in gui code.
8. **Code standards:** type hints on every function (Rule 1); `ruff` clean; no
   `print()` (Rule 14). mypy: gui code is type-hinted to `--strict` intent, but the
   enforced `mypy --strict` gate stays scoped to `core`/`api` unless Phase 1 finds Qt
   stubs clean enough to add `gui` — Phase 1 decides and records the decision in its
   report and in `CLAUDE.md` if changed.
9. **Testing:** `pytest-qt` (`qtbot`), headless via `QT_QPA_PLATFORM=offscreen`.
   Every menu/toolbar action added in a phase gets a programmatic trigger test (arch
   doc §8). GUI tests live in `src/radiant/gui/tests/` and run with
   `pytest src/radiant/gui/tests/ -v`. When a task touches only `gui/`, run the gui
   test suite plus one fast full-chain smoke — not the whole repo suite.
10. **Rule 29 changelog:** each phase that adds user-observable capability (all of
    them from Phase 1 on) adds a `CHANGELOG.md` entry under `[Unreleased]` —
    capability additions, never results-affecting.

---

## 5. Iteration Protocol (how the owner tests along the way)

Every phase ends with a **Checkpoint** — a section in the task report containing:

1. **Launch command** (e.g. `pip install -e ".[gui]" && radiant gui examples/leo_mwir.yaml`).
2. **Click script** — a numbered list of exactly what to do in the UI.
3. **Expected observations** — what each step should show, with units.
4. **Known-incomplete list** — what is intentionally stubbed, so the owner doesn't
   file feedback on planned gaps.

The owner runs the checkpoint and replies with feedback. Feedback items become a
**punch-list task** (its own conversation, Category A) that must close before the next
phase starts. This is the iterate-as-we-go loop; do not batch feedback across phases.

---

## 6. Phases

Effort key: S ≈ one short session, M ≈ one full session, L ≈ may need a split into two
tasks (split point named in the phase).

### Phase 0 — v1 Specification & Requirements Harvest
**Gate:** none — may run before the geometry stage merges (doc-only, D3-compatible).
**Category:** A · **Effort:** M
**Read first:** `docs/architecture/RADIANT_GUI_Architecture.md`,
`dev_tools/gui_mockups/README.md`, `dev_tools/gui_mockups/geometry_viewer/radiant_geometry_handoff.md`,
`docs/plans/Geometry_Stage_Plan.md`, `docs/architecture/RADIANT_Personas.md`

Tasks:
1. Read all 37 `scenarios/**/gui_workflow.md` files. Produce a requirements matrix:
   workflow → GUI feature it needs → v1 phase that delivers it (or "v1.1/deferred").
   The matrix becomes a new section of `RADIANT_GUI_Architecture.md`.
2. Revise `RADIANT_GUI_Architecture.md` from "DESIGN TARGET" to the ratified v1 spec:
   - Record decisions D1–D4 (§2 above) and the v1 scope split (§3 above).
   - Add **Geometry** as the first stage in the chain strip and layout diagrams
     (9 stages), aligned with the Geometry_Stage_Plan target architecture.
   - Fold the 2026-07-12 reconciliation banner into the body: delete the <100 ms /
     incremental-DAG contract text (CU-079, declined), fix the `EvaluationWorker`
     sketch to the real `evaluate()` signature, mark sweep/MC panels v1.1.
   - Add the geometry viewer panel spec, condensed from the handoff doc, including
     the not-to-scale rule (altitudes shown via leader labels, geometry never
     translated to fake scale — owner-endorsed convention from `geometry_gui_v2`).
3. File CUs (Rule 21) for anything found contradictory between mockups, arch doc, and
   shipped API during the harvest.

Exit criteria: revised arch doc merged; requirements matrix complete; no code.
Checkpoint: owner reads the revised doc's v1 scope + matrix and confirms.

### Phase 1 — Scaffold, Shell, and Test Harness
**Gate:** Geometry_Stage_Plan Complete and archived (D3). Verify before starting; if
not merged, stop and report.
**Category:** A · **Effort:** M
**Read first:** revised `RADIANT_GUI_Architecture.md` §§1–2, 8; `CLAUDE.md` import rules

Tasks:
1. `pyproject.toml`: add the `gui` optional-dependency group; pin versions.
2. Create `src/radiant/gui/` skeleton (§4.2), `RADIANTMainWindow` with: menu bar
   (File/Edit/View/Run/Tools/Help — actions present, unimplemented ones disabled),
   empty stage strip placeholder, empty dock panels, status bar.
3. `radiant gui [CONFIG.yaml]` CLI subcommand (lazy import; actionable error naming
   the `pip install "radiant[gui]"` remedy if PySide6 is missing).
4. Import-linter contracts + `CLAUDE.md` import table + `RADIANT_File_Tree.md` updated
   in the same PR (Rule 20).
5. pytest-qt harness: offscreen fixture, window-opens smoke test, menu-action trigger
   test pattern established. Decide and record the mypy scoping question (§4.8).
6. `CHANGELOG.md`: `radiant gui` entry point added (Rule 29b).

Checkpoint: `radiant gui` opens an empty themed window with menus; closing it exits
cleanly. Trivial to click through — the point is the toolchain works on the owner's Mac.

### Phase 2 — Parameter Panel
**Category:** A · **Effort:** L (split point: read-only tree lands first, editing second)
**Read first:** `docs/architecture/RADIANT_Parameter_System.md`, arch doc §2.3,
`api/sensor.py` (`parameter_defs`, `set`, `explain`)

Tasks:
1. Tree built **entirely** from `Sensor.parameter_defs()` grouped by dot-path
   namespace — geometry group first, matching chain order. No transcribed names.
2. Rows show value + unit suffix from the schema; derived parameters ⚡-badged and
   read-only; provenance badge (user-set / default / derived) from the resolved set.
3. Editing calls `sensor.set(dotpath, value)`; `ParameterBoundsError` /
   `UnknownParameterError` / consistency-group violations render what/why/action
   inline on the row and in a dialog; the rejected value never sticks.
4. Search box filtering (substring across dot-paths), right-click menu: Copy dot-path,
   Explain (renders `sensor.explain(dotpath)`), Reset to Default.
5. Tests: tree matches schema exactly (generated, both directions); edit-accept,
   edit-reject, search, enum/choice parameters render as combo boxes.

Checkpoint: open an example YAML, browse every stage's parameters, edit a value out of
bounds and read the actionable error, search "temp", explain a parameter.

### Phase 3 — Evaluate Loop  ← **Milestone A (D2)**
**Category:** D · **Effort:** M
**Read first:** arch doc §§2.4, 3.2–3.4 (as revised); `api/_progress.py`;
`api/plot.py`; `docs/architecture/RADIANT_Signal_Chain_Architecture.md` (ChainResult surface)

Tasks:
1. Worker `QThread` wrapping `sensor.evaluate()`; busy state in status bar; Run →
   Evaluate (F5) menu action wired.
2. Metric badge row above the canvas: SNR, NEDT, NIIRS, GSD, MTF@Nyquist — values
   with units, sourced from `ChainResult` (including result-typed metric failures,
   Rule 17 carve-out: a failed metric badge shows the `failure_reason`, not a blank).
3. Central matplotlib canvas (`FigureCanvasQTAgg`) rendering the existing
   `result.plot.*` figures — no plotting logic reimplemented in gui code.
4. Auto re-evaluate on parameter edit, debounced 200 ms, full chain (no incremental
   engine — CU-079). A failed evaluation leaves the previous result displayed with a
   visible "stale — last evaluation failed" state.
5. Integration tests: edit→evaluate→badges-update round trip offscreen; error dialog
   on an invalid config; golden suite untouched (Category D regression statement).

Checkpoint: the D2 milestone — open YAML, change aperture diameter, watch SNR/NEDT
badges and the plot update; enter a bad value and read the error. **This checkpoint is
the plan's main go/no-go review; expect a substantial feedback punch-list.**

### Phase 4 — Stage Strip and Detail Tabs
**Category:** A · **Effort:** L (split point: stage strip + per-stage visualizations
first; detail tabs second)
**Read first:** arch doc §§2.2, 2.5, 5.1, 5.2, 5.4; `api/inspect.py`

Tasks:
1. Stage strip: 9 clickable stages (Geometry → … → Performance), health dots
   (gray = stale, green = evaluated, yellow = warnings present, red = stage raised);
   click scrolls the parameter panel to that namespace and swaps the canvas to the
   stage's default visualization (arch doc §2.4 table, plus geometry: angle summary).
2. Detail tabs (each tab widget its own file): Spectral, MTF (per-term table +
   overlay plot), Noise Budget (table + bars + per-term explain), Variable Explorer
   (`result.inspect()` as a collapsible tree), YAML (read-only current config with
   provenance coloring + Export button). **No Sweep tab, no Console tab yet.**
3. Tests: strip health transitions; each tab populates from a canned result; every
   number rendered with a unit (assert on the formatting helper, used everywhere).

Checkpoint: click each stage, see its visualization; walk each tab after an evaluate;
click a noise term and read its explanation.

### Phase 5 — Geometry Screen (stage-0 forms)
**Category:** A · **Effort:** M
**Read first:** `docs/architecture/` geometry-stage doc (as landed by the
Geometry_Stage_Plan), ADR-0006, `geometry/_schema.py` as merged

Tasks:
1. Geometry gets a dedicated screen (selected via the Geometry stage-strip button):
   an input-mode selector matching the stage-0 modes, with only the active mode's
   fields editable; all fields schema-driven.
2. Live derived-angle readout panel from `stage_outputs["geometry"]` after each
   evaluate: target-frame and ground-frame angle sets, all with units and symbols
   matching the geometry doc.
3. Over-/under-specification errors from the stage render with the mode selector
   highlighted (these are the stage's actionable errors, not GUI-invented checks).
4. Tests: each input mode round-trips; conflicting-mode error surfaces; readout
   matches `stage_outputs["geometry"]` values exactly.

Checkpoint: define a scenario geometry three different ways (e.g. angles-direct,
orbit-derived, sun-from-date/time as available), watch derived angles agree.

### Phase 6 — 3D Viewer Technology Spike
**Category:** A · **Effort:** S — timeboxed; produces an ADR, minimal throwaway code
**Read first:** `radiant_geometry_handoff.md`, `dev_tools/gui_mockups/geometry_viewer/geometry.js`,
`dev_tools/geometry_gui_v2/ARCHITECTURE.md` (the working matplotlib-based tool)

Compare, with a small prototype each, for the schematic viewer inside the Qt app:
(a) `pyqtgraph.opengl.GLViewWidget`, (b) `QWebEngineView` embedding the existing JSX
viewer with a QWebChannel bridge, (c) reusing the `geometry_gui_v2` matplotlib
approach embedded in Qt. Criteria: orbit/pan/zoom feel, click-to-select angle arcs,
text labeling quality, dependency weight, restricted-network friendliness. Decision
recorded as `docs/adr/ADR-XXXX` (next number) — owner ratifies before Phase 7.

### Phase 7 — 3D Geometry Viewer
**Category:** D · **Effort:** L (split point: static scene + vectors first;
click-to-reveal angles + shape library second)
**Read first:** the Phase 6 ADR; handoff doc §§2, 4; geometry-stage doc

Tasks:
1. Implement the schematic viewer per the handoff spec: sun/sensor/target glyphs,
   the four vectors, ground illumination point, target shape library, RPY triad.
2. **The stage is the single source of angle truth.** The viewer renders angles taken
   from `stage_outputs["geometry"]`; the ported `geometry.js` math is used only for
   camera/projection/picking. A consistency test asserts viewer-local recomputation
   agrees with stage outputs (tolerance explicit) — divergence is a red build.
3. Not-to-scale convention: altitudes annotated via leader labels; geometry never
   rescaled or translated to fake proportionality (owner-endorsed rule).
4. Click-to-reveal angle annotations with the target-frame / ground-frame split;
   accordion side panel with live numeric readout (shares widgets with Phase 5).

Checkpoint: rotate/zoom the scene, click through each angle annotation, switch target
shapes, tilt the target with RPY and watch the triad + angles respond.

### Phase 8 — Scripting Console
**Category:** D · **Effort:** M
**Read first:** arch doc §§2.5 (Console row), 4.4; qtconsole embedding docs

Tasks:
1. Console tab: embedded IPython (`qtconsole` in-process kernel) with live `sensor`
   and `result` bound; `result.plot.*` figures render inline or route to the main
   canvas (pick one behavior in-phase, document it).
2. GUI/console coherence: console mutations don't silently desync panels — after any
   console command completes, the GUI marks state stale and offers one-click Refresh
   (explicit and honest beats magic sync; keep it simple).
3. Tests: kernel starts/stops cleanly offscreen; `sensor.set` from console followed
   by Refresh updates the parameter panel; app exit with a busy console is clean.

Checkpoint: the MATLAB-style loop — query `result.inspect()`, run
`sensor.set(...)`, re-evaluate from the console, plot a spectral frame, Refresh.

### Phase 9 — File Round-Trip, Undo/Redo, Polish, Closeout
**Category:** D · **Effort:** M
**Read first:** arch doc §§4.1–4.3, 6; `docs/architecture/RADIANT_Config_Format.md` §1.7

Tasks:
1. File menu complete: New, Open, Open Recent (persisted via `QSettings`), Save,
   Save As — all through `Sensor.load()` / `sensor.save()`; window title shows the
   file and a dirty marker.
2. Undo/redo: `QUndoStack` wrapping `sensor.set()` (named commands, 20 levels).
3. View menu: panel show/hide, stage jump shortcuts, light/dark theme toggle.
4. Full pass of the Phase 0 requirements matrix: every v1 row demonstrably works or
   is re-dispositioned with the owner. Every deferred item lands in
   `docs/tracking/gaps.md` as a tracked gap (sweep tab, batch/MC, packaging, etc.).
5. Closeout (Rules 22/24/29): CHANGELOG entry for v1 GUI capability; arch doc final
   reconciliation; **this plan moves to `docs/archive/` in the completing PR.**

Checkpoint: full acceptance walkthrough — the owner drives one complete scenario from
the requirements matrix end-to-end (geometry → parameters → evaluate → tabs → console
→ save, reopen, confirm identical state).

---

## 7. Phase-Task Prompt Template

Each phase is dispatched to an agent with this preamble (per CLAUDE.md discipline):

```
Task: GUI Development Plan — Phase N: <title>
Category: <A|D>   (validation requirements per CLAUDE.md)
Read first: docs/plans/GUI_Development_Plan.md §4 (ground rules) and §6 Phase N;
            the phase's own "Read first" list.
Scope: exactly the numbered tasks of Phase N. No other phases' work, no
       unrequested features. GUI code must not alter any computed result.
Gate check: confirm the phase's Gate condition holds before writing code;
            if it does not, stop and report.
Done means: phase tests pass (pytest src/radiant/gui/tests/ -v, offscreen) plus one
            fast full-chain smoke; ruff clean; import-linter clean;
            structured report with the Checkpoint section (§5).
```

Punch-list tasks (owner feedback after a checkpoint) use the same template with
Category A and the feedback list as the numbered scope.

---

## 8. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Geometry stage-0 surface shifts after Phase 5/7 are built | Phases 5/7 bind only to `geometry/_schema.py` and `stage_outputs["geometry"]` — the stage plan's published contract. Schema-driven forms absorb renames; the consistency test in Phase 7 catches silent angle drift. |
| Qt/PySide6 friction on macOS (theming, retina, offscreen tests) | Phase 1 exists to burn this down before any feature work; harness problems surface at the cheapest point. |
| 3D viewer becomes a tar pit | Timeboxed spike (Phase 6) with owner-ratified ADR before implementation; the handoff doc's phase-2 polish list (earth curvature, presets, rulers) stays out of v1. |
| qtconsole in-process kernel instability | Phase 8 is late and self-contained; if qtconsole proves fragile, fallback is a plain REPL widget over `code.InteractiveConsole` — decided in-phase, recorded as a CU if the vision item degrades. |
| GUI drifts from arch doc (Rule 20 exposure) | Phase 0 makes the arch doc match reality *first*; every later phase that changes a documented surface updates the doc in the same PR. |
| Scope creep via mockup fidelity | Mockups are visual spec, not contract (their README says so). Fidelity questions during a phase go to the owner as checkpoint feedback, not silent implementation. |

---

## 9. What Done Looks Like

- `radiant gui` launches a themed 9-stage application from any example YAML.
- Every scenario row marked v1 in the Phase 0 requirements matrix is demonstrable.
- All GUI tests pass headless in CI; golden results byte-identical to pre-GUI.
- `RADIANT_GUI_Architecture.md` describes the shipped application with zero
  aspirational claims; deferred items live in `gaps.md`, not in doc prose.
- This plan is in `docs/archive/` with a completion banner.
