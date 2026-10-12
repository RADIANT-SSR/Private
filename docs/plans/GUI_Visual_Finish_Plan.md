# GUI Visual Finish — Impeccable Program Plan

**Status:** Active — §9 ratified by the owner 2026-10-12 ("ratified and let's kick it off"). Tracked as Gap 143.

**Date:** 2026-10-12
**Category:** D (integration + UX). No physics changes; the plot package touches `radiant.api` (full battery), everything else is GUI-confined (scoped battery).
**Owner statement (conversation, 2026-10-12):** "I'm really pleased with the RADIANT GUI functionality — it captures the stages, inputs, outputs. But it looks like an AI hack job. Text output looks OK; all the plots look amateur. I can tell you when something looks good, but I can't tell you how to make it there."
**Execution model (owner-specified):** Fable 5.1 orchestrates; Opus sub-agents build; independent Opus sub-agents audit the result on **aesthetics only** — the marketing leg of the team, not the coders.

**Read first:**
`docs/architecture/RADIANT_GUI_Architecture.md` (§4 layout, §4.4 figure styling, §8 design system),
`docs/architecture/RADIANT_Personas.md` (user truth),
`PRODUCT.md` (repo root, gitignored — Impeccable product context),
`DESIGN.md` (repo root, gitignored — incumbent system record; **stale**, see §2.3),
`src/radiant/gui/themes/tokens.py` (the single owner of every visual literal),
`src/radiant/api/plot_style.py`, `src/radiant/api/plot.py` (the figure layer),
`~/.claude/skills/impeccable/SKILL.md` and its `reference/` playbooks (the method).

---

## 1. Objective

Take the RADIANT desktop GUI from *functionally complete, visually unfinished* to a **finished, authored, professional and distinctive instrument-grade interface** — plots first — and prove, with evidence the owner can judge by eye, that every change is an improvement.

Success is three things, all required:

1. **Every `result.plot.*` figure** reads as publication-grade in the GUI, in a script, and on a PowerPoint slide — light and dark.
2. **Every GUI surface** (welcome, ten stage views, parameter panel, right rail, dialogs) follows one composition grammar and one vocabulary, so a category-fluent engineer trusts it on sight.
3. **An audit trail** showing, per work package, that independent aesthetic reviewers preferred the new rendering over the old in a blind paired comparison, and that the owner saw it running before it merged.

Non-goals: no new functionality, no change to any computed number, no change to the API surface beyond display-name lookups, no 3D viewer, no web port, no change to the GUI's "view over the scripting API" architecture.

---

## 2. Where we are (evidence, 2026-10-12)

### 2.1 How the evidence was captured

An offscreen Qt capture harness (built this session; becomes `dev_tools/gui_capture/` in Phase 0) loads a config, evaluates, selects each stage and tab, and saves the main window at 1600×1000 in both themes with `QT_QPA_PLATFORM=offscreen`. Every `result.plot.*` figure was also rendered headlessly at 7.5×4.6 in. This is the same mechanism the auditors will use: **deterministic, identical before/after captures**, independent of whoever did the work.

### 2.2 Findings — plots (the owner's primary complaint)

Verdict: **not a matplotlib ceiling.** The house style in `plot_style.py` (left titles, open spines, IBM Plex, CVD-validated series order) is a sound base. The amateur reading comes from per-figure *composition*, all fixable in `plot.py`:

| # | Tell | Where | Fix family |
|---|------|-------|------------|
| P1 | Global `axes.grid=True` rules white lines across `imshow` images | PSF, PSF kernels, pupil | grid off on image axes |
| P2 | Figure does not own its frame: axes fill ~45%; a legend box floats in the void below, duplicating the direct labels already on the curves; a footnote is a third voice | MTF budget, spectral | one labelling device; axes fill; caption as a designed element |
| P3 | Square images centred in a 16:9 frame with empty flanks | PSF, kernels, pupil | pair image with its cross-section cuts in the flanks (what Tom reads) |
| P4 | Default-matplotlib bar charts: 8 fat x/y bar pairs, six of them 1.0, boxed legend; noise bars with gridlines cut through them | MTF-at-Nyquist, noise budget | lollipop/dot plots sorted by loss; 1.0 terms folded; bars over grid |
| P5 | Vocabulary leaks: figure says "Pixel aperture", the table beside it says `mtf_pixel_aperture`; noise table says `signal_shot`, `prnu`, `ktc_reset` | every table next to a figure | one display-name source for figure, table, card, export |
| P6 | Band-edge taper dominates spectral plots (a spike at 3.5/5.0 µm reads as a glitch); "target vs background" draws one line, no legend | spectral family | in-band shading; clipped range; both series visible or say why not |

### 2.3 Findings — chrome

Better than the owner thinks: the stage strip, parameter table, pinned card, tabs and the geometry schematic are consistent and calm. The "hack job" reading comes from a short list:

| # | Tell | Where |
|---|------|-------|
| C1 | Raw `snake_case` identifiers wherever a human reads: `sensor_altitude_m`, `path_zenith_rad` — and **`path_zenith_rad` displayed as `0 deg`** (name and unit disagree on screen) | parameter panel, geometry form, tables |
| C2 | Input fields stretched to half the panel with centred text; labels and values not on a shared column rhythm | every stage Inputs form |
| C3 | Each stage view is a different composition (Performance = cards; Detector = form + table; Optics = form + figure + table) with its own header hierarchy; the tiny grey caption "MTF budget" above a figure that repeats its own title | stage views |
| C4 | Code-comment prose as section titles: "Optics — aperture and wavefront error (transmission: Transmission tab)" | form section headers |
| C5 | Welcome-card mono spec lines truncated mid-word; "Worked examples" eyebrow in a different register from "Start a scenario" | welcome screen |
| C6 | `DESIGN.md` is 155 GUI commits stale (2026-08-02); `tokens.py` changed 2026-09-02; ~20 widgets post-date it | system record |
| C7 | To check in the live GUI, not the offscreen capture: the Performance "Spatial / MTF" card rendered with every value blank | performance view |

### 2.4 What is already right and must be preserved

- The visual world: **"The Calibrated Instrument"** (owner-chosen 2026-08-02) — cool grey-blue surfaces, hairline borders, small radii, mono numerals, one terracotta accent. The findings above are failures of *commitment and finish* inside that world, not evidence against it.
- `tokens.py` as the single owner of visual literals (test-enforced); `plot_style.py` mirroring it (test-enforced).
- The display-units hard rule, units on every output, the 2D not-to-scale schematic, the contextual per-stage layout with persistent right rail, the welcome-screen overlay architecture.

---

## 3. Team and roles

| Role | Who | What they do | What they never do |
|------|-----|--------------|--------------------|
| **Orchestrator** | Fable 5.1 (this session, successor sessions) | Runs the loop in §5; holds the direction contract; captures screenshots; packages inputs; synthesizes; reports to the owner; merges when gates pass | Write GUI or plot code itself; soften an auditor's verdict; narrate to an auditor what changed |
| **Builder** | Opus sub-agent, one per work package, `model: opus`, isolated worktree `../ssr-<wp>` | Implements the brief under CLAUDE.md rules; runs the gate battery; returns a structured report | Judge its own aesthetics; touch files outside the package scope; change a computed number |
| **Aesthetic auditor** ×2 | Opus sub-agents, fresh context, no transcript inheritance | Blind paired comparison and brochure scoring of screenshots (§4.1); the marketing leg | See code, diffs, commit messages, or the builder's report; know which image is "new"; run tools |
| **Users auditor** ×1 | Opus sub-agent, fresh context, briefed as the composite of all seven personas in `RADIANT_Personas.md` | The same blind pairs, scored per persona as "can I do my task faster and with more trust — yes / same / no" (§4.1); the check that stops "looks great, hides the number Mike needs" | Everything the aesthetic auditors never do; grade correctness of numbers |
| **Finish reviewer** | `impeccable-finish-reviewer` (shipped agent) | Fidelity of the build against the direction contract and approved comp; disposition `ship` / `fix` / `rebuild` | Render or screenshot (it has no browser; it gets our captures) |
| **Documenter** | `impeccable-documenter` (shipped agent) | Regenerates `DESIGN.md` + sidecar from the shipped build at the end (Phase 6) | Write the system before the build |
| **Asset producer** | `impeccable-asset-producer` (shipped agent) | Only if §9.1-D ratifies an identity asset (wordmark / app icon) | Invent brand claims |
| **Owner** | Jason | Per-figure yes/no on galleries; live review of every branch before merge (hard rule, 2026-09-01); §9 rulings | Have to say *how* — the comps and galleries are built so a yes/no is enough |

Token discipline (standing owner preference): serialize work packages; at most one builder plus two auditors in flight; auditors are spawned only after a package's captures exist.

---

## 4. The improvement proof — what "verified" means

A work package is **verified** only when all four hold. None substitutes for another.

### 4.1 Blind paired comparison (the aesthetic audit)

- Inputs per surface: the *before* capture (from the baseline set, Phase 0) and the *after* capture, same config, same window size, same theme — a pair for light and a pair for dark.
- Each pair is presented to each auditor as **A / B with the order randomised per pair** (orchestrator keeps the key). Auditors are told only: product purpose (one paragraph from `PRODUCT.md`), the persona who uses this surface, and the surface's job. They are not told which is current.
- Each auditor returns, per pair: preferred (A/B/neither), confidence (1–5), one sentence of the *first thing the eye lands on*, and a **brochure score** 1–5 for each image ("would I put this screen on the product brochure / trade-show demo as-is?").
- Each auditor also returns per package a free-text *creative-director note* (≤150 words): what is now distinctive, what still reads as generic, the one thing they would send back.
- **Users auditor (ratified addition, 2026-10-12):** a third blind auditor briefed as the composite of all seven personas receives the same pairs and returns the same preference and confidence, but instead of a brochure score returns, per pair and per persona, **"can I do my task on this screen faster and with more trust — yes / same / no"**, naming the element that decides it.
- **Pass criteria:** (i) marketing pair — the new rendering is preferred in ≥ 80% of pairs, **no pair** is preferred-old by both, and the mean brochure score rises; (ii) users auditor — **no persona regresses** on any pair (a single "no" fails the pair) and at least one persona says "yes" on the majority of pairs. A failed pair goes back to the builder with every auditor's notes verbatim; a pair the marketing pair loves and the users auditor fails is still a failed pair.
- All three auditors are independent with no shared context and their verdict is **binding on the builder**. If the marketing pair disagrees on more than 30% of pairs, a fourth agent is spawned on the disputed pairs only.

The auditor briefs (verbatim prompt templates) are §8.1 and §8.1b. Benchmarks the auditors are told to hold RADIANT against (owner-named): **Zemax OpticStudio, 4D Technology 4Sight, Zygo Mx** — optical-design and metrology software — for chrome and analysis windows; FT / Economist discipline for sweep and budget figures.

Owner overrule: the owner's live review (§4.4) remains the final gate and may overrule the auditors in either direction; an overrule is recorded in the package's audit file with one line of reason.

### 4.2 Finish review

`impeccable-finish-reviewer`, spawned fresh with: the package brief, the owner's confirmed answers, the artifact paths, the after-captures (light + dark), the direction contract (§5.2), `PRODUCT.md`, the approved comp path, and the craft-floor reference. Its disposition word is reported verbatim. `fix` → one batch, recapture, verdict pass; two rounds maximum; open items go to the owner's table, never relabelled.

### 4.3 Technical gates (unchanged from CLAUDE.md)

GUI-confined packages: full GUI suite + `pytest scripts/` + every static gate. The plot package and any display-name package touching `radiant.api` or any `_schema.py`: the full battery. Rule 20 docs in the same PR (GUI arch §4.4 / §8); Rule 29 CHANGELOG entry for every user-visible change; Rule 21 findings recorded.

### 4.4 Owner live review

No GUI merge the owner has not seen running (hard rule). The orchestrator launches the branch for the owner with the gallery / contact sheet open alongside. Approval is a plain "yes" per package; a "no" names the surface and goes back to §5 step 4.

### 4.5 Audit record

Each package's record — randomisation key, both auditors' returns, the finish-reviewer disposition(s), and the owner's approval line — is written to `docs/reports/gui_visual_finish_2026-10/<wp>.md` (immutable point-in-time record, Rule 24) with one downscaled before/after contact sheet per package committed beside it (Rule 26(b): a figure a committed document references, generator named). Full-resolution captures stay in the gitignored `.impeccable/captures/` tree.

---

## 5. The loop — one work package, start to finish

1. **Shape** (`/impeccable shape <wp>`): one or two rounds of 2–3 questions to the owner; returns the package brief (job and audience, outcome and proof, selected direction, scope and anti-goals, states and ranges, interaction intent, constraints). The owner answers in plain language; the brief never asks for CSS values.
2. **Direction** (new-work §1–5, inside the established world): the orchestrator writes the five-block contract — THESIS, OWN-WORLD, STORY, FIRST VIEWPORT, FORM — plus FINISH. It is stored as the module docstring preamble of the package's primary file (the Qt equivalent of the "first child of body" comment) so it survives the build and the reviewer can audit against it.
3. **Comps** (visualize, adapted): no image-generation tool exists here, so comps are **rendered prototypes** — three materially different compositions of the surface, built as throwaway code and captured through the harness, saved under `.impeccable/mocks/<wp>/` with a `.json` sidecar carrying the prompt and, after the owner picks, `"approved": true`. For figures the three comps are three real matplotlib renders of the same data. The owner picks one (or combines); nothing is built until a pick is recorded. This is the substitute for the visualize playbook's generated images and keeps its single non-skippable approval point.
4. **Build**: Opus builder in `../ssr-<wp>` with the brief, the contract, the approved comp, `DESIGN.md`, `tokens.py`, the craft floor, and the relevant Impeccable playbooks named in §6. Builds fully committed to the comp; runs the gate battery; returns the CLAUDE.md structured report.
5. **Capture**: orchestrator runs `dev_tools/gui_capture` on the branch — same config set, same sizes, both themes — and assembles the contact sheet and the gallery.
6. **Finish review** (§4.2) → fix batch if `fix` → recapture → verdict.
7. **Aesthetic audit** (§4.1), blind, two auditors in parallel.
8. **Owner live review** (§4.4) with the gallery open.
9. **Merge** on `main` from a checkout on `main`; delete the branch; push; write the audit record (§4.5); tick the ledger in §7.

Steps 6 and 7 may run concurrently once captures exist; neither sees the other.

---

## 6. Impeccable capability map — every command, where it is used, or why not

| Command / capability | Used in | How it applies to a Qt desktop app |
|---|---|---|
| `init` | Phase 0 | Refresh `PRODUCT.md`: v0.4.0 surfaces (configuration set to 12, FPA presets, element detail editor, calibration stage), current personas doc, the "no identity system exists" fact (§9.1-D) |
| `document` | Phase 6 only | `impeccable-documenter` regenerates `DESIGN.md` from the shipped build; never before (a rulebook written first gets defended against reality) |
| `shape` | every WP | The discovery interview with the owner; produces the brief; writes no code |
| new-work §1–7 | every WP | World decision (§9.1-A), direction contract, rendered comps, full-commitment build, batched inspection, finish review, documenter |
| `critique` | Phase 0 baseline; re-run at Phase 6 | Dual-agent: A = design review (Nielsen 10, cognitive load, persona red flags, design-specificity verdict) over the baseline captures; B = evidence pass over the same captures against the craft-floor checklist (the bundled `detect.mjs` is HTML-only and `node` is absent, so B is a screenshot-evidence agent and the report carries the provenance line saying so). Snapshot written by hand to `.impeccable/critique/<slug>.md` in the storage format, so the score trend exists at Phase 6 |
| `audit` (native variant) | Phase 5 | Appearance & theming (token coverage, both themes first-class), platform conformance (macOS native feel — menus, shortcuts, dialogs; Windows via the deploy checklist, Q1), adaptivity (1280×800 → 2560×1440, HiDPI 1×/2×), accessibility (keyboard focus order, contrast, labels), performance (figure embed latency, panel repaint) |
| `typeset` | WP-3 | Type ramp as actually rendered in Qt; numerals (tabular mono for every value); caption vs label vs title; Plex bundling (CU-103) so Windows renders the same face |
| `layout` | WP-3 | Field widths, label/value column rhythm, section spacing, one composition grammar across all ten stage views |
| `clarify` | WP-2 | Human display names for parameters, outputs, noise terms, MTF terms; units that agree with names; section titles that name the section, not the code comment; actionable message copy |
| `colorize` | WP-1, WP-3 | Restrained strategy (Operate mode floor): accent for primary action / selection / state only; series palette vs chrome contrast; state vocabulary (stale, evaluating, fresh, error) consistent in both themes |
| `quieter` | WP-3 forms, WP-4 messages | Where the surface shouts (oversized fields, boxed legends, redundant captions) |
| `bolder` | WP-4 welcome screen only | The one surface with permission to commit harder (first-run); still inside the world |
| `distill` | WP-3 Performance view, parameter panel | Remove what competes with the reading: duplicate titles, empty cards, eyebrow captions |
| `harden` | WP-4 | Every state: no config, stale, evaluating, failed run, long names, narrow window, missing fonts, Windows paths |
| `onboard` | WP-4 | Welcome screen, first evaluate, empty states that teach |
| `animate` | WP-4 | Operate-mode motion only: state transitions 150–250 ms (stale → evaluating → fresh); no decoration, no load choreography |
| `delight` | WP-4 | One authored moment, restrained — candidate: the evaluate completion on the stage strip health dots |
| `adapt` (native) | Phase 5 | Window-size and HiDPI adaptation on macOS; Windows parity is a deploy-time checklist, not a capture (Q1) |
| `optimize` | Phase 5 | Figure embed and resize latency; parameter-panel repaint under 12 configurations |
| `polish` | end of every WP | Final whole-path pass reading the critique snapshot's P0/P1 as backlog; refinement never redesign |
| `extract` | Phase 6 | Promote recurring widget patterns (readout row, section header, figure frame with caption, form field) to shared components; promote repeated literals to tokens |
| `doctor` | Phase 6 | Drift check across `PRODUCT.md`, `DESIGN.md`, sidecar, surface briefs |
| `craft-floor` | every build | Loaded by every builder immediately before editing; its Refuse list is binding (no eyebrows/kickers — the "MTF budget" caption above a titled figure is exactly this; no mono as costume; no glyph icons) |
| `operate.md` | every build | Mode is **Operate** for every surface; the product slop test ("can a category-fluent user trust it on sight") is the bar |
| `dataviz` skill | WP-1 | Loaded before any figure code: form heuristic, colour formula and validator, mark specs, stat-tile rules for the pinned card and metric cards |
| `impeccable-finish-reviewer` | every WP | §4.2 |
| `impeccable-documenter` | Phase 6 | `DESIGN.md` |
| `impeccable-asset-producer` | only if §9.1-D says yes | Wordmark / app icon |
| `live` | **not used** | Web-only (browser overlay + HMR); its role is filled by the owner's live review of the running branch |
| `hooks` / `detect.mjs` | **not used** | HTML/CSS rule engine; Qt stylesheets are out of its reach; the auditors and finish reviewer carry the aesthetic check instead |
| `overdrive` | **not used** | An Operate surface for engineers; "past conventional limits" is the wrong bar |
| `extract`/`document` before build | **not used** | Both are post-build by design |

---

## 7. Work packages and ledger

Order is by leverage and blast radius. Each row is one short-lived branch, one merge, one audit record.

| WP | Scope | Primary files | Battery | Impeccable commands | Status |
|----|-------|---------------|---------|---------------------|--------|
| **WP-0 Charter & baseline** | Ratify §9; refresh `PRODUCT.md`; commit the capture harness as `dev_tools/gui_capture/`; capture the baseline set (both themes, 6 surfaces × 3 configs); baseline `critique` per surface; mint the Gap entry | `dev_tools/gui_capture/`, `.impeccable/` | static gates + `pytest scripts/` | `init`, `critique` | Open |
| **WP-1 Figures** | One composition standard for all 25 `plot_*` functions (P1–P6); gallery before/after light/dark; owner per-figure yes/no | `api/plot.py`, `api/plot_style.py`, `api/tests/test_plot*.py`, GUI arch §4.4 | **full** (api) | `shape`, new-work, `dataviz`, `colorize`, `typeset`, `polish` | Open |
| **WP-2 Vocabulary & units** | One display-name source for every parameter, output, noise term, MTF term, metric; names agree with displayed units; section titles; message copy | location per §9.1-B; `gui/param_format.py`, `gui/metric_format.py`, the tables next to figures | full if `_schema.py` or `api` touched, else scoped | `clarify`, `distill` | Open |
| **WP-3 Composition grammar** | One grammar for all ten stage views (header → inputs → outputs → figure → table), field widths and column rhythm, readout rows, section headers, parameter panel density, right rail, stage strip | `gui/widgets/*_inputs_form.py`, `field_row.py`, `stage_views.py`, `parameter_panel.py`, `right_rail.py`, `themes/stylesheet.py`, `tokens.py` | scoped (GUI) | `layout`, `typeset`, `colorize`, `quieter`, `distill`, `polish` | Open |
| **WP-4 States & first run** | Welcome screen, no-config, stale/evaluating/fresh, failed run, messages panel, long content, narrow window; one authored motion moment | `welcome_screen.py`, `messages_panel.py`, `run_button.py`, `stage_strip.py`, `saturation_banner.py` | scoped (GUI) | `onboard`, `harden`, `bolder` (welcome), `animate`, `delight`, `polish` | Open |
| **WP-5 Adaptivity & performance (macOS)** | HiDPI 1×/2×, window sizes 1280×800 → 2560×1440, splitter behaviour, figure embed and resize latency, keyboard focus and contrast; a written **Windows deploy checklist** (fonts resolved, HiDPI, menu/shortcut conventions, path pickers) for the owner's later deployment — no Windows capture (Q1); no font bundling (Q2) | `themes/fonts.py`, `matplotlib_canvas.py`, `responsive_splitter.py`, `docs/guides/` (checklist) | scoped (GUI) | `audit` (native), `adapt` (native), `optimize`, `polish` | Open |
| **WP-6 System record** | Shared components extracted; tokens promoted; `DESIGN.md` regenerated by the documenter; re-run `critique` for the trend line; `doctor`; archive this plan | `gui/widgets/` shared set, `tokens.py`, `DESIGN.md`, `.impeccable/design.json` | scoped (GUI) | `extract`, `document`, `critique`, `doctor` | Open |

Ledger convention: on merge, the Status cell becomes `Merged <sha> · audit <report path> · owner ✓ <date>`. The plan moves to `docs/archive/` in the PR that merges WP-6 (Rule 24).

**Estimated cadence:** one package per working session; WP-1 and WP-3 may take two. The audit adds roughly two auditor runs and one reviewer run per package — small against the builder's cost.

---

## 8. Briefs — the prompts, so execution is mechanical

### 8.1 Aesthetic auditor brief (verbatim template)

> You are the creative director on the marketing side of a small aerospace software company. You are preparing this product's brochure and trade-show demo. You are not an engineer and you do not read code. You judge screens the way a design director judges a layout: hierarchy, finish, consistency, confidence, and whether a stranger would believe a serious team made this.
>
> Product, in one paragraph: *[PRODUCT.md purpose + positioning]*. The person who uses this screen: *[persona line from RADIANT_Personas.md]*. This screen's job: *[one sentence from the WP brief]*.
>
> You will see N pairs of screenshots, labelled A and B. In each pair the two images show the same screen with the same data. You do not know which is older. For each pair return:
> 1. `preferred`: A, B, or neither;
> 2. `confidence`: 1–5;
> 3. `first_landing`: the first thing your eye lands on in each, one sentence each;
> 4. `brochure_score`: 1–5 for each image — 5 means you would print it as-is, 1 means you would hide it;
> 5. `why`: two sentences, concrete — name the element.
>
> Then one note (≤150 words) for the whole set: what reads as distinctive and authored, what still reads as generic or default, and the single thing you would send back before it ships.
>
> Do not describe what the software does. Do not guess which image is newer. Do not grade correctness of numbers. Return JSON for the pairs and plain text for the note.

### 8.1b Users auditor brief (verbatim template)

> You are seven people at once — the users of this software, described in the attached persona document: Sarah (systems engineer running trade studies whose numbers end up in PowerPoint), Mike (detector physicist who wants every noise term in electrons and distrusts anything that hides an assumption), Raj (mission planner who needs a yes/no with margin from one scenario), Lisa (analyst who depends on the GUI and exports tables for briefings), Tom (optical designer reading MTF and PSF decompositions), Dr. Chen (researcher who wants every intermediate and its provenance), Karen (test engineer comparing predicted to measured). You do not read code.
>
> This screen's job: *[one sentence from the WP brief]*.
>
> You will see N pairs of screenshots, labelled A and B, the same screen with the same data; you do not know which is older. For each pair return `preferred` (A / B / neither), `confidence` (1–5), and then **for each of the seven personas**: `task_speed_trust`: yes / same / no — "on this version I can do my task faster and trust the result more" — and `deciding_element`: the one element that decides it (a value, a label, a figure, a control). If a persona would not use this screen, write `n/a`.
>
> Then one note (≤150 words): which persona is best served now, which is worst served, and the single thing that must change before you would put this in front of a customer.
>
> Do not grade correctness of numbers. Do not guess which image is newer. Return JSON for the pairs and plain text for the note.

### 8.2 Builder brief (skeleton)

> Category D. Read first: CLAUDE.md in full; `docs/architecture/RADIANT_GUI_Architecture.md` §4 and §8; `DESIGN.md`; `src/radiant/gui/themes/tokens.py`; the package brief below; the direction contract; the approved comp at `.impeccable/mocks/<wp>/<n>.png`; Impeccable `reference/craft-floor.md` and `reference/operate.md` immediately before editing UI; `reference/<commands>.md` named for this package.
>
> Build the approved comp fully committed; the comp is the spec for composition, hierarchy, density and material, not a pixel spec for semantics. Every visual literal goes through `tokens.py` (and `plot_style.py` for figures — the mirror is test-enforced). Preserve behaviour, copy facts, units rule, and everything outside scope. Do not add an eyebrow caption, a boxed legend, a glyph icon, or a mono face used as decoration. Work in `../ssr-<wp>` on branch `<wp>/<slug>`; run the battery named for this package; record findings per Rule 21; CHANGELOG per Rule 29; docs per Rule 20. Return the CLAUDE.md structured report. Do not judge your own aesthetics; capture nothing — the orchestrator captures.

### 8.3 Direction contract (format)

Five blocks, ≤150 words, in the primary module's docstring: THESIS · OWN-WORLD · STORY · FIRST VIEWPORT · FORM, then `FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md`.

---

## 9. Decisions — ratified 2026-10-12

Rulings, taken one at a time in conversation and ratified together:

| | Ruling |
|---|---|
| A | **Keep** "The Calibrated Instrument"; commit harder. Test applied: the geometry Schematic tab is the proof the world works when built with commitment. |
| B | Display names live in **`radiant.api.display_names`**, test-enforced for every `ParameterDef` and every stage-output key; `_schema.py` untouched. |
| C | Figures redesigned **API-wide**; figure-snapshot tests re-baselined under §5.3 in the same PR. |
| D | **No identity asset now**; revisit after WP-4 against the finished welcome screen. |
| E | **Three binding auditors** — marketing pair + users composite (§4.1); owner overrule recorded. |
| F | Baseline on **`mwir_leo_minimal`, the Landsat OLI-2 all-bands study, one point-source scenario**. |
| Q1 | **macOS only.** Builds are verified on macOS; the owner deploys on Windows later. WP-5 becomes macOS adaptivity/performance plus a written Windows deploy checklist. No program step depends on a Windows capture. |
| Q2 | **No font bundling** — resolve against installed fonts as today; CU-103 stays open as-is. Type work is designed on installed Plex and verified for graceful fallback. |
| Q3 | Benchmarks: **Zemax OpticStudio, 4Sight, Zygo Mx**. |
| Q4 | **Visible `Agent` calls**, serialized — same prompts, blindness, randomisation and scoring as a scripted workflow would give. |

The proposals as they were put to the owner are kept below for the record.

### 9.1 Proposed decisions (as put, 2026-10-12)

- **A. The visual world stays "The Calibrated Instrument" and the program commits to it harder.** Rationale: the world is product-true (precision instrument, mono numerals, chrome that recedes), owner-chosen, and encoded in `tokens.py`; every finding in §2 is a finish failure inside it, not a reason to replace it. "Unique" is earned by commitment and detail — the geometry schematic already shows what that looks like. A replacement world would discard a coherent system to fix defects that are cheaper to fix in place. *Alternative, if declined:* run new-work §3 "replace the visual world" in WP-0 with seven candidates and three rendered comps before anything else.
- **B. Display names live in the API layer, not the schema.** A `radiant.api.display_names` registry (parameter → human label; output/noise/MTF/metric key → label) consumed by figures, tables, cards, and exports. Keeps "clickable = scriptable", keeps `_schema.py` untouched (no full-GUI-suite trigger per change), and gives scripts the same labels the GUI shows. *Alternative:* a `display_name` field on `ParameterDef` — cleaner provenance, but a schema surface change (Rule 20 docs, full battery, `gen_param_reference`).
- **C. Figures are redesigned API-wide, per the 2026-08-03 ruling** — scripts, notebooks, saved PNGs and the GUI all change together. Golden *numbers* are unaffected; any figure-snapshot test is re-baselined under the §5.3 review protocol in the same PR.
- **D. No identity asset is produced in this program** (no logo, wordmark, or app icon) unless the owner wants one; `PRODUCT.md` records that none exists. If wanted, it is a WP-4 add-on through `impeccable-asset-producer` with an owner approval point.
- **E. Auditors are Opus, two per package, blind, and their verdict is binding on the builder** (a failed pair returns to build). The owner's live review remains the final gate and can overrule in either direction; an overrule is recorded in the audit file with one line of reason.
- **F. Baseline captures use three configs**: `examples/mwir_leo_minimal.yaml` (sparse), the Landsat OLI-2 study (12-configuration bar, most figure types), and one point-source scenario (sub-pixel regime, EE_box path) — so every stage view is exercised with real content.

### 9.2 Open questions (as put; answered in the table above)

1. Is there a Windows machine (or VM) the orchestrator can capture on for WP-5, or is Windows verified by the owner's eyes only?
2. Plex bundling (CU-103): ship IBM Plex Sans/Mono in the wheel under the OFL (≈1.5 MB), or keep resolving to system fallbacks? Without bundling, Windows renders Segoe UI and the type work in WP-3 is only half-verifiable.
3. Does the owner want a say in the auditors' benchmark set — i.e., which products should "professional" be judged against? Default: instrument-grade engineering UIs (test-and-measurement software, CAD property panels) for chrome; FT/Economist/Observable house styles for figures.
4. May the orchestrator use the Workflow tool for the audit fan-out (two auditors + reviewer in one scripted step), or should every sub-agent be a visible `Agent` call? Default: `Agent` calls, serialized, per the token-conservation preference.

---

## 10. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Auditors reward novelty over fitness (prefer the louder image) | The brief fixes the persona and the brochure framing; the finish reviewer holds fidelity to the contract; the owner's live review is the final gate |
| Offscreen captures differ from on-screen rendering (fonts, DPI, native widgets) | Harness records Qt version, platform plugin, font resolution in every capture's sidecar; owner live review catches the rest; WP-5 adds a real-display capture path |
| Figure redesign breaks a figure-snapshot test or a scenario walkthrough figure | Re-baseline under §5.3 in the same PR; scenario figures regenerate by their own runners (Rule 26); CHANGELOG entry per figure family |
| Display-name registry drifts from the schema | A test asserts every `ParameterDef` and every output key in the stage-output manifests has a label |
| Scope creep into functionality while "in there" | Every builder brief carries the anti-goals; the finish reviewer flags "added without approval" as a material finding |
| The plan outlives its usefulness in `docs/plans/` | WP-6 archives it; the ledger in §7 is the only status record |

---

## 11. Phase 0 — first session, concretely

1. Owner ratifies §9.1 A–F and answers §9.2 (one message is enough).
2. Mint the Gap entry (fetch, append, push the stub to `main`).
3. `init` refresh of `PRODUCT.md`; commit the capture harness to `dev_tools/gui_capture/` with a README naming it as the generator of every contact sheet in `docs/reports/gui_visual_finish_2026-10/`.
4. Capture the baseline set per §9.1-F; store under `.impeccable/captures/baseline/`.
5. Baseline `critique` of six surfaces (welcome, geometry, optics, detector, performance, parameter panel) — dual-agent, scores persisted — so WP-6 can print the trend.
6. Open WP-1 with `shape`.
