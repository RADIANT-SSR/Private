# Radiometric Model — Mixed Refractive and Reflective Optical Train

**This appendix is an implementation recipe, and it is written like one.** The chapters
before it state each equation with its derivation, its validity limits and a pinned
numeric anchor; this appendix instead gives the quantities in the order a program must
compute them, in the ASCII notation the implementation uses, so that a reader working
through the code can follow it line for line. There are no derivations or pitfalls
sections here, and the equation blocks are deliberately not typeset as display
mathematics — they are the recipe, not the physics. The physics they assemble is in the
radiometric-chain and spatial chapters.

Two separate radiometric paths are modeled:

1. **Signal path** — transmission/reflection of source photons through the full optical train
2. **Thermal background path** — self-emission of each optical element propagated to the focal plane

Elements are typed as either `REFRACTIVE` or `REFLECTIVE`. The per-element equations
differ fundamentally between the two types.

---

## Element types and their radiometric character

### Refractive element (lens, window, filter, beamsplitter substrate)

- Signal passes **through** the element
- Has bulk absorption (Beer-Lambert), entry and exit surface coatings
- System quantity is **transmittance** `T_sys,i(λ)`
- Thermal emission sourced from **bulk substrate + both surfaces**
- Cavity etalon effect between R1 and R2

### Reflective element (mirror, cold stop, baffle)

- Signal **reflects off** the element
- No bulk propagation — surface interaction only
- System quantity is **reflectance** `Rho_sys,i(λ)`
- Thermal emission sourced from **surface coating only**
- No etalon — single surface interaction
- Emissivity governed by Kirchhoff: `eps_i(λ) = 1 − Rho_sys,i(λ) − A_coat,i(λ)`
  where `A_coat,i` is the coating absorption (if known); if not: `eps_i = 1 − Rho_sys,i`

---

## Per-element radiometric quantities

### 1.1 Refractive element i

**This is a first-order model: one interaction per surface.** A ray meets surface 1
once and surface 2 once; the beam reflected back off surface 2 leaves through surface 1
without reflecting again. That second reflection begins the internal bounce series,
whose closed form is the Airy denominator `1 − R1·R2·beer²`. Summing it is a
higher-order term and is out of scope — the justification is the **order of the model**,
not the geometry of the element (owner ruling 2026-10-04, CU-398). Whether a given lens
is curved, wedged or plane-parallel, and at what ray angles, is detailed ray tracing
that RADIANT neither performs nor represents, so it cannot be what selects the formula.
This applies to every refractive element without exception; there is no plane-parallel
opt-in.

```
beer_i(λ)    = exp(−alpha_i(λ) · d_i)

T_sys,i(λ)   = T1_i(λ) · beer_i(λ) · T2_i(λ)

R_sys,i(λ)   = R1_i(λ) + T1_i(λ) · R2_i(λ) · beer_i(λ)²          (entering side 1)
R_side2,i(λ) = R2_i(λ) + T2_i(λ) · R1_i(λ) · beer_i(λ)²          (entering side 2)

eps_eff,i(λ) = T2_i(λ) · (1 − beer_i(λ)) · (1 + R1_i(λ) · beer_i(λ))

L_thermal,i(λ) = eps_eff,i(λ) · B(λ, T_i)
```

`R_sys` carries a single `T1`, where a truncated bounce series would carry `T1²`: with
no second bounce the ghost reflected off surface 2 exits surface 1 **in full**, rather
than leaving an `R1` share behind to keep bouncing. That is what makes the energy
identity close exactly —

```
T_sys,i(λ) + R_side2,i(λ) + eps_eff,i(λ) = 1       ← holds at each λ, to 2.2e-16
```

— and it is `R_side2`, not `R_sys`, that appears in it. The two coincide only for
symmetric coatings (`R1 == R2`); a "simplification" to `R_sys` silently reintroduces an
error on every asymmetric element, which is the common real case.

The `beer` factor above has no `/ cos(theta_r,i)` refraction-angle path lengthening.
RADIANT works at near-normal incidence: at f/2 the marginal ray inside germanium
(n = 4) refracts to 3.5°, so `cos theta_r = 0.998` and the path error is 0.2 %, below
the model's own data uncertainty. The doc previously specified the `cos` term while the
code never implemented it.


> **Corrected 2026-10-04 (CU-396).** This expression carried an `n_i(λ)²` factor in the
> numerator until that date. The reasoning was that the photon density of states inside
> a dielectric is enhanced by n² — which it is — but radiance is not invariant across a
> refracting surface (L/n² is), so the compensating 1/n² de-magnification on escape
> cancels it exactly. Keeping one without the other overstated refractive-element
> emissivity by ~n²: **15.8× for germanium** at 10.6 µm, 11.6× for silicon. The giveaway
> was that the result could exceed 1 and was being clipped in `optics/element.py` — a
> surface emitting more than a blackbody is a second-law violation, not a rounding
> artifact. This document stated **both** the n² form here and the energy-conservation
> check below, which are mutually exclusive for n > 1; the check was right.

The element **transfer factor** applied to upstream signals passing through it:

```
C_i(λ) = T_sys,i(λ)          [refractive — transmission]
```

### 1.2 Reflective element i

No bulk absorption. Single surface interaction. The coating has reflectance `Rho_i(λ)`
and absorptance `A_coat,i(λ)`. Transmittance is zero (opaque mirror).

```
Rho_sys,i(λ)   = Rho_i(λ)                    [mirror reflectance]

eps_i(λ)       = 1 − Rho_i(λ) − A_coat,i(λ)  [surface emissivity via Kirchhoff]
```

If coating absorptance is not separately characterized, conservative form:

```
eps_i(λ)       = 1 − Rho_i(λ)                [upper bound on emissivity]
```

Thermal radiance from the mirror surface:

```
L_thermal,i(λ) = eps_i(λ) · B(λ, T_i)
```

The element **transfer factor** applied to upstream signals reflecting off it:

```
C_i(λ) = Rho_sys,i(λ)        [reflective — reflectance]
```

### 1.3 Planck blackbody radiance (common to both types)

```
B(λ, T_i) =         2 h c²  /  λ⁵
             ─────────────────────────────────
             exp(h c / λ k_B T_i)  −  1
```

Constants are the CODATA 2018 values of the Notation chapter's physical-constants
table; they are defined once in the code and never re-entered here.

`B` is a **per-wavelength** spectral radiance in W/m²/sr/µm. Evaluate the expression
above with `λ` in meters and it returns W/m²/sr/m; the per-µm form used everywhere in
this manual carries the Jacobian factor 10⁻⁶ that converts the spectral density from
per-meter to per-micrometer. Mixing the two is the single most common radiometry error.

---

## Signal path through the full optical train

### 2.1 Cascaded system transfer

Each element applies its transfer factor `C_i(λ)` — either `T_sys,i` or `Rho_sys,i`
depending on type. The total signal transfer from source to focal plane is:

```
C_total(λ) = ∏ C_i(λ)    for i = 1 to N
```

Explicitly for a mixed train of N elements:

```
C_total(λ) = C_1(λ) · C_2(λ) · C_3(λ) · ... · C_N(λ)
```

Where each `C_i` is either `T_sys,i` (refractive) or `Rho_sys,i` (reflective).

### 2.2 Signal irradiance at the focal plane

```
E_signal,FP(λ) = π · L_source(λ) · sin²(θ_FP) · C_total(λ)
```

Or equivalently using f-number:

```
E_signal,FP(λ) =    π · L_source(λ) · C_total(λ)
                 ────────────────────────────────────
                 4 · (f/#)² · (1 + M)²
```

### 2.3 Total in-band signal irradiance

```
E_signal,total = ∫[λ1 to λ2]  E_signal,FP(λ) dλ
```

---

## Thermal background path from each element

Each element `i` emits thermal radiation that propagates through all downstream
elements `j > i` before reaching the focal plane.

### 3.1 Downstream cumulative transfer from element i to focal plane

The thermal emission from element `i` is transferred by every downstream element
using that element's transfer factor `C_j(λ)`:

```
tau_i(λ) = ∏ C_j(λ)    for j = i+1 to N
```

Note: `C_j` is `T_sys,j` if element j is refractive, `Rho_sys,j` if reflective.
Downstream reflective elements both redirect **and** attenuate the upstream thermal flux.

For the last element: `tau_N(λ) = 1.0`

Explicitly for a 4-element train:

```
tau_1(λ) = C_2 · C_3 · C_4
tau_2(λ) = C_3 · C_4
tau_3(λ) = C_4
tau_4(λ) = 1.0
```

### 3.2 The acceptance cone — one geometry for every element

The Lagrange invariant caps how much solid angle the focal plane can accept from an
in-beam element. Whatever the internal layout, each element is seen through the
reimaging optics and can fill at most the cone the working f-number sets:

```
Omega_cone = 2 · π · (1 − cos(theta)),    theta = arctan(1 / (2 · N_eff))
```

Where:
- `N_eff` = effective (post-cold-stop) f-number, `f / D_eff`
- `theta` = half-angle of the marginal ray

The exact form is used rather than the paraxial `π / (4 · N_eff²)`: the two agree to
0.5 % at f/6 and 5 % at f/2, and the paraxial form over-states the cone, exceeding
2·π as `N_eff` → 0, which no solid angle may do.

There is **no per-element geometry**. An element does not gain acceptance by sitting
close to the focal plane: a private `Omega_i = π (D_i/2)² / z_i²` is not bounded by the
invariant — a 0.3 m mirror 1.0 m from the focal plane would claim 0.0707 sr against an
f/6 cone of 0.0217 sr, 3.2× more than physics permits. Nor is there a cold-stop
attenuation factor: in-cone emission arrives through the imaging path itself and cannot
be blocked, while out-of-cone warm structure is taken to be blocked completely. What a
cold stop does control is the size of the pupil, hence `N_eff`, hence `Omega_cone`.

### 3.3 Focal plane irradiance from each element

Every element, last or upstream, emits as a graybody into that one cone, attenuated by
everything downstream of it:

```
E_FP,i(λ) = Omega_cone · L_thermal,i(λ) · tau_i(λ)
```

Fully expanded:

**Refractive element i:**

```
E_FP,i(λ) =  Omega_cone · eps_eff,i(λ) · B(λ, T_i)
           ·  ∏[j=i+1 to N] C_j(λ)
```

**Reflective element i:**

```
E_FP,i(λ) =  Omega_cone · eps_i(λ) · B(λ, T_i)
           ·  ∏[j=i+1 to N] C_j(λ)
```

The structure is identical — only the emissivity model differs between the two types.
The last element is not a special case: `tau_N = 1`, so it contributes
`Omega_cone · L_thermal,N(λ)`.

Dimensionally, sr × [--] × W/m²/sr/µm × [--] = W/m²/µm, the spectral irradiance the
focal plane sees.

### 3.4 Total thermal background irradiance at the focal plane

```
E_background,FP(λ) = ∑[i=1 to N] E_FP,i(λ)
```

Total in-band thermal background:

```
E_background,total = ∫[λ1 to λ2]  E_background,FP(λ) dλ
```

---

## Combined focal plane irradiance

```
E_FP,total(λ) = E_signal,FP(λ)  +  E_background,FP(λ)
```

Signal-to-background ratio:

```
SBR(λ) = E_signal,FP(λ) / E_background,FP(λ)
```

---

## Kirchhoff self-consistency check

### Refractive element i

System reflectance (accounting for cavity):

```
R_sys,i(λ) =  R1_i  +  T1_i² · R2_i · beer_i²
              ─────────────────────────────────
              1 − R1_i · R2_i · beer_i²
```

Check:

```
A_total,i(λ) = 1 − R_side2,i(λ) − T_sys,i(λ)
eps_eff,i(λ) =  A_total,i(λ)                  ← holds exactly, at each λ

where  R_side2,i = R2_i + T2_i² · R1_i · beer_i² / denom_i
```

**Note the side.** `R_sys,i` as defined above is the **side-1** reflectance (illuminate
the entry face). Emission toward the focal plane leaves through surface 2, so the
identity is against the **side-2** reflectance. The two coincide only for symmetric
coatings (R1 = R2); writing `1 − R_sys − T_sys` is correct for those and wrong for every
asymmetric element, which is the common real case.

### Reflective element i

```
A_total,i(λ) = 1 − Rho_sys,i(λ) − A_coat,i(λ)   [if A_coat known]
             = 1 − Rho_sys,i(λ)                   [conservative bound]
eps_i(λ)     ≈ A_total,i(λ)                       ← must hold at each λ
```

---

## Implementation recipe

```
Inputs per element i:

  type_i = REFRACTIVE or REFLECTIVE

  If REFRACTIVE:
    R1_i(λ), T1_i(λ)       entry surface coating
    R2_i(λ), T2_i(λ)       exit surface coating
    alpha_i(λ)              bulk absorption coefficient
    n_i(λ)                  refractive index
    d_i                     substrate thickness
    T_i                     temperature
    theta_r,i               refracted angle inside substrate

  If REFLECTIVE:
    Rho_i(λ)               surface reflectance
    A_coat,i(λ)            coating absorptance (optional; 0 if unknown)
    T_i                     temperature

  System geometry (all elements — one cone, not one per element):
    theta_FP               focal plane convergence half-angle
    N_eff                  effective (post-cold-stop) f-number
    Omega_cone             2 · pi · (1 − cos(arctan(1 / (2 · N_eff))))  [sr]

─────────────────────────────────────────────────────────
Per element, compute transfer factor C_i and emissivity:

  If REFRACTIVE (first order — one interaction per surface, CU-398):
    beer_i    = exp(−alpha_i · d_i)
    C_i       = T1_i · beer_i · T2_i                 [transmittance]
    eps_i     = T2_i · (1 − beer_i) · (1 + R1_i · beer_i)  [cavity emissivity]

  If REFLECTIVE:
    C_i       = Rho_i                                  [reflectance]
    eps_i     = 1 − Rho_i − A_coat,i                  [surface emissivity]

  Both types:
    L_i(λ)   = eps_i(λ) · B(λ, T_i)

─────────────────────────────────────────────────────────
Signal path:

  C_total(λ) = ∏ C_i(λ)    for i = 1 to N
  E_signal(λ) = π · L_source(λ) · sin²(θ_FP) · C_total(λ)

─────────────────────────────────────────────────────────
Thermal background path (build tau as reverse cumulative product):

  tau_N     = 1.0
  tau_i     = ∏ C_j(λ)    for j = i+1 to N   [reverse cumulative product]

  For i = 1 to N:
    E_FP,i(λ) = Omega_cone · L_i(λ) · tau_i(λ)

  E_background(λ) = ∑[i=1 to N] E_FP,i(λ)

─────────────────────────────────────────────────────────
Total:

  E_FP,total(λ) = E_signal(λ) + E_background(λ)
  SBR(λ)        = E_signal(λ) / E_background(λ)

─────────────────────────────────────────────────────────
Validation:

  Refractive:  eps_eff,i ≈ 1 − R_sys,i − T_sys,i   for each optic
  Reflective:  eps_i     ≈ 1 − Rho_i − A_coat,i    for each mirror
```

---

## Key physical distinctions summary

| Property                  | Refractive element         | Reflective element          |
|---------------------------|----------------------------|-----------------------------|
| Signal transfer factor    | `T_sys,i` (transmittance)  | `Rho_sys,i` (reflectance)   |
| Bulk emission             | Yes — Beer-Lambert path    | No                          |
| Surface emission          | Exit face (via T2)         | Single surface only         |
| Cavity / etalon effect    | Yes — R1·R2 denominator    | No                          |
| Emissivity model          | Full cavity eps_eff        | Kirchhoff: 1 − Rho − A_coat |
| Downstream attenuation    | `T_sys,j` per element      | `Rho_sys,j` per element     |
| Sensitive to temperature  | Bulk + surface             | Surface only                |
| Dominant in cold systems  | Windows, filters           | Warm fold mirrors           |
