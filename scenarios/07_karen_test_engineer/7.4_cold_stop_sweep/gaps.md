# Scenario 7.4 — Blocked Issues

Refreshed 2026-07-07 (Scenario_Execution_Plan Phase R). Registry mirror:
`docs/tracking/gaps.md` (Gaps 10, 12, 37, 42).

## Gap 1: No inverse solver / parameter matching (CLOSED)
**Severity**: Medium
**Status**: CLOSED — registry Gap 10
**Description**: RADIANT had no built-in mechanism to find the parameter value that produces a target output (e.g., "what nearfield_fraction gives 44,000 e⁻ background?"). The script previously worked around this by sweeping and linear interpolation.
**Resolution**: `Sensor.solve_for(param, target, bounds=, metric=)` (Brent root-finding, registry Gap 10). The refreshed script inverts each lab measurement in 6–7 forward-model evaluations, with a callable metric (`nearfield_e + background_e`). The sweep is retained only for the plots and output workbook, not for matching.

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
**Resolution**: RADIANT now computes NEDT in the performance stage. Access via `result.metrics["nedt_K"]`. The script displays NEDT in the baseline, sweep results, and SNR impact comparison sections.

## Gap 4: Nearfield = 0 in scalar transmission mode (CLOSED)
**Severity**: High (was scenario-limiting)
**Status**: CLOSED — registry Gap 37
**Description**: In scalar transmission mode, RADIANT modeled the optical train as a single lumped refractive element with ε = 1 − T − R = 0 by Kirchhoff's law, so `nearfield_e = 0` regardless of leakage — the cold stop sweep was non-functional and every lab measurement matched "above model range".
**Resolution**: `optics.scalar_emissivity` (registry Gap 37) declares the lumped-train emissivity. The refreshed script derives it Kirchhoff-consistently as ε = 1 − τ = 0.32 (reflective train: non-transmitted power absorbed). The sweep now produces nearfield_e from 0 to 812,493 e⁻ and every lab measurement inverts to an η_nf in [0.0437, 0.0686].

## Issue 5: cold_stop_efficiency convention mismatch (CLOSED)
**Severity**: Low (documentation)
**Status**: CLOSED — registry Gap 12
**Description**: The old parameter name `cold_stop_efficiency` was inverted from the vendor convention (RADIANT 1.0 = no cold stop; vendor 100% = perfect blocking), a recurring source of confusion.
**Resolution**: Renamed to `optics.nearfield_fraction` (deprecated alias retained). The name now states what the value is — the fraction of the FPA hemisphere filled by warm-emitting elements — and the script converts explicitly: η_nf = 1 − vendor efficiency.

## Gap 6: Lab/TVAC scenario must masquerade as the 'space' sub-case
**Severity**: Medium
**Status**: OPEN — registry Gap 42
**Description**: The `no_atmosphere` sub-case `lab_test` requires a manually-injected `UserSpectralBackground`; there is no `Sensor.from_dict`/YAML path for it, and `atmosphere.model = "exo"` auto-infers sub-case `space`. This scenario therefore runs as `space`, which requires a placeholder positive `platform.h_sensor` (set to 1.0 m ≈ bench height) to satisfy the Earth-limb intercept validator, and substitutes `ColdSpaceBackground` for the true chamber radiance.
**Workaround** (used here): acceptable because the extended target (blackbody or 77 K cold plate) fills the FOV and the true chamber background term is negligible in MWIR; the shroud parameters are retained in the config but contribute no photons (extended-regime Decision #13 skips the scene-background term regardless).
**Recommendation**: YAML/dict path for `source.no_atmosphere_subcase` + user background radiance — see registry Gap 42.

### Gaps Closed Since First Run

| Gap | Previous Status | Current Status |
|-----|----------------|----------------|
| Inverse solver | Sweep + interpolation workaround | `Sensor.solve_for` — CLOSED (Gap 10) |
| Nearfield = 0 in scalar mode | Scenario-limiting | `optics.scalar_emissivity` — CLOSED (Gap 37) |
| Convention mismatch | Confusing name | `optics.nearfield_fraction` rename — CLOSED (Gap 12) |
| NEDT metric | Not available | `result.metrics["nedt_K"]` — CLOSED |
| NIIRS metric | Not available | `result.metrics["niirs"]` — CLOSED |
| GSD metric | Not available | `result.metrics["gsd_geometric_mean_m"]` — CLOSED |
| Strehl ratio | Not available | `result.metrics["strehl"]` — CLOSED |
| Q parameter | Not available | `result.metrics["q_center"]` — CLOSED |
| MTF budget | Not available | `mtf_budget.per_term_at_nyquist` — CLOSED |
| Well margin | Not available | `result.metrics["well_margin_dB"]` — CLOSED |
