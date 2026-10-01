# Dispositions — external review 2026-09-30

**Status:** Complete (point-in-time record, Rule 24 — immutable)
**Date:** 2026-09-30
**Ruled by:** project owner, 2026-09-30, in session.

Rule 28 requires every finding to carry one of three dispositions: **CU'd**
(Rule 21), **Planned** (`docs/plans/`, Rule 24), or **Declined** with one line
of rationale. Capability additions are **Gap'd** per Rule 25, which governs
them instead of the CU registry.

---

## Findings

| # | Finding | Disposition | Entry |
|---|---|---|---|
| 1 | Warm optics silently zero in non-prescription transmission modes | **CU'd** + Planned | [[CU-380]] |
| 2 | 1/f noise: no corner frequency, timing-decoupled bandwidth, co-add averages correlated power | **CU'd** (family) + Planned | [[CU-381]] |
| 3 | `dark_rate_e_per_s` ceiling excludes real LWIR parts | **CU'd** + Planned | [[CU-382]] |
| 4 | `validate` passes configurations `evaluate` rejects | **CU'd** | [[CU-383]] |
| 5 | Studies cannot express architecture-conditional parameters | **CU'd**, owner-gated | [[CU-384]] |
| 6 | CLI crashes on a default Windows console (cp1252) | **CU'd** + Planned | [[CU-385]] |
| 7 | Tests write a tracked file, corrupting export provenance | **CU'd** + Planned | [[CU-386]] |
| — | *(triage finding)* scenario `gaps.md` is an unpromoted fourth registry | **CU'd**, owner ruling requested | [[CU-387]] |

## Recommended outputs and interop

| Item | Disposition | Entry |
|---|---|---|
| #1 warn on silently-zero dominant terms (general rule) | **Gap'd** — folded into the breakdown, which subsumes it | [[Gap 132]] |
| #2 background-composition breakdown | **Gap'd** | [[Gap 132]] |
| #3 per-term co-add scaling exponent + correlation class | **Gap'd** | [[Gap 133]] |
| #4 echo derived and converted quantities | **Gap'd** | [[Gap 134]] |
| #5 photon-unit NER/NEI; dark-current density input | **Gap'd** | [[Gap 135]] |
| #6 detection range when below threshold | **Gap'd** | [[Gap 136]] |
| Acceptance-cone convention doc note | **Findings Log** — fails all four intake tests | `Findings_Log.md` 2026-09-30 |
| 1/f α-form (signal-proportional) input mode | folded into [[CU-381]] | — |
| DFPA gain / well semantics confusion | **Declined** — RADIANT's refusal of an explicit `full_well_capacity_e` under `digital_counting` is the designed guard and the reviewer confirmed it caught a real overflow; the remaining confusion is documentation, covered by [[Gap 134]]'s derived-well echo | — |

---

## Declined within CU-380

Both are from the report's own suggested-fix list for Finding 1.

- **Fix #2 — promote to an error when the band is thermal.** Declined: a
  cryogenic telescope legitimately has ~zero warm-optics emission, and the
  proposed `filter_max_um > 3` trigger would hard-fail 39 of RADIANT's own
  scenario files. The warning is the fix; the error is a new footgun.
- **Fix #3 — add a lumped-emissive convenience (scalar ε + T).** Declined: a
  scalar ε and T on a lumped element with no reflectance/transmittance
  decomposition is exactly the over-specification Rule 5 forbids, and it
  reverses the 2026-09-10 owner ruling that removed `optics.optics_temperature_K`
  on that ground. The Rule-5-conforming route is for the warning text to point
  at the `optical_elements:` train, which costs nothing extra.

## Ruling on Finding 2's approach

The report offered three options of increasing fidelity. The owner ruled
2026-09-30 for the **first-principles replacement** over the staged patch
("We're fixing it, let's do it right"): the measurement's actual noise transfer
function, in which all three checklist defects dissolve into limits of one
integral rather than being patched individually. Design recorded in
[[CU-381]]'s suggested-fix field and in the execution plan.

One correction to the report's option 1: reclassifying `flicker_1f` as
correlated by moving it into `SPATIAL_TERMS` would mis-report it as
fixed-pattern in the temporal/spatial RSS split. 1/f **is** temporal noise; the
RSS classification is already right and only the scaling dispatch is wrong.

## Scope note

Finding 1's remediation covers `examples/` and the 5 point-source scenarios.
The 34 extended-scene thermal scenarios are left emitting the new warning, for
the chartered scenario sweep to take — their walkthrough narratives quote
numbers that would all need rewriting, which is a sweep, not a CU. That
deferral is recorded in CU-380 rather than left implicit.
