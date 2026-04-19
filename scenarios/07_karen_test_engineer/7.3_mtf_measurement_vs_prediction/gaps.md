# Scenario 7.3: Gaps — MTF Measurement vs. Prediction

## Gap Closure Summary

| Gap # | Description | Status | Notes |
|-------|-------------|--------|-------|
| 19    | No MTF budget decomposition API | **CLOSED** | `result.stage_outputs["performance"]["mtf_budget"]` provides per-term MTF at Nyquist via `.per_term_at_nyquist` dict and `.system_mtf_at_nyquist_x/y` |
| 29    | No defocus model (focus-shift parameter) | **CLOSED** | `optics.defocus_um` parameter now accepted; RADIANT applies Gaussian defocus blur with sigma = abs(delta)/(4*f/#*sqrt(3)) |
| 30    | No measurement data import/overlay API | OPEN | Must manually read and overlay lab data in script |
| 31    | No scatter/surface roughness (TIS) model | OPEN | Unmodeled MTF loss source |
| 32    | No electronics MTF model (amplifier bandwidth) | OPEN | Unmodeled MTF loss source |

## Newly Available Metrics

These metrics are now returned by `result.metrics` and were not available when
the scenario was first written:

| Metric | API Key | Value (this scenario) | Notes |
|--------|---------|----------------------|-------|
| Strehl ratio | `result.metrics["strehl"]` | 0.8324 [--] | From EffectivePSF |
| RER | `result.metrics["rer"]` | 0.6825 [--] | Relative edge response |
| Q (center) | `result.metrics["q_center"]` | 0.195 [--] | Sampling parameter |
| Q (min/max) | `result.metrics["q_min"]`, `["q_max"]` | 0.165 / 0.225 [--] | Over band |
| FWHM_x | `result.metrics["fwhm_x_m"]` | 10.79 [um] | PSF full-width half-max |
| Well margin | `result.metrics["well_margin_dB"]` | 429.6 [dB] | Very large -- lab test, near-zero signal |
| Dynamic range | `result.metrics["dynamic_range_dB"]` | 83.2 [dB] | |
| MTF budget | `result.stage_outputs["performance"]["mtf_budget"]` | See table | Per-component MTF at Nyquist |
| Folded MTF | `result.stage_outputs["performance"]["folded_mtf_x"]` | Available | Full folded MTF curve |
| Noise terms | `result.noise_terms` | See breakdown | Per-source noise in e- |
| GSD | `result.metrics["gsd_cross_track_m"]` | None | N/A for lab test (altitude=0) |
| NIIRS | `result.metrics["niirs"]` | None | N/A for lab test (altitude=0) |
| NEDT | `result.metrics["nedt_K"]` | ~8.5e17 [K] | Effectively infinite -- no thermal scene in VNIR lab test |

## RADIANT MTF Budget at Nyquist (from API)

| Component | MTF@Ny_x | MTF@Ny_y |
|-----------|----------|----------|
| Optics (diffraction + WFE + obscuration) | 0.8115 | 0.8115 |
| Pixel Aperture | 0.6364 | 0.6364 |
| IPC | 0.9602 | 0.9602 |
| Jitter | 1.0000 | 1.0000 |
| Smear | 1.0000 | 1.0000 |
| Charge Diffusion | 1.0000 | 1.0000 |
| TDI | 1.0000 | 1.0000 |
| **System (product)** | **0.4961** | **0.4961** |

Note: The RADIANT optics MTF (0.8115) is lower than the analytic ideal diffraction
MTF (0.8761) because RADIANT includes WFE (0.07 waves) and central obscuration (25%).

## Remaining Open Gaps

| Gap # | Description | Impact | Workaround |
|-------|-------------|--------|------------|
| 30    | No measurement data import/overlay API | Must manually read lab CSV/Excel and overlay | Script reads Excel directly with openpyxl |
| 31    | No scatter/TIS model | ~5-10% unmodeled MTF loss | None -- residual includes this effect |
| 32    | No electronics MTF model | Unmodeled bandwidth effects | Negligible for CCD at these frequencies |
