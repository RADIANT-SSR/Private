# RADIANT Signal Chain Architecture

**Date:** 2026-04-07  
**Status:** Accepted  
**Depends on:** RADIANT_Conventions.md, RADIANT_Parameter_System.md, RADIANT_Scope_Decisions.md  
**Scope:** Defines how modules compose into a signal chain, what each module produces and consumes, how the three radiometric regimes are dispatched, and how forward/backward propagation works.

---

## 1. What Is a Chain?

### Choice: **Ordered pipeline of stages with an immutable, accumulating trace.**

Not a free-form DAG. Not bare function composition. A `Chain` is an ordered list of `Stage` instances; each stage receives a `ChainState` and returns a new `ChainState`. The state is immutable per stage — every stage produces a fresh state that includes all prior state plus its own contributions.

### Justification

**Why not a DAG:**
- A DAG sounds general, but the radiometric signal chain is intrinsically sequential. Source → atmosphere → optics → detector → readout has only one valid topology. The MTF chain, the noise budget, and the spectral propagation all flow in the same direction.
- DAGs require a topological sort, dependency tracking, and a scheduler. None of that earns its keep when the topology is fixed.
- The places where the chain *appears* to branch (multiple source terms summed in MWIR; multiple noise terms in quadrature) are not graph branches — they're internal sums computed inside one stage.

**Why not bare function composition:**
- `chain = optics ∘ atmosphere ∘ source` gives no introspection. You can't ask "what was the at-aperture radiance?" once it's been pipelined into electrons.
- We need to record every intermediate quantity for the noise budget, MTF budget, and provenance chain. That requires a state object, not just function output.

**Why an immutable accumulating trace:**
- Every stage adds to the state but never overwrites prior fields. After the chain runs, the state contains a full history: source radiance, at-aperture radiance, post-optics radiance, photoelectrons, noise terms.
- Backward propagation is trivial: just look up the field from the relevant reference frame.
- Reproducibility and explainability are automatic — the state IS the audit record.

### Stages in v1

```
1. SourceStage         — assembles target/background emission and reflection; classifies regime
2. AtmosphereStage     — applies τ(λ), L_path(λ), L_atm(λ); adds turbulence MTF (ground-based only)
3. OpticsStage         — applies A, Ω, τ_opt(λ), warm-optics emission, cold stop, narcissus;
                         adds diffraction MTF, WFE/Strehl, defocus MTF, vignetting, encircled energy
4. PlatformStage       — adds smear MTF, jitter MTF, LOS drift, platform vibration, TDI alignment MTF
5. SpectralIntegrationStage — collapses spectral radiance to in-band photoelectrons per pixel;
                              applies regime-dependent spatial factors (Ω_pixel or EE_box)
6. DetectorStage       — applies QE, dark current, full well, generates noise terms;
                         adds pixel aperture MTF, IPC MTF, charge-diffusion MTF
7. ReadoutStage        — applies TDI signal gain, binning, coadds, gain, ADC; adds quantization noise;
                         finalizes noise budget
8. PerformanceStage    — composes system MTF from all accumulated MTF terms;
                         computes SNR, NEDT, RER, NIIRS, detection range
```

**Spatial and radiometric effects are interleaved through the chain**, not separated into parallel tracks. Each stage that has a spatial effect (diffraction, pixel aperture, jitter, IPC, etc.) writes its MTF contribution into `state.mtf_terms` at the same time it writes its radiometric contribution into a reference frame. `PerformanceStage` reads the accumulated MTF terms at the end and forms the system MTF as their product.

This interleaving is physically required because:
- **Encircled energy couples spatial and radiometric.** In point and sub-pixel regimes, the signal depends on how much PSF energy falls inside the pixel footprint (`EE_box`). OpticsStage computes the PSF; PlatformStage degrades it (jitter, smear, turbulence) and publishes `EE_box` from the fully degraded PSF (`stage_outputs["platform"]["EE_box"]`) before SpectralIntegrationStage can compute the photoelectron rate.
- **Regime dispatch depends on PSF size.** The extended/point/sub-pixel classification compares target angular extent to the diffraction PSF diameter — which doesn't exist until OpticsStage has run. SourceStage can tentatively classify based on IFOV alone, but the final regime is confirmed in OpticsStage.
- **Detector spatial response is part of the detector stage.** Pixel aperture MTF, IPC MTF, and charge-diffusion MTF are detector physics, not a separate spatial pass. They belong in DetectorStage.
- **Smear/jitter need integration time.** These MTF terms depend on `t_int` and platform motion and are naturally computed in PlatformStage, which is positioned after OpticsStage but before SpectralIntegration.

---

## 2. Module Interfaces

### The `Stage` protocol

Every stage implements a single method:

```python
@runtime_checkable
class Stage(Protocol):
    @property
    def name(self) -> str: ...

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        """Apply this stage to the chain state and return a new state.

        - state: the accumulated chain state from prior stages (may be empty
          for the first stage). Stages MUST NOT mutate the input state.
        - params: the resolved parameter set (configuration; same for all stages).
        - Returns: a new ChainState with this stage's contributions added.
        """
        ...
```

`name` is exposed as a read-only property rather than a class attribute so concrete stages can satisfy the protocol with either a class-level constant or an instance-resolved value, and `@runtime_checkable` enables `isinstance(obj, Stage)` checks in tests and tooling.

### What each stage produces and consumes

| Stage | Consumes | Produces (radiometric) | Produces (spatial) |
|-------|----------|------------------------|--------------------|
| **SourceStage** | params (target T, ε, ρ, area; background; geometry) | `L_source(λ)`, target solid angle, tentative regime | — |
| **AtmosphereStage** | `L_source(λ)`, params (atmosphere model, geometry) | `L_at_aperture(λ)`, τ_atm(λ), L_path(λ), L_atm(λ) | MTF_turbulence(f) (ground-based only) |
| **OpticsStage** | `L_at_aperture(λ)`, params (D, f, ε_obs, T_opt, ε_opt, η_cold, WFE, defocus, vignetting) | `L_post_optics(λ)`, A_collect, Ω_pixel, `effective_psf`, `reference_psf` (diffraction-limited reference with the same detector kernels, for PSF-derived Strehl), final regime | MTF_optics(f) — single term from the pupil autocorrelation; WFE and defocus enter via the pupil (Rule 4) |
| **PlatformStage** | `effective_psf`, regime, params (smear velocity, jitter, t_int) | **EE_box** (ensquared energy in pixel footprint, from the fully degraded PSF) | MTF_smear(f), MTF_jitter(f) |
| **SpectralIntegrationStage** | `L_post_optics(λ)`, **EE_box** (from PlatformStage), regime, params (filter, QE, λ-grid, t_int) | In-band photoelectrons per pixel per integration (regime-dependent) | — |
| **DetectorStage** | photoelectrons, params (J_dark, FWC, IPC, glow, L_d, nonlinearity, etc.) | Signal `S` [e-], noise terms {shot, dark, read, 1/f, kTC, DSNU, PRNU, NUC, glow, persistence, ...} | MTF_pixel(f), MTF_IPC(f), MTF_diffusion(f) |
| **ReadoutStage** | signal, noise terms, params (TDI, binning, coadds, gain, ADC) | Signal in DN, full noise budget; quantization noise added | — |
| **PerformanceStage** | full state (all frames, all noise terms, all MTF terms) | SNR, NEDT, RER, NIIRS, detection range | System MTF = ∏ MTF_i |

### State transformation rules

1. **Stages MUST NOT mutate the input state.** They construct a new state object via `state.with_(...)`, which returns a copy with new fields added.
2. **Stages MUST NOT remove fields.** Every field added by an earlier stage remains accessible to later stages and to the user.
3. **Stages MAY add fields under their stage namespace** (e.g., `state.optics.photon_rate`) and MUST add radiometric quantities to the appropriate reference frame (`state.frames["at_aperture"]`).
4. **Stages MUST register at least one reference frame** if they transform radiometric quantities (see §5).

---

## 3. Data Flow: ChainState

### Structure

```python
@dataclass(frozen=True)
class ChainState:
    # Spectral grid (set once at chain start)
    wavelength_um: np.ndarray  # the common grid

    # Reference frames — radiometric quantities at each propagation point.
    # Key is a frame name; value is a RadiometricFrame.
    frames: dict[str, "RadiometricFrame"]

    # Per-stage outputs (namespaced by stage name)
    stage_outputs: dict[str, dict[str, Any]]

    # MTF terms accumulated across stages (each stage writes its own terms)
    mtf_terms: dict[str, np.ndarray]   # term name -> MTF(f) array
    spatial_freq_cycles_per_mrad: np.ndarray | None

    # Computed performance metrics (populated by PerformanceStage)
    metrics: dict[str, float]

    # Trace metadata
    history: tuple[str, ...]  # ordered list of stage names that have run

    # Per-run identifier (UUID4); minted by ChainRunner if the caller
    # doesn't supply one. Required for the §C13 provenance record.
    run_id: str | None

    def with_frame(self, frame: "RadiometricFrame") -> "ChainState": ...
    def with_stage_output(self, stage: str, key: str, value: Any) -> "ChainState": ...
    def with_noise(self, term: "NoiseTerm") -> "ChainState": ...
    def with_mtf(self, term_name: str, mtf: np.ndarray) -> "ChainState": ...
    def with_metric(self, key: str, value: float) -> "ChainState": ...
```

### RadiometricFrame

A `RadiometricFrame` is a snapshot of the radiometric state at one reference point in the chain. It carries the spectral radiance/irradiance at that point plus relevant context (transmission accumulated so far, area, solid angle).

```python
@dataclass(frozen=True)
class RadiometricFrame:
    name: str                           # "at_target", "at_aperture", "at_fpa", "electrons", "dn"
    wavelength_um: np.ndarray
    spectral_radiance: np.ndarray | None   # W/m²/sr/µm  — when meaningful
    spectral_irradiance: np.ndarray | None # W/m²/µm     — when meaningful
    photon_rate: np.ndarray | None         # photons/s/m²/sr/µm or photons/s/pixel/µm
    in_band_value: float | None            # post-spectral-integration scalar
    in_band_unit: str
    notes: str = ""
```

Not every frame uses every field — frames upstream of the optics carry radiance; frames at/after the FPA carry photon or electron rates.

### Spectral arrays vs. scalars

- **Spectral arrays** (`np.ndarray`, length = N_wavelengths) flow through the radiance frames. They are stored in the `RadiometricFrame` and can be inspected at any reference point.
- **Scalars** (signal in electrons, noise in e- RMS, MTF at Nyquist) flow into stage outputs and metrics. The `SpectralIntegrationStage` is the explicit transition point — before it, everything spectral; after it, everything per-pixel scalar.
- Both kinds of data persist for the rest of the chain. A user can call `result.frames["at_aperture"].spectral_radiance` even after the detector stage has run.

---

## 4. Three Radiometric Regimes

### Regimes

| Regime | Condition | Signal equation |
|--------|-----------|-----------------|
| **Extended** | Target angular extent ≫ IFOV (target fills the pixel and overflows) | `S = L_target × A_collect × Ω_pixel × τ_atm × τ_opt × QE × t_int` — EE_box does **not** appear because every photon lost to a neighbor pixel is replaced by an identical photon from the neighboring scene, so the per-pixel radiance is preserved. |
| **Point** | Target angular extent ≪ PSF (point source unresolved) | `S = (I_target / R²) × A_collect × τ_atm × τ_opt × QE × **EE_box** × t_int` where I = L × A_target. **EE_box is a direct multiplicative factor** on the signal: only the fraction of PSF energy inside the pixel footprint contributes. |
| **Sub-pixel** | Target angular extent ~ IFOV (target smaller than pixel but not point-like) | Per-pixel signal = (target contribution) + (background contribution), where the target contribution scales with fill fraction η × **EE_box** and the background contribution is the extended-scene formula over (1 − η) of the pixel. EE_box applies to the target term because the target is sub-PSF; it does not apply to the background because the background is locally extended. |

### Dispatch: auto-detect with override

The framework auto-detects the regime from the **angular extent of the target** vs. the **angular size of the diffraction PSF** and the **IFOV**:

```
target_angular_extent_rad = sqrt(A_target / R²)        # small-angle approximation
ifov_rad = pixel_pitch / focal_length
psf_diameter_rad = 2.44 * lambda_c / D                  # Airy first dark ring

if target_angular_extent_rad >= 2 * ifov_rad:
    regime = "extended"
elif target_angular_extent_rad <= 0.5 * psf_diameter_rad:
    regime = "point"
else:
    regime = "subpixel"
```

The thresholds `2 * ifov_rad` and `0.5 * psf_diameter_rad` are deliberately conservative. When in doubt, the framework picks "subpixel" — which is the most general and reduces correctly to the other two regimes at the limits.

### User override

The user may force a regime via the parameter `target.regime`:

| Value | Meaning |
|-------|---------|
| `"auto"` (default) | Use the detection rule above |
| `"extended"` | Force extended-scene equation; warn if target angular extent < 0.5 IFOV |
| `"point"` | Force point-source equation; warn if target angular extent > 1 PSF |
| `"subpixel"` | Force sub-pixel equation |

### Architectural placement

Regime classification happens in **two steps**:

1. **SourceStage** makes a *tentative* classification based on target angular extent vs. IFOV only. This is enough to route atmosphere-side choices. Stored in `state.stage_outputs["source"]["regime_tentative"]`.
2. **OpticsStage** finalizes the regime after computing the diffraction PSF. It compares target angular extent against the actual PSF FWHM and writes `state.stage_outputs["optics"]["regime"]`. This is the authoritative regime for all downstream stages.

**SpectralIntegrationStage** reads the final regime and the PSF-derived **EE_box** from PlatformStage (`stage_outputs["platform"]["EE_box"]`, computed from the fully degraded PSF — jitter, smear, and turbulence included), then applies the regime-appropriate formula. This is the single point where EE_box enters the radiometric calculation. No other stage multiplies by EE_box.

The three regime equations differ only in **which spatial factors multiply the photoelectron integral**. The atmospheric transmission and optical throughput are identical across regimes. Encircled energy EE_box is the critical spatial→radiometric coupling and is applied exactly once, at SpectralIntegrationStage.

### Sub-pixel as the general case

The sub-pixel equation degenerates correctly:
- η = 1 → extended-scene equation
- A_target → 0, η → 0, but the *contrast* term (target − background) is preserved by switching to the point-source intensity formulation

For the implementation, we keep two code paths:
1. **Resolved/extended path** (η ≥ some threshold): area-weighted radiance integral
2. **Point-source path** (η below threshold): intensity / R² × encircled energy

The "subpixel" auto-classification routes to whichever path is more numerically stable for the actual target size.

---

## 5. Backward Propagation: Reference Frames

### The reference frame registry

A user must be able to ask: *"What is the noise referred to the aperture?"* or *"What is the signal in DN?"* The architecture answers this via named reference frames stored in the state.

Each radiometric reference frame has a canonical position in the chain:

| Frame name | Position | Units |
|-----------|----------|-------|
| `at_target` | Source emission, before atmosphere | W/m²/sr/µm |
| `at_aperture` | After atmosphere, at the entrance pupil | W/m²/sr/µm |
| `post_optics` | After optical throughput, before detector | W/m²/sr/µm + photon rate |
| `at_fpa` | At the focal plane, before QE | photons/s/pixel/µm |
| `photoelectrons` | After QE and integration time, before readout | e- (per pixel per integration) |
| `post_readout` | After TDI/coadds/gain | e- (per output sample) |
| `dn` | Digitized output | DN |

### Forward propagation (signal)

The conversion factors between adjacent frames are computed once per chain run and stored in `state.stage_outputs[stage]["forward_factor"]`. The full forward chain for an **extended scene** is:

```
L_at_target(λ)                                   [W/m²/sr/µm]
  × τ_atm(λ)   (+ L_path, L_atm added)           → at_aperture
  × A_collect × Ω_pixel × τ_opt(λ)               → post_optics (now W/pixel/µm)
  × (λ / hc)                                     → photons/s/pixel/µm
  × QE(λ)                                        → e-/s/pixel/µm
  ∫dλ over filter bandpass                       → e-/s/pixel       (in_band)
  × t_int                                        → photoelectrons   (per integration)
  × N_TDI × N_coadds                             → post_readout
  ÷ gain                                         → DN
```

For a **point source**, insert the regime-specific spatial factor at SpectralIntegrationStage (EE_box supplied by PlatformStage):

```
I_target / R²                                    [W/m²/µm, per wavelength]
  × τ_atm(λ) × A_collect × τ_opt(λ)              → photon flux at FPA
  × EE_box                                       → fraction landing in target pixel
  × (λ/hc) × QE(λ), ∫dλ, × t_int                 → electrons in target pixel
```

**EE_box enters exactly once**, applied to the target photon flux in the point-source and sub-pixel-target branches. It does not apply to the background term in the sub-pixel case. It does not apply at all in the extended-scene case (each photon displaced out of pixel (i,j) is replaced by a statistically identical photon from pixel (i±1, j±1)).

The full path is the product of all factors. The conversion from any frame `A` to any frame `B` is the product (or inverse product) of the factors between them.

### Backward propagation (noise)

Noise is generated at specific points in the chain (shot noise after spectral integration, dark noise at the detector, read noise at the readout, quantization at the ADC) and must be referrable to any frame.

Each noise term carries an **origin frame** — the frame in which it was generated. To express it in another frame, multiply (forward) or divide (backward) by the appropriate forward factors.

```python
def noise_at(
    state: ChainState,
    target_frame: ReferenceFrame,
    term_name: str | None = None,
) -> ChainQuantity:
    """Get noise (total or a specific term) at a target reference frame.

    If ``term_name`` is None, the total noise is the RSS of all terms whose
    origin_frame matches; mixed-origin RSS raises ValueError. Conversion
    between frames is handled by ChainQuantity.to(target_frame, state).
    """
    ...
```

### NoiseTerm

```python
@dataclass(frozen=True)
class NoiseTerm:
    name: str                  # "shot", "dark", "read", "1/f", "quantization", ...
    value_e: float             # σ in electrons RMS at origin_frame
    origin_frame: str          # one of the registered frame names
    physical_basis: str        # "Poisson", "thermal", "1/f", "ADC LSB/sqrt(12)", ...
    contributes_to: tuple[str, ...] = ("total",)  # which budgets to sum into
```

### Public query API

```python
result = chain.run(params)

# Forward propagation
result.signal_at("electrons")     # 12,450 e-
result.signal_at("dn")            # 124.5 DN
result.signal_at("at_aperture")   # spectral radiance returned

# Backward propagation
result.noise_at("electrons")      # 263 e- RMS total
result.noise_at("dn")             # 2.63 DN RMS total
result.noise_at("electrons", term_name="dark")  # 89.2 e- (just one term)
result.noise_budget()             # full breakdown table

# Spatial
result.mtf_at_nyquist()           # 0.42
result.mtf_curve("system")        # full MTF(f) array
result.mtf_budget()               # all individual MTF terms

# Performance
result.snr()                      # 47.3
result.nedt()                     # 23 mK
result.niirs()                    # 5.4
```

---

## 6. Non-Radiometric Information

Geometry, timing, and configuration do **not** flow through the chain state. They live in the `ParameterSet` and are passed alongside the state to every stage:

```python
def run(self, state: ChainState, params: ParameterSet) -> ChainState:
    aperture = params.get("sensor.optics.aperture_diameter")  # m
    ...
```

This is a deliberate separation:
- `ChainState` carries **physical quantities flowing through the chain** (spectral radiance, photoelectrons, MTF curves).
- `ParameterSet` carries **configuration that drives those physics** (aperture diameter, integration time, look angle).

Stages may read from both, but only write to a new `ChainState`. They never modify the parameter set.

### Why not put geometry in the state?

It was tempting. But geometry is constant for the duration of one chain run — it's a configuration input, not a propagating quantity. Putting it in `ChainState` would blur the line between "what is flowing" and "what is configured." Worse, it would invite stages to derive geometry on the fly, which violates the "compute once, in one place" rule.

### Inter-stage non-radiometric communication

Some stages need to publish metadata that downstream stages consume but that isn't a radiometric quantity. Examples:
- SourceStage publishes the **regime** ("extended" / "point" / "subpixel")
- SourceStage publishes the **target solid angle**
- OpticsStage publishes **A_collect**, **Ω_pixel**, the **effective_psf** and the diffraction-limited **reference_psf**
- PlatformStage publishes **EE_box** (ensquared energy in the pixel box, from the fully degraded PSF)
- PerformanceStage publishes the **system MTF** used in its NIIRS computation

These go into `state.stage_outputs[stage_name]` as a namespaced dict. Downstream stages access them via `state.stage_outputs["source"]["regime"]`. This is read-only by convention.

---

## 7. Concrete Python Interfaces

```python
# src/radiant/core/chain.py — Stage protocol
from typing import Protocol, runtime_checkable

@runtime_checkable
class Stage(Protocol):
    @property
    def name(self) -> str: ...
    def run(self, state: "ChainState", params: "ParameterSet") -> "ChainState": ...


# src/radiant/core/radiometry.py — RadiometricFrame, NoiseTerm
from dataclasses import dataclass, field, replace
from typing import Any
import numpy as np

@dataclass(frozen=True)
class RadiometricFrame:
    name: str
    wavelength_um: np.ndarray
    spectral_radiance: np.ndarray | None = None
    spectral_irradiance: np.ndarray | None = None
    photon_rate: np.ndarray | None = None
    in_band_value: float | None = None
    in_band_unit: str = ""
    notes: str = ""


@dataclass(frozen=True)
class NoiseTerm:
    name: str
    value_e: float
    origin_frame: str
    physical_basis: str
    contributes_to: tuple[str, ...] = ("total",)


# src/radiant/core/chain.py — ChainState
# All Mapping fields are wrapped in types.MappingProxyType at construction
# (__post_init__), so direct mutation raises TypeError. Stages only ever
# call the with_* helpers, which return a NEW state.
@dataclass(frozen=True)
class ChainState:
    wavelength_um: np.ndarray
    frames: Mapping[str, RadiometricFrame] = field(default_factory=dict)
    stage_outputs: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    noise_terms: tuple[NoiseTerm, ...] = ()
    mtf_terms: Mapping[str, np.ndarray] = field(default_factory=dict)
    spatial_freq_cycles_per_mrad: np.ndarray | None = None
    metrics: Mapping[str, float] = field(default_factory=dict)
    history: tuple[str, ...] = ()
    run_id: str | None = None  # UUID4; minted by ChainRunner per §C13

    def with_frame(self, frame: RadiometricFrame) -> "ChainState":
        new = dict(self.frames)
        new[frame.name] = frame
        return replace(self, frames=new)

    def with_stage_output(self, stage: str, key: str, value: Any) -> "ChainState":
        new = {k: dict(v) for k, v in self.stage_outputs.items()}
        new.setdefault(stage, {})[key] = value
        return replace(self, stage_outputs=new)

    def with_noise(self, term: NoiseTerm) -> "ChainState":
        return replace(self, noise_terms=self.noise_terms + (term,))

    def with_mtf(self, term_name: str, mtf: np.ndarray) -> "ChainState":
        new = dict(self.mtf_terms)
        new[term_name] = mtf
        return replace(self, mtf_terms=new)

    def with_spatial_freq(self, freq_cycles_per_mrad: np.ndarray) -> "ChainState":
        return replace(self, spatial_freq_cycles_per_mrad=freq_cycles_per_mrad)

    def with_metric(self, key: str, value: float) -> "ChainState":
        new = dict(self.metrics)
        new[key] = value
        return replace(self, metrics=new)

    def with_history(self, stage_name: str) -> "ChainState":
        return replace(self, history=self.history + (stage_name,))


# src/radiant/core/chain.py — ChainRunner
class ChainRunner:
    def __init__(self, stages: list[Stage]) -> None:
        # Validates stage-name uniqueness at construction.
        self._stages = list(stages)

    def run(
        self,
        params: ParameterSet,
        wavelength_um: np.ndarray,
        *,
        run_id: str | None = None,
        initial_stage_outputs: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> ChainState:
        state = ChainState(wavelength_um=wavelength_um, run_id=run_id or new_run_id())
        # Rule 6 hook: pre-chain injection of file-derived objects. The
        # IO/API layer loads files and seeds them into stage_outputs
        # before the first stage runs — e.g. the atmosphere model under
        # "atmosphere_config", the optical element list under
        # "optics_config" — so stages never read files themselves.
        if initial_stage_outputs is not None:
            for namespace, outputs in initial_stage_outputs.items():
                for key, value in outputs.items():
                    state = state.with_stage_output(namespace, key, value)
        for stage in self._stages:
            state = stage.run(state, params)
            # History auto-recorded if the stage didn't self-record.
        return state


# src/radiant/io/results.py — ChainResult
# ChainRunner.run returns the raw ChainState; the API layer
# (api/session.py) wraps it in a ChainResult for user-facing queries.
class ChainResult:
    def __init__(self, state: ChainState, params: ParameterSet | None = None) -> None:
        self._state = state
        self._params = params

    # --- Raw state access ---
    @property
    def state(self) -> ChainState: ...
    @property
    def frames(self) -> Mapping[str, RadiometricFrame]: ...
    @property
    def noise_terms(self) -> tuple[NoiseTerm, ...]: ...
    @property
    def stage_outputs(self) -> Mapping[str, Mapping[str, Any]]: ...
    @property
    def history(self) -> tuple[str, ...]: ...
    @property
    def metrics(self) -> Mapping[str, float]: ...

    # --- Forward / backward queries (ChainQuantity carries value + unit + frame) ---
    def signal_at(self, frame: ReferenceFrame | str) -> ChainQuantity: ...
    def noise_at(
        self,
        frame: ReferenceFrame | str,
        term_name: str | None = None,
    ) -> ChainQuantity: ...

    # --- Performance metrics ---
    def snr(self) -> float: ...
    def nedt(self) -> float: ...
    def niirs(self) -> float: ...

    # --- Provenance ---
    def to_provenance_record(self) -> dict: ...
```

---

## 8. Worked Example: Full Forward Pass

A staring MWIR sensor observing an extended thermal scene.

### Inputs (resolved ParameterSet)
- D = 0.30 m, f = 1.20 m, ε_obs = 0.33
- pixel pitch = 18 µm, λ_c = 4.2 µm, Δλ = 0.5 µm
- T_target = 300 K, ε_target = 0.95, A_target large (extended)
- T_optics = 280 K, η_cold = 0.9
- t_int = 5 ms, QE_peak = 0.75
- MODTRAN file loaded → τ_atm(λ), L_path(λ), L_atm(λ)

### Stage execution
1. **SourceStage** computes `L_source(λ) = ε × Planck(T,λ)`. Adds `at_target` frame. Tentative regime = extended (target angular size ≫ IFOV). Stores tentative regime + target solid angle in `state.stage_outputs["source"]`.
2. **AtmosphereStage** computes `L_at_aperture(λ) = L_source(λ) × τ_atm(λ) + L_path(λ) + L_atm(λ)`. Adds `at_aperture` frame. Turbulence MTF = 1 (space-based).
3. **OpticsStage** computes `L_post_optics(λ) = L_at_aperture(λ) × τ_opt(λ) + L_warm_optics(λ) × (1 − η_cold)`. Adds `post_optics` frame. Stores A_collect, Ω_pixel, computes the `effective_psf` and diffraction-limited `reference_psf`, finalizes regime = extended, writes MTF_optics (pupil autocorrelation) into `state.mtf_terms`.
4. **PlatformStage** writes MTF_smear (sinc from v_img × t_int), MTF_jitter (Gaussian from σ_jitter) into `state.mtf_terms`, degrades the PSF accordingly, and publishes EE_box from the fully degraded PSF (`stage_outputs["platform"]["EE_box"]`; 1.0 in the extended regime).
5. **SpectralIntegrationStage** reads regime = extended → does not apply EE_box. Computes per-pixel photon rate by integrating `L × A × Ω × τ × QE × λ/hc` over the filter bandpass. Adds `at_fpa` and (after × t_int) `photoelectrons` frames.
6. **DetectorStage** generates noise terms: shot, dark shot, read, 1/f, kTC (off because CDS=on), DSNU residual, PRNU residual, NUC residual, IPC, glow, persistence. Writes MTF_pixel, MTF_IPC, MTF_diffusion into `state.mtf_terms`.
7. **ReadoutStage** applies gain, ADC; adds quantization noise. Updates noise terms for TDI/coadds (each multiplied by √N_TDI · √N_coadd in the appropriate direction).
8. **PerformanceStage** forms system MTF = ∏ MTF_i over all accumulated terms. Computes SNR = signal / σ_total, NEDT from dS/dT, RER from system MTF integrated over the edge spread function, NIIRS from GIQE/IIRS using RER + SNR + GSD + Q.

### Backward query
A user wants to know the noise referred to the aperture in W/m²/sr/µm:
- `result.noise_at("at_aperture")` 
- The framework looks up the total noise (σ_total in electrons), traces backward through the forward factors stored in stage outputs, and returns the equivalent radiance noise.

---

## 9. Architectural Invariants

These hold for every chain run:

1. **Stages are pure functions of `(state, params)`.** No I/O, no global state, no mutation.
2. **Reference frames accumulate.** Once added, a frame is never removed or modified.
3. **Noise terms accumulate.** Each carries its origin frame; conversion between frames is computed at query time, not stored.
4. **Spectral integration happens exactly once,** in `SpectralIntegrationStage`. Before it: spectral arrays. After it: scalars.
5. **The MTF chain and the radiometric chain are interleaved, not independent.** Spatial effects (diffraction, pixel MTF, IPC, jitter, smear) are computed in the same stages that produce their radiometric counterparts. The two chains are coupled through `EE_box` (ensquared energy in the pixel footprint), a spatial quantity computed in `PlatformStage` from the fully degraded PSF (jitter, smear, turbulence included) that multiplies the radiometric signal in the point-source and sub-pixel regimes. `PerformanceStage` combines the accumulated MTF terms into the system MTF but does not "join" two separate chains.
6. **Regime is tentatively classified in `SourceStage` and finalized in `OpticsStage`** after the diffraction PSF is computed. The final regime lives in `stage_outputs["optics"]["regime"]`.
7. **EE_box is applied exactly once,** in `SpectralIntegrationStage`, and only in point-source and sub-pixel regimes. It is the single architectural coupling between the spatial PSF and the radiometric signal.
8. **Geometry and configuration are read from `ParameterSet`, never written.** Stages may read; only the resolver writes.
