# RADIANT Metrics

**Status**: Authoritative — first design pass
**Scope**: Every output metric RADIANT produces, with formulas, required inputs, applicable regimes, units, typical values, and failure modes. Plus the metric plugin interface.
**Sister documents**: RADIANT_Conventions.md, RADIANT_Signal_Chain_Architecture.md, RADIANT_Source_Target_System.md, RADIANT_Atmosphere.md, RADIANT_Optics.md, RADIANT_Spatial_Complete.md, RADIANT_Detector_Complete.md, RADIANT_Metric_Dependencies.md

---

## 1. Design Philosophy

1. **A metric is a pure function of `ChainState`.** No metric reaches outside the chain to read parameters directly. If a metric needs a parameter, that parameter must be visible in `ChainState` because some upstream stage put it there.
2. **Metrics declare their dependencies.** Each metric carries a `requires()` method returning the set of `ChainState` keys it needs. The parameter resolver uses this to validate the user's config *before* running the chain ("CSNR requires `target.area_m2`; you didn't set it").
3. **Metrics declare their applicable regimes.** SNR's signal equation differs by regime; NEDT is meaningless for visible-band reflective targets. Each metric has a `regimes()` method and the framework refuses to compute it outside its regime, with a clear message.
4. **Failure modes are explicit.** Every metric has documented failure conditions (saturation, division by zero, regime mismatch). When a failure condition is hit, the metric returns a `MetricResult` with `value=NaN` and `failure_reason` set, never a misleading number.
5. **Plugins are first-class.** Built-in metrics use the same plugin interface as user-supplied metrics. There is no special-cased "core metric" path.

---

## 2. The Metric Metadata Contract

> **Implementation status (2026-07-11, Gap 71):** the shipped contract is
> `MetricRecord` + the registry (§6) — every computed metric key carries a
> non-empty unit, description, and kind, joined to its value by
> `ChainResult.metric_records()`. The richer per-computation `MetricResult`
> below (regime, `failure_reason`, `derivation_chain`, `inputs_used`) remains
> a design target: `state.metrics` stays `Mapping[str, float]`, and
> result-typed failures live in the per-metric result objects
> (`SNRResult.failure_reason`, `NEDTResult.failure_reason`, …) stored in
> `stage_outputs["performance"]`.

```python
# Shipped (radiant.io.results):
@dataclass(frozen=True)
class MetricRecord:
    name: str          # exact key in result.metrics
    value: float
    unit: str          # never empty — project hard rule
    description: str
    kind: str          # "float" | "flag" (0/1) | "code" (enum-as-float)

result.metric_records()  # tuple[MetricRecord, ...], sorted by name;
                         # raises KeyError on a registry-drift key (CU-078 tripwire)
```

Design target (unimplemented — do not call):

```python
@dataclass(frozen=True)
class MetricResult:
    name: str
    value: float | np.ndarray
    unit: str
    regime: RadiometricRegime | None
    failure_reason: str | None
    derivation_chain: tuple[str, ...]
    inputs_used: dict[str, Any]                 # snapshot of every chain-state field consumed
```

In the target design every metric returns one of these; `value=NaN` with `failure_reason` set is a successful "I cannot compute this for the given config" — distinct from a thrown exception, which means RADIANT itself is broken.

---

## 3. The Metric Plugin Interface **[DESIGN-TARGET]**

> **Not implemented.** There is no `Metric` ABC and no `radiant.plugins.metric`
> entry point (the `plugins/` package was removed 2026-07-06). Built-in metrics
> are plain functions under `radiant/performance/` invoked by `PerformanceStage`
> and described by the `MetricSpec` registry (§6); plugin entry-point loading is
> v2-deferred (§6 says so). Rule 5 "plugins are first-class" (§1) is design intent.
> The ABC below is the planned interface.

```python
# DESIGN-TARGET — not in the codebase
class Metric(ABC):
    name: str                          # canonical name; used as dict key
    unit: str
    description: str

    @abstractmethod
    def requires(self) -> frozenset[str]:
        """ChainState keys (dotted) that must be present."""

    @abstractmethod
    def regimes(self) -> frozenset[RadiometricRegime]:
        """Regimes in which this metric is meaningful."""

    @abstractmethod
    def compute(self, state: ChainState) -> MetricResult: ...
```

Built-in metrics live under `radiant.performance.metrics` and register themselves on import. User plugins register via the `radiant.plugins.metric` entry point in `pyproject.toml`. The plugin loader validates that `name` is unique and that `requires()` returns only known keys (no typos).

---

## 4. Built-in Metrics

The full v1 catalog. For each: formula, inputs, regimes, units, typical values, failure modes.

### 4.1 SNR — Signal-to-Noise Ratio

**Formula** (regime-dependent; see RADIANT_Signal_Chain_Architecture.md §4):

```
Extended:    S = L_target × A × Ω_pixel × τ_atm × τ_opt × QE × t_int × λ/(hc)   [integrated]
Point:       S = (I_target / R²) × A × τ_atm × τ_opt × QE × EE_box × t_int × λ/(hc)
Sub-pixel:   S = ff · S_extended × EE_box + (1−ff) · S_extended_bg
SNR = S / σ_total
```

**Required inputs:** `state.frames["at_target"].spectral_radiance`, `state.optics.A_collect`, `state.optics.omega_pixel_sr`, `state.atmosphere.transmittance`, `state.optics.transmission`, `state.detector.qe`, `state.timing.integration_time_s`, `state.detector.sigma_total_e`. EE_box and ff for non-extended regimes.

**Regimes:** all three.

**Unit:** dimensionless.

**Typical values:** 10–10⁴ for trade studies; ≥ 100 for "good imaging"; ~6 for the classical detection threshold.

**Failure modes:**
- `σ_total = 0` (no noise sources active) → returns `inf` with reason "noiseless configuration."
- Saturation at well or ADC → returns the *clipped* SNR with reason "signal saturated; SNR is for clipped signal."
- Regime mismatch returns NaN.

### 4.2 NEΔT — Noise-Equivalent Differential Temperature

**Formula:**
```
NEΔT = σ_total / (dS/dT)
dS/dT = ∫ [signal integrand](λ) · (∂B/∂T)/B (λ, T) dλ × (t_int, EE factors)
```
The temperature sensitivity is the Planck **log-derivative** `(∂B/∂T)/B` of
the target's blackbody function — in which emissivity and atmospheric
transmission cancel — weighting the actual in-band signal integrand
(`SpectralIntegrationStage.stage_outputs["ds_dt_e_per_K"]`, Gap 43). This
is the exact band integral; it reduces **exactly** to the single-λ
Planck-factor form `NEΔT = T / (SNR · x·eˣ/(eˣ−1))`, `x = hc/(λ_eff k_B T)`,
in the narrow-band limit (`performance.nedt.compute_nedt_from_snr`, the
fallback when no target temperature is available).

**Required inputs:** everything for SNR plus `target.temperature_K`. Specifically requires that the target *has* a thermal source (either `ThermalSource` or `CombinedSource`); raises NaN with reason "no thermal contribution" otherwise.

**Regimes:** extended (most common); also valid in sub-pixel using the contrast form `NEΔT = NEΔL / (dL/dT)`.

**Unit:** K (kelvin).

**Typical values:** 0.020–0.100 K for well-cooled MWIR/LWIR thermal imagers; 0.5–2 K for uncooled microbolometers.

**Failure modes:**
- `dS/dT < 1e-12 e⁻/K` (effectively no thermal sensitivity at this wavelength) → NaN with reason "thermal contrast vanishes in band."
- Reflective-band sensors (visible) on a 300 K target → very large value, computed honestly.

### 4.3 NEΔL — Noise-Equivalent Differential Radiance

**Formula:**
```
NEΔL = σ_total / (dS/dL)
where dS/dL = A · Ω · τ_atm · τ_opt · QE_band · t_int  (in-band scalar)
```

**Required inputs:** SNR inputs.

**Regimes:** extended (and meaningfully sub-pixel with fill-fraction weighting).

**Units:** spectral form W/m²/sr/µm; band-integrated form W/m²/sr.

**Typical values:** 10⁻⁵–10⁻³ W/m²/sr/µm in MWIR.

**Failure modes:** none beyond SNR's.

### 4.4 NEΔρ — Noise-Equivalent Reflectance Difference

**Formula:**
```
NEΔρ = σ_total / (dS/dρ)
dS/dρ = E_solar_in_band · cos(θ_sun) / π · A · Ω · τ_atm² · τ_opt · QE · t_int
                                            (the τ_atm² is round-trip)
```

**Required inputs:** SNR inputs plus solar geometry (`geometry.solar_zenith_deg`) and reference solar spectrum.

**Regimes:** extended (reflective-band imaging).

**Unit:** dimensionless (reflectance units).

**Typical values:** 0.001–0.01 for well-designed visible/SWIR sensors.

**Failure modes:**
- Night-side / solar zenith ≥ 90° → NaN with reason "no solar illumination."
- Thermal-only band (LWIR) → NaN with reason "reflective metric in non-reflective band."

### 4.5 CSNR — Contrast SNR (sub-pixel target)

**Formula:**
```
ΔS = ff · (S_target − S_background) · EE_box     (electrons of contrast)
σ_total = (per detection regime, including clutter)
CSNR = ΔS / σ_total
```

`ff` is the fill fraction (target angular area / pixel angular area). EE_box couples sub-PSF behavior.

**Required inputs:** target and background sources both populated; `state.optics.ee_box`; target angular extent; pixel solid angle.

**Regimes:** sub-pixel (and edge case point source where EE_box is the only spatial term).

**Extended regime (ADR-0005, Gap 52):** by default the extended `contrast_snr` reports the whole-scene SNR (there is no adjacent background — Decision #13). Setting `source.contrast_reference.temperature > 0` supplies the uniform scene in the *neighbouring* extended pixel and makes it a true two-pixel spatial differential:
```
ΔS       = S_target − S_reference
σ_contrast = √(N_target² + N_reference²)      (N_ref² = N_t² − S_t + S_ref)
contrast_snr = ΔS / σ_contrast
```
It nulls at the radiance crossover `ε_t·B(λ,T_t) = ε_r·B(λ,T_r)`. The reference is metric-only — it never enters the noise budget, so the absolute SNR (and Decision #13's pinned anchors) are unchanged. `source.contrast_reference.*` is explicitly **not** the Decision-#15 `source.background.*` nor the Decision-#13 `BackgroundDescriptor`. Combined noise is exact for staring sensors; first-order for TDI/binned readouts.

**Unit:** dimensionless.

**Typical values:** 6–30 for detectable subpixel targets.

**Failure modes:**
- `ff > 1` → falls back to extended-regime SNR with informational note.
- `σ_total` includes clutter (`detector.clutter_sigma > 0`), and the user's noise regime is `imaging` → warning "clutter not in σ_total because regime=imaging; CSNR may be optimistic."

### 4.6 NIIRS — National Imagery Interpretability Rating Scale

**Formula** (GIQE-5):
```
NIIRS = c0 + c1·log10(GSD_inch)
              + c2·log10(RER_geometric)
              + c3·log10(SNR)
              + c4·H            (overshoot)
              + c5·G            (noise gain from MTFC)
where:
  GSD_inch = √(GSD_along · GSD_cross) · 39.37
  RER_geometric = √(RER_along · RER_cross)
  c0..c5 = GIQE-5 coefficients (published)
```

**Required inputs:** GSD (from optics + platform geometry), RER (from spatial), SNR, H, G (defaults if no MTF compensation declared).

**Regimes:** extended only (NIIRS is an interpretability scale for imagery, not detection).

**Unit:** dimensionless (NIIRS scale, ~0–9).

**Typical values:** 4–7 for civil aerial; 6–8 for commercial space; 8–9 for tactical military.

**Failure modes:**
- `RER ≤ 0` → NaN with reason "non-positive RER; PSF may be over-blurred to the point of ill-conditioning."

**Frequency-axis units (Gap 27).** PSF-path MTF curves (`stage_outputs["performance"]["mtf_freq_x/y"]`) are in cycles/m on the focal plane; the product-path grid (`ChainState.spatial_freq_cycles_per_mrad`) is in cycles/mrad. `performance/frequency_units.py` provides `convert_spatial_frequency(freq, from_unit, to_unit, pixel_pitch_m=, focal_length_m=)` across cy/m ↔ cy/mm ↔ cy/mrad ↔ cy/pixel for plotting and export.

**Sensitivity analysis (Gap 20).** `performance/giqe_sensitivity.py` provides `giqe5_sensitivity(gsd_m, rer, snr, h, g)` → `GIQESensitivity` with analytic partials (d(NIIRS)/d(GSD) = c1/(GSD·ln10), d/d(RER) = c2/(RER·ln10), d/d(SNR) = c3/(SNR·ln10), d/dH = c4, d/dG = c5) plus exact per-+1% NIIRS deltas. Pure function — not a chain metric; validated against central finite differences of `compute_giqe5`.

**Calibration range (Gap 22 / CU-166).** GIQE-5 is a fit; outside its published fit ranges (Harrington et al. 2015) the value is an extrapolation, not a measurement. Checked ranges: GSD 3–80 cm (1.18–31.5 inch), RER 0.2–0.95, SNR 2–130 — both ends. **Applicability gate (CU-166 approach 2, owner-ratified 2026-07-20 — strict refusal):** when any input is out of range, NIIRS is **not applicable** by default — no `niirs` metric is emitted; `stage_outputs["performance"]["niirs_result"]` carries an ADR-B result-typed `failure_reason` (naming the offending input(s) and the opt-in), `GIQEResult.applicable` is False, and the computed extrapolated value stays on `GIQEResult.niirs` for inspection (Rule 16). Setting `performance.niirs.allow_extrapolated = true` (default false) restores the extrapolated value as a `niirs` metric. Either way `GIQEResult.extrapolated` is True with per-input strings in `GIQEResult.warnings`, and `result.metrics["niirs_extrapolated"]` is 1.0 (else 0.0) — it describes the configuration, which is known regardless. The IIRS (MWIR/LWIR) dispatch inherits the same checks and gate; note the v1 IIRS is the GIQE-5 functional form and envelope verbatim — a real IR-calibrated IIRS (own coefficients, ranges, and labeling) is tracked as Gap 100. The out-of-range condition is carried as **structured status only** — the chain emits no `UserWarning` (nor `logger.warning`) for it: a metric outside its own calibration band is a property of the configuration, not a per-evaluate event (owner bar 2026-07-18: a valid, nominally-operating scenario evaluates warning-free).

### 4.7 RER — Relative Edge Response

**Formula:**
```
RER_along = ERF_along(0.5 · pitch_along) − ERF_along(−0.5 · pitch_along)
RER_cross = ERF_cross(0.5 · pitch_cross) − ERF_cross(−0.5 · pitch_cross)
RER       = √(RER_along · RER_cross)            (geometric mean per GIQE-5)
```

ERF comes from `EffectivePSF.erf(axis)` per RADIANT_Spatial_Complete.md. By definition, ERF and RER use the *same* PSF as MTF and EE.

**Required inputs:** `state.psf` (target PSF in tracked mode; only PSF in untracked).

**Regimes:** extended; meaningfully reported in any regime as a sharpness diagnostic.

**Unit:** dimensionless.

**Typical values:** 0.4–0.9. Below 0.2 implies severe under-sampling or smear.

**Failure modes:** none; always computable when a PSF exists.

### 4.8 Edge slope

**Formula:** maximum of `dERF/dx` along each axis, in units of contrast per arcsec or per FPA-meter (both reported).

**Required inputs:** `state.psf`.

**Regimes:** all.

**Units:** 1/arcsec or 1/m.

**Typical values:** sensor-dependent.

**Failure modes:** none.

### 4.9 MTF (system MTF, evaluated at request points)

**Formula:** `MTF_system(f) = Π_i MTF_i(f)` per RADIANT_Spatial_Complete.md §9. Evaluated at user-requested spatial frequencies (Nyquist, half-Nyquist, custom).

**Required inputs:** `state.mtf_terms` populated.

**Regimes:** all.

**Unit:** dimensionless.

**Failure modes:**
- Frequency above grid Nyquist → NaN with reason "above sampled Nyquist; refine `psf_oversample`."

### 4.10 EE — Encircled (or rather Ensquared) Energy

**Formula:** `EE_nxn = ∫∫_{n×n pixels centered} psf dxdy`. Registered variants: `ee_1x1` (often called EE_box) and `ee_3x3` only (see §6 / the metric registry). Larger boxes and an `ee_vs_offset(pitch)` sweep are not computed in v1.

**Required inputs:** `stage_outputs["optics"]["effective_psf"]` (registry: `ee`).

**Regimes:** all.

**Unit:** dimensionless [0, 1].

**Typical values:** EE_1×1 ranges 0.10–0.85 depending on Q (`λ·f# / pitch`).

**Failure modes:** none.

### 4.11 Strehl ratio (PSF-derived)

**Formula:** `effective_psf.peak / reference_psf.peak`, both normalized to unit volume (Rule 4: spatial-domain metric from the shared `EffectivePSF`). The reference is the diffraction-limited PSF from the same pupil with WFE = 0, carrying the **same detector kernels** as the degraded PSF, published by OpticsStage as `stage_outputs["optics"]["reference_psf"]`.

**Required inputs:** `stage_outputs["optics"]["effective_psf"]` **and** `stage_outputs["optics"]["reference_psf"]` (registry: `strehl`).

**Regimes:** all (more meaningful for low-WFE systems).

**Unit:** dimensionless [0, 1].

**Typical values:** 0.8 for "diffraction-limited"; 0.4–0.8 for "well-corrected."

**Failure modes:** none.

### 4.11b Strehl ratio — Marechal diagnostic (`strehl_marechal`)

**Formula:** `exp(-(2π · OPD_rms / λ)²)` with `OPD_rms = wfe_rms_waves × λ_ref` — the analytic small-aberration Marechal approximation (`radiant/performance/strehl.py::compute_strehl`). Distinct from `strehl` (§4.11): it is computed from the scalar WFE RMS alone and ignores obscuration, defocus, jitter, and smear.

**Required inputs:** `stage_outputs["optics"]["wavefront_error"]` (registry: `strehl_marechal`).

**Regimes:** all. Valid for WFE ≲ λ/5 (Strehl ≳ 0.8); underestimates Strehl for larger aberrations.

**Unit:** dimensionless [0, 1].

**Typical use:** fast sanity diagnostic against the PSF-derived `strehl`; large disagreement indicates non-WFE degradations (obscuration, defocus) dominating the peak.

**Failure modes:** none (returns 1.0 for zero WFE).

### 4.12 Point source detection range

> **Implementation status (2026-07-11, Gap 77):** wired in-chain as the
> `detection_range_m` metric, computed only in the point-source regime.
> `PerformanceStage._compute_detection_range_metric` bisects the
> Beer-Lambert solver (`performance.detection_beer_lambert`) using the
> current signal/noise at `source.range_m` as the reference and
> `performance.detection_snr_threshold` (default 5.0) as the target. The
> extinction is **constant**: `α = −ln(τ̄)/R` from the band-mean in-band
> transmittance — exact in vacuum (α = 0, pure inverse-square) and a
> first-order model for atmospheric paths. The full geometry-aware
> spherical-Earth slant-path solve (α varying along the path, τ_atm(R)
> recomputed per range) described below is the deferred refinement.
>
> **Update (2026-07-27, Geometry Flexibility Phase 3, finding GF-15):** the
> helper now dispatches on the **derived LOS direction** that `GeometryStage`
> publishes (`stage_outputs["geometry"]["los_direction"]`) — not on the scene
> class, which guardrail G3 forbids branching on inside `performance/`.
> `down` (and any run without a published direction) takes the constant-α
> solver above, unchanged and bit-identical. `up` and `level` take the
> **path-aware** solver `performance.detection_path_aware`, whose τ(R) comes
> from `performance.path_optical_depth` — a piecewise profile that knows where
> the ray leaves the modelled column (`h_atm_top`) and stops accruing optical
> depth there. Its search bound is analytic rather than a fixed ceiling: since
> τ(R)/τ(R_ref) ≤ 1 always, the detection range can never exceed the vacuum
> answer `R_ref·√(SNR_ref/threshold)`, which makes the bisection bracket
> provably root-containing. Three path shapes are solvable — a **level** arm
> (constant altitude ⇒ constant density ⇒ constant extinction is the arm
> model's *own* assumption, so it is exact, bounded by the ADR-0011 2 km
> tangent-sag ceiling ≈ 319 km), an **up-looking** path whose target already
> sits at or above `h_atm_top` (vacuum tail, exact), and a **transparent**
> path. An up-looking path whose continuation is still inside the column is
> **refused** with a named `failure_reason` (ADR-B result-typed failure) rather
> than answered with the constant-α model — that substitution is exactly the
> error GF-15 reports. Migrating the down-looking arm would move every existing
> point-source golden result and is an owner decision.

**Formula:** Solve for the range R at which SNR equals the user's `performance.detection_snr_threshold`:
```
S(R) = S_ref · (R_ref / R)² · exp(−α · (R − R_ref))      # constant-α (implemented)
R_detect = R such that S(R) / σ_noise = threshold
```
The design target recomputes `τ_atm(R)` along the slant path each iteration; the framework solves either form with a 1-D bisection.

**Required inputs:** point-source signal + noise from the chain, `source.range_m`, band-mean `tau_atm`, `performance.detection_snr_threshold`.

**Regimes:** point only (raises NaN otherwise).

**Unit:** m.

**Typical values:** 10²–10⁶ m depending on system and target.

**Failure modes:**
- No solution in bracket → NaN with reason "target not detectable at any range" or "target detectable at all ranges."
- Atmospheric model is `tabulated` (geometry-frozen) → NaN with reason "detection range requires geometry-aware atmosphere."

### 4.13 Saturation margin (well, ADC)

**Formula:**
```
margin_well_dB = 20 · log10(FWC / S_signal_e)
margin_adc_dB  = 20 · log10(adc_full_scale_dn / S_signal_dn)
```

**Required inputs:** `state.detector.signal_e_per_pixel`, `state.detector.full_well_capacity_e`, `state.detector.signal_dn`, `state.detector.adc_full_scale_dn`.

**Regimes:** all.

**Unit:** dB.

**Typical values:** ≥ 6 dB for "comfortable headroom"; negative is saturated.

**Failure modes:**
- `signal ≤ 0` (e.g., dark scene) → returns +∞ with reason "no signal."
- Already-saturated config → returns negative dB and a warning.

### 4.14 Dynamic range

**Formula:**
```
DR_dB = 20 · log10(FWC / σ_temporal_dark)
```
where `σ_temporal_dark` is the temporal noise evaluated at zero signal (dark frame).

**Required inputs:** `state.detector.full_well_capacity_e`, dark-condition `σ_temporal_e`.

**Regimes:** all.

**Unit:** dB.

**Typical values:** 60–80 dB for science detectors; 50–60 dB for commercial.

**Failure modes:** none.

### 4.15 Target-plane sample distance (non-ground counterpart of GSD)

> **Implementation status (2026-07-27, Geometry Flexibility Phase 3, finding
> GF-13):** wired in-chain as `target_plane_sample_distance_x_m` /
> `_y_m` / `_geometric_mean_m` (module
> `performance/target_plane_sample_distance.py`, Rule 19). Surfaced by default
> only for a **non-ground target** — see §7a.1.

**Formula:** the pixel's angular subtense projected at the slant range, in the
plane through the target **normal to the line of sight** — GSD without the
ground-plane `cos` projection, because an air or space target has no ground
plane:
```
IFOV_x = pitch_x / f                       [rad]
d_x    = R · IFOV_x = pitch_x · R / f      [m]
d_y    = R · IFOV_y = pitch_y · R / f      [m]
d_mean = √(d_x · d_y)                      [m]
```

**Required inputs:** `detector.pixel_pitch_x_um` / `_y_um` (canonical m),
`optics.focal_length_m`, and the slant range `GeometryStage` publishes
(`stage_outputs["geometry"]["slant_range_m"]`, ADR-0006). No incidence angle —
that absence is precisely why the metric is defined where GSD is not.

**Regimes:** all. **Unit:** m.

**Typical values:** cm–m for airborne air-to-air; 10⁰–10³ m for space-to-space
(≈ 360 m for a 10 µrad IFOV at GEO range).

**Relation to GSD:** identical at `incidence = 0`; off-axis, GSD's along-track
axis is longer by `1/cos(incidence)`. The metric deliberately carries **no**
target-body orientation term: it answers "how far apart are adjacent pixel
samples where the target is", which range and optics determine uniquely, not
"how much of the target's skin does a pixel cover", which needs an attitude the
framework does not carry (GF-5). The name *target-plane* rather than
*target-surface* keeps that distinction visible.

**Failure modes:** any non-positive or non-finite pitch, focal length, or slant
range raises `PerformanceValidationError` (Rule 16). The chain helper skips
silently when the geometry stage published no slant range or the optics /
detector parameters are unset.

---

## 5. Cross-cutting: How metrics see the chain state

A metric reads from `ChainState` only via documented keys. The key map below is
**illustrative** — the authoritative, CI-enforced dependency contract is each
metric's `MetricSpec.requires_frames` / `requires_stage_outputs` /
`requires_noise_terms` / `requires_metrics` / `requires_mtf_terms` in the registry
(§6). Note the rows for `stage_outputs["spatial"]`, `stage_outputs["timing"]`,
and the `OpticsState` / `DetectorState` / `TimingState` objects are
**design-target**: there is no `spatial` or `timing` stage (spatial physics is
distributed, §Spatial §0) and those State dataclasses are not implemented — the
real keys are `stage_outputs["optics"]["effective_psf"]` / `["reference_psf"]`,
`stage_outputs["platform"]["EE_box"]`, and `mtf_terms[...]`.

| Key | Meaning |
|-----|---------|
| `frames["at_target"].spectral_radiance` | Source radiance, before atmosphere |
| `frames["at_aperture"].spectral_radiance` | After atmosphere, at entrance pupil |
| `frames["at_fpa"].spectral_radiance` | After optics, at the FPA |
| `stage_outputs["source"]["regime_tentative"]` | Source's tentative regime |
| `stage_outputs["atmosphere"]["state"]` | Full `AtmosphericState` |
| `stage_outputs["optics"]["state"]` | Full `OpticsState` |
| `stage_outputs["optics"]["ee_box"]` | EE in pixel footprint |
| `stage_outputs["timing"]["state"]` | Full `TimingState` |
| `stage_outputs["detector"]["state"]` | Full `DetectorState` |
| `stage_outputs["spatial"]["psf"]` | `EffectivePSF` (target PSF in tracked) |
| `stage_outputs["spatial"]["psf_background"]` | Background PSF (tracked only) |
| `mtf_terms[<term>]` | Individual spatial MTF arrays |
| `metrics[<name>]` | Previously-computed metrics (for derived metrics) |

A metric that depends on a key not in this list is malformed and the loader rejects it.

---

## 6. The metric registry

The registry lives in `radiant/performance/registry.py` (reconciled with the shipped chain 2026-07-11, Gap 71 + CU-078). Each metric is described by a frozen `MetricSpec` and registered into the module-level `METRIC_SPECS` dict at import time:

```python
@dataclass(frozen=True)
class MetricSpec:
    name: str                                # exact state.metrics key
    unit: str                                # non-empty, human-readable
    description: str
    kind: str = "float"                      # "float" | "flag" | "code"
    requires_frames: frozenset[str] = frozenset()
    requires_stage_outputs: frozenset[tuple[str, str]] = frozenset()
    requires_noise_terms: bool = False
    requires_metrics: frozenset[str] = frozenset()
    requires_mtf_terms: bool = False
    regimes: frozenset[str] = frozenset()    # empty = all regimes

METRIC_SPECS: dict[str, MetricSpec]          # one spec per computable key

def metric_info(name: str) -> MetricSpec: ...
def can_compute(metric_name: str, state: ChainState) -> bool: ...
def available_metrics(state: ChainState) -> set[str]: ...
def missing_for(metric_name: str, state: ChainState) -> dict[str, list[str]]: ...
```

**Reconciliation contract:** the catalog registers exactly the keys `PerformanceStage` can write — `snr`, `contrast_snr`, `scnr` (Gap 77 — clutter-inclusive detection FoM), `detection_range_m` (Gap 77 — point-source only), `nedt_K`, `mrt_at_nyquist_K`, `fwhm_x_m`, `fwhm_y_m`, `rer`, `ee_1x1`, `ee_3x3`, `mtf_at_nyquist`, `strehl`, `strehl_marechal`, `mtf_system_at_nyquist_x/_y`, `mtf_folded_at_nyquist`, `alias_fraction_at_nyquist`, `niirs`, `niirs_extrapolated`, `well_margin_dB`, `adc_margin_dB`, `dynamic_range_dB`, `gsd_cross_track_m`, `gsd_along_track_m`, `gsd_geometric_mean_m`, `ground_range_m`, `swath_width_m`, `access_rate_m2_s`, `q_center`, `q_min`, `q_max`, `sampling_regime_code`, `diffraction_limit_angular_urad`, `diffraction_limit_ground_m`, `max_integration_time_s` (Gap 74 — pushbroom/TDI dwell limit, parameter-gated on a ground velocity). Enforced by `tests/integration/test_metric_registry_reconciliation.py`: a chain run producing an unregistered key fails CI, and `can_compute` must return True for every key the chain actually computed. Designed-but-not-computed metrics (NEΔL, NEΔρ, edge slope, Johnson DRI, Pd/ROC, D\*/NEP/NEI — Gap 78) are **not** registered; they enter with the commit that computes them. (`detection_range_m` and `scnr` landed with Gap 77, 2026-07-11.)

`can_compute` covers state-level dependencies only; several metrics (GSD family, Q family, diffraction limits) are additionally parameter-gated (positive altitude, focal length, …). The **GSD family is additionally geometry-gated on the LOS direction**: ground sample distance is the ground footprint of one pixel, which exists only when the line of sight meets a ground plane below the sensor, so `gsd_cross_track_m` / `gsd_along_track_m` / `gsd_geometric_mean_m` are not published for an up-looking (θ_o > π/2) or level (θ_o = π/2) scene. `PerformanceStage` reads the `los_direction` label GeometryStage derives (ADR-0011 decision 1) and skips the metric, rather than letting `compute_gsd_from_geometry`'s `[0, π/2)` validator raise and abort the whole evaluation. By the dependency-closure rule below this also withholds `niirs`, which needs `gsd_*` — correctly, since NIIRS is a ground-imagery interpretability scale. `diffraction_limit_ground_m` is **not** gated this way: despite its name it is `angular × slant_range` with no ground projection, so it stays meaningful up-looking (the naming mismatch is tracked as CU-231). The production consumer is `ChainResult.metric_records()` (§2), which joins each computed value with its spec. Plugin entry-point loading is v2-deferred, and there is currently no `radiant metrics` CLI subcommand; `available_metrics(state)` / `missing_for(name, state)` are the programmatic equivalents.

---

## 7. Validation of metric inputs

After a chain runs, `missing_for(metric_name, state)` (`radiant/performance/registry.py`) reports exactly which dependencies a metric lacks, keyed by category:

```python
missing_for("csnr", state)
# {
#   "frames": ["photoelectrons"],
#   "stage_outputs": ["spectral_integration.contrast_e"],
# }
```

`available_metrics(state)` returns the set of metric names whose dependencies are all satisfied for the given state.

Compare to RADIANT_Metric_Dependencies.md, which is the *static* form of this same information for all built-in metrics.

---

## 7a. Metric selection — which metrics are computed and surfaced (Gap 96)

The analyst chooses *which* metric families the chain computes and surfaces via five boolean **group flags** in the performance schema (`radiant/performance/_schema.py`). Turning a group off truly stops the *computation* of its metrics — and any warnings they would emit — not merely their display: `PerformanceStage.run` gates each `_compute_*` helper on the selection, so a deselected metric produces no value.

| Parameter (`bool`, default `True`) | Group | Surfaced metrics |
|---|---|---|
| `performance.metrics.radiometric` | Radiometric | `snr`, `contrast_snr`, `scnr`, `detection_range_m`, `nedt_K` |
| `performance.metrics.spatial_mtf` | Spatial / MTF | `fwhm_x_m`, `fwhm_y_m`, `rer`, `ee_1x1`, `ee_3x3`, `mtf_at_nyquist`, `strehl`, `strehl_marechal`, `mtf_system_at_nyquist_x/_y`, `mtf_folded_at_nyquist`, `alias_fraction_at_nyquist` |
| `performance.metrics.interpretability` | Interpretability | `niirs`, `niirs_extrapolated`, `mrt_at_nyquist_K` |
| `performance.metrics.sampling` | Sampling / geometry | `gsd_cross_track_m`, `gsd_along_track_m`, `gsd_geometric_mean_m`, `target_plane_sample_distance_x_m`, `target_plane_sample_distance_y_m`, `target_plane_sample_distance_geometric_mean_m`, `ground_range_m`, `swath_width_m`, `access_rate_m2_s`, `q_center`, `q_min`, `q_max`, `sampling_regime_code`, `diffraction_limit_angular_urad`, `diffraction_limit_ground_m`, `max_integration_time_s` |
| `performance.metrics.saturation` | Saturation | `well_margin_dB`, `adc_margin_dB`, `dynamic_range_dB` |

**Surfaced vs. compute (the dependency-closure rule).** Metrics are not independent — `niirs` needs `snr` + `rer` + `gsd_*`; `mrt_at_nyquist_K` needs `nedt_K` + `mtf_at_nyquist`; `nedt_K`/`scnr`/`detection_range_m` need `snr`. The **effective compute set is the transitive closure of the enabled (surfaced) set over the inter-metric dependency graph**, and a metric is *surfaced* (emitted in `result.metrics` and shown in the GUI) iff its group is enabled. So enabling only Interpretability auto-computes `snr`/`rer`/`gsd_*` (needed for NIIRS) but does **not** surface them; disabling Interpretability stops the NIIRS compute (and any of its warnings) entirely.

The dependency graph is **not** re-declared for this feature — it is derived from each `MetricSpec.requires_metrics` (§6, the single source of metric metadata). Only the group→metric partition is declared, in `radiant/performance/metric_selection.py` (`METRIC_GROUPS`, `GROUP_PARAMS`, `resolve_selection`), and `test_metric_selection.py` asserts it partitions `METRIC_SPECS` exactly. The view layers reach it through `radiant.api.metric_groups` (import-linter forbids `gui` → `performance`).

Default selection is **all groups on**, so the change is additive and alters no golden result. It is an analyst override: the engine-side applicability defaults that make a valid scenario clean *before* the user touches anything are CU-166.

### 7a.1 Scene-class relevance defaults (Geometry Flexibility Phase 3, guardrail G3)

The group flags are an *analyst* choice. Layered underneath them is an **engine-side default**: a declarative map from the derived scene class to the metrics whose default relevance is off, in `radiant/performance/scene_relevance.py`. Guardrail G3 of the Geometry Flexibility plan makes its shape binding — **one map, consulted once** by `PerformanceStage.run`; per-metric `if scene_class == ...` branches inside `performance/` modules are review-blocking. Physics never consults it (ADR-0011 decision 8): the class drives defaults, metric relevance, validation, and GUI composition only.

The discriminator is the **target** altitude band, not the observer's: GSD, ground range, swath width, access rate, `diffraction_limit_ground_m`, `max_integration_time_s`, and NIIRS/GIQE are all defined by projecting the sample footprint onto the *target's* ground plane through `incidence_angle_rad ∈ [0, π/2)`, which an air or space target does not have whichever band the observer occupies.

| Target band | Metrics off by default |
|---|---|
| `ground` (`*_to_ground`) | `target_plane_sample_distance_x_m`, `..._y_m`, `..._geometric_mean_m` |
| `air`, `space` (`*_to_air`, `*_to_space`) | `gsd_cross_track_m`, `gsd_along_track_m`, `gsd_geometric_mean_m`, `ground_range_m`, `swath_width_m`, `access_rate_m2_s`, `diffraction_limit_ground_m`, `max_integration_time_s`, `niirs`, `niirs_extrapolated` |

Every other metric — radiometric, spatial/MTF, saturation, the sampling parameter Q, the sampling-regime code, and the *angular* diffraction limit — is band-independent and stays on for all nine classes.

**Override semantics are unchanged.** The map conditions a group only while that group's `performance.metrics.*` flag still carries `Provenance.DEFAULT`; a flag the analyst set explicitly wins outright, including into an actionable refusal (opting `sampling` back on for an up-looking scene surfaces GSD's `incidence_angle_rad ∈ [0, π/2)` rejection, as it always did). Suppression applies to *surfacing* only: a suppressed metric that a surfaced metric depends on is still computed, exactly like any other hidden prerequisite.

**Zero drift.** For every `*_to_ground` class the off-set contains only the target-plane metrics this phase introduced — keys that did not exist before — so a ground-target scene's default selection is bit-identical to the pre-Phase-3 one. A run with no published scene class (a partial fixture without `GeometryStage`) falls back to the ground rule.

---

## 8. Out of Scope for v1

- Hyperspectral metrics (spectral angle mapper, spectral correlation).
- Radiometric calibration metrics (NEΔ-relative-to-blackbody-source).
- Track-mode metrics (centroiding accuracy as an output).
- Geolocation accuracy metrics (geolocation-tool concern).
- Image quality metrics requiring scene content (SSIM, PSNR vs. ground truth).

---
