# Multi-Configuration Capability — Development and Test Plan

**Status:** Active — ratified 2026-07-25; execution in progress (this Phase 0 commit)
**Date:** 2026-07-25 (rev 2 — reworked to the owner's CODE V zoom-configuration model)
**Category:** D (integration + UX; core model work is Category B)
**Read first:** `docs/architecture/RADIANT_Parameter_System.md`,
`docs/architecture/RADIANT_Config_Format.md` §1.3–1.5,
`docs/architecture/RADIANT_Scripting_API.md`, `docs/architecture/RADIANT_GUI_Architecture.md`,
`docs/adr/0009-gui-config-object-editing-and-import.md` (structured-sections mechanism).

---

## 1. Objective

Let one RADIANT session hold **up to 8 named configurations of the same modeling
problem** — different spectral bands of one sensor, different viewing geometries,
nominal vs. as-built builds — evaluate **all of them continuously in the background**,
and compare their results side by side. The interaction model is CODE V zoom
configurations (owner-ratified 2026-07-25):

- A parameter is **shared** (one value, all configurations) by default.
- The user explicitly marks a parameter as **configured**; it then carries **one value
  per configuration** — never sparse, never implicit. Configured parameters are
  visually marked (small red "C").
- A **master configuration selector** chooses which configuration the stage views
  display; the Performance surface shows **every configuration side by side**.

Both the scripting API and the GUI support this; the GUI remains a view over the API
(R-API, one action ↔ one API call).

Driving use cases: band variants (closes the expressibility half of Gap 80), geometry
variants, nominal vs. as-built. Any input parameter may be configured.

---

## 2. What Already Exists (code survey, 2026-07-25)

The survey below is what this plan builds on. File references are to current `main`.

| Building block | Where | Relevance |
|---|---|---|
| `ParameterSet` — schema, explicit-inputs store, provenance per input, `copy()`, `inputs()`, `input_provenances()`, tolerances | `src/radiant/core/parameters.py` | Materialization composes on top of this **without core changes**: config i is "shared inputs + configured values[i] set on a copy". Provenance already carries a `source` string per input. |
| `Sensor` — wraps `ParameterSet` + wavelength grid + element document + injections; `clone()`, `save()/load()/to_yaml()`, `set_many()`, `reset()` | `src/radiant/api/sensor.py` | The materialization target: one configuration ⇒ one `Sensor`. Note: the per-config wavelength grid already falls out of materialization — `_wavelength_grid()` spans that config's own `filter_min/max_um`. Only `wavelength_points` needs a small new hook (§3.4). |
| `compare_configs` (Gap 79, FIXED) — N `(label, ChainResult)` pairs → aligned union-of-metrics matrix, deltas vs. baseline, best-marks | `src/radiant/api/compare.py:323` | The comparison surface already exists; the Performance-tab config columns render from it (or from the raw per-config results). |
| GUI `ComparisonDialog` (GT-3) — current config vs. N **files**, sequential worker evaluation | `src/radiant/gui/widgets/comparison_dialog.py` | Worker + rendering patterns reused for evaluate-all; the file-based dialog itself is retained unchanged. |
| Tabbed Performance dashboard (Summary / All metrics / MTF budget), grouped metric readout | `src/radiant/gui/widgets/stage_center.py`, recent `gui/perf-*` branches | The owner's "each grouping gets its own tab, values shown for all configurations" lands as an extension of exactly this surface. |
| `BatchRunner` — labeled overrides, per-cell failure capture (Rule 17 pattern) | `src/radiant/api/batch.py` | Pattern precedent for failure capture in `evaluate_all`; not reused directly. |
| Structured YAML sections (ADR-0009): `_SECTION_KEYS`, `sections_out` opt-in, raise-not-skip | `src/radiant/io/config.py:51` | The persistence mechanism for the new `configurations:` document — same pattern as `optical_elements`. |
| Reserved keys `_extends` / `_imports` / `_vars` — designed but **unimplemented**, loader raises (CU-050) | `src/radiant/io/config.py:42` | Adjacent but distinct: file-composition features. Deliberately **not** implemented here (§8.1 D-5). |
| GUI main window — single `Sensor`, background evaluate loop, `QUndoStack`, `_adopt_sensor`, schema-driven parameter panel | `src/radiant/gui/main_window.py` | The GUI half rebases this single-sensor state onto "displayed configuration of a set". |
| Gap 80 (OPEN) — no multi-band run concept | `docs/tracking/gaps.md` | Band configurations make dual-band studies expressible; re-dispositioned at close-out (§7). |

**Conclusion:** no `radiant.core` changes are required. The capability is an API-layer
composition plus a persistence section plus GUI state. The physics chain, golden
results, and the `mypy --strict` core surface stay untouched — this plan is
**results-neutral by construction**; any golden diff in any of its PRs is a defect.

---

## 3. Core Design (owner-ratified model)

### 3.1 Data model — shared base + explicitly configured parameters

A **ConfigurationSet** is:

- a **base**: exactly today's `Sensor` state (shared explicit inputs, tolerances,
  element document) — every parameter *not* configured lives here, one value for all;
- an ordered tuple of **configuration names** (1 ≤ N ≤ 8, unique, user-visible);
- a table of **configured parameters**: `dotpath → (v_1, …, v_N)`, one value per
  configuration, aligned with the name order, in input units. Dense by construction —
  a configured parameter has a value in *every* configuration (CODE V zoom semantics);
  there is no sparse/overlay case and no tombstone machinery. Un-configuring keeps
  **configuration #1's value** as the shared value (D-6; scripting may override);
- optional per-configuration `wavelength_points` (§3.4); shared default otherwise;
- a **baseline** designation (for delta columns) and an **active** designation (the
  GUI's displayed configuration; ignored by scripting).

**State invariant:** a dotpath is either in the base's explicit inputs or in the
configured table — never both. `configure(dotpath)` moves it (seeding all N values
from its current shared value, or from its resolved default when the base never set
it); `unconfigure(dotpath, keep=<name>)` collapses it back to the kept configuration's
value as the new shared value. This invariant is what makes the consistency-group
story clean: a group member that should be *derived* is simply absent from both
stores, exactly as today.

**Materialization** (the only evaluation route — no second resolution engine):

```
sensor_for(i) = base.clone()
                 .set_many({p: values[p][i] for p in configured})   # source = "config:<name>"
                 [with per-config wavelength_points when set]
```

Resolution, validation, bounds, enums, consistency groups, defaults all run per
configuration inside the existing `ParameterSet.resolve()`. Nothing is bypassed. An
over-constrained group inside configuration *i* raises the existing actionable error,
tagged with the configuration name.

### 3.2 New API surface (all in `radiant.api`, Rule 19 — one module per concern)

New module `src/radiant/api/config_set.py`:

```python
class ConfigurationSet:
    MAX_CONFIGS: ClassVar[int] = 8

    base: Sensor                                   # owned; the shared state
    def names(self) -> tuple[str, ...]
    def add(self, name: str, *, copy_from: str | None = None) -> None
    def remove(self, name: str) -> None            # configured values for that column dropped
    def rename(self, old: str, new: str) -> None
    def reorder(self, names: Sequence[str]) -> None

    def configured(self) -> Mapping[str, tuple[Any, ...]]   # read-only view
    def configure(self, dotpath: str, values: Sequence[Any] | None = None) -> None
    def unconfigure(self, dotpath: str, *, keep: str | None = None) -> None
        # keep=None (the default, and what the GUI uses) keeps configuration #1's
        # value as the shared value (owner-ratified D-6); keep=<name> is a
        # scripting-only override.
    def set_value(self, dotpath: str, config: str, value: Any, *, unit: str | None = None) -> None
    def set_values(self, dotpath: str, values: Sequence[Any]) -> None
    def is_configured(self, dotpath: str) -> bool

    baseline: str                                  # delta reference for comparison surfaces
    active: str                                    # GUI display state; persisted, scripting-neutral

    def set_wavelength_points(self, config: str | None, n: int) -> None   # None = shared default
    def sensor_for(self, name: str) -> Sensor      # materialize (§3.1); isolated clone
    def validate_all(self) -> dict[str, RadiantError | None]              # resolve-only, no physics
    def evaluate_all(self, *, progress=None, cancel=None) -> ConfigSetRunResult
    def compare(self, run: ConfigSetRunResult) -> ComparisonResult        # compare_configs adapter

    @classmethod
    def load(cls, path) -> ConfigurationSet
    def save(self, path) -> Path
    def to_yaml(self, ...) -> str
```

Notes:

- `ConfigSetError(RadiantError)` with actionable what/why/action; every error raised
  on behalf of a configuration names it.
- `configure()` validates each seeded/supplied value through the schema immediately
  (type, bounds, enum — same path as `Sensor.set`), and enforces the §3.1 invariant.
- `evaluate_all` evaluates in name order with the **active configuration first** (so
  the GUI's displayed views refresh fastest), captures per-configuration
  `RadiantError`s as recorded failures (Rule 17 pattern from `BatchRunner` — never
  silently dropped), and supports the existing `radiant.api._progress`
  progress/cancel contract. N ≤ 8 × ~0.22 s/run keeps a full pass under ~2 s.
- `ConfigSetRunResult`: ordered `(name, ChainResult | error)` plus per-configuration
  warning attribution; feeds `compare_configs` directly.
- A `ConfigurationSet` with one configuration and an empty configured table behaves
  observably identically to a bare `Sensor` (the degenerate case is the current app).

**Out of the v1 model** (deferred; tracked as gaps at close-out): per-configuration
tolerance distributions (base tolerances apply to every configuration),
per-configuration stage-output injections (Gap 68 objects have no YAML form; they
apply to all configurations as today), cross-config derived metrics (band ratios,
dual-band contrast), sweeps/Monte-Carlo of a whole set, and per-configuration optical
element documents (owner-ratified defer to v1.1, D-7 — scalar as-built knobs cover the
near-term need; gap-tracked at close-out).

### 3.3 Persistence — a `configurations:` structured section

One file = one study. Extends the existing ADR-0009 section mechanism
(`_SECTION_KEYS`); shared parameters remain exactly today's document, so **a file with
no `configurations:` section is byte-for-byte today's format and loads everywhere
unchanged** (backward compatibility is structural, not a migration).

```yaml
# ... shared parameters exactly as today ...
optics:
  aperture_diameter_m: 0.30
# ...

configurations:
  names: [MWIR, LWIR]
  active: MWIR                  # GUI resume state
  baseline: MWIR                # delta reference
  wavelength_points:            # optional; omitted names use _radiant.wavelength_points
    LWIR: 300
  parameters:                   # dotpath → list aligned with `names` order
    spectral_integration.filter_min_um: [3.95, 8.0]
    spectral_integration.filter_max_um: [4.45, 12.0]
    detector.qe_value: [0.75, 0.62]
```

Rules: every `parameters` list length must equal `len(names)` (dense — a mismatch is a
`ConfigError`, never padded); dotpaths validate against the schema at load with the
existing did-you-mean; a dotpath may not appear both in the shared body and in
`parameters` (§3.1 invariant, checked at load); values are input-unit scalars;
`is_file_path` values relativize/resolve exactly like shared values (CU-177 helpers
reused); `names` length 1–8, unique; `active`/`baseline` must name a member. Loading a
section-bearing file through plain `Sensor.load`/`load_config` raises with an
actionable "load it with ConfigurationSet.load" message (Rule 17) via the existing
`_SECTION_KEYS` opt-in machinery.

### 3.4 Per-configuration wavelength grid (owner: in v1)

The evaluation grid itself is already per-configuration for free: each materialized
`Sensor` builds `linspace(filter_min_um, filter_max_um, wavelength_points)` from its
own resolved band. What is currently session-global is the **point count**. v1 adds an
optional per-configuration `wavelength_points` (§3.2/§3.3); supporting it needs one
small public `Sensor` addition — a supported way to produce a clone with a different
point count (e.g. `Sensor.with_wavelength_points(n) -> Sensor`), since `_wl_points` is
currently constructor-only. That is the **only** `Sensor` change this plan makes
(CHANGELOG public-surface entry; lock-step doc in `RADIANT_Scripting_API.md`).

### 3.5 What this does NOT touch

Physics stages, `ChainState`, `ChainRunner`, `RadiantSession`, the parameter schema,
golden baselines, and `radiant.core` in its entirety. CLI support (e.g.
`radiant run study.yaml --configuration LWIR`) is a thin follow-on, Phase 5.

---

## 4. GUI Design (owner vision, 2026-07-25 — binding for Phase 4)

CODE V zoom-configuration interaction, mapped onto the shipped contextual per-stage
layout:

1. **Configuration manager.** The user defines the number of configurations (≤ 8) and
   names them (create / duplicate / rename / delete / reorder; set baseline). A
   compact dialog reached from the toolbar/menu, driving the `ConfigurationSet` API
   one action per call.
2. **Master configuration selector.** A persistent control (toolbar combo or compact
   tab strip — final form decided in the Phase 4a spec against horizontal space)
   selects the **displayed** configuration. Stages 1–8 (all per-stage center views,
   forms, readouts, geometry viewer, right-rail values) show the displayed
   configuration's values and results.
3. **Marking a parameter as configured.** Opt-in per parameter (context-menu /
   editor-row action "Configure across configurations…"). Configured parameters carry
   a **small red "C" badge** in the parameter panel and per-stage forms — the owner's
   explicit visual spec. Un-configuring is the inverse action and keeps configuration
   #1's value as the shared value (D-6), stated in the confirmation so it is never a
   silent physics change in the other configurations.
4. **Editing configured values.** Two routes: (a) the "C" badge / context action opens
   a small per-parameter table — one row per configuration, value + unit, edit all N
   in one place (the owner's "set the value for that parameter for all
   configurations"); (b) inline edits in a stage form while configuration X is
   displayed edit **X's value only** (owner-confirmed, D-8). Editing a shared (unmarked)
   parameter edits the single shared value, as today — no hidden scope mode.
5. **Everything calculates.** The existing debounced background evaluate loop becomes
   evaluate-all: displayed configuration first (stage views refresh at today's
   latency), remaining configurations follow on the worker; per-configuration failures
   surface in the Messages panel tagged with the configuration name (never blocking
   the others). With N ≤ 8 a full pass is ~2 s.
6. **Performance surface — all configurations side by side.** Extending the tabbed
   Performance dashboard: each metric grouping gets its own tab; within a tab, each
   metric row shows a **column per configuration** (units per R-UNITS; values from the
   background evaluate-all; "—" for a configuration missing the metric — Rule 17,
   never zero-filled). **Plain values only** (D-9) — no delta or best-mark
   decoration in the GUI; delta-vs-baseline and best-marks remain available via the
   scripting `compare` surface.
   *As shipped (Phase 4d):* between this plan and that phase the owner slimmed the
   Performance pane to **one flat pane of themed group cards** and removed the interim
   tab set, so the grouping unit is the card, not a tab. The columns landed on those
   cards rather than re-introducing tabs — same groups, same order, N columns each.
   Rationale and the full rendering contract: `RADIANT_GUI_Architecture.md` §4.2e.
7. **Cross-cutting.** Undo/redo covers configure/unconfigure, per-config edits, and
   configuration CRUD (extend the existing `QUndoStack` commands with scope); YAML
   view shows the full document including the section; scripting console exposes the
   set (e.g. `configs` alongside `sensor`); open/save/dirty-tracking treat the set as
   the document; a stable per-configuration accent color from the theme token set
   identifies configurations in the selector, performance columns, and any plot
   overlays (both themes). Single-configuration sessions look **exactly like today's
   GUI** (selector collapsed/hidden; no badges) — a zero-regression requirement.

---

## 5. Development Plan (phases = branches = merges, per Multi-Agent Git Hygiene)

Each phase is a short-lived branch, lands with its tests and lock-step docs, passes the
full gate battery (`pytest -q`, touched goldens, `mypy --strict` core+api, `ruff`,
`lint-imports`, `check_org_rules.py`, `gen_param_reference.py --check`), and merges
before the next starts.

### Phase 0 — ADR (doc-only; Category A)
- **ADR-0010: Multi-configuration model** — records §3 (dense zoom-style configured
  parameters, §3.1 invariant, one-file persistence, N ≤ 8, per-config
  wavelength_points, `_extends` out of scope) and decisions D-1…D-10 (§8.1), including
  the D-10 terminology convention.
- Update this plan Draft → Active. (All design questions were resolved with the owner
  2026-07-25 — §8.2; Phase 0 is authoring + ratification of the ADR text only.)

### Phase 1 — Core model (`api/config_set.py`; Category B)
- `ConfigurationSet`, configure/unconfigure/set_value(s), CRUD, invariant enforcement,
  `sensor_for`, `validate_all`, `evaluate_all` (+ `ConfigSetRunResult`), `compare`
  adapter, `Sensor.with_wavelength_points`.
- Provenance: configured values carry `source="config:<name>"` — `Sensor.resolved()` /
  `explain()` name the owning configuration with zero new provenance machinery.
- Lock-step docs: `RADIANT_Scripting_API.md`, `RADIANT_Parameter_System.md`
  (provenance note). CHANGELOG public-surface entries.

### Phase 2 — Persistence (io + api; Category B)
- `configurations` added to `_SECTION_KEYS`; section schema validation in a new
  `io/config_set_section.py` (Rule 19); `ConfigurationSet.load/save/to_yaml`;
  interplay with `_radiant` meta (shared `wavelength_points`, tolerances stay shared).
- Lock-step docs: `RADIANT_Config_Format.md` (new §; cross-note in §1.3–1.5 that
  configurations are not `_extends`). CHANGELOG config-format entry.

### Phase 3 — Orchestration polish + example (api; Category B)
- Active-first evaluation order, per-configuration warning attribution,
  baseline-delta semantics end-to-end, failure-capture ergonomics.
- Example script under `examples/` (dual-band study) + walkthrough per the scenario
  workflow rules.

### Phase 4 — GUI (Category D; sub-phases land separately, each behind the gates)
- **4a. Session model + selector.** Main window holds a `ConfigurationSet`; the
  master selector switches the displayed configuration; evaluate loop becomes
  evaluate-all (displayed-first). Single-config zero-regression test.
- **4b. Configure/edit flow.** "Configure across configurations…" action; red "C"
  badges in the parameter panel and per-stage forms; the per-parameter N-value table
  editor; inline edits scoped to the displayed configuration; undo/redo of scoped
  edits and configure/unconfigure.
- **4c. Configuration manager dialog.** CRUD + baseline + live `validate_all` status
  per row; ≤ 8 enforcement with actionable messaging.
- **4d. Performance side-by-side.** Per-grouping tabs × per-configuration columns
  (plain values, D-9); config accent colors; per-config failure/warning surfacing in
  Messages.
- **4e. Persistence + polish.** Open/save/recent for studies; YAML view; console
  `configs` object; `active` persisted; dirty tracking.
- Lock-step docs: `RADIANT_GUI_Architecture.md` §4. gaps.md entries for any 4a–4e
  deferral.

### Phase 5 — Close-out (Category A)
- CLI `--configuration` flag (or explicitly gap it); Gap 80 re-disposition; CU sweep
  (Rule 21); plan → `docs/archive/` (Rule 24).

Rough effort: Phases 1–3 one solid session each; Phase 4 is 3–5 sessions (4b and 4d
are the heavy ones). Every phase ends user-visible.

---

## 6. Test Plan

**Gate battery** applies to every phase (§5 preamble). Beyond it:

### Phase 1 (unit, `src/radiant/api/tests/`)
- Materialization: configured values land per configuration; non-configured values
  identical to base across all N (full `inputs()` comparison); provenance
  `config:<name>`; isolation (mutating base after `sensor_for` doesn't leak, and vice
  versa).
- Invariant: configuring a base-set parameter moves it (seeded N-wide, base input
  removed); configuring a never-set parameter seeds from schema default; a dotpath in
  both stores is unrepresentable through the API; unconfigure() keeps configuration
  #1's value as shared (D-6 default), unconfigure(keep=X) keeps X's.
- Consistency groups: configure `f_number` while base holds `focal_length_m` →
  over-constrained error naming the configuration; after the user resets the base
  focal length, each configuration re-derives it from its own `f_number` (asserted
  numerically).
- CRUD: name collisions, unknown dotpath (did-you-mean preserved), remove drops the
  column, reorder keeps value alignment, 9th configuration rejected actionably,
  baseline/active validated.
- `evaluate_all`: active-first order; one failing configuration captured while others
  complete; cancel/progress fire (mirror existing sweep tests).
- Per-config `wavelength_points`: materialized grid point count differs per config;
  band-driven grid span differs per config with shared point count (the free path).
- Degenerate case: 1 configuration + empty table ≡ bare `Sensor` (metric-identical).
- `compare` adapter equals a hand-built `compare_configs` call.

### Phase 2 (unit + integration)
- Round-trip: save → load reproduces names/order, configured table (input units),
  baseline/active, per-config wavelength_points; shared-only round-trip unchanged
  (existing Gap 67 tests must not change).
- Load-time validation: list-length mismatch, duplicate names, dotpath in both body
  and section, unknown dotpath, >8 names — each a `ConfigError` naming file +
  configuration + parameter.
- File-path parameters inside the configured table relativize/resolve (CU-177 parity).
- Section-bearing file via bare `Sensor.load`/`load_config` raises actionably.
- Rule 30: explicit encodings, `newline="\n"`, `pathlib` only (org-rules script +
  fixture hygiene).

### Phase 3
- Warning attribution per configuration; baseline-delta correctness on a 3-config set
  with a metric absent in one configuration (None, never zero — Rule 17).

### Phase 4 (pytest-qt, `src/radiant/gui/tests/`, patterns already in-tree)
- 4a: switching the selector re-renders stage views with that configuration's values
  (assert a differing metric); evaluate-all populates all N in the background;
  single-config file shows today's UI exactly (explicit regression test).
- 4b: configure action seeds N values and shows the red "C"; table editor edits any
  configuration; inline edit while X displayed changes X only (assert Y unchanged);
  unconfigure collapses per Q-1; undo/redo restores value **and** scope.
- 4c: dialog CRUD drives the API object; duplicate name / delete-active / 9th-config
  paths handled actionably.
- 4d: performance tabs render metric × configuration matrices with units; a
  failed configuration's column shows its failure state, others intact (no silent
  drop); numbers equal `compare_configs` output.
- 4e: GUI open/save/recent round-trip; YAML view contains the section; console
  `configs` live; dirty tracking across configured edits.
- **Results-neutrality regression:** full golden suite untouched in every phase.

### Cross-cutting
- `mypy --strict` on the new api/io modules from day one; import-linter layer rules
  (GUI imports only `api`/`core`); every new error path asserts the actionable-error
  contract (what/why/action fields populated).

---

## 7. Registry & Doc Lock-Step Summary (Rules 20/21/29)

| Artifact | Change | Phase |
|---|---|---|
| `docs/adr/0010-multi-configuration-model.md` | new | 0 |
| `RADIANT_Scripting_API.md` | new section: ConfigurationSet; `Sensor.with_wavelength_points` | 1 |
| `RADIANT_Parameter_System.md` | provenance `source="config:<name>"` note | 1 |
| `RADIANT_Config_Format.md` | new §: `configurations:` section; cross-note in §1.3–1.5 | 2 |
| `RADIANT_GUI_Architecture.md` | §4 layout: selector, badges, performance columns | 4 |
| `CHANGELOG.md` | public-surface entries per phase (1, 2, 4) | each |
| `docs/tracking/gaps.md` | Gap 80 re-dispositioned (band configurations expressible; cross-band derived metrics remain a narrowed entry); new entries for §3.2 deferrals | 5 |
| This plan | Draft → Active (0), → archive (5) | 0, 5 |

---

## 8. Decisions

### 8.1 Ratified (owner, 2026-07-25)

- **D-1 Model:** CODE V zoom-configuration semantics — opt-in configured parameters,
  dense one-value-per-configuration, everything else shared. No sparse overlays, no
  per-configuration presence variance.
- **D-2 Marking:** configuring is explicit per parameter; configured parameters get a
  small red "C" badge; a per-parameter editor sets all N values in one place.
- **D-3 Display:** master selector picks the displayed configuration for stages 1–8;
  the Performance surface shows per-grouping tabs with all configurations side by
  side.
- **D-4 Evaluation:** all configurations evaluate in the background, always.
- **D-5 Scope:** per-configuration wavelength grids are **in** v1 (point count +
  band-driven span); N is capped at 8; `_extends`/`_imports` remain out of scope;
  naming is open to alternatives (see Q-5).
- **D-6 Unconfigure keeps configuration #1's value** (owner, 2026-07-25). When a
  parameter is un-configured, the first configuration's value always becomes the
  shared value (GUI confirmation states it; `keep=` is a scripting-only override).

- **D-7 Per-configuration optical prescriptions deferred to v1.1** (owner,
  2026-07-25). The `optical_elements` document stays shared across all
  configurations in v1; scalar as-built knobs (WFE, f/#, transmission, temperatures)
  are ordinary configurable parameters and cover the near-term as-built workflow. A
  per-configuration element document is an additive later extension of the section
  format; tracked as a gap entry at close-out (Phase 5).
- **D-8 Inline edit scope** (owner, 2026-07-25): editing a configured parameter in a
  stage form or the parameter panel while configuration X is displayed edits **X's
  value only**; the per-parameter table is the all-N editor. (CODE V behavior.)
- **D-9 Performance tabs show plain values only** (owner, 2026-07-25): metric ×
  configuration cells carry value + unit, nothing else. Delta-vs-baseline and
  best-marks are not rendered in the GUI; they remain available through the scripting
  `compare` surface (`compare_configs`), and the `baseline` designation stays in the
  model for that purpose.
- **D-10 Naming: "Configurations"** (owner, 2026-07-25, conditional on the
  terminology staying unambiguous). GUI label "Configurations"; code
  `ConfigurationSet`; docs "configuration set". **Binding disambiguation convention**
  (recorded in ADR-0010, enforced in every lock-step doc edit): prose written under
  this plan always says **"config file" / "YAML config"** for the on-disk artifact and
  reserves bare **"configuration"** for a member of a configuration set; existing doc
  text is amended where the two would otherwise collide in the same paragraph. If
  Phase 1–4 reviews find the convention breaking down in practice, renaming the
  members (e.g. "variants") is a Phase-0-level decision to reopen, not a silent drift.

### 8.2 Question-resolution record (all closed 2026-07-25)

- **Q-1 Unconfigure semantics.** RESOLVED → D-6.
- **Q-2 Per-configuration optical prescriptions.** RESOLVED → D-7 (defer to v1.1).
- **Q-3 Inline edit scope.** RESOLVED → D-8.
- **Q-4 Performance presentation.** RESOLVED → D-9 (plain values).
- **Q-5 Naming.** RESOLVED → D-10 ("Configurations", with the disambiguation
  convention).
