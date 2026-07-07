# RADIANT v1 Scope Decisions

**Date:** 2026-04-06  
**Status:** Accepted  
**Derived from:** RADIANT_Physics_Inventory.md (adjudicated scope triage)  
**Constraints applied:**
- OUT: molecular plume spectroscopy, multi-band/hyperspectral sensors, custom mesh import
- STUBBED acceptable: atmospheric turbulence, exotic BRDFs, stray light from first principles, stellar catalogs
- IN: everything else with a reasonable implementation path

---

## IN v1 — 82 Effects

### Stage 1: Source / Target Radiation (9 of 15)

| ID | Effect | Key Input Parameters |
|----|--------|---------------------|
| S1 | Planck thermal emission | T (K), ε(λ) |
| S2 | Reflected solar irradiance | E_sun(λ), ρ_BRDF, solar zenith angle |
| S3 | Reflected diffuse sky radiance | L_sky(λ) from MODTRAN or simple model |
| S4 | Target emissivity | ε(λ) table or scalar |
| S5 | Target BRDF | Lambertian ρ; hook for full BRDF model |
| S6 | Target temperature non-uniformity | Temperature histogram or two-temperature {T_hot, T_cool, f_hot} |
| S7 | Self-luminous emission | User-supplied L_source(λ); additive term |
| S10 | Reflected moonlight | Lunar phase angle, lunar irradiance spectrum |
| — | (MWIR note) | S1 + S2 + S3 are simultaneously active in MWIR; architecture must sum all source terms |

### Stage 2: Atmospheric Propagation (9 of 19)

| ID | Effect | Key Input Parameters |
|----|--------|---------------------|
| A1 | Molecular absorption | MODTRAN τ(λ) table OR species column amounts + profile |
| A2 | Spectral transmittance τ(λ) | Product of all atmospheric contributions |
| A3 | Path radiance L_path(λ) | MODTRAN output or simple scattering model |
| A4 | Atmospheric thermal emission L_atm(λ) | MODTRAN output or T_atm profile |
| A5 | Rayleigh scattering | Wavelength, molecular density; implicit in MODTRAN |
| A6 | Aerosol extinction | AOD, aerosol type, Ångström exponent; or MODTRAN |
| A7 | Aerosol phase function | Henyey-Greenstein asymmetry g |
| A8 | Water vapor continuum | PWV (cm), temperature; or MODTRAN |
| A9 | Ozone absorption | Ozone column (DU); or MODTRAN |
| A10 | Cloud/fog attenuation | Cloud optical depth τ_cloud, cloud altitude |

### Stage 3: Optical Train (11 of 19)

| ID | Effect | Key Input Parameters |
|----|--------|---------------------|
| O1 | Aperture area | Entrance pupil diameter D |
| O2 | Central obscuration | Obscuration ratio ε = D_secondary/D_primary |
| O3 | Net optical transmittance | Per-surface T_i(λ) table; or bulk τ_opt(λ) |
| O4 | Spectral bandpass filter | λ_c, Δλ, T_filter(λ), OOB rejection ratio |
| O5 | Warm optics emission | T_optics, ε_optics(λ), solid angle subtended |
| O6 | Cold stop efficiency | η_cold = Ω_cold / Ω_det |
| O7 | Narcissus | T_detector, surface reflectances, solid angle; simplified DC offset model |
| O11 | Diffraction PSF | D, ε_obscuration, λ, f/# |
| O12 | Wavefront error (Strehl) | σ_WFE (waves RMS) |
| O13 | Defocus | Blur circle diameter d (pixels); feeds SP11 |
| O15 | Thermal defocus | dn/dT, CTE, ΔT_thermal; maps to d → feeds O13 |
| O16 | Vignetting | T(θ_x, θ_y) table or polynomial coefficients |
| O18 | F/# and plate scale | Focal length f, pixel pitch p, f/# |
| O19 | Étendue | Implicit: A × Ω × τ_opt |

### Stage 4: Detector (20 of 27)

| ID | Effect | Key Input Parameters |
|----|--------|---------------------|
| D1 | Quantum efficiency | QE(λ) table; detector material |
| D2 | Pixel pitch and fill factor | Pixel pitch p, fill factor FF |
| D3 | Shot noise | S_signal (e⁻) |
| D4 | Dark current | J_dark (e⁻/s/pixel), T_detector |
| D5 | Dark current shot noise | J_dark, t_int |
| D6 | Read noise | σ_read (e⁻ RMS) |
| D7 | Fixed pattern noise (DSNU) | σ_DSNU (e⁻); residual after NUC |
| D8 | PRNU | σ_PRNU (%); residual after flat-field |
| D9 | NUC residual | NUC order, time since correction, ΔT_detector |
| D10 | 1/f noise | Corner frequency f_c, noise PSD coefficient |
| D11 | kTC reset noise | Node capacitance C, T; conditional on CDS flag |
| D12 | Quantization noise | ADC bits N, full-scale range |
| D13 | Saturation / full well | FWC (e⁻) |
| D14 | Nonlinearity | Polynomial coefficients; max nonlinearity (%) |
| D15 | Blooming | Overflow fraction, number of affected neighbors |
| D16 | Electrical crosstalk (IPC) | Coupling coefficient α |
| D18 | Charge diffusion | Minority carrier diffusion length L_d |
| D19 | Persistence | Persistence fraction f_persist, time constant τ, prior frame signal S_prev (user input) |
| D20 | Cosmic rays | Particle flux (e/cm²/day), pixel area; returns event rate statistic |
| D21 | Radiation damage | TID (krad), shielding thickness; scales J_dark via Arrhenius model |
| D22 | Detector glow + R12 mux glow | Combined internal glow rate (e⁻/s/pixel) |
| D25 | CTE (CCD) | CTE per transfer, N_transfers; conditional on detector type = CCD |
| D26 | Bad/dead pixels | Bad pixel fraction |
| D27 | Temperature effects on dark current | Arrhenius coefficients, T_detector |

### Stage 5: Readout Electronics (10 of 17)

| ID | Effect | Key Input Parameters |
|----|--------|---------------------|
| R1 | Integration time | t_int (s) |
| R2 | CDS | CDS flag (on/off) |
| R3 | TDI | N_TDI stages |
| R4 | TDI velocity mismatch smear | Velocity match error ε_v (fraction of pixel/stage) |
| R5 | Pixel binning | Binning factor N_x × N_y |
| R6 | Frame coadding | N_coadd; SNR improvement √N_coadd |
| R7 | Programmable gain | Gain G (e⁻/DN) |
| R8 | ADC resolution | N bits; LSB = FWC / 2^N |
| R10 | Bias/offset drift | Drift coefficient (DN/°C), ΔT_detector |
| R11 | 1/f readout noise | Subsumed in D10; ROIC corner frequency f_c |
| R16 | Anti-blooming drain | Drain efficiency; FWC_eff = FWC × (1 − η_drain) |

### Stage 6: Spatial Effects (13 of 17)

| ID | Effect | Key Input Parameters |
|----|--------|---------------------|
| SP1 | Diffraction PSF | D, ε_obscuration, λ |
| SP2 | Aberration PSF (Strehl) | σ_WFE; Strehl = exp(−(2πσ/λ)²) |
| SP3 | Pixel aperture MTF | Pixel pitch p, fill factor FF |
| SP4 | Sampling MTF | System Q = λ(f/#)/p |
| SP5 | Linear smear MTF | v_img (pixels/s), t_int |
| SP6 | Random jitter MTF | σ_jitter (µrad RMS) |
| SP7 | LOS drift | Combined with SP5: (v_smear + v_drift) × t_int |
| SP8 | Platform vibration | Vibration PSD → integrated σ_jitter feeding SP6 |
| SP10 | TDI alignment MTF | Yaw misalignment angle, N_TDI |
| SP11 | Defocus MTF | Blur circle d from O13; jinc(πd·f) |
| SP13 | Registration error | σ_registration (pixels RMS) |
| SP15 | Aliasing | System Q; flag if Q < 2 |
| SP17 | Charge diffusion MTF | Diffusion length L_d from D18 |

### Stage 7: Scene / Background (6 of 12)

| ID | Effect | Key Input Parameters |
|----|--------|---------------------|
| SC1 | Background radiance | T_bg (LWIR) or ρ_bg + illumination (VIS/SWIR) |
| SC2 | Background spatial clutter | σ_clutter; detection threshold = f(SNR, CNR) |
| SC3 | Thermal background variability | ΔT_bg statistics |
| SC4 | Sun glint | Solar angle, wind speed, view geometry; Cox-Munk model |
| SC6 | Mixed pixel / fill fraction | Target fill fraction η = A_target / A_pixel |
| SC7 | Target-background contrast | ΔL = L_target − L_background at sensor |
| SC12 | Partial cloud cover | Cloud fraction, τ_cloud from A10 |

---

## STUBBED v1 — 8 Effects

These effects have parameter hooks in the API but return zero/unity/identity. They can be upgraded without breaking the interface.

| ID | Effect | Stub Behavior | Reason for Stub |
|----|--------|--------------|-----------------|
| A13 | Turbulence (r₀, Cn²) | Parameters stored; feeds SP9 | Acceptable per constraints |
| A14 | Turbulence MTF | Returns 1.0 for space; long-exposure Kolmogorov model for ground | Acceptable per constraints |
| O8 | Stray light | SLRR parameter accepted; uniform additive background | First-principles BSDF out of scope |
| D24 | Snow/sparkle (RTS) | Rolled into bad pixel fraction (D26) | Subsumed by D26 |
| R15 | Data rate / compression | Lossy flag only; no artifact model | Artifact simulation out of scope |
| R17 | Rolling shutter | Snapshot assumed; flag reserved | Edge case for design trades |
| SP9 | Turbulence MTF | Returns 1.0 for space; Fried parameter model for ground | Acceptable per constraints |
| SP16 | Pointing knowledge error | Returns angular error parameter; no radiometric effect | Geolocation tool concern |

---

## DEFERRED — 26 Effects

Explicitly out of scope for v1. Not silently ignored — each has a stated reason.

| ID | Effect | Reason |
|----|--------|--------|
| S8 | Spectrally selective emission (plumes) | Molecular spectroscopy engine required; explicitly OUT |
| S9 | Reflected earthshine | Space-to-space geometry; not a v1 priority |
| S11 | Airglow | Upward-looking space geometry; specialized |
| S12 | Doppler shift | Passive broadband sensors; irrelevant |
| S13 | Fluorescence | Biological/vegetation sensing; specialized |
| S14 | Interreflection | Scene ray tracing required |
| S15 | Stellar background | Space surveillance; explicitly stubbed per constraints |
| A11 | Rain attenuation | Low priority for EO |
| A12 | Atmospheric refraction | Pointing/geolocation tool; not radiometric |
| A15 | Anisoplanatism | AO system context required |
| A16 | Scintillation | Point-source specific; specialized |
| A17 | Adjacency effect | Requires scene radiance array; architectural prerequisite not met in v1 |
| A18 | Atmospheric polarization | Out of scope v1 |
| A19 | Window/dome refraction | Optical design tool |
| O9 | Ghost images | Stray light tool responsibility |
| O10 | Surface scatter (BSDF) | UV-specific; first-principles stray light out of scope |
| O14 | Chromatic aberration | Refractive system design tool |
| O17 | Polarization in optics | Out of scope v1 |
| D17 | Optical crosstalk | Detailed detector model required |
| D23 | Trapping states | Too detailed for performance tool |
| R9 | ADC nonlinearity (INL/DNL) | Electronics design tool level |
| R13 | Clock feedthrough | Electronics design tool level |
| R14 | Power supply noise | Electronics design tool level |
| SP12 | Scan mechanism MTF | Whiskbroom scanner specific |
| SP14 | Geometric distortion | Geolocation calibration tool; not radiometric |
| SC5 | Shadow effects | Scene geometry tool |
| SC8 | Temporal scene variability | Revisit analysis tool |
| SC9 | Urban heat island | Scene-specific; not sensor performance |
| SC10 | Terrain-induced variation | Scene generation tool |
| SC11 | Spectral clutter | Multispectral/hyperspectral; phase 2 |

---

## Summary

| Status | Count |
|--------|-------|
| ✅ IN v1 | 82 |
| 🔶 STUBBED v1 | 8 |
| ❌ DEFERRED | 26 |
| **Total** | **116** |

---

## Open Architectural Decisions Surfaced by This Scope

The following must be resolved before implementation begins:

1. **Frame model:** RADIANT models single exposures. Coadds (R6) are handled as a scaling factor. Persistence (D19) uses prior frame signal level as a user-supplied input parameter — not live state. This keeps the tool stateless per computation.

2. **MWIR dual-source:** S1 (thermal) and S2 (reflected solar) are simultaneously active in MWIR. The source stage must sum contributions from Planck emission, reflected solar, reflected sky (S3), and self-luminous (S7) before propagating through the atmosphere.

3. **Atmosphere interface:** Three mandatory outputs from the atmospheric model: τ(λ), L_path(λ), L_atm(λ). All three must flow into the signal chain. A scalar transmittance is architecturally insufficient.

4. **MTF chain:** System MTF = ∏ MTF_i over all spatial terms. At minimum 11 MTF terms are now IN scope (SP1–SP8, SP10–SP11, SP13, SP15, SP17). This must be a composable product chain, not hardcoded.

5. **Noise budget chain:** At minimum 12 independent noise terms are IN scope. Each must be computed and reported independently before quadrature combination. The output must include a full noise budget breakdown, not just total noise.

6. **Internal glow consolidation:** D22 (detector glow) and R12 (mux glow) are combined into a single internal glow parameter (e⁻/s/pixel). The user does not distinguish source; the combined rate is the input.

7. **Coadds and D19 coupling:** When N_coadd > 1, persistence accumulates across coadded frames. The persistence model (D19) must account for N_coadd as a multiplier on the temporal exposure.
