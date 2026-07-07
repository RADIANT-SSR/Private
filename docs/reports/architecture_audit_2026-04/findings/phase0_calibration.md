# Phase 0 — Calibration

**Question this phase answers:** What does the architecture *promise*, and how do we test those promises mechanically?

## Spec corpus read
- [CLAUDE.md](../../../CLAUDE.md) — agent rules, 19 numbered rules (CLAUDE.md says "18 rules" in places but enumerates 1–19)
- [docs/architecture/RADIANT_Master_Architecture.md](../../RADIANT_Master_Architecture.md) — 15 architectural constraints C1–C15
- [docs/architecture/RADIANT_Signal_Chain_Architecture.md](../../RADIANT_Signal_Chain_Architecture.md) — Stage protocol, ChainState, RadiometricFrame, NoiseTerm
- [pyproject.toml](../../../pyproject.toml) — 5 import-linter contracts, mypy strict, ruff config

## Rule → predicate mapping
For Phase 2, each rule converts to a predicate that can be checked mechanically.

| Rule | Source | Predicate |
|------|--------|-----------|
| R1 (typing) | CLAUDE.md §1 | `mypy --strict` exit code on core/, api/ |
| R2 (units at boundaries) | CLAUDE.md §2 + C2 | grep physics modules for `* math.pi / 180`, `* 1e4`, `* 1e-6` |
| R3 (coords RH +Z) | CLAUDE.md §3 | docstring/comment audit on geometry.py, los_geometry.py |
| R4 (dual-path PSF/MTF) | CLAUDE.md §4 | inspect optics/ for single EffectivePSF; verify pupil-autocorr MTF; consistency check exists |
| R5 (emissivity derived) | CLAUDE.md §5 | grep for ParameterDef on element emissivity (must not exist as input) |
| R6 (pure stages) | CLAUDE.md §6 + C3 | grep stage.py for direct field assignment, file I/O, cross-stage calls |
| R7 (ChainState immutable) | CLAUDE.md §7 + C4 | grep `frozen=True`; grep for direct field assignment to state |
| R8 (spectral integ once) | CLAUDE.md §8 + C5 | trace integration call sites |
| R9 (EE_box once) | CLAUDE.md §9 + C6 | grep EE_box usage outside SpectralIntegrationStage |
| R10 (regime in optics) | CLAUDE.md §10 + C7 | grep regime classification call sites |
| R11 (no cross-stage imports) | CLAUDE.md §11 + C9 | `import-linter` exit code |
| R12 (every param has Def) | CLAUDE.md §12 + C10 | cross-check `params.get(...)` paths vs `_schema.py` registrations |
| R13 (constants.py only) | CLAUDE.md §13 + C1 | grep for `6.626e-34`, `2.998e8`, `1.381e-23`, `5.67e-8`, `h `, `c `, `k_B ` outside constants.py |
| R14 (no print) | CLAUDE.md §14 | grep `print(` outside cli/ and examples |
| R15 (actionable errors) | CLAUDE.md §15 + C12 | grep bare `raise ValueError`, `raise AssertionError`, `assert` for user input |
| R16 (validate before compute) | CLAUDE.md §16 + C11 | inspect API entry points for ParameterSet construction |
| R17 (no silent failures) | CLAUDE.md §17 | grep `except Exception` without re-raise; `except.*: pass`; `simplefilter("ignore"` |
| R18 (Level 0 tests) | CLAUDE.md §18 + C15 | inspect test markers, count level0-marked tests per stage |
| R19 (one comp / module) | CLAUDE.md §19 | file-size distribution + module purpose audit |

## Architectural promises (high-level)
1. 8-stage signal chain, ordered: source → atmosphere → optics → platform → spectral_integration → detector → readout → performance
2. `ChainState` is a frozen dataclass with `with_*` methods for every mutation
3. Two parallel spatial paths (PSF + MTF product) rooted in same pupil function
4. EE_box appears exactly once (SpectralIntegrationStage), only point/sub-pixel regimes
5. Regime finalized in OpticsStage; `state.stage_outputs["optics"]["regime"]` is authoritative
6. Public API surface = `radiant.Sensor`, `SensorConfig`, `ScenarioConfig`, `BatchRunner`, `ChainResult`
7. Provenance is mandatory on every ChainResult
8. 5 import-linter contracts enforced in CI

## What "good" looks like
- All 5 import-linter contracts green
- mypy --strict green on core/, api/
- Phase 2 rule predicates: ≤2 violations per rule, none in load-bearing paths
- Doc drift: ≤20% of falsifiable claims marked drifted
- No god modules (>1000 LOC) in physics stages
- Phase 5 sloppiness signals: dead helpers ≤5, swallowed warnings ≤2, schema/code drift ≤10 params
