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
