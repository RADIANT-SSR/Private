# Backlog Closeout Plan

**Status:** Active — opened 2026-08-01. Supersedes `docs/archive/Backlog_Reduction_Plan.md`
(archived same day; its 2026-07-28 charter was consumed by that week's closures and the
2026-07-31 two-tier tracking ratification).

## Charter

Work the **17 entries open on 2026-08-01** — five family heads (CU-224, CU-263, CU-289,
CU-293, CU-239), nine standalone (CU-306, 301, 267, 257, 250, 209, 181, 164, 110), three
parked (CU-011, 087, 138) — to closure or an explicit refreshed gate. The owner rulings of
2026-08-01 are recorded **on the entries themselves** (Rule 25: this plan references, never
re-enumerates); every package below whose entry carries a ruling executes it as written.

## Ground rules

Everything here runs under the ratified two-tier system: Rule 21 intake for new findings
(CU only past the four-test bar; otherwise a `Findings_Log.md` line), Rule 22 `CU-Closes`
trailer closures, one short-lived branch per package, full gate battery before every merge,
the `RADIANT_Testing_Validation.md` §5.3 protocol wherever a golden moves, a
**Results-affecting** CHANGELOG entry wherever a number moves, and stop-and-flag (never
guess) on anything that crosses an unruled decision. The meta-work moratorium stands.

## Work packages, in run order

**P0 — Batch-2 deck matrix (unblocks P5; owner in the loop).**
"Batch 2" was never rendered into deck rows — all 88 rows of
`docs/plans/modtran_run_matrix.csv` are run and ingested (the 2026-07-26 K/L delivery was
Geometry-Flexibility batch 1), and batch 2 exists only as prose in the archived plan's
close-out and the [[CU-224]] deferral records (status note there, resolved 2026-08-01).
First act of the run: author and render the batch-2 deck set — the SST full-column
ladder, the twilight/refraction on/off calibration pair, the sec-space zenith axis
(§4.2b GF-10), the upwelling/emission-height anchors for `L_path_up`, and
opportunistically [[CU-181]]'s elevated-rung downwelling — append the rows to the matrix
(the source of truth for what the owner runs), and hand the deck files over. P1–P4
proceed while MODTRAN runs.

**P1 — Independent results-affecting fixes** (each its own branch; rulings on the entries):
[[CU-209]] folded-MTF replication at `2·f_Nyquist`; [[CU-267]] gas-region smoothstep blend
(hw = 0.02 µm); [[CU-306]] log-tau resampling. Small, measured, and pre-approved — the
run's warm-up.

**P2 — Detection-range family [[CU-263]]** (incl. folded ex-236): shot-noise-consistent
solver in all three modules + the down arm routed path-aware, one §5.3 refresh including
scenario 4.1's matrix, reference-range-invariance test as the acceptance criterion.

**P3 — Target-spec door family [[CU-293]]** (incl. folded ex-294): evaluate refuses the
S11/S12 pair, inlined intensity-door guards move to the resolve-time seam,
`scenarios/`+`examples/` sweep first, CHANGELOG under Changed.

**P4 — Atmosphere family [[CU-224]], unblocked half** (checklist rulings on the entry):
species-split adoption gated on the five-rung verification; near-horizon hand-over for the
down-looking and solar columns; level-topology whole-path evaluator with the 10.2
walkthrough refresh; hybrid-ratification bookkeeping (docs + framing only — ratified).

**P5 — Atmosphere family [[CU-224]], gated half** (needs P0's runs ingested): the
`L_path_up` thermal-emission term anchored on the upwelling set; deck geometry from
`ColumnSegmentSpec.zeta_low_rad` (ex-223); the explicit exo-branch guard (ex-308);
[[CU-181]]'s altitude-dependent downwelling becomes cheap here if the deck set covers the
elevated rungs — fold it in opportunistically, else its scenario trigger stands.

**P6 — GUI batch**: [[CU-289]] transaction-test fidelity (ruled), [[CU-239]] family picker
(layer 1 + boost-family reachability), [[CU-301]] geometry-screen site-elevation field
(ruled), [[CU-250]] schematic glyph ray (ruled; screenshot expectations reset), [[CU-110]]
thread-safe warning capture.

**P7 — Scenario runner [[CU-164]]**: guard 4.3 per the ruling (lazy CSV load in the
factory), retire `_StopModuleExec`, close the entry.

**P8 — [[CU-257]]**: close as documentation per the ruling — `sub_pixel` is the correct
declaration for seeing-limited SST; no guard change.

**Parked, untouched by this plan**: [[CU-011]] / [[CU-087]] (trigger: a runnable MODTRAN
binary), [[CU-138]] (trigger: qtconsole installable). Their triggers were re-verified at
the 2026-07-31 triage and carry forward.

## Acceptance

- Every non-parked entry is Resolved (trailer or ruling closure) **or** carries a refreshed
  explicit gate with a re-audit date.
- No golden moved outside §5.3 + a Results-affecting CHANGELOG entry.
- The quarterly `Findings_Log.md` sweep is **not** part of this plan (first due ~2026-10).
- This plan moves to `docs/archive/` in the PR that closes its last actionable package
  (Rule 24).
