# Scenario 1.3 Gaps: Dual-Band MWIR/LWIR Wildfire Trade

Executed 2026-07-08 (Phase T3). Registry mirror: `docs/tracking/gaps.md`
(ASTER importer closed by f50253a; spectral-emissivity curve input is
scenario 4.3's subject; ROC-grade detection is planned T4 work).

## Summary
5 m² hotspot vs 300 K conifer forest from 10 km (4 m GSD, 31% fill,
sub-pixel with clutter σ = 0.03). At 600 K: MWIR SCNR 844 vs LWIR 123 —
nearly equal band-integrated ΔL (374 vs 382 W/m²/sr), but LWIR's clutter
is 350× MWIR's because its 300 K background is ~10× brighter in-band.
Both bands P_d ≈ 1 at 400–1200 K; LWIR saturates from ≈800 K, MWIR from
≈900 K at the fire-mode integrations. Recommendation: MWIR for detection.

## Gap Closure Status (catalog "Gaps revealed" list)

| # | Catalog gap | Status | Evidence |
|---|-------------|--------|----------|
| 1 | No ASTER spectral library importer | **CLOSED** (commit f50253a) | `radiant.io.aster_library.load_aster_spectrum` — native descending-order text format, percent/fraction from the `Y Units:` header, ε = 1 − ρ, band averages |
| 2 | No multi-band comparison workflow | Not filed — no machinery missing | Two `Sensor` configs + a comparison table; `BatchRunner` (Gap-4.1 prereq) covers larger grids |
| 3 | No ΔL (spectral contrast) output | Not filed — hand-Planck territory | ΔL(λ) is scene analysis, not a chain output; the script computes and plots it in 10 lines. If curve-level scene outputs land (scenario 4.3), revisit |
| 4 | No detection probability model | Deferred to planned T4 work | P_d = Q(threshold − SCNR) at P_fa = 1e-6 script-side; ROC/DRI modeling is scenarios 6.4/4.2 in the plan's Tier 4 list — no new registry entry |
| 5 | No Excel-to-YAML converter for detector specs | Mooted | The script reads the vendor comparison table directly (openpyxl at the scenario layer); nothing to convert |

## Defect Found and Fixed During Execution (scenario-side)

**First run clipped both bands at 100% well** on the 600 K fire with
ms-class integrations — SNR on a clipped signal is meaningless. Fixed by
adding per-band fire-mode integration times (MWIR 5 µs, LWIR 25 µs) to
the vendor table, which is exactly how real fire products handle it
(dedicated short-integration channels). The saturation *behaviour* is kept
in the temperature sweep as a first-class result (sat flags per point).

## Supporting Capabilities Exercised

- **Gap 6** (unit-aware set): cm/%/ms entries from the workbook.
- **Sub-pixel + clutter pattern from scenario 4.1**: `regime_override` to
  keep in-pixel background photons; SCNR assembled script-side because
  `snr`/`contrast_snr` metrics exclude spatial noise terms (see the
  observation filed with scenario 4.1).

## Non-Gap Observations

- **NEDT is the wrong figure of merit for fire detection** (LWIR wins
  NEDT 89.9 vs 123.1 mK yet loses detection by 7×). The walkthrough spells
  out why; both NEDT values carry the Gap 43 single-λ caveat.
- **Per-band background emissivity from the ASTER curve (0.9530 vs
  0.9821) differs by ~3%** — a shared scalar would bias each band's
  background radiance and hence the clutter estimate at the percent level.
- **Well saturation is a designed-in result, not an error**: the sweep
  flags every point with signal ≥ 98% well; above it, in-band fire
  temperature is unretrievable — the dynamic-range half of the band trade.
