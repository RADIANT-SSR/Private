# Radiometric Signal Chain

*Persona: Dr. Chen (researcher), Mike (detector engineer), Tom (optical designer)*

The complete governing equations of the RADIANT 7-stage signal chain, from
source emission to performance metrics.

---

## Overview

RADIANT models the end-to-end radiometric signal chain as seven sequential
stages. Each stage is a pure function that transforms an immutable
`ChainState`, adding radiometric frames, noise terms, and MTF contributions.

```
SourceStage → AtmosphereStage → OpticsStage → PlatformStage
→ SpectralIntegrationStage → DetectorStage → ReadoutStage
```

The final `ChainState` contains everything needed to compute performance
metrics (SNR, NEDT, NIIRS, MTF).

---

## Stage 1: Source

*Implementation: `src/radiant/source/stage.py`*

Computes target and background spectral radiance using the Planck function
with emissivity coupling.

### Planck Spectral Radiance

$$L(\lambda, T) = \varepsilon(\lambda) \cdot B(\lambda, T)$$

where the Planck function is:

$$B(\lambda, T) = \frac{2hc^2}{\lambda^5} \cdot \frac{1}{\exp\!\left(\frac{hc}{\lambda k_B T}\right) - 1}$$

- $\lambda$ in meters (converted from µm internally)
- $T$ in Kelvin
- $\varepsilon$ is the target emissivity (scalar or spectral)
- Output: $L$ in W/m$^2$/sr/µm

### Background Radiance

$$L_{\text{bg}}(\lambda) = \varepsilon_{\text{bg}} \cdot B(\lambda, T_{\text{bg}})$$

### Regime Classification (Tentative)

Angular extent: $\theta = \sqrt{A_{\text{target}}} / R$

Compared against IFOV = $p / f$ where $p$ is pixel pitch and $f$ is focal
length. See [Regime Selection](../guides/regime_selection.md) for decision
logic.

**ChainState additions:**

- Frame `at_target`: spectral radiance $L_{\text{target}}(\lambda)$
- Stage outputs: `regime_tentative`, `L_background`, `angular_extent_rad`,
  `fill_fraction`, `projected_area_m2`, `range_m`

---

## Stage 2: Atmosphere

*Implementation: `src/radiant/atmosphere/stage.py`*

Applies atmospheric transmission and path radiance via Beer-Lambert law.

### At-Aperture Radiance

$$L_{\text{aperture}}(\lambda) = L_{\text{target}}(\lambda) \cdot \tau_{\text{atm}}(\lambda) + L_{\text{path}}(\lambda)$$

where:

- $\tau_{\text{atm}}(\lambda)$ is spectral atmospheric transmittance
- $L_{\text{path}}(\lambda)$ is path radiance (atmospheric self-emission
  and scatter along the line of sight)

The simple atmosphere model computes $\tau_{\text{atm}}$ from molecular
absorption coefficients (H$_2$O, CO$_2$, O$_3$) and aerosol scattering
via Beer-Lambert:

$$\tau_{\text{atm}}(\lambda) = \exp\!\left(-\sum_i \alpha_i(\lambda) \cdot L_{\text{path\_length}}\right)$$

**ChainState additions:**

- Frame `at_aperture`: $L_{\text{aperture}}(\lambda)$
- Stage outputs: `tau_atm`, `L_path`, `L_atm_down`

---

## Stage 3: Optics

*Implementation: `src/radiant/optics/stage.py`*

Applies optical throughput, computes PSF/MTF, adds thermal self-emission,
and finalizes the radiometric regime.

### Throughput

For extended scenes, the signal irradiance at the focal plane is:

$$E_{\text{FPA}}(\lambda) = L_{\text{aperture}}(\lambda) \cdot \tau_{\text{opt}}(\lambda) \cdot \frac{\pi}{4 (f/\#)^2}$$

where $\tau_{\text{opt}}$ is the optical transmission and $f/\#$ is the
f-number.

Equivalently in terms of collecting area and solid angle:

$$\Phi(\lambda) = L_{\text{aperture}}(\lambda) \cdot A_{\text{pixel}} \cdot \Omega \cdot \tau_{\text{opt}}(\lambda)$$

where $A_{\text{pixel}} = p_x \cdot p_y$ and $\Omega = A_{\text{aperture}} / f^2$.

### Thermal Self-Emission

Warm optics contribute a nearfield background:

$$L_{\text{nf}}(\lambda) = \varepsilon_{\text{opt}}(\lambda) \cdot B(\lambda, T_{\text{opt}})$$

where $\varepsilon_{\text{opt}} = 1 - \tau_{\text{opt}}$ (Kirchhoff's law,
assuming no scattering).

### PSF and MTF

The diffraction-limited PSF is computed via FFT propagation from the pupil
aperture mask. Wavefront error reduces the Strehl ratio. The polychromatic
PSF is a photon-flux-weighted average across the spectral band.

See [Spatial Model](spatial_model.md) for the full PSF/MTF treatment.

### EE_box

Ensquared energy in a 1x1 pixel box, computed from the PSF. Applied
downstream in SpectralIntegrationStage for point-source and sub-pixel
regimes.

**ChainState additions:**

- Frame `post_optics`: irradiance at the focal plane
- Stage outputs: `regime` (final), `ee_box`, `effective_psf`, MTF terms

---

## Stage 4: Platform

*Implementation: `src/radiant/platform/stage.py`*

Adds platform-induced image degradation: smear MTF and jitter MTF.

### Smear MTF

$$\text{MTF}_{\text{smear}}(f) = \left|\text{sinc}(\pi f \cdot d_{\text{smear}})\right|$$

where $d_{\text{smear}} = v \cdot t_{\text{int}} \cdot f / h$ is the smear
distance in the focal plane (velocity $v$, integration time $t_{\text{int}}$,
focal length $f$, altitude $h$).

### Jitter MTF

$$\text{MTF}_{\text{jitter}}(f) = \exp(-2\pi^2 \sigma_j^2 f^2)$$

where $\sigma_j = \sigma_{\text{jitter\_rad}} \cdot f$ is the jitter RMS
in the focal plane.

**ChainState additions:**

- Stage outputs: smear and jitter MTF terms

---

## Stage 5: Spectral Integration

*Implementation: `src/radiant/spectral_integration/stage.py`*

Collapses spectral radiance to in-band photoelectrons per pixel. This is
the only stage that performs spectral-to-scalar reduction (Rule 8).

### Signal Electrons

$$S = \int_{\lambda_1}^{\lambda_2} E_{\text{FPA}}(\lambda) \cdot A_{\text{pixel}} \cdot \text{QE}(\lambda) \cdot \frac{\lambda}{hc} \cdot t_{\text{int}} \; d\lambda \;\cdot\; \text{EE}_{\text{box}}$$

where:

- Integration bounds are `filter_min_um` to `filter_max_um`
- QE$(\lambda)$ is quantum efficiency (flat scalar or spectral)
- $\lambda / hc$ converts from energy to photon rate
- $t_{\text{int}}$ is integration time
- EE$_{\text{box}}$ is 1.0 for extended scenes, < 1 otherwise (Rule 9)

**ChainState additions:**

- Frame `photoelectrons`: in-band signal in electrons
- Stage outputs: `signal_e`, `background_e`

---

## Stage 6: Detector

*Implementation: `src/radiant/detector/stage.py`*

Computes the noise budget. See [Noise Model](noise_model.md) for the
complete noise taxonomy.

**ChainState additions:**

- Stage outputs: `noise_budget_raw` with 16 individual noise terms

---

## Stage 7: Readout

*Implementation: `src/radiant/readout/stage.py`*

Applies TDI, binning, coadds, gain, and ADC. Scales noise terms from
the detector stage.

### TDI Signal Scaling

$$S_{\text{final}} = S \cdot N_{\text{TDI}} \cdot M_{\text{bin}} \cdot N_{\text{coadd}}$$

### Noise Scaling

Each noise term is scaled according to its type (shot-like, read-like,
spatial). See [Noise Model](noise_model.md) for scaling rules.

**ChainState additions:**

- Noise terms (16 `NoiseTerm` objects)
- Stage outputs: `sigma_total_e`, `sigma_temporal_e`, `sigma_spatial_e`,
  `signal_e_final`

---

## Performance Metrics

*Implementation: `src/radiant/performance/stage.py`, `src/radiant/performance/snr.py`,
`src/radiant/performance/giqe.py`*

### SNR

$$\text{SNR} = \frac{S}{\sigma_{\text{total}}}$$

where $S$ is signal electrons (post-readout) and $\sigma_{\text{total}}$ is
RSS of all noise terms.

### Contrast SNR

$$\text{SNR}_{\text{contrast}} = \frac{S_{\text{target}} - S_{\text{background}}}{\sigma_{\text{total}}}$$

### NIIRS (GIQE-5)

$$\text{NIIRS} = c_0 + c_1 \log_{10}(\text{GSD}) + c_2 \log_{10}(\text{RER}) + c_3 \log_{10}(\text{SNR}) + c_4 H + c_5 G$$

where GSD is in inches, RER is Relative Edge Response, $H$ is overshoot,
and $G$ is noise gain. Coefficients: $c_0=9.57$, $c_1=-3.32$, $c_2=3.32$,
$c_3=1.559$, $c_4=-0.334$, $c_5=-0.01$.

### System MTF at Nyquist

$$\text{MTF}_{\text{sys}}(f_N) = \text{MTF}_{\text{optics}} \cdot \text{MTF}_{\text{det}} \cdot \text{MTF}_{\text{smear}} \cdot \text{MTF}_{\text{jitter}}$$

at $f_N = 1 / (2p)$ where $p$ is pixel pitch.

---

## Dimensional Trace

| Stage                | Input Units          | Output Units         | Conversion        |
|----------------------|----------------------|----------------------|-------------------|
| Source               | K, dimensionless     | W/m$^2$/sr/µm       | Planck + ε        |
| Atmosphere           | W/m$^2$/sr/µm       | W/m$^2$/sr/µm       | × τ + L_path      |
| Optics               | W/m$^2$/sr/µm       | W/m$^2$/µm (irrad.) | × Ω × τ_opt       |
| Spectral Integration | W/m$^2$/µm, m$^2$   | electrons            | × A × QE × λ/hc × t |
| Detector             | electrons            | electrons (noise)    | noise model        |
| Readout              | electrons            | electrons (scaled)   | × N_TDI × M × N_co |
| Performance          | electrons            | dimensionless (SNR)  | S / σ             |

---

## Assumptions and Limitations

- Lambertian target emission (no BRDF)
- No molecular spectroscopy or fluorescence
- No atmospheric refraction or scintillation
- No ghost images, BSDF scatter, or chromatic aberration
- No optical crosstalk between pixels
- No temporal variability in scene
- See `docs/RADIANT_Scope_Decisions.md` for the full list of 26 deferred effects
