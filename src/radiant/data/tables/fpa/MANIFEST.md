# FPA Preset Library — Manifest

**Status:** Phase 0 home (Gap 119) — format v1 defined, no parts shipped yet.
Tranche 1 (plan §4.4) lands the first presets.

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
