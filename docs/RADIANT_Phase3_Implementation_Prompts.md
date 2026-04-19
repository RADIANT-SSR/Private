# RADIANT — Phase 3 Implementation Prompt Sequence

## Purpose

This document defines the implementation prompts for Phase 3: gap fixes
and enhancements identified during scenario exercises (scenarios 1.x–7.x).
It follows the structure and validation framework established in
`RADIANT_Phase2_Implementation_Prompts_Validated.md`.

**Gaps addressed:** 33, 34, 35, 36, 24, 29, 14, 11, 25, 16, plus the
mixed-train optical element model from `radiometric_model_mixed_train.md`
and smear-to-MTF chain integration.

**Guiding principle:** Every change must preserve backward compatibility
with existing golden tests.  Default parameter values (0.0 for angles,
scalar mode for optics, zero smear/defocus) must reproduce identical
results to the current codebase.  Any golden-value change requires the
review protocol from `RADIANT_Testing_Validation.md §5.3`.

---

## BEFORE YOU START

### Prerequisites

- Phase 2 is complete: all 1759+ tests pass, `mypy --strict` clean on
  `core/` and `api/`, `ruff check` clean.
- `docs/gaps.md` is up to date (36 gaps logged, 12 FIXED).
- Scenario scripts 1.x–7.x exist and run.
- `docs/radiometric_model_mixed_train.md` has been reviewed and approved.

### Dependency Map

```
Phase 3A (geometry):
  3A.1  Gaps 33+34+35  ←  standalone (no prereqs)
  3A.2  Gap 36         ←  depends on 3A.1 (uses off-nadir GSD/slant range)

Phase 3B (optics model):
  3B.1  Mixed-train element types + Mode 5 wiring  ←  standalone
  3B.2  Thermal path + Gap 11      ←  depends on 3B.1
  3B.3  Gap 29 (defocus)           ←  standalone

Phase 3C (spatial/PSF):
  3C.1  Smear → MTF chain          ←  depends on 3A.1 (uses slant range)
  3C.2  Gap 24 + Gap 16 (Zernike + per-λ PSF)  ←  standalone
  3C.3  Gap 25 (field-dependent WFE + chromatic Zernikes)  ←  depends on 3C.2
  3C.4  Gap 14 (aliased/folded MTF)             ←  standalone
```

### Cross-Cutting Concerns (from adversarial review)

1. **Authoritative GSD function:** `core/geometry.py:SceneGeometry.gsd_m()`
   already computes slant-range GSD. Prompt 3A.1 enhances this existing
   function rather than creating a parallel implementation in `performance/gsd.py`.
   `performance/gsd.py` delegates to `SceneGeometry.gsd_m()` for the physics
   and adds the along-track foreshortening + geometric mean.
2. **Transmission Mode 5 dead code:** `OpticsStage` never passes
   `full_elements` to `resolve_transmission()`. Prompt 3B.1 wires this.
3. **YAML config for element lists:** `ParameterSet` only supports scalar
   types. Mixed-train element specs use a YAML config format with custom
   deserialization in `io/`, bypassing `ParameterSet` for structured data.
4. **Smear uses slant range:** After 3A.1, smear computation in 3C.1 uses
   slant range (not altitude) for off-nadir consistency.
5. **Batch scenario regression:** Every checkpoint runs the full scenario
   suite as a regression gate.

### Impact Summary

| Prompt | Files Modified | Files Created | Golden Impact |
|--------|---------------|--------------|---------------|
| 3A.1 | `performance/gsd.py`, `performance/stage.py`, `core/geometry.py` | — | None (default zenith=0) |
| 3A.2 | `performance/stage.py` | `performance/access_geometry.py` | None (new metrics only) |
| 3B.1 | `optics/element.py`, `optics/element_list.py`, `optics/_schema.py`, `optics/stage.py` | `io/element_config.py` | None (existing elements unchanged) |
| 3B.2 | `optics/element_list.py`, `optics/stage.py` | — | None (new outputs only) |
| 3B.3 | `optics/_schema.py`, `optics/stage.py` | — | None (default defocus=0) |
| 3C.1 | `platform/_schema.py`, `platform/stage.py` | — | None (default smear=0) |
| 3C.2 | `optics/diffraction.py`, `optics/stage.py`, `optics/wavefront.py` | `optics/zernike.py` | None (default mode=scalar_rms) |
| 3C.3 | `optics/wavefront.py`, `optics/stage.py` | — | None (default mode=scalar_rms) |
| 3C.4 | `performance/stage.py` | `performance/folded_mtf.py` | None (new metric only) |

**Every prompt defaults to zero-impact on golden tests.** This is by
design: new parameters default to values that reproduce current behavior.

---

## PHASE 3A — OFF-NADIR GEOMETRY & ACCESS (2 prompts)

### Prompt 3A.1 — Off-nadir GSD with along/cross-track correction (Gaps 33 + 34 + 35)

```
Task: Correct GSD computation for off-nadir viewing geometry.
Category: C (physics implementation)

Read first:
- docs/RADIANT_Conventions.md (coordinate system, canonical units)
- docs/gaps.md (Gaps 33, 34, 35)
- scenarios/03_raj_mission_planner/3.4_off_nadir_agility/walkthrough.md
  (reference tables with hand-computed off-nadir GSD values)
- src/radiant/core/geometry.py (SceneGeometry.gsd_m() — existing
  slant-range GSD, the AUTHORITATIVE function to enhance)
- src/radiant/performance/gsd.py (current nadir-only implementation)
- src/radiant/performance/stage.py (_compute_gsd_metrics — how GSD is
  wired into the chain)
- src/radiant/atmosphere/protocol.py (AtmosphericGeometry — has
  slant_path_length_m() and air_mass() with spherical Earth correction;
  INDEPENDENT implementation for atmospheric path, not GSD)

Context:
Currently compute_gsd() uses the nadir formula: GSD = p × H / f. At
45 deg off-nadir from 600 km, this gives 1.37 m instead of the correct
1.86 m cross-track / 2.94 m along-track — a 26% error. The atmosphere
module already handles path_zenith_rad for atmospheric transmission, but
the performance stage ignores it for GSD.

IMPORTANT — existing slant-range GSD in core/geometry.py:
SceneGeometry.gsd_m() already computes pixel_pitch × slant_range / f,
using slant_range = altitude / cos(look_angle) (flat-Earth). This
is the authoritative slant-range formula. This prompt ENHANCES that
function with spherical Earth correction and adds the along-track
foreshortening factor. Do NOT create a parallel implementation.

Three distinct physics effects must be modeled:
1. Slant range increases with zenith angle → cross-track GSD grows
2. Ground projection foreshortening → along-track GSD grows faster
3. Earth curvature correction at large zenith angles (>80 deg)

Design decisions:
1. ENHANCE core/geometry.py SceneGeometry.gsd_m() with spherical Earth
   slant range (switchover at altitude > 30 km or zenith > 60 deg).
   This is the single authoritative GSD function. At zenith=0, it
   returns the current nadir formula — backward compatible.
2. performance/gsd.py compute_gsd() delegates to SceneGeometry for the
   cross-track GSD and adds along-track foreshortening + geometric mean.
   It does NOT reimplement slant-range geometry.
3. Slant range with spherical Earth: use the law of cosines on the
   Earth-center triangle. R_E = 6,371,000 m.
   slant = sqrt((R_E+h)² + R_E² - 2·R_E·(R_E+h)·cos(central_angle))
   where central_angle is derived from the sensor zenith angle.
4. Along-track GSD: incidence angle at the ground DIFFERS from the
   sensor zenith angle due to Earth curvature. The relationship is:
     sin(incidence) = (R_E + h) / R_E × sin(zenith)
   At 45 deg zenith from 600 km:
     incidence = arcsin((6971/6371) × sin(45°)) = ~50.7 deg (not 45 deg)
   This ~5.7 deg difference matters: along-track GSD at 45 deg is
   2.94 m (using incidence) vs 2.63 m (using zenith) — 12% error.
   Along-track GSD = p × slant_range / (f × cos(incidence_angle))
5. GSD result gains a geometric_mean_m field: sqrt(cross × along).
   NIIRS uses this geometric mean per GIQE-5.
6. _compute_gsd_metrics() reads geometry.path_zenith_rad from params
   (defaulting to 0.0 if not set).

IMPORTANT: The SceneGeometry enhancement lives in core/geometry.py
which is importable by all stages. The atmosphere module has its own
slant-path computation in protocol.py — these are INDEPENDENT
implementations serving different purposes (GSD vs atmospheric path).
Document this in comments.

Produce:
1. Updated src/radiant/core/geometry.py:
   - SceneGeometry.gsd_m() enhanced with spherical Earth slant range
   - New helper: _slant_range_spherical_m(altitude_m, zenith_rad)
     Uses law of cosines with R_E = 6,371,000 m
   - New helper: _incidence_angle_rad(altitude_m, zenith_rad)
     sin(incidence) = (R_E + h) / R_E × sin(zenith)
   - Flat-Earth fallback for altitude < 30 km AND zenith < 60 deg
   - At zenith=0, returns altitude (unchanged behavior)
2. Updated src/radiant/performance/gsd.py:
   - compute_gsd() gains path_zenith_rad: float = 0.0 parameter
   - Cross-track GSD: delegates to SceneGeometry.gsd_m() or
     uses _slant_range_spherical_m × pixel_pitch / focal_length
   - Along-track GSD: p_y × slant_range / (f × cos(incidence_angle))
     where incidence_angle = _incidence_angle_rad(altitude, zenith)
   - GSDResult gains geometric_mean_m property: sqrt(cross × along)
3. Updated src/radiant/performance/stage.py:
   - _compute_gsd_metrics() reads geometry.path_zenith_rad (with
     fallback to 0.0 if not set)
   - Passes zenith angle to compute_gsd()
   - Stores gsd_geometric_mean_m in metrics
4. src/radiant/performance/tests/test_gsd.py — updated/extended:
   - Existing nadir tests still pass (zenith=0 default)
   - Off-nadir tests at 15, 30, 45, 60 deg from 600 km
     verified against scenario 3.4 walkthrough tables
   - Along-track > cross-track at off-nadir (asymmetry test)
   - Geometric mean = sqrt(cross × along) identity
   - Spherical Earth correction test at >80 deg
   - Incidence angle test: at 45 deg zenith from 600 km,
     incidence ≈ 50.7 deg (NOT 45 deg) — verify the difference
   - Edge case: zenith=0 returns exactly the nadir formula
5. src/radiant/performance/tests/test_stage.py — extended:
   - Integration test: path_zenith_rad=0 gives identical GSD
     to current behavior
   - Integration test: path_zenith_rad > 0 gives larger GSD
   - Integration test: NIIRS changes when path_zenith_rad changes
     (verify the full chain: zenith → GSD → NIIRS cascade)

Gap 34 resolution: NIIRS (_compute_niirs_metric) already reads
gsd_along_track_m and gsd_cross_track_m from state.metrics. Once
compute_gsd returns corrected values, NIIRS is automatically correct.
No additional code changes needed for Gap 34.

Validation requirements (C):

Numerical truth anchors:
1. Scenario 3.4 walkthrough table (10 angles, 0-45 deg):
   Cross-track GSD, along-track GSD, and geometric mean at each angle.
   Source: hand-computed with spherical Earth geometry in walkthrough.md
   Tolerance: < 0.5% at all angles
2. Flat-Earth limit: at small angles (< 10 deg), the flat-Earth formula
   H/cos(θ) should match spherical to < 0.1%
3. Nadir identity: at zenith=0, cross = along = p × H / f exactly
   (bitwise identical to current code)
4. Incidence angle at 45 deg zenith from 600 km:
   sin(inc) = (6971/6371) × sin(45°) → inc ≈ 50.7 deg
   Source: spherical geometry hand calculation
   Tolerance: < 0.1 deg

Dimensional audit:
  Stage             | Input Units       | Output Units    | Check
  path_zenith_rad   | rad               | rad             | ✓
  _slant_range_m    | m, rad            | m               | ✓
  _incidence_angle  | m, rad            | rad             | ✓
  GSD cross         | m × m / m         | m               | ✓
  GSD along         | m × m / (m × dim) | m               | ✓

Failure modes:
  - zenith = 0: returns nadir GSD (verified)
  - zenith → 89.5 deg (near-horizon): slant range large but finite
    (spherical Earth prevents infinity)
  - zenith > 89.5 deg: raise ValueError (below-horizon)
  - altitude = 0: skip gracefully (existing behavior)
  - Negative zenith: raise ValueError

Assumptions:
  - Spherical Earth with R = 6,371,000 m
  - No terrain elevation (target at sea level)
  - Along-track foreshortening uses INCIDENCE angle at ground, NOT
    the sensor zenith angle. These differ by ~5.7 deg at 45 deg from
    600 km due to Earth curvature. Using zenith instead of incidence
    introduces 12% error in along-track GSD at 45 deg.
  - Flat-Earth acceptable for altitude < 30 km AND zenith < 60 deg

Report format: Category C (full).
```

### Prompt 3A.2 — Swath width and access geometry (Gap 36)

```
Task: Add swath width, ground range, and access rate metrics.
Category: C (physics implementation)

Read first:
- docs/gaps.md (Gap 36)
- scenarios/03_raj_mission_planner/3.4_off_nadir_agility/walkthrough.md
  (access vs. quality trade table)
- src/radiant/performance/gsd.py (after 3A.1 — now has slant range
  and off-nadir GSD)
- src/radiant/performance/stage.py (where to wire new metrics)

Context:
Mission planners need swath width (n_pixels × GSD_cross), ground range
(distance from nadir to target on Earth's surface), and access area
rate (swath × ground_speed) to evaluate the quality-vs-coverage trade.
These are geometric computations with no signal-chain dependencies.

The ground range computation requires spherical Earth geometry:
  ground_range = R_E × arcsin(sin(θ) × (R_E + h) / R_E)
This is already exercised (indirectly) in scenario 3.4.

Design decisions:
1. New module: performance/access_geometry.py with pure functions
2. Functions are independent of ChainState — they take geometric
   parameters and return results
3. _compute_gsd_metrics() in stage.py calls these when altitude > 0
   and n_pixels is available
4. ground_speed_m_s is an optional parameter; access rate is skipped
   if not provided

Produce:
1. src/radiant/performance/access_geometry.py:
   - compute_ground_range_m(altitude_m, path_zenith_rad) → float
     Uses spherical Earth geometry
   - compute_swath_width_m(gsd_cross_m, n_pixels_cross) → float
     Simple multiplication
   - compute_access_rate_m2_s(swath_m, ground_speed_m_s) → float
     Rate of area coverage
2. Updated src/radiant/performance/stage.py:
   - After GSD computation, compute and store:
     ground_range_m, swath_width_m, access_rate_m2_s (when available)
3. src/radiant/performance/tests/test_access_geometry.py:
   - Ground range at nadir = 0
   - Ground range at 30 deg from 600 km matches walkthrough (312 km)
   - Ground range at 45 deg from 600 km matches walkthrough (527 km)
   - Swath = GSD × n_pixels identity
   - Access rate = swath × speed identity
4. Existing golden tests unchanged (new metrics only, no existing
   values modified)

Validation requirements (C):

Numerical truth anchors:
1. Scenario 3.4 walkthrough table: ground range at 10 angles
   Tolerance: < 1 km at all angles
2. Flat-Earth check: at small angles, ground_range ≈ H × tan(θ)
3. Geometric identity: swath = n_pixels × GSD_cross (exact)

Failure modes:
  - zenith = 0: ground range = 0 (nadir)
  - zenith > 89.5 deg: raise ValueError
  - n_pixels = 0: swath = 0 (valid)
  - ground_speed not set: access rate skipped

Report format: Category C.
```

**CHECKPOINT 3A:**
1. Run full test suite — all existing + new tests pass.
2. Rerun scenario 3.4 script — verify RADIANT GSD and NIIRS now match
   the hand-computed corrected values from the walkthrough.
3. Golden tests at nadir still pass (zenith=0 is default).

---

## PHASE 3B — OPTICAL ELEMENT MODEL (3 prompts)

Goal: implement the mixed-train radiometric model from
`docs/radiometric_model_mixed_train.md` — reflective and refractive
elements with proper per-surface physics, per-element thermal emission,
and scalar/curve T or R input.

### Prompt 3B.1 — Reflective/refractive element types, Mode 5 wiring, YAML config

```
Task: Extend OpticalElement to support reflective and refractive element
types per radiometric_model_mixed_train.md, with T/R specifiable as
scalar or spectral curve. Wire Mode 5 into OpticsStage. Define YAML
config format for mixed-train element lists.
Category: C (physics implementation)

Read first:
- docs/radiometric_model_mixed_train.md (Parts 1, 2, 5 — element types,
  signal path, Kirchhoff checks)
- src/radiant/optics/element.py (current OpticalElement, ElementKind,
  Kirchhoff enforcement)
- src/radiant/optics/element_list.py (compute_system_transmission,
  compute_downstream_transmission)
- src/radiant/optics/stage.py (lines 251-258 — resolve_transmission()
  call site; _build_effective_psf signature)
- src/radiant/optics/_schema.py (current parameter definitions)
- src/radiant/io/ (YAML loading patterns for sensor configs)
- src/radiant/api/_param_registry.py (build_parameter_set — scalar only)
- CLAUDE.md Rule 5 (emissivity always derived, never independent)

Context:
The current OpticalElement has a single transmittance and reflectance
(both SpectralData), with net_transmittance dispatching on ElementKind
(mirrors use R, others use T). This is correct but simplistic:

1. Refractive elements (lenses, windows, filters) have cavity effects
   between their two surfaces (R1, T1, R2, T2), bulk Beer-Lambert
   absorption, and effective emissivity that accounts for the cavity.
2. Reflective elements (mirrors) have only surface reflectance and
   Kirchhoff emissivity.
3. Users want to specify T or R as either a scalar (float) or a
   spectral curve (SpectralData or file path).

CRITICAL — Mode 5 dead code:
OpticsStage.run() (lines 251-258) calls resolve_transmission() passing
ONLY transmission_scalar. The full_elements argument is never passed,
making Modes 3/4/5 dead code. This prompt must wire Mode 5 (full element
list) into OpticsStage so that mixed-train element specs are actually
used by the signal chain.

CRITICAL — YAML config format:
ParameterSet only supports scalar types (float, int, str, bool). Mixed-
train element lists are structured data (list of dicts with per-element
properties). These CANNOT be represented as ParameterDefs. The solution:
define a YAML config format in io/element_config.py that deserializes
the element list into OpticalElement objects. OpticsStage receives the
deserialized list via a separate path (not through ParameterSet).

The design adds an ElementTransferMode enum (REFLECTIVE, REFRACTIVE)
at the element level and new factory functions, while keeping backward
compatibility with the existing OpticalElement constructor.

Design decisions:
1. Add ElementTransferMode enum: REFLECTIVE, REFRACTIVE.
2. The existing OpticalElement stays as-is for simple cases. A new
   RefractiveCavityElement extends the model with per-surface properties.
3. Factory functions accept float | SpectralData for T and R, converting
   scalars to flat SpectralData internally. This requires a wavelength
   grid argument.
4. The transfer factor C_i(λ) is:
   - REFLECTIVE: Rho_sys,i(λ)
   - REFRACTIVE: T_sys,i(λ) = T1 × beer × T2 / denom (cavity model)
   The existing net_transmittance property becomes an alias for C_i.
5. Emissivity computation:
   - REFLECTIVE: eps = 1 − Rho (Kirchhoff; no coating absorption term)
     Rationale: assuming no separate coating absorption is adequate for
     most mirror coatings (gold, silver, aluminum). If A_coat were
     significant, eps = 1 − Rho − A_coat, but we default A_coat = 0.
     Document this assumption explicitly.
   - REFRACTIVE cavity: eps_eff = T2 × n² × (1 − beer) / denom
     This replaces the simple 1 − T − R for cavity elements.
6. Kirchhoff self-consistency check (Part 5):
   - REFRACTIVE: eps_eff ≈ 1 − R_sys − T_sys at each λ
   - REFLECTIVE: eps ≈ 1 − Rho at each λ (with A_coat = 0)
   Validated in __post_init__, raises KirchhoffViolationError if >1e-4.
7. Wire Mode 5 into OpticsStage: when the user provides a full element
   list (via YAML config), OpticsStage passes it to resolve_transmission()
   as the full_elements argument. The existing scalar/curve modes
   (1-4) remain as fallbacks.
8. YAML config format for element lists (see schema below).

YAML element list schema:
```yaml
optical_elements:
  - name: "primary_mirror"
    kind: MIRROR
    transfer_mode: REFLECTIVE
    reflectance: 0.98          # scalar
    temperature_K: 290.0
    diameter_m: 0.35
    distance_to_fpa_m: 1.2
  - name: "secondary_mirror"
    kind: MIRROR
    transfer_mode: REFLECTIVE
    reflectance: "data/gold_reflectance.csv"  # spectral curve file
    temperature_K: 290.0
    diameter_m: 0.10
    distance_to_fpa_m: 0.8
  - name: "field_lens"
    kind: LENS
    transfer_mode: REFRACTIVE
    R1: 0.02
    T1: 0.98
    R2: 0.02
    T2: 0.98
    alpha: 0.1                 # 1/m, or file path for spectral
    n_refr: 1.5                # or file path for spectral
    thickness_m: 0.003
    temperature_K: 280.0
    diameter_m: 0.04
    distance_to_fpa_m: 0.3
    theta_r_rad: 0.0
```

The deserializer in io/element_config.py:
- Parses YAML into list[OpticalElement]
- Resolves file paths for spectral curves relative to config file
- Validates energy conservation per element
- Returns the element list for injection into OpticsStage

IMPORTANT: Do NOT break the existing OpticalElement constructor or
the make_lumped_element factory. All existing tests and configs must
continue to work unchanged.

Produce:
1. Updated src/radiant/optics/element.py:
   - New enum: ElementTransferMode (REFLECTIVE, REFRACTIVE)
   - OpticalElement gains optional transfer_mode field (default inferred
     from kind: MIRROR/COLD_STOP → REFLECTIVE, others → REFRACTIVE)
   - Existing emissivity property enhanced: if cavity properties present,
     use cavity emissivity formula; otherwise use simple Kirchhoff
   - New factory: make_reflective_element(name, reflectance, temperature_K,
     diameter_m, distance_to_fpa_m, wavelength_um=None)
     where reflectance is float | SpectralData
   - New factory: make_refractive_element(name, R1, T1, R2, T2, alpha,
     n_refr, thickness_m, temperature_K, diameter_m, distance_to_fpa_m,
     wavelength_um=None, theta_r_rad=0.0)
     where R1, T1, R2, T2, alpha, n_refr are each float | SpectralData
   - Cavity physics (Beer-Lambert, denominator, T_sys, eps_eff) in
     private helper methods or a CavityModel dataclass
   - Kirchhoff self-consistency check per Part 5

2. Updated src/radiant/optics/element_list.py:
   - compute_system_transmission uses element.net_transmittance (C_i)
     which now correctly returns T_sys for refractive elements and
     Rho_sys for reflective elements — NO changes needed here if the
     element API is correct. Verify and add tests.

3. Updated src/radiant/optics/stage.py:
   - Wire Mode 5: when full_elements is available (from YAML config
     or API), pass it to resolve_transmission() as the full_elements
     argument. Currently lines 251-258 only pass transmission_scalar.
   - The element list comes from either:
     (a) SensorConfig loaded via io/element_config.py (YAML path)
     (b) API: sensor.set_elements(element_list) method
   - When Mode 5 is active, system transmission comes from the element
     list (compute_system_transmission), not from the scalar parameter.

4. NEW src/radiant/io/element_config.py:
   - load_element_list(yaml_path) → list[OpticalElement]
   - Parses the optical_elements YAML section
   - Resolves scalar vs file-path for each T/R/alpha/n parameter
   - Calls make_reflective_element or make_refractive_element per item
   - Validates per-element and total energy conservation

5. src/radiant/optics/tests/test_element.py — extended:
   - Existing tests unchanged (backward compatibility)
   - New tests for make_reflective_element with scalar R
   - New tests for make_reflective_element with spectral R
   - New tests for make_refractive_element with all-scalar inputs
   - New tests for make_refractive_element with spectral inputs
   - Cavity physics: T_sys + R_sys + A_total = 1 at each λ (energy
     conservation)
   - Cavity emissivity ≈ 1 − R_sys − T_sys (Kirchhoff identity)
   - Beer-Lambert: zero absorption (alpha=0) → T_sys = T1×T2/(1−R1R2)
   - High absorption → T_sys → 0, eps → cavity thermal
   - Mirror element: transfer_mode=REFLECTIVE, C = R, eps = 1−R
   - Kirchhoff violation detection (T + R > 1)

6. src/radiant/optics/tests/test_element_list.py — extended:
   - Mixed train: 3-mirror telescope + 2-lens relay + 1 filter
   - System transmission = product of all C_i
   - Each C_i is correct type (R for mirrors, T_sys for lenses)

7. src/radiant/optics/tests/test_stage.py — extended:
   - Mode 5 integration: OpticsStage receives element list, computes
     system transmission from element C_i products
   - Mode 5 with mixed train gives different transmission than scalar
   - Mode 1 (scalar) still works (backward compatibility)

8. src/radiant/io/tests/test_element_config.py (NEW):
   - Load valid YAML with mixed-train elements
   - Scalar reflectance → flat SpectralData
   - File path reflectance → loaded SpectralData
   - Missing required field → actionable error
   - Energy conservation violation → error

Validation requirements (C):

Numerical truth anchors:
1. Uncoated glass window (R1=R2=0.04, alpha=0, n=1.5, d=3mm):
   T_sys = T1×beer×T2/denom = 0.96×1×0.96/(1−0.04×0.04) ≈ 0.9216/0.9984 ≈ 0.923
   R_sys = R1 + T1²R2beer²/denom ≈ 0.077
   eps_eff ≈ 1 − 0.923 − 0.077 = 0.0 (no absorption)
2. Gold mirror at 10 µm: R=0.98, eps=0.02, C=0.98
   Compare against published gold reflectance data
3. Energy conservation: T_sys + R_sys + eps_eff = 1 at every wavelength
   for both element types (verify to < 1e-6)

Dimensional audit:
  alpha(λ)        | 1/m              | 1/m              | ✓
  d               | m                | m                | ✓
  beer = exp(-αd) | dimless          | dimless           | ✓
  T_sys           | dimless          | dimless           | ✓
  eps_eff         | dimless          | dimless           | ✓
  B(λ,T)          | W/m²/sr/µm      | W/m²/sr/µm       | ✓

Failure modes:
  - R1 + T1 > 1 (surface energy violation): error
  - alpha < 0 (gain, not absorption): error
  - n < 1 (unphysical): error or warn
  - d = 0 (no substrate): beer=1, reduces to surface-only
  - Scalar R or T outside [0, 1]: error
  - Missing wavelength_um when scalar input given: error with
    message telling user to provide wavelength grid
  - YAML missing required field: actionable error naming the field
  - YAML with spectral file not found: actionable error with path

Assumptions:
  - Coating absorption A_coat = 0 for reflective elements (adequate
    for standard mirror coatings: gold, silver, aluminum). If future
    use cases require A_coat ≠ 0, add as optional parameter.
    Document: eps = 1 − Rho assumes all non-reflected energy is
    thermally emitted. For high-absorption coatings, this overpredicts
    emissivity by A_coat.
  - Cavity etalon model assumes plane-parallel surfaces
  - Beer-Lambert assumes homogeneous substrate

Self-review:
  - Confirm: emissivity is NEVER an independent input (Rule 5)
  - Confirm: existing make_lumped_element still works
  - Confirm: existing MIRROR elements with R and T=0 produce
    identical results to before this change
  - Confirm: Mode 5 is actually exercised in OpticsStage (not dead code)
  - Confirm: YAML deserialization round-trips correctly

Report format: Category C (full).
```

### Prompt 3B.2 — Thermal background path and per-element nearfield breakdown (Gap 11)

```
Task: Implement the mixed-train thermal background path per
radiometric_model_mixed_train.md Part 3, with per-element breakdown.
Category: C (physics implementation)

Read first:
- docs/radiometric_model_mixed_train.md (Parts 3, 4 — thermal path,
  combined irradiance)
- src/radiant/optics/element_list.py (compute_nearfield_irradiance —
  current total-only implementation)
- src/radiant/optics/stage.py (how nearfield is wired into chain)
- docs/gaps.md (Gap 11 — per-element breakdown)

Context:
The current compute_nearfield_irradiance() already implements the
correct physics: per-element eps × B(λ,T) × Ω × tau_downstream,
summed over all elements and scaled by cold-stop efficiency. However:

1. It returns only the TOTAL irradiance — no per-element breakdown.
2. The emissivity model uses simple Kirchhoff (1−T−R), not the
   cavity emissivity from the mixed-train model.
3. The geometric transfer factor uses the simple Ω = π(D/2)²/d²
   formula, not the full G_i = A_stop × cos(θ) / z² from the
   mixed-train model.

After 3B.1, elements carry proper cavity emissivity (refractive) or
surface emissivity (reflective). This prompt:
1. Updates nearfield computation to use the element's emissivity
   property (which now returns cavity eps_eff for refractive elements)
2. Returns per-element contributions in addition to the total
3. Stores per-element breakdown in stage_outputs

Design decisions:
1. compute_nearfield_irradiance() returns a new NearfieldResult
   dataclass with total and per_element dict
2. Per-element contributions: {element_name: SpectralData} for
   each element
3. Stage outputs gain nearfield_per_element key
4. The current total nearfield behavior is unchanged — just adds
   the breakdown
5. The geometric model (Ω = π(D/2)²/d²) is retained as-is for now.
   The full G_i = A_stop × cos(θ) / z² model from the mixed-train
   doc is a refinement that could be added later. Document why.

Produce:
1. Updated src/radiant/optics/element_list.py:
   - NearfieldResult dataclass: total (SpectralData), per_element
     (dict[str, SpectralData])
   - compute_nearfield_irradiance returns NearfieldResult
   - Each element's contribution stored before summing
   - Existing total computation unchanged

2. Updated src/radiant/optics/stage.py:
   - Reads NearfieldResult from compute_nearfield_irradiance
   - Stores total in stage_outputs["optics"]["nearfield_irradiance_at_fpa"]
     (unchanged key for backward compatibility)
   - Stores breakdown in stage_outputs["optics"]["nearfield_per_element"]

3. src/radiant/optics/tests/test_element_list.py — extended:
   - Per-element contributions sum to total (identity)
   - Single-element case: per_element[name] == total
   - Hot element + cold element: only hot element contributes
   - Mixed train: mirror + lens + filter, verify each contribution
   - Empty contribution for T=0 K element

Validation requirements (C):

Numerical truth anchors:
1. Single gold mirror at 290 K: nearfield = eps × B(λ, 290) × Ω
   Compare against hand calculation at 4 µm
2. Two-element train: mirror (290 K) + window (280 K). Verify:
   - Mirror contribution attenuated by window transmission
   - Window contribution unattenuated (last element)
   - Total = sum of both
3. Energy check: per-element contributions sum to total exactly

Failure modes:
  - All elements at 0 K: total = 0, per_element all zeros
  - Single element: per_element has one key
  - Duplicate element names: dict keys must be unique — validate

Report format: Category C.
```

### Prompt 3B.3 — Defocus model (Gap 29)

```
Task: Add optics.defocus_um parameter with defocus PSF degradation.
Category: C (physics implementation)

Read first:
- docs/gaps.md (Gap 29)
- scenarios/07_karen_test_engineer/7.3_mtf_measurement_vs_prediction/
  walkthrough.md (defocus sweep analysis)
- src/radiant/optics/_schema.py (current parameters)
- src/radiant/optics/stage.py (_build_effective_psf — where kernels
  are applied)
- src/radiant/optics/psf.py (EffectivePSF.with_kernel)
- src/radiant/platform/jitter.py (reference for kernel generation
  pattern — same pattern, different physics)

Context:
Defocus shifts the detector plane away from best focus, producing a
geometric blur spot. For small defocus (wave-optics regime), the
defocus PSF is approximately Gaussian with:

  σ_defocus = |δ| / (4 × f/# × √3)

where δ is the linear defocus [m] and the √3 comes from the RMS of
a uniformly illuminated circle.

More precisely, defocus is Zernike Z4 (Noll index 4) with coefficient:

  Z4_waves = δ / (8 × λ × (f/#)²)

For the kernel approach (this prompt), the Gaussian approximation is
adequate for small defocus (< several waves of Z4). Large defocus
produces a pill-box PSF which is NOT Gaussian — document this
limitation.

Design decisions:
1. New parameter: optics.defocus_um (float, default 0.0, unit µm)
2. Defocus kernel generated in OpticsStage after ePSF construction
3. Applied via epsf.with_kernel("defocus", kernel) — same pattern
   as IPC and jitter kernels
4. Kernel is 2D Gaussian, isotropic (defocus is rotationally symmetric)
5. When defocus_um = 0.0, no kernel applied (backward compatible)

Produce:
1. Updated src/radiant/optics/_schema.py:
   - New ParameterDef: optics.defocus_um (float, default 0.0,
     bounds [-500, 500], canonical_unit µm)
   - Negative defocus is valid (inside vs outside focus)

2. Updated src/radiant/optics/stage.py:
   - After _build_effective_psf(), if defocus_um != 0:
     compute σ_defocus from |defocus_um|, f_number
     generate 2D Gaussian kernel
     epsf = epsf.with_kernel("defocus", kernel)
   - Store defocus_sigma_m in stage_outputs["optics"]

3. src/radiant/optics/tests/test_stage.py — extended:
   - defocus_um = 0: ePSF unchanged (convolution history empty
     for defocus)
   - defocus_um = 5.0 at f/10: MTF at Nyquist decreases
   - defocus_um = -5.0: same result as +5.0 (symmetric)
   - Large defocus: FWHM increases measurably
   - Verify σ_defocus = |δ|/(4·f/#·√3) numerically

Validation requirements (C):

Numerical truth anchors:
1. Analytical MTF: for defocus at f/3, δ=10 µm:
   σ = 10e-6 / (4 × 3 × √3) = 0.481 µm
   MTF_defocus(f) = exp(-2π²σ²f²)
   Compare numerical kernel MTF against analytical at 5 frequencies
   Tolerance: < 1%
2. Zero defocus: ePSF identical to no-defocus case (bit-identical)
3. Scenario 7.3 reference: script computed defocus MTF analytically.
   RADIANT's kernel should match within 2% at Nyquist.

Assumptions:
- Gaussian approximation valid for small defocus (Marechal: Strehl > 0.5)
- Breaks down for large defocus where pill-box PSF dominates
- Document: for accurate large-defocus, use Zernike Z4 (after Gap 24)

Failure modes:
  - f_number not set: skip defocus (warn)
  - Very large defocus (> 100 µm at f/3): warn that Gaussian
    approximation may be inaccurate

Report format: Category C.
```

**CHECKPOINT 3B:**
1. Full test suite passes including all new element and nearfield tests.
2. Verify mixed-train example: 3-mirror TMA + 2 lenses + 1 filter,
   check system transmission and per-element nearfield are physical.
3. Verify Mode 5 wiring: OpticsStage with YAML element list produces
   correct system transmission (not the scalar fallback).
4. Golden tests unchanged.
5. Rerun scenario 7.3 with defocus parameter — compare against
   the external defocus MTF computed in the scenario script.


---

## PHASE 3C — PSF, MTF, & SPATIAL ENHANCEMENTS (4 prompts)

### Prompt 3C.1 — Wire smear into MTF chain

```
Task: Integrate platform smear into the signal chain via PlatformStage.
Category: C (physics implementation)

Read first:
- src/radiant/platform/smear.py (fully implemented, not wired)
- src/radiant/platform/stage.py (currently jitter-only)
- src/radiant/platform/_schema.py (currently jitter parameters only)
- src/radiant/platform/jitter.py (reference for integration pattern)
- docs/RADIANT_Spatial_Complete.md (smear section, if available)

Context:
Platform smear math is fully implemented in smear.py (smear_mtf_1d,
smear_width_m, smear_kernel_1d) with 158 lines of tested code. But
PlatformStage.run() only handles jitter — smear is not wired in.
Three smear sources exist (RADIANT_Spatial_Complete.md §7):
1. Platform along-track motion: v_ground × t_int × f / H
2. Scan mechanism cross-track motion (if applicable)
3. Untracked target motion (rarely used)

For Phase 3, implement source 1 (platform along-track smear) only.
Sources 2 and 3 are deferred.

Design decisions:
1. New parameters in platform/_schema.py:
   - platform.ground_velocity_m_s (float, default 0.0) — along-track
     ground velocity. For LEO at 600 km: ~6900 m/s.
   - Alternative: platform.smear_length_um (direct focal-plane smear
     input, bypassing the velocity/altitude computation). Useful when
     the user has already computed the smear from an orbit model.
   - If BOTH are set, smear_length_um takes precedence (override).
   - If NEITHER is set (both 0.0), no smear applied.
2. Smear kernel is 1-D (along-track = y-axis). Extension to 2-D for
   ePSF convolution:
   - Build 1-D rect kernel via smear_kernel_1d(npix, spacing, width)
   - Extend to 2-D via outer product: kernel_2d = delta_x ⊗ rect_y
     where delta_x = [0, 0, 1, 0, 0] (single-pixel Kronecker delta)
   - Kernel sizing: match the ePSF grid pitch (pixel_pitch / N_oversample)
   - Kernel extent: at least 2× the smear width, padded to odd size
   - Normalize: kernel_2d.sum() == 1.0
3. Smear computed after jitter in PlatformStage.run():
   - Jitter kernel first (isotropic)
   - Smear kernel second (directional, along-track)
   - Both applied via epsf.with_kernel()
4. smear_width_m() function uses SLANT RANGE (not altitude) for
   off-nadir consistency. After 3A.1, slant range is available from
   geometry. The angular rate on the focal plane is:
     omega_fp = v_ground / slant_range  (not v_ground / altitude)
   At nadir, slant_range = altitude, so this is backward compatible.
   Read geometry.path_zenith_rad and geometry.sensor_altitude_m from
   params, compute slant range using the helper from core/geometry.py
   (physics stages can import from radiant.core per Rule 11).
   Also needs optics.focal_length_m and
   spectral_integration.integration_time_s.

Produce:
1. Updated src/radiant/platform/_schema.py:
   - GROUND_VELOCITY_M_S (float, default 0.0, bounds [0, 50000])
   - SMEAR_LENGTH_UM (float, default 0.0, bounds [0, 1000])

2. Updated src/radiant/platform/stage.py:
   - After jitter handling, compute smear:
     If smear_length_um > 0, use directly
     Elif ground_velocity_m_s > 0, compute via smear_width_m()
     Else skip
   - Generate 2-D smear kernel (rect along y, delta along x)
   - Apply: epsf = epsf.with_kernel("smear", kernel_2d)
   - Store smear_width_m in stage_outputs["platform"]
   - Existing jitter code unchanged

3. src/radiant/platform/tests/test_stage.py — extended:
   - Zero smear: ePSF unchanged
   - Non-zero smear: FWHM_y increases, FWHM_x unchanged
   - smear_length_um overrides ground_velocity
   - MTF_y at Nyquist decreases with smear
   - Jitter + smear combined: both degrade ePSF
   - Known smear_width: verify sinc MTF matches smear_mtf_1d()

Validation requirements (C):

Numerical truth anchors:
1. Smear MTF: |sinc(π × f × smear_width)| at 5 frequencies
   Compare kernel-derived MTF against analytical sinc
   Tolerance: < 1%
2. Smear width at nadir: v=6900 m/s, H=600 km, f=3.5 m, t=0.5 ms
   smear = (6900/600000) × 3.5 × 0.0005 = 20.1 µm
   Verify function output matches
3. Smear width at 45 deg off-nadir: slant_range ≈ 815 km (not 600 km)
   smear = (6900/815000) × 3.5 × 0.0005 = 14.8 µm (LESS than nadir)
   This is correct: larger slant range → smaller angular rate → less smear
4. Zero smear: ePSF identical to jitter-only case

Cross-model consistency:
- smear_mtf_1d(freq, width) from smear.py should match the MTF
  extracted from the smear kernel convolved with a delta PSF
- 2-D kernel outer product verified: x-axis unchanged, y-axis smeared

Failure modes:
  - Negative velocity: raise ValueError
  - Altitude = 0 with velocity > 0: raise ValueError
  - Smear larger than PSF grid: warn and clamp kernel
  - 2-D kernel not normalized: raise assertion (sum must equal 1.0)

Report format: Category C.
```

### Prompt 3C.2 — Zernike-to-PSF, WavefrontError threading, per-λ PSF (Gaps 24 + 16)

```
Task: Implement Zernike polynomial evaluation for PSF computation,
thread full WavefrontError through PSF pipeline, expose per-wavelength
PSFs, and return structured PolychromaticPSFResult.
Category: C (physics implementation)

Read first:
- docs/gaps.md (Gaps 24, 16)
- src/radiant/optics/diffraction.py (compute_psf, make_pupil_phase —
  currently uses random phase screen; compute_polychromatic_psf
  returns tuple[ndarray, float] — needs structured return type)
- src/radiant/optics/wavefront.py (WavefrontError, WfeMode.ZERNIKE —
  data structure exists but not applied to PSF)
- src/radiant/optics/stage.py (_build_effective_psf — currently only
  receives wfe_rms_waves scalar, NEVER the full WavefrontError object)
- scenarios/05_tom_optical_designer/5.1_wfe_budget_allocation/
  walkthrough.md (Tom's Zernike coefficients)

Context — Gap 24:
WavefrontError already defines WfeMode.ZERNIKE with a zernike_coeffs
dict (Noll index → coefficient in waves). But diffraction.py ignores
this — make_pupil_phase() always generates a RANDOM phase screen
scaled to the requested RMS. This gives correct Strehl (same RMS =
same Marechal) but wrong PSF shape — coma produces a comet, astigmatism
produces a cross, a random screen produces neither.

The fix: implement Zernike polynomial evaluation on the pupil grid and
use the resulting OPD map instead of the random phase screen when
WfeMode.ZERNIKE is selected.

Context — Gap 16:
compute_polychromatic_psf() computes N monochromatic PSFs internally
but discards them after weighted summation. Per-wavelength PSFs are
needed for chromatic analysis. The fix is small: store intermediates
and return them alongside the combined PSF.

CRITICAL — WavefrontError not threaded (HIGH-1):
_build_effective_psf() currently receives ONLY wfe_rms_waves (a float
scalar). It never sees the WavefrontError object, so Zernike coefficients
are invisible to the PSF computation. This prompt must change the
signature chain:
  OpticsStage → _build_effective_psf(wfe: WavefrontError, ...)
              → compute_psf(wfe: WavefrontError, ...)
              → make_pupil_phase (dispatches on wfe.mode)
When wfe.mode == SCALAR_RMS, behavior is identical to current code
(uses wfe.rms_waves for random phase). When wfe.mode == ZERNIKE,
uses the Zernike coefficients.

CRITICAL — PolychromaticPSFResult (HIGH-2):
compute_polychromatic_psf() currently returns tuple[ndarray, float].
Replace with a proper dataclass:
  @dataclass(frozen=True)
  class PolychromaticPSFResult:
      combined_psf: ndarray           # weighted sum across wavelengths
      pixel_scale_m: float            # focal-plane pixel scale
      per_wavelength: dict[float, ndarray] | None  # if requested
      wavelengths_um: ndarray         # wavelength grid used
      weights: ndarray                # spectral weights used
This makes the return type self-documenting and extensible.

Design decisions:
1. New file: optics/zernike.py with Zernike polynomial evaluation
   - Uses Noll indexing (standard in optical engineering)
   - Evaluates on a circular pupil grid with optional obscuration
   - Returns 2-D OPD map in waves
   - WARNING: for obscuration_ratio > 0.30, emit UserWarning that
     standard Zernike polynomials are NOT orthogonal on an annular
     pupil. The correct basis is annular Zernikes (Mahajan), but this
     implementation does NOT implement annular Zernikes. Results are
     still usable — the OPD map is physically valid — but the
     individual Zernike coefficients lose their orthogonal
     interpretation. Document this limitation.
2. diffraction.py gains a new function: make_pupil_phase_zernike()
   that replaces make_pupil_phase() when WfeMode.ZERNIKE
3. Change function signatures (HIGH-1 wiring):
   - _build_effective_psf(wfe: WavefrontError, ...) — replaces
     wfe_rms_waves: float
   - compute_psf(wfe: WavefrontError, ...) — dispatches on wfe.mode
   - compute_polychromatic_psf(wfe: WavefrontError, ...) →
     PolychromaticPSFResult
   - When wfe.mode == SCALAR_RMS: uses wfe.rms_waves (identical to
     current behavior)
   - When wfe.mode == ZERNIKE: uses wfe.zernike_coeffs
4. PolychromaticPSFResult dataclass replaces tuple return (HIGH-2)
5. Per-wavelength PSFs stored in stage_outputs when computed
6. Backward compatibility: WavefrontError with mode=SCALAR_RMS produces
   identical results to the current scalar path

Produce:
1. src/radiant/optics/zernike.py (NEW):
   - noll_to_nm(j) → (n, m): Noll index to radial/azimuthal order
   - zernike_radial(n, m, rho) → R_n^m(rho) polynomial
   - zernike_polynomial(j, rho, theta) → Z_j(rho, theta)
   - evaluate_zernike_opd(coeffs_dict, npix, obscuration_ratio) →
     2-D OPD array in waves
   - If obscuration_ratio > 0.30: emit UserWarning about non-
     orthogonality of standard Zernikes on annular pupil

2. Updated src/radiant/optics/diffraction.py:
   - make_pupil_phase_zernike(npix, coeffs, wavelength_m,
     obscuration_ratio) → 2-D phase screen [radians]
     Uses evaluate_zernike_opd × 2π to convert OPD waves → phase rad
   - Updated compute_psf(wfe: WavefrontError, ...): dispatch on
     wfe.mode. Signature changes from scalar wfe_rms_waves to full
     WavefrontError object.
   - Updated compute_polychromatic_psf(wfe: WavefrontError, ...) →
     PolychromaticPSFResult (replaces tuple return)
   - PolychromaticPSFResult dataclass (frozen):
     combined_psf, pixel_scale_m, per_wavelength, wavelengths_um, weights

3. Updated src/radiant/optics/wavefront.py:
   - Ensure WavefrontError can be constructed with mode=SCALAR_RMS
     using just rms_waves (backward compatible)

4. Updated src/radiant/optics/stage.py:
   - _build_effective_psf() signature: receives WavefrontError instead
     of wfe_rms_waves scalar. Dispatches:
     SCALAR_RMS → existing path (random phase via wfe.rms_waves)
     ZERNIKE → make_pupil_phase_zernike() path
   - Handles PolychromaticPSFResult return type
   - When psf_n_wavelengths > 1, stores per-wavelength PSFs in
     stage_outputs["optics"]["per_wavelength_psfs"] as dict
     {wavelength_um: EffectivePSF}

5. src/radiant/optics/tests/test_zernike.py (NEW):
   - Noll indexing: Z1=piston, Z2=tip, Z3=tilt, Z4=defocus, Z5=astig
   - Each polynomial normalized: ∫∫ Z_j² dA = π (over unit circle)
   - Orthogonality: ∫∫ Z_j × Z_k dA = 0 for j≠k
   - Z4 (defocus): radial profile is 2ρ²−1
   - Z7 (coma): asymmetric → PSF is comet-shaped (verify asymmetry)
   - Obscured pupil: Zernike evaluated only where amplitude > 0
   - Annular warning: obscuration > 0.30 triggers UserWarning

6. src/radiant/optics/tests/test_diffraction.py — extended:
   - Zernike mode with Z4 only: PSF shows defocus ring structure
   - Zernike mode with Z7: PSF is asymmetric (coma)
   - Zernike mode with RMS = scalar_rms mode: Strehl agrees (Marechal)
   - PolychromaticPSFResult: verify fields populated correctly
   - Per-wavelength PSFs: count matches psf_n_wavelengths
   - Per-wavelength PSFs: blue PSF narrower than red PSF
   - Backward compat: WavefrontError(mode=SCALAR_RMS) → same result
     as old scalar wfe_rms_waves path

7. src/radiant/optics/tests/test_stage.py — extended:
   - wfe_mode="scalar_rms": unchanged behavior (verify bit-identical)
   - wfe_mode="zernike": ePSF shape differs from random phase
   - per_wavelength_psfs stored when psf_n_wavelengths > 1
   - _build_effective_psf receives WavefrontError, not scalar

Validation requirements (C):

Numerical truth anchors:
1. Zernike Z4 (defocus): with coeff = 1 wave at 633 nm,
   Strehl = exp(-(2π × 1/√3 × 0.633e-6 / λ_op)²)
   (Note: RMS of Z4 with coeff c is c/√3 for a filled aperture)
   Compare against Marechal approximation
2. Zernike orthogonality: ∫Z_j × Z_k = 0 for j≠k
   Verify numerically for first 15 polynomials (< 1e-3)
3. Literature: Born & Wolf table of Zernike polynomials.
   Verify Z1-Z15 definitions match standard Noll convention.

Assumptions:
- Noll indexing convention (NOT ANSI/OSA — document difference)
- Circular pupil with optional central obscuration
- Standard (NOT annular) Zernike polynomials used even on obscured
  apertures. For obscuration > 30%, a UserWarning is emitted. The
  OPD map is still physically valid (it represents a real wavefront
  shape), but individual Zernike coefficients lose their orthogonal
  decomposition meaning. Annular Zernikes (Mahajan 1981) are NOT
  implemented — this is a known limitation, not a bug.
- Phase screen is monochromatic; polychromatic uses same coeffs
  with wavelength-scaled OPD

Failure modes:
  - Empty coefficients dict: return flat wavefront (no aberration)
  - Noll index 0: raise ValueError (Noll starts at 1)
  - Very large coefficients (> 10 waves): warn (beyond Marechal)
  - Obscuration ratio ≥ 1: raise ValueError
  - Obscuration ratio > 0.30: emit UserWarning (non-orthogonal basis)

Report format: Category C (full).
```

### Prompt 3C.3 — Field-dependent WFE with chromatic Zernikes (Gap 25)

```
Task: Implement field-dependent wavefront error with per-field-point
Zernike sets (no interpolation) and chromatic Zernike handling for
refractive systems.
Category: C (physics implementation)

Read first:
- docs/gaps.md (Gap 25)
- src/radiant/optics/wavefront.py (WfeMode.FIELD_DEPENDENT,
  FieldWfeSample — data structure defined, raises NotImplementedError)
- src/radiant/optics/zernike.py (after 3C.2 — Zernike evaluation)
- src/radiant/optics/diffraction.py (after 3C.2 — PSF from Zernike,
  PolychromaticPSFResult)
- src/radiant/optics/stage.py (_build_effective_psf — after 3C.2
  receives WavefrontError)
- scenarios/05_tom_optical_designer/5.1_wfe_budget_allocation/
  walkthrough.md (Tom has Zernikes at 4 field positions)

Context:
FieldWfeSample is already defined: (field_x, field_y, rms_waves,
zernike_coeffs). WavefrontError.rms_opd_m() raises NotImplementedError
for field_dependent mode. Tom has Zernike sets at 4 field positions
(on-axis + 3 off-axis) and cannot evaluate edge-of-field performance.

KEY DESIGN CHANGE — No interpolation:
The user has specified: NO interpolation of Zernike coefficients
between field points. Each field point must have its own unique,
user-defined Zernike coefficient set. The user selects which field
point to evaluate; RADIANT does NOT interpolate between them.

Rationale: Zernike coefficient interpolation is approximate and can
produce unphysical intermediate wavefronts (e.g., interpolating between
coma and astigmatism). Optical design tools (Zemax, Code V) provide
exact Zernike decomposition at each field point. Users should provide
these directly rather than rely on approximate interpolation.

KEY DESIGN — Chromatic Zernikes for refractive systems:
For multispectral or broadband systems, the wavefront aberrations of
refractive elements are wavelength-dependent (chromatic aberration).
Reflective elements have wavelength-independent wavefront errors.
The design distinguishes:

1. REFLECTIVE systems (all-mirror or mirror-dominated):
   A single set of Zernike coefficients is adequate across all
   wavelengths. The PSF changes size with wavelength (diffraction
   scales as λ/D) but the wavefront shape is achromatic.

2. REFRACTIVE systems (lens-based or lens-containing):
   Zernike coefficients vary with wavelength due to chromatic
   aberration (dispersion, longitudinal/lateral color). The user
   must provide unique Zernike coefficient sets at several wavelengths.
   The polychromatic PSF computation uses the wavelength-specific
   Zernike set for each monochromatic PSF.

Design decisions:
1. NO INTERPOLATION between field points. User selects a field point
   index (or field coordinates that must exactly match a tabulated
   point). If the requested position is not tabulated: raise
   ValueError with a message listing available field positions.
2. FieldWfeSample.zernike_coeffs is now REQUIRED (not optional).
   Each field sample must carry its own Zernike set.
3. New: ChromaticZernikeTable for refractive systems. This is a
   mapping: {wavelength_um: dict[int, float]} — Zernike coefficients
   at each wavelength. Used per-field-point.
4. New field in FieldWfeSample: chromatic_zernikes (optional):
   dict[float, dict[int, float]] — wavelength → Zernike coefficients.
   If present, overrides the single zernike_coeffs for polychromatic
   PSF computation.
5. New field in WavefrontError: optical_type (REFLECTIVE or REFRACTIVE)
   - REFLECTIVE: single zernike_coeffs per field point, used at all λ
   - REFRACTIVE: chromatic_zernikes required per field point
   Default: REFLECTIVE (backward compatible)
6. WavefrontError.at_field(field_x, field_y) → returns the exact
   FieldWfeSample at that position (no interpolation). Raises
   ValueError if position not in field table.
7. New method: WavefrontError.at_field_nearest(fx, fy) → returns the
   nearest tabulated field point (convenience, with warning if
   distance > 0.01 in normalized coordinates).
8. OpticsStage evaluates PSF at the selected field position by default
   (on-axis if not specified).
9. For polychromatic PSF with refractive chromatic Zernikes:
   compute_polychromatic_psf() looks up wavelength-specific Zernikes
   for each monochromatic PSF computation. If a wavelength falls
   between tabulated chromatic wavelengths, use the NEAREST tabulated
   wavelength (no interpolation — consistent with field-point policy).

Produce:
1. Updated src/radiant/optics/wavefront.py:
   - FieldWfeSample.zernike_coeffs is now required (not optional)
   - FieldWfeSample gains chromatic_zernikes: dict[float, dict[int, float]] | None
     Maps wavelength_um → Zernike coefficients for refractive systems
   - WavefrontError gains optical_type: ElementTransferMode
     (REFLECTIVE or REFRACTIVE, default REFLECTIVE)
   - WavefrontError.at_field(fx, fy) → FieldWfeSample
     Returns EXACT match only. Raises ValueError with list of
     available positions if not found.
   - WavefrontError.at_field_nearest(fx, fy) → FieldWfeSample
     Returns nearest tabulated point. Warns if distance > 0.01.
   - WavefrontError.rms_opd_m() for field_dependent: returns the
     on-axis field point's RMS. Document.
   - Validation in __post_init__:
     If optical_type == REFRACTIVE and any field sample lacks
     chromatic_zernikes → raise ValueError with actionable message

2. Updated src/radiant/optics/_schema.py:
   - optics.field_position_x (float, default 0.0, bounds [-1, 1],
     normalized field coordinate)
   - optics.field_position_y (float, default 0.0, bounds [-1, 1])

3. Updated src/radiant/optics/stage.py:
   - _build_effective_psf(): when wfe_mode == "field_dependent":
     Read field_position from params
     Get FieldWfeSample via wfe.at_field(fx, fy)
     If optical_type == REFLECTIVE:
       Use sample.zernike_coeffs for all wavelengths
     If optical_type == REFRACTIVE:
       Pass sample.chromatic_zernikes to polychromatic PSF builder
       Each monochromatic PSF uses its wavelength-specific Zernikes
     Build PSF using Zernike path (from 3C.2)
   - Store selected field point + coefficients in stage_outputs

4. Updated src/radiant/optics/diffraction.py:
   - compute_polychromatic_psf() gains optional chromatic_zernikes
     parameter: dict[float, dict[int, float]].
     When provided, each monochromatic PSF at wavelength λ looks up
     the nearest wavelength key in chromatic_zernikes and uses those
     Zernike coefficients instead of the single set.

5. src/radiant/optics/tests/test_wavefront.py — extended:
   - at_field at a tabulated point: returns exact FieldWfeSample
   - at_field at non-tabulated point: raises ValueError with
     helpful message listing available positions
   - at_field_nearest: returns nearest point, warns if far
   - REFLECTIVE: single zernike_coeffs across wavelengths
   - REFRACTIVE with chromatic_zernikes: verify different coeffs
     at different wavelengths
   - REFRACTIVE without chromatic_zernikes: raises ValueError
   - 4-point field table from scenario 5.1

6. src/radiant/optics/tests/test_stage.py — extended:
   - field_dependent REFLECTIVE: same Zernikes at all λ,
     PSF scaling differs (diffraction)
   - field_dependent REFRACTIVE: different Zernikes at different λ,
     polychromatic PSF shows chromatic aberration structure
   - field_dependent with on-axis: results similar to scalar_rms
     with equivalent RMS
   - field_dependent with off-axis: larger WFE → worse Strehl
   - Default field_position = (0,0): on-axis evaluation

Validation requirements (C):

Numerical truth anchors:
1. On-axis Zernike lookup: exact match to tabulated coefficients
2. Reflective polychromatic: same Zernikes at 0.5 µm and 0.8 µm,
   PSF width scales as λ/D (verify ratio)
3. Refractive chromatic: defocus Zernike varies with λ (simulating
   longitudinal chromatic aberration), polychromatic PSF broader
   than any individual monochromatic PSF

Assumptions:
- NO interpolation between field points or wavelengths.
  User must provide exact Zernike data at each point of interest.
- For refractive systems, chromatic_zernikes must span the
  operational wavelength range. Monochromatic PSFs at wavelengths
  between tabulated points use the NEAREST tabulated wavelength.
- Reflective systems: wavefront is achromatic (mirror figure error
  is geometric, not wavelength-dependent). Single Zernike set
  is physically correct.
- Refractive systems: wavefront varies with wavelength due to
  dispersion. Separate Zernike sets at multiple wavelengths capture
  defocus (longitudinal chromatic), coma (lateral color), and higher-
  order chromatic effects.

Failure modes:
  - Query field position not in table: raise ValueError with
    list of available positions
  - Only 1 field point: return that point (valid — on-axis only design)
  - Field table with duplicate positions: raise ValueError
  - REFRACTIVE with missing chromatic_zernikes: raise ValueError
  - Chromatic table with single wavelength: warn (reduces to achromatic)
  - No zernike_coeffs in field sample: raise ValueError

Report format: Category C.
```

### Prompt 3C.4 — Aliased / folded MTF (Gap 14)

```
Task: Compute the aliased (folded) MTF for undersampled systems.
Category: C (physics implementation)

Read first:
- docs/gaps.md (Gap 14)
- src/radiant/performance/system_mtf.py (mtf_at_nyquist)
- src/radiant/performance/stage.py (_compute_spatial_metrics)
- src/radiant/performance/qsample.py (Q parameter)

Context:
For undersampled systems (Q < 1), scene spatial frequencies above
Nyquist fold back into the baseband, creating apparent contrast that
is actually aliasing. The pre-sampling (optical) MTF does not capture
this effect. The folded MTF sums all aliased copies:

  MTF_folded(f) = Σ_{k=-∞}^{+∞} MTF_optical(f + k × f_Nyquist)

In practice, summing k = -3 to +3 (7 copies) is sufficient since
the optical MTF falls to near-zero at the diffraction cutoff.

The folded MTF tells the user how much of the signal at frequency f
is "real" vs aliased.  For well-sampled systems (Q > 2), the folded
MTF equals the optical MTF.

Design decisions:
1. New module: performance/folded_mtf.py
2. Pure function: compute_folded_mtf(freq, mtf_optical, f_nyquist)
3. Returns FoldedMTFResult with folded MTF curve and alias fraction
   (ratio of aliased energy to total energy at each frequency)
4. Computed in _compute_spatial_metrics when Q < 2 (only meaningful
   for undersampled or near-Nyquist systems)
5. Stored as new metrics: mtf_folded_at_nyquist, alias_fraction
6. Full folded curve stored in stage_outputs

Produce:
1. src/radiant/performance/folded_mtf.py (NEW):
   - compute_folded_mtf(freq_cy_m, mtf_values, f_nyquist_cy_m,
     n_folds=3) → FoldedMTFResult
   - FoldedMTFResult: freq, mtf_folded, alias_fraction
   - alias_fraction(f) = (folded(f) - optical(f)) / folded(f)

2. Updated src/radiant/performance/stage.py:
   - After spatial metrics, if Q < 2.0:
     Compute folded MTF from the system MTF curve
     Store mtf_folded_at_nyquist, alias_fraction_at_nyquist
     Store full curves in stage_outputs

3. src/radiant/performance/tests/test_folded_mtf.py (NEW):
   - Well-sampled (Q=2): folded MTF = optical MTF (alias = 0)
   - Undersampled (Q=0.5): folded MTF > optical MTF (alias > 0)
   - n_folds=0: returns optical MTF unchanged
   - Symmetry: folded MTF at f = folded MTF at f_Nyquist - f
   - Monotonicity: alias fraction increases toward Nyquist

Validation requirements (C):

Numerical truth anchors:
1. Analytical: for a Gaussian MTF (exp(-af²)) with known f_Nyquist,
   the folded sum can be computed analytically as a theta function.
   Compare numerical vs analytical at 5 frequencies. Tolerance: < 0.1%
2. Well-sampled limit: Q >> 1 → folded = optical (verify < 1e-6 diff)
3. Published: Holst "Electro-Optical Imaging System Performance"
   provides folded MTF examples for sinc detector MTF.

Failure modes:
  - f_nyquist = 0: raise ValueError
  - MTF values negative: raise ValueError
  - MTF values > 1: warn (possible with aliasing — physically valid)
  - Empty frequency array: return empty result

Report format: Category C.
```

**CHECKPOINT 3C:**
1. Full test suite passes.
2. Golden tests unchanged.
3. Rerun scenario 5.1 with Zernike coefficients — verify PSF shape
   differs from random phase but Strehl matches.
4. Rerun scenario 5.2 — verify folded MTF appears for undersampled
   configurations.
5. Verify smear integration: rerun scenario 1.4 (pushbroom) with
   ground_velocity set — confirm MTF_y degrades with smear.
6. Verify smear uses slant range: rerun scenario 3.4 with smear
   enabled — smear at 45 deg off-nadir should be LESS than at nadir
   (larger slant range → smaller angular rate).
7. Verify chromatic Zernikes: refractive system with wavelength-
   dependent Zernike coefficients produces broader polychromatic PSF
   than achromatic case.
8. Verify annular warning: system with obscuration > 30% emits
   UserWarning when using Zernike mode.

10. **Reviewer pass:** adversarial review of all Phase 3 deliverables.
    Focus on:
    - Does off-nadir GSD match the scenario 3.4 walkthrough tables?
    - Does incidence angle differ from zenith angle at 45 deg?
    - Does cavity emissivity satisfy Kirchhoff at every wavelength?
    - Is Mode 5 actually exercised (not dead code)?
    - Are Zernike polynomials correctly normalized?
    - Does annular pupil warning fire at obscuration > 30%?
    - Is smear kernel oriented along the correct axis (y = along-track)?
    - Does smear use slant range (not altitude)?
    - Does folded MTF handle the well-sampled limit correctly?
    - Do field-dependent Zernikes reject non-tabulated positions?
    - Do chromatic Zernikes produce different PSFs at different λ?
    - Does PolychromaticPSFResult contain all expected fields?

---

## OPERATING PRINCIPLES

Same as Phase 2, plus:

1. **Backward compatibility is non-negotiable.** Every new parameter
   defaults to a value that reproduces current behavior (0.0, "scalar",
   etc.). Golden tests must pass without modification.

2. **No cross-stage imports for physics.** Slant-range geometry lives
   in core/geometry.py (importable by all stages per import rules).
   Zernike polynomials live in optics/. Smear lives in platform/ and
   can import slant-range helpers from core/geometry.py (core/ imports
   are allowed by Rule 11). This preserves the import boundary.

3. **Rerun originating scenario after fixing a gap.** Gap 33 → scenario
   3.4. Gap 29 → scenario 7.3. Gap 24 → scenario 5.1. The scenario
   script is the acceptance test.

4. **One task per conversation.** Each prompt is one conversation.
   Do not combine prompts.

5. **No dead code.** Every new code path must be exercised by at least
   one test AND reachable from the signal chain. If Mode 5 exists,
   OpticsStage must be able to invoke it. If a return type is defined,
   callers must handle it.

6. **Structured data bypasses ParameterSet.** Complex inputs (element
   lists, chromatic Zernike tables, field-dependent WFE) use YAML
   config + deserialization, not ParameterDef scalars. ParameterSet
   remains for scalar parameters only.

7. **No interpolation of Zernike coefficients.** Between field points
   or between wavelengths, use exact tabulated values only. This is a
   deliberate design choice — interpolation of wavefront coefficients
   is approximate and can produce unphysical wavefronts.

8. **Batch scenario regression at every checkpoint.** Run all scenario
   scripts (1.x–7.x) after each sub-phase. Any output change must be
   explained and documented.

---

## TOTAL EFFORT ESTIMATE

| Prompt | Effort | Category | Notes |
|--------|--------|----------|-------|
| 3A.1 | 4-6 hours | C | +SceneGeometry enhancement, incidence angle |
| 3A.2 | 2-3 hours | C | |
| 3B.1 | 8-12 hours | C | +Mode 5 wiring, YAML config, io/element_config.py |
| 3B.2 | 3-5 hours | C | |
| 3B.3 | 2-3 hours | C | |
| 3C.1 | 4-6 hours | C | +slant range, 2-D kernel details |
| 3C.2 | 8-12 hours | C | +WavefrontError threading, PolychromaticPSFResult, annular warning |
| 3C.3 | 6-8 hours | C | Rewritten: no interpolation, chromatic Zernikes |
| 3C.4 | 3-4 hours | C | |
| **Total** | **40-59 hours** | | |

---

## GAP CLOSURE MAP

| Gap | Prompt | Status After |
|-----|--------|-------------|
| 33 | 3A.1 | FIXED |
| 34 | 3A.1 | FIXED (cascades from 33) |
| 35 | 3A.1 | FIXED |
| 36 | 3A.2 | FIXED |
| 11 | 3B.2 | FIXED |
| 29 | 3B.3 | FIXED |
| 24 | 3C.2 | FIXED |
| 16 | 3C.2 | FIXED |
| 25 | 3C.3 | FIXED |
| 14 | 3C.4 | FIXED |
| — | 3B.1 | Mixed-train model + Mode 5 wiring + YAML config (new capability) |
| — | 3C.1 | Smear → MTF with slant-range correction (new capability) |
| — | 3C.2 | WavefrontError threading + PolychromaticPSFResult (arch fix) |
| — | 3C.3 | Chromatic Zernikes for refractive systems (new capability) |
