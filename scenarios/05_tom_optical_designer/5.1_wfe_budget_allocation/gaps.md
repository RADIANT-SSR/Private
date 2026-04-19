# Scenario 5.1 Gaps: WFE Budget Allocation

## Summary
System: 40 cm Cassegrain, f/10, 10 µm CCD, 500–800 nm VNIR, GSD = 1.25 m, Q = 0.65.
Baseline (WFE = 0): Strehl = 1.00, MTF@Nyq = 0.2418, EE(1x1) = 0.4609, RER = 0.6021, SNR = 177.2, NIIRS = 6.38.
Diffraction-limited threshold (WFE = λ/14 = 0.071 waves): Strehl = 0.83, ΔNIIRS = −0.28.
Tom's Zernike budget (0.0513 waves, nearest sweep point 0.060): Strehl = 0.87, ΔNIIRS = −0.20.
NIIRS drops 0.25 at WFE ~ 0.071; 0.50 at ~ 0.100; 1.00 at ~ 0.140.

## Gap Closure Status

| # | Gap | Severity | Status | Evidence |
|---|-----|----------|--------|----------|
| 1 | No Zernike-to-PSF integration | Medium | Open | Scalar RMS phase screen only; no aberration-specific PSF morphology |
| 2 | No field-dependent WFE | Medium | Open | `FieldWfeSample` defined but `OpticsStage` raises `NotImplementedError` |
| 3 | No Zemax .ZMX importer | Low | Open | Manual Zernike entry required |
| 4 | MTF frequency axis in normalized units only | Low | Open | No cycles/mm or cycles/mrad conversion |
| 5 | No WFE sub-budget allocation tool | Low | Open | No RSS decomposition utility |
| — | Strehl/MTF@Nyq/RER/EE/NIIRS metric exposure | Medium | **CLOSED** | All exposed via `result.metrics[...]` |
| — | Dual-path (PSF + MTF product) consistency | High | **CLOSED** | Both paths rooted in same complex pupil; consistency invariant enforced |

## Marechal vs. RADIANT Strehl Comparison

| WFE [waves] | Marechal (@633nm) | RADIANT (@650nm) | Difference |
|------------:|------------------:|-----------------:|-----------:|
| 0.071 | 0.8195 | 0.8280 | +0.0085 |
| 0.100 | 0.6738 | 0.6877 | +0.0139 |
| 0.140 | 0.4613 | 0.4801 | +0.0188 |
| 0.200 | 0.2062 | 0.2237 | +0.0175 |

RADIANT's Strehl is systematically higher than the "at-reference" Marechal by ~1–2% because it evaluates at the operating band center (650 nm) where the same physical OPD corresponds to a smaller phase error. **This is correct physics**, not a bug.

## Non-Gap Observations

- WFE does not affect noise — SNR = 177.2 is constant across the sweep. NIIRS degradation comes entirely through the RER term (3.32·log₁₀(RER)).
- All spatial metrics (Strehl, MTF@Nyq, EE, RER) degrade at consistent rates (within 1–2%). This self-consistency confirms the dual-path architecture is working — both paths derive from the same pupil.
- Q = 0.65 (undersampled) limits baseline MTF@Nyquist to 0.24. WFE only degrades further from that detector-MTF-limited baseline.
- Marechal approximation is accurate only for Strehl > 0.3 (WFE < ~0.17 waves). Beyond that, the table is an approximation, not a rigorous calculation.
