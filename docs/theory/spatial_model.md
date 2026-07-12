# Spatial Model

*Persona: Tom (optical designer), Sarah (systems engineer)*

PSF construction, MTF decomposition, encircled/ensquared energy, and image
quality metrics as implemented in RADIANT.

---

## PSF Construction

*Implementation: `src/radiant/optics/psf.py`*

### Diffraction-Limited PSF

The monochromatic diffraction PSF is computed by FFT propagation from the
pupil aperture:

$$\text{PSF}(\mathbf{x}) = \left| \mathcal{F}\left\{ P(\mathbf{u}) \cdot \exp\!\left(i \phi(\mathbf{u})\right) \right\} \right|^2$$

where $P(\mathbf{u})$ is the binary pupil mask (including central
obscuration) and $\phi(\mathbf{u})$ is the wavefront phase error.

For a clear circular aperture, this produces the Airy pattern with first
dark ring at:

$$r = 1.22 \frac{\lambda f}{D}$$

Central obscuration (ratio $\epsilon$) redistributes energy from the core
to the rings, reducing peak intensity and encircled energy.

### Wavefront Error

WFE reduces image quality by distorting the PSF. RADIANT supports three
modes (`optics.wfe_mode`):

- **`scalar_rms`**: Applies a Strehl reduction. Strehl ratio:
  $S_r \approx \exp(-(2\pi \sigma_{\text{WFE}})^2)$ where $\sigma_{\text{WFE}}$
  is RMS WFE in waves at the reference wavelength.
- **`zernike`**: Constructs phase from Zernike polynomial coefficients
- **`kolmogorov`**: Atmospheric turbulence phase screen

### Polychromatic PSF

*Implementation: `src/radiant/optics/psf.py :: compute_polychromatic_psf()`*

The broadband PSF is a photon-flux-weighted average of monochromatic PSFs
across the spectral band:

$$\text{PSF}_{\text{poly}}(\mathbf{x}) = \frac{\sum_i w_i \cdot \text{PSF}(\mathbf{x}, \lambda_i)}{\sum_i w_i}$$

where the weights are proportional to photon flux:

$$w_i = L(\lambda_i) \cdot \frac{\lambda_i}{hc}$$

The number of wavelengths is controlled by `optics.psf_n_wavelengths`
(default: 1 = monochromatic at band center). The effective wavelength is
the flux-weighted mean:

$$\lambda_{\text{eff}} = \frac{\sum_i w_i \lambda_i}{\sum_i w_i}$$

---

## MTF Decomposition

The system MTF is the product of independent MTF components:

$$\text{MTF}_{\text{sys}}(f) = \text{MTF}_{\text{optics}}(f) \cdot \text{MTF}_{\text{det}}(f) \cdot \text{MTF}_{\text{smear}}(f) \cdot \text{MTF}_{\text{jitter}}(f)$$

Each is evaluated as a 1D function of spatial frequency $f$ (cycles/m)
or as a 2D transfer function.

### Optical MTF

*Implementation: `src/radiant/optics/mtf.py`*

Computed as the normalized magnitude of the Fourier transform of the PSF:

$$\text{MTF}_{\text{optics}}(f) = \frac{|\mathcal{F}\{\text{PSF}\}(f)|}{|\mathcal{F}\{\text{PSF}\}(0)|}$$

For a diffraction-limited circular aperture, this is the classical OTF:
approximately linear falloff from DC to the cutoff frequency
$f_c = D / \lambda$.

### Detector MTF (Pixel Aperture)

*Implementation: `src/radiant/platform/sampling.py`*

The pixel acts as a spatial integrator over its photosensitive area,
producing a sinc MTF:

$$\text{MTF}_{\text{det}}(f) = \left|\text{sinc}(\pi f \cdot p \cdot \sqrt{\text{FF}})\right|$$

where $p$ is pixel pitch and FF is the **areal** fill factor (the
photosensitive fraction of the pixel cell). A square photosite of area
$\text{FF}\cdot p^2$ has linear width $p\sqrt{\text{FF}}$, which sets the
sinc argument (CU-074). Separable in x and y if pixel pitches differ. At
$\text{FF}=1$ this reduces to $\text{sinc}(\pi f p)$. The same width
$p\sqrt{\text{FF}}$ is used by the PSF-path pixel-aperture kernel
(`optics/pixel_kernel.py`), so the two Rule-4 paths agree; the
radiometric collecting area is the photosensitive area $p^2\cdot\text{FF}$,
so the collected signal scales by FF (`spectral_integration/stage.py`).

### IPC MTF

*Implementation: `src/radiant/platform/sampling.py`*

Inter-pixel capacitance (IPC) coupling smears the image:

$$\text{MTF}_{\text{IPC}}(f) = (1 - 4\alpha) + 2\alpha \cos(2\pi f p)$$

where $\alpha$ is the coupling fraction (`detector.ipc_coupling`).

### Smear MTF

*Implementation: `src/radiant/platform/stage.py`*

Platform motion during integration causes image smear:

$$\text{MTF}_{\text{smear}}(f) = \left|\text{sinc}(\pi f \cdot d_{\text{smear}})\right|$$

where $d_{\text{smear}} = v_{\text{ground}} \cdot t_{\text{int}} \cdot f / h$
is the smear distance projected to the focal plane.

### Jitter MTF

*Implementation: `src/radiant/platform/stage.py`*

Random pointing errors modeled as Gaussian:

$$\text{MTF}_{\text{jitter}}(f) = \exp(-2\pi^2 \sigma_j^2 f^2)$$

where $\sigma_j = \sigma_{\text{jitter\_rad}} \cdot f$ is jitter RMS in the
focal plane (meters).

---

## Ensquared Energy (EE_box)

*Implementation: `src/radiant/optics/psf.py :: EffectivePSF.ensquared_energy()`*

EE_box is the fraction of PSF energy falling within a square pixel:

$$\text{EE}_{\text{box}} = \int\!\!\int_{\text{pixel}} \text{PSF}(x, y) \, dx \, dy$$

**Rule 4**: Both MTF and EE_box are derived from the same `EffectivePSF`
object. Never compute them from different PSFs.

**Rule 9**: EE_box is applied exactly once, in `SpectralIntegrationStage`:

- Extended scene: $\text{EE}_{\text{box}} = 1.0$
- Sub-pixel: applied to target signal only, not background
- Point-source: applied to target signal

---

## Nyquist Frequency

The Nyquist frequency for a pixel pitch $p$ is:

$$f_N = \frac{1}{2p}$$

`mtf_at_nyquist` in `result.metrics` reports $\text{MTF}_{\text{sys}}(f_N)$.
Values above ~0.1 are typical; below ~0.05 indicates severe resolution loss.

The ratio $Q = \lambda f/\# / p$ characterizes sampling:

- $Q < 1$: under-sampled (aliasing possible, higher MTF at Nyquist)
- $Q = 1$: critically sampled
- $Q > 1$: over-sampled (smoother PSF, lower MTF at Nyquist)

---

## NIIRS via GIQE-5

*Implementation: `src/radiant/performance/giqe.py`*

The General Image Quality Equation version 5:

$$\text{NIIRS} = c_0 + c_1 \log_{10}(\text{GSD}) + c_2 \log_{10}(\text{RER}) + c_3 \log_{10}(\text{SNR}) + c_4 H + c_5 G$$

| Coefficient | Value    |
|------------|----------|
| $c_0$      | 9.57     |
| $c_1$      | -3.32    |
| $c_2$      | 3.32     |
| $c_3$      | 1.559    |
| $c_4$      | -0.334   |
| $c_5$      | -0.01    |

Input terms:

- **GSD** (Ground Sample Distance) in inches: geometric mean of along-track
  and cross-track GSD. $\text{GSD} = p \cdot h / f$ (pixel pitch × altitude /
  focal length).
- **RER** (Relative Edge Response): geometric mean of x and y RER.
- **SNR**: signal-to-noise ratio.
- **H**: edge overshoot (0 for most systems).
- **G**: noise gain (≈1 for standard processing).

### RER Computation

*Implementation: `src/radiant/optics/psf.py :: EffectivePSF.rer()`*

RER is derived from the Edge Response Function (ERF), which is the
cumulative integral of the Line Spread Function (LSF):

$$\text{RER} = \text{ERF}(+p/2) - \text{ERF}(-p/2)$$

where $p$ is pixel pitch. The 2D RER is $\sqrt{\text{RER}_x \cdot \text{RER}_y}$.

---

## Summary of Key Variables

| Variable | Symbol | Unit | Code location |
|----------|--------|------|---------------|
| PSF | $\text{PSF}(x,y)$ | normalized | `EffectivePSF.data` |
| Pixel pitch | $p$ | m | `detector.pixel_pitch_x_um` (converted) |
| Focal length | $f$ | m | `optics.focal_length_m` |
| Aperture diameter | $D$ | m | `optics.aperture_diameter_m` |
| WFE RMS | $\sigma_{\text{WFE}}$ | waves | `optics.wfe_rms_waves` |
| Jitter RMS | $\sigma_{\text{jitter}}$ | rad | platform jitter parameter |
| EE_box | $\text{EE}_{\text{box}}$ | dimensionless | `EffectivePSF.ensquared_energy()` |
| MTF at Nyquist | $\text{MTF}(f_N)$ | dimensionless | `result.metrics["mtf_at_nyquist"]` |
| RER | $\text{RER}$ | dimensionless | `EffectivePSF.rer()` |
| GSD | $\text{GSD}$ | m | $p \cdot h / f$ |
| NIIRS | $\text{NIIRS}$ | dimensionless | `compute_giqe5()` |
