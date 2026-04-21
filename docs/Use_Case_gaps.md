# RADIANT Use-Case Coverage — Adversarial Gap Audit

**Date**: 2026-04-19 (audit) · updated 2026-04-20 after Option C landing
**Reviewer role**: adversarial (looking for what RADIANT *cannot* do, not what it can)
**Source of truth**: [RADIANT_Use_Case_Matrix.md](RADIANT_Use_Case_Matrix.md) v1, all 90 cataloged cells
**Method**: Cell-by-cell trace from descriptor schema (§4) and assembly equation (§6) through implemented code in `src/radiant/{source,atmosphere,core,optics,spectral_integration,api}/`; now also validated by the 90-cell parametric integration test [`tests/integration/test_use_case_matrix.py`](../tests/integration/test_use_case_matrix.py)
**Scope of this document**: structural/architectural gaps that prevent whole classes of cells from being expressible. Operational/numerical gaps already tracked in [gaps.md](gaps.md) (Gaps 1–30) are not duplicated here.

---

## Executive Summary

**Headline finding (2026-04-20, post-Option C)**: of the 90 cataloged cells in the use-case matrix, **80 now exercise the end-to-end chain successfully and 10 invalid-by-spec cells correctly raise** under the Option C architecture. The remaining gaps are no longer structural (descriptor schema, assembly equation, validators) but **numerical / physics-depth** — e.g. the E_sky decomposition (Open Q §8.6) and A3 partial-column atmosphere refinement. The 90-cell coverage harness lives at [`tests/integration/test_use_case_matrix.py`](../tests/integration/test_use_case_matrix.py) and writes its tally to [`tests/integration/_use_case_coverage.json`](../tests/integration/_use_case_coverage.json) on every run.

The previous (2026-04-19) audit captured the state **before** Option C landed, when the matrix was a forward-looking design contract and the codebase ran an older parameter-driven pipeline. That baseline is preserved below as the authoritative record of what changed. Historical statements of the form "🔴 NOT IMPLEMENTED" refer to the pre-Option-C codebase and are now superseded by the green-field implementation described in [`docs/Option_C_Implementation_Plan.md`](Option_C_Implementation_Plan.md) and [`docs/adr/0002-option-c-source-atmosphere-split.md`](adr/0002-option-c-source-atmosphere-split.md).

**Severity tally (current, post-Option C)**:

| Severity | Count | Examples |
|---|---|---|
| ✅ PASS (cell runs end-to-end) | 80 | All valid cells across Tables A/B/C/D-space/D-ground/D-lab — see `_use_case_coverage.json` |
| 🚫 CORRECT-RAISE (invalid-by-spec cell correctly rejected) | 10 | All at_aperture × {sub_pixel, point_source} combinations (Cells 2, 3, 5, 6, 8, 9, 11, 12, 14, 15) |
| ❌ FAIL (cell was expected to pass and doesn't) | 0 | — |
| 🟡 MINOR (cell passes but physics depth is incomplete) | ~6 | MWIR thermal+solar (Cells 25, 40, 55) — E_sky scattered-vs-thermal decomposition pending; C-table cells (31–45) use A3 column model that is not yet at MODTRAN parity |

**Severity tally (historical, 2026-04-19 pre-Option-C)**:

| Severity | Count | Examples |
|---|---|---|
| 🔴 BLOCKER (entire table inexpressible) | 5 | Tables A, C, D-ground, D-lab; airborne row of B |
| 🟠 MAJOR (cell expressible only by manual workaround) | ~35 | All sub-pixel and point-source cells in B; all of D except cold-bg LWIR |
| 🟡 MINOR (works but missing validation or physics term) | ~10 | Terrestrial LWIR extended (Cells 28); some at-aperture extended cells |

---

## 1. Axis-Level Coverage

### 1.1 `scene_type` axis

| Value | Status | Evidence |
|---|---|---|
| `extended` | 🟡 Implicit default | Triggered when `source.target.fill_fraction == 1.0` (default). No explicit enum, no descriptor field. [source/_schema.py:91-104](../src/radiant/source/_schema.py#L91-L104) |
| `sub_pixel` | 🟡 Implicit | Triggered when `0 < fill_fraction < 1`. Regime detection happens in OpticsStage [optics/stage.py:420-458](../src/radiant/optics/stage.py#L420-L458) but no first-class `scene_type` parameter exists. |
| `point_source` | 🟡 Implicit | Triggered when geometry implies √A_t/d ≪ pixel IFOV. Same indirection. |
| Schema enforcement of "at_aperture ⇒ extended only" (§7) | 🔴 MISSING | No cross-field validator. User can silently configure an invalid combination. |
| Sub-pixel-collapses-to-point-source warning (§1.1) | 🔴 MISSING | The "√A_t/d ≪ PSF_FWHM" UserWarning specified in §1.1 is not emitted. |

### 1.2 `wavelength_regime` axis

The matrix treats VIS/NIR/SWIR/MWIR/LWIR as bands that select dominant target physics. RADIANT does not enforce this:

- 🔴 No validator that **MWIR scenes require T3** (mixed emit+reflect). A user configuring an MWIR scene with `ThermalSource` only (T1) will silently get wrong radiance — solar reflection ignored. Matrix §3.2 lines 191–193 and §7 line 484 require this rejection.
- 🔴 No "SWIR hot-target ⇒ T3" validator (matrix §3.2 line 318, hot-target threshold ~700 K).
- 🔴 No "MWIR point-source pure thermal acceptable when ρ≈0" exemption (matrix §3.2 line 319).

### 1.3 `target_location` axis

| Value | Status | Evidence |
|---|---|---|
| `at_aperture` | 🔴 NOT EXPRESSIBLE AS DESIGNED | No `target_location` parameter, no `T5` user-radiance descriptor wired into a pass-through atmosphere path. The `TabulatedRadianceSource` ([source/tabulated.py](../src/radiant/source/tabulated.py)) loads a spectrum but it still flows through `AtmosphereStage.run()` which applies `τ·L + L_path` ([atmosphere/stage.py:80](../src/radiant/atmosphere/stage.py#L80)) — there is no pass-through guard. To get a true at-aperture answer the user must manually pair the tabulated source with `ExoAtmosphere` (τ≡1, L_path≡0). The "warn if atm parameters supplied" requirement of Decision #6 is not implemented. |
| `terrestrial` | 🟡 PARTIAL | `SimpleAtmosphere` [atmosphere/simple.py:399-515](../src/radiant/atmosphere/simple.py#L399-L515) and the MODTRAN backend can produce a column τ + single-scatter L_path. But the assembly equation (§6.1) is only partially wired — see §3 below. |
| `airborne` | 🔴 NOT IMPLEMENTED | The matrix's A3 path (partial column at arbitrary h_tgt) is not modeled. `AtmosphericGeometry` [atmosphere/protocol.py:54-100](../src/radiant/atmosphere/protocol.py#L54-L100) carries `target_altitude_m` but `SimpleAtmosphere._column_length_km()` and the MODTRAN card builder both effectively assume the target is at the surface; there is no τ_sun(h_tgt, θ_s)/τ_up(h_tgt, θ_o) split. Open Question §8.3 in the matrix flags this; it is unresolved. **Blocks all 15 cells in Table C.** |
| `no_atmosphere` | 🟡 PARTIAL | `ExoAtmosphere` [atmosphere/exo.py](../src/radiant/atmosphere/exo.py) provides A0. But: (a) no `no_atmosphere_subcase` parameter; (b) no Earth-LOS-intercept check for `space` sub-case; (c) no "must supply UserSpectralBackground" enforcement for ground_test/lab_test sub-cases. |

---

## 2. Descriptor Schema (§4) Coverage

### 2.1 TargetDescriptor — 🔴 NOT IMPLEMENTED

§4.1 specifies a discriminated descriptor with `scene_type`, `target_location`, `no_atmosphere_subcase`, `h_tgt`. **No such class exists.** SourceStage publishes raw spectral radiance into a `RadiometricFrame` named "at_target" ([source/stage.py:90-167](../src/radiant/source/stage.py#L90-L167)) and a few unstructured stage_outputs (`regime_tentative`, `projected_area_m2`, `range_m`, `fill_fraction`, `L_background`, `angular_extent_rad`). These do not constitute a descriptor and they violate the Option C contract that SourceStage shall publish *no radiance*.

**Consequences**:
- Downstream stages (atmosphere, optics, performance) cannot dispatch on `target_location`, so cell-specific assembly cannot be selected.
- `no_atmosphere_subcase` is not representable; ground_test and lab_test cannot be distinguished from space.

### 2.2 BackgroundDescriptor — 🔴 NOT IMPLEMENTED

§4.2 specifies four discriminated variants. None exist as named classes:

| Variant | Required for cells | Status |
|---|---|---|
| `AtApertureBackground(L_bg_aperture)` | Table A (15 cells) | ❌ MISSING — no class. `ConstantBackground` could approximate but no schema tag and no validator that `target_location == at_aperture`. |
| `ColdSpaceBackground` (L=0) | Table D space sub-case (15 cells) | ❌ MISSING — no class, no Earth-LOS-intercept check. |
| `GroundBackground(epsilon, T_g)` | Tables B, C (30 cells) | 🟡 PARTIAL — `BlackbodyBackground` [source/backgrounds/blackbody.py:22-73](../src/radiant/source/backgrounds/blackbody.py#L22-L73) carries (ε, T) but is not named GroundBackground, not validated as required for terrestrial/airborne, and is not transported to AtmosphereStage for the L_bg,aperture branch of the assembly equation. |
| `UserSpectralBackground(L_bg)` | Tables D-ground, D-lab (30 cells) | 🟡 PARTIAL — `TabulatedBackground` [source/backgrounds/tabulated.py](../src/radiant/source/backgrounds/tabulated.py) accepts a spectrum but is not validated as required for the no_atmosphere ground_test/lab_test sub-cases, and the no_atmosphere sub-case enum doesn't exist anyway. |

### 2.3 LineOfSightGeometry — 🔴 NOT IMPLEMENTED

§4.3 specifies `src/radiant/core/los_geometry.py` (per Rule 19, Decision #10) with fields `{h_tgt, h_atm_top, θ_o, θ_s, Δφ}` and the `theta_o_from_eta` input-boundary converter.

**Status**: file does not exist. `core/geometry.py` contains `ObserverGeometry`, `TargetGeometry`, `SceneGeometry` instead — different field names, different structure, not a LOS abstraction. The atmosphere stage uses a parallel `AtmosphericGeometry` with `solar_azimuth_rad` (an absolute compass azimuth) rather than `Δφ` (relative azimuth ∈ [−π, π]) — these are not interchangeable for the assembly equation.

**Direct blocker**: the assembly equation (§6.1) is parameterized on (h_tgt, h_atm_top, θ_o, θ_s, Δφ); without that descriptor the matrix's path-codes A2/A3/A4 cannot be cleanly invoked.

### 2.4 SensorDescriptor — DEFERRED, but referenced

§4.4 explicitly defers full scoping but flags `h_sensor` as needed for OpticsStage / platform. OpticsStage does not currently consume sensor altitude (uses focal length + aperture only), so the deferral does not bite *yet* — but it will when airborne/ground sensor (v2) lands or when Rule 2 boundary conversion `θ_o_from_eta` is needed.

---

## 3. Assembly Equation (§6) Coverage

The matrix's centerpiece is the assembly equation at §6.1:

```
L_t,aperture(λ) = [ε·B(T_t) + ρ·τ_sun·E_TOA·cos(θ_s)/π + ρ·E_sky,↓/π] · τ_up + L_path,up
L_bg,aperture(λ) = [ε_g·B(T_g) + ρ_g·E_g/π] · τ_full,up + L_path,full
```

Current implementation in [atmosphere/stage.py:69-94](../src/radiant/atmosphere/stage.py#L69-L94) is exactly:

```
L_at_aperture = L_target · τ + L_path
```

That is the trivial case (extended thermal LWIR, target = surface). Specifically missing:

| Term | Status | Cells affected |
|---|---|---|
| Separate `τ_sun(λ, h_tgt, θ_s)` and `τ_up(λ, h_tgt, θ_o)` | ❌ Single τ lumps both | All reflective + airborne cells (~50) |
| `τ_full,up(λ, 0, θ_o)` (background up-leg, distinct from target's τ_up) | ❌ Not computed | All sub-pixel + point-source cells with ground bg in airborne (Table C) |
| `E_TOA(λ)` solar spectrum applied with `cos(θ_s)` | 🟡 Computed inside ReflectedSolarSource [source/reflected.py:28-111](../src/radiant/source/reflected.py#L28-L111) but **diffuse E_sky is ignored** | All VIS/NIR reflective cells (Tables B, C, D, G, L) |
| `E_sky,↓` decomposed into scattered-solar vs. atm-thermal (Open Q §8.6) | ❌ Approximated as a single graybody (1−τ)·B(T_eff) [atmosphere/simple.py:357-372](../src/radiant/atmosphere/simple.py#L357-L372); decomposition absent | Required for MWIR audit (Cells 25–26, 40–41) |
| Background radiance branch (`L_bg,aperture`) | ❌ Not computed at all | All sub-pixel and point-source cells with non-zero bg (~40 cells) |
| A4 emission-only mode (drop solar terms for LWIR) | ❌ No regime gate | Cells 6, 7, 28–30, 43–45 — currently rely on the user not setting a sun |
| Pass-through guard for at_aperture with warn-if-atm-supplied (Decision #6) | ❌ Missing | All Table A cells |

---

## 4. Per-Table Cell Coverage

### Table A — `at_aperture` (15 cells, 5 valid)

| Cells | Status | Why |
|---|---|---|
| 1, 4, 7, 10, 13 (extended, all regimes) | 🟡 EXPRESSIBLE BY WORKAROUND | User must manually combine `TabulatedRadianceSource` + `ExoAtmosphere`. No descriptor, no pass-through validator, no warning on accidentally-supplied atm parameters. |
| 2, 3, 5, 6, 8, 9, 11, 12, 14, 15 (sub_pixel, point_source) | ✅ INVALID by spec | Matrix correctly forbids; RADIANT does not enforce the prohibition either. |

### Table B — `terrestrial` (15 cells)

| Sub-band | Status |
|---|---|
| Cells 16, 19, 22 (VIS/NIR/SWIR extended, reflective) | 🟠 PARTIAL — ReflectedSolarSource computes `ρ·E_sun·cos(θ_s)` but ignores diffuse `E_sky`; AtmosphereStage applies a single τ instead of separate τ_sun and τ_up. Result is dimensionally correct but radiometrically off (no skylight, no two-leg attenuation). |
| Cell 25 (MWIR extended, mixed) | 🟠 PARTIAL — `CombinedSource` [source/combined.py](../src/radiant/source/combined.py) implements ε·B + ρ·E/π with Kirchhoff; but no separation of E_sky_thermal vs E_sky_scattered (Open Q §8.6) so the MWIR-dominant downwelling thermal term is missing. |
| Cell 28 (LWIR extended, thermal) | 🟢 WORKS — this is the closest cell to a fully-supported case. |
| Cells 17, 18, 20, 21, 23, 24, 26, 27, 29, 30 (sub_pixel, point_source — 10 cells) | 🔴 BACKGROUND BRANCH MISSING — sub-pixel mixing (`L_pixel = ff·L_t·EE_box + (1−ff)·L_bg + L_path`) is correctly applied in SpectralIntegrationStage [spectral_integration/stage.py:168](../src/radiant/spectral_integration/stage.py#L168) per Rule 9, but `L_bg` itself is computed in SourceStage as a simple at-target blackbody; AtmosphereStage never propagates it through `τ_full,up`/`L_path,full`. Background radiance at the aperture is therefore wrong by the full atmospheric contribution. |

### Table C — `airborne` (15 cells)

🔴 **ENTIRE TABLE INEXPRESSIBLE.** The A3 partial-column atmosphere is not implemented. None of the simple, MODTRAN, or tabulated backends can produce τ at an arbitrary `h_tgt` between surface and TOA. Open Question §8.3 flags this; nothing has been done. Workaround: user could lie about h_tgt to the simple model, but the resulting τ would be wrong (wrong column length, wrong layer composition).

### Table D — `no_atmosphere` (space sub-case, 15 cells)

| Sub-band | Status |
|---|---|
| Cells 46, 49, 52, 55 (extended, with reflective/mixed) | 🟠 PARTIAL — ExoAtmosphere works; but TOA solar term must be configured manually per source; no validator that the user picked the right T-code for the regime; no "L_bg = 0" automatic injection. |
| Cell 58 (LWIR extended, thermal) | 🟢 WORKS — vacuum + ε·B is the simplest cell in the matrix and the codebase handles it. |
| Cells 47–48, 50–51, 53–54, 56–57, 59–60 (sub-pixel, point-source — 10 cells) | 🔴 NO ColdSpaceBackground — bg defaults to whatever the user supplies (typically a 290 K blackbody from the default `BACKGROUND_TEMPERATURE` parameter [source/_schema.py:106-115](../src/radiant/source/_schema.py#L106-L115)). The matrix requires L_bg = 0 for cold space; current default is wrong by ~10⁵ for LWIR sub-pixel SNR. The user can override but **the default silently produces a non-physical result.** |
| Earth-LOS-intercept check (matrix §3.3) | 🔴 MISSING — no validation; user can configure a "space" target with sensor below it and get nonsense. |

### Table D-ground — `no_atmosphere (ground_test)` (15 cells)

🔴 **ENTIRE TABLE INEXPRESSIBLE AS DESIGNED.** No `no_atmosphere_subcase` parameter, no required `UserSpectralBackground` validator, no preset distinguishing this from the space sub-case. Workaround: user manually combines `ExoAtmosphere` + `TabulatedBackground` + appropriate source. Possible but undocumented and unvalidated.

### Table D-lab — `no_atmosphere (lab_test)` (15 cells)

🔴 **ENTIRE TABLE INEXPRESSIBLE AS DESIGNED.** Same gap as D-ground. The "dark cal" sub-mode (illumination = None) is not directly supported because illumination is not currently a separable input — it lives inside the source classes. To run dark cal the user must use a `ThermalSource` only and avoid `ReflectedSolarSource`/`CombinedSource`; not enforced.

---

## 5. Validation Gaps (Matrix §7)

§7 lists ~10 invalid combinations the validator must reject. Implementation status:

| §7 rule | Status | Failure mode without it |
|---|---|---|
| `at_aperture` + (sub_pixel \| point_source) → raise | ❌ MISSING | Silent over-specification |
| `no_atmosphere (space)` + LOS intercepts Earth → raise | ❌ MISSING | Silent non-physical result |
| `no_atmosphere (ground_test \| lab_test)` without UserSpectralBackground → raise | ❌ MISSING (subcase doesn't exist) | Can't be triggered |
| `target_location == no_atmosphere` without `no_atmosphere_subcase` → raise | ❌ MISSING (subcase doesn't exist) | N/A |
| `terrestrial`/`airborne` without GroundBackground → raise | ❌ MISSING | Silent fallback to default 290 K bg |
| Both ε(λ) and ρ(λ) for target → raise | 🟡 ENFORCED LOCALLY in CombinedSource via Kirchhoff [source/combined.py:73-101](../src/radiant/source/combined.py#L73-L101); not enforced at descriptor schema level | Some user paths bypass |
| MWIR with T1 or T2 alone → warn or raise | ❌ MISSING | Solar reflection silently dropped in MWIR |
| Point-source with √A_t/d > 0.1·PSF_FWHM → raise | ❌ MISSING | Sub-pixel mis-classified as point silently |
| `T_g ∉ [150, 350] K` → warn / raise | 🟡 PARTIAL — bounds check at [0, 5000] in schema [source/_schema.py:106-116](../src/radiant/source/_schema.py#L106-L116); no narrower physical-plausibility band | Allows 50 K Earth surface |
| `θ_o > π/2` → raise | 🟡 ENFORCED in `AtmosphericGeometry.__post_init__` ([atmosphere/protocol.py:113](../src/radiant/atmosphere/protocol.py#L113)) | OK |
| `θ_s > π/2` for reflective T2 → warn | ❌ MISSING | Negative cos(θ_s) clamped silently |

---

## 6. Architectural Misalignment with Option C (Decision §4)

The matrix's Decision #4 says: **SourceStage publishes descriptors only; AtmosphereStage owns radiance assembly.** This is the most consequential architectural decision in the matrix and the codebase implements the *opposite*:

| Stage | Matrix says | Codebase does |
|---|---|---|
| SourceStage | Publishes TargetDescriptor + BackgroundDescriptor + LineOfSightGeometry; no radiance | Publishes a `RadiometricFrame` of L_target ([source/stage.py:109-115](../src/radiant/source/stage.py#L109-L115)) and a few stage_outputs |
| AtmosphereStage | Consumes descriptors, runs assembly equation (§6.1), emits L_t,aperture and L_bg,aperture | Consumes pre-computed L_target, applies `L_target·τ + L_path`, emits one combined L_at_aperture ([atmosphere/stage.py:69-94](../src/radiant/atmosphere/stage.py#L69-L94)) |

This is not just a refactor — it directly blocks correct assembly for Tables B/C/D in any non-trivial cell because:
- The two-leg attenuation (τ_sun then τ_up) cannot be applied if the source has already fully assembled L_target on the ground.
- The background term `L_bg,aperture` cannot exist as a separate field if AtmosphereStage doesn't know it's a separate object.
- A3 partial-column physics requires h_tgt-aware τ computations, which presuppose AtmosphereStage owning the geometry.

This is the single biggest gap; everything in §1–§5 is downstream of it.

---

## 7. Severity Ranking

### 🔴 Blockers (must fix to claim matrix coverage)

1. **Adopt Option C architecture**: refactor SourceStage to descriptor-only and move assembly into AtmosphereStage. Without this, Tables B (sub-pixel/point cells), C, and D-ground/D-lab are inexpressible.
2. **Create LineOfSightGeometry** in `src/radiant/core/los_geometry.py` with the §4.3 spec (h_tgt, h_atm_top, θ_o, θ_s, Δφ) and the `theta_o_from_eta` boundary converter.
3. **Implement TargetDescriptor + BackgroundDescriptor** as discriminated frozen dataclasses with the four background variants and the scene_type/target_location/no_atmosphere_subcase enums.
4. **Implement A3 (partial column) atmosphere**: at minimum a SimpleAtmosphere extension that exposes τ at arbitrary h_tgt, with separate τ_sun and τ_up. Without this, Table C (15 cells) is dead.
5. **Implement L_bg,aperture branch** in AtmosphereStage so the background term in sub-pixel and point-source cells survives atmospheric propagation (currently the bg is treated as already at the aperture, which is wrong for any terrestrial/airborne sub-pixel cell).

### 🟠 Major (entire categories are dependent on validation)

6. **Add §7 schema validators** as cross-field checks at descriptor construction — at minimum the at_aperture/scene_type interlock, the no_atmosphere/sub_case interlock, and the MWIR-requires-T3 check.
7. **Implement E_sky decomposition** (Open Q §8.6) so the MWIR thermal-downwelling-vs-scattered-solar audit is possible. Required for Cells 25–26, 40–41 to be physically right.
8. **Implement no_atmosphere sub-case presets**: enum + default-background dispatch + Earth-LOS-intercept check for `space`.
9. **Implement at_aperture pass-through guard** (Decision #6) with warn-if-atm-parameter-supplied.

### 🟡 Minor (correctness gaps in cells that "work")

10. Add the sub-pixel-collapses-to-point-source UserWarning (§1.1).
11. Tighten T_g bounds to physical range [150, 350] K with warning (§7).
12. Warn on θ_s > π/2 with reflective-only target (§7).
13. Add `point_source` + resolved-angular-size raise (§7).

---

## 8. Recommendation Matrix — minimum work to claim each table

| Table | Cells | Minimum work to claim "supported" |
|---|---|---|
| A (at_aperture) | 5 valid | Pass-through guard (Decision #6); `target_location` parameter; `AtApertureBackground` variant. **Smallest delta — likely a 1-day task.** |
| B (terrestrial) extended-only (3 cells) | 16, 19, 22 | Two-leg τ_sun/τ_up split in SimpleAtmosphere; E_sky term wired into reflective sources. |
| B (terrestrial) MWIR extended (Cell 25) | 1 | E_sky decomposition (Open Q §8.6). |
| B (terrestrial) LWIR extended (Cell 28) | 1 | **Already works.** Add validator that LWIR uses T1 or A4 path. |
| B (terrestrial) sub-pixel + point (10 cells) | | Option C refactor + L_bg,aperture branch + GroundBackground descriptor. |
| C (airborne) all 15 | | A3 partial-column atmosphere; partial column in SimpleAtmosphere/MODTRAN; Option C refactor. **Largest single chunk of work.** |
| D (space sub-case) extended LWIR (Cell 58) | 1 | **Already works.** |
| D space sub-case other 14 | | ColdSpaceBackground + Earth-LOS check + sub_case enum. |
| D-ground (15 cells) | | sub_case enum + UserSpectralBackground requirement; otherwise A0 already works. |
| D-lab (15 cells) | | Same as D-ground + dark-cal mode (illumination=None). |

---

## 9. What This Audit Did Not Cover

- **Numerical accuracy** of the cells that *do* work (Cells 28, 58, the at-aperture extended cells via workaround). These are tracked by the existing golden tests; this audit looked at expressibility, not correctness of expressed cells.
- **Performance** of MODTRAN integration for partial-column scenarios.
- **GUI / CLI surfacing** of any of the missing axes — the matrix gaps would propagate to user-facing config but that is downstream.
- **The 30 operational gaps already in [gaps.md](gaps.md)** — those are runtime / metric / output-format issues, orthogonal to the use-case axes here.

---

## 10. Bottom Line

**2026-04-20 update**: The three-step ordering below has been **completed**. Option C has landed, the descriptor schema is in place with §7 validators, and the A3 partial-column path is wired. The 90-cell parametric test [`tests/integration/test_use_case_matrix.py`](../tests/integration/test_use_case_matrix.py) now runs every cell in the matrix and records the outcome in [`tests/integration/_use_case_coverage.json`](../tests/integration/_use_case_coverage.json): **80 pass, 10 raise-by-spec, 0 fail**. The matrix has transitioned from *target architecture* to *description of what RADIANT does*.

**Remaining work is numerical depth, not architectural**: (a) E_sky scattered-vs-thermal decomposition (Open Q §8.6) affects MWIR-extended cells 25, 40, 55 accuracy but not expressibility; (b) A3 partial-column physics is expressible end-to-end but requires MODTRAN-parity validation for Table C cells 31–45; (c) warning-level validators (§7 rules 5, 9–11) are now emitted from descriptor construction and are covered by unit tests in `src/radiant/core/tests/test_descriptors.py` and `src/radiant/optics/tests/test_psf_regime_validation.py`.

**Original (2026-04-19) three-step plan — all three now complete**:

1. ✅ Land Option C (SourceStage descriptor refactor + assembly moved into AtmosphereStage).
2. ✅ Land the descriptor schema (TargetDescriptor / BackgroundDescriptor / LineOfSightGeometry) with the §7 validators.
3. ✅ Land the A3 partial-column atmosphere backend.

After (1)+(2), Tables A, B-extended, D-space, D-ground, and D-lab are reachable and verified. After (3), Table C is reachable and verified. The LWIR thermal extended cells remain the best-anchored reference cells (Cell 28 terrestrial and Cell 58 space — both have golden-value integration tests at rtol=1e-6).
