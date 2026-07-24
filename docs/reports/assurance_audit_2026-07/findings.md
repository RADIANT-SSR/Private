# Assurance Audit 2026-07 — Findings Register and Closure

Status: Complete (audit closed 2026-07-24)
Remediation: `docs/archive/assurance_audit_remediation.md` (executed 2026-07-23, CU-183…CU-206)
Verification: independent pass 2026-07-24 by the original auditor (this document's §3).

## 1. Track A — blind re-derivation: comparison-wave verdict

The wave-2 comparison agents were lost to a session usage limit on 2026-07-22; per plan item
R4.4 the comparison was instead completed by encoding the blind anchors as Level-0 tests
(R1.1–R1.8). Final physics verdict, per cluster:

| Cluster | Verdict | Evidence |
|---|---|---|
| A1 radiometry (Planck, dL/dT, band integral, inversions, responsivity) | **MATCH** — code equals blind literals to rel ≤ 1e-6 (band integral 1.6e-6 quadrature) | CU-183/184 resolutions; `test_blackbody.py`, `test_invert_band_radiance.py`, `test_responsivity.py` |
| A2 spatial (pupil MTF, detector/jitter/smear MTF, Maréchal, EE_box) | **MATCH with one quantified deviation** — physics and box definition correct; sampled EE_box carries an O(dx) discretization floor, +24 % at Q=2 with default psf_oversample=8 → open [[CU-188]] | CU-187/189 resolutions; `test_ee_box.py::test_ee_box_airy_q2_anchor` convergence data |
| A3 noise & sensitivity (RSS, ADC, PRNU, SNR, NEDT, NEP, D*, TDI, DR, BLIP) | **MATCH** — anchors matched exactly (NEP anchor to rel 1e-6; plan's λ-in-m band form was a convention difference, verified not a bug) | CU-186/191 resolutions; `test_noise*.py`, `test_adc.py` |
| A4 geometry (viewing triangle, orbit, GSD, solar, sampling) | **MATCH** — after reconciling the code's mean-radius Earth (blind anchors were equatorial-R; both variants tabulated in track_a4); cos θ_i lands on the code's tilt-plane convention, verified against the wrong-angle discriminator | CU-190 resolution; `test_gsd.py::TestA4GeometryAnchors`, `test_orbit.py`, `test_solar_geometry.py` |

**Headline: no physics error was found in the signal chain.** The one material finding is a
numerical-discretization bias (CU-188), not a formula error.

## 2. Disposition register (Rule 28: every finding CU'd / Planned→executed / Declined)

Track B (test quality): B1-1→CU-185, B1-2→CU-186, B1-3→CU-187 (+CU-188 filed), B1-4+B2-3→CU-183,
B1-5/B1-7/B1-8+B2-4/5/6/8→CU-192, B1-6+B2-7→CU-193, B2-1/B2-2→CU-184, **B1-9 Declined**
(band dispatch unobservable while IIRS≡GIQE-5; recorded in CU-193 close-out d854f3d).

Track C (doc drift): D6-D9→CU-199, S1-S6→CU-200, O1-O3→CU-201 (owner decision R4.2: keep 0.7
default, document), M1-M2→CU-202, P1-P3→CU-203, D3-D5→CU-204, D1-D2→CU-205 (owner decision
R4.1: implement frame-rate contract — `readout.frame_period_s` + `frame_timing.py`),
D10-D18→CU-206. Duplicated arch-doc parameter tables deleted per R2.4→CU-197 (+CU-198 filed:
Source_Target §8 name drift, open).

Unenforced risks: #1 dual-path warn-only→CU-194 (hard gate over 34 GUI baselines),
#2 conversion/constant lint→CU-195, #3 approx-tolerance lint→CU-196. **Declined** (documented
residual risk, revisit on implication): pupil_npix/psf_oversample literals (partially
mitigated by CU-188 follow-up), Ω typing, stage-output key schema, convolution-order test,
stage purity scanning, coverage thresholds.

All CU closures carry commit SHAs (Rule 22); remediation plan archived (Rule 24).

## 3. Independent verification of the remediation (2026-07-24)

Performed by the original auditor against main (post-merge, through 8ee60c7):

- **Anchor fidelity**: R1 test literals diffed against the committed blind derivations —
  values faithful (9.92403333 / 0.721976423 / 38.5004239 / 0.177327 / GIQE-5 six literature
  coefficients / NEP 2.8377797959e-16 W); geometry anchors correctly re-derived for the
  code's mean-radius Earth rather than silently loosened. No tolerance was widened to force
  a pass; the one bracket-style assertion (EE_box) is one-sided against the analytic limit
  with a floor-sized margin and the deviation is CU-tracked, not absorbed.
- **No concealed failures**: every CU close-out records its comparison-wave result; the only
  non-exact outcome (EE_box) became open CU-188 with measured convergence data
  (0.219/0.198/0.188/0.183 at oversample 8/16/32/48).
- **Post-remediation edits**: the style close-out (9d5d75b) touching six anchor files was
  re-diffed — formatting/rename only, all anchor literals and tolerances unchanged.
- **Tests**: all 271 tests across the 14 anchor-bearing files pass locally (173 s).
- **Tripwires trip**: in a scratch worktree, an injected `6.626e-34` in a physics module and
  an injected tolerance-less `pytest.approx` made `check_physics_conversions.py` and
  `check_approx_tolerances.py` exit 1 respectively; both run in the CI static gate. R2.1 is
  a hard parametrized assertion (`test_gui_baseline_dual_path_consistency`) over every
  shipped baseline, with the Gap-96 trivial-pass case documented.
- **R3.4 (only behavior-affecting change)**: new parameter in `_schema.py` (R12), own module
  (R19), actionable duty>1 rejection (R15), lock-step doc updates + regenerated parameter
  reference (R20), CHANGELOG entry (R29), unset default reproduces prior behavior — goldens
  unchanged.

**Verdict: remediation executed faithfully; audit closed.** Open follow-ups live in the
registries, not here: CU-188 (EE_box discretization bias — results-affecting for
point-source/sub-pixel SNR when fixed), CU-198 (Source_Target §8 name drift).

Per Rule 28 / OPERATING_MODEL §2 this folder is now immutable.
