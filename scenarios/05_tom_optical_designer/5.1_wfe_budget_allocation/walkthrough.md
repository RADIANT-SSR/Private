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
| 0.000 | 1.0000 | 0.4017 | 0.6251 | 0.8986 | 0.7113 | 6.62 |
| 0.020 | 0.9851 | 0.3955 | 0.6154 | 0.8846 | 0.7004 | 6.60 |
| 0.040 | 0.9419 | 0.3774 | 0.5871 | 0.8440 | 0.6688 | 6.53 |
| 0.060 | 0.8739 | 0.3491 | 0.5428 | 0.7804 | 0.6194 | 6.42 |
| 0.071 | 0.8280 | 0.3301 | 0.5130 | 0.7376 | 0.5861 | 6.34 |
| 0.080 | 0.7869 | 0.3131 | 0.4864 | 0.6995 | 0.5564 | 6.27 |
| 0.100 | 0.6877 | 0.2723 | 0.4225 | 0.6077 | 0.4850 | 6.07 |
| 0.120 | 0.5832 | 0.2297 | 0.3558 | 0.5118 | 0.4104 | 5.83 |
| 0.140 | 0.4801 | 0.1879 | 0.2906 | 0.4180 | 0.3374 | 5.55 |
| 0.160 | 0.3835 | 0.1490 | 0.2301 | 0.3311 | 0.2697 | 5.22 |
| 0.180 | 0.2973 | 0.1145 | 0.1767 | 0.2544 | 0.2100 | 4.86 |
| 0.200 | 0.2237 | 0.0852 | 0.1317 | 0.1896 | 0.1596 | 4.47 |
| 0.250 | 0.0963 | 0.0351 | 0.0554 | 0.0802 | 0.0740 | 3.36 |

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
| 0.100 | -31.2 | -32.2 | -32.4 | -31.8 | -0.55 | acceptable |
| 0.140 | -52.0 | -53.2 | -53.5 | -52.6 | -1.08 | moderate |
| 0.200 | -77.6 | -78.8 | -78.9 | -77.6 | -2.16 | significant |
| 0.250 | -90.4 | -91.3 | -91.1 | -89.6 | -3.26 | severe |

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
This system is undersampled (Q < 1), meaning the pixel pitch is larger than the Airy disk core. The detector MTF at Nyquist limits the achievable system MTF even with perfect optics. At Q = 0.65, the baseline MTF@Nyquist is 0.40 — well below the diffraction-limited OTF value. Adding WFE reduces this further.

### All Metrics Track Together
In this scenario, all spatial metrics (Strehl, MTF@Nyq, EE(1x1), RER) degrade at nearly the same rate. This is because all are derived from the same EffectivePSF. The percentage degradation at each WFE level is consistent across metrics (within ~1-2%). This self-consistency is a validation check — if one metric degraded much faster than another, it would indicate an implementation error.

## Gap Findings

### Gap 1: No Zernike-to-PSF Integration
RADIANT defines Zernike mode in `wavefront.py` but the optics stage only uses `scalar_rms` mode. Individual Zernike coefficients cannot produce aberration-specific PSF shapes (e.g., coma vs. astigmatism produce qualitatively different PSFs). The current random phase screen gives the correct Strehl but not the correct PSF morphology.

### Gap 2: No Field-Dependent WFE
`WavefrontError` defines `FIELD_DEPENDENT` mode with `FieldWfeSample` tuples, but `OpticsStage` raises `NotImplementedError`. Tom has Zernike sets at 4 field positions — he cannot evaluate edge-of-field performance.

### Gap 3: No Zemax Importer
Tom exports Zernike coefficients from Zemax (.ZMX). RADIANT has no parser for this format. Tom must manually enter coefficients into the spreadsheet.

### Gap 4: MTF Curve Frequency Axis Units
The MTF curve from RADIANT uses normalized spatial frequency (cycles/pixel). For optical designers like Tom, cycles/mm or cycles/mrad are more natural. A unit conversion utility or configurable axis would improve usability.

### Gap 5: No WFE Allocation Tool
Tom wants to allocate his WFE budget among contributors (alignment, fabrication, thermal, etc.). RADIANT sweeps total WFE but has no tool to decompose a budget into sub-allocations with RSS combination.
