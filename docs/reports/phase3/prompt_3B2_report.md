# Task Report: Prompt 3B.2 — Per-element nearfield breakdown (Gap 11)

## Category: C

## Files
Modified:
  - `src/radiant/optics/element_list.py` — `compute_nearfield_irradiance()` now returns `NearfieldResult` with per-element breakdown
  - `src/radiant/optics/stage.py` — Extracts `.total` from NearfieldResult; stores `.per_element` in stage_outputs
  - `src/radiant/optics/__init__.py` — Exports `NearfieldResult`
  - `src/radiant/optics/tests/test_element_list.py` — Updated existing tests for NearfieldResult return type; added 8 per-element tests
  - `docs/gaps.md` — Gap 11 marked CLOSED

Tests added:
  - `src/radiant/optics/tests/test_element_list.py` — 8 new tests (TestNearfieldPerElement class)

## Test Results
Total tests: 1701
Passing: 1701
Failing: 0

## Design Decisions

### NearfieldResult as frozen dataclass
`NearfieldResult` is a frozen dataclass with two fields:
- `total`: SpectralData — the total nearfield irradiance at the FPA (same as the previous return value)
- `per_element`: dict[str, SpectralData] — per-element contributions keyed by element name

Both `total` and each per-element contribution include cold-stop efficiency scaling, so `sum(per_element.values()) == total` is an exact identity.

### Zero-temperature elements excluded from per_element
Elements with `temperature_K == 0.0` are skipped (no emission), and do not appear in `per_element`. This avoids cluttering the dict with zero-valued entries.

### Backward compatibility
The stage extracts `.total` from the result for the existing `nearfield_irradiance_at_fpa` stage output. The `per_element` dict is stored as a new stage output `nearfield_per_element`. No downstream code changes needed.

## Numerical Validation

### Truth Anchor 1: Single mirror per-element
  Source: Hand calculation
  Expected: eps(0.02) × B(290K, λ) × Omega(π×0.15²/1.2²) = same as total
  Actual: per_element["primary"].values == total.values
  Relative error: < 1e-12
  Regime notes: Identity for single-element case.

### Truth Anchor 2: Two-mirror per-element breakdown
  Source: Hand calculation
  M1 (primary): eps=0.02, T=290K, Omega1=π×0.15²/1.2², tau_down=0.95
  M2 (secondary): eps=0.05, T=300K, Omega2=π×0.05²/0.6², tau_down=1.0
  Expected M1: 0.02 × B(290) × Omega1 × 0.95
  Expected M2: 0.05 × B(300) × Omega2 × 1.0
  Actual: matches to rtol=1e-10
  Regime notes: Downstream attenuation correctly applied per-element.

### Truth Anchor 3: Sum-to-total identity
  Source: Mathematical identity
  Expected: sum(per_element[k].values for all k) == total.values
  Actual: matches to rtol=1e-12
  Regime notes: Holds for any number of elements, any cold_stop_efficiency.

## Dimensional Audit

| Stage | Input Units | Output Units | Conversion | Check |
|-------|-------------|-------------|------------|-------|
| eps_i | dimensionless | dimensionless | none | ✓ |
| B(λ, T_i) | W/m²/sr/µm | W/m²/sr/µm | Planck function | ✓ |
| Omega_i | sr | sr | π(D/2)²/d² | ✓ |
| tau_down_i | dimensionless | dimensionless | product | ✓ |
| contribution_i | W/m²/µm | W/m²/µm | multiply | ✓ |
| × eta_cold | dimensionless | W/m²/µm | scale | ✓ |
| per_element[name] | W/m²/µm | W/m²/µm | stored | ✓ |
| total (sum) | W/m²/µm | W/m²/µm | sum | ✓ |

Issues: none

## Failure Modes Tested

| Case | Expected | Actual |
|------|----------|--------|
| Empty element list | ValueError | ✓ |
| cold_stop > 1.0 | ValueError | ✓ |
| T=0 K element | Not in per_element | ✓ |
| All elements T=0 K | total=0, per_element empty | ✓ |
| Single element | per_element matches total | ✓ |
| cold_stop=0.5 | All values halved | ✓ |

## Assumptions

**Assumption: Element names are unique**
  Why valid: OpticalElement names are set by the user; duplicates would overwrite earlier entries in per_element dict.
  What breaks: If two elements share a name, only the last one's contribution is stored.
  Detected how: Not validated at runtime; documented. Element list construction should enforce uniqueness.

**Assumption: Cold-stop efficiency applies uniformly to all elements**
  Why valid: The cold stop blocks a fraction of the total solid angle seen by the FPA. This fraction is the same for all elements.
  What breaks: Non-uniform cold stop geometry (e.g., baffles that block some elements more than others).
  Detected how: Not detected; would require per-element cold-stop factors.

## Fragility Points

**What breaks this implementation?**
- Duplicate element names: later entries overwrite earlier ones in the per_element dict. The total is still correct (it sums contributions before storing per-element), but the breakdown is wrong.
- Very large element lists: O(N²) downstream transmission computation (same as before, not changed by this task).

**Mitigations:**
- Total is computed independently of per_element dict (sum into array, then store per-element separately). Total is always correct even if per_element has name collisions.
- N² scaling is acceptable for realistic optical trains (N < 20).

## Traceability
Same inputs → identical outputs: verified (deterministic, no random state)
Deterministic seed: N/A (no stochastic components)
Intermediate values inspectable: yes — per_element dict provides full breakdown

## Regression Status
Existing tests: 1701/1701 passing
Changes to golden values: none
New tests added: 8 (TestNearfieldPerElement class)

## Self-Review

**Physics:** Per-element contributions are computed identically to before — the only change is capturing each contribution before summing. Cold-stop efficiency applied to each per-element entry ensures sum-to-total identity.

**Code:** NearfieldResult is a frozen dataclass (Rule 7 spirit). No mutations. Stage extracts `.total` for backward compatibility; stores `.per_element` as new stage output.

**Architecture:** No new cross-stage imports. NearfieldResult stays in `optics/element_list.py` (where the computation lives). Exported via `optics/__init__.py`.

**Scope:** Only Gap 11 addressed. No additional features.

## Open Issues or Questions

None.
