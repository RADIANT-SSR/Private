# Notation and Symbols

This front-matter chapter is the manual's single notation home. Every symbol, canonical
unit, and sign convention used in the chapters that follow is defined here once; the
chapters use the symbols without redefining them. Where a chapter needs a symbol that is
local to one derivation, it introduces it at the point of use and the local meaning wins
for that section only.

Two rules govern everything below:

- **One canonical unit per quantity.** RADIANT computes internally in the units of the
  table in §1 — wavelength in µm, angles in radians, length in meters, time in seconds,
  radiance in W/m²/sr/µm, noise in e- RMS. No module works in any other unit.
- **Conversion happens exactly once, at a boundary.** User input converts on entry;
  external files convert in their reader. A unit conversion inside a physics equation is
  a defect, not a convenience.

---

## 1. Canonical units

| Quantity | Symbol | Canonical unit | Notes |
|---|---|---|---|
| Wavelength | $\lambda$ | µm | The primary spectral variable; arrays ascend in $\lambda$ |
| Wavelength in SI | $\lambda_m$ | m | $\lambda_m = \lambda \cdot 10^{-6}$; used wherever $h$, $c$, or $k_B$ appears |
| Wavenumber | $\nu_{cm}$ | cm⁻¹ | Derived only ($\nu_{cm} = 10^4/\lambda$), never stored as the primary axis |
| Spectral radiance | $L(\lambda)$ | W/m²/sr/µm | MODTRAN's W/cm²/sr/µm converts by $\times 10^4$ in the reader |
| In-band radiance | $L$ | W/m²/sr | $\int L(\lambda)\,d\lambda$ over the bandpass |
| Spectral irradiance | $E(\lambda)$ | W/m²/µm | |
| In-band irradiance | $E$ | W/m² | |
| Spectral intensity | $I(\lambda)$ | W/sr/µm | Point sources |
| Spectral photon radiance | $L_q(\lambda)$ | photon/s/m²/sr/µm | Derived: $L_q = L\lambda_m/(hc)$ |
| Temperature | $T$ | K | Users may enter K, °C, or °F; the affine conversion is applied once at entry |
| Angle (all internal) | $\theta$, $\eta$, $\zeta$, ... | rad | Users enter large angles in degrees, small angles in µrad |
| Length | $D$, $f$, $p$, $R_s$ | m | |
| Time | $t_{int}$, $T_{frame}$ | s | Displays may use ms or µs; storage is seconds |
| Signal | $S$ | e- | Photoelectrons at the sense node, after integration |
| Noise | $\sigma$ | e- RMS | Every noise term, before any DN conversion |
| Digital number | DN | DN | $\mathrm{DN} = S/g$ with $g$ in e-/DN |
| Spatial frequency (focal plane) | $\nu$ | cy/m | Quoted as cy/mm in worked numbers; always labeled |
| Spatial frequency (angular) | $\nu_{ang}$ | cy/mrad | $\nu f$ with $f$ in m is cy/rad, so $\nu_{ang} = \nu f / 1000$; always labeled |
| Transfer function | $\mathrm{MTF}(\nu)$ | dimensionless | $0 \le \mathrm{MTF} \le 1$ |
| Dimensionless fractions | $\varepsilon$, $\rho$, $\tau$, $\mathrm{EE}$ | dimensionless | Stated on the interval $[0, 1]$ where physical |

**Reading the tables that follow.** Units in square brackets are the canonical units above.
A quantity listed as dimensionless still carries a physical range, given where it matters.

---

## 2. Coordinate, attitude, and indexing conventions

| Property | Convention |
|---|---|
| Handedness | Right-handed |
| $+Z$ | Toward the target, along the boresight / optical axis |
| $+X$ | Cross-track (perpendicular to the flight direction) |
| $+Y$ | Along-track (flight direction projected into the image plane) |
| Euler sequence | 3-2-1 (ZYX): yaw about $+Z$, then pitch about the once-rotated $+Y$, then roll about the twice-rotated $+X$ |
| Pixel indexing | $[\mathrm{row}, \mathrm{col}] = [y, x] = [\text{along-track}, \text{cross-track}]$, 0-indexed |

For a nadir-pointing space sensor $+Z$ is nadir; for a ground observer $+Z$ is toward the
target in the sky. The convention holds for every viewing geometry the model supports
without redefinition.

Viewing geometry is referenced to the **target**, not the sensor: the primary angle is the
line-of-sight zenith angle at the target, $\theta_o$, from which the look angle $\eta$ at
the sensor, the Earth central angle $\Lambda$, and the slant range $R_s$ follow.

---

## 3. Radiometric symbols

| Symbol | Meaning | Units |
|---|---|---|
| $B(\lambda, T)$ | Planck blackbody spectral radiance | W/m²/sr/µm |
| $B_q(\lambda, T)$ | Planck photon spectral radiance, $B/E_{ph}$ | photon/s/m²/sr/µm |
| $\partial B/\partial T$ | temperature derivative of Planck radiance (the NEDT kernel) | W/m²/sr/µm/K |
| $\bar{L}$ | band-averaged radiance | W/m²/sr/µm |
| $L_{\mathrm{band}}$ | band-integrated radiance | W/m²/sr |
| $L_{\mathrm{target}}$, $L_{\mathrm{bg}}$ | target and background spectral radiance at the source | W/m²/sr/µm |
| $L_{\mathrm{ap}}$ | at-aperture spectral radiance | W/m²/sr/µm |
| $L_{\mathrm{path}}$ | atmospheric path radiance (scattered plus emitted into the line of sight) | W/m²/sr/µm |
| $L_{\mathrm{sky}}$ | hemispheric downwelling sky radiance | W/m²/sr/µm |
| $E_{\mathrm{sun}}(\lambda)$ | top-of-atmosphere solar spectral irradiance | W/m²/µm |
| $E_{ph}$ | photon energy, $hc/\lambda_m$ | J |
| $\varepsilon(\lambda)$ | emissivity | dimensionless, 0–1 |
| $\rho(\lambda)$ | hemispherical reflectance (albedo) | dimensionless, 0–1 |
| $f_r$ | bidirectional reflectance distribution function (BRDF) | sr⁻¹ |
| $\tau_{\mathrm{atm}}(\lambda)$ | atmospheric transmittance along the slant path | dimensionless, 0–1 |
| $\tau_{\mathrm{opt}}(\lambda)$ | net optical-train transmittance | dimensionless, 0–1 |
| $R(\lambda)$, $T(\lambda)$ | surface reflectance and transmittance of an optical element | dimensionless, 0–1 |
| $\theta_{\mathrm{sun}}$ | solar zenith angle at the surface | rad |
| $x$ | dimensionless Planck argument, $x = hc/(\lambda_m k_B T)$ | dimensionless |
| $f\!f$ | sub-pixel fill fraction, target area over pixel footprint | dimensionless, 0–1 |
| $\mathrm{QE}(\lambda)$ | quantum efficiency | e-/photon |

---

## 4. Geometry and sampling symbols

| Symbol | Meaning | Units |
|---|---|---|
| $R$ | mean Earth radius, 6371.0 km | m |
| $h$ | sensor altitude above the surface | m |
| $R_s$ | slant range, sensor to target | m |
| $\eta$ | look (off-nadir) angle at the sensor | rad |
| $\theta_o$ | line-of-sight zenith angle at the target (equals incidence angle for a surface target) | rad |
| $\varepsilon_{el}$ | grazing/elevation angle at the target, $\pi/2 - \theta_o$ | rad |
| $\Lambda$ | Earth central angle between sub-sensor point and target | rad |
| $\zeta$ | path zenith angle used by the atmosphere models | rad |
| $A_t$ | target projected area | m² |
| $A_{\mathrm{ap}}$ | collecting aperture area | m² |
| $\Omega_{\mathrm{pix}}$ | pixel solid angle, $p_x p_y / f^2$ | sr |
| $\Omega_t$ | target solid angle, $A_t / R_s^2$ | sr |
| $D$ | aperture diameter | m |
| $f$ | focal length | m |
| $F_\#$ | f-number, $f/D$ | dimensionless |
| $p$, $p_x$, $p_y$ | pixel pitch (cross-track, along-track) | m |
| IFOV | instantaneous field of view of one pixel, $p/f$ | rad |
| GSD | ground sample distance | m |
| $v_{img}$ | image-plane motion rate during integration | m/s |
| $\theta$ | target angular extent, $\sqrt{A_t}/R_s$ | rad |

---

## 5. Spatial symbols — PSF and MTF

| Symbol | Meaning | Units |
|---|---|---|
| $P$ | complex pupil function, $P = A\,e^{i 2\pi W/\lambda}$ | dimensionless |
| $W$ | wavefront error across the pupil | m (quoted in waves at a stated $\lambda$) |
| $\sigma_{WFE}$ | RMS wavefront error | waves at the stated reference wavelength |
| $Z_n^m$ | Zernike coefficient (Noll-ordered) | waves RMS |
| PSF | point spread function (the degraded, chain-assembled one) | dimensionless, normalized to unit volume |
| OTF, $\mathrm{MTF}(\nu)$ | optical transfer function and its modulus | dimensionless |
| $\mathrm{MTF}_{sys}(\nu)$ | system MTF, the product of all contributor MTFs | dimensionless |
| $\epsilon$ | central-obscuration ratio, $D_{sec}/D$ | dimensionless, 0–1 |
| $\nu_c$ | optical cutoff frequency, $1/(\lambda F_\#)$ | cy/m |
| $\nu_{Nyq}$ | detector Nyquist frequency, $1/(2p)$ | cy/m |
| $Q$ | sampling parameter, $\lambda F_\# / p$ | dimensionless |
| $S_{tr}$ | Strehl ratio (degraded PSF peak over diffraction-limited peak) | dimensionless, 0–1 |
| $\mathrm{EE}_{\mathrm{box}}$ | ensquared energy inside one pixel, from the degraded PSF | dimensionless, 0–1 |
| RER | relative edge response | dimensionless |
| $\sigma_j$ | RMS angular jitter | rad (entered in µrad) |
| $L_{sm}$ | smear length during integration | m at the focal plane |
| $r_0$ | Fried parameter | m |
| $C_n^2(z)$ | refractive-index structure constant profile | m$^{-2/3}$ |
| $L_d$ | minority-carrier diffusion length | m |
| $\alpha_{IPC}$ | interpixel-capacitance coupling coefficient | dimensionless |

---

## 6. Detector, readout, and noise symbols

| Symbol | Meaning | Units |
|---|---|---|
| $S$, $S_{bg}$ | target and background signal | e- |
| $N_{fw}$ | full-well capacity | e- |
| $g$ | conversion gain, $N_{fw}/2^n$ for an $n$-bit converter | e-/DN |
| $t_{int}$ | integration time | s |
| $T_{frame}$ | frame period | s |
| $J_{dark}$ | dark-current rate | e-/s |
| $E_a$ | dark-current activation energy | eV |
| $\sigma_i$ | one noise term, input-referred to electrons | e- RMS |
| $\sigma_{tot}$ | total noise, the RSS of all contributing terms | e- RMS |
| $\sigma_{read}$ | read noise | e- RMS |
| $\sigma_{kTC}$ | reset (kTC) noise, $\sqrt{k_B T C_{node}}/q$ | e- RMS |
| $\sigma_{ADC}$ | quantization noise, $g/\sqrt{12}$ | e- RMS |
| $k$ | PRNU fraction (multiplicative gain dispersion) — the *residual* after NUC in the noise chapter's $\sigma_{PRNU} = kS$, the *pre-correction* value in the calibration chapter's one-point residual, which is what an offset-only correction leaves intact | dimensionless |
| $\sigma_{DSNU}$ | dark-signal non-uniformity | e- RMS |
| $\sigma_{clutter}$ | scene-induced spatial variance term | e- RMS |
| $N_{TDI}$, $N_{coadd}$, $M_{bin}$ | TDI stages, co-added frames, binned pixels | dimensionless counts |
| $dS/dT$ | signal derivative with respect to scene temperature | e-/K |
| $\oplus$ | root-sum-square combination, $a \oplus b = \sqrt{a^2 + b^2}$ | — |

---

## 7. Calibration symbols

| Symbol | Meaning | Units |
|---|---|---|
| $S_1$, $S_2$, $S_3$ | calibration-point signals (low, mid/high, high) | e- |
| $T_{cal,j}$ | calibration-source temperature at point $j$ | K |
| $f_j$ | calibration-point signal declared as a fraction of the scene signal | dimensionless |
| $S_{ref}$ | full-scale reference for the nonlinearity coefficient | e- |
| $\beta$ | 1σ per-pixel response-nonlinearity fraction at full scale | dimensionless |
| $D_j$ | calibration-point signal derivative, $dS/dT$ at $T_{cal,j}$ | e-/K |
| $\Delta T_{unif}$ | 1σ spatial non-uniformity of the calibration source | K |
| $r_g$ | gain-drift rate since calibration | s⁻¹ |
| $r_o$ | offset-drift rate since calibration | e-/s |
| $t_{cal}$ | elapsed time since the calibration event | s |
| $\sigma_{cal}$ | RSS of the calibration residual noise terms | e- RMS |
| $b_i$, $b_{tot}$ | per-source and total fractional radiometric bias (1σ) | dimensionless |
| $g(T)$ | band-shift log-derivative of the photon-weighted band integral | µm⁻¹ |
| $\delta\lambda$ | band-center (spectral-calibration) uncertainty | µm |
| $f_{fore}$ | photon-weighted fraction of near-field emission from elements ahead of an internal cal shutter | dimensionless, 0–1 |

---

## 8. Physical constants

Every constant is defined once in the code and never re-entered in an equation. The
first six rows are the CODATA 2018 values — the first five exact by the SI definitions,
the second radiation constant derived from them. The last row is not a CODATA quantity:
it is the mean Earth radius, a geodetic convention (see the geometry chapter).

| Constant | Symbol | Value | Units |
|---|---|---|---|
| Speed of light | $c$ | $2.99792458 \times 10^{8}$ | m/s |
| Planck constant | $h$ | $6.62607015 \times 10^{-34}$ | J·s |
| Boltzmann constant | $k_B$ | $1.380649 \times 10^{-23}$ | J/K |
| Stefan-Boltzmann constant | $\sigma_{SB}$ | $5.670374419 \times 10^{-8}$ | W/m²/K⁴ |
| Elementary charge | $q$ | $1.602176634 \times 10^{-19}$ | C |
| Second radiation constant | $c_2 = hc/k_B$ | $1.4387769 \times 10^{-2}$ | m·K |
| Mean Earth radius | $R$ | $6.3710 \times 10^{6}$ | m |

---

## 9. Operators, accents, and reused symbols

| Form | Meaning |
|---|---|
| $\bar{X}$ | band average of $X$ over the bandpass |
| $X_m$ | $X$ expressed in SI meters (used only for $\lambda_m$) |
| $a \oplus b$ | root-sum-square, $\sqrt{a^2 + b^2}$ |
| $\star$ | correlation (used for the pupil autocorrelation) |
| $\mathcal{F}\{\cdot\}$ | Fourier transform |
| $\prod_i$, $\sum_i$ | product and sum over contributor index $i$ |

Four symbols carry more than one meaning across the classical literature this manual
follows. They are disambiguated by chapter, and never used in two senses in one equation:

- $\eta$ is the **look (off-nadir) angle** everywhere except the performance chapter's
  NEI/NEP/D\* section, where the detector literature's $\eta$ (quantum efficiency) and
  $\eta_{sys}$ (end-to-end photon-to-electron efficiency) are kept; that section defines
  both at the point of use.
- $\varepsilon$ is **emissivity** in the radiometric, atmosphere, and calibration
  chapters. The geometry chapter's grazing/elevation angle is written $\varepsilon_{el}$
  here to keep the two apart.
- $\epsilon$ is the **central-obscuration ratio** in the spatial chapter only.
- $\nu$ is **spatial frequency** [cy/m] throughout the spatial and performance chapters;
  spectral wavenumber, which the atmospheric literature also writes $\nu$, appears only
  as $\nu_{cm}$ [cm⁻¹] at MODTRAN interfaces. Angular spatial frequency is written $f_a$
  [cy/rad] in the spatial chapter's turbulence section, where the classical results are
  stated that way.

Two chapters keep a legacy spelling that predates this table and is retained rather than
churned: the radiometric-chain chapter writes the slant range as $R$ (here and in the
geometry chapter it is $R_s$, with $R$ reserved for the mean Earth radius), and it writes
spectral power as $\Phi(\lambda)$ [W/µm].

---

## 10. Acronyms

| Acronym | Expansion |
|---|---|
| ADC | analog-to-digital converter |
| BLIP | background-limited infrared performance |
| BRDF | bidirectional reflectance distribution function |
| CDS | correlated double sampling |
| CSNR | contrast signal-to-noise ratio |
| DN | digital number |
| DROIC | digital readout integrated circuit (photon-counting) |
| DSNU | dark-signal non-uniformity |
| EE | ensquared (or encircled) energy |
| ERF | edge response function |
| FPA | focal plane array |
| FPN | fixed-pattern noise |
| FWHM | full width at half maximum |
| GIQE | General Image Quality Equation |
| GSD | ground sample distance |
| IFOV | instantaneous field of view |
| IPC | interpixel capacitance |
| LOS | line of sight |
| LSF | line spread function |
| MRT | minimum resolvable temperature difference |
| MTF | modulation transfer function |
| NEDL | noise-equivalent differential radiance |
| NEDT | noise-equivalent differential temperature |
| NEI | noise-equivalent irradiance |
| NEP | noise-equivalent power |
| NIIRS | National Imagery Interpretability Rating Scale |
| NUC | non-uniformity correction |
| OTF | optical transfer function |
| PRNU | photo-response non-uniformity |
| PSF | point spread function |
| QE | quantum efficiency |
| RER | relative edge response |
| ROIC | readout integrated circuit |
| RSS | root-sum-square |
| SCNR | signal-to-clutter-plus-noise ratio |
| SNR | signal-to-noise ratio |
| TDI | time delay and integration |
| TOA | top of atmosphere |
| WFE | wavefront error |
