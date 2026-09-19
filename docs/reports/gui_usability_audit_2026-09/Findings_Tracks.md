# GUI Usability Audit — Findings: Cross-Cutting Tracks (T-C, T-D, T-F, T-G, T-J, T-K, T-U, T-H)

**Status:** Complete (point-in-time record — immutable per Rule 24/28; corrections are new documents)
**Date:** 2026-09-19
**Phase:** 4 of `Audit_Plan.md` §8 (tracks half)
**Harness:** A. Not run under this charter: T-E beyond what J-4.1 covered (see phase 2), T-I keyboard-only, T-L soak, T-R template recovery, T-S scripting escape hatch — deferred to close (§4).
**Baseline:** `main` at `924f6039`. No source was changed.
**Numbering:** continues from `Findings_Journeys_P1_P4.md` (F-17…F-31).

---

## 1. Track outcomes

| Track | Outcome |
|---|---|
| T-C undo / unsaved guard | guard correct in all three answers (Cancel keeps, Save-then-cancelled keeps, Discard returns to welcome); undo depth 20 as documented, bottom reached silently |
| T-D YAML editor | **S1**: an out-of-bounds value is applied to the live sensor and the editor can then no longer be opened |
| T-F sweep / solve lifecycle | retained sweep is not marked stale by a later edit; solve list follows the metric groups correctly |
| T-G export gates by state | gates correct; an export after a failed re-evaluation writes the previous result without saying so |
| T-J not-wired actions | eight disabled actions carry no explanation |
| T-K Messages rail | clean: no duplication across re-evaluations, error clears on fix, dialog rejections stay inline |
| T-U units and theme | entry in the display unit is symmetric; the global angle toggle does not reach rows edited through the dialog |
| T-H window geometry | grabs at 1280×720, 1024×640 and a 520 px dock for live session 2 |

## 2. Findings

### F-32 — The YAML editor's Apply admits an out-of-bounds value, reports it as "incomplete", and then cannot be reopened — Severity: **S1**
Track T-D (two independent runs).
Steps: (1) Complete configuration. (2) Right rail ▸ Edit Config (YAML). (3) Change `aperture_diameter_m: 0.3` to `-1.0`. (4) Apply.
Observed: the dialog closes; the live sensor's input is now `-1.0`; the status bar reads *Configuration incomplete — set required parameters, then Evaluate (F5)…*; the Messages rail is clean; every dock row reads `—` (F-01); Edit ▸ Undo is disabled (a document swap clears the history, as documented). Edit Config (YAML) again: the handler raises `ParameterBoundsError: Parameter 'optics.aperture_diameter_m' = -1.0 out of bounds [0.0001, 20.0]` from `serialize_document → Sensor.to_yaml → _ensure_resolved` — uncaught, so the editor never opens. Evaluate then shows the bounds error as a modal.
Expected: Apply validates on a clone like every other commit path and refuses with the inline what/why/action; or, failing that, the status names the bad value, and the editor opens on an unresolvable document so the operator can fix it there.
Exit: find the row that shows `—`, guess that it is the one, and set a legal value; or File ▸ Open. Folded into **CU-372** as a checklist item (same clone-validate seam, document path).

### F-33 — The undo stack bottom is reached silently — Severity: **S4**
Track T-C. Twenty-one edits, twenty-one undos: the first edit survives (`0.001 s user-set`), Undo greys out, nothing says the history is exhausted. Documented depth; the cue is the disabled menu item only.

### F-34 — A retained sweep result is not marked stale by a later edit — Severity: **S3**
Track T-F. Sweep, then edit `detector.qe_value`: File ▸ Export Sweep CSV stays enabled and the status bar shows the new evaluation; the sweep that will be exported was run on the pre-edit clone and nothing says so. Sarah exports a sweep that disagrees with the inputs on screen.

### F-35 — After a failed re-evaluation, Export Metrics CSV writes the previous result with no marker — Severity: **S3**
Track T-G. Success, then an edit that fails (geometry over-specification): the window shows the previous result *stale*, the metrics export is enabled and writes it (SNR 316.19) with no stale flag, no timestamp of the run, and no inputs snapshot. The file cannot be told apart from a current one.

### F-36 — The eight not-wired actions explain nothing — Severity: **S4**
Track T-J. Find Parameter, Validate Only, Preferences…, Font Size ±, Documentation, Example Configs, About RADIANT: disabled, empty status tip, tooltip equal to the name. The guide says why they are disabled; the menu does not.

### F-37 — View ▸ Angles in Degrees does not change a row that was edited through the dialog — Severity: **S3**
Track T-U. `path_zenith_rad` typed as 30 with degrees on → row `30 deg` (0.5236 rad canonical, correct). Toggle degrees off → row still `30 deg`. Type 0.5 → stored as 0.5 **deg** (0.0087 rad). Toggle back on → `0.5 deg`. The dialog's chosen unit becomes a sticky per-row display unit (documented) that silently outranks the global toggle, so the toggle appears broken for exactly the rows the operator has touched, and a value typed "in radians" lands in degrees.

### F-38 — At 1024×640 the stage strip scrolls, the Compute row clips, and rail messages clamp — Severity: **S3** (for live session 2)
Track T-H; figure `figures/small_window_performance.png`. Chips 1–2 scroll off the strip (horizontal scrollbar), the metric-group checkboxes show two of five, the metrics table needs a horizontal scroll, each rail message is cut at three lines with no expander visible. Related: CU-363, F-14.

## 3. Observations that are not findings

- **The unsaved-edits guard is right** in all three branches, including Save followed by a cancelled Save As, which keeps the configuration and the dirty marker.
- **Rail hygiene is right**: three re-evaluations leave three warnings, not nine; the error clears the moment the fix lands; a dialog rejection stays in the dialog.
- **Display-unit entry is symmetric**: what you type in the row's unit is what the row shows, and the canonical value is right.
- **Export gates match the documented table** in every state tried (blank, incomplete, evaluated, stale, failed-after-success).
- **Dark theme, dock and rail toggles** re-render cleanly offscreen; native confirmation in live session 2.

## 4. Deferred to close

T-I (keyboard only), T-L (soak), T-R (template recovery), T-S (scripting as escape hatch) were not run under this charter's phase 4: T-I and T-R are better judged natively and belong to live session 2; T-L and T-S are queued for phase 6 with the Recommendation.
