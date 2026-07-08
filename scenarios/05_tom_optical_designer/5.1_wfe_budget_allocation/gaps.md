# Scenario 5.1 Gaps: WFE Budget Allocation

Refreshed 2026-07-07 (Scenario_Execution_Plan Phase R). Registry mirror:
`docs/tracking/gaps.md` (Gaps 23, 26, 27, 28).

## Summary
System: 40 cm Cassegrain, f/10, 10 µm CCD, 500–800 nm VNIR, GSD = 1.25 m, Q = 0.65.
Baseline (WFE = 0): Strehl = 1.00, MTF@Nyq = 0.2418, EE(1x1) = 0.4609, RER = 0.6021, SNR = 250.6, NIIRS = 6.62.
(SNR/NIIRS higher than the first run — the column-integrated atmospheric transmittance fix, Gap 2 family, raised in-band signal.)
Diffraction-limited threshold (WFE = λ/14 = 0.071 waves): Strehl = 0.82, ΔNIIRS = −0.28.
Tom's prescription (0.0513 waves RSS, Zernike mode): Strehl = 0.9194, ΔNIIRS = −0.08.
NIIRS drops 0.25 at WFE ~ 0.071; 0.50 at ~ 0.100; 1.00 at ~ 0.140.

## Gap Closure Status

| # | Gap | Severity | Status | Evidence |
|---|-----|----------|--------|----------|
| 1 | No Zernike-to-PSF integration | Medium | **CLOSED** (this refresh) | ZERNIKE-mode `WavefrontError` injected via `stage_outputs["optics_config"]["wavefront_error"]`; Step 5b runs Tom's actual prescription end-to-end |
| 2 | No field-dependent WFE | Medium | Open | `FieldWfeSample` lookup exists in `OpticsStage` (field_x/field_y params); not exercised by this scenario — needs a field-dependent prescription input |
| 3 | No Zemax importer | Low | **CLOSED** — registry Gap 26 | `radiant.io.zemax_zernike.load_zemax_zernike` parses the "Zernike Standard Coefficients" text export (`tom_zernike_zemax.txt`); cross-checked against the workbook sheet |
| 4 | MTF frequency axis in normalized units only | Low | **CLOSED** — registry Gap 27 | `performance.frequency_units` conversion (cy/m, cy/mm, cy/mrad, cy/pixel) |
| 5 | No WFE sub-budget allocation tool | Low | **CLOSED** — registry Gaps 23+28 | `radiant.api.ErrorBudget`: per-mode RSS contributors, allocation = λ/14, `.table()`, `margin`, `remaining_allocation()` |
| — | Strehl/MTF@Nyq/RER/EE/NIIRS metric exposure | Medium | **CLOSED** | All exposed via `result.metrics[...]` |
| — | Dual-path (PSF + MTF product) consistency | High | **CLOSED** | Both paths rooted in same complex pupil; consistency invariant enforced (but see CU-058 for the scalar-WFE + defocus combination — not hit here, defocus enters as Zernike Z4 in this scenario) |

## Zernike vs Scalar Screen at the Same RMS (Step 5b)

| Metric | Zernike (actual) | Scalar screen | Δ |
|--------|-----------------:|--------------:|---:|
| Strehl [--] | 0.9194 | 0.9019 | +0.0175 |
| MTF@Nyquist [--] | 0.2132 | 0.2181 | −0.0049 |
| EE(1x1) [--] | 0.4255 | 0.4157 | +0.0098 |
| RER [--] | 0.5728 | 0.5443 | +0.0285 |
| NIIRS [--] | 6.54 | 6.47 | +0.07 |
| SNR [--] | 250.6 | 250.6 | 0 |

Same 0.0513-wave RMS, different modal distribution → different metric set.
Shape matters; the scalar sweep is the budget trade, the Zernike run is the
as-built truth (cf. scenario 7.3, where the scalar-shape assumption dominated
the measured-vs-predicted MTF residual).

## Marechal vs. RADIANT Strehl Comparison

| WFE [waves] | Marechal (@633nm) | RADIANT | Difference |
|------------:|------------------:|--------:|-----------:|
| 0.071 | 0.8195 | 0.8207 | +0.0011 |
| 0.100 | 0.6738 | 0.6759 | +0.0021 |
| 0.140 | 0.4613 | 0.4648 | +0.0035 |
| 0.200 | 0.2062 | 0.2107 | +0.0045 |

RADIANT's Strehl is now the degraded-PSF peak over the diffraction-limited
reference PSF (Rule 4), evaluated at band center; it tracks Maréchal to
< 0.005 across the sweep — closer than the previous run because the ratio
definition cancels detector kernels on both paths.

## Non-Gap Observations

- WFE does not affect noise — SNR = 250.6 is constant across the sweep. NIIRS degradation comes entirely through the RER term (3.32·log₁₀(RER)).
- All spatial metrics (Strehl, MTF@Nyq, EE, RER) degrade at consistent rates. This self-consistency confirms the dual-path architecture is working — both paths derive from the same pupil.
- Q = 0.65 (undersampled) limits baseline MTF@Nyquist to 0.24. WFE only degrades further from that detector-MTF-limited baseline.
- Marechal approximation is accurate only for Strehl > 0.3 (WFE < ~0.17 waves). Beyond that, the table is an approximation, not a rigorous calculation.
- Zernike mode has no scalar-parameter/YAML path — the `WavefrontError` object must be injected at the API layer (`RadiantSession.run(extra_stage_outputs=...)`). A config-surface path would parallel registry Gap 42's ask for lab_test.
