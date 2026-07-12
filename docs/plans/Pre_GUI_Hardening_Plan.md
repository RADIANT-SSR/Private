# Pre-GUI Hardening Plan

**Status:** Active (activated 2026-07-11; audit landed in `bf70f73`)
**Source:** `docs/reports/capability_audit_2026-07/` (Findings + Recommendation)
**Goal:** close the GUI-blocking and fix-before-GUI registry items so GUI development
starts on a stable, honest surface. This plan references registry entries; it does not
re-enumerate them (Rule 25).

## Phase 1 — GUI binding surface (blocking) — ✅ COMPLETE 2026-07-11

Order chosen so each item unblocks the next: introspection feeds persistence feeds the
GUI contract. All five items landed 2026-07-11; registry entries closed with SHAs.

1. ~~Gap 70~~ — public schema-introspection API (`5a42649`; all five `_defs`/`_groups`/
   `_inputs`/`_tolerances`/`_resolved_flag` consumers migrated).
2. ~~Gap 67~~ — `Sensor.save/load` + `ChainResult.save/load` round-trip (`addcf43`).
3. ~~Gap 71 + CU-078~~ — metric units/metadata contract; registry reconciled,
   CI-enforced (`68e1fec`).
4. ~~Gap 68~~ — non-scalar input reachability: `Sensor.set_stage_output` +
   `evaluate(extra_stage_outputs=)`; transmission modes 2–4 and stray `spectral_file`
   wired to injections; `opd_map`/`pst_file` un-advertised (`5d338d9`).
5. ~~Gap 72 + CU-072 + CU-073~~ — progress/cancel hooks; parallel-sweep pickle
   fallback fixed; `UnknownParameterError` (`537a3a8`).

## Phase 2 — correctness and demo-safety

6. Gap 73 — point-source background/path photon noise.
7. CU-074, CU-083 — fill_factor dual-path; IPC kernel spacing.
8. Gap 74 (minimum slice) + Gap 75 — TDI/t_int feasibility constraint; orbit-derived
   ground velocity; collapse duplicate ground-speed/altitude parameters.
9. Gap 77, Gap 78 — SCNR metric + in-chain detection-range solver; surface Pd/DRI/NEDL/
   NEDR/D*-family metrics.
10. CU-076, CU-081, CU-085 — enum validation, dark-current default trap, validation sweep.
11. Gap 81 — MODTRAN downwelling ingestion (`tape7_down_path`, mirroring the landed
    `tape7_sun_path` pattern) so the model dropdown doesn't silently drop thermal-band
    background terms; CU-088 — LWIR aerosol clamp (small, doc-planned).

## Phase 3 — honest documentation before GUI speccing

12. CU-079 — re-banner or reconcile the aspirational "Authoritative" docs; refresh
    `RADIANT_GUI_Architecture.md` dot-paths against shipped `_schema.py`.
13. CU-075 — scenarios/README status table.
14. Scenario reruns for post-fix gaps (registry "rerun after fix" fields: Gaps 37/42/65/66
    originating scenarios).
15. Script-window dependency spike (embedded IPython + PySide6 sharing the sensor
    namespace) — de-risk the standing requirement before GUI kickoff.

## Explicitly out of this plan

CU-086 re-audit is complete (2026-07-11, correction doc in the audit folder): Gap 82
(clouds) and CU-087 (MODTRAN import residue) stay out — GUI-phase and MODTRAN-access-gated
respectively. Tier-3 items (Gap 69/76/79/80, Gap 62) fold into GUI phases; deferred
registry items keep their gates.
