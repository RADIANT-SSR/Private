# Atmosphere Documentation Plan

**Status:** Active — opened 2026-08-03 (owner-chartered in session; scope ratified verbally:
"draft the plan and then let's execute", with the explicit constraint **docs-only — no code,
no tests, no `src/` edits of any kind**).

## Charter

The atmosphere subsystem grew past what one architecture document can serve: 41 modules,
33 parameters, 44 warning sites, 266 raise sites, four backends (simple, interpolated,
tabulated, MODTRAN import) plus the hybrid composition, five path topologies, and a week of
MODTRAN-anchored physics landings whose measured parity tables live only in CU Resolved
records. `docs/architecture/RADIANT_Atmosphere.md` (1,443 lines, 42 sections) has become an
everything-document organized by change history. This plan re-homes its content along the
`docs/OPERATING_MODEL.md` §1 taxonomy so each reader class has one document, then slims the
architecture doc back to the contract.

**Ground rules.** Docs-only: zero changes under `src/`, `tests/`, `scripts/`, `scenarios/`.
Every quantitative claim in the new documents cites its enforcement — the anchor test,
golden, or runner output that pins it (no new normative claim without an existing enforcer;
the aspirational-drift rule). Re-homing, not rewriting: measured tables move verbatim with
their provenance (CU number, branch, date). Rule 23 placement; Rule 24 lifecycle (this plan
archives when P-D3 merges). Docs-only gate battery per merge (org rules, doc-parsing tests,
ruff on untouched trees confirming untouched).

## Work packages, in run order

**P-D1 — Theory + validation extraction (no owner gate).**
Create `docs/theory/atmosphere_models.md`: the physics of both model families with
derivations — single-scatter solar form and species-split weighting (CU-260/P4), the
CU-161 curve-of-growth linearisation and slant-column convention (CU-320), the gas-region
smoothstep blend (CU-267), spherical/near-horizon air mass (CU-275/P4), the level
whole-path evaluator (CU-276/P4), the escape-resolved layered emission temperature
(CU-321), log-τ interpolation/resampling (CU-306/316), and the interpolated-family
axis/vacuum-equivalence identities. Follows the `spatial_model.md` conventions (Pandoc
math, §5.4).
Create `docs/validation/atmosphere_modtran_parity.md`: the measured-accuracy record
against the 127-run set — model × band × geometry-class parity tables extracted from the
CU-224/320/321 records and the anchor suites (`test_emission_temperature_anchors`,
`test_species_split_anchors`, `test_segment_modtran_anchors`, `test_batch2_*`), each table
naming the test that pins it, plus the known-limitations register (CU-161 spectral shape,
VIS provisional sky, refraction guard-banding, the CU-324 refinement family, unrun decks
P7/P8 + M9–M13 + Q5/Q6).

**P-D2 — Operator selection guide (owner review gate before merge).**
Create `docs/guides/atmosphere_selection.md` on the `regime_selection.md` precedent: the
scene-class → model/family decision tree (mirroring `family_suitability.py`'s gate order),
the shipped-family catalogue with unit-bearing coverage lines, per-scenario availability
summary (26 first-try / 12 single-advisory, from the sweep test), and a catalog of the
operator-visible warnings and refusals with their meaning and remedy (hybrid two-model
warning, CU-167 non-axis mismatch, provisional VIS sky, coverage/ceiling/lower-endpoint
refusals, the exo guard's two arms). **The owner reads this document before it merges** —
it encodes judgment about what an operator should reach for. **Ratified by the owner
2026-08-03 ("guide ratified", in session) — merged on that ratification.**

**P-D3 — Slim the architecture doc (after D1/D2 merge).**
`RADIANT_Atmosphere.md` returns to the architecture contract: products and the
`AtmosphericQuantities` shape, backend seams and dispatch, topology composition, the guard
architecture, invariants, and cross-references to the three new homes. Zero content loss:
the PR records a moved-section ledger (old § → new home) so every claim's destination is
auditable. Target ≈600 lines.

## Acceptance

- Each new document's quantitative claims carry a source citation (test path or CU record);
  no claim without an existing enforcer.
- Rule 23: nothing new at `docs/` top level; the three documents land in their taxonomy
  homes; the plan archives on P-D3's merge with the moved-section ledger in that PR.
- The owner has read and ratified `atmosphere_selection.md` before its merge.
- Zero non-docs diffs across all three packages (verified per merge).
