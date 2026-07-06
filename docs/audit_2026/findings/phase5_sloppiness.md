# Phase 5 — Sloppiness Signals

**Question this phase answers:** Are there hidden signs of accumulated cruft — workarounds layered on workarounds, abandoned helpers, gutted tests, parallel `_v2`/`_legacy` versions, swallowed warnings — that the green CI gates wouldn't catch?

## Headline finding

**The sloppiness signals are essentially absent.** Across every probe a "haphazardly assembled" codebase would light up, this one is dark. The single known production-code suppression and the single oversize module are both on the existing CU backlog with explicit, dated remediation plans.

## Probe-by-probe results

### Comments-as-debt: TODO / FIXME / XXX / HACK

| Pattern | Hits in `src/` |
|---------|----------------|
| `TODO` / `FIXME` / `XXX` / `HACK` (case-sensitive) | **0** in non-test code |
| Test-file `state.frames["hack"]` | 3 — these are dummy-key tests verifying frozen-state immutability, not debt markers |
| `workaround` / `kludge` (case-insensitive) | 2 — both in user-facing error messages ([atmosphere/tabulated.py:498](../../../src/radiant/atmosphere/tabulated.py#L498), [atmosphere/interpolated.py:534](../../../src/radiant/atmosphere/interpolated.py#L534)) telling users to use SimpleAtmosphere as a workaround. Helpful guidance, not hidden debt. |

A codebase rushed to a deadline accumulates `# TODO: fix this` markers. RADIANT has none.

### Parallel-version symbols: `_v2` / `_legacy` / `_deprecated`

| Pattern | Hits |
|---------|------|
| `def \w+_v2`, `class \w+_v2`, `def \w+_legacy`, `def \w+_deprecated` | **0** |
| `LegacyV*`, `*V2*` class names | **0** |
| `@deprecated` decorator | **0** |
| `DeprecationWarning` emits | **1** — [source/resolvers/intensity.py:48](../../../src/radiant/source/resolvers/intensity.py#L48), a legitimate API-migration warning |
| `legacy` in test names | 1 — `test_matches_legacy_formula_bit_exact` ([atmosphere/tests/test_assembly.py:152](../../../src/radiant/atmosphere/tests/test_assembly.py#L152)) — bit-exact regression vs the prior formula, the right way to retire an algorithm |

The team refactors in place rather than spawning parallel `_v2` modules. This is a strong cultural signal.

### Gutted or bypassed tests

| Pattern | Hits |
|---------|------|
| `assert True` / `assert 1` | **0** |
| `@pytest.mark.skip` | **0** in production tests |
| `@pytest.mark.xfail` | **0** |
| `pytest.skip(...)` | 1 — `matplotlib not available` graceful-degrade ([atmosphere/tests/test_simple.py:549](../../../src/radiant/atmosphere/tests/test_simple.py#L549)) |
| Test ratio (production tests : production LOC) | 0.93 (`32,219 test LOC / 35,000 prod LOC`) |

No tests are silently disabled. No tests are placeholders that would still pass against a gutted implementation. The CLAUDE.md rule against "modifying `pytest.approx` tolerance to make a failing test pass" appears to be honored — every `pytest.approx(...)` call carries an explicit `rel=` or `abs=` (Phase 1 grep counted these in the hundreds).

### Swallowed warnings

| Pattern | Hits in production code |
|---------|------|
| `warnings.simplefilter("ignore", ...)` | **1** — [source/_inferrer.py:1675](../../../src/radiant/source/_inferrer.py#L1675), already filed as **CU-007** with a documented plan to remove |
| `warnings.filterwarnings("ignore", ...)` | 0 |

In tests, warning suppression is overwhelmingly `simplefilter("error", UserWarning)` — promoting warnings to test failures, the opposite of swallowing them. The `simplefilter("ignore", UserWarning)` calls in `test_inferrer_shape.py` are scoped to tests that are *exercising* the placeholder branches whose warnings are being verified separately.

### Dead-code helpers

The closest finding to "dead helper" is **CU-005** (`theta_o_from_eta` in `core/los_geometry.py`) — a converter with zero non-test callers in `src/`. The CU is actively tracked with a 3-option resolution path:
- (a) wire into `OpticsStage._finalize_regime()`
- (b) move to `radiant.api.geometry`
- (c) delete

The fact that it shows up as a CU rather than as decaying dead code is the relevant signal: when something orphans, the team logs it.

### Schema drift (parameter / definition / runtime)

Phase 2 R12 verified: 111 unique paths consumed via `params.get(...)`; 129 `ParameterDef` registrations; 19 defined-but-not-direct-`get`-d are consumed via the converter registry / `get_resolved` (legitimate). **One** orphan use exists: `geometry.observer_zenith_rad` at [source/_inferrer.py:325](../../../src/radiant/source/_inferrer.py#L325). This is already on the backlog as **CU-009** with a stand-alone task description. Schema is consistent.

### Module-size accretion (god-module check)

Phase 1 listed 7 files >800 LOC. Phase 5 inspected each for "accumulated cruft" patterns:

| File | LOC | Cruft signal? |
|------|-----|---------------|
| `source/_inferrer.py` | 2,040 | **No.** Opens with a 53-line docstring explaining it is a *deliberate* "additive bridge" between legacy parameter surface and the new Option C descriptor surface. Scope is declared, lossy boundary documented, rule conformance asserted (Rules 2, 11, 19 cited inline). The largest function clusters are deterministic routing rules, each cite-tagged to a row of the §3.2 inference matrix. |
| `atmosphere/assembly.py` | 1,166 | No. Single state machine assembling regime-dependent atmospheric quantities. Long but linear. |
| `atmosphere/simple.py` | 998 | No. One coherent atmospheric model with an analytic backend; tightly cohesive. |
| `core/descriptors.py` | 964 | No. Multi-class descriptor module — related dataclasses live together, which is appropriate per the docstring. |
| `optics/stage.py` | 897 | No. Heavy stage by design (PSF, MTF, regime, EE_box, throughput, warm optics) — and within rule. |
| `atmosphere/modtran.py` | 857 | No. File-format complexity (TAPE7 parsing). |
| `source/_schema.py` | 796 | No. ParameterDef registrations for the largest stage. Should be flat and long. |

**None show the rotting-cohesion pattern** (multiple unrelated computations bundled, helper functions with no consistent naming, regions cordoned off by `# === REGION ===` banners). All seven are documented and rule-conformant.

## CU-backlog audit: exhaustive vs. tip-of-iceberg?

A healthy debt log is one where the open items match what an outside auditor independently finds. A sloppy codebase is one where the audit turns up large categories of debt the team hasn't logged.

Cross-checking: every Phase-1/2/3 finding that pointed to real code-side debt mapped onto an existing CU:

| Phase finding | Existing CU |
|---------------|-------------|
| `geometry.observer_zenith_rad` orphan ParameterDef | CU-009 |
| `simplefilter("ignore", UserWarning)` in `_inferrer.py` | CU-007 |
| MTF consistency tolerance miss on `swir_aerial_gas` | CU-003 |
| `theta_o_from_eta` unwired | CU-005 |
| GroundBackground placeholder still grey | CU-008 |
| MODTRAN single-τ alias | CU-011 |
| Shadow-mode classification not wired | CU-012 |

**No Phase-5 probe found a debt category not already on the backlog.** Doc-vs-code drift items (`RadiantError` base class, top-level `Sensor` re-export, `to_provenance_record()` on ChainResult, test markers) are documented in [Doc_Reconciliation_Plan.md](../Doc_Reconciliation_Plan.md) as CU-NEW-01 through CU-NEW-05; those are doc-derived and were not visible from a code-only sweep.

The CU log uses an **explicit "stage-deferral expired" pattern**: each open CU records the stages it was deferred behind, the stages that have since landed, and an explicit re-audit line ("verified 2026-04-24"). This is exemplary debt-log hygiene. The 7 resolved CUs (CU-001/002/004/006/010/014/015) all closed within the last week with linked commits.

## Phase 5 verdict

The code does **not** look like a fast-and-loose deliverable. Across every classical sloppiness probe — debt comments, parallel `_v2` versions, gutted tests, swallowed warnings, schema drift, god modules without justifying cohesion — RADIANT is at or near the floor of how clean a young scientific codebase can plausibly be:

- **0** TODO/FIXME/HACK markers in production code
- **0** `_v2`/`_legacy`/`_deprecated` symbols
- **0** gutted or skipped tests
- **1** production-code warning suppression (CU-007, on the docket)
- **1** orphan ParameterDef (CU-009, on the docket)
- **6/6** large modules carry a justifying docstring or are inherent state machines
- Every code-side debt the audit found is already in the existing CU backlog with a remediation plan

The dominant signal here is the **opposite** of accumulated cruft — it's that the team has been logging debt as it accumulates, resolving CUs at a healthy weekly cadence, and refactoring in place rather than spawning parallel implementations. The "the code base has gotten sloppy" hypothesis from leadership is **not supported by the evidence**.
