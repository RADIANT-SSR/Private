# RADIANT Use-Case Matrix (v1)

**Status**: design-in-progress. This document captures the axes, locked decisions, and descriptor schemas for the v1 imaging-scenario matrix. It governs how SourceStage, AtmosphereStage, and downstream stages consume user inputs.

**Scope**: v1 covers space-based EO sensors observing at-aperture, terrestrial, airborne, or no-atmosphere targets across VIS–LWIR. The `no_atmosphere` location covers three sub-cases — space-target imaging, outdoor short-range ground tests, and indoor lab / chamber tests — which share A0 atmosphere but differ in default background and illumination. Airborne and ground-based sensors, clouds, ellipsoidal Earth, atmospheric refraction, earthlimb backgrounds, and diurnal thermal response are deferred to v2.

**Related documents**:
- `RADIANT_Master_Architecture.md` — 18 non-negotiable rules (especially 2, 4, 9, 10, 11, 12)
- `RADIANT_Signal_Chain_Architecture.md` — Stage protocol, ChainState
- `RADIANT_Conventions.md` — canonical units, coordinate frame
- `RADIANT_Atmosphere.md` — atmosphere backend (MODTRAN integration)

---

## 1. Axes

Three independent axes define a use case. Target/atmosphere/background models are the *dependent outputs* of the three axes, not additional axes.

### 1.1 Scene type

| Value | Radiometric spec | Key parameters | Area treatment |
|---|---|---|---|
| `extended` | Spectral radiance `L_t(λ)` [W/m²/sr/µm] fills pixel IFOV | `L_t(λ)` or (ε, T) or (ρ, E) | Pixel solid angle; no area parameter |
| `sub_pixel` | Spectral radiance `L_t(λ)` + finite target area `A_t` and shape | `L_t(λ)`, `A_t`, `shape` | Target subtends Ω_t = A_t/d², finite and < Ω_pix |
| `point_source` | Spectral intensity `I_t(λ)` [W/sr/µm] (pre-integrated) | `I_t(λ)` or (ε, T, A_t) collapsed into I | No separate area; unresolved |

**Scene-type constraints**:
- `at_aperture` target location is restricted to `extended` scene type.
- EE_box applies per Rule 9: never in extended, always in point_source and sub_pixel (on target term only).
- Sub-pixel collapses to point-source when `√A_t/d ≪ PSF_FWHM` (emit UserWarning suggesting reclassification).
- Point-source with a resolved target is a physics error (raise).

### 1.2 Wavelength regime

| Regime | Range (µm) | Dominant target physics | Dominant background physics |
|---|---|---|---|
| VIS | 0.4–0.7 | Solar reflection | Ground reflection |
| NIR | 0.7–1.0 | Solar reflection | Ground reflection |
| SWIR | 1.0–2.5 | Solar reflection (thermal emerges for hot targets) | Ground reflection |
| MWIR | 3–5 | **Mixed** — emission + reflection both matter | Mixed: ground emission + reflected solar |
| LWIR | 8–14 | Thermal emission | Ground thermal emission |

Regime affects which terms in the radiance assembly equation dominate and which atmospheric quantities (τ_sun, E_sky-scatter, L_path thermal) matter most. MWIR always requires the mixed target model (T3) for ambient-temperature scenes.

### 1.3 Target location

| Value | Definition | Atmosphere path type |
|---|---|---|
| `at_aperture` | Radiance specified at sensor pupil; no propagation | A0 (none) |
| `terrestrial` | At or near surface (h_tgt ≲ 1 km) | A2 (full two-way: solar down, sensor up) |
| `airborne` | In the atmosphere (1 km ≲ h_tgt ≲ 30 km); A3 degrades smoothly to A0 as h_tgt → TOA | A3 (partial two-way) |
| `no_atmosphere` | No significant atmospheric propagation between target and sensor. Covers space targets (h_tgt ≳ 100 km), short-range ground test ranges, and lab / chamber test setups. | A0 (none) |

**Sensor location is fixed to `space` in v1** (h_sensor ≥ h_atm_top). Airborne and ground sensors are v2.

---

## 2. Locked Decisions

Decisions made during design review, in order:

1. **Target location axis** = {`at_aperture`, `terrestrial`, `airborne`, `no_atmosphere`}. `airborne` is a first-class value, distinct from `terrestrial` because the partial-column atmosphere (A3) is physically different from the full-column case (A2). `no_atmosphere` is the umbrella for all A0 scenarios — space targets, short-range ground tests, and lab / chamber tests — which share "no propagation" but differ in default background and illumination (see §3.3 sub-cases).

2. **Scene type axis** = {`extended`, `sub_pixel`, `point_source`}. Distinction is radiometric: extended/sub_pixel are parameterized by spectral radiance + (optional) area; point_source by spectral intensity (area pre-integrated). `at_aperture` target location is restricted to `extended` only.

3. **Sensor location** = `space` only in v1; airborne and ground deferred to v2. Atmosphere model parameterization is kept on (h_source, h_destination) so v2 expansion is additive rather than breaking.

4. **Radiance assembly owned by AtmosphereStage (Option C)**. SourceStage publishes `TargetDescriptor`, `BackgroundDescriptor`, and `LineOfSightGeometry` (no radiance). AtmosphereStage consumes these plus atmospheric quantities and produces at-aperture `L_t(λ)` and `L_bg(λ)`.

5. **Kirchhoff consistency**: for target and ground-background material inputs, accept `ε(λ)` only; derive `ρ(λ) = 1 − ε(λ)` for opaque Lambertian. Over-specification (both ε and ρ) is a schema error.

6. **At-aperture API**: user supplies `L_t_aperture(λ)` (required) + `L_bg_aperture(λ)` (optional, default 0). Forced extended-only. AtmosphereStage becomes validated pass-through; warns if atm parameters were supplied.

7. **AtmosphereStage geometry contract** = `LineOfSightGeometry` with {`h_tgt`, `h_atm_top`, `θ_o`, `θ_s`, `Δφ`}. Physical sensor altitude lives in `geometry.sensor_altitude_m`, owned by `GeometryStage` (ADR-0006 — the SensorDescriptor concept was superseded; see §4.4).

8. **Earth model**: spherical, `R_E = 6378.137 km` in v1. Ellipsoidal (WGS84) is v2.

9. **Atmospheric refraction**: not modeled in v1. v2 only; becomes relevant at grazing geometries (θ_o → π/2).

10. **`LineOfSightGeometry` module split**: lives in its own file `src/radiant/core/los_geometry.py` per Rule 19. (`core/geometry.py`'s flat-Earth `ObserverGeometry`/`SceneGeometry` dataclasses were deleted 2026-07-12 — CU-094/ADR-0006; the module keeps the spherical helper functions.)

11. **BackgroundDescriptor types (v1)**: four variants — `AtApertureBackground`, `ColdSpaceBackground`, `GroundBackground`, `UserSpectralBackground`. Earthlimb and cloud deferred to v2. For `no_atmosphere (space)` sub-case, if LOS intercepts Earth, raise (no v1 earthlimb model). `UserSpectralBackground` covers ground-test / lab-test sub-cases where the user supplies test-range or chamber radiance.

12. **Ground background**: homogeneous across the scene, scalar `T_g`, no diurnal / solar-heating thermal response, no per-pixel texturing. All deferred to v2.

13. **Background absent for computed extended regime**: no BackgroundDescriptor populated; SpectralIntegrationStage skips background photon term.

14. **Default background selection**:
    - `at_aperture` → `AtApertureBackground(L_bg_aperture=None)` (treated as zero)
    - `no_atmosphere` → depends on sub-case: `space` → `ColdSpaceBackground` (or raise if LOS intercepts Earth); `ground_test` and `lab_test` → user **must** supply a `UserSpectralBackground`
    - `terrestrial` / `airborne` → user **must** supply `GroundBackground` explicitly (no sensible default ε, T_g)

---

## 3. Archetype Matrix

Collapsed to ~12 rows covering the physically distinct cells. Missing rows are marginal or redundant.

| # | Target loc | Regime | Scene | Target model | Atm | Background | Illum |
|---|---|---|---|---|---|---|---|
| 1 | terrestrial | VIS/NIR | extended | T2 (ρ·E/π) | A2 | GroundBackground | I1 or I2 |
| 2 | terrestrial | VIS/NIR | point / sub-pixel | T2 | A2 | GroundBackground | I1 or I2 |
| 3 | terrestrial | SWIR | extended | T2 (T3 if hot) | A2 | GroundBackground | I1 |
| 4 | terrestrial | MWIR | extended | **T3 mandatory** | A2 + A4 | GroundBackground | I1 |
| 5 | terrestrial | MWIR | point (hot target) | T3 or T1 | A2 or A4 | GroundBackground | I1 or I0 |
| 6 | terrestrial | LWIR | extended | T1 | A4 | GroundBackground | I0 |
| 7 | terrestrial | LWIR | point | T1 | A4 | GroundBackground | I0 |
| 8 | airborne | VIS–SWIR | point / sub-pixel | T2 | A3 | GroundBackground (past target) | I1 |
| 9 | airborne | MWIR | point / sub-pixel | **T3** | A3 | GroundBackground | I1 |
| 10 | airborne | LWIR | point / sub-pixel | T1 | A3 (emission-only up-leg) | GroundBackground | I0 |
| 11 | no_atmosphere (space) | VIS–SWIR | point / sub-pixel | T2 | A0 | ColdSpaceBackground | I1 (TOA direct) |
| 12 | no_atmosphere (space) | MWIR/LWIR | point / sub-pixel | T1 or T3 | A0 | ColdSpaceBackground | I0 or I1 |
| 12a | no_atmosphere (ground_test) | any | any scene | T1/T2/T3 (as physics requires) | A0 | UserSpectralBackground | User illumination (ambient or controlled) |
| 12b | no_atmosphere (lab_test) | any | any scene | T1/T2/T3 | A0 | UserSpectralBackground | User illumination (controlled source or none) |
| 13 | at_aperture | any | extended | T5 (user L_t_aperture) | A0 | AtApertureBackground (user L_bg or 0) | N/A |

### 3.1 Model-catalog references

**Target radiance models (T-codes)**:
- `T1` — Graybody thermal: `L_t = ε(λ)·B(λ, T_t)`. Parameters: ε(λ), T_t
- `T2` — Lambertian reflective: `L_t = ρ(λ)·E_illum(λ)/π`. Parameters: ρ (or ε + Kirchhoff), illumination from AtmosphereStage
- `T3` — Mixed emit + reflect: `L_t = ρ·E/π + ε·B(T_t)`. Opaque Lambertian with Kirchhoff. Mandatory for MWIR.
- `T4` — BRDF reflective (v2)
- `T5` — User-provided spectral radiance or intensity (used by `at_aperture`)
- `T6` — Plume / line emission (deferred beyond v2)

**Atmosphere path codes (A-codes)**:
- `A0` — None (at_aperture or space-to-space)
- `A1` — Up-path only (ground-based sensor; v2)
- `A2` — Full two-way: τ_sun (TOA→surface), τ_up (surface→sensor), L_path, E_sky
- `A3` — Partial two-way: τ_sun (TOA→h_tgt), τ_up (h_tgt→sensor), plus background path τ_full,up
- `A4` — Emission-only two-way (no solar down-leg): LWIR terrestrial

**Background codes (B-codes)**:
- `B0` — None / at-aperture pass-through
- `B1` — ColdSpaceBackground (L = 0 in v1)
- `B2` — Sky path looking up (v2)
- `B3` — GroundBackground
- `B4` — Earthlimb (v2)
- `B5` — Cloud (v2)

**Illumination codes (I-codes)**:
- `I0` — None (pure thermal)
- `I1` — Solar direct at TOA, attenuated to target altitude
- `I2` — Solar + diffuse sky hemispheric irradiance at target
- `I3` — Non-solar (moon / laser / active) — deferred

### 3.2 Full Matrix — All 60 Cells (Spelled Out)

All combinations of 4 target locations × 5 wavelength regimes × 3 scene types. Invalid cells flagged. Target model, atmosphere path, background, and illumination spelled out in full for readability; short codes are cross-referenced in §3.1.

The `no_atmosphere` target location has three sub-cases (space / ground_test / lab_test — see §3.3) that share A0 but differ in default background and illumination. Table D shows the default `space` sub-case; tables D-ground and D-lab show the alternative presets.

#### Table A — `at_aperture` (5 valid, 10 invalid)

User injects spectral radiance directly at the pupil; no propagation. Restricted to extended scene only per decision #2.

| # | Regime | Scene | Target model | Atmosphere | Background | Illumination |
|---|---|---|---|---|---|---|
| 1 | VIS | extended | User radiance at aperture | None | At-aperture pass-through (user L_bg or zero) | N/A |
| 2 | VIS | sub_pixel | **INVALID** — at_aperture requires extended | — | — | — |
| 3 | VIS | point_source | **INVALID** — at_aperture requires extended | — | — | — |
| 4 | NIR | extended | User radiance at aperture | None | At-aperture pass-through | N/A |
| 5 | NIR | sub_pixel | **INVALID** | — | — | — |
| 6 | NIR | point_source | **INVALID** | — | — | — |
| 7 | SWIR | extended | User radiance at aperture | None | At-aperture pass-through | N/A |
| 8 | SWIR | sub_pixel | **INVALID** | — | — | — |
| 9 | SWIR | point_source | **INVALID** | — | — | — |
| 10 | MWIR | extended | User radiance at aperture | None | At-aperture pass-through | N/A |
| 11 | MWIR | sub_pixel | **INVALID** | — | — | — |
| 12 | MWIR | point_source | **INVALID** | — | — | — |
| 13 | LWIR | extended | User radiance at aperture | None | At-aperture pass-through | N/A |
| 14 | LWIR | sub_pixel | **INVALID** | — | — | — |
| 15 | LWIR | point_source | **INVALID** | — | — | — |

#### Table B — `terrestrial` (h_tgt ≲ 1 km)

Full-column atmosphere; background is ground for sub_pixel/point_source cases.

| # | Regime | Scene | Target model | Atmosphere | Background | Illumination |
|---|---|---|---|---|---|---|
| 16 | VIS | extended | Solar reflective (Lambertian) | Full two-way column | None (extended fills pixel) | Solar direct + diffuse sky |
| 17 | VIS | sub_pixel | Solar reflective + area + shape | Full two-way column | Ground (ε_g, T_g) | Solar direct + diffuse sky |
| 18 | VIS | point_source | Solar reflective, area pre-integrated → intensity | Full two-way column | Ground | Solar direct + diffuse sky |
| 19 | NIR | extended | Solar reflective | Full two-way column | None | Solar direct + diffuse sky |
| 20 | NIR | sub_pixel | Solar reflective + area + shape | Full two-way column | Ground | Solar direct + diffuse sky |
| 21 | NIR | point_source | Solar reflective, intensity form | Full two-way column | Ground | Solar direct + diffuse sky |
| 22 | SWIR | extended | Solar reflective (mixed if hot target) | Full two-way column | None | Solar direct (scatter weak) |
| 23 | SWIR | sub_pixel | Solar reflective or mixed + area + shape | Full two-way column | Ground | Solar direct |
| 24 | SWIR | point_source | Solar reflective or mixed, intensity form | Full two-way column | Ground | Solar direct |
| 25 | MWIR | extended | **Mixed emit+reflect (mandatory)** | Full column + emission-only two-way | None | Solar direct + thermal downwelling sky |
| 26 | MWIR | sub_pixel | Mixed emit+reflect + area + shape | Full column + emission-only two-way | Ground | Solar direct + thermal downwelling sky |
| 27 | MWIR | point_source | Mixed or pure thermal, intensity form | Full column + emission-only two-way | Ground | Solar direct (or none if target is hot) |
| 28 | LWIR | extended | Thermal graybody | Emission-only two-way | None | None (pure thermal) |
| 29 | LWIR | sub_pixel | Thermal graybody + area + shape | Emission-only two-way | Ground | None |
| 30 | LWIR | point_source | Thermal graybody, intensity form | Emission-only two-way | Ground | None |

#### Table C — `airborne` (1 km ≲ h_tgt ≲ 30 km)

Partial-column atmosphere above target; background is ground past the target (LOS continues down to surface).

| # | Regime | Scene | Target model | Atmosphere | Background | Illumination |
|---|---|---|---|---|---|---|
| 31 | VIS | extended | Solar reflective | Partial column (TOA ↔ h_tgt) | None | Solar direct + diffuse sky |
| 32 | VIS | sub_pixel | Solar reflective + area + shape | Partial column | Ground (past target) | Solar direct + diffuse sky |
| 33 | VIS | point_source | Solar reflective, intensity form | Partial column | Ground (past target) | Solar direct + diffuse sky |
| 34 | NIR | extended | Solar reflective | Partial column | None | Solar direct + diffuse sky |
| 35 | NIR | sub_pixel | Solar reflective + area + shape | Partial column | Ground | Solar direct + diffuse sky |
| 36 | NIR | point_source | Solar reflective, intensity form | Partial column | Ground | Solar direct + diffuse sky |
| 37 | SWIR | extended | Solar reflective (mixed if hot) | Partial column | None | Solar direct |
| 38 | SWIR | sub_pixel | Solar reflective or mixed + area + shape | Partial column | Ground | Solar direct |
| 39 | SWIR | point_source | Solar reflective or mixed, intensity form | Partial column | Ground | Solar direct |
| 40 | MWIR | extended | **Mixed emit+reflect** | Partial column | None | Solar direct + thermal downwelling sky |
| 41 | MWIR | sub_pixel | Mixed emit+reflect + area + shape | Partial column | Ground | Solar direct + thermal downwelling sky |
| 42 | MWIR | point_source | Mixed or pure thermal, intensity form | Partial column | Ground | Solar direct (or none if hot) |
| 43 | LWIR | extended | Thermal graybody | Partial column (emission-only up-leg) | None | None |
| 44 | LWIR | sub_pixel | Thermal graybody + area + shape | Partial column | Ground | None |
| 45 | LWIR | point_source | Thermal graybody, intensity form | Partial column | Ground | None |

#### Table D — `no_atmosphere` (space sub-case, h_tgt ≳ 100 km)

No atmosphere (space-to-space); background is cold space (zero radiance in v1) unless LOS intercepts Earth (raises — v2 earthlimb).

| # | Regime | Scene | Target model | Atmosphere | Background | Illumination |
|---|---|---|---|---|---|---|
| 46 | VIS | extended | Solar reflective | None | None | Solar direct (TOA, no attenuation) |
| 47 | VIS | sub_pixel | Solar reflective + area + shape | None | Cold space (L=0) | Solar direct (TOA) |
| 48 | VIS | point_source | Solar reflective, intensity form | None | Cold space | Solar direct (TOA) |
| 49 | NIR | extended | Solar reflective | None | None | Solar direct (TOA) |
| 50 | NIR | sub_pixel | Solar reflective + area + shape | None | Cold space | Solar direct (TOA) |
| 51 | NIR | point_source | Solar reflective, intensity form | None | Cold space | Solar direct (TOA) |
| 52 | SWIR | extended | Solar reflective (mixed if hot) | None | None | Solar direct (TOA) |
| 53 | SWIR | sub_pixel | Solar reflective or mixed + area + shape | None | Cold space | Solar direct (TOA) |
| 54 | SWIR | point_source | Solar reflective or mixed, intensity form | None | Cold space | Solar direct (TOA) |
| 55 | MWIR | extended | Mixed emit+reflect | None | None | Solar direct (TOA) |
| 56 | MWIR | sub_pixel | Mixed emit+reflect + area + shape | None | Cold space | Solar direct (TOA) |
| 57 | MWIR | point_source | Mixed or pure thermal, intensity form | None | Cold space | Solar direct (TOA) or none |
| 58 | LWIR | extended | Thermal graybody | None | None | None |
| 59 | LWIR | sub_pixel | Thermal graybody + area + shape | None | Cold space | None |
| 60 | LWIR | point_source | Thermal graybody, intensity form | None | Cold space | None |

#### Table D-ground — `no_atmosphere` (ground_test sub-case)

Short-range outdoor test scenario (target ~meters to ~km from sensor; atmospheric path negligibly short). Target physics runs normally (material + temperature + illumination → radiance); atmosphere is A0 pass-through. User supplies the test range background and ambient / controlled illumination.

| # | Regime | Scene | Target model | Atmosphere | Background | Illumination |
|---|---|---|---|---|---|---|
| G1 | VIS | extended | Solar reflective | None | User-supplied spectral (test range) | User-supplied (ambient solar or controlled) |
| G2 | VIS | sub_pixel | Solar reflective + area + shape | None | User-supplied spectral | User-supplied |
| G3 | VIS | point_source | Solar reflective, intensity form | None | User-supplied spectral | User-supplied |
| G4 | NIR | extended | Solar reflective | None | User-supplied spectral | User-supplied |
| G5 | NIR | sub_pixel | Solar reflective + area + shape | None | User-supplied spectral | User-supplied |
| G6 | NIR | point_source | Solar reflective, intensity form | None | User-supplied spectral | User-supplied |
| G7 | SWIR | extended | Solar reflective (mixed if hot) | None | User-supplied spectral | User-supplied |
| G8 | SWIR | sub_pixel | Solar reflective or mixed + area + shape | None | User-supplied spectral | User-supplied |
| G9 | SWIR | point_source | Solar reflective or mixed, intensity form | None | User-supplied spectral | User-supplied |
| G10 | MWIR | extended | Mixed or pure thermal | None | User-supplied spectral | User-supplied (or none) |
| G11 | MWIR | sub_pixel | Mixed or thermal + area + shape | None | User-supplied spectral | User-supplied (or none) |
| G12 | MWIR | point_source | Mixed or thermal, intensity form | None | User-supplied spectral | User-supplied (or none) |
| G13 | LWIR | extended | Thermal graybody | None | User-supplied spectral | None |
| G14 | LWIR | sub_pixel | Thermal graybody + area + shape | None | User-supplied spectral | None |
| G15 | LWIR | point_source | Thermal graybody, intensity form | None | User-supplied spectral | None |

#### Table D-lab — `no_atmosphere` (lab_test sub-case)

Indoor calibration scenario (chamber walls, optical bench, vacuum or negligibly short air path). Target physics runs normally; atmosphere is A0 pass-through. User supplies chamber/backdrop radiance and any controlled illumination source (or none for dark cal).

| # | Regime | Scene | Target model | Atmosphere | Background | Illumination |
|---|---|---|---|---|---|---|
| L1 | VIS | extended | Solar reflective | None | User-supplied spectral (chamber) | User-supplied controlled source (or none) |
| L2 | VIS | sub_pixel | Solar reflective + area + shape | None | User-supplied spectral | User-supplied (or none) |
| L3 | VIS | point_source | Solar reflective, intensity form | None | User-supplied spectral | User-supplied (or none) |
| L4 | NIR | extended | Solar reflective | None | User-supplied spectral | User-supplied (or none) |
| L5 | NIR | sub_pixel | Solar reflective + area + shape | None | User-supplied spectral | User-supplied (or none) |
| L6 | NIR | point_source | Solar reflective, intensity form | None | User-supplied spectral | User-supplied (or none) |
| L7 | SWIR | extended | Solar reflective (mixed if hot) | None | User-supplied spectral | User-supplied (or none) |
| L8 | SWIR | sub_pixel | Solar reflective or mixed + area + shape | None | User-supplied spectral | User-supplied (or none) |
| L9 | SWIR | point_source | Solar reflective or mixed, intensity form | None | User-supplied spectral | User-supplied (or none) |
| L10 | MWIR | extended | Mixed or pure thermal (blackbody standard common) | None | User-supplied spectral | User-supplied (or none) |
| L11 | MWIR | sub_pixel | Mixed or thermal + area + shape | None | User-supplied spectral | User-supplied (or none) |
| L12 | MWIR | point_source | Mixed or thermal, intensity form | None | User-supplied spectral | User-supplied (or none) |
| L13 | LWIR | extended | Thermal graybody (blackbody standard common) | None | User-supplied spectral | None |
| L14 | LWIR | sub_pixel | Thermal graybody + area + shape | None | User-supplied spectral | None |
| L15 | LWIR | point_source | Thermal graybody, intensity form | None | User-supplied spectral | None |

### 3.3 `no_atmosphere` sub-cases (presets)

The `no_atmosphere` target location has three named sub-cases. They share A0 atmosphere and the same source-physics pipeline (target material + geometry → radiance via Planck, Kirchhoff, reflectance × illumination / π). They differ only in default BackgroundDescriptor and IlluminationDescriptor.

| Sub-case | Typical scenario | Default background | Default illumination | Geometry interpretation |
|---|---|---|---|---|
| `space` | Space-target imaging (SSA, space-to-space) | `ColdSpaceBackground` (L=0 in v1) | Solar direct TOA (unattenuated) | Astronomical sun direction, observer geometry |
| `ground_test` | Short-range outdoor test range (atmospheric path negligible) | `UserSpectralBackground` (required, no default) | User-supplied (ambient solar or controlled) | Test-range sun direction and sensor boresight |
| `lab_test` | Indoor calibration, optical bench, vacuum chamber | `UserSpectralBackground` (required, no default) | User-supplied controlled source, or none (dark cal) | Source-axis and sensor-axis in chamber frame |

**Validation**:
- `space` requires LOS clear of Earth; raises if intercepts (v1 has no earthlimb).
- `ground_test` and `lab_test` require explicit `UserSpectralBackground` — no sensible defaults.
- For `lab_test`, illumination can be `None` (dark cal / blackbody-standard measurement).

**Not the same as `at_aperture`**: lab/ground-test sub-cases run source physics from first principles (ε, T, ρ, illumination → L at target). `at_aperture` bypasses source physics entirely by accepting `L_t_aperture(λ)` as given. Choose `at_aperture` when you have a pre-computed radiance; choose `no_atmosphere (lab_test)` when you want RADIANT to derive radiance from material + T + illumination.

#### Summary statistics

- **Total primary cells** (4 target locations × 5 regimes × 3 scene types): 60
- **Valid primary cells**: 50
- **Invalid primary cells (at_aperture × sub_pixel/point_source)**: 10
- **Additional `no_atmosphere` sub-case cells** (ground_test: 15, lab_test: 15): 30
- **Total cataloged cells (including sub-cases)**: 90
- **Cells with no background (computed extended scenes)**: 15
- **Cells requiring ground parameters (ε_g, T_g)**: 30
- **Cells with cold-space background**: 10 (space sub-case only)
- **Cells with user-supplied spectral background**: 30 (ground_test + lab_test)
- **Cells requiring mixed emit+reflect target model**: all MWIR cells (15 valid in primary + mixed-or-thermal in sub-cases)

#### Edge cases flagged

- **SWIR "mixed if hot"** (cells 22–24, 37–39, 52–54): SWIR is usually reflective-dominated, but targets above ~700 K have measurable thermal emission. Validator checks `T_t` against a regime-dependent threshold and requires mixed model if crossed.
- **MWIR point_source with pure thermal** (cells 27, 42, 57): if ρ ≈ 0 (e.g., hot plume), thermal-only is sufficient and solar illumination is skipped. Validator must not force mixed model when ρ vanishes.
- **Thermal downwelling in MWIR** (cells 25–26, 40–41): the "diffuse sky" component of illumination is dominated by atmospheric thermal emission, not scattered solar. Same equation, very different internal weighting — open question #6 requires AtmosphereStage to publish scattered-solar and atm-thermal components separately.

---

## 4. Descriptor Schemas

### 4.1 TargetDescriptor

Published by SourceStage. No radiance — only material properties, geometry classification, and (for at-aperture) user-supplied radiance.

```
TargetDescriptor (base):
  scene_type: "extended" | "sub_pixel" | "point_source"
  target_location: "at_aperture" | "terrestrial" | "airborne" | "no_atmosphere"
  no_atmosphere_subcase: "space" | "ground_test" | "lab_test" | None   # required iff target_location == "no_atmosphere"
  h_tgt: float [m]                    # required except at_aperture

Concrete variants by target location × scene type combine:
  - Material: ε(λ), T_t (thermal) OR ρ(λ) (reflective, derived via Kirchhoff)
  - Geometry: A_t, shape (sub_pixel); or none (point_source intensity carries A); or none (extended)
  - Radiance: L_t_aperture(λ) or I_t_aperture(λ) (at_aperture only)
```

**Parameterization by scene type**:

| Scene type | T1 thermal | T2 reflective | T3 mixed | T5 at-aperture |
|---|---|---|---|---|
| extended | ε(λ), T_t | ρ(λ) | ρ(λ), T_t | L_t_aperture(λ) |
| sub_pixel | ε(λ), T_t, A_t, shape | ρ(λ), A_t, shape | ρ(λ), T_t, A_t, shape | N/A |
| point_source | ε(λ), T_t, A_t (→ I = εBA) | ρ(λ), A_t (→ I) | ρ(λ), T_t, A_t | N/A |

### 4.2 BackgroundDescriptor

Published by SourceStage. Populated only for point_source / sub_pixel / at_aperture targets; absent for computed extended targets.

```
BackgroundDescriptor (base, discriminated by background_type)

AtApertureBackground:
  L_bg_aperture: SpectralData | None = None   # W/m²/sr/µm; None → zero

ColdSpaceBackground:
  # no parameters in v1; L_bg = 0

GroundBackground:
  epsilon: SpectralData    # ε(λ); ρ(λ) = 1 − ε(λ) derived via Kirchhoff
  T_g: float [K]           # scalar, 150–350 K typical

UserSpectralBackground:
  L_bg: SpectralData       # W/m²/sr/µm; user-supplied spectral radiance
  # Used for no_atmosphere sub-cases ground_test and lab_test.
  # Distinct from AtApertureBackground because source physics still runs (atmosphere is A0 pass-through, not full bypass).
```

**Validation**:
- `AtApertureBackground` requires `target_location == "at_aperture"`
- `ColdSpaceBackground` requires `target_location == "no_atmosphere"` with `no_atmosphere_subcase == "space"` and LOS clear of Earth
- `UserSpectralBackground` valid for `no_atmosphere` sub-cases `ground_test` and `lab_test`; required (no default)
- `GroundBackground` valid for `terrestrial`, `airborne`
- Kirchhoff: `0 ≤ ε(λ) ≤ 1`
- T_g in physical range [150, 350] K (warn outside, error if extreme)

### 4.3 LineOfSightGeometry

Lives in `src/radiant/core/los_geometry.py` (new file, per Rule 19).

```
@dataclass(frozen=True)
class LineOfSightGeometry:
    h_tgt: float              # m, target altitude above MSL
    h_atm_top: float = 1e5    # m, top of atmospheric integration (Kármán line)
    theta_o: float            # rad, observer zenith at target
    theta_s: float | None     # rad, solar zenith at target
    delta_phi: float | None   # rad, relative azimuth φ_s − φ_o ∈ [−π, π]

    @property
    def slant_range_atm(self) -> float: ...      # m, LOS from h_tgt to h_atm_top, spherical Earth
    @property
    def path_airmass_up(self) -> float: ...      # dimensionless, airmass factor for up-leg
```

**Input-boundary converter** (also in this file): `theta_o_from_eta(eta, h_sensor, h_tgt)` using corrected sine rule `sin(θ_o) = (R_E + h_sensor)/(R_E + h_tgt) · sin(η)` — Rule 2 compliance (conversion once at boundary).

**Validation**:
- `h_tgt ∈ [0, h_atm_top]`
- `h_atm_top = 1e5 m` fixed in v1
- `θ_o ∈ [0, π/2)`; grazing warning; beyond = raise
- `θ_s ∈ [0, π]` if provided; downstream reflective terms zero when θ_s > π/2
- `Δφ ∈ [−π, π]` if provided

### 4.4 SensorDescriptor — SUPERSEDED by ADR-0006 (2026-07-12)

The deferred design review happened: sensor altitude and all other scene-geometry
inputs live in the `geometry.*` parameter namespace owned by `GeometryStage`
(stage 0), not in a separate descriptor object. See
[docs/adr/0006-geometry-stage.md](../adr/0006-geometry-stage.md) and
[RADIANT_Geometry.md](RADIANT_Geometry.md).

---

## 5. Stage Responsibilities (Option C)

### SourceStage
Publishes data descriptors only, no radiance:
- `TargetDescriptor` (material, geometry classification, scene_type, target_location)
- `BackgroundDescriptor` (or absent for computed extended)
- `LineOfSightGeometry` (h_tgt, h_atm_top, θ_o, θ_s, Δφ)
- At-aperture: publishes user-supplied `L_t_aperture(λ)` / `L_bg_aperture(λ)` into the descriptors

### AtmosphereStage
Consumes SourceStage's descriptors; performs propagation and assembly:
1. Computes atmospheric quantities from its own parameters + `LineOfSightGeometry`:
   - `τ_sun(λ; h_tgt, θ_s)`, `τ_up(λ; h_tgt, θ_o)`, `τ_full,up(λ; 0, θ_o)`
   - `E_TOA(λ)` solar spectrum
   - `E_sky,↓(λ, h_tgt)` downwelling hemispheric irradiance
   - `L_path,up(λ; h_tgt, θ_o)`, `L_path,full(λ; 0, θ_o)`
2. Assembles at-aperture spectral radiance:
   - For at_aperture: pass-through of user descriptor
   - For terrestrial / airborne / no_atmosphere: apply the appropriate form of the assembly equation (see §6)
3. Publishes `L_t,aperture(λ)` and `L_bg,aperture(λ)` into ChainState frames

### Downstream stages
OpticsStage onward consume already-propagated spectral radiances. No further radiometry of source/atmosphere type; only spatial transfer (PSF path + MTF product path, Rule 4), EE_box (Rule 9), spectral integration (Rule 8), detector response, readout, performance.

---

## 6. Reference Assembly Equations

### 6.1 Airborne target, MWIR (mixed, A3, full case)

```
L_t,aperture(λ) = [  ε(λ)·B(λ, T_t)                              ← self-emission
                   + ρ(λ)·τ_sun(λ)·E_TOA(λ)·cos(θ_s)/π            ← direct solar reflection
                   + ρ(λ)·E_sky,↓(λ, h_tgt)/π                     ← diffuse downwelling reflection
                  ] · τ_up(λ, h_tgt→h_atm_top, θ_o)
                + L_path,up(λ, h_tgt→h_atm_top, θ_o)

L_bg,aperture(λ) = [ε_g(λ)·B(λ, T_g) + ρ_g(λ)·E_g(λ)/π] · τ_full,up(λ, 0→h_atm_top, θ_o)
                 + L_path,full(λ, 0→h_atm_top, θ_o)
```

Kirchhoff: `ε(λ) = 1 − ρ(λ)` for target; `ε_g = 1 − ρ_g` for ground.

### 6.2 Special-case reductions

| Case | Reduces to |
|---|---|
| LWIR airborne, ρ≈0 | `ε·B·τ_up + L_path,up` (pure emitter) |
| VIS/NIR terrestrial, ε≈0 | `ρ·τ_sun·E_TOA·cos(θ_s)·τ_full,up/π + ρ·E_sky·τ_full,up/π + L_path,full` (pure reflector) |
| Exo-atmospheric (A0) | Atmosphere quantities → {τ=1, L_path=0, E_sky=0}; equation collapses to `ε·B + ρ·E_TOA·cos(θ_s)/π` |
| At-aperture | Pass-through: `L_t,aperture = user_L_t_aperture` |

Each reduction is a testable truth anchor for Category C validation.

---

## 7. Invalid Combinations (Schema-Level Errors)

The schema validator must reject combinations where the physics is ill-defined. Non-exhaustive list:

| Combination | Reason | Resolution |
|---|---|---|
| `at_aperture` + `sub_pixel` or `point_source` | At-aperture is extended-only per decision 2 | Raise `ParameterBoundsError` |
| `no_atmosphere (space)` + LOS intercepts Earth | v1 has no earthlimb model | Raise |
| `no_atmosphere (ground_test / lab_test)` without `UserSpectralBackground` | No sensible default for test-range / chamber radiance | Raise |
| `target_location == "no_atmosphere"` without `no_atmosphere_subcase` | Ambiguous sub-case | Raise |
| `terrestrial`/`airborne` without `GroundBackground` | No sensible default for (ε, T_g) | Raise |
| Specifying both ε(λ) and ρ(λ) for target or ground | Over-specification (violates Kirchhoff derivation rule) | Raise |
| MWIR scene with T1 or T2 alone (not T3) | MWIR requires mixed model for ambient targets | Warn (user may know what they're doing) or raise depending on ambient check |
| Point-source target with resolved angular size | `√A_t/d > 0.1 · PSF_FWHM` | Raise |
| `T_g ∉ [150, 350] K` | Physically implausible Earth surface | Warn if 150–350 boundaries; raise if far outside |
| `θ_o > π/2` | Target beyond horizon from sensor | Raise |
| `θ_s > π/2` with reflective-only target (T2) in a detection use case | Sun below horizon, zero reflected signal expected | Warn (physical, not error) |

---

## 8. Open Questions (Not Yet Resolved)

These are known-unresolved and expected to come up during implementation or subsequent design review:

1. **Illumination descriptor**: does SourceStage publish a separate `IlluminationDescriptor` (solar spectrum source, solar geometry, user override for E_sky), or is illumination purely an AtmosphereStage concern with solar spectrum loaded from a file internally? Probably the latter, but worth confirming.

2. **Point-source schema dual form**: user may specify point-source target either as (ε, T, A_t) → internal I = εBA, or as raw I(λ). Both need to route through the same downstream path; schema should accept either with a discriminator.

3. **MODTRAN / atmosphere backend for partial columns**: current atmosphere integration likely assumes full-column terrestrial paths. Partial columns (A3 for airborne targets) require τ at arbitrary h_tgt. Need to confirm backend supports this or scope an extension.

4. **Invalid-combination coverage**: §7 is non-exhaustive. Comprehensive validation matrix needs to be generated, likely as a table indexed by (target_location × scene_type × wavelength_regime × target_model) with allowed/forbidden cells marked.

5. **Cross-stage consistency at Option C boundary**: need an integration test that verifies AtmosphereStage's assembly produces identical outputs to the pre-Option-C implementation for the terrestrial LWIR-emitter case (regression anchor).

6. **Diffuse E_sky decomposition**: internally AtmosphereStage should produce E_sky,↓ with separable scattered-solar and atm-thermal components, so we can audit which dominates per regime. Report both; consume the sum.

7. **v2 evolution cleanliness**: schema fields named for v1 (like `ColdSpaceBackground` with no params) must not need renaming when v2 adds zodiacal light / diffuse galactic contributions. Current design allows additive fields; verify no assumptions are baked in that would force a breaking change.

---

## 9. v2 Deferred Items (Summary)

Tagged throughout this doc; consolidated here:

- Airborne sensor and ground-based sensor (new h_sensor altitude regimes)
- Ellipsoidal Earth (WGS84)
- Atmospheric refraction
- Earthlimb background model (B4)
- Cloud background / material / atmospheric layer (B5)
- Diurnal / solar-heating thermal response for ground (T_g(t))
- Per-pixel background texture (non-uniform scenes)
- BRDF reflective target model (T4)
- Plume / line emission target model (T6)
- Non-solar illumination (moonlight, lasers, active sources) (I3)
- Sky-path background for upward-looking sensors (B2)
- Zodiacal / stellar / diffuse-galactic contributions to ColdSpaceBackground
