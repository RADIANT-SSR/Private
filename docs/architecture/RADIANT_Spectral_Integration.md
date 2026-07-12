# RADIANT Spectral Integration (Stage 5)

**Date:** 2026-07-12
**Status:** Authoritative — written against shipped `src/radiant/spectral_integration/` (2026-07-12 doc-reconciliation pass).
**Depends on:** RADIANT_Signal_Chain_Architecture.md (§4 regimes, §5 frames), RADIANT_Conventions.md (canonical units), RADIANT_Parameter_System.md
**Scope:** `SpectralIntegrationStage` — the single point in the chain where per-wavelength spectral arrays collapse to per-pixel scalars (Rule 8) and the single point where `EE_box` enters the radiometric calculation (Rule 9). Covers the once-only integration and where the boundary sits; the three regime-dependent per-pixel signal assemblies; the areal fill-factor collection efficiency (CU-074); the background pedestal (Gap 73); the exact-NEDT `dS/dT` support (Gap 43); the extended contrast reference (ADR-0005, Gap 52); the nearfield/stray electron integration; the frame it registers; and its parameters. It fills the Stage-5 gap in the §2 document map: a tested, chain-critical stage that had no dedicated doc.

---

## 0. Why this document exists

Two of the framework's non-negotiable rules — **Rule 8** (spectral integration
happens exactly once) and **Rule 9** (`EE_box` applied exactly once) — are both
discharged in exactly one file: `spectral_integration/stage.py`. Everything
before this stage is a spectral array of length `N_wavelengths`; everything after
is a per-pixel scalar in electrons. That boundary, and the regime-dependent
choice of *which spatial factors multiply the photoelectron integral*, is the
whole job of this stage. This document is that stage's home.

**Module map:**

| File | Owns |
|------|------|
| `spectral_integration/stage.py` | `SpectralIntegrationStage`; the three regime branches; helpers `_background_pedestal_e`, `_extended_contrast_reference_signal` |
| `spectral_integration/_schema.py` | The three stage-owned parameters: `filter_min_um`, `filter_max_um`, `integration_time_s` |
| `spectral_integration/errors.py` | `SpectralIntegrationValidationError` (bad input), `SpectralIntegrationStateError` (invalid chain state) |

All radiances are W/m²/sr/µm, wavelengths µm (converted to metres locally only as
`lam_m = wl · 1e-6` for the photon-energy factor `λ/hc`), areas m², solid angles
sr, time seconds — canonical throughout (Conventions §3). `hc` is imported from
`core.constants` (Rule 13); no magic constants appear in the stage.

---

## 1. The boundary — where spectral becomes scalar

`SpectralIntegrationStage.run` reads the **`post_optics`** frame's
`spectral_radiance` (a length-`N` array) and produces the **`photoelectrons`**
frame carrying a single `in_band_value` scalar in electrons. `RadiometricFrame`
enforces the spectral-XOR-scalar invariant at construction
(`core/radiometry.py`): a frame holds *either* spectral arrays *or* an
`in_band_value`, never both — so the transition is structurally impossible to
straddle. Before this stage: arrays. After: scalars. No other stage collapses
spectral to scalar (Rule 8 / Master §C5).

The integral itself is a top-hat filter bandpass applied to a `numpy.trapezoid`
quadrature:

```
mask     = (wl ≥ filter_min_um) & (wl ≤ filter_max_um)
e_per_s  = ∫_band  e_rate(λ) dλ            [e⁻/s/pixel]   (trapezoid over wl[mask])
signal_e = e_per_s · t_int  (· EE_box for point source)   [e⁻/pixel/integration]
```

Guards (Rule 16/17 — no silent failure):
- `post_optics.spectral_radiance is None` → `SpectralIntegrationValidationError`.
- Any `NaN` in the post-optics radiance → `SpectralIntegrationValidationError`
  (upstream invalid input surfaced, never propagated).
- Fewer than 2 in-band wavelength samples → `SpectralIntegrationValidationError`
  (the trapezoid is undefined).
- Fewer than 10 in-band samples → `UserWarning` (integration accuracy flagged,
  not silently accepted).

---

## 2. The two spatial couplings this stage reads

The stage does **not** compute PSF, regime, or `EE_box`; it reads all three from
upstream stage outputs and applies them (Rule 10, Rule 9):

- **Regime** — `stage_outputs["optics"]["regime"]`, the authoritative
  classification finalized in OpticsStage (Rule 10). Legacy string values are
  normalized to the `RadiometricRegime` enum.
- **EE_box** — `stage_outputs["platform"]["EE_box"]`, computed by PlatformStage
  from the **fully degraded** PSF (jitter, smear, turbulence included). For
  partial-chain states that skip PlatformStage the stage falls back to
  `stage_outputs["optics"]["EE_box"]`; if neither exists it is `1.0` in the
  extended regime and a `SpectralIntegrationStateError` otherwise (the point and
  sub-pixel regimes *require* the coupling).
- **Rule-9 guard:** if the regime is `EXTENDED` and `EE_box ≠ 1.0`, the stage
  raises `SpectralIntegrationStateError` — applying `EE_box` in the extended
  regime is a programming error in PlatformStage, not an accepted input.

---

## 3. Collection efficiency — QE × fill factor (CU-074)

Photons collect only on the photosensitive fraction of the pixel. The stage folds
the **areal fill factor** into an effective per-λ collection efficiency used for
*every* electron conversion in the stage:

```
collection(λ) = qe_curve(λ) · fill_factor          # detector.fill_factor
```

- `qe_curve` is the API-pre-evaluated spectral QE passed via
  `stage_outputs["spectral_integration"]["qe_curve"]` when tabulated QE is
  configured; otherwise it is the scalar `detector.qe_value` broadcast to the grid.
- At `fill_factor = 1` this is a no-op. The stored `qe_curve` / `qe_scalar`
  provenance outputs remain **pure QE** — the fill factor lives only in the
  `collection` product, never in the reported QE.
- The full-pitch pixel area feeds only the geometric `Ω_pixel` (IFOV / GSD); it is
  **never** used for photon collection. This is the CU-074 fix: fill factor was
  previously coupled inconsistently across the PSF, MTF, and radiometry paths.

---

## 4. Per-pixel signal assembly, by regime

All three branches build a spectral `photon_rate` [photons/s/pixel/µm], multiply
by `collection(λ)` to get `e_rate` [e⁻/s/pixel/µm], integrate over the band, and
scale by `t_int`. They differ **only** in which spatial factors enter the photon
rate and whether `EE_box` multiplies.

### 4.1 Extended (`RadiometricRegime.EXTENDED`)

```
photon_rate(λ) = L_post_optics(λ) · A_collect · Ω_pixel · (λ / hc)
signal_e       = ∫_band photon_rate(λ) · collection(λ) dλ · t_int
```

No `EE_box`: every photon lost to a neighbour pixel is replaced by a statistically
identical photon from the neighbouring extended scene, so per-pixel radiance is
preserved (Signal_Chain §4).

### 4.2 Point source (`RadiometricRegime.POINT_SOURCE`)

The target signal is built from the **target-only** radiance, obtained by
stripping the up-path radiance from the `at_aperture_target` frame and
transmitting once through the optics:

```
L_target_only = at_aperture_target.spectral_radiance − L_path_up      # atmosphere.L_path
L_target_post = L_target_only · tau_opt                               # optics.tau_opt
Ω_target      = A_target / R²                                         # source.projected_area_m2, source.range_m
photon_rate(λ)= L_target_post · A_collect · Ω_target · (λ / hc)
signal_e      = (∫_band photon_rate · collection dλ) · t_int · EE_box
```

`EE_box` is a **post-integration multiplicative factor** here — only the fraction
of PSF energy inside the pixel footprint contributes. `R ≤ 0` or a missing
`projected_area_m2` / `range_m` raises `SpectralIntegrationValidationError`.

### 4.3 Sub-pixel (`RadiometricRegime.SUB_PIXEL`)

The pixel is a fill-fraction mix of target and locally-extended background, with
the up-path radiance added back **once, unweighted** (it fills the whole pixel and
must not be split by `ff` or subjected to `EE_box`):

```
L_target_through = (at_aperture_target − L_path_up)  · tau_opt
L_bg_through     = (at_aperture_background − L_path_full) · tau_opt
L_path_through   = L_path_up · tau_opt
L_mixed(λ)       = ff · L_target_through · EE_box + (1 − ff) · L_bg_through + L_path_through
photon_rate(λ)   = L_mixed · A_collect · Ω_pixel · (λ / hc)
signal_e         = ∫_band photon_rate · collection dλ · t_int
```

`ff` is `stage_outputs["source"]["fill_fraction"]`; `L_path_full` is
`atmosphere.atm_quantities.L_path_full`. `EE_box` multiplies the **target term
only** (Rule 9) — the background is locally extended and keeps its full pixel
weight. When no `at_aperture_background` frame is configured (matrix Decision #13)
the background radiance falls back to zero, and the `(1 − ff)` term vanishes.

---

## 5. Background pedestal and contrast (Gap 73)

The stage computes a **full-pixel background pedestal** with one shared helper,
`_background_pedestal_e` — the same `Ω_pixel` formula used by the
extended/sub-pixel background reference and the point-source pedestal, so the
noise budget is continuous across the sub-pixel → point-source boundary (Rule 19,
one computation one place):

```
_background_pedestal_e = (∫_band  L_bg · tau_opt · A_collect · Ω_pixel · (λ/hc) · collection dλ) · t_int
```

The `at_aperture_background` frame already bundles `L_bg·τ_full_up + L_path_full`,
so the helper transports it once through the optics and integrates over the full
pixel IFOV.

| Regime | `contrast_e` | `background_e` |
|--------|--------------|----------------|
| Point source, background present | `signal_e` (target-only excess *is* the contrast) | `_background_pedestal_e(...)` — real photo-charge that shot-noises and fills the well, but **not** part of the target signal |
| Point source, no background | `signal_e` | `0.0` |
| Extended / sub-pixel, background present | `signal_e − background_e` | `_background_pedestal_e(...)` |
| Extended / sub-pixel, no background | `signal_e` (+ optional contrast-reference differential, §6) | `0.0` |

`background_e` and `contrast_e` are written to `stage_outputs["spectral_integration"]`
for the noise budget (DetectorStage) and the detection-relevant differential
(PerformanceStage).

---

## 6. Extended contrast reference (ADR-0005 / Gap 52)

When `source.contrast_reference.temperature > 0`,
`_extended_contrast_reference_signal` builds the in-band signal `S_b` of a uniform
reference scene in the neighbouring pixel:

```
L_ref = ε_ref · B(λ, T_ref) · tau_atm + L_path   → transmit through tau_opt → integrate → S_b
```

and sets `contrast_e = signal_e − S_b`, storing `S_b` as
`contrast_reference_signal_e`. This differential is **metric-only**: `background_e`
(and therefore the noise budget) stays `0`, preserving matrix Decision #13. The
helper returns `None` (no-op) when no valid reference temperature is configured.
`B(λ,T)` uses `core.blackbody.planck_spectral_radiance` — no in-stage Planck
re-derivation.

---

## 7. Exact-NEDT support — dS/dT (Gap 43)

The stage computes the temperature sensitivity of the in-band signal as the
Planck log-derivative `(dB/dT)/B` of the target's blackbody function, weighted by
the actual in-band electron-rate spectrum and integrated over the band:

```
log_deriv(λ) = planck_spectral_radiance_dT(λ,T) / planck_spectral_radiance(λ,T)   [1/K]
ds_dt_e_per_K = (∫_band e_rate(λ) · log_deriv(λ) dλ) · t_int   (· EE_box for point source)
```

This is the **exact band integral**; it reduces exactly to the single-λ
Planck-factor approximation (`performance/nedt.py`) in the narrow-band limit. It is
stored as `ds_dt_e_per_K` only when `source.target.temperature` is finite and
positive; PerformanceStage prefers it over the approximation when available.

---

## 8. Nearfield and stray-light electron integration

The stage converts the optics-side irradiance-at-FPA outputs to electrons per
pixel. These are **irradiance** [W/m²/µm], so they use the geometric pixel area
`A_pixel = pixel_pitch_x · pixel_pitch_y` (not `A_collect · Ω_pixel`) and the same
`collection = QE·FF` efficiency (CU-074):

```
nearfield_e = (∫_band  E_nf(λ)   · A_pixel · collection(λ) · (λ/hc) dλ) · t_int
stray_e     = (∫_band  E_stray(λ)· A_pixel · collection(λ) · (λ/hc) dλ) · t_int
```

sourced from `stage_outputs["optics"]["nearfield_irradiance_at_fpa"]` and
`["stray_light_irradiance_at_fpa"]` (both `SpectralData`); each defaults to `0.0`
when the optics stage did not produce it.

---

## 9. What this stage registers and writes

**Frame registered:** exactly one — **`photoelectrons`** (`in_band_value =
signal_e`, `in_band_unit = "e-"`).

> **Note:** **No `at_fpa` `RadiometricFrame` is registered by this stage or any
> other** — the shipped stage collapses `post_optics` → `photoelectrons` in one
> step. The only `at_fpa` symbols in the code are the optics-side *stage-output*
> keys `nearfield_irradiance_at_fpa` / `stray_light_irradiance_at_fpa` (§8), which
> are irradiance arrays, not frames. Signal_Chain §5's frame table was reconciled
> to match this (CU-091).

**Stage outputs written to `stage_outputs["spectral_integration"]`:**
`signal_e`, `e_rate_per_s`, `background_e`, `contrast_e`, `ds_dt_e_per_K`
(when the target temperature is set), `nearfield_e`, `stray_e`, `qe_curve` and
`qe_scalar` (pure-QE provenance, re-exported so backward-propagation code in
`core/responsivity.py` can include QE without a cross-stage detector import), and
`contrast_reference_signal_e` (when a contrast reference is configured).

---

## 10. Parameters

**Owned by this stage** (`_schema.py`, all `default=None` — required inputs):

| Parameter | Unit | Bounds | Meaning |
|-----------|------|--------|---------|
| `spectral_integration.filter_min_um` | µm | (0.1, 30.0) | Short-wavelength edge of the top-hat filter |
| `spectral_integration.filter_max_um` | µm | (0.1, 30.0) | Long-wavelength edge of the top-hat filter |
| `spectral_integration.integration_time_s` | s | (1e-9, 100.0) | Detector integration time `t_int` |

**Read from other stages' schemas** (Rule 12 — each has its `ParameterDef` in the
owning stage): `detector.qe_value`, `detector.fill_factor`,
`detector.pixel_pitch_x_um`, `detector.pixel_pitch_y_um`,
`source.target.temperature`, `source.contrast_reference.temperature`,
`source.contrast_reference.emissivity`.

**Read from upstream stage outputs** (not parameters):
`optics.{A_collect, Omega_pixel, regime, tau_opt}`, `platform.EE_box`,
`source.{projected_area_m2, range_m, fill_fraction}`,
`atmosphere.{tau_atm, L_path, atm_quantities.L_path_full}`, and the `post_optics`,
`at_aperture_target`, `at_aperture_background` frames.

---

## 11. What is NOT done here

- **No QE/dark/full-well noise physics.** Only the *signal* electron count is
  formed; DetectorStage generates shot, dark, read, and pattern-noise terms and
  applies the well.
- **No TDI, gain, or ADC.** ReadoutStage scales by TDI/coadd/binning and converts
  to DN.
- **No PSF, no `EE_box` computation, no regime classification.** Those are
  OpticsStage (PSF, regime, throughput) and PlatformStage (degraded PSF, `EE_box`);
  this stage only *consumes* them.
- **`EE_box` is never applied to the background term** (sub-pixel) and never
  applied at all in the extended regime (Rule 9).
- **No unit conversion beyond the local `µm → m` for the `λ/hc` photon-energy
  factor** — that is physics, not a boundary conversion (Rule 2).

---

## 12. How the rest of RADIANT consumes this

- **DetectorStage** reads `signal_e` / `background_e` to seed shot-noise terms and
  the well-fill check.
- **PerformanceStage** reads `contrast_e` (detection differential),
  `ds_dt_e_per_K` (exact NEDT, preferred over the narrow-band approximation), and
  the signal for SNR.
- **Backward-propagation queries** (`ChainResult.signal_at`,
  `core/quantity.py`) read the `photoelectrons` frame's `in_band_value` as the
  anchor and propagate to any reference frame using the composite transfer factor
  `signal_e / L_at_aperture_mean` — see RADIANT_Reference_Frames.md §3.
