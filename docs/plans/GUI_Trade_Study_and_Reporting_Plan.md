# GUI Trade-Study & Reporting Plan — the Tier-2 Increment

**Status:** **Ratified (owner, 2026-07-16) — EXECUTION ON HOLD** (owner directive: concurrent
agent work is in flight; no phase dispatches until the owner lifts the hold). When lifted:
FW-A/FW-B may start immediately; GUI phases additionally wait for the Exposure Increment's
GX-2 closeout (so the acceptance-walkthrough punch list folds into GT-0 rather than colliding).
**Date:** 2026-07-16
**Scope:** the work the owner deferred out of the Exposure Increment ("I don't think we need
sweeps and MC — I really want to expose existing capabilities", 2026-07-16) now returns as its
own tier: the **trade-study surfaces** (sweep / Monte Carlo / batch), **comparison**,
**reporting/export**, plus the small analysis UIs whose backends already exist (measurement
overlay, inverse solve) and the Gap 85 remainder. Detection/acquisition panels (GUI-6 → Gap 78)
stay **out** (§2.3).
**Depends on / references (Rules 20/25 — reference, never re-enumerate):**
- `docs/plans/GUI_Capability_Expansion_Plan.md` (Exposure Increment — Active; its ground rules
  and iteration protocol carry forward verbatim, themselves inherited from the archived v1 plan §4/§5).
- `docs/reports/GUI_audit_071426/GUI_Capability_Audit.md` — the audit rows this tier drains
  (§11.2 sweeps, §11.4 comparison, §11.5 export, P-4 measurement overlay).
- `docs/tracking/gaps.md` — GUI-2/3/4/8/9/16/17, Gaps 72/78/79/85/88.
- `docs/adr/0009-gui-config-object-editing-and-import.md` (Accepted) — the D5 import-dialog
  contract; the shipped `ImportPreviewDialog` is the reusable piece GT-5 builds on.
- **CLAUDE.md Rule 30** (cross-platform, 2026-07-16) binds every phase: `pathlib` paths,
  `encoding="utf-8"` on all text I/O, no POSIX-only APIs — export phases especially.
**Naming note:** filename carries no version word (Rule 23 §5); "Tier 2" is prose only.

---

## 1. What this tier delivers

1. **Sweep surface** — Run → Run Sweep… as a first-class GUI flow: 1-D and 2-D parameter
   sweeps with live progress/cancel, plotted into the center canvas.
2. **Tolerance annotation + console-first Monte Carlo/Batch** (owner-shaped 2026-07-16):
   tolerances edited *on the parameter* (a small optional section in the existing
   ParameterEditorDialog, ± badges in the tree — never a standalone 130-row editor; the
   `_radiant.tolerances` YAML block already persists them, Gap 67); MC and Batch run in the
   **scripting window**, with the Run-menu items becoming **script scaffolds** that open the
   console prefilled from current state (toleranced params + a ready-to-run
   `sensor.monte_carlo(...)` / `BatchRunner` snippet) — the GUI teaches the API.
3. **Comparison mode** — N configs side-by-side: aligned metric table, deltas vs a baseline,
   best-per-metric; the atmosphere A/B toggle (GUI-10) falls out as a special case.
4. **Reporting/export** — resolved-scope YAML, metrics/sweep CSV, per-chart PNG/SVG, and an
   XLSX workbook (owner decision D2); PDF/PPT stay out.
5. **Measurement overlay** — imported lab points over model curves with a residual sub-plot
   (starting with MTF via the shipped `compare_mtf`).
6. **Inverse-solve dialog** — a GUI face on `Sensor.solve_for`.
7. **Gap 85 remainder** — regime tags on the non-source stages where relevance genuinely
   varies + relevance badging in the All-Parameters tree.
8. **Punch-list slot** — whatever the GX-2 acceptance walkthrough surfaces (reserved, §5).

---

## 2. API-Readiness Map (verified 2026-07-16 during the Exposure Increment)

### 2.1 Backend that already exists — GUI-only phases

| Capability | Verified public surface |
|---|---|
| 1-D / 2-D sweep | `Sensor.sweep(param, values, metric=…) → SweepResult`, `Sensor.sweep_2d(...) → Sweep2DResult` |
| Monte Carlo | `Sensor.monte_carlo(n_trials, seed) → MonteCarloResult` (requires ≥1 `set_tolerance`) |
| Batch matrix | `radiant.api.batch.BatchRunner.run() → BatchResult` (`.pivot`, `.n_failed` — per-cell failures surfaced, never dropped) |
| Progress + cancel | Gap 72 hooks on `sweep` / `sweep_2d` / `monte_carlo` / `sensitivity` / `BatchRunner.run`: `progress(done,total)` + `cancel()` polled per unit, `OperationCancelledError` on abort |
| Tolerances | `Sensor.set_tolerance(dotpath, distribution, **kwargs)` (gaussian / uniform / truncated_gaussian / log_normal) |
| Inverse solve | `Sensor.solve_for(param, target, bounds=…) → SolveResult` (+ `SolveBracketError` with endpoint values) |
| MTF measured-vs-predicted | `radiant.api.compare.compare_mtf → MtfComparisonResult` (overlap-only residuals, RMS/max stats) |
| Import preview UX | shipped `ImportPreviewDialog` (ADR-0009 D5) — GT-5 adds a measured-curve kind |
| Config snapshot | `Sensor.save` (inputs scope; carries `optical_elements`) |

### 2.2 Backend gaps this tier must build first — FW phases

| # | Gap | What's missing | Blocks |
|---|-----|----------------|--------|
| FW-A | **Gap 79** (OPEN) | No general multi-config compare primitive — `compare_mtf` covers MTF only. Needed: `compare_configs(sensors_or_results, labels=…, baseline=…) → ComparisonResult` (aligned metric matrix with units from `metric_records()`, per-metric deltas vs the baseline, best-per-metric marks; accepts pre-evaluated results so the GUI never re-runs needlessly). Category B, results-neutral. | GT-3 Comparison |
| FW-B | **Gap 88** (OPEN) + no results-export surface | `Sensor.to_yaml(scope="inputs"\|"resolved") → str` (in-memory — kills the YAML-tab temp-file workaround too) and `ChainResult.to_records() / to_csv(path)`; `SweepResult`/`Sweep2DResult`/`MonteCarloResult` gain matching `to_csv`. Category A–B, results-neutral. Rule 30: `encoding="utf-8"`, explicit `newline=` where bytes matter. | GT-4 Export |

### 2.3 Explicitly out of this tier

**GUI-6 detection/threshold panels → Gap 78** (Pd/ROC, Johnson DRI, NEDL/MRC, D*/NEI): the
registry's own deferral rationale stands — each metric needs study-specific inputs the chain
does not carry (P_fa, target dimensions + criterion, electrical bandwidth), so surfacing them
means *designing those study inputs*, a physics+UX effort that deserves its own charter. Also
out: image simulator / library browser (arch §9), PDF/PPT rendering (D2), curve digitizer
(GUI-11), temporal/profile sweep mode (GUI-16 — revisit when a diurnal-profile source exists,
Gap 84 family).

---

## 3. Crosswalk (Rule 25 — the registries stay authoritative)

| Tier-2 item | Audit | Backlog | Backend | Phase |
|---|---|---|---|---|
| Sweep surface | §11.2 | GUI-17, GUI-9 | ready (Gap 72) | GT-1 |
| MC + Batch | §11.2 | GUI-17 | ready | GT-2 |
| Comparison | §11.4 | GUI-3, GUI-10 | **FW-A** | GT-3 |
| Export/report | §11.5 | GUI-2 | **FW-B** | GT-4 |
| Measurement overlay | P-4 | GUI-4 | ready (`compare_mtf`) | GT-5 |
| Inverse solve | — | GUI-8 | ready (`solve_for`) | GT-6 |
| Relevance remainder | S-5 residue | Gap 85 | pattern shipped (source stage) | GT-7 |

---

## 4. Ground rules (inherited + tier-specific)

All Exposure-Increment ground rules apply unchanged (one action ↔ one API call; schema-driven
controls; units on every displayed value; errors shown never swallowed; results-neutral GUI —
a golden diff in any phase is a defect; per-phase CHANGELOG + lock-step docs). Tier-specific:

1. **Long-running work never blocks the UI.** Sweeps/MC/Batch run on the worker thread with
   the Gap 72 hooks; the progress dialog shows done/total + ETA, and **abort keeps partial
   results** where the API returns them (a cancelled run reports what completed — never a
   silent discard). `OperationCancelledError` is an expected outcome, not an error dialog.
2. **Arch-doc §9 subsystems get their content spec in the same PR** that builds them (Rule
   20): GT-1/GT-2 (sweep surface) and GT-3 (comparison mode) add their §-level layout/content
   sections to `RADIANT_GUI_Architecture.md`.
3. **Rule 30 compliance** on every file written (exports especially): `pathlib`,
   `encoding="utf-8"`, explicit `newline=` for byte-stable artifacts.
4. **No new hard dependency without owner sign-off** — XLSX export hinges on decision D2.

---

## 5. Phase Sequence — PROPOSAL (pending ratification)

Framework-first; one phase = one agent task; effort S/M/L as before. FW phases are api-only
and may run immediately on ratification; GT phases wait for the Exposure Increment's GX-2
closeout (punch-list first).

**FW-A — Multi-config compare primitive (Gap 79).** Category B · S–M.
`radiant.api.compare.compare_configs` per §2.2. Closes Gap 79 (Rule 22 on merge).
**Checkpoint (script):** compare two example configs; read the aligned unit-carrying table,
deltas vs baseline, best-per-metric marks.

**FW-B — Serialize + results export (Gap 88).** Category A–B · S–M.
`Sensor.to_yaml(scope)`, `ChainResult.to_records()/to_csv`, `to_csv` on the trade-study result
types. Also retires the GUI YAML-tab temp-file workaround (Gap 88's original symptom).
**Checkpoint (script):** print resolved YAML (defaults + derived marked); write metrics and
sweep CSVs; inputs-scope output byte-identical to `Sensor.save`.

**GT-0 — Walkthrough punch list (reserved).** Category A · size unknown.
The GX-2 acceptance findings, fixed before new surfaces land on top of them.

**GT-1 — Sweep surface.** Category D · L (split: 1-D dialog + live curve first; 2-D grid +
heatmap second). Gate: GX-2 closed.
Run → Run Sweep…: schema-driven parameter picker (unit-aware range builder — linspace / log /
explicit list, entered in the display unit), metric selector from `metric_records()`, worker
execution with progress + cancel, live curve (1-D) / heatmap (2-D) into the center canvas,
result held for GT-4 export and console reuse; a **"Copy as script"** button emits the
equivalent `sensor.sweep(...)` one-liner so a GUI-configured sweep graduates to the console.
Arch-doc §9 sweep spec in the same PR.
**Checkpoint:** sweep aperture 10 points watching SNR live; abort mid-run and keep the partial
curve; run a visibility×PWV heatmap; Copy as script reproduces the run in the console.

**GT-2 — Tolerance annotation + MC/Batch console scaffolds.** Category D · M. Gate: GX-2.
(Reshaped per owner decision D3, 2026-07-16 — no MC/Batch dialogs.)
(a) ParameterEditorDialog gains an optional **Tolerance** section (distribution combo +
params, default none) committing via the existing `sensor.set_tolerance`; toleranced rows get
a ± badge in the All-Parameters tree; the `_radiant.tolerances` YAML block already round-trips
them (Gap 67 — this completes the missing GUI face of an existing surface).
(b) Run → Monte Carlo… / Batch Run… become **script scaffolds**: open the scripting window
with a snippet prefilled from current state (the toleranced params listed,
`mc = sensor.monte_carlo(n_trials=500, seed=42)` + a percentile printout; a `BatchRunner`
skeleton for Batch) — edit and run in the console.
**Checkpoint:** tolerance QE ±0.02 gaussian from its editor dialog (badge appears; Save →
reload keeps it); Run → Monte Carlo… drops the prefilled snippet into the console; running it
prints percentiles.

**GT-3 — Comparison mode.** Category D · M. Gate: FW-A + GX-2.
Compare view over `compare_configs`: current sensor + N loaded configs, aligned metric table
(units), deltas vs a chosen baseline, best-per-metric highlight; "duplicate current + change
one thing" convenience for the A/B atmosphere swap (GUI-10). Arch-doc §9 comparison spec in
the same PR.
**Checkpoint:** compare the current config against a saved variant; switch baseline; run the
6.2 parametric-vs-tape7 A/B.

**GT-4 — Export & report.** Category D · M. Gate: FW-B.
File menu grows: Export Resolved YAML (scope picker), Export Metrics CSV, Export Sweep/MC CSV
(when one exists), per-chart PNG/SVG save on every canvas; **XLSX workbook** (config sheet +
metrics sheet + sweep sheets) if D2 approves the dependency. PDF/PPT stay out.
**Checkpoint:** export resolved YAML + metrics CSV + the sweep CSV + a PNG; reimport the YAML
and confirm identical metrics.

**GT-5 — Measurement overlay.** Category D · M. Gate: GX-2.
A "measured data" import (new `ImportPreviewDialog` kind: two-column measured curve) overlaid
on the Performance MTF plot via `compare_mtf` — model curve + lab points + residual sub-plot
with RMS/max stats (unit-switchable frequency axis noted as a follow-on if not already carried
by the accessor).
**Checkpoint:** import a measured MTF CSV, see the overlay + residuals on Performance.

**GT-6 — Inverse-solve dialog.** Category D · S–M. Gate: GX-2.
Tools → Solve for…: pick the free parameter (schema-driven), the target metric + value, and
the bracket (display units); run on the worker; report solution + achieved + n_evaluations;
`SolveBracketError` shows its endpoint values actionably. On success, offer "apply solution"
(one `sensor.set`).
**Checkpoint:** solve aperture for SNR = 500 on the example; apply; evaluate confirms.

**GT-7 — Relevance remainder (Gap 85 close-out).** Category B+D · M. Gate: none (independent).
Author `regime:<scene_type>` tags on the non-source stages where relevance genuinely varies
(audit the schemas; most instrument parameters are regime-independent and stay untagged), and
badge the All-Parameters tree (dimmed rows + tooltip when a declared type excludes them — the
Source-form pattern generalized). Closes Gap 85 or records precisely what remains.
**Checkpoint:** declare `point_source`; the tree and stage forms show consistent dimming.

**GT-8 — Closeout.** Category A–D · S–M. Registry hygiene (GUI-2/3/4/8/9/17 rows + Gaps
72/79/85/88 dispositions, Rule 22 SHAs), CHANGELOG consolidation, arch-doc reconciliation,
plan archived (Rule 24).

### Sequencing summary

```
(on ratification)                (after Exposure GX-2 closeout)
FW-A ───────────┐            ┌─ GT-0 punch list ── GT-1 Sweep ── GT-2 MC/Batch
FW-B ───────────┼────────────┼─ GT-3 Compare (FW-A) ── GT-4 Export (FW-B)
                └────────────┼─ GT-5 Overlay · GT-6 Solve · GT-7 Relevance (any order)
                             └─ GT-8 Closeout (last)
```

---

## 6. Decisions for owner (ratify to lock)

1. **Ratify the tier scope** — **RATIFIED (owner, 2026-07-16)**, including the GUI-6/Gap 78
   exclusion (§2.3).
2. **D2 — XLSX dependency:** **RATIFIED as proposed (owner, 2026-07-16)** — `openpyxl` joins
   the `gui` extra for the GT-4 workbook (CSV remains the guaranteed floor).
3. **MC tolerance editor scope (GT-2):** **RESOLVED (owner, 2026-07-16)** — no MC/Batch
   dialogs. Tolerances are per-parameter annotations in the ParameterEditorDialog (+ tree
   badges); MC/Batch run console-first via Run-menu script scaffolds; the sweep dialog stays
   (sweeps are frequent enough to earn dedicated UI) and gains "Copy as script".
4. **Ordering** — **RATIFIED (owner, 2026-07-16)** with an execution hold on top: nothing
   dispatches (FW included) until the owner lifts the hold; then FW-A/FW-B first, GT phases
   after GX-2 closeout, in the §5 order.
5. **GT-7 depth:** **RATIFIED as proposed (owner, 2026-07-16)** — close Gap 85 fully in this
   tier (non-source tags where relevance genuinely varies + tree badging).

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| Sweep UI invites huge grids (memory via `keep_results`) | GT-1 caps live-retained results with a visible note (no silent cap — Rule 17) and offers keep_results off for large sweeps |
| A cancelled run reads as a failure | Ground rule 1: cancellation is a first-class outcome (partial results + "cancelled at k/N" status), never an error dialog |
| FW-A grows into a framework (N-run orchestration, shared-scene consistency — the Gap 80 family) | FW-A is a *table-builder over results the caller supplies*; multi-band orchestration stays Gap 80, untouched |
| XLSX dependency creep | Gated on D2; CSV is the guaranteed floor |
| Punch list arrives mid-tier | GT-0 is sequenced first among GUI phases; later punch items become ordinary phase-scoped fixes |
| Windows regressions in export paths | Rule 30 checklist is acceptance criteria for FW-B/GT-4 (explicit encoding/newline; pathlib) |
