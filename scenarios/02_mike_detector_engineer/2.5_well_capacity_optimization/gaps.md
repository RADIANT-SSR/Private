# Scenario 2.5 Gaps: Well Capacity Optimization

## Summary
200–1500 K scene dynamic range is physically impossible in a single frame.
SNR ≥ 10 on 200 K requires t_int ≥ 1.82 ms.
At t_int = 1 ms, max scene temperature staying below 90% well fill is 300 K.
Cold-target (200 K) noise is background-shot dominated (98.5% of variance).

## Gap Closure Status

| # | Gap | Severity | Status | Evidence |
|---|-----|----------|--------|----------|
| 1 | No HDR / dual-integration mode | Medium | Open | No built-in dual-t_int combination |
| 2 | Well fill excludes background/nearfield/dark | Medium | Open | RADIANT clips `signal_e` at FWC; total well charge not tracked |
| 3 | No saturation map output | Low | **PARTIALLY CLOSED** | `result.metrics["well_margin_dB"]` exposed; no per-pixel map |
| 4 | No automatic trade study support | Low | Open | 500 evaluations run manually |
| 5 | No NEDT-at-saturation warning | Low | Open | At FWC, dS/dT = 0 ⇒ NEDT → ∞ silently |
| 6 | No spectral narrowing analysis | Low | Open | No band-optimization mode |
| 7 | **NEW — Nearfield emission = 0 in scalar transmission mode** | **HIGH** | Open | Mirror self-emission from warm optics not modeled; noise under-predicted for cold targets |

## Gap 7 Detail — Nearfield Emission Missing (HIGH)

### Observation
At 200 K target in this configuration (MWIR, 4 warm optical elements at 293 K):
```
background_shot:  696.0 e⁻ RMS (98.5%)
nearfield_shot:   0.00 e⁻ RMS (0.0%)  ← should be non-zero
```

### Expected Behavior
With 4 optical elements at 293 K and ε ≈ 0.02 per surface (for aluminum mirrors), the MWIR photon flux per element should contribute several hundred e⁻ per ms of integration. Total nearfield shot noise of ~300–450 e⁻ RMS would be expected.

### Root Cause
Scalar transmission mode lumps all optical elements into a single τ and applies Kirchhoff's law for a **refractive** element (ε = 1 − T − R). Mirrors follow ε = 1 − R, not ε = 1 − T − R. In scalar mode the emissivity evaluates to zero.

### Impact
- Cold targets (<300 K) under-predict noise by 30–40% in warm-optics MWIR
- The 1.82 ms minimum-t_int result is slightly optimistic (real system needs more t_int to overcome larger actual noise)
- Cold stop trade studies (scenario 7.4) completely non-functional in scalar mode

### Workarounds
- Use `optics.mode: "key_elements"` with per-surface ε from R
- Use `optics.mode: "full_prescription"` for Zemax-exported designs

## Non-Gap Observations

- 200–1500 K dynamic range (>6 orders of magnitude in MWIR flux) cannot be captured in a single frame on a 2 M e⁻ well — this is a fundamental radiometric constraint, not a RADIANT limitation.
- BLIP regime at 200 K correctly identified (signal_shot 1.1% vs background_shot 98.5%).
- Signal-limited regime at 400 K correctly identified (signal_shot 80.4%).

## Drift Fix 2026-07-07 — Stage-7 h_sensor precondition (registry Gap 42)

The script raised in `validate_no_atmosphere_subcase` after the Stage-7
landing: `atmosphere.model = "exo"` auto-infers the `no_atmosphere / space`
sub-case, which requires a positive user-set `platform.h_sensor` for the
Earth-limb intercept check (the `lab_test` sub-case has no `Sensor.from_dict`
path — registry Gap 42). Fixed in the Phase R sweep pass by adding the
placeholder `platform.h_sensor = 1.0` m (bench height); no radiometric
effect. Remove the placeholder when Gap 42 lands a first-class lab path.
