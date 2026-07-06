# ADR-D: Parameter Naming — Unit Suffixes Are Canonical

**Date:** 2026-07-06
**Status:** Accepted

## Context

The 2026-07-06 architecture audit found a direct contradiction between two
documented naming conventions:

- `docs/RADIANT_Parameter_System.md` (naming rule #2) and
  `docs/RADIANT_Config_Format.md` (§1.2) mandate **no unit in the parameter
  name** — "`aperture_diameter` not `aperture_diameter_m`" — and a strict
  depth-2 `category.parameter_name` namespace with a `sensor.` prefix in
  examples.
- The shipped code, `docs/RADIANT_File_Tree.md` (§ parameter naming), and
  `docs/RADIANT_Conventions.md` §5 all use **unit-suffixed** names:
  `optics.aperture_diameter_m`, `detector.pixel_pitch_x_um`,
  `platform.jitter_rms_urad`, `atmosphere.visibility_km`. Roughly 58 of the
  ~129 `ParameterDef` names in `*/_schema.py` carry a unit suffix, and four
  namespaces nest to depth 3 (`source.target.*`, `source.background.*`,
  `optics.stray.*`, `atmosphere.modtran.*`). No `sensor.*` prefix exists
  anywhere in the schema.

One side had to become the law; the other had to be rewritten.

## Decision

**The code convention is canonical.** Recorded rules:

1. **Unit suffix required** on every parameter whose value is dimensioned:
   the suffix names the **input unit** — the unit a user supplies to
   `params.set()` — exactly as declared in the schema's `input_unit`
   (`_m`, `_um`, `_urad`, `_K`, `_rad`, `_s`, `_hz`, `_km`, `_cm`,
   `_e` (electrons), `_e_per_s`, `_e_rms`, `_m_s`, `_W_m2`, `_cm1`,
   `_eV`, `_ohm_cm2`, `_pct`, `_waves`, `_per_dn`, `_F`, …).
   Examples: `detector.pixel_pitch_x_um` (input µm, canonical m),
   `platform.jitter_rms_urad` (input µrad, canonical rad).
   Dimensionless parameters (ratios, counts, flags, enums) carry no suffix.
2. **Namespace depth is 2 or 3**: `stage.parameter_name` or
   `stage.group.parameter_name` where the group names a cohesive sub-model
   (`optics.stray.*`, `atmosphere.modtran.*`, `source.target.*`,
   `source.background.*`). No `sensor.` super-prefix.
3. Names remain lowercase with underscores; no camelCase.

`RADIANT_Parameter_System.md` and `RADIANT_Config_Format.md` are rewritten to
this convention in the same change set (2026-07-06 doc-reconciliation pass).

## Rationale

1. **Self-documenting inputs.** A user typing
   `params.set("optics.aperture_diameter_m", 0.3)` states the unit at the
   point of use. With unit-free names the unit lives only in the schema, and
   a wrong-unit guess (mm vs m) validates silently if it lands in bounds.
   For a physics tool whose Rule 2 makes unit discipline load-bearing, the
   redundancy is protective, not noise.
2. **Zero churn, zero breakage.** Renaming ~58 parameters would touch every
   schema, YAML config, scenario script, GUI binding, and golden test for a
   purely cosmetic outcome, and would require a deprecation-alias layer in
   `ParameterSet` that outlives everyone's patience.
3. **The suffix names the input unit, which is part of the parameter's
   contract.** Changing a parameter's input unit changes what user-supplied
   numbers mean — a rename would be *appropriate* then, so the suffix
   cannot silently rot.
4. **Depth-3 groups are cohesive sub-models,** not namespace sprawl: MODTRAN
   configuration and stray-light configuration are meaningful bundles that
   would otherwise need a `modtran_`/`stray_` name prefix — the same depth
   information, encoded worse.

## Consequences

- The suffix names the input unit; the canonical unit may differ
  (`detector.pixel_pitch_x_um` accepts µm, stores meters; the boundary
  conversion in `core/parameters.py::_validate_and_convert` is unchanged).
  The schema remains the single source of truth for conversion; the suffix
  is a human affordance, not a parser input.
- New parameters MUST follow this convention; reviewers reject unit-free
  names for dimensioned quantities (Rule 12 review point).
- The naming sections of `RADIANT_Parameter_System.md` and
  `RADIANT_Config_Format.md` cite this ADR.
