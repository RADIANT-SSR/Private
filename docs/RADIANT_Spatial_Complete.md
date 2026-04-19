# RADIANT Spatial Complete

**Status**: Authoritative — first design pass, unified
**Scope**: Diffraction, PSF construction, MTF derivation, encircled energy, line-spread and edge-response functions, smear (all five sources), jitter, TDI alignment, and atmospheric turbulence MTF. Anything that touches the spatial structure of the image.
**Sister documents**: RADIANT_Conventions.md, RADIANT_Optics.md, RADIANT_Atmosphere.md, RADIANT_Signal_Chain_Architecture.md, RADIANT_Detector_Complete.md

---

## 1. Critical Insight — Dual-Path Spatial Architecture

RADIANT maintains two parallel spatial paths, both rooted in the **same complex pupil function**. This is the most important architectural decision in the spatial subsystem.

### 1.1 PSF Path — Spatial-Domain Metrics

The `EffectivePSF` is the single source of truth for **spatial-domain** metrics: EE_box, RER, FWHM, Strehl, LSF, and ERF. Every spatial degradation enters the PSF as a convolution kernel (§6). These metrics are computed from the convolved PSF via numerical integration on a common grid. **NEVER** compute EE from one PSF and RER from another.

### 1.2 MTF Product Path — Frequency-Domain Budget

The system MTF is the product of independently computed contributor MTFs:

- **Optical MTF**: computed from the **autocorrelation of the complex pupil function** `P(ξ,η)`. For incoherent imaging, OTF = normalized autocorrelation of the generalized pupil (Goodman, *Introduction to Fourier Optics*, Ch. 6). This is mathematically equivalent to `|FT{PSF}|` by the Wiener-Khinchin theorem, but is computed directly from the pupil without constructing an intermediate PSF. The full complex pupil — including aperture geometry, central obscuration, and all WFE terms — enters as a single entity. Aberrations and diffraction interact in the pupil and **cannot** be factored into separate `MTF_diffraction × MTF_aberration` terms.
- **Downstream contributors**: detector aperture (`sinc`), charge diffusion (`Gaussian`), jitter (`Gaussian`), smear (`sinc`), IPC (analytic), TDI misalignment (`sinc`), and turbulence (`Kolmogorov`). Each has an analytic or kernel-derived MTF and is physically independent of the others.
- **System MTF**: `MTF_sys(f) = MTF_optics × Π_i MTF_i(f)` where the product runs over the independent contributors.

This path produces MTF budgets (which contributor dominates at Nyquist?), MTF-at-Nyquist, folded/aliased MTF, and feeds directly into GIQE/NIIRS.

### 1.3 Why Two Paths

The previous generation of EO performance tools computed MTF and EE independently, frequently from different formulas, and the inconsistency manifested as a noise budget that no longer matched the spatial budget at high frequency. A PSF-only approach (RADIANT Phase 1–2) eliminated that bug entirely. The MTF product path restores the frequency-domain budget that analysts need for trade studies, but now with a **consistency check** tying the two together.

### 1.4 The Consistency Invariant

Both paths originate from the same pupil. After all convolutions are applied to the PSF (§6), the FFT of the resulting `psf_eff` must equal the product of the 12 individual MTFs (§9) to within numerical tolerance. This check runs at `standard` fidelity and above. If it fails, a degradation was added to one path but not the other — the build is broken.

The corollary still holds: every spatial degradation must enter **both** paths. A new smear term implemented only as "multiply MTF by sinc" without the corresponding PSF convolution kernel will be caught by the consistency check.

---

## 2. The `EffectivePSF` Class

```python
@dataclass(frozen=True)
class EffectivePSF:
    """The end-state PSF after every spatial degradation has been applied.

    Single source of truth for all spatial metrics.
    """

    # ---- Underlying data ---------------------------------------------------
    psf: np.ndarray                          # 2D, normalized to ∫∫ psf dxdy = 1
    sample_spacing_m: float                  # physical spacing on the FPA
    pixel_pitch_m: float                     # for EE_box default
    wavelength_um: float | np.ndarray        # scalar (mono) or array (poly-PSF)
    polychromatic_weights: np.ndarray | None # used to build the poly-PSF; None if mono
    fidelity_preset: FidelityPreset

    # ---- Provenance --------------------------------------------------------
    convolution_history: tuple[str, ...]     # in-order list of degradations applied
    pupil_grid_size_px: int                  # so a debugger can find the optical PSF

    # ---- Methods (all derived from psf, never independently) ---------------
    def mtf_2d(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]: ...
    def mtf_1d(self, axis: Axis) -> tuple[np.ndarray, np.ndarray]: ...
    def ensquared_energy(self, box_size_m: float, offset_m=(0,0)) -> float: ...
    def ensquared_energy_nxn(self, n: int, pitch_m: float | None = None) -> float: ...
    def ee_vs_offset(self, pitch_m: float | None = None, n_offsets=21) -> np.ndarray: ...
    def lsf(self, axis: Axis) -> tuple[np.ndarray, np.ndarray]: ...
    def erf(self, axis: Axis) -> tuple[np.ndarray, np.ndarray]: ...
    def edge_slope(self, axis: Axis) -> float: ...
    def rer(self) -> float: ...
    def fwhm(self, axis: Axis) -> float: ...
    def strehl(self, reference: "EffectivePSF") -> float: ...
```

**Method invariants:**
1. `mtf_2d()` is `np.fft.fft2(psf)`, normalized so MTF(0,0) = 1.
2. `lsf(axis)` is the projection of `psf` onto `axis`.
3. `erf(axis)` is the cumulative integral of `lsf(axis)`.
4. `edge_slope(axis)` is the maximum slope of `erf(axis)`, in units of contrast per FPA-meter.
5. `rer()` is `erf(0.5·pitch) − erf(−0.5·pitch)` in *both* axes geometrically averaged (this is the GIQE-5 definition; see RADIANT_Metrics.md).
6. `ensquared_energy(box, offset)` is `∫∫_box psf dxdy` with the box centered at `offset`. `ensquared_energy_nxn(n)` is the centered case for an `n × n_pixel` box.
7. `strehl(reference)` is `psf.max() / reference.psf.max()` after both are normalized to unit volume. The reference is typically the diffraction-limited PSF for the same pupil with WFE = 0.

There is no `mtf_at_freq(f)` method that bypasses the FFT. There is no `ee_analytical()`. There is no `lsf_from_mtf()`. The point of having one class is that there is only one way to ask each question.

---

## 3. Diffraction Engine

### 3.1 Pupil → PSF via FFT

Given a complex pupil `P(x, y) = A(x, y) · exp(i · φ(x, y))` from `OpticsState.pupil`:
1. Pad to a power-of-two grid sized to give the desired focal-plane sample spacing.
2. FFT.
3. `psf_optical = |fft|²`, normalized to unit volume.

The pupil grid sampling and the focal-plane grid sampling are coupled by the FFT relation `Δx_focal · Δx_pupil = λ · f / N`. RADIANT does not let the user set both — see §4.

### 3.2 Apodization, obscuration, spiders

All baked into the pupil amplitude `A(x, y)` by `OpticsState.pupil`. The diffraction engine is agnostic to where they came from.

### 3.3 Wavefront error

`OpticsState.pupil.wavefront_error.opd_at_field(field, λ_op)` returns the OPD in meters on the pupil grid. The diffraction engine multiplies the pupil by `exp(2πi · OPD / λ_op)`. For Maréchal mode (draft fidelity), the engine instead returns the diffraction-limited PSF and tags `convolution_history` with `"strehl_marechal:S=...,σ=..."`; the spatial module then multiplies the *MTF* by `S` (not the PSF). This is the only place RADIANT applies a spatial term as an MTF rather than a convolution, and it is explicitly marked in fidelity preset metadata.

### 3.4 Polychromatic PSF

For each wavelength sample λ_k in the integration grid, compute a monochromatic PSF and accumulate with weight `w_k`:
```
psf_poly(x, y) = Σ_k w_k · psf_λ_k(x, y)
```

The weights are the in-band spectral radiance × QE × τ product, normalized to sum to 1. This couples spatial to radiometric: the polychromatic PSF *depends on the source spectrum*. RADIANT recomputes the polychromatic PSF if the source spectrum changes meaningfully (a parameter dependency edge tracked by the resolver).

The wavelength sample count is set by the fidelity preset (§5).

---

## 4. Sampling Configuration (Three Mutually-Constrained Parameters)

Three parameters fully specify the spatial sampling:

| Parameter | Unit | What it controls |
|-----------|------|------------------|
| `spatial.psf_oversample` | int | Number of PSF samples per detector pixel |
| `spatial.psf_sample_spacing_um` | µm | Physical sample spacing on the FPA |
| `spatial.min_samples_per_psf_fwhm` | int | Minimum samples across the diffraction FWHM |

These are linked by the consistency relation:
```
psf_sample_spacing_um = pixel_pitch_um / psf_oversample
samples_across_fwhm    = (1.22 × λ × f / D) / (psf_sample_spacing_um × 1e-6)
```

The user specifies **one** (or none, in which case the fidelity preset picks). The other two are derived. If the user specifies two, the parameter resolver solves for the third and validates the solution; if the user specifies all three inconsistently, it raises `ConsistencyGroupConflict`.

**Why not call this `Q` or `padding_ratio`?** Because:
- `Q` collides with quantum efficiency notation (the rest of RADIANT uses `QE(λ)`; `Q` would be ambiguous).
- `padding_ratio` is FFT-implementation jargon that does not say what it means to a user thinking in pixels.
- `psf_oversample` says exactly what it is.

---

## 5. Fidelity Presets

```python
class FidelityPreset(StrEnum):
    DRAFT = "draft"
    STANDARD = "standard"
    HIGH = "high"
    PUBLICATION = "publication"
```

| Preset | Pupil grid | Padded grid | psf_oversample | Wavelength samples | WFE handling |
|--------|------------|-------------|----------------|--------------------|----|
| `draft` | 64 × 64 | 256 × 256 | 4 | 3 | Marechal Strehl |
| `standard` | 128 × 128 | 1024 × 1024 | 8 | 7 | Full FFT of complex pupil |
| `high` | 256 × 256 | 4096 × 4096 | 16 | 15 | Full FFT |
| `publication` | 512 × 512 | 8192 × 8192 | 32 | 31 | Full FFT, Gauss-Legendre quadrature |

Wavelength samples are placed at Gauss-Legendre nodes within each filter band; the weight is the in-band spectral product at that node.

The fidelity preset is also propagated to the optics module (which uses it to decide pupil grid size) and to the detector module (which uses it for PSF-based MTF computation grids).

---

## 6. The PSF Convolution Pipeline

Starting from the optical PSF `psf_optical` (already polychromatic, already includes WFE), the spatial pipeline convolves in this order:

```
psf_0 = psf_optical
psf_1 = psf_0  ∗  rect(pixel_pitch_x, pixel_pitch_y)         # detector aperture
psf_2 = psf_1  ∗  gauss(σ_diffusion_x, σ_diffusion_y)        # charge diffusion
psf_3 = psf_2  ∗  rect(v_along · t_int, 0)                   # platform smear (along-track)
psf_4 = psf_3  ∗  rect(0, v_cross · t_int)                   # scan smear (cross-track, if any)
psf_5 = psf_4  ∗  rect(v_target_x · t_int_eff,
                       v_target_y · t_int_eff)               # target motion (untracked only)
psf_6 = psf_5  ∗  gauss(σ_jitter_x, σ_jitter_y)              # jitter (possibly anisotropic)
psf_7 = psf_6  ∗  rect(misalign_x, misalign_y)               # TDI misalignment (small)
psf_8 = psf_7  ∗  kolmogorov_kernel(r₀, λ)                   # turbulence (ground only)
psf_eff = psf_8
```

Order matters because some kernels are not commutative when truncated to the working grid (the detector aperture is much wider than the optical PSF and dominates the support of the result; convolving with it first is numerically friendlier). The result is the same to within FFT round-off, but the working order above is the canonical one and the convolution_history records it.

`t_int_eff` for target-motion smear in TDI mode is `N_TDI × t_int_per_stage` (the target moves through every TDI stage's integration time before being read out).

---

## 7. The Five Distinct Smear Sources

Confusing these is one of the top sources of error in EO performance modeling. RADIANT names each one and computes it from a different parameter group:

| Smear source | Origin | Parameters | Direction | Always present? |
|--------------|--------|------------|-----------|-----------------|
| Platform motion | Sensor moves along-track during integration | `platform.velocity_m_s`, `platform.altitude_m`, `t_int` | Along-track | Yes |
| Scan mechanism | Cross-track scanner (whiskbroom or dual-axis pushbroom) | `scan.cross_track_velocity_m_s`, `t_int` | Cross-track | Only for whiskbroom / dual-axis |
| Target motion | Target moves in scene during integration | `target.velocity_x_m_s`, `target.velocity_y_m_s`, `t_int_eff` | Either | Only if target moving and untracked |
| Jitter | Random pointing errors | `platform.jitter_rms_urad`, `platform.jitter_axes` | Either / both | Yes (default 0) |
| Turbulence | Atmospheric refractive-index fluctuations | `atmosphere.r0_cm` | Isotropic | Ground only |

A user studying a moving target observed by a stationary tracking ground sensor has all five potentially active. A user studying a building from LEO has platform motion and jitter only. The framework does not switch behavior based on use case — every term is computed (zero if not configured) and every term enters the PSF cascade. Zero-magnitude terms are skipped from the convolution (their kernel is a delta) but logged in `convolution_history` as `"name:zero"` so the user can verify the framework saw them.

---

## 8. Tracking Mode

```python
class TrackingMode(StrEnum):
    UNTRACKED = "untracked"   # platform smears target and background equally
    TRACKED = "tracked"       # target image is stabilized; background smears instead
```

In `tracked` mode:
- The platform-motion smear kernel is **not** applied to the target PSF. The target is held still on the FPA.
- The platform-motion smear kernel **is** applied to the background PSF. The background slides past while the tracker stares at the target.
- Two `EffectivePSF` objects are produced: `state.psf["target"]` and `state.psf["background"]`.
- The MTF cascade has two budgets: `target_mtf` and `background_mtf`. They differ in the smear term only.

The downstream consumer of these PSFs (the detection-range and CSNR calculation in `RADIANT_Metrics.md`) uses the *target* PSF for the signal numerator and the *background* PSF for the clutter denominator. This matters for point-source-while-tracking detection, which is precisely the situation tracking exists for.

In `untracked` mode, target and background see the same PSF and only one is built.

---

## 9. The MTF Product Path — System MTF Budget

The system MTF is the product of the optical MTF and all independent contributor MTFs:
```
MTF_system(f_x, f_y) = MTF_optics(f_x, f_y) × Π_i MTF_i(f_x, f_y)
```

### 9.1 Optical MTF — Pupil Autocorrelation

The optical MTF is computed from the **autocorrelation of the complex pupil function**, not from a product of separate diffraction and aberration terms. For incoherent imaging:

```
OTF_optics(f_x, f_y) = ∫∫ P(ξ, η) P*(ξ − λzf_x, η − λzf_y) dξdη
                        ─────────────────────────────────────────────
                        ∫∫ |P(ξ, η)|² dξdη

MTF_optics = |OTF_optics|
```

where `P(ξ, η) = A(ξ, η) · exp(i · 2π · W(ξ, η) / λ)` is the generalized pupil function including aperture amplitude `A` (with obscuration) and wavefront error `W`. This single computation captures diffraction, all aberrations (including field-dependent and chromatic Zernikes), defocus, and their interactions. Aberrations modify the diffraction pattern in ways that cannot be factored — computing `MTF_diffraction × MTF_aberration` separately is physically incorrect and is **forbidden**.

For polychromatic operation, the optical MTF is the weighted average of monochromatic pupil-autocorrelation MTFs:
```
MTF_optics_poly(f) = Σ_k w_k · MTF_optics(f; λ_k)
```
with weights `w_k` = in-band photon-weighted spectral radiance at each wavelength sample.

### 9.2 Independent Contributor MTFs

The remaining contributors are physically independent of the pupil and of each other. Each has an analytic form or is derived from its convolution kernel:

| # | Term | MTF formula | Source module |
|---|------|-------------|---------------|
| 1 | `mtf_optics` | Pupil autocorrelation (§9.1) — includes diffraction, WFE, defocus | Optics |
| 2 | `mtf_pixel_aperture` | sinc(π · f · p_x) · sinc(π · f · p_y) | Detector |
| 3 | `mtf_charge_diffusion` | exp(−2π² · σ_d² · f²) | Detector |
| 4 | `mtf_ipc` | (1 − 4α) + 2α · cos(2πf · p) | Detector |
| 5 | `mtf_smear_along` | \|sinc(π · f · v · t)\| | Platform / Spatial |
| 6 | `mtf_smear_cross` | \|sinc(π · f · v · t)\| | Platform / Spatial |
| 7 | `mtf_target_motion` | \|sinc(π · f · v_t · t_eff)\| | Platform / Spatial |
| 8 | `mtf_jitter` | exp(−2π² · σ_j² · f²) | Platform / Spatial |
| 9 | `mtf_tdi_misalign` | \|sinc(π · f · misalign)\| | Readout / Spatial |
| 10 | `mtf_turbulence` | exp(−3.44 · (λ · f / r₀)^(5/3)) | Atmosphere |

Note: the old 12-component table listed `mtf_diffraction`, `mtf_wfe`, and `mtf_defocus` as separate terms. These are now unified into a single `mtf_optics` via pupil autocorrelation. The component count is 10, not 12.

### 9.3 The Consistency Check

This is the key invariant linking the two paths. After every spatial degradation has been applied via convolution to the PSF (§6), the FFT of the resulting `psf_eff` must equal the product of `mtf_optics` and the independent contributor MTFs:

```python
mtf_from_psf = np.abs(np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(psf_eff))))
mtf_from_psf /= mtf_from_psf.max()

mtf_from_product = mtf_optics * np.prod([mtf_i for mtf_i in independent_mtfs.values()], axis=0)

assert np.allclose(mtf_from_psf, mtf_from_product, atol=1e-6)
```

This check runs at `standard` fidelity and above. If it fails, a degradation was added to one path but not the other — the build is broken.

The check tolerates one approved exception: when `wfe_mode` is in Marechal mode (draft fidelity), the WFE term enters as `MTF_wfe = Strehl` (a flat scalar) rather than as a full pupil computation, so the equality is approximate. This case is recorded in `convolution_history`.

---

## 10. Parameter Inventory

All parameters under `spatial.*` (sampling) and feed-in parameters from sister modules.

### 10.1 Sampling
| Parameter | Unit | Default |
|-----------|------|---------|
| `spatial.fidelity_preset` | enum | `standard` |
| `spatial.psf_oversample` | int | from preset |
| `spatial.psf_sample_spacing_um` | µm | derived |
| `spatial.min_samples_per_psf_fwhm` | int | 4 |
| `spatial.n_wavelength_samples` | int | from preset |
| `spatial.tracking_mode` | enum: `untracked`, `tracked` | `untracked` |

### 10.2 Smear and motion (most live in `platform.*`)
| Parameter | Unit | Default |
|-----------|------|---------|
| `platform.velocity_m_s` | m/s | derived from orbit if `platform.orbit_*` set |
| `platform.altitude_m` | m | None (required) |
| `platform.jitter_rms_urad` | µrad | 0.0 |
| `platform.jitter_axes` | enum: `isotropic`, `anisotropic` | `isotropic` |
| `platform.jitter_rms_x_urad` | µrad | 0.0 (anisotropic) |
| `platform.jitter_rms_y_urad` | µrad | 0.0 (anisotropic) |
| `platform.drift_rate_urad_s` | µrad/s | 0.0 |
| `scan.cross_track_velocity_m_s` | m/s | 0.0 |
| `target.velocity_x_m_s` | m/s | 0.0 |
| `target.velocity_y_m_s` | m/s | 0.0 |

### 10.3 TDI and turbulence pass-through
| Parameter | Unit | Default |
|-----------|------|---------|
| `detector.tdi_misalign_pixels` | pixels | 0.0 |
| `atmosphere.r0_cm` | cm | (consumed from atmosphere module) |

---

## 11. Validation

| Check | Bound |
|-------|-------|
| `psf_oversample ≥ 2` | hard (Nyquist) |
| `samples_across_fwhm ≥ min_samples_per_psf_fwhm` | hard, from preset |
| `psf` integrates to 1 ± 1e-4 | hard (after every convolution) |
| `mtf_2d` ≤ 1 + 1e-9 ∀f | hard |
| `tracking_mode == "tracked"` requires non-zero target velocity, else warning | soft |
| MTF consistency check (§9.1) | hard at standard+ fidelity |
| `r0_cm > 0` if turbulence enabled | hard |
| `psf_eff` symmetric for symmetric inputs | soft (sanity) |

---

## 12. Out of Scope for v1

- Anisoplanatic PSFs (off-axis WFE different from on-axis).
- Field-dependent PSFs across an extended FOV (single PSF per scenario).
- Coherent imaging.
- Wave-optics propagation through volumes (we use Fraunhofer + image-plane convolutions).
- Speckle from coherent illumination.
- Adaptive-optics correction simulation.

---
