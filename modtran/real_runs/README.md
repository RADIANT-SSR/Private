# Real MODTRAN 6 run set (tracked in git as of 2026-08-02)

Delivered by the owner 2026-07-17: the 39-run matrix of
`docs/plans/modtran_run_matrix.csv` (A1–H4) — 39 `<run_id>.tp7` tape7
outputs plus 4 Block-E `*_flux.csv` spectral-flux sidecars (E1–E4).

This data is LOCAL-ONLY and irreplaceable without a MODTRAN license:
it is deliberately gitignored (fixture subset committal is plan §7.1),
so treat this directory as precious. Provenance: MODTRAN 6-family
build (Card-1 echo `M F 6…`); deck conventions verified CU-065/CU-067.

Re-staged 2026-07-20 from the owner's original delivery folders
(`~/Downloads/ModTranRuns1`, `ModTranRuns2`, `Flux`, `Flux2`) after a
tracked-symlink checkout clobbered the directory (see the 2026-07-20
`fix(repo)` commit); integrity re-verified against the pinned band-mean
goldens in `tests/integration/test_modtran_real_runs.py`.

Boost-ladder expansion deliveries (G7–G11, I1–I9, H5, J1–J2 — 17 runs,
plan §3) land here as `<run_id>.tp7` alongside the originals.

## Batch-2 delivery (2026-08-02)

35 of the 37 batch-2 rows delivered (M1–M8, N1–N10, O1–O5, P1–P6, Q1–Q4,
Q7, Q8), run on the owner's MODTRAN machine and transferred by folder copy
(`~/Downloads/20260802` + `20260802_2`). All 35 parse through `Tape7Reader`
(25 976 spectral points each, τ ∈ [0, 1], no NaN).

- **Q5/Q6 were not run** (refraction on/off pair): the owner's deck audit
  found no refraction switch was exercised, and running them without one
  would duplicate Q3/M8 with a meaningless zero delta — per the batch-2 run
  note, the horizon-guard thresholds stay guard-banded (ADR-0011 decision 5).
- **Q7/Q8 hand-edits verified** in the tape7 card echoes: Q7 H1=20 km,
  ANGLE=93.000, LENN=1, path 1439.94 km; Q8 H1=50 km, ANGLE=96.000, LENN=1,
  path 1744.52 km; both IEMSCT=2 (the below-horizon-sun radiance path ran;
  the τ_sun anchor reads TOT TRANS, which is solar-source-independent).
