# RADIANT Use-Case Coverage — Remaining Gaps

**Date**: 2026-04-21 (post-Option-C, post-Stage-8)
**Source of truth**: [RADIANT_Use_Case_Matrix.md](RADIANT_Use_Case_Matrix.md) v1, 90 cataloged cells
**Coverage harness**: [`tests/integration/test_use_case_matrix.py`](../tests/integration/test_use_case_matrix.py), persisted at [`tests/integration/_use_case_coverage.json`](../tests/integration/_use_case_coverage.json)
**Historical pre-Option-C audit**: [`archive/Use_Case_gaps_2026-04-19_pre_option_c.md`](archive/Use_Case_gaps_2026-04-19_pre_option_c.md)

---

## Executive Summary

Option C landed on 2026-04-20 (tag `option-c-complete`). Of the 90 cataloged cells:

| Severity | Count | Examples |
|---|---|---|
| ✅ PASS (cell runs end-to-end) | 80 | All valid cells across Tables A/B/C/D-space/D-ground/D-lab |
| 🚫 CORRECT-RAISE (invalid-by-spec cell correctly rejected) | 10 | All at_aperture × {sub_pixel, point_source} (Cells 2, 3, 5, 6, 8, 9, 11, 12, 14, 15) |
| ❌ FAIL | 0 | — |

The remaining items are **numerical / physics-depth**, not structural. Descriptor schema, assembly equation, §7 validators, and A3 partial-column backend are all in place.

---

## Remaining Gaps

| # | Gap | Cells affected | Impact | Next step |
|---|-----|----------------|--------|-----------|
| 1 | **E_sky scattered-vs-thermal decomposition** (Open Q §8.6). Single-scatter formula `E_sky_scattered = E_TOA·cos(θ_s)·ω₀·(1−τ_down,vert)` is in place, but ω₀ is a fixed scalar and does not vary by aerosol regime or wavelength with MODTRAN-parity fidelity. | MWIR mixed emit+reflect: Cells 25, 40, 55 | Expressibility: ✅. Accuracy: ~10–30% on MWIR-band radiance in scenes where thermal downwelling competes with scattered solar. No effect on LWIR (Cell 28, 58) or VIS/NIR-dominated cells. | Defer to a dedicated aerosol-parity task once MODTRAN-driven lookup tables are wired. Not a release blocker. |
| 2 | **A3 partial-column MODTRAN parity** — **BLOCKED: no MODTRAN access** (2026-04-21). A3 is wired end-to-end in `SimpleAtmosphere` and the Table C smoke tests pass monotonicity ([`tests/integration/test_table_c_cells.py`](../tests/integration/test_table_c_cells.py)), but MODTRAN-equivalent validation of τ(h_tgt, θ_o) requires a licensed MODTRAN install to generate reference tape7 fixtures. The backend extension itself is ~2 days (two-run differential: full column + h_tgt→sensor legs, extending `ModtranAtmosphere.evaluate` in `src/radiant/atmosphere/modtran.py`), but cannot be validated without MODTRAN. | Table C (Cells 31–45) | Expressibility: ✅. Accuracy: smoke-tested and monotone in h_tgt, but not pinned against an external reference. | Unblock when MODTRAN access is available (licensed install or donated tape7 fixtures). Alternative: substitute a lower-fidelity reference model (e.g. `lowtran` python port or hand-derived Beer-Lambert comparison at thin-atmosphere limits) — adds a dependency, not recommended for closure. |
| 3 | ~~**§7 warning-level validators are not all covered by integration tests**~~ — **CLOSED 2026-04-21** by [`tests/integration/test_use_case_warnings.py`](../tests/integration/test_use_case_warnings.py): 19 parametrized tests across four warning classes (SWIR hot-target, T2+sun-below-horizon, sub-pixel-collapses-to-point-source, point-source oversized-raise) covering Tables B / C / D-space / D-ground / D-lab. | All warning paths | Silent-drift risk resolved at the integration level. Future refactors that remove a `warnings.warn` will now break this file, not just the unit tests. | — |
| 4 | **`no_atmosphere (lab_test)` dark-cal mode is not a first-class parameter**. The matrix's dark-cal sub-mode (illumination=None) is expressible by simply not configuring a source illumination, but there is no positive assertion in the descriptor that this is dark-cal. | D-lab subset (~5 cells where illumination=None is intended) | Expressibility: ✅ (cells pass). Readability: the scenario YAML has no field explicitly flagging dark-cal vs lit-lab. | Minor ergonomics — add an optional `lab_test_mode: "dark" \| "lit"` enum when a user actually asks for it. Not a correctness gap. |
| 5 | **Earth-LOS-intercept check is present but not exercised in a negative integration test**. `LineOfSightGeometry.intercepts_earth(h_sensor)` is implemented ([src/radiant/core/los_geometry.py](../src/radiant/core/los_geometry.py)) and unit-tested, but no integration test configures a "space" target with sensor below the target to confirm the validator raises end-to-end. | D-space invalid configurations | Validator works in isolation; negative integration path not proven. | Add one negative-path test to `test_use_case_matrix.py` that flips sensor and target altitudes for Cell 58 and asserts a raise. |

---

## Bottom Line

RADIANT expresses all 80 valid use-case cells and correctly rejects all 10 invalid-by-spec cells. The matrix is now a **description of what RADIANT does**, not a forward-looking contract.

Of the five original remaining items, Gap #3 is **closed** (2026-04-21) by the new warnings-coverage file. Gap #2 is **blocked** on MODTRAN access. Gaps #1, #4, #5 remain low-priority numerical-depth / ergonomics items; none block a release. The pre-Option-C blocker list (Option C refactor, descriptor schema, A3 partial-column backend) is complete and preserved for archaeology in [`archive/Use_Case_gaps_2026-04-19_pre_option_c.md`](archive/Use_Case_gaps_2026-04-19_pre_option_c.md).

Operational/numerical gaps that predate Option C (Gaps 1–30) continue to live in [gaps.md](gaps.md).
