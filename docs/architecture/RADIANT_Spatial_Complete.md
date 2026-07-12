# RADIANT Spatial Architecture

**Status:** Authoritative — rewritten 2026-04-25 per **ADR-A** (drop FidelityPreset)
**Filename note:** content was previously titled "RADIANT Spatial Complete". The filename `RADIANT_Spatial_Complete.md` is retained because ~50 source-file docstrings and sister-doc references link to it; the page title is now "RADIANT Spatial Architecture" to reflect what it actually documents (the dual-path discipline + distributed-spatial reality), not a finished-feature claim.
**Scope:** Diffraction, PSF construction (mono + polychromatic), MTF derivation, encircled energy, line-spread and edge-response functions, smear, jitter, TDI alignment, and atmospheric turbulence MTF — every architectural piece that touches the spatial structure of the image.
**Sister documents:** [RADIANT_Conventions.md](RADIANT_Conventions.md), [RADIANT_Optics.md](RADIANT_Optics.md), [RADIANT_Atmosphere.md](RADIANT_Atmosphere.md), [RADIANT_Signal_Chain_Architecture.md](RADIANT_Signal_Chain_Architecture.md), [RADIANT_Detector_Complete.md](RADIANT_Detector_Complete.md), [adr/ADR-A-fidelity-preset.md](adr/ADR-A-fidelity-preset.md)

---

## 0. Distributed-Spatial Reality

There is **no separate "spatial stage"** in RADIANT. Spatial physics is interleaved through the radiometric chain: each stage that has a spatial effect publishes its MTF contribution to `state.mtf_terms` and (where it owns a kernel) convolves it into the propagating `EffectivePSF`. The accumulator is `ChainState`; the stages that contribute spatial terms are `OpticsStage`, `PlatformStage`, `DetectorStage`, `ReadoutStage`, and `AtmosphereStage` (turbulence, ground-based scenarios only). `PerformanceStage` reads the accumulated terms at the end and forms the system MTF.

This is the actual implementation as of 2026-04-25 (post-Stage-8). Earlier docs implied a monolithic "spatial pass" or a configurable fidelity dial; neither exists. The dual-path discipline (PSF path + MTF product path) is enforced by the **unconditional** `check_dual_path_consistency` step in `PerformanceStage`, with a fixed tolerance of `5e-2` — see §1.4 and §9.3.

---

## 1. Critical Insight — Dual-Path Spatial Architecture

RADIANT maintains two parallel spatial paths, both rooted in the **same complex pupil function**. This is the most important architectural decision in the spatial subsystem and is codified as **CLAUDE.md Rule 4**.

### 1.1 PSF Path — Spatial-Domain Metrics

The `EffectivePSF` (`src/radiant/optics/psf/effective.py`) is the single source of truth for **spatial-domain** metrics: EE_box, RER, FWHM, Strehl, LSF, and ERF. Every spatial degradation enters the PSF as a convolution kernel (§6). These metrics are computed from the convolved PSF via numerical integration (or FFT, for MTF). **NEVER** compute EE_box from one PSF and RER from another.

### 1.2 MTF Product Path — Frequency-Domain Budget

The system MTF is the product of independently computed contributor MTFs:

- **Optical MTF**: computed from the **autocorrelation of the complex pupil function** `P(ξ,η)`. For incoherent imaging, `OTF = normalized autocorrelation of the generalized pupil` (Goodman, *Introduction to Fourier Optics*, Ch. 6). This is mathematically equivalent to `|FT{PSF}|` by the Wiener-Khinchin theorem, but is computed directly from the pupil without constructing an intermediate PSF. The full complex pupil — including aperture geometry, central obscuration, and all WFE terms — enters as a single entity. Aberrations and diffraction interact in the pupil and **cannot** be factored into separate `MTF_diffraction × MTF_aberration` terms. Implementation: `src/radiant/optics/pupil_mtf.py`.
- **Downstream contributors**: detector aperture (`sinc`), charge diffusion (`Gaussian`), jitter (`Gaussian`), smear (`sinc`), IPC (analytic), TDI misalignment (`sinc`), and turbulence (`Kolmogorov`). Each has an analytic or kernel-derived MTF and is physically independent of the others.
- **System MTF**: `MTF_sys(f) = MTF_optics × Π_i MTF_i(f)` where the product runs over the independent contributors. Implementation: `src/radiant/performance/system_mtf.py`.

This path produces MTF budgets (which contributor dominates at Nyquist?), MTF-at-Nyquist, folded/aliased MTF, and feeds directly into GIQE/NIIRS.

### 1.3 Why Two Paths

The previous generation of EO performance tools computed MTF and EE independently, frequently from different formulas, and the inconsistency manifested as a noise budget that no longer matched the spatial budget at high frequency. A PSF-only approach (RADIANT Phase 1–2) eliminated that bug entirely. The MTF product path restores the frequency-domain budget that analysts need for trade studies, but now with a **consistency check** tying the two together.

### 1.4 The Consistency Invariant

Both paths originate from the same pupil. After all convolutions are applied to the PSF (§6), the FFT of the resulting `psf_eff` must equal the product of the contributor MTFs (excluding terms that have no spatial-domain kernel — see §9.3) to within a fixed tolerance.

Per **ADR-A** (`docs/adr/ADR-A-fidelity-preset.md`), the check is **unconditional** — it runs on every chain execution, not gated by a fidelity preset. Tolerance: `5e-2` absolute error on max(|MTF_psf − MTF_product|) below Nyquist on each axis. The check function is `check_dual_path_consistency` in `src/radiant/performance/consistency_check.py`; the result lives at `state.stage_outputs["performance"]["dual_path_consistency"]`.

A failure means a degradation was added to one path but not the other — the build is broken. The default `2e-2` tolerance (CU-045, 2026-07-10) sits ~2× above the worst measured full-chain discretization residual (~1e-2 at undersampled Q ≈ 0.2) now that the pixel-aperture rect kernel is area-integrated (anti-aliased edges — CU-003 option a; the old binary mask cost up to 4.5e-2 at Nyquist). Wide enough to absorb the remaining bin-average envelope, narrow enough to catch a missing convolution or an unmultiplied MTF term.

---

## 2. The `EffectivePSF` Class

```python
@dataclass(frozen=True)
class EffectivePSF:
    """End-state PSF after every spatial degradation has been applied.

    Single source of truth for all spatial metrics.
    """

    data: np.ndarray                  # 2D, normalized to ∫∫ data dxdy = 1
    sample_spacing_m: float           # physical spacing on the FPA
    pixel_pitch_m: float              # for EE_box default
    wavelength_um: float              # scalar (mono PSF) — see §3.4 for poly
    convolution_history: tuple[str, ...]   # in-order list of degradations applied

    # Properties / methods (every spatial metric derives from `data`)
    @property
    def shape(self) -> tuple[int, int]: ...
    @property
    def peak(self) -> float: ...
    @property
    def total(self) -> float: ...

    def with_kernel(self, name: str, kernel: np.ndarray) -> EffectivePSF: ...
    def mtf_2d(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]: ...
    def mtf_1d(self, axis: str) -> tuple[np.ndarray, np.ndarray]: ...
    def ensquared_energy(self, box_size_m: float, offset_m=(0, 0)) -> float: ...
    def lsf(self, axis: str) -> tuple[np.ndarray, np.ndarray]: ...
    def erf(self, axis: str) -> tuple[np.ndarray, np.ndarray]: ...
    def edge_slope(self, axis: str) -> float: ...
    def rer(self) -> float: ...
    def fwhm(self, axis: str) -> float: ...
    def strehl(self, reference: EffectivePSF) -> float: ...
```

Source: `src/radiant/optics/psf/effective.py`.

**Method invariants:**
1. `mtf_2d()` is `np.fft.fft2(data)`, normalized so MTF(0,0) = 1.
2. `lsf(axis)` is the projection of `data` onto `axis`.
3. `erf(axis)` is the cumulative integral of `lsf(axis)`.
4. `edge_slope(axis)` is the maximum slope of `erf(axis)` in contrast per FPA-meter.
5. `rer()` is `erf(0.5·pitch) − erf(−0.5·pitch)` averaged across the two axes (GIQE-5 definition).
6. `ensquared_energy(box, offset)` is `∫∫_box data dxdy` with the box centered at `offset`.
7. `strehl(reference)` is `data.peak / reference.peak` after both are normalized to unit volume. In the shipped chain the reference is `stage_outputs["optics"]["reference_psf"]` — the diffraction-limited PSF from the same pupil with WFE = 0, carrying the **same detector kernels** as the degraded PSF — published by `OpticsStage`; `PerformanceStage` computes the reported `strehl` metric as `epsf.strehl(ref_epsf)`.

There is no `mtf_at_freq(f)` method that bypasses the FFT. There is no `ee_analytical()`. There is no `lsf_from_mtf()`. The point of having one class is that there is only one way to ask each question.

**Note on what's not on the class:** the previous version of this doc listed `polychromatic_weights`, `pupil_grid_size_px`, and a `fidelity_preset` enum. None of those are fields on the actual class as of 2026-04-25 — the polychromatic weights live inside `psf_poly.py` during construction and are not retained on the EffectivePSF; pupil-grid metadata stays in the upstream `PSFSamplingConfig` (§4); fidelity preset was dropped per ADR-A. The class deliberately carries the minimum state needed to answer "what's the PSF here, sampled how, with what history?".

---

## 3. Diffraction Engine

### 3.1 Pupil → PSF via FFT

Given a complex pupil `P(x, y) = A(x, y) · exp(i · φ(x, y))` from the optics pupil amplitude / phase modules:
1. Pad to a power-of-two grid sized to give the desired focal-plane sample spacing.
2. FFT.
3. `psf_optical = |fft|²`, normalized to unit volume.

The pupil grid sampling and the focal-plane grid sampling are coupled by the FFT relation `Δx_focal · Δx_pupil = λ · f / N`. RADIANT does not let the user set both — see §4.

### 3.2 Apodization, obscuration, spiders

All baked into the pupil amplitude `A(x, y)` by `optics/pupil_amplitude.py`. The diffraction engine is agnostic to where they came from.

### 3.3 Wavefront error

`optics/pupil_phase.py` and `optics/wavefront.py` build the OPD on the pupil grid (Zernike-polynomial expansion or user-supplied OPD map). The diffraction engine multiplies the pupil by `exp(2πi · OPD / λ_op)`. The full FFT path is the only WFE handling that enters the PSF/MTF paths in v1. The Maréchal approximation survives only as the **`strehl_marechal` diagnostic metric** (`performance/strehl.py::compute_strehl`, `exp(-(2π·OPD_rms/λ)²)` from `stage_outputs["optics"]["wavefront_error"]`) — a named sanity check alongside the PSF-derived `strehl`, never a substitute for the pupil-phase computation.

### 3.4 Polychromatic PSF

For each wavelength sample λ_k, `optics/psf_poly.compute_polychromatic_psf` builds a monochromatic PSF and accumulates with weight `w_k`:

```
psf_poly(x, y) = Σ_k w_k · psf_λ_k(x, y)
```

The weights are the in-band spectral radiance × QE × τ product, normalized to sum to 1. This couples spatial to radiometric: the polychromatic PSF *depends on the source spectrum*. The number of wavelength samples is controlled by **`optics.psf_n_wavelengths`** (default 1 = monochromatic at band center; bounds [1, 101]). Setting > 1 opts in to polychromatic broadening (typically 5–10 % for MWIR).

---

## 4. Sampling Configuration

The optics module owns a single sampling helper, `optics/sampling.py::compute_sampling`, that derives a fully consistent `PSFSamplingConfig` from physical quantities the user has already specified for the optics + detector:

| Input | Source |
|-------|--------|
| `wavelength_m` | `optics.psf_n_wavelengths` × spectral grid |
| `focal_length_m` | `optics.focal_length_m` |
| `aperture_diameter_m` | `optics.aperture_diameter_m` |
| `pixel_pitch_m` | `detector.pixel_pitch_x_um / 1e6` |
| `pupil_npix` | hard default `128` |
| `psf_oversample` | hard default `8` (samples per detector pixel; minimum 2 enforced) |

The function then:
1. Sets pupil sample spacing `Δx_pupil = aperture_diameter_m / pupil_npix`.
2. Sets target focal-plane spacing `Δx_focal = pixel_pitch_m / psf_oversample`.
3. Solves the FFT constraint `Δx_focal = λ·f / (N · Δx_pupil)` for `N` and rounds up to the next power of 2.
4. Recomputes the actual focal spacing from the rounded `N` for downstream consistency.
5. Logs a warning if `samples_across_Airy_FWHM < 2`.

The two free knobs (`pupil_npix=128`, `psf_oversample=8`) are **not** exposed as schema parameters in v1. They are the values that fit the entire scenario set without undersampling — CU-003 (resolved 2026-07-10) had one corner case (non-integer samples-per-pixel) where the binary pixel-aperture rect kernel saw discretization noise; the kernel is now area-integrated (exact edge coverage), leaving only the irreducible sinc(πfΔ) bin-average envelope (~3.5e-3 at Nyquist worst-case) — a numerical property of any nonnegative sampled kernel, not a sampling-knob deficiency.

**Open follow-up:** if a future scenario needs deeper pupil sampling (e.g., for very low Q or extreme aberrations), promote `optics.pupil_npix` and/or `optics.psf_oversample` to `_schema.py` parameters with defaults matching today's hard-coded values. There is no FidelityPreset to bundle them under.

---

## 5. ~~Fidelity Presets~~ (dropped per ADR-A)

**Removed.** Earlier drafts of this doc described a `FidelityPreset` enum (`draft` / `standard` / `high` / `publication`) that would gate (a) the consistency-check tolerance and (b) bundles of `pupil_npix` / `psf_oversample` / `n_wavelength_samples` defaults. Per **ADR-A** (`docs/adr/ADR-A-fidelity-preset.md`):

- The dual-path consistency check is **unconditional** with tolerance `5e-2` (§1.4, §9.3). No "draft mode that skips the check" exists.
- The two sampling knobs (`pupil_npix=128`, `psf_oversample=8`) are unconditional defaults. If a scenario needs different sampling, the schema gets two new parameters; it does not need a preset enum to bundle them.
- Polychromatic sampling is controlled by the existing `optics.psf_n_wavelengths` parameter (§3.4), which is the only "fidelity-like" knob that ships.

The FidelityPreset enum, the per-preset table, and the preset-driven WFE handling are all retired; any code referencing them is dead and should be removed (none exist as of the 2026-04-25 audit — the enum was always doc-only).

---

## 6. The PSF Convolution Pipeline

`src/radiant/optics/psf/builder.py::build_effective_psf` takes the optical PSF and a list of `(name, kernel_2d)` tuples and produces the `EffectivePSF`. Convolution is FFT-based and unit-volume-normalized after each kernel.

The canonical kernel order — recorded in `convolution_history` — is:

```
psf_0 = psf_optical                                          # diffraction + WFE
psf_1 = psf_0  ∗  rect(pixel_pitch_x, pixel_pitch_y)         # detector aperture
psf_2 = psf_1  ∗  gauss(σ_diffusion_x, σ_diffusion_y)        # charge diffusion
psf_3 = psf_2  ∗  rect(v_along · t_int, 0)                   # platform smear (along-track)
psf_4 = psf_3  ∗  rect(0, v_cross · t_int)                   # scan smear (cross-track) — NOT IMPLEMENTED (Gap 74)
psf_5 = psf_4  ∗  rect(v_target_x · t_int_eff,
                       v_target_y · t_int_eff)               # target motion — NOT IMPLEMENTED (Gap 74)
psf_6 = psf_5  ∗  gauss(σ_jitter_x, σ_jitter_y)              # jitter
psf_7 = psf_6  ∗  ipc_kernel_pitch_spaced(α, Δx, p)          # inter-pixel capacitance
psf_8 = psf_7  ∗  kolmogorov_kernel(r0, λ)                   # turbulence (ground only)
psf_eff = psf_8
```

Order matters because some kernels are not commutative when truncated to the working grid (the detector aperture is much wider than the optical PSF and dominates the support of the result). The result is the same to within FFT round-off, but the working order above is the canonical one and `convolution_history` records it.

`t_int_eff` for target-motion smear in TDI mode is `N_TDI × t_int_per_stage` (the target moves through every TDI stage's integration time before being read out).

**IPC kernel is resampled to the PSF sample grid (CU-083).** The logical IPC kernel places the four nearest-neighbour couplings α one **pixel pitch** `p` away from the centre, but the PSF cascade is sampled at the sub-µm focal-plane spacing `Δx`. Convolving the raw 3×3 `ipc_kernel(α)` directly would place the couplings one *sample* away — orders of magnitude too close — making the PSF-path IPC blur negligible and divergent from the analytic MTF-product term `mtf_ipc`. `ipc_kernel_pitch_spaced(α, Δx, p)` (`detector/ipc.py`) builds the kernel on the sample grid with the couplings at `±p` (linearly interpolated between the two straddling samples so the first moment lands exactly at the pitch), so its DFT reproduces `(1−4α) + 2α·cos(2πf·p)` and both Rule-4 paths agree. The detector stage builds it (reading `Δx` from the optics `EffectivePSF` via stage outputs, Rule 11) and stores it as `stage_outputs["detector"]["ipc_kernel_psf"]`; the raw 3×3 `ipc_kernel` output is retained for provenance only.

**TDI misalignment is not in the PSF cascade.** TDI line-to-line misalignment is a *readout* effect in v1 — it has an MTF term (see §9, term 9) but no spatial-domain kernel, so it appears in the MTF product path and is excluded from the dual-path comparison (`_EXCLUDED_PREFIXES = ("mtf_tdi",)` in `consistency_check.py`). If a future stage adds a spatial kernel for TDI shear, both paths must update together.

Zero-magnitude kernels are skipped from the convolution (their kernel is a delta) but logged in `convolution_history` as `"name:zero"` so the user can verify the framework saw them.

---

## 7. The Distinct Smear Sources

Confusing these is one of the top sources of error in EO performance modeling. RADIANT computes the smear MTF generically (`src/radiant/platform/smear.py::smear_mtf_1d` returns `|sinc(π·f·smear_width_m)|`) but the architecture distinguishes:

| Smear source | Origin | Parameters | Direction | Always present? |
|--------------|--------|------------|-----------|-----------------|
| Platform motion | Sensor moves along-track during integration | `platform.velocity_m_s`, `platform.altitude_m`, `t_int` | Along-track | Yes |
| Scan mechanism | Cross-track scanner (whiskbroom or dual-axis pushbroom) | `scan.cross_track_velocity_m_s`, `t_int` | Cross-track | Only for whiskbroom / dual-axis |
| Target motion | Target moves in scene during integration | `target.velocity_x_m_s`, `target.velocity_y_m_s`, `t_int_eff` | Either | Only if target moving and untracked |
| Jitter | Random pointing errors | `platform.jitter_rms_urad`, `platform.jitter_axes` | Either / both | Yes (default 0) |
| Turbulence | Atmospheric refractive-index fluctuations | `atmosphere.r0_cm` | Isotropic | Ground only |

A user studying a moving target observed by a stationary tracking ground sensor has all five potentially active. A user studying a building from LEO has platform motion and jitter only. The framework does not switch behavior based on use case — every term is computed (zero if not configured) and every term enters the PSF cascade. Zero-magnitude terms are skipped from the convolution and logged in `convolution_history`.

---

## 8. Tracking Mode — **v2 deferred**

Earlier drafts described a `TrackingMode` enum with `untracked` / `tracked` modes, a per-mode pair of `EffectivePSF` objects (`state.psf["target"]` vs `state.psf["background"]`), and a tracker-stabilized smear cascade. **None of this is implemented in v1.** All v1 scenarios route through the untracked path: target and background see the same PSF, and a single `EffectivePSF` is produced.

When tracking is implemented, it MUST land alongside an updated dual-path consistency check that handles the per-target/per-background variants and an explicit ADR documenting the new ChainState shape. Until then, this section is a placeholder, not a contract.

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
                       ─────────────────────────────────────────
                       ∫∫ |P(ξ, η)|² dξdη

MTF_optics = |OTF_optics|
```

where `P(ξ, η) = A(ξ, η) · exp(i · 2π · W(ξ, η) / λ)` is the generalized pupil function including aperture amplitude `A` (with obscuration) and wavefront error `W`. This single computation captures diffraction, all aberrations (including field-dependent and chromatic Zernikes), defocus, and their interactions. Aberrations modify the diffraction pattern in ways that cannot be factored — computing `MTF_diffraction × MTF_aberration` separately is physically incorrect and is **forbidden** (CLAUDE.md Rule 4 §4).

For polychromatic operation, the optical MTF is the weighted average of monochromatic pupil-autocorrelation MTFs:

```
MTF_optics_poly(f) = Σ_k w_k · MTF_optics(f; λ_k)
```

with weights `w_k` = in-band photon-weighted spectral radiance at each wavelength sample.

Implementation: `src/radiant/optics/pupil_mtf.py`.

### 9.2 Independent Contributor MTFs

The remaining contributors are physically independent of the pupil and of each other. Each has an analytic form or is derived from its convolution kernel:

| # | Term | MTF formula | Source module |
|---|------|-------------|---------------|
| 1 | `mtf_optics` | Pupil autocorrelation (§9.1) — includes diffraction, WFE, defocus | `optics/pupil_mtf.py` |
| 2 | `mtf_pixel_aperture` | sinc(π · f · p_x) · sinc(π · f · p_y) | `optics/pixel_kernel.py` |
| 3 | `mtf_charge_diffusion` | exp(−2π² · σ_d² · f²) | `detector/diffusion.py` |
| 4 | `mtf_ipc` | (1 − 4α) + 2α · cos(2πf · p) | `detector/ipc.py` |
| 5 | `mtf_smear_along` | \|sinc(π · f · v · t)\| | `platform/smear.py` |
| 6 | `mtf_smear_cross` | \|sinc(π · f · v · t)\| | `platform/smear.py` |
| 7 | `mtf_target_motion` | \|sinc(π · f · v_t · t_eff)\| | `platform/smear.py` |
| 8 | `mtf_jitter` | exp(−2π² · σ_j² · f²) | `platform/jitter.py` |
| 9 | `mtf_tdi_misalign` | \|sinc(π · f · misalign)\| | `readout/tdi_mtf.py` |
| 10 | `mtf_turbulence` | exp(−3.44 · (λ · f / r₀)^(5/3)) | `atmosphere/turbulence.py` + `performance/turbulence_mtf_term.py` |
| 11 | `mtf_electronics` | exp(−2π² · σ_e² · f²), x-axis only | `readout/electronics_mtf.py` |
| 12 | `mtf_scatter` | (1 − TIS) + TIS·exp(−2π² σ_halo² f²), isotropic | `optics/scatter.py` |

Notes:
- The previous 12-component table listed `mtf_diffraction`, `mtf_wfe`, and `mtf_defocus` as separate terms. These are unified into a single `mtf_optics` via pupil autocorrelation (§9.1). The component count is 11, not 12.
- Each term keys into `state.mtf_terms` with a `_x` / `_y` suffix for per-axis storage (e.g., `mtf_optics_x`, `mtf_pixel_aperture_y`).
- **Scatter MTF (Gap 31) enters BOTH paths**: `OpticsStage` computes TIS = 1 − exp(−(4πσ_s/λ)²) from `optics.surface_roughness_nm` at the ePSF wavelength, convolves the mixed kernel `(1−TIS)·δ + TIS·Gaussian(optics.scatter_halo_sigma_um)` into the ePSF, and pushes the analytic Fourier-pair term `(1−TIS) + TIS·exp(−2π²σ_halo²f²)` isotropically. Included in the consistency check. Harvey–Shack BRDF is out of scope for v1.
- **Electronics MTF (Gap 32) enters BOTH paths**, unlike TDI: `ReadoutStage` pushes the analytic term and builds the matching Gaussian-in-x kernel (delta in y — readout-axis blur only), which `PerformanceStage` convolves into the `EffectivePSF` exactly like the IPC kernel (the kernel travels via `stage_outputs["readout"]["electronics_kernel"]`, Rule 11). It is therefore *included* in the dual-path consistency comparison. Parameter: `readout.electronics_sigma_um` (default 0 = ideal electronics).

### 9.3 The Consistency Check (unconditional)

After every spatial degradation has been applied via convolution to the PSF (§6), the FFT of the resulting `psf_eff` must equal the product of `mtf_optics` and the independent contributor MTFs that have a corresponding spatial kernel:

```python
# performance/consistency_check.py — pseudocode
mtf_psf_x = epsf.mtf_1d("x")[1]                 # FFT path
product_x = product_over_i(mtf_terms[name]
                           for name in mtf_terms
                           if name.endswith("_x")
                           and not name.startswith("mtf_tdi"))
errors = abs(product_x[:nyquist] − mtf_psf_x[:nyquist])
passed_x = max(errors) <= 5e-2
```

The check runs unconditionally on every chain execution (default tolerance `5e-2`, the `tolerance` parameter of `check_dual_path_consistency`). The result lives at `state.stage_outputs["performance"]["dual_path_consistency"]` as a `DualPathConsistencyResult` with `passed_x`, `passed_y`, `max_absolute_error_x`, `max_absolute_error_y`, and `tolerance`. On failure, `PerformanceStage` logs a warning with both per-axis errors and stores the failing result — it does **not** raise; the stored result is the machine-checkable record.

**Excluded prefixes:** `mtf_tdi*` is excluded because TDI misalignment has no spatial-domain kernel in v1 (§6). When a kernel is added, the exclusion list shrinks; both paths must update together.

**Why the wider tolerance than the previous doc claimed (5e-2 vs the old "1e-6"):** the rect kernel in `optics/pixel_kernel.py` is a binary mask sampled on the FPA grid, not the analytic `sinc` it pairs with on the product side; at low Q (long-wave SWIR, small focal length, e.g., `swir_aerial_gas` with Q ≈ 0.34) the discretization mismatch reaches ~5 % near Nyquist. CU-003 tracks the planned anti-aliased-rect fix that would let the tolerance tighten back to ~1e-6; until then, `5e-2` is calibrated to the real-world worst case across the baseline scenario set without masking any actual missing-degradation regressions.

---

## 10. Parameter Inventory (current — what actually exists in `_schema.py`)

This section enumerates only parameters that ship today. Future-state spatial parameters that earlier drafts listed (e.g., `spatial.fidelity_preset`, `spatial.psf_oversample` as a tuneable, `spatial.tracking_mode`) are documented in §5 / §8 with their deferral status.

### 10.1 Optics-side spatial parameters

| Parameter | Unit | Default | Source |
|-----------|------|---------|--------|
| `optics.aperture_diameter_m` | m | required | `optics/_schema.py` |
| `optics.focal_length_m` | m | required | |
| `optics.f_number` | — | derived | |
| `optics.obscuration_ratio` | — | 0.0 | |
| `optics.defocus_um` | µm | 0.0 | |
| `optics.wfe_mode` | enum | `none` | |
| `optics.wfe_rms_waves` | waves | 0.0 | |
| `optics.wfe_reference_wavelength_um` | µm | (band-center) | |
| `optics.field_position_x` | deg | 0.0 | |
| `optics.field_position_y` | deg | 0.0 | |
| `optics.psf_n_wavelengths` | int | 1 | controls polychromatic broadening (§3.4) |

Pupil grid (`pupil_npix`) and PSF oversample (`psf_oversample`) are hard-coded inside `optics/sampling.py` (128 and 8 respectively). Promoting them to schema parameters is an open follow-up (§4).

### 10.2 Platform-side smear / motion / jitter

| Parameter | Unit | Default |
|-----------|------|---------|
| `platform.velocity_m_s` | m/s | derived from orbit if `platform.orbit_*` set |
| `platform.altitude_m` | m | required |
| `platform.jitter_rms_urad` | µrad | 0.0 |
| `platform.jitter_axes` | enum (`isotropic` / `anisotropic`) | `isotropic` |
| `platform.jitter_rms_x_urad` | µrad | 0.0 (anisotropic only) |
| `platform.jitter_rms_y_urad` | µrad | 0.0 (anisotropic only) |
| `scan.cross_track_velocity_m_s` | m/s | 0.0 |
| `target.velocity_x_m_s` | m/s | 0.0 |
| `target.velocity_y_m_s` | m/s | 0.0 |

### 10.3 Detector / readout / atmosphere pass-through

| Parameter | Unit | Default | Notes |
|-----------|------|---------|-------|
| `detector.pixel_pitch_x_um` | µm | required | feeds `pixel_pitch_m` for sampling |
| `detector.pixel_pitch_y_um` | µm | required | |
| `detector.ipc_alpha` | — | 0.0 | term 4 in §9.2 |
| `detector.diffusion_sigma_um` | µm | 0.0 | term 3 in §9.2 |
| `readout.tdi_misalign_pixels` | pixels | 0.0 | term 9 in §9.2 |
| `atmosphere.r0_cm` | cm | (consumed from atmosphere model) | term 10 in §9.2 |

---

## 11. Validation

| Check | Where enforced | Hard / soft |
|-------|----------------|-------------|
| `psf_oversample ≥ 2` (Nyquist minimum) | `optics/sampling.py::compute_sampling` | hard (raises `ValueError`) |
| `samples_across_Airy_FWHM ≥ 2` | `optics/sampling.py::compute_sampling` | soft (logs warning) |
| `psf.data` integrates to 1 ± numerical error | `optics/psf/builder.py` re-normalizes after each kernel | hard (always-true post-build) |
| `mtf_2d` ≤ 1 + 1e-9 | `optics/psf/effective.py` per FFT normalization | hard |
| Dual-path MTF consistency, tol = 5e-2 | `performance/consistency_check.py` (§9.3) | **unconditional**; soft on failure (logs a warning, result stored in stage outputs — does not raise) |
| `r0_cm > 0` if turbulence enabled | `atmosphere/turbulence.py` | hard |
| `psf_eff` symmetric for symmetric inputs | unit tests | sanity |

---

## 12. Out of Scope for v1

- Anisoplanatic PSFs (off-axis WFE different from on-axis).
- Field-dependent PSFs across an extended FOV (single PSF per scenario).
- Coherent imaging.
- Wave-optics propagation through volumes (we use Fraunhofer + image-plane convolutions).
- Speckle from coherent illumination.
- Adaptive-optics correction simulation.
- Tracking mode (target / background PSF split — §8 — v2).
- Anti-aliased pixel-aperture rect kernel (CU-003) — would let §9.3 tighten to ~1e-6.
