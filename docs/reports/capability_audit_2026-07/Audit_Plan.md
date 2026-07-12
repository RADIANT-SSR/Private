# Capability Audit — Charter (Rule 28)

**Status:** Complete (2026-07-11) — findings in `Findings.md`, recommendation in `Recommendation.md`; all findings dispositioned (Gaps 67–80, CU-072–086, `docs/plans/Pre_GUI_Hardening_Plan.md`)
**Chartered by:** Project owner (Jason), 2026-07-11
**Auditor:** Claude (coding agent), multi-agent sweep
**Folder:** `docs/reports/capability_audit_2026-07/`

## Objective

Pre-GUI capability audit of RADIANT from a capabilities-and-usefulness
perspective: identify missing core functionality and capability gaps that
should be resolved (or consciously deferred) before significant investment
in GUI development. RADIANT is an internal single-company tool; the framing
is "cool, useful, expandable" — not competitive market positioning.

## Scope

In scope (read-only — the audit modifies no source code):

1. **Capability inventory** — every stage schema and physics surface
   (`src/radiant/*/`), the public API (`api/`, `cli/`), I/O and data
   layers (`io/`, `data/`), and existing GUI groundwork (`dev_tools/`).
2. **Persona demand vs. supply** — all 7 personas and 35 scenarios
   (`scenarios/`): what each user needs, what is implemented, what is
   evidenced, what the `gui_workflow.md` files demand of a GUI.
3. **Registry triage** — open/deferred entries in `docs/tracking/gaps.md`
   and open CUs in `docs/tracking/Cleanup_Backlog.md`, classified as
   GUI-blocking / fix-before-GUI / fine-after-GUI.
4. **Interactivity probe** — measured single-run chain latency, as input
   to GUI architecture decisions.
5. **Expandability & UX review** — onboarding docs, examples, exports,
   session persistence, uncertainty outputs.

Out of scope:

- Competitive/market comparison against external tools (owner declined).
- Any code changes. Findings are dispositioned, not fixed, in this audit.
- **Firm findings against `atmosphere/` MODTRAN functionality** — a
  concurrent effort is modifying that area during this audit. Observations
  there are recorded as PROVISIONAL and must be re-checked against the
  landed MODTRAN work before acting.

## Method

Multi-agent workflow: parallel read-only inventory agents per package area
and per persona, a chain-latency probe, adversarial verification of every
candidate "missing capability" claim (grep-refutation pass), followed by
synthesis into `Findings.md` and a prioritized pre-GUI punch list in
`Recommendation.md`.

## Disposition rule (Rule 28)

Every finding in `Findings.md` carries exactly one disposition:
**CU'd** (entry filed in `Cleanup_Backlog.md` or gap filed in `gaps.md`),
**Planned** (referenced plan in `docs/plans/`), or **Declined** (one line
of rationale). The audit is complete only when all findings are
dispositioned and this file's Status is set to Complete.
