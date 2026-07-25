# Radiometric Signal Chain

*Persona: Dr. Chen (researcher), Mike (detector engineer), Tom (optical designer)*

The radiometry foundations of RADIANT: the governing equations that carry a
photon from source emission to a photoelectron count, each stated with its
derivation, validity limits, classic implementation pitfalls, a pinned numeric
anchor, and the exact place in the code where it lives. This chapter covers
the radiometric quantities themselves; the spatial (PSF/MTF) treatment is in
[Spatial Model](spatial_model.md) and the noise taxonomy is in
[Noise Model](noise_model.md).

Every numeric anchor below was independently re-derived from the physics
literature (no access to RADIANT source) in the 2026-07 assurance audit and
then verified against the implementation — see
`docs/reports/assurance_audit_2026-07/track_a1_radiometry_derivation.md`.

---

## Notation

One symbol table for the whole chapter. RADIANT canonical units throughout:
wavelength in µm, angles in radians, lengths in meters, spectral radiance in
W/m²/sr/µm.

| Symbol | Meaning | Units |
|---|---|---|
| $\lambda$ | wavelength (canonical spectral variable) | µm |
| $\lambda_m$ | wavelength converted to meters, $\lambda_m = \lambda \cdot 10^{-6}$ | m |
| $T$ | absolute temperature | K |
| $B(\lambda, T)$ | Planck blackbody spectral radiance | W/m²/sr/µm |
| $L(\lambda)$ | spectral radiance (general) | W/m²/sr/µm |
| $L_{\mathrm{band}}$ | band-integrated radiance | W/m²/sr |
| $\bar{L}$ | band-averaged radiance | W/m²/sr/µm |
| $E(\lambda)$ | spectral irradiance | W/m²/µm |
| $I(\lambda)$ | spectral intensity (point source) | W/sr/µm |
| $\Phi(\lambda)$ | spectral power (flux) | W/µm |
| $\varepsilon(\lambda)$ | emissivity | dimensionless, 0–1 |
| $\rho(\lambda)$ | hemispherical (Lambertian) reflectance / albedo | dimensionless, 0–1 |
| $\tau$ | transmittance (atmospheric or optical, per context) | dimensionless, 0–1 |
| $f_r$ | bidirectional reflectance distribution function (BRDF) | sr⁻¹ |
| $\theta_{\mathrm{sun}}$ | solar zenith angle at the surface | rad |
| $h, c, k_B$ | Planck constant, speed of light, Boltzmann constant (CODATA 2018) | J·s, m/s, J/K |
| $x$ | dimensionless Planck argument, $x = hc/(\lambda_m k_B T)$ | — |
| $c_2$ | second radiation constant $hc/k_B = 1.4387769 \times 10^{-2}$ m·K | m·K |
| $R$ | slant range, observer to target | m |
| $A_t$ | target projected area | m² |
| $A_{\mathrm{ap}}$ | collecting aperture area | m² |
| $\Omega_{\mathrm{pix}}$ | pixel solid angle, $p_x p_y / f^2$ | sr |
| $\Omega_t$ | target solid angle, $A_t / R^2$ | sr |
| $f\!f$ | sub-pixel fill fraction | dimensionless, 0–1 |
| $\mathrm{QE}(\lambda)$ | quantum efficiency | e⁻/photon |
| $t_{\mathrm{int}}$ | integration time | s |
| $\mathrm{EE}_{\mathrm{box}}$ | ensquared energy in one pixel, from the degraded PSF | dimensionless, 0–1 |

Where a formula needs $\lambda$ in meters (anything with $h$, $c$, $k_B$ in
it), we write $\lambda_m$ explicitly. The µm-to-m bookkeeping is the single
most common bug source in this entire subject; every entry below calls out
where the $10^{-6}$ lives.

---

## The Chain at a Glance

RADIANT models the end-to-end signal chain as nine sequential stages
(geometry-first, per ADR-0006). Each stage is a pure function that transforms
an immutable `ChainState`, adding radiometric frames, noise terms, and MTF
contributions:

```
GeometryStage → SourceStage → AtmosphereStage → OpticsStage → PlatformStage
→ SpectralIntegrationStage → DetectorStage → ReadoutStage → PerformanceStage
```

The final `ChainState` contains everything needed to compute performance
metrics (SNR, NEDT, NIIRS, MTF). The foundations in this chapter are the
radiometric content of that chain: Geometry establishes ranges and angles;
Source builds $L(\lambda)$ from the equations below; Atmosphere applies
$\tau_{\mathrm{atm}}$ and adds path radiance; Optics applies throughput and
finalizes the radiometric regime; SpectralIntegration collapses spectra to
photoelectrons using the photon-conversion entry. A stage-by-stage map is
given in [How the Foundations Feed the Chain](#how-the-foundations-feed-the-chain)
at the end.

---

## Foundations

### Planck Spectral Radiance

**Equation.**

$$B(\lambda, T) = \frac{2 h c^2}{\lambda_m^5} \cdot \frac{1}{e^{x} - 1} \cdot 10^{-6}, \qquad x = \frac{h c}{\lambda_m k_B T}$$

The first factor evaluates in W/m²/sr/m; the trailing $10^{-6}$ is the
Jacobian $d\lambda_m / d\lambda_{\mu m}$ that converts to the canonical
W/m²/sr/µm.

**Symbols.** $\lambda_m$ [m] wavelength in meters; $T$ [K]; $h$ [J·s]; $c$
[m/s]; $k_B$ [J/K]; $x$ dimensionless; output $B$ [W/m²/sr/µm].

**Derivation.** Planck's law follows from Bose–Einstein statistics of photon
modes in a cavity: the mode density per unit volume per unit frequency is
$8\pi\nu^2/c^3$, each mode carries mean energy $h\nu/(e^{h\nu/k_B T} - 1)$,
and converting energy density to radiance (multiply by $c/4\pi$) and changing
variables from $\nu$ to $\lambda$ (Jacobian $c/\lambda^2$) gives the
per-meter form $2hc^2/\lambda_m^5 \cdot (e^x - 1)^{-1}$. A per-µm spectral
interval is $10^{-6}$ of a per-m interval, hence the final factor. The
dimensionless argument can equivalently be written $x = c_2 / (\lambda_m T)$
with the second radiation constant $c_2 = hc/k_B$.

**Assumptions & validity.** Thermal-equilibrium emission into vacuum
(refractive index $n = 1$; in a medium $B$ scales as $n^2$). Unpolarized,
Lambertian (direction-independent) radiance. Valid for all $\lambda, T > 0$.
Numerically, $x \gtrsim 700$ overflows `exp()` in float64; RADIANT truncates
the Wien tail to exactly zero there (the true value is below float64
underflow, so no physics is lost). $T = 0$ returns exactly zero radiance.

**Pitfalls.**

- The per-µm $10^{-6}$ applied zero times or twice — results off by $10^6$
  or $10^{12}$.
- Using $\lambda$ in µm inside $\lambda^5$ without conversion — a $10^{30}$
  scale error partially masked by the $10^{-6}$ Jacobian.
- `exp(x) - 1` instead of `expm1(x)`: catastrophic cancellation for
  $x \ll 1$ (Rayleigh–Jeans regime). RADIANT uses `numpy.expm1`.
- Confusing the radiance constant $c_{1L} = 2hc^2$ with the exitance
  constant $c_1 = 2\pi hc^2$ — a stray factor of $\pi$. Radiance $B$ and
  exitance $M = \pi B$ are different quantities.

**Numeric anchor.** $B(10\ \text{µm}, 300\ \mathrm{K}) = 9.92403333$
W/m²/sr/µm ($x = 4.796$, near the LWIR peak of a 300 K blackbody at
$\lambda_{\max} = 2898\ \text{µm·K} / 300\ \mathrm{K} \approx 9.66$ µm).
Also $B(4\ \text{µm}, 300\ \mathrm{K}) = 0.721976423$ W/m²/sr/µm.

**In RADIANT.** `core/blackbody.py::planck_spectral_radiance` · anchored by
`src/radiant/core/tests/test_blackbody.py::test_planck_radiance_anchor_literals`
(plus `test_stefan_boltzmann_integral`, `test_wien_displacement`, and
`test_independent_formulation_five_points` as independent truth anchors).
Constants come from `core/constants.py` (`two_hc2`, `hc_over_kB`; CODATA 2018).

**References.** [Planck 1901], [Siegel & Howell §1.6], [CODATA 2018].

---

### Temperature Derivative of Planck Radiance — the NEDT Kernel

**Equation.**

$$\frac{\partial B}{\partial T} = B(\lambda, T) \cdot \frac{x}{T} \cdot \frac{e^{x}}{e^{x} - 1} \qquad \left[\text{W/m}^2\text{/sr/µm/K}\right]$$

**Symbols.** As in the Planck entry; output in W/m²/sr/µm/K. The fully
expanded form is $\partial B/\partial T = (2 h^2 c^3 \cdot 10^{-6}) /
(\lambda_m^6 k_B T^2) \cdot e^x / (e^x - 1)^2$.

**Derivation.** Write $B = A / (e^x - 1)$ with $A = 2hc^2/\lambda_m^5$ fixed
in $T$. Since $x = hc/(\lambda_m k_B T)$, $dx/dT = -x/T$. Chain rule:
$dB/dT = A \, e^x (e^x - 1)^{-2} \cdot (x/T) = B \cdot (x/T) \cdot
e^x/(e^x - 1)$. This is the kernel of every NEDT computation: a scene
temperature change $\Delta T$ produces a radiance change $\Delta L \approx
(\partial B/\partial T)\, \Delta T$.

**Assumptions & validity.** The derivative itself is exact — no linearization.
Using it as the NEDT kernel assumes $\Delta T$ small enough that $B$ is
locally linear: excellent for $\Delta T \lesssim$ a few K at terrestrial
temperatures, degrading in the Wien regime where the fractional error of the
linearization grows like $(x/2)(\Delta T / T)$. Undefined at $T = 0$
(RADIANT raises).

**Pitfalls.**

- Dropping the $e^x/(e^x - 1)$ factor (writing $\partial B/\partial T = B
  \cdot x/T$) — a Wien-limit shortcut that is ~0.8 % low at 10 µm/300 K and
  silently regime-dependent.
- Carrying $(e^x - 1)^1$ where the expanded form needs $(e^x - 1)^2$.
- Sign check: $\partial B/\partial T > 0$ for every $\lambda, T$. A negative
  value anywhere is a bug.
- All the per-µm $10^{-6}$ hazards of the Planck entry, now propagating
  straight into NEDT.

A physical sanity check worth internalizing: at 300 K the MWIR derivative is
~5.5× smaller than LWIR in absolute per-µm terms, but its *fractional*
contrast $(\partial B/\partial T)/B$ is larger (4.00 %/K at 4 µm vs 1.61 %/K
at 10 µm) — the classic MWIR-vs-LWIR contrast trade.

**Numeric anchor.** $\partial B/\partial T\,(10\ \text{µm}, 300\ \mathrm{K})
= 0.159971567$ W/m²/sr/µm/K (audit value, verified against central finite
differences to $\leq 3\times 10^{-10}$ relative).

**In RADIANT.** `core/blackbody.py::planck_spectral_radiance_dT` · anchored by
`src/radiant/core/tests/test_blackbody.py::test_planck_dBdT_anchor_literal`
and `test_dBdT_finite_difference`.

**References.** [Planck 1901], [Holst], [CODATA 2018].

---

### Band-Integrated and Band-Averaged Radiance

**Equation.**

$$L_{\mathrm{band}} = \int_{\lambda_1}^{\lambda_2} L(\lambda)\, d\lambda \approx \sum_{i=1}^{N-1} \tfrac{1}{2}\left(L_i + L_{i+1}\right)\left(\lambda_{i+1} - \lambda_i\right) \qquad \left[\text{W/m}^2\text{/sr}\right]$$

$$\bar{L} = \frac{L_{\mathrm{band}}}{\lambda_2 - \lambda_1} \qquad \left[\text{W/m}^2\text{/sr/µm}\right]$$

**Symbols.** $\lambda_1, \lambda_2$ [µm] band edges; $L_i$ [W/m²/sr/µm]
samples on the spectral grid; grid spacing in µm.

**Derivation.** Integrating a per-µm spectral density over a wavelength
interval expressed in µm yields W/m²/sr with *no* extra conversion factor —
the units cancel by construction. The trapezoid rule is the RADIANT quadrature
(via `numpy.trapezoid`); its general form handles non-uniform grids correctly
because the spacing enters per interval. The band average divides by the full
span $\lambda_2 - \lambda_1$; if a relative spectral response $R(\lambda)$ is
involved, the correct band average is instead $\int L R\, d\lambda / \int R\,
d\lambda$.

**Assumptions & validity.** Trapezoid accuracy requires the grid to resolve
the integrand: trivially satisfied for a smooth blackbody (201 points across
a band gives $< 10^{-6}$ relative error in LWIR/MWIR), but for atmospherically
filtered radiance the grid must resolve the $\tau(\lambda)$ line structure or
the result is quadrature-limited, not physics-limited.

**Pitfalls.**

- $\Delta\lambda$ in the wrong units (m or nm instead of µm) — $10^{-6}$ or
  $10^3$ scale errors on the integral.
- Dividing by the sample count $N$ instead of the wavelength span when
  band-averaging.
- Applying the band average *and* multiplying by $\Delta\lambda$ somewhere
  downstream — integrating twice.
- Treating the band as a top-hat when a real spectral response weighting
  exists.
- Coarse-grid bias: even trapezoid on a 5-point grid across 8–12 µm is 0.4 %
  low; a left-Riemann sum is worse.

**Numeric anchor.** $\int_{8}^{12} B(\lambda, 300\ \mathrm{K})\, d\lambda =
38.5004239$ W/m²/sr (adaptive-quadrature truth; band average $9.62510598$
W/m²/sr/µm). Sanity: that is 26.3 % of the total $\sigma T^4/\pi = 146.15$
W/m²/sr, consistent with blackbody band-fraction tables.

**In RADIANT.** `source/converters/invert_band_radiance.py::integrate_planck_over_band`
(general spectral integration happens inline via `numpy.trapezoid` wherever a
stage integrates) · anchored by
`src/radiant/source/tests/test_invert_band_radiance.py::TestForwardIntegralMonotone::test_forward_integral_absolute_anchor`.

**References.** [Siegel & Howell §1.6], [Holst].

---

### Brightness Temperature — Spectral (Monochromatic) Inversion

**Equation.** Given spectral radiance $L$ [W/m²/sr/µm] at wavelength
$\lambda$, the brightness temperature is the closed-form inverse of Planck:

$$T_B = \frac{h c}{\lambda_m k_B} \cdot \frac{1}{\ln\!\left(1 + \dfrac{2 h c^2 \cdot 10^{-6}}{\lambda_m^5 \, L}\right)} \qquad \left[\mathrm{K}\right]$$

**Symbols.** $\lambda_m$ [m]; $L$ [W/m²/sr/µm]; the prefactor
$hc/(\lambda_m k_B) = c_2/\lambda_m$ [K]; the log argument is dimensionless
(both terms in W/m²/sr/µm at that $\lambda$).

**Derivation.** Solve $L = (2hc^2 \cdot 10^{-6}/\lambda_m^5) / (e^x - 1)$
for $x$: $e^x - 1 = 2hc^2 \cdot 10^{-6}/(\lambda_m^5 L)$, so $x = \ln(1 + r)$
with $r$ the radiance ratio, and $T_B = hc/(\lambda_m k_B x)$. Because
$B(\lambda, T)$ is strictly monotonic in $T$ at fixed $\lambda$, the inverse
is unique. For a blackbody, $T_B$ at every wavelength equals the physical
temperature; $\lambda$-dependence of $T_B$ diagnoses a graybody or selective
emitter.

**Assumptions & validity.** Blackbody spectral shape at that wavelength
($\varepsilon = 1$); a graybody's brightness temperature sits *below* its
thermodynamic temperature. Monochromatic: $L$ must be the spectral radiance
at $\lambda$, or a band narrow enough that $L$ is flat across it. Defined for
any $L > 0$.

**Pitfalls.**

- The $10^{-6}$ inside the log: $L$ is per-µm, so the $2hc^2/\lambda_m^5$
  term must be converted to per-µm before forming the ratio — omitting it is
  a $10^6$ error in the log argument.
- Dropping the "$1 +$" (Wien approximation) — fine for $x \gg 1$, but a
  hidden ~1 K bias near the band peak (at 10 µm/300 K, $x \approx 4.8$).
- `log(1 + r)` evaluated naively for tiny $r$ (very hot / Rayleigh–Jeans
  cases) — use `log1p`.
- $\lambda$ in µm inside $\lambda^5$ (same as the Planck entry).

**Numeric anchor.** $T_B(10\ \text{µm},\ L = 9.0\ \text{W/m}^2\text{/sr/µm})
= 294.054730$ K; re-forwarding gives $B(10\ \text{µm}, 294.054730\ \mathrm{K})
= 9.00000000$ W/m²/sr/µm (round-trip exact to 10 digits).

**In RADIANT.** RADIANT does not expose the closed form directly — the S11
user entry point accepts $T_B(\lambda)$ and runs the *forward* direction,
building $L(\lambda) = B(\lambda, T_B(\lambda))$ pointwise:
`source/converters/brightness_temperature.py::brightness_temperature_to_descriptor`
· anchored by
`src/radiant/source/tests/test_brightness_temperature_converter.py::test_L_at_10um_matches_planck_blackbody`
and `test_roundtrip_within_1e_4_kelvin`. The closed-form inverse above is the
theory statement of what that round-trip test verifies.

**References.** [Planck 1901], [NIST ITS-90], [Holst].

---

### Band Radiance Temperature — Band-Integrated Inversion

**Equation.** Given a measured band radiance $L_{\mathrm{meas}}$ [W/m²/sr]
over $[\lambda_1, \lambda_2]$, the band radiance temperature $T_R$ solves

$$F(T_R) \equiv \int_{\lambda_1}^{\lambda_2} B(\lambda, T_R)\, d\lambda - L_{\mathrm{meas}} = 0$$

No closed form exists; solve numerically (RADIANT uses Brent's method on a
bracketing interval).

**Symbols.** $L_{\mathrm{meas}}$ [W/m²/sr]; $T_R$ [K]; band edges in µm.

**Derivation.** Existence and uniqueness follow from monotonicity:
$\partial B/\partial T > 0$ for every $\lambda, T$ (previous entry, strictly
positive), so $F'(T) = \int \partial B/\partial T\, d\lambda > 0$ — $F$ is
strictly increasing. $F(T \to 0^{+}) = -L_{\mathrm{meas}} < 0$ and
$F(T \to \infty) \to +\infty$, so a strictly increasing continuous function
with a sign change has exactly one root. This licenses bracketing solvers
with a guaranteed single solution — which is exactly why RADIANT validates
the bracket before calling Brent.

**Assumptions & validity.** Blackbody spectral *shape* within the band; a
graybody or atmospherically filtered scene yields an *effective* $T_R$, not
the physical temperature. With a spectral response $R(\lambda) \geq 0$ the
same monotonicity argument holds. The quadrature grid used inside the solver
must match the one used to produce $L_{\mathrm{meas}}$, or a quadrature
mismatch masquerades as a temperature bias (a 0.15 % radiance error is
~0.1 K at LWIR).

**Pitfalls.**

- Inverting the *band-averaged* radiance through the *monochromatic* Planck
  at band center — close for narrow bands, a systematic bias for wide bands
  (Planck is nonlinear across the band).
- Solver bracket too narrow (e.g. [200, 400] K fails on hot targets).
  RADIANT brackets [1, 10 000] K and raises an actionable error if
  $L_{\mathrm{meas}}$ falls outside the image of the bracket.
- Comparing per-µm to band-integrated units (W/m²/sr/µm vs W/m²/sr) — a
  $(\lambda_2 - \lambda_1)$ factor error.
- Confusing tolerance on radiance with tolerance on temperature: at 3–5 µm,
  $dL_{\mathrm{band}}/dT \approx 4\,\%/\mathrm{K}$ of $L_{\mathrm{band}}$,
  so a 1 % radiance tolerance is ~0.25 K.

**Numeric anchor.** For 8–12 µm and $L_{\mathrm{meas}} = 30.0$ W/m²/sr:
$T_R = 285.450727$ K (re-forward reproduces 30.0000000 W/m²/sr). The
self-consistency case $L_{\mathrm{meas}} = 38.5004239$ W/m²/sr recovers
exactly 300.000000 K.

**In RADIANT.**
`source/converters/invert_band_radiance.py::invert_band_radiance_to_temperature`
· anchored by
`src/radiant/source/tests/test_invert_band_radiance.py::TestRoundTripAnchors::test_anchor_1_LWIR_300K`
(plus MWIR-500 K and Wien-2000 K anchors). The S12 user entry point that
consumes a supplied $T_R$ is
`source/converters/radiance_temperature.py::radiance_temperature_to_descriptor`,
anchored by
`src/radiant/source/tests/test_radiance_temperature_converter.py::test_roundtrip_within_1e_3_K`.

**References.** [Siegel & Howell §1.6], [Press et al. §9.3] (Brent's method).

---

### Graybody Emission (Scene Targets)

**Equation.**

$$L_{\mathrm{emit}}(\lambda, T) = \varepsilon(\lambda) \cdot B(\lambda, T) \qquad \left[\text{W/m}^2\text{/sr/µm}\right], \qquad 0 \leq \varepsilon \leq 1$$

The complete at-surface leaving radiance in the thermal IR adds the reflected
downwelling term:

$$L_{\mathrm{leave}}(\lambda) = \varepsilon(\lambda)\, B(\lambda, T_{\mathrm{surf}}) + \left[1 - \varepsilon(\lambda)\right] L_{\mathrm{down}}(\lambda)$$

**Symbols.** $\varepsilon(\lambda)$ dimensionless emissivity (scalar graybody
or spectral); $T_{\mathrm{surf}}$ [K]; $L_{\mathrm{down}}$ [W/m²/sr/µm]
downwelling sky radiance.

**Derivation.** Kirchhoff's law in local thermodynamic equilibrium equates
spectral directional absorptance and emissivity, $\alpha(\lambda) =
\varepsilon(\lambda)$. Energy balance for an opaque surface
($\tau = 0$) gives $\rho + \alpha = 1$, hence $\rho = 1 - \varepsilon$: the
emission and sky-reflection terms are complementary. High-$\varepsilon$
surfaces emit; low-$\varepsilon$ surfaces mirror the sky.

For **scene targets and backgrounds**, $\varepsilon$ is a legitimate
*independent* material input — it describes what the material is, and RADIANT
accepts it directly (contrast with optical elements, next entry).

**Assumptions & validity.** Local thermodynamic equilibrium (fails only for
luminescent/lasing media — not passive-EO scenes). Strictly, Kirchhoff holds
per direction: $\varepsilon(\lambda, \theta, \phi) = \alpha(\lambda, \theta,
\phi)$; using a hemispherical $\varepsilon$ for directional radiance assumes
a diffuse emitter (water at grazing angles is the classic violator).
$\varepsilon$ is assumed independent of $T$ over the range of interest.
RADIANT validates $\varepsilon \in [0, 1]$ and refuses to extrapolate a
spectral emissivity table outside its wavelength range.

**Pitfalls.**

- Applying $\rho + \varepsilon = 1$ across bands — pairing a *solar-band*
  $\rho$ with a *thermal-band* $\varepsilon$. Kirchhoff is spectral; visible
  albedo says nothing about 10 µm emissivity.
- Forgetting the reflected-downwelling term: for $\varepsilon = 0.95$ at
  LWIR it is a ~5 % correction, and omitting it biases retrieved brightness
  temperatures.
- Allowing $\varepsilon > 1$ or $\varepsilon + \rho > 1$ through unvalidated
  inputs.

**Numeric anchor.** $\varepsilon = 0.95$ at $\lambda = 10$ µm, $T = 300$ K:
$L = 0.95 \times 9.92403333 = 9.42783166$ W/m²/sr/µm. Reflected-sky term for
$\rho = 0.05$, $L_{\mathrm{down}} = 5.0$ W/m²/sr/µm: $0.250000000$
W/m²/sr/µm (2.6 % of the emitted term).

**In RADIANT.** `source/emitted.py::ThermalSource.spectral_radiance` ·
anchored by
`src/radiant/source/tests/test_emitted.py::test_scalar_graybody_matches_epsilon_times_planck`
(plus `test_epsilon_one_equals_blackbody`, `test_spectral_emissivity`). The
point-source variant $I(\lambda) = A_t\, \varepsilon\, B(\lambda, T)$ is
`source/point_source_blackbody.py::BlackbodyIntensitySource.spectral_intensity`,
anchored by
`src/radiant/source/tests/test_point_source.py::TestBlackbodyIntensitySource::test_basic_formula`.

**References.** [Kirchhoff 1860], [Siegel & Howell §3], [Holst].

---

### Kirchhoff-Derived Emissivity of Optical Elements (Rule 5)

**Equation.** For any optical element *inside the sensor*, emissivity is
never an input — it is derived:

$$\text{mirrors:}\quad \varepsilon(\lambda) = 1 - R(\lambda) \qquad\qquad \text{transmissive elements:}\quad \varepsilon(\lambda) = 1 - T(\lambda) - R(\lambda)$$

**Symbols.** $R(\lambda)$ reflectance, $T(\lambda)$ transmittance,
$\varepsilon(\lambda)$ emissivity — all dimensionless, all per wavelength,
constrained by $T + R \leq 1$.

**Derivation.** Same physics as the graybody entry — Kirchhoff plus energy
balance — but the *architectural* consequence differs. A scene target's
$\varepsilon$ is a material property the user legitimately knows. An optical
element's $\varepsilon$, $R$, and $T$ are locked together by energy
conservation: a user who specifies both $R$ and $\varepsilon$ for a mirror
has over-specified the energy balance, and the two claims can contradict.
RADIANT therefore accepts $R$ (and $T$ where applicable) and *derives*
$\varepsilon$; the derived value then drives the warm-optics self-emission
term $L_{\mathrm{nf}}(\lambda) = \varepsilon_{\mathrm{opt}}(\lambda)\,
B(\lambda, T_{\mathrm{opt}})$ that the optics stage adds to the background.

For a refractive element modeled with the cavity model, the generalized form
$\varepsilon_{\mathrm{eff}} = T_2\, n^2 (1 - \beta) / D$ applies ($n^2$
enhancement for emission inside a dielectric medium); for a simple
refractive element with no bulk absorption model, $\varepsilon = 0$ — the
residual $1 - T$ is predominantly reflection, and assigning it to emission
would fabricate thermal background.

**Assumptions & validity.** Same LTE assumptions as Kirchhoff generally.
Per-wavelength: the constraint is enforced on the full spectral grid, not on
band averages.

**Pitfalls.**

- Accepting $\varepsilon$ as an independent parameter for an optical surface
  — the over-specification bug Rule 5 exists to forbid. RADIANT raises
  `KirchhoffViolationError` instead.
- Applying $\varepsilon = 1 - R$ to a *transparent* element (missing the
  $T$ term).
- Letting $T + R > 1$ slip through unvalidated — RADIANT enforces
  $T + R \leq 1$ within tolerance and raises otherwise.
- Assigning the whole $1 - T$ of a lens to emission when most of it is
  reflection — over-predicts warm-optics background.

**Numeric anchor.** Gold mirror with $R = 0.98$ (flat): $\varepsilon = 1 -
0.98 = 0.02$ (dimensionless), and its self-emission at $T_{\mathrm{opt}} =
300$ K, $\lambda = 10$ µm is $0.02 \times 9.92403333 = 0.198480667$
W/m²/sr/µm.

**In RADIANT.** `optics/element.py::OpticalElement.emissivity` (property;
enforcement in `OpticalElement.__post_init__`) · anchored by
`src/radiant/optics/tests/test_element.py::TestKirchhoffIdentity::test_mirror_kirchhoff`
and `TestKirchhoffViolations::test_t_plus_r_exceeds_one`.

**References.** [Kirchhoff 1860], [Wolfe & Zissis §5], RADIANT Master
Architecture Rule 5.

---

### Top-of-Atmosphere Solar Irradiance

**Equation.**

$$E_{\mathrm{sun}}(\lambda) = \pi \, B(\lambda, T_{\mathrm{sun}}) \left(\frac{R_{\mathrm{sun}}}{d}\right)^{2} k_{\mathrm{scale}} \qquad \left[\text{W/m}^2\text{/µm}\right]$$

with distance scaling $E(d) = E(1\ \mathrm{AU}) / d_{\mathrm{AU}}^2$.

**Symbols.** $T_{\mathrm{sun}} = 5778$ K effective photospheric temperature;
$R_{\mathrm{sun}} = 6.957 \times 10^8$ m; $d$ Sun–target distance [m]
($d_{\mathrm{AU}}$ in AU); $(R_{\mathrm{sun}}/d)^2 \approx 2.18 \times
10^{-5}$ dimensionless geometric dilution; $k_{\mathrm{scale}}$ the flat
calibration factor that makes $\int E_{\mathrm{sun}}\, d\lambda = S_0 =
1361$ W/m² exactly.

**Derivation.** The Sun subtends $\Omega_{\mathrm{sun}} = \pi
(R_{\mathrm{sun}}/d)^2$ at the observer (small-angle; the $\pi$ here is the
projected-solid-angle integral of a uniform disk). Irradiance on a normal
plane is radiance × solid angle: $E = \Omega_{\mathrm{sun}} B(\lambda,
T_{\mathrm{sun}})$, which regroups into the form above. Because a 5778 K
blackbody with IAU nominal $R_{\mathrm{sun}}$/AU integrates to ~1365 W/m²
rather than the observed $S_0 = 1361$ W/m², RADIANT applies the flat
$k_{\mathrm{scale}}$ correction: the spectral *shape* stays exactly Planck
while the integral recovers $S_0$ to machine precision. Distance scaling is
conservation of intensity: $E \propto 1/d^2$; Earth's seasonal range
$d = 0.9833$–$1.0167$ AU gives a ±3.4 % annual swing.

**Assumptions & validity.** Blackbody spectral shape — real solar spectra
deviate at the few-percent level (Fraunhofer lines, UV/VIS deficit). A
tabulated `astm_e490` model is planned to replace the shape without breaking
the API. Small-angle solid angle is excellent ($\Omega_{\mathrm{sun}} \approx
6.8 \times 10^{-5}$ sr).

**Pitfalls.**

- Confusing irradiance with radiance: $E_{\mathrm{sun}}$ is W/m²/µm; the
  equivalent-Lambertian radiance used in single-scatter path-radiance
  formulas is $E_{\mathrm{sun}}/\pi$ [W/m²/sr/µm].
- Applying $1/d^2$ twice (once in the irradiance table, once in code) or
  not at all.
- Using the solar radius/distance ratio unsquared.

**Numeric anchor.** A pure 5772 K blackbody Sun gives $E(0.55\ \text{µm}) =
1748.50$ W/m²/µm at 1 AU ($\Omega_{\mathrm{sun}} = 6.79427 \times 10^{-5}$
sr) — within 7 % of the measured $\approx 1870$ W/m²/µm [ASTM E490]; the
real Sun exceeds the blackbody near 0.55 µm. RADIANT's calibrated model
integrates to $S_0 = 1361.0$ W/m² over 0.05–50 µm to ~$10^{-6}$ relative.

**In RADIANT.** `core/solar.py::toa_solar_spectral_irradiance` (and
`toa_solar_equivalent_radiance` for the $/\pi$ variant) · anchored by
`src/radiant/core/tests/test_solar.py::test_integral_recovers_nominal_s0` and
`test_visible_band_irradiance_within_10_percent_of_reference`.

**References.** [Kopp & Lean 2011] ($S_0 = 1361$ W/m²), [ASTM E490],
[Wehrli 1985].

---

### Reflected Solar Radiance

**Equation.**

$$L_{\mathrm{refl}}(\lambda) = f_r(\lambda;\, \theta_{\mathrm{sun}}, \theta_{\mathrm{obs}}) \cdot E_{\mathrm{sun}}(\lambda, d) \cdot \cos\theta_{\mathrm{sun}} \qquad \left[\text{W/m}^2\text{/sr/µm}\right]$$

For the Lambertian special case $f_r = \rho/\pi$:

$$L_{\mathrm{refl}}(\lambda) = \frac{\rho(\lambda)\, E_{\mathrm{sun}}(\lambda)\, \cos\theta_{\mathrm{sun}}}{\pi}$$

**Symbols.** $f_r$ [sr⁻¹] BRDF; $E_{\mathrm{sun}}$ [W/m²/µm] solar spectral
irradiance on a plane normal to the rays at the target (exo-atmospheric if
$\tau_{\mathrm{atm}}$ is applied separately downstream — which is RADIANT's
convention); $\theta_{\mathrm{sun}}$ [rad] solar zenith angle;
$\cos\theta_{\mathrm{sun}}$ projects normal-incidence irradiance onto the
tilted surface; $d$ [AU] Sun–target distance.

**Derivation.** By definition of BRDF, $dL_o = f_r\, dE_i$: outgoing radiance
is BRDF times incident irradiance *on the surface*, which is the
normal-plane irradiance times $\cos\theta_{\mathrm{sun}}$. For a Lambertian
surface, reflected exitance is $M = \rho E \cos\theta_{\mathrm{sun}}$ and a
perfectly diffuse surface has $M = \pi L$, giving the $1/\pi$ [sr⁻¹]. The
Sun is treated as a single collimated directional source (no hemisphere
integration) — v1 convention.

**Assumptions & validity.** BRDF model fidelity is the limit — Lambertian is
the baseline, Phong adds a glint lobe (next entry). Collimated-sun is fine
except in near-terminator penumbra. $\cos\theta_{\mathrm{sun}} \geq 0$
required: RADIANT clamps sun-below-horizon to zero radiance *with intent*
(returns zeros, never silent negative radiance) and rejects zenith angles
outside $[0, \pi/2]$ at construction.

**Pitfalls.**

- Missing $1/\pi$ (returns an exitance-like value, high by $\pi \approx
  3.14$) or dividing by $2\pi$ (confusing hemisphere solid angle $2\pi$
  with the projected-solid-angle integral $\int \cos\theta\, d\Omega = \pi$).
- Omitting $\cos\theta_{\mathrm{sun}}$, or using *elevation* where *zenith*
  is expected (a cos↔sin swap).
- Degrees passed to `cos()` expecting radians.
- Applying a $\cos\theta_{\mathrm{view}}$ as well — for a Lambertian surface
  the radiance has no view-angle cosine (the $\cos\theta_v$ in received
  power exactly cancels the $1/\cos\theta_v$ in projected source area).
- Double-counting the atmosphere: $E_{\mathrm{sun}}$ must be
  exo-atmospheric if $\tau_{\mathrm{atm}}$ is applied separately (RADIANT's
  case), at-surface if not.

**Numeric anchor.** With the audit's adopted $E_0(0.55\ \text{µm}) = 1870$
W/m²/µm (exo-atmospheric, $\tau = 1$), $\rho = 0.3$, $\theta_{\mathrm{sun}} =
30°$: $L = 154.647755$ W/m²/sr/µm. This anchor scales linearly with the
adopted solar table — RADIANT's `blackbody_5778` model gives a
few-percent-lower $E_0$ at 0.55 µm (previous entry), so rescale by
$E_{0,\mathrm{impl}}/1870$ before comparing implementation output against it.

**In RADIANT.** `source/reflected.py::ReflectedSolarSource.spectral_radiance`
· anchored by
`src/radiant/source/tests/test_reflected.py::TestReflectedSolarSource::test_lambertian_noon_hand_calc`,
`test_oblique_sun`, and `test_distance_scaling`.

**References.** [Nicodemus 1977], [Holst], [ASTM E490].

---

### BRDF Normalization — Lambertian and Phong

**Equation.** BRDF definition: $f_r(\omega_i, \omega_o) = dL_o / dE_i$
[sr⁻¹]. Energy conservation requires
$\int_{\mathrm{hemi}} f_r \cos\theta_o\, d\Omega_o \leq 1$ for every
incidence direction. RADIANT implements both of:

$$\text{Lambertian:}\quad f_r = \frac{\rho}{\pi} \qquad\qquad \text{Phong:}\quad f_r = \frac{\rho_d}{\pi} + \rho_s \cdot \frac{n + 2}{2\pi} \cdot \cos^{n}\alpha$$

**Symbols.** $\rho$ [—] total hemispherical reflectance; $\rho_d, \rho_s$
[—] diffuse and specular shares with $\rho_d + \rho_s = \rho$; $n \geq 0$
[—] Phong exponent (higher = narrower lobe); $\alpha$ [rad] angle between
the observer direction and the mirror-reflection direction.

**Derivation.** *Lambertian:* the projected-solid-angle integral over the
hemisphere is $\int \cos\theta\, d\Omega = 2\pi \int_0^{\pi/2} \cos\theta
\sin\theta\, d\theta = \pi$ — so $f_r = \rho/\pi$ integrates to exactly
$\rho$. That is why the divisor is $\pi$, not $2\pi$. *Phong:* with the lobe
centered on the normal ($\alpha = \theta$), $\int_{\mathrm{hemi}}
\cos^{n}\alpha \cos\theta\, d\Omega = 2\pi \int_0^{\pi/2} \cos^{n+1}\theta
\sin\theta\, d\theta = 2\pi/(n + 2)$; the factor $(n+2)/(2\pi)$ therefore
makes the specular lobe integrate to exactly $\rho_s$ at normal incidence,
so $\rho_d + \rho_s \leq 1$ suffices for energy conservation there. The
weaker $(n+1)/(2\pi)$ variant seen in graphics literature normalizes
$\int \cos^n\alpha\, d\Omega$ *without* the $\cos\theta$ throughput factor —
it conserves lobe solid-angle weight, not reflected energy, and can
over-reflect by up to $(n+2)/(n+1)$. RADIANT uses the energy-normalizing
$(n+2)/(2\pi)$.

**Assumptions & validity.** Lambertian: exact energy conservation for any
$\rho \leq 1$; view-independent radiance. Phong: phenomenological (no
reciprocity in the classic form, no Fresnel dependence); the normalization
is exact only when the mirror direction coincides with the normal — at
grazing incidence part of the lobe falls below the horizon and the actual
reflected fraction is $< \rho_s$ (energy lost, never gained: conservative
but biased). Adequate for glint order-of-magnitude budgets; use microfacet
models for rendering-grade physics. RADIANT evaluates $\alpha =
|\theta_{\mathrm{obs}} - \theta_{\mathrm{sun}}|$ in the plane of incidence
(azimuthally symmetric v1 geometry).

**Pitfalls.**

- $\rho$ instead of $\rho/\pi$ — off by $\pi$ in every reflected radiance;
  arguably the single most common radiometry bug in existence. Or
  $\rho/(2\pi)$ from the hemisphere-vs-projected-solid-angle confusion.
- $(n+1)/(2\pi)$ where energy normalization $(n+2)/(2\pi)$ is intended, or
  vice versa without documenting the convention.
- Measuring $\alpha$ from the surface normal instead of from the
  mirror-reflection direction.
- $\cos^{n}\alpha$ not clamped at $\alpha > \pi/2$ — odd $n$ on a negative
  cosine produces negative radiance. RADIANT clamps
  $\cos\alpha$ at zero.
- Adding a Lambertian *radiance* term to a Phong *BRDF* term (unit
  mismatch: one already has the $1/\pi$ folded into a radiance, the other
  is sr⁻¹).

**Numeric anchor.** Lambertian, $\rho = 0.3$: $\int f_r \cos\theta\,
d\Omega = 0.300000000$ (dimensionless, $= \rho$ exactly). Phong with
$(n+2)/(2\pi)$ at normal incidence: the hemispherical integral over
$\rho_s$ equals $1.00000000$ (dimensionless) for $n = 1, 10, 100$ (audit
adaptive quadrature).

**In RADIANT.** `source/brdf_lambertian.py::LambertianBRDF.evaluate` ·
anchored by
`src/radiant/source/tests/test_brdf.py::TestLambertianBRDF::test_energy_conservation`
(numerical hemisphere integral recovers $\rho$).
`source/brdf_phong.py::PhongBRDF.evaluate` · anchored by
`src/radiant/source/tests/test_brdf.py::TestPhongBRDF::test_specular_peak`
and `test_zero_specular_equals_lambertian`; no anchor test pins the Phong
$(n+2)/(2\pi)$ hemispherical-integral normalization itself (as of 2026-07).

**References.** [Nicodemus 1977], [Phong 1975], [Lewis 1994].

---

### Point-Source Irradiance and Pixel Solid Angle

**Equation.** A point source of spectral intensity $I(\lambda)$ [W/sr/µm] at
range $R$ [m] through path transmittance $\tau_{\mathrm{atm}}(\lambda)$
delivers at-aperture spectral irradiance

$$E_{\mathrm{ap}}(\lambda) = \frac{I(\lambda)\, \tau_{\mathrm{atm}}(\lambda)}{R^{2}} \qquad \left[\text{W/m}^2\text{/µm}\right]$$

The pixel-subtended solid angle (small-angle) is

$$\Omega_{\mathrm{pix}} = \frac{p_x\, p_y}{f^{2}} = \mathrm{IFOV}_x \cdot \mathrm{IFOV}_y \qquad \left[\mathrm{sr}\right]$$

and the target solid angle is $\Omega_t = A_t / R^2$ [sr].

**Symbols.** $I(\lambda)$ [W/sr/µm] — for a small Lambertian-emitting facet
$I = L \cdot A_t$; $R$ [m] slant range; $p_x, p_y$ [m] pixel pitches; $f$
[m] focal length; $A_t$ [m²] projected target area.

**Derivation.** Inverse square is conservation of energy through expanding
spheres: intensity is fixed, irradiance $= I/R^2$. Aperture spectral power is
then $\Phi(\lambda) = E_{\mathrm{ap}} A_{\mathrm{ap}}$ [W/µm]. RADIANT's
spectral-integration stage implements the equivalent radiance route:
$\Phi = L_{\mathrm{target}} \cdot A_{\mathrm{ap}} \cdot \Omega_t$ with
$\Omega_t = A_t/R^2$ — identical to $I/R^2 \cdot A_{\mathrm{ap}}$ because
$I = L A_t$. The blur spreads this energy per the PSF; the ensquared-energy
fraction $\mathrm{EE}_{\mathrm{box}}$ multiplies the in-pixel signal, applied
exactly once, downstream (Rule 9).

**Assumptions & validity.** Point-source regime valid when the source's
angular extent $\ll$ IFOV *and* $\ll$ PSF width. $\Omega = A/R^2$ is the
small-angle approximation — exact solid-angle formulas matter only for
$\mathrm{IFOV} \gtrsim 0.1$ rad, never for imaging sensors. Flat
normal-incidence footprint assumed; off-nadir the ground footprint grows by
$1/\cos$(incidence). $\tau_{\mathrm{atm}}$ is the *slant-path*
transmittance, not the vertical column.

**Pitfalls.**

- Applying both $1/R^2$ *and* $\Omega_{\mathrm{pix}}$ to the same term —
  double-counting the geometry. Radiance-based extended-scene math
  ($L \cdot \Omega_{\mathrm{pix}} \cdot A_{\mathrm{ap}}$) and
  irradiance-based point-source math ($I/R^2 \cdot A_{\mathrm{ap}}$) are
  *alternative routes*, never multiplied together.
- $\tau_{\mathrm{atm}}^2$ (two-way path) sneaking in from radar heritage —
  passive EO is one-way.
- Range in km fed to a formula expecting m — a $10^6$ error in
  $E_{\mathrm{ap}}$.
- Applying $\mathrm{EE}_{\mathrm{box}}$ anywhere but once, in
  spectral integration (Rule 9).

**Numeric anchor.** $I = 100$ W/sr/µm, $\tau = 0.7$, $R = 500$ km:
$E_{\mathrm{ap}} = 2.80000000 \times 10^{-10}$ W/m²/µm. Pixel solid angle
for GSD = 3 m at $R$ = 500 km: $\Omega_{\mathrm{pix}} = 3.60000000 \times
10^{-11}$ sr (IFOV = 6 µrad).

**In RADIANT.** Point-source branch of
`spectral_integration/stage.py::SpectralIntegrationStage.run`
($\Omega_t = A_t/R^2$, photon rate $= L \cdot A_{\mathrm{ap}} \cdot \Omega_t
\cdot \lambda_m/hc$) · anchored by
`src/radiant/spectral_integration/tests/test_stage.py::test_EE_box_applied_once_point_source`
and `test_hand_calculated_flat_source`. $\Omega_{\mathrm{pix}}$ is published
by the optics stage (`optics/aperture.py`) as `Omega_pixel`.

**References.** [Holst], [Wolfe & Zissis §1].

---

### Sub-Pixel Fill Fraction and Radiance Mixing

**Equation.** When the target's solid angle is smaller than the pixel's:

$$f\!f = \frac{\Omega_t}{\Omega_{\mathrm{pix}}} = \frac{A_t}{R^{2}\, \Omega_{\mathrm{pix}}} \qquad \left(0 < f\!f \leq 1,\ \text{clamped at } 1\right)$$

The pixel-averaged apparent radiance is the area-weighted mix (with path
radiance filling the whole pixel uniformly):

$$L_{\mathrm{mixed}}(\lambda) = f\!f \cdot L_{\mathrm{target}}(\lambda) \cdot \mathrm{EE}_{\mathrm{box}} + \left(1 - f\!f\right) L_{\mathrm{bg}}(\lambda) + L_{\mathrm{path}}(\lambda)$$

**Symbols.** $f\!f$ [—] fill fraction; $L_{\mathrm{target}},
L_{\mathrm{bg}}$ [W/m²/sr/µm] pure target and background contributions at
the aperture (path radiance separated out); $L_{\mathrm{path}}$ [W/m²/sr/µm]
path radiance; $\mathrm{EE}_{\mathrm{box}}$ [—] applied to the compact
target term only.

**Derivation.** The pixel sees $\Omega_{\mathrm{pix}}$; the target fills
$\Omega_t$ of it and background fills the rest — hence the $f\!f$ /
$(1 - f\!f)$ split. The **regime-consistency identity** ties the sub-pixel
and point-source routes together: the target's contribution to aperture
irradiance via the point-source route is $L_t A_t \tau / R^2$, and via the
sub-pixel route it is $L_t \cdot f\!f \cdot \Omega_{\mathrm{pix}} \cdot
\tau$. Since $f\!f \cdot \Omega_{\mathrm{pix}} = A_t/R^2 = \Omega_t$ by
construction, the two routes agree identically — that identity is what the
fill-fraction anchor test pins. Path radiance is generated along the line of
sight, not at the target, so it is added once, unweighted by $f\!f$, and
never multiplied by $\mathrm{EE}_{\mathrm{box}}$.

**Assumptions & validity.** Areal mixing assumes the target sits fully
within one IFOV footprint (no straddling-pixel split modeling). Clamps to
$f\!f = 1$ when the target overfills the pixel (the regime then belongs to
extended-scene handling). Fill fraction from geometry requires positive
area, range, pitches, and focal length; otherwise RADIANT falls back to the
explicit `fill_fraction` parameter rather than guessing.

**Pitfalls.**

- Area vs side-length confusion: $f\!f = A_t/\mathrm{GSD}^2$, not
  $l_t/\mathrm{GSD}$.
- Forgetting the $(1 - f\!f)$ background complement — the unfilled pixel
  area still sees background radiance.
- Applying $\mathrm{EE}_{\mathrm{box}}$ to the background term — background
  is extended; EE applies to the compact target only (Rule 9; RADIANT
  guards this explicitly).
- Splitting path radiance by $f\!f$ — it fills the pixel uniformly.
- Deriving $f\!f$ from nadir GSD² off-nadir — the footprint grows with
  incidence.

**Numeric anchor.** $A_t = 1$ m², GSD = 3 m (i.e. $\Omega_{\mathrm{pix}}$
matched to a 3 m footprint): $f\!f = 0.111111111$ (dimensionless).

**In RADIANT.** `source/fill_fraction.py::fill_fraction_from_area` · anchored
by
`src/radiant/source/tests/test_fill_fraction.py::test_ff_times_omega_pixel_recovers_omega_target`
(the regime-consistency identity) and `test_matches_areal_ratio`. The mixing
equation is the sub-pixel branch of
`spectral_integration/stage.py::SpectralIntegrationStage.run`, anchored by
`src/radiant/spectral_integration/tests/test_stage.py::test_EE_box_exempts_background_sub_pixel`.

**References.** [Holst], RADIANT Source/Target System doc §3.

---

### Photon Conversion — Spectral Power to Photoelectron Rate

**Equation.** Photon energy $E_{\mathrm{ph}} = hc/\lambda_m$ [J]. The
photoelectron rate from spectral power $\Phi(\lambda)$ [W/µm] at the detector
is

$$\dot{n}_e = \int \mathrm{QE}(\lambda)\, \Phi(\lambda)\, \frac{\lambda_m}{h c}\, d\lambda \qquad \left[\mathrm{e^{-}/s}\right], \quad \lambda_m = \lambda \cdot 10^{-6}$$

integrated over $\lambda$ in µm; total signal $N_e = \dot{n}_e \cdot
t_{\mathrm{int}}$ [e⁻]. RADIANT packages the same physics as an
aperture-referred spectral responsivity

$$R(\lambda) = A_{\mathrm{ap}}\, \Omega_{\mathrm{pix}}\, \tau_{\mathrm{opt}}(\lambda)\, \mathrm{QE}(\lambda)\, \frac{\lambda_m}{h c} \qquad \left[\mathrm{e^{-}/s}\ \text{per}\ \text{W/m}^2\text{/sr/µm}\right]$$

with $R_{\mathrm{band}} = \int R(\lambda)\, d\lambda$ used for backward
propagation ($L_{\mathrm{aperture}} = N_e / (R_{\mathrm{band}}\,
t_{\mathrm{int}})$).

**Symbols.** $\Phi(\lambda)$ [W/µm]; $\mathrm{QE}(\lambda)$ [e⁻/photon,
dimensionless]; $\lambda_m/(hc)$ [photons/J] converts watts to photons/s;
$t_{\mathrm{int}}$ [s]; $A_{\mathrm{ap}}$ [m²]; $\Omega_{\mathrm{pix}}$ [sr];
$\tau_{\mathrm{opt}}$ [—].

**Derivation.** A watt of monochromatic light at wavelength $\lambda$ carries
$1/E_{\mathrm{ph}} = \lambda_m/hc$ photons per second. Weight by QE per
photon and integrate across the band. The $10^{-6}$ lives in $\lambda_m$:
$\lambda$ in µm must be converted to meters so $\lambda_m/(hc)$ has units
1/J.

**Assumptions & validity.** One photoelectron per detected photon, weighted
by QE (no avalanche gain — gain is a separate downstream stage). $\lambda/hc$
must stay *inside* the integral: photon energy varies across the band, and
pulling out a band-center value biases wide bands (for 3–5 µm the
edge-to-edge photon-energy ratio is 5/3). QE convention (per incident vs per
absorbed photon) must be consistent, with fill factor and window transmission
counted once — inside QE or as separate factors, never both. Shot noise
follows as $\sqrt{N_e}$ only if $N_e$ is a true photon count: any premature
gain scaling corrupts the Poisson statistics.

**Pitfalls.**

- The $10^{-6}$: using $\lambda$ in µm directly in $\lambda/(hc)$ — rate
  high by $10^6$.
- Energy-weighted vs photon-weighted band averages confused: QE tables are
  per-photon; responsivity in A/W is per-energy ($R_{A/W} = \mathrm{QE}
  \cdot q\lambda_m/hc$) — mixing them double-counts $\lambda$.
- Applying $t_{\mathrm{int}}$ inside a "rate" function so downstream
  multiplies by it again.
- The electron charge $q = 1.602 \times 10^{-19}$ C appearing where it does
  not belong — electron *counts* are dimensionless; charge enters only when
  converting to amperes.

**Numeric anchor.** Monochromatic $\Phi = 10^{-12}$ W at $\lambda = 4$ µm
with QE = 0.7: $\dot{n}_e = 1.40955264 \times 10^{7}$ e⁻/s (check:
$E_{\mathrm{ph}}(4\ \text{µm}) = 4.96611464 \times 10^{-20}$ J, and
$0.7 \times 10^{-12}\,\mathrm{W} / 4.96611464 \times 10^{-20}\,\mathrm{J}$
reproduces the rate).

**In RADIANT.** Forward direction: the $\lambda_m/hc$ photon-rate factor in
`spectral_integration/stage.py::SpectralIntegrationStage.run` · anchored by
`src/radiant/spectral_integration/tests/test_stage.py::test_hand_calculated_flat_source`.
Backward/packaged direction: `core/responsivity.py::spectral_responsivity`
and `band_integrated_responsivity` · anchored by
`src/radiant/core/tests/test_responsivity.py::test_band_integral_closed_form_anchor`
and `test_round_trip_recovers_known_radiance`.

**References.** [Holst], [Janesick 2001], [CODATA 2018].

---

## How the Foundations Feed the Chain

The nine stages consume the foundations above in a fixed order. Each stage is
a pure function `run(state, params) -> state` (Rule 6); all inter-stage data
flows through the immutable `ChainState`.

| # | Stage | Radiometric role | Foundations used | Detailed in |
|---|---|---|---|---|
| 0 | Geometry (`geometry/`) | Slant range $R$, incidence, solar geometry | — (feeds $R$, $\theta_{\mathrm{sun}}$ to everything) | ADR-0006 |
| 1 | Source (`source/`) | Build $L_{\mathrm{target}}(\lambda)$, $L_{\mathrm{bg}}(\lambda)$; tentative regime | Planck, graybody, reflected solar, BRDF, brightness/radiance temperature converters, point-source intensity | this chapter |
| 2 | Atmosphere (`atmosphere/`) | $L_{\mathrm{ap}} = L\,\tau_{\mathrm{atm}} + L_{\mathrm{path}}$ | band integration on the $\tau(\lambda)$ grid | atmosphere docs |
| 3 | Optics (`optics/`) | Throughput $\tau_{\mathrm{opt}}$, $A_{\mathrm{ap}}$, $\Omega_{\mathrm{pix}}$; warm-optics self-emission; **final regime** | Kirchhoff Rule-5 emissivity, Planck (self-emission), pixel solid angle | [Spatial Model](spatial_model.md) for PSF/MTF |
| 4 | Platform (`platform/`) | Smear/jitter degradation; $\mathrm{EE}_{\mathrm{box}}$ from the fully degraded PSF | — | [Spatial Model](spatial_model.md) |
| 5 | Spectral Integration (`spectral_integration/`) | Spectral → scalar, exactly once (Rule 8); $\mathrm{EE}_{\mathrm{box}}$ applied exactly once (Rule 9) | photon conversion, point-source/sub-pixel regime radiometry, fill-fraction mixing | this chapter |
| 6 | Detector (`detector/`) | Noise budget (16 terms) | $\sqrt{N_e}$ shot statistics | [Noise Model](noise_model.md) |
| 7 | Readout (`readout/`) | TDI, binning, coadd, gain, ADC scaling | — | [Noise Model](noise_model.md) |
| 8 | Performance (`performance/`) | SNR, NEDT, NIIRS, system MTF | $\partial B/\partial T$ (NEDT kernel), band responsivity (backward propagation) | performance docs |

Three chain-glue equations worth stating here because they are pure
radiometry:

**At-aperture radiance** (Atmosphere stage):

$$L_{\mathrm{ap}}(\lambda) = L_{\mathrm{target}}(\lambda)\, \tau_{\mathrm{atm}}(\lambda) + L_{\mathrm{path}}(\lambda)$$

where $\tau_{\mathrm{atm}}$ follows Beer–Lambert along the slant path and
$L_{\mathrm{path}}$ is atmospheric self-emission and scatter into the line
of sight.

**Extended-scene signal electrons** (Spectral Integration stage, Rule 8 —
the only spectral-to-scalar collapse in the chain):

$$N_e = \int_{\lambda_1}^{\lambda_2} L_{\mathrm{ap}}(\lambda)\, \tau_{\mathrm{opt}}(\lambda)\, A_{\mathrm{ap}}\, \Omega_{\mathrm{pix}}\, \mathrm{QE}(\lambda)\, \frac{\lambda_m}{h c}\, t_{\mathrm{int}}\, d\lambda$$

with $\mathrm{EE}_{\mathrm{box}}$ multiplying the target term only in
point-source and sub-pixel regimes, never in extended scenes and never on
the background term (Rule 9).

**SNR** (Performance stage): $\mathrm{SNR} = N_e / \sigma_{\mathrm{total}}$
with $\sigma_{\mathrm{total}}$ the RSS of the noise budget; contrast SNR uses
$N_{e,\mathrm{target}} - N_{e,\mathrm{bg}}$ in the numerator. NEDT divides
the noise-equivalent radiance by the band-integrated $\partial B/\partial T$
— which is why the NEDT-kernel entry above carries per-K units end to end.

### Dimensional Trace

| Stage | Input units | Output units | Conversion |
|---|---|---|---|
| Geometry | orbit/attitude params | m, rad | trigonometry |
| Source | K, dimensionless ε/ρ | W/m²/sr/µm | Planck + ε; BRDF · E_sun · cos θ |
| Atmosphere | W/m²/sr/µm | W/m²/sr/µm | × τ_atm + L_path |
| Optics | W/m²/sr/µm | W/m²/sr/µm (+ A_ap [m²], Ω_pix [sr] published) | × τ_opt |
| Platform | — (radiometric pass-through) | EE_box [—] | PSF ensquared energy |
| Spectral Integration | W/m²/sr/µm, m², sr, s | e⁻ | × A·Ω · QE · λ_m/hc · t_int, ∫dλ |
| Detector | e⁻ | e⁻ RMS (noise terms) | noise model |
| Readout | e⁻ | e⁻ (scaled), DN | × N_TDI · M_bin · N_coadd; ÷ gain |
| Performance | e⁻ | dimensionless (SNR), K (NEDT), NIIRS | S/σ; σ_L / ∫(∂B/∂T)dλ |

Every row must check; integrating a per-µm density over µm is the only
"conversion-free" collapse, and the two $10^{-6}$ factors in the chain
(Planck Jacobian, photon-energy $\lambda_m$) each appear exactly once.

---

## Assumptions and Limitations

- Lambertian target emission; BRDF structure available only through the
  Lambertian and normalized-Phong models (no microfacet, no measured BRDF
  tables)
- Sun as a collimated directional source; blackbody-5778 solar spectral
  shape (few-percent deviations from the real spectrum; tabulated ASTM E490
  model planned)
- No molecular spectroscopy or fluorescence
- No atmospheric refraction or scintillation
- No ghost images, BSDF scatter, or chromatic aberration
- No optical crosstalk between pixels
- No temporal variability in scene
- See `docs/architecture/RADIANT_Scope_Decisions.md` for the full list of
  deferred effects
