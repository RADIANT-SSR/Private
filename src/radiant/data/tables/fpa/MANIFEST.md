# FPA Preset Library — Manifest

**Status:** Tranche 1 shipped (plan §4.4, 2026-09-06): geosnap-18, geosnap-10,
flir-neutrino-lc, flir-boson-plus-640, teledyne-h2rg-2p5, dfpa-generic.
`configs/` holds the generated loadable RADIANT configs (one per preset,
rendered by `scripts/gen_fpa_configs.py` — Rule 26 generated artifacts,
freshness-gated by `tests/test_fpa_configs_current.py`).

One YAML per part, filename `<name>.yaml` (lowercase, hyphenated slug), format
version 1 per `docs/plans/FPA_Preset_Library_Plan.md` §3.1. Loaded and
format-validated by `radiant.data.fpa.FPALibrary`; schema conformance of every
shipped preset is asserted by `tests/test_fpa_presets.py` (lands with the first
part, plan §6).

Contract highlights:

- Values are stored in the **cited document's native unit**; conversion to
  RADIANT canonical units happens at apply time via
  `ParameterSet.set(..., unit=...)` (Rule 2).
- Every value carries `source`/`basis`/`location` attribution; `basis: assumed`
  values carry a justification `note` instead.
- Cited reference documents (the PDFs) live at
  `docs/validation/fpa_datasheets/` with hashes in that folder's `MANIFEST.md`;
  they are repo-only (excluded from the wheel) — the citation URL/DOI is what a
  wheel user gets.
- Presets set `detector.*`/`readout.*` parameters only (owner-confirmed scope,
  plan §8.2.4).
