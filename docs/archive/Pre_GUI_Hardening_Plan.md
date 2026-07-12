# Pre-GUI Hardening Plan

> **HISTORICAL — COMPLETE 2026-07-12 (completed-by: overnight autonomous run).**
> All three phases landed or explicitly deferred-with-tracking. Deferred work
> lives in the registries, not here: Gap 74 full scan/timing subsystem, Gap 78
> acquisition-metric family, Gap 81 `tape7_down_path` ingestion (MODTRAN-access
> gated), CU-085 remaining 2 sub-items, CU-090 (altitude-parameter collapse).
> This plan is retired to `docs/archive/`; the CHANGELOG `[Unreleased]` section
> and `docs/tracking/` registries are the live record.

**Status:** Complete (activated 2026-07-11 `bf70f73`; completed 2026-07-12)
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

## Phase 2 — correctness and demo-safety — ✅ COMPLETE 2026-07-12

6. ~~Gap 73~~ — point-source background pedestal (`2d06ca4`; + DN-factor
   robustness `00ef0b4`).
7. ~~CU-074, CU-083~~ — fill_factor √FF dual-path (`3921e5d`); IPC kernel
   resampled to pixel pitch (`80f1a79`).
8. ~~Gap 74 (min slice) + Gap 75~~ — pushbroom/TDI dwell feasibility guard
   (`bdc5ca3`); orbit-derived ground velocity + ground-speed collapse
   (`6abef43`). Altitude collapse deferred → CU-090; full scan/timing
   subsystem deferred (Gap 74 narrowed).
9. ~~Gap 77~~ — SCNR + in-chain point-source detection range (`133fa41`).
   Gap 78 (Pd/DRI/NEΔL/NEΔρ/D\*-family) deferred to GUI-phase surfacing
   (needs study-specific inputs).
10. ~~CU-076, CU-081, CU-085~~ — enum validation; dark-current trap
    (default alignment + warning); validation sweep 6/8 (`513c9c5`).
    CU-085 remaining 2 (SpectralDataStore extrapolation warning,
    digital-TDI test coverage) narrowed.
11. ~~CU-088~~ — LWIR aerosol clamp at the MWIR-LWIR boundary (`eb22d5c`).
    Gap 81 — MODTRAN downwelling **un-silenced with a warning** (`17943ba`);
    full `tape7_down_path` ingestion deferred on MODTRAN access (narrowed).

## Phase 3 — honest documentation before GUI speccing — ✅ COMPLETE 2026-07-12

12. ~~CU-079~~ — aspirational "Authoritative" docs re-bannered DESIGN-TARGET;
    GUI dot-paths directed to `Sensor.parameter_defs()` (`c5a77e6`, plus
    the Gap 71/74 banners).
13. ~~CU-075~~ — scenarios/README status table corrected to 37/37 (`268594b`).
14. ~~Scenario reruns~~ — representative scenarios (6.3 noise, 2.3 IPC) ran
    clean under all Phase-2 changes; full suite green after repinning the
    Cell 28 LWIR Option-C anchor for CU-088 (`da0fb4b`).
15. ~~Script-window dependency spike~~ — feasible, low risk; core namespace
    pattern proven headlessly; qtconsole+in-process-kernel recommended
    (`docs/reports/script_window_spike_2026-07/`, `e827715`).

## Explicitly out of this plan

CU-086 re-audit is complete (2026-07-11, correction doc in the audit folder): Gap 82
(clouds) and CU-087 (MODTRAN import residue) stay out — GUI-phase and MODTRAN-access-gated
respectively. Tier-3 items (Gap 69/76/79/80, Gap 62) fold into GUI phases; deferred
registry items keep their gates.
