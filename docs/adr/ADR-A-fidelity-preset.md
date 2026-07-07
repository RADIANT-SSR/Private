# ADR-A: FidelityPreset — Drop from Roadmap

**Date:** 2026-04-25
**Status:** Accepted

## Context

`RADIANT_Spatial_Complete.md` and `RADIANT_Optics.md` describe a `FidelityPreset` enum (`draft` / `standard` / `high`) that would gate:
1. Whether the dual-path PSF/MTF consistency check runs
2. Pupil grid size
3. Marechal-approximation vs full-OTF dispatch

The 2026-04-25 audit ([Doc_Drift_Report.md#D2](../reports/architecture_audit_2026-04/Doc_Drift_Report.md)) found that `FidelityPreset` does not exist in `src/radiant/`. The behavior the docs ascribe to it is implemented through other mechanisms:

- The dual-path consistency check ([performance/consistency_check.py](../../src/radiant/performance/consistency_check.py)) runs **unconditionally** with hardcoded `tolerance = 5e-2`, independent of any preset. It is actively load-bearing — it caught CU-003 (the rect-kernel discretization mismatch on `swir_aerial_gas.yaml` at low Q).
- Marechal-vs-full-OTF selection is dispatched through a separate mode mechanism in `optics/`, not gated by a fidelity preset.
- Pupil grid size is a fixed parameter, not preset-controlled.

The doc therefore describes a system that was never built. The audit framed this as Bucket A or Bucket C depending on roadmap intent: A if the team had de-scoped FidelityPreset, C if it was still on the roadmap.

## Decision

**Drop `FidelityPreset` from the roadmap.** Remove all references to it from the architecture documentation. No code change is required (nothing exists to remove).

## Rationale

The unconditional consistency check is doing the job the `standard` preset would have nominally enabled, and it is doing it for every run — which is the safer default than gating it behind a preset. A `draft` mode that turns the check off would weaken the architectural commitment to Rule 4 (dual-path consistency invariant) for marginal speed gains that nobody is currently asking for.

Adding `FidelityPreset` now would be a pure refactor: it would introduce a new public API surface (the enum, parameter wiring, dispatch logic) without delivering a new capability. It is the wrong shape of work for a young codebase that has just passed an audit recommending Continue + Cleanup.

If high-fidelity pupil grids or full-OTF dispatch later become expensive enough that batch sweeps need a `draft` mode, the right move is to file a fresh Category B task at that time. Gating already-existing knobs behind a preset is a small, well-scoped change once the actual performance pressure exists.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| Drop (chosen) | Doc matches code immediately; consistency check stays mandatory; no new public surface | Loses the option of a `draft` mode for fast sweeps until refiled |
| Keep on roadmap as Category B | Preserves a future fast-sweep escape hatch; codifies what each level gates | Adds a public-API surface with no current consumer; risks weakening Rule 4 if `draft` disables the consistency check |
| Implement now | Resolves the doc/code drift in code rather than docs | ~Week of refactor for zero new capability; rejected as premature |

## Consequences

- **Positive:** Doc-vs-code drift on the largest spec drift item resolves to a doc cleanup. Rule 4's consistency check remains unconditional and mandatory — no future PR can disable it through a preset selection.
- **Negative:** No fast-sweep mode exists. If `BatchRunner` workloads later hit a wall on pupil-grid cost, a follow-on task will be needed to add gating.
- **Neutral:** The Marechal-vs-full-OTF dispatch and pupil grid size parameters retain their current shape (mode dispatch and fixed parameter, respectively).

## Downstream Tasks Unblocked

This decision unblocks the following audit reconciliation tasks (see [docs/reports/architecture_audit_2026-04/Reconciliation_Tasks.md](../reports/architecture_audit_2026-04/Reconciliation_Tasks.md)):

- **R2.A1** — Rewrite `RADIANT_Spatial_Complete.md`. The new `RADIANT_Spatial_Architecture.md` MUST remove all `FidelityPreset` references. The unconditional consistency check (tolerance `5e-2`, runs on every chain execution) is the documented behavior.
- **R2.A1** — `RADIANT_Optics.md` `FidelityPreset` references must be removed in the same pass.

No code task is filed; nothing exists in `src/` to remove.

## References

- [docs/reports/architecture_audit_2026-04/Doc_Drift_Report.md#D2](../reports/architecture_audit_2026-04/Doc_Drift_Report.md)
- [docs/reports/architecture_audit_2026-04/Reconciliation_Tasks.md](../reports/architecture_audit_2026-04/Reconciliation_Tasks.md) §R1.1
- [docs/reports/architecture_audit_2026-04/Recommendation.md](../reports/architecture_audit_2026-04/Recommendation.md)
- [src/radiant/performance/consistency_check.py](../../src/radiant/performance/consistency_check.py) — the unconditional check this ADR formalizes as the design
- CLAUDE.md Rule 4 — Dual-Path Spatial Architecture (the rule the unconditional check enforces)
