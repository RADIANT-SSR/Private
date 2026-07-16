# GUI Capability Expansion Plan — "GUI v2" Exposure Increment

**Status:** Active — owner-ratified 2026-07-16; **FW-1 + GS-2 + GS-3 + GS-1 + GS-4 + GX-1 all
SHIPPED 2026-07-16** (sequential run, owner-directed; TEG Phase G went green the same day).
Remaining: **GX-2 closeout** — the owner acceptance walkthrough + registry hygiene + archiving
this plan (needs an owner-driven session; see the GX-2 checkpoint).
**Date:** 2026-07-16
**Scope (owner-directed 2026-07-16, revised same day):** **exposure-only** — surface capabilities
the engine already has behind existing `ParameterDef`s, loaders, and API calls. The owner's
ruling: *"I don't think we need sweeps and MC — I really want to expose existing capabilities in
the GUI."* Anything requiring new backend construction beyond the one facade the import contract
forces (ADR-0009) is out: the **sweep/MC/Batch surface (GUI-17/GUI-9), Comparison mode (GUI-3 →
Gap 79), and the report/export data layer (GUI-2 → Gap 88) all defer to a later tier**, even
though the audit ranked them P0 — the audit ranks scenario impact; this plan follows the owner's
build priority. Later tiers get their own plans.
**Depends on / references (Rule 20, Rule 25 — reference, never re-enumerate):**
- `docs/reports/GUI_audit_071426/GUI_Capability_Audit.md` — the screen-by-screen findings this plan sequences.
- `docs/tracking/gaps.md` — the requirement registry: **GUI-1…GUI-17** (post-v1 backlog) and Gaps 78/79/85/88.
- `docs/architecture/RADIANT_GUI_Architecture.md` — the authoritative content surface (§4.4.1 per-stage content, §9 deferred subsystems).
- `docs/archive/GUI_Development_Plan.md` — the completed v1 plan; its ground rules (§4) and iteration protocol (§5) carry forward verbatim.
- `docs/adr/0009-gui-config-object-editing-and-import.md` (**Proposed**) — config-object editor + import surface; the structural spine of the element editor and import dialogs. §5 phases FW-1 and GS-4 execute it.
- `docs/plans/Target_Extent_Geometry_Plan.md` (**Active**, concurrent) — **hard gate:** that plan's own header rules "GUI Phase II must not start until Phase G of this plan is green." Every GUI-surface phase below (GS-*/GX-*) carries that gate; the FW-* phases are api-only and may proceed before Phase G.
**Naming note:** filename omits a version token per Rule 23 §5; the "v2" label is colloquial, used in prose only.

---

## 1. What this increment delivers (exposure-only)

Six items — every one an engine capability that exists today and is invisible in the GUI. This
plan brings them to the Geometry gold standard; nothing else.

1. **Source reflective / solar path** + day/night (audit S-1, S-3) — `source.target.reflectance`/
   `albedo`, `geometry.solar_illumination`, solar-geometry params.
2. **Source scene-type / mission-type selector** (S-5) — `source.scene_type` + `regime_override`
   (selector only; TEG T2 owns the cross-check, §2.3).
3. **Atmosphere input form**: `atmosphere.model` selector + per-model params + tape7/tabulated
   file-path params (A-1…A-4).
4. **Optics element / coating editor**: the per-element %R/%T/T/ε train `load_element_list`
   already consumes (O-1) — the one item needing the small ADR-0009 facade.
5. **Detector full-schema expansion**: spectral QE, dark model, 1/f, G-R, FPN, persistence, IPC —
   all existing `ParameterDef`s (D-1…D-9).
6. **Existing-API menu wire-ups**: Export YAML → `Sensor.save`, Export JSON Result →
   `ChainResult.save`, Tools → Schema Browser (Gap 70 introspection), Explain Parameter →
   `Sensor.explain`, Edit → Reset to Defaults → `Sensor.reset`. Zero new backend.

**Explicitly deferred to a later tier** (audit-P0 rank notwithstanding — owner build priority):
the sweep/MC/Batch surface (GUI-17/GUI-9; `sensor.sweep()` et al. exist, the GUI surface is new
construction), Comparison mode (GUI-3 — needs the Gap 79 primitive, new backend), the
report/export data layer beyond the existing save calls (GUI-2 — needs Gap 88), plus everything
the v1 plan already deferred: bespoke analysis panels (GUI-12), detection traffic-light panels
(GUI-6 → Gap 78), image simulator / library browser / report generator (arch §9), geometry
orbit/coverage dashboards (GUI-14).

---

## 2. API-Readiness Map (verified 2026-07-16 against `src/radiant/api/`)

The v1 rule holds: **one GUI action ↔ one API call; a GUI phase never starts until its backend
hook exists.** This map resolves every "verify" flag from the audit. Verdict column: **GUI-only**
(backend ready — pure GUI work) vs **FW-first** (a framework/API phase must land first).

### 2.1 Backend that already exists (verified)

| Capability | Public API surface (confirmed) | Verdict |
|---|---|---|
| Set any scalar param, unit-aware | `Sensor.set(dotpath, value, unit=…)`, `set_many` | GUI-only |
| **Inject a config object** (element list, WFE screen, PSF-weighting, source_config) | **`Sensor.set_stage_output(group, key, value)`** — public, e.g. `("optics_config","element_list",elements)` | GUI-only + builder (ADR-0009) |
| Spectral-QE import | `detector.qe_table_path` is a **plain ParameterDef**; `session.py` loads the CSV (Gap 44) | GUI-only (file-picker → `set`) |
| Atmosphere model + import | `atmosphere.model` enum + `atmosphere.tabulated_*_file` / `atmosphere.modtran.tape7_path` are ParameterDefs; `build_atmosphere_model(params)` dispatches | GUI-only (selector + file-picker → `set`) |
| Optics element train | `io/element_config.py::load_element_list()` builds the list → `set_stage_output("optics_config","element_list",…)` | GUI-only + builder (ADR-0009) |
| Single-axis sweep | `Sensor.sweep(param, values, metric=…) → SweepResult` | GUI-only |
| Two-axis sweep | `Sensor.sweep_2d(...) → Sweep2DResult` | GUI-only |
| Monte Carlo | `Sensor.monte_carlo(n_trials) → MonteCarloResult` | GUI-only |
| Batch / matrix | `radiant.api.batch.BatchRunner.run() → BatchResult` (`.pivot`, `.n_failed`) | GUI-only |
| Progress / cancel (for the above) | `radiant.api.\_progress` + `OperationCancelledError` (Gap 72) | GUI-only |
| Inverse solve | `Sensor.solve_for(param, target_metric, target_value) → SolveResult` | GUI-only |
| Sensitivity / tornado | `Sensor.sensitivity(...) → SensitivityResult` | GUI-only |
| WFE / jitter RSS budget | `radiant.api.error_budget.ErrorBudget`, `BudgetContributor` | GUI-only |
| MTF measured-vs-predicted | `radiant.api.compare.compare_mtf → MtfComparisonResult` | GUI-only |
| Calibration fit | `radiant.api.calibration_analysis` | GUI-only |
| YAML config save | `Sensor.save(path)` (inputs scope) | GUI-only |
| Result → dict | `ChainResult.to_provenance_record()`, `ChainResult.save(path)` | GUI-only (thin) |
| All 14 stage plots | `result.plot.*` — psf, psf_pixel_grid, pupil_amplitude, pupil_phase, noise_budget, **noise_pie**, mtf, mtf_budget, spectral_source, **spectral_source_emission**, optical_throughput, coating_spectra, spectral_atmosphere, spectral_inband | GUI-only |

### 2.2 The one framework phase this increment needs

| # | Gap | What's missing | Blocks | FW phase |
|---|-----|----------------|--------|----------|
| FW-1 | Config **facade + persistence parity** (ADR-0009 D3/D4) | `gui` is **forbidden** from importing `radiant.io` (import-linter), so the loaders are unreachable from GUI code; and `Sensor.save`/`from_yaml` do not carry the `optical_elements:` section — authored element trains cannot persist | Optics editor (item 4), import previews (items 3/5) | `radiant.api` config facade (preview-parse + validate-and-inject via the existing io parsers) and `Sensor.save`/`load` round-trip of the `optical_elements:` section. **Resolved by ADR-0009** (Proposed): api-level, not GUI-side — forced by the import contract. Category B. This is not new *capability* — it is plumbing that makes an existing capability reachable and persistent. |

**Backend gaps confirmed OUT of this increment** (recorded so the boundary is explicit):
**Gap 79** (multi-config compare primitive) defers with Comparison mode; **Gap 88** (in-memory /
resolved-scope serialize + results-to-CSV) defers with the report/export layer — item 6 wires the
*existing* `Sensor.save` / `ChainResult.save` only; **Gap 78** (acquisition metrics) defers with
the detection panels (GUI-6). None of these is wired in this increment.

### 2.3 The scene-type selector (item 2) — split with the concurrent TEG plan

The engine axes exist (`source.scene_type`, `source.regime_override`, `source.target_location`,
`source.no_atmosphere_subcase`, `source.lab_test_mode`) — confirmed by ADR-0008 Amendment 1, which
ruled "do **not** add a new `scenario.type`; build on what exists." Ownership split with the
in-flight `Target_Extent_Geometry_Plan`:

- **TEG Phase T2 owns** the declared-vs-derived cross-check (compare declared `scene_type` against
  the OpticsStage final regime; warn on mismatch, surfaced in the Messages panel — "no selector" is
  explicitly in T2's scope note).
- **This plan (GS-1) owns** the *selector UI* (the scene-type/mission-type combo + the
  `regime_override` control) and consumes T2's warning; it must **not** re-implement the cross-check.
- The **relevance gating** ("which params matter for this declared type") needs per-regime metadata
  on the `ParameterDef`s that **does not exist** (Gap 85 / ADR-0008 Decision 4a residue). This
  increment ships the selector without gating; the relevance filtering/badging is a fast-follow
  that lands the schema metadata first.

---

## 3. Crosswalk — Audit findings ↔ GUI-1…GUI-17 backlog ↔ backend status

Rule 25: `gaps.md` GUI-1…GUI-17 is the registry; this plan references it. The six items map onto
the backlog as follows (audit IDs are from `GUI_Capability_Audit.md`).

| Item | Audit IDs | Backlog | Backend gap | Readiness |
|---|---|---|---|---|
| 1 Source reflective/solar + day/night | S-1, S-2, S-3, S-4, S-8 | (new — audit-surfaced) | — | **GUI-only** |
| 2 Scene-type selector | S-5, S-6 | GUI-5 | Gap 85 (relevance meta); cross-check = **TEG T2** (§2.3) | GUI-only selector; gating = fast-follow |
| 3 Atmosphere form + import | A-1…A-4, A-8, A-9 | GUI-7, GUI-10 | Gap 81 (fidelity, not blocking) | **GUI-only** |
| 4 Optics element/coating editor | O-1, O-2, O-3, O-4 | GUI-12 (partial), Gap 90 | FW-1 facade | GUI + facade (ADR-0009) |
| 5 Detector schema expansion | D-1…D-9 | GUI-12, GUI-15 | — | **GUI-only** |
| 6 Existing-API menu wire-ups | §11.7 | (v1 placeholders) | — | **GUI-only** |

Backlog items **not** in this increment (deferred to a later tier, listed so the boundary is
explicit): **GUI-17/GUI-9/GUI-16 (sweep / MC / Batch surface — owner ruling 2026-07-16)**,
**GUI-3 (Comparison → Gap 79)**, **GUI-2 (report/export layer → Gap 88)**, **GUI-1 (the general
unit-mapping spreadsheet-import dialog — this increment ships only the per-stage D5 import dialogs
its forms need)**, GUI-4 (measurement overlay — `compare_mtf` exists, panel later), GUI-6
(detection traffic-light → Gap 78), GUI-8 (inverse-solve UI — `solve_for` exists), GUI-11 (curve
digitizer), GUI-12 (the full bespoke-panel set), GUI-13 (image sim), GUI-14 (orbit/coverage
dashboards → coordinate with `Target_Extent_Geometry_Plan`).

---

## 4. Gates and coordination (all resolved or tracked)

1. **ADR-0009** — drafted (`docs/adr/0009-...md`, **Proposed**). Rulings: file-path-first imports;
   authored configs edited as declarative documents (the io parser's own YAML schema); a
   `radiant.api` config facade as the only GUI↔loader bridge (forced by the import contract);
   authoring implies `Sensor.save`/`load` persistence parity; one shared import-dialog contract.
   **Owner ratifies with this plan** — FW-1 and GS-4 execute it.
2. **TEG Phase G gate.** The `Target_Extent_Geometry_Plan` rules GUI Phase II starts only after its
   Phase G (GUI backend-path migration + full-suite regression) is green. **Every GS-*/GX-* phase
   below carries `Gate: TEG Phase G green` implicitly**; the api-only FW-1 does not.
3. **TEG T2 split** (§2.3): T2 owns the declared-vs-derived cross-check; GS-1 owns the selector.
4. **Arch-doc lock-step (Rule 20).** Each GS/GX phase updates `RADIANT_GUI_Architecture.md` §4.4.1
   (per-stage content rows) **in the same PR**.
5. **Geometry screen**: not reworked in this increment (GUI-14 orbit/coverage is a later tier) —
   the TEG coordination is the Phase-G gate plus GS-1's parameter namespace (`geometry.target.*`
   after TEG Phase A; GS-1 must read the migrated dot-paths, not the pre-TEG ones).

---

## 5. Phase Sequence — PROPOSAL (pending owner ratification)

Framework-first, mirroring the v1 plan; one phase = one agent task = one conversation. Effort key:
S ≈ one short session, M ≈ one full session, L ≈ may need a split. Every phase inherits the ground
rules (§6), ends with a v1-protocol **Checkpoint** (launch command / click script / expected
observations / known-incomplete), and adds its Rule-29 CHANGELOG entry. Every FW phase is
**results-neutral** (goldens byte-identical — a diff is a defect).

### The one framework phase (api-only; may run before/parallel to TEG Phase G)

**FW-1 — Config facade + element-train persistence (ADR-0009 D3/D4).** Category B · Effort M ·
Gate: ADR-0009 accepted. **SHIPPED 2026-07-16** (same-day as ratification).
Delivered: `radiant.api.config_io` (`preview_optical_elements` / `normalize_element_document` /
`ElementPreview` — parse-for-display via the real io parser, no mutation);
`Sensor.set_optical_elements` / `optical_elements()` (validate-and-attach, parsed onto the
evaluation grid per run → `optics_config.element_list`); `Sensor.save`/`load`/`from_yaml`/
`from_dict` round-trip the `optical_elements:` section; bare `load_config` raises actionably on
section-bearing configs (Rule 17; opt-in `sections_out=`); `parse_element_entries` document seam
in `io/element_config.py`. 19 new tests; api+io 370 pass; goldens byte-identical; mypy strict +
import-linter + ruff clean. Docs: Scripting_API §2.2/§2.6, Config_Format §1.8, CHANGELOG. New
CU-153 (CLI bare-loader path). **Checkpoint (script):** `entries=[{...M1...}]` →
`preview_optical_elements(entries)` shows Kirchhoff-derived ε=1−R; `s.set_optical_elements(entries);
s.evaluate()` runs full-prescription; `s.save(p); Sensor.load(p)` → identical SNR to 1e-12.

### Per-stage GUI phases (Gate: TEG Phase G green, + listed gates)

**GS-1 — Source instrument v2: reflective path + scene-type selector.** Category D · Effort M–L ·
Gate: TEG G. **SHIPPED 2026-07-16** (`4f5df42`).
Adds to the Source Inputs card: reflectance/albedo (scalar; spectral via path param, D1 import
dialog), day/night `geometry.solar_illumination` toggle with the solar-geometry echo
(zenith/azimuth read-outs), fill-fraction, hot-target opt-out, and the **scene-type selector**
(`source.scene_type` + `regime_override`, §2.3 — consumes TEG T2's warning, does not re-implement
it). The stage note states which radiometric terms are active for the current configuration
(emissive / reflected-solar / mixed). Uses post-TEG dot-paths. **Checkpoint:** configure a VIS
reflective scenario end-to-end in the GUI (set ρ, day, solar geometry; evaluate; see the reflected
term in the source spectra); declare `sub_pixel` and see the T2 mismatch warning fire on an
extended-scene config.

**GS-2 — Atmosphere instrument: model selector + inputs + import.** Category D · Effort M ·
Gate: TEG G. **SHIPPED 2026-07-16** (file-picker fallback for imports; the D5 preview dialog
remains a follow-on).
The Atmosphere stage finally gets an Inputs card: the `atmosphere.model` selector driving a
per-model form (simple: profile / aerosol / visibility / PWV; modtran: tape7 path + profile /
aerosol / H2O / O3 scaling; tabulated: the three file params; interpolated: data dir + axes +
method; exo: note), turbulence r₀, and the D1/D5 import flow for tape7/tabulated files. Keep the
existing τ/L_path and before/after-aperture plots; add the pre-atmosphere emission
(`spectral_source_emission`) beside the at-aperture radiance so propagation vs path-emission reads
separately (audit A-5). **Checkpoint:** switch `simple → modtran(tape7)` and watch τ(λ) change;
import a tape7 with the preview dialog; read before/after spectra side by side.

**GS-3 — Detector instrument expansion (full schema).** Category D · Effort M · Gate: TEG G.
**SHIPPED 2026-07-16** (`bd9eb91` — manifest-equals-schema test enforces completeness).
Expand the Detector Inputs tab from 6 fields to the full schema, grouped: QE (scalar / `qe_table_path`
import via D5 / temperature coefficients), Dark (rate / reference T / activation energy), 1/f
(K, f_low, f_high), G-R & Johnson, FPN (PRNU / DSNU / clutter σ / `noise_regime`), Persistence
(fraction / τ / prior signal), IPC + diffusion, pixel counts. Every field schema-driven; the noise
pie refreshes per edit. **Checkpoint:** run Mike's 2.2 1/f setup in the GUI (set K + band, watch the
1/f wedge appear in the pie); import a QE CSV and see the confirmed-units preview.

**GS-4 — Optics element/coating editor.** Category D · Effort L (split: editor table first;
spectral-file rows + WFE-mode selector second) · Gate: TEG G + **FW-1 merged**.
**Split 1 SHIPPED 2026-07-16** (`2329bb3` — Elements-tab table editor, scalar + CSV-path cells,
derived-ε column, Apply → one `set_optical_elements` call, save/load round-trip). Split 2 (the
WFE-mode selector + Zemax import UI) remains.
The ADR-0009 D2 structured editor: an element-list table (add/remove/reorder rows: kind, transfer
mode, T_K, R/T scalar-or-CSV, cavity fields), ε rendered **derived read-only** per Rule 5 (editable
only on LUMPED rows), committed through the FW-1 facade; the `transmission_input_mode` selector
(scalar mode keeps today's form); `scalar_emissivity` + `nearfield_fraction` (with the Gap-12
vendor-convention tooltip); the WFE-mode selector (scalar / zernike via Zemax import). The
Throughput tab's coating-spectra plot now reflects the authored train. **Checkpoint:** author a
4-element MWIR train (3 mirrors + filter) with per-element temperatures, evaluate, watch
`coating_spectra` + nearfield noise respond; save → reopen → train intact.

### Cross-cutting phases (Gate: TEG Phase G green)

**GX-1 — Existing-API menu wire-ups.** Category A · Effort S · Gate: TEG G.
**SHIPPED 2026-07-16** (`a162ade` — Export YAML/JSON, Schema Browser, Explain; Reset-to-Defaults
stays disabled pending Gap 93).
Enable the disabled placeholders that are pure one-call wire-ups over the shipped API — zero new
backend: File → Export YAML (`Sensor.save`), File → Export JSON Result (`ChainResult.save`),
Tools → Schema Browser (Gap 70 introspection surface), Tools → Explain Parameter…
(`Sensor.explain`), Edit → Reset to Defaults (`Sensor.reset`). The Run-menu sweep/MC/Batch items
**stay disabled** (deferred tier — the tooltips may note "available from the scripting console").
**Checkpoint:** export the current config + result from the menus and reopen them; browse the
schema; explain a parameter; reset one to default.

**GX-2 — Closeout.** Category A–D · Effort S–M · Gate: all prior merged.
Full acceptance pass — each §1 item demonstrated against its audit row; registry hygiene:
close/refresh the GUI-1…GUI-17 rows this increment touched (Rule 22 commit-linked), re-audit
deferrals; CHANGELOG consolidation; arch-doc reconciliation; **this plan moves to
`docs/archive/`** in the completing PR (Rule 24). **Checkpoint:** owner drives one VIS-reflective
and one MWIR element-train scenario end-to-end — configure source + atmosphere + detector, author
the element train, import a QE curve, evaluate, export — without touching the console.

### Sequencing summary

```
   (may start now)                (after TEG Phase G green)
FW-1 (ADR-0009) ──────────┐   ┌─ GS-2 Atmosphere ── GS-3 Detector ── GS-1 Source
                          └───┼─ GS-4 Optics editor   (needs FW-1)
                              ├─ GX-1 Menu wire-ups   (anytime)
                              └─ GX-2 Closeout        (last)
```

GS-2 → GS-3 → GS-1 → GS-4 is the suggested per-stage order (Atmosphere unblocks the most
scenarios and needs no facade; Source waits for TEG T2 to land its warning; Optics needs FW-1),
but the GS phases are independent and may be reordered on owner priority. Total: **one small
framework phase + five GUI phases + closeout** — every phase a view over capability that already
exists.

---

## 5.1 Decisions for owner

1. **Ratify ADR-0009.** — **RATIFIED (owner, 2026-07-16)**; FW-1 executed and shipped same day.
2. **Ratify the phase set and ordering** (§5). — Phase set implicit in decisions 1/3; the GS
   order runs as suggested (GS-2 Atmosphere → GS-3 Detector → GS-1 Source → GS-4 Optics) unless
   the owner reorders before dispatch.
3. **Confirm the deferral list** (§1). — **RATIFIED (owner, 2026-07-16)**: sweep/MC/Batch
   surface, Comparison mode (Gap 79), and the report/export layer (Gap 88) stay out of this
   increment and return in a later-tier plan.
4. **Gap-85 relevance metadata stays a post-increment fast-follow.** — **RATIFIED (owner,
   2026-07-16)**: GS-1 ships the scene-type selector ungated; relevance filtering/badging follows
   once the per-regime schema metadata exists.

---

## 6. Ground rules (inherited verbatim from the v1 plan §4)

All twelve v1 ground rules bind every phase here unchanged: backend-is-the-API (one action ↔ one
call); `src/radiant/gui/` layout; import rules (`gui → api + core` only); worker-thread evaluation;
**units on every displayed value**; errors shown never swallowed; type hints + ruff + no `print`;
design-system styling; pytest-qt offscreen testing; Rule 29 changelog. One addition specific to this
increment: **every new input control is schema-driven from `parameter_defs()`** (never a transcribed
list) and **every config-object editor round-trips through the same loader the API already uses** — a
GUI that builds a config object the engine can't also load from YAML is a defect.
