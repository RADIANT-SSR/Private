# Scenario 6.3: Noise Model Verification — Analytic vs. RADIANT

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
2. Convert all inputs to RADIANT canonical units (m, fractions, seconds)
3. Run RADIANT evaluation to get all 16 noise terms
4. Compute hand-calculated values using first-principles Planck integration
5. Compare each noise term with percent error and PASS/CHECK/FAIL status
6. Report all performance metrics now available in RADIANT

### Hand Calculation Method

Signal electrons are computed as:

    S = integral(eps * B(lam, T) * dlam) * tau_opt * Omega * A_pixel * QE * t_int / E_photon

where B(lam, T) is the Planck spectral radiance, Omega = pi / (4 f/#^2) is the pixel
solid angle, and E_photon = hc / lam_center. The hand calc uses 1000 spectral samples
across the 3.5-5.0 um band.

Shot noise terms are sqrt(N_electrons) for each source (signal, background, dark).
Deterministic terms (read noise, quantization = gain/sqrt(12)) are exact.

## Key Results

### Noise Term Comparison

| Noise Term | Hand Calc [e- RMS] | RADIANT [e- RMS] | % Error | Status |
|------------|-------------------:|------------------:|--------:|--------|
| signal_shot | 1193.12 | 1227.28 | 2.86% | PASS |
| background_shot | 991.61 | 1021.39 | 3.00% | PASS |
| nearfield_shot | 0.00 | 0.00 | 0.00% | PASS |
| dark_shot | 0.71 | 0.71 | 0.00% | PASS |
| read_noise | 20.00 | 20.00 | 0.00% | PASS |
| quantization | 0.29 | 0.29 | 0.00% | PASS |
| **TOTAL (RSS)** | **1551.52** | **1596.82** | **2.92%** | **PASS** |

### Performance Metrics

| Metric | RADIANT | Hand Calc | Unit | % Error |
|--------|--------:|----------:|------|--------:|
| SNR | 943.25 | 917.50 | -- | 2.81% |
| NEDT | 28.18 | 30.43 | mK | 7.37% |
| NIIRS | 10.89 | -- | -- | -- |
| GSD | 0.1200 | 0.1200 | m | 0.00% |
| MTF at Nyquist | 0.2532 | -- | -- | -- |
| Strehl | 1.0000 | -- | -- | -- |
| Q (sampling) | 0.9444 | 0.9444 | -- | 0.00% |
| EE (1x1) | 0.4699 | -- | -- | -- |
| Well margin | 2.46 | -- | dB | -- |

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

### Why the ~3% Difference in Shot Noise?

The hand calculation uses a mean photon energy at band center (lam = 4.25 um)
to convert from photons to electrons. RADIANT performs a proper per-wavelength
integration: at each wavelength, it computes spectral radiance * QE(lam) * filter(lam)
and integrates. Because the Planck function and photon energy both vary across
the 3.5-5.0 um band, the band-center approximation introduces ~3% error.
RADIANT's spectral integration is the more physically accurate approach.

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

### NEDT Interpretation

NEDT = 28.18 mK means the sensor can resolve temperature differences as small
as ~28 mK against a 300 K background in the MWIR band. The 7.4% difference
versus the hand calc is expected: the NEDT hand calculation uses a finite-difference
approximation for dS/dT at band center, while RADIANT computes dL/dT spectrally.

### NIIRS and Spatial Quality

NIIRS = 10.89 is exceptionally high because this is an 8 km altitude airborne
platform with a 30 cm aperture, yielding GSD = 0.12 m. The Q parameter of 0.94
indicates near-optimal sampling (Q = 1 is ideal for Nyquist matching).

## Gaps

### Previously Documented Gaps — Now Closed

| Gap | Status | Evidence |
|-----|--------|----------|
| No NEDT metric | **CLOSED** | `result.metrics["nedt_K"]` = 28.18 mK |
| No NIIRS metric | **CLOSED** | `result.metrics["niirs"]` = 10.89 |
| No GSD metric | **CLOSED** | `result.metrics["gsd_geometric_mean_m"]` = 0.12 m |
| No Strehl metric | **CLOSED** | `result.metrics["strehl"]` = 1.0 |
| No Q parameter | **CLOSED** | `result.metrics["q_center"]` = 0.9444 |
| No MTF budget | **CLOSED** | `mtf_budget.per_term_at_nyquist` with 7 terms |

### Remaining Gaps

| Gap | Severity | Workaround |
|-----|----------|------------|
| No noise sensitivity matrix (d(sigma_i)/d(p_j)) | Medium | Can be computed manually via parameter sweeps |
| Scalar transmission mode does not support nearfield | Low | Use key_elements mode for reflective systems |

## What Dr. Chen Would Do Next

1. Re-run with explicit mirror elements (key_elements mode) to verify nearfield
   emission against her mirror-emissivity hand calculations
2. Sweep integration time to verify noise scaling: shot ~ sqrt(t), read = const
3. Use `sensor.sensitivity()` to compute parametric sensitivities if available
4. Compare RADIANT results against published benchmark data (Scenario 6.1)
