# RADIANT Metric Dependencies

**Status**: **Design-era reference — parameter names NOT reconciled to the shipped schema.**
**Scope**: For every metric in `RADIANT_Metrics.md`, the complete dependency tree from the metric back to input parameters. Used by the parameter resolver to (1) validate required inputs before running, (2) emit specific error messages, (3) determine which metrics are computable from the current config, and (4) tell the user exactly what to add for a desired analysis.
**Sister documents**: RADIANT_Parameter_System.md, RADIANT_Metrics.md, plus all six stage docs (Source/Target, Atmosphere, Optics, Spatial, Detector, Scan/Timing)

> **Reconciliation banner (2026-07-12).** This document is a **design-era mirror**
> and its dependency trees use parameter names that largely **do not exist in the
> shipped schema**. Known-stale references include: `radiant.performance.dependencies`
> (no such module — the authoritative machine-readable dependency contract is the
> `MetricSpec` registry in `radiant/performance/registry.py`, whose `requires_*`
> fields are CI-enforced, see RADIANT_Metrics.md §6); the `scan.*` namespace (no
> `scan.*` parameters exist — timing is `spectral_integration.integration_time_s`
> plus `platform.ground_velocity_m_s`); the QE model `detector.qe_input` /
> `qe_material` / `qe_file` / `qe_peak` / `qe_cutoff_um` (real: `detector.qe_value`
> or `detector.qe_table_path`, see RADIANT_Detector_Complete.md §3.1);
> `optics.apodization_mode` and `optics.transmission_file` / `telescope_transmission`
> / `filters` / `key_elements` / `residual_transmission` / `elements` (apodization is
> unbuilt; transmission modes 2–5 arrive as `optics_config[...]` injections, not
> path parameters, see RADIANT_Optics.md §5/§10). Treat the **structure** of the
> trees (which intermediate quantity flows from which stage) as informative and the
> **leaf parameter names** as design-target. This doc should be regenerated from the
> registry when time permits (logged in the reconciliation findings).

---

## 1. Notation

```
metric
├── intermediate_quantity
│   ├── ★ required_parameter
│   ├── ● defaulted_parameter (parameter has a usable default; user can omit)
│   └── nested_intermediate
└── ...
```

- **★** = required (no usable default; user MUST set)
- **●** = has a default value; the user *may* set it but doesn't have to
- *italics* in tree text = computed by an upstream stage, not a parameter

Repeated subtrees are abbreviated `[see <metric>]` to keep the document under control. The full unrolled form lives in code (`radiant.performance.dependencies`) where it is consumed by the resolver; this document is the human-readable mirror.

---

## 2. Common subtrees (referenced from many metrics)

### 2.1 Signal in extended regime → `S_ext_e`

```
S_ext_e (electrons in extended regime)
├── L_at_aperture(λ)
│   ├── L_at_target(λ)
│   │   ├── ★ target.temperature_K          (if thermal source)
│   │   ├── ★ target.emissivity              (or target.material from library)
│   │   ├── ★ geometry.solar_zenith_deg      (if reflective)
│   │   ├── ● target.brdf_model              (default lambertian)
│   │   ├── ● solar.spectrum_source          (default kurucz)
│   │   └── (per RADIANT_Source_Target_System.md §6 — see source for full path)
│   ├── τ_atm(λ)                             [see §2.3]
│   └── L_path(λ)                            [see §2.3]
├── A_collect (m²)
│   ├── ★ optics.aperture_diameter_m
│   ├── ● optics.obscuration_ratio           (default 0.0)
│   ├── ● optics.n_spiders                   (default 0)
│   ├── ● optics.spider_width_m              (default 0)
│   └── ● optics.apodization_mode            (default uniform)
├── Ω_pixel (sr)
│   ├── ★ detector.pixel_pitch_x_um
│   ├── ● detector.pixel_pitch_y_um          (default = pitch_x)
│   └── ★ optics.focal_length_m
├── τ_opt(λ)
│   └── (one of five transmission modes — see RADIANT_Optics.md §5)
│       Mode 1: ★ optics.transmission_scalar
│       Mode 2: ★ optics.transmission_file
│       Mode 3: ★ optics.telescope_transmission AND ★ optics.filters
│       Mode 4: ★ optics.key_elements AND ★ optics.residual_transmission
│       Mode 5: ★ optics.elements
├── QE(λ)
│   ├── ★ detector.qe_input
│   ├── ★ detector.qe_material               (if input=library)
│   │     OR ★ detector.qe_file              (if input=file)
│   │     OR ★ detector.qe_peak              (if input=custom)
│   └── ● detector.qe_cutoff_um              (defaulted by material)
├── t_int_s
│   └── (one of four derivation modes — see RADIANT_Scan_Timing.md §4)
│       Direct:        ★ scan.t_int_s
│       From scan:     ★ scan.mode + scan.geometry chain
│       From frame:    ★ scan.frame_rate_hz + ● scan.duty_cycle
│       Auto:          framework picks best available
└── λ/(hc) factor                            (universal constant; no params)
```

### 2.2 Total noise → `σ_total_e`

```
σ_total_e
├── σ_temporal_e (always computed)
│   ├── signal_shot                          (no params; from S_ext_e)
│   ├── background_shot                      (no params; from background source)
│   ├── nearfield_shot
│   │   ├── ● optics.optics_temperature_K    (default 290 K)
│   │   ├── ● optics.cold_stop_efficiency    (default 1.0)
│   │   ├── ● optics.elements                (default = lumped from τ)
│   │   └── (per element: ● temperature_K, ● distance_to_fpa_m)
│   ├── straylight_shot
│   │   ├── ● optics.stray.input_mode        (default veiling_glare)
│   │   └── ● optics.stray.veiling_glare_fraction (default 0.0)
│   ├── dark_shot
│   │   ├── ● detector.dark_current_e_per_s  (defaulted by material+T)
│   │   ├── ● detector.detector_temperature_K
│   │   └── (depends on t_int from §2.1)
│   ├── gr_noise                             ● detector.gr_factor (default 0)
│   ├── johnson_noise                        ● detector.r0a_ohm_cm2 (default ∞)
│   ├── flicker_1f                           ● detector.flicker_K (default 0)
│   ├── read_noise                           ★ detector.read_noise_e_rms
│   ├── ktc_reset_noise                      ● detector.cds_enabled (default True; if True ktc=0)
│   ├── quantization_noise                   ● detector.gain_e_per_dn, ● detector.adc_bits
│   ├── persistence_noise                    ● detector.persistence_fraction (default 0)
│   └── glow_shot                            ● detector.glow_e_per_s (default 0)
└── σ_spatial_e (always computed; included in total only if regime=detection)
    ├── prnu                                 ● detector.prnu_pct (default 0)
    ├── dsnu                                 ● detector.dsnu_e_rms (default 0)
    └── clutter                              ● background.clutter_sigma (default 0)

   regime selector: ● detector.noise_regime  (default imaging)
```

### 2.3 Atmosphere outputs → `τ_atm(λ)`, `L_path(λ)`

```
atmospheric outputs
├── ● atmosphere.model                       (default: exo if both endpoints space, else simple)
├── (model-specific subtree)
│   simple parametric:
│     ├── ● atmosphere.visibility_km          (default 23 km)
│     ├── ● atmosphere.aerosol_type           (default rural)
│     ├── ● atmosphere.precipitable_water_cm  (default 1.4)
│     └── ● atmosphere.standard_atmosphere    (default us_standard)
│   tabulated:
│     ├── ★ atmosphere.tabulated_transmittance_file
│     └── ★ atmosphere.tabulated_path_radiance_file
│   modtran:
│     ├── ● atmosphere.modtran.binary_path    (env var or default)
│     ├── ● atmosphere.modtran.atmosphere_profile
│     ├── ● atmosphere.modtran.aerosol_model
│     └── (more — see RADIANT_Atmosphere.md §6.4)
│   exo:
│     └── (no params)
└── geometry
    ├── ★ geometry.sensor_altitude_m         (or derived from platform.altitude_m)
    ├── ★ geometry.target_altitude_m
    ├── ★ geometry.path_zenith_deg
    └── ● geometry.solar_zenith_deg          (default 0 — sun overhead)
```

### 2.4 PSF → `state.psf`

```
EffectivePSF
├── psf_optical
│   ├── pupil amplitude
│   │   └── A_collect chain                  [see §2.1, A_collect block]
│   ├── pupil phase (WFE)
│   │   ├── ● optics.wfe_mode                (default scalar_rms)
│   │   ├── ● optics.wfe_rms_waves            (default 0)
│   │   └── ● optics.wfe_reference_wavelength_um (default 0.633)
│   └── ● spatial.fidelity_preset             (default standard)
├── pixel aperture convolution               (★ detector.pixel_pitch_x_um, ● fill_factor)
├── charge diffusion                          (● detector.charge_diffusion_length_um)
├── platform smear
│   ├── ★ platform.altitude_m
│   ├── ground velocity                       [one of orbit / aircraft / override]
│   └── t_int                                  [§2.1]
├── target motion smear                       (● target.velocity_x_m_s, ● target.velocity_y_m_s)
├── jitter                                    (● platform.jitter_rms_urad)
├── TDI misalignment                          (● detector.tdi_misalign_pixels)
└── turbulence                                (● atmosphere.turbulence_enabled, ● atmosphere.r0_cm)
```

---

## 3. Per-Metric Dependency Trees

### 3.1 SNR

```
SNR
├── S_e                                       [see §2.1; full S_ext_e tree]
└── σ_total_e                                 [see §2.2]
```

Required (★) summary: target source params, optics aperture + focal length + transmission, detector pitch + QE + read noise, integration time. Everything else has a default.

### 3.2 NEΔT

```
NEΔT
├── σ_total_e                                 [see §2.2]
└── dS/dT
    ├── ★ target.temperature_K                (must exist; thermal source mandatory)
    ├── target.emissivity (or material)
    └── (full S_ext_e tree from §2.1, evaluated at T and T+ΔT)
```

Required additions over SNR: `target.temperature_K` must drive a `ThermalSource` or `CombinedSource`. If only a `TabulatedRadianceSource` is used, NEΔT raises NaN with reason "no thermal contribution; cannot perturb temperature."

### 3.3 NEΔL

```
NEΔL
├── σ_total_e                                 [see §2.2]
└── dS/dL = A · Ω · τ_atm · τ_opt · QE · t_int   [all from §2.1]
```

Same required set as SNR. No new ★.

### 3.4 NEΔρ

```
NEΔρ
├── σ_total_e                                 [see §2.2]
└── dS/dρ
    ├── ★ geometry.solar_zenith_deg
    ├── ● solar.spectrum_source               (default kurucz)
    ├── (full S_ext_e tree, with reflective source)
    └── × τ_atm² (round-trip)                  [§2.3]
```

New ★ over SNR: `geometry.solar_zenith_deg` must be < 90°. Source must include a reflective component.

### 3.5 CSNR (sub-pixel)

```
CSNR
├── ΔS = ff · (S_target − S_background) · EE_box
│   ├── ff
│   │   ├── ★ target.area_m2
│   │   ├── ★ geometry.slant_range_m         (or derived from platform.altitude + look angle)
│   │   └── Ω_pixel                           [§2.1]
│   ├── S_target                              [§2.1]
│   ├── S_background
│   │   ├── ★ background.temperature_K       (or background.material)
│   │   └── (rest of source chain for background)
│   └── EE_box
│       └── EffectivePSF                      [§2.4]
└── σ_total_e                                 [§2.2]
```

New ★ over SNR: `target.area_m2`, `background.temperature_K` (or any populated background source), `geometry.slant_range_m`.

### 3.6 NIIRS (GIQE-5)

```
NIIRS
├── GSD_inch
│   ├── GSD_along
│   │   ├── ifov_along (★ pixel_pitch_y_um, ★ focal_length_m)
│   │   └── ★ geometry.slant_range_m
│   └── GSD_cross
│       └── (same with pitch_x)
├── RER                                       [see §3.7]
├── SNR                                       [see §3.1]
├── ● metric.niirs.overshoot_H                (default 1.0)
└── ● metric.niirs.noise_gain_G               (default 1.0)
```

New ★ over SNR: `geometry.slant_range_m`. NIIRS otherwise inherits SNR's requirements.

### 3.7 RER

```
RER
└── EffectivePSF                              [§2.4]
   pitch parameters: ★ detector.pixel_pitch_x_um, ● detector.pixel_pitch_y_um
```

Required: aperture, focal length, pitch, fidelity preset (defaulted).

### 3.8 Edge slope

```
edge_slope
└── EffectivePSF                              [§2.4]
```

Same requirements as RER.

### 3.9 MTF (system, evaluated at request points)

```
MTF(f)
├── EffectivePSF                              [§2.4]  (the PSF-derived MTF)
└── ● metric.mtf.frequencies_cycles_per_mrad  (default = nyquist, half-nyquist)
```

Same requirements as RER plus a list of frequencies (defaulted).

### 3.10 Encircled Energy (EE_nxn, EE_vs_offset)

```
EE_nxn
├── EffectivePSF                              [§2.4]
├── ★ metric.ee.n                             (e.g., 1, 3, 5)
└── pitch parameters as in RER
```

### 3.11 Strehl ratio (PSF-derived, `strehl`)

```
Strehl
├── EffectivePSF                              [§2.4]  stage_outputs["optics"]["effective_psf"]
└── reference (diffraction-limited PSF)                stage_outputs["optics"]["reference_psf"]
    └── (same pupil with WFE = 0, same detector kernels;
        published by OpticsStage)
```

### 3.11b Marechal Strehl diagnostic (`strehl_marechal`)

```
strehl_marechal = exp(-(2π · OPD_rms / λ)²)
└── WavefrontError                            stage_outputs["optics"]["wavefront_error"]
    ├── ★ optics.wfe_rms_waves
    ├── ● optics.wfe_reference_wavelength_um
    └── operating (band-center) wavelength
```

Analytic small-aberration diagnostic — ignores obscuration, defocus, jitter, smear. Distinct from the PSF-derived `strehl` above.

### 3.12 Point source detection range

```
R_detect
├── ★ target.intensity_W_per_sr  (or full point-source spectral chain)
├── A_collect                                 [§2.1]
├── τ_opt                                     [§2.1]
├── QE                                        [§2.1]
├── t_int_s                                   [§2.1]
├── EE_box                                    [§2.4]
├── σ_total_e                                 [§2.2]
├── ● metric.detection.threshold              (default 6.0)
└── atmosphere model that supports geometry rebuild   [§2.3 — must NOT be tabulated]
```

New ★ over SNR: a *point-source* target (i.e., `target.input_path = DIRECT_INTENSITY` or `INTEGRATED_OBJECT_INTENSITY`). Tabulated atmosphere is forbidden — bisection over range needs a re-evaluable atmosphere.

### 3.13 Saturation margins (well, ADC)

```
margin_well_dB
├── ★ detector.full_well_capacity_e
└── S_signal_e (the realized per-pixel signal)
    └── (full S chain × N_TDI × binning factors per RADIANT_Detector_Complete.md §10)

margin_adc_dB
├── ★ detector.adc_full_scale_dn (or derived from ★ detector.adc_bits)
├── ★ detector.gain_e_per_dn
└── S_signal_e
```

New ★ over SNR: `detector.full_well_capacity_e`, `detector.gain_e_per_dn`, `detector.adc_bits`.

### 3.14 Dynamic range

```
DR_dB
├── ★ detector.full_well_capacity_e
└── σ_temporal_dark
    ├── ● detector.dark_current_e_per_s      (defaulted by material+T)
    ├── ● detector.detector_temperature_K
    └── ★ detector.read_noise_e_rms
```

Required ★: FWC, read noise. (Dark defaults from material library.)

---

## 4. Required Parameter Summary by Metric

The minimum-set table — what the user *must* set to compute each metric, assuming everything else uses defaults. ★-only.

| Metric | Required user inputs |
|--------|---------------------|
| SNR | `target.temperature_K` (or material), `optics.aperture_diameter_m`, `optics.focal_length_m`, transmission (one mode), `detector.pixel_pitch_x_um`, `detector.qe_*`, `detector.read_noise_e_rms`, `scan.t_int_s` (or scan-derivable), `platform.altitude_m` |
| NEΔT | SNR set + thermal source must exist |
| NEΔL | SNR set |
| NEΔρ | SNR set + `geometry.solar_zenith_deg < 90°` + reflective source |
| CSNR | SNR set + `target.area_m2` + `background.temperature_K` (or material) + `geometry.slant_range_m` |
| NIIRS | SNR set + `geometry.slant_range_m` |
| RER | aperture, focal length, pitch (everything else defaulted) |
| Edge slope | RER set |
| MTF | RER set |
| EE | RER set + `metric.ee.n` (defaulted to {1,3,5}) |
| Strehl (`strehl`) | RER set (needs both `effective_psf` and `reference_psf` stage outputs) |
| Marechal Strehl (`strehl_marechal`) | `optics.wfe_rms_waves` + reference wavelength (needs the `wavefront_error` stage output) |
| Detection range | SNR set + point-source target + non-tabulated atmosphere |
| Saturation margin (well/ADC) | SNR set + `detector.full_well_capacity_e` + `detector.gain_e_per_dn` + `detector.adc_bits` |
| Dynamic range | `detector.full_well_capacity_e` + `detector.read_noise_e_rms` |

---

## 5. How the Resolver Uses This

The dependency trees in §3 are encoded as data in `radiant.performance.registry` (`METRIC_SPECS: dict[str, MetricSpec]`) — the runtime form is expressed in ChainState terms (required frames, `(stage, key)` stage-output pairs, noise terms, metric-on-metric dependencies, regimes) rather than raw parameter dot-paths:

```python
DEPENDENCIES: dict[str, MetricDependency] = {   # design sketch; actual: METRIC_SPECS
    "snr": MetricDependency(
        required_keys=frozenset({
            "target.temperature_K",
            "optics.aperture_diameter_m",
            "optics.focal_length_m",
            "detector.pixel_pitch_x_um",
            "detector.qe_input",
            "detector.read_noise_e_rms",
            "platform.altitude_m",
            ...
        }),
        consistency_groups=("transmission", "integration_time"),
        forbidden_combinations=(),
        regime=frozenset({EXTENDED, POINT, SUB_PIXEL}),
    ),
    ...
}
```

The runtime workflow (`radiant/performance/registry.py`):
1. Run the chain to produce a `ChainState`.
2. For each requested metric, `can_compute(name, state)` checks the `MetricSpec` requirements (frames, stage outputs, noise terms, prerequisite metrics, regime).
3. `available_metrics(state)` returns the set of computable metrics.
4. `missing_for(name, state)` reports exactly which frames / stage outputs / noise terms / metrics are absent, per category.

(There is no `radiant metrics` CLI subcommand today; the functions above are the programmatic interface.) `performance/tests/test_registry.py` covers the registry behavior; there is no automated markdown-tree drift check — keep §3 in sync manually per Rule 20.

---

## 6. Open Questions

1. **Should plugin metrics be required to declare their dependencies in this format?** Probably yes — otherwise the resolver cannot validate them. Proposed: `Metric.dependency() -> MetricDependency` is a required abstract method.
2. **How to handle metrics whose dependencies are dynamic** (e.g., NIIRS that includes an MTF compensation term `G` only if MTFC is enabled)? Current plan: declare the *maximum* dependency set; let `compute()` skip the optional pieces at runtime. The static check is conservative.
3. **Where do consistency groups live?** Currently planned in RADIANT_Parameter_System.md, referenced from here. The resolver evaluates them at the parameter level, before the metric trees are walked.

---
