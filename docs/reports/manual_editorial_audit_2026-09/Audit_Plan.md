# Manual Editorial Audit — Charter

**Status:** Complete
**Date:** 2026-09-17
**Trigger:** Owner direction 2026-09-17 ("auditing, evaluating, scrutinizing and analyzing the four generated RADIANT manuals … make a master list of all findings"), immediately after Gap 131 closure.

## Scope

An expert technical-editing audit of the four shipped RADIANT manuals (Gap 131 suite,
built by `scripts/build_manual.py`):

| Vol | Title | Sources | Rendered PDF audited |
|---|---|---|---|
| I | Theory Manual | `docs/theory/*.md` (10 chapters per `VOLUMES`) | `build/manuals/radiant_theory.pdf` (91 pp.) |
| II | User's Guide | `docs/guides/ug_*.md` + menu appendix | `build/manuals/radiant_users_guide.pdf` (97 pp.) |
| III | Technical Reference | `docs/guides/tech_*.md`, `scripting.md`, `configuration.md`, `parameter_reference.md`, three bound architecture specs | `build/manuals/radiant_tech_ref.pdf` (161 pp.) |
| IV | Worked Examples & Validation | `docs/guides/examples_*.md`, `trade_studies.md`, scenario index appendix | `build/manuals/radiant_examples.pdf` (162 pp.) |

**Evaluated for:** common voice across and within volumes; consistency of formatting
conventions; formatting/rendering bugs in the typeset PDFs; grammar and usage errors;
extraneous content; verboseness; cross-volume consistency (terminology, notation,
units style, cross-references); adherence to the project's own standard
(`docs/OPERATING_MODEL.md` §5.4, `docs/theory/notation.md`, the ratified
Support Documentation Plan rulings).

**Scope boundaries (defaults stated to owner 2026-09-17, ratified "go"):**

1. Both forms audited — Markdown sources (canonical, `file:line`) and rendered PDFs
   (render-only defects, PDF page cites).
2. Vol III Part 3 bound-verbatim architecture specs (ruling Q2) and the generated
   parameter reference: outright errors only; voice/tone mismatch there is by design
   and is not a finding.
3. Read-only audit — findings are recorded, not fixed. Fixes are follow-on work.

## Method

One editorial-review agent per volume (source pass + full rendered-PDF pass), each
returning structured findings and a style fingerprint; a cross-volume consistency
analysis over the four fingerprints; findings compiled, deduplicated, severity-ranked,
and dispositioned per Rule 28 in `Findings.md` (this folder).

## Disposition rule

Editorial findings are dispositioned inside `Findings.md`. Any tooling defect
uncovered in passing (builder, filters, generators) is recorded per Rule 21
(CU or Findings_Log line) separately from the editorial list.
