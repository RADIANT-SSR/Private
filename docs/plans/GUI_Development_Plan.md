# GUI Development Plan — RADIANT Desktop GUI v1

**Status:** Active (owner-ratified 2026-07-12; revised 2026-07-14)
**Date:** 2026-07-12 · **Revised:** 2026-07-14 (redesign reconciliation + go-forward sequence)
**Owner decisions record:** §2 (D1–D7)
**Depends on:** `docs/plans/Geometry_Stage_Plan.md` (Complete and archived 2026-07-12),
`docs/architecture/RADIANT_GUI_Architecture.md` (the authoritative layout + per-stage
content spec — this plan references it, never re-duplicates it, per Rule 20)
**Supersedes:** `docs/archive/Geometry_GUI_v2_Plan.md` (geometry-viewer scope; archived
2026-07-12)
**Executes as:** one phase = one agent task = one conversation (per CLAUDE.md task discipline)

---

## 0. Revision Note (2026-07-14) — why this plan changed

This plan was written (2026-07-12) for a **"stage strip + shared canvas + bottom detail
tabs"** GUI, sequenced as Phases 0–9. Two owner-ratified redesigns have since landed and
**Phases 0–7 shipped**, so the original phase list no longer describes the built product:

1. **Contextual per-stage layout** (owner-ratified 2026-07-13). The global metric-badge
   row + shared canvas + bottom detail tabs were **replaced** by a *contextual per-stage
   workspace*: the 9-stage strip is the single primary navigation, the center shows only
   the selected stage's content (Inputs / Outputs / Plots), and a **persistent right
   rail** carries pinned values, the Edit-Config modal, Messages, and the Evaluate footer.
   Nothing built was discarded — every Phase 1–4 piece was relocated
   (`RADIANT_GUI_Architecture.md` §4, §4.7 record the exact mapping). Rule 24/27:
   the old structure is **superseded**, not kept alongside the new one.
2. **2D orthographic Qt schematic viewer** (ADR-0007, owner-ratified 2026-07-14). The 3D
   PyVista/VTK geometry viewer of D5 was **replaced** by a pure-Qt `QPainter` 2D
   orthographic schematic — no VTK/OpenGL dependency, always available, faithful to the
   mockup's line-art. The three-backend degradation ladder is gone.

This revision (a) records what shipped and marks the superseded structure, and (b)
proposes the **go-forward phase sequence** for the remaining GUI value — the bespoke
per-stage content the owner specified in `RADIANT_GUI_Architecture.md` §4.4.1, most of
which is gated on framework **plotting** capability that does not yet exist. The
go-forward sequence (§7) is a **proposal pending owner ratification**; §8 lists the
choices the owner ratifies.

**Authoritative surfaces (Rule 20).** The shipped layout, the right rail, the 2D
schematic, and the binding **per-stage content spec** live in
`docs/architecture/RADIANT_GUI_Architecture.md` (§4 layout, §4.4.1 per-stage content
classification, §6 the shipped schematic) and `docs/adr/0007-3d-viewer-visual-direction.md`
(the ratified 2D-schematic decision). This plan sequences the work; the arch doc defines
the content. Where they differ, the arch doc governs content and this plan governs
sequence.

---

## 1. Goal

Ship RADIANT GUI v1: a PySide6 desktop application that is a *view over the scripting
API* — every GUI action maps to exactly one `Sensor` / `ChainResult` call, no physics in
GUI code. v1 delivers the core evaluate loop (open YAML → edit parameters → evaluate →
metrics + plots), the geometry-first **contextual per-stage** workspace (a permanent
All-Parameters tree, a per-stage center view, and a persistent right rail), the 2D
geometry schematic viewer, the bespoke per-stage instruments, and the embedded scripting
console.

The plan is deliberately incremental: **every phase ends with something the owner can
launch and click**, followed by a feedback round before the next phase starts. The owner
is not a software developer; acceptance is by using the app, not by reading code. The
shipped **Geometry screen** (stage-0 mode forms + frame-grouped derived-angle readout +
the 2D schematic) is the **gold-standard per-stage instrument** — every go-forward
per-stage phase (§7) brings its stage up to that standard.

---

## 2. Ratified Decisions (owner)

| # | Decision | Ruling |
|---|----------|--------|
| D1 | Technology | **PySide6 / Qt6 native** (2026-07-12). HTML/React mockups are the *visual spec*, ported to Qt — not the implementation medium. |
| D2 | First runnable milestone | **Evaluate loop first** (2026-07-12): open YAML → parameter tree → Evaluate → metrics + plot, before other panels. **Shipped** (Phase 3). |
| D3 | Geometry stage-0 dependency | **Wait for stage 0** (2026-07-12). Satisfied — Geometry stage complete/merged 2026-07-12. |
| D4 | v1 must-haves beyond the core | **Geometry viewer** and **scripting console** in v1; **Sweep tab** and **Batch / Monte Carlo** deferred to **v1.1** (2026-07-12). |
| D5 | 3D viewer engine | ~~PyVista via `pyvistaqt.QtInteractor`, lifting `geometry_gui_v2`~~ (2026-07-12) — **SUPERSEDED by D7.** Matplotlib remains the engine for all 2D plots. |
| **D6** | **Contextual per-stage layout** (owner-ratified **2026-07-13**) | The global-badge-row + shared-canvas + **bottom-detail-tabs** design is **replaced** by the **contextual per-stage workspace** (`RADIANT_GUI_Architecture.md` §4): 9-stage strip = single primary nav, per-stage center view, persistent right rail (Pinned / Edit Config / Messages / Evaluate footer). Rearrangement + additions, **not a rebuild** — every shipped piece relocated (§4.7). **Shipped** (contextual-layout retrofit, 2026-07-13). |
| **D7** | **2D schematic viewer engine** (owner-ratified **2026-07-14**, ADR-0007) | The 3D PyVista/VTK viewer (D5) is **replaced** by a pure-Qt `QPainter` **2D orthographic schematic** porting the mockup's `geometry.js` projection. No VTK/OpenGL dependency; always available; the three-backend degradation ladder is removed. **Shipped** (schematic Pass 1 + Pass 2, 2026-07-14). |

### 2.1 Phase 0 Checkpoint Amendments (owner, 2026-07-12, still binding)

- **Amendment 1** — **light theme is the v1 launch default**, dark the alternate; both
  from one token set, View-menu toggle in Phase 9.
- **Amendment 2** — the persistent, non-dismissible **`well_status` saturation banner**
  is in v1 (shipped in Phase 3; CU-101 API half landed).

---

## 3. Scope

### In scope (v1)

1. Application shell: main window, menus, **9-stage** geometry-first strip (the single
   primary navigation), a permanent left **All-Parameters** tree, a per-stage **center**
   view, a **persistent right rail** (Pinned cards / Edit-Config modal / Messages /
   Evaluate footer), status bar. *(No bottom detail-tab dock — dissolved by D6.)*
2. Schema-driven parameter tree + per-stage Inputs, generated from
   `Sensor.parameter_defs()` — never a transcribed parameter list (Gap 70).
3. Evaluate loop: background-thread `sensor.evaluate()`, pinnable metric cards, actionable
   error dialogs (`RadiantError` what/why/action), debounced full-chain re-evaluation, the
   saturation banner.
4. **Bespoke per-stage instruments** — each stage's Inputs / Outputs / Plots per the
   ratified content spec (`RADIANT_GUI_Architecture.md` §4.4.1). The evaluate-loop
   surfaces (metric cards, the shipped `result.plot.*` figures, the relocated MTF/Noise
   panels) already back several stages; the remainder is the go-forward work (§7).
5. Geometry screen: stage-0 input-mode forms + frame-grouped derived-angle readout from
   `stage_outputs["geometry"]` — the **gold-standard** instrument. **Shipped.**
6. **2D geometry schematic viewer** (D7): not-to-scale line-art schematic — sun/sensor/
   target glyphs, vectors, revealable angle arcs, shape library, RPY triad. **Shipped.**
7. Scripting console: embedded IPython with live `sensor` / `result` (go-forward Phase 8).
8. File round-trip: Open/Save/Recent YAML via `Sensor.load()` / `sensor.save()`;
   undo/redo of parameter edits (go-forward Phase 9).

### Out of scope (v1) — do not implement, even partially

- Sweep tab UI, Batch / Monte Carlo dialogs (v1.1 — D4).
- Everything in arch-doc §9 "Deferred to Phase 2" (image simulator, library browser,
  report generator, comparison mode, plugin UI, remote compute).
- PyInstaller / standalone-binary packaging (v1.x; v1 runs from the repo venv).
- Incremental / stale-DAG re-evaluation (DECLINED for v1, CU-079 — full re-runs only).
- Any change to physics, schemas, or golden results. The GUI is results-neutral by
  construction; a golden-test diff in any GUI PR is a defect. **The go-forward
  framework-plot phases (§7) are results-neutral view/accessor additions** — they persist
  and plot already-computed intermediates; a golden diff in one of them is likewise a defect
  (Gap 91 is the one to watch: verify no double-count against the at-aperture path).

---

## 4. Architecture Ground Rules (binding on every phase)

1. **Backend is the scripting API** (arch doc §3.1). One GUI action ↔ one API call.
   If the API lacks a hook the GUI needs, the phase *stops* and files the gap in
   `docs/tracking/gaps.md` — GUI code never reaches into stage internals or
   re-implements a computation. *(This is exactly why the go-forward per-stage phases are
   gated on framework-plot phases: the missing plots are API gaps, filed as Gaps 89–92.)*
2. **Package location:** `src/radiant/gui/`. Layout:

   ```
   src/radiant/gui/
   ├── __init__.py        # launch_gui(sensor: Sensor | None) entry
   ├── app.py             # QApplication bootstrap
   ├── main_window.py     # RADIANTMainWindow(QMainWindow)
   ├── widgets/           # one widget class per file (Rule 19 spirit)
   ├── viewer/            # the 2D schematic viewer (D7) — projection, canvas, overlays
   ├── workers.py         # QThread evaluation worker
   ├── themes/            # QSS stylesheets (light default, dark alternate)
   └── tests/             # pytest-qt tests
   ```

3. **Import rules** (shipped, Phase 1): `gui/` may import `radiant.api` + `radiant.core`
   (+ PySide6, matplotlib, qtconsole); **no PyVista/VTK** (removed with the 2D pivot, D7);
   no physics stage directly, no `io`/`cli`. `cli/` gains `radiant.gui` (lazy, for
   `radiant gui`). Enforced by import-linter; the `CLAUDE.md` import table and
   `RADIANT_File_Tree.md` are kept in lock-step (Rule 20).
4. **Dependencies:** optional group in `pyproject.toml`. The `gui` extra still pins
   `pyvista`/`pyvistaqt` from the pre-D7 design; **no `radiant.gui` code imports them**
   after the 2D pivot — dropping the pins is **CU-134**, folded into Phase 9 (or the next
   `pyproject` touch). Core RADIANT must remain importable and fully functional without the
   `gui` extra. With the 2D schematic there is no OpenGL/VTK requirement, so the viewer is
   always available (the graceful-degradation ladder of the old 3D design is retired).
5. **Threading:** Qt main thread never runs the chain. Evaluations run in a worker
   `QThread` (against a private `sensor.clone()` taken at schedule time); the worker emits
   started/finished/failed and the status bar shows a busy indicator. `evaluate()` has no
   progress/cancel callback — per-point progress/cancel exists only on
   `sweep()`/`monte_carlo()` (Gap 72, v1.1).
6. **Units on every displayed value — no exceptions** (R-UNITS). Every numeric shown
   anywhere (card, table cell, tooltip, axis, readout) carries its unit, sourced from the
   `ParameterDef` / result metadata, never hardcoded. Owner hard rule; acceptance criterion
   for every phase — including every new plot axis and readout a go-forward phase adds.
7. **Errors are shown, never swallowed** (Rules 15/17). `RadiantError` → modal what/why/
   action/context. Unexpected exceptions → error dialog with a traceback fold. A plot
   accessor that cannot render (frame absent for the regime) raises `ApiValidationError`
   with an actionable message, never a blank. No `except Exception: pass` in gui code.
8. **Code standards:** type hints on every function (Rule 1); `ruff` clean; no `print()`
   (Rule 14). Enforced `mypy --strict` stays scoped to `core`/`api`.
9. **All styling flows through the design system.** The Design System (arch doc §8) is
   the QSS theme in `gui/themes/`. No widget hardcodes a color, font, or size outside
   `themes/` — review-blocking. The **one documented exception** is the viewer's semantic
   physics-domain glyph palette (`radiant.gui.viewer` allowlisted `palette` module, arch
   doc §8.5) — glyph colors encode meaning, not chrome; viewer *chrome* still follows the
   tokens. **Light is the v1 launch default, dark the alternate**; both ship from one token
   set and the Phase 9 View-menu toggle switches them.
10. **Testing:** `pytest-qt` (`qtbot`), headless via `QT_QPA_PLATFORM=offscreen`. Every
    menu/toolbar action added in a phase gets a programmatic trigger test. The 2D viewer is
    grabbed offscreen via `QWidget.grab()` (fully faithful — no VTK offscreen dance). When a
    task touches only `gui/`, run `pytest src/radiant/gui/tests/ -v` plus one fast full-chain
    smoke — not the whole repo suite. A **framework-plot** phase (§7) touches `api/` and gets
    its own `api` accessor tests plus the golden-suite regression statement (results-neutral).
11. **Rule 29 changelog:** each phase that adds user-observable capability adds a
    `CHANGELOG.md` entry under `[Unreleased]`. Framework-plot phases add a **public-surface**
    entry (new `result.plot.*` accessor / new stored frame) — a surface addition, not a
    results change; state explicitly that goldens are byte-identical.

---

## 5. Iteration Protocol (how the owner tests along the way)

Every phase ends with a **Checkpoint** — a section in the task report containing:

1. **Launch command** (e.g. `pip install -e ".[gui]" && radiant gui examples/leo_mwir.yaml`).
2. **Click script** — a numbered list of exactly what to do in the UI.
3. **Expected observations** — what each step should show, with units.
4. **Known-incomplete list** — what is intentionally stubbed, so the owner doesn't file
   feedback on planned gaps.

The owner runs the checkpoint and replies with feedback. Feedback items become a
**punch-list task** (its own conversation, Category A) that must close before the next
phase starts. Do not batch feedback across phases.

A go-forward **framework-plot** phase has no clickable GUI surface of its own (it adds an
API accessor); its checkpoint is a **script** the owner runs (`result.plot.<new>()` in a
Python session or the future console) plus the paired per-stage instrument phase that
consumes it. The two are sequenced back-to-back so the owner sees the plot land in the GUI.

---

## 6. What Shipped — Phases 0–7 (Done)

Phases 0–7 of the original plan are **complete**. The redesigns (D6, D7) mean the *shipped
arrangement* differs from the original phase descriptions; the table below records status
and points at the authoritative surface. The original per-phase task text is preserved in
git history — it is not re-transcribed here (Rule 27: one canonical description; the arch
doc is that description).

| Orig. phase | What it delivered | Status | Authoritative surface |
|---|---|---|---|
| **0 — v1 Spec & Requirements Harvest** | Ratified arch doc; 37-scenario requirements matrix; Design System | **Done** (checkpoint passed 2026-07-12) | arch doc §7 (matrix), §8 (design system), §1.3 (checkpoint) |
| **1 — Scaffold, Shell, Design System, Test Harness** | `radiant gui` entry point; `RADIANTMainWindow`; QSS light/dark theme; import rules; pytest-qt harness | **Done** | arch doc §8, §11; `src/radiant/gui/themes/` |
| **2 — Parameter Panel** | Schema-driven All-Parameters tree; per-dtype editors; validate-on-clone; Explain/Reset; display-unit preference | **Done** | arch doc §4.3 |
| **3 — Evaluate Loop (Milestone A)** | Worker thread; metric surface; `result.plot.*` canvas; debounced re-eval; **saturation banner** (CU-101) | **Done** | arch doc §3.2–3.3, §4.4 (metric surface), §4.5 |
| **4 — Stage Strip + Detail Tabs** | 9-stage strip + health dots; the detail-tab data sources (Spectral / MTF / Noise / Variables / YAML) | **Done, then relocated by D6** — the strip stayed; the bottom tabs dissolved into per-stage center views + right-rail tools + the global Inspector (arch doc §4.7 maps each) | arch doc §4.2, §4.4, §4.6, §4.7 |
| **5 — Geometry Screen** | Stage-0 mode forms; frame-grouped derived-angle readout; over/under-spec highlighting | **Done — the gold-standard instrument** | arch doc §4.4 (Geometry Inputs) |
| **6 — Viewer Visual-Direction ADR + Lift Assessment** | ADR-0007 (visual direction + lift map) | **Done, then superseded** — the PyVista recommendation was overtaken by the 2D pivot (D7); the ADR's supersession note records it | ADR-0007 |
| **7 — Geometry Viewer** | The bound scene viewer: glyphs, vectors, revealable angle arcs, shape library, RPY triad, altitude leaders, angle-truth consistency test | **Done as the 2D schematic** (D7 — Pass 1 + Pass 2, not the 3D PyVista original) | arch doc §6.9; ADR-0007 §Supersession |

### 6.1 The shipped reality that supersedes the original structure

- **Layout (D6).** Single primary nav = the 9-stage strip; a permanent left
  All-Parameters tree; a per-stage center view (Inputs / Outputs / Plots); a persistent
  right rail (Pinned cards, Edit-Config-YAML modal, Messages, Evaluate footer); the full
  `result.inspect()` dump is a global **Inspector** tool, not a docked tab. **There is no
  global metric-badge row and no bottom detail-tab dock** — both were relocated (arch doc
  §4.7). This is the structure every go-forward phase builds into.
- **Viewer (D7).** A pure-Qt 2D orthographic schematic (`radiant.gui.viewer`) — no VTK.
  The lifted PyVista scene library was removed (CU-132); only the allowlisted glyph
  `palette` survives. Arch doc §6.9 is the complete description; §§6.7–6.8 are retained
  history of the retired PyVista Part A/B.
- **Gold standard.** The Geometry instrument (mode forms + frame-grouped readout + the 2D
  schematic) is the bar. Every go-forward per-stage phase brings its stage to it:
  schema-driven Inputs (one `sensor.set` per edit, validate-on-clone), unit-carrying
  Outputs read verbatim from `stage_outputs`, and the stage's plots from the public
  `result.plot.*` surface.

---

## 7. Go-Forward Phase Sequence — PROPOSAL (pending owner ratification)

**Status of this section: proposal.** The phase set, grouping, and ordering below are put
to the owner in §8. Nothing here is committed until ratified.

The go-forward work is the **bespoke per-stage content** the owner ratified in
`RADIANT_GUI_Architecture.md` §4.4.1. That spec classifies each item **[exists]** (a real
`result.plot.*` / stage-output surface backs it today), **[GUI-only]** (data exists; the
GUI reshapes/draws it), or **[GAP N]** (needs a framework capability that does not exist).
The sequence follows that classification:

- **Framework-plot phases (FP-1…FP-3)** build the missing **plotting capability first** —
  results-neutral additions to `radiant.api.plot` + `result.plot.*` accessors (and, for
  Gap 91, one persisted frame). They unblock the Source and Optics instruments and **also
  benefit script/console users**, who get the same accessors.
- **Per-stage instrument phases (PS-1…PS-6)** bring each stage to the Geometry gold
  standard, consuming the FP plots and the already-shipped surfaces.
- **Phase 8** (scripting console) and **Phase 9** (file round-trip, undo/redo, polish,
  closeout) keep their original numbers — they are the last two phases.
- **Housekeeping** (CU-134 pyvista pins, CU-122 attitude owner) folds into the phases
  noted.

Effort key: S ≈ one short session, M ≈ one full session, L ≈ may need a split.

Each phase's `Read first` always includes `RADIANT_GUI_Architecture.md` §4.4.1 (the
content spec) and the gating gap's `gaps.md` entry; not repeated per phase below.

---

### Framework-plot phases (build the plotting capability first)

#### Phase FP-1 — Framework plot: Source pre-atmosphere emission spectrum
**Gate:** none (api/gui both idle-safe). **Category:** B–C · **Effort:** M
**Gating gap:** **Gap 91** (no stored pre-atmosphere source-emission frame).
**Read first:** `gaps.md` Gap 91; `RADIANT_Signal_Chain_Architecture.md` (frame flow);
`source/stage.py`, `atmosphere/stage.py` (where radiance is assembled); `api/plot.py`.
**Delivers:** a persisted pre-atmosphere emitted-radiance frame for target + background
(`at_source_target` / `at_source_background`, W/m²/sr/µm) and a
`result.plot.spectral_source_emission()` accessor. Separates "what the target emits" from
"what reaches the aperture" (the owner's Source-vs-Atmosphere split). **Results-neutral**
— persists an already-computed intermediate; Category C only because the double-count
check against the at-aperture path must be proven (verify goldens byte-identical).
**Checkpoint (script):** in a Python session, `result.plot.spectral_source_emission()`
renders target + background emission with units; the existing `spectral_source()`
(at-aperture) still renders unchanged; golden suite untouched.

#### Phase FP-2 — Framework plot: Optics pupil apodization + wavefront-error maps
**Gate:** none. **Category:** A–B · **Effort:** M
**Gating gap:** **Gap 89** (complex-pupil diagnostics not exposed).
**Read first:** `gaps.md` Gap 89; `optics/stage.py` (`_compute_optical_mtf`,
`make_pupil_amplitude`, `make_pupil_phase_for_wfe`); `api/plot.py`.
**Delivers:** persist the pupil amplitude + WFE-phase arrays (at `pupil_npix`) in
`stage_outputs["optics"]` (e.g. `pupil_amplitude`, `pupil_phase_waves`), and add
`result.plot.pupil_amplitude()` / `pupil_phase()` imshow accessors. Amplitude + phase are
two faces of one complex pupil (Rule 4's single pupil root) — one phase. **Results-neutral**
(a view over arrays the chain already builds each run).
**Checkpoint (script):** `result.plot.pupil_amplitude()` shows the obscuration/vane mask;
`result.plot.pupil_phase()` shows the WFE screen; goldens untouched.

#### Phase FP-3 — Framework plot: Optics coating / transmission spectra
**Gate:** none. **Category:** A · **Effort:** S–M
**Gating gap:** **Gap 90** (per-element R/T/ε + system-throughput spectra not exposed).
**Read first:** `gaps.md` Gap 90; `optics/element.py` (`OpticalElement.transmittance`/
`reflectance`/`declared_emissivity`), `optics/stage.py` (`tau_opt_spectral`); `api/plot.py`.
**Delivers:** `result.plot.optical_throughput()` (system `tau_opt_spectral`) and
`result.plot.coating_spectra()` (per-element R/T/ε overlay) accessors, delegating to
`plot_spectral_multi` / a twin-axis helper. **Results-neutral** (view over stored
`SpectralData`). Rule 5: ε is Kirchhoff-derived and displayed as such, never an input.
**Checkpoint (script):** `result.plot.coating_spectra()` overlays each element's R/T/ε;
`result.plot.optical_throughput()` shows the assembled band transmission; goldens untouched.

---

### Per-stage instrument phases (bring each stage to the Geometry standard)

#### Phase PS-1 — Source instrument
**Gate:** **FP-1 merged** (Gap 91 accessor available). **Category:** D · **Effort:** M
**Read first:** arch doc §4.4.1 (Source rows); `gaps.md` Gap 85; `source/_schema.py`.
**Delivers:** the Source center view — target + background **emission** spectra
(`spectral_source_emission()`, FP-1) plus size/shape/orientation Inputs (`source.target.*`
shape/dims/RPY, `projected_area_m2`), all schema-driven, one `sensor.set` per edit. The
**per-scenario-type input gating** (which inputs are relevant) ties to **Gap 85**
(mission-type relevance, DEFERRED post-v1) — v1 shows all inputs; the gating is a v1.1
companion. Integration test: edit → evaluate → the emission plot + shape inputs refresh.
**Checkpoint:** open the Source stage, read the emitted target/background spectra, set a
shape and its dimensions, watch the spectra update.

#### Phase PS-2 — Optics instrument
**Gate:** **FP-2 + FP-3 merged** (Gaps 89, 90 accessors). **Category:** D · **Effort:** L
(split: PSF/MTF composite first; pupil + coating tabs second — uses the §4.4 sub-view hook)
**Read first:** arch doc §4.4.1 (Optics rows), §4.4 (sub-view hook); `gaps.md` 89, 90.
**Delivers:** the Optics center view — MTF (`mtf()`) + PSF (`psf()`) which **exist today**,
plus pupil apodization + WFE maps (`pupil_amplitude()`/`pupil_phase()`, FP-2) and coating/
transmission spectra (`coating_spectra()`/`optical_throughput()`, FP-3). With four+
diagnostics this stage is the first to use the declared **sub-view tab** hook
(`StageComposition.subviews`). Integration test over a WFE/obscuration config (personas
5.1, 1.5). **Checkpoint:** open Optics, view MTF/PSF, switch to the pupil tab and the
coating tab, tilt an obscuration/WFE input and watch the maps respond.

#### Phase PS-3 — Detector instrument
**Gate:** none beyond shipped surfaces (all **[GUI-only]**). **Category:** D · **Effort:** M
**Read first:** arch doc §4.4.1 (Detector rows); `detector/_schema.py`;
`api/inspect.py` (`result.noise_terms`); the shipped `NoiseBudgetPanel`.
**Delivers:** the Detector center view — a **noise pie** (reshape of the scalar
`result.noise_terms`, same data as the shipped bar), a **detector illustration** drawn
from `pixel_pitch_x_um`/`pixel_pitch_y_um`/`fill_factor`/`n_pixels_*` (like the geometry
schematic), and a **PSF + pixel-grid overlay** (a GUI draw over `psf()` using the
`EffectivePSF` `pixel_pitch_m`/`sample_spacing_m`). All **[GUI-only]** — no framework gap.
**Owner decision surfaced (§8):** whether the **noise pie** is a **framework**
`result.plot.noise_pie()` accessor (R-API: "one action ↔ one API call" argues for a
framework accessor, consistent with the shipped `noise_budget()` bar) or a **GUI-side**
reshape of `result.noise_terms`. Default proposal: **framework accessor**, for symmetry
with `noise_budget()` and console reuse — but this is the owner's call.
**Checkpoint:** open Detector, read the noise pie (every wedge labeled, e- RMS), see the
pixel-pitch illustration, toggle the PSF pixel-grid overlay.

#### Phase PS-4 — Spectral-Integration instrument
**Gate:** none. **Category:** A–D · **Effort:** S–M
**Read first:** arch doc §4.4.1 (Spectral-Integration rows); `gaps.md` Gap 92.
**Delivers:** the Spectral-Integration center view — the **signal** spectrum
(`spectral_inband()`, **exists**) paired with the **scalar** noise budget
(`noise_budget()`, **exists**). The owner's "noise terms **as a spectrum**" is **Gap 92**
(no per-λ noise decomposition) — **DEFERRED** (runs against Rule 8's once-only integration;
a design question, not a defect). v1 pairs the signal spectrum with the scalar budget; the
per-λ decomposition is out of v1 pending the owner's scope confirmation (§8). Also honor the
**[GUI-grouping note]**: `integration_time_s` may be presented under a more operator-relevant
heading (presentation only, **no schema change**).
**Checkpoint:** open Spectral Integration, read the in-band signal spectrum beside the
scalar noise budget.

#### Phase PS-5 — Platform + Readout instruments (v1-minimal)
**Gate:** none. **Category:** A · **Effort:** S
**Read first:** arch doc §4.4.1 (Platform, Readout rows — both **[TBD] v1-minimal**);
`platform/_schema.py`, `readout/_schema.py`.
**Delivers (shipped 2026-07-15):** v1-minimal center views for Platform and Readout —
editable schema-driven inputs as shared `FieldRow`s (Platform: `PlatformInputsForm`, jitter +
smear knobs; Readout: `ReadoutInputsForm`, read-noise/ADC/full-well knobs) beside a
unit-carrying Outputs readout plus a themed "v1-minimal" note; no bespoke invented content.
Platform needs no dedicated MTF view (smear/jitter terms remain in the Optics/Performance MTF
overlay); Readout adds the scalar `noise_budget()` (read noise + quantization live in this
stage). **Housekeeping (CU-122):** this phase
is the natural place to re-audit the **platform/sensor attitude has no stage owner** decision
(ADR-0006 §4) — the Platform stage is where a platform-attitude output would live. v1 does
not require it (the target RPY triad already ships from `source.target.*`); this phase either
lands a decision or refreshes the CU-122 deferral. **Owner decision surfaced (§8).**
**Checkpoint:** open Platform and Readout, read their outputs with units; confirm the
v1-minimal scope is acceptable.

#### Phase PS-6 — Performance instrument (polish)
**Gate:** none (all **[exists]**). **Category:** A · **Effort:** S
**Read first:** arch doc §4.4.1 (Performance row); `api/inspect.py`
(`ChainResult.metrics` / `metric_records()`).
**Delivers (shipped 2026-07-15):** the Performance center view polish — the metric surface
(SNR/NEDT/NIIRS/GSD/MTF@Nyquist and the full `metric_records()` set, units from
`metric_records()`) as an `OutputsReadout` metric summary + `mtf()` (system MTF) +
`mtf_budget()`, all landing on the default post-evaluate stage. Layout/polish + the pin
affordances, not new capability. A result-typed metric failure (a non-finite value) renders as
`n/a (<failure_reason>)` from the metric's result object, never a bare `nan`/blank (Rule 17
carve-out — `OutputsReadout.show_metrics` reads `metric_format.metric_failure_reason`). This
completes all nine per-stage instruments (Geometry / Source / Atmosphere / Optics / Platform /
Spectral Integration / Detector / Readout / Performance).
**Checkpoint:** open Performance, read every metric with units, view system MTF + the MTF
budget, pin a metric to the right rail.

---

### Phase 8 — Scripting Console
**Gate:** none (self-contained; no gap dependency). **Category:** D · **Effort:** M
**Read first:** arch doc §4.6/§5 (Console hand-off), §10 (Tools menu); qtconsole embedding
docs; `docs/tracking/MEMORY`-noted MATLAB-style command-window vision.
**Delivers:** an embedded IPython (`qtconsole` in-process kernel) with live `sensor` and
`result` bound; `result.plot.*` figures render inline or route to the stage view (pick one,
document it) — the console reuses **every** FP accessor for free. GUI/console coherence:
after a console mutation the GUI marks state stale and offers one-click Refresh (explicit
beats magic sync). Fallback if qtconsole proves fragile: a plain REPL over
`code.InteractiveConsole`, decided in-phase and CU'd if the vision item degrades.
**Checkpoint:** the MATLAB-style loop — `inspect_result(result)`, `sensor.set(...)`,
re-evaluate from the console, plot a spectral frame, Refresh.

### Phase 9 — File Round-Trip, Undo/Redo, Polish, Closeout
**Gate:** all prior go-forward phases merged. **Category:** D · **Effort:** M
**Read first:** arch doc §4.5 (Edit Config), §5 (interop), §10 (menus);
`RADIANT_Config_Format.md` §1.7.
**Delivers:**
1. File menu complete: New, Open, Open Recent (`QSettings`), Save, Save As — all through
   `Sensor.load()` / `sensor.save()`; window title shows file + dirty marker.
2. Undo/redo: `QUndoStack` wrapping `sensor.set()` (named commands, 20 levels).
3. View menu: panel show/hide, stage jump shortcuts, **light/dark theme toggle** (one
   `Theme` in → QSS + viewer chrome restyle); persist the display-unit + pin preferences
   via `QSettings` (CU-115).
4. Full pass of the arch doc §7 requirements matrix: every v1 row demonstrably works or is
   re-dispositioned with the owner; every deferred item lands in `gaps.md`.
5. **Housekeeping — CU-134:** drop the unused `pyvista`/`pyvistaqt` pins from the `gui`
   extra (no `radiant.gui` importer remains; a viewer grep + `test_no_pyvista_import_in_viewer`
   guard it). Move CU-134 to Resolved with the commit SHA (Rule 22).
6. Closeout (Rules 22/24/29): CHANGELOG entry for v1 GUI capability; arch doc final
   reconciliation; **this plan moves to `docs/archive/` in the completing PR** with a
   HISTORICAL banner (Rule 24).
**Checkpoint:** full acceptance walkthrough — the owner drives one complete scenario end to
end (geometry → parameters → per-stage instruments → console → save, reopen, confirm
identical state) and toggles the theme.

---

## 8. Decisions for Owner (ratify to lock the go-forward sequence)

**Status: RATIFIED (owner, 2026-07-14).** The owner ratified the revised plan's
go-forward sequence (§7) — converting it from proposal to Active — and all five decisions
below as proposed (no amendments). Each decision records its ratified ruling.

1. **Framework-plot scope for v1.** **RATIFIED (2026-07-14): all three** framework-plot
   gaps (Gap 91 Source emission, Gap 89 Optics pupil/WFE, Gap 90 Optics coating spectra)
   are **in v1**. They are the only genuinely new framework work; each keeps its paired
   per-stage instrument content (PS-1 the emission split; PS-2 the pupil/coating tabs).
2. **Detector noise-pie: framework accessor vs GUI-side reshape.** **RATIFIED
   (2026-07-14): framework `result.plot.noise_pie()` accessor** (symmetry with the shipped
   `noise_budget()` bar; console reuse; R-API "one action ↔ one API call"), not a GUI-side
   reshape of the scalar `result.noise_terms` (PS-3).
3. **Gap 92 (per-λ noise spectrum) stays DEFERRED.** **RATIFIED (2026-07-14): DEFERRED.**
   The owner's "noise as a spectrum" stays out of v1 — it runs against Rule 8's once-only
   spectral integration and is a new physics accounting (Category C), not a view. v1 pairs
   the signal spectrum with the scalar noise budget (PS-4).
4. **CU-122 — platform/sensor attitude owner.** **RATIFIED (2026-07-14): option (c) —
   leave deferred**, re-audited at PS-5. The **target** RPY triad already ships (from
   `source.target.*`); the **platform/sensor** attitude (`observer_{yaw,pitch,roll}`) has
   **no stage owner** (ADR-0006 §4 deferred it "until a consumer exists") and no v1
   consumer needs it.
5. **Phase ordering / grouping.** **RATIFIED (2026-07-14): framework-plot-first ordering.**
   All framework-plot phases build before the per-stage instruments that consume them (§7);
   Console = Phase 8 and Closeout = Phase 9 remain last.

---

## 9. Phase-Task Prompt Template

Each phase is dispatched to an agent with this preamble (per CLAUDE.md discipline):

```
Task: GUI Development Plan — Phase <ID>: <title>
Category: <A|B|C|D>   (validation requirements per CLAUDE.md)
Read first: docs/plans/GUI_Development_Plan.md §4 (ground rules) and §7 Phase <ID>;
            docs/architecture/RADIANT_GUI_Architecture.md §4.4.1 (per-stage content spec);
            the phase's own "Read first" list (incl. its gating gaps.md entry).
Scope: exactly the deliverables of Phase <ID>. No other phases' work, no
       unrequested features. GUI code must not alter any computed result; a
       framework-plot phase persists/plots only already-computed intermediates and
       states the golden suite is byte-identical.
Gate check: confirm the phase's Gate condition holds before writing code
            (e.g. a per-stage instrument phase confirms its framework-plot phase merged);
            if it does not, stop and report.
Done means: phase tests pass (pytest src/radiant/gui/tests/ -v, offscreen; plus api
            accessor tests + the golden regression statement for a framework-plot phase)
            plus one fast full-chain smoke; ruff clean; import-linter clean;
            structured report with the Checkpoint section (§5).
```

Punch-list tasks (owner feedback after a checkpoint) use the same template with
Category A and the feedback list as the numbered scope.

---

## 10. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| A framework-plot phase accidentally changes results (esp. Gap 91's persisted frame) | Every FP phase is results-neutral by construction (view/accessor over already-computed arrays) and carries the golden-suite regression statement; a golden diff is a defect that blocks the PR. Gap 91 additionally proves no double-count against the at-aperture path. |
| A per-stage instrument phase starts before its framework plot exists | The Gate condition names the prerequisite FP phase; the phase stops and reports if it is not merged (ground rule 1 — the missing plot is an API gap, already filed as Gaps 89–92). |
| Gap 85 (mission-type relevance) blocks the Source per-scenario input gating | Gap 85 is DEFERRED post-v1 by owner disposition; PS-1 ships all inputs ungated, the gating is a v1.1 companion — no v1 dependency. |
| Gap 92 pulls per-λ noise physics into a UX phase | Kept out of v1 by proposal (decision 3); PS-4 pairs the existing signal spectrum with the scalar budget — no new physics in a GUI phase. |
| CU-122 attitude decision drifts across phases | Re-audited at PS-5 (the Platform instrument), with the ADR-0006 §4 trigger; the target triad already ships, so nothing v1 blocks on it. |
| Console (qtconsole) instability | Phase 8 is late and self-contained; fallback is a plain REPL over `code.InteractiveConsole`, decided in-phase, CU'd if it degrades. |
| GUI drifts from the arch doc (Rule 20) | The arch doc is the authoritative content surface (§0); every phase that changes a documented surface updates it in the same PR; this plan references §4.4.1, never re-duplicates it. |
| pyvista pins linger as dead install weight | CU-134 folded into Phase 9 (or the next `pyproject` touch); guarded by `test_no_pyvista_import_in_viewer`. |

---

## 11. What Done Looks Like

- `radiant gui` launches a themed contextual 9-stage application from any example YAML.
- Every stage is a bespoke instrument at the Geometry gold standard: schema-driven Inputs
  (one `sensor.set` per edit), unit-carrying Outputs from `stage_outputs`, and the stage's
  plots from `result.plot.*` — including the four framework-plot additions (Gaps 89–91;
  Gap 92 deferred).
- The 2D schematic viewer, scripting console, and file round-trip / undo-redo all work.
- Every scenario row marked v1 in the arch doc §7 requirements matrix is demonstrable.
- All GUI tests pass headless in CI; golden results byte-identical to pre-GUI.
- `RADIANT_GUI_Architecture.md` describes the shipped application with zero aspirational
  claims; deferred items live in `gaps.md`, not in doc prose.
- CU-134 (pyvista pins) resolved; CU-122 (attitude) closed or with a refreshed deferral.
- This plan is in `docs/archive/` with a completion banner.
</content>
</invoke>
