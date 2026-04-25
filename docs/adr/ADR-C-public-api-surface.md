# ADR-C: Public API Surface — Top-Level Sensor, Drop Config Classes, Drop BatchRunner

**Date:** 2026-04-25
**Status:** Accepted

## Context

[RADIANT_Scripting_API.md](../RADIANT_Scripting_API.md) shows code examples using:

```python
from radiant import Sensor
from radiant.api import SensorConfig, ScenarioConfig, BatchRunner
```

The 2026-04-25 audit ([Doc_Drift_Report.md#D5, #D8](../audit_2026/Doc_Drift_Report.md)) found:

- `src/radiant/__init__.py` exports only `__version__`. `Sensor` is reachable via `from radiant.api.sensor import Sensor` or `from radiant.api import Sensor`. The top-level `from radiant import Sensor` example fails.
- No `SensorConfig`, `ScenarioConfig`, or `BatchRunner` classes exist anywhere in `src/radiant/`. Every example using these classes fails at import.
- `Sensor.from_yaml()` and `Sensor.from_dict()` already accept the YAML/dict formats those config classes would have wrapped.
- `Sensor.sweep()` exists and is the working entry point for parameter sweeps.

This ADR resolves three sub-questions on the public API surface.

## Decision

1. **Top-level `from radiant import Sensor` — yes.** Re-export `Sensor` from `src/radiant/__init__.py`. Implemented via CU-NEW-02.
2. **`SensorConfig` / `ScenarioConfig` — no.** These classes are unnecessary. `Sensor.from_yaml()` / `Sensor.from_dict()` already absorb their roles. Remove all references from `RADIANT_Scripting_API.md`.
3. **`BatchRunner` — no separate class.** Keep `Sensor.sweep()` as the entry point for parameter sweeps. Remove `BatchRunner` references from `RADIANT_Scripting_API.md`. If batch features grow (parallel execution, checkpointing, progress reporting, distributed sweeps) such that a dedicated class would carry that state cleanly, file a fresh Category B task at that time.

## Rationale

**Sub-question 1 — top-level Sensor:** One-line change in `__init__.py` that matches what the doc already shows and what users will reach for first. `Sensor` is unambiguously the front door of the public API; burying it under `radiant.api` is churn for no gain.

**Sub-question 2 — config classes:** `Sensor.from_yaml()` and `Sensor.from_dict()` already accept the same data those wrappers would have carried. The `ParameterSet` they return is typed, validated, and inspectable. Adding `SensorConfig` / `ScenarioConfig` would be pure API surface — more import paths, more docstrings, more test coverage — for no capability not already present. CLAUDE.md "Don't add features ... beyond what the task requires" applies directly.

**Sub-question 3 — BatchRunner:** `Sensor.sweep()` covers current usage. Introducing a dedicated `BatchRunner` class now would be speculative design for hypothetical future requirements (CLAUDE.md "Don't design for hypothetical future requirements"). If parallel execution, checkpointing, or distributed sweeps later need a dedicated state-carrying class, refactoring `Sensor.sweep()` into a `BatchRunner` at that time is straightforward — and at that point the actual requirements will be known. Premature abstraction now produces an API surface shaped for guesswork rather than usage.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| Yes / No / No (chosen) | Doc matches code with minimal change; preserves `Sensor` as the single front door; no speculative API surface | Closes the door on independent config-object workflows until refiled |
| Yes / Yes / Yes (build everything) | Doc examples become valid as-written | Adds ~3 classes of public API surface for capabilities `Sensor.from_yaml()` and `Sensor.sweep()` already provide; days of work for no diagnostic gain |
| Yes / Yes / No (keep configs, drop BatchRunner) | Compromise position | `SensorConfig` still adds wrapper class without a use case; same objection as full-build option, just smaller |
| No on all (update doc to current code) | Zero code change | Forces `from radiant.api import Sensor` as the canonical import — uglier than `from radiant import Sensor` for one-line cost; rejected |

## Consequences

- **Positive:** Doc and code agree on the full top-level public surface. `Sensor` is the unambiguous front door (`Sensor.from_yaml()`, `Sensor.from_dict()`, `Sensor.sweep()`). No speculative classes. New contributors find one entry point, not four.
- **Negative:** Users who would have wanted a standalone, sensor-detached config object cannot construct one without instantiating a `Sensor`. Mitigation: `ParameterSet` exists and is the typed, validated, serializable object that role would have filled — it's already the right shape for that use case.
- **Neutral:** `radiant.api` continues to expose `Sensor` for explicit-import users; the top-level re-export is additive, not replacing.

## Downstream Tasks Unblocked

This decision unblocks the following audit reconciliation tasks (see [docs/audit_2026/Reconciliation_Tasks.md](../audit_2026/Reconciliation_Tasks.md)):

- **R3.CU-NEW-02** — Add top-level `Sensor` re-export to `src/radiant/__init__.py`. Per R20, confirm `RADIANT_Scripting_API.md` examples that say `from radiant import Sensor` now match reality. Add `tests/test_public_api.py::test_top_level_sensor_import`.
- **R2.A1 / Doc cleanup** — `RADIANT_Scripting_API.md` must be updated to:
  - Remove all `SensorConfig` and `ScenarioConfig` examples; replace with `Sensor.from_yaml()` / `Sensor.from_dict()` as the canonical entry.
  - Remove all `BatchRunner` examples; replace with `Sensor.sweep()` as the canonical sweep entry.
  - Drop the `from radiant.api import SensorConfig, ScenarioConfig, BatchRunner` import line entirely.
- **R3.CU-NEW-03** — `ChainResult` API method names (`signal_at` vs `signal_at_frame`) is decided in its own task; this ADR scopes only the top-level `Sensor` and config/batch classes.

## Subsequent Extensions

- **2026-04-25 (CU-018):** `RadiantError` joined the top-level surface — `from radiant import RadiantError`. The class lives at `radiant.core.exceptions.RadiantError` and is re-exported via `radiant/__init__.py`. Rationale: user code that wants to catch every framework-defined error needs a single name to use in `except RadiantError`, and forcing users to reach into `radiant.core.exceptions` for that one base class would defeat the "tight, documented top-level surface" goal of this ADR. The top-level `__all__` is now `{RadiantError, Sensor, __version__}`. SensorConfig / ScenarioConfig / BatchRunner remain out per the original decision.

## References

- [docs/audit_2026/Doc_Drift_Report.md#D5, #D8](../audit_2026/Doc_Drift_Report.md)
- [docs/audit_2026/Reconciliation_Tasks.md](../audit_2026/Reconciliation_Tasks.md) §R1.3
- [docs/audit_2026/Recommendation.md](../audit_2026/Recommendation.md)
- [src/radiant/api/sensor.py](../../src/radiant/api/sensor.py) — the `Sensor` class this ADR re-exports
- [src/radiant/__init__.py](../../src/radiant/__init__.py) — the file CU-NEW-02 will modify
- [docs/RADIANT_Scripting_API.md](../RADIANT_Scripting_API.md) — the doc whose examples this ADR brings into alignment with code
