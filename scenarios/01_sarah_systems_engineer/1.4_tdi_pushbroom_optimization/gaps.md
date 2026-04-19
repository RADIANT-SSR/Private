# Scenario 1.4 Gaps: TDI Pushbroom Optimization

## Summary
System: 25 cm aperture, f/10, 7 um pitch VNIR pan, 500 km SSO; GSD = 1.40 m, Q = 0.964, line period = 0.2013 ms.
Peak NIIRS = 5.81 at N_tdi = 16 (83% well fill); SNR scales as √N until saturation at N_tdi ≈ 19.
Below saturation SNR grows as √N (shot-limited); above, signal clips at FWC while background shot keeps growing, so SNR decreases.

## Gap Closure Status

| # | Gap | Severity | Status | Evidence |
|---|-----|----------|--------|----------|
| 1 | Smear MTF not applied inside ChainRunner | Medium | Open | `platform/smear.py` exists but PlatformStage still doesn't convolve motion smear into ePSF; walkthrough applies it analytically |
| 2 | No orbital-velocity → line-period calculator | Low | Open | Script computes ground velocity and line period manually; no built-in module |
| 3 | No automatic saturation warning during N_tdi sweep | Low | Open | Signal clips at FWC silently; user must inspect well-fill column |
| 4 | TDI misalignment MTF not in chain | Medium | Open | `readout/tdi.py` provides helpers but misalignment kernel is never convolved into ePSF |
| 5 | No effective integration time output | Low | Open | No `result.metrics["t_int_effective_s"]` exposing N_tdi × line_period |

## Non-Gap Observations
- SNR scaling is exactly √N within the unsaturated regime (1.00, 1.41, 2.00, 2.83, 4.00 at N=1,2,4,8,16), confirming shot-noise-limited operation with analog TDI (read noise fixed at 15 e⁻).
- MTF_opt is constant at 0.1821 across the sweep — N_tdi does not change optical or detector MTF.
- Smear MTF at Nyquist is 2/π = 0.6366 regardless of N_tdi (1 pixel/line smear inherent to pushbroom operation).
- RER is 0.4790 across the full sweep because the RADIANT ePSF does not yet include smear or misalignment kernels.
- The saturation cliff is sharp: N_tdi = 16 yields peak NIIRS = 5.81 at 83% fill; N_tdi = 32 saturates and NIIRS falls to 5.78 and continues declining.
