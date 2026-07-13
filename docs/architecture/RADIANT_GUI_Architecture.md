# RADIANT GUI Architecture

**Date:** 2026-04-07 · **Ratified v1 spec:** 2026-07-12
**Status:** Active — ratified v1 specification (2026-07-12). Supersedes the prior
"DESIGN TARGET" draft. This document is the binding specification the GUI
Development Plan (`docs/plans/GUI_Development_Plan.md`) implements phase by phase;
it describes v1 scope, the GUI-backend contract, the layout, the geometry-viewer
panel, the design system, and the scenario requirements matrix.
**Depends on:** `RADIANT_Personas.md`, `RADIANT_Signal_Chain_Architecture.md`,
`RADIANT_Geometry.md`, `api/sensor.py` (the scripting API this GUI is a view over).
**Governed by:** `docs/plans/GUI_Development_Plan.md` §§2–4 (ratified decisions,
scope, ground rules). Where this doc and the plan differ, the plan governs v1 scope
and this doc is updated in lock-step (Rule 20).

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
7. Scripting console: embedded IPython with live `sensor` / `result` objects.
8. File round-trip: Open/Save/Recent YAML via `Sensor.load()` / `sensor.save()`;
   undo/redo of parameter edits.

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

```python
class EvaluationWorker(QThread):
    finished_ok = Signal(object)      # ChainResult
    failed = Signal(object)           # the exception (RadiantError or otherwise)

    def __init__(self, sensor: Sensor) -> None:
        super().__init__()
        self._sensor = sensor

    def run(self) -> None:
        try:
            result = self._sensor.evaluate()
        except Exception as exc:      # re-raised into the GUI thread via signal — never swallowed (Rules 15/17)
            self.failed.emit(exc)
        else:
            self.finished_ok.emit(result)
```

The `except Exception` here is a thread-boundary hand-off, not a swallow: the exception
is re-emitted to the GUI thread, which renders it (RadiantError → what/why/action modal;
anything else → error dialog with a traceback fold). Nothing is silently dropped.

**Thread isolation (as shipped, GUI plan Phase 3).** The main window hands the worker a
private `sensor.clone()` taken on the GUI thread at schedule time, not the live sensor, so
a parameter edit that lands on the GUI thread while the chain is mid-run cannot race the
worker's read of the same object. The worker still performs exactly one `evaluate()` call
(one GUI action ↔ one API call); the clone is a thread-isolation mechanism, not a second
API surface. The status bar shows an indeterminate busy indicator while the worker runs,
and only one evaluation runs at a time — an edit that arrives mid-run is coalesced and
re-issued when the in-flight run finishes.

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

## 4. Layout

### 4.1 Top-Level Window Structure

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  RADIANT — leo_mwir_clear.yaml                                        [≡][□][X]│
├──────────────────────────────────────────────────────────────────────────────┤
│  File  Edit  View  Run  Tools  Help                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│ Geometry │ Source │ Atmosphere │ Optics │ Platform │ Spectral │ Detector │ Readout │ Performance │
│  [9-stage geometry-first signal-chain strip — clickable, health dots]          │
├────────────────┬─────────────────────────────────────────────────────────────┤
│  PARAMETERS    │  VISUALIZATION AREA                                          │
│  [Search box]  │  SNR 47.3  NEDT 23 mK  NIIRS 5.4  GSD 3.6 m  MTF_nyq 0.42   │
│  ▶ Geometry    │                                                              │
│  ▶ Source      │  [Main plot canvas — matplotlib figure]                      │
│  ▶ Atmosphere  │                                                              │
│  ▶ Optics      │                                                              │
│  ▶ Detector    │                                                              │
│  ▶ Readout     │                                                              │
├────────────────┴─────────────────────────────────────────────────────────────┤
│  Spectral │ MTF │ Noise Budget │ Variable Explorer │ YAML │ Console            │
│  [Detail tabs — current tab content fills this panel]                         │
│  [Status bar: "Evaluated in 0.22 s — 500 wavelength points" ]                │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Signal-Chain Strip (9 stages, geometry-first)

A horizontal strip of clickable stage buttons, in chain order per ADR-0006
(geometry-first): **Geometry → Source → Atmosphere → Optics → Platform → Spectral
Integration → Detector → Readout → Performance.** Each button shows the stage name and
a health dot:

```
 ● green  = evaluated, no issues
 ◑ yellow = warnings present
 ○ red    = stage raised an error
 ◌ gray   = stale / not yet evaluated
```

Clicking a stage is navigation only (no API call): it scrolls the parameter panel to
that stage's namespace and swaps the canvas to the stage's default visualization.

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

### 4.3 Parameter Panel (Left)

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
the resolved set via the public `Sensor.explain(dotpath)` surface (a structured accessor
is tracked as CU-105). A search box filters by substring across dot-paths.

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
offered.

**Two complementary edit paths.** The Value column keeps its fast in-place editor
(double-click column 1 → `ParameterEditDelegate`); the Parameter (name) and Source columns
open the full Parameter Editor dialog instead (double-click, or right-click → **Edit…** at
the top of the menu). Those two columns carry a `ReadOnlyCellDelegate` so Qt's default
rename editor never appears there, and the dialog is opened from the tree's `doubleClicked`
signal (which fires for derived rows too). The unit-enumeration seam being the underscored
`radiant.api.units._CONVERSIONS` re-export (rather than a named `units_for()` accessor) is
tracked as CU-109.

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

### 4.4 Visualization Area (Center)

A large matplotlib canvas (`FigureCanvasQTAgg`) rendering the existing `result.plot.*`
figures — no plotting logic is reimplemented in GUI code. The default figure depends on
the active stage:

| Active stage | Default visualization |
|-------------|----------------------|
| Geometry | Stage-0 scene: resolved input mode, derived slant/ground range, θ_o/η, solar angles (the 3D viewer panel, §6) |
| Source | Spectral radiance at target: L_source(λ) [W/m²/sr/µm] |
| Atmosphere | τ_atm(λ), L_path(λ), L_atm(λ) overlaid |
| Optics | Spectral radiance at aperture and post-optics; MTF curve |
| Platform | Smear/jitter MTF terms |
| Spectral Integration | In-band integrated radiance per frame |
| Detector | Spectral QE(λ); noise budget bar chart |
| Readout | Noise budget table + bar chart |
| Performance | System MTF; SNR summary |

A metric-badge row above the canvas always shows the current performance summary, every
value with its unit (R-UNITS): **SNR · NEDT · NIIRS · GSD · MTF@Nyquist.** A
metric that returns a result-typed failure (Rule 17 carve-out) shows its
`failure_reason`, not a blank.

**As shipped (GUI plan Phase 3).** Each badge reads one metric from the `ChainResult`
metric surface — SNR ← `snr`, NEDT ← `nedt_K`, NIIRS ← `niirs`, GSD ←
`gsd_geometric_mean_m`, MTF@Nyquist ← `mtf_at_nyquist` — and its **unit is sourced from
`ChainResult.metric_records()`** (the registry metadata), never hardcoded in the widget.
Consequently NEDT renders in its canonical unit **K** (e.g. `0.04463 K`), not the
mockup's illustrative `mK`; a per-metric display-scaling nicety (mK, µrad, …) is a later
enhancement (CU-108). A pure ratio / rating-scale unit (`dimensionless`, `NIIRS level`)
renders as a bare number, matching the mockup. The **default post-evaluate figure** while
no stage is selected (the stage strip lands in Phase 4) is the **MTF overlay**
(`result.plot.mtf()`) — the on-spec choice for the Performance row above, and the figure
that visibly responds to the D2 aperture-diameter edit. The **saturation banner** (below)
is placed **between the badge row and the canvas**.

**Per-stage default views as shipped (GUI plan Phase 4 Task A).** Selecting a stage swaps
the canvas per the table above, but every figure is drawn **only** from the existing
`result.plot.*` surface (`ResultPlotNamespace`: `mtf`, `noise_budget`, `psf`,
`mtf_budget`) — one GUI action ↔ one API call, no plotting in GUI code (§1.2 R-API). The
mapping (`radiant.gui.stage_views`) resolves each stage as:

| Stage | Shipped default view | Source |
|-------|---------------------|--------|
| Geometry | Derived-angle **readout** of `stage_outputs["geometry"]` (symbols + units); the 3D viewer is Phases 6–7 | stage outputs (verbatim) |
| Source | Source spectral radiance L_src(λ) [W/m²/sr/µm] | `result.plot.spectral_source()` |
| Atmosphere | τ_atm(λ) + L_path(λ) twin-axis overlay | `result.plot.spectral_atmosphere()` |
| Optics | MTF overlay | `result.plot.mtf()` |
| Platform | MTF overlay (shows the smear/jitter terms) | `result.plot.mtf()` |
| Spectral Integration | In-band (post-optics) spectral radiance [W/m²/sr/µm] | `result.plot.spectral_inband()` |
| Detector | Noise-budget bar chart | `result.plot.noise_budget()` |
| Readout | Noise-budget bar chart | `result.plot.noise_budget()` |
| Performance | MTF overlay (system MTF) | `result.plot.mtf()` |

Every §4.4 row now names a real `result.plot` accessor. The Source / Atmosphere /
Spectral Integration rows — which through Phase 4 Task A fell back to a themed "Gap 86"
panel because `result.plot` carried no spectral-radiance figure — render their spectral
figures directly once the three accessors landed (`api` commit f678dfd; the GUI
re-mapping is Phase 4 Task B). **Gap 86 is resolved**; the former gap panel
(`StageGapPanel`) is deleted. Geometry's default remains the angle summary — a key-value
readout of the derived stage outputs with units and symbols (R-UNITS), read verbatim
(data display, not physics).

The full-well **saturation banner** (§7.2 row 8, owner amendment 2) is a persistent,
non-dismissible banner shown whenever `result.well_status().is_saturated`; it renders the
well fill fraction (as a `×` multiple) and the accumulated-versus-capacity charge in
electrons (R-UNITS), and clears on the next unsaturated result. It reads the
`ChainResult.well_status()` surface (CU-101), never a `stage_outputs` dict-hop.

The **chain-warning strip** (`WarningStrip`, owner feedback 2026-07-13) sits between the
badge row and the canvas, carrying the **warn** design token — deliberately distinct from
the red saturation banner. Chain `UserWarning`s (saturation clip, NIIRS extrapolation, …)
used to print only to the terminal, invisible to a GUI user; the `EvaluationWorker` now
captures them with `warnings.catch_warnings(record=True)` + `simplefilter("always")` (so
the process-wide filter — including pytest's `filterwarnings=error` — cannot suppress or
raise them, and none is deduplicated away) and delivers them with the result. The strip
reads `⚠ N warnings` with the first message inline and, clicked, opens a themed
`WarningListDialog` listing every message verbatim; it clears on a warning-free evaluation.
Captured warnings are also re-logged, so nothing is swallowed (Rule 17) — script users lose
nothing. Capturing is safe against the global-filter mutation because at most one worker
runs at a time (edits coalesce into a single run) and the Qt thread never runs the chain.

### 4.5 Tabbed Detail Panel (Bottom)

v1 ships **six** tabs (the Sweep tab is v1.1 and absent from v1):

| Tab | Content |
|-----|---------|
| **Spectral** | Spectral radiance at all frames; wavelength-grid info; filter bandpass overlay |
| **MTF** | System MTF + all individual terms (table + overlay plot); MTF at Nyquist; RER; PSF plot; EE curve |
| **Noise Budget** | Full noise-budget table; bar chart; per-term explanation (`result.explain(term)`) |
| **Variable Explorer** | `result.inspect()` rendered as a collapsible tree |
| **YAML** | Read-only view of current config with provenance coloring; Export button |
| **Console** | Embedded IPython console with live `sensor` and `result` (GUI plan Phase 8) |
| ~~Sweep~~ | **v1.1** — inline parameter sweep (`sensor.sweep()`); absent in v1 |

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

**GUI → script hand-off.** In the Console tab `sensor` and `result` are live references
to the current GUI objects; any scripting-API call works. After a console mutation the
GUI marks its panels stale and offers one-click Refresh (explicit-and-honest beats magic
sync; GUI plan Phase 8).

---

## 6. Geometry Viewer Panel (v1, GUI plan Phases 6–7)

The Geometry Viewer is the Geometry stage's central visualization: a spatial schematic
of the sun/sensor/target relationship, optimized for understanding the angles that drive
the downstream radiometry. It is **not** a flight visualizer or a Cesium-style globe —
it is a CAD / engineering-drawing view: line-art forward, schematic, every element
labeled, every angle clickable. Engine: PyVista via `pyvistaqt.QtInteractor` (D5),
lifting the `dev_tools/geometry_gui_v2` scene library. Condensed from
`dev_tools/gui_mockups/geometry_viewer/radiant_geometry_handoff.md`.

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
- **Vectors:** sun→target (always on); sensor→target (always on); sun→ground
  illumination point G_i and sensor-LOS extension target→G_i (only when target
  altitude > 0).
- **Click-to-reveal angle annotations**, split by frame:
  - *Target-frame* (anchored at the target): θₛ, θᵥ, φₛ, φᵥ, Δφ, phase angle g.
  - *Ground-frame* (anchored at G_i, the radiometrically-relevant point when target
    altitude > 0): θₛ_g, θᵥ_g, φₛ_g, φᵥ_g.
- Target shape library: extended scene, plate, box, sphere, cylinder, cone, circle,
  ellipsoid, point source, custom-mesh placeholder.
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

### 6.4 Interaction & Visual Conventions (port exactly)

Click a vector → it becomes selected and its angle arcs/labels appear (clicking empty
space deselects). Click a 3D target body → the RPY triad appears and the side panel
switches to the RPY accordion. Editing side-panel values updates all readouts and the
scene live.

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

If OpenGL/VTK is unavailable (headless CI, restricted GPU) the viewer panel shows an
actionable message and the rest of the app works (GUI plan §4.4). Viewer tests use VTK
offscreen rendering.

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

| # | Feature | Requesting scenarios | Suggested disposition |
|---|---------|---------------------|----------------------|
| 1 | **Spreadsheet / XLSX import with unit-mapping dialog** | 1.2,1.3,1.4,2.1,2.2,2.3,2.5,3.2,3.3,5.1,5.2,5.4,6.1,6.3,7.1,7.2,7.4,7.5 (18) | **v1.1** — highest-leverage add; `Sensor.set(unit=)` + io loaders exist, only the dialog is missing |
| 2 | **Report / slide export (PDF, PowerPoint, XLSX)** | 1.1,1.4,2.2,2.3,2.5,3.2,5.1,5.2,5.3,5.4,6.3,7.1,7.2 (13) | **deferred (report generator, §9)**; near-universal — revisit priority in v1.1 |
| 3 | **Comparison mode (2+ configs side-by-side)** | 1.3,1.5,2.1,2.2,3.3,3.5,4.3,5.3,5.5,7.4 (10) | **deferred (comparison mode, §9)**; heavily requested — promote in v1.1 planning |
| 4 | **Measurement / reference-data overlay (lab points on model curves, residual sub-plot)** | 2.3,6.1,7.1,7.2,7.3,7.4,7.5 (7) | **gaps.md**; core to every persona-7 (test-engineer) workflow |
| 5 | **Library / preset browser (target, ship-class, sensor, weather, lab/TVAC presets)** | 2.1,2.3,3.2,4.1,4.2,7.1,7.2,7.3,7.4,7.5 (10) | **deferred (library browser, §9)** |
| 6 | **Detection / threshold traffic-light & go/no-go panels (DRI matrix, detection-range heatmap, ROC/P_d, feasibility)** | 1.3,2.5,3.2,4.1,4.2,4.5,6.4 (7) | **gaps.md** |
| 7 | **Data importers (ASTER material, measured-ε/QE/dark CSV, tape7/libRadtran, NETD vendor, Zemax Zernike)** | 1.1,1.3,2.1,4.3,4.5,5.1,5.2,6.2,7.5,8.1 (10) | **v1.1** (io loaders exist; dialogs needed); tape7/libRadtran flagged specifically |
| 8 | **Persistent `well_status` saturation banner** | 1.3,1.4,2.5,4.4,8.2 (5) | **v1 (Phase 3 banner; CU-101 API half is the Phase 3 prerequisite)** — pulled into v1 at the 2026-07-12 Phase 0 checkpoint (owner amendment 2). The GUI half (a persistent banner when the detector well clips) lands in GUI plan Phase 3; the API half is **CU-101** (expose `well_status`, only in `stage_outputs`, on the `ChainResult` metric surface), now a Phase 3 prerequisite |
| 9 | **2-D / multi-axis sweep + live heatmap** (beyond v1.1 single-axis) | 1.2,2.5,3.2 (3) | **v1.1+** (Sweep tab is single-axis in v1.1; 2-D grid is a further increment) |
| 10 | **Inverse-solve / optimizer UI (`solve_for`, reverse lookup, FoM optimize, constraint solve)** | 1.2,5.1,5.2,7.4 (4) | **gaps.md** (`solve_for` exists in API; no GUI surface) |
| 11 | **Atmosphere-source A/B toggle (parametric vs imported)** | 1.1,6.2 (2) | **gaps.md** (explicitly flagged) |
| 12 | **Curve digitizer (vendor PDF graph → CSV)** | 1.1 (1) | **gaps.md** |
| 13 | **Bespoke analysis panels (cooler-trade, 1/f PSD, GIQE-5 decomp, tornado, Jacobian, calibration fit-card, RSS jitter budget, Arrhenius-knee, WFE ErrorBudget)** | 2.1,2.2,3.2,5.1,5.4,6.1,6.5,7.1,7.2,7.5 (10) | **gaps.md** (each one-off; none in v1) |
| 14 | **Image simulator / 2-D scene / raster-map / stray-light-PSF / pupil-mask render** | 1.5,3.5,5.5,6.4 (4) | **deferred (image simulator, §9)** |
| 15 | **Orbit / coverage / access dashboards + map view** | 3.1,3.4 (2) | **gaps.md** (helpers console-callable; panels not in v1) |
| 16 | **Spectral-QE / co-varying QE(T) injection toggle** (Gaps 44/48) | 2.1,7.5 (2) | **gaps.md** (no config path — GUI-owned injection) |
| 17 | **Profile-driven temporal sweep (sweep along a loaded time series)** | 4.4 (1) | **gaps.md** (distinct sweep mode) |

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
       Export YAML… · Export JSON Result… · ───── · Quit (Ctrl+Q)
Edit   Undo (Ctrl+Z) · Redo · Reset to Defaults · Find Parameter (Ctrl+F)
View   Show/Hide Parameter Panel (F6) · Show/Hide Detail Panel (F7) ·
       Stage: … (Ctrl+1..9) · Dark/Light Theme · Font Size +/−
Run    Evaluate (F5) · Validate Only (Ctrl+R) ·
       Run Sweep…  [v1.1] · Monte Carlo…  [v1.1] · Batch Run…  [v1.1]
Tools  Python Console · Parameter Schema Browser · Explain Parameter… · Preferences…
Help   Documentation · Example Configs · About RADIANT
```

Actions not yet implemented in a given phase are present but **disabled** (GUI plan
Phase 1). Sweep / Monte Carlo / Batch remain disabled through v1 (D4).

---

## 11. Implementation Notes

- **PySide6 ≥ 6.6** (LTS); pin the minor version in `pyproject.toml`. Qt6-only, no Qt5
  target. Optional-dependency group: `gui = ["PySide6>=6.6", "matplotlib>=3.8",
  "qtconsole>=5.5", "pyvista", "pyvistaqt"]`; pyvista/pyvistaqt pinned to match
  `dev_tools/geometry_gui_v2`. Core RADIANT stays importable without the `gui` extra.
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
