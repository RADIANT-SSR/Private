# GUI Usability Audit — Findings: Persona Journeys P1–P4 (Sarah, Mike, Raj, Lisa)

**Status:** Complete (point-in-time record — immutable per Rule 24/28; corrections are new documents)
**Date:** 2026-09-19
**Phase:** 2 of `Audit_Plan.md` §8
**Harness:** A (headless scripted drive). Sweeps, solves, the configuration manager, presets, comparison and the script scaffolds were driven through the window's own menu actions with the modal loop replaced; file dialogs answered from the driver; every static message box intercepted and logged.
**Baseline:** `main` at `1f32d7e2`. No source was changed.
**Numbering:** continues from `Findings_Bootstrap_Recovery.md` (F-01…F-16).

---

## 1. Journey outcomes

| Journey | Outcome | Findings raised |
|---|---|---|
| J-1.1 Sarah — aperture trade from nothing | reached two exports; the trade is meaningless (flat SNR) and nothing in the sweep or the CSV says why | F-17, F-18, F-30, F-31 |
| J-1.2 Sarah — jitter limit by solve | **blocked**: NIIRS is not offered as a solve target; the dialog's default target is `adc_margin_dB` | F-19, F-20 |
| J-1.3 Sarah — same trade, LWIR | reached Save As; one modal on the way, blaming emissivity | F-21 |
| J-2.1 Mike — detector first | reached the noise budget and exports; twelve modals to get there | F-29 (quantifies F-13) |
| J-2.2 Mike — preset then override | clean; the preset card is honest ("10 applied, 2 kept (explicit wins)") | — |
| J-2.3 Mike — temperature sweep, cancel | clean; cancel is honest ("Cancelled at 4/8. No partial results") and the export gate agrees | — |
| J-3.1 Raj — one scenario, three non-default doors | clean once one over-specification of my own was removed; the derived readout names every mode | F-25 |
| J-3.2 Raj — weather sensitivity | reached the sweep; the "no" answer is a vanished row | F-27 |
| J-3.3 Raj — same target from an aircraft | reached a result after one reset in the dock; the pivot passes through a grazing geometry and a door conflict | F-05 (recurs), F-28 |
| J-4.1 Lisa — three sensors in one study | study built, columns correct on screen; the workbook export carries one unlabeled configuration | F-22 |
| J-4.2 Lisa — compare against her saved file | **blocked** for a study file; works for a plain config | F-23 |
| J-4.3 Lisa — the matrix | handed a Python scaffold that starts from an empty config | F-24 |

## 2. Findings

### F-17 — Sweep CSV (and the workbook's Sweep sheet) has bare column names, numpy literals in cells, and float-noise axis values — Severity: **S2**
J-1.1 step 21, J-2.3 step 34.
Observed header: `optics.aperture_diameter_m,adc_margin_dB,alias_fraction_at_nyquist,…` — no units, no descriptions, all 33 metric keys. Twelve cells per file contain the literal text `np.float64(1.9949069310951775e-05)` (the FWHM columns). The axis column reads `0.32999999999999996`, `0.42000000000000004`. The metrics CSV from the same session has `name,value,unit,description`, so the two exports disagree on the units rule (product principle 5, "units on everything").
Expected: every column carries its unit; cells are numbers; the axis is the value the operator typed.
Exit: post-process in Excel.

### F-18 — A sweep or solve over a clipped configuration reports success with a flat metric and no saturation notice — Severity: **S3**
J-1.1 step 19, J-1.2 step 26.
Sarah's from-scratch MWIR configuration saturates the default 1e5 e⁻ well (fill 7.9–11×). The sweep over aperture 0.15–0.60 m returns SNR = 316.19 at every point with status *Done — 6 points*; nothing in the dialog, the retained result or the CSV says the metric is clipped. The solve for jitter reports *snr does not reach the target 150 inside the bracket [0, 50] — snr(0) = 316.187, snr(50) = 316.187. Widen or shift the bounds* — advice that cannot help. The main window's saturation banner is the only cue, and the sweep runs on a clone. Lisa's study (J-4.1) shows three identical SNR columns for three apertures for a different reason (fixed f-number), with no per-column indicator of either cause.
Rubric misses: 2, 3 (the solve message).

### F-19 — The solve dialog's default target is the alphabetically first metric, every metric key is offered, and NIIRS is absent without a reason — Severity: **S3**
J-1.2 steps 25–26.
The metric list is `sorted(last_result.metrics)`, so the dialog opens on `adc_margin_dB`; `sampling_regime_code` and `niirs_extrapolated` (a 0/1 flag) are offered as targets. NIIRS itself is missing because the run refused it (GSD 211 inch and SNR 316 are outside the GIQE-5 envelope; `allow_extrapolated` would report it), but the dialog does not say so — the reason lives in `stage_outputs["performance"]["niirs_result"]`, the CU-371 II-009 seam. Sarah's journey ("how much jitter before NIIRS drops below 5") cannot be run from this dialog.
Rubric misses: 3, 5.

### F-20 — Undo of a first-time set writes the schema default back as a user-set value — Severity: **S2**
J-1.2 step 28.
`platform.jitter_rms_urad` set to 5 (row: `5 µrad user-set`), then Edit ▸ Undo: the row reads `0 µrad user-set`. The undo command restores the previous *value* as an explicit input instead of withdrawing the edit, so provenance now lies: *Changed only* lists jitter, a later preset or reset treats it as explicit ("explicit wins"), and a saved file carries it. Compare J-3.2, where undoing an edit to a value that was already user-set is correct.
Expected: undo of a set on a default-provenance row returns the row to default provenance.
Exit: Reset to Default on the row (which the operator has no reason to think is needed).

### F-21 — Widening a band upward passes through a state that fails with an internal-grid message blaming emissivity — Severity: **S3**
J-1.3 step 29.
Setting `filter_min_um` = 8 while `filter_max_um` is still 5 is accepted at the door; the re-evaluation raises the modal *Cannot set "evaluate" — source.target.emissivity: wavelength_um must be strictly ascending*. Every upward band change is two edits and always visits this state. The right message is "filter_min_um (8 µm) is above filter_max_um (5 µm)".
Rubric misses: 1, 2, 3, 7.

### F-22 — The workbook export of a study contains one unlabeled configuration — Severity: **S2**
J-4.1 step 19; figure `figures/study_columns.png` shows the on-screen columns the export loses.
The XLSX has sheets `Config` (219 rows, columns `parameter, value, unit`) and `Metrics` (34 rows, `name, value, unit, description`): the displayed configuration's resolved values and metrics only. No sheet, column or cell names *Configuration 1*, *Sensor B* or *Sensor C*; the Performance workspace shows all three. The persona whose deliverable is a matrix for a briefing gets one sensor and cannot tell which. Also: the `Config` sheet's unit column holds the string `None` for unitless and enum parameters (S4).
Expected: one column per configuration, or one sheet per configuration, named as on screen.

### F-23 — Compare Config Files refuses the study file the operator just saved, with a developer action — Severity: **S3**
J-4.2 (direct probe after the scripted run stalled on this path).
Against a plain config the dialog works and reads well: *33 metrics × 2 configs (Δ vs current; ✓ = best)*. Against the study saved two steps earlier by File ▸ Save As, the status reads *Config load failed — ConfigError in …/j42_study.yaml: Config carries structured section(s) 'configurations', which this loader does not attach. This config file is a configuration set (ADR-0010) — load it with ConfigurationSet.load(path)…*. File ▸ Open reads both kinds with one reader; this dialog does not, and says so in API terms.
Rubric misses: 2, 3, 7.

### F-24 — The Batch Run scaffold starts from an empty configuration, not the one on screen — Severity: **S2**
J-4.3.
Run ▸ Batch Run… opens the scripting window with a `BatchRunner` skeleton whose first line is `base = {}  # or a nested config dict; cells start from Sensor.from_dict(base)`. The console binds `sensor` to the displayed configuration, and the Monte Carlo scaffold uses it (`mc = sensor.monte_carlo(...)`), but the batch scaffold does not — the tool consumer this surface exists for is asked to reconstruct her sensor as a dict. The Monte Carlo scaffold with no tolerances set is a good contrast: it says what to do and where ("or use the Tolerance section in any parameter editor dialog").
Expected: `base = sensor.to_dict()` (or the equivalent) so the axes vary the configuration she built.

### F-25 — The site-and-time solar mode offers LTAN and local solar time as two editable fields of one mode, and entering both is an over-specification — Severity: **S3**
J-3.1 (first run, step 16).
The guide's mode table lists S3 as "latitude, day of year, local solar time, LTAN"; the form shows both fields editable. Entering both raises *Both geometry.ltan_h and geometry.local_solar_time_h are set — they are mutually exclusive… Set exactly one* on every re-evaluation, with a modal each time, until one is reset. The message is good; the form and the guide invite the mistake.
Rubric misses: 5, 6.

### F-26 — On a blank configuration every family card opens on a non-default door — Severity: **S3**
J-3.1 step 1 (extends F-15 to all four families).
Viewing **V2** (off-boresight), Solar **S2** (elevation), Kinematics **direct**, Line-of-sight rate **K1** (direct LOS rate). The documented defaults are V1, S1, direct and K0 (platform-only, derived). An operator who wants the default door must change two selectors before entering anything, and K1 presents a rate field the guide says is normally derived.

### F-27 — "Not detectable" is a row that disappears — Severity: **S3**
J-3.2 step 25.
At 23 km and 10 km visibility the metric set carries `detection_range_m`; at 5 km (SNR 5.8 below the threshold of 6) the key is simply absent. Raj's pass/fail is the absence of a row in a 33-row table, with no "below threshold" reading, no traffic light, and the threshold he set (`performance.detection_snr_threshold`) not echoed anywhere near the result.

### F-28 — The platform pivot passes through a grazing geometry whose refusal cites an ADR — Severity: **S3**
J-3.3 step 31.
Lowering the sensor from 600 km to 10 km while the ground-range door still holds 350 km produces *horizon guard: near-horizontal path rejected — path leaves its lower endpoint (0.0 m MSL) at zenith 89.9389°… inside the ±0.5° hard horizon guard | Why … v1.x has no refraction model, so any number returned here would be quietly wrong (ADR-0011 decision 6) | Action: Move the path more than 2° off the horizontal…*. The what/why/action is sound; "v1.x" and "ADR-0011 decision 6" are process language (CU-371 class), and the modal repeats on every edit until the pivot is finished. The subsequent V2 door then conflicts with the retained ground range exactly as F-05 describes; the card selector again does not withdraw it.
Rubric misses: 6, 7.

### F-29 — Detector-first entry costs a modal per edit for the whole detector and readout block — Severity: **S4** (quantifies F-13)
J-2.1 steps 2–14: twelve accepted edits, twelve *Circular dependency* modals, before the first optics parameter. Mike's persona always enters this way.

### F-30 — Status-bar and dialog strings speak API — Severity: **S4** (CU-371 class)
*Sweep complete — result retained (export via SweepResult.to_csv)* (J-1.1 step 19); *Config incomplete — set optics.focal_length_m (see Messages…)* is fine, but the rail item under it ends *Set it via: params.set('optics.focal_length_m', value)* (F-12).

### F-31 — Internal codes and flags are exported as metrics — Severity: **S4**
`sampling_regime_code = 1.0` and `niirs_extrapolated = 1.0` appear in every metrics export and every sweep column. The metrics CSV's description column explains them; the sweep CSV (F-17) does not, so `niirs_extrapolated = 1.0` reads as NIIRS 1.0 on Sarah's slide.

## 3. Observations that are not findings

- **The FPA preset card is honest**: *geosnap-18: 10 applied, 2 kept (explicit wins)* over hand-entered values; *12 applied* on a blank detector. Remove leaves the operator's own values alone.
- **Sweep cancel is honest** and the export gate follows it.
- **The geometry derived readout names every active mode** (`viewing_mode = geometry.ground_range_m`, `solar_mode = site+time (S3)`, `kinematics_mode = circular_orbit`, `los_rate_mode = target velocity (K2)`), and three non-default doors in one session are honoured.
- **Study creation is smooth**: Configurations… ▸ add twice, the bar appears, configure across seeds every column from the shared value, the badge summary lists each configuration with units, un-configure keeps the displayed configuration's value and asks first.
- **Save As adopts the file** (title `j13_lwir.yaml — RADIANT…`, `(3 configurations)` for a study); *Changed only* lists exactly what was set (16 rows for Sarah).
- **Undo of an edit to an already user-set value is correct** (visibility 23 km after two undos).
- **The comparison table on plain files reads well** — *Δ vs current; ✓ = best*.
- Per-configuration SNR identical across apertures at fixed f-number is physics (extended-scene radiance), not a defect, but see F-18 for the missing per-column cue.

## 4. Proposed dispositions (for `Recommendation.md` at close)

No S1 in this phase, so no CU is minted at this merge (§10 ruling 4). Proposed grouping: F-17, F-22, F-31 are one export-format family (units, labels, one row per configuration); F-18, F-19, F-27 are one "the trade surfaces need the result's own flags" family (clipped, refused, below-threshold) and share the CU-371 II-009 seam; F-20 joins CU-372 (edit discipline: undo provenance); F-21, F-25, F-28 join the phase-1 routing/strings family (F-09/F-12/F-13); F-23 and F-24 are two small stand-alone tasks; F-26 joins F-15 and waits on the Gap 85 mission-type decision.

## 5. Native confirmation queue for live session 1 (additions)

F-20, F-22, F-24 (S2), after the phase-1 queue.
