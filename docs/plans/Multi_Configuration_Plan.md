# Multi-Configuration Capability — Development and Test Plan

**Status:** Draft — awaiting owner ratification of the decision points in §8 and the
owner's GUI vision (§6 is a proposal, not a spec, until then).
**Date:** 2026-07-25
**Category:** D (integration + UX; core model work is Category B)
**Read first:** `docs/architecture/RADIANT_Parameter_System.md`,
`docs/architecture/RADIANT_Config_Format.md` §1.3–1.5,
`docs/architecture/RADIANT_Scripting_API.md`, `docs/architecture/RADIANT_GUI_Architecture.md`,
`docs/adr/0009-gui-config-object-editing-and-import.md` (structured-sections mechanism).

---

## 1. Objective

Let one RADIANT session hold **multiple named configurations of the same modeling
problem** — different spectral bands of one sensor, different viewing geometries,
nominal vs. as-built builds — where **any input parameter may take a per-configuration
value**, evaluate them together, and compare their results. Both the scripting API and
the GUI must support this; the GUI remains a view over the API (R-API, one action ↔ one
API call).

Driving use cases (owner, 2026-07-25):

1. **Band variants** — one sensor, N filter bands (closes the expressibility half of
   Gap 80: no multi-band run concept).
2. **Geometry variants** — one sensor, N viewing geometries (nadir vs. 60° slant, etc.).
3. **Nominal vs. as-built** — same sensor, measured values overriding design values
   (possibly including a different optical prescription).
4. Any mix of the above; any parameter is fair game for per-config override.

---

## 2. What Already Exists (code survey, 2026-07-25)

The survey below is what this plan builds on. File references are to current `main`.

| Building block | Where | Relevance |
|---|---|---|
| `ParameterSet` — schema, explicit-inputs store, provenance per input, `copy()`, `inputs()`, `input_provenances()`, tolerances | `src/radiant/core/parameters.py` | The overlay mechanism composes on top of this **without core changes**: a variant is "base inputs + overrides re-set on a copy". Provenance already distinguishes sources via the `source` string. |
| `Sensor` — wraps `ParameterSet` + wavelength grid + element document + stage-output injections; `clone()`, `save()/load()/to_yaml()`, `set_many()`, `reset()` | `src/radiant/api/sensor.py` | The materialization target: one variant ⇒ one `Sensor`. `clone()` + `set_many()` is already the supported variant-building route (docstring on `ParameterSet.copy`). |
| `compare_configs` (Gap 79, FIXED) — N `(label, ChainResult)` pairs → aligned union-of-metrics matrix, deltas vs. baseline, best-marks | `src/radiant/api/compare.py:323` | The comparison surface already exists. Multi-config evaluation feeds it directly; no new comparison math needed. |
| GUI `ComparisonDialog` (GT-3) — current config vs. N **files**, sequential worker evaluation, `compare_configs` rendering | `src/radiant/gui/widgets/comparison_dialog.py` | Reuse the worker + table rendering; replace "load files" with "the session's configurations". |
| `BatchRunner` — labeled-axis cartesian product with per-cell dot-path overrides and per-cell failure capture | `src/radiant/api/batch.py` | Pattern precedent for named overrides + Rule 17 failure capture; multi-config is the N=1-axis, hand-named version of this. Not reused directly (different lifecycle: persistent named configs vs. throwaway grid). |
| Structured YAML sections (ADR-0009): `_SECTION_KEYS`, `sections_out` opt-in, raise-not-skip | `src/radiant/io/config.py:51` | The persistence mechanism for the new `configurations:` document — same pattern as `optical_elements`. |
| Reserved keys `_extends` / `_imports` / `_vars` — designed (Config_Format §1.3–1.5) but **unimplemented**, loader raises (CU-050) | `src/radiant/io/config.py:42` | Adjacent but distinct: those are *file-composition* features. This plan deliberately does **not** implement them (§8 D-1). |
| GUI main window — single `Sensor`, background evaluate loop, `QUndoStack`, `_adopt_sensor` lifecycle, schema-driven parameter panel | `src/radiant/gui/main_window.py` | The GUI half rebases this single-sensor state onto "active configuration of a set". |
| Gap 80 (OPEN) — no multi-band run concept | `docs/tracking/gaps.md` | Band variants under this plan make dual-band studies expressible; Gap 80 is re-dispositioned at the end (§7). |

**Conclusion of survey:** no core (`radiant.core`) changes are required. The capability
is an API-layer composition (`ParameterSet.copy` + `Sensor.clone` + `compare_configs`)
plus a persistence section plus GUI state. That keeps the physics chain, golden results,
and `mypy --strict` core surface untouched — this plan is **results-neutral by
construction**; any golden diff in any of its PRs is a defect.

---

## 3. Core Design

### 3.1 Data model — base + named overlay variants (recommended)

A **ConfigurationSet** (working name; see Q-1 in §8) is:

- a **base**: exactly today's `Sensor` state (explicit inputs, tolerances, element
  document, wavelength_points), and
- an ordered list of **variants**, each:

```
Variant:
  name: str                     # unique, user-visible ("MWIR", "as-built")
  description: str = ""
  overrides: dict[str, Any]     # flat dot-path → value, input units (same contract as Sensor.set_many)
  clears: tuple[str, ...] = ()  # dot-paths whose BASE explicit input is removed before overrides apply
  optical_elements: list[dict] | None = None   # optional per-variant element document (replaces base's)
```

- one variant (or the bare base) is designated **baseline** for delta reporting, and
  one is **active** (the GUI's editing focus).

**Materialization** (the only evaluation route — no second resolution engine):

```
sensor_for(variant) = base.clone()
                       .reset(each of variant.clears)
                       .set_many(variant.overrides)      # provenance source = "config:<name>"
                       [.set_optical_elements(variant.optical_elements) if given]
```

Resolution, validation, consistency groups, defaults — all run exactly as today, per
variant, inside the existing `ParameterSet.resolve()`. Nothing is bypassed.

**Why `clears` (tombstones) is not optional.** Consistency groups make pure overlays
insufficient: if the base sets `focal_length_m` and an as-built variant instead measures
`f_number`, setting `f_number` on top **over-constrains** the group and correctly raises.
The variant must be able to *remove* a base input so the group re-derives. This is the
nominal-vs-as-built workflow, not an edge case.

**Explicitly rejected alternatives:**

- *Layered inputs inside `ParameterSet`* (a real override stack in core): more invasive,
  touches the frozen, `mypy --strict`-gated core for something composition already
  provides; violates "no abstractions not in the architecture docs" until an ADR says
  otherwise. Revisit only if materialization cost ever matters (it will not: a full
  evaluate is ~0.22 s; a clone+resolve is milliseconds).
- *N independent full `Sensor`s with no shared base*: loses the central point — edit a
  shared parameter once, all configurations see it; the diff between configs is explicit
  and small. Also what the owner described ("any input parameter can be defined as part
  of a different configuration" implies the rest is shared).
- *Implementing `_extends`/`_imports` and managing N files*: file composition solves a
  different problem (config libraries on disk). A GUI session needs one document with
  the variants inside it. §8 D-1.

### 3.2 New API surface (all in `radiant.api`, Rule 19 — one module per concern)

New module `src/radiant/api/config_set.py` (name per Q-1):

```python
@dataclass(frozen=True)
class ConfigVariant:
    name: str
    overrides: Mapping[str, Any]
    clears: tuple[str, ...] = ()
    description: str = ""
    optical_elements: tuple[Mapping[str, Any], ...] | None = None

class ConfigurationSet:
    base: Sensor                                  # owned; the shared state
    def variants(self) -> tuple[ConfigVariant, ...]
    def add(self, variant: ConfigVariant) -> None           # name-collision → ConfigSetError
    def remove(self, name: str) -> None
    def rename(self, old: str, new: str) -> None
    def update(self, variant: ConfigVariant) -> None        # replace by name
    def duplicate(self, name: str, new_name: str) -> None
    baseline: str | None                          # None = bare base is the baseline column
    def sensor_for(self, name: str | None) -> Sensor        # None = base; materialize (§3.1)
    def evaluate_all(self, *, include_base: bool = ..., progress=None, cancel=None)
        -> ConfigSetRunResult                     # ordered; per-variant RadiantError captured (Rule 17
                                                  #   pattern from BatchRunner — recorded, never dropped)
    def compare(self, run: ConfigSetRunResult) -> ComparisonResult   # thin compare_configs adapter
    def validate_all(self) -> dict[str, RadiantError | None]         # resolve-only pass, no physics
    # persistence
    @classmethod def load(cls, path) -> ConfigurationSet
    def save(self, path) -> Path
    def to_yaml(self, ...) -> str
```

`ConfigSetError(RadiantError)` with actionable what/why/action. Errors from a variant's
resolution are re-raised (or captured, in `evaluate_all`) **tagged with the variant
name** — a bounds error must say which configuration it came from.

Out of the v1 model (deferred, tracked as gaps at close-out unless the owner pulls them
in — §8): per-variant tolerances (base tolerances apply to every variant), per-variant
`wavelength_points`, per-variant stage-output injections (Gap 68 objects have no YAML
form; they apply to all variants as today), cross-config derived metrics (band ratios),
and sweeps/Monte-Carlo *of a whole set*.

### 3.3 Persistence — a `configurations:` structured section

One file = one study. Extends the existing ADR-0009 section mechanism
(`_SECTION_KEYS`); base parameters remain exactly today's document, so **a file with no
`configurations:` section is byte-for-byte today's format and loads everywhere
unchanged** (backward compatibility is structural, not a migration).

```yaml
# ... base parameters exactly as today ...
optics:
  aperture_diameter_m: 0.30
# ...

configurations:
  baseline: nominal          # optional; must name a variant or "base"
  active: as-built           # GUI resume state; ignored by scripting
  variants:
    - name: nominal
      description: Design prescription
      overrides: {}
    - name: as-built
      description: TVAC-measured values
      overrides:
        optics.wfe_rms_waves: 0.11
        optics.f_number: 3.02
      clears:
        - optics.focal_length_m        # re-derive from measured f/# instead
    - name: LWIR
      overrides:
        spectral_integration.filter_min_um: 8.0
        spectral_integration.filter_max_um: 12.0
```

Rules: `overrides` keys are flat dot-paths validated against the schema at load
(unknown name → `ConfigError` with did-you-mean, same as base parameters); values are
input-unit scalars; `is_file_path` values relativize/resolve exactly like base values
(CU-177 helpers reused); per-variant `optical_elements:` allowed inside a variant entry,
normalized through the same ADR-0009 parser. Loading a section-bearing file through
plain `Sensor.load` raises with an actionable "load it with ConfigurationSet.load"
message (Rule 17 — never silently drop the variants); `load_config` gets
`configurations` added to `_SECTION_KEYS` so the existing opt-in machinery does this.

### 3.4 What this does NOT touch

Physics stages, `ChainState`, `ChainRunner`, `RadiantSession`, the parameter schema,
golden baselines, and `radiant.core` in its entirety. CLI support (e.g.
`radiant run study.yaml --configuration LWIR`) is a thin follow-on, Phase 5.

---

## 4. Development Plan (phases = branches = merges, per Multi-Agent Git Hygiene)

Each phase is a short-lived branch, lands with its tests and lock-step docs, passes the
full gate battery (`pytest -q`, touched goldens, `mypy --strict` core+api, `ruff`,
`lint-imports`, `check_org_rules.py`, `gen_param_reference.py --check`), and merges
before the next starts. Category letters set the report requirements.

### Phase 0 — ADR + ratification (doc-only; Category A)
- **ADR-0010: Multi-configuration model** — records §3's decisions (base+overlay,
  tombstones, one-file persistence, `_extends` explicitly out of scope, naming per Q-1,
  the v1 exclusion list in §3.2) and the owner's answers to §8.
- Update this plan Draft → Active.
- Exit: owner ratifies ADR + the GUI direction (§6).

### Phase 1 — Core model (`api/config_set.py`; Category B)
- `ConfigVariant`, `ConfigurationSet`, materialization, `validate_all`, `evaluate_all`
  with progress/cancel (reusing `radiant.api._progress`), `compare` adapter,
  `ConfigSetError`.
- Provenance: overridden values carry `source="config:<name>"`; `Sensor.resolved()`
  therefore explains per-config values with zero new provenance machinery.
- Lock-step docs: `RADIANT_Scripting_API.md` (new section), ADR cross-links.
- CHANGELOG: public-surface addition.

### Phase 2 — Persistence (io + api; Category B)
- `configurations` added to `_SECTION_KEYS`; section schema validation in a new
  `io/config_set_section.py` (Rule 19); `ConfigurationSet.load/save/to_yaml`;
  `_radiant` meta interplay (wavelength_points, tolerances stay base-level).
- Lock-step docs: `RADIANT_Config_Format.md` (new §, plus a note in §1.3–1.5 that
  variant overlays are NOT `_extends`).
- CHANGELOG: config-format addition.

### Phase 3 — Comparison & orchestration polish (api; Category B)
- `ConfigSetRunResult`: ordered results, per-variant captured errors, warnings
  aggregation surface (labels which config warned), direct feed into `compare_configs`.
- Baseline semantics end-to-end (baseline column drives deltas).
- Example script under `examples/` (band-pair study) + walkthrough doc per the
  scenario-workflow rule if the owner wants a scenario exercising it.

### Phase 4 — GUI (Category D; sub-phases land separately, each behind the gates)
Sequenced smallest-risk-first; detailed spec in §6 once ratified.
- **4a. Session model + selector**: main window holds a `ConfigurationSet`; a
  configuration selector (proposal: compact tab bar above the stage strip) switches the
  **active** variant; switching materializes via `sensor_for` and drives the existing
  evaluate loop untouched. Single-config files behave exactly as today (selector hidden
  or showing only "base" — zero-regression requirement).
- **4b. Edit scoping + indicators**: every parameter edit goes to base (all configs) or
  to the active variant's overrides; per-row badge on overridden parameters (config
  color chip + tooltip listing per-config values); context actions "Override in this
  configuration" / "Revert to shared value" / "Promote to all configurations"; `clears`
  exposed as "Unset in this configuration". Undo/redo covers scoped edits (extend the
  existing `QUndoStack` commands with scope).
- **4c. Manage Configurations dialog**: add/duplicate/rename/delete/reorder, set
  baseline, per-variant description, live `validate_all` status per row.
- **4d. Results across configs**: Evaluate-All action (worker per GT-3 pattern);
  in-session comparison table (rework `ComparisonDialog` to take the set; file-based
  mode retained); overlay curves (MTF, spectral) colored per config where the stage
  view already supports overlays.
- **4e. Persistence + polish**: open/save studies (dirty tracking, title, recent
  files), YAML view shows the full document, scripting console exposes the set
  (`configs` object alongside `sensor`), `active` remembered in the file.
- Lock-step docs: `RADIANT_GUI_Architecture.md` §4 (layout addition), gaps.md entries
  for anything deferred out of 4a–4e.

### Phase 5 — Close-out (Category A)
- CLI `--configuration` flag (or explicitly gap it), Gap 80 re-disposition (§7), CU
  sweep for anything found en route (Rule 21), plan → `docs/archive/` (Rule 24).

Rough effort: Phases 1–3 are each a solid single-session task; Phase 4 is 3–5 sessions
(4b is the hardest — edit scoping touches the parameter panel, per-stage forms, and
undo). Nothing here is speculative infrastructure; every phase ends user-visible.

---

## 5. Test Plan

**Gate battery** applies to every phase (see §4 preamble). Beyond it:

### Phase 1 (unit, `src/radiant/api/tests/`)
- Materialization: override applies; un-overridden values identical to base (spot-check
  full `inputs()` equality minus overrides); provenance shows `config:<name>`.
- Tombstones: base-set + variant-clear → group re-derivation (the f/# vs. focal-length
  case above, asserted numerically); clear of a never-set input is a no-op (or error —
  per ADR decision); override + clear of the same path → error.
- Consistency-group over-constraint through an overlay raises the existing actionable
  error, tagged with the variant name.
- Name collisions, unknown-parameter override (did-you-mean preserved), rename/remove/
  duplicate semantics, baseline validation.
- `evaluate_all`: order preserved; one failing variant captured, others complete;
  cancel/progress callbacks fire (mirror existing sweep tests).
- Isolation: mutating the base after materialization does not affect a returned
  `Sensor` and vice versa (clone semantics).
- `compare` adapter equals a hand-built `compare_configs` call.

### Phase 2 (unit + integration)
- Round-trip: save → load reproduces variants, overrides (input units), clears,
  baseline/active, per-variant element docs; base round-trip unchanged (existing Gap 67
  tests must not change).
- A no-section file loads as a set with zero variants; a section-bearing file through
  bare `Sensor.load` / `load_config` raises actionably; unknown override name at load
  → `ConfigError` naming file, variant, and parameter.
- File-path parameters inside overrides relativize/resolve (CU-177 parity test).
- Rule 30: explicit encodings, `newline="\n"`, `pathlib` only — asserted by existing
  org-rules script plus a Windows-oblivious round-trip test (no absolute POSIX paths in
  fixtures).

### Phase 3
- Per-variant warning attribution; baseline-delta correctness on a 3-config set with a
  metric absent in one config (None, never zero — Rule 17).

### Phase 4 (pytest-qt, `src/radiant/gui/tests/`, patterns already in-tree)
- 4a: switching configs re-evaluates with the right materialized values (assert a
  metric differs across two variants); single-config file shows today's UI (explicit
  regression test); dirty/undo state survives a switch per the ratified semantics.
- 4b: scoped edit lands in the right place (base edit visible in all variants; variant
  edit only in one); badge presence/absence; revert/promote actions round-trip;
  undo/redo of a scoped edit restores both value and scope.
- 4c: dialog CRUD drives the API object; invalid states (dup name, deleting the active
  config) handled with actionable messages.
- 4d: Evaluate-All happy path + one-variant-failure path (table renders, failure
  surfaced, no silent drop); comparison table numbers equal `compare_configs` output.
- 4e: open/save/recent round-trip through the GUI; YAML view contains the section;
  console `configs` object live.
- **Results-neutrality regression:** full golden suite untouched in every GUI phase.

### Cross-cutting
- `mypy --strict` on the new api/io modules from day one; import-linter (new modules
  obey existing layer rules — `api` may import `io`, GUI imports only `api`/`core`).
- Every new error path asserts the actionable-error contract (what/why/action fields).

---

## 6. GUI Concept (PROPOSAL — to be replaced by the owner's vision in Phase 0)

The owner has a GUI vision not yet captured. The following is the strawman the
questions in §8 are calibrated against; Phase 4 specs are written only after this
section is ratified or rewritten.

- **Selector:** a compact configuration tab bar (or dropdown, if horizontal space
  loses) directly above the stage strip; one tab per variant plus optionally "base".
  Active tab = the whole existing workspace (parameter panel, stage views, right rail)
  shows that configuration. A "+" affordance adds/duplicates.
- **Edit scope:** default per Q-4 (owner call). The affordance is per-edit and visible
  — e.g. a small scope toggle on the editor row or a modifier action — never a hidden
  global mode. Overridden rows carry a colored chip; hovering shows every config's
  value with units (R-UNITS).
- **Comparison:** right-rail pinned cards optionally show sparklines/values across
  configs; the comparison matrix is one click (Evaluate All) from the toolbar; curve
  overlays reuse the config colors.
- **Color identity:** each configuration gets a stable color from the theme token set,
  used consistently in tabs, badges, table columns, and plot overlays (both themes).

---

## 7. Registry & Doc Lock-Step Summary (Rules 20/21/29)

| Artifact | Change | Phase |
|---|---|---|
| `docs/adr/0010-multi-configuration-model.md` | new | 0 |
| `RADIANT_Scripting_API.md` | new section: ConfigurationSet | 1 |
| `RADIANT_Config_Format.md` | new §: `configurations:` section; cross-note in §1.3–1.5 | 2 |
| `RADIANT_Parameter_System.md` | provenance `source="config:<name>"` note | 1 |
| `RADIANT_GUI_Architecture.md` | §4 layout + new views | 4 |
| `CHANGELOG.md` | public-surface entries per phase (1, 2, 4) | each |
| `docs/tracking/gaps.md` | Gap 80 re-dispositioned (band variants expressible; anything remaining — e.g. cross-band derived metrics — stays open or becomes a narrowed entry); new gap entries for §3.2 deferrals the owner wants tracked | 5 |
| This plan | Draft → Active (0), → archive (5) | 0, 5 |

---

## 8. Decision Points for the Owner (blockers before Phase 0 closes)

- **Q-1 Naming.** "Configuration" collides with "config file" everywhere in the docs.
  Proposal: the file/session object is a **study** or **configuration set**; the
  members are **configurations** (GUI label) / `ConfigVariant` (code). Alternatives
  welcome — this word will be all over the GUI.
- **Q-2 The GUI vision.** Describe it (sketch, prose, or markup): how you picture
  switching, editing per-config values, and seeing differences. §6 is disposable.
- **Q-3 Base + overrides confirmed?** The recommended model (§3.1) vs. N fully
  independent configs. Includes: is the bare base itself a runnable/comparable column,
  or only ever a template?
- **Q-4 Default edit scope in the GUI.** When you edit a parameter with a variant
  active: does it change all configurations (base) unless you say otherwise, or that
  variant only? (Recommendation: base by default — shared-first matches "variants are
  small diffs" — with a one-click per-edit override and a loud badge.)
- **Q-5 Evaluation cadence.** Active-config-only on every debounced edit (today's
  loop), with Evaluate-All on demand for comparison — or always evaluate all N?
  (Recommendation: active-only + on-demand all; N×0.22 s is fine for N≤10 but
  Evaluate-All-on-every-keystroke buys little.)
- **Q-6 Scope check on the v1 exclusions** (§3.2): per-variant tolerances, per-variant
  wavelength grid, cross-config derived metrics (band ratios, dual-band contrast),
  sweeps/MC over a whole set — confirm deferred, or pull any into v1.
- **Q-7 Per-variant optical prescriptions** (as-built element list differing from
  nominal): in v1 as specced (§3.3), or defer?
- **Q-8 Typical N** — how many configurations should the UI be comfortable at? (Tabs
  read well to ~8; beyond that the selector becomes a list.)
