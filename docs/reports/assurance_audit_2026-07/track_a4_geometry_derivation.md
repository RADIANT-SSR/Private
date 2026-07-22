# Track A4 — Blind Re-Derivation: Geometry / Sampling / Kinematics

Status: Complete (derivation phase)
Produced by: blind-derivation agent (no access to src/ or docs/), 2026-07-22.
Comparison against implementation: see findings.md.

---

# Blind Re-Derivation Report — RADIANT Geometry / Sampling / Kinematics Audit

**Method statement.** Produced without reading any file under `src/` or `docs/`. Derived from first principles (spherical trigonometry, two-body circular orbital mechanics, paraxial imaging). Numerics: R = 6378.137 km (WGS-84 equatorial), mean radius R_m = 6371.0 km noted where it matters, µ = 3.986004418e14 m³/s². Internal units: radians, meters, seconds.

**Symbols:** R Earth radius; h altitude; η look/off-nadir angle at satellite; Λ Earth central angle; ε grazing/elevation angle at target; θ_i incidence angle at target (θ_i = π/2 − ε); R_s slant range; p pixel pitch; f focal length; IFOV = p/f.

---

## 1. The Viewing Triangle

**(a)** Triangle C (Earth center) – S (satellite) – T (target): CT = R, CS = R+h, ST = R_s. Interior angles: η at S, Λ at C, π/2 + ε at T. Closure: η + Λ + ε = π/2, i.e. **Λ = θ_i − η**.
Law of sines: R_s/sin Λ = R/sin η = (R+h)/cos ε. Load-bearing identity:

**sin θ_i = cos ε = ((R+h)/R)·sin η**

Closed-form solution sets:
- Given h, η (η ≤ η_max = asin(R/(R+h))): θ_i = asin((R+h)/R·sin η); ε = π/2 − θ_i; Λ = θ_i − η; R_s = (R+h)cos η − √(R² − (R+h)²sin²η).
- Given h, ε: η = asin(R/(R+h)·cos ε) (branch-safe, η < π/2 always); Λ = π/2 − η − ε.
- Given h, Λ (Λ ≤ acos(R/(R+h))): η = atan2(R sin Λ, (R+h) − R cos Λ) (exact, branch-safe); ε = π/2 − η − Λ.

**(b)** Spherical Earth, surface target, no refraction (refraction lifts apparent elevation up to ~0.5° at ε≈0), coplanar.

**(c) Pitfalls.** asin branch: the factor is the *amplifying* (R+h)/R (θ_i > η always on a sphere); R/(R+h) belongs only in the ε→η direction. θ_i vs ε vs η conflation (flat-earth θ_i = η is wrong). Degrees into radian trig. Λ = θ_i − η, not η − θ_i.

**(d) Spot checks** (h = 500 km, η = 30°): **θ_i = 32.628951°, ε = 57.371049°, Λ = 2.628951°**; ground arc R·Λ = 292.653 km. Law-of-sines ratios identical to 12 digits (12,756,274.000 m). Mean-radius variant: θ_i = 32.631938°.

## 2. Slant Range

**(a)** Law of cosines: R_s² = R² + (R+h)² − 2R(R+h)cos Λ. Direct form:

**R_s = (R+h)cos η − √(R² − (R+h)²sin²η)**

**Sign:** minus root = near intersection (visible surface); plus root = far-side exit, never physical. **Discriminant** negative ⇔ sin η > R/(R+h) ⇔ looking above the limb. Boundary: η_max = asin(R/(R+h)), ε = 0, R_s(η_max) = √(2Rh + h²) (tangent ray).

**(c) Pitfalls.** Plus root (at nadir gives ~11.3 Mm instead of h); silent NaN on negative discriminant instead of actionable beyond-horizon error; R for (R+h) inside the discriminant (silently wrong off-nadir). Near η_max, dR_s/dη → ∞ — solvers should re-parameterize in Λ or ε there.

**(d) Spot checks.** h = 500 km, η = 30°: **R_s = 585,101.608073 m** (both forms agree to 2.3e-10 m). Mean radius: 585,110.538 m (+8.9 m). Horizon: R_s = 2,574,516.848 m.

## 3. Degenerate Cases

Nadir η = 0: R_s = h exactly; small-η expansion R_s ≈ h(1 + η²(R+h)/(2R)). Horizon ε = 0: η_max + Λ_max = π/2 identically; θ_i = 90°, 1/cos θ_i factors diverge (GSD → ∞, correctly). Pitfalls: division by sin η at nadir (use atan2); float-equality nadir tests. Checks: η = 1e-4 rad → R_s = 500,000.002696 m, matches expansion to sub-mm. **η_max(500 km) = 68.018674°**; horizon ground distance 2446.950 km.

## 4. Circular Orbit Kinematics

**(a)** v = √(µ/(R+h)); T = 2π√((R+h)³/µ); ω = v/(R+h); **v_g = ω·R = v·R/(R+h)**.
The R/(R+h) factor: satellite and nadir point share angular rate ω; linear speed = ω × circle radius (R+h vs R). Projection of angular motion, not vector projection.

**(b)** Two-body, no J₂ (~0.1% LEO period effect); circular; **non-rotating Earth** for v_g (Earth rotation adds up to ±465·cos(lat) m/s — ~6.6% at the equator — that a smear model must eventually book).

**(c) Pitfalls.** √(µ/R) instead of √(µ/(R+h)) (3.8% at 500 km); orbital v where ground v_g belongs (smear/line rate: +7.84% at 500 km); µ km³/s² mixed with meters.

**(d) Spot checks** (h = 500 km): **v = 7612.608173 m/s; T = 5676.978 s = 94.6163 min; v_g = 7059.216450 m/s**. Mean radius: v = 7616.561 m/s, T = 94.4691 min (8.8 s period difference — baselines must state R).

## 5. GSD (Nadir and Off-Nadir)

**(a)** IFOV = p/f. Nadir: GSD = (p/f)·h. Off-nadir, project beam width w = IFOV·R_s (⊥ to LOS) onto local tangent plane; the LOS makes angle **θ_i (incidence at target, NOT look angle η)** with the surface normal:

**GSD_in-plane (cross-track for cross-track pointing) = IFOV·R_s/cos θ_i**
**GSD_out-of-plane (along-track) = IFOV·R_s**

The out-of-plane horizontal direction is itself ⊥ to the LOS (normal to the C-S-T plane), so projection is length-preserving — the 1/cos θ_i applies in-plane only. Exactness on the sphere: differentiating Λ(η) gives R·dΛ/dη = R_s/cos θ_i (exact identity via law of sines) — IFOV·R_s/cos θ_i is the exact spherical cross-track GSD. For an along-track-tilted sensor the roles swap.

**(c) Pitfalls.** cos η vs cos θ_i (2.75% at η = 30°, h = 500 km; unbounded toward the limb). cos vs 1/cos (GSD must *grow* off-nadir). Applying 1/cos θ_i to both directions (another 19% area error at this geometry). Single-number off-nadir "GSD" without direction stated.

**(d) Spot checks** (p = 10 µm, f = 2 m): nadir h = 500 km: **GSD = 2.500000 m**. η = 30°: **along-track 2.925508 m, cross-track 3.473732 m** (wrong-angle /cos η gives 3.378086 m, 2.75% low). Numerical spherical differencing confirms 3.473732 m to 4e-10 m.

## 6. Swath Width

**(a)** W = R·[Λ(η_half,right) + Λ(η_half,left)] with Λ(η) = asin((R+h)/R·sin η) − η; symmetric W = 2R·Λ(η_half). Flat-earth limit W → 2h·tan η_half → h·FOV.

**(b)** Nadir-centered symmetric FOV; off-nadir-pointed use R·[Λ(η_c+η_half) − Λ(η_c−η_half)] (wider, asymmetric). Arc vs chord: Λ²/24 relative, negligible below ~10°.

**(c) Pitfalls.** Flat-earth 2h·tan at wide angles (0.29% low at ±15°, diverges beyond ~30°); W = 2R_s·η_half (mixes projections); no beyond-horizon clamp to Λ_max.

**(d) Spot checks** (h = 500 km): η_half = 15°: Λ = 1.207010°, **W = 268.727 km** (flat: 267.949 km, spherical 0.29% wider). η_half = 1°: ratio 1.0000123 (quadratic convergence).

## 7. Image-Plane Smear During Integration

**(a)** d_img = v_img·t_int. Nadir pushbroom uncompensated: d_ground = v_g·t_int; **d_img = d_ground·f/R_s** (= v_g·t_int·f/h at nadir; f/R_s is the paraxial magnification). TDI line-rate matching: **p·f_line = v_img = v_g·f/h ⇔ f_line = v_g/GSD ⇔ t_line = GSD/v_g**. Residual per-stage smear |v_img − p·f_line|·t_line; N stages multiply rate-mismatch smear by N.

**(b)** Nadir-looking; rigid focal plane; constant v_img over t_int; non-rotating Earth (±6.6% direction-dependent).

**(c) Pitfalls.** Orbital v instead of v_g (**+7.84% at 500 km** — corrupts an MTF budget while looking plausible); f/R or f/(R+h) instead of f/R_s; ground-meters vs focal-plane-µm without f/R_s; t_int vs t_line conflation in TDI (t_int = N·t_line; the matching condition constrains t_line).

**(d) Spot checks** (h = 500 km, p = 10 µm, f = 2 m, t_int = 1 ms): d_ground = 7.059216 m; **d_img = 28.2369 µm = 2.8237 pixels**. TDI: f_line = 2823.6866 Hz, t_line = 354.1470 µs (two routes identical). Wrong-velocity inflation = 7.8393% = h/R exactly.

## 8. Solar Geometry

**(a)** **cos θ_z = sin φ·sin δ + cos φ·cos δ·cos H** (φ latitude +N, δ declination ±23.44° solstices, H hour angle, 0 at solar noon, +15°/h).

**(b)** No refraction (~0.57° at horizon); H is apparent solar time (equation of time ±16 min ≈ ±4° in H).

**(c) Pitfalls.** Degrees into radian trig; clock time vs solar time; sign conventions on δ; elevation returned where zenith expected (sin/cos swap downstream).

**(d) Spot checks.** φ = 35°N, δ = 23.44°, H = 15°: **θ_z = 17.425559°** (elevation 72.574°). Noon: θ_z = φ − δ = 11.56° exactly. H = 90°: θ_z = 76.811°.

## 9. Sampling: Nyquist and Q

**(a)** f_Nyq = 1/(2p) at focal plane; ground-projected Nyquist = 1/(2·GSD) (direction-dependent off-nadir). Incoherent diffraction cutoff f_c = 1/(λF#). **Q = λF#/p; f_cutoff/f_Nyq = 2/Q.** Q = 2 critically sampled (cutoff = Nyquist, zero aliasing); Q < 2 aliased; Q > 2 oversampled.

**(c) Pitfalls.** 1/p (sampling) vs 1/(2p) (Nyquist); double ground-projection with R_s when GSD already contains it; Q-convention confusion (state f_cutoff/f_Nyq = 2/Q); coherent cutoff 1/(2λF#) off by 2.

**(d) Spot checks** (p = 10 µm, f = 2 m): f_Nyq = **50.000 cy/mm**; ground Nyquist at 500 km = 0.2 cy/m. λ = 0.55 µm, F# = 4: Q = 0.22, f_c/f_Nyq = 9.09 = 2/Q ✓. Q = 2 at λ = 0.55 µm, p = 10 µm needs F# = 36.36.

## 10. Euler ZYX (Yaw–Pitch–Roll)

**(a)** Intrinsic z–y′–x″ (yaw ψ, pitch θ, roll φ): **R = R_z(ψ)·R_y(θ)·R_x(φ)** (active, column vectors, right-handed):

```
⎡ cψcθ    cψsθsφ − sψcφ    cψsθcφ + sψsφ ⎤
⎢ sψcθ    sψsθsφ + cψcφ    sψsθcφ − cψsφ ⎥
⎣ −sθ         cθsφ              cθcφ      ⎦
```

Extraction: θ = −asin(R₃₁), ψ = atan2(R₂₁, R₁₁), φ = atan2(R₃₂, R₃₃); gimbal lock at θ = ±90°.

**(b)** Must pin all three of {active/passive, intrinsic/extrinsic, order}. Matches scipy `Rotation.from_euler('ZYX', ...)` exactly.

**(c) Pitfalls.** Intrinsic z-y′-x″ = extrinsic x-y-z (same product) but ≠ intrinsic x-y′-z″; transpose (active/passive) errors; R_y sign placement (+sθ top-right); degrees/radians.

**(d) Spot checks** (ψ=30°, θ=20°, φ=10°): closed form vs numeric product: max diff 3.5e-18; vs scipy 'ZYX': 2.2e-16; det = 1, orthogonality 4.2e-17.

---

## Anchor Summary Table (R = 6378.137 km unless noted)

| Anchor | Value |
|---|---|
| h=500 km, η=30°: Λ | **2.628951°** (mean-R: 2.631938°) |
| " R_s | **585,101.608 m** (mean-R: 585,110.538 m) |
| " ε / θ_i | **57.371049° / 32.628951°** |
| h=500 km circular: v | **7612.608173 m/s** (mean-R: 7616.561 m/s) |
| " v_g | **7059.216450 m/s** |
| " period | **5676.978 s = 94.6163 min** (mean-R: 94.4691 min) |
| GSD nadir (p=10 µm, f=2 m, h=500 km) | **2.500000 m** |
| GSD η=30° along / cross | **2.925508 m / 3.473732 m** |
| Max look angle h=500 km | **68.018674°**; horizon slant range 2574.517 km |
| Solar zenith φ=35°N, δ=23.44°, H=15° | **17.425559°** |

**Flags for the audit diff:** (1) cos η vs cos θ_i in off-nadir cross-track GSD (2.75% at anchor — plausible silent bug); (2) v vs v_g in smear/line-rate (7.84%); (3) asin branch direction sin θ_i = (R+h)/R·sin η (amplifying); (4) which Earth radius — equatorial vs mean shifts the 500-km period by 8.8 s and R_s(30°) by 8.9 m, so match radii before comparing physics.
