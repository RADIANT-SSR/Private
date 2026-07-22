# Scenario 5.1 Walkthrough: WFE Budget Allocation — How Much Aberration Can I Tolerate?


> **NIIRS applicability — engine update (CU-166).** Since this walkthrough was written, RADIANT added a metric-applicability gate: when one or more GIQE-5 inputs fall outside the calibration envelope — GSD 1.18–31.5 inch, RER 0.20–0.95, SNR 2–130 — the engine reports **NIIRS as N/A** by default instead of silently extrapolating. This configuration is outside that envelope, so the NIIRS values below are the **extrapolated** GIQE-5-form output: reproduce them with `performance.niirs.allow_extrapolated = true` and read them as a *relative trend, not a calibrated rating*. (The SNR/NEDT figures here predate later physics updates and are indicative; a full numeric refresh is tracked separately in the cleanup backlog. No IR-calibrated IIRS model yet — see `docs/tracking/gaps.md` Gap 100.)

Refreshed 2026-07-07 (Scenario_Execution_Plan Phase R): the Zernike
prescription is now parsed from the Zemax text export via
`load_zemax_zernike` (Gap 26), the allocation is a `radiant.api.ErrorBudget`
(Gaps 23+28), and a Zernike-mode chain run compares the actual prescription
against the scalar-RMS screen at the same total RMS. Numbers below are from
the refreshed run (SNR/NIIRS are higher than the first execution — the
column-integrated atmospheric transmittance fix raised in-band signal).

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

The coefficients arrive as `tom_zernike_zemax.txt` — the Zemax "Zernike
Standard Coefficients" text export — parsed by
`radiant.io.zemax_zernike.load_zemax_zernike` (Gap 26: encoding detection,
Noll-index validation, reference-wavelength capture). The script
cross-checks the parsed set against the workbook sheet and refuses to run on
a mismatch.

## The WFE Allocation as an ErrorBudget (Gaps 23+28)

The λ/14 requirement is expressed as a `radiant.api.ErrorBudget` with one RSS
contributor per Zernike mode (Noll-normalized coefficients are per-mode RMS
contributions, so total RMS = RSS):

| Quantity | Value |
|----------|-------|
| RSS total | 0.0513 waves |
| Allocation (λ/14) | 0.0714 waves |
| Over budget | No |
| Linear margin | +0.0201 waves |
| RSS headroom (`remaining_allocation()`) | **0.0497 waves** |

The RSS headroom is the actionable number: an assembly/thermal contributor of
up to 0.0497 waves RMS can be added before the λ/14 allocation is exceeded —
notably larger than the 0.0201-wave linear margin, because independent errors
add in quadrature. The budget table also ranks contributors by variance share
(spherical 34.2%, coma-Y 23.7%, defocus 15.2%), telling Tom where reduction
effort pays off.

## Approach
The script sweeps `optics.wfe_rms_waves` from 0 to 0.25 waves (at 633 nm HeNe reference) and evaluates the full RADIANT signal chain at each point. RADIANT applies a random phase screen scaled to the requested RMS in the optics stage, producing an aberrated PSF. PerformanceStage computes Strehl, MTF, EE, RER, and NIIRS from the aberrated EffectivePSF.

The scalar sweep is the budget *trade*; the as-built *truth* is the Zernike
run (next section). Tom's 0.0513 waves total RMS also corresponds to one
point on the sweep for continuity with the previous execution.

## Zernike Mode vs Scalar Screen (Step 5b — new)

RADIANT now runs the actual prescription: `zemax.to_wavefront_error()`
produces a ZERNIKE-mode `WavefrontError`, injected via
`RadiantSession.run(extra_stage_outputs={"optics_config": {"wavefront_error": …}})`
(Rule 6 — file-derived objects are built by the IO/API layer and injected
before chain execution; there is no scalar-parameter path for Zernike mode).

| Metric | Zernike (actual) | Scalar screen | Δ |
|--------|-----------------:|--------------:|---:|
| Strehl [--] | 0.9194 | 0.9019 | +0.0175 |
| MTF@Nyquist [--] | 0.2132 | 0.2181 | −0.0049 |
| EE(1x1) [--] | 0.4255 | 0.4157 | +0.0098 |
| RER [--] | 0.5728 | 0.5443 | +0.0285 |
| NIIRS [--] | 6.54 | 6.47 | +0.07 |
| SNR [--] | 250.6 | 250.6 | 0 |

Same total RMS, different modal mix, different metrics — the shape effect a
single RMS number cannot capture. At this small RMS (Strehl ≈ 0.9) the
difference is modest but visible (+0.07 NIIRS); it grows with WFE, and only
the Zernike route reproduces aberration-specific PSF structure (coma
asymmetry, spherical rings). This is the same shape-ambiguity that dominated
scenario 7.3's measured-vs-predicted MTF residual — use the prescription
whenever one exists.

## Key Results

### WFE Sweep
| WFE [waves] | Strehl [--] | MTF@Nyq [--] | EE(1x1) [--] | EE(3x3) [--] | RER [--] | NIIRS [--] |
|---|---|---|---|---|---|---|
| 0.000 | 1.0000 | 0.2418 | 0.4609 | 0.8861 | 0.6021 | 6.62 |
| 0.020 | 0.9844 | 0.2380 | 0.4538 | 0.8723 | 0.5930 | 6.59 |
| 0.040 | 0.9391 | 0.2271 | 0.4329 | 0.8322 | 0.5663 | 6.53 |
| 0.060 | 0.8683 | 0.2101 | 0.4002 | 0.7695 | 0.5245 | 6.42 |
| 0.071 | 0.8207 | 0.1986 | 0.3783 | 0.7272 | 0.4964 | 6.34 |
| 0.080 | 0.7781 | 0.1884 | 0.3587 | 0.6896 | 0.4713 | 6.26 |
| 0.100 | 0.6759 | 0.1638 | 0.3115 | 0.5990 | 0.4110 | 6.07 |
| 0.120 | 0.5692 | 0.1382 | 0.2623 | 0.5045 | 0.3480 | 5.83 |
| 0.140 | 0.4648 | 0.1131 | 0.2142 | 0.4119 | 0.2864 | 5.55 |
| 0.160 | 0.3681 | 0.0897 | 0.1696 | 0.3262 | 0.2292 | 5.22 |
| 0.180 | 0.2827 | 0.0689 | 0.1302 | 0.2505 | 0.1788 | 4.87 |
| 0.200 | 0.2107 | 0.0513 | 0.0970 | 0.1867 | 0.1363 | 4.47 |
| 0.250 | 0.0886 | 0.0212 | 0.0407 | 0.0788 | 0.0641 | 3.39 |

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
| 0.040 | -6.1 | -6.1 | -6.1 | -6.0 | -0.09 | diffraction-limited |
| 0.071 | -17.9 | -17.8 | -17.9 | -17.6 | -0.28 | diffraction-limited |
| 0.100 | -32.4 | -32.2 | -32.4 | -31.7 | -0.55 | acceptable |
| 0.140 | -53.5 | -53.2 | -53.5 | -52.4 | -1.07 | moderate |
| 0.200 | -78.9 | -78.8 | -79.0 | -77.4 | -2.14 | significant |
| 0.250 | -91.1 | -91.2 | -91.2 | -89.4 | -3.23 | severe |

### Tom's Design Assessment
- **Total Zernike RMS**: 0.0513 waves (run in Zernike mode, not just the nearest sweep point)
- **Strehl**: 0.9194 (well above 0.80 diffraction limit; the structured prescription outperforms a random screen at the same RMS)
- **dNIIRS**: -0.08 (Zernike mode) vs -0.15 (scalar screen at the same RMS)
- **Budget**: RSS 0.0513 vs allocation 0.0714 waves — within budget, 0.0497 waves RSS headroom for assembly/thermal terms
- **Assessment**: Tom's WFE budget is well within diffraction-limited territory.

### Noise Budget (constant across sweep)
| Noise Term | Value [e- RMS] | Fraction [%] |
|---|---|---|
| signal_shot | 250.6 | 100.0 |
| dark_shot | 0.1 | 0.0 |
| read_noise | 5.0 | 0.0 |
| quantization | 0.3 | 0.0 |
| TOTAL (RSS) | 250.7 | 100.0 |

Signal: 62,818 e-, SNR: 250.6. WFE does not affect noise — it degrades spatial metrics only. (The background-shot term present in the first run is now zero: in the extended regime RADIANT skips the separate scene-background photon term by design — matrix Decision #13.)

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
| Zernike-to-PSF (scenario Gap 1) | **CLOSED** (this refresh) | ZERNIKE-mode `WavefrontError` injected via `optics_config` — Step 5b runs Tom's actual prescription |
| Zemax importer (scenario Gap 3, registry Gap 26) | **CLOSED** (this refresh) | `load_zemax_zernike` parses the text export; cross-checked vs workbook |
| MTF frequency units (scenario Gap 4, registry Gap 27) | **CLOSED** | cy/m, cy/mm, cy/mrad, cy/pixel conversions |
| WFE allocation tool (scenario Gap 5, registry Gaps 23+28) | **CLOSED** (this refresh) | `radiant.api.ErrorBudget` — RSS, allocation, margin, headroom |
| Strehl/MTF@Nyq/RER/EE/NIIRS metric exposure | **CLOSED** | All available via `result.metrics[...]` |
| Dual-path consistency (PSF path + MTF product path) | **CLOSED** | Both paths rooted in same complex pupil; consistency checked |

### Open Gaps
- **Gap 2 (Field-dependent WFE)**: the `OpticsStage` field-lookup path exists (`optics.field_position_x/y` + `FieldWfeSample`) but is not exercised by this scenario — needs a field-dependent prescription input.
- **Config-surface Zernike path**: Zernike mode requires API-level injection (`RadiantSession.run(extra_stage_outputs=...)`); no YAML/dict route yet (parallel to registry Gap 42's lab_test ask).
