# Scenario 10.3 — Ground-to-Space SST, Visible Band

**Scene class:** `ground_to_space` (ADR-0011 §2 grid, owner priority 4 — the SST class)
**Validates:** Geometry-Flexibility Phases 1–4 (direction-general geometry, direction-aware
atmosphere, scene-class metric conditioning, the Phase-4 GUI surfaces)
**Category:** D (integration and UX)
**Runner:** `scripts/run_ground_to_space_sst_visible.py`
**Module-level factory:** `make_sensor() -> Sensor`

---

## 1. The problem

A space-surveillance site operates a 1 m visible-band tracking telescope. On a given
evening it is tasked on **ORB-4471**, a small LEO object at 700 km, during the
terminator window: the sun is 12° below the *site's* horizon (nautical twilight),
so the sky at the telescope is dark, while the object 700 km up is still in full
sunlight. The operator needs to know:

1. Does RADIANT express this scene at all? (Before ADR-0011 it could not: the sensor
   had to be strictly above the target, θ_o was bounded to [0, π/2), and the sun was
   hard-bounded above the horizon.)
2. What SNR does the tasking produce, and how does it decay across the pass as the
   object drops from culmination toward the horizon?
3. Is the measurement seeing-limited or aperture-limited, and by how much?
4. Which of RADIANT's metrics are *meaningful* for a target that is not on the ground?

This is the fourth scene class in ADR-0011's priority order and the one the Gap 110
turbulence work was built for.

## 2. The system

Vendor inputs live in `inputs/`, in vendor units, and are converted to RADIANT
canonical units exactly once inside `build_config()`.

| Quantity | Vendor value | Canonical value | Note |
|---|---|---|---|
| Site elevation | 900 m MSL | 900 m | below the 1 km ground/air band edge → `observer_class = ground` |
| Entrance pupil | 1000 mm | 1.000 m | mm → m |
| Effective focal length | 10 000 mm | 10.000 m | f/10 |
| Optical transmission | 60 % | 0.600 | % → fraction |
| Filter band | 400–900 nm | 0.400–0.900 µm | nm → µm |
| Pixel pitch | 15 µm | 15 µm | µm is the schema input unit |
| Quantum efficiency | 80 % | 0.800 | % → fraction |
| Dark current | 100 e-/s | 100 e-/s | — |
| Read noise | 5 e- RMS | 5 e- RMS | — |
| Full well | 400 ke- | 4.00 × 10⁵ e- | ke- → e- |
| Gain / ADC | 10 e-/DN, 16 bit | same | — |
| Exposure | 5 ms | 0.005 s | ms → s |
| Object altitude | 700 km | 7.00 × 10⁵ m | km → m |
| Pointing zenith | 20° | 0.34907 rad | deg → rad; referenced to the **lower** endpoint |
| Solar depression | 12° | θ_s = 1.78024 rad (102°) | δ → θ_s = 90° + δ, then deg → rad |
| Relative solar azimuth | 45° | 0.78540 rad | deg → rad |
| Visibility | 100 km | 100 km | km is the schema input unit |
| Cn² profile | HV-5/7 (w = 21 m/s, A = 1.7e-14 m^(-2/3)) | same | Gap 110 |

**Target spec — the intensity door.** The object is entered through
`source.target.user_intensity_path`, a two-column `(wavelength_um, I [W/sr/µm])`
CSV, together with `source.scene_type = "point_source"`. The vendor artifact is
`inputs/object_signature_ORB-4471.csv` in the SST-native units **nm** and
**W/sr/nm**; `write_canonical_signature()` converts (nm → µm, W/sr/nm → W/sr/µm).

The signature itself is built by `inputs/create_spreadsheet.py` as

$$ I(\lambda) = \frac{\rho\, A_{proj}\, E_{sun}(\lambda)\, p(\alpha)}{\pi}
\qquad
p(\alpha) = \frac{\sin\alpha + (\pi - \alpha)\cos\alpha}{\pi} $$

with ρ = 0.25, A_proj = 1.00 m², and a solar phase angle α = 35° (p = 0.8424).
**Why this and not a shape + albedo entry:** RADIANT has no reflective *point-source*
door — see `gaps.md` G1. The framework's reflective path (`T2Reflective`) multiplies
by `max(cos θ_s, 0)`, which is identically zero in the terminator window this
scenario exists to model. The intensity door is the only way to express a sunlit
object over a dark site today, and it is the same idiom scenario 1.6 uses for a
thermal point source.

## 3. Geometry — what the direction-general machinery publishes

```
scene_class                  ground_to_space          (derived, Provenance.DERIVED)
observer_class/target_class  ground / space
los_direction                up
viewing_mode                 geometry.path_zenith_rad (up-looking — angle at the
                                                       sensor, the lower endpoint)
```

| Angle | Value | Meaning |
|---|---|---|
| ζ_low | 20.0000° | zenith **at the telescope** — the tasking card's pointing angle, and the *lower* GUI arc |
| θ_o | 162.0489° | canonical target-side path zenith — **obtuse**, the *upper* GUI arc |
| η | 160.0000° | interior angle at the sensor = 180° − ζ_low |
| slant range | 739.156 km | spherical triangle |
| ground range | 227.828 km | surface arc between the two ground points |

**Independent closed-form check** (spherical sine rule, computed in the runner and
not by RADIANT):

$$\sin(\pi - \theta_o) = \frac{R_E + h_{sen}}{R_E + h_{tgt}}\sin(\pi - \zeta_{low})$$

gives θ_o = 162.0489° and R = 739.156 km, matching the chain to a relative error of
**5.98 × 10⁻¹⁵** — i.e. to floating-point. A flat-Earth estimate h/cos ζ = 744.924 km
is 5.8 km long; Earth curvature *shortens* an up-looking slant because the target
shell is reached sooner than the plane-parallel geometry predicts.

`outputs/signature_and_column_transmittance.png` shows the signature I(λ) and the
column τ_up(λ) this geometry produces.

## 4. Radiometry at the nominal tasking point

| Quantity | Value | Unit |
|---|---|---|
| regime (final, `OpticsStage`) | `point_source` | — |
| band-mean τ_up | 0.5330 | dimensionless |
| τ_up at 0.55 µm | 0.4492 | dimensionless |
| τ_sun (TOA → object) | 1.0000 | dimensionless (vacuum solar leg) |
| Fried parameter r₀ (0.650 µm) | 19.820 | cm |
| EE_box | 0.12075 | dimensionless |
| signal, central pixel | 34 961 | e- |
| SNR | 186.89 | dimensionless |
| detection range (SNR = 3 threshold) | 4 519.0 | km |
| sampling Q_center | 0.433 | dimensionless |
| PSF FWHM (x) | 35.41 | µm on the focal plane |

**Rule-4 dual-path consistency: PASSED, silently.** `passed_x = passed_y = True`,
max |FFT(PSF) − Π MTFᵢ| = **3.935 × 10⁻³** against the 2 × 10⁻² tolerance, and the
nominal run raised **zero** warnings of any kind. The turbulence term therefore
enters *both* spatial paths correctly in this scene class (the CU-234 regression
that once made `mtf_turbulence_*` ≡ 1 is not present here).

## 5. Metric conditioning by scene class (guardrail G3)

`radiant.api.scene_relevance.default_off_metrics("ground_to_space")` turns ten
metrics off by default, and none of them appears in `result.metrics`:

```
access_rate_m2_s, diffraction_limit_ground_m, ground_range_m,
gsd_along_track_m, gsd_cross_track_m, gsd_geometric_mean_m,
max_integration_time_s, niirs, niirs_extrapolated, swath_width_m
```

The target-plane family replaces them:

| Metric | Value |
|---|---|
| `target_plane_sample_distance_x_m` | 1.10873 m at the object |
| `target_plane_sample_distance_y_m` | 1.10873 m at the object |
| `target_plane_sample_distance_geometric_mean_m` | 1.10873 m at the object |
| `diffraction_limit_angular_urad` | 0.7930 µrad |

Physically: a pixel subtends 1.5 µrad, which at 739 km is 1.11 m — so the 1 m object
is about one *geometric* pixel across, and far smaller than the seeing disc. GSD and
swath are meaningless because nothing is being projected onto the ground.

## 6. Per-altitude solar illumination — the terminator (GF-9)

`outputs/terminator_shadow_height.png`. The shadow-height test is
$h_{shadow}(\delta) = R_E(\sec\delta - 1)$; a point is sunlit iff $h \ge h_{shadow}$.

| Solar depression δ [deg] | θ_s [deg] | h_shadow [km] | 100 km object | 700 km object | GEO object |
|---|---|---|---|---|---|
| 0 | 90 | 0.0 | SUNLIT | SUNLIT | SUNLIT |
| 6 | 96 | 35.1 | SUNLIT | SUNLIT | SUNLIT |
| **12** | **102** | **142.3** | shadow | **SUNLIT** | SUNLIT |
| 18 | 108 | 327.9 | shadow | SUNLIT | SUNLIT |
| 22 | 112 | 500.3 | shadow | SUNLIT | SUNLIT |
| 26 | 116 | 717.4 | shadow | shadow | SUNLIT |
| 30 | 120 | 985.6 | shadow | shadow | SUNLIT |

The 700 km object enters eclipse at δ = **25.71°**, and the hand check agrees
exactly: sec δ = 1 + h/R_E = 1.109873 → δ = 25.71°.

At the nominal 12° the site is dark and the object is sunlit — the terminator window
an SST site actually works in, and a scene that was *inexpressible* before Phase 2.
The chain agrees at the radiometric level too: it publishes τ_sun = 1.0000, a vacuum
solar leg, because the object sits above `h_atm_top` and the beam lighting it never
enters the atmosphere.

**But the illumination verdict does not reach the signal.** The intensity door
consumes I(λ) verbatim, so τ_sun never multiplies the target term: rerunning at 30°
depression, with the object fully eclipsed and τ_sun = 0, returns the *same* signal.
With this door the analyst owns the illumination gate (`gaps.md` G2).

## 7. Turbulence — seeing-limited, not aperture-limited (Gap 110)

`outputs/seeing_vs_diffraction_mtf.png`.

```
r0 resolution mode           profile (hufnagel_valley)
reference wavelength         0.6500 µm  (band centre)
∫ Cn² W ds                   3.7552e-13 m^(1/3)
lower-endpoint zenith        20.000 deg
integration span             0.900 – 100.0 km MSL
Fried parameter r0           19.820 cm
D / r0                       5.05
```

| Blur term | Angular FWHM | In arcsec |
|---|---|---|
| seeing, 0.98 λ/r₀ | 3.214 µrad | 0.663 |
| diffraction, 1.22 λ/D | 0.793 µrad | 0.164 |
| ratio | **4.05** | — |

**Verdict: seeing-limited.** The 1 m aperture buys photons, not resolution: the
long-exposure core is set by r₀, and doubling D would leave the blur diameter
unchanged while doubling D/r₀. The MTF consequence is severe —

| | with HV-5/7 | without turbulence |
|---|---|---|
| MTF_system at Nyquist (333.3 cycles/mrad) | 0.00862 | 0.46250 |
| PSF FWHM (x) | 35.41 µm | 15.24 µm |
| RER | 0.3317 | 0.7704 |
| EE 3×3 | 0.6246 | 0.9445 |
| SNR | 186.89 | 431.95 |

— turbulence removes essentially all modulation at the sampling limit while the
diffraction-limited system still carries 46 %. Note the "without turbulence" PSF
FWHM of 15.24 µm is *pixel*-dominated (the 15 µm aperture), not diffraction-dominated
(6.7 µm), so even the reference case is not diffraction-limited at this plate scale.

**Literature cross-check on r₀** (anchor 4 below): HV-5/7 is *defined* by r₀ ≈ 5 cm at
0.5 µm, sea level, zenith. The exact vertical integral of the analytic profile from
0 m gives 4.961 cm at 0.5 µm; scaling by $r_0 \propto \lambda^{6/5}\sec\zeta^{-3/5}$ to
0.650 µm and 20° gives 6.547 cm. The chain returns 19.820 cm because the integral
starts at the 900 m site altitude, above the profile's 100 m-scale-height surface
term. **Caveat (`gaps.md` G8):** the HV ground term is conventionally *above ground
level*, but `cn2_hufnagel_valley` evaluates the profile against MSL, so a site at
900 m MSL silently loses its own boundary layer. Scaled to 0.5 µm the chain r₀ is
14.5 cm — 0.70″ seeing, world-class-site quality — where a real 0.9 km high-desert
site runs 1.0–1.5″. **Treat the seeing here as optimistic by roughly 2×.**

## 8. The pass — pointing-zenith ladder

`outputs/zenith_ladder.png`.

| ζ_low [deg] | θ_o [deg] | R [km] | airmass | band-mean τ | r₀ [cm] | SNR | PSF FWHM [µrad] |
|---|---|---|---|---|---|---|---|
| 0 | 180.0000 | 699.1 | 1.000 | 0.5505 | 20.573 | 206.62 | 3.433 |
| 20 | 162.0489 | 739.2 | 1.064 | 0.5330 | 19.820 | 186.89 | 3.541 |
| 40 | 144.6032 | 882.8 | 1.305 | 0.4739 | 17.533 | 133.93 | 3.933 |
| 55 | 132.4248 | 1115.5 | 1.743 | 0.3878 | 14.739 | 82.92 | 4.589 |
| 65 | 125.2440 | 1387.5 | 2.366 | 0.2974 | 12.271 | 49.54 | 5.427 |
| 75 | 119.4918 | 1831.9 | 3.864 | 0.1655 | 9.143 | 20.78 | 7.160 |

θ_o = 180° at culmination is not a singularity — it is the ordinary vertical
up-looking geometry with the object at the site's zenith, and ADR-0011's closed
domain [0, π] is what makes it expressible.

SNR falls by an order of magnitude across the pass, and *both* mechanisms matter:
transmittance drops 3.3× while r₀ shrinks as sec ζ^(−3/5), widening the blur and
cutting EE_box. Neither alone explains the ladder.

**Air-mass handover artifact (`gaps.md` G5).** Above 80° the simple model switches
from `Δh/cos ζ` to a spherical root form parameterised by x = Δh/R_E. For an
atmospheric slab (Δh ≈ 10 km) that is correct; here the observer segment spans
site → object, Δh = 699 km, x = 0.110, and the correction is applied to the wrong
thickness:

| ζ_low [deg] | τ @ 0.55 µm | implied optical depth |
|---|---|---|
| 78.0 | 0.02687 | 3.6168 |
| 79.9 | 0.01373 | 4.2880 |
| **80.1** | **0.09796** | **2.3232** ← optical depth *dropped* as the path got longer |
| 85.0 | 0.06370 | 2.7536 |

Transmittance is therefore non-monotonic in zenith angle above 80°. **Every number
reported in this scenario is at or below 75°**, where the flat-Earth branch is in
force and sec ζ is correct to better than 0.5 %.

**Horizon guard (ADR-0011 decision 6).** At ζ_low = 88.6° the chain computes and
emits the quantified refraction warning; at ζ_low = 89.8° it raises
`ParameterBoundsError`. A real SST site stops tracking near 20° elevation for the
same reason the guard exists.

## 9. The sky background, and why the VIS/NIR caveat never fires here

The LOS-termination rule (Use-Case Matrix §3.2.5, rule B) follows the line of sight
*past* the object; it exits into cold space, so `SkyBackground` is selected — and the
chain does select it. But the at-aperture background radiance is
**1.3637 × 10⁻¹⁸ W/m²/sr/µm**, i.e. numerically zero, for two independent structural
reasons this scenario pins down:

1. **The intensity door strips the sun.** `_adjust_scene_los` keeps θ_s only for
   `T2Reflective` / `T3Mixed`; `T7IntensityAtSource` (the intensity door) is treated
   as pure-thermal by the CU-009 predicate, so the atmosphere sees θ_s = None and
   builds a purely thermal sky, which at 0.4–0.9 µm is ~10⁻¹⁸ W/m²/sr/µm
   (`gaps.md` G3).
2. **Even with θ_s kept, the ground-to-space sky is zero.** Re-tasking the same
   telescope on a 10 m² GEO object through the shape+albedo door (which *does* keep
   θ_s = 60°) still gives 1.3637 × 10⁻¹⁸ W/m²/sr/µm, because (i) the `SkyBackground`
   source term is the LOS *continuation*, which is vacuum when the target is above
   `h_atm_top`, so `sky_radiance_along_los` — the only place the VIS/NIR provisional
   warning lives — is never called; and (ii) the observer leg's single-scatter source
   takes its species split at the segment's arithmetic **mean altitude**, here
   0.5 × (0.9 + 35 786) km = 17 893 km, where every exp(−h/H) underflows to exactly
   zero (`gaps.md` G4).

**The provisional warning is therefore structurally unreachable in the whole
`ground_to_space` class.** To capture it, the runner tasks the same telescope on a
20 km stratospheric target (`ground_to_air`, extended scene, sun 30° up), where the
continuation genuinely is atmospheric, and prints it verbatim:

> `sky_radiance_along_los`: the scattered-solar component of the sky radiance below
> 3 µm is provisional — the simple model's single-scatter source underestimates the
> daytime sky, where multiple scattering dominates. The thermal component (MWIR/LWIR)
> is MODTRAN-anchored and is not affected. Use a MODTRAN or interpolated backend for
> quantitative VIS/NIR sky-background work (Geometry Flexibility plan §8.3 answer 3).

That probe's observer-leg L_path is **21.572 W/m²/sr/µm** — an order-of-magnitude
plausible daytime sky pedestal, and exactly the number the `ground_to_space` class is
silently missing. The caveat itself is real: a single-scatter source under-states a
daylight sky in which most arriving photons have scattered several times, so both the
pedestal and its shot noise are optimistic. MWIR/LWIR sky is thermal and
MODTRAN-anchored, which is why the band gate sits at 3 µm.

**Consequence for this scenario's headline SNR:** with a real twilight sky pedestal
the SNR of 186.89 would be lower. The number should be read as *shot-noise-on-target
plus detector noise only*, not as an end-to-end SST link budget.

## 10. Cross-checks

Four independent anchors plus a deliberate non-anchor.

### Anchor 1 — closed-form point-source identity and its vacuum limit ✅

Every factor read back out of the chain, then the textbook integral evaluated by hand:

$$ S = t_{int}\,\eta_{QE}\,\mathrm{EE_{box}} \int \tau_{opt}(\lambda)\,\tau_{atm}(\lambda)\,
\frac{I(\lambda)}{R^2}\,A_{coll}\,\frac{\lambda}{hc}\,\mathrm d\lambda $$

| | |
|---|---|
| A_collect | 0.785398 m² |
| band-mean τ_opt | 0.600000 |
| EE_box | 0.120752 |
| R | 739.156 km |
| t_int | 5.0 ms |
| **hand-computed signal** | **34 961.236 e-** |
| **chain signal** | **34 961.236 e-** |
| relative difference | **2.081 × 10⁻¹⁶** — PASS |

Vacuum limit (τ_atm → 1 in the same integral): S_vac = 63 971.812 e-, and
S_chain/S_vac = 0.546510, which equals the photon-weighted band-mean τ to
**0.000 × 10⁰**. So the chain applies the column transmittance exactly and
multiplicatively, and the atmosphere-free answer is recoverable analytically.

A *true* vacuum run (telescope raised to `h_atm_top` = 100 km, where the topology
dispatcher returns τ_up ≡ 1) **raises**: the wholly-vacuum branch returns
`sky_radiance_at_aperture = None` while the LOS-termination rule still selects
`SkyBackground`, and the assembly refuses to default it to zero (`gaps.md` G7). The
identity is therefore evaluated analytically rather than by a second chain run.

### Anchor 2 — published astronomical extinction ❌ FAIL, root-caused

Broadband V-band zenith extinction at good astronomical sites is
k_V ≈ 0.12–0.20 mag/airmass (Hardie 1962 photometric-reduction practice;
Burke, Gladders & Graham, *Astronomical Photometry*, 2010, §5, quoting 0.1–0.3 for V
at typical observatories). A magnitude is −2.5 log₁₀ of a flux ratio, so
τ = 10^(−0.4 k) → τ(0.55 µm) at zenith should be **0.832–0.895**.

RADIANT returns **τ(0.55 µm) = 0.4714**, i.e. **0.816 mag/airmass** — 4–7× too much
extinction. **This cross-check fails, and it fails for a locatable reason.**

`radiant.atmosphere.simple` uses

```
sigma_mol(lambda) = 0.0088 * lambda_um**(-4.09)   # documented as [1/km at sea level]
```

and multiplies it by the molecular column length (7.1488 km above a 900 m site). But
`0.0088 λ^(-4.09)` is the standard fit to the **total vertical Rayleigh optical
depth** — dimensionless (Hansen & Travis 1974; Bucholtz 1995) — not a volume
extinction coefficient. The true sea-level Rayleigh volume extinction at 550 nm is
0.0116 km⁻¹, about 8.7× smaller than the 0.10148 the expression yields.

| | optical depths |
|---|---|
| 0.0088 × 0.55^(−4.09) | 0.10148 |
| Rayleigh OD *as used* (σ × 7.1488 km) | 0.7255 |
| Rayleigh OD *read as an OD* | 0.0907 |
| published Rayleigh OD at 550 nm (sea level) | 0.0973 |
| RADIANT total zenith OD | 0.7520 |
| **corrected total zenith OD** | **0.1172** |
| corrected τ(0.55 µm) | 0.8894 |
| **corrected extinction** | **0.127 mag/airmass — INSIDE the published band** |

The correction lands squarely inside the literature range, which is what confirms the
diagnosis rather than merely asserting it. MWIR/LWIR is unaffected in practice
(Rayleigh OD at 4 µm is ~2.5 × 10⁻⁴ either way), which is why the CU-161 MODTRAN
calibration — anchored over 3–14 µm — never saw it. Filed as `gaps.md` G9.

**Consequence for this scenario:** every τ, and therefore every SNR, in §4 and §8 is
pessimistic by a factor of roughly 1/0.55 ≈ 1.8 at the nominal geometry. The
*trends* (monotone decay with airmass, the τ vs r₀ split) are unaffected.

### Anchor 3 — apparent visual magnitude ✅

| | |
|---|---|
| total radiant intensity, all λ (= ρ A S₀ p(α)/π) | 91.24 W/sr |
| I(0.55 µm) from the signature file | 117.2764 W/sr/µm |
| irradiance at the aperture, I/R² | 1.6700 × 10⁻¹⁰ W/m² |
| solar irradiance at 1 AU, S₀ | 1361.0 W/m² |
| m = m_☉ − 2.5 log₁₀(E/S₀), m_☉ = −26.74 | **5.54 mag** above the atmosphere |
| RADIANT column extinction on this path | 0.656 mag |
| apparent magnitude at the site | 6.19 mag |

Catalogued LEO objects of ~1 m² projected area at a few hundred to 1000 km routinely
photometer at m_V ≈ 4–8 (the naked-eye-satellite regime). 5.54 mag is squarely inside
that band — the signature file is the right order of magnitude, independently of
anything RADIANT computed.

### Anchor 4 — HV-5/7 Fried parameter

Covered in §7: the exact vertical integral of the analytic profile reproduces the
4.961 cm ≈ 5 cm definition at 0.5 µm, and the λ^(6/5) sec ζ^(−3/5) scaling is an
independent closed form the path integral is not built from.

### Identity check — transmittance reciprocity ✅

ADR-0011 decision 3 says a segment carries *one* τ, computed at its lower endpoint,
because transmittance is reciprocal. Flipping the scene — sensor in space, target on
the ground, same column, same lower-endpoint zenith — gives
`space_to_ground` / `los = down`, and

```
max |tau_up - tau_down| = 1.665e-16
```

i.e. bit-for-bit. The direction-general machinery is *not* the source of the Anchor-2
failure; that is a calibration defect the down-looking path shares.

### Deliberate non-anchor — MODTRAN

The ground-to-space full-column MODTRAN ladder for this class is **owner-run batch 2**
(ADR-0011 decision 10) and has not been delivered. **No MODTRAN comparison is
reported.** When batch 2 lands, rerun this scenario and compare τ(λ) directly; the
Anchor-2 diagnosis predicts the simple model will read ~8× too opaque in the VIS
Rayleigh term.

## 11. What does not affect the result

- `source.target.temperature` / `emissivity` — unused; the intensity door takes I(λ)
  verbatim and no emission model runs.
- `nedt_K` = 0.0227 K is meaningless here: it is dS/dT taken against the *default*
  target temperature, a parameter this scene never sets. It is present because the
  thermal metric group is on by default.
- `geometry.solar_azimuth_rad` enters only the single-scatter sky phase function,
  which is off with the sun below the site horizon.
- `atmosphere.tau_sun` = 1.0 (vacuum solar leg) — and, as §6 explains, it does not
  multiply the intensity-door target term at all.
- Ground-projection metrics are off by scene class, not by accident.
- The platform is a fixed ground mount, so `smear_width_m` = 0. A real SST tracking
  rate would enter through `geometry.los_angular_rate_rad_s` (mode K1); note that an
  untracked 700 km LEO object moves at ~10 mrad/s, which in the 5 ms exposure is
  50 µrad — 15× the seeing disc. The 5 ms exposure is set by tracking accuracy, not
  by the well.

## 12. Non-obvious physics

1. **Direction-aware path products.** Up-looking, the observer leg is the column from
   the *telescope* to `h_atm_top`, and the continuation past the object exits into
   cold space. τ_up is that observer leg; L_path_up is the radiance accumulated along
   it. These are segment-composed, not the down-looking bundle read backwards
   (ADR-0011 decision 3, guardrail G1).
2. **Lower-endpoint angle convention.** The tasking card's pointing zenith *is* ζ_low
   because the telescope is the lower endpoint. θ_o, the canonical angle every
   downstream stage reads, is its obtuse partner through the spherical triangle — not
   simply 180° − ζ_low, since the central angle φ = 2.05° adds in.
3. **The sky is both background and attenuator.** The same column that dims the object
   fills the pixel behind it. In the point-source regime the target term uses
   Ω_target = A_t/R² with the path-radiance pedestal stripped, while the background
   enters at the full pixel solid angle Ω_pixel and shot-noises.
4. **Seeing beats aperture.** EE_box is 12.1 %, not because the optics are poor but
   because the seeing disc spread over the pixel grid puts most of the object's
   photons outside the central pixel. EE_box is computed once in `PlatformStage` from
   the fully degraded PSF and applied once in spectral integration (Rules 4 and 9).
5. **Horizon guard.** No refraction model exists, so the near-horizontal band raises
   rather than returning a plausible wrong number (Rule 17).
6. **A τ discontinuity at 0.70 µm** is visible in
   `outputs/signature_and_column_transmittance.png`: the simple model's calibrated
   gas-region table is piecewise constant and k_h2o jumps 0.0025 → 0.1245 at the
   0.70 µm region edge. Filed as `gaps.md` G10.

## 13. What the operator would do next

1. Rerun once the batch-2 MODTRAN SST ladder lands and re-anchor τ(λ) (blocked).
2. Re-run with the Rayleigh coefficient corrected and re-derive the pass SNR budget;
   the current numbers are ~1.8× pessimistic at the nominal geometry.
3. Add a real sky pedestal — either by fixing the observer-leg scatter for
   above-atmosphere targets or by injecting a measured sky spectrum through
   `UserSpectralBackground` — before quoting an SST detection limit.
4. Enter the tracking rate (K1) and sweep exposure against tracking jitter to find the
   knee where smear overtakes seeing.
5. Sweep object albedo × projected area to derive the site's limiting magnitude, and
   compare with the site's measured photometric zero point.
