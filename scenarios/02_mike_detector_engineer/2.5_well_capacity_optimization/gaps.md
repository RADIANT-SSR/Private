# Scenario 2.5 Gaps: Well Capacity Optimization

## Summary
200–1500 K scene dynamic range is physically impossible in a single frame.
SNR ≥ 10 on 200 K requires t_int ≥ 103.2 µs.
At t_int = 1 ms, max scene temperature staying below 90% well fill is 300 K.
Cold-target (200 K) noise at 1 ms is signal-shot dominated (75.2% of variance),
but with a material ROIC floor — quantization 19.3% and read noise 5.5%.
There is no separate `background_shot` line: the extended regime carries the
whole-FOV radiance in `signal_shot` (ADR-0002 Decision #13).

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage 2026-04-19). Dominant mover: the extended-regime consolidation of `background_shot` into `signal_shot` (ADR-0002 Decision #13), which predates the CU-317 attribution window (that table begins 2026-07-16). No in-window Results-affecting landing applies — this bench is `atmosphere.model = "exo"`, which CU-224, CU-267 and CU-253 all exclude by their own scope statements.*

## Gap Closure Status

| # | Gap | Severity | Status | Evidence |
|---|-----|----------|--------|----------|
| 1 | No HDR / dual-integration mode | Medium | OPEN | No built-in dual-t_int combination — **CU-387 triage 2026-09-30: promoted to [[Gap 138]]** (HDR / dual-integration mode). |
| 2 | Well fill excludes background/nearfield/dark | Medium | FIXED | RADIANT clips `signal_e` at FWC; total well charge not tracked — **CU-387 triage 2026-09-30: verified FIXED.** `readout.total_well_e` tracks the full pedestal — signal + dark + glow + near-field + stray — and the saturation warning reports it (20 references in `readout/stage.py`). |
| 3 | No saturation map output | Low | **PARTIALLY CLOSED** | `result.metrics["well_margin_dB"]` exposed; no per-pixel map |
| 4 | No automatic trade study support | Low | FIXED | 500 evaluations run manually — **CU-387 triage 2026-09-30: verified FIXED.** `Sensor.sweep`, `sweep_2d`, `solve_for`, `sensitivity`, `monte_carlo` and `tolerances` all exist on the public API; the 500 manual evaluations this row describes are now one `sweep_2d` call. |
| 5 | No NEDT-at-saturation warning | Low | OPEN | At FWC, dS/dT = 0 ⇒ NEDT → ∞ silently — **CU-387 triage 2026-09-30: stays open, Findings-Log tier.** Saturation *is* warned generally (well, ADC, and a performance-stage clipped-signal advisory naming `contrast_snr` as unreliable); what is absent is the NEDT-specific statement that dS/dT -> 0 at the well. Fails all four CU intake tests. |
| 6 | No spectral narrowing analysis | Low | OPEN | No band-optimization mode — **CU-387 triage 2026-09-30: stays open, Findings-Log tier** (a band-optimization mode; no result moves, nothing blocked). |
| 7 | **NEW — Nearfield emission = 0 in scalar transmission mode** | **HIGH** | FIXED | Mirror self-emission from warm optics not modeled; noise under-predicted for cold targets — **CU-387 triage 2026-09-30: superseded by [[CU-380]]** — one of the five independent recordings of the same defect. Warm train for this scenario is CU-380's open item. |

## Gap 7 Detail — Nearfield Emission Missing (HIGH)

### Observation
At 200 K target in this configuration (MWIR, 4 warm optical elements at 293 K),
the whole reported noise budget at t_int = 1 ms is:
```
signal_shot:       74.0 e⁻ RMS (75.2%)
quantization:      37.5 e⁻ RMS (19.3%)
read_noise:        20.0 e⁻ RMS ( 5.5%)
dark_shot:          0.3 e⁻ RMS ( 0.0%)
nearfield_shot:    0.00 e⁻ RMS ( 0.0%)  ← should be non-zero
                  ─────────────────────
RSS TOTAL:         85.3 e⁻ RMS
```
The warm-optics contribution is absent from an 85.3 e⁻ RMS total, so the
omission is proportionally far larger than the old budget suggested.

### Expected Behavior
With 4 optical elements at 293 K and ε ≈ 0.02 per surface (for aluminum mirrors), the MWIR photon flux per element should contribute several hundred e⁻ per ms of integration. Total nearfield shot noise of ~300–450 e⁻ RMS would be expected.

### Root Cause
Scalar transmission mode lumps all optical elements into a single τ and applies Kirchhoff's law for a **refractive** element (ε = 1 − T − R). Mirrors follow ε = 1 − R, not ε = 1 − T − R. In scalar mode the emissivity evaluates to zero.

### Impact
- Cold targets (<300 K) under-predict noise in warm-optics MWIR. Against the
  current 85.3 e⁻ RMS total at 200 K / 1 ms, an expected ~300–450 e⁻ RMS
  nearfield term would be the *dominant* contributor, not a 30–40% correction —
  the impact is far larger than previously recorded.
- The 103.2 µs minimum-t_int result is correspondingly optimistic (a real
  system needs more t_int to overcome the larger actual noise)
- Cold stop trade studies (scenario 7.4) completely non-functional in scalar mode

### Workarounds
- Use `optics.mode: "key_elements"` with per-surface ε from R
- Use `optics.mode: "full_prescription"` for Zemax-exported designs

## Non-Gap Observations

- 200–1500 K dynamic range (>6 orders of magnitude in MWIR flux) cannot be captured in a single frame on a 2 M e⁻ well — this is a fundamental radiometric constraint, not a RADIANT limitation.
- Both temperatures are signal-shot limited as reported, but by very different
  margins: signal_shot is 75.2% of the variance at 200 K and 99.9% at 400 K.
  The cold end is where the ROIC floor (quantization + read = 24.8%) still
  matters — which is exactly where the missing nearfield term (Gap 7) would land.
- Signal-limited regime at 400 K correctly identified (signal_shot 99.9%), with
  the well clipped at 2,000,000 e⁻ (100.0% fill) at t_int = 1 ms.

## Drift Fix 2026-07-07 — Stage-7 h_sensor precondition (registry Gap 42)

The script raised in `validate_no_atmosphere_subcase` after the Stage-7
landing: `atmosphere.model = "exo"` auto-infers the `no_atmosphere / space`
sub-case, which requires a positive user-set `platform.h_sensor` for the
Earth-limb intercept check (the `lab_test` sub-case has no `Sensor.from_dict`
path — registry Gap 42). Fixed in the Phase R sweep pass by adding the
placeholder `platform.h_sensor = 1.0` m (bench height); no radiometric
effect. Remove the placeholder when Gap 42 lands a first-class lab path.
