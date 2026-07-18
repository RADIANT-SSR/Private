# Output Manifest

All artifacts below are produced by `scripts/run_atmospheric_intercomparison.py`,
which reads the real MODTRAN 6 A-block (`modtran/real_runs/A1-A6.tp7`,
gitignored staging set — see `modtran/real_runs/README.md`) when staged,
falling back to `modtran/synthetic/A1-A6.synthetic.tp7` (regenerate with
`python scripts/generate_synthetic_tape7.py`) with a loud banner.
Regenerate by running the script from the repo root. The committed
figures are from the **real** data.

| Artifact | Kind | Data source | Last generating commit |
|---|---|---|---|
| fig1_transmittance_overlay_by_profile.png | figure (committed) | real MODTRAN 6 (2026-07-17) | see `git log -1 -- <file>` |
| fig2_inband_transmittance_by_profile.png | figure (committed) | real MODTRAN 6 (2026-07-17) | see `git log -1 -- <file>` |
