# Scenario 5.1 Walkthrough: WFE Budget Allocation — How Much Aberration Can I Tolerate?

## Persona
Tom, optical designer. He has a Zernike decomposition from Zemax for a 40 cm Cassegrain telescope (f/10, 35% linear obscuration) operating in VNIR (500--800 nm). He wants to determine how much total WFE RMS his design can tolerate before Strehl, MTF, EE, RER, and NIIRS degrade unacceptably.

## System Configuration
| Parameter | Value | Unit |
|---|---|---|
| Aperture diameter | 40 | cm |
| Focal length | 400 | cm |
| f-number | 10.0 | -- |
| Optical transmission | 75 | % |
| Optics temperature | 20 | C |
| Central obscuration | 35 | % (linear) |
| WFE reference wavelength | 633 | nm |
| Pixel pitch | 10.0 | um |
| QE | 85 | % |
| Dark current | 3.0 | e-/s |
| Read noise | 5.0 | e- RMS |
| FWC | 100,000 | e- |
| Band | 500--800 | nm |
| Orbit altitude | 500 | km |
| Target reflectance | 0.15 | -- |
| Background reflectance | 0.10 | -- |
| Solar zenith angle | 30 | deg |
| Integration time | 2.0 | ms |
| GSD | 1.25 | m |
| Q (sampling) | 0.650 | -- (undersampled) |
| IFOV | 2.5 | urad |

## Tom's Zernike Coefficients (from Zemax)
| Index | Name | Coefficient [waves] |
|---|---|---|
| Z4 | Defocus | 0.020 |
| Z5 | Astigmatism 0 | 0.015 |
| Z6 | Astigmatism 45 | 0.010 |
| Z7 | Coma Y | 0.025 |
| Z8 | Coma X | 0.018 |
| Z9 | Trefoil Y | 0.005 |
| Z10 | Trefoil X | 0.004 |
| Z11 | Spherical | 0.030 |
| Z12 | 2nd Astigmatism 0 | 0.003 |
| Z13 | 2nd Astigmatism 45 | 0.002 |
| Z14 | 2nd Coma Y | 0.002 |
| Z15 | 2nd Coma X | 0.001 |
| **Total RMS** | | **0.0513 waves** |

The dominant contributors are spherical (Z11 = 0.030), coma Y (Z7 = 0.025), and defocus (Z4 = 0.020). The total RMS is the RSS of all coefficients.

## Approach
The script sweeps `optics.wfe_rms_waves` from 0 to 0.25 waves (at 633 nm HeNe reference) and evaluates the full RADIANT signal chain at each point. RADIANT applies a random phase screen scaled to the requested RMS in the optics stage, producing an aberrated PSF. PerformanceStage computes Strehl (Marechal), MTF, EE, RER, and NIIRS from the aberrated EffectivePSF.

Since RADIANT uses scalar RMS mode (not individual Zernike coefficients), the results represent the average impact of a given total WFE. The Zernike coefficients are provided as reference data — Tom's 0.0513 waves total RMS corresponds to one point on the sweep.

## Key Results

### WFE Sweep
| WFE [waves] | Strehl [--] | MTF@Nyq [--] | EE(1x1) [--] | EE(3x3) [--] | RER [--] | NIIRS [--] |
|---|---|---|---|---|---|---|
| 0.000 | 1.0000 | 0.2418 | 0.4609 | 0.8861 | 0.6021 | 6.38 |
| 0.020 | 0.9851 | 0.2380 | 0.4538 | 0.8723 | 0.5930 | 6.36 |
| 0.040 | 0.9419 | 0.2271 | 0.4329 | 0.8322 | 0.5663 | 6.29 |
| 0.060 | 0.8739 | 0.2101 | 0.4002 | 0.7695 | 0.5245 | 6.18 |
| 0.071 | 0.8280 | 0.1986 | 0.3783 | 0.7272 | 0.4964 | 6.10 |
| 0.080 | 0.7869 | 0.1884 | 0.3587 | 0.6896 | 0.4713 | 6.03 |
| 0.100 | 0.6877 | 0.1638 | 0.3115 | 0.5990 | 0.4110 | 5.83 |
| 0.120 | 0.5832 | 0.1382 | 0.2623 | 0.5045 | 0.3480 | 5.59 |
| 0.140 | 0.4801 | 0.1131 | 0.2142 | 0.4119 | 0.2864 | 5.31 |
| 0.160 | 0.3835 | 0.0897 | 0.1696 | 0.3262 | 0.2292 | 4.99 |
| 0.180 | 0.2973 | 0.0689 | 0.1302 | 0.2505 | 0.1788 | 4.63 |
| 0.200 | 0.2237 | 0.0513 | 0.0970 | 0.1867 | 0.1363 | 4.24 |
| 0.250 | 0.0963 | 0.0212 | 0.0407 | 0.0788 | 0.0641 | 3.15 |

### NIIRS Thresholds
| Degradation | WFE Threshold [waves] |
|---|---|
| -0.25 NIIRS | ~0.071 |
| -0.50 NIIRS | ~0.100 |
| -1.00 NIIRS | ~0.140 |

### Metric Degradation (relative to perfect optics)
| WFE [waves] | dStrehl [%] | dMTF@Nyq [%] | dEE(1x1) [%] | dRER [%] | dNIIRS [--] | Quality |
|---|---|---|---|---|---|---|
| 0.000 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00 | diffraction-limited |
| 0.040 | -5.8 | -6.1 | -6.1 | -6.0 | -0.09 | diffraction-limited |
| 0.071 | -17.2 | -17.8 | -17.9 | -17.6 | -0.28 | diffraction-limited |
| 0.100 | -31.2 | -32.2 | -32.4 | -31.7 | -0.55 | acceptable |
| 0.140 | -52.0 | -53.2 | -53.5 | -52.4 | -1.07 | moderate |
| 0.200 | -77.6 | -78.8 | -79.0 | -77.4 | -2.14 | significant |
| 0.250 | -90.4 | -91.2 | -91.2 | -89.4 | -3.23 | severe |

### Tom's Design Assessment
- **Total Zernike RMS**: 0.0513 waves (nearest sweep point: 0.060)
- **Strehl**: 0.87 (well above 0.80 diffraction limit)
- **dNIIRS**: -0.20 (only 0.2 NIIRS loss from perfect optics)
- **Assessment**: Tom's WFE budget is well within diffraction-limited territory.

### Noise Budget (constant across sweep)
| Noise Term | Value [e- RMS] | Fraction [%] |
|---|---|---|
| signal_shot | 250.6 | 50.0 |
| background_shot | 250.6 | 50.0 |
| read_noise | 5.0 | 0.0 |
| TOTAL (RSS) | 354.5 | 100.0 |

Signal: 62,818 e-, SNR: 177.2. WFE does not affect noise — it degrades spatial metrics only.

## Physics Discussion

### Why WFE Degrades Image Quality
Wavefront error introduces phase variations across the pupil. The PSF is the squared modulus of the Fourier transform of the pupil function (including phase). As WFE increases:
- The PSF peak drops (Strehl decreases)
- Energy moves from the central core to side lobes
- The MTF (Fourier transform of PSF) drops at all frequencies
- Edge response broadens (RER decreases)
- Ensquared energy in the central pixel decreases

### Marechal Approximation
For small WFE (Strehl > 0.3, or WFE < ~0.17 waves):

    S = exp(-(2*pi*OPD_rms/lambda)^2)

where OPD_rms = WFE_rms_waves x lambda_ref. At a different operating wavelength, the same physical OPD produces a different Strehl because the phase error in radians depends on wavelength.

At the lambda/14 threshold (0.071 waves): S = 0.80. This is the conventional definition of "diffraction-limited."

### SNR Is Constant
WFE does not add noise. The signal (photons collected) is determined by the source radiance, aperture area, and integration time — none of which depend on wavefront quality. The noise budget (signal shot, background shot, read noise) is identical at all WFE levels.

NIIRS changes with WFE come entirely through the RER term (3.32 x log10(RER)) and marginally through the EE-dependent signal term for point sources.

### Undersampled System (Q = 0.65)
This system is undersampled (Q < 1), meaning the pixel pitch is larger than the Airy disk core. The detector MTF at Nyquist limits the achievable system MTF even with perfect optics. At Q = 0.65, the baseline MTF@Nyquist is 0.24 — well below the diffraction-limited OTF value. Adding WFE reduces this further.

### All Metrics Track Together
In this scenario, all spatial metrics (Strehl, MTF@Nyq, EE(1x1), RER) degrade at nearly the same rate. This is because all are derived from the same EffectivePSF. The percentage degradation at each WFE level is consistent across metrics (within ~1-2%). This self-consistency is a validation check — if one metric degraded much faster than another, it would indicate an implementation error.

## Gap Findings

See [gaps.md](gaps.md) for full detail.

### Gap Closure Since Last Run
| Gap | Status | Notes |
|-----|--------|-------|
| Strehl/MTF@Nyq/RER/EE metric exposure | **CLOSED** | All available via `result.metrics["strehl"]`, `["mtf_at_nyquist"]`, `["rer"]` |
| NIIRS metric exposure | **CLOSED** | `result.metrics["niirs"]` available |
| Dual-path consistency (PSF path + MTF product path) | **CLOSED** | Both paths rooted in same complex pupil; consistency checked |

### Open Gaps
- **Gap 1 (No Zernike-to-PSF)**: still open. Scalar RMS phase screen gives correct Strehl but not aberration-specific PSF morphology (coma vs. astigmatism).
- **Gap 2 (No field-dependent WFE)**: still open. `FieldWfeSample` defined but `OpticsStage` raises `NotImplementedError`.
- **Gap 3 (No Zemax .ZMX importer)**: still open.
- **Gap 4 (MTF frequency axis units)**: still open. Normalized cycles/pixel only — no cycles/mm or cycles/mrad conversion utility.
- **Gap 5 (No WFE allocation tool)**: still open. No sub-budget RSS decomposition.
