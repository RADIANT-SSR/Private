# Scenario 7.4 — Blocked Issues

## Gap 1: No inverse solver / parameter matching
**Severity**: Medium
**Status**: OPEN
**Description**: RADIANT has no built-in mechanism to find the parameter value that produces a target output (e.g., "what cold_stop_efficiency gives 44,000 e- background?"). The script works around this by sweeping and linear interpolation, but a proper root-finding solver would be more efficient and generalizable.
**Workaround**: Sweep + linear interpolation in the script.
**Recommendation**: Add a `Sensor.solve_for(parameter, target_metric, target_value)` method or similar to the API.

## Gap 2: No per-element nearfield breakdown
**Severity**: Low
**Status**: OPEN
**Description**: RADIANT outputs total `nearfield_e` but does not break it down by optical element (primary mirror, secondary, fold mirror, field lens, filter). Karen cannot determine which element contributes most to the nearfield, which would help diagnose whether the cold stop leakage is directional (coming from one element's solid angle).
**Workaround**: None — would require changes to `optics/element_list.py` to return per-element contributions.
**Recommendation**: Add per-element nearfield breakdown to stage_outputs.

## Gap 3: No NEDT metric (CLOSED)
**Severity**: Medium
**Status**: CLOSED
**Description**: Karen's requirements include NEDT (noise-equivalent differential temperature), but RADIANT did not previously compute NEDT.
**Resolution**: RADIANT now computes NEDT in the performance stage. Access via `result.metrics["nedt_K"]`. The script now displays NEDT in the baseline, sweep results, and SNR impact comparison sections.

## Gap 4: Nearfield = 0 in scalar transmission mode
**Severity**: High (scenario-limiting)
**Status**: OPEN
**Description**: In scalar transmission mode (the default), RADIANT models the entire optical train as a single lumped refractive element. By Kirchhoff's law, a refractive element has emissivity ε = 1 − T − R = 0 (all loss is reflection, not absorption). With ε = 0, there is no thermal self-emission, so `nearfield_e = 0` regardless of cold_stop_efficiency.

This makes the cold stop sweep fundamentally non-functional in scalar mode — all sweep values produce identical (zero) nearfield signal. The lab measurement matching produces "above model range" for all measurements since the model predicts zero background from warm optics.

**Fix required**: Use `key_elements` or `full_prescription` transmission mode to specify individual optical elements (mirrors with ε = 1 − R, lenses with ε = 1 − T − R). This allows RADIANT to compute per-element self-emission and makes the cold stop sweep meaningful.

**Impact**: The script runs without error but produces physically meaningless results for the cold stop analysis. The SNR, NEDT, NIIRS, and MTF results are still valid — only the nearfield-dependent analysis is affected.

## Issue 5: cold_stop_efficiency convention mismatch
**Severity**: Low (documentation)
**Status**: OPEN
**Description**: RADIANT's `cold_stop_efficiency` parameter (fraction of FPA hemisphere filled by warm-emitting elements) is inverted from the vendor convention (where "100% efficient cold stop" means complete blocking). η_cold = 0 in RADIANT means perfect cold stop; vendors say "100% efficient" for the same condition. This caused initial confusion in the script and will confuse GUI users.
**Workaround**: Script includes an explicit convention note in the output.
**Recommendation**: Consider renaming to `cold_stop_leakage` or `nearfield_fraction` to avoid ambiguity. Alternatively, add a prominent tooltip/note in the GUI.

### Gaps Closed Since Last Run

| Gap | Previous Status | Current Status |
|-----|----------------|----------------|
| NEDT metric | Not available | `result.metrics["nedt_K"]` — CLOSED |
| NIIRS metric | Not available | `result.metrics["niirs"]` — CLOSED |
| GSD metric | Not available | `result.metrics["gsd_geometric_mean_m"]` — CLOSED |
| Strehl ratio | Not available | `result.metrics["strehl"]` — CLOSED |
| Q parameter | Not available | `result.metrics["q_center"]` — CLOSED |
| MTF budget | Not available | `mtf_budget.per_term_at_nyquist` — CLOSED |
| Well margin | Not available | `result.metrics["well_margin_dB"]` — CLOSED |
