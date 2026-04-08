# RADIANT Physics Inventory

**Version:** 0.1  
**Date:** 2026-04-06  
**Status:** Draft — Pending Scope Triage Review  
**Purpose:** Exhaustive enumeration of physical effects that influence EO sensor performance, UV through LWIR. Each effect is characterized and triaged for v1 scope. No effect is silently ignored — every deferral is explicit.

---

## Notation

**Type:** F = Fundamental (physics of the phenomenon), E = Engineering (implementation/hardware artifact)  
**Regimes:** UV = 0.2–0.4 µm, VIS = 0.4–0.7 µm, SWIR = 0.7–2.5 µm, MWIR = 3–5 µm, LWIR = 8–14 µm  
**Magnitude:** Order-of-magnitude effect on signal or noise floor  
**Practice:** Whether this effect is typically modeled or ignored in performance tools  

---

## 1. Source / Target Radiation

| # | Effect | Type | Regimes | Magnitude | Practice | Input Parameters |
|---|--------|------|---------|-----------|----------|-----------------|
| S1 | **Planck thermal emission** — blackbody/graybody emission from target at temperature T | F | MWIR, LWIR (secondary in SWIR) | Dominant in LWIR; 10⁻²–10² W/m²/sr/µm | Always modeled | Target temperature T, emissivity ε(λ) |
| S2 | **Reflected solar irradiance** — specular and diffuse reflection of direct solar beam | F | UV, VIS, SWIR (secondary in MWIR) | Dominant in VIS/SWIR; ~10² W/m²/µm at TOA | Always modeled | Solar irradiance E_sun(λ), target BRDF ρ(λ,θᵢ,θᵣ,φ), solar zenith angle |
| S3 | **Reflected diffuse sky radiance** — reflection of atmospheric downwelling into sensor FOV | F | UV, VIS, SWIR | 1–20% of direct solar contribution depending on surface albedo | Modeled in rigorous tools; often ignored in simple models | Sky radiance L_sky(λ,Ω), hemispherically-integrated BRDF |
| S4 | **Target emissivity** — spectral departure from blackbody; ε(λ) < 1 | F | MWIR, LWIR | 5–40% effect on emitted radiance for ε = 0.6–0.95 | Always modeled | Spectral emissivity ε(λ) or emissivity library |
| S5 | **Target BRDF** — bidirectional reflectance distribution function; non-Lambertian angular dependence | F | UV, VIS, SWIR, MWIR | Factor of 2–10× between Lambertian and specular for same material | Modeled in high-fidelity; Lambertian assumed in simple | BRDF model (Lambertian ρ, Hapke, Cook-Torrance, or tabulated); view/illumination geometry |
| S6 | **Target temperature non-uniformity** — spatial variation of temperature within resolution element | F | MWIR, LWIR | Subresolution hot spots can increase apparent radiance 10–100× | Usually ignored in simple models | Temperature distribution or effective temperature + contrast |
| S7 | **Self-luminous emission** — combustion, exhaust plumes, fires, rocket motor | F | MWIR, LWIR (VIS for visible flame) | Can exceed Planck background by 10²–10⁴× for hot targets | Modeled when relevant | Flame temperature, species concentrations, plume geometry |
| S8 | **Spectrally selective emission** — molecular emission bands (CO₂, H₂O in exhaust plumes) | F | MWIR, LWIR | 1–3 orders of magnitude above background in narrow bands | Modeled for plume/exhaust targets; ignored otherwise | Molecular species concentrations, temperature, path length |
| S9 | **Reflected earthshine** — Earth thermal/reflected radiation illuminating space targets | F | MWIR, LWIR | 1–10% of solar for LEO targets; geometry dependent | Ignored in most tools; significant for space-to-space geometry | Earth spectral radiance model, target-Earth geometry |
| S10 | **Reflected moonlight** — lunar illumination of surface targets at night | F | VIS, SWIR | ~10⁻⁶ of solar irradiance (full moon) | Rarely modeled; relevant for nighttime VIS performance | Lunar phase, lunar irradiance spectrum, geometry |
| S11 | **Airglow** — chemiluminescent emission from upper atmosphere | F | UV, VIS, SWIR | ~10⁻⁴ W/m²/sr/µm; relevant for space-to-ground looking up | Rarely modeled | Altitude, solar activity index, spectral airglow model |
| S12 | **Doppler shift** — wavelength shift due to relative radial velocity between target and sensor | F | All | ~0.01–1 nm shift per 1000 km/h; significant in narrow-band or LiDAR | Usually ignored for passive broadband sensors | Relative radial velocity, center wavelength, spectral resolution |
| S13 | **Target fluorescence** — photon emission at wavelength different from excitation | F | UV, VIS | Very material-specific; typically < 1% of reflectance signal | Ignored except in vegetation/biological sensing | Excitation spectrum, fluorescence yield, emission spectrum |
| S14 | **Interreflection / multiple bounce** — radiation from one surface illuminating another in scene | F | All | 1–5% for simple scenes; significant in urban canyons or cavities | Usually ignored | Scene geometry, surface BRDF, multiple bounce order |
| S15 | **Stellar background** — star flux incident on space-based sensor | F | UV, VIS, SWIR | Negligible per resolution element except for very dim targets | Ignored for Earth observation; relevant for space surveillance | Star catalog, sensor FOV, spectral bandpass |

---

## 2. Atmospheric Propagation

| # | Effect | Type | Regimes | Magnitude | Practice | Input Parameters |
|---|--------|------|---------|-----------|----------|-----------------|
| A1 | **Molecular absorption** — line-by-line absorption by H₂O, CO₂, O₃, CH₄, N₂O, CO, O₂ | F | All (band-specific) | 0–100% attenuation in absorption bands; defines transmission windows | Always modeled | Species column densities, temperature/pressure profile, path geometry; or MODTRAN output |
| A2 | **Spectral transmittance** — net wavelength-dependent path transmission τ(λ) | F | All | 0–1 per resolution element; product of all absorption and scattering | Always modeled | Atmosphere profile, geometry, or MODTRAN τ(λ) table |
| A3 | **Path radiance** — photons scattered into sensor FOV from sun/sky by atmosphere | F | UV, VIS, SWIR | Dominates over surface signal in UV/VIS hazy conditions; up to 80% of TOA signal | Always modeled | Aerosol loading, solar geometry, view geometry, wavelength; or MODTRAN L_path(λ) |
| A4 | **Atmospheric thermal emission** — blackbody emission from atmospheric gases along path | F | MWIR, LWIR | Dominant background term in LWIR; comparable to target in MWIR | Always modeled | Atmospheric temperature profile, species concentrations; or MODTRAN L_atm(λ) |
| A5 | **Rayleigh scattering** — molecular scattering from N₂, O₂; λ⁻⁴ dependence | F | UV, VIS | Significant in UV/VIS; sets sky background and limits contrast | Always modeled (included in MODTRAN) | Wavelength, molecular density profile |
| A6 | **Aerosol extinction** — scattering + absorption by particulates (dust, smoke, haze, maritime) | F | UV, VIS, SWIR, MWIR | 10–90% signal reduction at high aerosol loading | Always modeled | Aerosol optical depth (AOD), type (rural/urban/maritime/desert), spectral dependence |
| A7 | **Aerosol scattering phase function** — angular distribution of scattered light | F | UV, VIS, SWIR | ±20–50% error in path radiance if isotropic assumed vs. Mie | Modeled in rigorous tools (MODTRAN); often simplified | Aerosol type, size distribution, wavelength; Henyey-Greenstein asymmetry g |
| A8 | **Water vapor continuum absorption** — broadband absorption between lines in near-IR windows | F | SWIR, MWIR | 10–30% transmission reduction in 2–2.5 µm window at high humidity | Modeled in MODTRAN; often ignored in simplified models | Precipitable water vapor (PWV), temperature |
| A9 | **Ozone absorption** — Hartley/Huggins bands (UV) and Chappuis band (VIS) | F | UV, VIS | Near-total absorption below 0.3 µm; 10–30% in 0.6 µm Chappuis | Always modeled | Ozone column (Dobson units), altitude profile |
| A10 | **Cloud/fog attenuation** — scattering and absorption by liquid water droplets | F | All | Near-zero transmission through optically thick clouds | Modeled as blocking condition (on/off) or cloud optical depth | Cloud optical depth, droplet distribution, altitude |
| A11 | **Rain attenuation** — scattering by precipitation | F | MWIR, LWIR (less in VIS) | 1–20 dB/km at heavy rain rates; more significant in LWIR | Modeled only when explicitly needed; often ignored | Rain rate (mm/hr), drop size distribution, path length |
| A12 | **Atmospheric refraction** — bending of ray path due to refractive index gradient | F | All | Displaces apparent target position; < 1 mrad at moderate elevation | Usually ignored for performance; important for pointing/geolocation | Temperature/pressure/humidity profile vs. altitude, elevation angle |
| A13 | **Turbulence (isoplanatic angle, Fried parameter r₀)** — refractive index fluctuations from thermal mixing | F | UV, VIS, SWIR | Limits resolution to 5–20 cm seeing at sea level; wavelength dependent (r₀ ∝ λ^(6/5)) | Modeled for ground-based; often ignored for space-based short exposures | Cn² profile (turbulence strength vs. altitude), path geometry, wavelength |
| A14 | **Turbulence MTF** — degradation of spatial resolution by turbulence (long and short exposure) | F | UV, VIS, SWIR | Dominates over diffraction for apertures > r₀ at sea level | Modeled when turbulence matters | r₀, outer scale L₀, exposure time, aperture diameter |
| A15 | **Anisoplanatism** — spatial variation of turbulence across FOV | F | UV, VIS, SWIR | Limits AO correction field; significant when FOV > isoplanatic angle θ₀ | Usually ignored for wide-FOV sensors | θ₀, Cn² profile |
| A16 | **Scintillation** — intensity fluctuations due to turbulence | F | UV, VIS, SWIR | Point source intensity variance σ²_I ~ 0.1–1.0 in strong turbulence | Modeled for point targets; ignored for extended scenes | Rytov variance σ²_R, path geometry, wavelength |
| A17 | **Adjacency effect** — scattered light from neighboring scene elements contributing to pixel signal | F | UV, VIS, SWIR | 1–15% signal contamination at visible wavelengths over bright/dark boundaries | Rarely modeled; significant for urban/rural edges | Atmospheric PSF, scene reflectance distribution, wavelength |
| A18 | **Polarization by atmosphere** — Rayleigh scattering polarizes light up to ~70% at 90° scatter angle | F | UV, VIS | Not in scope v1; noted for completeness | Out of scope | — |
| A19 | **Refraction through windows/domes** — path bending at sensor aperture window | E | All | < 1 arcsec; small unless extreme angles or thick window | Usually ignored | Window material, thickness, wedge angle |

---

## 3. Optical Train

| # | Effect | Type | Regimes | Magnitude | Practice | Input Parameters |
|---|--------|------|---------|-----------|----------|-----------------|
| O1 | **Aperture area** — collecting area determines photon flux | F | All | Linear scaling with A = π(D/2)² (minus obscuration) | Always modeled | Aperture diameter D, obscuration ratio ε |
| O2 | **Central obscuration** — secondary mirror / Cassegrain obstruction reduces effective area | E | All | 10–30% area reduction; also modifies PSF sidelobe structure | Always modeled | Obscuration ratio ε = D_secondary/D_primary |
| O3 | **Net optical transmittance / reflectance** — combined throughput of all surfaces | E | All | 0.3–0.9 depending on number of surfaces and coatings | Always modeled | Per-surface reflectance R_i(λ) or transmittance T_i(λ); product τ_opt(λ) = ∏T_i |
| O4 | **Spectral bandpass filter** — defines wavelength band of measurement | E | All | Defines integration limits; OOB rejection determines stray light vulnerability | Always modeled | Center wavelength λ_c, FWHM Δλ, in-band transmission, OOB rejection ratio |
| O5 | **Warm optics thermal emission** — self-emission of optical elements at instrument temperature | F | MWIR, LWIR | Can dominate focal plane signal; emissivity × Planck at T_optics | Always modeled in MWIR/LWIR; irrelevant in VIS/SWIR | Optical element temperature T_opt, effective emissivity ε_optics(λ) |
| O6 | **Cold stop / Lyot stop efficiency** — fraction of detector solid angle filled by cold stop | E | MWIR, LWIR | Cold stop efficiency < 1 allows warm background into detector; 10–100% NEDT impact | Always modeled for cooled sensors | Cold stop solid angle Ω_cold, detector IFOV solid angle Ω_det; efficiency η = Ω_cold/Ω_det |
| O7 | **Narcissus effect** — retroreflection of detector self-image back onto detector through optics | E | MWIR, LWIR | Fixed-pattern DC offset; changes with focus/temperature; 1–10% of NEDT | Modeled in high-fidelity MWIR tools; often stubbed | Optical prescription, detector temperature, reflection coefficients at each surface |
| O8 | **Stray light (out-of-field)** — radiation from sources outside FOV reaching focal plane | E | All | 10⁻⁶–10⁻³ fraction of in-field signal; design-dependent | Usually modeled qualitatively; stubbed in performance tools | Stray light rejection ratio (SLRR), source geometry |
| O9 | **Ghost images** — internal reflections between optical surfaces creating secondary images | E | All | 10⁻⁴–10⁻² of primary image; antireflection coating dependent | Usually ignored in performance tools; modeled in stray light tools | Per-surface reflectance, surface spacing, image plane geometry |
| O10 | **Surface scatter (BSDF)** — scattering from polishing errors and contamination | E | UV, VIS, SWIR | 10⁻⁶–10⁻⁴ of specular signal; TIS = (4πσ_rms/λ)² | Usually ignored; significant in UV or high-contrast applications | RMS surface roughness σ_rms, BSDF model, wavelength |
| O11 | **Diffraction PSF** — Airy pattern from circular aperture; core + rings | F | All | Resolves structures > 1.22λ/D; ring energy 16% of total | Always modeled | Aperture D, obscuration ε, wavelength λ |
| O12 | **Wavefront error (WFE)** — phase aberrations reducing Strehl ratio and broadening PSF | E | All | Strehl S = exp(−(2πσ_WFE/λ)²); σ_WFE = λ/14 gives S = 0.8 | Modeled as bulk Strehl in performance tools; Zernike decomposition for high-fidelity | RMS WFE σ_WFE, or Zernike coefficients Z_n^m |
| O13 | **Defocus** — Z4 Zernike; temperature or mechanism-induced | E | All | Dominant low-order aberration; easily ±50% Strehl if uncorrected | Often modeled as Strehl factor; thermal defocus modeled separately | Defocus in waves W₀₂₀, or δz in focal plane |
| O14 | **Chromatic aberration** — wavelength-dependent focal length (refractive systems) | E | UV, VIS, SWIR | Significant in refractive systems; reflective systems are chromatic-aberration free | Modeled when refractive elements present | Abbe number V, lens prescription; or Δfocus vs. λ |
| O15 | **Thermal defocus** — focal length change with temperature | E | All | 10–100 µm focus shift per °C for aluminum-mirror systems | Modeled in thermal/structural tools; usually stubbed in radiometric tools | Thermal expansion coefficient, thermo-optic coefficient, temperature range |
| O16 | **Vignetting** — off-axis reduction in throughput | E | All | 0–50% at field edge depending on design | Modeled as field-angle-dependent throughput map | Vignetting function T(θ_x, θ_y) |
| O17 | **Polarization effects in optics** — birefringence, reflection polarization (Fresnel) | F | UV, VIS, SWIR | < 5% for most designs; significant for high-incidence-angle mirrors | Not in scope v1 | — |
| O18 | **F/# and plate scale** — determines IFOV and photon solid angle | F | All | Fundamental scaling: IFOV = p/f; Ω = π/(4(f/#)²) | Always modeled | Focal length f, pixel pitch p, f-number f/# |
| O19 | **Optical bandwidth (étendue)** — A·Ω product conservation through optical train | F | All | Sets fundamental limit on radiance throughput | Always modeled (implicit in area × solid angle × transmittance) | Aperture A, IFOV solid angle Ω, optical throughput |

---

## 4. Detector

| # | Effect | Type | Regimes | Magnitude | Practice | Input Parameters |
|---|--------|------|---------|-----------|----------|-----------------|
| D1 | **Quantum efficiency (QE)** — probability of photon → electron conversion; spectral | F | All | 0.1–0.95 depending on material and wavelength | Always modeled | QE(λ) table or model; detector material (Si, InGaAs, HgCdTe, InSb, etc.) |
| D2 | **Pixel pitch and fill factor** — physical pixel size and active fraction | E | All | Linear effect on signal; fill factor 0.5–1.0 | Always modeled | Pixel pitch p, fill factor FF |
| D3 | **Shot noise (photon noise)** — Poisson fluctuation in detected photoelectron count | F | All | σ_shot = √(S_signal); fundamental noise floor in high-signal regime | Always modeled | Signal electrons S = QE × Φ_photons × t_int |
| D4 | **Dark current** — thermally generated electrons without incident photons | F | All | Doubles every ~6–8°C for HgCdTe; 1–10⁶ e⁻/s/pixel depending on T and material | Always modeled | Dark current density J_dark (e⁻/s/pixel), detector temperature T_det |
| D5 | **Dark current shot noise** — Poisson fluctuation in dark current | F | All | σ_dark = √(J_dark × t_int) | Always modeled | J_dark, t_int |
| D6 | **Read noise** — electronic noise from the readout process (source follower, amplifier) | E | All | 1–100 e⁻ RMS depending on ROIC design and readout rate | Always modeled | Read noise σ_read (e⁻ RMS) |
| D7 | **Fixed pattern noise (FPN) — pixel-to-pixel** — spatial non-uniformity in offset (dark signal) | E | All | 0.1–5% of full well; appears as structured background | Always modeled | DSNU σ_DSNU (e⁻); corrected by NUC but residual remains |
| D8 | **Photo-response non-uniformity (PRNU)** — pixel-to-pixel gain variation | E | All | 0.1–2% of signal; gain-proportional fixed pattern | Always modeled | PRNU σ_PRNU (%); corrected by flat-field but residual remains |
| D9 | **NUC residual error** — residual non-uniformity after two-point or scene-based correction | E | MWIR, LWIR | Typically 0.01–0.1% of dynamic range post-correction; key NEDT driver | Always modeled in IR performance tools | NUC correction order (1-point, 2-point), time since correction, temperature drift |
| D10 | **1/f noise (flicker noise)** — low-frequency noise with power spectral density ∝ 1/f | E | All | 1–30 e⁻ RMS integrated over measurement bandwidth; scan-dependent | Modeled in detailed noise analyses; often ignored in simple SNR calculations | Corner frequency f_c, noise power at reference frequency, integration bandwidth |
| D11 | **kTC (reset) noise** — thermal noise from resetting detector capacitance | E | All | σ_kTC = √(kTC/q²); 10–200 e⁻; eliminated by CDS | Often ignored if CDS is assumed; must model if CDS not used | Node capacitance C, temperature T; eliminated by CDS |
| D12 | **Quantization noise** — error from ADC digitization | E | All | σ_q = LSB/√12; 0.3 LSB RMS | Always modeled when ADC bits < ~14 | ADC full-scale range, number of bits N; LSB = FS/2^N |
| D13 | **Saturation / full well capacity** — maximum charge storage per pixel before blooming | E | All | Sets dynamic range upper limit; 10⁴–10⁶ e⁻ | Always modeled | Full well capacity FWC (e⁻), integration time t_int |
| D14 | **Nonlinearity** — departure of output from linear response to input signal | E | All | 0.1–5% deviation from linear; distorts radiometric accuracy | Modeled as polynomial correction; often ignored in simple models | Nonlinearity curve or polynomial coefficients; max nonlinearity (%) |
| D15 | **Blooming** — charge overflow from saturated pixel into neighbors | E | All | Spreads 1–100+ pixels from saturated source | Usually modeled as on/off saturation; bloom spread rarely modeled | Saturation threshold, anti-blooming drain current (if present) |
| D16 | **Electrical crosstalk** — charge coupling between pixels via interpixel capacitance | E | All | 0.5–5% of signal transferred to neighbors | Often ignored; modeled as MTF degradation or as explicit coupling matrix | Interpixel capacitance C_IPC/C_pixel ratio |
| D17 | **Optical crosstalk** — photon scattering between pixels within detector material | E | MWIR, LWIR (HgCdTe) | 1–10% for thick absorbing layers; diffusion-limited | Modeled in high-fidelity detector tools; often ignored | Absorber thickness, minority carrier diffusion length, pixel pitch |
| D18 | **Charge diffusion** — lateral spreading of photocarriers before collection | E | All | Broadens effective pixel response; degrades MTF | Often modeled as detector MTF term | Diffusion length L_d, depletion width, pixel pitch |
| D19 | **Persistence / image lag** — residual signal from previous high-signal frames | E | MWIR, LWIR (HgCdTe, InSb) | 0.1–5% of previous signal remaining in next frame | Modeled in high-fidelity; often ignored in performance tools | Time constant τ_persist, previous signal level |
| D20 | **Cosmic rays / energetic particles** — ionizing particle tracks producing transient signal spikes | E | All (space environment) | ~100–10,000 events/cm²/day at LEO; deposits 10³–10⁶ e⁻ per event | Usually modeled as a rate statistic; not spatially modeled | Particle flux (LEO vs. GEO vs. HEO), shielding thickness, detector volume |
| D21 | **Radiation damage** — accumulated TID and displacement damage degrading QE and dark current | E | All (space) | Dark current increase 10–100× over mission life at unshielded LEO | Modeled in mission lifetime analysis; often ignored in initial performance | Total ionizing dose (krad), displacement damage dose (MeV·cm²/g), shielding model |
| D22 | **Detector self-emission (glow)** — ROIC or detector emitting photons that illuminate itself | E | MWIR, LWIR | 10–1000 e⁻/s/pixel; DC offset but spatially structured | Modeled in high-fidelity MWIR/LWIR designs; often stubbed | Glow level (e⁻/s/pixel), glow pattern |
| D23 | **Trapping states / charge trapping** — interface states capturing and releasing charge with time constants | E | MWIR, LWIR | Creates non-exponential persistence; complicates NUC | Usually ignored in performance tools | Trap density, time constants τ_trap |
| D24 | **Snow/sparkle noise** — random telegraph signal in HgCdTe pixels; intermittent high-noise pixels | E | MWIR, LWIR | Affects 0.01–0.1% of pixels; can increase effective read noise 10× | Usually modeled as bad pixel fraction | RTS amplitude, affected pixel fraction |
| D25 | **Charge transfer efficiency (CTE)** — fraction of charge transferred per CCD shift | E | UV, VIS, SWIR (CCD) | 1 − CTE per transfer; 10⁴ transfers → 0.9999^10000 = 0.37 at CTE = 0.99999 | Always modeled for CCD; not relevant for CMOS/ROIC | CTE per transfer, number of transfers |
| D26 | **Bad/dead pixels** — pixels with zero or pathological response | E | All | 0.01–1% of array; handled by flagging and interpolation | Modeled as a fraction; spatial pattern usually not modeled | Bad pixel fraction, bad pixel map (if available) |
| D27 | **Operating temperature effects on QE and dark current** — temperature-dependent material properties | F | All | Dark current: factor of 2 per 6–8°C; QE: < 5% over operating range | Always modeled for dark current; QE temperature dependence often ignored | Detector operating temperature T_det, T-dependence coefficients |

---

## 5. Readout Electronics

| # | Effect | Type | Regimes | Magnitude | Practice | Input Parameters |
|---|--------|------|---------|-----------|----------|-----------------|
| R1 | **Integration time** — duration of charge accumulation; sets signal and noise levels | E | All | Linear effect on signal and dark current; sets saturation headroom | Always modeled | Integration time t_int; constrained by dwell time, frame rate, saturation |
| R2 | **Correlated Double Sampling (CDS)** — reset-then-sample to cancel kTC noise | E | All | Eliminates kTC noise; increases bandwidth noise by √2 | Modeled as noise reduction; assumed ON by default in most modern ROICs | CDS flag (on/off); noise multiplier √2 on thermal/1/f noise components |
| R3 | **Time Delay Integration (TDI)** — accumulation over multiple rows as image moves across detector | E | All (pushbroom sensors) | Increases signal by N_TDI, noise by √N_TDI → SNR improvement √N_TDI | Always modeled when TDI used | Number of TDI stages N_TDI; velocity matching accuracy ε_v |
| R4 | **TDI velocity mismatch smear** — image motion rate ≠ TDI clocking rate | E | All | Adds smear MTF term; ~10% MTF loss per pixel of misalignment | Modeled when TDI used | Velocity match error ε_v (fraction of pixel per TDI stage) |
| R5 | **Pixel binning (spatial)** — summing adjacent pixels in row and/or column | E | All | Increases signal by N_bin, noise by √N_bin → SNR improvement √N_bin; reduces spatial resolution | Modeled when binning used | Binning factor N_x × N_y |
| R6 | **Frame coadding** — summing multiple frames | E | All | Same as TDI but in time domain; increases dynamic range and SNR | Modeled when coadding used | Number of coadds N_coadd |
| R7 | **Programmable gain amplifier (PGA)** — analog gain stage before ADC | E | All | Sets ADC input range; gain error contributes to FPN | Modeled as gain factor; gain error usually ignored | Gain G (e⁻/DN or equivalent), gain error σ_G |
| R8 | **ADC resolution** — number of bits determines minimum detectable step | E | All | Dynamic range = 20·log₁₀(2^N) dB; N = 12 → 72 dB, N = 16 → 96 dB | Always modeled | ADC bit depth N; LSB in electrons = FWC/2^N |
| R9 | **ADC nonlinearity (INL/DNL)** — integral and differential nonlinearity of ADC | E | All | INL typically ±0.5–2 LSB; DNL < 1 LSB (missing codes) | Modeled in precision radiometric applications; often ignored | INL (LSB), DNL (LSB); worst-case or RMS |
| R10 | **Bias / offset drift** — temporal and thermal drift of dark signal zero-point | E | All | 1–100 DN drift over temperature or time; drives NUC frequency requirements | Modeled as drift term; important for NUC scheduling | Offset drift coefficient (DN/°C or DN/hr), temperature variation ΔT |
| R11 | **1/f noise in readout chain** — flicker noise from MOSFET source followers in ROIC | E | All | Adds low-frequency noise floor; read-noise equivalent 1–20 e⁻ RMS depending on bandwidth | Modeled in detailed noise budgets; often included in bulk read noise spec | Corner frequency f_c, low-frequency noise PSD |
| R12 | **Multiplexer glow** — photon emission from ROIC switching transistors | E | MWIR, LWIR | 10–1000 e⁻/s/pixel spatially structured glow; DC but temperature sensitive | Modeled in high-fidelity MWIR/LWIR; often ignored | Glow current per pixel, wavelength spectrum of ROIC glow |
| R13 | **Clock feedthrough** — capacitive coupling of clock signals into analog signal path | E | All | 1–10 DN structured noise; synchronous with readout clock | Usually ignored in performance models; relevant in detailed electronics design | Coupling capacitance, clock amplitude, signal chain impedance |
| R14 | **Power supply noise** — ripple and noise on supply rails coupling into analog signal | E | All | 0.1–5 DN RMS; depends on PSRR of ROIC | Usually ignored; modeled in electronics noise budgets | Power supply ripple amplitude, PSRR (dB) |
| R15 | **Output data rate and compression** — digitization bandwidth; lossy compression artifacts | E | All | Compression ratios > 4:1 may introduce artifacts in low-SNR scenes | Modeled as a system constraint; compression artifacts usually ignored | Data rate (Gbps), compression ratio, algorithm (lossless vs. lossy) |
| R16 | **Anti-blooming drain** — active drain current preventing bloom propagation | E | All | Reduces effective full well capacity by 30–70% when active | Modeled as FWC reduction | Anti-blooming efficiency, FWC with/without drain |
| R17 | **Snapshot vs. rolling shutter** — whether all pixels integrate simultaneously | E | All | Rolling shutter introduces differential timing artifacts across rows | Modeled as smear/distortion term when relevant | Readout rate (rows/sec), image motion velocity |

---

## 6. Spatial Effects

| # | Effect | Type | Regimes | Magnitude | Practice | Input Parameters |
|---|--------|------|---------|-----------|----------|-----------------|
| SP1 | **Diffraction-limited PSF** — Airy disk from circular aperture; sets diffraction floor | F | All | Airy disk radius r = 1.22λf/D; encircled energy 84% in core | Always modeled | Aperture D, obscuration ε, wavelength λ, f/# |
| SP2 | **Aberration PSF** — non-ideal PSF from WFE; Strehl ratio and PSF shape change | E | All | Strehl = exp(−(2πσ/λ)²); WFE spreads energy to wings | Modeled as Strehl × diffraction PSF in performance tools; full WFE for high-fidelity | σ_WFE or Zernike coefficients; or PSF table |
| SP3 | **Pixel aperture MTF** — sinc response of finite pixel integration | F | All | MTF(f) = sinc(p·f) where p = pixel pitch; MTF = 0.637 at Nyquist | Always modeled | Pixel pitch p, fill factor FF |
| SP4 | **Sampling MTF** — aliasing and reconstruction at Nyquist limit | F | All | Nyquist frequency f_N = 1/(2p); aliasing for f > f_N | Always modeled | Pixel pitch p, image-domain spatial frequency |
| SP5 | **Smear — linear (along-track)** — image motion during integration | E | All | MTF(f) = sinc(v·t_int·f) where v = image velocity; 1-pixel smear → MTF = 0.637 at Nyquist | Always modeled | Ground speed projected to image plane v_img (pixels/s), integration time t_int |
| SP6 | **Jitter — random (high-frequency)** — high-frequency angular vibration | E | All | Gaussian blur of width σ_jitter; MTF(f) = exp(−2π²σ²f²) | Always modeled | Angular jitter RMS σ_jitter (µrad), vibration PSD, bandwidth |
| SP7 | **Jitter — line-of-sight drift (low-frequency)** — slow pointing drift during integration | E | All | Adds to smear at low frequency; indistinguishable from platform motion | Often combined with smear | Drift rate (µrad/s), integration time |
| SP8 | **Platform vibration** — structural vibration from mechanisms, cryocoolers, reaction wheels | E | All | Broadband vibration adds to jitter; cryocooler at 50–80 Hz often dominant | Modeled as jitter PSD contribution | Vibration PSD from platform model; or total jitter budget |
| SP9 | **Atmospheric turbulence MTF** — long and short exposure blurring by seeing | F | UV, VIS, SWIR | Long exposure: MTF = exp(−3.44(λf/r₀D)^(5/3)); short exposure: Strehl-limited | Modeled for ground-based and low-altitude sensors | Fried parameter r₀, aperture D, wavelength λ, exposure time vs. coherence time |
| SP10 | **TDI alignment MTF** — image motion misalignment to TDI clocking direction | E | All | Sinc-like MTF loss in cross-track; sensitive to yaw error | Modeled when TDI used | Yaw misalignment angle, TDI stage count, pixel pitch |
| SP11 | **Defocus MTF** — blurring from out-of-focus image plane | E | All | MTF = jinc(πd·f) where d = blur circle diameter | Modeled as PSF modification | Defocus blur diameter d (pixels), depth of focus range |
| SP12 | **Scan mechanism MTF** — velocity non-uniformity in whiskbroom or mechanical scanner | E | All | Proportional to velocity jitter ÷ scan rate | Modeled when scanning mechanism used | Scanner velocity uniformity, scan rate, integration time |
| SP13 | **Image registration error** — misalignment between frames or spectral bands | E | All | Subpixel to multi-pixel; drives band-to-band spatial accuracy | Modeled as a systematic or random offset | Registration accuracy (pixels RMS), source of error (GPS, attitude, terrain) |
| SP14 | **Geometric distortion** — spatial mapping nonlinearity (barrel, pincushion, keystone) | E | All | 0.1–5% distortion at field edge; correctable in post-processing | Modeled as field-position-dependent pixel position error | Distortion polynomial coefficients k₁, k₂, k₃; or distortion map |
| SP15 | **Aliasing artifacts** — undersampling creates false spatial frequencies | F | All | Significant when system Q < 2 (undersampled); creates moiré patterns | Modeled as MTF effect; anti-aliasing filter may be required | System Q = λ(f/#)/pixel_pitch; Q < 2 → aliasing |
| SP16 | **Pointing knowledge error** — uncertainty in where sensor is pointed | E | All | 0.1–10 pixels RMS; impacts geolocation and co-registration | Modeled as geolocation error budget term | Attitude knowledge accuracy (µrad), leverarm uncertainty |
| SP17 | **Charge diffusion MTF** — lateral spreading of photoelectrons before collection | E | All | Gaussian MTF term; significant when diffusion length > pixel pitch / 4 | Often modeled as a detector MTF term | Minority carrier diffusion length L_d, pixel pitch p |

---

## 7. Scene / Background

| # | Effect | Type | Regimes | Magnitude | Practice | Input Parameters |
|---|--------|------|---------|-----------|----------|-----------------|
| SC1 | **Background radiance** — mean thermal or reflected radiation from scene background | F | All | Sets photon background noise floor; dominates in LWIR | Always modeled | Background temperature T_bg (LWIR) or background reflectance ρ_bg and illumination (VIS/SWIR) |
| SC2 | **Background spatial clutter** — natural spatial variation in scene radiance within resolution cell | F | All | Clutter σ_clutter often > NEDT; limits detection, not NEDT | Always relevant for detection; often ignored in pure radiometric models | Clutter-to-noise ratio (CNR), spatial power spectral density of scene |
| SC3 | **Thermal background variability** — temperature variation of background scene elements | F | MWIR, LWIR | ΔT_bg ~ 2–20 K for natural scenes; drives contrast and detection thresholds | Modeled for detection range calculations | Background temperature distribution, ΔT statistics |
| SC4 | **Sun glint** — specular reflection of sun from water or smooth surfaces into sensor FOV | F | UV, VIS, SWIR | Can saturate sensor; 10²–10⁴× normal surface radiance | Modeled as a saturation risk; geometry dependent | Solar position, wind speed (ocean surface roughness), view geometry |
| SC5 | **Shadow effects** — self-shadowing and cast shadows from terrain or objects | F | UV, VIS, SWIR | 10–30% of illuminated radiance in shadow; reduces contrast | Often ignored; important for target-in-shadow scenarios | Solar elevation, terrain relief, object geometry |
| SC6 | **Adjacency / mixed pixel** — multiple materials within one resolution element | F | All | Dominant effect at resolution limit; target fill fraction < 1 | Modeled as area-weighted average | Target fill fraction η = A_target/A_pixel, background radiance |
| SC7 | **Target-background contrast** — difference in radiance between target and background | F | All | ΔL = L_target − L_background; drives SNR for detection | Always modeled | Target and background radiance at sensor (after atmosphere) |
| SC8 | **Temporal scene variability** — scene changes between revisit opportunities | F | All | Background temperature drifts 1–5 K/hr; clouds change on minutes | Modeled as temporal stability parameter; usually not in performance tools | Scene change rate, revisit time |
| SC9 | **Urban heat island / thermal anomalies** — anthropogenic thermal features in background | F | MWIR, LWIR | Creates elevated clutter in urban scenes; 2–10 K above surroundings | Usually ignored in performance tools; important for NIIRS in urban areas | Land use map, urban fraction, anthropogenic heat flux |
| SC10 | **Terrain-induced radiance variation** — slope and aspect effects on solar illumination | F | UV, VIS, SWIR | ±50% variation from illuminated to shadowed slopes | Modeled in high-fidelity scene models; often ignored | DEM, slope/aspect map, solar zenith angle |
| SC11 | **Spectral clutter** — variation in spectral signature of background materials | F | All | Can masquerade as or mask target; limits spectral discrimination | Modeled in multi/hyperspectral; usually ignored in single-band | Background spectral library, spectral mixing model |
| SC12 | **Partial cloud cover** — fraction of FOV obscured by clouds | F | All | Binary obstruction for fully cloudy pixels; edge diffraction for sub-pixel | Usually modeled as cloud fraction (on/off per pixel) | Cloud fraction, cloud altitude, cloud optical depth |

---

## Scope Triage

**Final adjudicated scope — agreed 2026-04-06.**

Legend: ✅ IN v1 | 🔶 STUBBED v1 (placeholder returns, no real model) | ❌ DEFERRED

### Stage 1: Source / Target Radiation

| ID | Effect | Recommendation | Rationale |
|----|--------|---------------|-----------|
| S1 | Planck thermal emission | ✅ IN | Core physics; required for MWIR/LWIR |
| S2 | Reflected solar irradiance | ✅ IN | Core physics; required for VIS/SWIR |
| S3 | Reflected diffuse sky radiance | ✅ IN | Hemispherical integral over L_sky(λ); additive source term; L_sky from MODTRAN or simple model |
| S4 | Target emissivity | ✅ IN | First-order effect; scalar ε(λ) is sufficient |
| S5 | Target BRDF | ✅ IN | Lambertian model in v1; hook for full BRDF |
| S6 | Target temperature non-uniformity | ✅ IN | Two-temperature or histogram model; weighted Planck sum over area fractions |
| S7 | Self-luminous emission | ✅ IN | User-supplied L_source(λ); additive term in source stage; molecular plume spectroscopy (S8) remains DEFERRED |
| S8 | Spectrally selective emission | ❌ DEFERRED | Requires molecular spectroscopy engine; plume model explicitly out of scope |
| S9 | Reflected earthshine | ❌ DEFERRED | Space-to-space geometry; low priority for v1 |
| S10 | Reflected moonlight | ✅ IN | Lunar irradiance spectrum scaled by phase angle; enables nighttime VIS performance prediction |
| S11 | Airglow | ❌ DEFERRED | Space-based looking-up geometry; specialized |
| S12 | Doppler shift | ❌ DEFERRED | Not in scope for passive broadband |
| S13 | Fluorescence | ❌ DEFERRED | Specialized vegetation/biological sensing |
| S14 | Interreflection | ❌ DEFERRED | Scene-level ray tracing; out of scope |
| S15 | Stellar background | ❌ DEFERRED | Space surveillance use case; not v1 |

### Stage 2: Atmospheric Propagation

| ID | Effect | Recommendation | Rationale |
|----|--------|---------------|-----------|
| A1 | Molecular absorption | ✅ IN | Via MODTRAN τ(λ) ingestion |
| A2 | Spectral transmittance | ✅ IN | Core; product of all atmospheric effects |
| A3 | Path radiance | ✅ IN | Required for VIS/SWIR accuracy |
| A4 | Atmospheric thermal emission | ✅ IN | Required for MWIR/LWIR accuracy |
| A5 | Rayleigh scattering | ✅ IN | Included implicitly via MODTRAN; explicit model for simple mode |
| A6 | Aerosol extinction | ✅ IN | Via MODTRAN or AOD + Angstrom model |
| A7 | Aerosol phase function | ✅ IN | Henyey-Greenstein model (asymmetry parameter g); MODTRAN handles in full mode |
| A8 | Water vapor continuum | ✅ IN | Included in MODTRAN; bulk PWV parameter in simple mode |
| A9 | Ozone absorption | ✅ IN | Included in MODTRAN; ozone column parameter in simple mode |
| A10 | Cloud/fog attenuation | ✅ IN | Beer-Lambert model from cloud optical depth τ_cloud; binary flag is τ_cloud → ∞ degenerate case |
| A11 | Rain attenuation | ❌ DEFERRED | Specialized; low priority |
| A12 | Atmospheric refraction | ❌ DEFERRED | Pointing/geolocation tool; not radiometric |
| A13 | Turbulence (r₀, Cn²) | 🔶 STUBBED | Parameter stored; turbulence MTF computed in SP9 |
| A14 | Turbulence MTF | 🔶 STUBBED | Long-exposure Kolmogorov model only; return 1.0 if space-based |
| A15 | Anisoplanatism | ❌ DEFERRED | Requires AO system context |
| A16 | Scintillation | ❌ DEFERRED | Point-source specific; specialized |
| A17 | Adjacency effect | ❌ DEFERRED | Requires scene radiance field |
| A18 | Polarization | ❌ DEFERRED | Out of scope v1 |
| A19 | Window/dome refraction | ❌ DEFERRED | Optical design tool; not performance model |

### Stage 3: Optical Train

| ID | Effect | Recommendation | Rationale |
|----|--------|---------------|-----------|
| O1 | Aperture area | ✅ IN | Fundamental |
| O2 | Central obscuration | ✅ IN | Simple correction to effective area and PSF |
| O3 | Net optical transmittance | ✅ IN | Product of surface transmittances; spectral table input |
| O4 | Spectral bandpass filter | ✅ IN | Defines integration limits; critical |
| O5 | Warm optics emission | ✅ IN | Required for MWIR/LWIR |
| O6 | Cold stop efficiency | ✅ IN | Required for MWIR/LWIR NEDT accuracy |
| O7 | Narcissus | ✅ IN | DC offset = f(detector T, optics reflectance at each surface, solid angle); simplified retroreflection model |
| O8 | Stray light | 🔶 STUBBED | SLRR parameter input; uniform background added |
| O9 | Ghost images | ❌ DEFERRED | Stray light tool responsibility |
| O10 | Surface scatter | ❌ DEFERRED | UV-specific; low priority for v1 |
| O11 | Diffraction PSF | ✅ IN | Both geometric and diffraction-limited PSF |
| O12 | Wavefront error (Strehl) | ✅ IN | Bulk Strehl reduction to PSF core |
| O13 | Defocus | ✅ IN | Jinc MTF term parameterized by blur circle diameter d; feeds SP11 |
| O14 | Chromatic aberration | ❌ DEFERRED | Refractive system design tool |
| O15 | Thermal defocus | ✅ IN | dn/dT × ΔT → Δfocus → blur circle diameter → feeds O13; trivial given O13 is IN |
| O16 | Vignetting | ✅ IN | Field-angle-dependent throughput T(θ_x, θ_y); polynomial or table lookup |
| O17 | Polarization in optics | ❌ DEFERRED | Out of scope v1 |
| O18 | F/# and plate scale | ✅ IN | Fundamental; IFOV, Ω, plate scale |
| O19 | Étendue | ✅ IN | Implicit in A × Ω × T chain |

### Stage 4: Detector

| ID | Effect | Recommendation | Rationale |
|----|--------|---------------|-----------|
| D1 | Quantum efficiency | ✅ IN | Spectral QE(λ) table |
| D2 | Pixel pitch and fill factor | ✅ IN | Fundamental |
| D3 | Shot noise | ✅ IN | Fundamental noise |
| D4 | Dark current | ✅ IN | Key noise term especially MWIR/LWIR |
| D5 | Dark current shot noise | ✅ IN | √(J_dark × t_int) |
| D6 | Read noise | ✅ IN | Key noise term |
| D7 | Fixed pattern noise (DSNU) | ✅ IN | Key term; modeled as residual after NUC |
| D8 | PRNU | ✅ IN | Key term; residual after flat-field |
| D9 | NUC residual | ✅ IN | Critical for MWIR/LWIR NEDT |
| D10 | 1/f noise | ✅ IN | Modeled via corner frequency f_c; significant in MWIR/LWIR ROICs |
| D11 | kTC reset noise | ✅ IN | Conditional on CDS flag; σ_kTC = √(kTC/q²) when CDS off |
| D12 | Quantization noise | ✅ IN | LSB/√12; important at low signal |
| D13 | Saturation / full well | ✅ IN | Sets dynamic range ceiling |
| D14 | Nonlinearity | ✅ IN | Polynomial correction model; residual error term after correction |
| D15 | Blooming | ✅ IN | Overflow fraction × FWC spills to N neighbor pixels; simple nearest-neighbor model |
| D16 | Electrical crosstalk (IPC) | ✅ IN | Nearest-neighbor coupling coefficient α; modifies effective pixel MTF |
| D17 | Optical crosstalk | ❌ DEFERRED | Requires detailed detector model |
| D18 | Charge diffusion | ✅ IN | Gaussian MTF term; diffusion length L_d as input parameter |
| D19 | Persistence | ✅ IN | Exponential decay: residual = f_persist × S_prev × exp(−t/τ); S_prev is a user input (prior frame signal level), not live state |
| D20 | Cosmic rays | ✅ IN | Poisson rate model; returns event rate statistic for space sensor pixel availability |
| D21 | Radiation damage | ✅ IN | Arrhenius dark current scaling vs. TID; multiplies J_dark in D4 as time-dependent mission age parameter |
| D22 | Detector glow | ✅ IN | Combined with R12 as single internal glow DC offset term (e⁻/s/pixel); user input |
| D23 | Trapping states | ❌ DEFERRED | Too detailed for performance tool |
| D24 | Snow/sparkle (RTS) | 🔶 STUBBED | Modeled as bad pixel fraction |
| D25 | CTE (CCD) | ✅ IN | Signal loss = CTE^N_transfers; conditional on detector type = CCD |
| D26 | Bad/dead pixels | ✅ IN | Fraction parameter; affects effective sensitivity |
| D27 | Temperature effects on dark current | ✅ IN | Arrhenius model; critical for cooling trade |

### Stage 5: Readout Electronics

| ID | Effect | Recommendation | Rationale |
|----|--------|---------------|-----------|
| R1 | Integration time | ✅ IN | Fundamental |
| R2 | CDS | ✅ IN | Standard assumption; eliminates kTC |
| R3 | TDI | ✅ IN | Common in pushbroom; √N_TDI SNR gain |
| R4 | TDI velocity mismatch smear | ✅ IN | Sinc MTF term from velocity mismatch fraction; feeds smear MTF chain |
| R5 | Pixel binning | ✅ IN | Simple scaling |
| R6 | Frame coadding | ✅ IN | Simple scaling |
| R7 | Programmable gain | ✅ IN | Gain factor in signal chain |
| R8 | ADC resolution | ✅ IN | Quantization noise; dynamic range |
| R9 | ADC nonlinearity (INL/DNL) | ❌ DEFERRED | Electronics design tool level |
| R10 | Bias/offset drift | ✅ IN | Linear drift (DN/°C × ΔT); feeds D7/D9 NUC residual as time/temperature-dependent term |
| R11 | 1/f noise in readout | ✅ IN | Subsumed into D10 model; ROIC corner frequency f_c as separate input parameter |
| R12 | Multiplexer glow | ✅ IN | Combined with D22 as single internal glow term; ROIC photon emission contribution |
| R13 | Clock feedthrough | ❌ DEFERRED | Electronics design level |
| R14 | Power supply noise | ❌ DEFERRED | Electronics design level |
| R15 | Data rate / compression | 🔶 STUBBED | Flag if lossy; no artifact model |
| R16 | Anti-blooming drain | ✅ IN | FWC_eff = FWC × (1 − drain_efficiency); reduces dynamic range ceiling |
| R17 | Rolling shutter | 🔶 STUBBED | Snapshot assumed; rolling shutter flag reserved |

### Stage 6: Spatial Effects

| ID | Effect | Recommendation | Rationale |
|----|--------|---------------|-----------|
| SP1 | Diffraction PSF | ✅ IN | Core; Airy function with obscuration |
| SP2 | Aberration PSF (Strehl) | ✅ IN | Strehl × diffraction PSF |
| SP3 | Pixel aperture MTF | ✅ IN | Sinc model |
| SP4 | Sampling MTF | ✅ IN | Nyquist analysis |
| SP5 | Linear smear MTF | ✅ IN | Sinc from integration time × velocity |
| SP6 | Random jitter MTF | ✅ IN | Gaussian blur from angular jitter σ |
| SP7 | LOS drift | ✅ IN | Combined with SP5 as sinc MTF from (v_smear + v_drift) × t_int |
| SP8 | Platform vibration | ✅ IN | PSD integration → RMS jitter; preprocessing step feeding SP6 |
| SP9 | Turbulence MTF | 🔶 STUBBED | Long-exposure model only; return 1.0 for space |
| SP10 | TDI alignment MTF | ✅ IN | Sinc MTF from yaw misalignment angle; feeds MTF chain for TDI sensors |
| SP11 | Defocus MTF | ✅ IN | Jinc MTF from blur circle diameter d; required coupling with O13 |
| SP12 | Scan mechanism MTF | ❌ DEFERRED | Whiskbroom scanner specific |
| SP13 | Registration error | ✅ IN | Gaussian MTF equivalent to registration RMS error; feeds system MTF chain |
| SP14 | Geometric distortion | ❌ DEFERRED | Geometric calibration tool |
| SP15 | Aliasing | ✅ IN | Computed from system Q; flag if undersampled |
| SP16 | Pointing knowledge error | 🔶 STUBBED | Geolocation budget; return pointing knowledge parameter |
| SP17 | Charge diffusion MTF | ✅ IN | Gaussian MTF term from diffusion length L_d; required coupling with D18 |

### Stage 7: Scene / Background

| ID | Effect | Recommendation | Rationale |
|----|--------|---------------|-----------|
| SC1 | Background radiance | ✅ IN | Fundamental; drives photon noise floor |
| SC2 | Background spatial clutter | ✅ IN | σ_clutter as input; detection threshold = f(SNR, clutter-to-noise ratio); no spatial scene generation |
| SC3 | Thermal background variability | ✅ IN | ΔT input for detection range calculations |
| SC4 | Sun glint | ✅ IN | Cox-Munk geometry check; returns estimated glint radiance and saturation risk flag |
| SC5 | Shadow effects | ❌ DEFERRED | Scene geometry tool |
| SC6 | Mixed pixel / fill fraction | ✅ IN | Target fill fraction η; area-weighted radiance |
| SC7 | Target-background contrast | ✅ IN | ΔL = L_target − L_background; core detection metric |
| SC8 | Temporal variability | ❌ DEFERRED | Revisit analysis tool |
| SC9 | Urban heat island | ❌ DEFERRED | Scene-specific; not a sensor performance parameter |
| SC10 | Terrain-induced variation | ❌ DEFERRED | Scene generation tool |
| SC11 | Spectral clutter | ❌ DEFERRED | Multispectral/hyperspectral use case; phase 2 |
| SC12 | Partial cloud cover | ✅ IN | Cloud fraction × A10 optical depth model; area-weighted transmission per resolution element |

---

## Summary Count

| Status | Count |
|--------|-------|
| ✅ IN v1 | 82 |
| 🔶 STUBBED v1 | 8 |
| ❌ DEFERRED | 26 |
| **Total** | **116** |

---

## Key Architectural Implications

The following observations from this inventory should directly drive architecture decisions:

1. **MWIR is the most complex regime.** It requires simultaneous modeling of reflected solar + thermal emission (S1+S2 both active), warm optics emission (O5), cold stop efficiency (O6), NUC residual (D9), and detector glow (D22). The radiometric chain branches here — the architecture must support additive contributions from multiple source terms in the same spectral band.

2. **The atmosphere returns three distinct outputs** (τ(λ), L_path(λ), L_atm(λ)) and all three must flow through the signal chain. A scalar transmittance is insufficient for MWIR/LWIR.

3. **MTF is a product of independent terms.** At minimum 7 MTF terms are in-scope for v1 (SP1–SP6, SP15). The architecture needs a composable MTF chain, not hardcoded combination.

4. **Noise is quadrature sum of independent terms.** At minimum 10 noise terms are in-scope for v1. The noise model must be structured so each term is computed and reported independently before quadrature combination — for noise budget visibility.

5. **Stubbed effects must have parameter hooks.** All STUBBED effects must accept their input parameters and store them even if the model returns zero/unity. This allows v1 to be upgraded without API changes.

6. **NUC and radiometric calibration are first-class.** D7, D8, D9 and their temporal drift behavior (R10) mean the tool must model post-correction residuals, not just raw detector performance.
