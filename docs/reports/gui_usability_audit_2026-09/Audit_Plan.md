# GUI Usability Audit — Plan

**Status:** Active — §10 ruled by the owner 2026-09-19 ("whatever you think is best"; no Windows machine; the target is irritation in real workflows). Phase 1 findings: `Findings_Bootstrap_Recovery.md`.
**Date initiated:** 2026-09-19
**Owner trigger:** Jason Forsyth, 2026-09-19 — "a critical look into the GUI … challenges and problems encountered when actually using the tool … switching between different types of analysis and scenarios without opening up pre-existing scenarios."
**Auditor:** coding agent (headless scripted drive) + owner (live native sessions), see §2.
**Scope class:** Rule 28 chartered audit. Read-only on `src/`; every output lives in this folder. Findings are dispositioned CU'd / Planned / Declined at close.
**Not in scope:** physics correctness, golden values, numerical accuracy. A number is judged only by whether the tool told the truth about its own state.

**Read first:** `docs/architecture/RADIANT_GUI_Architecture.md`, `docs/architecture/RADIANT_Personas.md`, `docs/guides/ug_main_window.md`, `docs/guides/ug_menu_reference.md`, `docs/guides/ug_troubleshooting.md` §6 (the recovery claims this audit tests), `docs/reports/GUI_audit_071426/GUI_Capability_Audit.md` (the 2026-07 capability audit — that one asked *what is missing*; this one asks *what goes wrong when you use what is there*).

---

## 0. The question

> Can each persona get from an **empty window** to their deliverable, **pivot** mid-session to a different kind of analysis, make ordinary mistakes, and **recover** — without a wedge, a misleading message, or having to leave the GUI for YAML or a script?

Two owner-reported symptoms motivate the charter and are the first two things the audit must reproduce and characterize:

1. **Conflict wedge.** Editing a parameter that conflicts with something set earlier lands the session in a state that cannot be repaired one edit at a time.
2. **Blank-start error spray.** Building a configuration from nothing produces errors on every edit until the configuration is complete, and the errors do not say what is still missing.

The 2026-09-19 pre-charter probes (§6) already reproduced both mechanisms headlessly.

## 1. Ground rules

1. **Every journey starts blank.** File ▸ New or a bare launch, then the welcome screen's *Blank config* card. No shipped YAML, scenario `.gui.yaml`, study, or mission template is opened inside a journey. (Exception: track T-R deliberately tests the mission-template cards, because the troubleshooting guide §6.3 names them as the recovery surface. That claim is under test, so the track may use them.)
2. **Entry is through the GUI's own surfaces:** stage forms, the Parameters dock (row edit dialog, right-click menu), the family mode selectors, the dialogs (sweep, solve, configurations, FPA part picker, element editor, QE table). The YAML editor and the scripting window are themselves surfaces under test (tracks T-D, T-S); a journey may **not** use them to get past a form that failed. If the only way through is YAML or a script, that is the finding.
3. **The state is read the way an operator reads it:** the Messages rail, the modal error text, the title-bar `*`, the Evaluate button's stale/amber state, the family-card tint, the stage strip, disabled menu actions, the Parameters dock provenance badges and *Changed only* filter, the Inspector, and the files an export writes. Internal Python state is consulted only to confirm what the screen showed.
4. **Every finding is reproducible from numbered steps** starting at Blank config, with a screenshot of the moment it appears, and a severity (§2.4). No "it felt clunky" without steps.
5. **Physics is not judged.** An implausible number is out of scope unless the GUI misrepresents its provenance, units, staleness, or completeness.
6. **Nothing is fixed during the audit.** Fixes are dispositions at close (Rule 28); the live-review rule (owner-ratified 2026-09-01) gates every GUI merge that follows.

## 2. Method

### 2.1 Harness A — headless scripted drive (agent)

The real GUI, offscreen. `scripts/gen_gui_screenshots.py` already proves the pattern: `QT_QPA_PLATFORM=offscreen`, construct `RADIANTMainWindow`, wait for the worker-thread evaluation, grab any widget to PNG. The audit driver extends that pattern in a scratch script (not committed — the committed record is steps + screenshots):

- **Drive real widgets**, not the API: `QTest.mouseClick` on stage chips, tabs, mode radio buttons, form fields and dialog buttons; `QTest.keyClicks` into editors; the same `ParameterEditorDialog` commit path an operator's Enter key takes. The `Sensor` is never written to directly.
- **Read the operator channels** after every step: rail text, dialog text, title, button label and colour, tint, enabled states, dock rows and badges. Screenshot each step to `figures/<track>/<step>.png` in this folder; only figures a findings document references are kept (Rule 26b, generator = the driver script named in the manifest).
- **Timing.** The production 200 ms debounce is kept (`RADIANT_GUI_DEBOUNCE_MS` unset) so message ordering is what an operator sees; the suite's 10 ms override is not used.
- **Layout probes.** The window and dock are resized to the widths in track T-H; offscreen grabs show clipping exactly as CU-363 and CU-371 found.

Harness A cannot judge: latency and responsiveness, focus and keyboard order on native widgets, native file dialogs, macOS window decorations and HiDPI, menu-bar behaviour on macOS, dark theme on a real display.

### 2.2 Harness B — live native sessions (owner)

For what Harness A cannot see. Each live session is a **script**: the agent hands the owner the numbered steps of one or more journeys, the owner drives the native window, and reports per step (a screenshot or a sentence). Live sessions are used for: journey J-1.1 and J-4.1 end to end (the two most GUI-dependent personas), track T-H, track T-I, and every S1/S2 finding from Harness A, to confirm it reproduces natively.

### 2.3 What is observed, per step

| Channel | What is checked |
|---|---|
| Messages rail | new message? correct family (rejection / advisory / warning)? names the parameter? clears when the condition clears? duplicates? |
| Modal error dialog | appears only when the guide says it should; what/why/action all present; *action* is doable from where the user is |
| Locator | tint / jump-to-stage lands on the parameter the message names |
| Staleness | the Evaluate button and result cards go stale exactly when an input changed, and only then |
| Title bar | `*` on first edit; cleared on Save; guard on New/Open/Quit |
| Menu gates | *config* / *result* / *sweep* gated actions enable and disable at the documented moments |
| Parameters dock | badge shows the true provenance (user / default / derived / configured); *Changed only* lists exactly what was set |
| Exports | file written, units on every column, contents match the screen |
| Undo | `Ctrl+Z` returns the screen to the previous state, including form widgets and tint |

### 2.4 Severity

| Level | Meaning | Example |
|---|---|---|
| **S1 — wedge / loss** | no in-GUI exit short of File ▸ New or Open, or work is lost, or the tool lies about state (green when stale, saved when not) | a mode switch every edit of which is rejected |
| **S2 — blocked** | an exit exists but is undocumented, undiscoverable, or requires the YAML editor or scripting window | recovery needs *Reset to Default* on two parameters the message did not name |
| **S3 — friction** | the task completes but a message misleads, a locator points wrong, or steps are wasted | "Circular dependency" on a blank config |
| **S4 — polish** | wording, layout, defaults, ordering | truncated label at default dock width |

### 2.5 Error-message rubric (applied to every message seen)

1. Names the parameter by its dot-path and its form label.
2. Says why in one sentence a persona of the relevant expertise understands.
3. Says what to do, and the action is possible from the current screen.
4. The locator lands on the named parameter.
5. It does not fire for a condition the user has not yet had a chance to satisfy (a blank config is incomplete, not wrong).
6. It disappears when the condition clears.
7. It contains no process language (CU numbers, ADR references, "owner ratified", "v1-minimal") — the CU-371 family bar.

## 3. Surface inventory and coverage matrix

Every clickable thing, from `ug_menu_reference.md`, mapped to the journeys (§4) and tracks (§5) that exercise it. A surface with no entry in the right-hand column is a coverage gap in this plan, to be closed before ratification.

| Surface | Exercised by |
|---|---|
| Welcome screen: Blank config, template cards, worked examples, recent | all journeys (blank), T-R |
| File: New / Open / Recent / Save / Save As / Export YAML / Export JSON / Export Resolved YAML / Export Metrics CSV / Export Sweep CSV / Export XLSX / Quit | T-C, T-G, J-1.3, J-4.2, J-6.2 |
| Edit: Undo / Redo / Reset to Defaults / Configurations… | T-C, T-E, J-4.1 |
| View: Parameter panel F6 / theme / right rail F7 / Angles in Degrees / Go to Stage | T-H, T-I, T-U |
| Run: Evaluate / Run Sweep… / Monte Carlo… / Batch Run… | every journey, T-F, J-1.1, J-4.3, J-6.3 |
| Tools: Inspector / Scripting Window / Schema Browser / Compare Config Files… / Compare Measured MTF… / Solve for Parameter… / Explain Parameter… | J-6.1, T-S, J-2.1, J-4.2, J-5.3, J-1.2, T-B |
| Not-wired actions (8) and Help menu | T-J |
| Right rail: Evaluate button, Edit Config (YAML), + Pin…, per-row pin, Messages | every journey, T-D, T-K |
| Stage strip chips; Ctrl+1…0 | T-I |
| Parameters dock: filter, Changed only, row right-click (Edit / Copy / Explain / Reset / Configure / Un-configure) | T-A, T-B, T-E |
| Geometry: scene-class card, four family cards with mode selectors, site elevation, target size/shape, derived-angle readout, schematic tab with editable forms | J-3.x, P-03…P-05, P-12 |
| Source: Scene & regime, Target thermal / reflective / point source, Background & contrast | P-01, P-02, J-3.2, J-4.1 |
| Atmosphere: model selector, family picker, guidance | P-06, J-3.3, J-7.1 |
| Optics: Inputs, Transmission selector, element train, Import Zemax Zernike…, MTF, PSF + Pupil tabs | J-5.x, P-07 |
| Platform form | J-1.2, J-5.2 |
| Detector: FPA part picker (choose / details / remove / datasheet), form, QE table, QE import preview, pixel phase | J-2.x, P-08, J-7.2 |
| Readout: architecture selector and the rest | J-2.2, P-09, Gap 102 boundary |
| Calibration: scheme selector, cal points, three error families | J-7.x, P-10 |
| Performance: Compute checkboxes, metric table, per-configuration columns | P-14, J-1.1, J-4.1 |
| Configuration bar (studies): tabs, ⚙ Manage… | T-E, J-4.1 |
| Sweep dialog: 1-D / 2-D, progress, cancel, retained result | T-F, J-1.1, J-5.2 |
| Solve dialog | J-1.2, J-5.3 |
| Comparison dialog | J-4.2 |
| Scripting window, Monte Carlo and Batch scaffolds | T-S, J-4.3, J-6.3 |

## 4. Persona journeys

Twenty-one journeys, three per persona, ordered so that each persona's second and third journey **pivot** out of the first without starting over. Every journey has the same fields.

- **Goal** — the deliverable in the persona's words.
- **Start** — always Blank config unless the journey is a pivot from a named earlier journey, in which case the live session continues.
- **Steps** — what the persona does, in the order a person who does not know the tool would try.
- **Probe points** — where the plan expects trouble and what to look at.
- **Pass** — the observable condition that means the journey worked.

Parameter names are given so the driver can find the row; the persona would find them by label.

### P1 — Sarah, EO Systems Engineer (v1-critical)

**J-1.1 Aperture trade from nothing.**
*Goal:* SNR and NIIRS vs aperture 15–60 cm, MWIR, 300 K target, 500 km, 10 cm GSD, for a slide.
*Start:* Blank config.
*Steps:* (1) Geometry: platform altitude 500 km, viewing V1 path zenith 0, then realise the GSD needs focal length and go to Optics. (2) Optics: aperture 0.3 m, f/4 (`optics.f_number`), spectral band 3.5–5.0 µm — wherever the band lives, she will look in Optics first. (3) Source: thermal target 300 K, ε 0.95, extended scene. (4) Atmosphere: `simple`, a mid-latitude profile. (5) Detector: pitch 15 µm, integration time 5 ms, leave the rest at defaults. (6) Evaluate. (7) Run ▸ Run Sweep… 1-D over `optics.aperture_diameter_m` 0.15–0.60, 10 points, metrics SNR and NIIRS. (8) Export Sweep CSV, Export XLSX.
*Probe points:* the message count and text between steps 1 and 6 (the blank-start spray, §6 F-2); whether any step tells her what is still missing; whether the sweep dialog explains that it sweeps a clone and the main window stays put; whether NIIRS is refused out of the GIQE envelope and whether the refusal reaches the card (CU-371 II-009); whether the sweep result survives a subsequent edit or is silently dropped; units on every CSV column.
*Pass:* two exports on disk with units; the rail names what was missing at every failed evaluate; no message she had to ignore.

**J-1.2 Add jitter and find the tolerable limit** (pivot from J-1.1).
*Steps:* (1) Platform: set jitter. (2) Watch the MTF and NIIRS cards go stale and recompute. (3) Tools ▸ Solve for Parameter…: jitter such that NIIRS = 5. (4) Explain Parameter on the solved value.
*Probe points:* does the solve dialog list only parameters that make sense; what happens when the target is unreachable; is the solved value written to the document or only reported, and does the screen say which.
*Pass:* the solved value is visible, its provenance badge says how it got there, undo removes it.

**J-1.3 Same trade, LWIR** (pivot from J-1.2).
*Steps:* (1) Change the band to 8–12 µm. (2) Change the detector cutoff to match. (3) Evaluate. (4) Save As a new file; confirm the title bar and *Changed only* show what she set.
*Probe points:* pivot P-13 — does anything from the MWIR setup (QE curve, filter, FPA preset if one was applied) silently stay and contradict; do the stale markers cover every metric; does Save As adopt the new path.
*Pass:* one coherent LWIR configuration, and the tool said so or said what disagreed.

### P2 — Mike, Detector Physics Engineer (v1-critical)

**J-2.1 Noise budget for a detector he specifies to the digit.**
*Start:* Blank config.
*Steps:* (1) Go straight to Detector and enter everything: material, cutoff, QE, dark current, read noise, IPC, pitch, fill factor, temperature 80 K, integration 10 ms. (2) Readout: CDS, gain, FWC. (3) Evaluate — expect failure: no geometry, no source. (4) Fill the minimum scene he does not care about (§6 F-2 is the probe: does the tool tell him *what* the minimum is?). (5) Read the noise budget table on Detector ▸ Noise; pin the terms. (6) Export Metrics CSV and JSON.
*Probe points:* the detector-first ordering (the from-scratch spray from the far end of the chain); Gap 102 — acquisition parameters not on the form, does the form say where they are; whether every noise term is in electrons with the unit shown; whether the FPA preset picker gets in his way when he wants custom.
*Pass:* every noise term visible individually with units, exported, and the scene he had to add is minimal and was named by the tool.

**J-2.2 Apply a preset, then override it** (pivot from J-2.1).
*Steps:* (1) Detector ▸ Choose part & apply… pick a preset. (2) Override read noise. (3) Details… — does it show his override or the datasheet? (4) Remove the preset. (5) Undo three times.
*Probe points:* P-08 — what survives preset removal (guide says explicit user values do); does the badge distinguish preset from user; does undo cross the preset boundary sanely.
*Pass:* the provenance of every detector row is correct on screen after each step.

**J-2.3 Dark current vs temperature** (pivot from J-2.2).
*Steps:* (1) Run Sweep over `detector.operating_temp` 60–120 K. (2) Cancel it halfway. (3) Run again; export.
*Probe points:* T-F cancel semantics; is a cancelled sweep's partial result shown, retained, or exportable, and does the menu gate agree.
*Pass:* the sweep gate and the export gate agree with what is on screen.

### P3 — Raj, Mission Planning Analyst (high)

**J-3.1 One scenario, yes or no.**
*Start:* Blank config (he has no file — the sensor he is given is a spec sheet, so he types it).
*Steps:* (1) Geometry: kinematics via circular orbit (V6) at 600 km; viewing via ground range (V3) 350 km; solar via site + time (S3): 35° N, day 166, 10:30. (2) Source: sub-pixel vehicle, 2 m², reflective, ρ 0.3; LOS rate via target velocity (K2) 40 km/h. (3) Atmosphere: visibility 23 km. (4) Sensor: the spec-sheet values in Optics and Detector. (5) Evaluate. (6) Read SNR and detection metrics.
*Probe points:* three families each entered by a non-default door in one session; the derived-angle readout updating; whether choosing K2 explains that it replaces the platform-only default; whether "sub-pixel + reflective" is coherent or trips the door guard; whether a detection threshold is a thing he can set or the tool leaves him to compare by eye.
*Pass:* a single evaluate with every geometry door honoured and the derived readout matching what he typed.

**J-3.2 Weather sensitivity** (pivot from J-3.1).
*Steps:* (1) Visibility 10 km. (2) Visibility 5 km. (3) Undo twice. (4) Sweep visibility 3–30 km.
*Probe points:* the `simple` model's knobs appear only when `simple` is selected — switch to another model and back (P-06) and check the values survive.
*Pass:* undo restores exactly; sweep runs over the atmosphere parameter.

**J-3.3 Same target, from an aircraft** (pivot from J-3.2).
*Steps:* (1) Kinematics: switch from orbit to direct ground speed. (2) Altitude 10 km. (3) Viewing: switch to off-boresight angle (V2) 30°. (4) Evaluate.
*Probe points:* P-12 and P-03 together — the orbit-derived ground speed group (`_GROUND_SPEED_GROUP`) must release when the mode changes; does switching mode withdraw the old door's value or leave it set so the family over-specifies; does the card tint clear.
*Pass:* mode switches never produce an over-specification the user did not author.

### P4 — Lisa, Detection Analyst (high) — the persona that most depends on the GUI

**J-4.1 Three sensors, one target, in one study.**
*Start:* Blank config.
*Steps:* (1) Build one complete configuration by forms only, using library items where the GUI offers them (background material, FPA preset, atmosphere family). (2) Edit ▸ Configurations…: add two more configurations. (3) Right-click aperture ▸ Configure across configurations… and give each its own value. (4) Evaluate; read the per-configuration metric columns. (5) Configure the FPA preset per configuration. (6) Un-configure aperture. (7) Export XLSX.
*Probe points:* T-E and P-11 — the moment a single-model session becomes a study; whether the configuration bar appears with a sensible name; whether un-configure restores the shared value or one of the three; Gap 103 boundary (element train is shared — does the GUI say so before she tries); whether the workbook has one sheet per configuration or one column.
*Pass:* the Performance table shows three columns that match what she configured; the export matches the table.

**J-4.2 Compare against a colleague's file** (pivot from J-4.1).
*Steps:* (1) Tools ▸ Compare Config Files… against a file she Saved As in step J-4.1. (2) Read the comparison table. (3) Export.
*Probe points:* the dialog operates on files, not the live study — is that clear; are units in the table.
*Pass:* she can tell which column is which.

**J-4.3 The 15 × 4 × 3 matrix** (pivot from J-4.2).
*Steps:* (1) Run ▸ Batch Run… (2) Read the scaffold.
*Probe points:* this is the point where the GUI hands a tool consumer a Python scaffold; the finding is what the scaffold assumes she knows and whether the scripting window explains how to run it.
*Pass:* recorded as a Planned or Declined disposition either way; the audit documents the gap between the persona and the surface.

### P5 — Tom, Optical Systems Engineer (high)

**J-5.1 MTF decomposition of a three-mirror telescope.**
*Start:* Blank config.
*Steps:* (1) Optics: aperture, obscuration, f/#; Transmission ▸ element train; add three mirrors with reflectance and (deliberately) an emissivity, expecting the Kirchhoff refusal. (2) Import Zemax Zernike… with a small file. (3) Minimal scene and detector. (4) Evaluate. (5) Optics ▸ MTF tab: every contributor; PSF + Pupil tab.
*Probe points:* the element editor's Kirchhoff message (rubric §2.5); the element table's bounded scroll box (CU-371 item 5); P-07 switching back to scalar transmission — does the element train survive hidden, and does the form say so.
*Pass:* every MTF contributor visible and named; the Kirchhoff refusal names the surface.

**J-5.2 Jitter tolerance sweep** (pivot from J-5.1).
*Steps:* (1) 2-D sweep: jitter × WFE. (2) Read; export.
*Probe points:* the 2-D result presentation; axis units.
*Pass:* the 2-D result is readable without the CSV.

**J-5.3 Measured MTF overlay** (pivot from J-5.2).
*Steps:* (1) Tools ▸ Compare Measured MTF… with a two-column CSV. (2) Then Solve for aperture such that MTF at Nyquist = 0.2.
*Probe points:* the CSV format the dialog expects — does it say; a solve on a spatial metric while the Spatial group is toggled off (P-14).
*Pass:* both dialogs state their input contract before failing on it.

### P6 — Dr. Chen, University Researcher (medium)

**J-6.1 Provenance of every number.**
*Start:* Blank config; set everything explicitly (no defaults).
*Steps:* (1) Use the Parameters dock only, no stage forms. (2) Evaluate. (3) Tools ▸ Inspector. (4) Explain Parameter on three derived values. (5) Export Resolved YAML and JSON result.
*Probe points:* the dock-only path (filter box, 200-plus rows, keyboard); *Changed only* correctness; whether the resolved YAML round-trips (T-D).
*Pass:* the resolved YAML re-opened gives an identical JSON result.

**J-6.2 Disable one effect at a time** (pivot from J-6.1).
*Steps:* (1) Performance ▸ Compute checkboxes off one group at a time. (2) Set jitter to zero, smear to zero, atmosphere to none. (3) Each time, read what disappeared.
*Probe points:* P-14 — cards for disabled groups: are they "n/a" with a reason or silently gone (CU-371 II-009).
*Pass:* every absent metric says why it is absent.

**J-6.3 Monte Carlo** (pivot from J-6.2).
*Steps:* (1) Set tolerances on three parameters. (2) Run ▸ Monte Carlo… (3) Read the scaffold.
*Probe points:* tolerance entry (display units, symmetric); whether the scaffold picked up exactly the three.
*Pass:* the scaffold names the three tolerances with the units he entered.

### P7 — Karen, Integration & Test Engineer (medium)

**J-7.1 Lab mode: blackbody, no atmosphere.**
*Start:* Blank config.
*Steps:* (1) Atmosphere: none / lab. (2) Source: blackbody 298 K filling the aperture. (3) Geometry: the shortest slant range the tool accepts. (4) As-built detector and readout. (5) Calibration: scheme, cal points. (6) Evaluate; NEDT.
*Probe points:* whether "no atmosphere" and "aperture-filling source" are reachable from the forms at all or require a range and an extended-scene trick; what the geometry family demands of a bench test.
*Pass:* NEDT with the full noise breakdown, and no geometry she had to invent.

**J-7.2 Close a 4 mK gap** (pivot from J-7.1).
*Steps:* (1) Solve for read noise such that NEDT = 22 mK. (2) Explain the result. (3) Export the parameter audit trail (Resolved YAML).
*Pass:* the audit trail shows the solved value with its provenance.

**J-7.3 Switch calibration scheme mid-session** (pivot from J-7.2).
*Steps:* (1) Change `calibration` scheme; change `cal_point_mode`. (2) Watch which rows appear and disappear. (3) Undo.
*Probe points:* P-10 — the mode-switched rows and whether the values under a hidden mode are withdrawn or retained and later over-specify (the CU-346 door).
*Pass:* no scheme switch produces an over-specification she did not author.

## 5. Cross-cutting tracks

Tracks are persona-free state-machine exercises. Each runs headless first, then the S1/S2 results are confirmed live.

### T-A From-scratch bootstrap
Blank config; enter a complete configuration in six different **orders** (geometry-first, optics-first, detector-first, source-first, performance-first, random). At every edit record: the rail message, whether it names a missing parameter, whether it repeats. Count messages per order. Probe: is there any surface that lists *what is still missing*? Does the modal ever appear during bootstrap (the guide says never)? Owner symptom 2.

### T-B Over-specification and recovery
For every consistency group and every mutually exclusive door (§3 pivot catalog P-01…P-10): (a) from a complete configuration, author the conflict — expect a door rejection; (b) from a blank configuration, author the same conflict — expect it to be accepted (§6 F-3), complete the configuration, then try to repair one edit at a time. Record every exit that works: Reset to Default, Undo, Reset to Defaults, mode selector, YAML. Score against the troubleshooting guide §6 claims. Owner symptom 1.

### T-C Undo, redo, unsaved guard
Twenty-one edits (one past the stack); undo through a mode switch, a preset apply, an element-train edit, a configuration-scope change, a sweep; redo after a new edit; the `*` and the guard on New / Open / Recent / Quit; Save then cancel.

### T-D YAML editor and file round trip
Edit Config (YAML): Apply a document with a bounds error, an unknown key, and a removed key; Revert; Apply a valid document and confirm the undo stack cleared as documented; Save, Open, and diff what survived (guide §3.2 says two things do not).

### T-E Study conversion
Single → study via Configurations…; configure, un-configure, delete a configuration, delete the displayed configuration, rename, reach the 13-configuration cap (CU-371 II-015 message); back to a single-model session if that is possible at all.

### T-F Sweep, solve, compare lifecycle
Sweep then edit (is the retained result marked stale?); cancel at 0 %, 50 %, 99 %; solve with an unreachable target; solve on a metric whose group is off; compare against a file that fails to resolve.

### T-G Export at every state
Every export action in every state: blank, incomplete, evaluated, stale, failed-after-success, study, after a cancelled sweep. Record the gate, the file, the units, and whether a stale result exports with a stale marker.

### T-H Window geometry
Window at 1280×720, 1024×640, and the smallest the layout allows; Parameters dock at default and at half width; right rail hidden; every stage tab grabbed at each size. CU-363 and CU-371 IV-031 are the known items; the audit records the rest.

### T-I Keyboard only
A full journey (J-1.1) without the mouse: Ctrl+1…0, F6/F7, Tab order through a form, Enter to commit, Escape to cancel, Ctrl+Z.

### T-J Discoverability and the eight not-wired actions
What a new user sees when Help is empty and Find Parameter, Validate Only, Preferences and Font Size do nothing; whether the disabled state explains itself.

### T-K Messages rail hygiene
Across J-1.1: do messages clear when their condition clears, do they duplicate on every re-evaluate, is the most recent on top, is there a way to clear, does the rail distinguish rejection from advisory from warning (guide §5 taxonomy).

### T-L Soak
Two hundred edits with evaluation on, twenty sweeps, forty dialog open/close cycles; memory and message count at the end; the CU-212 widget-lifetime threshold in a single live window.

### T-R Recovery via templates
The troubleshooting guide §6.3 claim: from a tangled J-3.3 session, start from a template and re-apply *Changed only*. Time it; record what the operator must remember.

### T-S Scripting window as an escape hatch
For every S1/S2 finding in T-B: can the scripting window repair the state, and does the main window notice.

### T-U Display units and theme mid-edit
Angles in Degrees toggled while an editor is open; a per-parameter unit changed then undone; theme toggled with the sweep dialog open.

### T-W Windows
Deferred unless the owner has a Windows machine available (§10). Rule 30 makes it review-blocking for new code; this audit only records whether any finding is platform-specific.

## 6. Seed findings — 2026-09-19 pre-charter probes

Reproduced headlessly through `ParameterEditorDialog._try_resolve`, the exact path the row editor's Enter key takes. Each is recorded as a Findings-Log line today and is promoted at audit close with the rest.

**F-1 (S1 candidate) — mode switch across a mutually exclusive door is unreachable one edit at a time.** Shipped MWIR example, target on the thermal door. Set `source.target.reflectance` = 0.5 → rejected ("mutually exclusive with temperature / emissivity"). Right-click Reset to Default on emissivity → still rejected, because `source.target.temperature` has a schema default of 300 K and the door guard counts a default as set. The exit is two resets in the right order, which no message names, and the form's own note says "set reflectance alone". Owner symptom 1.

**F-2 (S3) — blank-config evaluate reports a circular dependency.** `Sensor().evaluate()` raises `Circular dependency detected: parameters ['optics.aperture_diameter_m', 'optics.focal_length_m', 'optics.f_number'] could not be resolved after 10 passes. Check consistency groups for cycles` (`core/parameters.py:649`). The resolver's cycle detector fires before the required-parameter check, so the first thing a from-scratch user reads is a developer diagnostic. Every 200 ms debounce re-evaluate repeats it. Owner symptom 2.

**F-3 (S2) — the editor's differential guard admits over-specification on an incomplete configuration.** Blank config: aperture 0.3 m, focal length 1.2 m, then `optics.f_number` = 6 is **accepted** (`parameter_editor_dialog.py:1041-1059` treats every resolve failure on an incomplete config as pre-existing incompleteness and falls back to bounds-only checks). The same edit on a complete configuration is correctly refused. The conflict surfaces only when the configuration becomes complete, far from the edit that caused it. Compounds F-2.

## 7. Already tracked — excluded from new findings

Reproduced only to confirm, then cited, never re-minted: CU-363 (Detector form clipping at off-default widths), CU-371 (process language in GUI strings; `badge_display` n/a states; viewer pill clipping; bounded table scroll boxes), CU-362 (catalog staleness), Gap 85 (no mission-type-driven parameter relevance — the two-tier selector proposal is owner-pending and must not be redesigned here), Gap 98 (point-source workflow does not steer to intensity), Gap 102 (readout acquisition parameters have no form surface), Gap 103 (shared element train across configurations), Gap 79 (multi-config compare ergonomics), the eight not-wired menu actions (documented as such; T-J records only whether their disabled state explains itself).

## 8. Execution

| Phase | Work | Harness | Output |
|---|---|---|---|
| 0 | Owner ratifies §10; mint the three seed findings' Findings-Log lines (done 2026-09-19) | — | this plan → Active |
| 1 | Build the scratch driver; run T-A and T-B in full; write `Findings_Bootstrap_Recovery.md` | A | first findings document; owner symptoms characterized |
| 2 | Run J-1.x, J-2.x, J-3.x, J-4.x; write `Findings_Journeys_P1_P4.md` | A | |
| 3 | Live session 1: J-1.1 and J-4.1 natively, plus every S1/S2 from phases 1–2 | B | owner step reports appended to the phase-2 document |
| 4 | Run J-5.x, J-6.x, J-7.x and tracks T-C…T-K, T-R, T-S, T-U; write `Findings_Journeys_P5_P7.md` and `Findings_Tracks.md` | A | |
| 5 | Live session 2: T-H, T-I, and the phase-4 S1/S2 set | B | |
| 6 | T-L soak; `Recommendation.md`: every finding dispositioned CU'd / Planned / Declined, ordered by severity then by persona priority; family CUs where findings share a mechanism (Rule 21) | — | plan → Complete; findings immutable |

Each phase is one branch and one docs-only merge (docs-only gates). No `src/` change lands under this charter. Time: phases 1–2 and 4 are agent-hours; the live sessions are owner-scheduled.

## 9. Finding template

```
### F-NN — <one-line symptom>            Severity: S1 | S2 | S3 | S4
Persona / journey: J-x.y or track T-x
Steps (from Blank config):
  1. ...
Observed: <exact message text, screenshot figures/<track>/<step>.png>
Expected: <what the guide or Rule 15 says should happen>
Rubric misses: <§2.5 items 1–7 that fail>
Exit found: <Reset to Default | Undo | mode selector | YAML | scripting | none>
Native confirmation: <live session date | not attempted>
Related: <CU / Gap if any>
```

## 10. Owner decisions — ruled 2026-09-19

Rulings (owner delegated the calls; recorded here so they bind the later phases):

1. **Templates** — journeys start from Blank config only; mission-template cards are exercised in T-R alone.
2. **Live sessions** — two, scripted by the agent; session 1 takes J-1.1 and J-4.1 plus the S1/S2 queue from phase 1 (`Findings_Bootstrap_Recovery.md` §7).
3. **Windows** — no machine available; T-W is deferred and the audit records nothing platform-specific.
4. **Fix timing** — no fixes under the charter; S1 findings are minted as CUs at each phase merge so they can be scheduled before close, everything else at close.
5. **Seed findings** — kept as Findings-Log lines; promoted with their families at close (one family CU per mechanism, per `Findings_Bootstrap_Recovery.md` §6).

The questions as originally posed:

1. **Templates.** Confirm the ground rule: journeys start from Blank config only; mission-template cards are exercised in T-R alone. (Alternative: also allow a template as the starting point for the P3/P4 journeys, which matches how those personas would really start.)
2. **Live sessions.** Two sessions of roughly an hour each, scripted by the agent; confirm the two journeys chosen for session 1 (J-1.1, J-4.1) or name others.
3. **Windows.** Is a Windows machine available for T-W, or is it deferred?
4. **Fix timing.** Findings are dispositioned at close (Rule 28). If F-1 or another S1 should be fixed as soon as it is characterized rather than at close, say so; the live-review rule still gates the merge.
5. **Seed findings.** F-1…F-3 are Findings-Log lines today; at close they are promoted, likely as one family CU ("edit discipline on incomplete and mode-switching configurations"). Confirm or mint now.
