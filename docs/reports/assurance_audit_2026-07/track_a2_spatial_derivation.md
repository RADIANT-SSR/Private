# Track A2 — Blind Re-Derivation: Spatial / PSF / MTF

Status: Complete (derivation phase)
Produced by: blind-derivation agent (no access to src/ or docs/), 2026-07-22.
Comparison against implementation: see findings.md.

---

# Blind Physics Re-Derivation — RADIANT Spatial/MTF Audit

**Status:** Independent derivation. No RADIANT source or docs were read. All results derived from first principles and standard literature (Goodman, *Introduction to Fourier Optics*; Gaskill, *Linear Systems, Fourier Transforms, and Optics*; Holst, *Electro-Optical Imaging System Performance*; Fried 1966 JOSA 56:1372; Boreman, *Modulation Transfer Function in Optical and Electro-Optical Systems*). Numerics computed with scipy to ≥6 significant figures.

**Conventions used throughout:** λ in µm (converted to mm or m explicitly where noted), angles in rad, focal-plane lengths in m (pixel-relative quantities stated in units of pitch *p*). Spatial frequency ν in cycles/mm at the focal plane unless explicitly normalized; normalized frequency ν̃ = ν/ν_c. **sinc convention: I write the argument explicitly** — `sin(πwν)/(πwν)` — and never rely on a bare "sinc(x)" whose π-inclusion is ambiguous (NumPy `sinc(x)` = sin(πx)/(πx); many optics texts define sinc(x) = sin(x)/x).

---

## 1. Diffraction-limited PSF of a circular aperture (Airy)

**(a) Governing equation.** For an unaberrated, uniformly illuminated circular pupil of diameter D [m], focal length f [m], working at wavelength λ [m], the incoherent (irradiance) PSF at focal-plane radius r [m] is

I(r) = I₀ [2 J₁(v)/v]², v = πr/(λF#), F# = f/D

- J₁ — Bessel function of the first kind, order 1 (dimensionless)
- v — dimensionless radial coordinate; r [m], λ [m], F# dimensionless
- I₀ — on-axis peak irradiance [W/m²]

**First zero:** at the first zero of J₁, v₁ = 3.8317060, i.e.

r₁ = (v₁/π)·λF# = 1.2196699·λF# (≈ 1.22 λF#)

**Encircled energy** inside radius r (Rayleigh's classical result):

EE(v) = 1 − J₀²(v) − J₁²(v)

At the first dark ring EE = 0.837785 (83.8%); second ring 0.909931; third 0.937647.

**With central obscuration ratio ε = D_obs/D** (annular pupil), the PSF is the difference of two scaled Airy amplitudes, normalized to unit transmitted energy fraction:

I(v) = I₀/(1−ε²)² · [2J₁(v)/v − ε²·2J₁(εv)/(εv)]²

Effects: core narrows (first zero moves inward), energy is thrown from the core into the rings.

**(b) Assumptions / validity.** Scalar diffraction, Fraunhofer regime (image at focus or far field), uniform pupil amplitude, unpolarized/incoherent imaging, paraxial (F# ≳ 2 for the scalar approximation to hold well; for F# < 1.5 vector effects matter), monochromatic (polychromatic PSF is the spectrally weighted sum).

**(c) Pitfalls.**
- Using 1.22 instead of the exact 1.2196699 — fine for display, wrong for a tight golden baseline (0.03% difference).
- Confusing *amplitude* PSF (2J₁/v) with *irradiance* PSF (its square).
- For the obscured form, forgetting the 1/(1−ε²)² renormalization, or normalizing the peak instead of the energy (peak Strehl of an annular pupil is (1−ε²)², not 1).
- EE formula 1 − J₀² − J₁² is valid **only** for the unobscured pupil; annular EE must be integrated numerically.

**(d) Spot checks** (λ = 4 µm, F# = 4):
- First-zero radius: exact r₁ = (3.8317060/π)·4 µm·4 = **19.5147 µm** (1.22 approximation gives 19.5200 µm).
- EE at first dark ring: **0.837785**.
- Obscured ε = 0.3: first zero at v = 3.50136, i.e. radius shrinks to **0.913789×** the unobscured value (17.8322 µm at λ=4 µm, F#=4).

---

## 2. Diffraction-limited incoherent MTF of a circular pupil

**(a) Governing equation.** The incoherent OTF is the normalized autocorrelation of the pupil function. For a clear circular pupil this evaluates analytically (the "two overlapping circles" lens area) to

MTF(ν̃) = (2/π)[arccos(ν̃) − ν̃√(1−ν̃²)], 0 ≤ ν̃ ≤ 1; MTF = 0, ν̃ > 1

with ν̃ = ν/ν_c and cutoff

ν_c = 1/(λF#) [cy/mm when λ is in mm] = D/(λf)

**(b) Assumptions.** Incoherent illumination (coherent cutoff is ν_c/2 — a classic factor-of-two trap), aberration-free, monochromatic, uniform pupil transmission. Polychromatic MTF is the spectrally weighted average of monochromatic MTFs, each with its own cutoff.

**Annular pupil (obscuration ε):** compute the OTF as the exact autocorrelation of the annulus (overlap area of two annuli at center separation 2ν̃ pupil-radii, normalized by the annulus area π(1−ε²)). Closed forms exist (piecewise, e.g. O'Neill 1956) but the robust route is direct numerical pupil autocorrelation. Qualitative behavior: **same cutoff ν_c** (set by the outer diameter), **depressed mid-frequencies** (energy removed from small shear overlaps), **boosted response near cutoff relative to the clear aperture** (the outer annulus dominates large shears). Numeric (ε = 0.3): MTF/MTF_clear = 0.782 at 0.3ν_c (dip), but 1.099 at 0.8–0.9ν_c (boost).

**(c) Pitfalls.**
- Clamping: arccos requires ν̃ ∈ [0,1]; must return exactly 0 above cutoff, not NaN.
- λ-unit slip in ν_c: with λ = 4 µm = 4×10⁻³ mm, ν_c = 1/(4×10⁻³·4) = 62.5 cy/mm. Using λ in µm silently gives cy/µm.
- Coherent vs incoherent cutoff (factor 2).
- Treating the obscured MTF as clear-MTF × (some scalar) — the annular OTF is not a separable correction; it must come from the annular-pupil autocorrelation.

**(d) Spot checks.**
- **Anchor:** MTF(0.5ν_c) = (2/π)(π/3 − √3/4) = **0.391002** (numerical pupil-autocorrelation reproduces this to 2×10⁻⁷ on a 4501² grid).
- MTF(0.25ν_c) = **0.685038**; MTF(0.75ν_c) = **0.144294**.
- ν_c(λ=4 µm, F#=4) = **62.5000 cy/mm**; normalized, ν̃_c = 1 by definition.
- Annular ε = 0.3 at 0.5ν_c: **0.337079** (vs 0.391002 clear).

---

## 3. Detector footprint (aperture) MTF

**(a) Governing equation.** A photosensitive aperture of width w [mm] performs a spatial average — convolution with rect(x/w) — whose transfer function is

MTF_det(ν) = |sin(πwν)/(πwν)|

- w — active aperture width [mm]; ν — [cy/mm]. First zero at ν = 1/w.
- **Fill factor:** sampling pitch p sets Nyquist (ν_Nyq = 1/(2p)); the MTF width is set by the **active aperture w**, not the pitch. For 100% fill factor in that dimension, w = p. For linear fill fraction w/p < 1, MTF_det is *wider* (less blur) but aliasing worsens because sampling is unchanged.

**(b) Assumptions.** Uniform responsivity across the aperture (a rect); rectangular aperture separable in x, y. Non-uniform intra-pixel response (real diffusion-rounded apertures) replaces the sinc with the FT of the actual response map. This term is the *pre-sampling* aperture MTF — sampling/aliasing is a separate phenomenon, not an MTF multiplier.

**(c) Pitfalls (the classic one).**
- **sinc convention:** here sinc is written explicitly as sin(πwν)/(πwν). NumPy's `np.sinc(x)` already includes π (`sin(πx)/(πx)`), so the correct NumPy call is `np.sinc(w*nu)`. Writing `np.sinc(np.pi*w*nu)` double-counts π — first zero lands at ν = 1/(πw) instead of 1/w, a factor-π error.
- Using pitch p instead of aperture w when fill factor < 100%.
- Dropping the absolute value: beyond ν = 1/w the sinc goes negative (contrast reversal); MTF is the modulus, but if the term feeds a signed OTF product, keep the sign consistently instead.

**(d) Spot checks** (w = p, i.e. 100% fill):
- **Anchor:** at Nyquist ν = 1/(2w): sin(π/2)/(π/2) = 2/π = **0.636620**. Confirmed.
- First zero: sin(πwν)/(πwν) at ν = 1/w = **0** (numerically 3.9×10⁻¹⁷). Note 1/w = 2ν_Nyq for 100% fill.
- 50% linear fill (w = p/2) at ν_Nyq = 1/(2p): argument πwν = π/4 → sin(π/4)/(π/4) = **0.900316**.

---

## 4. Jitter MTF (random line-of-sight motion)

**(a) Governing equation.** Zero-mean Gaussian random image displacement with RMS σ [mm at the focal plane] — many independent motion cycles within t_int — blurs the image by convolution with a Gaussian of standard deviation σ; its transfer function is

MTF_jit(ν) = exp(−2π²σ²ν²)

- σ — RMS jitter displacement at the focal plane [mm]; if jitter is specified as an angle σ_θ [rad], then σ = σ_θ·f with f the focal length [mm]. ν in cy/mm. (Equivalently work in angular units: σ_θ [rad] with ν in cy/rad.)
- Derivation: FT of a Gaussian pdf N(0,σ): exp(−2π²σ²ν²) — no modulus needed, always positive.

**(b) Assumptions.** Gaussian displacement statistics; jitter frequency ≫ 1/t_int (motion fully averages within one integration — the "high-frequency jitter" regime, Holst); isotropic σ or per-axis σ_x, σ_y applied separably. For jitter periods comparable to t_int the Gaussian form fails and the blur depends on the actual phase/PSD (crossover regime).

**(c) Pitfalls (the factor-2π² trap).**
- The exponent is **2π²σ²ν²**, not 2πσ²ν² and not (2πσν)²/2 written wrongly — note exp(−(2πσν)²/2) = exp(−2π²σ²ν²) is the *same* thing; the error is writing exp(−2π(σν)²) (missing a π) or exp(−4π²σ²ν²) (dropping the ½).
- **σ vs FWHM:** FWHM = 2√(2 ln 2)·σ = 2.35482σ. Feeding a FWHM where σ is expected inflates the blur by 2.35².
- Units: σ in mm with ν in cy/mm (or σ in pixels with ν in cy/pixel) — mixing angular σ with focal-plane ν without the ×f conversion is a silent error.

**(d) Spot checks** (pixel-unit form: σ in pixels, ν_Nyq = 0.5 cy/pixel):
- **Anchor:** σ = 0.25 p at Nyquist: exp(−2π²·0.25²·0.5²) = exp(−π²/32) = **0.734603**.
- σ = 0.1 p at Nyquist: exp(−2π²·0.01·0.25) = **0.951850**.
- Sanity: MTF(0) = 1 exactly; Gaussian never reaches zero (no cutoff) — a jitter MTF with a zero crossing indicates a wrong (sinc-type) model.

---

## 5. Linear smear MTF (constant-rate image motion)

**(a) Governing equation.** Uniform image motion at focal-plane velocity v_image [mm/s] during integration time t_int [s] convolves the image with rect(x/d), d = v_image·t_int [mm]:

MTF_smear(ν) = |sin(πdν)/(πdν)|, d = v_image·t_int

First zero at ν = 1/d. Applies along the motion direction only; unity in the orthogonal direction.

**(b) Assumptions.** Constant velocity during t_int (uniform exposure weighting → rect kernel; a shaped exposure/TDI weighting changes the kernel and hence the transfer function); motion direction fixed; d ≪ scene extent. For a scanning system with residual scan-rate error, d is the *uncompensated* motion.

**(c) Pitfalls.**
- Identical sinc-convention trap as §3 (π placement).
- Confusing smear (deterministic, sinc) with jitter (random, Gaussian): a σ = d/√12 "equivalent Gaussian" is only a second-moment match, not the correct MTF.
- Forgetting |·| past the first zero.
- Using ground velocity instead of image velocity (missing the f/H image-scale factor).

**(d) Spot checks** (pixel units, ν_Nyq = 0.5 cy/pixel):
- **Anchor:** d = 0.5 p at Nyquist: argument π·0.5·0.5 = π/4 → sin(π/4)/(π/4) = **0.900316**.
- d = 1.0 p at Nyquist: sin(π/2)/(π/2) = 2/π = **0.636620** (identical to the 100%-fill detector MTF at Nyquist — same rect width, as expected).
- MTF(0) = 1 for any d (limit handled analytically, not by 0/0).

---

## 6. Kolmogorov turbulence — Fried parameter and atmospheric MTF

**(a) Governing equations.** The Fried parameter r₀ [m] is the aperture diameter over which the wavefront phase variance from Kolmogorov turbulence is ≈ 1 rad² (κ = 6.88 convention: D_φ(r₀) = 6.88 rad²). From the path integral of the structure constant C_n²(z) [m^(−2/3)]:

r₀ = [0.423 k² secζ ∫C_n²(z)dz]^(−3/5), k = 2π/λ

Since r₀ ∝ k^(−6/5): **r₀ ∝ λ^(6/5)** (ζ = zenith angle).

**Long-exposure atmospheric MTF**, in angular spatial frequency f [cy/rad]:

MTF_LE(f) = exp[−3.44(λf/r₀)^(5/3)]

(3.44 = 6.88/2; λf is dimensionless when λ [m], f [cy/rad] — strictly λf has units of m·cy/rad interpreted as the pupil-plane separation λf [m] over r₀ [m]). To use focal-plane ν [cy/mm]: f = ν·f_len with f_len in mm.

**Short-exposure (tilt-removed) correction** (Fried 1966):

MTF_SE(f) = exp[−3.44(λf/r₀)^(5/3)·(1 − α(λf/D)^(1/3))]

α = 1 (near field) or α = 1/2 (far field); D = aperture diameter [m]. Removing random tilt (the dominant Zernike term) restores high-frequency response for a single short frame.

**(b) Assumptions.** Kolmogorov spectrum (infinite outer scale L₀, zero inner scale — finite L₀ softens low-frequency loss); weak-fluctuation regime for the phase-structure-function derivation (scintillation excluded); long exposure = full ensemble average over tilt; system MTF = MTF_atm × MTF_optics is valid because atmosphere and pupil are statistically independent (turbulence is the one contributor legitimately multiplied without pupil-level treatment, in the long-exposure ensemble-average sense).

**(c) Pitfalls.**
- **r₀ wavelength scaling:** r₀(λ₂) = r₀(λ₁)·(λ₂/λ₁)^(6/5) — quoting r₀ at 0.5 µm and using it unscaled in the MWIR is a large error (see spot check). Net exponent: turbulence blur *angle* λ/r₀ ∝ λ^(−1/5) — weakly better at long wavelengths.
- 3.44 vs 6.88: 6.88 belongs to the phase structure function D_φ(r) = 6.88(r/r₀)^(5/3); the MTF exponent is −½D_φ → 3.44.
- Applying the short-exposure form to a staring ensemble-averaged product, or the long-exposure form to a single fast frame.
- The SE bracket can go negative near λf/D → 1 for α = 1 (unphysical MTF > 1); clamp the correction to the valid regime.

**(d) Spot checks.**
- λf/r₀ = 0.5: MTF_LE = exp(−3.44·0.5^(5/3)) = **0.338398**.
- r₀ scaling: r₀ = 0.10 m at λ = 0.5 µm → r₀(4 µm) = 0.10·(8)^(6/5) = **1.21257 m**.
- Seeing angle λ/r₀ at 0.5 µm, r₀ = 0.1 m: **5.00000 µrad** (≈ 1.03 arcsec).

---

## 7. Zernike defocus, P-V vs RMS, Maréchal Strehl

**(a) Governing equations.** Noll-indexed Zernike defocus (Z₄, n=2, m=0), orthonormal on the unit disk:

Z₄(ρ) = √3(2ρ² − 1), 0 ≤ ρ ≤ 1

so a wavefront W(ρ) = a₄·Z₄ has **RMS OPD σ = a₄** (verified numerically: RMS of √3(2ρ²−1) over the unit disk = 1.000000). The function (2ρ²−1) spans [−1, +1] → P-V of the Z₄ mode is 2√3·a₄:

P-V = 2√3·σ = 3.46410·σ

Equivalently, for classical defocus W = W₀₂₀ρ² (Seidel form), P-V = W₀₂₀ and σ = W₀₂₀/(2√3) after piston removal — same 2√3 factor.

**Maréchal approximation** for Strehl ratio from RMS OPD σ_OPD [same units as λ]:

S ≈ exp[−(2π·σ_OPD/λ)²]

(the exponential "extended Maréchal"; the original quadratic form is S ≈ 1 − (2πσ/λ)² ≈ same to second order).

**(b) Assumptions.** Small aberration: reliable for σ ≲ λ/10 (S ≳ 0.67); degrades badly beyond σ ≈ λ/7. Circular unobscured pupil for the Z₄ normalization (annular pupils need annular Zernikes — the 2√3 factor changes). σ is OPD RMS, not phase RMS (phase σ_φ = 2πσ_OPD/λ, giving S ≈ exp(−σ_φ²)).

**(c) Pitfalls.**
- **2√3 factor direction:** P-V = 2√3·RMS for *defocus only*. Each aberration has its own factor; applying 2√3 (≈3.46) or the flat-window √12 to arbitrary aberrations is wrong.
- Mixing OPD in waves vs radians in the Maréchal exponent (factor (2π)² ≈ 39.5).
- Zernike normalization conventions: Noll's √3 prefactor makes coefficient = RMS; the "Born & Wolf/Wyant" convention omits it (coefficient = half the P-V for defocus). Mixing conventions gives √3-type errors in σ.
- The Maréchal Strehl is a *scalar diagnostic*; it does not license reconstructing the PSF or MTF from σ alone (see §10).

**(d) Spot checks.**
- σ = λ/14 (Maréchal criterion): S = exp(−(2π/14)²) = **0.817569** (the classic ≈0.8 "diffraction-limited" threshold).
- σ = λ/20: S = **0.906018**.
- Quarter-wave P-V defocus (Rayleigh criterion): σ = (λ/4)/(2√3) = 0.0721688λ → S = exp(−(2π·0.0721688)²) = **0.814145** — consistent with the classical "λ/4 P-V ↔ ~0.8 Strehl" statement.

---

## 8. Ensquared energy of the Airy pattern; Q and Nyquist

**(a) Definitions and governing equation.** Sampling ratio:

Q ≡ λF#/p, ν_Nyq = 1/(2p) [cy/mm], and f_cutoff/ν_Nyq = 2/Q

Q = 2 is critical sampling: ν_Nyq = ν_c and the optical cutoff is exactly Nyquist (no aliasing of the diffraction-limited image). Ensquared (boxed) energy in a centered square of side = pixel pitch p:

EE_□(p) = ∫∫_{-p/2}^{p/2} I_Airy(x,y) dx dy, I_Airy = π/(4(λF#)²)·[2J₁(πu)/(πu)]², u = √(x²+y²)/(λF#)

normalized so ∫∫ I dA = 1 over the plane (radial normalization check integrated to u = 200: 0.998988 — remainder is the slowly converging ring tail; the dblquad below uses the exact analytic normalization π/4).

**(b) Assumptions.** Unaberrated, unobscured pupil; PSF centered on the box (worst-case/best-case phasing between PSF and pixel grid shifts EE — a real system averages over sub-pixel phase); no detector diffusion (this is the *optics-only* EE; the system ensquared energy convolves in detector kernels first).

**(c) Pitfalls.**
- **Ensquared vs encircled:** EE in a square of side p ≠ EE in a circle of diameter p. Quoting Rayleigh's 83.8% (first *ring*, radius 1.22λF#) for a pixel box is a category error.
- Airy tails: truncating the numerical integration domain too early biases the normalization; ring energy decays only as 1/u², so either normalize analytically or integrate very far out.
- Q convention: state it. Here Q = λF#/p with ν_c = ν_Nyq exactly at Q = 2.
- Half-width p/2 vs full-width p in the integration limits (factor-4 area error).

**(d) Spot checks** (adaptive 2-D quadrature, abs err < 10⁻¹³):
- **Anchor, Q = 2** (box side p = λF#/2, half-width 0.25λF#): EE_□ = **0.177327** — only ~17.7% of a point source's energy lands in the center pixel at critical sampling.
- Q = 1 (p = λF#): EE_□ = **0.528891**.
- Q = 0.5 (p = 2λF#): EE_□ = **0.833845**.
- Concrete units: λ = 4 µm, F# = 4, Q = 2 → p = 8.00 µm, ν_Nyq = **62.5000 cy/mm** = ν_c ✓.

---

## 9. TDI mis-registration MTF (drift angle θ over N stages)

**(a) Governing equation.** If the image velocity vector is misaligned by drift angle θ [rad] from the TDI axis, the image walks cross-track by δ = p·tanθ ≈ p·θ per stage; the N summed samples are displaced copies at spacing d = pθ, total drift N·p·θ. The transfer function of averaging N equally spaced, equally weighted displaced samples is the Dirichlet kernel:

MTF_TDI(ν) = |(1/N)·Σ_{k=0}^{N−1} e^{−i2πνkd}| = |sin(πνNd)/(N·sin(πνd))|, d = p·tanθ

For νd ≪ 1 (small per-stage drift) this reduces to the **sinc-type form in the total drift** D_tot = Npθ:

MTF_TDI(ν) ≈ |sin(πνNpθ)/(πνNpθ)|

Applied in the cross-track direction. (An along-track *rate* mismatch Δv/v produces the analogous along-track term with per-stage displacement d = p·Δv/v; same mathematics.)

**(b) Assumptions.** Equal-weight, equally spaced stage contributions (uniform TDI gain); drift constant over the N-stage transit; per-stage smear during one clock period is booked separately (in the §5 smear term) — this term captures only the *stage-to-stage registration error*. Note this is a **readout-timing/registration effect with no single-frame spatial kernel** in the instantaneous PSF; it appears in the time-aggregated image formation.

**(c) Pitfalls.**
- Using θ alone without N: the degradation scales with **total** drift Npθ; a tolerance on θ must tighten as N grows.
- Discrete (Dirichlet) vs continuous (sinc): the sinc form slightly *underestimates* MTF for small N; for N ≳ 16 they agree to <0.1% at Nyquist for sub-pixel total drift.
- Same π-in-sinc convention trap as §3/§5.
- The Dirichlet form has grating-lobe maxima at νd = integer — a numerical hazard (0/0) if evaluated blindly.

**(d) Spot checks** (ν = ν_Nyq = 0.5 cy/pixel):
- N = 16, total drift 0.5 p (d = p/32): discrete = **0.900678**; sinc(π·0.5·0.5) approx = **0.900316** (0.04% apart).
- N = 16, total drift 1.0 p: discrete = **0.637644**; sinc approx = 2/π = **0.636620**.
- N = 4, total drift 0.5 p: discrete = **0.906127** vs sinc **0.900316** — the small-N case where the discrete form is measurably higher (0.64%).

---

## 10. Consistency identity — FT{PSF} = MTF product; why MTF_diff × MTF_aberr is wrong

**(a) Governing identities.** Let P(ξ,η) = A·exp[i·2πW/λ] be the complex pupil (A = amplitude transmission; W = wavefront OPD). For incoherent imaging:

1. Amplitude PSF h = FT{P} (Fraunhofer);
2. Irradiance PSF = |h|² = |FT{P}|²;
3. OTF(ν) = FT{PSF}/FT{PSF}|₀ = (P ⋆ P)(λfν)/(P ⋆ P)(0) — the **normalized autocorrelation of the complex pupil**;
4. MTF = |OTF|.

"FT of the PSF" and "pupil autocorrelation" are *the same object computed two ways* — this is the consistency invariant. Legitimate MTF *products* arise only from genuinely cascaded, statistically independent blur processes, each of which convolves the image plane: PSF_sys = PSF_optics ∗ k_det ∗ k_jitter ∗ k_smear ∗ … ⟺ OTF_sys = OTF_optics · MTF_det · MTF_jit · MTF_smear · … Convolution in space ↔ multiplication in frequency, term by term, **because each kernel is a separate image-plane convolution**.

**(b) Why MTF_diffraction × MTF_aberration is wrong.** Aberrations are **not** an image-plane convolution applied after diffraction — they are a phase modification *inside the same pupil*. The aberrated OTF integrand contains the phase as a *difference across the shear* under the same integral — it cannot be factored out of the autocorrelation into (clear-aperture autocorrelation) × (aberration-only function). Concrete failure: factored models are frequency-generic, while true aberrated OTFs can go **negative** (contrast reversal — defocus does this) and exhibit aperture-dependent structure; a positive "MTF_aberration" multiplier can never produce a phase-reversed OTF. Equivalently in the spatial domain: there is no PSF_aberration such that PSF_aberrated = PSF_airy ∗ PSF_aberration in general. (Approximate factored "aberration transfer functions" — e.g. Shannon's empirical ATF — are curve fits for budgeting, valid only for small σ and never a substitute for the pupil computation.)

**Correct single-pupil treatment:** build one complex pupil containing aperture shape, obscuration, apodization, and all wavefront terms; compute MTF_optics as its autocorrelation as a **single term**; multiply only the genuinely independent downstream kernels (detector aperture, diffusion, jitter, smear, IPC), plus ensemble-average atmospheric MTF (§6, independent statistics) and any purely non-spatial term (e.g. the §9 TDI registration term, which has no instantaneous kernel and legitimately lives only on the frequency side — it must therefore be excluded from any FT{PSF}-vs-product cross-check).

**(c) Pitfalls.**
- Normalization: OTF(0) must equal 1 — normalize the autocorrelation by the pupil "energy" ∫|P|² (for a phase-only aberration this equals the clear-aperture area; with apodization it does not).
- FFT-based checks: PSF must be sampled at ≥ Nyquist for the *cutoff* (grid spacing ≤ λF#/2), with enough guard band that PSF truncation doesn't ripple the MTF; wrap-around (fftshift) errors masquerade as consistency failures.
- Comparing |FT{PSF}| against a product that includes a frequency-side-only term (TDI-type) — the check must compare like against like.
- Discretization residual: on finite grids the two paths agree only to the sampling error; a consistency tolerance must sit above the measured discretization floor but low enough to catch a missing contributor (a single omitted Nyquist-level term typically shifts the product by ≳5–30% there, vs ~1% discretization floor).

**(d) Spot checks.**
- Pupil-autocorrelation (4501² grid) vs analytic circular MTF at 0.5ν_c: 0.391002 vs 0.391002, difference **1.85×10⁻⁷** — the identity holds numerically.
- Aberration non-factorability witness: the annular case (§2d) shows pupil-structure changes are non-multiplicative (ratio to clear pupil is 0.782 at 0.3ν_c yet 1.099 at 0.8ν_c; no single positive multiplier reproduces a ratio that crosses 1).
- Kernel-cascade closure: detector (w = p) and smear (d = p) rect kernels of equal width give identical Nyquist MTF 2/π = 0.636620 (§3d, §5d) — the transform of the convolved double-rect (triangle) at Nyquist is (2/π)² = 0.405285, the correct cascaded value, illustrating that image-plane convolutions (and only those) multiply.

---

## Summary table — required anchors

| Anchor | Value (≥6 s.f.) |
|---|---|
| Diffraction MTF at 0.5ν_c, clear circular pupil | **0.391002** = (2/π)(π/3 − √3/4) |
| Airy first-zero radius, λ = 4 µm, F# = 4 | **19.5147 µm** exact (1.22 approx: 19.5200 µm) |
| Encircled energy at first dark ring (unobscured) | **0.837785** |
| Detector MTF at Nyquist, 100% fill | **0.636620** = 2/π ✓ (convention sin(πwν)/(πwν) confirmed) |
| Jitter MTF at Nyquist, σ = 0.25 pixel | **0.734603** = exp(−π²/32) |
| Smear MTF at Nyquist, d = 0.5 pixel | **0.900316** = sin(π/4)/(π/4) |
| Ensquared energy, 1-pixel box, Q = 2 | **0.177327** |
| ν_c and ν_Nyq for λ = 4 µm, F# = 4, Q = 2 | both **62.5000 cy/mm** (Q = 2 ⇒ ν_Nyq = ν_c) |

All numerics computed with scipy (Bessel zeros, adaptive quadrature to <10⁻¹² abs error, and a 4501²-point pupil-autocorrelation cross-check); no RADIANT source or documentation was consulted.
