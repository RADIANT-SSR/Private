# Scenario 5.4 Walkthrough: Jitter Tolerance — Line-of-Sight Stability Requirements

## Persona
Tom, optical designer. He has designed a VNIR panchromatic imager (50 cm aperture, f/10, 8 um Si CCD) for a 500 km SSO and needs to derive the jitter requirement. How much line-of-sight wander can the spacecraft allow before image quality degrades unacceptably?

## System Configuration
| Parameter | Value | Unit |
|---|---|---|
| Aperture diameter | 50 | cm |
| Focal length | 500 | cm |
| f-number | 10.0 | -- |
| Optical transmission | 70 | % |
| Optics temperature | 20 | C |
| WFE RMS | 0.05 | waves |
| Central obscuration | 30 | % |
| Pixel pitch | 8.0 | um |
| QE | 85 | % |
| Dark current | 5.0 | e-/s |
| Read noise | 5.0 | e- RMS |
| FWC | 100,000 | e- |
| Integration time | 0.5 | ms |
| Band | 450--700 | nm |
| Orbit altitude | 500 | km |
| Target reflectance | 0.15 | -- |
| Background reflectance | 0.10 | -- |
| Solar zenith angle | 30 | deg |
| GSD | 0.80 | m |
| Q (sampling) | 0.72 | -- (undersampled) |
| IFOV | 1.6 | urad |
| Airy disk | 14.0 | um (1.75 pixels) |

## Approach
The script runs the full RADIANT signal chain at each jitter level using the built-in PlatformStage. The `platform.jitter_rms_urad` parameter feeds into PlatformStage, which convolves a Gaussian jitter kernel into the EffectivePSF. PerformanceStage then computes MTF, RER, and NIIRS from the jitter-degraded PSF.

This is more accurate than the analytic erfinv/erf approach used in the first version of this scenario, because the full ePSF convolution captures the non-Gaussian tails of the Airy PSF (diffraction rings). The analytic approach assumed a purely Gaussian PSF shape, which underestimated the jitter sensitivity.

## Trade Study Design
- **Jitter sweep**: 0--5.0 urad (51 points, linear)
- **Thresholds**: delta_NIIRS = -0.5, delta_NIIRS = -1.0, NIIRS = 6.0 floor
- **Total evaluations**: 51 full RADIANT chain evaluations

## Baseline Results (Zero Jitter)
| Parameter | Value | Unit |
|---|---|---|
| Signal | 2,109 | e- (2.1% well) |
| Total noise | 46.2 | e- RMS |
| SNR | 45.6 | -- |
| MTF@Nyquist | 0.2330 | -- |
| RER | 0.5483 | -- |
| NIIRS | 5.97 | -- |

*Numbers refreshed 2026-09-01 from the unmodified runner (previous vintage
2026-08-30). Sole mover: **CU-336** — the same fit's grid convention was
corrected, so the two floors come down to 0.1375 and 0.0402 and this VNIR scene
gains a little τ back. **SNR 44.6 → 45.6 (+2.2 %)**, signal 2,020 → 2,109 e⁻,
NIIRS 5.97 at zero jitter (was 5.96). Every spatial metric (MTF@Nyquist, RER,
jitter MTF, σ_fp) is bit-identical — jitter physics did not move, and the ΔNIIRS
column is unchanged at every sweep point. **The CU-335 verdict stands**: the
NIIRS = 6.0 floor is still unreachable at any jitter, the baseline reaching only
5.97 (see below).*

*Prior vintage, 2026-08-30. **CU-335** put those two floors on the table for the
first time (0.1597 / 0.0517): SNR 61.4 → 44.6 (−27 %), signal
3,804 → 2,020 e⁻, NIIRS 6.17 → 5.96 at zero jitter, and that is the change that
put the NIIRS = 6.0 floor out of reach.*

*Prior vintage, for the trend: the 2026-08-02 refresh was dominated by CU-253 —
the Rayleigh optical depth was 8× too
large, halving `E_sky_scattered` and taking this VNIR scene's SNR 93.0 → 61.4
(−34 %), exactly the figure the CU-253 CHANGELOG entry names for 5.4. NIIRS
follows through the GIQE-5 SNR term. Every spatial metric (MTF@Nyquist, RER,
jitter MTF, σ_fp) was unchanged — jitter physics did not move.*

### Noise Budget
| Noise Term | sigma [e- RMS] | Fraction [%] |
|---|---|---|
| signal_shot | 44.9 | 98.6 |
| read_noise | 5.0 | 0.7 |
| quantization | 1.9 | 0.1 |
| dark_shot | 0.1 | 0.0 |

Signal shot noise dominates almost entirely. There is **no separate background_shot term** — the extended scene is one radiance field, so its shot noise is `signal_shot` alone (ADR-0002 Decision #13). This is a photon-noise-limited system where read noise is negligible.

## Key Results

### SNR Invariance
SNR is exactly 45.6 [--] at every sweep point (spread = 0.0000). This confirms the fundamental physics: jitter blurs the image but doesn't affect photon counts or noise. NIIRS degrades entirely through the RER term.

### Jitter Sweep
| Jitter [urad] | sigma_fp [pixels] | MTF_jitter@Nyq [--] | MTF_sys@Nyq [--] | RER [--] | NIIRS [--] | delta_NIIRS [--] |
|---|---|---|---|---|---|---|
| 0.0 | 0.000 | 1.0000 | 0.2330 | 0.5483 | 5.97 | +0.00 |
| 0.2 | 0.125 | 0.9258 | 0.2157 | 0.5359 | 5.94 | -0.03 |
| 0.6 | 0.375 | 0.4996 | 0.1164 | 0.4614 | 5.72 | -0.25 |
| 0.8 | 0.500 | 0.2912 | 0.0679 | 0.4178 | 5.58 | -0.39 |
| 1.0 | 0.625 | 0.1455 | 0.0339 | 0.3773 | 5.43 | -0.54 |
| 1.6 | 1.000 | 0.0072 | 0.0017 | 0.2838 | 5.02 | -0.95 |
| 2.0 | 1.250 | 0.0004 | 0.0001 | 0.2409 | 4.79 | -1.19 |
| 3.0 | 1.875 | 0.0000 | 0.0000 | 0.1730 | 4.31 | -1.66 |
| 5.0 | 3.125 | 0.0000 | 0.0000 | 0.1097 | 3.65 | -2.32 |

At jitter ≥ ~2.6 µrad the RER falls below 0.20 — outside the GIQE-5 calibration
envelope — so the NIIRS values in the tail are the **extrapolated** GIQE-5-form
output (`performance.niirs.allow_extrapolated = true`, CU-178); read them as a
relative degradation trend, not a calibrated rating.

### Jitter Budget Thresholds
| Threshold | Jitter [urad] | sigma_fp [um] | sigma_fp [pixels] |
|---|---|---|---|
| delta_NIIRS = -0.5 | 0.9 | 4.7 | 0.59 |
| delta_NIIRS = -1.0 | 1.7 | 8.4 | 1.05 |
| NIIRS = 6.0 floor | not reachable | — | — |

**The NIIRS = 6.0 floor is no longer reachable at any jitter.** CU-253 lowered
the zero-jitter NIIRS 6.45 → 6.17, CU-335 took it to 5.96 and CU-336 to 5.97, which is below the
floor with the optics perfectly stable — so the runner now reports "floor not
reached in sweep range" where it previously reported a 0.5 µrad jitter budget.
The design's shortfall is radiometric, not a pointing problem: at this signal
level no jitter specification recovers the grade, and the fix is aperture,
integration time or band, not stability. The two ΔNIIRS thresholds are relative
and therefore unmoved.

### Jitter in Context
| Jitter [urad] | Fraction of IFOV | sigma_fp [pixels] | MTF@Nyq [--] | delta_NIIRS [--] |
|---|---|---|---|---|
| 0.2 | 0.13 | 0.125 | 0.2157 | -0.03 |
| 0.5 | 0.31 | 0.312 | 0.1439 | -0.18 |
| 1.0 | 0.62 | 0.625 | 0.0339 | -0.54 |
| 1.6 (= 1 IFOV) | 1.00 | 1.000 | 0.0017 | -0.95 |
| 2.0 | 1.25 | 1.250 | 0.0001 | -1.19 |
| 3.0 | 1.88 | 1.875 | 0.0000 | -1.66 |
| 5.0 | 3.13 | 3.125 | 0.0000 | -2.32 |

### Comparison: Full-Chain vs. Analytic Approach
The first version of this scenario used an analytic approach (single RADIANT run + erfinv/erf RER approximation). The full-chain approach yields tighter (more conservative) thresholds:

| Metric | Analytic (old) | Full-chain (new) | Difference |
|---|---|---|---|
| dNIIRS = -0.5 threshold | 1.0 urad | 0.9 urad | -10% (more conservative) |
| dNIIRS = -1.0 threshold | 1.7 urad | 1.7 urad | same |
| RER at 1.0 urad | 0.4564 | 0.3773 | -17% |
| RER at 2.0 urad | 0.2869 | 0.2409 | -16% |

The analytic approach assumed a purely Gaussian PSF shape when inverting the baseline RER. The real PSF has Airy rings (diffraction) and IPC coupling, making it wider in the tails than a Gaussian. The full ePSF convolution captures this, producing a lower RER for the same jitter — and thus tighter jitter requirements.

**Lesson**: For jitter tolerance derivation, always use the full ePSF convolution. The Gaussian approximation is useful for quick estimates but overestimates the jitter budget by ~20%.

## Physics Discussion

### Why This Sensor Is So Jitter-Sensitive
The 5.0 m focal length amplifies angular jitter enormously on the focal plane:
- sigma_fp = jitter_rms [rad] x focal_length [m]
- At 1 urad jitter: sigma_fp = 1e-6 x 5.0 = 5 um = 0.625 pixels
- At 2 urad jitter: sigma_fp = 10 um = 1.25 pixels

This is a fundamental consequence of long-focal-length design. The same 1 urad jitter on a shorter focal length (e.g., 1.2 m for the MWIR sensor in Scenario 3.2) would produce only 1.2 um = 0.067 pixels of blur -- barely noticeable.

**Design trade-off**: Long focal length gives small GSD (0.80 m) and high spatial resolution, but demands extremely tight pointing stability. This is the central tension in high-resolution EO satellite design.

### How Jitter Degrades Image Quality
1. **Jitter MTF**: MTF_jitter(f) = exp(-2 pi^2 sigma^2 f^2). This is a Gaussian low-pass filter. It kills high spatial frequencies exponentially. By 1 IFOV of jitter (1.6 urad), the jitter MTF at Nyquist is only 0.007 -- essentially zero high-frequency content survives.

2. **System MTF**: The total system MTF is the product of all MTF contributors. The baseline system MTF at Nyquist is 0.2330 (from optics + detector + aberrations). At 1 urad jitter, the system MTF drops to 0.0339 -- an 85% reduction.

3. **RER (Relative Edge Response)**: RER measures how sharp edges appear. Baseline RER = 0.548; at 1 urad jitter, RER drops to 0.377 (computed via full ePSF convolution, not the Gaussian approximation).

4. **NIIRS impact**: NIIRS depends on RER through +3.32 x log10(RER). When RER drops from 0.548 to 0.377, NIIRS drops by 0.54 -- more than half a grade. The RER term has the same coefficient magnitude as the GSD term, so RER degradation is as significant as GSD degradation.

### Why Jitter Doesn't Affect SNR
Jitter is random pointing wander during the integration time. It spreads the image of a point source over a larger area, but:
- The same number of photons still reach the detector (no absorption or scattering)
- The noise floor (shot noise, read noise, dark current) is unchanged
- For extended scenes (which GIQE-5 assumes), the average signal per pixel is unchanged
- Therefore SNR (for extended-scene NIIRS) is unaffected by jitter

The script explicitly verified this: SNR is 45.62 at every one of the 51 sweep points, spread exactly 0.0000.

**Caveat**: For point-source detection, jitter does reduce per-pixel SNR because it spreads the PSF. This analysis is specific to the GIQE-5/NIIRS regime which assumes extended targets.

### The Undersampling Challenge
This system has Q = 0.72 (undersampled). The Airy disk (14 um) is 1.75 pixels across, so the optics deliver more resolution than the detector can capture. This means:
- The baseline MTF at Nyquist (0.2330) is already limited by the pixel aperture
- There is aliased energy beyond Nyquist
- Jitter actually reduces aliasing (by killing high frequencies before they alias), but this doesn't help because the GIQE-5 equation uses the system MTF at Nyquist, not aliased MTF

### Jitter Budget Allocation
The total jitter from all sources adds in quadrature (RSS):

sigma_total^2 = sigma_RW^2 + sigma_solar^2 + sigma_cryo^2 + sigma_struct^2 + sigma_ACS^2

For sigma_total <= 0.9 urad (the dNIIRS = -0.5 threshold):
- If 5 sources contribute equally: each gets sqrt(0.9^2 / 5) = 0.40 urad
- Rule of thumb: dominant source gets ~60% of budget, others share the rest
- Reaction wheel balance (1--5 urad typical) is the biggest risk -- isolators or low-disturbance wheels are essential
- ACS residual (0.5--5 urad typical) is the second risk -- requires high-bandwidth star tracker + gyro loop

## Gap Findings

### Gap 1: No MTF Budget Decomposition
RADIANT computes a system MTF but doesn't decompose it into individual contributors (optics, detector, jitter, smear, etc.) in a way that's easy to inspect. An MTF budget table showing each contributor's MTF at Nyquist would be valuable for optical designers like Tom.

### Gap 2: No GIQE-5 Sensitivity Analysis
The GIQE-5 equation has terms for GSD, RER, SNR, H, and G. A built-in sensitivity analysis showing d(NIIRS)/d(parameter) for each would help designers understand which parameter to improve. In this case, d(NIIRS)/d(RER) = 3.32 / (RER x ln(10)) -- very steep near the baseline RER.

### Gap 3: No Jitter-Frequency Dependence
This analysis assumes "well-sampled" jitter (many cycles during integration). Real jitter has a power spectral density (PSD). Low-frequency jitter (< 1/t_int) produces pointing error (frame shift), not blur. RADIANT should accept a jitter PSD and compute the in-band blur vs. out-of-band pointing error partition.

### Gap 4: RER Below GIQE-5 Calibration Range
At moderate jitter (>2.5 urad), RER drops below 0.2 which is outside the GIQE-5 calibration range. RADIANT prints warnings but continues computing. The GIQE-5 results at very low RER should be flagged as extrapolations with reduced confidence.

### Gap 5: No Jitter-Source Allocation Tool
The script mentions RSS allocation of jitter budget across sources, but RADIANT doesn't have a tool to help allocate and track jitter budgets across multiple contributors. An "error budget table" feature would be valuable.
