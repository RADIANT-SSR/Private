# Scenario 3.3 — Gaps and Friction

## Composition scenario — no new model

3.3 reuses existing capability: the chain metrics (SNR/NIIRS/NEDT/MTF/GSD)
and `performance.giqe_sensitivity` (Gap 20) for the "which improvement
matters most" analysis. The comparison table, ranking, compliance matrix,
and radar chart are scenario-level assembly. The catalog's NEDT/NIIRS/GSD
"gaps" were closed in earlier phases.

## Framework gaps (mirrored to docs/tracking/gaps.md)

### Gap 55 — no PDF spec-sheet parser
The catalog flagged "no PDF spec sheet parser." Vendor spec sheets arrive
as PDFs; RADIANT has no PDF ingestion. This scenario transcribes the vendor
numbers into a workbook (the RADIANT-facing input) as the workaround. A PDF
parser (text + embedded-plot digitisation) is a substantial I/O capability;
the structured-workbook workaround is adequate for procurement. Filed as
Gap 55, Low priority.

## Friction / lessons

- **The binding requirement can be infeasible for all proposals.** Here no
  vendor meets GSD ≤ 1.5 m from 600 km with their f/# — a genuine
  procurement finding (the requirement, orbit, and optics are inconsistent),
  not a modelling artifact. The compliance matrix surfaces it cleanly.
- **A tiny pixel can zero MTF@Nyquist** (Vendor C, Q ≫ 2): fine sampling
  flatters GSD/NIIRS but wastes the pixel on unresolvable detail — the radar
  chart makes this trade visible.
- **NIIRS leverage is resolution, not SNR** (GSD/RER ≈ 2× the SNR lever per
  10 %), because NIIRS is logarithmic in an already-high SNR. Reused
  `giqe5_sensitivity` for this without new code.
