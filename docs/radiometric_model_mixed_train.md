# Radiometric model — mixed refractive and reflective optical train

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

## Part 1 — Per-element radiometric quantities

### 1.1 Refractive element i

```
beer_i(λ)    = exp(−alpha_i(λ) · d_i / cos(theta_r,i))
denom_i(λ)   = 1 − R1_i(λ) · R2_i(λ) · beer_i(λ)²

T_sys,i(λ)   =      T1_i(λ) · beer_i(λ) · T2_i(λ)
               ──────────────────────────────────────
               1 − R1_i(λ) · R2_i(λ) · beer_i(λ)²

eps_eff,i(λ) =   T2_i(λ) · n_i(λ)² · (1 − beer_i(λ))
               ──────────────────────────────────────────
               1 − R1_i(λ) · R2_i(λ) · beer_i(λ)²

L_thermal,i(λ) = eps_eff,i(λ) · B(λ, T_i)
```

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

Constants: `h = 6.626e-34` J·s, `c = 2.998e8` m/s, `k_B = 1.381e-23` J/K

---

## Part 2 — Signal path through the full optical train

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

## Part 3 — Thermal background path from each element

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

### 3.2 Geometric transfer factor

For upstream element `i`, only emission intercepted by the downstream limiting
aperture reaches the focal plane:

```
G_i = A_stop,i · cos(θ_i)
      ─────────────────────
            z_i²
```

Where:
- `A_stop,i` = area of the first downstream limiting aperture (stop or clear aperture)
- `z_i`      = distance from element `i` to that aperture
- `θ_i`      = on-axis angle (= 0 for paraxial systems)

### 3.3 Focal plane irradiance from each element

**Last element N** (fills full focal plane cone):

```
E_FP,N(λ) = π · L_thermal,N(λ) · sin²(θ_FP)
```

This applies regardless of whether element N is refractive or reflective —
both fill the focal plane cone by definition as the last element.

**Upstream elements i = 1 to N-1:**

```
E_FP,i(λ) = L_thermal,i(λ) · G_i / A_FP  ·  tau_i(λ)
```

Fully expanded:

**Refractive element i:**

```
E_FP,i(λ) =  eps_eff,i(λ) · B(λ, T_i)
           ·  A_stop,i · cos(θ_i) / (z_i² · A_FP)
           ·  ∏[j=i+1 to N] C_j(λ)
```

**Reflective element i:**

```
E_FP,i(λ) =  eps_i(λ) · B(λ, T_i)
           ·  A_stop,i · cos(θ_i) / (z_i² · A_FP)
           ·  ∏[j=i+1 to N] C_j(λ)
```

The structure is identical — only the emissivity model differs between the two types.

### 3.4 Total thermal background irradiance at the focal plane

```
E_background,FP(λ) = E_FP,N(λ)  +  ∑[i=1 to N-1] E_FP,i(λ)
```

Total in-band thermal background:

```
E_background,total = ∫[λ1 to λ2]  E_background,FP(λ) dλ
```

---

## Part 4 — Combined focal plane irradiance

```
E_FP,total(λ) = E_signal,FP(λ)  +  E_background,FP(λ)
```

Signal-to-background ratio:

```
SBR(λ) = E_signal,FP(λ) / E_background,FP(λ)
```

---

## Part 5 — Kirchhoff self-consistency check

### Refractive element i

System reflectance (accounting for cavity):

```
R_sys,i(λ) =  R1_i  +  T1_i² · R2_i · beer_i²
              ─────────────────────────────────
              1 − R1_i · R2_i · beer_i²
```

Check:

```
A_total,i(λ) = 1 − R_sys,i(λ) − T_sys,i(λ)
eps_eff,i(λ) ≈ A_total,i(λ)                   ← must hold at each λ
```

### Reflective element i

```
A_total,i(λ) = 1 − Rho_sys,i(λ) − A_coat,i(λ)   [if A_coat known]
             = 1 − Rho_sys,i(λ)                   [conservative bound]
eps_i(λ)     ≈ A_total,i(λ)                       ← must hold at each λ
```

---

## Part 6 — Implementation recipe

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

  System geometry (all elements):
    theta_FP               focal plane convergence half-angle
    z_i                    distance from element i to limiting downstream aperture
    A_stop,i               area of limiting downstream aperture for element i
    A_FP                   detector / pixel area

─────────────────────────────────────────────────────────
Per element, compute transfer factor C_i and emissivity:

  If REFRACTIVE:
    beer_i    = exp(−alpha_i · d_i / cos(theta_r,i))
    denom_i   = 1 − R1_i · R2_i · beer_i²
    C_i       = T1_i · beer_i · T2_i / denom_i       [transmittance]
    eps_i     = T2_i · n_i² · (1 − beer_i) / denom_i [cavity emissivity]

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

  E_FP,N(λ) = π · L_N(λ) · sin²(θ_FP)

  For i = 1 to N-1:
    E_FP,i(λ) = L_i(λ) · A_stop,i · cos(θ_i) / (z_i² · A_FP) · tau_i(λ)

  E_background(λ) = E_FP,N(λ) + ∑ E_FP,i(λ)

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

## Part 7 — Key physical distinctions summary

| Property                  | Refractive element         | Reflective element          |
|---------------------------|----------------------------|-----------------------------|
| Signal transfer factor    | `T_sys,i` (transmittance)  | `Rho_sys,i` (reflectance)   |
| Bulk emission             | Yes — Beer-Lambert path    | No                          |
| Surface emission          | Both surfaces (via T2, n²) | Single surface only         |
| Cavity / etalon effect    | Yes — R1·R2 denominator    | No                          |
| Emissivity model          | Full cavity eps_eff        | Kirchhoff: 1 − Rho − A_coat |
| Downstream attenuation    | `T_sys,j` per element      | `Rho_sys,j` per element     |
| Sensitive to temperature  | Bulk + surface             | Surface only                |
| Dominant in cold systems  | Windows, filters           | Warm fold mirrors           |
