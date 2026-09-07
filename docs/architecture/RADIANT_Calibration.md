# RADIANT Calibration Stage

**Scope:** the calibration error model (Gap 120, ADR-0012) — schemes, the
post-NUC residual noise terms, the bias/accuracy budget, and the stage's
structural guarantees.

**Implementation status:** Phase 2 of `docs/plans/Calibration_Model_Plan.md`
— the model is live end-to-end. Active schemes emit the residual noise
terms and bias terms on real chain runs; the post-calibration total is
published at `stage_outputs["calibration"]["sigma_total_e"]` and preferred
by SNR/CSNR (SCNR adds `sigma_calibration_e` to its spatial RSS); the
radiometric-accuracy metric (`RADIANT_Metrics.md` §4.14) consumes the bias
budget. Both ADR-0012 structural guarantees are contract-tested on full
chains (`tests/integration/test_calibration_chain.py`). `scheme = "none"`
remains bit-identical to the pre-Gap-120 chain (asserted). The dedicated GUI screen is built (plan
Phase 3 — `RADIANT_GUI_Architecture.md` §4.4.1 Calibration row; merge
gated on owner live review). Remaining: scenarios (Phase 4).

---

## 1. Position and character

`CalibrationStage` runs **between ReadoutStage and PerformanceStage**. It is
a terms-only stage (PlatformStage precedent): it transforms no frame,
collapses no spectrum, and writes no MTF term. It contributes:

- **Noise terms** — the post-NUC residual FPN family (`nuc_residual`,
  `gain_drift`, `offset_drift`), spatial, appended via `state.with_noise()`.
- **Bias terms** — the accuracy budget (`BiasTerm` via `state.with_bias()`).
- **Stage outputs** — `stage_outputs["calibration"]`: scheme, enabled flag,
  and the derived residual budget the GUI readout panel and the
  radiometric-accuracy metric consume (`s1_e`/`s2_e`, per-term residuals,
  `sigma_calibration_e`, `sigma_total_e`, `bias_total_frac`,
  `calibration_nedt_K`).

### 1.1 The ordering guarantee (do not move this stage)

ReadoutStage applies TDI/coadd/binning $\sqrt{N}$ scaling to temporal noise
terms. CalibrationStage runs after, so its residual terms are added
post-scaling and are **structurally exempt from $\sqrt{N}$ averaging** —
correlated errors do not average down. This is enforced by chain position,
asserted by contract test *(Phase 2)* , and marked in
`core/noise_budget.py::CALIBRATION_TERMS` for any future re-scaling code.

**Full-scale reference domain.** The two-point quadratic reference
``S_ref`` is taken in the same summed domain as ``signal_e_final``: the
counting ``effective_well_e`` when the DROIC branch ran, else
``readout.full_well_capacity_e`` scaled by the accumulation gain the signal
actually received (``signal_e_final / detector signal_e``). One domain for
numerator and denominator is what makes the residual's signal-relative size
TDI-invariant (the contract test).

**Noise-regime interplay.** ``detector.noise_regime = "imaging"`` excludes
pre-cal FPN as "calibrated out"; the calibration residuals are precisely
what survives that calibration, so they enter the total in **both**
regimes — contract-tested.

### 1.2 The bias/noise separation

`BiasTerm` ≠ `NoiseTerm` by type. SNR/NEDT consume `ChainState.noise_terms`
only; the radiometric-accuracy metric *(Phase 2)* consumes
`ChainState.bias_terms` only. A bias is never RSS'd into $\sigma_{total}$.
Biases from independent sources RSS *within* the accuracy budget; conversion
to K at scene temperature happens in the metric layer.

### 1.3 Rule 4 non-interaction

Residual FPN is spatial *noise*, not a spatial *degradation*: it has no PSF
kernel and no MTF term. Neither Rule 4 path gains a contributor;
`performance/consistency_check.py` is unaffected. Do not "helpfully" add an
FPN MTF term.

---

## 2. Schemes

`calibration.scheme ∈ {none, one_point, two_point}` (default `none`).

| Scheme | Meaning | Residual model |
|---|---|---|
| `none` | Model off — today's behavior. Detector `prnu`/`dsnu` terms act as static dispersions. Stage emits nothing. | — |
| `one_point` | Offset corrected at cal flux $S_1$ | gain dispersion on the departure: $\sigma = \mathrm{prnu}\cdot\lvert S-S_1\rvert$; offset re-grows by drift |
| `two_point` | Per-pixel gain+offset corrected at $S_1, S_2$ (from cal temps through the band) | quadratic-nonlinearity residual (plan §3.2, D1): parabola vanishing at both cal points |

Under an active scheme, `detector.prnu_pct` / `detector.dsnu_e_rms` are
re-read as **pre-correction** dispersions (handoff mechanism per ratified
D2 — detector emits them as stage outputs, not noise terms; no double
counting). Cal-point *fluxes* are always derived from cal temperatures —
never independent inputs.

## 3. Parameters

The `calibration.*` namespace — see `calibration/_schema.py` and
`RADIANT_Parameter_System.md`. Sentinel: cal temperatures use 0.0 = unset
(evaluate-time validation when a scheme is active). Defaults are the
`none` limit — golden results bit-identical with the model off (the plan §16
regression contract).

## 4. Errors

`CalibrationValidationError` (rejected input — e.g. inverted cal temps) vs.
`CalibrationConfigIncompleteError` (mid-switch config — active scheme with an
unset cal point; also the Phase 0 phase-gate). Message surfaces route on the
type via `is_calibration_config_incomplete` (the Gap 117 advisory pattern).

## 5. Deferred (ratified)

- FPA-ΔT-driven drift (D4 — time-linear v1 only; follow-on gap when needed).
- Ops-level calibration (cal cadence trades, scene-based NUC, onboard-source
  fore-optics exclusion) — the stage is the home when it arrives (ADR-0012).
- Partial along-column decorrelation of PRNU under long TDI (plan §14 —
  v1 takes full correlation, an upper bound on the floor).
