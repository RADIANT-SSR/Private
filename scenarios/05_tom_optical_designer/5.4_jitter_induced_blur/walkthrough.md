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
| Signal | 9,463 | e- (9.5% well) |
| Total noise | 137.7 | e- RMS |
| SNR | 68.7 | -- |
| MTF@Nyquist | 0.2409 | -- |
| RER | 0.5547 | -- |
| NIIRS | 6.27 | -- |

### Noise Budget
| Noise Term | sigma [e- RMS] | Fraction [%] |
|---|---|---|
| signal_shot | 97.3 | 49.9 |
| background_shot | 97.3 | 49.9 |
| read_noise | 5.0 | 0.1 |
| quantization | 1.9 | 0.0 |
| dark_shot | 0.1 | 0.0 |

Signal and background shot noise dominate equally. This is a photon-noise-limited system where read noise is negligible.

## Key Results

### SNR Invariance
SNR is exactly 68.73 [--] at every sweep point (spread = 0.0000). This confirms the fundamental physics: jitter blurs the image but doesn't affect photon counts or noise. NIIRS degrades entirely through the RER term.

### Jitter Sweep
| Jitter [urad] | sigma_fp [pixels] | MTF_jitter@Nyq [--] | MTF_sys@Nyq [--] | RER [--] | NIIRS [--] | delta_NIIRS [--] |
|---|---|---|---|---|---|---|
| 0.0 | 0.000 | 1.0000 | 0.2409 | 0.5547 | 6.27 | +0.00 |
| 0.2 | 0.125 | 0.9258 | 0.2230 | 0.5420 | 6.23 | -0.03 |
| 0.5 | 0.312 | 0.6176 | 0.1488 | 0.4878 | 6.08 | -0.19 |
| 0.8 | 0.500 | 0.2912 | 0.0702 | 0.4209 | 5.87 | -0.40 |
| 1.0 | 0.625 | 0.1455 | 0.0351 | 0.3797 | 5.72 | -0.55 |
| 1.6 | 1.000 | 0.0072 | 0.0017 | 0.2848 | 5.31 | -0.96 |
| 2.0 | 1.250 | 0.0004 | 0.0001 | 0.2416 | 5.07 | -1.20 |
| 3.0 | 1.875 | 0.0000 | 0.0000 | 0.1733 | 4.59 | -1.68 |
| 5.0 | 3.125 | 0.0000 | 0.0000 | 0.1098 | 3.93 | -2.34 |

### Jitter Budget Thresholds
| Threshold | Jitter [urad] | sigma_fp [um] | sigma_fp [pixels] |
|---|---|---|---|
| delta_NIIRS = -0.5 | 0.9 | 4.7 | 0.59 |
| delta_NIIRS = -1.0 | 1.7 | 8.3 | 1.04 |
| NIIRS = 6.0 floor | 0.6 | 3.1 | 0.39 |

### Jitter in Context
| Jitter [urad] | Fraction of IFOV | sigma_fp [pixels] | MTF@Nyq [--] | delta_NIIRS [--] |
|---|---|---|---|---|
| 0.2 | 0.13 | 0.125 | 0.2230 | -0.03 |
| 0.5 | 0.31 | 0.312 | 0.1488 | -0.19 |
| 1.0 | 0.62 | 0.625 | 0.0351 | -0.55 |
| 1.6 (= 1 IFOV) | 1.00 | 1.000 | 0.0017 | -0.96 |
| 2.0 | 1.25 | 1.250 | 0.0001 | -1.20 |
| 3.0 | 1.88 | 1.875 | 0.0000 | -1.68 |
| 5.0 | 3.13 | 3.125 | 0.0000 | -2.34 |

### Comparison: Full-Chain vs. Analytic Approach
The first version of this scenario used an analytic approach (single RADIANT run + erfinv/erf RER approximation). The full-chain approach yields tighter (more conservative) thresholds:

| Metric | Analytic (old) | Full-chain (new) | Difference |
|---|---|---|---|
| dNIIRS = -0.5 threshold | 1.0 urad | 0.9 urad | -10% (more conservative) |
| dNIIRS = -1.0 threshold | 1.7 urad | 1.7 urad | same |
| RER at 1.0 urad | 0.4564 | 0.3797 | -17% |
| RER at 2.0 urad | 0.2869 | 0.2416 | -16% |

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

2. **System MTF**: The total system MTF is the product of all MTF contributors. The baseline system MTF at Nyquist is 0.241 (from optics + detector + aberrations). At 1 urad jitter, the system MTF drops to 0.035 -- an 85% reduction.

3. **RER (Relative Edge Response)**: RER measures how sharp edges appear. Baseline RER = 0.555; at 1 urad jitter, RER drops to 0.380 (computed via full ePSF convolution, not the Gaussian approximation).

4. **NIIRS impact**: NIIRS depends on RER through +3.32 x log10(RER). When RER drops from 0.555 to 0.380, NIIRS drops by 0.55 -- more than half a grade. The RER term has the same coefficient magnitude as the GSD term, so RER degradation is as significant as GSD degradation.

### Why Jitter Doesn't Affect SNR
Jitter is random pointing wander during the integration time. It spreads the image of a point source over a larger area, but:
- The same number of photons still reach the detector (no absorption or scattering)
- The noise floor (shot noise, read noise, dark current) is unchanged
- For extended scenes (which GIQE-5 assumes), the average signal per pixel is unchanged
- Therefore SNR (for extended-scene NIIRS) is unaffected by jitter

The script explicitly verified this: SNR spread across all 51 sweep points is exactly 0.0000.

**Caveat**: For point-source detection, jitter does reduce per-pixel SNR because it spreads the PSF. This analysis is specific to the GIQE-5/NIIRS regime which assumes extended targets.

### The Undersampling Challenge
This system has Q = 0.72 (undersampled). The Airy disk (14 um) is 1.75 pixels across, so the optics deliver more resolution than the detector can capture. This means:
- The baseline MTF at Nyquist (0.373) is already limited by the pixel aperture
- There is aliased energy beyond Nyquist
- Jitter actually reduces aliasing (by killing high frequencies before they alias), but this doesn't help because the GIQE-5 equation uses the system MTF at Nyquist, not aliased MTF

### Jitter Budget Allocation
The total jitter from all sources adds in quadrature (RSS):

sigma_total^2 = sigma_RW^2 + sigma_solar^2 + sigma_cryo^2 + sigma_struct^2 + sigma_ACS^2

For sigma_total <= 0.8 urad (the dNIIRS = -0.5 threshold):
- If 5 sources contribute equally: each gets sqrt(0.8^2 / 5) = 0.36 urad
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
