# Doc-vs-Code Drift Report

**Read-only audit:** these findings document drift; no source files were modified.

Bucket key:
- **A** — code is right, doc is stale → mechanical doc update
- **B** — doc is right, code drifted → cleanup-backlog item, code should change
- **C** — both wrong / design question → needs an ADR

## High-impact drift

### D1. `radiant.spatial` module does not exist
- **Doc claim:** [RADIANT_Spatial_Complete.md](../RADIANT_Spatial_Complete.md) describes a top-level `spatial/` subpackage that owns sampling, fidelity, PSF assembly, and the MTF product
- **Reality:** No `spatial/` directory in `src/radiant/`. Spatial responsibilities are distributed across `optics/`, `platform/`, `detector/`, and `performance/consistency_check.py`
- **Bucket:** A — code is the working design; doc needs to either be deleted (if obsolete) or rewritten to reflect the distributed-spatial reality
- **Impact:** new contributors reading `Spatial_Complete.md` will look for files that don't exist

### D2. `FidelityPreset` system does not exist
- **Doc claim:** [RADIANT_Spatial_Complete.md](../RADIANT_Spatial_Complete.md) and [RADIANT_Optics.md](../RADIANT_Optics.md) describe a `FidelityPreset` enum (`draft`, `standard`, `high`) that gates the dual-path consistency check, controls pupil grid size, and selects Marechal vs full-OTF
- **Reality:** No `FidelityPreset` class anywhere in `src/`. The dual-path consistency check ([performance/consistency_check.py](../../src/radiant/performance/consistency_check.py)) runs unconditionally with hardcoded `tolerance = 5e-2`. Marechal/full-OTF selection is via a different mechanism (mode dispatch in `optics/`).
- **Bucket:** A or C — depending on whether the team intended to build FidelityPreset and decided not to (A: doc out of date) or still intends to (C: roadmap item)

### D3. `RadiantError` base class does not exist
- **Doc claim:** [RADIANT_Master_Architecture.md §C12, §7.4](../RADIANT_Master_Architecture.md), CLAUDE.md §15, [RADIANT_Testing_Validation.md](../RADIANT_Testing_Validation.md) describe a `RadiantError(Exception)` base with `what`/`why`/`action`/`context` fields and a hierarchy under `radiant.exceptions`
- **Reality:** No `radiant.exceptions` module. No `RadiantError` class. Custom errors subclass stdlib (`ValueError`, `RuntimeError`). 153 structured raises (subclasses) vs 404 bare `raise ValueError/Type/Runtime`. The bare ones still have descriptive messages, but they don't have the four-field structure.
- **Bucket:** B — doc reflects the team's design intent; the code lags. This is a real cleanup item.
- **Impact:** future agents reading the rule will assume `RadiantError` exists and try to import it from `radiant.exceptions` (will fail).

### D4. `NumericalError` does not exist; `compute_snr` returns NaN with reason instead
- **Doc claim:** CLAUDE.md §16, RADIANT_Testing_Validation.md show a `NumericalError` for "NaN, inf, or non-convergence"
- **Reality:** [performance/snr.py](../../src/radiant/performance/snr.py) returns `SNRResult(value=nan, failure_reason=...)` instead of raising `NumericalError`. This is a **deliberate** soft-fail pattern — the result object is structured and inspectable.
- **Bucket:** C — design preference change. The soft-fail pattern is arguably better for a metrics layer (callers want to inspect why SNR was unobtainable, not catch exceptions). Needs an ADR to make the choice explicit.

### D5. Public API top-level imports do not match docs
- **Doc claim:** [RADIANT_Scripting_API.md](../RADIANT_Scripting_API.md) shows `from radiant import Sensor`, `from radiant.api import SensorConfig, ScenarioConfig, BatchRunner`
- **Reality:** `src/radiant/__init__.py` exports nothing public — only `__version__`. `Sensor` is only reachable via `from radiant.api.sensor import Sensor` or `from radiant.api import Sensor`. No `SensorConfig`, `ScenarioConfig`, `BatchRunner` classes exist anywhere in the codebase.
- **Bucket:** B (Sensor re-export at top level is trivial to add) + C (the missing classes are a real design question — does the team still want this surface, or has the API converged on a different shape via `RadiantSession`?)
- **Impact:** every doc example with `from radiant import Sensor` will fail import.

### D6. `RADIANT_File_Tree.md` shows obsolete file layout
- **Doc claim:** lists `source/blackbody.py`, `source/solar.py`, `source/reflected.py` as Stage 1 files
- **Reality:** Planck and solar moved to `core/` (`core/blackbody.py`, `core/solar.py`); the source/ tree has restructured significantly — `_inferrer.py`, `resolvers/`, `converters/`, `shapes/`, `composite.py`, `combined.py`, `material.py`, `point_source_*.py`, `sub_pixel.py`, `tabulated.py` are present and not described
- **Bucket:** A — doc is stale; code is the canonical layout. Regenerate `RADIANT_File_Tree.md` from `find` output

### D7. Stage protocol uses `@property name` not class attribute
- **Doc claim:** [RADIANT_Signal_Chain_Architecture.md §2](../RADIANT_Signal_Chain_Architecture.md), §7 show `class Stage(Protocol): name: str`
- **Reality:** [core/chain.py:38-43](../../src/radiant/core/chain.py#L38-L43) defines it as `@property def name(self) -> str: ...`. All 8 stages implement it as `@property`.
- **Bucket:** A — minor; the property form is more flexible. Update the doc snippet.

### D8. `ChainResult` API method names diverge
- **Doc claim:** `result.signal_at(frame)`, `result.noise_at(frame)`, `result.snr()`, `result.nedt()`, `result.niirs()`
- **Reality:** [io/results.py](../../src/radiant/io/results.py) implements `signal_at_frame()`, `noise_at_frame()`. Performance metrics are exposed as `result.metrics["snr"]` etc., not as methods.
- **Bucket:** B (small) — either rename methods to match doc or update doc; user impact is real because docs show working code that doesn't work
- **Impact:** every example in `RADIANT_Scripting_API.md` that calls `result.signal_at(...)` will fail

### D9. `to_provenance_record()` partial implementation
- **Doc claim:** C13 — every ChainResult carries: run ID, RADIANT version, git commit, Python version, dep versions, resolved params, input file hashes, active model identifiers
- **Reality:** [core/parameters.py:566](../../src/radiant/core/parameters.py#L566) `ParameterSet.to_provenance_record(radiant_version)` returns only `radiant_version`, `resolved_at`, and resolved parameters. Missing: run ID, git commit, Python version, dep versions, file hashes, active model identifiers. Not surfaced via `ChainResult.to_provenance_record()` — that method does not exist.
- **Bucket:** B — doc is right, code is incomplete. Real cleanup work, not a rewrite trigger.

## Medium-impact drift

### D10. Test markers incompletely applied
- **Doc claim:** RADIANT_Testing_Validation.md §3 describes Level 0/1/2 hierarchy with CI gating ("Level 0 failure blocks Level 1")
- **Reality:** 287 level0-marked, 6 level1-marked, 0 level2-marked, ~2,058 unmarked tests
- **Bucket:** B — the structure is in place but enforcement is impossible without the markers. Needs a sweep to add markers.

### D11. CLAUDE.md says "18 rules" — actually lists 19
- **Doc claim:** CLAUDE.md prose references "the 18 rules" in places
- **Reality:** Rules are numbered 1–19 in the same document
- **Bucket:** A — trivial doc fix

### D12. `RADIANT_Plugins.md` describes ABCs; `radiant/plugins/` has 1 LOC
- **Doc claim:** Plugin ABCs (`SourcePlugin`, `AtmospherePlugin`, `MetricPlugin`) with entry-points and spectral library hooks
- **Reality:** `src/radiant/plugins/` contains just an `__init__.py` (1 LOC). The `import-linter` contract for plugins exists but there's nothing to enforce against.
- **Bucket:** A or C — if plugins are deferred to v2 (per Master_Architecture §4), the plugin doc should be marked `[v2]`. If they're in scope now, the implementation is a stub.

### D13. Aspirational/historical planning docs mixed with current docs
- The `docs/` directory contains 30+ `RADIANT_*.md` files. Some are roadmaps (`RADIANT_Phase1_Plan.md`, `RADIANT_Phase2_Implementation_Prompts_*.md`, `RADIANT_Phase3_Implementation_Prompts.md`), some are spec, some are completed-feature design docs (`Option_C_Implementation_Plan.md`, `Cleanup_Backlog_Phase2_Plan.md`). New contributors cannot easily tell which is authoritative.
- **Bucket:** A — needs a docs/archive policy. Move completed-stage docs to `docs/archive/`; mark roadmap docs explicitly.

## Low-impact drift / observations

- D14. `RADIANT_Master_Architecture.md` Phase 1d ordering describes detector/readout/performance as depending on 1b+1c — the actual implementation order matched this; doc is fine.
- D15. `RADIANT_Conventions.md` units table is consistent with code — spot-check on radiance, wavelength, time.
- D16. Optics-doc dual-path description matches code (after accounting for distributed-spatial reality — D1).

## Summary by bucket

| Bucket | Count | Examples |
|--------|-------|----------|
| A (doc stale, fix doc) | 7 | D1, D2, D6, D7, D11, D12, D13 |
| B (code drifted, fix code) | 5 | D3, D5 (partial), D8, D9, D10 |
| C (design question) | 3 | D2 (alternate), D4, D5 (partial) |

**Conclusion:** Most drift is doc lag (Bucket A) — common in a young codebase where implementation outruns documentation. The code-side debts (Bucket B) are well-bounded and align with the existing Cleanup_Backlog format.
