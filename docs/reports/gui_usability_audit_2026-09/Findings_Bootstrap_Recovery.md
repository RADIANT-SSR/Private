# GUI Usability Audit — Findings: Bootstrap and Recovery (tracks T-A, T-B)

**Status:** Complete (point-in-time record — immutable per Rule 24/28; corrections are new documents)
**Date:** 2026-09-19
**Phase:** 1 of `Audit_Plan.md` §8
**Harness:** A (headless scripted drive, §2.1). Native confirmation of the S1/S2 items is scheduled for live session 1.
**Baseline:** `main` at `d5905846`. No source was changed.

---

## 1. What was run

Every run starts at the welcome screen's **Blank config** card. Parameters are entered through the two real entry paths:

- **dialog** — the `ParameterEditorDialog`, which is what a stage form's value button and a double-click on a dock row's name column open;
- **inline** — the in-place delegate editor in the Parameters dock's Value column.

The minimal complete configuration is the eleven parameters the from-scratch test uses (`gui/tests/test_from_scratch.py`): sensor altitude, target temperature and emissivity, aperture and f-number, filter band edges and integration time, pixel pitch x/y and QE.

**T-A** entered those eleven in six orders (geometry-first, optics-first, detector-first, source-first, spectral-first, random) through the dialog path, and one order through the inline path. **T-B** built the complete configuration (optics-first, the quiet order) and then exercised ten doors and groups: the f-number consistency group (two ways), the thermal↔reflective target door, a second viewing-geometry door, an over-specified group authored on a blank config, the scene-type declaration, the atmosphere model selector, undo across a rejection, the readout architecture, the calibration scheme and cal-point mode, and the transmission input mode. Every step's status bar, Messages rail, modal text, chip states, dock row text and provenance were logged; every step was grabbed.

## 2. T-A result table

| Path | Order | Modals before success | Rejected edits | Reached a result |
|---|---|---|---|---|
| dialog | optics-first | 0 | 0 | yes |
| dialog | geometry-first | 3 | 0 | yes |
| dialog | source-first | 3 | 0 | yes |
| dialog | random | 5 | 0 | yes |
| dialog | detector-first | 6 | 0 | yes |
| dialog | spectral-first | 6 | 0 | yes |
| inline | geometry-first | 12 | 11 of 11 | **no** |

The modal count on the dialog path equals the number of accepted edits made **before** `optics.aperture_diameter_m` is set. Once the aperture exists, every further missing parameter is reported through the advisory path (status bar names it, owning chip goes red, no modal) and the eleven-parameter journey completes in as many evaluations as there are parameters left.

## 3. Findings

Severity per `Audit_Plan.md` §2.4; rubric items per §2.5. "Exit" is the in-GUI recovery an operator can find.

### F-01 — On an unresolved configuration the Parameters dock shows every value as unset, including the ones just entered — Severity: **S1**
Track T-A, dialog path, any order; figures `figures/bootstrap_dock_blank.png`, `figures/bootstrap_form_vs_dock.png`.
Steps: (1) Blank config. (2) Set `geometry.sensor_altitude_m` = 500000 through the editor dialog (accepted). (3) Look at the dock row.
Observed: the row reads `—` with an empty Source cell; so do the temperature, emissivity and aperture rows after they are accepted (log rows 2–6). *Changed only* lists nothing. The Value column collapses to a few pixels. The Geometry **form**, by contrast, shows `500000 m` for the same parameter. Rows only start showing values and provenance once the configuration resolves (step 12).
Expected: an accepted value is shown where it was accepted, with its provenance, whether or not the whole configuration resolves yet (the from-scratch contract of 2026-07-17 accepts the value; the dock should show it).
Rubric misses: n/a (a display, not a message) — but the tool misrepresents its own state, which is the S1 criterion.
Exit: none needed to proceed, but the operator cannot see what they have entered until the configuration is complete; a mistyped value is invisible until then.
Mechanism: `ParameterPanel.populate` reads through the guarded resolved-value accessor, which yields "unset" for every row on an unresolvable sensor (the CU-105/CU-140 guard); the input value and its provenance are available without resolving.

### F-02 — The inline dock editor rejects every edit on a blank configuration — Severity: **S1**
Track T-A, inline path.
Steps: (1) Blank config. (2) Double-click the Value cell of `geometry.sensor_altitude_m`, type 500000, Enter.
Observed: modal *Parameter Rejected — Cannot set "geometry.sensor_altitude_m"* whose What is `Circular dependency detected: parameters ['optics.aperture_diameter_m', 'optics.focal_length_m', 'optics.f_number'] could not be resolved after 10 passes…`; the row reverts. All eleven parameters, in any order, are rejected the same way, so nothing can be entered through this path at all. The editor dialog accepts the same values.
Expected: the two entry paths reject identically (the target-spec guard was shared between them for exactly this reason, CU-244); the dialog's differential acceptance on an incomplete configuration is missing from `ParameterPanel._commit_edit`.
Rubric misses: 1 (names the wrong parameter — the edited one, not the missing ones), 2, 3, 5, 7.
Exit: use the dialog (double-click the *name* column, or a stage form). Nothing tells the operator this.

### F-03 — *Reset to Default* on a consistency-group member reports a rejection but applies the reset, leaves the row showing the old value, and cannot be undone — Severity: **S1**
Track T-B b1b.
Steps: (1) Complete configuration with aperture and f-number set (focal length derived). (2) Right-click `optics.f_number` ▸ Reset to Default.
Observed: modal *Parameter Rejected — Cannot set "optics.f_number" — Required parameter 'optics.focal_length_m' is not set*. The row still shows `4  user-set`. But `f_number` is gone from the sensor's inputs; no undo step was recorded (Edit ▸ Undo disabled); no re-evaluation was scheduled; the title's dirty marker did not change. The next Evaluate reports the configuration incomplete. Repopulating the tree shows `—`.
Expected: either the reset is refused and nothing changes, or it applies and the display, the undo stack and the stale state all say so.
Mechanism: `_reset_to_default` calls `sensor.reset` on the **live** sensor and only then resolves; the resolve failure is rendered as a rejection, but the reset is not rolled back and `parameterEdited` is not emitted.
Rubric misses: 1 (says "cannot set" about a withdrawal), 3 (the action it implies — set focal length — is right, but the modal says the reset failed), 6.
Exit: re-enter the value by hand. Undo does not restore it.

### F-04 — A derived group member is read-only with no way to take it over — Severity: **S2**
Track T-B b1.
Steps: (1) Aperture 0.3 m and f-number 4 set; focal length shows `⚡ 1.2 m derived`. (2) Open the editor on `optics.focal_length_m`, type 1.8, Apply.
Observed: the dialog opens read-only ("derived from a consistency group — read-only"); Apply is a silent no-op; the row stays derived. The only route to "specify focal length instead of f-number" is Reset to Default on the f-number row — which is F-03 — and then setting focal length. Going back (f-number 4 with focal length now set) is the same dance in reverse; typing the value the group already implies (6) is also a no-op rather than a promotion to user-set.
Expected: an operator who types into a derived member is choosing that member as the input; the dialog should offer "set this and derive `<other>`" or say which row to reset.
Rubric misses: 3 (the read-only note names no action).
Exit: undocumented two-step via the dock's context menu, through F-03.

### F-05 — A second viewing-geometry door is accepted at the door, then rejected on every re-evaluation; the mode card auto-selects the new door and grays the field that must be withdrawn — Severity: **S2**
Track T-B b3; figure `figures/geometry_door_conflict.png`.
Steps: (1) Complete configuration; Geometry workspace. (2) `geometry.path_zenith_rad` = 0.3 (V1). (3) `geometry.ground_range_m` = 300000 (V3) — accepted. (4) The debounced evaluation runs.
Observed: modal *Parameter Rejected — Cannot set "evaluate"* with a good What/Why/Action ("Over-specified viewing geometry… Set exactly one of these parameters (the others derive from it), or make the redundant values consistent"); the rail carries the same; the window jumps to Geometry and tints the Viewing family. The card's selector now reads **Ground range (V3)** and `path_zenith_rad` is grayed and non-editable at `0.3 deg` — the very value that must go. Choosing V3 on the selector changes nothing (the V1 value stays user-set, the tint stays). Every subsequent edit anywhere re-raises the modal. The exit is Reset to Default on `path_zenith_rad` in the dock; the card offers no way to clear a grayed field.
Expected: the card's selector is the mode affordance the guide describes; selecting a mode should withdraw (or offer to withdraw) the other doors' explicit values, or the grayed conflicting field should be clearable in place.
Rubric misses: 4 (the locator tints the family but grays the field to act on), 7 (modal per re-evaluate).
Exit: dock right-click on a field the form shows as inactive.

### F-06 — An over-constrained group authored on a blank configuration is admitted, surfaces only when the configuration completes, then raises a modal on every subsequent edit and blames the wrong parameter — Severity: **S2**
Track T-B b4 (seed finding F-3).
Steps: (1) Blank config. (2) Aperture 0.3, focal length 1.2, then f-number 6 — all accepted (the dialog's differential guard treats the resolve failure as pre-existing incompleteness and falls back to bounds-only checks). (3) Enter the remaining eight parameters.
Observed: from the fourth parameter on, every accepted edit re-raises *Cannot set "evaluate" — Consistency group 'fnumber' is over-constrained… User-specified 'optics.aperture_diameter_m' = 0.3, Computed … = 0.2 … Fix: either remove 'optics.aperture_diameter_m' from inputs and let it be derived, or correct the inconsistent value.* — ten modals for eight edits, each naming the aperture (the first member set) rather than the f-number that was typed last. Setting f-number to 4 repairs it.
Rubric misses: 1 (names the wrong parameter), 5, 6 (repeats on every edit).
Exit: guess which member to correct.

### F-07 — Door switches need N manual resets in the right order and give no one-step route — Severity: **S3**
Track T-B b2, b5, b9 (seed finding F-1, **corrected**: the message does name both parameters to remove; the friction is the multi-reset choreography, not the message).
Steps (thermal → reflective): (1) Complete configuration with temperature and emissivity set. (2) Set `source.target.reflectance` = 0.5 → rejected inline in the dialog with a clear What/Why/Action ("Remove source.target.temperature and .emissivity when using reflectance/albedo…"). (3) Reset emissivity → still rejected. (4) Reset temperature → accepted. Going back is the mirror: temperature is rejected until reflectance is reset.
Same shape: declaring `scene_type = point_source` then entering a point intensity is rejected until temperature is reset (b5); flipping `calibration.cal_point_mode` to `flux_fraction` with cal temperatures set is rejected on every re-evaluation until each temperature is unset, and the message names only `cal_temp_low_K` (b9).
Expected: a mode switch is one operator intention; the tab or selector that represents the new mode should offer to withdraw the old door's values, or the rejection should offer that as an action.
Rubric misses: 3 partially (the action is right but is two or three separate dock operations the message does not sequence); b9 misses 1 (names one of the two temperatures).
Exit: dock right-click Reset, N times.

### F-08 — Transmission input-mode switches raise a modal per edit whose text is Python API instructions — Severity: **S2**
Track T-B b10.
Steps: (1) Complete configuration. (2) `optics.transmission_input_mode` = `key_elements` (or `spectral_file`).
Observed: *Cannot set "evaluate" — resolve_transmission: KEY_ELEMENTS mode requires at least one OpticalElement in key_elements (residual_transmission optional). Inject pre-chain via stage_outputs['optics_config']['key_elements'] — e.g. Sensor.evaluate(extra_stage_outputs={'optics_config': {'key_elements': (elem1, elem2)}}).* The spectral-file variant ends "(Rule 6: stages do not read files)". The modal repeats on every re-evaluation. Nothing points at the Optics ▸ Transmission tab, which is where an operator adds elements.
Rubric misses: 2, 3, 5, 6, 7.
Exit: switch the mode back, or find the Transmission tab unaided.

### F-09 — Mid-switch states are handled two different ways — Severity: **S3**
Tracks T-B b8, b9, b10, b3, b4.
Readout architecture (`digital_counting` with no packet) and calibration scheme (`two_point` with no temperatures) get the **advisory** treatment: no modal, only the owning chip goes red, the status bar names the parameter to set. Calibration cal-point mode, transmission mode, a geometry door conflict and a consistency-group conflict get the **modal** treatment on every re-evaluation, with the whole chip strip red and the title *Parameter Rejected — Cannot set "evaluate"*. The advisory pattern is the right one and is already in the code (CU-322 routing by exception type); the other four states are not routed through it.
Rubric misses: 5, 6, 7 for the modal cases.

### F-10 — The status bar misroutes a file-mode atmosphere failure as a library-coverage refusal — Severity: **S3**
Track T-B b6.
Steps: (1) Complete configuration. (2) `atmosphere.model` = `tabulated` with no files set.
Observed: the rail says, correctly, *model='tabulated' requires atmosphere.tabulated_transmittance_file and atmosphere.tabulated_path_radiance_file to be set*; the status bar says *The atmosphere library does not cover this scene — see Messages*. The advisory routing keys on the exception type, which the tabulated-model loader shares with the coverage refusal. Switching back to `simple` keeps the visibility the operator had set (correct).
Rubric misses: 1, 2 (status bar).

### F-11 — The Messages rail lists the error below the warnings — Severity: **S3**
Figure `figures/geometry_door_conflict.png`.
On the minimal configuration every successful evaluation carries three saturation warnings (full well, ADC, pixel), each several lines long. When an evaluation then fails, the error is the fourth item, below the fold of the rail at 900 px window height; the only above-the-fold cue is the "3 warnings, 1 error" count. The failure the operator must act on is the least visible item.

### F-12 — Product messages carry scripting and configuration-set language in a single-model session — Severity: **S3**
Tracks T-A, T-B (every required-parameter advisory and every evaluate-failure modal).
The required-parameter advisory ends `Set it via: params.set('optics.focal_length_m', value)`. The evaluate-failure modal on a fresh Blank config reads `Configuration 'Configuration 1' failed to evaluate: configuration 'Configuration 1' does not resolve … Action: Fix the parameters of configuration 'Configuration 1' — configured values are [], everything else is shared on the base.` — the configuration-set wrapper's wording, in a session that has never had a second configuration. The modal title for every evaluation failure is *Parameter Rejected — Cannot set "evaluate"*.
Rubric misses: 7, and 1 for the modal title (nothing named "evaluate" was set).
Related: CU-371 (process language family) — this is the same class, from different strings.

### F-13 — On a blank configuration the first evaluation failure is a developer diagnostic, and it is a modal — Severity: **S3**
Track T-A (seed finding F-2).
Every accepted edit on a Blank config schedules a full evaluation; until the aperture is set the failure is `Circular dependency detected … Check consistency groups for cycles (A derived from B, B derived from A)` from the resolver's cycle detector (`core/parameters.py:649`), which fires before the required-parameter check. It is routed to the modal (it is not a `RequiredParameterError`), so each of those edits costs a modal. Once the aperture exists, the required-parameter advisory takes over and the rest of the bootstrap is quiet. The status-bar guidance on Blank config ("edit parameters, then Evaluate") does not mention that the aperture unlocks the quiet path.
Rubric misses: 2, 3, 5, 7.

### F-14 — Parameter names in the dock are elided to unreadability at the default dock width — Severity: **S3**
Figure `figures/geometry_door_conflict.png` (left column).
At the default dock width in a 1400×900 window, once values are present the name column shows `sens…de_m`, `targ…ge_m`, `grou…m_s`, `targe…h_rad` — most rows cannot be told apart, and the eight `target.shape.*` rows are indistinguishable. The resolved sizing CU made the Value and Source columns content-sized so the name column takes the remainder; at this width the remainder is not enough. Related: CU-363 (form clipping at off-default widths) is the same family from the other side.

### F-15 — On a blank configuration the mode cards default to doors the documentation does not call the default, and show `—` for schema defaults — Severity: **S3**
Figure `figures/bootstrap_form_vs_dock.png`.
With nothing set, the Viewing selector reads **Off-boresight angle (V2)** and Solar reads **Solar elevation (S2)**, so `path_zenith_rad` (the documented default door, V1) is grayed out of the box; every field including defaulted ones (`target_altitude_m` = 0, `solar_illumination` = day) shows `—`. The operator who follows the guide's default door has to change a selector first, and sees no defaults to anchor on.

### F-16 — Switching the readout architecture back discards the packet the operator entered — Severity: **S4**
Track T-B b8. `analog_well → digital_counting`, set `count_packet_e` = 100, back to `analog_well`: the packet row is back to `0 e- default`. The switch clears inputs the new selection rejects (the Gap 117 rule) — correct for evaluation, but a round trip loses work with no notice.

## 4. Observations that are not findings

- **The dialog path's differential acceptance works as designed** and is what makes from-scratch entry possible at all; the fix for F-02 is to share it, not to change it.
- **The geometry over-specification message is the best message in the set**: what, why, a doable action, and the locator jumps to the right screen.
- **The advisory pattern (readout, calibration scheme, required parameters) is the right pattern** — quiet, chip-local, status bar names the fix. F-09 asks for it to be applied uniformly.
- **Undo after a rejection is correct**: a rejected edit pushes nothing; Undo reverts the last accepted edit; Redo restores it.
- **Visibility survives an atmosphere-model round trip** (`simple → interpolated → tabulated → simple`).
- **The minimal from-scratch configuration saturates** (well fill 11×): the first successful result a novice sees carries a saturation banner and three warnings. Not a GUI defect, but the welcome-screen Blank card's hint ("start from schema defaults") leads there.
- Declaring `scene_type = point_source` with a thermal pair set evaluates as `extended` with a warning: Gap 98, already tracked.

## 5. Seed-finding dispositions from `Audit_Plan.md` §6

- **F-1 → F-07**, severity corrected from the S1 candidate to S3: the rejection text names both parameters; the irritation is the reset choreography and the absence of a mode-level switch.
- **F-2 → F-13** (S3) as characterized.
- **F-3 → F-06** (S2), with the added observation that the late-surfacing error blames the first-set member.

## 6. Proposed dispositions (for `Recommendation.md` at close; the S1 family is minted as CU-372)

**CU-372** (minted 2026-09-19 at this phase merge) is the family CU for the edit-discipline seam — F-01, F-02, F-03, F-04, F-06 share the clone-validate / resolve-guard mechanism in `parameter_panel.py` and `parameter_editor_dialog.py` and should be fixed as one design. One family CU for failure routing — F-09, F-10, F-12, F-13 are all `_on_eval_failed` routing and string questions. F-05 and F-07 are one design question (does a mode selector withdraw the other doors?) and belong with the Gap 85 mission-type decision rather than ahead of it. F-08 is a string fix plus a pointer to the Transmission tab. F-11, F-14, F-15 are layout and default questions for live session 1. F-16 is a Findings-Log line.

## 7. Native confirmation queue for live session 1

F-01, F-02, F-03 (S1) and F-04, F-05, F-06, F-08 (S2), in that order, each from Blank config by the steps above.
