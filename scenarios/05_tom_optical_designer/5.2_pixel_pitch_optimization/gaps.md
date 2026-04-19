# Scenario 5.2 — Gaps

## Gap 1: No Q parameter in RADIANT output (CLOSED)
**Severity**: Low
**Status**: CLOSED
**Description**: The sampling parameter Q = λ·f/#/p was not computed by RADIANT.
**Resolution**: Q is now computed natively by PerformanceStage. Access via `result.metrics["q_center"]`, `result.metrics["q_min"]`, `result.metrics["q_max"]`.

## Gap 2: No GSD in RADIANT output (CLOSED)
**Severity**: Low
**Status**: CLOSED
**Description**: GSD was not computed by RADIANT.
**Resolution**: GSD is now computed natively. Access via `result.metrics["gsd_cross_track_m"]`, `result.metrics["gsd_along_track_m"]`, `result.metrics["gsd_geometric_mean_m"]`.

## Gap 3: No aliased/folded MTF model
**Severity**: Medium
**Status**: PARTIALLY CLOSED
**Description**: RADIANT computes the system MTF but previously did not model aliasing (spatial frequency folding at Nyquist). For undersampled systems (Q < 1), high-frequency scene content folds back below Nyquist, producing spurious apparent contrast.
**Current status**: Folded MTF is now computed and available in `result.stage_outputs["performance"]["folded_mtf_x"]`. The script does not yet plot or display it.
**Remaining work**: Script should extract and display folded MTF for undersampled configurations to show aliasing impact.

## Gap 4: No full MTF curve export (CLOSED)
**Severity**: Medium
**Status**: CLOSED
**Description**: Only MTF at Nyquist was reported.
**Resolution**: Full MTF curves are now available in `result.stage_outputs["performance"]` as `mtf_freq_x`, `mtf_x`, `mtf_freq_y`, `mtf_y`.

## Gap 5: MTF = 0.000 at 8 µm pixel pitch (Q = 2.12) (CLOSED)
**Severity**: Medium
**Status**: CLOSED — physically correct, not a bug
**Description**: At Q = 2.12, the Nyquist frequency (62.5 cy/mm) exceeds the diffraction cutoff (~59 cy/mm at 4.25 µm, f/4). MTF = 0 is the correct physical result.

### Gaps Closed Since Last Run

| Gap | Previous Status | Current Status |
|-----|----------------|----------------|
| Q parameter | Manual computation | `result.metrics["q_center"]` — CLOSED |
| GSD | Manual computation | `result.metrics["gsd_cross_track_m"]` — CLOSED |
| Full MTF curve | Not available | `stage_outputs["performance"]["mtf_x"]` — CLOSED |
| MTF = 0 at 8 µm | Under investigation | Physically correct — CLOSED |
| NEDT | Not available | `result.metrics["nedt_K"]` — CLOSED |
| NIIRS | Not available | `result.metrics["niirs"]` — CLOSED |
| Strehl | Not available | `result.metrics["strehl"]` — CLOSED |
| RER | Not available | `result.metrics["rer"]` — CLOSED |
| Well margin | Not available | `result.metrics["well_margin_dB"]` — CLOSED |
| Folded MTF | Not available | `stage_outputs["performance"]["folded_mtf_x"]` — PARTIALLY CLOSED |
