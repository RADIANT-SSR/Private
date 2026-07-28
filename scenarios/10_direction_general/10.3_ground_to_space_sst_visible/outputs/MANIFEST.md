# Outputs manifest — scenario 10.3 (ground-to-space SST, visible)

Every committed artifact, its generator, and its input. Regenerate everything with

```bash
cd scenarios/10_direction_general/10.3_ground_to_space_sst_visible
python inputs/create_spreadsheet.py            # only if the vendor inputs changed
python scripts/run_ground_to_space_sst_visible.py
```

Runtime of the runner: ~2 s on a 2023 laptop. Committed under Rule 26 clause (b) —
each figure is referenced by `walkthrough.md`.

| Artifact | Generator | Input | Referenced by | Committed |
|---|---|---|---|---|
| `signature_and_column_transmittance.png` | `scripts/run_ground_to_space_sst_visible.py` → `make_figures()` | `inputs/object_signature_ORB-4471.csv`, `inputs/sst_site_and_tasking.xlsx` | `walkthrough.md` §3, §5 | yes |
| `terminator_shadow_height.png` | same, `make_figures()` | `inputs/sst_site_and_tasking.xlsx` (`Terminator Ladder`) | `walkthrough.md` §6 | yes |
| `seeing_vs_diffraction_mtf.png` | same, `make_figures()` | `inputs/sst_site_and_tasking.xlsx` (`Seeing`) | `walkthrough.md` §7 | yes |
| `zenith_ladder.png` | same, `make_figures()` | `inputs/sst_site_and_tasking.xlsx` (`Zenith Ladder`) | `walkthrough.md` §8 | yes |
| `ground_to_space_sst_results.xlsx` | same, `write_results_workbook()` | as above | — | **no** (gitignored via `scenarios/*/*/outputs/*.xlsx`, Rule 26 regenerate-on-demand) |

Commit that produced this set: the commit introducing
`scenarios/10_direction_general/10.3_ground_to_space_sst_visible/` on branch
`gf5/ground-to-space`. Regenerating on a later RADIANT revision may move the
numbers; the walkthrough tables record the values as of that commit.

## Committed derived input (Rule 26)

| Artifact | Generator | Input | Why committed |
|---|---|---|---|
| `inputs/object_signature_radiant_um.csv` | `scripts/run_ground_to_space_sst_visible.py::write_canonical_signature` (regenerated deterministically on every run and by `make_sensor()`) | `inputs/object_signature_ORB-4471.csv` (vendor nm / W·sr⁻¹·nm⁻¹ signature) | Referenced by the GUI baseline `inputs/10.3_ground_to_space_sst_visible.gui.yaml` (`source.target.user_intensity_path`, relative) — part of the baseline the verify gate asserts against; a temp-dir path was unportable (Phase-5 gate finding) |
