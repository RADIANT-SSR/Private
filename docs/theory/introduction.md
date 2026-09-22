# Introduction

*Persona: every reader — this chapter orients the rest of the manual.*

RADIANT is a first-principles performance model for electro-optical sensors, space-based
and airborne, from the ultraviolet through the long-wave infrared. It answers questions of
the form *what will this sensor, looking at that scene through this atmosphere, actually
measure* — and it answers them by carrying a physical quantity, in canonical units, from
the emitting surface to a photoelectron count and then to a performance metric, with no
unexplained factor anywhere in between.

This chapter states what the chain is, what selects the radiometric regime a target falls
into, and where the model's boundaries lie. Every equation named here is developed in a
later chapter; the purpose of this one is that a reader always knows which chapter to
open.

---

## 1. The chain at a glance

RADIANT models the end-to-end signal chain as ten sequential stages. Each stage is a pure
function of an immutable chain state: it consumes what earlier stages published, adds its
own radiometric frames, noise terms, bias terms, and transfer-function contributions, and
returns a new state. No stage reads a file, calls another stage, or edits what an earlier
stage published.

| # | Stage | What it establishes | Detailed in |
|---|---|---|---|
| 0 | Geometry | Slant range $R_s$ [m], target-referenced zenith angle $\theta_o$ [rad], solar geometry, ground sampling, motion rates | Ch. 2 |
| 1 | Source | Target and background spectral radiance $L_{\mathrm{target}}(\lambda)$, $L_{\mathrm{bg}}(\lambda)$ [W/m²/sr/µm]; tentative regime | Ch. 3 |
| 2 | Atmosphere | Transmittance $\tau_{\mathrm{atm}}(\lambda)$, path radiance $L_{\mathrm{path}}(\lambda)$, downwelling $L_{\mathrm{sky}}(\lambda)$, and the at-aperture radiance they produce | Ch. 3, Ch. 4 |
| 3 | Optics | Aperture area $A_{\mathrm{ap}}$ [m²], pixel solid angle $\Omega_{\mathrm{pix}}$ [sr], throughput $\tau_{\mathrm{opt}}(\lambda)$, warm-optics self-emission, the diffraction-plus-aberration PSF and optical MTF, and the **final** regime | Ch. 3, Ch. 5 |
| 4 | Platform | Jitter and smear degradation of the PSF and the MTF budget; $\mathrm{EE}_{\mathrm{box}}$ from the fully degraded PSF | Ch. 5 |
| 5 | Spectral integration | The single spectral-to-scalar collapse: spectra in, photoelectrons out | Ch. 3 |
| 6 | Detector | Quantum efficiency, dark current, the noise budget's detector terms, detector-plane MTF kernels | Ch. 5, Ch. 6 |
| 7 | Readout | TDI, binning, co-adding, gain, ADC — signal scaling and the readout noise terms | Ch. 6 |
| 8 | Calibration | Post-NUC residual fixed-pattern noise, drift, and the radiometric bias budget | Ch. 7 |
| 9 | Performance | SNR, NEDT, NIIRS, system MTF, detection range, and the rest of the metric layer | Ch. 8 |

### Geometry first

Geometry runs before radiometry, not alongside it. The reason is that almost every
radiometric quantity downstream is conditioned on a geometric one: the atmospheric slant
column depends on the path zenith angle, the solar reflected term depends on the solar
zenith angle, the sub-pixel fill fraction depends on the target's angular extent at the
slant range, and the smear kernel depends on the image-plane motion rate. Deriving those
inside the stages that consume them would mean deriving several of them more than once,
which is how two parts of a model come to disagree about the same angle. The geometry
stage solves the viewing triangle once, publishes $R_s$, $\theta_o$, $\eta$, and the
sampling and motion quantities, and every later stage reads them.

### The radiometric spine

Stages 1 through 5 form the radiometric spine. The source stage builds spectral radiance
from Planck emission, graybody emissivity, reflected solar irradiance through a BRDF, or a
user-supplied spectrum. The atmosphere stage attenuates it and adds what the atmosphere
itself contributes along the line of sight:

$$L_{\mathrm{ap}}(\lambda) = L_{\mathrm{target}}(\lambda)\,\tau_{\mathrm{atm}}(\lambda) + L_{\mathrm{path}}(\lambda)$$

The optics stage supplies the collecting area, the solid angle the pixel subtends, the
train's transmittance, and — in the thermal infrared — the train's own emission, whose
emissivity is never an independent input but is always derived from the element's
reflectance and transmittance by Kirchhoff's law. The spectral-integration stage then
performs the one collapse the whole model is allowed:

$$S = \int_{\lambda_1}^{\lambda_2} L_{\mathrm{ap}}(\lambda)\,\tau_{\mathrm{opt}}(\lambda)\,A_{\mathrm{ap}}\,\Omega_{\mathrm{pix}}\,\mathrm{QE}(\lambda)\,\frac{\lambda_m}{hc}\,t_{\mathrm{int}}\;d\lambda \quad [\mathrm{e}\text{-}]$$

Before that integral every radiometric quantity is a spectrum; after it every quantity is
a per-pixel scalar in electrons. There is no second collapse and no stage that partially
collapses one.

### The spatial spine

In parallel with the radiometric spine, the model carries a spatial description of the
same system along two paths that must agree. The **PSF path** starts from the complex
pupil, forms the point spread function, and convolves onto it every spatial degradation in
turn — detector aperture, charge diffusion, interpixel capacitance, jitter, smear,
turbulence. Ensquared energy, relative edge response, full width at half maximum, Strehl
ratio, and the line and edge responses are computed from that one object. The **MTF product
path** computes the optical transfer function directly from the autocorrelation of the same
pupil and multiplies it by an analytic or kernel-derived MTF for each downstream
contributor:

$$\mathrm{MTF}_{sys}(\nu) = \prod_i \mathrm{MTF}_i(\nu)$$

MTF budgets, MTF at Nyquist, folded MTF, and the image-quality equation consume this path.
Because both paths originate in the same pupil, the Fourier transform of the convolved PSF
must reproduce the MTF product, and the model checks that on every run that computes the
spatial path. A failure means a degradation was added to one path and not the other. The
two paths and the check are the subject of Chapter 5.

### Terms, not transformations

Two stages — platform and calibration — deliberately transform nothing. They contribute
*terms*: a kernel and an MTF factor in the platform's case, noise terms and bias terms in
the calibration's. The calibration stage's position is itself load-bearing physics. Readout
applies the $\sqrt{N}$ averaging of TDI and co-adding to the temporal noise terms;
calibration runs after, so its residuals are structurally exempt from that averaging,
which is exactly right because correlated errors do not average down.

---

## 2. The three radiometric regimes

How much of a target's flux reaches one pixel depends on whether the target fills the
pixel, underfills it, or is small enough that the point spread function — not the target —
sets the energy distribution. RADIANT classifies every scene into one of three regimes,
and the classification changes the signal equation, not merely a label.

| Regime | Physical meaning | $\mathrm{EE}_{\mathrm{box}}$ applied? |
|---|---|---|
| Extended | Target fills the pixel footprint completely | No — the pixel sees a uniform radiance field |
| Sub-pixel | Target smaller than the pixel but larger than the diffraction blur | Yes, to the target term only |
| Point source | Target smaller than the diffraction limit | Yes, to the target term |

**What selects the regime.** The source stage computes the target's angular extent
$\theta = \sqrt{A_t}/R_s$ [rad] and compares it with the pixel instantaneous field of
view $\mathrm{IFOV} = p/f$ [rad]. A declared fill fraction below 1.0 forces the sub-pixel
regime; otherwise an explicit override is honored if present; otherwise
$\theta \ge 2\,\mathrm{IFOV}$ gives extended, $\theta \le 0.25\,\mathrm{IFOV}$ gives point
source, and anything between is sub-pixel. That classification is *tentative*. The optics
stage, which is the first stage that knows the actual PSF size, finalizes it. Every
downstream stage reads the final classification and no stage re-derives it.

**Where the ensquared energy enters.** $\mathrm{EE}_{\mathrm{box}}$ — the fraction of the
degraded PSF's energy falling inside one pixel — is computed in the platform stage from the
*fully* degraded PSF, so jitter, smear, and turbulence are already in it, and it is applied
in the spectral-integration stage and nowhere else. It multiplies the target term in the
sub-pixel and point-source regimes, never the background term, and never anything in the
extended regime, where the pixel is filled by construction and the energy that leaves it
is replaced by energy from the neighboring scene.

Getting the regime wrong is the most common cause of an SNR that looks inexplicable: an
extended scene treated as a point source loses the factor $\mathrm{EE}_{\mathrm{box}} < 1$
for no physical reason, and a point source treated as extended assumes a uniformly filled
pixel that does not exist.

---

## 3. What the model predicts

The metric layer turns the final chain state into the quantities an analyst reports. They
fall into five families, each of which can be enabled or disabled per run:

- **Radiometric** — SNR, contrast SNR, signal-to-clutter-plus-noise ratio, NEDT [K],
  radiometric accuracy [% and K], detection range [m], minimum resolvable temperature at
  Nyquist [K]. The classical sensitivity relatives — noise-equivalent irradiance, power,
  specific detectivity, noise-equivalent radiance and reflectance, and the temperature
  retrieval with its Jacobians — are developed in Chapter 8 as computed relatives of the
  same chain state.
- **Spatial and MTF** — system MTF at Nyquist, folded MTF, aliased fraction, Strehl ratio,
  relative edge response, ensquared energy in 1×1 and 3×3 pixel boxes, PSF full width at
  half maximum [m], per-contributor MTF budgets.
- **Sampling** — ground sample distance [m] cross-track, along-track, and geometric mean;
  target-plane sample distance [m]; the sampling parameter $Q$; swath width [m]; ground
  range [m]; access rate [m²/s]; diffraction limit in µrad and in meters.
- **Saturation and dynamic range** — well margin [dB], ADC margin [dB], dynamic range
  [dB], maximum integration time before saturation [s].
- **Interpretability** — NIIRS via the General Image Quality Equation, with an explicit
  flag when an input falls outside the equation's calibration envelope.

Every metric is reported with its units, and a metric whose inputs do not support it is
reported as a named failure rather than as a silent NaN.

---

## 4. Model scope — what is deliberately absent

A performance model earns trust by being explicit about its edges. The following are not
modeled, and a result that depends on one of them is outside the model's validity rather
than merely imprecise.

**Scene and source.** No molecular band spectroscopy or plume chemistry; no fluorescence;
no scene-level interreflection or ray tracing; no temporal scene variability within or
between frames; no lunar illumination and no sun-glint geometry. Target emission is
Lambertian, and the reflectance structure available is the Lambertian and normalized-Phong
BRDF pair rather than a microfacet model or measured BRDF tables.

**Atmosphere.** No refraction, and therefore no bending of the geometric path; no
scintillation; no adjacency effect; no polarization; no cloud or precipitation attenuation.
The simple parametric model and the library-backed models are two families with one
contract, and their limits are the subject of Chapter 4.

**Optics.** No ghost images, no bidirectional scatter distribution function beyond the
scalar-roughness halo, no chromatic aberration, no field-dependent vignetting map.
Aberrations enter as wavefront error in the pupil — either a bulk RMS value or a Zernike
set — and their interaction with diffraction is handled in the pupil, never as a separate
multiplicative MTF factor.

**Detector and readout.** No optical crosstalk between pixels, no charge-trapping model,
no ADC integral or differential nonlinearity, no electronics-level coupling or supply
noise, no cosmic-ray transient or bad-pixel statistics. Blooming, charge-transfer
efficiency in CCDs, and radiation-damage accumulation are outside the current model.

**Spatial.** No geometric distortion, no frame-to-frame registration error, no whiskbroom
scan-mechanism transfer function, and no short-exposure turbulence branch — turbulence
enters as the long-exposure Kolmogorov result, from a Fried parameter entered directly or
integrated from a $C_n^2$ profile (Chapter 4), and is omitted entirely when that parameter
resolves to zero or negligible.

---

## 5. How to read this manual

Chapter 2 establishes the viewing geometry and sampling on which everything else is
conditioned. Chapter 3 is the radiometric core: the governing equations from Planck's law
to the photoelectron count, each with its validity limits, its classic implementation
pitfalls, and a pinned numeric anchor. Chapter 4 covers the two atmosphere model families.
Chapter 5 is the spatial model, PSF and MTF together. Chapter 6 is the noise taxonomy and
its acquisition scaling. Chapter 7 is the calibration error model — what survives a
non-uniformity correction, and how it sets a floor that integration time cannot lower.
Chapter 8 is the metric layer. The appendix treats the mixed refractive-reflective optical
train in full, and the front matter holds the notation on which all of it depends.

Throughout, an equation is stated in the form the model actually evaluates. Where the
implementation makes an approximation, the approximation is named where the equation is
given, not deferred to a limitations list.

Every quantitative claim in the source documents behind this manual is anchored to the
implementation function that evaluates it and to a committed test that pins its value;
the repository sources carry those anchors as the project's traceability record. The
typeset manual omits the pointers and keeps the physics.
