# Task Report: Prompt 3A.2 — Swath width and access geometry (Gap 36)

## Category: C

## Files
Created:
  - `src/radiant/performance/ground_range.py` — compute_ground_range_m()
  - `src/radiant/performance/swath_width.py` — compute_swath_width_m()
  - `src/radiant/performance/access_rate.py` — compute_access_rate_m2_s()
  - `src/radiant/performance/tests/test_access_geometry.py` — 15 tests
Modified:
  - `src/radiant/performance/stage.py` — Added _compute_access_metrics(), wired after GSD
  - `src/radiant/performance/tests/test_gsd.py` — 7 new access wiring tests
  - `src/radiant/detector/_schema.py` — Added N_PIXELS_CROSS parameter
  - `src/radiant/atmosphere/_schema.py` — Added GROUND_SPEED_M_S parameter
  - `docs/tracking/gaps.md` — Gap 36 marked CLOSED
Tests added:
  - `src/radiant/performance/tests/test_access_geometry.py` — 15 tests (9 ground_range, 3 swath, 3 access_rate)
  - `src/radiant/performance/tests/test_gsd.py` — 7 new tests (TestAccessMetricsWiring)

## Test Results
Total tests: 1693
Passing: 1693
Failing: 0

## Design Decisions

### Separate modules per Rule 19
Ground range, swath width, and access rate are independent pure functions with no shared state. Each gets its own module per Rule 19.

### Graceful degradation
All three metrics skip gracefully when their inputs are not available:
- Ground range: requires altitude_m and path_zenith_rad (defaults to 0.0)
- Swath width: requires n_pixels_cross > 0
- Access rate: requires ground_speed_m_s > 0

### Parameter defaults
- `detector.n_pixels_cross` defaults to 0 (not set), so existing tests are not affected.
- `geometry.ground_speed_m_s` defaults to 0.0 (not set), so access rate is skipped by default.

### Ground range formula
Uses law of cosines on the (sensor, Earth center, target) triangle with ray-sphere slant range, consistent with `core/geometry.py`:

```
cos(gamma) = (r_s² + R_E² - d²) / (2 × r_s × R_E)
ground_range = R_E × gamma
```

Note: ground range values differ from scenario 3.4 walkthrough because the walkthrough used the atmospheric slant-path formula, not the geometric ray-sphere intersection. The geometric formula is correct for GSD/access geometry; the atmospheric formula is correct for atmospheric path length. See `test_gsd.py` lines 283-288 for the same note.

## Numerical Validation

### Truth Anchor 1: Ground range at 30 deg from 600 km
  Source: Hand calculation (law of cosines on ray-sphere triangle)
  slant = 704.1 km, R_E = 6371 km, r_s = 6971 km
  cos(gamma) = (6971² + 6371² - 704.1²) / (2 × 6971 × 6371)
  Expected: 352.2 km
  Actual: 352.2 km
  Relative error: < 0.1%
  Regime notes: Consistent with ray-sphere geometry in core/geometry.py.

### Truth Anchor 2: Ground range at 45 deg from 600 km
  Source: Hand calculation
  slant = 892.9 km
  Expected: 632.4 km
  Actual: 632.4 km
  Relative error: < 0.1%

### Truth Anchor 3: Flat-Earth limit
  Source: Analytic — at small angles, ground_range ≈ H × tan(θ)
  At 5 deg from 600 km: flat ≈ 52.6 km, spherical ≈ 52.5 km
  Relative error: < 1%
  Regime notes: Spherical and flat-Earth converge at small angles.

### Truth Anchor 4: Swath width identity
  Source: Definition — swath = n_pixels × GSD_cross
  Verified exact (multiplication identity).

### Truth Anchor 5: Access rate identity
  Source: Definition — rate = swath × speed
  Verified exact (multiplication identity).

## Dimensional Audit

| Stage | Input Units | Output Units | Conversion | Check |
|-------|-------------|-------------|------------|-------|
| altitude_m | m | m | none | ✓ |
| path_zenith_rad | rad | rad | none | ✓ |
| slant_range | m | m | ray-sphere | ✓ |
| cos(gamma) | m²/m² | dimensionless | law of cosines | ✓ |
| ground_range | m × rad | m (arc length) | R_E × gamma | ✓ |
| swath_width | m × dimensionless | m | multiply | ✓ |
| access_rate | m × m/s | m²/s | multiply | ✓ |

Issues: none

## Failure Modes Tested

| Case | Expected | Actual |
|------|----------|--------|
| zenith = 0 | ground_range = 0 | ✓ |
| zenith > horizon | ValueError | ✓ |
| zenith < 0 | ValueError | ✓ |
| altitude = 0 | ground_range = 0 | ✓ |
| n_pixels = 0 | swath = 0 | ✓ |
| ground_speed not set | access rate skipped | ✓ |
| n_pixels_cross not set | swath and access rate skipped | ✓ |
| No altitude in params | all access metrics skipped | ✓ |

## Assumptions

**Assumption: Spherical Earth with R = 6,371,000 m**
  Why valid: Standard mean Earth radius. Same constant used throughout RADIANT.
  What breaks: Ellipsoidal Earth would give different ground range at polar/equatorial latitudes (< 0.3% error).
  Detected how: Not detected at runtime; documented.

**Assumption: Target at sea level**
  Why valid: Consistent with GSD computation (no terrain elevation).
  What breaks: Mountain targets at high elevation would have different ground range.
  Detected how: Not detected; geometry.target_altitude_m exists but is not used here.

**Assumption: Ground range is arc distance, not chord distance**
  Why valid: For mission planning, arc distance along the surface is the relevant quantity (it corresponds to what a map shows).
  What breaks: Nothing — arc distance is the correct quantity for ground range.

## Fragility Points

**What breaks this implementation?**
- Near-horizon angles: cos_gamma denominator is never zero (r_s > R > 0), and slant_range_spherical_m raises ValueError for beyond-horizon angles. No numerical instability.
- Very high altitude (GEO): law of cosines is numerically stable for all altitudes. Ground range can exceed π × R_E (halfway around the Earth) which is physically correct.

**Mitigations:**
- cos_gamma clamped to [-1, 1] for floating-point safety.
- slant_range_spherical_m validates horizon limit before ground range computation.

## Traceability
Same inputs → identical outputs: verified (deterministic, no random state)
Deterministic seed: N/A (no stochastic components)
Intermediate values inspectable: yes — ground_range_m, swath_width_m, access_rate_m2_s all stored as individual metrics

## Regression Status
Existing tests: 1671/1671 passing (unchanged)
New tests added: 22 (15 pure function + 7 wiring)
Changes to existing tests: 0
Changes to golden values: none

## Self-Review

**Physics:** Ground range uses law of cosines with ray-sphere slant range — geometrically exact for spherical Earth. Swath and access rate are trivial identities.

**Code:** Three separate modules (Rule 19). Pure functions, no state. Stage wiring follows existing `_compute_gsd_metrics` pattern with graceful skip.

**Architecture:** No cross-stage imports. New parameters have backward-compatible defaults (0 = not set). `_compute_access_metrics` runs after `_compute_gsd_metrics` in the stage pipeline.

**Scope:** Implemented only what Gap 36 requested. No additional features.

## Open Issues or Questions

1. **Ground range discrepancy with walkthrough**: The walkthrough table reports 527.2 km at 45° while RADIANT computes 632.4 km. This is because the walkthrough used the atmospheric slant-path formula (which gives a shorter slant range of 814.8 km vs geometric 892.9 km). The geometric ray-sphere formula is correct for ground geometry; the atmospheric formula is correct for atmospheric path. The walkthrough should be updated to note this distinction, or use the geometric formula for ground range.
