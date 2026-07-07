# Doc Reconciliation Plan

**Purpose:** translate the [Doc_Drift_Report.md](Doc_Drift_Report.md) findings into a concrete sequence of doc updates and code-side cleanup tasks.

**Operating principle:** docs are authoritative for *intent*; code is authoritative for *current state*. When they disagree, decide which is right and bring the other into alignment. Don't auto-update either silently.

## Order of operations

1. **First, decide each open design question (Bucket C).** These are the only items that warrant an ADR. Until they're resolved, neither doc updates nor code changes are safe — you don't know which side to align to.
2. **Then update stale docs (Bucket A).** Mechanical: regenerate from code state, mark archive items, fix obsolete examples.
3. **Then fix code-side debts (Bucket B).** These are real CU-style backlog items — file them in [docs/tracking/Cleanup_Backlog.md](../Cleanup_Backlog.md) using the existing format.

## Bucket C — design ADRs needed

Three open questions. Each needs an explicit decision before we know how to update doc or code.

### ADR-A: FidelityPreset — keep the design or drop it?
- **Question:** is `FidelityPreset` still on the roadmap, or has the team de-scoped it in favor of always-on consistency checking and direct mode parameters?
- **Evidence for "drop":** unconditional consistency check works (CU-003 caught a real issue). Marechal vs full-OTF dispatch already exists by another mechanism. Adding a fidelity preset now would be a refactor, not a new feature.
- **Evidence for "keep":** computational cost — high-fidelity pupil grids may be expensive in trade-study sweeps. A `draft` mode could matter for `BatchRunner` performance.
- **Recommended decision:** drop unless someone has burned cycles waiting for a sweep. Update [Spatial_Complete.md](../RADIANT_Spatial_Complete.md) and [Optics.md](../RADIANT_Optics.md) to remove `FidelityPreset` references.

### ADR-B: SNR/metrics — soft-fail SNRResult or NumericalError exception?
- **Question:** should physics-correctness failures (zero noise, negative signal, NaN) raise or return a structured failure?
- **Code's choice:** `SNRResult(value=nan, failure_reason=...)` — soft fail with inspectable reason
- **Doc's choice:** `raise NumericalError(...)` — hard fail
- **Recommended decision:** keep the soft-fail pattern; it's better for sweep/Monte-Carlo workflows where individual cells failing shouldn't kill the batch. Update [Master_Architecture.md §C12 and §16](../RADIANT_Master_Architecture.md) to allow result-typed soft-fails for metric computations specifically.

### ADR-C: Public API surface — `radiant import Sensor` or qualified import?
- **Question:** do we want top-level `from radiant import Sensor`? Do `SensorConfig`/`ScenarioConfig`/`BatchRunner` exist as separate classes, or has `Sensor` absorbed their roles?
- **Evidence:** Sensor takes a YAML/dict directly via `Sensor.from_yaml()`/`from_dict()` — config-class wrappers may not be needed
- **Recommended decision:** add `Sensor` to top-level `__init__.py` (trivial). Decide whether `SensorConfig`/`ScenarioConfig` need to exist (probably not — `Sensor.from_yaml()` covers it). `BatchRunner` is mentioned in `Sensor.sweep()` — verify whether a separate class adds value.

## Bucket A — doc updates (after Bucket C resolved)

### A1. Rewrite or retire `RADIANT_Spatial_Complete.md`
- The doc describes a `spatial/` module that doesn't exist. The actual spatial architecture is distributed across `optics/`, `platform/`, `detector/`, with consistency check in `performance/`.
- Two options:
  1. **Retire and replace** with a `RADIANT_Spatial_Architecture.md` that explains the dual-path PSF/MTF design as it actually exists (consistent with CLAUDE.md Rule 4)
  2. **Heavy edit** the existing doc to remove `FidelityPreset` (per ADR-A) and `spatial/` module references, and reframe it as a guide to the dual-path discipline rather than a module spec
- **Recommended:** option 1. The current doc's structure assumes a module that isn't there.

### A2. Regenerate `RADIANT_File_Tree.md`
- Run a script to scan `src/radiant/` and produce the actual tree. Replace the doc.
- Mark `plugins/` as `[stub — see ADR on plugins scope]`.

### A3. Update `RADIANT_Signal_Chain_Architecture.md` §2 and §7
- Change `class Stage(Protocol): name: str` → `class Stage(Protocol): @property def name(self) -> str: ...`
- Update the `ChainResult` example block in §5 to match real method names (`signal_at_frame`, `metrics["snr"]`)

### A4. Sync CLAUDE.md "18 rules" → "19 rules"
- Find/replace prose references; numbered list is already correct

### A5. Mark `RADIANT_Phase{1,2,3}_*` and `*_Implementation_Prompts*` as `[archive]`
- These are historical roadmaps; current contributors should not consult them as spec
- Move to `docs/archive/` or add a top-of-file banner: "**HISTORICAL — for current architecture see RADIANT_Master_Architecture.md**"

### A6. Mark `RADIANT_Plugins.md` as `[v2 deferred]` (or implement)
- Per ADR on plugin scope

## Bucket B — code-side cleanup tasks (file in Cleanup_Backlog.md)

### CU-NEW-01: Introduce `radiant.exceptions.RadiantError` base class
- Create `src/radiant/exceptions.py` with `RadiantError(Exception)` carrying `what`, `why`, `action`, `context`
- Migrate `ParameterBoundsError`, `KirchhoffViolationError`, `ConfigError`, `ElementConfigError`, `Tape7ParseError`, `ModtranUnavailableError` to inherit from `RadiantError`
- Provide convenience constructor that builds the message from the four fields
- Estimate: Category B, ~200 LOC including migration of existing classes
- Defer mass migration of bare `ValueError` raises — do that incrementally

### CU-NEW-02: Add top-level `Sensor` re-export to `src/radiant/__init__.py`
- Trivial fix; one line; restores doc examples
- Pending ADR-C resolution

### CU-NEW-03: Rename `ChainResult.signal_at_frame` → `signal_at` (or update doc)
- Pending ADR — pick a direction; if rename, add deprecation alias for one minor version
- Update [RADIANT_Scripting_API.md](../RADIANT_Scripting_API.md) examples

### CU-NEW-04: Complete `to_provenance_record()` per C13
- Add to `ChainResult`
- Capture: run UUID, git commit (via subprocess if not available via importlib.metadata), Python version, dependency versions (importlib.metadata.requires), input file hashes (compute from any path-typed parameter), active model identifiers (atmosphere model, source resolver chosen, etc.)
- Category C — physics behavior unchanged but sweeps and Monte Carlo runs should record it
- Estimate: ~150 LOC + tests

### CU-NEW-05: Apply test markers
- Sweep `src/**/tests/` and `tests/`. Add `@pytest.mark.level0` to physics-equation tests, `level1` to module-level integration, `level2` to full-chain tests.
- Wire up CI gating per RADIANT_Testing_Validation.md §3
- Estimate: 1 day to mark; ~2 hours to wire CI
- Mechanical, low risk

## Effort summary

| Item | Bucket | Effort | Risk |
|------|--------|--------|------|
| ADR-A FidelityPreset | C | Decision only | Low |
| ADR-B Soft-fail vs raise | C | Decision only | Low |
| ADR-C Public API surface | C | Decision only | Low |
| A1 Spatial doc | A | 1 day | Low |
| A2 File_Tree regen | A | 1 hour | Low |
| A3 Signal_Chain update | A | 30 min | Low |
| A4 19 rules sync | A | 5 min | Low |
| A5 Archive Phase docs | A | 30 min | Low |
| A6 Plugins doc status | A | 5 min | Low |
| CU-NEW-01 RadiantError | B | 4–6 hours | Low |
| CU-NEW-02 Top-level export | B | 5 min | Low |
| CU-NEW-03 Rename method | B | 30 min | Low (with alias) |
| CU-NEW-04 Provenance | B | 1–2 days | Low |
| CU-NEW-05 Test markers | B | 1 day | Low |

Total: ≈ 4 person-days of doc + code cleanup, broken into independent commits. None of it is rewrite-bait.
