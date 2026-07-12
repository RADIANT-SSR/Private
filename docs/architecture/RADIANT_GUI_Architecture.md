# RADIANT GUI Architecture

**Date:** 2026-04-07
**Status:** DESIGN TARGET — implementation not started; several contracts revised (see banner)
**Depends on:** RADIANT_Scripting_API.md, RADIANT_Personas.md, RADIANT_Signal_Chain_Architecture.md
**Scope:** Defines the technology choice, layout, GUI-backend interface, and interoperability contract for the RADIANT desktop GUI. Implementation is deferred. This document ensures the scripting API and future GUI share the same backend.

> **Reconciliation (2026-07-12, CU-079).** This document predates the
> capability audit and several of its contracts have since been revised:
> - **The `<100 ms` incremental-re-resolution / stale-DAG re-evaluation
>   contract is DECLINED for GUI v1** (owner-ratified 2026-07-11). Measured
>   full-chain evaluation is ~0.22 s, fast enough that simple full re-runs
>   suffice; there is no incremental-DAG engine and none is planned for v1.
>   Treat every "< 100 ms / incremental re-resolution / stale subgraph"
>   claim below as design-target-only.
> - **Parameter dot-paths quoted in examples are illustrative and may not
>   match the shipped `_schema.py`** — generate the parameter surface from
>   `Sensor.parameter_defs()` (Gap 70), never by transcribing this doc.
> - The File-menu / persistence, schema-introspection, progress/cancel, and
>   metric-metadata surfaces the GUI binds to **are** now implemented
>   (Gaps 67/70/71/72). §4 already reflects those.

---

## 1. Technology Choice: PySide6 (Qt6 Native)

### Decision

**Native desktop application using PySide6 (Qt 6).**

Not: React + FastAPI backend. Not: Jupyter widgets.

### Evaluation

#### Option A: Web (React + FastAPI)

**Pros:** Modern, browser-accessible, good visualization libraries (plotly, d3), cloud-deployable.

**Cons:**
- Two separate runtime processes (FastAPI server + browser); adds deployment complexity.
- State synchronization between browser and Python server introduces latency and race conditions.
- Requires npm/node toolchain for build. Aerospace users on restricted networks often cannot install npm packages.
- Cannot embed in a classified environment without an internal server.
- The target users (Sarah, Mike, Tom) already work in Python environments. Browser-based tools add a layer of context-switching.
- JSON serialization of spectral arrays (500+ points) across process boundary on every parameter change is expensive.

#### Option B: Jupyter Widgets (ipywidgets / panel)

**Pros:** Users who already use Jupyter get GUI-like interaction. No separate application to install. Notebook workflow preservation.

**Cons:**
- Jupyter widgets are designed for notebook cells, not multi-panel professional applications. Building the signal chain strip, parameter panel, and detail tabs in ipywidgets produces brittle, hard-to-maintain code.
- No standalone binary distribution. Requires a Jupyter server.
- Poor experience outside Jupyter (VS Code Jupyter extension is good, but lab-style multi-panel layout is not suited to notebook cells).
- Lisa (P4) wants a standalone app she can hand to an analyst who doesn't run Jupyter.

#### Option C: PySide6 / Qt6 Native (Selected)

**Pros:**
- Single-process: GUI and RADIANT backend run in the same Python process. No serialization, no IPC, no state sync. A `sensor.set()` call from the GUI is the same call the user makes in a script.
- Cross-platform standalone binary via `PyInstaller`/`cx_Freeze`. Distributable without Python.
- Mature ecosystem: Qt has been the standard for scientific instrumentation GUIs (FLIR tools, Zemax OpticStudio, etc.) for 30 years. The persona users are familiar with this style.
- PySide6 is the official Qt Python binding (LGPL), no licensing cost.
- Matplotlib integrates via `matplotlib.backends.backend_qtagg`. All `result.plot.*` methods work inside the GUI without modification.
- Thread model: background computation in `QThread` or `concurrent.futures`, GUI remains responsive. Qt's signal/slot mechanism handles thread-safe result delivery.
- `<100 ms` responsiveness requirement for parameter changes is achievable with incremental re-resolution (only stale subgraph is re-evaluated).

**Cons:**
- Requires Qt installation. Mitigated by bundled binary distribution.
- Qt styling (dark mode, custom themes) requires CSS-like QSS. More effort than browser CSS.
- Not browser-accessible. If remote access is needed, a future web front-end can be layered on top of the same scripting API.

### Justification from Personas

| Persona | GUI requirement | How PySide6 satisfies |
|---------|----------------|----------------------|
| Sarah (P1) | Parametric sweep plots, one-page summary export | Sweep UI triggers `sensor.sweep()`, renders into embedded matplotlib canvas |
| Mike (P2) | Noise budget breakdown, drill-down into individual terms | Tabbed detail panel with noise budget tree; same data as `result.noise_budget()` |
| Lisa (P4) | Standalone app, no coding required, batch execution | PySide6 bundles as standalone EXE/APP; batch dialog calls `BatchRunner` |
| Tom (P5) | MTF plot with all components, RER, PSF viewer | MTF tab with individual MTF term overlays; PSF 2D image view |
| Raj (P3) | Load sensor file, specify scenario, get answer | File open dialog → scenario panel → evaluate button → results panel |

---

## 2. Layout

### 2.1 Top-Level Window Structure

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  RADIANT v1.0.0 — leo_mwir_clear.yaml                                  [≡][□][X]│
├──────────────────────────────────────────────────────────────────────────────┤
│  File  Edit  View  Run  Tools  Help                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│  ← Source │ Atmosphere │ Optics │ Platform │ Detector │ Readout │ Performance →│
│  [Signal chain strip — clickable stage tabs with health indicators]           │
├────────────────┬─────────────────────────────────────────────────────────────┤
│  PARAMETERS    │  VISUALIZATION AREA                                          │
│  ─────────     │  ─────────────────                                          │
│  [Search box]  │                                                              │
│                │  [Main plot canvas — matplotlib figure]                      │
│  ▶ Optics      │                                                              │
│    D = 0.30 m  │  SNR = 47.3  NEDT = 23 mK  NIIRS = 5.4  GSD = 3.6 m       │
│    f = 1.20 m  │                                                              │
│    f/# = 4.0   │                                                              │
│    WFE = 0.07λ │                                                              │
│  ▶ Detector    │                                                              │
│    HgCdTe      │                                                              │
│    18 µm pitch │                                                              │
│    80 K        │                                                              │
│  ▶ Readout     │                                                              │
│    5 ms        │                                                              │
│    CDS on      │                                                              │
│  ▶ Filter      │                                                              │
│  ▶ Geometry    │                                                              │
│  ▶ Atmosphere  │                                                              │
│  ▶ Target      │                                                              │
│  ▶ Background  │                                                              │
│  ▶ Platform    │                                                              │
├────────────────┴─────────────────────────────────────────────────────────────┤
│  Spectral │ MTF │ Noise Budget │ Sweep │ Variable Explorer │ YAML │ Console   │
│  ─────────────────────────────────────────────────────────────────────────── │
│  [Detail tabs — current tab content fills this panel]                         │
│                                                                               │
│  [Status bar: "Evaluated in 0.23 s — 500 wavelength points" ]                │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Signal Chain Strip

A horizontal strip of clickable stage buttons at the top of the main area. Each button:
- Shows the stage name
- Shows a health indicator: green (evaluated, no issues), yellow (warning), red (error), gray (not yet evaluated)
- Clicking a stage jumps the parameter panel to that stage's parameters and the visualization to the stage's primary output

```
┌─────────┐  ┌────────────┐  ┌────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌─────────────┐
│ Source  │→ │ Atmosphere │→ │ Optics │→ │ Platform │→ │ Detector │→ │ Readout │→ │ Performance │
│   ●     │  │     ●      │  │   ●    │  │    ●     │  │    ●     │  │    ●    │  │     ●       │
└─────────┘  └────────────┘  └────────┘  └──────────┘  └──────────┘  └─────────┘  └─────────────┘
   ● green = OK    ◑ yellow = warning    ○ red = error    ◌ gray = stale
```

### 2.3 Parameter Panel (Left)

A tree-structured parameter panel that mirrors the YAML hierarchy. Groups are collapsible. Each parameter is an editable row:

```
▼ sensor
  ▼ optics
      aperture_diameter    [0.30  ] m        ● derived: f_number = 4.0
      focal_length         [1.20  ] m
      f_number             [ 4.0  ]          ⚡ derived
      obscuration_ratio    [0.33  ]
      wfe_rms              [0.07  ] waves
      temperature          [280   ] K
  ▼ detector
      material             [HgCdTe ▾]
      pixel_pitch          [18.0  ] µm
      cutoff_wavelength    [ 5.0  ] µm
      ...
```

**Interaction design:**
- Editable fields are text inputs with units displayed as suffix labels.
- Changing a value immediately calls `sensor.set(param, value)` and triggers incremental re-evaluation in a background thread.
- Derived parameters are shown with a ⚡ icon and are non-editable (grayed out).
- Parameters with active tolerances show a ±σ badge.
- Right-clicking any parameter shows: Copy dot-path, Set Tolerance, Explain, Reset to Default.

**Search box:** Type any substring to filter the parameter tree. "aperture" matches `sensor.optics.aperture_diameter`. "temp" matches all temperature parameters across all sections.

### 2.4 Visualization Area (Center)

A large matplotlib canvas embedded via `FigureCanvasQTAgg`. The displayed figure depends on the active stage:

| Active stage | Default visualization |
|-------------|----------------------|
| Source | Spectral radiance at target: L_source(λ) [W/m²/sr/µm] |
| Atmosphere | τ_atm(λ), L_path(λ), L_atm(λ) all overlaid |
| Optics | Spectral radiance at aperture and post-optics; MTF curve |
| Detector | Spectral QE(λ); noise budget bar chart |
| Readout | Noise budget table + bar chart |
| Performance | System MTF; SNR vs. parameter (last sweep if any) |

A row of metric badges above the canvas always shows the current performance summary:

```
SNR = 47.3    NEDT = 23 mK    NIIRS = 5.4    GSD = 3.6 m    MTF_nyq = 0.42
```

These update live (< 100 ms) for fast parameter changes.

### 2.5 Tabbed Detail Panel (Bottom)

Fixed-height panel with 7 tabs. All tabs show data from the last evaluated result.

| Tab | Content |
|-----|---------|
| **Spectral** | Spectral radiance at all frames; wavelength grid info; filter bandpass overlay |
| **MTF** | System MTF + all individual terms; MTF at Nyquist; RER; PSF plot; EE curve |
| **Noise Budget** | Full noise budget table; bar chart; per-term explanation |
| **Sweep** | Run a parameter sweep inline: parameter picker, value range, metric picker, plot |
| **Variable Explorer** | `result.inspect()` tree rendered as collapsible tree widget |
| **YAML** | Read-only view of current config in YAML format; Export button |
| **Console** | Embedded IPython console with `sensor` and `result` pre-loaded |

---

## 3. GUI-Backend Interface

### 3.1 The Backend is the Scripting API

The GUI does not have its own data model. It is a view over the scripting API's `Sensor` and `ChainResult` objects. Every action in the GUI maps to exactly one scripting API call.

```
GUI Action                         Scripting API Call
──────────────────────────────────────────────────────
Open YAML file                     sensor = Sensor.load(path)
Edit parameter value               sensor.set(param_name, value)
Click "Evaluate"                   result = sensor.evaluate()
Stage strip button click           (navigation only — no API call)
Sweep tab: Run Sweep               sweep = sensor.sweep(param, values, metric)
Monte Carlo tab: Run MC            mc = sensor.monte_carlo(n_trials)
Export YAML                        sensor.save(path)
Export result archive              result.save(path)   # reload: ChainResult.load
Console: type Python               direct IPython evaluation in sensor namespace
```

This mapping is one-to-one and explicit. No GUI component contains physics logic.

### 3.2 Threading Model

The GUI runs on the Qt main thread. Signal chain evaluations run in a `QThread` worker. The worker emits signals when evaluation completes or when intermediate progress is available.

```python
class EvaluationWorker(QThread):
    result_ready = Signal(ChainResult)
    progress = Signal(str, float)     # (stage_name, fraction_complete)
    error_occurred = Signal(str)

    def __init__(self, sensor: Sensor):
        self._sensor = sensor

    def run(self):
        try:
            # emit progress per stage
            result = self._sensor.evaluate(
                on_stage_complete=lambda name, frac: self.progress.emit(name, frac)
            )
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))
```

**Latency targets:**

| Operation | Target latency | How achieved |
|-----------|---------------|--------------|
| Parameter edit → metric badge update | < 100 ms | Incremental re-resolution: only stale DAG subgraph re-evaluated |
| Full chain evaluation (single band) | < 500 ms | All-numpy signal chain; no I/O except spectral data load |
| Full chain with MODTRAN file load | < 2 s | MODTRAN file is cached after first load; subsequent evaluations reuse cached spectral data |
| Parametric sweep (20 points) | < 5 s | Parallel execution via `BatchRunner(n_jobs=-1)` |
| Monte Carlo (1000 trials) | < 30 s | BatchRunner with all cores; progress reported via worker signal |

Operations longer than 500 ms show a progress indicator in the status bar. Operations longer than 2 s show a modal progress dialog with cancel button.

### 3.3 Incremental Evaluation

When a parameter changes, the GUI does not re-evaluate the full chain. It calls `sensor.set()`, which triggers the parameter resolver's invalidation logic (mark stale subgraph). The GUI then calls a fast re-evaluation that only runs stages downstream of the changed parameter.

```
Change: sensor.optics.aperture_diameter = 0.45 m

Stale stages: OpticsStage, PlatformStage, SpectralIntegrationStage,
              DetectorStage, ReadoutStage, PerformanceStage
Clean stages: SourceStage, AtmosphereStage (atmosphere doesn't depend on aperture)

→ Re-run from OpticsStage forward only.
→ Elapsed: ~40 ms (vs. ~200 ms for full chain).
```

The parameter resolver's DAG makes stale-stage computation automatic. The GUI does not need to know which parameters affect which stages.

### 3.4 Live Feedback Loops

Certain parameters are "fast" (< 10 ms re-evaluation): those that only affect scalar post-processing (integration time, gain, ADC bits). For these, the GUI can update metric badges on every keystroke as the user types.

Other parameters are "slow" (> 50 ms): those that require spectral reintegration or atmosphere re-evaluation. For these, the GUI debounces with a 200 ms timer — it waits until the user stops typing before triggering re-evaluation.

Fast parameters (metric update on every keystroke): `integration_time`, `gain`, `n_tdi`, `n_coadds`, `adc_bits`, `target.temperature`

Slow parameters (debounced 200 ms): `aperture_diameter`, `focal_length`, `pixel_pitch`, `filter.*`, `atmosphere.*`, `wfe_rms`

Very slow (full re-evaluation with progress bar): `atmosphere.modtran_file` (triggers file I/O)

---

## 4. Interoperability: GUI ↔ Scripting API ↔ YAML

All three representations (GUI, Python script, YAML file) are views of the same `Sensor` object. They are interchangeable at any point.

### 4.1 GUI → YAML

Clicking File → Export YAML calls `sensor.save(path)` (implemented, Gap 67 2026-07-11). The saved YAML holds the explicitly-set inputs plus a `_radiant` metadata block (wavelength_points, tolerances) — defaults and derived values are *not* written, so a reload reproduces the original resolution and provenance splits exactly (`RADIANT_Config_Format.md` §1.7). For a fully-specified documentation export with every resolved value, use `radiant.io.config.save_config(params, path, scope="resolved")`. The user can load the saved YAML in a script.

### 4.2 YAML → GUI

File → Open YAML calls `Sensor.load(path)` (implemented, Gap 67 2026-07-11). The GUI displays all parameters from the YAML, with provenance badges distinguishing explicit values from defaults and derived values. GUI edits override in the highest-priority layer (equivalent to CLI `--set`).

### 4.3 Script → GUI (Hand-off)

A user running a sweep in a Jupyter notebook can open the interesting operating point in the GUI:

```python
# In Jupyter:
s = Sensor.load("config.yaml")
s.set("sensor.optics.aperture_diameter", 0.35)   # operating point of interest

# Launch the GUI, pre-loaded with this sensor state:
s.gui()   # opens RADIANT GUI window with current sensor state
```

`sensor.gui()` serializes the current state to a temporary YAML and launches the GUI process, which loads that YAML. The GUI is a subprocess; the Jupyter kernel continues running.

### 4.4 GUI → Script (Hand-off)

In the GUI Console tab, `sensor` is a live reference to the current GUI sensor object. The user can type:

```python
# In the GUI Console tab:
sweep = sensor.sweep("sensor.optics.aperture_diameter", [0.20, 0.25, 0.30, 0.35, 0.40])
sweep.to_csv("/tmp/sweep_result.csv")
```

The Console tab is a full IPython terminal. Any scripting API call works. The result is immediately reflected in the GUI visualization area.

---

## 5. Mock-up: Key Panels

### 5.1 Noise Budget Tab (Bottom Panel)

```
Noise Budget                          Signal: 12,450 e-    SNR: 47.3
────────────────────────────────────────────────────────────────────────
■ photon_shot       111.6 e-  ████████████████████████░░░░░░░  18.0%
■ dark_current_shot  89.2 e-  ████████████████████░░░░░░░░░░░  11.5%
■ read_noise         25.0 e-  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░   0.9%
■ 1_over_f           12.0 e-  ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0.2%
■ ipc_crosstalk       8.1 e-  █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0.09%
■ prnu_residual       7.3 e-  █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0.08%
■ dsnu_residual       4.2 e-  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0.03%
■ quantization        3.2 e-  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0.02%
────────────────────────────────────────────────────────────────────────
Total (RSS)         263.3 e-                                  100.0%

                  [Export CSV]  [Copy Table]  [Explain Selected Term]
```

Clicking a row explains that noise term (calls `result.explain(term)`, shows physics derivation in a tooltip/popup).

### 5.2 MTF Tab (Bottom Panel)

```
MTF Budget                            MTF @ Nyquist = 0.42   RER = 0.28
────────────────────────────────────────────────────────────────────────
[Matplotlib MTF plot — spatial freq (cycles/mrad) on X, MTF on Y]
    Curves: system (bold), diffraction, wfe, smear, jitter, pixel, ipc

Nyquist frequency: 27.8 cycles/mrad
                        MTF @ Nyquist
system:                    0.42
  diffraction:             0.68
  wfe (Marechal):          0.87
  smear (3 µrad, 5 ms):    0.93
  jitter (3 µrad RMS):     0.91
  pixel aperture:          0.64
  ipc (α=0.02):            0.96

          [Export Plot]  [Export CSV]  [Show PSF]  [Show EE Curve]
```

### 5.3 Sweep Tab (Bottom Panel)

```
Sweep Setup
────────────────────────────────────────────────────────────────────────
Parameter:  [sensor.optics.aperture_diameter          ▾]
Min: [0.10] m   Max: [0.60] m   N: [26]   Scale: (●) Linear  ( ) Log

Metric:  [snr ▾]   Threshold: [40 ]   [▶ Run Sweep]

[Matplotlib sweep plot — parameter value on X, metric on Y]
  Red dashed horizontal line at threshold=40
  Vertical marker at threshold crossing: D = 0.31 m

Threshold crossing: sensor.optics.aperture_diameter = 0.31 m
                    [Export CSV]  [Open at this Point]
```

"Open at this Point" sets `sensor.set("sensor.optics.aperture_diameter", 0.31)` and re-evaluates the full chain, updating all panels.

### 5.4 YAML Tab (Bottom Panel)

```yaml
# YAML Tab — read-only view of current state
# Generated: 2026-04-07T14:30:00Z  |  RADIANT v1.0.0
# [Copy]  [Export YAML...]  [Diff vs. original...]

sensor:
  optics:
    aperture_diameter: 0.30   # m (user_set — sensors/baseline_mwir.yaml)
    focal_length: 1.20        # m (user_set — sensors/baseline_mwir.yaml)
    f_number: 4.0             # derived: focal_length / aperture_diameter
    obscuration_ratio: 0.33   # (user_set)
    wfe_rms: 0.07             # waves (user_set)
    temperature: 280          # K (user_set)
  detector:
    ...
```

Parameters modified from the GUI since file load are shown in a different color (amber). Parameters carrying their default value are shown in gray.

---

## 6. Menu Structure

```
File
  New                  Ctrl+N   — create blank config
  Open YAML...         Ctrl+O   — open config file
  Open Recent          →        — last 10 files
  Save                 Ctrl+S   — save current state to YAML
  Save As...           Ctrl+Shift+S
  Export XLSX...                — export to Excel
  Export JSON Result...         — export last result + provenance
  ─────
  Quit                 Ctrl+Q

Edit
  Undo                 Ctrl+Z   — undo last parameter change (20-level history)
  Redo                 Ctrl+Shift+Z
  Reset to Defaults             — reset all user-set values to schema defaults
  Find Parameter       Ctrl+F   — focus search box in parameter panel

View
  Show/Hide Parameter Panel     F6
  Show/Hide Detail Panel        F7
  Stage: [stage name]           Ctrl+1..7  — jump to stage
  Dark Mode
  Font Size +/-

Run
  Evaluate             F5       — run full chain evaluation
  Validate Only        Ctrl+R   — validate config without evaluating
  Run Sweep...                  — open sweep dialog
  Monte Carlo...               — open Monte Carlo dialog
  Batch Run...                  — open batch execution dialog

Tools
  Python Console                — focus Console tab (same as clicking tab)
  Parameter Schema Browser      — browse all ParameterDef objects
  Explain Parameter...          — explain provenance for a named parameter
  Preferences...                — font size, color theme, default paths, n_jobs

Help
  Documentation                 — open docs in browser
  Example Configs               — open example config directory
  About RADIANT
```

---

## 7. Deferred to Phase 2

The following GUI capabilities are explicitly deferred. The Phase 1 architecture must not preclude them.

| Capability | Why deferred | Precondition |
|------------|-------------|-------------|
| 2D image simulator (focal plane array visualization) | Requires scene/image modeling; separate module | RADIANT Scene module (future) |
| Library browser (sensor library, target library) | Database/catalog UI; nontrivial | Library management system |
| Report generator (auto-generated PDF summary) | Nice to have; high engineering effort | PDF templating |
| MATLAB bridge | Small user population; Python is primary | Stable API (done) |
| Plugin UI (custom stage configuration panels) | Plugin API is stable; UI integration is effort | Phase 1 plugin system |
| Remote computation (submit jobs to HPC cluster) | Infrastructure; separate from GUI | Cluster job management |
| Real-time comparison mode (two sensors side by side) | UI complexity; multi-result state management | Core API (stable) |

The scripting API is already sufficient for all of these use cases programmatically. The GUI Phase 2 work adds visual interfaces for workflows that are currently script-only.

---

## 8. Implementation Notes (for Phase 2 Planning)

These are notes for the implementation team, not architecture decisions.

**Framework version pinning:** Use PySide6 ≥ 6.6 (LTS). Pin the minor version in `pyproject.toml`. Qt6 APIs that break Qt5 compatibility are acceptable — there is no Qt5 target.

**Matplotlib backend:** Use `matplotlib.backends.backend_qtagg.FigureCanvasQTAgg`. The GUI's `result.plot.*` calls are identical to the scripting API calls — the figure is created by the same code in both cases. The only difference is whether the figure is shown in a Qt widget or a standalone matplotlib window.

**Main window class:** `RADIANTMainWindow(QMainWindow)`. Subcomponents are `QDockWidget`-based for the parameter panel and detail panel, allowing user-configurable docking.

**Theming:** Ship with one built-in dark theme (default) and one light theme. Use Qt QSS stylesheets stored in `radiant/gui/themes/`. Do not re-implement the entire Qt widget palette — customize only colors, not widget geometry.

**Undo/redo:** `QUndoStack` with `QUndoCommand` wrapping each `sensor.set()` call. Maximum 20 levels. Commands are named: "Set aperture_diameter to 0.45 m". Redo is "Re-set aperture_diameter to 0.45 m".

**Testing:** Qt GUI tests use `pytest-qt` (`qtbot` fixture). Every action in the menu structure has a corresponding test that triggers it programmatically and verifies the result without human interaction.
