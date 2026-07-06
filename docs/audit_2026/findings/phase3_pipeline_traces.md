# Phase 3 — Pipeline Structural Traces

**Question this phase answers:** Does the actual pipeline match the architecture document, end to end?

**Scope note:** Per user direction, physics correctness is assumed. This phase verifies STRUCTURE only.

## The 8-stage pipeline assembly

Single source of truth: [src/radiant/api/session.py:41-50](../../../src/radiant/api/session.py#L41-L50)

```python
self._runner = ChainRunner([
    SourceStage(),
    AtmosphereStage(),
    OpticsStage(),
    PlatformStage(),
    SpectralIntegrationStage(),
    DetectorStage(),
    ReadoutStage(),
    PerformanceStage(),
])
```

**Verdict:** Matches [docs/RADIANT_Signal_Chain_Architecture.md §1](../../RADIANT_Signal_Chain_Architecture.md) exactly. 8 stages, in order. No bypass paths.

## SNR pipeline trace

| Step | Location | Reads from | Writes to |
|------|----------|------------|-----------|
| Photon flux at FPA | spectral_integration/stage.py | `frames["post_optics"]`, `stage_outputs["optics"]["EE_box"]`, `stage_outputs["optics"]["regime"]` | `frames["photoelectrons"]` |
| Detector noise terms | detector/stage.py | photoelectrons | `state.noise_terms` |
| Readout aggregation | readout/stage.py | noise_terms, signal_e | `stage_outputs["readout"]["sigma_total_e", "signal_e_final"]` |
| SNR | performance/stage.py:464 → snr.py:55 `compute_snr(state)` | reads above outputs | `state.metrics["snr"]` |

[performance/snr.py](../../../src/radiant/performance/snr.py) is a pure function on `ChainState`. Documented failure modes (zero noise → inf, negative signal → NaN with reason). It returns an `SNRResult` dataclass with explicit `failure_reason` field instead of `raise NumericalError` — this is a **design deviation** from CLAUDE.md §17 "no silent failures" but is an explicit, structured non-raise (the caller gets the reason). Not a violation; doc-vs-code disagreement (Bucket A or C, Phase 4).

## NEDT pipeline trace

| Step | Location | Reads from | Writes to |
|------|----------|------------|-----------|
| dS/dT | performance/nedt.py | `frames["at_aperture"]`, `state.metrics["snr"]` | — |
| NEDT | performance/stage.py:494 → `_compute_nedt_metric(state, params)` | SNR + Planck derivative | `state.metrics["nedt"]` |

`compute_nedt` is a separate function ([nedt.py:61](../../../src/radiant/performance/nedt.py#L61)). Computed only after SNR is in metrics — sequence dependency is enforced at the `_compute_*_metric` call ordering inside `PerformanceStage.run()` (stage.py:464-499).

## NIIRS pipeline trace

| Step | Location | Reads from | Writes to |
|------|----------|------------|-----------|
| RER (system MTF integral) | performance/_compute_spatial_metrics(stage.py:38) | `state.mtf_terms`, `frames`, EffectivePSF | `state.metrics["rer"]`, `state.stage_outputs["performance"]["spatial_*"]` |
| GSD | performance/_compute_gsd_metrics(stage.py:244) | params (geometry) | `state.metrics["gsd_*"]` |
| Q | performance/_compute_q_metrics(stage.py:344) | wavelength, F#, pitch | `state.metrics["q"]` |
| NIIRS (GIQE5/IIRS) | performance/niirs.py + stage.py:497 `_compute_niirs_metric` | RER, SNR, GSD, Q | `state.metrics["niirs"]` |

The NIIRS chain depends on RER → which depends on system MTF → which is the product of all `state.mtf_terms` written by upstream stages. This dependency is the heart of the dual-path-MTF requirement (Rule 4) — NIIRS's correctness depends on the consistency invariant in [performance/consistency_check.py](../../../src/radiant/performance/consistency_check.py) running and passing.

## EE_box producer/consumer flow (Rule 9 trace)

| Step | Location | Action |
|------|----------|--------|
| Compute | optics/stage.py:_finalize_regime() + EE_box logic | derives EE_box from PSF and regime |
| Publish | optics/stage.py:895 | `state.with_stage_output("optics", "EE_box", ee_box)` |
| Consume (point) | spectral_integration/stage.py:230 | `signal_e = e_per_s * t_int * EE_box` |
| Consume (subpixel target) | spectral_integration/stage.py:193 | `fill_fraction * L_target_through * EE_box` |
| Skip (extended) | spectral_integration/stage.py:65 | guards: errors if `EE_box != 1.0` in EXTENDED |

**Verdict:** Single producer, exactly two consumer multiplications, both in spectral_integration. Matches Rule 9 to the letter.

## Regime finalization flow (Rule 10 trace)

| Step | Location | Field |
|------|----------|-------|
| Tentative | source/resolvers/{intensity,geometry,direct,sub_pixel,physical}.py | `tentative_regime` (returned by resolver, written by SourceStage) |
| Final | optics/stage.py:419 `_finalize_regime()` | `stage_outputs["optics"]["regime"]` |
| Consumer | spectral_integration/stage.py:58 | `regime = optics_out["regime"]` |
| Consumer | atmosphere/assembly.py | reads `regime` (verified in Phase 2 grep) |

No downstream stage re-classifies regime.

## ChainResult API surface

[src/radiant/io/results.py:26](../../../src/radiant/io/results.py#L26) implements ChainResult.

| Promised in Signal_Chain doc §7 | Implemented? |
|----|----|
| `signal_at(frame)` | ✅ as `signal_at_frame()` (renamed) |
| `noise_at(frame, term=...)` | ✅ as `noise_at_frame()` |
| `noise_budget()` | (need to verify) |
| `mtf_curve(term)` | (need to verify) |
| `mtf_at_nyquist()` | (need to verify) |
| `snr()`, `nedt()`, `niirs()` | partially — exposed as `result.metrics["snr"]` etc., not as methods |
| `to_provenance_record()` | ❌ on ChainResult; ✅ on ParameterSet |

The shapes don't all match the doc — some are properties/dict access instead of methods. Functional parity is mostly there; doc drift on the exact API names.

## Provenance status (Rule C13)

CLAUDE.md / C13 promises a provenance record containing:
- run ID
- RADIANT version
- git commit
- Python version
- dependency versions
- resolved parameter set with per-parameter provenance
- input file hashes
- active model identifiers

Implemented in [core/parameters.py:566](../../../src/radiant/core/parameters.py#L566) `ParameterSet.to_provenance_record(radiant_version)`:
```python
return {
    "radiant_version": radiant_version,
    "resolved_at": _dt.datetime.now(_dt.UTC).isoformat(),
    "parameters": {name: rv.to_dict() for name, rv in self._resolved.items()},
}
```

**Captured:** radiant_version, resolved timestamp, resolved parameters (with per-param provenance — Provenance enum exists at parameters.py:77).

**Missing:** run ID, git commit, Python version, dependency versions, input file hashes, active model identifiers.

This is a **partial implementation** of C13. The data is captured at the parameter level (per-param provenance enum), but the chain-result-wrapping promised by the doc is not surfaced through ChainResult. Bucket B (code should change) or Bucket C (decide whether C13 is realistic for v0.1.0).

## Phase 3 verdict

The 8-stage pipeline is structurally as documented. The signal-chain dataflow is honored:
- One assembly point (api/session.py)
- No bypass paths
- EE_box producer/consumer pattern matches Rule 9
- Regime finalization matches Rule 10
- SNR/NEDT/NIIRS are pure functions reading from ChainState — no side channels

Real gaps exposed by the trace:
1. **`to_provenance_record()` on ChainResult is missing.** ParameterSet has a partial implementation; the chain-level wrapper is not there. C13 is aspirational rather than enforced.
2. **`SNRResult.failure_reason` is a soft-fail pattern,** not the `NumericalError` the doc envisions. Whether this is a doc-vs-code drift or a real preference change needs ADR-level adjudication.
3. **ChainResult API names diverge from the doc** (`signal_at_frame` vs `signal_at`; metrics-as-dict vs metric-methods). Functional parity is preserved.

None of these break the architecture. They represent a system that has been built mostly to spec but with naming refinements and a still-incomplete provenance feature.
