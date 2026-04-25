# ADR-B: Metric Layer Soft-Fail — Codify SNRResult.failure_reason Pattern

**Date:** 2026-04-25
**Status:** Accepted

## Context

CLAUDE.md §16 ("Validate Before Compute") states: *"Never return `NaN` or `inf` silently; raise `NumericalError` with context."* §17 ("No Silent Failures") forbids `except Exception: pass`, swallowed warnings, and returning default values when physics is undefined.

The 2026-04-25 audit ([Doc_Drift_Report.md#D4](../audit_2026/Doc_Drift_Report.md)) found:

- No `NumericalError` class exists anywhere in `src/radiant/`. The rule references a class that has never been built.
- [performance/snr.py](../../src/radiant/performance/snr.py) returns `SNRResult(value=nan, failure_reason=str)` on physics-undefined inputs (zero noise, negative signal, NaN propagation). The `failure_reason` field is structured and inspectable. This is a **deliberate** soft-fail pattern, not a silent NaN return.
- Every metric-layer caller already inspects `failure_reason` — nothing is being swallowed in the §17 sense.

The drift is real but bounded: the docs describe a `NumericalError`-raising metric layer, the code implements a result-typed failure layer. Both achieve "no silent NaN propagation" — they differ on whether the failure surfaces as an exception or as a field on the return value.

## Decision

**The metric layer keeps the soft-fail `SNRResult.failure_reason` pattern.** Codify a narrow, named carve-out from §16/§17 for metric-layer computations. Physics-layer functions continue to raise on undefined inputs.

The carve-out scope is explicit:

- **Metric layer (soft-fail allowed):** `src/radiant/performance/snr.py`, `performance/nedt.py`, `performance/niirs.py`, and any future per-cell-fail-tolerant computation under `performance/`. Returns a result type whose value is `nan` and whose `failure_reason` field carries a structured, human-readable explanation.
- **Physics layer (hard-fail required):** `source/`, `atmosphere/`, `optics/`, `platform/`, `spectral_integration/`, `detector/`, `readout/`. These continue to raise per §16/§17. They never return `nan` silently.

A metric-layer "soft-fail" is *not* a silent failure: the failure is explicit, named in `failure_reason`, and surfaces in the result object that callers already inspect.

`NumericalError` is not introduced as a class. The doc claim that referenced it is removed in the doc update task triggered by this ADR.

## Rationale

The soft-fail pattern is the right shape for metric-layer code because:

1. **Sweep / Monte-Carlo / `BatchRunner` workflows** compute metrics across many cells. A single physics-undefined cell should not abort a 1000-cell sweep. Soft-fail lets the harness record the failure and move on; hard-fail forces try/except scaffolding around every cell.
2. **`failure_reason` carries the same diagnostic content** an exception's `context` dict would. Callers inspect a structured field rather than catch and unpack an exception.
3. **§17's intent — "no hidden NaN propagation" — is preserved.** The NaN is named, the reason is explicit, and downstream code that consumes `result.value` without checking `failure_reason` is just as buggy as code that ignores a raised exception. The harness pattern around `SNRResult` in `performance/` already enforces the check.
4. **The carve-out is narrow and named** — "metric layer" is the `performance/` modules listed above. Physics modules retain the universal §16/§17 rule unchanged.

The hard-fail alternative would require: (a) introducing `NumericalError`, (b) converting `compute_snr`/`compute_nedt`/`compute_niirs` to raise, (c) wrapping every sweep/BatchRunner caller in try/except, (d) building a new failure-recording channel in the harness that re-creates what `failure_reason` already provides. That is a meaningful refactor with no diagnostic gain.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| Soft-fail wins (chosen) | Matches sweep workflows; preserves diagnostic content; no code change; narrow named carve-out | Adds a wrinkle to a previously-universal §16/§17 rule; future contributors must learn where the carve-out applies |
| Hard-fail wins (introduce `NumericalError`, convert metric layer) | §16/§17 stays universal; one rule, no carve-out | Adds try/except scaffolding to every sweep caller; rebuilds failure-recording infrastructure; days of refactor for no diagnostic gain |
| Hybrid — raise but provide a `safe_compute_snr` wrapper | Lets users opt into soft-fail | Two parallel APIs for the same operation; more surface, more confusion |

## Consequences

- **Positive:** Doc and code agree. Sweep / Monte-Carlo workflows keep the per-cell diagnostic ergonomics they already have. `failure_reason` is now a documented, supported pattern rather than an undocumented divergence.
- **Negative:** §16/§17's universality is broken by a named carve-out. Future contributors and agents must understand where the carve-out applies. Mitigation: the carve-out is named explicitly in CLAUDE.md §17, and the metric-layer modules are enumerated.
- **Neutral:** `NumericalError` does not exist and will not be created by this ADR. If a future non-metric numerical failure path needs a typed exception, it can be filed at that time as its own task.

## Downstream Tasks Unblocked

This decision triggers the following doc updates (R20 — doc-and-code lock-step):

1. **CLAUDE.md §17** — add the metric-layer carve-out clause:
   > *Exception (metric layer):* computations under `radiant.performance/` (`snr.py`, `nedt.py`, `niirs.py`) may return result-typed failures with an explicit `failure_reason` field instead of raising. The failure must be named and surfaced in the result; silent NaN propagation remains forbidden. Physics-layer modules (source through readout) keep the universal raise rule.
2. **CLAUDE.md §16** — qualify the "raise `NumericalError`" sentence: physics-layer functions raise; metric-layer functions may use the soft-fail result pattern. Remove the implication that `NumericalError` is an existing class.
3. **`docs/RADIANT_Master_Architecture.md` §C12 and §16** — describe `SNRResult.failure_reason` as the canonical metric-layer failure pattern. Remove `NumericalError` references.
4. **`docs/RADIANT_Testing_Validation.md`** — update test guidance to assert on `result.failure_reason` for metric-layer failure modes rather than `pytest.raises(NumericalError)`.
5. **R2.A4 (CLAUDE.md sync task)** — pick up the §16/§17 changes alongside the rule-count fix.

No code task is filed — `performance/snr.py` already implements the codified pattern.

## References

- [docs/audit_2026/Doc_Drift_Report.md#D4](../audit_2026/Doc_Drift_Report.md)
- [docs/audit_2026/Reconciliation_Tasks.md](../audit_2026/Reconciliation_Tasks.md) §R1.2
- [docs/audit_2026/findings/phase3_pipeline_traces.md](../audit_2026/findings/phase3_pipeline_traces.md)
- [src/radiant/performance/snr.py](../../src/radiant/performance/snr.py) — the SNRResult.failure_reason implementation this ADR formalizes
- CLAUDE.md §16, §17 — the rules this ADR carves a metric-layer exception from
