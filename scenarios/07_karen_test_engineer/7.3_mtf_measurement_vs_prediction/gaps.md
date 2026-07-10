# Scenario 7.3: Gaps — MTF Measurement vs. Prediction

Refreshed 2026-07-07 (Scenario_Execution_Plan Phase R). Registry mirror:
`docs/tracking/gaps.md` (Gaps 19, 26, 29–32) and
`docs/tracking/Cleanup_Backlog.md` (CU-058).

## Gap Closure Summary

| # | Description | Status | Notes |
|---|-------------|--------|-------|
| Gap 19 | No MTF budget decomposition API | **CLOSED** | `result.stage_outputs["performance"]["mtf_budget"]` — `.per_term_at_nyquist`, `.system_mtf_at_nyquist_x/y` |
| Gap 29 | No defocus model | **CLOSED** | `optics.defocus_um`; pupil Zernike Z4 on BOTH spatial paths (CU-058 resolved 2026-07-09) |
| Gap 30 | No measurement import/overlay API | **CLOSED** (this refresh) | `radiant.io.measurement.load_measured_curve` reads the slanted-edge tool's CSV; `radiant.api.compare_mtf` converts cy/mm → cy/m and returns residual statistics. Exercised end-to-end here. |
| Gap 31 | No scatter/TIS model | **CLOSED** (this refresh) | `optics.surface_roughness_nm` + `optics.scatter_halo_sigma_um`; exercised as a residual explainer (rejected by the data — see walkthrough) |
| Gap 32 | No electronics MTF model | **CLOSED** (this refresh) | `readout.electronics_sigma_um`; exercised as a residual explainer (rejected by the data — the residual sign points to WFE shape, not blur) |

## Defects Found by This Refresh

### CU-058 — Scalar WFE + defocus violated Rule 4 (FILED → RESOLVED 2026-07-09)
Combining scalar `optics.wfe_rms_waves` with `optics.defocus_um` made the
dual-path consistency check fail on every evaluation (max_err ≈ 0.169 vs
tolerance 0.05): `_add_defocus_to_wfe` folded defocus into the pupil as
Zernike Z4 for the MTF product path but **dropped the scalar-RMS screen** in
doing so, and the two paths modeled defocus differently (PSF: Gaussian
kernel; product: pupil Z4). **Resolved** (commit f5c8fda): defocus now folds
into the pupil once — screen preserved, Z4 alongside — and both paths build
their pupil phase through one shared dispatch, so the consistency check
passes on every run of this scenario and the budget's Optics term carries
the full pupil (0.8115 → 0.6699 at Nyquist). This scenario's rerun under
the fix is the closure evidence.

### Odd-kernel crash on even PSF grids (FIXED, commit 8a5d9e8)
The Gap 31 explainer run initially crashed:
`ValueError: npix must be a positive odd integer, got 256` — kernel sizing
forced odd before capping to the (even) PSF grid, so any config whose 6σ
kernel span exceeded the grid passed an even npix to
`scatter_kernel_2d`/`defocus_kernel_2d`. Fixed inline (cap now clamps to the
largest odd size within the grid) with an end-to-end regression test in
`tests/integration/test_scatter_chain.py`.

## Remaining Limitation (inherent, not a registry gap)

Scalar `wfe_rms_waves` under-determines the MTF shape: it fixes the Strehl
but not where the aberrated energy lands, so any comparison against a
measured MTF curve inherits the model's halo-shape assumption. When the
purpose is measured-vs-predicted comparison, use the as-built Zernike
prescription via `io.load_zemax_zernike` (Gap 26, closed — exercised in
scenario 5.1).

## Newly Available Metrics (unchanged from previous run)

| Metric | API Key | Value (this scenario) | Notes |
|--------|---------|----------------------|-------|
| Strehl ratio | `result.metrics["strehl"]` | 0.8256 [--] | From EffectivePSF |
| RER | `result.metrics["rer"]` | 0.6825 [--] | Relative edge response |
| Q (center) | `result.metrics["q_center"]` | 0.195 [--] | Sampling parameter |
| FWHM_x | `result.metrics["fwhm_x_m"]` | 10.79 [µm] | PSF full-width half-max |
| Well margin | `result.metrics["well_margin_dB"]` | 429.6 [dB] | Very large — lab test, near-zero signal |
| Dynamic range | `result.metrics["dynamic_range_dB"]` | 83.2 [dB] | |
| GSD / NIIRS / NEDT | — | None / None / N/A | Lab test (altitude = 0, no thermal scene in VNIR) |
