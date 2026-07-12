# Capability Audit — Recommendation

**Status:** Complete (2026-07-11)
**Question chartered:** is core functionality missing that should be squared away before
investing in the GUI?

## Answer

Yes — but it is a bounded, well-defined set, and it is *surface* work, not physics
rework. The engine is strong and fast (0.22 s full-chain runs). The pre-GUI work divides
into three tiers; Tier 1 is the do-not-start-the-GUI-without-it set.

## Tier 1 — GUI-blocking (the GUI's contract cannot be implemented without these)

1. **Persistence** (Gap 67): `Sensor.save/load` + full `ChainResult` serialize/reload.
   Every File-menu operation and cross-session comparison depends on it.
2. **Schema introspection API** (Gap 70): public enumeration of ParameterDefs (bounds,
   units, enums, defaults, descriptions). The parameter panel generates from this.
3. **Non-scalar input reachability** (Gap 68): a config path for element lists,
   Zernike/OPD, pupil masks, spectral curves — or `Sensor.evaluate(extra_stage_outputs=)`
   passthrough as the interim seam. Also un-advertise the schema modes that always raise.
4. **Metric metadata** (Gap 71): units on every metric (owner hard rule) via a uniform
   MetricResult-style contract; fix registry drift (CU-078).
5. **Progress/cancel hooks** (Gap 72) + **parallel-sweep crash fix** (CU-072).
6. **Error boundary** (CU-073): unknown-parameter KeyError → RadiantError.

## Tier 2 — fix-before-GUI (cheap now, expensive to retrofit; or demo-embarrassing)

- Point-source background/path photon noise (Gap 73) — wrong answers on a headline use case.
- fill_factor dual-path divergence (CU-074); IPC kernel spacing (CU-083).
- SCNR + in-chain detection-range solver (Gap 77); acquisition-metric surfacing (Gap 78).
- Scan/timing feasibility minimum (Gap 74): at least the t_int ≤ line_period × n_tdi
  constraint and orbit-derived ground velocity (Gap 75) so GUI fields cross-validate.
- Dark-current temperature default trap (CU-081); enum validation (CU-076);
  validation-hardening sweep (CU-085).
- Doc reconciliation (CU-079) **before** GUI speccing — otherwise the GUI is designed
  against phantom surfaces; refresh `scenarios/README.md` (CU-075).
- Script-window dependency spike (highest-integration-risk GUI element; standing owner
  requirement in every gui_workflow.md).

## Tier 3 — fine after GUI / fold into GUI phases

Compare primitive (Gap 79) and multi-band orchestration (Gap 80) can land as GUI-phase
features; solar spectrum upgrade (Gap 76); library dropdown params (Gap 69) is small and can
ride either tier; report/PPTX export (Gap 62) should be designed with the GUI's reporting
view; all MODTRAN items wait for the concurrent rework then re-audit (CU-086); deferred
registry items keep their gates (Gap 21/38/39/58/60/63, CU-011/065/067/070).

## What I recommend you do next

1. Ratify the three Proposed-Declined items in `Findings.md` (incremental re-eval engine,
   pre-GUI QE(T) model, uplooking geometry).
2. Activate `docs/plans/Pre_GUI_Hardening_Plan.md` (Draft → Active) and burn Tier 1 down —
   rough order: Gap 70 → 67 → 71 → 68 → 72/CU-072/073.
3. Hand the F-19 PROVISIONAL list to the MODTRAN workstream now (especially the zeroed
   downwelling term) so it lands inside that rework instead of after it.
4. Re-run the four scenarios whose gaps were fixed after execution (F-24) to close the loop.
5. Then start the GUI with the geometry prototype's scene library, the verified-fast
   full-re-run loop, and a script-window spike as the first two GUI work items.
