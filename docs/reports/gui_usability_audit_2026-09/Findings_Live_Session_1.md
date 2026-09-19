# GUI Usability Audit — Findings: Live Session 1 (owner at the native window)

**Status:** Complete (point-in-time record — immutable per Rule 24/28; corrections are new documents)
**Date:** 2026-09-19
**Phase:** 3 of `Audit_Plan.md` §8
**Harness:** B — the owner drove `radiant gui` on macOS from the agent's numbered script and reported per step with screenshots; the agent replayed each surprise headless to name the mechanism.
**Baseline:** `main` at `e554b603` (the owner's title bar).
**Numbering:** continues from `Findings_Journeys_P5_P7.md` (F-39…F-43).

---

## 1. Native confirmations

| Finding | Native result |
|---|---|
| F-01 dock shows unset on unresolved config | **Confirmed.** Optics form showed 0.3 / 1.2 / 6 while every dock row read `—`; rows filled only once the configuration resolved. |
| F-02 in-place editor dead on blank config | **Confirmed in a worse form** (F-46 below): the editor opens, accepts typing, and reverts to `—` with no message. |
| F-03 Reset to Default applies but reports rejection | **Confirmed.** "Cannot set optics.focal_length_m" modal, row still 1.2 m user-set, status still "Evaluated", dock banner repeating the modal; the reset had applied. (The scripted step used the wrong member and reset cleanly — a state difference, corrected in-session.) |
| F-05 door conflict, selector display-only | **Confirmed.** Good modal, card tinted, selector flipped to V3 with the V1 field greyed; changing the selector changed nothing; exit was the dock's right-click Reset. Owner did not say whether the exit was findable unaided. |
| F-06 blank-config over-spec admitted, blames first member | **Confirmed**, including the `0.19999999999999998` in the modal. |
| F-12 / F-13 "Cannot set evaluate" cycle diagnostic per edit | **Confirmed**; quiet advisory path took over once the aperture existed. |
| F-17 sweep CSV bare headers, float noise | **Confirmed** (`1.3200000000000000` axis values; owner opened it in Numbers). |
| F-18 flat sweep, no saturation notice | **Confirmed**: "Done — 6 points", flat at 316 from the second point, saturation mentioned nowhere in the dialog. The dialog also accepted a 6 m aperture typed by mistake. |
| F-20 undo writes default back as user-set | **Confirmed**: `jitter_rms_urad 0 µrad user-set` beside untouched rows saying default. |
| F-32 YAML Apply admits out-of-bounds; editor cannot reopen | **Confirmed**: "Configuration incomplete", rows `—`, Edit Config (YAML) dead, F5 gives the bounds modal, dialog on the aperture recovers. |

## 2. New findings from the session

### F-44 — `radiant gui` never shows the welcome screen — Severity: **S3**
The CLI hands the window a blank `Sensor`, so the templates, Blank config card and recent list appear only after File ▸ New. The guide and `launch_gui`'s docstring say a bare launch shows them. The two blank states also greet differently: "Configuration incomplete — set required parameters, then Evaluate (F5)…" from the CLI, "New configuration — edit parameters, then Evaluate" from the card. → CU-373.

### F-45 — The Parameters dock rebuilds on every accepted edit: selection lost, view jumps to the top — Severity: **S2**
Owner: "after every new value is set in the parameter table it resets and jumps to the top. this is very annoying behavior." Mechanism: `populate` clears the tree (`self._tree.clear()`) and rebuilds it after each accepted edit; the current row is lost every time (headless confirmed) and the scroll position with it natively. The owner fell back to the filter box to work around it. → CU-376.

### F-46 — On a blank configuration the in-place editor accepts typing and reverts silently, and its column has no width — Severity: **S2**
The Value column collapsed to about ten pixels ("Va"), so the first double-click landed on the name column and opened the dialog instead. Once widened, the in-place editor opened, took the value, and on Enter reverted to `—` with no modal or message. Headless the same commit shows the "Parameter Rejected" modal, so natively the modal is lost in the editor-close sequence. → CU-376 (and CU-372 for the guard).

### F-47 — The required-parameter advisory points at a stage whose form has no field for it — Severity: **S2**
"Config incomplete — set spectral_integration.integration_time_s" reddened the Spectral chip; the Spectral form holds only the two filter edges. Integration time lives on Readout ▸ Acquisition. The operator had to use the dock. → CU-373.

### F-48 — Inactive geometry doors display schema defaults, not derived values — Severity: **S3**
With path zenith 10° from 500 km, the greyed `ground_range_m` read 0 m and `elevation_angle_rad` 90 deg (true: ~88 km, ~80°); after switching to ground range 300 km the greyed zenith read 0 deg (true 33°). The guide says inactive doors show values derived from the active one. → CU-377.

### F-49 — Source tab labels truncate at 1440 px — Severity: **S4**
"Target — th…", "Target — point s…", "Background & co…". → CU-376.

### F-50 — Editor dialog details on an unresolved configuration — Severity: **S4**
Preview reads "= —" while a value is typed; "Configure across configurations…" offered in a single-model session. → Findings Log.

### F-51 — After a document swap that leaves the configuration unresolvable, the previous result's banners stay — Severity: **S3**
After F-32 the saturation banner and three warnings from the old configuration remained with no stale marker, and the centre dropped to the "New configuration" placeholder although a stage was selected. → CU-373.

### F-52 — Process language seen natively — Severity: **S4**
"Gap 65" in the saturation warnings, "deferred (Gap 92) … (Rule 8)" on the Spectral outputs note, "v1-minimal (owner-ratified…) (ADR-0006 §4 / CU-122)" on the Platform note, raw `context.*` rows at the foot of the geometry modal. → CU-371 checklist.

### F-53 — A POSIX default path in the dock — Severity: **S4**
`modtran.binary_path` shows `/usr/lo…modtran` as a default. → CU-371 checklist (Rule 30 says a platform-dependent default should fail actionably, not display).

### F-54 — Observation: a YAML round trip relabels user-set values as "config"
After the recovery, `focal_length_m` carried a `config` badge. Documented (`ug_yaml_roundtrip.md` §3.1), noted because it silently changes the provenance of everything typed.

## 3. Observations

- The owner's instinct on the first blank-config edit was the Value cell; the collapsed column steered the click to the dialog. That accident is why the dialog path, which works, is what most operators will hit first.
- The dock's tooltip on hover (dot-path plus description) was noticed and useful.
- Session length: about 30 steps, roughly an hour, one script slip on the agent's side (the reset target).

## 4. Not confirmed natively

F-04, F-08, F-22, F-24 (S2) were not in the session; they stand on headless evidence. Live session 2 (T-H, T-I) was not held; the T-H grabs are in `Findings_Tracks.md`.
