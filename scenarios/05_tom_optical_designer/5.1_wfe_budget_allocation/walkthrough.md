# Scenario 5.1 Walkthrough: WFE Budget Allocation — How Much Aberration Can I Tolerate?


> **NIIRS applicability — engine update (CU-166).** Since this walkthrough was written, RADIANT added a metric-applicability gate: when one or more GIQE-5 inputs fall outside the calibration envelope — GSD 1.18–31.5 inch, RER 0.20–0.95, SNR 2–130 — the engine reports **NIIRS as N/A** by default instead of silently extrapolating. This configuration is outside that envelope, so the NIIRS values below are the **extrapolated** GIQE-5-form output: reproduce them with `performance.niirs.allow_extrapolated = true` and read them as a *relative trend, not a calibrated rating*. (SNR/spatial figures were refreshed 2026-07-22 against the current engine, CU-176. No IR-calibrated IIRS model yet — see `docs/tracking/gaps.md` Gap 100.)

Refreshed 2026-07-07 (Scenario_Execution_Plan Phase R): the Zernike
prescription is now parsed from the Zemax text export via
`load_zemax_zernike` (Gap 26), the allocation is a `radiant.api.ErrorBudget`
(Gaps 23+28), and a Zernike-mode chain run compares the actual prescription
against the scalar-RMS screen at the same total RMS. Numbers below were
refreshed 2026-08-02 against the current engine; the Rayleigh-optical-depth
correction (CU-253) shifted SNR to 173.5 (from 242.2 in the 2026-07-22 run);
the CU-335 gas-table re-fit then took it to 115.4.
WFE-driven spatial *trends* are unchanged — Strehl, MTF@Nyquist and RER are
bit-identical to the previous vintage at every sweep point.

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
| Strehl [--] | 0.9174 | 0.9019 | +0.0156 |
| MTF@Nyquist [--] | 0.2246 | 0.2297 | −0.0051 |
| EE(1x1) [--] | 0.3953 | 0.3868 | +0.0085 |
| RER [--] | 0.5812 | 0.5526 | +0.0285 |
| NIIRS [--] | 6.04 | 5.97 | +0.07 |
| SNR [--] | 115.4 | 115.4 | 0 |

*Numbers refreshed 2026-08-30 from the unmodified runner (previous vintage
2026-08-02). Sole mover: **CU-335** — the calibrated gas table's 0.45–0.70 and
0.70–1.30 µm well-mixed floors had been fitted against a pre-CU-253 Rayleigh
optical depth ~8× too large and so clamped to zero; the re-fit sets them to
0.1597 and 0.0517, and this VNIR scene loses band-mean τ on both the solar and
the view leg. **SNR falls 173.5 → 115.4 (−33 %)**, signal 30,121 → 13,352 e⁻,
and NIIRS follows through the GIQE-5 SNR term at every sweep point (WFE = 0:
6.39 → 6.11). Every spatial column — Strehl, MTF@Nyquist, EE(1×1), EE(3×3),
RER — is bit-identical, which is the check that this is a radiometric change
and nothing optical. **The scenario's conclusions are unchanged**: the WFE
thresholds (−0.25 NIIRS at 0.071 waves, −0.50 at 0.100, −1.00 at 0.140) are
identical, because they are set by the spatial terms, and Tom's prescription
still sits inside budget at Strehl 0.9174.*

*Prior vintage, for the trend: the 2026-08-02 refresh was dominated by CU-253 —
the Rayleigh optical depth was 8× too
large, which halved `E_sky_scattered` and dropped this VNIR scene's SNR from
242.2 to 173.5 (−28 %), carrying NIIRS down with it through the GIQE-5 SNR
term. The EE columns moved separately under CU-188 (cell-area-overlap EE_box).
Strehl, MTF@Nyquist and RER are unchanged.*

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
| 0.000 | 1.0000 | 0.2546 | 0.4288 | 0.8833 | 0.6114 | 6.11 |
| 0.020 | 0.9844 | 0.2506 | 0.4222 | 0.8696 | 0.6021 | 6.09 |
| 0.040 | 0.9392 | 0.2392 | 0.4028 | 0.8296 | 0.5750 | 6.03 |
| 0.060 | 0.8683 | 0.2212 | 0.3724 | 0.7671 | 0.5325 | 5.92 |
| 0.071 | 0.8207 | 0.2092 | 0.3519 | 0.7250 | 0.5040 | 5.84 |
| 0.080 | 0.7781 | 0.1984 | 0.3337 | 0.6874 | 0.4785 | 5.76 |
| 0.100 | 0.6759 | 0.1725 | 0.2899 | 0.5972 | 0.4173 | 5.56 |
| 0.120 | 0.5692 | 0.1455 | 0.2441 | 0.5029 | 0.3533 | 5.32 |
| 0.140 | 0.4648 | 0.1191 | 0.1993 | 0.4106 | 0.2907 | 5.04 |
| 0.160 | 0.3680 | 0.0944 | 0.1578 | 0.3251 | 0.2327 | 4.72 |
| 0.180 | 0.2827 | 0.0726 | 0.1212 | 0.2497 | 0.1815 | 4.36 |
| 0.200 | 0.2106 | 0.0540 | 0.0903 | 0.1861 | 0.1382 | 3.97 |
| 0.250 | 0.0885 | 0.0223 | 0.0379 | 0.0786 | 0.0649 | 2.88 |

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
| 0.100 | -32.4 | -32.2 | -32.4 | -31.8 | -0.55 | acceptable |
| 0.140 | -53.5 | -53.2 | -53.5 | -52.5 | -1.07 | moderate |
| 0.200 | -78.9 | -78.8 | -79.0 | -77.4 | -2.14 | significant |
| 0.250 | -91.1 | -91.2 | -91.2 | -89.4 | -3.23 | severe |

### Tom's Design Assessment
- **Total Zernike RMS**: 0.0513 waves (run in Zernike mode, not just the nearest sweep point)
- **Strehl**: 0.9174 (well above 0.80 diffraction limit; the structured prescription outperforms a random screen at the same RMS)
- **dNIIRS**: -0.07 (Zernike mode) vs -0.15 (scalar screen at the same RMS)
- **Budget**: RSS 0.0513 vs allocation 0.0714 waves — within budget, 0.0497 waves RSS headroom for assembly/thermal terms
- **Assessment**: Tom's WFE budget is well within diffraction-limited territory.

### Noise Budget (constant across sweep)
| Noise Term | Value [e- RMS] | Fraction [%] |
|---|---|---|
| signal_shot | 115.6 | 99.8 |
| dark_shot | 0.1 | 0.0 |
| read_noise | 5.0 | 0.2 |
| quantization | 0.3 | 0.0 |
| TOTAL (RSS) | 115.7 | 100.0 |

Signal: 13,352 e-, SNR: 115.4. WFE does not affect noise — it degrades spatial metrics only. (The background-shot term present in the first run is now zero: in the extended regime RADIANT skips the separate scene-background photon term by design — matrix Decision #13.)

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
This system is undersampled (Q < 1), meaning the pixel pitch is larger than the Airy disk core. The detector MTF at Nyquist limits the achievable system MTF even with perfect optics. At Q = 0.65, the baseline MTF@Nyquist is 0.25 — well below the diffraction-limited OTF value. Adding WFE reduces this further.

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
