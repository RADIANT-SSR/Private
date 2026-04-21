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
| 2 | **A3 partial-column MODTRAN parity**. A3 is wired end-to-end in `SimpleAtmosphere` and the Table C smoke tests pass monotonicity ([`tests/integration/test_table_c_cells.py`](../tests/integration/test_table_c_cells.py)), but MODTRAN-equivalent validation of τ(h_tgt, θ_o) is pending. | Table C (Cells 31–45) | Expressibility: ✅. Accuracy: smoke-tested and monotone in h_tgt, but not pinned against an external reference. | Add MODTRAN-driven A3 truth anchors when the MODTRAN backend is extended to emit layer-resolved τ. |
| 3 | **§7 warning-level validators are not all covered by integration tests**. The descriptor-side warnings (SWIR hot-target, θ_s>π/2, sub-pixel-collapses-to-point-source) are emitted and have unit-test coverage in `src/radiant/core/tests/test_descriptors.py` and `src/radiant/optics/tests/test_psf_regime_validation.py`, but the 90-cell harness does not assert the warning fires. | All warning paths | Silent drift possible if a future refactor removes the warning emit without breaking the unit test. | Extend `test_use_case_matrix.py` fixtures to capture `pytest.warns(UserWarning)` for the cells known to straddle a warning boundary. Low priority. |
| 4 | **`no_atmosphere (lab_test)` dark-cal mode is not a first-class parameter**. The matrix's dark-cal sub-mode (illumination=None) is expressible by simply not configuring a source illumination, but there is no positive assertion in the descriptor that this is dark-cal. | D-lab subset (~5 cells where illumination=None is intended) | Expressibility: ✅ (cells pass). Readability: the scenario YAML has no field explicitly flagging dark-cal vs lit-lab. | Minor ergonomics — add an optional `lab_test_mode: "dark" \| "lit"` enum when a user actually asks for it. Not a correctness gap. |
| 5 | **Earth-LOS-intercept check is present but not exercised in a negative integration test**. `LineOfSightGeometry.intercepts_earth(h_sensor)` is implemented ([src/radiant/core/los_geometry.py](../src/radiant/core/los_geometry.py)) and unit-tested, but no integration test configures a "space" target with sensor below the target to confirm the validator raises end-to-end. | D-space invalid configurations | Validator works in isolation; negative integration path not proven. | Add one negative-path test to `test_use_case_matrix.py` that flips sensor and target altitudes for Cell 58 and asserts a raise. |

---

## Bottom Line

RADIANT expresses all 80 valid use-case cells and correctly rejects all 10 invalid-by-spec cells. The matrix is now a **description of what RADIANT does**, not a forward-looking contract.

The five remaining items above are numerical-depth or coverage-harness polish; none block a release. The pre-Option-C blocker list (Option C refactor, descriptor schema, A3 partial-column backend) is complete and preserved for archaeology in [`archive/Use_Case_gaps_2026-04-19_pre_option_c.md`](archive/Use_Case_gaps_2026-04-19_pre_option_c.md).

Operational/numerical gaps that predate Option C (Gaps 1–30) continue to live in [gaps.md](gaps.md).
