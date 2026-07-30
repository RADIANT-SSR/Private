# RADIANT GUI Architecture

**Date:** 2026-04-07 · **Ratified v1 spec:** 2026-07-12 · **v1 shipped / plan closed:** 2026-07-15
**Status:** Active — ratified v1 specification. **GUI v1 is shipped** and the GUI
Development Plan closed at Phase 9 (2026-07-15); this document now describes the **shipped**
application (all nine per-stage instruments, the 2D schematic viewer, the scripting window,
and file round-trip / undo-redo / theme toggle). It supersedes the prior "DESIGN TARGET"
draft, and describes v1 scope, the GUI-backend contract, the layout, the geometry-viewer
panel, the design system, and the scenario requirements matrix. This remains the authoritative
GUI-content surface; post-v1 work updates it in lock-step (Rule 20).
**Depends on:** `RADIANT_Personas.md`, `RADIANT_Signal_Chain_Architecture.md`,
`RADIANT_Geometry.md`, `api/sensor.py` (the scripting API this GUI is a view over).
**Implemented by:** `docs/archive/GUI_Development_Plan.md` (Complete, archived 2026-07-15) —
§§2–4 record the ratified decisions, scope, and ground rules. Post-v1 GUI features and the
v1.1 backlog live in `docs/tracking/gaps.md` (GUI-1…GUI-17), not in this doc's prose.

**Layout redesign (owner-ratified 2026-07-13).** §4 now specifies the **contextual
per-stage workspace** (visual spec: the ratified wireframe reviewed 2026-07-13). This
**supersedes** the earlier global-metric-badge-row + shared-canvas + bottom-detail-tabs
layout (Rule 24/27). The redesign is a **rearrangement plus additions, not a rebuild**:
every piece shipped in Phases 1–4 (application shell, QSS theme, left parameter tree,
background evaluate loop/worker, 9-stage strip, the `result.plot.*` figures, metric
badges, warning strip, YAML view) is **retained and relocated** — metric badges become
pinnable right-rail cards, the warning strip becomes the Messages panel, the bottom detail
tabs dissolve into per-stage center views and two global tools. Nothing built is discarded.
The GUI Development Plan was re-sequenced to this layout (revision landed 2026-07-14) and has
since closed (archived 2026-07-15); §4 describes the shipped layout.

---

## 1. Ratified v1 Decisions (owner, 2026-07-12)

Four decisions were put to the owner explicitly (GUI plan §2) and are binding for v1;
D5 (the 3D engine) was ratified the same day.

| # | Decision | Ruling |
|---|----------|--------|
| **D1** | Technology | **PySide6 / Qt6 native** (confirming the 2026-04-07 architecture decision, §2). The HTML/React mockups in `dev_tools/gui_mockups/` are the *visual spec*, ported to Qt — not the implementation medium. |
| **D2** | First runnable milestone | **Evaluate loop first**: open YAML → parameter tree → Evaluate → metric badges + plot, end-to-end, before any other panel is built out (GUI plan Phase 3, Milestone A). |
| **D3** | Geometry stage-0 dependency | **Wait for stage 0.** No GUI *implementation* starts until the Geometry stage is complete and merged (done 2026-07-12). Phase 0 doc-only spec work (this document) ran before that. |
| **D4** | v1 must-haves beyond the core | **3D geometry viewer** and **scripting console** are in v1. **Sweep tab** and **Batch / Monte Carlo dialogs** are deferred to **v1.1** — they remain in this doc's layout as absent/disabled tabs; the backend already supports them via script (`sensor.sweep()`, `sensor.monte_carlo()`). |
| **D5** | 3D viewer engine | **PyVista embedded via `pyvistaqt.QtInteractor`**, lifting the `dev_tools/geometry_gui_v2` scene library (the proven PySide6 + PyVista combination). Matplotlib remains the engine for all 2D plots. |

### 1.1 v1 Scope Split

**In scope (v1)** — delivered across GUI plan Phases 1–9:

1. Application shell: main window, menus, **9-stage** geometry-first stage strip,
   dockable parameter panel, central plot canvas, tabbed detail panel, status bar.
2. Schema-driven parameter panel generated from `Sensor.parameter_defs()` — never a
   transcribed parameter list (Gap 70).
3. Evaluate loop: background-thread `sensor.evaluate()`, metric badges, actionable
   error dialogs (`RadiantError` what/why/action), debounced full-chain re-evaluation.
4. Detail tabs: Spectral, MTF, Noise Budget, Variable Explorer, YAML.
5. Geometry screen: stage-0 input-mode forms bound to the `geometry.*` schema, with
   live derived-angle readout from `stage_outputs["geometry"]`.
6. 3D geometry viewer: the not-to-scale schematic (sun/sensor/target glyphs, vectors,
   click-to-reveal angle annotations, target shape library, RPY triad).
7. Scripting console: embedded REPL with live `sensor` / `configs` / `result` objects.
8. File round-trip: Open/Save/Recent YAML via `Sensor.load()` / `sensor.save()`;
   undo/redo of parameter edits.

> **Layout note.** Items 1 and 4 above name the *shipped* components (central plot canvas,
> tabbed detail panel; the Spectral / MTF / Noise / Variables / YAML tabs). The
> 2026-07-13 redesign (§4) keeps these components but **relocates** them: the shared
> canvas + global badge row become per-stage contextual center views with a pinnable
> right rail, and the detail tabs dissolve into per-stage center content plus two global
> tools (§4.7). The scope is unchanged; only the arrangement is.

**Out of scope (v1)** — do not implement, even partially:

- Sweep tab UI, Batch / Monte Carlo dialogs — **v1.1** (D4).
- Everything in §9 "Deferred to Phase 2" (image simulator, library browser, report
  generator, comparison mode, plugin UI, remote compute).
- PyInstaller / standalone-binary packaging (v1.x; v1 runs from the repo venv).
- Incremental / stale-DAG re-evaluation — **DECLINED for v1** (CU-079, owner-ratified
  2026-07-11): full re-runs only. Measured full-chain evaluation is ~0.22 s, fast
  enough that simple full re-runs suffice; there is no incremental-DAG engine and none
  is planned for v1.
- Any change to physics, schemas, or golden results. The GUI is results-neutral by
  construction; a golden-test diff in any GUI PR is a defect.

### 1.2 Binding Cross-Cutting Requirements

These two ground rules (GUI plan §4.1, §4.6) are acceptance criteria for **every**
phase and are restated here as the contract this architecture enforces:

- **R-API — The backend is the scripting API. One GUI action ↔ exactly one API call.**
  The GUI has no data model of its own; it is a view over `Sensor` / `ChainResult`
  (§3). No GUI component contains physics. If a GUI action needs a hook the API lacks,
  the phase *stops* and files the gap in `docs/tracking/gaps.md` — GUI code never
  reaches into stage internals or re-implements a computation.
- **R-UNITS — Units on every displayed value, no exceptions.** Every numeric shown
  anywhere in the GUI (badge, table cell, tooltip, axis, readout) carries its unit,
  sourced from the `ParameterDef` / result metadata, never hardcoded. This is an owner
  hard rule.

### 1.3 Phase 0 Checkpoint Ratification (owner, 2026-07-12)

The owner ran the GUI plan Phase 0 checkpoint against this document and **confirmed** it
— OUT-OF-V1 table accepted (§7.2), v1 scope split confirmed (§1.1), geometry-viewer
contract confirmed (§6), design system approved (§8) — with two amendments:

- **Amendment 1 — light theme is the v1 launch default**, dark is the alternate. Both
  derive from the same token set; the View-menu toggle (Phase 9) is unchanged. The owner
  reviewed the light rendering live in `radiant_mid_fi.html` (its load default) on
  2026-07-12. Recorded in §8.
- **Amendment 2 — the `well_status` saturation banner is pulled into v1** (was §7.2 row 8,
  dispositioned to `gaps.md`). The GUI half — a persistent banner when the detector well
  clips — lands in GUI plan Phase 3; the API half is **CU-101** (expose `well_status` on
  the `ChainResult` metric surface), now a Phase 3 prerequisite. Recorded in §7.2 row 8.

---

## 2. Technology Choice: PySide6 (Qt6 Native)

**Native desktop application using PySide6 (Qt 6).** Not: React + FastAPI backend.
Not: Jupyter widgets. (Ratified D1.)

### 2.1 Evaluation

**Option A — Web (React + FastAPI).** *Pros:* modern, browser-accessible, strong viz
libraries, cloud-deployable. *Cons:* two runtime processes; browser↔server state sync
adds latency and race conditions; needs npm/node (aerospace users on restricted
networks often cannot install npm packages); cannot embed in a classified environment
without an internal server; JSON serialization of 500-point spectral arrays across the
process boundary on every parameter change is expensive.

**Option B — Jupyter widgets (ipywidgets / panel).** *Pros:* GUI-like interaction for
existing Jupyter users; no separate app. *Cons:* widgets target notebook cells, not
multi-panel professional applications — the stage strip, parameter panel, and detail
tabs become brittle; no standalone distribution; poor experience outside Jupyter.

**Option C — PySide6 / Qt6 native (selected).** *Pros:*

- **Single-process:** GUI and RADIANT backend run in the same Python process. A
  `sensor.set()` call from the GUI is the same call the user makes in a script — no
  serialization, no IPC, no state sync. This is what makes R-API cheap to honor.
- Cross-platform; a future standalone binary via PyInstaller/cx_Freeze (v1.x).
- Mature ecosystem: Qt is the 30-year standard for scientific-instrument GUIs (FLIR
  tools, Zemax OpticStudio); persona users recognize this style. PySide6 is the
  official LGPL Qt binding (no licensing cost).
- Matplotlib integrates via `matplotlib.backends.backend_qtagg`; all `result.plot.*`
  methods render inside the GUI unchanged.
- Background computation in a `QThread`; Qt signal/slot delivers thread-safe results.

*Cons:* requires Qt (mitigated by a bundled binary later); dark/custom theming needs
QSS (§8 Design System addresses this once, centrally); not browser-accessible (a future
web front-end can layer on the same scripting API if remote access is ever needed).

### 2.2 Justification from Personas

| Persona | GUI requirement | How PySide6 satisfies |
|---------|----------------|----------------------|
| Sarah (P1) | Parametric sweep plots, one-page summary export | Sweep UI (**v1.1**) triggers `sensor.sweep()`, renders into the embedded matplotlib canvas |
| Mike (P2) | Noise budget breakdown, drill-down into terms | Noise Budget tab; same data as `result.noise_budget()` |
| Lisa (P4) | Standalone app, batch execution | Bundled app (v1.x); batch/MC dialog (**v1.1**) calls `sensor.monte_carlo()` / `BatchRunner` |
| Tom (P5) | MTF plot with all components, RER, PSF viewer | MTF tab with individual term overlays; PSF 2D view |
| Raj (P3) | Load sensor file, specify scenario, get answer | File open → geometry/parameter panel → Evaluate → results |

---

## 3. GUI-Backend Interface

### 3.1 The Backend Is the Scripting API (R-API)

The GUI is a view over the scripting API's `Sensor` and `ChainResult` objects. Every
action maps to exactly one scripting-API call:

```
GUI Action                         Scripting API Call
──────────────────────────────────────────────────────
Open YAML file                     sensor = Sensor.load(path)
Edit parameter value               sensor.set(dotpath, value, unit=…)
Click "Evaluate"                   result = sensor.evaluate()
Stage strip button click           (navigation only — no API call)
Explain a parameter                sensor.explain(dotpath)
Export YAML                        sensor.save(path)
Export result archive              result.save(path)   # reload: ChainResult.load
Console: type Python               direct IPython evaluation in the sensor namespace
Run Sweep       (v1.1)             sweep = sensor.sweep(param, values, metric=…)
Monte Carlo     (v1.1)             mc = sensor.monte_carlo(n_trials)
```

This mapping is one-to-one and explicit. No GUI component contains physics logic.

### 3.2 Threading Model

The GUI runs on the Qt main thread. A full-chain evaluation runs in a `QThread`
worker; the worker emits a signal when evaluation completes or fails.

`Sensor.evaluate()` takes **no** progress or per-stage callback — its real signature is:

```python
def evaluate(self, *, extra_stage_outputs: dict[str, dict] | None = None) -> ChainResult
```

A full chain evaluates in ~0.22 s, so the worker emits only started / finished / failed
and the status bar shows a busy indicator — there is **no** per-stage progress stream
(the old `on_stage_complete` sketch described a callback the API does not have):

Since the session model became a configuration set (§4.2b, multi-configuration Phase 4a)
the worker drives `ConfigurationSet.evaluate_all` — one call, every configuration, the
displayed one first:

```python
class ConfigSetEvaluationWorker(QThread):
    finished_ok = Signal(object)      # ConfigSetRunResult
    failed = Signal(object)           # the exception (RadiantError or otherwise)

    def __init__(self, config_set: ConfigurationSet) -> None:
        super().__init__()
        self._config_set = config_set

    def run(self) -> None:
        try:
            run = self._config_set.evaluate_all()
        except Exception as exc:      # re-raised into the GUI thread via signal — never swallowed (Rules 15/17)
            self.failed.emit(exc)
        else:
            self.finished_ok.emit(run)
```

The `except Exception` here is a thread-boundary hand-off, not a swallow: the exception
is re-emitted to the GUI thread, which renders it (RadiantError → what/why/action modal;
anything else → error dialog with a traceback fold). Nothing is silently dropped. Note
that a *per-configuration* physics failure is not an exception at this boundary — it is
recorded on the returned `ConfigSetRunResult` (Rule 17), and the window decides how to
show it (§4.5).

**Warning capture lives in the API, not the worker.** `evaluate_all` opens one
`warnings.catch_warnings(record=True)` + `simplefilter("always")` window **per
configuration** and records that configuration's warnings on `ConfigRun.warnings`
(re-logging them as well, so nothing is dropped). The GUI worker therefore captures
nothing of its own: a second capture would double-count the warnings and destroy the
per-configuration attribution. CU-110 (the process-global filter mutation being safe only
under the single-worker invariant) travels with the capture to `api/config_set.py`.

**Thread isolation (as shipped, GUI plan Phase 3; set-level since Phase 4a).** The main
window hands the worker a private `config_set.clone()` taken on the GUI thread at schedule
time, not the live document, so a parameter edit that lands on the GUI thread while the
chain is mid-run cannot race the worker's read of the same objects. The worker still
performs exactly one `evaluate_all()` call (one GUI action ↔ one API call); the clone is a
thread-isolation mechanism, not a second API surface. The status bar shows an
indeterminate busy indicator while the worker runs, and only one evaluation runs at a
time — an edit that arrives mid-run is coalesced and re-issued when the in-flight run
finishes. The whole pass is retained on the window (`last_run`): it is the sole source of the
per-configuration Performance columns (§4.2e) and it renders a selector switch from
cache.

Per-point `progress(done, total)` / `cancel()` callbacks **do** exist on
`sensor.sweep()` / `sweep_2d()` / `monte_carlo()` (Gap 72, `api/_progress.py`) and back
the **v1.1** sweep/MC progress bars — not the v1 single-shot evaluate loop.

### 3.3 Re-Evaluation Policy

On a parameter edit the GUI calls `sensor.set()` and then re-runs the **whole chain**
in the worker, debounced by a 200 ms timer (edits within the window coalesce into one
run). There is no incremental / stale-subgraph engine and none is planned for v1
(CU-079, declined). A failed evaluation leaves the previous result displayed with a
visible "stale — last evaluation failed" state; it never shows a blank or a partial mix.

---

## 4. Layout — Contextual Per-Stage Workspace (ratified 2026-07-13)

The layout is a **contextual per-stage workspace**: the 9-stage strip is the single
primary navigation, and clicking a stage makes the center show **only that stage's
contextual content** (its editable inputs, its outputs with units, its plot(s)). A
permanent left tree lists all parameters; a persistent right rail carries pinned values,
the config editor, and messages. This supersedes the earlier global-badge-row +
shared-canvas + bottom-tabs design (Rule 24/27); §4.7 records exactly where each
superseded piece moved.

### 4.1 Top-Level Window Structure

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  RADIANT — leo_mwir_clear.yaml                                        [≡][□][X]│
├──────────────────────────────────────────────────────────────────────────────┤
│  File  Edit  View  Run  Tools  Help                            ◈ Inspector    │
├──────────────────────────────────────────────────────────────────────────────┤
│ Geometry │ Source │ ▣Atmosphere │ Optics │ Platform │ Spectral │ Detector │ Readout │ Performance │
│  [9-stage geometry-first strip — the SINGLE primary navigation; health dots]   │
├──────────────┬──────────────────────────────────────────────┬─────────────────┤
│ ALL          │  03  ATMOSPHERE          [contextual view]    │ PINNED          │
│ PARAMETERS   │  ── Inputs (editable · 1 edit → 1 set) ────   │  SNR   616      │
│ [search ⌘F]  │   standard_atmosphere  visibility_km  …       │  NIIRS 10.62    │
│  ▶ geometry  │  ── Outputs (read-only · with units) ─────    │  τ_atm 0.812    │
│  ▶ source    │   τ_atm 0.812   L_path 0.94 W/m²/sr/µm  …     │  [+ pin a value]│
│  ▼ atmosphere│  ── Plot(s) ─────────────────────────────    │ ┌─────────────┐ │
│    visibility│   [τ_atm & L_path vs λ]                       │ │Edit Config  │ │
│    path_type │   [source & bkgd radiance at aperture]        │ │  (YAML) ⎙   │ │
│  ▶ optics    │                                               │ └─────────────┘ │
│  ▶ …         │                                               │ MESSAGES        │
│              │                                               │  ⚠ 1 warning    │
├──────────────┴──────────────────────────────────────────────┴─────────────────┤
│  [Status bar: "Evaluated in 0.22 s — 500 wavelength points" ]                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

Three columns under the strip: **left** = permanent searchable *All Parameters* tree
(§4.3, kept); **center** = the selected stage's contextual view (§4.4); **right** = the
persistent rail — *Pinned* / *Edit Config (YAML)* button / *Messages* (§4.5). The full
`result.inspect()` variable dump is a **global Inspector tool** on the menu/toolbar
(§4.6), not a docked panel.

### 4.2 Signal-Chain Strip (9 stages, geometry-first) — the single primary navigation

A horizontal strip of clickable stage buttons, in chain order per ADR-0006
(geometry-first): **Geometry → Source → Atmosphere → Optics → Platform → Spectral
Integration → Detector → Readout → Performance.** In the ratified layout the strip is the
**single primary navigation**: there is **no global metric-badge row** (removed — a fixed
badge row is non-contextual; the performance metrics live in the right-rail *Pinned* panel
instead, §4.5, where any stage's value can join them). Each button shows the stage name and
a health dot:

```
 ● green  = evaluated, no issues
 ◑ yellow = warnings present
 ○ red    = stage raised an error
 ◌ gray   = stale / not yet evaluated
```

Clicking a stage is navigation only (no API call): it scrolls the parameter panel to that
stage's namespace and makes the **center show only that stage's contextual view** (§4.4) —
its editable inputs, its outputs, and its plot(s). There is no shared canvas that all
stages write into; each stage owns its center content.

**As shipped (GUI plan Phase 4 Task A).** A click emits the chip's **real schema
namespace** — not the shortened eyebrow display, which may abbreviate (the 6th stage
displays `SPECTRAL` but navigates to `spectral_integration`; the eyebrow-vs-namespace
drift is CU-106, resolved here, with a construction-time guard asserting every chip
namespace is a real chain stage). The host then scrolls the parameter panel to that
namespace group and swaps the central canvas to the stage's §4.4 default visualization.
A selected chip carries `focus-soft` background + `focus` border (§8.4); a warned/errored
chip also carries the `<status>-soft` tint, and selection wins visually when both apply.

**Health-dot attribution (v1 decision, GUI plan Phase 4 Task A).** The dots are driven
from the *whole run*, not per stage:

- **gray / stale** — no result yet, or a parameter edit since the last run (the
  `parameterEdited` signal flips every dot back to stale until the pending debounced
  re-run lands).
- **green / ok** — the run finished with **no** chain warnings.
- **yellow / warn** — the run finished but carried **at least one** chain warning.
  Warnings are **not** attributed to a single stage: the captured warnings are free text
  (`warnings.catch_warnings`, arch doc §4.4) and not reliably mappable to one stage, so
  v1 marks **every** dot yellow on any warning. Per-stage warning attribution is deferred.
- **red / err** — the evaluation raised. The failing stage is **not** identified: the
  public exception surface does not reliably carry the originating stage, so v1 marks
  **every** dot red rather than guessing. Per-stage failure attribution is deferred.

These two "whole-run" choices keep the health signal honest (it never claims a precision
it cannot source); refining either to per-stage attribution is a later enhancement.

> The mockups in `dev_tools/gui_mockups/radiant_ui/` predate ADR-0006 — they open on the
> **Source** screen with an 8-stage strip. v1 opens on **Geometry** with the 9-stage
> strip above; the mockups remain the visual spec for chrome and styling only.

### 4.2b Master Configuration Selector (multi-configuration — Phase 4a SHIPPED 2026-07-25)

The GUI session is a **`ConfigurationSet`**, not a bare `Sensor` (ADR-0010; plan
`docs/archive/Multi_Configuration_Plan.md` §4). A plain config file loads as the
**degenerate one-configuration set** — observably the single sensor it contains — and a
study file (one carrying a `configurations:` section) loads as the full set.

**Selector form (decided in Phase 4a).** A compact **tab strip in its own thin top dock,
directly above the signal-chain strip** — one tab per configuration, in set order, each
carrying that configuration's accent chip (§8.1 `config_accents`, both themes). It is
`ConfigurationBar` (`widgets/configuration_bar.py`). The alternative considered was a
toolbar/status-area combo; the window has **no toolbar**, and the nine stage chips already
consume the full width of the strip, so a combo would have had to crowd either the menu
corner (already carrying the Inspector affordance) or the status bar (which is a
transient-message surface, not a persistent control). The dedicated band costs one row and
keeps the study's shape readable at a glance.

**Zero visibility for a single configuration.** With one configuration the bar builds no
tabs and its **dock is hidden**, so the window carries no extra band at all — a
single-configuration session is the pre-Phase-4a GUI byte for byte. This is a tested
requirement, not an intention (`gui/tests/test_configuration_selector.py`).

**What a switch does.** One GUI action ↔ the API state it means: `config_set.active = name`
plus one `sensor_for(name)` materialization (R-API). Every surface then reads the displayed
configuration — the nine stage center views, the input forms, the readouts, the right rail,
the parameter tree, and the scripting console's `sensor`. A switch **does not re-evaluate**
when the retained pass already holds that configuration's result; the views render from
cache. A pass made stale by an edit is covered by the ordinary 200 ms debounce (§3.3).

**Displayed-sensor identity.** `RADIANTMainWindow.sensor` returns the *displayed
configuration's materialized sensor* and is **stable between evaluations** — materialized
once per displayed configuration and cached — because every existing reader treats it as a
live handle it may `set()` on. In the degenerate case it is literally
`configuration_set.base` (the same object, not a clone), which is what makes the
single-model edit path unchanged.

**Where an edit lands.** A shared parameter's edit is written through to the shared
base, exactly as a single-model edit behaves, and the undo commands target that base — so
a shared edit stays undoable **across** a selector switch. An inline edit of a parameter
the study marks *configured* is written to the displayed configuration's own column
(ADR-0010 D-8) and, since Phase 4b, is undoable as a scoped command (§4.2c).

Since Phase 4c the strip also carries a trailing **gear** at its right end, which opens
the configuration manager (§4.2d) — the same dialog `Edit → Configurations…` opens. The
selector itself is still display-only: it chooses which configuration is shown, and the
manager is the one place membership changes.

The study YAML document, the console `configs` object, study-aware recent handling, and
the dirty/title polish landed in **Phase 4e** (§4.2f); no part of the multi-configuration
GUI is outstanding.

### 4.2c Configured Parameters — badge, table editor, scoped undo (Phase 4b SHIPPED 2026-07-25)

A parameter is **shared** by default and becomes **configured** — one value per
configuration, dense by construction — only when the analyst says so (ADR-0010 D-A/D-2).
Phase 4b is the surface for that decision and for editing the values it creates.

**The scope object.** One `ConfigurationScope` (`gui/config_scope.py`) is the read side
and the intent channel shared by every badge-bearing surface. Widgets ask it *is this
dot-path configured* and *what are its values*; they emit *configure / edit values /
un-configure* through it. The main window is its only listener, so a widget still makes
no API call — the window makes the single `ConfigurationSet` call and records one undo
command (R-API). A single `changed` signal re-reads every badge in the window, which is
what keeps the "C" honest after a configure, an un-configure, or any value edit.

**The red "C" badge — immediately right of the name.** Every configured parameter is
marked with a small red **C** — the owner's explicit visual spec — in the all-parameters
tree (§4.3) and in every per-stage form field (§4.4). The form badge reaches all nine
stages because every field is the one shared `FieldRow`. The colour is the theme's `err`
token in both themes (§8.1), never a literal. The tooltip lists **every** configuration's
value with its unit, in set order — `MWIR: 3.5 um · LWIR: 8 um` — so the whole column is
readable without opening anything.

*Placement* (owner feedback 2026-07-26, *"move the red C just to the right of the variable
name"* — it had been sitting after the value box, and in the tree to the left of the name):

| Surface | How it is placed |
|---|---|
| Form field (`FieldRow`) | The badge is the grid column **between** the label and the value box. Its slot retains its size when hidden (`setRetainSizeWhenHidden`), so configuring a parameter never reflows the row |
| Parameter tree | A `QTreeWidgetItem` decoration can only paint *left* of the text, so the Parameter column carries `ConfiguredNameDelegate` (`widgets/configured_name_delegate.py`), which paints the row normally and then the badge at the name's text advance plus a gap, clamped inside the cell for an elided name. The item sets only the `CONFIGURED_ROLE` flag the delegate reads — no icon. `badge_rect()` is the placement decision, factored out so it is assertable without a rendered window |

**The three actions** (identical wording and order in the tree's context menu and the form
fields', because both are built by one helper, `widgets/configure_menu.py`):

| Action | API call | Notes |
|---|---|---|
| *Configure across configurations…* | `configure(dotpath)` | Seeds every configuration from the current shared value and moves the parameter out of the base (D-B). Offered on a shared parameter. In a **single-configuration** session it answers with an actionable status message naming the configuration manager by its real menu path, `Edit → Configurations…` (§4.2d) — never a silent no-op. The Parameter Editor offers the same action as a button (below), differing only in that it stages values first and so commits `configure(dotpath, values, unit=)`. |
| *Edit configured values…* | `set_values(dotpath, values, unit=)` | Opens the Parameter Editor in its per-configuration mode (below). |
| *Un-configure (keep &lt;first&gt;'s value)…* | `unconfigure(dotpath)` | Always keeps configuration #1's value (D-6). The confirmation **states that value with its unit** before proceeding, so collapsing a column is never a silent physics change in the other configurations. |

**The per-configuration editor is the Parameter Editor** (owner feedback 2026-07-26 —
*"when you click on a parameter that is configured you should be able to set the value for
all the configurations at one time … one box for MWIR and one for LWIR"*). Opened on a
**configured** parameter, `ParameterEditorDialog` (§4.3) shows one seeded value box per
configuration instead of its single box: `PerConfigurationValues`
(`widgets/per_configuration_values.py`) renders one row per configuration in set order —
the configuration's accent chip (§8.1 `config_accents`, the selector's hue for that slot),
its name, a value editor built from the parameter's own schema entry (enum → combo, bool →
check box, int → bounded spin box, float/str → line edit — the same editors the
single-value path builds), and the unit (R-UNITS). One dot-path, one editor, whatever its
scope; the badge, the tree double-click, the form value button, and *Edit configured
values…* all raise this dialog.

*Phase 4b's stand-alone `ConfiguredValuesDialog` is retired* (Rule 27): it had become a
second, thinner copy of this same table, reachable only from the badge route. Its
behaviour and every one of its tests moved onto the editor dialog — the badge route still
opens per-configuration editing, it just opens the one editor.

It commits in **one** API call — `set_values(dotpath, values, unit=)` — recorded as one
scoped undo step. The API validates the whole column before replacing it, so a rejected
value leaves the set untouched (no half-commit) and the rejection, which names the
offending configuration, renders inline while the dialog stays open (Rules 15/17). The
rows work in the **parameter row's display unit** — whatever unit the analyst chose for
that dot-path (`ParameterPanel.display_units`), falling back to the schema `input_unit` —
labelled on every row, and the dialog's single unit selector governs the whole column
(one schema entry ⇒ one dimension) rather than a per-row unit. Changing it *reinterprets*
what is typed, exactly as it does in the single-value path; the conversion still happens
once, at the API boundary, so the GUI performs no unit arithmetic (Rule 2). A unit the
public registry cannot soundly invert drops every row back to the input unit rather than
showing a mixture. (CU-211, closed in Phase 4c — the API seam it needed is
`ConfigurationSet.set_values(..., unit=)`.)

Two other things change in this mode. The **canonical preview** — the single `= 8 um`
line — becomes N named canonical values, `= MWIR: 3.5 um · LWIR: 8 um`: with N boxes the
one-number line was no longer true of anything. And the **Tolerance** section keeps its
base-level meaning (ADR-0010 puts the Monte-Carlo spread on the shared parameter, not on
one configuration's column) with a one-line clarifier saying so, rather than being
redesigned.

**Configuring from the editor — the discoverability answer** (owner question 2026-07-26,
*"how do you set a variable to be configurable?"*). Opened on an editable **shared**
parameter with a document bound, the dialog offers a *Configure across configurations…*
button (the same wording as the context-menu action, from the one `configure_menu`
constant). Clicking it **stages** the intent: the dialog expands in place into the same
per-configuration boxes, seeded from the value currently in its editor, and *nothing is
configured yet* — Cancel leaves the parameter shared and untouched. **Apply** commits the
promotion and the typed values together, as the single atomic
`configure(dotpath, values, unit=)` call, so one undo returns the parameter to its prior
shared state (value *and* scope). In a **single-configuration** session the button is
present but guarded: it answers with the same `SINGLE_CONFIGURATION_HINT`, naming
`Edit → Configurations…`, that the 4b context-menu action gives — a hidden control cannot
teach the analyst that the capability exists. The context-menu route is unchanged.

**How a dialog reaches the scope.** `ParameterEditorDialog` takes an optional
`scope=`; omitted, it walks its ancestors for the window's `configuration_scope`
(`config_scope.scope_of`), so the ten places that open the editor need no plumbing and a
parentless dialog (a unit test) simply gets the single-value behaviour. Writing a whole
column is the one *synchronous* scope request — a dialog needs the API's verdict inline —
so it goes through a committer the window installs on the scope
(`ConfigurationScope.set_committer`), keeping the single `ConfigurationSet` call and the
undo push in the window (R-API). Surfaces gate on `scope.can_commit`; a write attempted
without a committer raises `ConfigurationScopeError` (a `RadiantError`, Rule 15) rather
than dropping the analyst's column, which makes the wiring fault loud instead of silent.

**Scoped undo/redo.** `ScopedParameterCommand` (`widgets/scoped_parameter_command.py`)
records a parameter's whole **scope state** — which store it lives in plus the value(s) —
before and after an action, so one command class covers configure (with or without
staged values), un-configure, a whole-column write, and an inline per-configuration
edit, and undo restores **both the value and the scope**: undoing a configure drops the
column and restores the base's prior explicit input (or resets it, when the base never had one, so a defaulted parameter stays
defaulted); undoing an un-configure restores the full column. Shared edits keep Phase 4a's
`SetParameterCommand` against the base, so both kinds share one stack and a shared edit
stays undoable across a selector switch.

**Single-configuration sessions are unchanged.** Nothing is configured, so no badge is
ever shown and no per-configuration editing surface appears; the only new behaviour is
the guarded action — the context-menu item's status message and the editor dialog's
button, both answering with the one `SINGLE_CONFIGURATION_HINT`. A tested zero-regression
requirement (`gui/tests/test_configured_parameters.py`,
`gui/tests/test_configured_badge_placement.py`).

### 4.2d Configuration Manager (Phase 4c SHIPPED 2026-07-25)

The dialog that answers the owner's first study requirement — *"the user can define the
number of configurations and then name them"* (plan §4 item 1). It is reached from
**`Edit → Configurations…`** and from the **gear** at the right end of the selector band
(§4.2b); both trigger the one `edit.configurations` action. It lives in Edit rather than
Tools because it edits the *document's* shape; Tools' neighbouring
*Compare Config Files…* compares this config against other config **files on disk** and
is unrelated. That item read *Compare Configurations…* until Phase 4d relabelled it
(CU-214): under the ADR-0010 D-10 convention a bare "configuration" is a member of a
configuration set, and the surface that compares *those* is §4.2e's Performance columns.

It is `ConfigurationManagerDialog` (`widgets/configuration_manager_dialog.py`).

**One row per configuration**, in set order: the configuration's accent chip (§8.1
`config_accents`, the selector's hue for that slot) and name, a **baseline** marker, its
per-configuration **wavelength-points** override, and a live **status**.

* *Wavelength points* — an integer, or blank to inherit. A blank row's grey placeholder
  states both the shared value and what blank means (`shared: 500 pts`), so an empty box
  is never unexplained. Reading and clearing the state needs the Phase-4c API additions
  `ConfigurationSet.wavelength_points(config=None)` (CU-210) and
  `set_wavelength_points(config, None)`. The shared field, the column heading, and every
  row box carry a tooltip saying **what** is being set (owner question 2026-07-26, *"what
  are we setting here?"*): the number of **wavelength samples** in that configuration's
  spectral evaluation grid, which spans its own `filter_min_um → filter_max_um`; blank
  inherits the shared value; RADIANT's default is 500. The wording lives in one place
  (`SHARED_POINTS_TOOLTIP` / `GRID_POINTS_COLUMN_TOOLTIP` / `row_points_tooltip`) so the
  three surfaces cannot answer the question differently.
* *Status* — from `ConfigurationSet.validate_all()`: `OK`, or the failing
  configuration's error *what*-line with the full what/why/action on hover. It is
  **resolve-only**; opening or editing in this dialog never runs physics. It re-runs
  after every action in the dialog.

**Actions**: Add, Duplicate (`add(copy_from=)`), Rename, Remove, Move Up / Move Down
(`reorder`), Set as Baseline — one `ConfigurationSet` call each (R-API).

**A private working copy.** The dialog edits `config_set.clone()` and hands the window a
whole study *shape* on OK. Two things follow. Cancel is exactly "discard the clone" — no
partial application and no undo entry. And every guard the analyst meets is the **API's
own** — a ninth configuration, a duplicate or empty name, removing the last one — raised
by the real call on the clone and rendered inline as its what/why/action; the dialog
duplicates no validation.

**Removing the displayed configuration** is allowed. The policy, stated in the dialog and
again in the confirmation, is the model's own `remove()` behaviour: *the display moves to
the first remaining configuration*. The confirmation also names how many configured
parameters lose a value, so a column is never dropped silently.

**Undo/redo is one step for the whole transaction.**
`ConfigurationShapeCommand` (`widgets/configuration_shape_command.py`) records the study's
**shape** — names in order, the configured table's value columns, each
`wavelength_points` override plus the shared default, and `baseline` / `active` — before
and after the dialog's OK, and applies a shape as a unit. That follows from the
apply-on-OK design: the live set never sees the intermediate states, so there are no
per-action steps to reverse. It also avoids the sequencing trap a per-action design has
(undoing *rename A→B* after *add A* must not collide) — a shape is applied by
construction, via placeholder renames, rather than by replaying inverses. Undoing a
Remove therefore restores that configuration's configured values exactly, and the
selector, badges, and displayed configuration are refreshed from the same code path in
both directions. A shape deliberately does **not** carry *which* parameters are
configured or any shared value: the manager never changes those, so they stay with
§4.2c's `ScopedParameterCommand`. Both command kinds mutate the one live
`ConfigurationSet` and share one undo stack in any order.

**This is how a plain session becomes a study.** Add on a one-configuration session
reveals the selector band on the way out, marks the document dirty, and makes
`File → Save` write the `configurations:` section (the routing 4a already put in
`_write_document`). Undoing it collapses the session back to a hidden selector.

### 4.2e Per-Configuration Performance Columns (Phase 4d SHIPPED 2026-07-25)

The study's comparison surface: on the **Performance** stage every metric row carries
**one column per configuration** (plan §4 item 6). The full content spec is the §4.4.1
Performance row; this section records the decisions behind it.

**Grouping → columns, not grouping → tabs.** The plan wrote this as *"each metric
grouping gets its own tab, with a column per configuration"*. Between the plan and this
phase the owner slimmed the Performance pane twice, ending at **one flat pane of themed
group cards** — one card per Gap-96 metric group — with the interim Summary / All
metrics / MTF-budget tab set removed. The grouping unit therefore already exists, and it
is the **card**, not a tab. Phase 4d promotes those cards to matrices rather than
re-introducing the tab strip the owner had just taken out: the analyst still sees one
labelled section per metric group, in the same order, and each section grows N columns.
Re-adding tabs is still a data change away (`StageComposition.subviews`, §4.4) if the
owner later wants one group per screen; nothing here forecloses it.

**Plain values only (ADR-0010 D-9).** A cell carries a value and its unit and nothing
else — no delta column, no best-per-metric mark. Delta-vs-baseline and best-marks live
on the scripting surface (`ConfigurationSet.compare` → `compare_configs`), and the set's
`baseline` designation stays in the model for exactly that. This is the one place the
GUI deliberately shows *less* than the API.

**Where the numbers come from.** The retained evaluate-all pass (`last_run`, §3.2) and
nothing else. Rendering a study — including switching the displayed configuration —
**runs no physics**; a pass made stale by an edit is covered by the ordinary 200 ms
debounce and the existing staleness affordances (§3.3).

**The presentation model is Qt-free.** `gui/metric_matrix.py` turns the run into a
`MetricMatrix` (columns × grouped rows, each cell a text + tooltip); `MetricGroupCards`
only lays it out. Every rule below is therefore unit-tested without a widget, and both
layers are asserted against `run.result_for(<name>)` in
`gui/tests/test_performance_columns.py`.

| Rule | Rendering |
|---|---|
| Column order | The **set** order (`ConfigurationSet.names()`), never the run's evaluation order (which puts the active configuration first) — so columns do not reshuffle when the displayed configuration changes |
| Units | `metric_format.metric_value_display` — the *same* function the single-model readout uses, sourcing the unit from `ChainResult.metric_records()` (R-UNITS). No unit string is written in the matrix or the widget |
| Metric a configuration did not compute | `—`, never `0` and never blank (Rule 17); the cell's hover text names the configuration and the metric |
| Configuration that **failed** to evaluate | Its column stays. Cells read *not evaluated*; the header carries a `✕` and the error's **what**-line (plus its *why*) on hover. Other columns keep their real values — no silent drop |
| Configuration that **warned** | A `⚠` on its header, its warnings on hover. This is a **pointer** to the right-rail Messages entries Phase 4a already attributes per configuration, not a second rendering of them |
| Column headers | The configuration name with its accent chip — the *selector band's* hue for that slot (§8.1 `config_accents`, both themes), handed down from the window so the two surfaces cannot drift apart |
| The displayed configuration | Marked by a **text emphasis** on its header (ink + weight, a themed `[displayed="true"]` property), never a second colour — colour on that header belongs to the accent chip |
| Card layout | One-up in a study (a card carrying N configuration columns needs the full pane width), two-up in a single-configuration session as before |

**Zero regression for one configuration.** A single-configuration session pushes no
matrix at all: `MetricGroupCards.show_metrics(result)` builds exactly the widgets it
built before this phase — no headers, no chips, no extra grid columns — and the pinning
path is the pre-4d `_MetricRow`. Tested explicitly, like the §4.2b selector's hidden
dock.

**Pinning survives.** A matrix row's label cell keeps the hover-revealed pin (§4.5, pin
any metric). It pins the *metric*; the rail card shows the **displayed** configuration's
value for it, which is what every other rail card already does.

### 4.2f Study Persistence and Polish (Phase 4e SHIPPED 2026-07-25)

The last multi-configuration sub-phase: the surfaces that read, write, or narrate the
**document** rather than one configuration of it (plan §4 item 7).

**One predicate decides the document's kind.** `gui/document_yaml.py` is Qt-free and
holds three functions — `is_study`, `serialize_document`, `load_document_from_text` —
and every surface that serializes or re-reads the session goes through them: `File →
Save`, `Export YAML`, the right-rail *Edit Config (YAML)* modal, and
`RADIANTMainWindow._is_degenerate` itself. A **study** is a set with more than one
configuration *or* any configured parameter (a one-configuration set with a configured
column is still a study document — its column would be lost if the file were written as a
bare sensor). A study serializes as `ConfigurationSet.to_yaml` (shared body +
`configurations:`), a plain session as `Sensor.to_yaml(scope="inputs")` — byte-for-byte
the format the app has always written. Putting the choice in one place is what keeps the
file the analyst saves and the text the YAML modal shows from ever disagreeing.

**The YAML view/editor is the study.** *Edit Config (YAML)* (§4.5) preloads the whole
document, section included, and Apply re-parses it through `ConfigurationSet.load` — the
one reader that handles both kinds. Success adopts the parsed document exactly as
`File → Open` does: selector, badges, parameter tree, forms and console rebind, undo stack
cleared (a whole-document replace is not one reversible edit), dirty set, file path kept.
Failure leaves the session untouched and renders the loader's own what/why/action — for a
section violation the `ConfigError` already names the configuration and the parameter, so
the GUI adds nothing. Two consequences follow from routing through the loader rather than
special-casing:

* adding a `configurations:` section by hand turns a plain session into a study;
* **removing** it collapses the study to a plain session (selector hidden) — the analyst's
  explicit instruction, typed into the document. (A removal that leaves a formerly-configured
  dot-path set nowhere produces a document that does not resolve; the window opens it
  editable with the reason in Messages, the same from-scratch rule §4.2b already applies.)

**The console binds the document.** Alongside `sensor` the Command Window namespace
carries **`configs`** — the live `ConfigurationSet`, the same object the selector, the
manager, and Save write through (§4.6.1). No GUI-only wrapper: it is the scripting API
object. `sensor` keeps its §4.2b meaning (the *displayed configuration's* materialization,
which in a plain session is literally `configs.base`), so a study's document edits belong
on `configs`. **Refresh is study-aware**: it adopts `configs`, so a console edit to one
configuration's column survives and the study is never collapsed to the displayed
configuration; a rebound `configs = ConfigurationSet.load(...)` is adopted by identity; a
rebound `sensor` in a plain session is still adopted as the document (the pre-4e
workflow), and in a study the status line says why `sensor` is not one. The staleness
banner's mutation surface grew the `configs` document-editing calls beside
`sensor.set*`/`sensor.load`; it deliberately lists the *named* mutating calls rather than a
bare `configs.` prefix, so an ordinary read does not raise a false banner.

**`active` is view state — written on save, never dirty.** `ConfigurationSet.save`
persists `active`, so switching the displayed configuration does change what the next save
writes. It nevertheless does **not** mark the document dirty: a switch is a look-around,
and putting a `*` in the title for one would train the analyst to ignore the marker. The
switch is captured silently at save time instead (the owner-recommended choice; recorded
here because the alternative — dirty-on-switch — is the one a reader would otherwise
expect from "save writes it"). Everything that changes the **model** does mark dirty: a
shared or per-configuration parameter edit, configure / un-configure, a configured-value
table write, a configuration-manager transaction, an undo or redo of any of those, a
YAML-editor Apply, and a console Refresh.

**Title.** The existing `[*] <file> — RADIANT <build>` pattern gains one parenthetical in
a study — `dual_band.yaml (2 configurations) — RADIANT v…` — filling the slot the pattern
already had between the name and the app suffix. No new chrome; a plain session's title is
unchanged.

**Recent files** need no study-specific handling and are tested to prove it: `Open Recent`
routes through the same `_open_path` → `ConfigurationSet.load` as `File → Open`, so a
study reopens as the full set with its selector visible.

**Shared spectral grid points (CU-213).** The configuration manager (§4.2d) gained the one
control it was missing: a **Shared grid points** field above the rows, writing
`set_wavelength_points(None, n)`. It is the number every blank per-row placeholder already
named, and until now it was reachable only from the YAML editor or the console. Blank has
no meaning above the shared default (`wavelength_points()` always reports a count in
force), so a cleared box restores the current value rather than writing `None`. Undo is
free: `ConfigurationShape` already snapshots `shared_wavelength_points`, so the change
reverses with the rest of the manager transaction in one step.

### 4.3 All-Parameters Panel (permanent left column)

The permanent left column of the contextual layout (§4.1): a searchable tree of **every**
parameter across all stages, retained unchanged from the shipped design. It complements —
does not duplicate — the center stage view's *Inputs* section (§4.4), which shows only the
selected stage's editable inputs; the left tree is the global, cross-stage index.

A tree, grouped by dot-path namespace in chain order (Geometry group first), built
**entirely** from `Sensor.parameter_defs()` — never transcribed from this doc (the
example dot-paths below are illustrative and may not match the shipped `_schema.py`).

```
▼ geometry
      input_mode           [angles_direct ▾]
      sensor_altitude_m    [500000 ] m
      off_nadir_angle      [0.0    ] rad        ⚡ or user-set per mode
▼ optics
      aperture_diameter    [0.30   ] m
      focal_length         [1.20   ] m
      f_number             [ 4.0   ]            ⚡ derived
```

Each row shows the value plus a **unit suffix from the schema** (R-UNITS). Derived
parameters are ⚡-badged and read-only; a provenance badge (user-set / default /
derived) comes from the resolved set. The shipped tree (GUI plan Phase 2) renders this
as three columns — **Parameter / Value / Source** — where Value carries the value + unit
(⚡-prefixed when derived) and Source is the provenance label; provenance is read from
the structured public `Sensor.resolved(dotpath)` / `Sensor.provenance(dotpath)` accessors
(CU-105, resolved — no longer parsed out of the `Sensor.explain` text). A search box
filters by substring across dot-paths.

**Editing (Task B).** Double-click (or the platform edit key) on a non-derived row
opens the editor its `ParameterDef` dtype calls for: a combo box for an enum (choices
read from `ParameterDef.enum_values`, never hardcoded), a checkbox for a bool, a spin
box for an int, a line edit for a float or free string. Each commit is exactly one
`sensor.set(dotpath, value)` (§4.1). To keep the live sensor untouched on rejection, the
value is first validated on a throwaway `sensor.clone()` (the API's own resolve does the
validating — no reimplemented physics); only a clean value is applied to the live sensor
and the row (value + provenance) is refreshed by re-reading the resolved set.
`ParameterBoundsError` / `UnknownParameterError` / consistency-group violations (all
surfaced by the resolver — the generic schema-bounds path raises a flat
`CoreValidationError`, tracked as CU-107) render their what/why/action inline on the row
(a themed error tint + banner) **and** in a modal `ActionableErrorDialog`; the rejected
value never sticks. An unexpected exception raises `UnexpectedErrorDialog` with a
traceback fold (Rules 15/17 — nothing swallowed). Right-click: Copy dot-path, Explain
(renders `Sensor.explain(dotpath)` in a themed modal `ExplainDialog` — the surface chosen
to match the `Tools → Explain Parameter…` menu), Reset to Default (`Sensor.reset(dotpath)`,
which clears the input so the parameter reverts to its default or is re-derived).

**Parameter Editor dialog (Phase 3 checkpoint punch-list).** The narrow dock truncates
long dot-paths, so a full-detail **Parameter Editor** (`ParameterEditorDialog`, one widget
per file) opens on demand and shows the **complete** dot-path (selectable, mono), the
schema description, the current value with unit + provenance, the schema bounds (with
units), and the derived/read-only state. It offers a value editor per dtype (numeric field,
enum combo from `enum_values`, bool checkbox) and — for a dimensional (numeric) parameter —
a **unit selector** populated from the units the conversion registry can convert to the
parameter's canonical unit, read through the public `radiant.api.units` seam (the same
surface `radiant convert` enumerates from), never a hardcoded list. A canonical **preview**
confirms the result before and after applying (enter `8` `km` → `= 8000 m`). Committing is
exactly one `sensor.set(dotpath, value, unit=<chosen>)` (§4.1), validated first on a
throwaway `sensor.clone()` so a rejected value never touches the live sensor; a rejection
renders its what/why/action **inside** the dialog (themed error area) and keeps it open for
correction, while an accepted edit refreshes the tree (the panel's existing refresh path)
and — via **Apply & Close** — dismisses (plain **Apply** keeps it open). A derived (⚡)
parameter opens read-only: the value/unit editors are disabled and only a Close button is
offered. **In a study** the same dialog carries the per-configuration value boxes and the
*Configure across configurations…* affordance — see §4.2c, which owns that spec.

**Path parameters get a Browse… picker (owner request 2026-07-18).** A `str` parameter
whose dot-path leaf follows the schema's path naming convention (`*_path` / `*_file` →
file picker, `*_dir` → directory picker; `path_picker_kind()` in the dialog module) gains
a **Browse…** button beside the line edit that opens the native `QFileDialog` and fills
the field with the chosen path — typing a path stays possible, it just stops being the
only way. When the field is empty the picker opens on the parameter's shipped-data home
(`default_browse_dir`: `atmosphere.*` → `data/atmospheres/`, `detector.*` →
`data/detectors/`, `source.*` → `data/emissivity/`, anything else → `data/`), not an
arbitrary working directory (owner bug 2026-07-18); a set field re-opens beside its
current value. The picker only fills the text field; committing still goes through the one
validated `sensor.set` on Apply. Cancelling the picker leaves the field untouched. (Every
`*_path`/`*_file`/`*_dir` parameter in the schema is a real filesystem path — audited
2026-07-18; the convention is load-bearing for this affordance.)

**Two complementary edit paths.** The Value column keeps its fast in-place editor
(double-click column 1 → `ParameterEditDelegate`); the Parameter (name) and Source columns
open the full Parameter Editor dialog instead (double-click, or right-click → **Edit…** at
the top of the menu). Those two columns carry a `ReadOnlyCellDelegate` so Qt's default
rename editor never appears there, and the dialog is opened from the tree's `doubleClicked`
signal (which fires for derived rows too). The unit choices come from the named public
accessor `radiant.api.units.units_for(canonical_unit)` (CU-109) — the underscored
`_CONVERSIONS` registry stays private to `core`; the CLI `radiant convert` uses the sibling
`input_units()` / `targets_for()` accessors.

**Display units (owner feedback 2026-07-13).** A row shows its value in the unit the
**user** chose, not always the schema canonical/input unit ("otherwise I'm doing math in my
head every time" — an altitude the user set as 500 km reads `500 km`, not `500000 m`). The
mechanism: the panel keeps a session-scoped `dict[dotpath -> display_unit]`; a row absent
from it displays in its schema `input_unit` (unchanged), and a row gains an entry when the
user commits a Parameter-Editor edit with an explicit unit choice (the dialog hands the
chosen unit back through its `on_committed(dotpath, unit)` callback). The Parameter Editor
opens on that display unit — the Current line, the value editor, the unit combo, and the
bounds all read in it. **All canonical↔display conversion goes through the public
`radiant.api.units` seam** (`convert` to the canonical unit, `inverse_convert` back out) —
the GUI does **no** ad-hoc unit maths (Rule 2). The registry holds only pure multiplicative
factors (no additive offsets are registered — temperature keeps only `K`), so
division-through-canonical is always sound for a *registered* unit; a unit that is not
soundly convertible (a one-way or offset unit) **falls back** to the row's canonical/input
unit rather than inventing a conversion. Inline Value-column edits interpret the typed number
in the row's display unit and write it with `sensor.set(dotpath, value, unit=display_unit)`
so entry and display stay symmetric (type `550` into a km-displaying row → `550000 m`
canonical, row shows `550 km`). The unit suffix is always part of the displayed string
(R-UNITS). The preference is **session-scoped**; QSettings persistence across launches
arrives in Phase 9. Loading a new sensor resets the preferences.

### 4.4 Center: Contextual Stage View

The center column shows the **selected stage's view and nothing else**. Every stage view
is built from the same three sections, in order:

1. **Inputs** — the stage's editable parameters (the schema group for that namespace).
   Each edit is exactly one `sensor.set()` (§4.1, R-API), validated on a throwaway
   `sensor.clone()` before it touches the live sensor; each field carries its unit
   (R-UNITS). Derived parameters are ⚡-badged read-only, as in the left tree.
2. **Outputs** — the stage's read-only results from `stage_outputs["<stage>"]` (and, for
   Performance, the metric surface), every value with its unit and symbol.
3. **Plot(s)** — the stage's figure(s), drawn **only** from the public `result.plot.*`
   surface — one GUI action ↔ one API call, no plotting logic in GUI code (§1.2 R-API).

There is **no global metric-badge row and no shared canvas**: the performance metrics
that used to sit in the badge row now live in the right-rail *Pinned* panel (§4.5), and
each stage owns its own plot region. A metric that returns a result-typed failure (Rule 17
carve-out) shows its `failure_reason`, not a blank.

*As shipped (contextual-layout retrofit Step B, 2026-07-13).* `StageCenter` (a
`QStackedWidget` of one `StagePane` per stage over a pre-evaluate placeholder) replaces the
single-canvas swap. Each pane assembles the §4.4.1 composition from existing widgets: the
scalar-outputs readout (`OutputsReadout`, unit inferred from the stage-output key suffix),
the relocated `MtfPanel` (Optics) / `NoiseBudgetPanel` (Detector) / `GeometryReadout`
(Geometry), the `result.plot.*` plot sections, and the Performance metric readout. Every
figure is one `result.plot.*` call, guarded so an `ApiValidationError` (a frame absent for
the regime) shows its actionable message, never a blank (Rules 15/17). Selecting a stage
still navigates the left tree (the Phase-4A behaviour, preserved); the first evaluation
lands the center on the default stage (**Performance** — the grouped metric readout,
owner-slimmed 2026-07-25; the MTF figures live on the Optics MTF tab). Only **[exists]** surfaces are
built here; the **[GAP 89–92]** / bespoke items (Optics pupil & coating maps, the Source
pre-atmosphere emission spectrum, the per-λ noise spectrum, the Detector pie/illustration
and PSF-grid overlay) remain separate later per-stage tasks. Platform is v1-minimal
(owner-ratified, GUI plan Phase PS-5): editable schema-driven inputs (jitter/smear) beside
the outputs readout and a themed note — Platform carries no MTF; no bespoke invented
content. Readout began v1-minimal (read-noise/ADC/well) and was expanded per **Gap 102**
(owner request 2026-07-24) with the acquisition knobs — TDI (`n_tdi`/`tdi_mode`/
`tdi_misalign_pixels`), co-adds (`n_coadds`/`coadd_mode`), on/off-chip binning, and frame
timing (`readout.frame_period_s` beside the shared integration time; the derived
`frame_rate_hz`/`duty_cycle` appear in the Outputs readout) — plus the scalar noise budget.
`cds_enabled`/`node_capacitance_F`/`electronics_sigma_um` remain tree/YAML/scripting-only.

*Geometry Inputs section (shipped, GUI plan Phase 5, 2026-07-13).* The Geometry pane is the
first to realise the §4.4 **Inputs** section: above its `GeometryReadout` it embeds a
`GeometryModeForm` — the stage-0 **input-mode selectors** over the viewing / solar /
kinematics families and their modes V0–V4, S1–S3 + night, direct/circular. The family →
mode → parameter structure is owned by `radiant.geometry.mode_manifest` and read through
the public `radiant.api.geometry_modes` bridge (CU-120, the `metric_groups` precedent);
`radiant.gui.geometry_modes` keeps only the display wording (family titles, mode labels —
checked complete against the manifest at import) and the error→family highlight map. Each family carries a mode combo; only the **active** mode's
fields are editable, the rest disabled, so the user drives exactly one door per family
(ADR-0006 rule 1). The active mode is detected from **provenance** (mirroring
`radiant.geometry.modes`), never guessed. Every field is schema-driven (`Sensor.parameter_def`
— value/unit/bounds/editor), never transcribed (Gap 70); editing opens the shared
`ParameterEditorDialog`, so a commit is one `sensor.set` validated on a clone first (the
Phase-2 edit+reject discipline, actionable error inline) and the value shows in the row's
display unit (the same session store the parameter tree uses, shared by reference). The
`GeometryReadout` groups its derived angles by **reference frame** — *target-frame* (θ_o, θ_i,
θ_s, Δφ) vs *ground/platform frame* (η, slant/ground range, altitudes, ground speed, orbital
period) vs a *resolution* group (illumination + the three `*_mode` labels) — each value with
its unit and symbol, read verbatim from `stage_outputs["geometry"]`. When an evaluation raises
the stage's over-/under-specification `GeometrySpecificationError`, the window
(`_highlight_geometry_conflict`) maps the error's context to the offending family
(`implicated_families`), tints that selector, and jumps to the Geometry screen — a locator
only; the actionable what/why/action is still shown by the error dialog and the Messages
panel, and no geometry validation is invented GUI-side. The 3D scene viewer remains GUI plan
Phases 6–7.

*Tabbed sub-view hook (in production).* A stage may declare named **sub-views**; when two
or more are present, `StagePane` renders them as a `QTabWidget` (one scoped composite per
tab) instead of a single scroll pane, so a stage with substantial, separable content can
split it into tabs without a widget rewrite. The **Geometry** stage (Inputs | Schematic)
was the first to declare sub-views; the **Optics** stage (GUI plan Phase PS-2) is the first
*production* use of the full mechanism — four tabs (**Inputs | MTF | PSF + Pupil |
Throughput**) carrying the richest per-stage content (editable inputs + FINAL-regime
outputs, the MTF table + overlay + budget, the PSF + FP-2 complex-pupil maps, and the FP-3
throughput + coating spectra). The hook is the data seam (`StageComposition.subviews` of
`StageSubView`, `radiant.gui.stage_views`); a stage with zero or one sub-view falls back to
the single flat pane.

*Outputs pin affordance (Step B, CU-115 clause).* Each Outputs / Metrics row carries a pin
control (metric-card rows reveal theirs on hover — 2026-07-25 redesign; always-on pin
glyphs were visual noise). A stage-output pin adds a card that **re-reads
`stage_outputs[stage][key]` on each evaluation** (value + unit, R-UNITS); a metric pin
uses the existing metric-surface card path, labelled with the metric's human display label. This delivers the §4.5 "pin any stage's metric or output value" capability. Pin-set
persistence across sessions remains Phase 9 (CU-115, persistence clause).

**Metric surface (retained from the shipped badge row).** The five performance metrics —
SNR ← `snr`, NEDT ← `nedt_K`, NIIRS ← `niirs`, GSD ← `gsd_geometric_mean_m`, MTF@Nyquist ←
`mtf_at_nyquist` — and their **units sourced from `ChainResult.metric_records()`** (never
hardcoded) are unchanged; they are simply *relocated* from a fixed row into the pinnable
rail (§4.5) and the Performance stage view (§4.4.1). NEDT renders in its canonical unit
**K**; a per-metric display-scaling nicety (mK, µrad, …) remains CU-108. A pure ratio /
rating-scale unit (`dimensionless`, `NIIRS level`) renders as a bare number.

**Saturation banner (retained).** The full-well **saturation banner** (§7.2 row 8, owner
amendment 2) remains a persistent, non-dismissible banner shown whenever
`result.well_status().is_saturated`; it renders the well fill fraction (as a `×` multiple)
and the accumulated-versus-capacity charge in electrons (R-UNITS), and clears on the next
unsaturated result. It reads the `ChainResult.well_status()` surface (CU-101). In the
contextual layout it renders at the top of the center column (above the stage view) and,
for the well it describes, most naturally alongside the Detector/Readout stage views;
chain warnings and errors go to the right-rail *Messages* panel (§4.5), not a center strip.

#### 4.4.1 Per-Stage Content Spec (owner-ratified requirements, 2026-07-13)

The ratified per-stage content. Each item is classified **[exists]** (a real API/plot
surface backs it today — named), **[GUI-only]** (the data exists; the GUI reshapes/draws
it, no new framework capability), or **[GAP N]** (needs a framework capability that does
not exist — filed in `docs/tracking/gaps.md`). Plots marked [exists] are the shipped
`result.plot.*` accessors (`ResultPlotNamespace`: `mtf`, `noise_budget`, `psf`,
`mtf_budget`, `spectral_source`, `spectral_source_emission`, `target_reflectance`,
`spectral_reflected_radiance`, `spectral_atmosphere`, `spectral_inband`).

| Stage | Ratified content | Classification |
|-------|------------------|----------------|
| **Geometry** | Two tabs: **Inputs** (scene-class steering card + stage-0 input-mode forms + derived-angle readout) and **Schematic** (the 2D schematic viewer, §6) | **[exists]** The Inputs tab leads with the **scene-class steering card** (`SceneClassPanel`, Geometry-Flexibility Phase 4 / ADR-0011 decision 8): the **derived** class chip read verbatim from `stage_outputs["geometry"]` (`scene_class` + `observer_class`/`target_class`; a neutral placeholder pre-evaluate), the optional **`geometry.scene_class` assertion** (the mission-type entry point — a shared `FieldRow` + `ParameterEditorDialog`, one `sensor.set` per edit; asserting steers defaults and is validated against the derivation at the next evaluate), and the **relevance preview** — the metrics the displayed class turns off by default, read through the `radiant.api.scene_relevance` bridge (guardrail G3 — one declarative map, never transcribed GUI-side) with human labels from `metric_format`, plus the note that an explicitly-set `performance.metrics.*` group flag always wins (Gap 96 override semantics). An asserted-vs-derived `GeometrySpecificationError` tints the card in-context (`[state="conflict"]`, the `geoModeFamily` pattern) with the error's what-line beside the chip. Full per-input mission-type gating remains Gap 85. Below it: `GeometryModeForm` (mode selectors + schema-driven fields, one `sensor.set` per edit; labels re-worded direction-general per ADR-0011 — "Path zenith at lower endpoint (V1)", "Off-boresight angle (V2)", "Elevation angle, signed (V4)") + frame-grouped readout from `stage_outputs["geometry"]` (symbols + units, verbatim); over/under-spec errors highlight the offending selector. The **Schematic** tab embeds `GeometryViewer` (§6.9, incl. the Phase-4 up-looking/level compositions) |
| **Source** | Target radiance plot | **[SHIPPED — GUI plan Phase PS-1; retabbed by owner walkthrough items 5 + 6]** `result.plot.spectral_source_emission()` — draws the pre-atmosphere `at_source_target` frame (emitted+reflected radiance leaving the target, before the up-leg), persisted by AtmosphereStage. It is the Source stage's **primary** center plot. `spectral_source()` (at-aperture) is **no longer** shown on any Source tab: it is post-atmosphere, and the Atmosphere view owns that step |
| **Source** | Background radiance plot | **[SHIPPED — GUI plan Phase PS-1]** same accessor draws the optional `at_source_background` arm alongside the target |
| **Source** | Reflective view — ρ(λ) and the radiance it produces | **[SHIPPED — owner walkthrough item 6]** The *Target — reflective* tab is a surface-property instrument: `result.plot.target_reflectance()` (ρ(λ), dimensionless, from `stage_outputs["source"]["reflectance"]`) leads, with `result.plot.spectral_reflected_radiance()` (`frames["at_source_target_reflected"]`) beside it — cause and effect in one row. Both reflectance **input** surfaces are mounted: the scalar `source.target.reflectance` and the λ-dependent `source.target.reflectance_path` CSV (mutually exclusive; the engine's inferrer-time rejection reaches the operator through the actionable evaluate dialog + Messages, the surface every cross-parameter conflict uses). The three `geometry.solar_*` rows stay on the tab **read-only** (`FieldRow.set_read_only`) with the Geometry stage named as their owner — they explain a dark reflected term without offering a second editor for a Geometry-owned parameter |
| **Source** | Radiometric inputs (thermal + reflective + scene declaration) | **[SHIPPED — GUI plan Phase PS-1; expanded by GUI Capability Expansion plan GS-1]** `SourceInputsForm`, grouped: **Thermal** (target T/ε + `is_hot_target`), **Reflective (solar)** (`source.target.reflectance` + `source.target.reflectance_path` — pure-ρ T2 pathway, mutually exclusive with ε/T and with each other by engine design; the read-only `geometry.solar_illumination` day/night + solar zenith/azimuth mirrors), **Background & contrast reference** (T/ε pairs + `source.background.material` library name), **Scene type & regime** (`source.scene_type` declared + `source.regime_override` force + `fill_fraction`) — all shared `FieldRow`s, one `sensor.set` per edit; editing re-evaluates and the emission spectra + Outputs readout refresh. The ADR-0008 T2 declared-vs-derived warning surfaces in Messages. The `albedo` aliases stay tree-only (never invite an over-specified pair) |
| **Source** | Size / shape / orientation inputs — **relocated to Geometry** | **[MOVED — GT-0 (owner walkthrough 2026-07-16) / Windows-deployment finding 14]** Target extent/shape/orientation is geometry content post-TEG (`geometry.target.shape*`): the shared `TargetShapePanel` mounts on **Geometry → Schematic only** (nominal-dim seeding on shape-select, CU-125, applies there). The Source stage carries **no shape editor** — the earlier PS-1 duplicate was removed (Geometry is the single source of truth, geometry-first/Rule 10), and the composition vocabulary no longer has a `target_shape` section. The **per-scenario-type gating** (which inputs are relevant) stays deferred to **[GAP 85]** (mission-type relevance) — v1 shows all inputs, disabling only those a *declared* `source.scene_type` excludes (`regime:<type>` schema tags): the sub-pixel `fill_fraction` off outside sub-pixel, and (Gap 98 D) a **"Target — point source"** tab with the radiant-intensity inputs (`source.target.point_intensity_temperature_K`/`_area_m2`/`_emissivity`, `_band_W_per_sr`) enabled only for a `point_source` scene, with the surface-radiance (ε, T) rows disabled there (a point source is defined by intensity, not radiance × area) |
| **Source** | Tentative-regime + classification outputs | **[SHIPPED — GUI plan Phase PS-1]** `OutputsReadout` over `stage_outputs["source"]` — the tentative regime (`regime_tentative`, Rule 10) plus `projected_area_m2` (m²), `range_m` (m), `fill_fraction`, `angular_extent_rad` (rad), each with its unit (units from `api.stage_output_units`). The `reflectance` output is a ρ(λ) **array**, so it carries its unit on its figure axis and stays out of this scalar table (and out of the stage's `OUTPUT_UNITS` map) |
| **Atmosphere** | Model + propagation inputs (model selector, per-model knobs, turbulence r₀) | **[SHIPPED — GUI Capability Expansion plan GS-2]** `AtmosphereInputsForm` — the `atmosphere.model` selector (`simple`/`exo`/`tabulated`/`modtran`/`interpolated`) with **only the active backend's group visible** (simple: profile/aerosol/visibility/PWV; modtran: tape7 + sun-path tape7 + profile/aerosol/H₂O/O₃ scaling; tabulated: the three file params; interpolated: run-matrix dir/axes/method; exo: a themed note) + `atmosphere.r0_m`, as shared `FieldRow`s, one `sensor.set` per edit. File paths are string schema fields (the plan's file-picker fallback; the ADR-0009 D5 preview dialog is the follow-on). Editing re-evaluates and every plot below refreshes |
| **Atmosphere** | Scalar outputs readout | **[SHIPPED — GS-2]** `OutputsReadout` over `stage_outputs["atmosphere"]` |
| **Atmosphere** | τ_atm & L_path vs λ plot | **[SHIPPED]** `result.plot.spectral_atmosphere()` (twin-axis τ_atm + L_path — transmission loss and the path's own radiance separately visible) |
| **Atmosphere** | **Before** atmosphere — target & background emission | **[SHIPPED — GS-2]** `result.plot.spectral_source_emission()` (the pre-atmosphere frame, FP-1) shown beside the at-aperture plot so propagation reads as before/after |
| **Atmosphere** | **After** atmosphere — radiance at aperture | **[SHIPPED — owner walkthrough item 8]** `result.plot.spectral_at_aperture_arms()` — draws the `at_aperture_target` + `at_aperture_background` frames on one axis, per arm (the at-aperture radiances the owner wants shown here now that atmosphere is applied). This is the **only** place the GUI shows an at-aperture radiance; `spectral_source()` remains a scripting accessor over the same frames but is mounted on no view (row corrected 2026-07-27 — it named the pre-item-8 accessor) |
| **Optics** | Element-train editor (per-element R/T/temperature/geometry, ε derived) | **[SHIPPED — GUI Capability Expansion plan GS-4]** `OpticalElementEditor` in the Optics **Elements** tab — the ADR-0009 D2 declarative-document editor: table rows ⇌ the `optical_elements:` entry dicts (R/T cells take a scalar or a spectral-CSV path); *Apply* = one `Sensor.set_optical_elements` call (io-parser validation, Kirchhoff checks; a rejection shows the actionable dialog and never touches the live sensor); the ε column is **derived read-only** (Rule 5 — 1−R mirrors, cavity/zero refractive, from `preview_optical_elements`); the attached train persists through `Sensor.save`/`load` (ADR-0009 D4) and the optics stage runs full-prescription on the next evaluation |
| **Optics** | MTF | **[SHIPPED — GUI plan Phase PS-2]** `result.plot.mtf()` overlay + the per-term MTF@Nyquist table (`MtfPanel`) + the `mtf_budget()` bar, in the Optics **MTF** tab |
| **Optics** | PSF | **[SHIPPED — GUI plan Phase PS-2]** `result.plot.psf()` (`stage_outputs["optics"]["effective_psf"]`), in the Optics **PSF + Pupil** tab |
| **Optics** | Pupil apodization (amplitude map) | **[SHIPPED — GUI plan Phase PS-2]** `result.plot.pupil_amplitude()` (Gap 89 closed, FP-2) — the dimensionless transmission across the complex pupil (obscuration + spiders), in the **PSF + Pupil** tab |
| **Optics** | Pupil wavefront-error (phase) map | **[SHIPPED — GUI plan Phase PS-2]** `result.plot.pupil_phase()` (Gap 89 closed, FP-2) — the WFE map in **waves** (colorbar carries the unit; an unaberrated config renders flat, a non-zero `wfe_rms_waves` shows structure), in the **PSF + Pupil** tab |
| **Optics** | Coating performance & transmission spectra | **[SHIPPED — GUI plan Phase PS-2]** `result.plot.optical_throughput()` (system τ_opt(λ)) + `result.plot.coating_spectra()` (per-element R/T/ε) (Gap 90 closed, FP-3), in the Optics **Throughput** tab |
| **Optics** | Editable optics inputs + final regime | **[SHIPPED — GUI plan Phase PS-2]** `OpticsInputsForm` — aperture / focal length / f-number / obscuration / spiders / scalar throughput / WFE / optics temperature as shared `FieldRow`s (one `sensor.set` per edit, the edit+reject discipline), beside the FINAL-regime `OutputsReadout` (`stage_outputs["optics"]["regime"]`, Rule 10), in the Optics **Inputs** tab; editing re-evaluates and every tab refreshes (edit-and-watch) |
| **Platform** | Minimal for v1 (does **not** need MTF) | **[SHIPPED — GUI plan Phase PS-5, v1-minimal]** `PlatformInputsForm` — jitter RMS (isotropic + cross/along-track) under a *Jitter* heading and `ground_velocity_m_s` + `smear_length_um` under a *Motion & smear* heading, as shared `FieldRow`s (one `sensor.set` per edit, the edit+reject discipline), beside the scalar `OutputsReadout` (`jitter_sigma_x_m`/`jitter_sigma_y_m`/`smear_width_m` in m, `EE_box` fraction; units from `api.stage_output_units`) and a themed *v1-minimal* note; editing re-evaluates and the outputs refresh (edit-and-watch). No dedicated MTF view (owner-ratified — the smear/jitter MTF terms remain reachable in the Optics/Performance MTF overlay). Single flat pane. Platform/sensor **attitude** still has no stage owner (ADR-0006 §4 / CU-122, re-audited at PS-5; the target RPY triad ships from `source.target.*`) |
| **Spectral Integration** | Final plot of the signal spectral radiance | **[SHIPPED — GUI plan Phase PS-4]** `result.plot.spectral_inband()` (post-optics integrand frame) — the Spectral-Integration center's **primary** plot, above the scalar electron-budget `OutputsReadout` (`signal_e`, `e_rate_per_s`, `background_e`, `contrast_e`, `qe_scalar`, …, units from `api.stage_output_units`). Single flat pane (owner judgment) |
| **Spectral Integration** | Editable band + acquisition inputs | **[SHIPPED — GUI plan Phase PS-4]** `SpectralIntegrationInputsForm` — the filter bandpass edges (`spectral_integration.filter_min_um` / `filter_max_um`) under a *Filter bandpass* heading and `integration_time_s` under an *Acquisition* heading, as shared `FieldRow`s (one `sensor.set` per edit, the edit+reject discipline); editing the band re-clips the in-band spectrum and editing the integration time re-scales the electron budget (edit-and-watch) |
| **Spectral Integration** | Noise terms alongside the signal | **[exists (scalar)]** `result.plot.noise_budget()` — but noise is **scalar per term** (`NoiseTerm.value_e`, e- RMS, computed post-integration per Rule 8); a **per-wavelength** noise decomposition to show noise *as a spectrum* is **[GAP 92]**. The Spectral-Integration center carries a themed note pointing at the Detector view's noise budget so the deferral reads as intentional, not missing |
| **Spectral Integration** | `integration_time_s` grouping | **[SHIPPED — GUI plan Phase PS-4, GUI-grouping note]** — the owner notes `integration_time_s` feels mis-placed here. The GUI presents it under a separate **Acquisition** heading in the inputs card (distinct from the *Filter bandpass* edges); GUI grouping need not mirror the schema namespace. **No schema change** — the sensor path stays `spectral_integration.integration_time_s`. Relocating it to a dedicated cross-stage acquisition grouping is deferred (**CU-137**) |
| **Detector** | Editable detector inputs + outputs | **[SHIPPED — GUI plan Phase PS-3; expanded to the full schema by GUI Capability Expansion plan GS-3]** `DetectorInputsForm` — **every** `detector.*` ParameterDef as shared `FieldRow`s (a manifest-equals-schema test enforces completeness), grouped: pixel geometry & temperature; QE (scalar / `qe_table_path` CSV import / temperature coefficients); dark current & glow (Arrhenius); 1/f noise (K + band); G-R & Johnson; FPN (PRNU/DSNU/clutter σ/`noise_regime`); persistence (fraction/τ/prior signal); IPC & diffusion. One `sensor.set` per edit (the edit+reject discipline), beside the scalar `OutputsReadout` (`signal_e`, `dark_e`, …, units from `api.stage_output_units`), in the Detector **Inputs** tab; editing re-evaluates and every tab refreshes (edit-and-watch) |
| **Detector** | Detector illustration with size | **[SHIPPED — GUI plan Phase PS-3]** `DetectorIllustration` — a Qt-drawn, not-to-scale pixel schematic labelled with the pitch (`detector.pixel_pitch_x_um`/`pixel_pitch_y_um`, in µm) and `fill_factor`, drawn from the live parameters (like the geometry schematic; no framework plot needed), in the Detector **Detector + PSF** tab; editing the pitch/fill redraws it |
| **Detector** | PSF with detector/pixel-grid overlay | **[SHIPPED — GUI plan Phase PS-3]** `result.plot.psf_pixel_grid()` — `psf()` with the detector pixel grid overlaid (a `plot_psf(pixel_grid=True)` draw over `EffectivePSF.pixel_pitch_m`/`sample_spacing_m`, cropped to the PSF core, pitch µm in the title), in the **Detector + PSF** tab |
| **Detector** | Noise contributions as a **pie** chart | **[SHIPPED — GUI plan Phase PS-3, framework accessor]** `result.plot.noise_pie()` — the **primary** chart of the Detector **Noise** tab: a pie of `result.noise_terms` by **variance** share (σ_i²; noise adds in quadrature), each wedge labelled with its σ_i in e- RMS and % of variance. The ratified framework accessor (§8 decision 2), the pie sibling of the shipped `noise_budget()` bar; the per-term table + click-to-explain (`NoiseBudgetPanel`) sits alongside, the redundant bar suppressed |
| **Readout** | Minimal for v1 | **[SHIPPED — GUI plan Phase PS-5, v1-minimal]** `ReadoutInputsForm` — `read_noise_e_rms` under a *Read noise* heading, `gain_e_per_dn` + `adc_bits` under an *ADC* heading, `full_well_capacity_e` under a *Full well* heading, as shared `FieldRow`s (one `sensor.set` per edit, the edit+reject discipline), beside the scalar `OutputsReadout` (`signal_dn_final` DN, `sigma_total_e`/`total_well_e` e-, `well_fill_fraction`, …; units from `api.stage_output_units`), the scalar noise budget (`result.plot.noise_budget()` — read noise + quantization live in this stage), and a themed *v1-minimal* note; editing re-evaluates and the outputs + noise budget refresh (edit-and-watch). Single flat pane |
| **Performance** | Grouped metric readout | **[SHIPPED — GUI plan Phase PS-6; owner-shaped 2026-07-25 over two walkthrough rounds: the flat single-column readout read as a "wall of text"; the interim tabbed dashboard was then slimmed to just its All-metrics screen]** One flat pane: a compact **Compute:** toggle row (`PerformanceMetricsForm`, Gap 96: five checkboxes bound to the `performance.metrics.*` group flags; each toggle is one `sensor.set` + `parameterEdited`, and a deselected group stops its *computation*, not just its display) **ordered to match the card sections by construction** (both derive from `metric_format.METRIC_GROUP_HEADINGS` — geometry first, owner 2026-07-25), above the grouped metric cards (`MetricGroupCards`): one themed card per Gap-96 group in reading order — *Sampling / geometry*, *Spatial / MTF*, *Radiometric*, *Interpretability*, *Saturation* (+ a defensive *Other*) — two-up, every row a **human display label** (`metric_format.METRIC_DISPLAY_LABELS`, CI-checked to cover the taxonomy; never a raw registry key) with its registry unit (`ChainResult.metric_records()`, R-UNITS), rows in the table's physics order, pin affordances hover-revealed (§4.5 pin-any-metric retained). **No plots on this stage** (owner decision 2026-07-25): the system MTF and MTF budget live on the Optics **MTF** tab; plot tabs may return later via the sub-view hook (a data change). A **result-typed metric failure** (non-finite, Rule 17 carve-out) renders as `n/a (<failure_reason>)`, never a bare `nan`/blank. The metric-selection row is the only editable control (terminal stage). Presentation-only: the computed set and every value/unit are unchanged. **In a study (multi-configuration Phase 4d, §4.2e)** each card becomes a **metric × configuration matrix**: the same groups, the same rows in the same order, plus one column per configuration in **set order** with the selector band's accent chip on its header. Cells are **plain values only** (ADR-0010 D-9 — no delta, no best-mark), rendered by the same `metric_value_display` and so carrying the same registry units; `—` for a metric a configuration did not compute (Rule 17, never zero); a **failed** configuration keeps its column with a `✕` and the error's what-line on hover while the others keep their numbers; a configuration that warned gets a `⚠` pointing at its Messages entries. The cards lay out one-up in that mode. Values come from the retained `last_run` — rendering, including a selector switch, evaluates nothing. A **single-configuration** session renders exactly the pre-4d readout: no columns, no headers, no chips (tested) |

**Reading the spec.** Most of the ratified content **already has a backing surface** —
every plot the shipped `result.plot.*` carries (MTF, PSF, noise budget, and the three
spectral-radiance accessors) plus the metric/stage-output readouts. The genuinely new
framework work is concentrated in **Optics diagnostics** (pupil map, coating spectra) and
an optional **spectral noise decomposition** — Gaps 89/90/92, all view/accessor additions
over already-computed physics (no results change). The **Source pre-atmosphere emission
frame** (Gap 91) is closed and shipped in the Source stage instrument (GUI plan Phase
PS-1). The pie chart, detector schematic, and PSF-grid overlay are GUI-only reshapes; the
per-scenario-type input gating rides on the still-deferred Gap 85.

### 4.5 Right Rail (persistent): Pinned · Edit Config · Messages · Evaluate footer

A persistent right column, always visible regardless of the selected stage. Three
sections plus a pinned footer, top to bottom:

**Pinned.** User-pinnable value cards. The user can pin **any** stage's metric or output
value (via `+ pin a value` / the value's pin affordance); each card shows the label, the
value with its unit (R-UNITS), and the source stage. The **default pinned set** is the
five performance metrics — **SNR · NEDT · NIIRS · GSD · MTF@Nyquist** — so the summary the
old badge row provided is present on launch, now movable and extensible (badges → pinnable
cards). Cards read the same `ChainResult` metric / `stage_outputs` surfaces as before.

*Step-A delivered scope (retrofit 2026-07-13):* the default set ships, plus a `+ Pin…`
action that pins **any metric on the result surface** (`ChainResult.metric_records()`) via
a small picker. Pinning an arbitrary intermediate `stage_outputs` value is deferred to
Step B, where each per-stage center view carries a natural in-place pin affordance
(**CU-115**). The pinned set is **session-scoped** (a list on the rail); persisting it
across sessions via `QSettings` is Phase 9 (also CU-115). A failed / absent metric shows
its `failure_reason` (Rule 17 carve-out), never a blank.

**Edit Config (YAML) button.** A button that opens a **roomy modal editor** of the full
**document** — since Phase 4e the whole study when the session is one, `configurations:`
section included, and exactly today's single-config text when it is not (§4.2f decides
which, once, for this modal and for Save alike). **Apply re-parses the edited text through
the framework** (`ConfigurationSet.load`, the one reader that takes both document kinds);
**invalid YAML → an actionable error and the document is left unchanged** (the live
document is never corrupted — the edit is parsed on a throwaway first, exactly the §4.1
validate-before-commit discipline), and a section violation's error already names the
configuration and the parameter. This is the relocation of the shipped read-only YAML tab
into an editable modal. As shipped, the serialized text is the **inputs** scope and there
is no resolved-scope serialize surface (**Gap 88**); the modal shows the inputs scope until
that lands.

**Messages.** Warnings and errors, replacing the old floating warning strip. Chain
`UserWarning`s (saturation clip, NIIRS extrapolation, …) are captured by
`ConfigurationSet.evaluate_all` (`warnings.catch_warnings(record=True)` +
`simplefilter("always")` per configuration, so the process-wide filter cannot suppress
them and none is deduplicated — §3.2) and delivered with the result; the panel reads
`⚠ N warnings` with the first inline and, clicked, lists every message verbatim (the
shipped `WarningListDialog`). Captured warnings are also re-logged, so nothing is
swallowed (Rule 17). **Errors surface here too**: a `RadiantError` renders its actionable
**what / why / action** (Rule 15), and clicking opens the full message. This is the
warning strip relocated and widened to carry errors as well as warnings.

*Multi-configuration attribution (Phase 4a).* In a study, each warning is prefixed with
the configuration that raised it (`LWIR: UserWarning: …`) so a per-band effect never reads
as a property of the whole study; a **single-configuration session shows the bare text it
always showed**. A configuration that failed while it was **not** the displayed one is a
named error row (`MessagesPanel.set_configuration_failures`) and raises **no modal** — the
rest of the study keeps evaluating and the operator is not interrupted for a configuration
they are not looking at. A failure in the **displayed** configuration takes the ordinary
modal + stale-result path unchanged; the wrapper `ConfigSetError` is unwrapped first, so
the operator sees the underlying physics error exactly as before.

*Step-A saturation-banner placement (retrofit 2026-07-13):* the generic chain warnings
move into this Messages panel, but the full-well **saturation banner stays in the center**
column (§4.4, "renders at the top of the center column"). It is deliberately **not** folded
into the Messages list — it is high-signal and non-dismissible (three scenarios lost time
to silent clipping, Gap 65 / CU-101), so it keeps its own prominent strip rather than
becoming one err item among many.

**Evaluate (F5) footer.** The accent **Evaluate** button is a **rail footer** pinned at
the **bottom-right** of the right rail (owner feedback 2026-07-13 — the run action belongs
in the persistence area at the bottom-right, not floating in a center run bar). It sits
below the stretchy Messages panel, so it is always visible and never scrolls away. F5 and
the **Run ▸ Evaluate** menu action drive the same evaluate slot; the button carries the
`#runButton` accent style and is enabled only once a sensor is loaded. The earlier center
run bar (Step-A) is removed.

### 4.6 Global Inspector Tool

The full `result.inspect()` variable dump — every intermediate value across the whole
chain — is a **global tool** on the menu/toolbar (`◈ Inspector`), not a docked tab. This
is the old Variable Explorer tab promoted to a global tool: it renders
`radiant.api.inspect.inspect_result(result)` as a collapsible tree (wrapped NumPy reprs
folded per **CU-113**). The convenience method `result.inspect()` still does not exist on
`ChainResult` — the tool calls the module-level `inspect_result` (the real public surface);
the sugar accessor remains **Gap 87**.

*As shipped (Step B, 2026-07-13).* The `InspectorDialog` is reachable from **Tools →
Inspector** (`Ctrl+I`) and the wireframe's right-aligned menu-bar `◈ Inspector` button;
both trigger the same action, which is **disabled until the first evaluation** (nothing to
dump) and opens **non-modally** against the most recent result so the operator can keep
working with it open.

### 4.6.1 Scripting Window (separate window — Editor + Command Window + Workspace)

*As shipped (Pass 1 + Pass 2, owner-ratified 2026-07-15).* The MATLAB-style scripting
environment is a **separate top-level window** (`ScriptingWindow`, title "RADIANT Scripting") —
not a dock inside the main window — so the operator can move it to a second monitor. It is a
**global tool**, launched from **Tools → Scripting Window** (`Ctrl+Shift+P`); the action is
enabled once a sensor is loaded (nothing to bind before that), and re-triggering
**raises/focuses the single existing instance** rather than spawning a duplicate. It
**replaces the earlier bottom-dock console** (the retired `consoleDock` / `_toggle_console` /
View-menu toggle are gone; Rule 27). The shortcut is `Ctrl+Shift+P` (⌘⇧P on macOS) rather than
the earlier ``Ctrl+` ``: Qt maps portable "Ctrl" to the macOS Command key, so ``Ctrl+` ``
became ⌘` — an **OS-reserved** shortcut (cycle windows of the active app) that never reached
the app, so the console would not open on macOS (owner report 2026-07-15).

The window is **complete** as of Pass 2: all three vision panes ship, in an outer vertical
splitter with the **Editor** on top and the Command Window + Workspace row (a horizontal
splitter, Workspace left, Command Window right) below.

* the **Editor** (top/main pane, Pass 2) — a multi-tab Python `ScriptEditor` (a `QTabWidget` of
  `ScriptTab` code panes) for authored, saved, re-runnable scripts. Several `.py` scripts open
  at once; each tab shows its file name and a trailing `*` while it has unsaved edits. A File
  menu + toolbar give **New / Open / Open Recent / Save / Save As** over plain `.py` text
  (`Ctrl+N/O/S`, `Ctrl+Shift+S`) — **not** `Sensor.load`, since scripts are source, not configs;
  the recent-scripts list persists via `SettingsStore` and is kept distinct from the config
  recent list. Source is syntax-highlighted from the theme's `syntax_*` tokens. **Run** (F5 /
  `Ctrl+Return`, or the toolbar button) executes the active tab's full text, and **Run
  Selection** (`Ctrl+Shift+Return`) executes the selected lines — both through the Command
  Window's `ScriptingConsole.run_script`, i.e. **in the same shared namespace** the command line
  and Workspace use. A script's top-level `x = result.snr()` therefore leaves `x` bound for the
  next command line and visible in the Workspace; stdout/stderr and any traceback route into the
  Command Window transcript (surfaced, never swallowed — Rule 17); and a `sensor.set(...)` in a
  script marks the GUI stale exactly like a typed command (the shared coherence path). A bad
  file load surfaces the actionable/traceback error dialog and leaves the open tabs intact.
  **Run auto-displays top-level bare expressions**, exactly as the command line does: `run_script`
  parses the source once and executes it one top-level statement at a time, compiling each bare
  expression statement (an `ast.Expr` — e.g. a lone `plot.mtf()` or `result.snr()`) in interactive
  `"single"` mode so its value fires `sys.displayhook` (a Figure pops out into its own window, any
  other value echoes its `repr`, `None` stays silent) and every other statement in `"exec"` mode.
  So a bare `plot.mtf()` on its own line pops its figure with **no** `show()` / `sys.displayhook(...)`
  wrapper — the MATLAB "run a script, see the plots" behaviour — while the explicit
  `sys.displayhook(fig)` pattern still works unchanged. Statement order and side effects are
  preserved; a runtime exception halts the run at the offending statement (like a standalone script)
  and surfaces its traceback (Rule 17).
* the **Command Window** — the reused `ScriptingConsole` REPL (unchanged; the binding,
  history, figure pop-out, and coherence model below are all the dock console's logic hosted
  in the new window); and
* the **Workspace** — a `WorkspacePanel` live variable browser of the command namespace: a
  table of each variable's **name**, **type**, and a short **value / size** summary
  (`sensor: Sensor`, `result: ChainResult`, `x: ndarray (500,)`, `snr: float 616.0`). It
  refreshes after each executed command / Editor Run (the console's `commandExecuted` signal)
  and after every evaluate/refresh (a result re-bind outside a command). Selecting a variable
  shows a fuller **detail** dump below the table — the full `inspect_result` tree for a
  `ChainResult`, else the value's `repr`. This is related to but distinct from the global
  Inspector (§4.6), which dumps one result; the Workspace lists the whole live namespace.

**Theme.** The design-system stylesheet is installed app-wide on the `QApplication`
(`apply_theme`), so this separate top-level window is themed automatically and the View-menu
light/dark toggle re-themes it in step. The one exception is the Editor's syntax-highlight
glyph colours (a `QSyntaxHighlighter`, outside QSS's reach): the toggle calls
`ScriptingWindow.set_theme` to re-apply them. No visual literal lives outside `themes/`.

**Live-object binding.** The console namespace carries live references: `sensor` (the
window's live `Sensor` — the *same* object the parameter tree edits, so a `sensor.set(...)`
in the console and a tree edit both mutate one object; in a study it is the displayed
configuration's materialization, §4.2b), **`configs`** (the live `ConfigurationSet` — the
session *document*, the same object the selector, the configuration manager, and Save write
through, multi-configuration Phase 4e §4.2f; a plain session binds the degenerate set, whose
`configs.base is sensor`), `result` (the most recent `ChainResult`, re-bound after every
evaluation), `plot` (`ResultPlotNamespace(result)` — the public `result.plot.*` figure
surface, since `ChainResult` carries no `.plot` property, Gap 87), plus the conveniences
`inspect_result` (Gap-87 sugar for `result.inspect()`) and the classes `Sensor` /
`ConfigurationSet` (so a script can rebind either name).

**REPL, not qtconsole (CU-138).** The plan prefers a `qtconsole` in-process Jupyter kernel,
but explicitly sanctions a plain REPL over `code.InteractiveConsole` if qtconsole proves
fragile or untestable offscreen. It is both (the module is not installed here and an
in-process kernel under the `offscreen` QPA is hard to exercise headlessly), so v1 ships the
sanctioned REPL fallback — same binding, same coherence model, fully testable offscreen. The
`qtconsole` pin stays in the `gui` extra; restoring the kernel path is CU-138.

**Figures.** A command that evaluates to a matplotlib `Figure` (e.g. `plot.mtf()`) is
**popped out into its own window** (a `FigureCanvasQTAgg` in a top-level dialog) rather than
rendered inline — dependency-light and backend-agnostic. The console keeps references so the
windows are not garbage-collected and closes them on teardown.

**GUI ↔ console coherence (explicit, not magic).** A console command can mutate `sensor`
or `configs` behind the GUI's back. After such a command the console raises a visible
**"console changed state — Refresh"** banner and the window echoes the staleness
(stage-health dots → stale + status bar); the one-click **Refresh** *adopts the console's
current document* — `configs` — covering an in-place edit anywhere in it (`sensor.set(...)`
on a plain session's base, `configs.set_value(...)` on one configuration's column,
`configs.add(...)` on its membership; detected via the named mutation surface, §3.1 and
§4.2f) and a full rebind of either name (a new object, detected by identity) — re-reads it
into the selector, parameter tree, and input forms, and re-evaluates every configuration. A
study is never collapsed to its displayed configuration. A fresh evaluation clears the
stale state. There is no live-sync (GUI plan Phase 8 — "explicit and honest beats magic
sync").

### 4.7 What the Redesign Relocates (the dissolved detail tabs)

Nothing built in Phases 1–4 is discarded; the bottom detail tabs and the global badge row
are **relocated**, not removed. Precise mapping:

| Shipped component (old layout) | New home (contextual layout) |
|--------------------------------|------------------------------|
| Global metric-badge row (SNR/NEDT/NIIRS/GSD/MTF@Nyq) | Right-rail **Pinned** cards (default set) + the **Performance** stage view (§4.4.1) |
| Floating chain-warning strip | Right-rail **Messages** panel (now carries errors too) (§4.5) |
| **Spectral** detail tab | **Source / Atmosphere / Spectral Integration** center views (the spectral accessors) (§4.4.1) |
| **MTF** detail tab | **Optics / Platform / Performance** center views (`mtf`, `mtf_budget`) (§4.4.1) |
| **Noise Budget** detail tab | **Detector / Readout** center views (bar/pie of `noise_terms`) (§4.4.1) |
| **Variable Explorer** detail tab | **Global Inspector** tool (§4.6) |
| **YAML** detail tab (read-only) | Right-rail **Edit Config (YAML)** modal (now editable, re-parsed via `Sensor.load`) (§4.5) |
| **Console** tab | **Global tool** — the Command Window of the separate scripting window (§4.6.1, Pass 1), reachable from Tools → Scripting Window (`Ctrl+Shift+P`). A REPL over `code.InteractiveConsole` (CU-138), not qtconsole; the earlier bottom-dock host is retired (Rule 27). |

The per-tab data sources that shipped (Phase 4 Task B) are unchanged; each is re-hosted in
its new container. The Sweep tab remains **v1.1** and absent from v1 (D4). The migration of
the GUI Development Plan phases to this arrangement is the pending plan-revision task noted
in the header.

*As shipped (Step B, 2026-07-13).* The relocation is complete: the `DetailTabs` dock and
its `SpectralTab` / `MtfTab` / `NoiseBudgetTab` / `VariableExplorerTab` / `YamlTab` widgets
are deleted. `MtfTab` → `MtfPanel` and `NoiseBudgetTab` → `NoiseBudgetPanel` (embedded in
the Optics / Detector center views, §4.4.1); the Spectral tab's figures became per-stage
plot sections; the Variable Explorer became the global `InspectorDialog` (§4.6); the
read-only YAML tab was superseded by the Step-A right-rail Edit Config (YAML) modal (§4.5).
Nothing user-facing was lost — every surface has a new home in the contextual layout.

---

## 5. Interoperability: GUI ↔ Scripting API ↔ YAML

All three representations (GUI, Python script, YAML file) are views of the same `Sensor`
object and are interchangeable at any point.

**GUI → YAML.** File → Export YAML calls `sensor.save(path)` (Gap 67). The saved YAML
holds the explicitly-set inputs plus a `_radiant` metadata block; defaults and derived
values are not written, so a reload reproduces the original resolution and provenance
splits exactly (`RADIANT_Config_Format.md` §1.7). For a fully-resolved documentation
export, `radiant.io.config.save_config(params, path, scope="resolved")`.

**YAML → GUI.** File → Open YAML calls `Sensor.load(path)` (Gap 67). Provenance badges
distinguish explicit values from defaults and derived values. GUI edits override in the
highest-priority layer (equivalent to CLI `--set`).

**Script → GUI hand-off.** The v1 entry point is a module function, not a `Sensor`
method:

```python
from radiant.gui import launch_gui   # lands in GUI plan Phase 1
s = Sensor.load("config.yaml")
s.set("sensor.optics.aperture_diameter", 0.35)   # operating point of interest
launch_gui(s)                                     # opens the GUI on the current state
```

> The prior draft referenced a `sensor.gui()` convenience method; **no such method
> exists on `Sensor`** and none is planned for v1. The ratified entry point is
> `launch_gui(sensor: Sensor | None)` (GUI plan §4.2). A `Sensor.gui()` sugar wrapper,
> if ever added, is out of v1 scope.

**GUI → script hand-off.** In the scripting window's Command Window (§4.6.1, the separate
global tool) `sensor` and `result` are live references to the current GUI objects; any scripting-API call
works. After a console mutation the GUI marks its state stale (the console's Refresh banner +
stale stage dots) and one-click Refresh adopts the console's `sensor` and re-reads it
(explicit-and-honest beats magic sync; GUI plan Phase 8).

---

## 6. Geometry Viewer Panel (v1, GUI plan Phases 6–7)

The Geometry Viewer is the Geometry stage's central visualization: a spatial schematic
of the sun/sensor/target relationship, optimized for understanding the angles that drive
the downstream radiometry. It is **not** a flight visualizer or a Cesium-style globe —
it is a CAD / engineering-drawing view: line-art forward, schematic, every element
labeled. Condensed from
`dev_tools/gui_mockups/geometry_viewer/radiant_geometry_handoff.md`.

> **Engine (updated 2026-07-14 — ADR-0007 superseded):** the viewer is a **2D orthographic
> Qt schematic** drawn with `QPainter`, porting the mockup's `geometry.js` projection —
> **not** the PyVista/VTK render of D5. The VTK raster could not match the mockup's crisp
> antialiased SVG line-art; a pure-Qt 2D canvas reproduces it faithfully with **no** VTK/
> OpenGL dependency. **Pass 1** (shipped) is the renderer core: `viewer/projection.py`
> (ported projection + direction math) and `viewer/schematic_view.py` (the `SchematicView`
> canvas), with `GeometryViewer` reimplemented over the canvas and the Geometry center tab
> renamed **"3D View" → "Schematic"**. **Pass 2 (shipped)** added the angle arcs + degree
> labels (CU-128), the altitude leader labels (CU-129), the RPY triad (CU-130), the full
> shape library + per-shape dimension inputs (CU-131), and the angle-truth consistency test
> (CU-133), and **removed** the retired lifted VTK scene library (CU-132 — only the
> allowlisted glyph `palette` survives). The complete shipped viewer is described in **§6.9**;
> §§6.7–6.8 describe the retired PyVista Part A/B and are retained for history; §6.1–6.4
> (not-to-scale, contents, stage-as-angle-truth, conventions) hold for the 2D schematic. The
> `ViewerState` adapter (§6.7) is reused unchanged.

### 6.1 Not-To-Scale Rule (owner-endorsed, binding)

**Altitudes and distances are annotated via leader labels; the geometry is never
rescaled or translated to fake proportionality.** A 500 km slant range and a 2 m target
are not drawn to relative scale — the true angles are preserved and the magnitudes are
shown as leader-label text (owner-endorsed convention from `geometry_gui_v2`). Resist
applying PBR materials or realistic shading; keep the schematic line-art aesthetic.

### 6.2 Contents

- 3D schematic viewport with orbit / pan / zoom (standard mouse drag / shift-drag / wheel).
- Sun, sensor, target glyphs on a faint two-tone reference ground grid (reference, not
  measurement).
- **Vectors:** sun→target (day scenes); sensor→target (always on); and, **only in a
  down-looking scene with an elevated target** (target altitude > 0), **sensor→ground**
  (blue, dashed) and **sun→ground** (amber, dashed, day scenes), both landing at the
  target's **ground projection** G_i (the nadir footprint directly below the body on the
  ground plane) — a ground target has target == ground, so these are degenerate and absent
  (owner request 2026-07-14). The pair is likewise **omitted for the ADR-0011 up-looking
  and level compositions**: looking up or along, the LOS never terminates on the ground and
  the footprint below an air/space target is not a scene participant, so drawing them would
  assert a ground interaction the scene does not have. The legend rows match what is drawn.
- **Composition keyed by the stage-derived `los_direction`** (Geometry-Flexibility Phase 4,
  ADR-0011 decisions 1/8 — read verbatim from `stage_outputs["geometry"]`, never re-derived):
  the original **down-looking** layout (bit-identical to pre-Phase-4, proven by a pinned
  regression test and a byte-identical render-parity check); an **up-looking** layout in
  which the SENSOR is the path's lower endpoint — sitting *on* the ground plane for a
  `ground` observer class, lifted to the fixed abstract off-ground height otherwise — with
  the target carried above it along the θ_o ray so the SENSOR→TARGET vector ascends; and a
  **level** layout with both endpoints at the one fixed abstract height (LOS horizontal).
  All placements are fixed abstract scene units (§6.1); the scene class places the ground
  plane and nothing else. The **h_t altitude pill** keeps the original airborne-only rule
  for down-looking and is always shown for up/level (both endpoints are drawn apart, so
  both magnitudes are annotated — including a surface-level arm's 0 m). **Level arms** add
  the **Δh tangent-sag leader pill** ("Δh  49 m"): the LOS's tangent-height depression,
  invisible in a not-to-scale drawing, computed from the stage's θ_o + endpoint altitude
  through the core horizon-guard classifier
  (`radiant.core.viewing_triangle.classify_horizon_topology`) — the schematic never
  restates the formula, so the pill and the guard cannot disagree.
- **Night scenes** (`geometry.solar_illumination = "night"`, owner bug 2026-07-18): the
  geometry stage publishes θ_s / Δφ as `None` — there is no sun — so the schematic drops
  the sun glyph, both sun vectors, the sun drop lines, the sun legend rows, and every
  sun-derived angle annotation (θ_s, Δφ, phase) rather than fabricating angles. The
  sensor/target/zenith geometry renders unchanged (`ViewerState.has_sun` /
  `SchematicScene.has_sun`).
- **Click-to-reveal angle annotations**, split by frame:
  - *Target-frame* (anchored at the target): θₛ, θᵥ, φₛ, φᵥ, Δφ, phase angle g.
  - *Ground-frame* (anchored at G_i, the radiometrically-relevant point when target
    altitude > 0): θₛ_g, θᵥ_g, φₛ_g, φᵥ_g.
- Target shape library: extended scene, plate, box, sphere, cylinder, cone, circle,
  ellipsoid, point source, custom-mesh placeholder. The shared **Target shape** panel
  (`TargetShapePanel`, mounted on the Geometry Schematic tab only — GT-0 / finding 14
  removed the Source-instrument duplicate) shows the
  selected shape's dimension subset **or**, when the shape is `none`, a scalar **Projected
  area** field (`geometry.target.projected_area_m2`) — never both (they are the two
  mutually-exclusive ways to size the target; the engine's shape-wins precedence is the
  backstop for raw configs that set both).
- **Projected-area leader pill** (CU-168): when the target is sized only by
  `geometry.target.projected_area_m2` (shape library = "none", so no wireframe body is
  drawn — just a point marker), a leader-label pill by the target reads
  `A_t  <area> m²  ·  <n> px`, where the pixel multiple is the angular extent (√A / range)
  over the detector IFOV — the sub-pixel-vs-resolved cue. Same not-to-scale idiom as the
  h_s / h_t pills (§6.1); read verbatim from `stage_outputs["source"]`
  (`projected_area_m2` / `angular_extent_rad`) via `ViewerState` /
  `SchematicScene.target_area_label`. Without it a defined target area was visible only in
  the parameter tree, so the schematic read as "no target size defined".
- Target body-frame **RPY** (roll/pitch/yaw) with an on-target triad gizmo for 3D shapes
  (color-coded pink=Roll, green=Pitch, purple=Yaw).
- Right-side accordion side panel: live numeric readout of all angles (every value with
  units, R-UNITS); sun/sensor/target editors.

### 6.3 Stage Is the Single Source of Angle Truth

The viewer renders angles taken from `stage_outputs["geometry"]`. The ported
`geometry.js` math is used **only** for camera / projection / picking — never as a second
angle authority. A consistency test asserts viewer-local recomputation agrees with stage
outputs to an explicit tolerance; divergence is a red build (GUI plan Phase 7). This
keeps R-API intact: the panel is a view over stage outputs, not a re-implementation.

### 6.4 Interaction & Visual Conventions

**As shipped, reveal is driven from an on-canvas overlay** — the mockup's "click a vector
in the scene" is realized as a per-angle **toggle checkbox**. Owner feedback 2026-07-14
moved this **angle-arc selector out of the right-column accordion and onto the plot** as a
compact **bottom-left overlay** (`AngleToggleOverlay`, `viewer/angle_overlay.py`) that
mirrors the QPainter **VECTORS** legend at top-left — a real child `QWidget` parented to the
`SchematicView` canvas, absolutely positioned bottom-left and repositioned in the canvas
`resizeEvent`. Toggling an angle reveals its arc + the stage-output value pinned beside it.
The "show orientation triad" checkbox stays in the accordion's shape page; toggling it shows
the on-target RPY gizmo. Editing a side-panel shape or RPY value performs the one
`sensor.set` and updates the scene. (The offscreen test suite exercises the overlay
checkboxes directly; in-scene VTK point-picking + the lifted `highlight.py` re-stroke need a
live interactor and are deferred, CU-124.)

The right-column side panel is a `QToolBox` accordion with a **Geometry inputs** page (the
reusable Phase-5 `GeometryModeForm`) and a **Target shape & orientation** page. The Target
page is built from the **same** parts as the Inputs page — `geoModeFamily` cards holding a
`geoModeSelector`-styled shape combo and the shared `FieldRow` (label + value button) for
each dimension and RPY value — so the two pages are visually indistinguishable (owner
feedback 2026-07-14), plus a triad toggle. The angle-arc reveal toggles are **not** in the
accordion — they are the on-canvas bottom-left overlay above.

Color roles (domain glyph palette, distinct from the app chrome palette): sun = amber,
sensor = cyan, phase/azimuth = magenta, zenith = neutral, ground/projection = faded
amber/cyan. Stroke weights: main vectors ≈ 1.6 px, arcs ≈ 0.9 px dashed, reference axes
≈ 0.7 px dashed. Label boxes: monospace 10 px, fill rectangle with a thin stroke in the
arc's color. The panel follows the §8 design-system tokens (background, accent, label
typography) so it does not read as a different app embedded in the window.

### 6.5 Out of Scope for v1 (handoff Phase-2 polish)

Painter's-algorithm depth ordering, hidden-line treatment, curved-Earth toggle, ruler
ticks on vectors, hover-preview of angles, view presets, mini compass/sun rose,
persistent radiometric callout card, time-stepped orbit animation, real satellite-mesh
rendering. These stay out of v1 (GUI plan §8 risk register).

### 6.6 Degradation

**As of the 2026-07-14 2D pivot the three-backend ladder is gone — this is a win.** A
pure-Qt `QPainter` canvas has no VTK/OpenGL dependency, so it renders anywhere Qt runs
(including the headless `offscreen` platform) and there is no segfault-prone live
interactor. The viewer is therefore **always available** (`mode == "schematic"`); a
**minimal** guard remains — if building the scene from a result raises, an actionable
`"Geometry schematic unavailable: <reason>"` panel replaces the canvas (Rules 15/17) — but
for a pure-Qt widget this is effectively unreachable. Viewer tests grab the canvas
offscreen via `QWidget.grab()`, fully faithful.

*(Retired: the pre-pivot PyVista viewer resolved one of three backends — live
`pyvistaqt.QtInteractor` / offscreen `pyvista.Plotter` image in a `QLabel` / unavailable
panel — because embedding VTK needs a real display and constructing a `QtInteractor` under
the Qt `offscreen` plugin segfaults. The 2D canvas removes that whole class of fragility.)*

### 6.7 Part A — What Shipped (static scene + vectors; GUI plan Phase 7 Part A)

Part A (this phase) delivers the **static** bound scene; the interactions in §6.4 and the
shape library / RPY triad in §6.2 are **Part B**. What shipped:

- **Scene library lift.** The `dev_tools/geometry_gui_v2/scene` subset needed for a static
  scene is lifted verbatim (path-rewritten) into `radiant.gui.viewer.scene`: the layout /
  camera / framing / lighting / display-distance / direction helpers, the ground, target
  shapes, four vectors, sun/sensor/background glyphs, regime overlays, and the leader-label
  layer. The angle-arc modules (`arcs/`), the RPY body-axes triad (`frames/`), and the
  corner widgets (`widgets/`) are **not** lifted — they return with Part B. The lifted
  library imports no Qt and no physics stage (import-linter: gui → api + core; the scene
  reads a `ViewerState`, not `radiant.geometry`).
- **`ViewerState` adapter** (`radiant.gui.viewer.viewer_state`) — a frozen dataclass with
  the prototype `SceneState` field names, built from a `ChainResult` + the live `Sensor`
  via `ViewerState.from_chain_result`. Field mapping (ADR-0007 §2): `observer_altitude_m ←
  h_sensor_m`, `observer_look_angle_rad ← eta_rad`, `target_altitude_m ← h_target_m`,
  `solar_zenith_rad ← theta_s_rad`, `relative_azimuth_rad ← delta_phi_rad`, `regime_override
  ← stage_outputs["optics"]["regime"]` (Rule 10), shape/dims ← `source.target.*` params,
  `focal_length_m ← optics.focal_length_m`, `pixel_pitch_m ← detector.pixel_pitch_x_um`
  (canonical m). Platform attitude has no stage owner (ADR-0006 §4 / CU-122), so
  `observer_{yaw,pitch,roll}_rad` default to zero — the RPY triad that would render them is
  Part B.
- **Color split for theme integration.** Semantic *physics-domain glyph* colors (sun =
  amber, sensor = blue, surface normal = green, target = teal) live in the one documented
  allowlisted module `radiant.gui.viewer.scene.palette` (ADR-0007 §3/§8.5, exempted from
  the §4.9 token-discipline test). Theme-bound *chrome* (viewport background, leader lines,
  label pill) is resolved from the active `Theme` via `radiant.gui.viewer.scene.chrome` and
  holds no literal, so the Phase-9 theme toggle restyles the viewport.
- **Mount.** The Geometry stage center is a two-tab composite (the §4.4 sub-view hook):
  **Inputs** (mode forms + `GeometryReadout`) and **3D View** (the `GeometryViewer`). The
  viewer re-renders the static scene after each evaluate.

### 6.8 Part B — What Shipped (interactions; GUI plan Phase 7 Part B)

Part B adds the interaction half over the Part-A static scene. The 3D View tab is now a
split: the viewport (left) and the accordion side panel (right).

- **Click-to-reveal angle annotations.** The angle-arc modules (`scene/arcs/` — off-nadir
  η, sun-zenith θ_s, phase-angle α_t) are lifted; each reveals on demand a curved arc tube
  plus a pinned value label. The **value comes from `stage_outputs["geometry"]` verbatim**
  (`eta_rad`, `theta_s_rad`), formatted with its unit exactly as the readout formats it —
  never recomputed from the scene. The phase angle has no stage-output truth, so it renders
  **symbol-only** (arch §6.3), analogous to the Rule-4 MTF-only TDI term. The catalog of
  annotatable angles (`scene/angle_annotations.py`) is the single source of the
  target-frame / ground-frame split, and it matches the Phase-5 `GeometryReadout` grouping.
- **Angle-truth consistency test (binding).** `scene/angle_truth.py` recomputes each
  stage-backed angle from the ported `geometry.js` direction math and a test asserts it
  agrees with `stage_outputs["geometry"]` within `ANGLE_CONSISTENCY_ABS_TOL_RAD = 1e-9`
  rad (measured residual ~1e-15). Divergence is a red build — this enforces that the stage
  is the single source of angle truth.
- **Target shape library.** The side panel's shape combo is populated from the
  `source.target.shape` schema `enum_values` (never a hardcoded list — Gap 70). Selecting a
  shape performs one `sensor.set` and previews the new glyph immediately, then schedules the
  full re-evaluation. A shape whose required dimensions are unset fails the physics re-run
  through the normal actionable-error path (CU-125).
- **RPY triad.** The target body-axes triad (`scene/frames/body_axes.py`) renders from
  `source.target.shape_{yaw,pitch,roll}_rad` (the **target** orientation), colour-coded
  pink=Roll / green=Pitch / purple=Yaw, using the same `euler_to_rotation_matrix` (ZYX) the
  target body mesh uses, so tilting the target via those params rotates the gizmo. Platform/
  sensor attitude still has **no stage owner** (CU-122): `observer_{yaw,pitch,roll}_rad`
  remain defaulted to identity, so there is no platform-attitude triad yet.
- **Accordion side panel** (`widgets/geometry_angle_panel.py`) — a `QToolBox` with two
  pages: **Geometry inputs** (the reusable Phase-5 `GeometryModeForm`, so geometry is
  editable from the Schematic tab — owner request 2026-07-14) and **Target shape &
  orientation** (the shape combo + dimension + RPY editors + triad toggle). The dimension and
  RPY editors reuse the **same** shared `FieldRow` building block (`widgets/field_row.py`) and
  QSS object names as the `GeometryModeForm` fields, so the two pages render identically by
  construction (owner feedback 2026-07-14 — the target fields "should be just like the
  geometry boxes"). The panel stays a **view + control surface only** (it never touches the
  `Sensor`): the shape combo emits `shapeRequested`, and clicking a dimension/RPY value emits
  `editRequested(dotpath)`. On `editRequested` the owning `StagePane` opens the shared
  `ParameterEditorDialog` (the same value/unit/reject path as the parameter tree), so the edit
  is exactly one `sensor.set` validated on a clone first; the embedded `GeometryModeForm` owns
  its own copy of that edit/commit path and the `StagePane` re-emits its `parameterEdited`. The
  **angle-arc reveal toggles** are **not** on
  this panel — owner feedback 2026-07-14 moved that selector onto the plot as the bottom-left
  `AngleToggleOverlay` (§6.4), leaving the right column to geometry inputs + shape/attitude.
  The derived-angles `GeometryReadout` table is **not** on this panel either (owner request
  2026-07-14 — it duplicated the Inputs tab; the derived values surface on the schematic
  itself as arc degree labels + altitude leader labels). Both geometry forms (Inputs tab +
  Schematic panel) read the one live sensor and re-sync on the next clean evaluation, so an
  edit on either reflects on both.
- **Deferred (needs a live interactor):** in-scene VTK point-picking and the lifted
  `scene/highlight.py` active-edit re-stroke (CU-124); the corner view-cube / world-axes
  gnomon widgets stay out of v1.

### 6.9 2D Schematic — Complete Shipped Viewer (Pass 1 + Pass 2, ADR-0007 superseded)

The shipped viewer is a pure-Qt `QPainter` orthographic schematic. It supersedes §§6.7–6.8
(PyVista Part A/B). Modules (all under `radiant.gui.viewer`, gui → api + core; **no**
PyVista/VTK, no physics stage):

- **`projection.py`** — the orthographic camera + direction math ported verbatim from the
  mockup `geometry.js` (`dir_from_az_zen`, `Camera.project`), plus the Pass-2 additions
  `compute_angles` (port of `computeAngles`), `arc_between` (great-circle arc), and
  `ground_azimuth_arc`. These are used for arc **geometry/placement** and the angle-truth
  check **only** — never as a second angle authority (§6.3).
- **`schematic_view.py`** — the `SchematicView` canvas + the engine-independent
  `build_scene`/`SchematicScene`. Draws: ground grid, X/Y/Z axes, the labelled vectors
  (sun→target, sensor→target, zenith always; sensor→ground + sun→ground only for a
  down-looking elevated target, landing at its nadir ground projection
  `scene.ground_point` — §6.2), sun/sensor glyphs, the **full shape-library** wireframe
  (sphere great-circles, box, cylinder, cone, flat-plate, point reticle), rotated by the
  target's ZYX-Euler RPY; the **revealable angle arcs** (off-nadir η, sun-zenith θ_s,
  relative-azimuth Δφ on the ground, phase α_t, and — Geometry-Flexibility Phase 4 — the
  path zenith **θ_o** and lower-endpoint zenith **ζ_low**) each with a **degree** value
  pill; the **h_s / h_t altitude leader labels** and the level-arm **Δh sag pill**
  (not-to-scale magnitudes, §6.1); and the on-target **RPY triad** (roll +X′ pink / pitch
  +Y′ green / yaw +Z′ purple). Composition is keyed by the stage-derived `los_direction`
  (§6.2 — down / up / level). **Each stage-backed zenith arc is swept to its own ray**
  (`eta_dir` / `theta_o_dir` / `zeta_low_dir`): η, θ_o and ζ_low are read at different
  vertices of the viewing triangle and differ by the Earth-centre central angle, so sharing
  one ray would pin a stage-true number on a visibly wrong arc; the ζ_low arc moves to the
  sensor glyph when the sensor is the lower endpoint (`_arc_apex`). Orthographic yaw/pitch
  by mouse drag. Hosts the interactive `AngleToggleOverlay` as a bottom-left child widget
  (mirroring the top-left VECTORS legend), repositioned in `resizeEvent`.
- **`angle_overlay.py`** — the interactive `AngleToggleOverlay` reveal selector: one
  frame-grouped checkbox per annotatable angle, mounted **on** the canvas bottom-left (owner
  feedback 2026-07-14, moved out of the right-column accordion). Each toggle emits
  `angleToggled`, wired by `GeometryViewer` to `set_angle_revealed` — the reveal path is
  unchanged, only the control's location moved.
- **`angle_catalog.py`** — the Qt-free annotation catalog (name, symbol, frame, stage-truth
  key, colour) the schematic and the side panel share; the single source of the
  target-frame/ground-frame split (matches the Phase-5 `GeometryReadout` grouping).
- **`angle_truth.py`** — the viewer-local recomputation the consistency test checks against
  `stage_outputs["geometry"]` within `ANGLE_CONSISTENCY_ABS_TOL_RAD = 1e-9` rad (off-nadir,
  sun-zenith, relative-azimuth, and — Phase 4 — path-zenith θ_o and lower-zenith ζ_low;
  phase excluded — no stage truth). `stage_angle_rad(geometry, name)` is the single
  stage-truth accessor: every annotation reads one key verbatim except ζ_low, which has no
  single stage key and goes through the direction-keyed transform defined once in
  `angle_catalog.lower_zenith_rad` — θ_o for a down/level scene (the target/shared lower
  endpoint), **π − η for an up-looking one** (the sensor's zenith is the supplement of the
  sensor-vertex interior angle; note this is *not* π − θ_o, which differs by the
  Earth-centre central angle). The consistency tests parametrize over the scene classes
  (down, ground→air up, ground→space up, LEO→GEO up, air→air level). Divergence is a red
  build.
- **`viewer_state.py` / `viewer_widget.py`** — the `ViewerState` adapter and the
  `GeometryViewer` widget; `set_angle_revealed` / `set_triad_visible` reveal the arcs /
  triad on the canvas and repaint (a plain `update()`, no VTK render). Phase 4 binds five
  more stage outputs verbatim — `theta_o_rad`, `los_direction`, `scene_class`,
  `observer_class`, `target_class` — with down-looking defaults, so a partial or
  pre-ADR-0011 result composes exactly the pre-Phase-4 scene.

**Angle value sourcing (§6.3, binding):** each arc's degree label is `math.degrees()` of the
stage angle bound verbatim into `ViewerState` (`eta_rad`, `theta_s_rad`, `delta_phi_rad`) —
the radians → degrees conversion is a **display-boundary** formatting step, not a physics
computation. The phase arc renders **symbol-only** (no stage-output phase angle exists, so
§6.3 forbids fabricating one — analogous to the Rule-4 MTF-only TDI term).

**Shape dimensions (owner request, 2026-07-14):** the side panel exposes **every** relevant
dimension input for the selected shape, schema-driven from `source.target.shape_*`
(radius / length / width / height / base-radius), showing only the subset the shape uses
(sphere → radius; cylinder → radius+length; flat_plate → length+width; box →
length+width+height; cone → base-radius+height). Each is one `sensor.set` per edit (the
Phase-2 edit/reject pattern, unit-carrying). The wireframe reflects the shape's own **aspect
ratio** (dim ratios normalised to an abstract extent) but never the raw metres (§6.1).

**Nominal dimensions on shape selection (CU-125, owner request 2026-07-14):** selecting a
shape whose required dimensions are still the `0.0` "not set" sentinel would trip the
`radiant.source` shape factory (`ParameterBoundsError`) on the scheduled re-evaluate. The
owning `StagePane` therefore seeds each required dimension still at `0.0` to a nominal
non-zero value (`geometry_angle_panel.NOMINAL_SHAPE_DIMENSIONS` — sphere r=1 m; cylinder
r=0.5 m + L=2 m; flat_plate L=W=1 m; box L=W=H=1 m; cone base-r=0.5 m + H=1 m) with one
`sensor.set` each, so the re-run succeeds. A user-set non-zero value is **never** overwritten,
and the schema keeps the `0.0` Rule-12 default (0.0 still means "shape not provided"); the
nominal map is a GUI-side UX default only. Magnitudes are not-to-scale (§6.1).

---

## 7. Scenario Requirements Matrix

Harvested from all **37** `scenarios/**/gui_workflow.md` files (the count matches the
GUI plan's estimate of 37). Each workflow's concrete GUI asks are mapped to the v1 phase
that delivers them, or flagged **OUT-OF-V1** (requested but in no v1 phase → dispositioned
to v1.1 or `gaps.md` at GUI plan Phase 9). The baseline asks present in nearly every
scenario — a scripting/command window (Phase 8) and a schema-driven parameter panel with
derived-value display (Phase 2) — are noted once here and not repeated per row.

### 7.1 Per-Scenario Summary

| Scenario (persona) | Salient GUI asks → disposition |
|---|---|
| **1.1** Maritime MWIR (Sarah) | regime-error → suggest `sub_pixel` inline → **P3**; tape7 import UI · curve digitizer · atmosphere A/B toggle · PPT export → **OUT**; aperture sweep → **v1.1** |
| **1.2** VNIR GSD/aperture (Sarah) | solar-geometry helpers → **P8**; sampling-regime band → **P4**; 2-D sweep + GSD→focal constraint · trade-surface cursor readout → **OUT** |
| **1.3** Dual-band MWIR/LWIR (Sarah) | material-spectrum import · pre-run well advisory · P_d/ROC panel → **OUT**; band comparison cards → **deferred (comparison)**; fire-temp sweep → **v1.1** |
| **1.4** TDI pushbroom (Sarah) | derived GSD/IFOV/Q/Airy → **P2**; noise stacked bar → **P4**; sensitivity sliders → **P3**; saturation status table → **OUT**; TDI sweep+progress/abort → **v1.1**; analog↔digital compare + PDF/Excel → **deferred** |
| **1.5** Obscured aperture (Sarah) | strut slider → live PSF/EE/RER/SNR → **P3/P4**; Strehl caveat → **P4**; pupil-mask preview · measured-pupil import → **OUT**; multi-config table → **deferred** |
| **2.1** InSb vs HgCdTe (Mike) | noise table/bars → **P4**; QE/dark-current CSV import · detector-bench preset · spectral-QE toggle · cooler-trade panel → **OUT**; FPA side-by-side → **deferred** |
| **2.2** 1/f corner (Mike) | noise stacked bar + cards → **P4/P3**; XLSX import · 1/f PSD viewer → **OUT**; with/without-1/f toggle → **deferred**; frame-rate sweep → **v1.1** |
| **2.3** IPC → MTF (Mike) | provenance badges → **P2**; regime badge → **P3/P4**; MTF per-term → **P4**; multi-sheet import + column mapper · threshold lines · lab-data overlay → **OUT**; IPC sweep → **v1.1** |
| **2.4** Persistence (Mike) | config load → **P2/P9**; sequence from console → **P8**; decay panel · ghost-in-LSB overlay · dead-time readout → **OUT** |
| **2.5** Well capacity (Mike) | what-if sliders → **P3** (some analytic → §7.3); import · 2-D sweep heatmap · dynamic-range/well-fill viz · feasibility cards → **OUT** |
| **3.1** ISR pass planning (Raj) | off-nadir slider re-run + NIIRS-floor → **P3/P5**; orbit dashboard · access-corridor plot · coverage readout · revisit panel → **OUT** |
| **3.2** Weather sensitivity (Raj) | weather sweep → **v1.1**; XLSX import + weather presets · 2-D grid heatmap · traffic-light go/no-go · GIQE-5 decomposition · analytic sliders · PPT export → **OUT** |
| **3.3** Multi-sensor compare (Raj) | 3-way comparison table → **deferred (comparison)**; proposals import · compliance matrix · radar chart · leverage readout · PDF spec-sheet importer → **OUT** |
| **3.4** Off-nadir agility (Raj) | performance dashboard → **P4**; off-nadir label/geometry → **P5**; angle sweep tabs → **v1.1**; off-nadir GSD/NIIRS physics (Gaps 33-36, §7.3) · access map · trade explorer → **OUT** |
| **3.5** Nighttime MWIR (Raj) | dual-band side-by-side → **deferred**; scene/humidity preset coupling · LST GeoTIFF raster import · day/night toggle · draw-region-on-map → **OUT** |
| **4.1** Detection matrix (Lisa) | deprecation banner → **P2**; matrix builder + BatchRunner grid → **v1.1 (Batch)**; target-library import → **deferred (library)**; detection-range traffic-light heatmap · worst-case panel · Excel export → **OUT** |
| **4.2** Ship classification (Lisa) | derived √(L·H)/IFOV/horizon → **P2**; Johnson/horizon helpers → **P8**; what-if altitude → live matrix → **P3**; DRI matrix by binding-limit · range bars · cycles-vs-range drill → **OUT** |
| **4.3** Camouflage (Lisa) | ASTER/measured-ε import + overlay · spectral-ε→radiance (Gap 47) · ΔL(λ) sub-band table · half-band seeker · detection-range bars → **OUT**; signature cards differenced → **deferred (comparison)** |
| **4.4** Time-of-day (Lisa) | diurnal-profile CSV import · profile-driven temporal sweep · two-pixel differencing (Gap 52) · zero-crossing finder · well banner → **OUT**; contrast-SNR-vs-time → **v1.1** |
| **4.5** Altitude trade UAV (Lisa) | NETD⇄NEP⇄D* converters → **P8**; NETD vendor input mode · altitude trade w/ apparent-contrast · fill-fraction/τ breakdown · detection-ceiling panel → **OUT**; altitude sweep → **v1.1** |
| **5.1** WFE budget (Tom) | derived params → **P2**; dual-path consistency indicator · MTF overlay → **P4**; WFE input-mode selector · Zernike import + ErrorBudget · reverse NIIRS→WFE lookup · Zernike allocation tool → **OUT**; WFE sweep → **v1.1** |
| **5.2** Pixel pitch (Tom) | sampling-regime/Q badges → **P4/P3**; folded-MTF tab → **P4**; multi-sheet import · PSF grid overlay · trade-space scatter · FoM optimizer + compliance filter → **OUT**; detector sweep → **v1.1**; PPT → **deferred** |
| **5.3** Mono vs poly PSF (Tom) | config load → **P9**; chromatic MTF overlay → **P4**; per-λ PSF viewer + λ-slider · convergence plot · traffic-light chromaticism · FITS export → **OUT**; split-screen diff → **deferred** |
| **5.4** Jitter blur (Tom) | dual-unit jitter (µrad/pixel/IFOV) → **P2**; XLSX import · jitter-source RSS budget · GIQE-5 decomposition → **OUT**; jitter sweep (analytic, §7.3) → **v1.1** |
| **5.5** Stray-light glare (Tom) | clean vs with-stray noise bars → **P4**; stray-light side-by-side → **deferred (comparison)**; XLSX/FRED import · VGI tolerance slider · 2-D stray-light-PSF import (Gap 60) → **OUT/v1.1** |
| **6.1** SNR benchmark (Chen) | noise breakdown → **P4**; D*/NEP/NETD converters → **P8**; datasheet auto-configure · benchmark PASS/FAIL panel → **OUT** |
| **6.2** Atmospheric intercompare (Chen) | tape7/libRadtran import UI · atmosphere-swap A/B · six-profile small-multiples · residual/per-band panel → **OUT** |
| **6.3** Noise-model verification (Chen) | provenance badges → **P2**; noise bar/table/pie → **P4**; MTF-budget sub-tab → **P4**; XLSX import + unit-mapping dialog · RADIANT-vs-hand-calc panel → **OUT**; multi-format export → **deferred** |
| **6.4** Synthetic scene (Chen) | scene/target-table import → **P2/library**; per-target radiometry panel · 1-D scene strip + seed/re-roll · ROC/AUC panel · 2-D scene canvas (image sim) → **OUT/deferred** |
| **6.5** Emissivity sensitivity (Chen) | config import → **P2**; retrieval sweep slider → **v1.1**; Jacobian panel · retrieval-tolerance readout · bias-vs-noise viz → **OUT** |
| **7.1** NEDT reconciliation (Karen) | per-term noise breakdown → **P4**; NEDT-over-temps sweep → **v1.1**; multi-sheet lab import + nominal/as-built diff · TVAC preset · predicted-vs-measured overlay · tornado chart → **OUT** |
| **7.2** Radiometric calibration (Karen) | DN-domain results → **P3/P4**; temperature-sweep calibration → **v1.1**; XLSX import + lab preset · self-emission panel · measured-curve import · calibration fit-card + "Apply calibration" → **OUT** |
| **7.3** MTF measure vs predict (Karen) | **MTF component decomposition → P4 (the one bespoke viz that lands in v1)**; predicted-vs-measured overlay → **P3 canvas + OUT**; Rule-4 consistency trust banner (§7.3) → **P3/P4**; measured-MTF import · residual-explainer grid (Gaps 31/32) → **OUT**; defocus sweep → **v1.1** |
| **7.4** Cold-stop sweep (Karen) | derived-badges + ε=0 warn → **P2**; exo→space auto-fill → **P5**; metrics dashboard → **P4**; nearfield sweep → **v1.1**; multi-sheet import · inverse `solve_for` UI · side-by-side compare → **OUT/deferred** |
| **7.5** Env temp extremes (Karen) | co-varying J(T)+QE(T) sweep (Gap 48) → **v1.1 + OUT**; measured-curve import · lab preset · Arrhenius-knee panel · spec-compliance table → **OUT** |
| **8.1** Off-nadir interpolation | MODTRAN family-coverage/interpolate-vs-nearest UI · family registry browser · one-call tabulated-atmosphere config → **OUT (library + atmosphere-config builder)** |
| **8.2** Altitude interpolation | same tool as 8.1, plus **persistent non-dismissible `well_status` saturation banner** → **OUT** (flagged; 3 scenarios lost time to silent clipping — see CU-101) |

### 7.2 Consolidated OUT-OF-V1 Features (owner checkpoint reading)

Distinct capabilities requested by workflows but delivered by **no** v1 phase — with one
exception: **row 8 (the `well_status` saturation banner) was pulled into v1** at the
2026-07-12 Phase 0 checkpoint (owner amendment 2, §1.3). Ranked by breadth of demand. The
remaining rows are dispositioned at GUI plan Phase 9 (each becomes a `gaps.md` entry or a
v1.1 line item); listed here so the owner can confirm the deferral is acceptable.

**Registry moved (Rule 25).** The 17-row consolidated disposition table now lives in
`docs/tracking/gaps.md` → **"GUI v1.1 & Deferred-Feature Backlog (arch doc §7.2 migration)"**
(entries **GUI-1 … GUI-17**), migrated at GUI plan Phase 9 closeout so capability gaps live
only in the registry. Each row keeps its owner-ratified disposition (v1.1 / deferred-§9 /
gaps.md) and cross-references the underlying physics gap where only the GUI surface is new.
Row 8 (the `well_status` saturation banner) was **pulled into v1** (shipped Phase 3; CU-101)
and is therefore not in the deferred backlog. The interpretive reading below is retained
here as analysis, not as a registry.

**Read:** the dominant unmet demand is data ingestion (rows 1, 7) and results
communication (rows 2, 3, 4) — not the physics, which the chain already computes. The v1
evaluate-loop-plus-panels covers the compute; the deferred tail is mostly I/O and
reporting ergonomics. At the 2026-07-12 Phase 0 checkpoint the owner confirmed this
deferral shape and pulled exactly one row into v1: **row 8, the saturation banner** (owner
amendment 2) — three scenarios reported lost time to silent clipping; it lands in GUI plan
Phase 3 with CU-101 (the API half) as its prerequisite. All other rows remain
dispositioned as listed.

### 7.3 Assumptions in Workflows That the Shipped API / v1 Scope Does Not Meet

Places where a workflow assumes behavior the v1 architecture or the shipped API does not
provide. These are *not* defects to fix in Phase 0 — they are boundary notes so later
phases don't silently build to a false assumption.

1. **Sweep-with-progress-bar + Abort as the central run action** (1.4, 2.2, 2.5, 3.2,
   5.1, 7.1). v1 Phase 3 is a single background `evaluate()` with no sweep engine and no
   progress/abort surface; sweeps are **v1.1**. Per-point progress/cancel hooks exist on
   `sweep()`/`monte_carlo()` (Gap 72) but not on `evaluate()`.
2. **Live-streaming / incremental partial sweep results** (2.5, 3.2 — "heatmap updates as
   each column completes"). v1's loop is a debounced single-shot; even the v1.1 Sweep tab
   returns a completed `SweepResult`, not a streamed one.
3. **Analytic "what-if" sliders that update metrics without re-running the chain** (5.4
   "instant, no re-evaluation"; 3.2, 2.5). v1 Phase 3 always re-runs the full chain
   (debounced). There is no analytic surrogate / post-hoc degradation model.
4. **Inverse solve / reverse lookup as a first-class GUI action** (7.4 `solve_for`, 5.1
   NIIRS→WFE, 1.2 GSD→focal, 5.2 FoM optimize). v1 is evaluate-only; `solve_for` exists
   in the API but has no v1 surface (reachable only from the Phase-8 console).
5. **Off-nadir GSD / NIIRS display depends on unshipped physics** (3.4). Requires
   slant-range-based GSD and off-nadir NIIRS (framework Gaps 33–36; related to CU-096's
   θ_o/η conflation). The GUI cannot render corrected values until the chain closes those
   gaps — already tracked; no new CU.
6. **`well_status` surfaced as a metric/banner** (8.2, 1.3, 4.4). The value lives only in
   `stage_outputs["readout"]["well_status"]`, not on the `ChainResult` metric/badge
   surface, and the v1 badge set (SNR/NEDT/NIIRS/GSD/MTF@Nyquist) omits it → **CU-101**.
7. **Rule-4 dual-path consistency warning as a plain-language trust banner** (7.3, 5.1).
   Not an enumerated v1 feature; foldable into the Phase-3 warning surface. Minor.
8. **Richer default metric surface** (3.4, 5.x, 7.x treat contrast-SNR, SCNR, well-margin
   dB, dynamic-range dB, Strehl, RER, Q, EE as dashboard cards). v1 badges only the five
   above; the rest are reachable via the Phase-4 Variable Explorer, not as badges. Minor.

---

## 8. Design System

The binding visual specification the Phase 1 QSS theme implements. **No widget in any
phase hardcodes a color, font, or size outside `gui/themes/`** (GUI plan §4.9 —
review-blocking). All values below are pulled verbatim from the mockup CSS in
`dev_tools/gui_mockups/radiant_ui/radiant_mid_fi.html` and `radiant_scripting.html`
(the `:root` light block and the `body.dark` override). **Light is the v1 launch
default, dark is the alternate** (GUI plan §4.4, Phase 0 checkpoint amendment 1);
both derive from the same token set, and the View-menu toggle (Phase 9) switches
between them. The mockup HTML defaults to light, so the app matches that default.
*Ratification note:* the owner reviewed the light rendering live in `radiant_mid_fi.html`
(its load default) on 2026-07-12 and confirmed light-default at launch (§1.3).

### 8.1 Color Palette

Named as design tokens (CSS-var names preserved so the QSS maps 1:1). **Dark theme —
alternate** (both token sets ship in Phase 1; the View-menu toggle switches them):

| Token | Hex (dark) | Role |
|-------|-----------|------|
| `bg` | `#0f1216` | window background |
| `panel` | `#171a21` | panel / card surface |
| `panel-2` | `#1d2029` | inset / header surface, hover |
| `panel-3` | `#262a35` | raised hover surface |
| `panel-4` | `#323744` | deepest inset (scripting console) |
| `line` | `#2b3140` | default 1 px border |
| `line-2` | `#3a4254` | emphasized border / hover border |
| `ink` | `#e6e9ef` | primary text |
| `ink-2` | `#c3c9d4` | secondary text |
| `muted` | `#8b94a4` | labels, units, captions |
| `muted-2` | `#6e7685` | faintest text |
| `accent` | `#e08157` | terracotta accent — Run button, active, selection |
| `accent-soft` | `#3a2218` | accent tint (backgrounds) |
| `ok` | `#7fb987` | health OK (green dot, positive trend) |
| `ok-soft` | `#1f2f22` | OK ring / tint |
| `warn` | `#e0b249` | health warning (yellow) |
| `warn-soft` | `#3a2f16` | warn ring / tint |
| `err` | `#e07874` | health error (red) |
| `err-soft` | `#3a1e1c` | err ring / tint |
| `stale` | `#666b77` | stale / not-evaluated (gray) |
| `stale-soft` | `#242832` | stale ring / tint |
| `focus` | `#86a8df` | keyboard/selection focus (blue) |
| `focus-soft` | `#1e2a3e` | focus tint (selected stage background) |

**Light theme — v1 launch default** (Phase 0 checkpoint amendment 1; the View-menu
toggle switches to the dark alternate, GUI plan Phase 9): `bg #ebeef2` · `panel #fafbfc` ·
`panel-2 #f1f3f6` · `panel-3 #e6e9ee` · `line #cfd5de` · `line-2 #b7bfcb` · `ink #1b2230`
· `ink-2 #384050` · `muted #6b7380` · `muted-2 #8a93a1` · `accent #b8431a` ·
`accent-soft #f6e2d6` · `ok #2f7a3a` / `ok-soft #dcebdd` · `warn #a97c14` /
`warn-soft #f5ebcf` · `err #a8302a` / `err-soft #f3dbd7` · `stale #9aa3b0` /
`stale-soft #e6e9ee` · `focus #2f5aa8` / `focus-soft #dde6f4`.

**Console syntax-highlight tokens** (`radiant_scripting.html`) — dark / light:
keyword `#d69fd8` / `#8a2a8e` · string `#97c49e` / `#2f6b3a` · number `#e0a075` /
`#a04018` · function `#9bb8e3` / `#2a5abf` · comment `#6a7385` / `#8a93a1`.

**Window traffic-light dots** (macOS-style title chrome, raw hex, not themed):
red `#ec6a5e` · yellow `#f4bf4f` · green `#61c555`. These are the window-decoration
dots only; **stage health dots use the themed `ok`/`warn`/`err`/`stale` tokens** above.

**Configuration accents** (`config_accents`, multi-configuration Phase 4a) — eight hues,
one per configuration **slot** (`ConfigurationSet.MAX_CONFIGS` = 8), assigned by position
in the set so a configuration keeps its colour, and index-for-index across the two themes
so it survives a theme toggle. Dark / light: `#86a8df` / `#2f5aa8` · `#e08157` /
`#b8431a` · `#7fb987` / `#2f7a3a` · `#c79ad8` / `#7a3a8e` · `#e0b249` / `#a97c14` ·
`#6fc0c0` / `#1f7a7a` · `#e07fa4` / `#a8305a` · `#a8b0be` / `#5a6270`. Used by the master
configuration selector (§4.2b) and, since Phase 4d, the per-configuration Performance
column headers (§4.2e), which read their hue off the selector so the two cannot drift.

### 8.2 Typography

| Role | Family | Size / weight |
|------|--------|--------------|
| Base UI text | `'IBM Plex Sans', system-ui, sans-serif` | 13 px / 400, line-height 1.35 |
| **All numeric values, dot-paths, code, chips** | `'IBM Plex Mono', monospace` | see rows below (values are always mono) |
| App title (h1) | Sans | 18 px / 600, letter-spacing −0.01em |
| Panel title | Sans | 12.5 px / 600, uppercase, letter-spacing 0.04em |
| Stage name (eyebrow) | Sans | 10.5 px / 500, uppercase, letter-spacing 0.06em |
| Stage title | Sans | 14 px / 600 |
| KPI/metric label | Sans | 10.5 px / 500, uppercase, letter-spacing 0.06em, `muted` |
| **KPI/metric value** | Mono | 17 px / 600, `ink` |
| KPI/metric unit | Sans | 11 px / 400, `muted`, small left margin |
| Small labels / captions | Sans | 10.5–11.5 px |
| Keycap (`kbd`) | Mono | 10.5 px, border-bottom-width 2 px (keycap effect) |

Weights: 400 body, 500 labels/buttons, 600 titles and values. **Numeric values are
always mono** — this is what carries the instrument-panel feel and keeps unit-suffixed
readouts aligned.

**Rendering note (CU-104).** The `letter-spacing` values above are **nominal design
targets**: Qt's QSS subset supports neither `letter-spacing` nor `text-transform` on a
`QLabel`, so they are **not** applied in the stylesheet and the shell reads close to — not
pixel-identical with — the CSS mockup. The `uppercase` transform *is* honored, applied
**in-widget** in Python (`.upper()` in `StageChip` / metric labels) rather than via QSS.
If exact tracking is ever required, it would be applied per-widget via
`QFont.setLetterSpacing(...)` from `themes/`, not through the stylesheet (deferred — the
current approximation is accepted).

### 8.3 Spacing, Radius, Borders

- **Border radius:** cards/panels 8–9 px · buttons & inputs 4–5 px · chips/kbd/badges
  2–3 px · pill badges 9 px · dots 50%.
- **Padding:** panels ~12 px 14 px · buttons 6–7 px 14 px · inputs 5 px 8 px ·
  KPI cells 4 px 14 px · stage buttons 10 px 12 px.
- **Gaps:** 6 px is the default inter-control gap; strip/panel padding 12 px 14 px.
- **Borders:** 1 px solid `line` everywhere; hover raises to `line-2`. `kbd` uses a 2 px
  bottom border for a keycap look.
- **Transitions:** 0.12 s on `border-color` / `background` for hover/active feedback.

### 8.4 Badges & Health Dots

- **Health dot:** a 9–11 px circle filled with the themed status token (`ok`/`warn`/
  `err`/`stale`), wrapped in a soft ring `box-shadow: 0 0 0 2px <token>-soft`. Used on
  every stage-strip button (§4.2) and per-noise-term rows.
- **Derived / provenance badge:** a small pill — 1 px `line` border, 9 px radius, mono
  9.5 px, `muted` text. Renders the ⚡-derived marker and the user-set / default / derived
  provenance state (§4.3).
- **Stage state:** a warned/errored/stale stage button sets its background to the
  `<status>-soft` tint and its border to the `<status>` token; a selected stage uses
  `focus-soft` background + `focus` border.
- **KPI stale marker:** when a result is stale the metric value appends a ` →?` glyph in
  the `warn` color (`.v::after`), signaling "this number predates the last edit."
- **Run button:** `accent` background, white text; when the config is dirty/stale it
  flips to a `warn` background to signal "re-evaluate."

### 8.5 Geometry-Viewer Glyph Palette (domain colors, separate layer)

The 3D scene uses domain color *roles*, not the chrome tokens above (§6.4): sun = amber,
sensor = cyan, phase/azimuth arcs = magenta, zenith = neutral, ground/projection = faded
amber/cyan; RPY triad pink=Roll / green=Pitch / purple=Yaw. The panel's chrome (side
panel, labels, background) still follows the §8.1 tokens so the panel matches the app.

---

## 8b. Sweep Surface (Tier-2 GT-1 — SHIPPED 2026-07-16)

**Run → Run Sweep…** opens `SweepDialog` (Rule 20 content spec; sequence in the Trade-Study
plan):

- **Parameter picker(s)**: every float `ParameterDef`, schema-driven; an optional second
  parameter turns the run into a 2-D grid.
- **Range entry in the parameter's input unit** (unit label beside the picker, R-UNITS);
  converted once at the dialog boundary to canonical units (Rule 2). Linear or log spacing.
- **Metric picker**: the live metric set from the last result (fallback `snr`).
- **Execution**: `Sensor.sweep` / `sweep_2d` on a **clone** (a trade study never mutates the
  session config), on a worker `QThread` with the Gap 72 `progress(done,total)` / `cancel()`
  hooks driving a progress bar. **Cancel is a first-class outcome**: the API returns no partial
  results by contract and the dialog reports "Cancelled at k/N — no partial results" honestly.
- **Result**: 1-D curve (log x when log-spaced) or 2-D heatmap with colorbar into the dialog
  canvas; the completed `SweepResult`/`Sweep2DResult` is retained on the main window
  (`last_sweep_result`) for export (`to_csv`, Gap 88 surfaces).
- **Copy as script**: emits the equivalent `sensor.sweep(...)` one-liner to the clipboard —
  the dialog-to-console graduation path (owner-shaped D3: the GUI teaches the API).

Monte Carlo / Batch deliberately have **no dialogs** (owner D3): they are console workflows;
their Run-menu items become script scaffolds (GT-2).

## 8c. Config-File Comparison Mode (Tier-2 GT-3 — SHIPPED 2026-07-16)

**Tools → Compare Config Files…** opens `ComparisonDialog` (content spec per Rule 20).
The label says *config files* deliberately (relabelled 2026-07-25, CU-214): this dialog
compares the live config against config **files on disk**, and is not the study's
per-configuration surface — that is §4.2e's Performance columns and the scripting
`ConfigurationSet.compare`.

- **Columns**: the current live config (always first, evaluated on a clone) plus N config
  files added via a file picker; baseline column selectable.
- **Execution**: each column evaluates once, sequentially, on a worker thread with progress;
  a failed column reports which config failed and why (actionable), never a partial table.
- **Matrix**: `compare_configs` (Gap 79) — union-of-metrics rows, registry units, per-metric
  Δ against the baseline shown inline, best-per-metric marked ✓ + bold (conservative sense:
  higher-is-better default, NEDT/GSD/FWHM lower, flags unmarked), absent metrics shown "—"
  (never zero-filled, Rule 17); metric descriptions as tooltips.
- The **atmosphere A/B swap** (GUI-10) is this flow: save the current config, flip
  `atmosphere.model`, add the saved file.

## 9. Deferred to Phase 2 (post-v1)

Explicitly deferred; the v1 architecture must not preclude them.

| Capability | Why deferred | Precondition |
|------------|-------------|-------------|
| 2D image simulator (focal-plane visualization) | Requires scene/image modeling | RADIANT Scene module (future) |
| Library browser (sensor / target / atmosphere libraries) | Database/catalog UI | Library management system |
| Report generator (auto PDF/PPT summary) | High engineering effort | Reporting templates |
| Comparison mode (two+ sensors side-by-side) | Multi-result state management | Core API (stable) |
| Plugin UI (custom stage panels) | UI integration effort | Plugin system |
| Remote computation (submit to HPC) | Infrastructure | Cluster job management |
| MATLAB bridge | Small user population; Python is primary | Stable API (done) |

The scripting API already serves all of these programmatically; Phase-2 work adds visual
interfaces for workflows that are currently script-only.

---

## 10. Menu Structure

```
File   New · Open YAML… (Ctrl+O) · Open Recent → · Save (Ctrl+S) · Save As… ·
       Export YAML… [SHIPPED GX-1 → sensor.save] · Export JSON Result… [SHIPPED GX-1 → result.to_provenance_record] · ───── · Quit (Ctrl+Q)
Edit   Undo (Ctrl+Z) · Redo · Reset to Defaults · Find Parameter (Ctrl+F) ·
       ───── · Configurations… [SHIPPED 4c → §4.2d configuration manager]
View   Show/Hide Parameter Panel (F6) · Show/Hide Detail Panel (F7) ·
       Stage: … (Ctrl+1..9) · Dark/Light Theme · Font Size +/−
Run    Evaluate (F5) · Validate Only (Ctrl+R) ·
       Run Sweep…  [v1.1] · Monte Carlo…  [v1.1] · Batch Run…  [v1.1]
Tools  Scripting Window (Ctrl+Shift+P) · Parameter Schema Browser ·
       Compare Config Files… [SHIPPED GT-3 → §8c; relabelled 2026-07-25, CU-214] ·
       Compare Measured MTF… · Solve for Parameter… · Explain Parameter… · Preferences…
Help   Documentation · Example Configs · About RADIANT
```

Actions not yet implemented in a given phase are present but **disabled** (GUI plan
Phase 1). Sweep / Monte Carlo / Batch remain disabled through v1 (D4).

**Shipped (GUI plan Phase 9):** File → New / Open / **Open Recent** (persisted via
`QSettings`) / Save / Save As are wired through `Sensor.load()` / `Sensor.save()` only
(§4.1); the window title shows the current file name with a `*` **dirty marker** that sets
on any edit and clears on save. Edit → **Undo / Redo** (Ctrl+Z / Ctrl+Shift+Z) reverse the
last ~20 parameter edits via a `QUndoStack` of named `sensor.set` commands (a whole-config
swap — Open / New / YAML-editor Apply / console Refresh — clears the stack). View → the
**light/dark theme toggle** re-applies the QSS + re-themes the custom-painted widgets
(schematic viewer, detector illustration) and persists the choice; panel show/hide
(Parameter Panel F6, Right Rail F7) and stage-jump shortcuts (Ctrl+1..9) are wired.

---

## 11. Implementation Notes

- **PySide6 ≥ 6.6** (LTS); pin the minor version in `pyproject.toml`. Qt6-only, no Qt5
  target. Optional-dependency group: `gui = ["PySide6>=6.6", "matplotlib>=3.8",
  "qtconsole>=5.5"]`. **The shipped console is a REPL over `code.InteractiveConsole`, not
  qtconsole (§4.6.1, CU-138)** — the `qtconsole` pin is kept for the deferred kernel path.
  The pre-D7 `pyvista`/`pyvistaqt` pins were **dropped** (CU-134, GUI plan Phase 9): the
  geometry viewer is a pure-Qt 2D `QPainter` schematic (ADR-0007) with no VTK/OpenGL
  dependency. Core RADIANT stays importable without the `gui` extra.
- **Matplotlib backend:** `backend_qtagg.FigureCanvasQTAgg`; the GUI's `result.plot.*`
  calls are identical to the scripting-API calls.
- **Main window:** `RADIANTMainWindow(QMainWindow)`; parameter and detail panels are
  `QDockWidget`-based for user-configurable docking.
- **Theming:** QSS stylesheets in `gui/themes/`, generated from the §8 tokens; customize
  colors/typography, not widget geometry.
- **Undo/redo:** `QUndoStack` wrapping each `sensor.set()`; 20 levels; named commands
  ("Set aperture_diameter to 0.45 m").
- **Testing:** `pytest-qt` (`qtbot`), headless via `QT_QPA_PLATFORM=offscreen`; every
  menu/toolbar action gets a programmatic trigger test; a theme test asserts every
  top-level widget picks up the stylesheet (no unstyled gray-Qt leaks).
- **Errors:** `RadiantError` → modal with what/why/action/context verbatim; unexpected
  exceptions → error dialog with a traceback fold. No `except Exception: pass` anywhere
  in GUI code (Rules 15/17).
- **Modal-dialog lifetime (CU-216):** every handler-owned modal loop runs through
  `gui/dialog_lifetime.exec_dialog(dialog)`, never `dialog.exec()` directly. A parented
  `QDialog` closed by `exec()` returning is *hidden, not destroyed*, so without this the
  session accumulates one live dialog per open — measured at 10 dialogs after 10
  `Edit → Configurations…` cycles — and the next theme toggle re-polishes all of them
  (`apply_theme` → `QApplication.setStyleSheet` walks the live tree). `exec_dialog`
  `deleteLater()`s the dialog as the loop unwinds, which still leaves every result the
  handler reads afterwards (`SweepDialog.sweep_result`, `ConfigurationManagerDialog.shape()`)
  valid. The carve-out is a **builder** that *returns* an un-exec'd dialog for its caller to
  drive (`open_yaml_editor`, `open_inspector`): the deletion belongs to whichever handler
  later exec's it. `gui/tests/test_dialog_lifetime.py` pins both halves and statically
  scans for direct `.exec()` call sites.
