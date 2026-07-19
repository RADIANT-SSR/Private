# Output Manifest

Produced by `scripts/run_boost_phase_target_altitude_sweep.py`, which sweeps
`geometry.target_altitude_m` (0–300 km) against the shipped interpolated
atmosphere library `data/atmospheres/midlat_summer_ladders/` (no external input
file — the config is defined in the runner). Regenerate by running the script
from the repo root:

    python scenarios/08_interpolation_demonstrations/8.3_boost_phase_target_altitude_sweep/scripts/run_boost_phase_target_altitude_sweep.py

| Artifact | Kind | Last generating commit |
|---|---|---|
| fig1_boost_phase_tau_vs_altitude.png | figure (committed) | (this PR) |
