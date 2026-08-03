# Scenario 5.4 Gaps: Jitter Tolerance

## Summary
System: 50 cm aperture, f/10, 8 um pixel, 500 km SSO VNIR pan; Q = 0.72 (undersampled), GSD = 0.80 m.
Baseline (0 jitter): MTF@Nyq = 0.2330, RER = 0.5483, NIIRS = 6.17, SNR = 61.4.
Jitter thresholds: dNIIRS = -0.5 at 0.9 urad; dNIIRS = -1.0 at 1.7 urad; NIIRS = 6.0 floor at 0.5 urad.
SNR is invariant (spread = 0.0000) — NIIRS degradation enters entirely through the RER term.

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-07-07 — this file was missed by the 2026-07-22 walkthrough refresh, so it
carried two vintages of drift). Dominant mover: CU-253 — the 8×-too-large
Rayleigh optical depth, which halved `E_sky_scattered` and took SNR 68.7 → 61.4
across the two refreshes (−34 % on the 2026-07-22 baseline of 93.0). The
NIIRS = 6.0 floor tightened from 0.6 to 0.5 urad because the zero-jitter NIIRS
fell to 6.17; the two relative dNIIRS thresholds are unmoved.*

## Gap Closure Status

| # | Gap | Severity | Status | Evidence |
|---|-----|----------|--------|----------|
| — | Platform jitter not wired (master Gap 18) | High | **CLOSED** | `platform.jitter_rms_urad` ingested by PlatformStage; ePSF convolution confirmed |
| 1 | No MTF budget decomposition | Medium | **CLOSED** | `result.stage_outputs["performance"]["mtf_budget"].per_term_at_nyquist` exposes per-contributor MTF |
| 2 | No GIQE-5 sensitivity analysis | Low | Open | No d(NIIRS)/d(parameter) utility; designers must compute by finite differences |
| 3 | No jitter PSD / frequency dependence | Large | Open | Assumes well-sampled stationary jitter; no partition between in-band blur and out-of-band frame shift |
| 4 | RER below GIQE-5 calibration range | Low | Open | For jitter > 2.5 urad, RER < 0.2 is extrapolation; warning raised but results reported |
| 5 | No jitter-source allocation tool | Medium | Open | No RSS budget utility for RW / solar / cryo / struct / ACS contributors |

## Non-Gap Observations
- SNR is exactly 61.45 across all 51 sweep points — confirms jitter spreads light but doesn't change photon counts or noise.
- Full ePSF convolution gives ~15–20% tighter jitter thresholds than the legacy Gaussian-PSF erfinv approach because the real PSF has Airy-ring and IPC tails the Gaussian model missed.
- At 1 urad jitter (0.625 pix), MTF@Nyq collapses from 0.2330 to 0.0339 (85% reduction) because the jitter MTF at Nyquist is exp(-2pi²·0.625²) = 0.1455 on top of the already-low Q=0.72 baseline.
