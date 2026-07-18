# Output Manifest

Produced by `scripts/run_off_nadir_interpolation.py` via
`scripts/synth_modtran/family_interpolate.py`, which reads the real
MODTRAN 6 zenith fan (`modtran/real_runs/A1,B1,B2,B3.tp7`, 2026-07-17
set, gitignored staging — see `modtran/real_runs/README.md`) when
staged, falling back to `modtran/synthetic/*.synthetic.tp7` (regenerate
with `python scripts/generate_synthetic_tape7.py`) with a loud banner.
Regenerate by running the script from the repo root. The committed
figure is from the **real** data.

| Artifact | Kind | Data source | Last generating commit |
|---|---|---|---|
| fig1_interpolation_vs_nearest_neighbor.png | figure (committed) | real MODTRAN 6 (2026-07-17) | see `git log -1 -- <file>` |
