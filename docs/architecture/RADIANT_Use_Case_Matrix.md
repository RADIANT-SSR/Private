# RADIANT Use-Case Matrix

**Status**: Active — reworked 2026-07-26 under Geometry-Flexibility **Phase 0** (Category A, docs only). Two changes: the observer location becomes an explicit axis (§1.4), and scenes are defined **compositionally** (§3.2) instead of enumerated cell-by-cell. Decision record: [ADR-0011 — Generalized viewing geometry](../adr/0011-generalized-viewing-geometry.md), authored in the same PR; execution plan: [`docs/plans/Geometry_Flexibility_Plan.md`](../plans/Geometry_Flexibility_Plan.md); source audit: [`docs/reports/geometry_flexibility_2026-07/findings.md`](../reports/geometry_flexibility_2026-07/findings.md).

**Scope**: this document captures the axes, locked decisions, composition rules, and descriptor schemas for the imaging-scenario space. It governs how GeometryStage, SourceStage, AtmosphereStage, and downstream stages consume user inputs. Three tiers, and the difference between them is load-bearing:

- **Supported today (runs, tested, golden-backed).** Space-based sensors (the v1 baseline: space→ground, space→air, space→space down-looking) **and airborne down-looking sensors** — air-to-ground was ratified as already-supported on 2026-07-26 (plan §8.1 item 3, audit finding GF-6): nothing validates `h_sensor ≥ h_atm_top`, `SimpleAtmosphere` integrates optical depth between the two endpoint altitudes, and the MODTRAN deck builder already emits H1/H2 pairs for an in-atmosphere sensor. The pre-2026-07-26 scope sentence ("sensor location is fixed to `space` in v1") described an intent the code never enforced; it is superseded here (locked decision 15).
- **Ratified for delivery, NOT yet implemented.** Ground-based and up-looking observers, equal-altitude/horizontal paths, sky-along-LOS backgrounds, per-altitude solar illumination, and direction-aware metrics. These are ratified in ADR-0011 and scheduled by plan §4 (Phases 1–5). **The code restriction remains fully in force until Geometry-Flexibility Phase 1 lands**: `core/viewing_triangle.py::_validate_altitudes` raises `ParameterBoundsError` unless `h_sensor > h_target` ("v1 has no uplooking geometry"), and $\theta_o \in [0, \pi/2)$ is enforced independently in `viewing_triangle._validate_theta_o`, `LineOfSightGeometry.__post_init__`, and `AtmosphericGeometry.__post_init__` (ceiling 89.5°). Every up-looking, ground-based, and equal-altitude scene **raises today**. Wherever this document describes such a scene it is describing ratified intent, and says so explicitly.
- **Still deferred.** Clouds, ellipsoidal Earth, atmospheric refraction, earthlimb/limb radiance, BRDF, plume/line emission, diurnal ground thermal response, per-pixel background texture (§9).

**Related documents**:
- `RADIANT_Master_Architecture.md` — the non-negotiable rules (especially 2, 4, 9, 10, 11, 12)
- `RADIANT_Signal_Chain_Architecture.md` — Stage protocol, ChainState
- `RADIANT_Conventions.md` — canonical units, coordinate frame
- `RADIANT_Geometry.md` — GeometryStage contract, input modes (ADR-0006)
- `RADIANT_Atmosphere.md` — atmosphere backend (MODTRAN integration)
- `RADIANT_Target_Definition_Matrix.md` — expansion of the T-code axis
- [ADR-0011](../adr/0011-generalized-viewing-geometry.md) — generalized viewing geometry (supersedes the 2026-07-11 down-looking-only ruling)

---

## 1. Axes

Four independent axes define a use case. Target/atmosphere/background/illumination models are the *dependent outputs* of the axes (§3.2), not additional axes. Axes 1.1–1.3 are original; axis 1.4 (observer location) was implicit — pinned to `space` — until the 2026-07-26 ratification made it explicit.

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
| VIS | 0.4–0.7 | Solar reflection | Ground reflection / scattered sky |
| NIR | 0.7–1.0 | Solar reflection | Ground reflection / scattered sky |
| SWIR | 1.0–2.5 | Solar reflection (thermal emerges for hot targets) | Ground reflection |
| MWIR | 3–5 | **Mixed** — emission + reflection both matter | Mixed: ground emission + reflected solar; sky thermal emission for up-looking |
| LWIR | 8–14 | Thermal emission | Ground thermal emission; sky thermal emission for up-looking |

Regime affects which terms in the radiance assembly equation dominate and which atmospheric quantities (τ_sun, E_sky-scatter, L_path thermal) matter most. MWIR always requires the mixed target model (T3) for ambient-temperature scenes.

### 1.3 Target location

| Value | Definition | Observer-leg path type (down-looking) |
|---|---|---|
| `at_aperture` | Radiance specified at sensor pupil; no propagation | A0 (none) |
| `terrestrial` | At or near surface (h_tgt ≲ 1 km) | A2 (full two-way: solar down, sensor up) |
| `airborne` | In the atmosphere (1 km ≲ h_tgt ≲ 30 km); A3 degrades smoothly to A0 as h_tgt → TOA | A3 (partial two-way) |
| `no_atmosphere` | No significant atmospheric propagation between target and sensor. Covers space targets (h_tgt ≳ 100 km), short-range ground test ranges, and lab / chamber test setups. | A0 (none) |

`target_location` remains a **declared descriptor field** (`TargetDescriptor.target_location`, plus `no_atmosphere_subcase`), not a derived one. It selects the source-physics preset; the *path* code is derived from the altitude pair per Rule A (§3.2.3).

### 1.4 Observer location (explicit since 2026-07-26)

| Value | Definition | Status |
|---|---|---|
| `space` | `h_sensor > h_atm_top` (100 km) | Supported today — the v1 baseline |
| `air` | 1 km ≲ `h_sensor` ≲ 100 km | Down-looking (`h_sensor > h_target`): **supported today** (ratified, GF-6). Level and up-looking arms: ratified, Phase 1–2 |
| `ground` | `h_sensor` ≲ 1 km | Ratified, **not implemented** — every such scene needs either an up-looking or an equal-altitude path, both rejected by the current code |

Observer location is **not a user switch**: it is a classification of `geometry.sensor_altitude_m`, exactly as target location classifies `geometry.target_altitude_m`. LOS direction (up / level / down) is likewise derived from the altitude pair and $\theta_o$, never entered (locked decision 17; `RADIANT_Geometry.md` §2 mode resolution is unchanged in form).

**Scene class** is the (observer, target) pair — the 3×3 taxonomy of plan §2. Per plan §8.1 item 8 it is **derived, never mandatory**: computed from `h_sensor`, `h_target`, $\theta_o$ and published with `Provenance.DERIVED`; physics never branches on it (it drives defaults, metric relevance, validation, and GUI composition only). An optional `geometry.scene_class` enum lets a user *assert* intent and raises `GeometrySpecificationError` on disagreement with the derivation. **Neither the derived output nor the assertion parameter exists in code today** — both are Phase 1/3 deliverables (locked decision 19).

---

## 2. Locked Decisions

Decisions made during design review, in order. Decisions 1–14 are the original v1 record and are preserved verbatim; where the 2026-07-26 ratification changes one, the supersession is annotated in place and the replacement is appended as a new decision (history is not rewritten).

1. **Target location axis** = {`at_aperture`, `terrestrial`, `airborne`, `no_atmosphere`}. `airborne` is a first-class value, distinct from `terrestrial` because the partial-column atmosphere (A3) is physically different from the full-column case (A2). `no_atmosphere` is the umbrella for all A0 scenarios — space targets, short-range ground tests, and lab / chamber tests — which share "no propagation" but differ in default background and illumination (see §3.3 sub-cases).

2. **Scene type axis** = {`extended`, `sub_pixel`, `point_source`}. Distinction is radiometric: extended/sub_pixel are parameterized by spectral radiance + (optional) area; point_source by spectral intensity (area pre-integrated). `at_aperture` target location is restricted to `extended` only.

3. **Sensor location** = `space` only in v1; airborne and ground deferred to v2. Atmosphere model parameterization is kept on (h_source, h_destination) so v2 expansion is additive rather than breaking.
   → **SUPERSEDED 2026-07-26 by decision 15** (ADR-0011). The scope statement was never enforced in code (GF-6); air-to-ground is ratified as supported now, and ground/up-looking observers are ratified for delivery. The "(h_source, h_destination)" parameterization noted here is precisely why the expansion is additive — that part still holds.

4. **Radiance assembly owned by AtmosphereStage (Option C)**. SourceStage publishes `TargetDescriptor`, `BackgroundDescriptor`, and `LineOfSightGeometry` (no radiance). AtmosphereStage consumes these plus atmospheric quantities and produces at-aperture `L_t(λ)` and `L_bg(λ)`.

5. **Kirchhoff consistency**: for target and ground-background material inputs, accept `ε(λ)` only; derive `ρ(λ) = 1 − ε(λ)` for opaque Lambertian. Over-specification (both ε and ρ) is a schema error.

6. **At-aperture API**: user supplies `L_t_aperture(λ)` (required) + `L_bg_aperture(λ)` (optional, default 0). Forced extended-only. AtmosphereStage becomes validated pass-through; warns if atm parameters were supplied.

7. **AtmosphereStage geometry contract** = `LineOfSightGeometry` with {`h_tgt`, `h_atm_top`, `θ_o`, `θ_s`, `Δφ`}. Physical sensor altitude lives in `geometry.sensor_altitude_m`, owned by `GeometryStage` (ADR-0006 — the SensorDescriptor concept was superseded; see §4.4).
   → **AMENDED 2026-07-26 by decision 17**: `h_sensor` joins the contract object in Phase 1 (GF-3), retiring the backend side-load of `geometry.sensor_altitude_m` in the same PR (guardrail G2). Field set and semantics are unchanged today.

8. **Earth model**: spherical, `R_E = 6371.0 km` (mean radius) in v1. Ellipsoidal (WGS84) is v2. *(Still deferred — §9.)*

9. **Atmospheric refraction**: not modeled in v1. v2 only; becomes relevant at grazing geometries (θ_o → π/2).
   → **AMENDED 2026-07-26 by decision 18**: still not modeled, but the grazing band now gets explicit guards (hard raise inside ±0.5° of horizontal; compute-with-`UserWarning` out to ≈±2°) instead of being unreachable by construction.

10. **`LineOfSightGeometry` module split**: lives in its own file `src/radiant/core/los_geometry.py` per Rule 19. (`core/geometry.py`'s flat-Earth `ObserverGeometry`/`SceneGeometry` dataclasses were deleted 2026-07-12 — CU-094/ADR-0006; the module keeps the spherical helper functions.)

11. **BackgroundDescriptor types (v1)**: four variants — `AtApertureBackground`, `ColdSpaceBackground`, `GroundBackground`, `UserSpectralBackground`. Earthlimb and cloud deferred to v2. For `no_atmosphere (space)` sub-case, if LOS intercepts Earth, raise (no v1 earthlimb model). `UserSpectralBackground` covers ground-test / lab-test sub-cases where the user supplies test-range or chamber radiance.
    → **EXTENDED 2026-07-26 by decision 20**: a fifth variant, `SkyBackground` (B2), is ratified for Phase 2. Earthlimb (B4) and cloud (B5) remain deferred.

12. **Ground background**: homogeneous across the scene, scalar `T_g`, no diurnal / solar-heating thermal response, no per-pixel texturing. All deferred to v2.

13. **Background absent for computed extended regime**: no BackgroundDescriptor populated; SpectralIntegrationStage skips background photon term.

14. **Default background selection**:
    - `at_aperture` → `AtApertureBackground(L_bg_aperture=None)` (treated as zero)
    - `no_atmosphere` → depends on sub-case: `space` → `ColdSpaceBackground` (or raise if LOS intercepts Earth); `ground_test` and `lab_test` → user **must** supply a `UserSpectralBackground`
    - `terrestrial` / `airborne` → user **must** supply `GroundBackground` explicitly (no sensible default ε, T_g)
    → **GENERALIZED 2026-07-26 by decision 16 / Rule B (§3.2.5)**: the selector becomes *where the LOS terminates* rather than *what the target location is*. Every branch above is reproduced exactly by the termination test for today's down-looking scenes; the new branches (sky termination) are additions, not changes.

**Ratification of 2026-07-26** (Geometry Flexibility plan §8.3; owner-ratified in full). Each item below is a decision of ADR-0011 as it lands in this document:

15. **Observer location is a free axis; air-to-ground is supported now.** `h_sensor` is not restricted to `space`. Air-to-ground (airborne sensor, down-looking) is ratified as supported today (GF-6). Ground-based and up-looking observers are ratified for delivery; the enforcing code restriction (`h_sensor > h_target`, $\theta_o \in [0, \pi/2)$) stays in force until plan Phase 1 lands. Supersedes decision 3.

16. **Scenes are composed, not enumerated.** A scene = observer leg × illumination leg × LOS-termination background, with the target model selected by regime and material. Adding the observer axis by enumeration would roughly triple an already 60-row matrix and pull the code toward per-cell match arms; the composition rules (§3.2) are normative and the matrix carries exactly one worked example per scene class (§3.4). This is the plan's highest-leverage anti-spaghetti decision, companion to guardrails G1–G4 (plan §3.5).

17. **Canonical representation extended, not duplicated.** The target-referenced $\theta_o$ stays canonical with its domain extended to $[0, \pi)$: $\theta_o < \pi/2$ = sensor above the target's horizon plane (all of today), $\theta_o > \pi/2$ = sensor below it (up-looking). Path segments are keyed to the **lower endpoint** (matching the MODTRAN Card-3 convention already implemented); transmittance is reciprocal, radiance products are direction-specific. `h_sensor` joins `LineOfSightGeometry` (amends decision 7). New codes enter the catalogs: **A1** (up-path observer leg) and **A5** (constant-altitude horizontal arm), both Phase-2 pending.

18. **Limb, refraction, and ellipsoidal Earth stay excluded — with hard guards.** Paths within ±0.5° of the geometric horizon raise; the shoulder from ±0.5° to ≈±2° computes and emits a `UserWarning` quantifying the refraction-excluded caveat (so long-range air-to-air is usable at first delivery). Limb-crossing radiance/earthlimb backgrounds remain declined for v1.x (finding GF-11). Amends decision 9.

19. **Scene class is derived, never mandatory — with an optional validated assertion.** See §1.4. Not implemented today.

20. **Sky background (B2 / `SkyBackground`) is ratified, band-gated at first delivery.** MWIR/LWIR sky backgrounds ship in Phase 2; VIS/NIR sky computes but carries a "provisional — single-scatter underestimates daytime sky" `UserWarning` until MODTRAN-anchored. Extends decision 11.

21. **Illumination becomes per-altitude.** The global $\theta_s < \pi/2$ bound is replaced by a shadow-height test — the target is sunlit iff its altitude exceeds the terminator shadow height for the given solar depression — enabling sunlit-target-over-dark-ground (GF-9). **Today the global bound is enforced**: `geometry.solar_zenith_rad` is bounded at 1.5707 rad by the schema and `AtmosphericGeometry.__post_init__` raises for $\theta_s \geq \pi/2$; night scenes are expressed only through `geometry.solar_illumination = "night"` (mode S0, θ_s = Δφ = None). Phase 2.

---

## 3. Scene Composition

The v1 form of this section spelled out all 60 primary cells (4 target locations × 5 regimes × 3 scene types) plus 30 `no_atmosphere` sub-case cells in five tables. Enumeration does not survive a second location axis (locked decision 16), so §3.2 states the **rules that generate those cells** and §3.4 carries one worked example per scene class. The executable form of the enumeration is retained where it belongs — `tests/integration/test_use_case_matrix.py` (90-cell sweep) and `tests/integration/test_table_c_cells.py` — see §3.5.

### 3.1 Model-catalog references

**Target radiance models (T-codes)**:
- `T1` — Graybody thermal: `L_t = ε(λ)·B(λ, T_t)`. Parameters: ε(λ), T_t
- `T2` — Lambertian reflective: `L_t = ρ(λ)·E_illum(λ)/π`. Parameters: ρ (or ε + Kirchhoff), illumination from AtmosphereStage
- `T3` — Mixed emit + reflect: `L_t = ρ·E/π + ε·B(T_t)`. Opaque Lambertian with Kirchhoff. Mandatory for MWIR.
- `T4` — BRDF reflective (deferred, §9)
- `T5` — User-provided spectral radiance or intensity (used by `at_aperture`)
- `T6` — Plume / line emission (deferred, §9)

**Atmosphere path codes (A-codes)** — each names the **observer leg** (the column between target and sensor). A2/A3/A4 additionally bundle the down-looking solar leg for historical reasons; A0/A1/A5 name the observer leg only and pair with an explicit I-code (§3.2.4). This is the direction the segment abstraction of guardrail G1 takes the contract in Phase 2.
- `A0` — None (at_aperture; space-to-space with no atmospheric column; negligible-path test setups)
- `A1` — **Up-path only** (sensor below target: column `h_sensor → h_tgt`, zenith taken at the lower endpoint). *Was "ground-based sensor; v2".* **Ratified 2026-07-26 (ADR-0011); implementation is plan Phase 2** — not reachable today, because the geometry gate rejects `h_sensor ≤ h_target` first.
- `A2` — Full two-way: τ_sun (TOA→surface), τ_up (surface→sensor), L_path, E_sky. The up-leg terminates at the **sensor** altitude — `h_atm_top` for a space observer, `h_sensor` for an airborne one. That endpoint generality is what makes air-to-ground work today (GF-6).
- `A3` — Partial two-way: τ_sun (TOA→h_tgt), τ_up (h_tgt→sensor), plus background path τ_full,up
- `A4` — Emission-only two-way (no solar down-leg): LWIR terrestrial
- `A5` — **Horizontal constant-altitude arm** (equal or near-equal endpoint altitudes): Beer-Lambert at local density in the simple model, MODTRAN `ITYPE=1`. **New code, ratified 2026-07-26; implementation is plan Phase 2** — not reachable today (equal altitudes survive only as the degenerate collocated carve-out with no viewing triangle, GF-1).

**Background codes (B-codes)** — selected by where the LOS terminates (§3.2.5):
- `B0` — None / at-aperture pass-through
- `B1` — ColdSpaceBackground (L = 0 in v1)
- `B2` — **Sky radiance along the LOS** (`SkyBackground`): the atmospheric column the ray traverses beyond the target before reaching space, for up-looking and near-horizontal paths. *Was "sky path looking up (v2)".* **Ratified 2026-07-26 (locked decision 20); implementation is plan Phase 2, band-gated** (MWIR/LWIR at first delivery; VIS/NIR provisional with a `UserWarning`). Not reachable today.
- `B3` — GroundBackground
- `B4` — Earthlimb — **declined for v1.x** (GF-11); a limb-crossing termination raises
- `B5` — Cloud (deferred, §9)

**Illumination codes (I-codes)**:
- `I0` — None (pure thermal; night mode S0; ρ ≈ 0 targets)
- `I1` — Solar direct at TOA, attenuated to target altitude (unattenuated when the target is above `h_atm_top`)
- `I2` — Solar direct + diffuse sky hemispheric irradiance at target
- `I3` — Non-solar (moon / laser / active) — deferred, §9

### 3.2 Composition rules (normative)

A scene is generated, not looked up:

$$\text{scene} \;=\; \underbrace{\text{observer leg}}_{\text{Rule A}} \;\times\; \underbrace{\text{illumination leg}}_{\text{Rule I}} \;\times\; \underbrace{\text{LOS-termination background}}_{\text{Rule B}}$$

with the target model chosen by Rule T and its parameterization by Rule S. The inputs the rules read are exactly the axes of §1 plus the two altitudes and three angles GeometryStage publishes: `h_sensor`, `h_target`, $\theta_o$, $\theta_s$, $\Delta\phi$.

Two derived selectors (both classifications of existing numbers, neither a new user switch):

- **Scene class** $= (C_{obs}, C_{tgt})$, each $\in$ {ground ($h \lesssim 1$ km), air (1–100 km), space ($h > h_{atm,top}$)}. Derived per §1.4; **not implemented today**.
- **LOS direction** — down ($\theta_o < \pi/2$, sensor above the target's horizon plane), horizontal ($\theta_o \approx \pi/2$), up ($\theta_o > \pi/2$). Today only the down branch is reachable; the other two raise (§7).

#### 3.2.1 Rule T — target model from regime and material

| Condition | Target model | Notes |
|---|---|---|
| `target_location == at_aperture` | **T5** | User radiance at pupil; source physics bypassed. Forces `extended` (Rule S) |
| LWIR (8–14 µm) | **T1** | Thermal graybody; reflective term negligible for ambient scenes |
| VIS / NIR (0.4–1.0 µm) | **T2** | Lambertian reflective; ρ = 1 − ε by Kirchhoff |
| SWIR (1.0–2.5 µm) | **T2**, escalated to **T3** for hot targets | *Hot-target escalation*: targets above ≈700 K have measurable in-band thermal emission. The validator checks `T_t` against a regime-dependent threshold and **requires** the mixed model if crossed |
| MWIR (3–5 µm) | **T3 mandatory** | Emission and reflection are comparable for ambient-temperature scenes. Specifying T1 or T2 alone is a validation event (§7) |
| MWIR/SWIR with ρ ≈ 0 (e.g. hot plume, blackbody standard) | **T1** permitted | *Carve-out*: the validator must **not** force the mixed model when ρ vanishes — the solar term is identically zero and thermal-only is exact |

Rule T is independent of scene class and of LOS direction: the target's own radiance does not care who is looking at it. Direction enters through Rules A/I/B.

#### 3.2.2 Rule S — scene type fixes parameterization, not physics

| Scene type | What changes | Constraint |
|---|---|---|
| `extended` | Target radiance fills the IFOV; **no** BackgroundDescriptor is populated (locked decision 13) and SpectralIntegrationStage skips the background photon term | EE_box never applied (Rule 9) |
| `sub_pixel` | Adds `A_t` + `shape`; Ω_t = A_t/d² < Ω_pix | EE_box on the **target term only**; background term never gets EE_box (Rule 9). Warn + suggest reclassification when `√A_t/d ≪ PSF_FWHM` |
| `point_source` | Area pre-integrated into intensity `I_t(λ)` | EE_box applied; **raise** if the target is resolved (`√A_t/d > 0.1·PSF_FWHM`) |

`at_aperture` is restricted to `extended` (locked decision 2). All ten `at_aperture × {sub_pixel, point_source}` combinations are invalid and raise at descriptor construction (§7) — this is the entire invalid-cell population of the primary space (§3.5).

#### 3.2.3 Rule A — observer leg from path topology

Read the altitude pair and the declared target location; emit the A-code for the column between target and sensor. Transmittance is reciprocal, so one τ per segment suffices, computed with the zenith at the segment's **lower endpoint** (locked decision 17).

| Path topology (target ↔ sensor) | A-code | Status |
|---|---|---|
| `at_aperture` — propagation declared away | A0 | Supported today |
| `no_atmosphere (ground_test / lab_test)` — path short enough that τ ≈ 1 | A0 | Supported today |
| Both endpoints above `h_atm_top`, LOS does not re-enter the atmosphere | A0 | Down-looking supported today; up-looking (LEO→GEO) blocked **only** by the geometry gate — plan Phase 1 quick win |
| Sensor above a surface target, solar down-leg present | A2 | Supported today (up-leg ends at `h_sensor`, not necessarily `h_atm_top`) |
| Sensor above a surface target, no solar down-leg (LWIR / night) | A4 | Supported today |
| Sensor above an in-atmosphere target at altitude | A3 | Supported today; degrades smoothly to A0 as `h_tgt → h_atm_top` |
| **Sensor below the target** — column `h_sensor → h_tgt`, zenith at `h_sensor` | **A1** | Ratified; **raises today** (`h_sensor ≤ h_target`) — plan Phase 2 |
| **Equal / near-equal altitudes** — constant-altitude arm | **A5** | Ratified; **raises today** — plan Phase 2 |

Implementation note (current behavior, GF-3): `LineOfSightGeometry` does not carry `h_sensor`; `slant_range_atm` and `path_airmass_up` integrate target → top-of-atmosphere, and backends side-load `geometry.sensor_altitude_m` from params. Phase 1 puts `h_sensor` on the contract and deletes every side-load in the same PR (guardrail G2).

#### 3.2.4 Rule I — illumination leg

| Condition | I-code | Notes |
|---|---|---|
| `geometry.solar_illumination == "night"` (mode S0), or LWIR, or ρ ≈ 0 | **I0** | θ_s = Δφ = None; no direct-solar reflection and no single-scatter solar sky. Thermal self-emission and reflected *thermal* downwelling remain |
| Target above `h_atm_top` (A0 observer leg) | **I1** | Solar direct at TOA, unattenuated |
| VIS / NIR through an atmospheric column | **I2** | Direct + diffuse; the diffuse term is scattered solar |
| SWIR through an atmospheric column | **I1** | Diffuse scatter weak in-band |
| MWIR through an atmospheric column | **I2** | *Edge case preserved*: the "diffuse sky" component here is dominated by **atmospheric thermal emission**, not scattered solar — same equation, very different internal weighting. AtmosphereStage must publish the scattered-solar and atmospheric-thermal components separately (open question 6) |
| `no_atmosphere (ground_test / lab_test)` | user-supplied | Ambient solar or a controlled source; may be none (dark cal) — §3.3 |
| Moon / laser / active source | I3 | Deferred, §9 |

The illumination leg is independent of the observer leg: a ground-based sensor viewing a sunlit aircraft reads I2 on the TOA→`h_tgt` column while the observer leg is A1. That independence is why enumeration was collapsing under its own weight.

**Today**: the sun must be above the horizon everywhere in the scene ($\theta_s < \pi/2$, schema bound 1.5707 rad, `AtmosphericGeometry` raises at or beyond $\pi/2$). Locked decision 21 replaces this with a per-altitude shadow-height test in Phase 2; until then, sunlit-target-over-dark-ground and twilight scenes are inexpressible.

#### 3.2.5 Rule B — background from LOS termination

Follow the LOS **past the target** and ask where it ends. This is the generalization of locked decision 14: for every down-looking scene it selects exactly what decision 14 selected.

| LOS continuation terminates on | B-code / descriptor | Default | Status |
|---|---|---|---|
| *(nothing — computed `extended` target fills the pixel)* | none populated | n/a (locked decision 13) | Supported today |
| The pupil (`at_aperture`) | B0 — `AtApertureBackground` | `L_bg_aperture=None` → zero | Supported today |
| Earth's surface | B3 — `GroundBackground` | **none** — user must supply (ε_g, T_g) | Supported today |
| Space, without traversing an atmospheric column | B1 — `ColdSpaceBackground` | `ColdSpaceBackground` (L=0) | Supported today |
| Space, **through** an atmospheric column (up-looking, near-horizontal) | **B2 — `SkyBackground`** | B2 | Ratified; **not reachable today** — Phase 2, band-gated (decision 20) |
| A limb-crossing column (tangent point inside the atmosphere, no Earth intercept) | B4 — earthlimb | — | **Declined for v1.x** — raise (GF-11) |
| A test range or chamber wall | `UserSpectralBackground` | **none** — required | Supported today |
| A cloud deck | B5 | — | Deferred, §9 |

Preserved sub-rules: `no_atmosphere (space)` requires the LOS to be clear of Earth and **raises** if it intercepts (no v1 earthlimb model); `terrestrial` / `airborne` scenes with a non-extended target require an explicit `GroundBackground`; `ground_test` / `lab_test` require an explicit `UserSpectralBackground`.

#### 3.2.6 Rule V — validation

Applied after composition, before any physics runs (Rule 16). The full list of schema-level rejections is §7. The rules the enumeration used to carry cell-by-cell:

1. `at_aperture` accepts `extended` only (10 invalid combinations).
2. MWIR without T3 is a validation event — warn or raise on the ambient check; never silently accepted.
3. SWIR hot-target escalation is checked against `T_t`, not assumed.
4. The MWIR ρ ≈ 0 carve-out must not be overridden by the MWIR mandate.
5. Point-source with a resolved target raises; sub-pixel far below the PSF warns.
6. `T_g ∉ [150, 350]` K warns at the boundary and raises far outside.
7. Over-specification of ε and ρ (target or ground) raises.
8. `no_atmosphere` without `no_atmosphere_subcase` raises.
9. **Geometry gate (current behavior)**: `h_sensor ≤ h_target` raises, and $\theta_o \notin [0, \pi/2)$ raises. ADR-0011 replaces both with the extended domain plus the horizon guard band (decision 18); until Phase 1 lands they are unconditional.

### 3.3 `no_atmosphere` sub-cases (presets)

The `no_atmosphere` target location has three named sub-cases. They share A0 atmosphere and the same source-physics pipeline (target material + geometry → radiance via Planck, Kirchhoff, reflectance × illumination / π). They differ only in default BackgroundDescriptor and IlluminationDescriptor.

| Sub-case | Typical scenario | Default background | Default illumination | Geometry interpretation |
|---|---|---|---|---|
| `space` | Space-target imaging (SSA, space-to-space) | `ColdSpaceBackground` (L=0 in v1) | Solar direct TOA (unattenuated) | Astronomical sun direction, observer geometry |
| `ground_test` | Short-range outdoor test range (atmospheric path negligible) | `UserSpectralBackground` (required, no default) | User-supplied (ambient solar or controlled) | Test-range sun direction and sensor boresight |
| `lab_test` | Indoor calibration, optical bench, vacuum chamber | `UserSpectralBackground` (required, no default) | User-supplied controlled source, or none (dark cal) | Source-axis and sensor-axis in chamber frame |

**Validation**:
- `space` requires LOS clear of Earth; raises if it intercepts (v1 has no earthlimb).
- `ground_test` and `lab_test` require explicit `UserSpectralBackground` — no sensible defaults.
- For `lab_test`, illumination can be `None` (dark cal / blackbody-standard measurement).

Target physics runs normally in all three sub-cases across every regime and scene type: T1 for thermal, T2 for reflective, T3 when mixed (blackbody standards in the lab sub-case are the common T1 instance). The 30 sub-case cells the v1 tables spelled out are exactly Rule T × Rule S under a fixed (A0, user-background, user-illumination) composition.

**Not the same as `at_aperture`**: lab/ground-test sub-cases run source physics from first principles (ε, T, ρ, illumination → L at target). `at_aperture` bypasses source physics entirely by accepting `L_t_aperture(λ)` as given. Choose `at_aperture` when you have a pre-computed radiance; choose `no_atmosphere (lab_test)` when you want RADIANT to derive radiance from material + T + illumination.

The sub-case presets are **observer-agnostic**: a chamber measurement has no meaningful observer altitude class, and the ratification does not change these three rows.

### 3.4 Worked examples — one per scene class

Exactly one example per cell of the plan §2 taxonomy (observer × target ∈ {ground, air, space}²), spelled out in the style of the retired matrix rows. These are illustrations of §3.2, not an enumeration: any other regime/scene-type choice in the same class is generated by the same rules.

| # | Scene class (obs → tgt) | Example scenario | Regime / scene type | Target model | Atmosphere (observer leg) | Background | Illumination | Status |
|---|---|---|---|---|---|---|---|---|
| E1 | ground → ground | Two 30 m towers 8 km apart, level LOS (θ_o ≈ 90.04°; both endpoints inside each other's geometric horizon) | LWIR / point_source | Thermal graybody (**T1**) | Horizontal constant-altitude arm (**A5**) | Terrain beyond the target (**B3**, explicit ε_g, T_g) | None (**I0**) | **Ratified, not implemented** — Phases 1 + 2. Today equal altitudes hit the degenerate collocated carve-out (no viewing triangle, GF-1). Note the unresolved interaction with the ±0.5° hard guard of decision 18 — open question 10 |
| E2 | ground → air | Ground site tracking an aircraft at 10 km altitude, ~30 km slant range (θ_o ≈ 110°) | MWIR / point_source | **T3 mandatory** (T1 permitted if ρ ≈ 0, e.g. plume-dominated) | Up-path only, 0 → 10 km (**A1**) | Sky along the LOS (**B2**, MWIR — first-delivery band) | Solar direct + thermal downwelling (**I2**) | **Ratified, not implemented** — Phases 1 + 2. Owner priority 1 |
| E3 | ground → space | Ground SST site observing a satellite above `h_atm_top` | VIS / point_source | Lambertian reflective (**T2**) | Up-path full column, 0 → `h_atm_top` (**A1**); vacuum above | Sky along the LOS (**B2**, VIS — provisional, carries a `UserWarning` per decision 20) | Solar direct at TOA, unattenuated (**I1**) | **Ratified, not implemented** — Phases 1 + 2; credible spatial performance also needs the Gap 110 turbulence upgrade (Phase 3). Owner priority 4 |
| E4 | air → ground | Airborne sensor at 10 km imaging a surface target | MWIR / sub_pixel | **T3 mandatory** | Full two-way; up-leg terminates at `h_sensor` = 10 km, not `h_atm_top` (**A2**, with the **A4** thermal arm) | Ground (**B3**, explicit ε_g, T_g) | Solar direct + thermal downwelling (**I2**) | **Supported today** — ratified 2026-07-26 (decision 15, GF-6). Caveat: `h_sensor` reaches the backend by side-load, not the LOS contract (GF-3); Phase 1/G2 fixes the plumbing without changing results |
| E5 | air → air | Two aircraft at 10 km, 150 km apart, level LOS (θ_o ≈ 90.7°) | MWIR / point_source | **T3** (T1 if ρ ≈ 0) | Horizontal constant-altitude arm (**A5**) | Sky along the LOS (**B2**), inside the near-horizontal shoulder → computes with the refraction-caveat `UserWarning` (decision 18) | Solar direct at altitude (**I1**) | **Ratified, not implemented** — Phases 1 + 2. The *down-looking* sub-case (higher aircraft, lower aircraft) is already expressible via **A3** today; the level and up-looking arms are not. Owner priority 2 |
| E6 | air → space | Sensor at 12 km viewing a boosting target at 120 km | SWIR / point_source | **T2 escalated to T3** (hot-target rule, `T_t` ≳ 700 K) | Up-path partial column, 12 km → `h_atm_top` (**A1**) | Sky along the LOS with a cold-space terminus (**B2**) | Solar direct at TOA, unattenuated (**I1**) | **Ratified, not implemented** — Phases 1 + 2 |
| E7 | space → ground | Spaceborne imager, extended terrestrial scene | LWIR / extended | Thermal graybody (**T1**) | Emission-only two-way (**A4**) | **None populated** — extended target fills the pixel (locked decision 13) | None (**I0**) | **Supported today** — the v1 baseline |
| E8 | space → air | Spaceborne sensor, airborne target at 20 km | MWIR / point_source | **T3** | Partial two-way (**A3**) | Ground past the target (**B3**) | Solar direct + thermal downwelling (**I2**) | **Supported today** |
| E9 | space → space | LEO sensor viewing a lower space target (down); LEO → GEO (up) | VIS / point_source | Lambertian reflective (**T2**) | None (**A0**) | Cold space (**B1**); raises if the LOS intercepts Earth | Solar direct at TOA (**I1**) | **Down-looking supported today.** Up-looking is blocked by the geometry gate alone — the exo backends already handle it, making LEO → GEO the Phase 1 quick win. Owner priority 3 |

Reading the table: every "not implemented" row raises today at `core/viewing_triangle.py` (altitude ordering) or at one of the three $\theta_o$ validators, before any atmosphere code is consulted. No row describes behavior that is silently wrong — the restriction is loud (§7).

### 3.5 Semantic-preservation ledger

Every rule the retired tables encoded, and where it now lives. This ledger is the review artifact for the "no semantic loss" requirement of the Phase 0 conversion.

| Rule the enumeration carried | New home |
|---|---|
| `at_aperture` is extended-only; 10 invalid combinations | §1.1, Rule S (§3.2.2), Rule V.1, §7 |
| EE_box never in extended, target-term-only in sub_pixel/point_source (Rule 9) | Rule S |
| Sub-pixel → point-source collapse warning; resolved point source raises | Rule S, Rule V.5, §7 |
| MWIR requires the mixed model (T3) | Rule T, Rule V.2, §7 |
| MWIR pure-thermal carve-out when ρ ≈ 0 (old cells 27, 42, 57) | Rule T (last row), Rule V.4 |
| SWIR "mixed if hot" escalation ≈700 K (old cells 22–24, 37–39, 52–54) | Rule T, Rule V.3 |
| LWIR → T1; VIS/NIR → T2 | Rule T |
| A2 for surface targets, A3 for targets at altitude, A4 when no solar leg | Rule A |
| A3 degrades smoothly to A0 as `h_tgt → h_atm_top` (Table C altitude ladder) | §1.3, Rule A |
| Background absent for computed extended scenes | Rule B (first row), locked decision 13 |
| Default background selection by target location (locked decision 14) | Rule B — restated as a termination test that reproduces decision 14 exactly |
| Ground background must be explicit (no default ε_g, T_g) | Rule B, §7 |
| `no_atmosphere (space)` + LOS intercepts Earth → raise | Rule B, §3.3, §7 |
| `no_atmosphere` sub-cases: space / ground_test / lab_test presets (old Tables D, D-ground, D-lab) | §3.3 — **retained verbatim**, plus the "30 sub-case cells = Rule T × Rule S under a fixed A0 composition" statement |
| MWIR thermal-downwelling weighting of the "diffuse sky" term (old cells 25–26, 40–41) | Rule I (MWIR row), open question 6 |
| `T_g ∈ [150, 350]` K bounds | Rule V.6, §4.2, §7 |
| ε/ρ over-specification raises (Kirchhoff) | Rule V.7, locked decision 5, §7 |
| `no_atmosphere` without a sub-case raises | Rule V.8, §7 |

**Generated-cell counts** (unchanged by the conversion — a cross-check on the rules, not a table of contents):

- Primary combinations (4 target locations × 5 regimes × 3 scene types): **60**
- Valid primary: **50**; invalid primary (`at_aperture` × {sub_pixel, point_source}): **10**
- `no_atmosphere` sub-case cells (ground_test 15 + lab_test 15): **30**; total cataloged: **90**
- Cells with no background (computed extended): **15**
- Cells requiring ground parameters (ε_g, T_g): **30**
- Cells with cold-space background: **10** (space sub-case only)
- Cells with user-supplied spectral background: **30**
- Cells requiring the mixed model: all MWIR cells (15 valid primary; mixed-or-thermal in the sub-cases)

**Legacy cell numbering.** The retired tables numbered primary cells 1–60 in the order (target location: `at_aperture`, `terrestrial`, `airborne`, `no_atmosphere`) × (regime: VIS, NIR, SWIR, MWIR, LWIR) × (scene type: extended, sub_pixel, point_source), with the sub-case cells labelled G1–G15 and L1–L15 in the same regime × scene-type order. That numbering is still referenced by `tests/integration/test_use_case_matrix.py` (90-cell sweep), `tests/integration/test_use_case_warnings.py`, and `tests/integration/test_table_c_cells.py`, which are now the **executable** form of the enumeration — the doc holds the generating rules, the tests hold the cells. Their docstring references to "§3.2 (60 primary cells)" resolve here.

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

**Parameterization by scene type** (this is Rule S in schema form):

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

**Ratified addition, not yet implemented** (locked decision 20; plan Phase 2): a fifth variant `SkyBackground` (B2) carrying the sky radiance along the LOS for up-looking and near-horizontal terminations, band-gated at first delivery (MWIR/LWIR supported; VIS/NIR provisional with a `UserWarning`). No such class exists today.

### 4.3 LineOfSightGeometry

Lives in `src/radiant/core/los_geometry.py` (per Rule 19).

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

**Validation (current behavior)**:
- `h_tgt ∈ [0, h_atm_top]`
- `h_atm_top = 1e5 m` fixed
- `θ_o ∈ [0, π/2)`; **raises** outside — enforced here, in `viewing_triangle._validate_theta_o`, and (at 89.5°) in `AtmosphericGeometry`
- `θ_s ∈ [0, π]` accepted by this object if provided; the schema bound (1.5707 rad) and `AtmosphericGeometry` reject θ_s ≥ π/2 upstream, so a sub-horizon sun cannot reach here
- `Δφ ∈ [−π, π]` if provided

**Ratified changes, not yet implemented** (ADR-0011; plan Phase 1): `h_sensor` joins the contract (GF-3) and the object exposes a signed LOS direction; the θ_o domain extends to $[0, \pi)$ with the horizon guard band of decision 18; serialization round-trip extends back-compatibly. Every field and validator above is unchanged until that PR lands.

### 4.4 SensorDescriptor — SUPERSEDED by ADR-0006 (2026-07-12)

The deferred design review happened: sensor altitude and all other scene-geometry
inputs live in the `geometry.*` parameter namespace owned by `GeometryStage`
(stage 0), not in a separate descriptor object. See
[docs/adr/0006-geometry-stage.md](../adr/0006-geometry-stage.md) and
[RADIANT_Geometry.md](RADIANT_Geometry.md).

---

## 5. Stage Responsibilities (Option C)

### GeometryStage (stage 0, ADR-0006)
Resolves one input mode per family into the canonical representation and derives every geometric quantity exactly once — including the `LineOfSightGeometry` the Source → Atmosphere contract carries. It owns `h_sensor`, `h_target`, θ_o, θ_s, Δφ, and therefore owns the altitude ordering that Rule A reads. **Ratified addition (not implemented)**: publishing the derived scene class with `Provenance.DERIVED` and validating the optional `geometry.scene_class` assertion (§1.4, locked decision 19).

### SourceStage
Publishes data descriptors only, no radiance:
- `TargetDescriptor` (material, geometry classification, scene_type, target_location)
- `BackgroundDescriptor` (or absent for computed extended)
- `LineOfSightGeometry` (adopted from GeometryStage, descriptor-adjusted)
- At-aperture: publishes user-supplied `L_t_aperture(λ)` / `L_bg_aperture(λ)` into the descriptors

Rules T, S, and B are SourceStage's validation surface: it selects the target model from regime and material, enforces the scene-type parameterization, and populates (or omits) the background descriptor.

### AtmosphereStage
Consumes SourceStage's descriptors; performs propagation and assembly:
1. Computes atmospheric quantities from its own parameters + `LineOfSightGeometry`:
   - `τ_sun(λ; h_tgt, θ_s)`, `τ_up(λ; h_tgt, θ_o)`, `τ_full,up(λ; 0, θ_o)`
   - `E_TOA(λ)` solar spectrum
   - `E_sky,↓(λ, h_tgt)` downwelling hemispheric irradiance
   - `L_path,up(λ; h_tgt, θ_o)`, `L_path,full(λ; 0, θ_o)`
2. Assembles at-aperture spectral radiance:
   - For at_aperture: pass-through of user descriptor
   - Otherwise: apply the appropriate form of the assembly equation (see §6)
3. Publishes `L_t,aperture(λ)` and `L_bg,aperture(λ)` into ChainState frames

Rules A and I are AtmosphereStage's surface. **Ratified addition (not implemented, plan Phase 2)**: the path-segment product (a column evaluated between two arbitrary altitudes with the zenith at the lower endpoint) that yields A1 and A5, the sky-radiance-along-LOS product feeding B2, and the per-altitude shadow-height illumination test. Guardrail G1 governs the contract shape — segment composition, not further flat-field accretion in `AtmosphericQuantities`.

### Downstream stages
OpticsStage onward consume already-propagated spectral radiances. No further radiometry of source/atmosphere type; only spatial transfer (PSF path + MTF product path, Rule 4), EE_box (Rule 9), spectral integration (Rule 8), detector response, readout, performance. **Ratified addition (not implemented, plan Phase 3)**: metric relevance conditioned on scene class through one declarative map over the Gap 96 selection machinery — ground-projection metrics (GSD, ground range, swath/access, NIIRS) are meaningless for non-ground targets. Guardrail G3 forbids per-metric scene-class branches.

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

Kirchhoff: `ε(λ) = 1 − ρ(λ)` for target; `ε_g = 1 − ρ_g` for ground. For an airborne observer the up-leg upper limit is `h_sensor`, not `h_atm_top` (Rule A, A2/A3 rows) — the same equation with a different segment endpoint.

### 6.2 Special-case reductions

| Case | Reduces to |
|---|---|
| LWIR airborne, ρ≈0 | `ε·B·τ_up + L_path,up` (pure emitter) |
| VIS/NIR terrestrial, ε≈0 | `ρ·τ_sun·E_TOA·cos(θ_s)·τ_full,up/π + ρ·E_sky·τ_full,up/π + L_path,full` (pure reflector) |
| Exo-atmospheric (A0) | Atmosphere quantities → {τ=1, L_path=0, E_sky=0}; equation collapses to `ε·B + ρ·E_TOA·cos(θ_s)/π` |
| At-aperture | Pass-through: `L_t,aperture = user_L_t_aperture` |

Each reduction is a testable truth anchor for Category C validation.

### 6.3 Direction-general forms — ratified, not implemented

Shape only; the products on the right-hand side do not exist yet (plan Phase 2, Category C, where they arrive with truth anchors: MODTRAN up-looking runs, reciprocity checks, vacuum limits, horizontal-path analytic values).

For an **up-looking** observer leg (A1, sensor below target), the target term keeps its form with the segment endpoints swapped — transmittance is reciprocal, so `τ` over `h_sensor → h_tgt` is the same τ read the other way (computed with the zenith at the lower endpoint, `h_sensor`) — while the path-radiance term is **not** reciprocal and must be the *up-path* product (sensor → target leg viewed from below), which has no slot in today's `AtmosphericQuantities`. The background term is no longer a ground column but the sky radiance along the LOS beyond the target (B2), terminating in cold space.

For a **horizontal** arm (A5) the column is constant-density: `τ = exp(−α(h)·d)` in the simple model at the local absorption coefficient, MODTRAN `ITYPE=1`. The near-horizontal guard band of decision 18 applies.

---

## 7. Invalid Combinations (Schema-Level Errors)

The schema validator rejects combinations where the physics is ill-defined. Non-exhaustive. The **Status** column separates rules that are permanent from restrictions that ADR-0011 lifts on a schedule.

| Combination | Reason | Resolution | Status |
|---|---|---|---|
| `at_aperture` + `sub_pixel` or `point_source` | At-aperture is extended-only per decision 2 | Raise `ParameterBoundsError` | Permanent |
| `no_atmosphere (space)` + LOS intercepts Earth | No earthlimb model (B4 declined for v1.x) | Raise | Permanent for v1.x |
| `no_atmosphere (ground_test / lab_test)` without `UserSpectralBackground` | No sensible default for test-range / chamber radiance | Raise | Permanent |
| `target_location == "no_atmosphere"` without `no_atmosphere_subcase` | Ambiguous sub-case | Raise | Permanent |
| `terrestrial`/`airborne` without `GroundBackground` | No sensible default for (ε, T_g) | Raise | Permanent |
| Specifying both ε(λ) and ρ(λ) for target or ground | Over-specification (violates Kirchhoff derivation rule) | Raise | Permanent |
| MWIR scene with T1 or T2 alone (not T3) | MWIR requires the mixed model for ambient targets | Warn or raise on the ambient check; never forced when ρ ≈ 0 | Permanent |
| Point-source target with resolved angular size | `√A_t/d > 0.1 · PSF_FWHM` | Raise | Permanent |
| `T_g ∉ [150, 350] K` | Physically implausible Earth surface | Warn at the boundaries; raise far outside | Permanent |
| **`h_sensor ≤ h_target`** | `core/viewing_triangle.py::_validate_altitudes` — "v1 has no uplooking geometry" (owner ruling 2026-07-11) | Raise `ParameterBoundsError` | **Current restriction.** Superseded by [ADR-0011](../adr/0011-generalized-viewing-geometry.md); **lifted when plan Phase 1 lands**, replaced by symmetric solutions for any altitude ordering plus the equal-altitude case |
| **`θ_o ∉ [0, π/2)`** | Target beyond the sensor's horizon plane; enforced in `viewing_triangle._validate_theta_o`, `LineOfSightGeometry.__post_init__`, and `AtmosphericGeometry` (89.5° ceiling) | Raise | **Current restriction.** Superseded by ADR-0011 (domain extends to $[0,\pi)$); **lifted in plan Phase 1** |
| **LOS within ±0.5° of the geometric horizon** | No refraction model; the answer would be quietly wrong (Rule 17) | Raise | **Ratified, not implemented** — the guard arrives with the extended domain (decision 18, Phase 1) |
| **LOS in the ±0.5°–≈±2° near-horizontal shoulder** | Refraction excluded but the path is still usable (long-range air-to-air) | Compute + `UserWarning` quantifying the caveat | **Ratified, not implemented** — decision 18, Phase 1 |
| **Limb-crossing LOS termination** | No limb radiance model (B4 declined, GF-11) | Raise | **Ratified, not implemented** — the termination test arrives with B2 in Phase 2 |
| `θ_s ≥ π/2` (sun at or below the horizon) | Currently rejected outright: `geometry.solar_zenith_rad` is bounded at 1.5707 rad and `AtmosphericGeometry.__post_init__` raises. Night scenes use `geometry.solar_illumination = "night"` (S0), not a sub-horizon sun | Raise (schema bound / `AtmosphereValidationError`) | **Current restriction.** Superseded by decision 21 (per-altitude shadow-height test, Phase 2). *This row previously read "Warn (physical, not error)", which never matched the code; corrected here per Rule 20* |

---

## 8. Open Questions

Known-unresolved, expected to come up during implementation or subsequent design review. Items answered by the 2026-07-26 ratification are marked.

1. **Illumination descriptor**: does SourceStage publish a separate `IlluminationDescriptor` (solar spectrum source, solar geometry, user override for E_sky), or is illumination purely an AtmosphereStage concern with solar spectrum loaded from a file internally? Probably the latter, but worth confirming.

2. **Point-source schema dual form**: user may specify point-source target either as (ε, T, A_t) → internal I = εBA, or as raw I(λ). Both need to route through the same downstream path; schema should accept either with a discriminator.

3. **MODTRAN / atmosphere backend for partial columns**: partial columns (A3) require τ at arbitrary h_tgt. *Largely settled by delivery* — the backends integrate between endpoint altitudes (GF-6) — but the up-looking and horizontal **library families** (A1, A5) must be generated, not just wired: plan §8.3 answer 2 appends the first batch (ground-to-air up-looking partial-column ladder + constant-altitude horizontal set, with the CU-065 uplooking Card-3 ANGLE convention check) to `docs/plans/modtran_run_matrix.csv`; the SST full-column ladder is batch 2.

4. **Invalid-combination coverage**: §7 is non-exhaustive. Under the compositional model the comprehensive validation surface is Rule V plus the per-rule preconditions, not a cell-indexed table — the executable coverage lives in the integration sweeps named in §3.5.

5. **Cross-stage consistency at the Option C boundary**: integration test verifying AtmosphereStage's assembly matches the pre-Option-C implementation for the terrestrial LWIR-emitter case (regression anchor).

6. **Diffuse E_sky decomposition**: AtmosphereStage should produce E_sky,↓ with separable scattered-solar and atmospheric-thermal components, so we can audit which dominates per regime. Report both; consume the sum. (Rule I's MWIR row depends on this.)

7. **Evolution cleanliness**: schema fields named for v1 (like `ColdSpaceBackground` with no params) must not need renaming when zodiacal light / diffuse galactic contributions arrive. Current design allows additive fields; verify no assumptions are baked in that would force a breaking change.

8. **B2 / B4 boundary for near-horizontal paths** (new, 2026-07-26). — **ANSWERED (owner, 2026-07-26; plan §8.3 addendum)**: the discriminator is the same interior-tangent test that resolves question 10. Continue the LOS past the target: if the continuation has an **interior tangent point deeper than the guard's raise threshold** below its endpoints (without intercepting Earth), it is a limb crossing → B4, raise; shallower → B2 sky. One tangent-height computation serves both questions, so a level air-to-air path (shallow sag) classifies as B2 by construction. Implemented with Rule B in Phase 2.

9. **Retirement of the bundled A-codes** (new, 2026-07-26). A2/A3/A4 bundle the observer leg with the solar down-leg; A0/A1/A5 do not. Guardrail G1 pushes toward one segment abstraction, which would make the bundled codes a legacy naming layer over segment compositions. Whether the catalog collapses at Phase 2 close or the names survive as shorthand is open — the codes are kept unchanged here so no live cross-reference breaks.

10. **Does the ±0.5° hard guard apply to constant-altitude arms?** (new, 2026-07-26). — **ANSWERED (owner, 2026-07-26; plan §8.3 addendum)**: no — the guard keys on the ray's **tangent-point topology**, not on $|\theta_o - \pi/2|$ alone. (a) Paths whose minimum altitude is at an **endpoint** (ordinary up/down slants grazing the horizon) keep the ratified angular bands, measured at the lower endpoint: raise inside ±0.5°, compute-with-`UserWarning` out to ≈±2°. (b) Paths with an **interior tangent point** (level and near-level A5 arms, long air-to-air) guard on the tangent-height depression $\Delta h = (R_E + h_{low})\,(1 - \sin\theta_{low}) \approx L^2/8R_E$: below ~100 m compute clean (towers at 1.3 m, air-to-air to ~70 km); ~100 m to ~2 km compute + the refraction-caveat `UserWarning` quantified by $\Delta h$ (the ratified 200 km air-to-air case, Δh ≈ 0.8 km, lands here per §8.3 answer 1); above ~2 km raise (limb-like transit). Thresholds are provisional, calibrated in Phase 2 by a MODTRAN refraction on/off deck pair (batch 2). Keying on topology rather than exact altitude equality keeps behavior continuous in the real inputs (no equal-vs-almost-equal discontinuity). Refines ADR-0011 decision 6; implemented in `core/viewing_triangle.py` with the extended domain in Phase 1. Resolves question 8 with the same machinery.

---

## 9. Deferred Items

### 9.1 Ratified for delivery on 2026-07-26 (no longer deferred)

Moved out of the v2-deferral list by [ADR-0011](../adr/0011-generalized-viewing-geometry.md) and the Geometry Flexibility plan. **None of these is implemented yet** except where noted; each carries its plan phase.

| Item | Codes | Phase |
|---|---|---|
| Airborne sensor, down-looking (air-to-ground) | A2/A3 | **Supported today** — ratified, GF-6 (decision 15) |
| Ground-based sensor; up-looking observer legs | A1 | Phases 1–2 |
| Equal-altitude / horizontal paths | A5 | Phases 1–2 |
| Up-looking space-to-space (LEO → GEO) | A0 | Phase 1 (quick win — geometry gate only) |
| Sky-path background for upward-looking sensors | B2 (`SkyBackground`) | Phase 2, band-gated (decision 20) |
| Per-altitude (shadow-height) solar illumination | I0/I1/I2 selection | Phase 2 (decision 21) |
| Direction-aware turbulence ($C_n^2$ profile, path-weighted $r_0$) | — | Phase 3 (Gap 110) |
| Scene-class-conditioned metric relevance | — | Phase 3 (guardrail G3) |
| Target kinematics → LOS angular rate | — | Phase 3 (Gap 111) |

### 9.2 Still deferred

- Ellipsoidal Earth (WGS84) — locked decision 8
- Atmospheric refraction — modeled nowhere; guard-banded instead (decision 18)
- Earthlimb background model (B4) — **declined for v1.x** (GF-11); re-scoped only if a limb-viewing mission materializes
- Cloud background / material / atmospheric layer (B5) — Gap 82
- Diurnal / solar-heating thermal response for ground (T_g(t)) — locked decision 12
- Per-pixel background texture (non-uniform scenes) — locked decision 12
- BRDF reflective target model (T4)
- Plume / line emission target model (T6)
- Non-solar illumination (moonlight, lasers, active sources) (I3) — see the active-imaging plan
- Zodiacal / stellar / diffuse-galactic contributions to `ColdSpaceBackground`
- Two-point geodetic scene entry (Gap 83) and ephemeris / time-series geometry (Gap 84) — the Phase 1 representation is designed not to preclude them
