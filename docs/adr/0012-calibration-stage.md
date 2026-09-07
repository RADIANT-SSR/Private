# ADR-0012: Calibration Stage and Bias Accumulator

**Date:** 2026-09-06
**Status:** Accepted (owner-ratified 2026-09-06 with
`docs/plans/Calibration_Model_Plan.md` D1–D7)

## Context

RADIANT had no calibration error model (Gap 120). The noise budget treats
every term as an a-priori stochastic source; `detector.prnu_pct` /
`detector.dsnu_e_rms` are static non-uniformity inputs with no relationship to
a calibration process; and there is no representation of systematic
(bias) error at all — `performance/temperature_retrieval.py` reports a
retrieval with no accuracy statement.

Three physical facts drive the design:

1. **Calibration-limited NEDT.** For cooled staring IR systems the achieved
   NEDT is frequently set by post-NUC residual FPN, not the temporal floor.
2. **Correlated errors do not average down.** TDI/coadds/binning reduce
   temporal noise by $\sqrt{N}$; calibration residuals are correlated
   frame-to-frame and along-column, so they are exempt.
3. **Precision ≠ accuracy.** Cal-source and gain uncertainties bias the
   radiometric scale; a bias must never be RSS'd into $\sigma_{total}$.

## Decision

**1. A terms-only `CalibrationStage` between Readout and Performance.**
Precedent: `PlatformStage` (terms-only, no frame transformation). The chain
position is load-bearing: residual-FPN noise terms are appended AFTER
readout's TDI/coadd scaling, so they are structurally exempt from $\sqrt{N}$
averaging — ordering enforces the correlation physics, no scaling code needs
term-awareness. The stage adds no PSF kernel and no MTF term: residual FPN is
spatial *noise*, not a spatial *degradation*; neither Rule 4 path gains a
contributor and the consistency check is unaffected.

**2. A `BiasTerm` accumulator on `ChainState`.** New frozen dataclass
`BiasTerm` (`core/radiometry.py`) and field
`ChainState.bias_terms: tuple[BiasTerm, ...]` with `with_bias()`. SNR/NEDT
consume `noise_terms` only; the radiometric-accuracy metric consumes
`bias_terms` only. The type separation — not reviewer discipline — is what
enforces bias-is-never-RSS'd-with-noise.

**3. `CALIBRATION_TERMS` classification** (`core/noise_budget.py`), parallel
to Gap 117's `COUNTING_TERMS`: `{"nuc_residual", "gain_drift",
"offset_drift"}`, members of `SPATIAL_TERMS`, excluded from the detector
raw-budget contract, and marked correlated-across-integration for any future
re-scaling code path.

**4. One namespace, one screen.** All parameters live in
`calibration/_schema.py` (`calibration.*`), giving one YAML block and — via
the GUI's screen-per-stage invariant (`STAGE_COMPOSITIONS` keyed by
`RadiantSession.stage_names`) — a dedicated Calibration screen (plan Phase 3)
without breaking the signal-chain-strip semantic.

## Alternative rejected

Modules scattered inside detector/readout with a non-stage GUI screen
composed across namespaces. Rejected 2026-09-06 (owner discussion): it
fragments the analyst-facing concept ("what is my cal scheme and how good is
it" is one question), splits the YAML surface, requires the $\sqrt{N}$
exemption to be a term-classification convention instead of a structural
ordering, and breaks the GUI's screens-are-stages invariant.

## Consequences

- Chain grows to 10 stages; `history` and stage-roster assertions updated.
- `scheme = "none"` (default) is a recorded no-op — golden results are
  bit-identical until an analyst enables the model.
- Ops-level growth (cal cadence trades, scene-based NUC, onboard-source
  fore-optics exclusion) has a home when it arrives.
- Lock-step docs: `RADIANT_Calibration.md` (stage doc),
  `RADIANT_Signal_Chain_Architecture.md`, `RADIANT_Parameter_System.md`,
  `RADIANT_Master_Architecture.md`, `CLAUDE.md`.
