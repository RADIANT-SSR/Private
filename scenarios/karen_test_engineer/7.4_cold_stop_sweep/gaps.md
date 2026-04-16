# Scenario 7.4 — Blocked Issues

## Gap 1: No inverse solver / parameter matching
**Severity**: Medium
**Description**: RADIANT has no built-in mechanism to find the parameter value that produces a target output (e.g., "what cold_stop_efficiency gives 44,000 e- background?"). The script works around this by sweeping and linear interpolation, but a proper root-finding solver would be more efficient and generalizable.
**Workaround**: Sweep + linear interpolation in the script.
**Recommendation**: Add a `Sensor.solve_for(parameter, target_metric, target_value)` method or similar to the API.

## Gap 2: No per-element nearfield breakdown
**Severity**: Low
**Description**: RADIANT outputs total `nearfield_e` but does not break it down by optical element (primary mirror, secondary, fold mirror, field lens, filter). Karen cannot determine which element contributes most to the nearfield, which would help diagnose whether the cold stop leakage is directional (coming from one element's solid angle).
**Workaround**: None — would require changes to `optics/element_list.py` to return per-element contributions.
**Recommendation**: Add per-element nearfield breakdown to stage_outputs.

## Gap 3: No NEDT metric
**Severity**: Medium
**Description**: Karen's requirements include NEDT (noise-equivalent differential temperature), but RADIANT does not currently compute or output NEDT. This is a standard thermal imager metric: NEDT = noise / (dS/dT).
**Workaround**: Could be hand-calculated from RADIANT's signal and noise outputs, but not automated.
**Recommendation**: Add NEDT computation to the performance stage. This is also needed by scenarios 7.1, 2.2, and others.

## Issue 4: cold_stop_efficiency convention mismatch
**Severity**: Low (documentation)
**Description**: RADIANT's `cold_stop_efficiency` parameter (fraction of FPA hemisphere filled by warm-emitting elements) is inverted from the vendor convention (where "100% efficient cold stop" means complete blocking). η_cold = 0 in RADIANT means perfect cold stop; vendors say "100% efficient" for the same condition. This caused initial confusion in the script and will confuse GUI users.
**Workaround**: Script includes an explicit convention note in the output.
**Recommendation**: Consider renaming to `cold_stop_leakage` or `nearfield_fraction` to avoid ambiguity. Alternatively, add a prominent tooltip/note in the GUI.
