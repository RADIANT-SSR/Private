# Phase 1 — Mechanical Health Metrics

**Question this phase answers:** What does an objective, scriptable health check show?

## Summary verdict
**Strong mechanical health.** No CI gates broken. The codebase enforces its own architectural rules through tooling that is currently green.

## Top-line metrics

| Metric | Value | Verdict |
|--------|-------|---------|
| Production Python files (non-test) | ~217 | Reasonable for 8-stage scope |
| Test files | 127 | High |
| Total test functions | 2,352 | Strong |
| Tests collected by pytest | 2,741 | (includes parametrized) |
| Test pass rate (excluding optics) | 2280/2280 = 100% | Green |
| Total production LOC | ~35,000 | Moderate |
| Total commits on `main` | 70 | Young codebase |

## Tooling status (all CI gates)

| Gate | Status | Notes |
|------|--------|-------|
| `import-linter` (5 contracts) | ✅ all 5 KEPT | core, physics-only-core, no-cross-stage, cli-via-api, plugins-only-core |
| `mypy --strict` (core, api) | ✅ green | 51 source files, 0 issues |
| `ruff check src/` | ✅ green | All checks passed |
| `pytest` (non-optics) | ✅ 2280/2280 | 138 sec runtime; 54 known UserWarnings |

This is the single most important finding of the audit. Every architectural rule that has automated enforcement is currently green.

## Per-stage size and test ratio

| Stage | Prod LOC | Test LOC | Prod files | Test files | Test/prod LOC |
|-------|----------|----------|------------|------------|---------------|
| core | 4,777 | 4,549 | 17 | 15 | 0.95 |
| source | 7,412 | 7,553 | 45 | 27 | 1.02 |
| atmosphere | 5,910 | 4,984 | 12 | 11 | 0.84 |
| optics | 6,015 | 6,273 | 32 | 19 | 1.04 |
| platform | 968 | 1,339 | 7 | 6 | 1.38 |
| spectral_integration | 400 | 110 | 3 | 1 | **0.28** |
| detector | 1,882 | 1,514 | 16 | 9 | 0.80 |
| readout | 1,168 | 968 | 11 | 8 | 0.83 |
| performance | 2,912 | 2,802 | 29 | 16 | 0.96 |
| io | 576 | 560 | 4 | 3 | 0.97 |
| api | 1,750 | 1,078 | 10 | 7 | 0.62 |
| cli | 1,024 | 478 | 12 | 1 | **0.47** |
| plugins | 1 | 0 | 1 | 0 | — |

**Concerns:**
- `spectral_integration` test ratio = 0.28 — the *single* most important stage (Rule 8: spectral integration happens exactly once; Rule 9: EE_box applied here only) has only one test file. This is undertested for what it owns.
- `cli` test ratio = 0.47, and 12 prod files vs 1 test file. CLI shape testing is light.
- `plugins` is essentially empty (1 LOC). The architecture promises plugin ABCs in [docs/architecture/RADIANT_Plugins.md](../../RADIANT_Plugins.md); the implementation is a stub.

## Largest files (god-module candidates)

Threshold from CLAUDE.md context: 1000+ LOC is the watch line.

| File | LOC | Comment |
|------|-----|---------|
| `source/_inferrer.py` | **2,040** | Far above threshold. Inferrer translates user inputs into descriptors — long but linear; single file because routing logic is deeply intertwined |
| `atmosphere/assembly.py` | **1,166** | Above threshold. Assembles atmospheric quantities across regimes |
| `atmosphere/simple.py` | 998 | At threshold |
| `core/descriptors.py` | 964 | Definitions live together — multi-class file |
| `optics/stage.py` | 897 | Longest stage.py — does heavy lifting (PSF, MTF, regime, EE_box, throughput, warm optics) |
| `atmosphere/modtran.py` | 857 | MODTRAN reader — file format complexity |

`source/_inferrer.py` at 2,040 LOC is the standout. Phase 2/5 should determine whether this is justifiable cohesion (one large state machine) or accumulated routing.

## Rule-aligned grep counts (sanity scan)

| Rule | Predicate | Count | Notes |
|------|-----------|-------|-------|
| R6 (no file I/O in stages) | `open(`, `with open` in physics modules | **0** | Clean |
| R7 (no direct ChainState mutation) | `state.frames[...]=`, `state.mtf_terms[...]=` | **0** | Clean |
| R11 (no cross-stage imports) | import-linter | **0 violations** | Clean |
| R13 (no magic constants) | `6.626e-34`, `2.998e8`, `1.381e-23` outside constants.py | **0** | Clean |
| R14 (no print) | `print(` in lib code | 1 (in docstring example) | Effectively clean |
| R17 (no silent failures) | `except Exception:` in non-test | **0** | Clean |
| R17 (warning suppression) | `simplefilter("ignore"` | 1 | Known: CU-007 |
| Stage protocol | `def run(self, state, params) -> ChainState` per stage | 8/8 | All 8 stages conform |
| Stage `name` property | `@property def name` per stage | 8/8 | All conform (doc says class attr; code uses property — minor drift) |

## Rule-aligned sanity counts that need Phase 2 inspection

| Rule | Predicate | Count | To investigate |
|------|-----------|-------|----------------|
| R2 | `* 1e-6` in physics modules | 18 | Most look like µm→m for Planck/SI calcs (canonical-unit prep, not boundary conversion). Verify. |
| R12 | `params.get(...)` in physics modules | 173 | Cross-check vs 129 ParameterDef registrations |
| R15 | `raise ValueError/TypeError/RuntimeError` in non-test | 404 | Many will be `ParameterBoundsError` subclass calls. Ratio of bare-vs-actionable matters. |
| R15 | `assert` in physics modules | 27 | Spot check shows all are `# constructor invariant` style — legitimate per CLAUDE.md |
| R19 | Files >800 LOC | 6 | Already itemized above |

## Test marker distribution

| Marker | Count |
|--------|-------|
| `@pytest.mark.level0` | 287 |
| `@pytest.mark.level1` | 6 |
| `@pytest.mark.level2` | 0 |
| `@pytest.mark.golden` | 1 |
| Unmarked test functions | ~2,058 |

CLAUDE.md and RADIANT_Testing_Validation.md describe a Level 0/1/2 hierarchy with CI gating. The marker system exists but is sparsely applied — most tests are unmarked. The CI gating mechanism described in C15 ("Level 0 failure blocks Level 1") cannot be enforced if level1/level2 markers aren't on the bulk of tests. **This is a real gap** but it doesn't suggest rewrite — the tests exist and pass; only the categorization is incomplete.

## Custom error hierarchy

| Class | Base | Location |
|-------|------|----------|
| `ParameterBoundsError` | `ValueError` | core/parameters.py |
| `KirchhoffViolationError` | `ValueError` | optics/element.py |
| `ConfigError` | `Exception` | io/config.py |
| `ElementConfigError` | `ValueError` | io/element_config.py |
| `ModtranUnavailableError` | `RuntimeError` | atmosphere/modtran.py |
| `Tape7ParseError` | `ValueError` | atmosphere/modtran.py |

CLAUDE.md §15 describes `RadiantError` with `what`/`why`/`action`/`context` fields. **No `RadiantError` base class exists in the codebase.** Errors subclass standard exceptions instead. The actionable-error pattern is implemented bottom-up via `ParameterBoundsError`'s constructor (need to inspect) but the unified base is missing. Doc-vs-code drift, Bucket A or B (Phase 4 to determine).

## Provenance

| Question | Status |
|----------|--------|
| Does `ChainResult` carry provenance? | To verify in Phase 3 — C13 says mandatory |
| Is provenance disabled-able? | Should not be |

## Phase 1 verdict signals

**Pro-continuation:**
- All 5 import contracts green
- mypy/ruff/pytest all green
- 0 file I/O in stages, 0 direct state mutations, 0 magic constants, 0 print() in lib code, 0 except-Exception swallowing
- 8/8 stages conform to Stage protocol
- 100% test pass rate where measured

**Concerns (not rewrite-bait, but real):**
- `source/_inferrer.py` at 2,040 LOC — investigation target
- `spectral_integration/` undertested (0.28 test/prod ratio for the single most architecturally critical stage)
- Test markers sparse — Level 0/1/2 CI gating is aspirational, not enforced
- `RadiantError` base class promised in docs, missing in code
- 404 bare-exception raises — need ratio analysis (Phase 2)

Optics test run still in progress at end of phase; status appended to phase 5 report.
