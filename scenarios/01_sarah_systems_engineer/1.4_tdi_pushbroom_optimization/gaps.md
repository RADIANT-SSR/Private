# Scenario 1.4 Gaps: TDI Pushbroom Optimization

## Summary
System: 25 cm aperture, f/10, 7 um pitch VNIR pan, 500 km SSO; GSD = 1.40 m, Q = 0.964, line period = 0.2013 ms.
Peak NIIRS = 6.13 at N_tdi = 64 (100% well fill); SNR scales as √N until saturation at N_tdi ≈ 38.
Below saturation SNR grows as √N (shot-limited); above, signal clips at FWC while background shot keeps growing, so SNR decreases.

## Gap Closure Status

| # | Gap | Severity | Status | Evidence |
|---|-----|----------|--------|----------|
| 1 | Smear MTF not applied inside ChainRunner | Medium | FIXED | `platform/smear.py` exists but PlatformStage still doesn't convolve motion smear into ePSF; walkthrough applies it analytically — **CU-387 triage 2026-09-30: verified FIXED.** `PlatformStage` convolves motion smear into the ePSF and publishes the smear MTF (72 references in `platform/stage.py`); the row predates that landing. |
| 2 | No orbital-velocity → line-period calculator | Low | OPEN | Script computes ground velocity and line period manually; no built-in module — **CU-387 triage 2026-09-30: stays open, Findings-Log tier** (fails all four Rule-21 CU intake tests — a convenience calculator, no result moves). Logged in `docs/tracking/Findings_Log.md`. |
| 3 | No automatic saturation warning during N_tdi sweep | Low | FIXED | Signal clips at FWC silently; user must inspect well-fill column — **CU-387 triage 2026-09-30: verified FIXED.** `ReadoutStage` warns on both well and ADC saturation, naming the fill fraction and the remedy. |
| 4 | TDI misalignment MTF not in chain | Medium | FIXED | `readout/tdi.py` provides helpers but misalignment kernel is never convolved into ePSF — **CU-387 triage 2026-09-30: verified FIXED — and by design.** TDI mis-registration is the one deliberate MTF-only term (CLAUDE.md Rule 4): it is a readout-timing effect with no spatial kernel, so it enters the MTF product and is excluded from the dual-path consistency check. It is not missing from the ePSF; it never belonged there. |
| 5 | No effective integration time output | Low | OPEN | No `result.metrics["t_int_effective_s"]` exposing N_tdi × line_period — **CU-387 triage 2026-09-30: folded into [[Gap 134]]** (echo derived and converted quantities) — `t_int_effective = N_tdi x line_period` is exactly the class of computed value Gap 134 exists to surface. |

## Non-Gap Observations
- SNR scaling tracks √N within the unsaturated regime (1.00, 1.46, 2.10, 3.00, 4.26 at N=1,2,4,8,16 against √N = 1.00, 1.41, 2.00, 2.83, 4.00), confirming shot-noise-limited operation with analog TDI (read noise fixed at 15 e⁻); it runs slightly *above* √N because the fixed 15 e⁻ read-noise floor matters less as the signal grows.
- MTF_opt is constant at 0.1962 across the sweep — N_tdi does not change optical or detector MTF.
- Smear MTF at Nyquist is 2/π = 0.6366 regardless of N_tdi (1 pixel/line smear inherent to pushbroom operation).
- RER is 0.4884 across the full sweep because the RADIANT ePSF does not yet include smear or misalignment kernels.
- Saturation is a plateau, not a cliff: N_tdi = 32 runs at 84.5% fill (NIIRS 6.08), N_tdi = 64 first clips at FWC, and NIIRS then holds flat at 6.13 for all higher stages — because this extended reflective scene has no separable background term, the noise stops growing when the signal does.
*(Numbers refreshed 2026-08-02 from the unmodified runner; see walkthrough.md for the CU-253 attribution.)*

- 2026-09-06 (calibration variant): CU-346 — v1 Planck cal-point mapping anchors to the declared target temperature on this reflective scene; stand-in semantics documented in the variant script and walkthrough.
