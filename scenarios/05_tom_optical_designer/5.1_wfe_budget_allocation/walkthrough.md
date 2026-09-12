# Scenario 5.1 Walkthrough: WFE Budget Allocation — How Much Aberration Can I Tolerate?


> **NIIRS applicability — engine update (CU-166).** Since this walkthrough was written, RADIANT added a metric-applicability gate: when one or more GIQE-5 inputs fall outside the calibration envelope — GSD 1.18–31.5 inch, RER 0.20–0.95, SNR 2–130 — the engine reports **NIIRS as N/A** by default instead of silently extrapolating. This configuration is outside that envelope, so the NIIRS values below are the **extrapolated** GIQE-5-form output: reproduce them with `performance.niirs.allow_extrapolated = true` and read them as a *relative trend, not a calibrated rating*. (SNR/spatial figures were refreshed 2026-07-22 against the current engine, CU-176. No IR-calibrated IIRS model yet — see `docs/tracking/gaps.md` Gap 100.)

Refreshed 2026-07-07 (Scenario_Execution_Plan Phase R): the Zernike
prescription is now parsed from the Zemax text export via
`load_zemax_zernike` (Gap 26), the allocation is a `radiant.api.ErrorBudget`
(Gaps 23+28), and a Zernike-mode chain run compares the actual prescription
against the scalar-RMS screen at the same total RMS. Numbers below were
refreshed 2026-08-02 against the current engine; the Rayleigh-optical-depth
correction (CU-253) shifted SNR to 173.5 (from 242.2 in the 2026-07-22 run);
the CU-335 gas-table re-fit then took it to 115.4, and the CU-336 grid-convention
correction to that same fit brought it back to 120.2.
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
The script sweeps `optics.wfe_rms_waves` from 0 to 0.25 waves (at 633 nm HeNe reference) and evaluates the full RADIANT signal chain at each point. RADIANT expands the scalar RMS over the fixed equal-RMS low-order Zernike set (Noll Z4–Z11, deterministic — CU-355, owner-ratified 2026-09-11; it replaced the earlier white-noise phase screen, which put all its variance at the pupil-grid sample scale and ignored the reference wavelength), producing an aberrated PSF. PerformanceStage computes Strehl, MTF, EE, RER, and NIIRS from the aberrated EffectivePSF.

The scalar sweep is the budget *trade*; the as-built *truth* is the Zernike
run (next section). Tom's 0.0513 waves total RMS also corresponds to one
point on the sweep for continuity with the previous execution.

## Zernike Mode vs Scalar Screen (Step 5b — new)

RADIANT now runs the actual prescription: `zemax.to_wavefront_error()`
produces a ZERNIKE-mode `WavefrontError`, injected via
`RadiantSession.run(extra_stage_outputs={"optics_config": {"wavefront_error": …}})`
(Rule 6 — file-derived objects are built by the IO/API layer and injected
before chain execution; there is no scalar-parameter path for Zernike mode).

| Metric | Zernike (actual) | Scalar expansion | Δ |
|--------|-----------------:|-----------------:|---:|
| Strehl [--] | 0.9174 | 0.9256 | −0.0082 |
| MTF@Nyquist [--] | 0.2246 | 0.2204 | +0.0041 |
| EE(1x1) [--] | 0.3953 | 0.3999 | −0.0046 |
| RER [--] | 0.5812 | 0.5872 | −0.0060 |
| NIIRS [--] | 6.07 | 6.08 | −0.01 |
| SNR [--] | 120.2 | 120.2 | 0 |

*Refreshed 2026-09-12 (CU-355): the "scalar screen" column is now the
deterministic equal-RMS Z4–Z11 expansion, and the Δs flip sign — Tom's
actual prescription (spherical + coma dominant) sits slightly BELOW the
equal-weight mix at the same 0.0513-wave RMS, where it sat above the old
white-noise halo. The two are now near-twins (|ΔNIIRS| 0.01, was 0.07),
which is what two low-order pupils at one RMS should be; the Zernike route
still earns its keep on aberration-specific PSF structure.*

*Numbers refreshed 2026-09-01 from the unmodified runner (previous vintage
2026-08-30). Sole mover: **CU-336** — the same fit's grid convention was
corrected (`floor_add` had been subtracting a uniform-λ non-water reference from
a wavenumber-grid ladder optical depth), so the two floors come down to 0.1375
and 0.0402 and this VNIR scene gains band-mean τ back on both the solar and the
view leg. **SNR rises 115.4 → 120.2 (+4.2 %)**, signal 13,352 → 14,468 e⁻, and
NIIRS follows through the GIQE-5 SNR term at every sweep point (WFE = 0:
6.11 → 6.14). Every spatial column — Strehl, MTF@Nyquist, EE(1×1), EE(3×3),
RER — is bit-identical, which is the check that this is a radiometric change and
nothing optical. **The scenario's conclusions are unchanged**: the WFE thresholds
(−0.25 NIIRS at 0.071 waves, −0.50 at 0.100, −1.00 at 0.140) are identical,
because they are set by the spatial terms, and Tom's prescription still sits
inside budget at Strehl 0.9174.*

*Prior vintage, 2026-08-30. **CU-335** put those two floors on the table for the
first time (0.1597 / 0.0517): SNR fell 173.5 → 115.4 (−33 %), signal
30,121 → 13,352 e⁻, and NIIRS at WFE = 0 went 6.39 → 6.11.*

*Prior vintage, for the trend: the 2026-08-02 refresh was dominated by CU-253 —
the Rayleigh optical depth was 8× too
large, which halved `E_sky_scattered` and dropped this VNIR scene's SNR from
242.2 to 173.5 (−28 %), carrying NIIRS down with it through the GIQE-5 SNR
term. The EE columns moved separately under CU-188 (cell-area-overlap EE_box).
Strehl, MTF@Nyquist and RER are unchanged.*

Same total RMS, different modal mix, different metrics — the shape effect a
single RMS number cannot capture. Under CU-355 both pupils are low-order, so
at this small RMS the difference is slight (−0.01 NIIRS; it was +0.07
against the retired white-noise screen); it grows with WFE, and only the
Zernike route reproduces aberration-specific PSF structure (coma asymmetry,
spherical rings). This is the same shape-ambiguity that dominated scenario
7.3's measured-vs-predicted MTF residual — use the prescription whenever one
exists.

## Key Results

### WFE Sweep
| WFE [waves] | Strehl [--] | MTF@Nyq [--] | EE(1x1) [--] | EE(3x3) [--] | RER [--] | NIIRS [--] |
|---|---|---|---|---|---|---|
| 0.000 | 1.0000 | 0.2546 | 0.4288 | 0.8833 | 0.6114 | 6.14 |
| 0.020 | 0.9879 | 0.2488 | 0.4242 | 0.8805 | 0.6079 | 6.13 |
| 0.040 | 0.9534 | 0.2327 | 0.4107 | 0.8720 | 0.5966 | 6.11 |
| 0.060 | 0.9011 | 0.2101 | 0.3903 | 0.8581 | 0.5786 | 6.06 |
| 0.071 | 0.8671 | 0.1968 | 0.3770 | 0.8484 | 0.5665 | 6.03 |
| 0.080 | 0.8402 | 0.1862 | 0.3654 | 0.8394 | 0.5556 | 6.00 |
| 0.100 | 0.7794 | 0.1663 | 0.3384 | 0.8167 | 0.5295 | 5.93 |
| 0.120 | 0.7210 | 0.1530 | 0.3117 | 0.7912 | 0.5022 | 5.86 |
| 0.140 | 0.6750 | 0.1450 | 0.2866 | 0.7640 | 0.4751 | 5.78 |
| 0.160 | 0.6334 | 0.1383 | 0.2637 | 0.7367 | 0.4492 | 5.70 |
| 0.180 | 0.5953 | 0.1296 | 0.2428 | 0.7101 | 0.4248 | 5.62 |
| 0.200 | 0.5589 | 0.1178 | 0.2234 | 0.6852 | 0.4018 | 5.54 |
| 0.250 | 0.4681 | 0.0863 | 0.1783 | 0.6300 | 0.3490 | 5.33 |

*Refreshed 2026-09-12 (chartered scenario sweep). Sole mover: **CU-355** —
the scalar screen became the deterministic Z4–Z11 expansion, whose low-order
blur is partially forgiven by pixel integration, so every spatial column
degrades far more gently at equal RMS than the retired white-noise halo did
(Strehl at 0.25 waves: 0.089 → 0.468). The WFE = 0 row is bit-identical, as
CU-355's zero-budget guarantee requires.*

### NIIRS Thresholds
| Degradation | WFE Threshold [waves] |
|---|---|
| -0.25 NIIRS | ~0.110 |
| -0.50 NIIRS | ~0.175 |
| -1.00 NIIRS | not reached in the 0–0.25 sweep (−0.81 at 0.250) |

*Thresholds moved substantially under CU-355 (previously ~0.071 / ~0.100 /
~0.140): at equal RMS the deterministic low-order screen costs roughly half
the NIIRS the white-noise halo charged. The budget REASONING is unchanged —
the thresholds still come off the spatial terms alone.*

### Metric Degradation (relative to perfect optics)
| WFE [waves] | dStrehl [%] | dMTF@Nyq [%] | dEE(1x1) [%] | dRER [%] | dNIIRS [--] | Quality |
|---|---|---|---|---|---|---|
| 0.000 | +0.0 | +0.0 | +0.0 | +0.0 | +0.00 | diffraction-limited |
| 0.040 | -4.7 | -8.6 | -4.2 | -2.4 | -0.04 | diffraction-limited |
| 0.071 | -13.3 | -22.7 | -12.1 | -7.3 | -0.11 | diffraction-limited |
| 0.100 | -22.1 | -34.7 | -21.1 | -13.4 | -0.21 | acceptable |
| 0.140 | -32.5 | -43.1 | -33.2 | -22.3 | -0.36 | moderate |
| 0.200 | -44.1 | -53.7 | -47.9 | -34.3 | -0.61 | significant |
| 0.250 | -53.2 | -66.1 | -58.4 | -42.9 | -0.81 | severe |

*Note the columns now decouple (CU-355): the white-noise screen degraded
every metric by the same fraction (a flat Strehl factor); the low-order
expansion hits mid-frequency MTF hardest and RER least — visible structure
a single scatter halo could not produce.*

### Tom's Design Assessment
- **Total Zernike RMS**: 0.0513 waves (run in Zernike mode, not just the nearest sweep point)
- **Strehl**: 0.9174 (well above 0.80 diffraction limit; near-twin of the CU-355 scalar expansion's 0.9256 at the same RMS)
- **dNIIRS**: -0.07 (Zernike mode) vs -0.06 (CU-355 scalar expansion at the same RMS)
- **Budget**: RSS 0.0513 vs allocation 0.0714 waves — within budget, 0.0497 waves RSS headroom for assembly/thermal terms
- **Assessment**: Tom's WFE budget is well within diffraction-limited territory.

### Noise Budget (constant across sweep)
| Noise Term | Value [e- RMS] | Fraction [%] |
|---|---|---|
| signal_shot | 120.3 | 99.8 |
| dark_shot | 0.1 | 0.0 |
| read_noise | 5.0 | 0.2 |
| quantization | 0.3 | 0.0 |
| TOTAL (RSS) | 120.4 | 100.0 |

Signal: 14,468 e-, SNR: 120.2. WFE does not affect noise — it degrades spatial metrics only. (The background-shot term present in the first run is now zero: in the extended regime RADIANT skips the separate scene-background photon term by design — matrix Decision #13.)

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
