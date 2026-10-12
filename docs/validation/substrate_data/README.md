# Substrate material library — provenance and generator of record

**Status:** Active — live provenance for a shipped data product. Moved here from
`docs/plans/substrate_data_proposed/` on 2026-10-12, when the plan it was a
companion to completed (`docs/archive/Refractive_Substrate_Emission_Plan.md`,
delivered as Gap 142 in v0.4.0).

This folder is not a plan and not an archive. It is the set of inputs the shipped
substrate tables were built from, kept live because Rule 26 requires every
committed generated artifact to name its generator, and this is that generator.

## What ships, and what does not

The ratified library is `src/radiant/data/tables/substrates/` — six materials
(germanium, silicon, zinc selenide, multispectral zinc sulphide, calcium
fluoride, barium fluoride), read by `radiant.data.substrate`, shipped in the
wheel. Nothing in *this* folder ships; it is repo-only, the same arrangement as
`docs/validation/fpa_datasheets/` under Rule 26(c).

The two extra candidates here — sapphire and fused silica — were **declined** by
the study (§7.1: one α anchor each). Their inputs and generated tables are kept
because the declining argument is only checkable against them.

| Path | What it is |
|---|---|
| `<material>.yaml` | Generator input: the dispersion-formula or table reference for n(λ), plus the published laser-line α anchors. The shipped YAML is this file plus the shipped-only fields — `tier` on all six, and `valid_temperature_K` (germanium) or `display_name` (multispectral ZnS) where needed. |
| `build_substrate_tables.py` | **Generator of record** (Rule 26) for the shipped `*.csv`. Run from the repo root. |
| `tables/` | This generator's own output, all eight candidates. The six ratified CSVs are byte-identical to the shipped copies; `src/radiant/data/tables/substrates/` is the canonical location that `radiant.data` reads. |
| `sources/` | The exact byte streams retrieved from refractiveindex.info and vendor material pages, with SHA-256, URL and retrieval date in `sources/MANIFEST.md`. The Rule 26(c) datasheet-equivalent subtree. |
| `grade_substrate_data.py` | Three-tier grading harness — pushes this data through the shipped `CavityModel` and compares against published vendor reflection losses. Study §8. |
| `ge_alpha_temperature.py` | Study §7.2: whether germanium's α(λ,T) forces a temperature axis. Concluded no; the shipped tables are α(λ) at 293 K with a declared validity window. |
| `n2_derivation.py` | Study §7.3: the derivation that found the shipped cavity `eps_eff` carried an uncancelled n² factor. Became CU-396. |

## Regenerating

```bash
python docs/validation/substrate_data/build_substrate_tables.py          # -> tables/
PYTHONPATH=./src python docs/validation/substrate_data/grade_substrate_data.py
```

The generator writes to `tables/` here, never to the shipped tree — promoting a
regenerated table into `src/radiant/data/tables/substrates/` is a deliberate
copy, so that a re-run cannot silently move a shipped number or add a declined
material to the library.
