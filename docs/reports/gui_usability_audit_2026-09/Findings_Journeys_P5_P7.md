# GUI Usability Audit — Findings: Persona Journeys P5–P7 (Tom, Dr. Chen, Karen)

**Status:** Complete (point-in-time record — immutable per Rule 24/28; corrections are new documents)
**Date:** 2026-09-19
**Phase:** 4 of `Audit_Plan.md` §8 (journeys half)
**Harness:** A.
**Baseline:** `main` at `924f6039`. No source was changed.
**Numbering:** continues from `Findings_Tracks.md` (F-32…F-38).

---

## 1. Journey outcomes

| Journey | Outcome | Findings |
|---|---|---|
| J-5.1 Tom — element train, Kirchhoff, Zernike | train and import work; the WFE mode row does not follow the import | F-39, F-40 (observation) |
| J-5.2 Tom — 2-D sweep | clean (*Done — 3×3 grid*); CSV axis carries float noise (F-17) | — |
| J-5.3 Tom — measured MTF overlay, solve with spatial off | overlay clean; the solve dialog silently falls back to its first metric | F-19 (recurs), F-41 |
| J-6.1 Chen — dock-only entry, inspector, explain, exports | the inline path works once the configuration is complete (and only then, F-02); JSON record carries provenance keys | F-42 |
| J-6.2 Chen — disable one effect at a time | metric counts honest (33 → 20 → 18 → 7 → 4 → 0) | — |
| J-6.3 Chen — tolerances and Monte Carlo | tolerances set through the editor dialog; scaffold lists them | — |
| J-7.1 Karen — lab mode | a bench at 0 m is refused by the horizon guard; 1 m of invented altitude makes it run | F-43 |
| J-7.2 Karen — close a 4 mK gap | the solve reports "widen the bounds" for an insensitive metric; the audit trail carries values without provenance | F-18 (recurs), F-42 |

## 2. Findings

### F-39 — After a Zernike import the WFE mode row still reads `scalar_rms default` — Severity: **S3**
J-5.1. Optics ▸ Import Zemax Zernike… on the bundled fixture, confirm *Apply as the wavefront error (supersedes the scalar WFE)?* → `optics.zernike_file` is `user-set`, but `optics.wfe_mode` stays `scalar_rms default` and `optics.wfe_rms_waves` shows `0 waves`. The confirmation says the file supersedes the scalar; the form and dock say the scalar mode is active. Whichever the engine uses, one surface is wrong.

### F-40 — Observation: a default mirror saturates the from-scratch MWIR configuration
J-5.1. Adding one mirror with its defaults (R 0.97, T 293 K) to the eleven-parameter configuration fills the 1e5 e⁻ well entirely from near-field emission (*signal 1.508e+06 e- clipped to 0.000e+00 e-*). Physics, not a GUI defect; recorded because the element table gives no cue, and it compounds F-18 for Tom exactly as the default well did for Sarah.

### F-41 — The solve dialog silently substitutes its first metric when the requested one is not in the list — Severity: **S3**
J-5.3. With the Spatial/MTF group off, `mtf_at_nyquist` is (correctly) absent from the metric list; a target chosen for it lands on `adc_margin_dB`, and the failure reads *adc_margin_dB does not reach the target 0.2* — an operator who did not notice the combo reverting reads a nonsense failure. Same seam as F-19.

### F-42 — The audit-trail exports carry no per-value provenance, and the JSON record's commit is `unknown` — Severity: **S3**
J-6.1, J-7.2. Export Resolved YAML writes `read_noise_e_rms: 40.0` with no user-set / default / derived marker (the dock has it); Karen's "exact inputs used for this prediction" cannot distinguish what she typed from what the schema supplied. Export JSON Result has the right keys (`run_id`, `radiant_version`, `git_commit`, `python_version`, `dependency_versions`, `parameter_set`, `input_file_hashes`, `active_models`) but `git_commit` is `unknown` on a source checkout while the title bar shows `(+924f6039)`.

### F-43 — A bench geometry is refused: sensor and target at 0 m with a 2 m slant range trips the horizon guard — Severity: **S3**
J-7.1. Lab mode as Karen would set it (both altitudes 0, `target_range_m` 2 m) fails on every re-evaluation with the ±0.5° horizon-guard bounds error (a horizontal path *is* grazing). Lifting the sensor to 1 m runs. Nothing in the geometry surface offers a bench or "no geometry" door; the operator invents an altitude to satisfy a refraction guard that is irrelevant to a 2 m path. Related: the personas doc's lab-mode requirement.

## 3. Observations that are not findings

- **The element train's inline parser message is right**: *OpticalElement 'mirror': reflectance values must be in [0, 1], got range [1.2, 1.2]*, with ε re-derived (0.1000) the moment a legal value lands.
- **The transmission banner is honest in both directions**: *Element train defines transmission (0 elements) — scalar τ ignored* and *Scalar throughput is active — the 1 element row(s) below are inactive and held in this session only. Saving writes no optical_elements section*.
- **2-D sweeps work** and the measured-MTF overlay reports residuals plainly (*5 points compared (overlap-only) · RMS residual 0.4997 · max |residual| 0.5 · frequency in cy/m*); its parse error names the columns it needs.
- **Metric-group toggles are honest**: every group off gives 0 metrics and still says *Evaluated*.
- **Tolerances set through the editor dialog land** (gaussian, std 0.05 on three parameters) and the Monte Carlo scaffold lists them.
- **The inline dock path works on a complete configuration** (0 rejections) — it is dead only before completion (F-02).

## 4. Proposed dispositions (for `Recommendation.md` at close)

F-32 → CU-372 checklist (done at this merge). F-34, F-35, F-42 join the export-format family from phase 2 (F-17/F-22/F-31): every export needs a run stamp, a stale flag and provenance. F-37 joins CU-372 or the display-units family (owner call). F-39 is a one-line form fix. F-41 joins F-19. F-43 is a personas-level question (a lab-mode door) for the owner, adjacent to Gap 85. F-33, F-36, F-38 go to live session 2.
