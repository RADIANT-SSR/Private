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
remains bit-identical to the pre-Gap-120 chain (asserted). The dedicated GUI screen shipped (plan
Phase 3, live-review approved 2026-09-07) and the scenarios are delivered
(Phase 4: 2.7 + the 1.4 TDI calibration variant). All plan phases landed;
follow-ons: Gap 122 (v1.1 error-budget extensions), CU-346.

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

Five bias terms exist: `source_temp` (band-Planck log-derivative ×
$\Delta T_{src}$, `cal_source_bias.py`), `source_emissivity`
($\Delta\varepsilon/\varepsilon_{src}$), `spectral_cal` (band-center
uncertainty as a rigid band shift, `spectral_cal.py` — the calibration
absorbs the scale error at its own temperature, so the residual is the
scene-vs-cal difference of band-shift log-derivatives: zero at
$T_{scene} = T_{cal}$, scene-temperature-dependent otherwise; Gap 122
item 3), `internal_cal_offset` (internal-shutter cal path — the flag
blocks the fore-optics from the cal view, so their near-field emission
returns uncorrected; the photon-weighted per-element split lives in
`internal_cal.py`, the electron magnitude rides the detector's own
`nearfield_e`, and the term is the offset over the scene signal; Gap 122
item 4, active only under `calibration.cal_path = "internal_shutter"`),
and `gain` (direct fractional input). The internal-shutter path also
emits a fifth *noise* term, `narcissus_fpn` (spatial): the
`narcissus_fpn_pct` fraction of the uncorrected fore-optics offset that
varies across the array.

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
| `three_point` | Piecewise gain+offset through $S_1, S_2, S_3$ (`cal_temp_mid_K` between low and high; Gap 122 item 2, owner-scoped to three points — beyond that is rarely done) | each bracketing segment carries **its own** nonlinearity parabola, vanishing at all three cal points and peaking at a quarter of that segment's span squared; outside the span the nearest segment extrapolates. The source-uniformity imprint (item 1) interpolates piecewise the same way |

**Cal-point declaration modes (Gap 122 item 5 — the CU-346 flux-ratio
door, delivered 2026-09-12).** `calibration.cal_point_mode ∈ {temperature,
flux_fraction}` (default `temperature`). The temperature form maps
`cal_temp_*_K` to cal signals through the band Planck photon-radiance
ratio; the flux form declares them directly as fractions of the scene
signal (`cal_flux_low/mid/high` — the integrating-sphere / flat-field
form): $S_i = f_i \cdot S_{scene}$, no thermal anchor, no CU-346
reflective-scene stand-in. Under `flux_fraction`, every
temperature-anchored input (cal temperatures, source ΔT,
`source_uniformity_K`, `band_center_uncertainty_um`, source Δε) is
**rejected as over-specification** — a flux-declared point gives them no
anchor, and a set value silently doing nothing is the failure class Rule 16
exists for. Drift, the direct gain bias, and the internal-shutter path are
temperature-free and flow unchanged in both modes.

Under an active scheme, `detector.prnu_pct` / `detector.dsnu_e_rms` are
re-read as **pre-correction** dispersions (handoff mechanism per ratified
D2 — detector emits them as stage outputs, not noise terms; no double
counting). Cal-point *fluxes* are always derived from cal temperatures —
never independent inputs.

**Reflective-scene guard (CU-346, owner-ratified 2026-09-07 — guard now,
flux-ratio door later).** The Planck mapping
$S(T_{cal}) = S_{scene} \cdot B_q(T_{cal})/B_q(T_{scene})$ anchors at the
declared scene temperature, which describes none of the collected signal when
the sensing band carries no thermal photons at that temperature (a VNIR band
at 300 K: in-band photon share $\sim 10^{-22}$; the signal is
Kirchhoff-reflected sunlight). With a scheme active, the stage then emits a
`CU-346` `UserWarning` and publishes
`stage_outputs["calibration"]["reflective_scene_cal_note"]`; the run proceeds
— residual *structure* (the correlated plateau, the $\sqrt{N}$ exemption) is
mapping-independent, only the absolute level rides the stand-in. Trigger:
`T2Reflective` descriptor, **or**
`band_thermal_photon_fraction(T_scene, band) < 10^{-9}`
(`calibration/cal_points.py`; ~$10^{-22}$ VNIR@300 K fires, ~$8\times10^{-7}$
SWIR@300 K and ~$2\times10^{-5}$ LWIR@77 K lab stay quiet). A flux-declared
cal point (integrating-sphere flat field) is inexpressible in v1 — the
flux-ratio door is tracked under Gap 122.

**Cal-source spatial non-uniformity (Gap 122 item 1, 2026-09-07).** A real
blackbody holds ±0.01–0.05 K (1σ) across its aperture; at cal time each pixel
views a slightly different source temperature and the correction imprints the
pattern. `calibration.source_uniformity_K` (1σ, default 0.0 = off,
bit-identical) drives a fourth residual noise term `cal_source_uniformity`:

$$\sigma_{unif}(S) = \Delta T_{unif} \cdot \frac{\lvert D_1 (S_2 - S) + D_2 (S - S_1)\rvert}{S_2 - S_1} \;\; \text{(two-point)}, \qquad \sigma_{unif} = \Delta T_{unif} \cdot D_1 \;\; \text{(one-point)}$$

with $D_j = dS/dT\rvert_{T_{cal,j}}$ through the band Planck-ratio mapping
(`cal_point_ds_dt_e_per_K`). The same plate is viewed at both cal points and a
cavity gradient is temperature-independent in kelvin to first order, so the two
imprints combine **linearly** (correlated), not in RSS — the documented
assumption. Unlike the NUC parabola this term does **not** vanish at the cal
points ($\sigma(S_1) = \Delta T_{unif} D_1$), retiring v1's
exactly-zero-residual-at-cal-point optimism; it enters `sigma_calibration_e`
and the post-scaling noise position (√N-exempt) like its siblings, and sets a
calibration-limited NEDT floor $\approx \Delta T_{unif}$ when it dominates.

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
- Ops-level calibration (cal cadence trades, scene-based NUC) — the stage is
  the home when it arrives (ADR-0012). The onboard-source **fore-optics
  exclusion** piece landed 2026-09-11 as the `internal_shutter` cal path
  (Gap 122 item 4, §1.2); cadence and scene-based NUC remain deferred.
- Partial along-column decorrelation of PRNU under long TDI (plan §14 —
  v1 takes full correlation, an upper bound on the floor).
