> **HISTORICAL — archived 2026-09-17 (completed by the coding agent; Phases 0–5 all landed, the last on branch `gap131/phase5-shipping`).** The suite ships: **Theory Manual** (91 pp.), **User's Guide** (97 pp.), **Technical Reference** (161 pp.), **Worked Examples & Validation** (162 pp.), built from the Markdown chapters under `docs/` by `scripts/build_manual.py` on the shared `scripts/manual_assets/` template. `scripts/build_release.py` is the one-command release step: it builds all four volumes, stages them into the wheel at `radiant/manuals/` and the 710 git-tracked files of the 51-scenario suite at `radiant/scenarios/` (owner direction 2026-09-17), builds and verifies the sdist + wheel, and assembles `build/release/` — the four PDFs, `radiant_scenarios_<version>.zip`, the wheel and the sdist. Ruling Q1 is satisfied in both directions, with no PDF committed (Rule 26). Gap 131 closed 2026-09-17. Two §6 TOC lines were found stale during Phase 2 and are recorded in `docs/tracking/Findings_Log.md` rather than edited here.

# RADIANT Support Documentation Plan

**Status:** Complete — all five phases delivered 2026-09-16..17; structure, TOCs, and all seven §10 rulings were ratified by the owner 2026-09-16; tracked as Gap 131 (closed)
**Date:** 2026-09-16
**Scope:** The shipped RADIANT documentation suite — a set of paper-quality, typeset PDF manuals covering the physics theory, GUI operation, the underlying codebase, and worked examples.

---

## 1. Objective

Produce a professional, versioned set of PDF manuals that ship with RADIANT. The suite must:

1. Cover four content areas: **physics theory**, **GUI operation**, **the underlying codebase** (API, parameters, architecture), and **worked examples with validation evidence**.
2. Be **paper quality**: XeLaTeX typesetting, LaTeX equations, numbered sections, hyperlinked tables of contents and cross-references, consistent notation, cover pages, version and date stamps.
3. Be **single-sourced from Markdown** under `docs/` per OPERATING_MODEL §5.4 — the PDFs are generated artifacts (Rule 26), never hand-edited, never forked to `.tex`.
4. Stay correct by construction where possible: generated content (parameter reference, GUI screenshots) is produced by scripts from the code itself, so Rule-20 lock-step extends into the manuals.

## 2. Governing Constraints

| Constraint | Consequence for this plan |
|---|---|
| §5.4 single-source rule | All manual text lives as Markdown in `docs/theory/` and `docs/guides/`; Pandoc + XeLaTeX generates the PDFs. No parallel `.tex` sources. |
| Rule 26 (regenerable artifacts) | PDFs are gitignored and built on demand / at release. Screenshots committed for the GUI manual are doc-referenced figures with a generator named in a manifest — the permitted class (b). |
| Rule 20 (doc/code lock-step) | Manual chapters that restate a public surface must be either generated (preferred) or added to the lock-step review surface. The plan minimizes hand-restated API content. |
| Rule 30 (cross-platform) | The build must work on macOS **and** Windows. The current `build_manual.py` font choices (Helvetica Neue / Menlo) are macOS-only — Phase 0 replaces them with TeX-Live-bundled fonts (Findings_Log 2026-09-16). |
| Process-machinery moratorium | The owner waived the moratorium for exactly one non-blocking CI conversion job (§10, ruling Q5); no manual-related check gates a merge. Build validation otherwise runs inside the builder itself. |
| §1 closed folder taxonomy | No new `docs/` top-level folder. Theory chapters → `docs/theory/`, user-facing chapters → `docs/guides/`, figures → `docs/guides/figures/`. |

## 3. The Suite — Four Volumes

| Vol | Title | Content area | Primary audience | Est. size |
|---|---|---|---|---|
| I | **RADIANT Theory Manual** | Physics: governing equations for every stage | Analysts, physicists, reviewers | 90–120 pp |
| II | **RADIANT User's Guide** | Installation, concepts, GUI operation, workflows | Tool operators (the seven personas) | 70–100 pp |
| III | **RADIANT Technical Reference** | Scripting API, CLI, YAML, parameters, architecture, extending | Script authors, developers, agents | 100–140 pp |
| IV | **RADIANT Worked Examples & Validation** | Example scripts, persona case studies (tiered, all 51 scenarios), flagship-mission validation | New users, evaluators, V&V reviewers | 150–200 pp |

All four share one visual identity: common LaTeX template (cover page, headers/footers, fonts, table style), a shared **Notation and Symbols** table (canonical home: Volume I front matter; Volumes II–IV reference it), section numbering `--number-sections`, `--toc` depth 2, hyperref-linked internal references.

Volume I already exists in embryo: `scripts/build_manual.py` binds six `docs/theory/` chapters today. This plan generalizes that builder to a volume registry and grows each volume in phases.

---

## 4. Volume I — RADIANT Theory Manual

Subtitle: *Physics Reference for the RADIANT EO Sensor Performance Model* (unchanged).

### Table of contents

| Ch | Title | Source | State |
|---|---|---|---|
| — | Front matter: cover, TOC, **Notation & Symbols** | new (extracted from `radiometric_chain.md` §Notation + `RADIANT_Conventions.md` units table) | new |
| 1 | Introduction — the signal chain at a glance, regimes, model scope | new short chapter (~6 pp), distilled from `radiometric_chain.md` §"The Chain at a Glance" + `regime_selection.md` | new |
| 2 | Viewing Geometry & Sampling | `theory/geometry.md` (viewing triangle, slant range, orbit kinematics, GSD, swath/access, smear & TDI line-rate, solar geometry, Euler ZYX, ground sampling) | exists |
| 3 | The Radiometric Signal Chain | `theory/radiometric_chain.md` (foundations, source → readout radiometry, assumptions) | exists |
| 4 | Atmosphere Models | `theory/atmosphere_models.md` (two families, simple parametric model, library-backed/MODTRAN models, limits) | exists — **not yet bound into the manual**; add to `CHAPTERS` |
| 5 | The Spatial Model — PSF and MTF | `theory/spatial_model.md` (dual-path Rule 4, pupil autocorrelation, Zernike/Strehl, detector/platform kernels, turbulence, TDI mis-registration, EE_box & pixel phase, Nyquist/Q/folded MTF, RER) | exists |
| 6 | The Noise Model | `theory/noise_model.md` (RSS composition, 16-term taxonomy, acquisition scaling, regime selection, dominance map) | exists |
| 7 | Calibration Error Model | **new** `theory/calibration_model.md` — post-NUC residuals, drift, bias budget, calibration-limited NEDT (the Gap 120/122 stage has an architecture doc but no theory chapter) | new |
| 8 | Performance Metrics | `theory/performance_metrics.md` (SNR family, NEDT, NEI/NEP/D\*, GIQE-5 NIIRS, Johnson criteria, detection range, saturation/DR/BLIP, inversions) | exists |
| A | Appendix: Mixed Optical-Train Radiometric Model | `theory/radiometric_model_mixed_train.md` — currently excluded from the binding; bring in as an appendix | exists |
| — | References | `theory/references.md`, grown as chapters cite | exists |

### Work items

- Add chapters 4 and A to the binding; write chapters 1, 7, and the front-matter notation table.
- **Physics-inventory audit:** diff the manual's coverage against `architecture/RADIANT_Physics_Inventory.md`; every implemented physics computation must be traceable to a manual section (or an explicit "not covered, see spec" line). Findings feed a chapter gap list before v1.0 is declared.
- Equation pass: new/edited equation content in `$...$` / `$$...$$` per §5.4 (grandfathered Unicode math stays until a chapter is wholesale rewritten).

## 5. Volume II — RADIANT User's Guide

Subtitle: *Installing, Configuring, and Operating RADIANT*. Mostly **new writing**; the GUI has a 2,200-line architecture spec but no user-facing manual. Chapters are new `lowercase_snake.md` files in `docs/guides/` unless noted.

### Table of contents

| Ch | Title | Content | Source |
|---|---|---|---|
| 1 | Introduction | What RADIANT predicts; who it serves (the persona set); mission types (extended / sub-pixel / point-source) | new; `RADIANT_Personas.md` distilled |
| 2 | Installation & Launch | pip install, extras (`gui`, `scenarios`, `dev`), Windows & macOS notes, `radiant gui` | extends `guides/quickstart.md` |
| 3 | Quickstart Tour | First evaluation end-to-end in the GUI, then the same run from YAML/CLI | new + `guides/quickstart.md` |
| 4 | Core Concepts | Signal chain stages; parameters, units & entry/display symmetry; radiometric regimes; configurations | `guides/regime_selection.md` + new |
| 5 | The Main Window | Contextual per-stage workspace layout; persistent right rail (Pinned, YAML button, Messages); menu map | new; from `RADIANT_GUI_Architecture.md` §4, §10 |
| 6 | Defining the Scene | Geometry workspace + 2D geometry viewer; target & background (source workspace); atmosphere workspace + model selection guidance | new; `guides/atmosphere_selection.md` folded in |
| 7 | Defining the Sensor | Optics & element trains (configured element rows, undo); platform (jitter/smear); detector incl. FPA preset library; readout (TDI, DROIC); calibration terms | new |
| 8 | Configuration Sets | Multi-configuration model (up to 12), per-configuration overrides, comparison mode | new; ADR-0010 distilled |
| 9 | Running & Reading Results | Metric selection (metric groups, spatial-path skip), performance displays, messages & advisory notes, warnings taxonomy from the operator's view | new |
| 10 | Sweeps & Trade Studies in the GUI | Sweep surface, config-file comparison mode | new; `guides/trade_studies.md` GUI-side |
| 11 | YAML Round-Trip | Config import/export, file format orientation (full reference → Vol III), GUI ↔ script ↔ YAML interoperability | `guides/configuration.md` distilled |
| 12 | Troubleshooting | Actionable-error philosophy, common rejections (bounds, Kirchhoff, consistency groups), where to look (Messages rail, logs) | new |
| A | Appendix: Menu & Shortcut Reference | generated or hand-maintained table | new |

Deliberately **not** chaptered yet: the script/command window (pending capability — added as a chapter when it ships).

### Screenshot pipeline (the enabling work)

Paper-quality GUI documentation lives or dies on current screenshots. Hand-captured images go stale with every GUI PR.

Feasibility is proven (spike, 2026-09-16): the real `RADIANTMainWindow` built under `QT_QPA_PLATFORM=offscreen` on `examples/mwir_leo_minimal.yaml` auto-evaluated on its worker thread and yielded clean 1440×900 `QWidget.grab()` captures of the Performance, Geometry, Optics, and Detector workspaces — no display, no new dependencies. Spike lessons folded in below: per-figure dock/splitter geometry (default widths elide parameter names), panel-level grabs for detail figures, and the note that offscreen rendering uses Fusion-style chrome rather than native macOS decorations (platform-neutral figures; ruled Q7: all figures offscreen, no native hero shots).

Because Volume IV's GUI-led examples need the same machinery, the generator itself is **Phase 0 infrastructure**; Phases 3 and 4 only add capture definitions and prose.

- New `scripts/gen_gui_screenshots.py`: drives the GUI offscreen (same pytest-qt/`QWidget.grab()` machinery the GUI suite uses), loads a fixed demo config (a flagship-mission baseline) or a named exercise baseline, captures each documented workspace/panel at a fixed window size and dock geometry, writes `docs/guides/figures/gui/<workspace>_<view>.png`.
- Figures are committed (Rule 26(b): doc-referenced) with a `MANIFEST.md` naming the generator, input config, and commit.
- Regeneration is a release-checklist step and can be re-run after any GUI change that alters documented surfaces; a stale screenshot is then a one-command fix, not an archaeology project.

## 6. Volume III — RADIANT Technical Reference

Subtitle: *API, Configuration, Parameters, and Architecture*. Three parts with different sourcing strategies to avoid a hand-maintained restatement of the code (the Rule-20 drift trap):

**Part 1 — Orientation (new, distilled):**

| Ch | Title | Source |
|---|---|---|
| 1 | System Overview | signal chain, stage list, dual spatial path, geometry-first design — distilled from `RADIANT_Master_Architecture.md` |
| 2 | Conventions | canonical units, coordinate system, spectral variable — from `RADIANT_Conventions.md` |

**Part 2 — Reference (reuse guides + generated content):**

| Ch | Title | Source |
|---|---|---|
| 3 | Scripting API | `Sensor`, `SensorConfig`, `ChainResult`, `SweepResult`, `BatchRunner`, progress/cancellation — grown from `guides/scripting.md` + `RADIANT_Scripting_API.md` |
| 4 | Command-Line Interface | `radiant run / validate / explain / gui` — new short chapter |
| 5 | YAML Configuration Format | from `guides/configuration.md` + `RADIANT_Config_Format.md` |
| 6 | Parameter Reference | **generated** — `gen_param_reference.py` output (`guides/parameter_reference.md`) bound directly; stays fresh via the existing `--check` gate |
| 7 | Error Taxonomy | the `RadiantError` tree, per-class meaning and typical triggers |
| 8 | Data Libraries | `SpectralLibrary`, `FPALibrary` (21 presets + provenance manifest), bundled atmosphere libraries |
| 9 | External Data Interfaces | MODTRAN tape7 ingest, measured-data import, spreadsheet interfaces |

**Part 3 — Internals (bind existing architecture specs):**

| Ch | Title | Source |
|---|---|---|
| 10 | Signal-Chain Internals | `RADIANT_Signal_Chain_Architecture.md` (stage protocol, `ChainState`) — bound as-is |
| 11 | Parameter System Internals | `RADIANT_Parameter_System.md` — bound as-is |
| 12 | Testing & Validation Framework | `RADIANT_Testing_Validation.md` — bound as-is |
| 13 | Extending RADIANT | new stage / new parameter walkthrough; import rules; plugins (DEFERRED banner carried over) |

Binding the Part-3 specs verbatim is deliberate: they are already Rule-20 lock-step maintained, so the manual inherits their freshness for free. A light Pandoc-compatibility pass (raw-HTML removal if any, table width fixes) is in scope; a rewrite is not (see §10, Q2).

## 7. Volume IV — RADIANT Worked Examples & Validation

Subtitle: *Case Studies, Example Scripts, and Validation Evidence*. **Mixed-modality by design (owner direction 2026-09-16):** the volume interleaves GUI-driven worked examples (screenshot-illustrated walkthroughs) with scripted examples, so a reader sees both ways of driving the tool. The repo already sources both sides: every scenario carries a mandatory `gui_workflow.md`, and the GUI exercise layer ships GUI-openable baselines per chain scenario.

**Part A — Driving RADIANT from the GUI:**

| Ch | Title | Content | Source |
|---|---|---|---|
| 1 | Running the Examples | setup, extras, the two modalities (GUI baselines vs. scripts), where inputs/outputs live | new + `scenarios/README.md` |
| 2 | GUI Worked Examples | short task-oriented walkthroughs with screenshots: build a sensor from scratch; open a flagship baseline and read every metric group; pick an FPA preset; edit an element train; run a sweep; compare two configs | new prose + `scenarios/GUI_EXERCISE_INDEX.md` + exercise baselines; figures via the Phase-0 screenshot generator |

**Part B — Driving RADIANT from Scripts:**

| Ch | Title | Content | Source |
|---|---|---|---|
| 3 | Scripting Examples | the six `examples/scripts/` programs, each with listing excerpts, output, and commentary (basic evaluation, aperture sweep, compare configs, custom loop, tolerance analysis, dual-band configuration set) | code + new prose |

**Part C — Persona Case Studies (tiered — owner-ratified 2026-09-16, ruling Q3: every scenario appears; eight at full depth, the rest as digests):**

*Tier 1 — full-depth case studies* (one per persona, modality matched to the persona's natural workflow):

| Ch | Case study | Modality |
|---|---|---|
| 4 | 1.1 MWIR maritime surveillance (Sarah, systems engineer) | **GUI-led** |
| 5 | 2.1 InSb vs HgCdTe noise budget (Mike, detector engineer — FPA presets, comparison mode) | **GUI-led** |
| 6 | 3.1 ISR pass planning (Raj, mission planner — geometry modes, GUI sweep surface) | **GUI-led** |
| 7 | 4.1 target detection matrix (Lisa, analyst — batch matrix) | script-led |
| 8 | 5.1 WFE budget allocation (Tom, optical designer — Zernike import) | script-led |
| 9 | 6.1 published SNR benchmark (Dr. Chen, researcher) | script-led |
| 10 | 7.1 NEDT reconciliation (Karen, test engineer — measured-data import) | script-led |
| 11 | 10.2 air-to-air level IRST (general direction) | **GUI-led** |

Each full-depth case study is adapted from the scenario's `walkthrough.md` (mission context, inputs, run, results with units, regime discussion); GUI-led chapters follow the scenario's `gui_workflow.md` with screenshots of each step, and every chapter closes with a one-paragraph pointer to the other modality (the exercise baseline for script-led chapters, the run script for GUI-led ones) so neither path is a dead end.

*Tier 2 — scenario digest compendium* (ch. 12): a 1–2 page digest of **every** scenario not covered at full depth elsewhere (the 39 remaining after the eight case studies and the four flagship-validation scenarios; the tree holds 51 scenario directories, not the 52 first estimated), grouped by persona in catalog order. Fixed digest format, condensed from each `walkthrough.md`: mission setup, key inputs, headline results with units, regime in effect, takeaway, and a pointer to the scenario folder. No new runs — digests report the committed walkthrough numbers.

**Part D — Validation & Cookbook:**

| Ch | Title | Content | Source |
|---|---|---|---|
| 13 | Flagship-Mission Validation | Sentinel-2 MSI SNR, Landsat OLI-2 SNR, Landsat TIRS NEDT, MODIS TEB NEDT vs published values; MODTRAN parity; MWIR single-wave ground truth | scenarios 9.1–9.4 + `docs/validation/` (script-led — these are batch comparisons) |
| 14 | Trade-Study Cookbook | worked sweep/sensitivity/Monte-Carlo recipes, GUI sweep surface and scripted sweeps side by side | `guides/trade_studies.md` |
| A | Appendix: Scenario Index | one-line index of all 51 scenarios with their chapter/digest location (generated from `guides/scenario_catalog.md`) | exists |

Coverage is total by owner ruling (Q3, 2026-09-16): all 51 scenarios appear — eight at full depth (4 GUI-led / 4 script-led), four as the validation chapter, thirty-nine as digests (the tree holds 51 scenario directories; the plan's original 52 was an estimate). The tiering is what keeps the volume at ~150–200 pp instead of 400.

## 8. Build Pipeline (Phase 0)

Generalize the existing single-volume builder; keep the name and CLI shape.

- **Volume registry** in `scripts/build_manual.py`: each volume = title, subtitle, ordered chapter list (paths may span `theory/`, `guides/`, `architecture/`). CLI: `build_manual.py [theory|users_guide|tech_ref|examples|--all] [--tex]`.
- **Shared template** under `scripts/manual_assets/`: Pandoc defaults file + LaTeX template — cover page (title, subtitle, version from `radiant.__version__` + git describe, date), headers/footers, `hyperref`, `longtable` styling, code-listing style.
- **Cross-platform fonts (Rule 30 fix):** replace Helvetica Neue/Menlo with TeX-Live-bundled faces (proposed: TeX Gyre Termes body — a serif face befitting a paper-quality manual — TeX Gyre Heros headings, DejaVu Sans Mono code; all cover µ/°/²). Closes the 2026-09-16 Findings_Log line.
- **Build-time validation** inside the builder (not a merge gate — moratorium): chapters exist, referenced images resolve, raw-HTML scan on manual-class files, balanced `$$`. Fails the build with an actionable message.
- **Bound-spec header stripping (ruling Q2):** when a chapter source is an `architecture/` spec, the builder drops the leading Date/Status/Depends-on metadata block before conversion — the spec files themselves are untouched.
- **CI conversion tripwire (ruling Q5 — moratorium waived for this one job):** a non-blocking CI job runs `build_manual.py --tex --all` (Pandoc only, no TeX install) so Markdown that stops converting is visible without gating merges.
- Output: `build/manuals/radiant_<volume>.pdf`, gitignored. Pandoc/XeLaTeX remain the only external tools; missing tools keep raising actionable errors.
- Equation treatment: `$...$`/`$$...$$` through `--from gfm+tex_math_dollars`, numbered **sections**; per-equation numbering/cross-referencing (pandoc-crossref) is explicitly deferred — it adds a toolchain dependency for cosmetic gain.

## 9. Phasing

Each phase = one or more normal PRs through the standard gate battery (docs-only phases ride the docs-only gate set; Phase 0/3 touch `scripts/`, so full battery).

| Phase | Deliverable | Size | Depends on |
|---|---|---|---|
| 0 | Multi-volume builder, shared template, portable fonts, build-time validation, bound-spec header stripping; `gen_gui_screenshots.py` (offscreen capture generator — spike-proven, see §5); non-blocking CI `--tex` job (ruling Q5); Volume I rebinds and builds under the new template | S–M | — |
| 1 | **Theory Manual v1.0**: chapters 1/7/front-matter written, 4/A bound, physics-inventory audit dispositioned | M | 0 |
| 2 | **Technical Reference v1.0**: orientation chapters, CLI/API/error/data-library chapters, generated parameter reference bound, Part-3 specs bound | M | 0 |
| 3 | **User's Guide v1.0**: capture definitions + figures, chapters 1–12 + appendix; owner reviews rendered PDF per chapter batch (the GUI live-review principle applied to its manual) | L | 0 |
| 4 | **Examples & Validation v1.0**: GUI worked examples + eight full case studies (4 GUI-led / 4 script-led) + 40-scenario digest compendium + flagship validation chapter; GUI-led figures via the Phase-0 generator | L | 0 (content-independent of 1–3) |
| 5 | **Shipping**: release build step stages the manuals (`radiant/manuals/`, ruling Q1) **and the full 51-scenario suite** (`radiant/scenarios/` — owner-directed 2026-09-17: the manuals document every scenario, so pip-installed users get the suite the manual points at; ~13 MB, single canonical home stays `scenarios/`) into the wheel and attaches both as release artifacts; CHANGELOG entry (Rule 29(c): capability added), Gap 131 closure | S–M | 1–4 |

Phases 1, 2, 4 are parallelizable across sessions once Phase 0 lands (one branch per phase, normal worktree hygiene). Phase 3 is the long pole; its chapter batches can interleave with owner review.

## 10. Ratified Rulings (owner, 2026-09-16)

All seven questions were put to the owner one at a time and ruled on 2026-09-16:

1. **Shipping mechanism — BOTH.** A release build step puts the PDFs in the wheel under `radiant/manuals/` and attaches them to the release/distribution as standalone artifacts. The repo never commits them.
2. **Volume III Part 3 sourcing — BIND VERBATIM.** The three architecture specs are bound as-is with a one-page reader's preface; the builder strips the Date/Status/Depends-on metadata headers mechanically. No second lock-step copy is created.
3. **Case studies — ALL 52, TIERED.** The eight proposed full-depth studies with the 4 GUI-led / 4 script-led split stand; every remaining scenario gets a 1–2 page digest (§7 Part C tier 2). Total coverage, tiered depth.
4. **Mission-type framing — SHIPPED MACHINERY ONLY.** The User's Guide documents the auto-classification regime machinery as built; the mission-type selector gets a chapter when (if) it ships.
5. **CI docs build — YES, NON-BLOCKING.** The owner waives the process-machinery moratorium for exactly one CI job: `build_manual.py --tex --all` (Pandoc only, no TeX install), non-blocking — visible red, never gates a merge.
6. **Cover identity — MINIMAL.** Title, subtitle, version + git describe, build date, "RADIANT Project" author line. No logo, no document numbers, no distribution markings.
7. **Screenshot chrome — ALL OFFSCREEN.** Every figure is an offscreen capture with platform-neutral Fusion-style chrome; no hand-captured native shots. Every figure stays regenerable by one command.

## 11. Tracking & Governance

- Ratified 2026-09-16: plan **Active**; tracked as **Gap 131** (`docs/tracking/gaps.md`, minted and pushed the same day); the gap closes at Phase 5.
- Figures and any committed generated content carry Rule-26 manifests naming generator + input + commit.
- New chapters are §5.4-compliant from birth; grandfathered Unicode math in existing bound chapters stays until wholesale rewrite (no churn PRs).
- Owner direction 2026-09-17 (render review): repo-internal anchors (Persona tags, `In RADIANT.`/`Record:`/`Enforced by:` paragraphs, repo doc-path pointers) stay in sources, out of the typeset volumes — implemented as build-time filters; and the scenario suite ships with radiant (folded into Phase 5 above).
- Completion: the PR that lands Phase 5 moves this plan to `docs/archive/` (Rule 24).
