# Spatial Model

*Persona: Tom (optical designer), Sarah (systems engineer)*

PSF construction, the MTF budget, ensquared energy, sampling, and the dual-path
architecture that keeps them consistent — as implemented in RADIANT. Numeric anchors are
blind-derived literature values from the 2026-07 assurance audit
(`docs/reports/assurance_audit_2026-07/track_a2_spatial_derivation.md`).

**Symbols used throughout:** $\lambda$ wavelength [µm] ($\lambda_m = \lambda\cdot10^{-6}$ m
where SI is needed); $D$ aperture diameter [m]; $f$ focal length [m]; $F_\# = f/D$;
$\epsilon$ central-obscuration ratio; $p$ pixel pitch [m]; $\nu$ spatial frequency at the
focal plane [cy/m] (cy/mm in worked numbers); $\nu_c = 1/(\lambda F_\#)$ optical cutoff;
$\nu_{Nyq} = 1/(2p)$ Nyquist.

---

## 1. The two spatial paths (Rule 4)

RADIANT maintains **two parallel spatial representations, both rooted in the same complex
pupil**:

- the **PSF path** — every spatial degradation enters as a convolution kernel on one
  `EffectivePSF`; EE_box, RER, FWHM, Strehl, LSF and ERF are computed only from it;
- the **MTF product path** — the frequency-domain budget
  $\mathrm{MTF}_{sys}(\nu) = \prod_i \mathrm{MTF}_i(\nu)$ consumed by MTF-at-Nyquist,
  folded MTF, and GIQE/NIIRS.

The two are the same information: for incoherent imaging the OTF is simultaneously the
Fourier transform of the PSF and the normalized autocorrelation of the complex pupil
$P = A\,e^{i2\pi W/\lambda}$,

$$\mathrm{OTF}(\boldsymbol{\nu}) = \frac{\mathcal{F}\{\mathrm{PSF}\}(\boldsymbol{\nu})}{\mathcal{F}\{\mathrm{PSF}\}(0)} = \frac{(P \star P)(\lambda f \boldsymbol{\nu})}{(P \star P)(0)},$$

so the FFT of the fully convolved `EffectivePSF` must agree with the MTF product. RADIANT
checks this on every chain run that computes the spatial path, to an absolute tolerance of
$2\times10^{-2}$ (≈2× the measured full-chain discretization floor).

**Why a separate $\mathrm{MTF}_{diffraction}\times\mathrm{MTF}_{aberration}$ factoring is
forbidden:** aberrations are a phase modification *inside* the pupil, entering the
autocorrelation as a phase *difference across the shear* under the integral — they cannot
be factored into (clear-aperture MTF) × (aberration-only multiplier). True aberrated OTFs
can go negative (defocus contrast reversal); no positive scalar multiplier can reproduce
that. Only genuinely independent *image-plane convolutions* (detector aperture, diffusion,
IPC, jitter, smear) and statistically independent ensemble averages (turbulence) multiply.
The one deliberate MTF-only term is TDI mis-registration (§8) — a readout-timing effect
with no instantaneous kernel, excluded from the consistency comparison.

**In RADIANT.** `performance/consistency_check.py::check_dual_path_consistency`
(`_EXCLUDED_PREFIXES = ("mtf_tdi",)`) · anchored by
`performance/tests/test_consistency_check.py` and hard-gated across all shipped GUI
baselines by `tests/integration/test_gui_baselines.py::test_gui_baseline_dual_path_consistency`.
**References.** [Goodman 2005], [Gaskill 1978].

---

## 2. Diffraction-limited PSF

**Equation.** Unaberrated circular pupil (Airy):

$$I(r) = I_0\left[\frac{2J_1(v)}{v}\right]^2,\qquad v = \frac{\pi r}{\lambda F_\#},$$

first zero at $v_1 = 3.8317060$, i.e. $r_1 = 1.2196699\,\lambda F_\#$. Encircled energy
$EE(v) = 1 - J_0^2(v) - J_1^2(v)$ (unobscured only): 0.837785 at the first dark ring.
With central obscuration $\epsilon$:

$$I(v) = \frac{I_0}{(1-\epsilon^2)^2}\left[\frac{2J_1(v)}{v} - \epsilon^2\,\frac{2J_1(\epsilon v)}{\epsilon v}\right]^2$$

— core narrows, energy moves into the rings.

**Implementation.** RADIANT does not evaluate the Bessel form; it FFT-propagates the
sampled complex pupil (aperture mask incl. obscuration and spider vanes, plus wavefront
phase) and takes $|\cdot|^2$ — the Airy pattern is the *test oracle*, not the algorithm.
Polychromatic PSFs are photon-flux-weighted sums of monochromatic PSFs
(`optics/psf_poly.py`, `optics.psf_n_wavelengths`).

**Assumptions & validity.** Scalar Fraunhofer diffraction; $F_\# \gtrsim 2$ for the scalar
approximation; grid effects controlled by `pupil_npix=128`, `psf_oversample=8` defaults
(`optics/sampling.py`).

**Pitfalls.** 1.22 vs the exact 1.2196699 (0.03% — matters for tight baselines); amplitude
vs irradiance PSF; forgetting the $(1-\epsilon^2)^{-2}$ energy renormalization; applying
the unobscured EE formula to an annular pupil.

**Numeric anchor.** $r_1 = 19.5147$ µm at $\lambda = 4$ µm, $F_\# = 4$.

**In RADIANT.** `optics/psf_mono.py::compute_psf` (pupil from `optics/aperture.py`,
`optics/pupil_amplitude.py`, `optics/pupil_phase.py`) · anchored by
`optics/tests/test_diffraction.py::TestAiryFirstZero` and `optics/tests/test_psf.py`
(84%-ring energy). **References.** [Goodman 2005].

---

## 3. Optical MTF from the pupil autocorrelation

**Equation.** Clear circular pupil, incoherent:

$$\mathrm{MTF}(\tilde\nu) = \frac{2}{\pi}\left[\arccos\tilde\nu - \tilde\nu\sqrt{1-\tilde\nu^2}\right],\quad \tilde\nu = \nu/\nu_c \le 1,\qquad \nu_c = \frac{1}{\lambda F_\#}.$$

RADIANT computes the general case (obscuration, spiders, aberrations) by direct
autocorrelation of the complex pupil — a single `MTF_optics` term, never a factored
product (§1).

**Assumptions & validity.** Incoherent illumination (the coherent cutoff is $\nu_c/2$ — a
classic factor-2 trap); monochromatic per-λ, spectrally weighted for broadband.

**Pitfalls.** λ-unit slips in $\nu_c$ (λ must be in mm for cy/mm); NaN instead of 0 above
cutoff; treating the annular-pupil MTF as clear-MTF × scalar (the true ratio crosses 1:
≈0.78 at $0.3\nu_c$ but ≈1.10 at $0.8\nu_c$ for $\epsilon=0.3$).

**Numeric anchor.** $\mathrm{MTF}(0.5\nu_c) = \frac{2}{\pi}\left(\frac{\pi}{3} - \frac{\sqrt3}{4}\right) = 0.391002$;
$\nu_c = 62.5$ cy/mm at $\lambda = 4$ µm, $F_\# = 4$.

**In RADIANT.** `optics/pupil_mtf.py::pupil_autocorrelation_mtf_1d` (and `_2d`) · anchored
by `optics/tests/test_pupil_mtf.py` (analytic circular form) and the dual-path tests
`tests/integration/test_dual_path_mtf.py`. **References.** [Goodman 2005], [O'Neill 1956].

---

## 4. Wavefront error, Zernike modes, and Strehl

**Equations.** Wavefront OPD enters the pupil phase as $e^{i2\pi W/\lambda}$. Noll-indexed
Zernike defocus $Z_4 = \sqrt3\,(2\rho^2 - 1)$: with $W = a_4 Z_4$, the RMS OPD is exactly
$a_4$ and the peak-to-valley is $2\sqrt3\,\sigma$. Maréchal Strehl approximation from RMS
OPD $\sigma_{OPD}$:

$$S \approx \exp\!\left[-\left(\frac{2\pi\,\sigma_{OPD}}{\lambda}\right)^2\right].$$

RADIANT reports two Strehls: the **PSF-derived** `strehl` — degraded-PSF peak over the
diffraction-limited `reference_psf` peak, with the *same* detector kernels applied to both
so detector effects cancel — and the analytic `strehl_marechal` diagnostic.

**Assumptions & validity.** Maréchal reliable for $\sigma \lesssim \lambda/10$; Noll
normalization (coefficient = RMS) — the Wyant convention differs by $\sqrt3$-type factors.
Zernike modes are orthonormal on the unbobscured unit disk; annular pupils strictly need
annular polynomials.

**Pitfalls.** Waves vs radians in the Maréchal exponent (factor $(2\pi)^2$); P-V vs RMS
(the $2\sqrt3$ is defocus-specific); using Maréchal to reconstruct a PSF or MTF (it is a
scalar diagnostic only).

**Numeric anchors.** $S(\sigma = \lambda/14) = 0.817569$ (the classic ≈0.8
diffraction-limited threshold); quarter-wave P-V defocus → $S = 0.814$.

**In RADIANT.** `optics/zernike.py`, `optics/zernike_opd.py`, `optics/wavefront.py`
(modes: `scalar_rms` / `zernike` / `kolmogorov`, `optics.wfe_reference_wavelength_um`
default 0.633 µm); `optics/strehl.py::compute_strehl` (PSF ratio),
`performance/strehl.py::compute_strehl` (Maréchal metric) · anchored by
`optics/tests/test_zernike.py` (orthonormality integrals),
`performance/tests/test_strehl.py`. **References.** [Noll 1976], [Goodman 2005].

---

## 5. Detector-plane kernels: pixel aperture, diffusion, IPC

**Pixel aperture.** A photosite of linear width $w$ integrates the image — a rect
convolution:

$$\mathrm{MTF}_{det}(\nu) = \left|\frac{\sin(\pi w \nu)}{\pi w \nu}\right|,$$

first zero at $\nu = 1/w$. With areal fill factor FF, $w = p\sqrt{\mathrm{FF}}$ (CU-074) —
the same width used by the PSF-path pixel kernel (`optics/pixel_kernel.py`, area-overlap
sampled per CU-003), so the Rule-4 paths agree.

**Charge diffusion.** Gaussian carrier spread of RMS $\sigma_d$:
$\mathrm{MTF}_{diff}(\nu) = \exp(-2\pi^2\sigma_d^2\nu^2)$.

**Inter-pixel capacitance.** Pitch-spaced coupling kernel with fraction $\alpha$
(`detector.ipc_coupling`): $\mathrm{MTF}_{IPC}(\nu) = (1-4\alpha) + 2\alpha\cos(2\pi\nu p)$
per axis (nearest-neighbor form).

**Pitfalls.** The sinc convention: NumPy's `np.sinc(x)` already includes π —
`np.sinc(w·ν)` is correct, `np.sinc(π·w·ν)` double-counts π and moves the first zero to
$1/(\pi w)$. Pitch vs aperture width when FF < 1. IPC and diffusion both exist in kernel
form for the PSF path and analytic form for the MTF path — adding one side only violates
Rule 4.

**Numeric anchor.** 100% fill at Nyquist: $\sin(\pi/2)/(\pi/2) = 2/\pi = 0.636620$.

**In RADIANT.** `detector/stage.py` (aperture term, with $\sqrt{\mathrm{FF}}$),
`detector/diffusion.py::diffusion_mtf`, `detector/ipc.py::ipc_mtf_1d` +
`ipc_kernel_pitch_spaced` · anchored by `detector/tests/test_stage_mtf_term.py`,
`test_diffusion.py`, `test_ipc.py` (kernel-FFT vs analytic cross-checks).
**References.** [Boreman 2001], [Holst 2008].

---

## 6. Platform kernels: jitter and smear

**Jitter** (random LOS motion, many cycles per integration): Gaussian blur of RMS
$\sigma$ at the focal plane ($\sigma = \sigma_\theta f$ for angular jitter
$\sigma_\theta$):

$$\mathrm{MTF}_{jit}(\nu) = \exp(-2\pi^2\sigma^2\nu^2).$$

**Smear** (deterministic image motion $d = v_{image}\,t_{int}$ during integration): rect
blur,

$$\mathrm{MTF}_{smear}(\nu) = \left|\frac{\sin(\pi d \nu)}{\pi d \nu}\right|,$$

applied along the motion direction only. $v_{image}$ derives from the **ground-track**
velocity ($v_g = v\,R/(R+h)$, see `theory/geometry.md` §4) times the magnification
$f/R_s$ — using orbital $v$ instead of $v_g$ inflates smear by $h/R$ (+7.8% at 500 km).

**Assumptions & validity.** Jitter Gaussian form requires jitter frequency ≫ $1/t_{int}$;
comparable-period motion is neither pure jitter nor pure smear. A $d/\sqrt{12}$
"equivalent Gaussian" for smear is a second-moment match, not the correct MTF.

**Pitfalls.** The jitter exponent is $2\pi^2\sigma^2\nu^2$ exactly (equivalently
$e^{-(2\pi\sigma\nu)^2/2}$); σ vs FWHM ($\times 2.3548$); a jitter MTF with a zero
crossing indicates a wrongly applied sinc model.

**Numeric anchors.** $\sigma = 0.25\,p$ at Nyquist: $e^{-\pi^2/32} = 0.734603$;
$d = 0.5\,p$ at Nyquist: $\sin(\pi/4)/(\pi/4) = 0.900316$.

**In RADIANT.** `platform/jitter.py::jitter_mtf`, `platform/smear.py::smear_mtf_1d`
(kernels via `platform/stage.py`, EE_box computed there from the fully degraded PSF per
Rule 9) · anchored by `platform/tests/test_jitter.py`, `test_smear.py`,
`test_stage_mtf_term.py`. **References.** [Holst 2008].

---

## 7. Atmospheric turbulence

**Equations.** Fried parameter $r_0 \propto \lambda^{6/5}$ (so
$r_0(\lambda_2) = r_0(\lambda_1)(\lambda_2/\lambda_1)^{6/5}$); long-exposure Kolmogorov
MTF in angular frequency $f_a$ [cy/rad]:

$$\mathrm{MTF}_{LE}(f_a) = \exp\!\left[-3.44\left(\frac{\lambda f_a}{r_0}\right)^{5/3}\right].$$

The 3.44 is half the structure-function constant 6.88. Turbulence is the one contributor
legitimately multiplied into the budget without pupil-level treatment: in the
long-exposure ensemble average the atmosphere is statistically independent of the pupil.
The PSF path receives the matching kernel (`platform/turbulence_kernel.py`).

**Assumptions & validity.** Kolmogorov spectrum (infinite outer scale), weak fluctuations,
full tilt averaging (long exposure). Short-exposure (tilt-removed) imaging needs Fried's
corrected form — not the shipped default.

**Pitfalls.** Quoting $r_0$ at 0.5 µm and using it unscaled in the IR (at 4 µm,
$r_0$ is 12× larger); 3.44 vs 6.88; gating on platform type instead of $r_0 > 0$ (RADIANT
gates on the parameter `atmosphere.r0_m`, and the MTF term is written by
**PerformanceStage**, not AtmosphereStage — the atmosphere stage publishes `r0_m` only).

**Numeric anchors.** $\mathrm{MTF}_{LE} = 0.338398$ at $\lambda f_a/r_0 = 0.5$;
$r_0 = 0.10$ m @ 0.5 µm → 1.21257 m @ 4 µm.

**In RADIANT.** `atmosphere/turbulence.py::turbulence_mtf` (evaluated via
`performance/turbulence_mtf_term.py` and `performance/stage.py`),
`platform/turbulence_kernel.py` (PSF path) · anchored by
`atmosphere/tests/test_turbulence.py`, `performance/tests/test_turbulence_mtf_term.py`,
`platform/tests/test_turbulence_kernel.py`. **References.** [Fried 1966].

---

## 8. TDI mis-registration — the one MTF-only term

**Equation.** Cross-track drift angle $\theta$ over $N$ TDI stages displaces the $N$
summed samples by $d = p\tan\theta$ each; averaging $N$ displaced copies gives the
Dirichlet kernel, which for sub-pixel per-stage drift reduces to a sinc in the **total**
drift $Np\theta$:

$$\mathrm{MTF}_{TDI}(\nu) \approx \left|\frac{\sin(\pi\nu N p\theta)}{\pi\nu N p\theta}\right|.$$

This is a readout-timing/registration effect on the time-aggregated image — there is no
instantaneous spatial kernel, so it enters **only** the MTF product and is excluded from
the Rule-4 consistency comparison.

**Pitfalls.** Tolerancing θ without N (degradation scales with total drift, so the θ
tolerance tightens as N grows); the discrete Dirichlet form exceeds the sinc form by up to
~0.6% at small N.

**Numeric anchor.** Total drift $0.5\,p$ at Nyquist, $N=16$: 0.9007 (Dirichlet) vs
0.900316 (sinc).

**In RADIANT.** `readout/tdi_mtf.py::tdi_misalign_mtf_1d` (parameter
`readout.tdi_misalign_pixels`); the analogous electronics term
`readout/electronics_mtf.py::electronics_mtf` · anchored by
`readout/tests/test_tdi.py`, `test_electronics_mtf.py`, and exclusion pinned in
`performance/tests/test_consistency_check.py`. **References.** [Holst 2008].

---

## 9. Ensquared energy (EE_box)

**Equation.** Fraction of the fully degraded PSF's energy inside the centered $n\times n$
pixel box:

$$EE_{n\times n} = \int_{-np/2}^{np/2}\!\!\int_{-np/2}^{np/2}\mathrm{PSF}(x,y)\,dx\,dy.$$

Computed in `PlatformStage` from the **fully degraded** `EffectivePSF` (jitter, smear,
turbulence included) and applied exactly once, in `SpectralIntegrationStage`, to
point-source and sub-pixel target signals only — never to the background term, never in
the extended regime (Rules 4/9).

**Discretization.** Each PSF cell is weighted by the fraction of its area inside the box
(cell-area-overlap, CU-188) — second-order accurate; the earlier full-weight edge-cell
scheme carried an $O(dx)$ bias (+24% at Q=2 at default sampling) that overstated
point-source SNR.

**Pitfalls.** Ensquared ≠ encircled (a square of side $p$ is not a circle of diameter
$p$ — quoting the 83.8% first-ring figure for a pixel box is a category error); Airy ring
tails decay as $1/u^2$, so truncated normalization biases EE.

**Numeric anchor.** Unaberrated Airy at critical sampling ($Q=2$):
$EE_{1\times1} = 0.177327$ — only ~18% of a point source's energy lands in the center
pixel.

**In RADIANT.** `optics/psf/effective.py::EffectivePSF.ensquared_energy` /
`ensquared_energy_nxn`, wrapped by `optics/ee_box.py` · anchored by
`optics/tests/test_ee_box.py::test_ee_box_airy_q2_anchor` (abs=1e-3 at default sampling).
**References.** [Holst 2008].

---

## 10. Sampling: Nyquist, Q, and folded MTF

**Equations.** $\nu_{Nyq} = 1/(2p)$;

$$Q = \frac{\lambda F_\#}{p},\qquad \frac{\nu_c}{\nu_{Nyq}} = \frac{2}{Q}.$$

- $Q = 2$: **critically sampled** — the optics pass nothing above Nyquist; no aliasing.
- $Q < 2$: undersampled (typical EO design point, chosen for SNR/GSD); the band
  $[\nu_{Nyq}, \nu_c]$ folds.
- $Q > 2$: oversampled.

The folded MTF adds the aliased response back onto the baseband
(`performance/folded_mtf.py`). Sampling on a pitch $p$ replicates the pre-sampling spectrum
at integer multiples of the **sampling** frequency $\nu_s = 1/p = 2\nu_{Nyq}$, so

$$\mathrm{MTF}_{fold}(\nu) = \sum_{k=-N}^{+N} \mathrm{MTF}_{opt}\!\left(\left|\nu + k\,\nu_s\right|\right).$$

At $\nu = \nu_{Nyq}$ the $k = -1$ replica lands back on $\nu_{Nyq}$, so the folded value
there is twice the pre-sampling MTF (alias fraction $\to 1/2$) whenever the higher orders
are negligible — and it is *zero* for optics that cut off below Nyquist, which is the
oversampled sanity check. The alias fraction
$(\mathrm{MTF}_{fold} - \mathrm{MTF}_{opt})/\mathrm{MTF}_{fold}$ is evaluated only where
$\mathrm{MTF}_{fold} > 10^{-9}$ of its DC value; below that floor both terms are
round-off, and the reported fraction is exactly zero — an oversampled design has no
aliased energy (CU-315). GIQE consumes RER from the PSF path and the MTF budget per
`theory/performance_metrics.md`.

**Pitfalls.** "Q = 1 critical" is a different (sampling-frequency) convention — RADIANT's
statement is $\nu_c/\nu_{Nyq} = 2/Q$, critical at $Q=2$; sampling frequency $1/p$ vs
Nyquist $1/(2p)$ — replicating the spectrum at $\nu_{Nyq}$ instead of $\nu_s$ puts the
$k=-1$ copy on DC and adds $\mathrm{MTF}(0)=1$ to every system (CU-209); ground-projecting
Nyquist twice.

**Numeric anchor.** $\lambda = 0.55$ µm, $F_\# = 4$, $p = 10$ µm: $Q = 0.22$ —
$\nu_c/\nu_{Nyq} = 9.1$, heavily aliased, the classic high-resolution VNIR design point.

**In RADIANT.** `performance/qsample.py::compute_q`, `performance/sampling_regime.py`,
`performance/folded_mtf.py::compute_folded_mtf`, `optics/sampling.py::compute_sampling` ·
anchored by `performance/tests/test_qsample.py`, `test_sampling_regime.py`,
`test_folded_mtf.py` (Gaussian-sum analytic anchors). **References.** [Holst 2008],
[Boreman 2001].

---

## 11. RER and the edge response

**Equation.** The edge response function is the cumulative integral of the line spread
function (itself the 1-D projection of the PSF); the relative edge response per axis is

$$\mathrm{RER}_x = \mathrm{ERF}_x(+p/2) - \mathrm{ERF}_x(-p/2),$$

and the reported scalar is the **geometric mean** $\sqrt{\mathrm{RER}_x\,\mathrm{RER}_y}$
(GIQE-5 usage). All of LSF/ERF/RER derive from the same `EffectivePSF` (Rule 4).

**In RADIANT.** `optics/psf/effective.py::EffectivePSF.rer` (with `lsf`/`erf`) · anchored
by `optics/tests/test_psf.py`; consumed by `performance/giqe.py`.
**References.** [Harrington 2015].

---

## Scope and deferred effects

No ghost images, no measured-BSDF scatter beyond the TIS/halo model
(`optics/scatter.py`, `optics/stray_light.py` — see `RADIANT_Optics.md`), no chromatic
aberration model, no short-exposure turbulence. See
`docs/architecture/RADIANT_Scope_Decisions.md`.
