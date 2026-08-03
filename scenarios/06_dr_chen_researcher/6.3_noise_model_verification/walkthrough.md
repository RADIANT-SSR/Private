# Scenario 6.3: Noise Model Verification — Analytic vs. RADIANT


> **NIIRS applicability — engine update (CU-166).** Since this walkthrough was written, RADIANT added a metric-applicability gate: when one or more GIQE-5 inputs fall outside the calibration envelope — GSD 1.18–31.5 inch, RER 0.20–0.95, SNR 2–130 — the engine reports **NIIRS as N/A** by default instead of silently extrapolating. This configuration is outside that envelope, so the NIIRS values below are the **extrapolated** GIQE-5-form output: reproduce them with `performance.niirs.allow_extrapolated = true` and read them as a *relative trend, not a calibrated rating*. (SNR/NEDT/spatial figures were refreshed 2026-07-22 against the current engine, CU-176. No IR-calibrated IIRS model yet — see `docs/tracking/gaps.md` Gap 100.)

Refreshed 2026-07-07 (Scenario_Execution_Plan Phase R): parameters now enter
RADIANT in vendor units via the unit-aware `Sensor.set(..., unit=...)`
boundary (Gap 6) with a conversion cross-check; the hand model was upgraded
to the photon-weighted spectral integral plus the Kirchhoff reflected-solar
term, after which **every noise term agrees to 0.00%**. The refresh also
surfaced registry Gap 43 (NEDT single-λ approximation).

## The Problem

Dr. Chen is writing a paper comparing RADIANT against analytic noise models
(Rogalski's textbook equations). She needs to verify that each of RADIANT's
16 noise terms matches her hand calculations to within acceptable tolerance.

## System Configuration

| Parameter | Value | Unit | Notes |
|-----------|-------|------|-------|
| Aperture diameter | 30 | cm | Converted to 0.30 m |
| Focal ratio | f/4.0 | -- | |
| Focal length | 1.20 | m | Derived: f/# x D |
| Optical transmission | 70 | % | Converted to 0.70 fraction |
| Optics temperature | 293 | K | Room temperature |
| Pixel pitch | 18 | um | |
| Quantum efficiency | 70 | % | Converted to 0.70 fraction |
| Dark current | 100 | e-/s | At 77 K operating temp |
| Full well capacity | 2,000,000 | e- | Large-well HgCdTe |
| Read noise | 20 | e- RMS | Post-CDS |
| ADC bits | 14 | bits | |
| System gain | 1.0 | e-/DN | |
| Target temperature | 300 | K | Blackbody source |
| Target emissivity | 0.95 | -- | |
| Band | 3.5 - 5.0 | um | MWIR |
| Integration time | 5 | ms | |
| Altitude | 8 | km | Airborne platform |
| Atmosphere | exo (vacuum) | -- | No atmospheric effects |

## Approach

1. Read parameters from Dr. Chen's Excel spreadsheet in vendor units
2. Convert inputs for the **hand-calculation anchors** (script-side, shown with conversion table)
3. Hand RADIANT the **raw vendor values**: `Sensor.set(param, value, unit="cm"/"%"/"ms"/"km")`
   converts once at the parameter boundary (Gap 6, Rule 2) — Step 3a cross-checks
   RADIANT's conversions against the script's own (all match to 1e-12)
4. Run RADIANT evaluation to get all noise terms
5. Compute hand-calculated values using first-principles Planck integration
6. Compare each noise term with percent error and PASS/CHECK/FAIL status
7. Report all performance metrics now available in RADIANT

### Hand Calculation Method (upgraded this refresh)

Signal electrons are the **photon-weighted spectral integral** plus the
**Kirchhoff reflected-solar term**:

    S_thermal = ∫ ε·B(λ,T)·λ/(hc) dλ · τ_opt · Ω · A_pixel · QE · t_int
    S_solar   = ∫ ρ·E_sun_TOA(λ)·cosθ_sun/π · λ/(hc) dλ · τ_opt · Ω · A_pixel · QE · t_int
    S = S_thermal + S_solar,   with ρ = 1 − ε (Kirchhoff), θ_sun = 0.5 rad (default)

where B(λ,T) is the Planck spectral radiance and Ω = π/(4·f/#²). Two upgrades
over the original hand model, both required to match the current architecture:

- **Photon integral, not band-center E_photon**: a 300 K source emits its
  in-band photons preferentially at the long end of 3.5–5 µm; the band-center
  shortcut reads ~5.5% low.
- **Reflected solar**: the `no_atmosphere (space)` sub-case illuminates the
  target with the unattenuated TOA solar spectrum, and a grey (ε = 0.95)
  target reflects ρ = 0.05 of it — ~9% of the in-band signal. A thermal-only
  textbook model is verifying a different (nighttime) scene.

The hand calc uses 1000 spectral samples across the 3.5–5.0 µm band and
shares only CODATA constants and the solar irradiance table with RADIANT.

Shot noise terms are sqrt(N_electrons) for each source (signal, background, dark).
Deterministic terms (read noise, quantization = gain/sqrt(12)) are exact.

## Key Results

### Noise Term Comparison

| Noise Term | Hand Calc [e- RMS] | RADIANT [e- RMS] | % Error | Status |
|------------|-------------------:|------------------:|--------:|--------|
| signal_shot | 1280.68 | 1280.68 | 0.00% | PASS |
| background_shot | 0.00 | 0.00 | 0.00% | PASS |
| nearfield_shot | 0.00 | 0.00 | 0.00% | PASS |
| dark_shot | 0.71 | 0.71 | 0.00% | PASS |
| read_noise | 20.00 | 20.00 | 0.00% | PASS |
| quantization | 0.29 | 0.29 | 0.00% | PASS |
| **TOTAL (RSS)** | **1280.83** | **1280.83** | **0.00%** | **PASS** |

signal_shot agrees to better than 0.01% once the hand model integrates
photons spectrally and includes the reflected-solar term (1,506,203 thermal
+ 133,931 solar = 1,640,135 e⁻ vs RADIANT 1,640,136 e⁻).

background_shot = 0 **by design** in the extended regime: the 300 K target
fills the pixel IFOV, so there is no separate scene-background photon stream
(matrix Decision #13). The background temperature/emissivity inputs define
the contrast scene only. (The first execution predated this architecture
and hand-modeled a 991.6 e⁻ RMS background term; that scene construct no
longer exists in extended regime.)

### Performance Metrics

| Metric | RADIANT | Hand Calc | Unit | % Error |
|--------|--------:|----------:|------|--------:|
| SNR | 1280.52 | 1280.52 | -- | 0.00% |
| NEDT | 21.79 | 23.92 | mK | 8.91% (Gap 43 — see below) |
| NIIRS | 11.12 | -- | -- | -- |
| GSD | 0.1200 | 0.1200 | m | 0.00% |
| MTF at Nyquist | 0.2668 | -- | -- | -- |
| Strehl | 1.0000 | -- | -- | -- |
| Q (sampling) | 0.9444 | 0.9444 | -- | 0.00% |
| EE (1x1) | 0.4141 | -- | -- | -- |
| Well margin | 1.72 | -- | dB | -- |

*One value refreshed 2026-08-02 from the unmodified runner (previous
vintage 2026-07-22): EE (1×1) 0.4826 → 0.4141. Mover: CU-188 —
cell-area-overlap EE_box. Note the scope nuance: CU-188's stated scope is
the point-source / sub-pixel regimes where EE_box is **applied** to the
signal, and this scenario is EXTENDED, so its SNR and every noise term are
bit-identical. Only the **reported** EE metric moved, because it is the
output of the same recomputed EE_box. Everything else on this page —
including the whole MTF budget and Strehl = 1.0 — is unchanged, as
expected for an `exo` (vacuum) path that CU-224 and CU-267 cannot touch.*

### MTF Budget (at Nyquist)

| Component | MTF_x | MTF_y |
|-----------|------:|------:|
| Optics (diffraction) | 0.4223 | 0.4223 |
| Pixel aperture | 0.6366 | 0.6366 |
| Jitter | 1.0000 | 1.0000 |
| Smear | 1.0000 | 1.0000 |
| IPC | 1.0000 | 1.0000 |
| Charge diffusion | 1.0000 | 1.0000 |
| TDI | 1.0000 | 1.0000 |
| **System** | **0.2688** | **0.2688** |

## Physics Discussion

### Why the Shot-Noise Match Is Now Exact

Two former approximations in the hand model were removed:

1. **Band-center photon energy → spectral photon integral.** Converting the
   band-integrated radiance with a single E_photon at 4.25 µm reads ~5.5%
   low for a 300 K source in 3.5–5 µm, because in-band photons concentrate
   at the long-wavelength end. The photon-weighted integral ∫L·λ/(hc) dλ
   reproduces RADIANT's per-wavelength integration.
2. **Thermal-only scene → thermal + reflected solar.** The space sub-case
   illuminates the target with the TOA solar spectrum by default; Kirchhoff
   gives the grey target ρ = 1 − ε = 0.05, contributing ~9% of the in-band
   signal at the 0.5 rad default solar zenith. This is correct daytime
   physics — a verification against a thermal-only textbook formula is
   verifying a nighttime scene instead.

With both corrections the hand and RADIANT signals agree to < 0.01%, which
is a genuinely strong verification: it pins the Planck integral, the solar
model coupling, the Kirchhoff reflectance, the pixel étendue (Ω·A), the QE
and transmission application, and the shot-noise square root simultaneously.

Deterministic noise terms (dark_shot, read_noise, quantization) match exactly
because they do not depend on spectral integration.

### Why Is nearfield_shot = 0?

In scalar transmission mode, RADIANT models the entire optical train as a
single lumped refractive element. For a refractive element, the transmission
loss (1 - tau) is treated as reflection, not absorption. By Kirchhoff's law:
T + R = 1, so emissivity eps = 1 - T - R = 0. With zero emissivity, there is
no thermal self-emission and nearfield_shot is correctly zero.

This is physically correct for lens-based systems. For reflective telescope
systems (mirrors where eps = 1 - R), the user should specify individual optical
elements using `key_elements` or `full_prescription` mode, which allows RADIANT
to compute per-element emissivity via Kirchhoff's law (eps_mirror = 1 - R).

### NEDT Interpretation (registry Gap 43)

RADIANT reports NEDT = 21.79 mK; the exact hand calculation gives 23.92 mK
(8.9% apart). The cause is identified and filed as **registry Gap 43**:
the performance stage uses the single-wavelength Planck-factor approximation
`NEDT = T / (SNR · x·eˣ/(eˣ−1))` (`nedt.compute_nedt_from_snr`), and its SNR
numerator includes the reflected-solar signal — which does **not** vary with
target temperature. The inflated SNR makes RADIANT's thermal sensitivity
read optimistically low. The exact path (`nedt.compute_nedt` with a
band-integrated dS/dT) exists in the module but is not wired to the stage.
Until Gap 43 lands, the hand recipe (finite-difference photon integral at
T ± 0.1 K) is the trustworthy NEDT for daytime scenes.

### NIIRS and Spatial Quality

NIIRS = 11.12 is exceptionally high because this is an 8 km altitude airborne
platform with a 30 cm aperture, yielding GSD = 0.12 m. The Q parameter of 0.94
indicates near-optimal sampling (Q = 1 is ideal for Nyquist matching). (Note:
SNR = 1281 is far outside the GIQE-5 calibration range [2, 130]; RADIANT logs
this extrapolation warning on every run.)

## Gaps

### Previously Documented Gaps — Now Closed

| Gap | Status | Evidence |
|-----|--------|----------|
| Unit-aware input (registry Gap 6) | **CLOSED** (exercised this refresh) | `Sensor.set(value, unit="cm"/"%"/"ms"/"km")`; Step 3a cross-check matches script conversions to 1e-12 |
| No NEDT metric | **CLOSED** | `result.metrics["nedt_K"]` = 21.79 mK (but see Gap 43) |
| No NIIRS metric | **CLOSED** | `result.metrics["niirs"]` = 11.12 |
| No GSD metric | **CLOSED** | `result.metrics["gsd_geometric_mean_m"]` = 0.12 m |
| No Strehl metric | **CLOSED** | `result.metrics["strehl"]` = 1.0 |
| No Q parameter | **CLOSED** | `result.metrics["q_center"]` = 0.9444 |
| No MTF budget | **CLOSED** | `mtf_budget.per_term_at_nyquist` with 8 terms |

### Remaining Gaps

| Gap | Severity | Workaround |
|-----|----------|------------|
| NEDT single-λ approximation (registry Gap 43, filed this refresh) | Medium | Finite-difference dS/dT hand recipe (this scenario shows it) |
| No noise sensitivity matrix (d(sigma_i)/d(p_j)) | Medium | Can be computed manually via parameter sweeps |
| Scalar transmission mode defaults nearfield to 0 | Low | Set `optics.scalar_emissivity` (Gap 37) or use key_elements mode |

## What Dr. Chen Would Do Next

1. Re-run with explicit mirror elements (key_elements mode) to verify nearfield
   emission against her mirror-emissivity hand calculations
2. Sweep integration time to verify noise scaling: shot ~ sqrt(t), read = const
3. Use `sensor.sensitivity()` to compute parametric sensitivities if available
4. Compare RADIANT results against published benchmark data (Scenario 6.1)
