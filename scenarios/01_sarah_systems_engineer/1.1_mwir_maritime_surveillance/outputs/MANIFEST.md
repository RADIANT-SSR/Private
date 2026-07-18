# Output Manifest

All artifacts below are produced by `scripts/run_mwir_maritime_surveillance.py`,
which reads `inputs/insb_qe_representative.csv` and the real MODTRAN 6
`D2` run (`modtran/real_runs/D2.tp7`, gitignored staging set — see
`modtran/real_runs/README.md`) when staged, falling back to
`modtran/synthetic/D2.synthetic.tp7` (regenerate with
`python scripts/generate_synthetic_tape7.py --run-id D2`) with a loud
banner. Regenerate by running the script from the repo root. The
committed figure is from the **real** data.

| Artifact | Kind | Data source | Last generating commit |
|---|---|---|---|
| fig1_snr_and_range_vs_aperture.png | figure (committed) | real MODTRAN 6 (2026-07-17) | see `git log -1 -- <file>` |
