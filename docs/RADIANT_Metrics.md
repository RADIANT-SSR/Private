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

## 2. The `MetricResult` Contract

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

Every metric returns one of these. `value=NaN` with `failure_reason` set is a successful "I cannot compute this for the given config" — distinct from a thrown exception, which means RADIANT itself is broken.

---

## 3. The Metric Plugin Interface

```python
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
dS/dT = ∂/∂T [ ∫ ε(λ) · B(λ, T) · A·Ω·τ_atm·τ_opt·QE·λ/(hc) dλ × t_int ]
       evaluated numerically by perturbing target temperature by 0.1 K
```

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

**Unit:** dimensionless.

**Typical values:** 6–30 for detectable subpixel targets.

**Failure modes:**
- `ff > 1` → falls back to extended-regime SNR with informational note.
- `σ_total` includes clutter (`background.clutter_sigma > 0`), and the user's noise regime is `imaging` → warning "clutter not in σ_total because regime=imaging; CSNR may be optimistic."

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
- `SNR < 5` → returns the formula value but flags reason "SNR below GIQE-5 calibration range."

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

**Formula:** `EE_nxn = ∫∫_{n×n pixels centered} psf dxdy`. Variants: 1×1 (often called EE_box), 3×3, 5×5, and `ee_vs_offset(pitch)`.

**Required inputs:** `state.psf`.

**Regimes:** all.

**Unit:** dimensionless [0, 1].

**Typical values:** EE_1×1 ranges 0.10–0.85 depending on Q (`λ·f# / pitch`).

**Failure modes:** none.

### 4.11 Strehl ratio

**Formula:** `psf.max() / psf_diffraction_limited.max()`, both normalized to unit volume. The reference is built from the same pupil with WFE = 0.

**Required inputs:** `state.psf` and access to `state.optics.pupil` to construct the reference.

**Regimes:** all (more meaningful for low-WFE systems).

**Unit:** dimensionless [0, 1].

**Typical values:** 0.8 for "diffraction-limited"; 0.4–0.8 for "well-corrected."

**Failure modes:** none.

### 4.12 Point source detection range

**Formula:** Solve for the range R at which CSNR (with `ff` for a point source ≪ 1) equals the user's `detection_threshold` (default = 6):
```
S(R) = (I_target / R²) · A · τ_atm(R) · τ_opt · QE · EE_box · t_int · λ/(hc)
R_detect = R such that S(R) / σ_total(R) = threshold
```
This is an iterative solve because `τ_atm(R)` depends on slant path. The framework solves with a 1-D bisection over `R ∈ [1 m, 10⁶ m]`.

**Required inputs:** `target.intensity` (point source), `atmosphere.model`, `optics.*`, `detector.*`, plus `metric.detection_threshold`.

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

---

## 5. Cross-cutting: How metrics see the chain state

A metric reads from `ChainState` only via documented keys. The key map:

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

```python
class MetricRegistry:
    def register(self, metric: Metric) -> None: ...
    def get(self, name: str) -> Metric: ...
    def all(self) -> tuple[Metric, ...]: ...
    def applicable_to(self, state: ChainState) -> tuple[Metric, ...]:
        """Return only metrics whose requires() and regimes() match state."""
```

The registry is populated at startup by:
1. Importing `radiant.performance.metrics.builtin`, which registers the 14 metrics above.
2. Loading `radiant.plugins.metric` entry points, which register user plugins.

The CLI command `radiant metrics list` prints every registered metric with its `requires()` and `regimes()`. A user planning a study can ask "what can I get from this config?" via `radiant metrics applicable my_config.yaml` — which runs the parameter resolver, builds an empty `ChainState` shape, and returns the list.

---

## 7. Validation of metric inputs

Before running a chain, the parameter resolver collects the union of `requires()` over all requested metrics and verifies that every key will be present after the chain runs. Missing keys raise `MetricRequirementError` with a list like:

```
CSNR requires:
  ✓ frames["at_target"].spectral_radiance
  ✓ optics.A_collect
  ✗ stage_outputs["optics"]["ee_box"]      ← missing because spatial.fidelity_preset = "draft" disables EE_box
  ✗ target.area_m2                          ← missing; add target.area_m2 to your config
```

Compare to RADIANT_Metric_Dependencies.md, which is the *static* form of this same information for all built-in metrics.

---

## 8. Out of Scope for v1

- Hyperspectral metrics (spectral angle mapper, spectral correlation).
- Radiometric calibration metrics (NEΔ-relative-to-blackbody-source).
- Track-mode metrics (centroiding accuracy as an output).
- Geolocation accuracy metrics (geolocation-tool concern).
- Image quality metrics requiring scene content (SSIM, PSNR vs. ground truth).

---
