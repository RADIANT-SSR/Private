# Track A1 — Blind Re-Derivation: Radiometry & Sources

Status: Complete (derivation phase)
Produced by: blind-derivation agent (no access to src/ or docs/), 2026-07-22.
Comparison against implementation: see findings.md.

---

# Blind First-Principles Re-Derivation — RADIANT Radiometry Audit

Independent derivation from physics literature only. No RADIANT source or docs were read. All numerics computed with Python/numpy/scipy using CODATA 2018 constants:

- h = 6.62607015 × 10⁻³⁴ J·s
- c = 2.99792458 × 10⁸ m/s
- k_B = 1.380649 × 10⁻²³ J/K
- hc = 1.98644586 × 10⁻²⁵ J·m ; hc/k_B = 1.43877688 × 10⁻² m·K (second radiation constant c₂)

Conventions: λ in µm, spectral radiance in W/m²/sr/µm, angles in rad, lengths in m, temperature in K.

---

## 1. Planck Spectral Radiance L(λ, T)

### (a) Governing equation

In SI-per-meter form, with λ_m the wavelength in meters:

  L_m(λ_m, T) = (2 h c² / λ_m⁵) · 1 / (exp(hc / (λ_m k_B T)) − 1)  [W/m²/sr/**m**]

To express per micrometer with input λ in µm:

  **L(λ, T) = 10⁻⁶ · (2 h c² / (λ·10⁻⁶)⁵) · 1 / (exp(hc / (λ·10⁻⁶ · k_B T)) − 1)**  [W/m²/sr/µm]

Symbols: λ [µm] wavelength; T [K] absolute temperature; h [J·s]; c [m/s]; k_B [J/K]. The dimensionless argument is x = hc/(λ_m k_B T) = c₂/(λ_m T).

**The 1e-6 handling, explicitly:** convert λ to meters (×10⁻⁶) *inside* the formula, evaluate in W/m²/sr/m, then multiply the result by 10⁻⁶ because 1 W/m²/sr/m = 10⁻⁶ W/m²/sr/µm (a per-µm interval is 10⁻⁶ of a per-m interval). Net effect: L[per-µm] = 2hc²·10⁻⁶ / λ_m⁵ / (eˣ − 1). Equivalently, with c₁L = 2hc² = 1.191042972 × 10⁻¹⁶ W·m⁴/sr and λ kept in µm: L = c₁L·10²⁴/λ⁵ / (eˣ−1) — the exponent bookkeeping (λ⁻⁵ contributes 10³⁰, the per-µm conversion 10⁻⁶) is exactly where implementations go wrong.

### (b) Assumptions / validity
- Thermal equilibrium blackbody emission into vacuum (refractive index n = 1; in a medium L scales as n²).
- Unpolarized, isotropic (Lambertian) emission — L is direction-independent.
- Valid for all λ, T > 0; numerically, x ≫ 700 overflows exp() in float64 (use expm1 and accept underflow to 0 for deep Wien tail; do not let it produce inf/NaN silently).

### (c) Classic pitfalls
- **Per-µm vs per-m factor of 10⁻⁶** applied zero times or twice → results off by 10⁶ or 10¹².
- Using λ in µm inside λ⁵ without the unit conversion → off by 10³⁰/10²⁴ mismatches.
- Using `exp(x) - 1` instead of `expm1(x)`: catastrophic cancellation for x ≪ 1 (Rayleigh–Jeans regime, radio/submm).
- Confusing first radiation constant for *radiance* (c₁L = 2hc²) with the one for *exitance* (c₁ = 2πhc²) — a stray factor of π.
- Confusing radiance L with exitance M = πL.

### (d) Spot checks
| Input | Output |
|---|---|
| λ = 10 µm, T = 300 K (x = 4.79592293) | **L = 9.92403333 W/m²/sr/µm** |
| λ = 4 µm, T = 300 K (x = 11.9898073) | **L = 0.721976423 W/m²/sr/µm** |
| λ = 0.55 µm, T = 5772 K (solar photosphere) | **L = 2.57349155 × 10⁷ W/m²/sr/µm** |

Sanity: LWIR peak of 300 K blackbody is near λ_max = 2898 µm·K / 300 K ≈ 9.66 µm, so L(10 µm) ≈ 9.9 is near-peak — consistent with the familiar textbook value ≈ 9.92.

---

## 2. dL/dT — the NEDT Kernel

### (a) Governing equation

Differentiate L w.r.t. T at fixed λ. With x = hc/(λ_m k_B T):

  **∂L/∂T = L(λ, T) · (x / T) · eˣ / (eˣ − 1)**  [W/m²/sr/µm/K]

Expanded: ∂L/∂T = (2h²c³·10⁻⁶ / (λ_m⁶ k_B T²)) · eˣ/(eˣ−1)². All symbols as §1; T in K.

### (b) Assumptions / validity
- Exact analytic derivative of the Planck function; no linearization assumed *in the derivative itself*. Using it as the NEDT kernel (ΔL ≈ (∂L/∂T)·ΔT) assumes ΔT small enough that L is locally linear — excellent for ΔT ≲ a few K at terrestrial temperatures; degrades in the Wien regime (large x) where L is exponentially steep (relative error in the linearization ~ (x/2)(ΔT/T)).
- Same n = 1, equilibrium assumptions as §1.

### (c) Classic pitfalls
- Dropping the eˣ/(eˣ−1) factor (i.e., writing ∂L/∂T = L·x/T) — a Wien-limit-only shortcut; at λ = 10 µm, T = 300 K (x ≈ 4.8) it's ~0.8% low, at MWIR it's fine to ~6×10⁻⁶ but the omission is regime-dependent and silent.
- Squaring error: the fully expanded form has (eˣ−1)², implementers sometimes carry (eˣ−1)¹.
- Sign: ∂L/∂T > 0 for all λ, T. A negative value anywhere is a bug.
- Same per-µm 10⁻⁶ hazards as §1; units are per-K *in addition* — off-by-10⁶ propagates straight into NEDT.

### (d) Spot checks (analytic form verified against central finite difference to ≤ 3×10⁻¹⁰ relative)
| Input | Output |
|---|---|
| λ = 10 µm, T = 300 K | **∂L/∂T = 0.159971567 W/m²/sr/µm/K** |
| λ = 4 µm, T = 300 K | **∂L/∂T = 2.88547064 × 10⁻² W/m²/sr/µm/K** |
| λ = 10 µm, T = 250 K | **∂L/∂T = 8.73744062 × 10⁻² W/m²/sr/µm/K** |

Sanity: MWIR ∂L/∂T is ~5.5× smaller than LWIR at 300 K in per-µm terms, but its *fractional* contrast (∂L/∂T)/L = x/T·eˣ/(eˣ−1) is larger (4.00%/K vs 1.61%/K) — the classic MWIR-vs-LWIR contrast trade.

---

## 3. Band-Integrated and Band-Averaged Radiance

### (a) Governing equations

  **L_band = ∫_{λ1}^{λ2} L(λ, T) dλ ≈ Σ_{i=1}^{N−1} ½·(L_i + L_{i+1})·(λ_{i+1} − λ_i)**  [W/m²/sr]

  **L̄ = L_band / (λ2 − λ1)**  [W/m²/sr/µm]

λ1, λ2 [µm] band edges; L_i = L(λ_i, T) on the spectral grid [W/m²/sr/µm]; grid spacing in µm. Integrating per-µm radiance over µm yields W/m²/sr with no extra conversion factor.

### (b) Assumptions / validity
- Trapezoidal rule assumes L is well-resolved by the grid — smooth for a blackbody; for atmospherically filtered radiance (line structure) the grid must resolve the τ(λ) features or the result is quadrature-limited, not physics-limited.
- Non-uniform grids are handled correctly by the general trapezoid formula (spacing per interval, not a single Δλ).
- Band-average L̄ divides by the *full* span λ2−λ1; if a spectral response function R(λ) is involved, the correct band average is ∫L·R dλ / ∫R dλ instead.

### (c) Classic pitfalls
- Δλ in wrong units (m instead of µm, or nm) → 10⁻⁶/10³ scale errors on integration.
- Using a rectangle/left-Riemann sum with coarse grids — visible bias (see N = 5 row below: −0.4% even for trapezoid).
- Dividing by N or by number of samples instead of the wavelength span when band-averaging.
- Applying the band-average *then* multiplying by Δλ elsewhere too — integrating twice.
- For sensor use: forgetting the relative spectral response weighting and treating the band as a top-hat.

### (d) Spot checks — T = 300 K blackbody
| Band / grid | L_band [W/m²/sr] | L̄ [W/m²/sr/µm] |
|---|---|---|
| 8–12 µm, N = 5 (Δλ = 1 µm, trapz) | 38.3471444 | 9.58678610 |
| 8–12 µm, N = 401 (trapz) | 38.5004086 | 9.62510215 |
| 8–12 µm, adaptive quad (truth) | **38.5004239** | **9.62510598** |
| 3–5 µm, N = 20001 (trapz) | **1.86595621** | 0.932978105 |

Sanity: 8–12 µm captures 38.5/(σT⁴/π = 146.15) ≈ 26.3% of total 300 K radiance — consistent with blackbody band-fraction tables (F(0→λT): F(3600 µm·K) − F(2400 µm·K) ≈ 0.404 − 0.140 ≈ 0.26).

---

## 4. Radiance Temperature (Monochromatic Inversion)

### (a) Governing equation

Given measured L [W/m²/sr/µm] at a single λ [µm], solve L = c₁′/λ⁵/(eˣ−1) for T. Closed form:

  **T = (hc / (λ_m k_B)) · 1 / ln(1 + 2hc²·10⁻⁶ / (λ_m⁵ · L))**  [K]

with λ_m = λ·10⁻⁶ [m]. The numerator hc/(λ_m k_B) = c₂/λ_m [K]; the log argument is 1 + c₁L·10⁻⁶/(λ_m⁵ L), dimensionless (both terms in W/m²/sr/µm at that λ).

### (b) Assumptions / validity
- The source is a blackbody at that wavelength (ε = 1); for a graybody the radiance temperature is *below* the thermodynamic temperature.
- Monochromatic: L is the spectral radiance at exactly λ (or a band narrow enough that L is flat across it).
- Defined for any L > 0; exact inverse of §1 (strictly monotonic in T), so uniqueness is automatic.

### (c) Classic pitfalls
- **The 10⁻⁶ inside the log**: since L is per-µm, the c₁L/λ_m⁵ term must also be converted to per-µm before forming the ratio; omitting it shifts T noticeably (a 10⁶ error in the log argument).
- Using `log` of the ratio alone (Wien approximation T = c₂/λ_m / ln(c₁′/(λ⁵L))) without the "1 +" — fine for x ≫ 1, a hidden bias near band peak (at 10 µm/300 K, x ≈ 4.8, the "+1" matters at the ~1 K level).
- Using `log(1 + r)` naively for tiny r — use log1p for very hot/Rayleigh–Jeans cases.
- λ in µm inside λ⁵ without conversion (same as §1).

### (d) Spot checks
| Input | Output |
|---|---|
| λ = 10 µm, L = 9.0 W/m²/sr/µm | **T_rad = 294.054730 K** (re-forward: L(10, 294.054730) = 9.00000000 ✓) |
| λ = 10 µm, L = L(10 µm, 300 K) = 9.92403333 | T_rad = 300.000000 K (round-trip exact to 10 digits) |
| λ = 4 µm, L = L(4 µm, 300 K) = 0.721976423 | T_rad = 300.000000 K (round-trip) |

---

## 5. Band Brightness Temperature

### (a) Governing equation

Given measured band radiance L_meas [W/m²/sr] over [λ1, λ2], the band brightness temperature T_B solves:

  **F(T_B) ≡ ∫_{λ1}^{λ2} L(λ, T_B) dλ − L_meas = 0**  [W/m²/sr]

No closed form; solve numerically (bisection/Brent on T, or Newton using §2's analytic ∫∂L/∂T dλ as the derivative).

**Uniqueness/monotonicity argument:** ∂L/∂T > 0 for every λ and T (§2, strictly positive since eˣ/(eˣ−1)² > 0), therefore F′(T) = ∫ ∂L/∂T dλ > 0 — F is strictly increasing in T. Moreover F(T→0⁺) → −L_meas < 0 and F(T→∞) → +∞ (band radiance is unbounded above, growing ∝ T⁴ times the band fraction). A strictly increasing continuous function with a sign change has exactly one root: T_B exists and is unique for any L_meas > 0. This licenses bracketing solvers with a guaranteed single solution.

### (b) Assumptions / validity
- Blackbody spectral shape assumed within the band; a graybody or atmospherically filtered scene yields an *effective* T_B, not the physical temperature.
- If a spectral response R(λ) applies, the same argument holds with R(λ) ≥ 0 weighting (F′ still > 0 as long as R is not identically zero).
- The quadrature grid used in the solver must match the one used to produce/compare L_meas, or a quadrature-mismatch bias masquerades as a temperature bias (see N = 5 vs quad rows in §3: 0.15% radiance error ≈ 0.1 K at LWIR).

### (c) Classic pitfalls
- Inverting the *band-averaged* radiance through the *monochromatic* Planck at band center — close for narrow bands but a systematic bias for wide bands (nonlinearity of Planck across the band).
- Solver bracket too narrow (e.g., [200, 400] K) — fails on hot targets; or seeded Newton diverging in the Wien regime where F is extremely flat at low T.
- Comparing per-µm to band-integrated units (W/m²/sr/µm vs W/m²/sr) — a (λ2−λ1) factor error.
- Tolerance on radiance vs on temperature confused: at 3–5 µm, dL_band/dT ≈ 4%/K of L_band, so 1% radiance tolerance ≈ 0.25 K.

### (d) Spot checks (Brent, bracket [4, 3000] K, 4001-pt trapezoid)
| Input | Output |
|---|---|
| 8–12 µm, L_meas = 38.5004238 W/m²/sr (self-consistency) | **T_B = 300.000000 K** |
| 8–12 µm, L_meas = 30.0 W/m²/sr | **T_B = 285.450727 K** (re-forward: 30.0000000 ✓) |
| 3–5 µm, L_meas = 0.5 W/m²/sr | **T_B = 267.404258 K** (re-forward: 0.500000000 ✓) |

---

## 6. Lambertian Reflected Solar Radiance

### (a) Governing equation

  **L_refl(λ) = ρ(λ) · E_sun(λ) · cos θ_sun / π**  [W/m²/sr/µm]

- ρ(λ) [dimensionless, 0–1]: hemispherical (Lambertian) reflectance / albedo
- E_sun(λ) [W/m²/µm]: solar spectral irradiance **on a plane normal to the sun's rays, at the surface** (i.e., exo-atmospheric E₀ × τ_down if atmosphere is applied)
- θ_sun [rad]: solar zenith angle at the surface; cos θ_sun projects normal-incidence irradiance onto the tilted surface
- The 1/π [sr⁻¹] converts reflected exitance M = ρ·E·cosθ [W/m²/µm] into radiance for a perfectly diffuse surface (M = πL for Lambertian).

**Distance scaling:** E_sun ∝ 1/d² with d the sun–target distance. At d [AU]: E(d) = E₀(1 AU)/d². Seasonal Earth range: d = 0.9833–1.0167 AU → ±3.4% annual swing. This follows from conservation: the sun's intensity is fixed, irradiance = I/d².

**Exo-atmospheric anchor at 0.55 µm:** I use **E₀(0.55 µm) = 1870 W/m²/µm** (≈ 1.87 W/m²/nm, consistent with ASTM E490 / Wehrli 1985 to within a few %). Cross-check from first principles: a 5772 K blackbody sun, R_sun = 6.957×10⁸ m at 1 AU = 1.495978707×10¹¹ m subtends Ω_sun = π(R/d)² = 6.79427397×10⁻⁵ sr, giving E = Ω_sun·L(0.55, 5772) = 1748.50 W/m²/µm — within 7% of the measured value (the real sun exceeds the blackbody near 0.55 µm), confirming order and scale.

### (b) Assumptions / validity
- Surface is Lambertian (radiance independent of view direction) — real surfaces have BRDF structure (hot-spot, specular glint); this is the flat-Earth-of-BRDFs baseline.
- Sun treated as a collimated point source (Ω_sun ≈ 6.8×10⁻⁵ sr, fine except near-terminator penumbra effects).
- cos θ_sun ≥ 0 required; θ_sun ≥ π/2 (sun below horizon) must clamp to zero *with intent*, not by silent negative radiance.
- E_sun must be at-surface if τ_atm is not applied separately, exo-atmospheric if it is — double-counting the atmosphere is the classic system-integration bug.

### (c) Classic pitfalls
- **Missing 1/π** (returns exitance-like value, high by π ≈ 3.14) or **dividing by 2π** (confusing hemisphere solid angle with the projected-solid-angle integral ∫cosθ dΩ = π).
- **Omitting cos θ_sun**, or using elevation angle in place of zenith angle (cos↔sin swap).
- Degrees passed to cos() expecting radians.
- Applying cos θ_view as well — for a Lambertian surface the *radiance* has no view-angle cosine (the cosθ_v in received power is exactly cancelled by the 1/cosθ_v in projected source area).
- Applying 1/d² twice (once in the irradiance table, once in code) or not at all.

### (d) Spot checks
| Input | Output |
|---|---|
| λ = 0.55 µm, ρ = 0.3, θ_sun = 30°, E₀ = 1870 W/m²/µm (exo-atm, τ = 1) | **L = 154.647755 W/m²/sr/µm** |
| λ = 0.55 µm, ρ = 0.5, θ_sun = 60°, E₀ = 1870 W/m²/µm | **L = 148.809872 W/m²/sr/µm** |
| Blackbody-sun irradiance cross-check | E(0.55 µm) = **1748.50066 W/m²/µm** (vs 1870 adopted; Ω_sun = 6.79427397×10⁻⁵ sr) |

---

## 7. Graybody Emission and Kirchhoff Constraint

### (a) Governing equations

  **L_emit(λ, T) = ε(λ) · L_planck(λ, T)**  [W/m²/sr/µm], 0 ≤ ε ≤ 1 dimensionless emissivity.

Kirchhoff's law (thermal equilibrium, per wavelength, per direction): **α(λ) = ε(λ)**. Energy balance for an **opaque** surface (transmittance τ = 0): ρ(λ) + α(λ) = 1, hence

  **ε(λ) = 1 − ρ(λ)**

For a non-opaque element: ρ + α + τ = 1 → ε = 1 − ρ − τ. The complete at-surface leaving radiance in the IR is L = ε·L_planck(T_surf) + ρ·L_downwelling, and with ε = 1−ρ the two terms are complementary — high-ε surfaces emit, low-ε surfaces mirror the sky.

### (b) Assumptions / validity
- Kirchhoff requires local thermodynamic equilibrium; valid for essentially all passive-EO scenes (fails for luminescent/lasing media).
- Strictly, ε(λ, θ, φ) = α(λ, θ, φ) holds *per direction*; using hemispherical ε for a directional radiance assumes a diffuse (Lambertian) emitter. Real surfaces (water at grazing angles) have strong directional ε.
- ε independent of T assumed over the range of interest.
- Scene targets/backgrounds: ε is a legitimate independent material input. Optical elements inside the sensor: ε must be *derived* (ε = 1 − R for mirrors) — accepting both R and ε independently over-specifies the energy balance.

### (c) Classic pitfalls
- Using ρ + ε = 1 with the *solar-band* ρ and the *thermal-band* ε — Kirchhoff is spectral; visible albedo says nothing about 10 µm emissivity.
- Forgetting the reflected-downwelling term ρ·L_down, which for ε = 0.95 at LWIR is a ~5% correction — then wondering why measured T_B is biased.
- Applying Kirchhoff to a transparent element with ε = 1 − ρ (missing τ).
- Allowing ε > 1 or ε + ρ > 1 through unvalidated inputs.

### (d) Spot checks
| Input | Output |
|---|---|
| ε = 0.95, λ = 10 µm, T = 300 K | **L = 9.42783166 W/m²/sr/µm** (= 0.95 × 9.92403333) |
| ε = 0.20, λ = 4 µm, T = 300 K | **L = 0.144395285 W/m²/sr/µm** |
| Reflected sky term: ρ = 1−0.95 = 0.05, L_down = 5.0 W/m²/sr/µm | **ρ·L_down = 0.250000000 W/m²/sr/µm** (2.6% of the emitted term above) |

---

## 8. Point Source and Sub-Pixel Regimes

### (a) Governing equations

**Point source.** Spectral intensity I(λ) [W/sr/µm] (for a small Lambertian-emitting facet, I = L·A_t·cosθ). At-aperture spectral irradiance at range R [m] through path transmittance τ_atm(λ) [dimensionless]:

  **E_ap(λ) = I(λ) · τ_atm(λ) / R²**  [W/m²/µm]

Aperture spectral power: Φ(λ) = E_ap·A_ap [W/µm]. This is the inverse-square law; valid when R ≫ source extent.

**Pixel-subtended solid angle.** For ground sample distance GSD [m] at range R [m] (small angle):

  **Ω_pix = GSD² / R²**  [sr]  (= IFOV², with IFOV = GSD/R = p/f)

**Sub-pixel fill fraction.** When target area A_t [m²] < pixel ground footprint A_pix = GSD² [m²]:

  **f = A_t / A_pix**  (dimensionless, 0 < f ≤ 1)

and the pixel-averaged apparent radiance is the area-weighted mix

  L_pix = f·L_target + (1 − f)·L_background.

Equivalently, the target's contribution to aperture irradiance is the point-source result E = L_t·A_t·τ/R², which is f × (the irradiance a full pixel of target radiance would deliver into Ω_pix): L_t·Ω_pix·f·τ. The two routes must agree — that identity is the regime-consistency check.

### (b) Assumptions / validity
- Point-source regime valid when the source's angular extent ≪ IFOV *and* ≪ PSF width; the ensemble of optics blur then spreads the energy per the PSF (ensquared-energy fraction multiplies the in-pixel signal — applied once, downstream).
- Ω = A/R² is the small-angle approximation; exact Ω = 4 arcsin(...) matters only for IFOV ≳ ~0.1 rad, never for imaging sensors.
- Flat, normal-incidence footprint assumed; off-nadir, the ground footprint grows as GSD_x·GSD_y/(cos of incidence) — using nadir GSD² off-nadir underestimates the footprint.
- τ_atm is the path transmittance for the actual slant path, not the vertical column.

### (c) Classic pitfalls
- **Applying both 1/R² and Ω_pix to the same term** — double-counting the geometry. Radiance-based extended-scene math (L·Ω·A_ap) and irradiance-based point-source math (I/R²·A_ap) are alternative routes, never multiplied together.
- Using diameter vs radius or area vs side-length in fill fractions (f = A_t/GSD², not (l_t/GSD)).
- Forgetting the background (1−f) complement — the sub-pixel pixel still sees background radiance in the unfilled area.
- Applying ensquared energy to the background term (background is extended; EE applies to the compact target only).
- τ_atm² (both-way path) sneaking in from radar heritage — passive EO is one-way.
- Sign/units on R: slant range in km fed to a formula expecting m → 10⁶ error in E.

### (d) Spot checks
| Input | Output |
|---|---|
| I = 100 W/sr/µm, τ = 0.7, R = 500 km | **E_ap = 2.80000000 × 10⁻¹⁰ W/m²/µm** |
| I = 2500 W/sr/µm, τ = 0.85, R = 36 000 km (GEO) | **E_ap = 1.63966049 × 10⁻¹² W/m²/µm** |
| GSD = 3 m, R = 500 km | **Ω_pix = 3.60000000 × 10⁻¹¹ sr** (IFOV = 6 µrad) |
| A_t = 1 m², GSD = 3 m | **f = 0.111111111** |

---

## 9. Photon Conversion — Spectral Power to Photoelectron Rate

### (a) Governing equation

Photon energy: **E_photon = hc/λ_m** [J], λ_m = λ·10⁻⁶ [m]. Photoelectron rate from spectral power Φ(λ) [W/µm] at the detector with quantum efficiency QE(λ) [e⁻/photon, dimensionless]:

  **ṅ_e = ∫ QE(λ) · Φ(λ) · (λ·10⁻⁶)/(hc) dλ**  [e⁻/s], integral over λ in µm

The λ/hc factor [photons/J] converts watts to photons/s; the 10⁻⁶ converts λ from µm to m so that λ_m/(hc) has units 1/J. Integrated signal over integration time t_int [s]: N_e = ṅ_e · t_int [e⁻].

### (b) Assumptions / validity
- One photoelectron per absorbed photon, weighted by QE (no avalanche gain; add gain as a separate multiplicative stage).
- λ/hc must stay *inside* the integral — photon energy varies across the band; pulling out a band-center value biases wide bands (for 3–5 µm the edge-to-edge photon-energy ratio is 5/3).
- QE(λ) defined per incident (or per absorbed — be consistent) photon; fill factor and window transmission either inside QE or as separate factors, never both.
- Shot noise follows as √N_e only if N_e is a true photon count — any premature scaling (e.g., applying gain before the noise calc) corrupts Poisson statistics.

### (c) Classic pitfalls
- **The 10⁻⁶**: using λ in µm directly in λ/(hc) → rate high by 10⁶.
- Using E_photon = hν with ν computed from λ in µm → same error, opposite direction.
- Energy-weighted vs photon-weighted band averages confused (QE tables are per-photon; responsivity R = QE·λq/hc is per-energy [A/W] — mixing them double-counts λ).
- Applying t_int inside a "rate" function so downstream multiplies by t_int again.
- 1.60217663×10⁻¹⁹ (electron charge) appearing where it doesn't belong — e⁻ counts are dimensionless counts; charge enters only if converting to amperes.

### (d) Spot checks
| Input | Output |
|---|---|
| E_photon at λ = 0.55 / 4.0 / 10.0 µm | **3.61171974×10⁻¹⁹ / 4.96611464×10⁻²⁰ / 1.98644586×10⁻²⁰ J** |
| Monochromatic Φ = 10⁻¹² W at λ = 4 µm, QE = 0.7 | **ṅ_e = 1.40955264 × 10⁷ e⁻/s** |
| Flat Φ(λ) = 10⁻¹³ W/µm over 3–5 µm, QE = 0.8 (trapz, 2001 pts) | **ṅ_e = 3.22183460 × 10⁶ e⁻/s** |

Sanity: check 2 = 0.7 × 10⁻¹² / 4.96611464×10⁻²⁰ ✓; check 3 equals QE·Φ_λ·(λ̄_photon-weighted)/hc with effective λ = 4.000 µm (flat spectrum, linear λ weight → mean λ = 4 exactly): 0.8·2×10⁻¹³·(4×10⁻⁶)/hc = 3.22183×10⁶ ✓.

---

## 10. BRDF Normalization — Lambertian and Phong

### (a) Governing equations

BRDF definition: f_r(ω_i, ω_o) = dL_o/dE_i [sr⁻¹]. Energy conservation requires the directional-hemispherical reflectance ∫_hemi f_r cos θ_o dΩ_o ≤ 1 for every incidence direction.

**Lambertian:**  **f_r = ρ/π**  [sr⁻¹], ρ [dimensionless] the albedo. The π (not 2π) arises because the projected-solid-angle integral over the hemisphere is ∫ cos θ dΩ = π, so ∫ (ρ/π) cos θ dΩ = ρ ≤ 1 exactly.

**Normalized Phong specular lobe** (lobe about the mirror direction, α = angle between view and mirror reflection [rad], n ≥ 0 shininess):

  **f_r,spec = ρ_s · (n + 2)/(2π) · cosⁿ α**  [sr⁻¹]

The (n+2)/(2π) normalization comes from ∫_hemi cosⁿα · cos θ dΩ evaluated with the lobe centered on the normal (α = θ): 2π ∫₀^{π/2} cos^{n+1}θ sin θ dθ = 2π/(n+2). Hence the factor (n+2)/(2π) makes the lobe integrate to exactly ρ_s at normal incidence, guaranteeing ρ_s + ρ_d ≤ 1 suffices for energy conservation there. (The weaker (n+1)/(2π) variant normalizes ∫ cosⁿα dΩ without the cos θ throughput factor — it conserves *lobe solid-angle weight*, not reflected *energy*, and can over-reflect by up to (n+2)/(n+1).)

### (b) Assumptions / validity
- Lambertian: view-independent radiance; exact energy conservation for any ρ ≤ 1.
- Phong: phenomenological, not physical (no reciprocity in the classic form; no Fresnel dependence). The (n+2)/(2π) normalization is exact only when the mirror direction coincides with the normal; at grazing incidence part of the lobe falls below the horizon and the *actual* reflected fraction is < ρ_s (energy is lost, never gained — conservative but biased).
- n → ∞ approaches a mirror; n = 1 is a broad gloss. For rendering-grade physics use microfacet models; Phong is adequate for glint-order-of-magnitude budgets.

### (c) Classic pitfalls
- **ρ instead of ρ/π** for Lambertian BRDF (off by π ≈ 3.14159 in every reflected radiance) — the single most common radiometry bug in existence; or ρ/(2π) from confusing hemisphere solid angle 2π with projected solid angle π.
- Using (n+1)/(2π) where energy normalization (n+2)/(2π) is intended, or vice versa without documenting which convention.
- Measuring α from the normal instead of from the mirror-reflection direction.
- Forgetting cosⁿα must clamp at α > π/2 (cosⁿ of negative cos with odd n goes negative — negative radiance).
- Adding a Lambertian *radiance* term to a Phong *BRDF* term (unit mismatch: one already has the 1/π folded into a radiance, the other is sr⁻¹).

### (d) Spot checks (numeric hemispherical integrals, adaptive quadrature)
| Check | Result |
|---|---|
| Lambertian, ρ = 0.3: ∫ f_r cos θ dΩ | **0.300000000** (= ρ ✓) |
| Phong (n+2)/(2π), n = 1, normal incidence: ∫ f_r,spec cos θ dΩ / ρ_s | **1.00000000** ✓ |
| Phong, n = 10 | **1.00000000** ✓ |
| Phong, n = 100 | **1.00000000** ✓ |

---

## Requested Anchor Summary (for direct comparison against implementation)

| Anchor | Value |
|---|---|
| L(10 µm, 300 K) | **9.92403333 W/m²/sr/µm** |
| L(4 µm, 300 K) | **0.721976423 W/m²/sr/µm** |
| ∂L/∂T (10 µm, 300 K) | **0.159971567 W/m²/sr/µm/K** |
| T_rad(10 µm, L = 9.0 W/m²/sr/µm) | **294.054730 K** |
| L_refl(0.55 µm, ρ = 0.3, θ_sun = 30°, E₀ = 1870 W/m²/µm exo-atm) | **154.647755 W/m²/sr/µm** — note this value scales linearly with the adopted E₀; if the implementation uses a different solar table (e.g., 1859 W/m²/µm from E490 tabulation), rescale by E₀_impl/1870 before comparing |
| 8–12 µm band-integrated L(300 K) | **38.5004239 W/m²/sr** (band-avg 9.62510598 W/m²/sr/µm) |

Computation notes: all analytic derivatives verified against central finite differences (≤ 3×10⁻¹⁰ relative); all inversions verified by round-trip through the forward model (≤ 10⁻⁹ relative).
