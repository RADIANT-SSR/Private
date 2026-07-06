# RADIANT Audit Reconciliation — Task Plan & Prompts

**Source:** [Doc_Drift_Report.md](Doc_Drift_Report.md), [Doc_Reconciliation_Plan.md](Doc_Reconciliation_Plan.md), [Recommendation.md](Recommendation.md)
**Date drafted:** 2026-04-25
**Total scope:** 3 ADR decisions + 6 doc updates + 5 code cleanups = ~4 person-days, broken into independent commits

This file contains one prompt per task. Each prompt is self-contained (an agent can pick it up cold without reading the audit). Sequencing is enforced by explicit blocking dependencies.

## Sequencing & dependency graph

```
Phase R1 — Decisions       Phase R2 — Docs              Phase R3 — Code
───────────────────────    ───────────────────────      ─────────────────────────
ADR-A FidelityPreset  ──┐
ADR-B SNR soft-fail   ──┼──► A1 Spatial doc          ┌─► CU-NEW-01 RadiantError
ADR-C Public API      ──┘    A2 File_Tree regen      ├─► CU-NEW-02 Top-level Sensor
                             A3 Signal_Chain update  ├─► CU-NEW-03 ChainResult API
                             A4 19 rules sync        ├─► CU-NEW-04 Provenance C13
                             A5 Archive Phase docs   └─► CU-NEW-05 Test markers + CI
                             A6 Plugins doc status
```

**Critical path:** ADRs unblock everything else. After ADRs land, A1–A6 (doc) and CU-NEW-01–05 (code) can proceed in parallel — no cross-task code conflicts.

**Hard rule per CLAUDE.md R20:** any task that changes a doc-bearing surface (CU-NEW-01, 02, 03, 04, 05) must update the matching `RADIANT_*.md` in the same PR.

---

# Phase R1 — Architecture Decisions (Bucket C)

These are not coding tasks; they are owner-level scope decisions. Each decision should be recorded as a brief ADR (`docs/adr/ADR-NNN-<slug>.md`) and committed before downstream work begins.

## R1.1 — ADR-A: FidelityPreset — Keep or Drop?

**Audit reference:** [Doc_Drift_Report.md#D2](Doc_Drift_Report.md), [Doc_Reconciliation_Plan.md#ADR-A](Doc_Reconciliation_Plan.md)

**Question:** Is `FidelityPreset` (the `draft` / `standard` / `high` enum gating consistency check, pupil grid size, and Marechal vs full-OTF dispatch) still on the roadmap, or has the team de-scoped it in favor of (a) always-on consistency checking and (b) direct-mode parameters?

**Owner prompt (for the human deciding):**

> RADIANT_Spatial_Complete.md and RADIANT_Optics.md describe a `FidelityPreset` system. The audit found:
> - No `FidelityPreset` class anywhere in `src/`.
> - The dual-path consistency check (`performance/consistency_check.py`) runs unconditionally with hardcoded `tolerance = 5e-2`. It is catching real issues (CU-003).
> - Marechal vs full-OTF selection is via a different mechanism (mode dispatch in `optics/`).
> - Pupil grid size is currently a fixed parameter, not gated by fidelity.
>
> Decide: keep on roadmap, or drop?
>
> **Drop signals:** the unconditional check works. Adding `FidelityPreset` now would be a refactor, not a new feature. Sweep performance is currently acceptable.
> **Keep signals:** future high-fidelity pupil grids may be expensive. A `draft` mode could matter for `BatchRunner` performance on large parameter sweeps.
>
> If drop: mark `FidelityPreset` references in [RADIANT_Spatial_Complete.md](../RADIANT_Spatial_Complete.md) and [RADIANT_Optics.md](../RADIANT_Optics.md) for removal in task A1.
> If keep: file a Category B implementation task and update the docs to describe what the preset will gate (consistency check on/off, pupil grid size, Marechal vs full-OTF).

**Deliverable:** `docs/adr/ADR-A-fidelity-preset.md` recording the decision, the rationale, and the doc/code follow-on tasks.

## R1.2 — ADR-B: SNR/metrics — Soft-fail SNRResult or NumericalError?

**Audit reference:** [Doc_Drift_Report.md#D4](Doc_Drift_Report.md), [phase3_pipeline_traces.md](findings/phase3_pipeline_traces.md), [Doc_Reconciliation_Plan.md#ADR-B](Doc_Reconciliation_Plan.md)

**Question:** Should physics-correctness failures in the metrics layer (zero noise, negative signal, NaN inputs) **raise** `NumericalError` (per CLAUDE.md §16/§17) or **return** a structured `SNRResult(value=nan, failure_reason=...)` (the current code pattern in `performance/snr.py`)?

**Owner prompt:**

> CLAUDE.md §16/§17 promise that no NaN or inf returns silently — `NumericalError` is raised. The code in `performance/snr.py` returns `SNRResult(value=nan, failure_reason=str)` instead. The `failure_reason` field is structured and inspectable.
>
> Decide:
> - **Soft-fail (current code wins):** keep `SNRResult.failure_reason`, codify in CLAUDE.md §17 that *metric-layer* computations may return result-typed failures with explicit reason fields, while physics-layer functions still raise. Update [RADIANT_Master_Architecture.md §C12 and §16](../RADIANT_Master_Architecture.md) and [RADIANT_Testing_Validation.md](../RADIANT_Testing_Validation.md) accordingly.
> - **Hard-fail (current docs win):** file a Category B task that converts `compute_snr` (and `compute_nedt`, `compute_niirs` if symmetric) to raise `NumericalError`. Update callers (sweep harnesses, BatchRunner) to catch and record the failure per cell.
>
> **Recommended:** soft-fail. It is better for sweep / Monte-Carlo workflows where individual cells failing should not abort the batch. The `failure_reason` field already gives callers everything they would inspect from an exception.

**Deliverable:** `docs/adr/ADR-B-metric-soft-fail.md` recording the decision.

## R1.3 — ADR-C: Public API surface — top-level imports and config classes

**Audit reference:** [Doc_Drift_Report.md#D5, #D8](Doc_Drift_Report.md), [Doc_Reconciliation_Plan.md#ADR-C](Doc_Reconciliation_Plan.md)

**Three sub-questions:**

1. Top-level `from radiant import Sensor` — wanted? (Yes is trivial: one line in `__init__.py`.)
2. `SensorConfig` / `ScenarioConfig` classes — needed, or has `Sensor.from_yaml()` / `from_dict()` absorbed their roles?
3. `BatchRunner` — separate class, or a method on `Sensor` (`Sensor.sweep()`)?

**Owner prompt:**

> RADIANT_Scripting_API.md examples use `from radiant import Sensor` and `from radiant.api import SensorConfig, ScenarioConfig, BatchRunner`. The audit found:
> - `radiant/__init__.py` exports only `__version__`. `Sensor` is reachable via `from radiant.api import Sensor` only.
> - No `SensorConfig`, `ScenarioConfig`, or `BatchRunner` classes exist anywhere.
> - `Sensor.from_yaml()` / `Sensor.from_dict()` already accept the config formats those classes would have wrapped.
> - `Sensor.sweep()` exists and references "BatchRunner" semantically but is not a separate class.
>
> Decide each question. The recommended path:
> 1. **Yes** — add `Sensor` to top-level `__init__.py` (CU-NEW-02).
> 2. **No** — `SensorConfig`/`ScenarioConfig` are unnecessary if `Sensor.from_yaml()` covers it. Update doc to remove them.
> 3. **No separate class** — keep `Sensor.sweep()` as the entry point. If batch features grow (parallel execution, progress reporting), revisit then.
>
> Either accept the recommendation, or specify what the additional classes would do that `Sensor` does not.

**Deliverable:** `docs/adr/ADR-C-public-api-surface.md` recording the three decisions.

---

# Phase R2 — Doc Updates (Bucket A)

These are mechanical doc fixes. Each can be done independently after the ADRs land. Estimated effort per item is in the audit.

## R2.A1 — Rewrite `RADIANT_Spatial_Complete.md`

**Category:** A
**Effort:** 1 day
**Audit reference:** [Doc_Drift_Report.md#D1, #D2](Doc_Drift_Report.md), [Doc_Reconciliation_Plan.md#A1](Doc_Reconciliation_Plan.md)
**Blocked by:** ADR-A

**Read first:**
- [docs/RADIANT_Spatial_Complete.md](../RADIANT_Spatial_Complete.md)
- [docs/RADIANT_Optics.md](../RADIANT_Optics.md)
- [docs/RADIANT_Master_Architecture.md](../RADIANT_Master_Architecture.md) §4
- [src/radiant/optics/](../../src/radiant/optics/) (skim — esp. `psf/effective.py`, `pupil_mtf.py`)
- [src/radiant/performance/consistency_check.py](../../src/radiant/performance/consistency_check.py)

**Task prompt:**

> The current `RADIANT_Spatial_Complete.md` describes a `spatial/` subpackage that does not exist. The actual spatial architecture is distributed across `optics/`, `platform/`, `detector/`, with the dual-path consistency check in `performance/consistency_check.py`.
>
> Retire the existing file (rename to `docs/archive/RADIANT_Spatial_Complete_v1.md`, or move under `docs/archive/`) and create a new `docs/RADIANT_Spatial_Architecture.md` that:
> 1. States that spatial responsibilities are *distributed*, not centralized in a `spatial/` module
> 2. Documents the dual-path discipline (PSF path / MTF product path) consistent with CLAUDE.md Rule 4
> 3. Names which stage owns each spatial concern (sampling — optics; jitter MTF — platform; detector aperture/IPC — detector; system MTF / RER — performance)
> 4. Documents the consistency invariant (`performance/consistency_check.py`, tolerance 5e-2, runs unconditionally)
> 5. Per ADR-A: removes `FidelityPreset` references entirely (if dropped) or describes what it actually gates (if kept)
>
> **Deliverable:** `docs/RADIANT_Spatial_Architecture.md` (new), `docs/archive/RADIANT_Spatial_Complete_v1.md` (moved with banner: "ARCHIVED — see `RADIANT_Spatial_Architecture.md`").
>
> **Completion criteria:** every code reference in the new doc points to an actual file at an actual line. No `spatial/` directory references remain. CLAUDE.md Rule 4 verbatim quote must align with the new doc's prose.

## R2.A2 — Regenerate `RADIANT_File_Tree.md`

**Category:** A
**Effort:** 1 hour
**Audit reference:** [Doc_Drift_Report.md#D6](Doc_Drift_Report.md)

**Task prompt:**

> The current `RADIANT_File_Tree.md` lists `source/blackbody.py`, `source/solar.py`, `source/reflected.py` as Stage 1 files. Reality:
> - Planck and solar live in `core/` (`core/blackbody.py`, `core/solar.py`)
> - The `source/` tree restructured significantly (`_inferrer.py`, `resolvers/`, `converters/`, `shapes/`, `composite.py`, `combined.py`, `material.py`, `point_source_*.py`, `sub_pixel.py`, `tabulated.py` are present and not described)
>
> Regenerate the file tree from `src/radiant/` with one-line annotations per file. Mark `plugins/` as `[v2 deferred]` per ADR result on R2.A6. Mark stub directories explicitly.
>
> **Deliverable:** updated `docs/RADIANT_File_Tree.md` matching `find src/radiant/ -name '*.py'` output.
>
> **Completion criteria:** every file listed in the doc exists; every `.py` file in `src/radiant/` is described.

## R2.A3 — Update `RADIANT_Signal_Chain_Architecture.md`

**Category:** A
**Effort:** 30 min
**Audit reference:** [Doc_Drift_Report.md#D7, #D8](Doc_Drift_Report.md)
**Blocked by:** CU-NEW-03 decision (rename method or update doc)

**Task prompt:**

> Two specific corrections:
>
> 1. **§2 and §7 Stage protocol snippet:** change
>    ```python
>    class Stage(Protocol):
>        name: str
>    ```
>    to
>    ```python
>    class Stage(Protocol):
>        @property
>        def name(self) -> str: ...
>    ```
>    Match [src/radiant/core/chain.py:38-43](../../src/radiant/core/chain.py#L38-L43).
>
> 2. **§5 ChainResult example:** update method names to match `io/results.py`. After CU-NEW-03 decides direction:
>    - If method renamed (`signal_at_frame` → `signal_at`), update doc to use `signal_at`
>    - If doc updated to match code, change to `signal_at_frame`, `noise_at_frame`, and `result.metrics["snr"]` (dict access) instead of `result.snr()`
>
> **Deliverable:** updated `docs/RADIANT_Signal_Chain_Architecture.md`.

## R2.A4 — Sync CLAUDE.md "18 rules" → "22 rules"

**Category:** A
**Effort:** 5 min
**Audit reference:** [Doc_Drift_Report.md#D11](Doc_Drift_Report.md) — note: count is now 22 after R20–R22 were added

**Task prompt:**

> CLAUDE.md was updated 2026-04-25 to add R20 (Doc-and-Code Lock-Step), R21 (Every Finding Becomes a Tracked CU), R22 (CU Closure Is Commit-Linked). Confirm any prose references to "the 18 rules" or "all 18 rules above" in the file are updated to "22 rules". Self-Review section already updated.
>
> **Deliverable:** grep for "18 rules" and "19 rules" returns zero hits in CLAUDE.md.

## R2.A5 — Archive Phase{1,2,3} and `Implementation_Prompts*` docs

**Category:** A
**Effort:** 30 min
**Audit reference:** [Doc_Drift_Report.md#D13](Doc_Drift_Report.md)

**Task prompt:**

> Several roadmap and historical docs in `docs/` are no longer authoritative:
> - `RADIANT_Phase1_Plan.md`, `RADIANT_Phase2_Implementation_Prompts_*.md`, `RADIANT_Phase3_Implementation_Prompts.md`
> - `Option_C_Implementation_Plan.md` (if landed)
> - `Cleanup_Backlog_Phase2_Plan.md` (if completed)
>
> For each, choose one of:
> 1. Move to `docs/archive/` (preferred for completed roadmaps)
> 2. Add a top-of-file banner: `**HISTORICAL — for current architecture see RADIANT_Master_Architecture.md**`
>
> Cross-check against the supersession table in `RADIANT_Master_Architecture.md` — if a doc is listed as superseded there, archive it.
>
> **Deliverable:** every historical doc either lives under `docs/archive/` or carries the `[archive]` banner. New contributors can tell which docs are authoritative on first scan.

## R2.A6 — Mark `RADIANT_Plugins.md` per ADR

**Category:** A
**Effort:** 5 min
**Audit reference:** [Doc_Drift_Report.md#D12](Doc_Drift_Report.md)
**Blocked by:** plugin scope ADR (informal — file inline if not already decided)

**Task prompt:**

> `RADIANT_Plugins.md` describes `SourcePlugin` / `AtmospherePlugin` / `MetricPlugin` ABCs. `src/radiant/plugins/` is a 1-LOC stub.
>
> Decide and apply:
> - If plugins are deferred to v2: add top-of-file banner `**v2 DEFERRED — implementation tracked as future scope**` and remove the `RADIANT_Plugins.md` doc from the `Read first` lists in any task that doesn't actually need it.
> - If plugins are in scope now: file a Category D task to implement the ABCs. Update [Master_Architecture.md §4](../RADIANT_Master_Architecture.md) accordingly.
>
> **Deliverable:** doc reflects actual code state.

---

# Phase R3 — Code Cleanups (CU-NEW-01 through CU-NEW-05)

After this section, append each entry to [docs/Cleanup_Backlog.md](../Cleanup_Backlog.md) per R21 with the next available CU number.

## R3.CU-NEW-01 — Introduce `radiant.exceptions.RadiantError` base class

**Category:** B
**Effort:** 4–6 hours, ~200 LOC
**Audit reference:** [Doc_Drift_Report.md#D3](Doc_Drift_Report.md), [phase2_rule_conformance.md §R15](findings/phase2_rule_conformance.md), [Doc_Reconciliation_Plan.md#CU-NEW-01](Doc_Reconciliation_Plan.md)

**Read first:**
- [CLAUDE.md §15](../../CLAUDE.md) (actionable errors)
- [docs/RADIANT_Master_Architecture.md](../RADIANT_Master_Architecture.md) §C12, §7.4
- [src/radiant/core/parameters.py](../../src/radiant/core/parameters.py) — see `ParameterBoundsError`
- [src/radiant/optics/element.py](../../src/radiant/optics/element.py) — see `KirchhoffViolationError`
- [src/radiant/io/config.py](../../src/radiant/io/config.py) — see `ConfigError`
- [src/radiant/io/element_config.py](../../src/radiant/io/element_config.py) — see `ElementConfigError`
- [src/radiant/atmosphere/modtran.py](../../src/radiant/atmosphere/modtran.py) — see `Tape7ParseError`, `ModtranUnavailableError`

**Task prompt:**

> CLAUDE.md §15 promises a `RadiantError(Exception)` base class with `what` / `why` / `action` / `context` fields. No such class exists. Custom errors currently subclass stdlib exceptions directly.
>
> 1. Create `src/radiant/exceptions.py` with:
>    - `class RadiantError(Exception)` carrying `what: str`, `why: str`, `action: str`, `context: dict[str, Any]`
>    - `__init__` accepting the four fields, building the formatted message from them, and storing each as an attribute for programmatic inspection
>    - `__str__` produces a multi-line actionable error message
>
> 2. Migrate the existing custom error classes to inherit from `RadiantError`:
>    - `ParameterBoundsError` (currently subclasses `ValueError`)
>    - `KirchhoffViolationError` (currently `ValueError`)
>    - `ConfigError` (currently `Exception`)
>    - `ElementConfigError` (currently `ValueError`)
>    - `Tape7ParseError` (currently `ValueError`)
>    - `ModtranUnavailableError` (currently `RuntimeError`)
>
> 3. **Do NOT** mass-migrate the 404 bare `raise ValueError/TypeError/RuntimeError` calls in this PR. Those are out of scope. Filing CU-NEW-06 for incremental migration is acceptable.
>
> 4. Per R20: update CLAUDE.md §15 example (it already shows `ParameterBoundsError`), [RADIANT_Master_Architecture.md §C12, §7.4](../RADIANT_Master_Architecture.md), and [RADIANT_Testing_Validation.md](../RADIANT_Testing_Validation.md) to reference `radiant.exceptions.RadiantError` as the actual base.
>
> 5. Tests:
>    - Level 0: `RadiantError(what=..., why=..., action=..., context=...)` produces an inspectable instance with all fields preserved
>    - Level 0: each migrated subclass remains catchable as both `RadiantError` AND its prior parent (where prior parent was a stdlib base — keep multi-inheritance if needed for backward compat with existing test code)
>    - Level 1: `pytest.raises(RadiantError) as exc; exc.value.context["param"] == ...` works on a real call site
>
> **Completion criteria:** `mypy --strict` passes; `import-linter` passes; existing test suite still green; new tests pass; CLAUDE.md §15 / Master_Architecture §C12 / Testing_Validation references updated.
>
> **Deliverables:** new file, migrated error classes, doc updates, tests.

## R3.CU-NEW-02 — Add top-level `Sensor` re-export

**Category:** A
**Effort:** 5 min + a test
**Audit reference:** [Doc_Drift_Report.md#D5](Doc_Drift_Report.md), [Doc_Reconciliation_Plan.md#CU-NEW-02](Doc_Reconciliation_Plan.md)
**Blocked by:** ADR-C

**Task prompt:**

> Per ADR-C decision: `from radiant import Sensor` should work.
>
> 1. Update [src/radiant/__init__.py](../../src/radiant/__init__.py):
>    ```python
>    from radiant.api.sensor import Sensor
>    __all__ = ["Sensor", "__version__"]
>    ```
>
> 2. Per R20: confirm [RADIANT_Scripting_API.md](../RADIANT_Scripting_API.md) examples that say `from radiant import Sensor` now match reality.
>
> 3. Test: add `tests/test_public_api.py::test_top_level_sensor_import` that imports `from radiant import Sensor`, instantiates it from a minimal YAML, and runs one frame.
>
> **Completion criteria:** doc example runs verbatim from a Python REPL.

## R3.CU-NEW-03 — Reconcile `ChainResult` API method names

**Category:** A (with deprecation alias) or A→B (if rename without alias)
**Effort:** 30 min
**Audit reference:** [Doc_Drift_Report.md#D8](Doc_Drift_Report.md), [Doc_Reconciliation_Plan.md#CU-NEW-03](Doc_Reconciliation_Plan.md)

**Task prompt:**

> Doc says `result.signal_at(frame)`, `result.noise_at(frame)`, `result.snr()`, `result.nedt()`, `result.niirs()`. Code provides `result.signal_at_frame()`, `result.noise_at_frame()`, and metrics as `result.metrics["snr"]` (dict, not method).
>
> Pick one direction:
>
> **Direction 1 — rename methods to match doc:**
>    - Rename `signal_at_frame` → `signal_at`, `noise_at_frame` → `noise_at` in `io/results.py`
>    - Add deprecation aliases (`signal_at_frame = signal_at  # deprecated`) for one minor version, with `DeprecationWarning`
>    - Add convenience methods `result.snr()`, `result.nedt()`, `result.niirs()` that read from `metrics`
>    - Update tests to use new names
>
> **Direction 2 — update doc to match code:**
>    - In [RADIANT_Scripting_API.md](../RADIANT_Scripting_API.md), update every example: `signal_at` → `signal_at_frame`, `result.snr()` → `result.metrics["snr"]`, etc.
>
> **Recommended:** Direction 1. Method names read better than dict access; rename is cheap and only affects one module's public surface.
>
> **Completion criteria:** every example in `RADIANT_Scripting_API.md` runs verbatim. R20 satisfied (code+doc in same PR). If Direction 1 chosen, deprecation warning fires when the old names are used and is silenced after one minor version per a TODO with date.

## R3.CU-NEW-04 — Complete `ChainResult.to_provenance_record()` per C13

**Category:** C
**Effort:** 1–2 days, ~150 LOC + tests
**Audit reference:** [Doc_Drift_Report.md#D9](Doc_Drift_Report.md), [phase3_pipeline_traces.md §Provenance status](findings/phase3_pipeline_traces.md), [Doc_Reconciliation_Plan.md#CU-NEW-04](Doc_Reconciliation_Plan.md)

**Read first:**
- [docs/RADIANT_Master_Architecture.md](../RADIANT_Master_Architecture.md) §C13
- [src/radiant/core/parameters.py:566](../../src/radiant/core/parameters.py#L566) — current partial provenance
- [src/radiant/io/results.py](../../src/radiant/io/results.py) — `ChainResult`
- [src/radiant/api/session.py](../../src/radiant/api/session.py) — where ChainResult is constructed

**Task prompt:**

> CLAUDE.md / Master_Architecture C13 promises every `ChainResult` carries: run UUID, RADIANT version, git commit, Python version, dependency versions, resolved parameter set with per-parameter provenance, input file hashes, active model identifiers.
>
> Currently `ParameterSet.to_provenance_record(radiant_version)` returns only `radiant_version`, `resolved_at`, and resolved parameters. There is no `ChainResult.to_provenance_record()`.
>
> 1. Add `ChainResult.to_provenance_record()` that returns a dict with:
>    - `run_id`: a UUID4 generated at chain start (carry through `ChainState`)
>    - `radiant_version`: from `importlib.metadata.version("radiant")`
>    - `git_commit`: from `subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True)` if the source is a git checkout, else `None`
>    - `python_version`: `sys.version`
>    - `dependency_versions`: from `importlib.metadata.requires("radiant")` resolved to actual installed versions
>    - `parameter_set`: forward of `ParameterSet.to_provenance_record()`
>    - `input_file_hashes`: SHA256 of every path-typed parameter the run consumed (walk `params._resolved` for path-typed values)
>    - `active_models`: dict naming the atmosphere backend, source resolver(s), and any other plugin-selected model
>
> 2. Wire `run_id` through `ChainRunner.run()` so the same UUID flows from start to result.
>
> 3. Tests:
>    - Level 0: each field is present and non-None when the run succeeds in a git checkout
>    - Level 0: `git_commit` is `None` (not crashing) outside a git repo
>    - Level 1: round-trip — run twice with same inputs, verify `run_id` differs but `git_commit` / `python_version` / `dependency_versions` / `input_file_hashes` are stable
>    - Level 1: `dependency_versions` includes `numpy`, `scipy`, and any other installed dep listed in `pyproject.toml`
>
> 4. Per R20: confirm [Master_Architecture.md §C13](../RADIANT_Master_Architecture.md) is consistent with the implementation. If C13 had aspirational fields not implemented, either implement them or update the doc explicitly.
>
> **Category C requirements (per CLAUDE.md):**
> - Dimensional audit: N/A (no physics)
> - Failure modes: outside git repo, no installed package metadata, missing input file
> - Numerical truth anchors: not applicable to provenance — explicitly note "no truth anchors required; this is a metadata-capture task"
> - Assumptions: explicit list (e.g., "git checkout assumption", "importlib.metadata available in Python ≥ 3.8")
> - Fragility: subprocess to `git` may fail; importlib.metadata may miss optional deps; large files may cause hashing latency
>
> **Completion criteria:** every C13 field present in the returned dict; tests cover the failure modes; doc and code agree.

## R3.CU-NEW-05 — Apply test markers + wire CI gating

**Category:** A
**Effort:** 1 day to mark + ~2 hours to wire CI
**Audit reference:** [Doc_Drift_Report.md#D10](Doc_Drift_Report.md), [phase1_mechanical.md §Test marker distribution](findings/phase1_mechanical.md), [Doc_Reconciliation_Plan.md#CU-NEW-05](Doc_Reconciliation_Plan.md)

**Read first:**
- [docs/RADIANT_Testing_Validation.md](../RADIANT_Testing_Validation.md) §3 (Level hierarchy)
- [docs/RADIANT_Master_Architecture.md](../RADIANT_Master_Architecture.md) §C15 (CI gating)
- [pyproject.toml](../../pyproject.toml) — current pytest marker registration

**Task prompt:**

> RADIANT_Testing_Validation.md §3 describes Level 0 (key-equation), Level 1 (module integration), Level 2 (full chain) markers with CI gating ("Level 0 failure blocks Level 1"). Currently 287 tests are level0-marked, 6 level1, 0 level2, ~2,058 unmarked.
>
> 1. Sweep `src/**/tests/` and `tests/` and apply markers per the doc:
>    - `@pytest.mark.level0` — tests that verify a single key equation against a known-good analytic value, no chain dependencies
>    - `@pytest.mark.level1` — module-level integration (e.g., a full `OpticsStage.run()` against synthetic inputs)
>    - `@pytest.mark.level2` — `tests/integration/` full-chain tests (`test_full_system.py`, `test_chain_extended.py`, `test_chain_spatial.py`, `test_dual_path_mtf.py`, `test_ground_truth_mwir.py`, `test_mwir_leo_minimal.py`, `test_no_atm_subcases.py`, `test_regime_continuity.py`)
>    - `@pytest.mark.golden` — anything that reads from / writes to `tests/integration/snapshots/`
>
> 2. Update `pyproject.toml` `[tool.pytest.ini_options]` to register all four markers explicitly.
>
> 3. Wire the CI gating per Testing_Validation.md §3:
>    - Add a `Makefile` target or `tox` env: `test-level0` runs only `-m level0`, `test-level1` runs only `-m level1`, `test-level2` runs only `-m level2`
>    - In CI workflow (`.github/workflows/*.yml` if present, else file a follow-on for ops): jobs run sequentially. Level 1 starts only if Level 0 passed. Level 2 starts only if Level 1 passed.
>
> 4. Per R20: if Testing_Validation.md described a marker that doesn't exist (or vice versa), reconcile.
>
> **Completion criteria:**
> - `pytest --collect-only -m level0` collects ~all key-equation tests (well above current 287)
> - `pytest --collect-only -m "not (level0 or level1 or level2 or golden)"` returns 0 unmarked tests (every test categorized)
> - CI gating actually skips downstream levels on upstream failure (verify by introducing a Level 0 fail in a branch and confirming Level 1 doesn't run)

---

# Phase R4 — Process and culture follow-ups

These are not code changes; they are habits the new R20–R22 rules formalize. Filed here so they don't get lost.

## R4.1 — Backfill the existing CU backlog to R21/R22 format

**Category:** A
**Effort:** 30 min

**Task prompt:**

> The 8 open CUs in [docs/Cleanup_Backlog.md](../Cleanup_Backlog.md) are already well-formatted. Verify each carries:
> - Discovery context (date + originating task or commit)
> - File path
> - Symptom (reproducer)
> - Why it still matters
> - Suggested fix with effort estimate and category
> - For stage-deferred entries: gating stage(s), re-audit date
>
> The 7 resolved CUs (CU-001/002/004/006/010/014/015) should each carry: resolution date, linked commit SHA, one-line summary. Spot-check; backfill any missing.
>
> **Completion criteria:** all 15 entries pass the R21/R22 format check.

## R4.2 — Make R20 enforceable in PR review

**Effort:** 1 hour (process, not code)

**Task prompt:**

> R20 says "any change that modifies a public API name, parameter schema, error class, stage protocol, ChainState field, public method on Sensor/ChainResult/SweepResult, or an architectural rule MUST update the corresponding RADIANT_*.md doc(s) in the same PR."
>
> Add a PR template checklist at `.github/PULL_REQUEST_TEMPLATE.md` (or update existing):
> - [ ] R20 — does this PR change a documented surface? If yes, which `RADIANT_*.md` is updated in this PR?
> - [ ] R21 — did I uncover any latent issue? If yes, link the new CU entry.
> - [ ] R22 — if I closed a CU, the Resolved entry has linked commit SHA + date.
>
> **Completion criteria:** the template ships in the next PR; reviewers visibly use it.

---

# Effort summary (full reconciliation)

| Item | Phase | Effort | Risk | Blocked by |
|------|-------|--------|------|------------|
| ADR-A FidelityPreset | R1 | Decision only | Low | — |
| ADR-B Soft-fail vs raise | R1 | Decision only | Low | — |
| ADR-C Public API surface | R1 | Decision only | Low | — |
| A1 Spatial doc rewrite | R2 | 1 day | Low | ADR-A |
| A2 File_Tree regen | R2 | 1 hour | Low | A6 |
| A3 Signal_Chain update | R2 | 30 min | Low | CU-NEW-03 |
| A4 22-rules sync | R2 | 5 min | Low | — |
| A5 Archive Phase docs | R2 | 30 min | Low | — |
| A6 Plugins doc status | R2 | 5 min | Low | plugin ADR |
| CU-NEW-01 RadiantError | R3 | 4–6 hours | Low | — |
| CU-NEW-02 Top-level export | R3 | 5 min | Low | ADR-C |
| CU-NEW-03 ChainResult names | R3 | 30 min | Low (with alias) | — |
| CU-NEW-04 Provenance C13 | R3 | 1–2 days | Low | — |
| CU-NEW-05 Test markers + CI | R3 | 1 day | Low | — |
| R4.1 Backlog format backfill | R4 | 30 min | None | — |
| R4.2 PR template | R4 | 1 hour | None | — |

**Total: ≈ 4 person-days** of doc + code cleanup, broken into independent commits. None of it is rewrite-bait. R20–R22 are now enforceable per CLAUDE.md and the PR template.

# Suggested execution order

1. **Day 1 morning** — owner makes ADR-A, ADR-B, ADR-C decisions (~2 hours of focused thinking). Commit each ADR.
2. **Day 1 afternoon** — A4 + A5 + A6 + R4.1 + R4.2 (mechanical, fast). One PR per item or batched.
3. **Day 2** — A1 Spatial doc rewrite (full day; the only doc task with real depth).
4. **Day 2 in parallel** — CU-NEW-02, CU-NEW-03 (if a second contributor is available).
5. **Day 3** — CU-NEW-01 (RadiantError + migration).
6. **Day 3** — A2 File_Tree regen + A3 Signal_Chain update (after CU-NEW-03 lands).
7. **Day 4** — CU-NEW-05 test markers + CI gating.
8. **Day 5–6** — CU-NEW-04 Provenance C13 (Category C; needs the full validation report).

By the end of week 2 the audit findings are fully reconciled, every doc and code surface agrees, and the new R20/R21/R22 rules are enforced in PR review. The existing 8-item CU backlog continues on its current cadence in parallel.
