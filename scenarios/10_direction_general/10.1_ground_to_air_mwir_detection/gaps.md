# Scenario 10.1 — Gaps

Limitations of RADIANT hit while building and running this `ground_to_air` scenario, with
the workaround each one forced. Open items here are mirrored to `docs/tracking/gaps.md`
by the Phase-5 orchestrator; the per-scenario copy is the primary record of *how* the
scenario worked around each one.

The Phase 1–4 direction-general machinery itself worked as specified — the up-looking
triangle, the derived scene class and its assertion, `SkyBackground` selection, the
metric-relevance map with Gap-96 override semantics, the horizon guard, and the Rule-4
dual-path check all behaved exactly as the docs claim. Nothing below is a defect in that
delivery; they are the edges the first real ground-to-air scene ran into.

---

## G10.1-1: Detection range is unavailable for **every** ground-to-air scene with the target inside the atmosphere

**Severity**: High (it removes the class's headline metric)
**Status**: OPEN — the refusal is correct behaviour; the missing capability is the gap
**Where**: `radiant/performance/path_optical_depth.py` (profile construction),
consumed by `radiant/performance/stage.py::_compute_detection_range_metric`

**What happens.** `detection_range_m` is absent from `result.metrics` and
`detection_range_result.ok` is `False`, with:

> Detection range is not available for an up-looking path whose continuation is still
> inside the atmosphere: the target sits at 10000 m and the ray leaves the modelled
> column (h_atm_top = 100000 m) only at 115174 m, past the 11544 m reference range.
> Extinction along that continuation varies with altitude, and the metric layer has no
> altitude-resolved extinction profile to integrate — reusing the constant-extinction
> model here is exactly the error finding GF-15 reports.

**Why it matters.** The refusal is a correct Rule-17 named failure — substituting a
constant-α model there is exactly the error GF-15 reports. But the *condition* it
refuses on ("continuation still inside the column") is true for the entire ground-to-air
class with a target below `h_atm_top`, i.e. every aircraft, UAS and balloon target there
is. The path-aware solver as shipped serves only up-looking targets already at or above
100 km (SST/space) and level arms. For scene class E2 the headline metric is
structurally unreachable.

**Workaround used.** The scenario computes detection range by walking the ray with the
**full chain**: at each trial path length `s` the target is placed at the altitude the
ray reaches, `h(s) = sqrt(R_E^2 + s^2 + 2 R_E s cos(zeta_low)) - R_E`, and the chain is
re-evaluated; 24 bisection halvings of a < 400 km bracket converge to < 25 m. This is
more expensive (about 200 chain evaluations, ~18 s) but strictly more correct than any
1-D extinction profile — the background, the noise and the transmittance are all
re-derived at every trial range.

**Suggested fix.** Give `path_optical_depth` an altitude-resolved extinction profile for
the in-column continuation (the atmosphere already integrates optical depth slab-by-slab
in `segment_simple`), or expose the chain-walk as a first-class solver. Either way it is
a `performance/` + `atmosphere/` task, not a scenario one.

---

## G10.1-2: Sky background behind an up-looking target depends on the target's altitude

**Severity**: Medium (systematic, signed, and it biases SNR optimistic)
**Status**: **RESOLVED 2026-07-29** (commit `5c0f3dd`, CU-254). The sky is now one whole-path
evaluation rooted at the **sensor**, and the `SkyBackground` assembly arm passes it through
instead of re-propagating it, so the background is a property of the ray as this entry says
it must be. Re-measured on the shipped config at fixed pointing: 2.214790e5 e⁻ at target
altitudes of 10, 20, 50 and 99 km — identical to the last digit, against the 1.94207e5 /
2.14046e5 / 2.21479e5 spread recorded below. Headline metrics moved with it: SNR
136.424 → 131.465, NEDT 0.648013 → 0.672457 K, i.e. the ≈ 3.5 % optimism this entry
predicted, removed. The `.gui.expected.json` baseline was regenerated; **the numeric tables
in `walkthrough.md` are from the pre-fix run and are stale until the scenario is re-run** —
the `background [e⁻]`, `SNR` and `NEDT` columns of its zenith sweep are the affected ones.
**Where**: `radiant/atmosphere/uplooking_quantities.py::_sky_radiance_at_aperture` (was
`sky_radiance.py` + `segment_simple.py` composition)

**What happens.** A ground sensor pointed at a fixed zenith sees a fixed sky column, but
the composed background drifts with where the target is placed:

| target altitude [km] | sky background [e⁻] | deficit vs full column [%] |
|---|---|---|
| 10 | 1.7528 × 10⁵ | −12.9 |
| 20 | 1.9415 × 10⁵ | −3.5 |
| 40 | 2.0072 × 10⁵ | −0.3 |
| 99 | 2.0130 × 10⁵ | 0 (reference: the ray leaves the column at the target) |

**Why it matters.** The LOS terminates on cold space in every row, so the sky radiance
arriving at the sensor is a property of the *ray*, not of the target. The chain composes
`L_bkg = L_up(sensor→target) + tau(sensor→target)·L_sky(target→top)`, and the simple
model's single-effective-temperature graybody per segment is not additive, so the
composition loses radiance. Direction of the error is always the same: the composed sky
is too dim, so SNR comes out optimistic (≈ 3.5 % at this scenario's nominal point, where
background shot noise carries 55 % of the noise variance; more for a dimmer target).

MODTRAN says the composition makes it worse rather than better: in 3–5 µm the
single-segment full column gives 0.7230 W/m²/sr and the composed 10 km value
0.6304 W/m²/sr, against MODTRAN K5 (0 → 20 km) at 0.8027 W/m²/sr — ratios 0.901 and
0.785 respectively.

**Workaround used.** None applied — the scenario reports the size and sign of the effect
(script section 5b, walkthrough §11) so the SNR column is read with the right caveat.

**Suggested fix.** Either make the segment thermal model additive under splitting (carry
an effective emission temperature that composes), or have `SkyBackground` evaluate the
whole sensor→top column once and take the behind-target term as
`L_sky(full) − L_up(sensor→target)` so the identity closes by construction.

---

## G10.1-3: The shipped up-looking MODTRAN family cannot serve an off-vertical query

**Severity**: Medium (blocks the tabulated-atmosphere path for this whole class)
**Status**: OPEN — known and deliberate; recorded here because it bit this scenario
**Where**: `radiant/atmosphere/interpolated.py::InterpolatedAtmosphere.uplooking_column_product`

**What happens.** `src/radiant/data/tables/atmospheres/midlat_summer_uplooking_ladder`
is vertical-only, and an off-vertical query raises `AtmosphereValidationError` naming
`VERTICAL` rather than mapping through airmass `sec(ζ)` space the way the down-looking
`midlat_summer_boost_offnadir` family does.

**Why it matters.** Every point of this scenario except ζ_low = 0 is off-vertical, so
the tabulated (MODTRAN-anchored) atmosphere is unusable for the whole sweep and the
scenario is confined to `atmosphere.model = "simple"` — which is exactly the model whose
+17 % to +30 % MWIR τ excess §10 of the walkthrough measures. The refusal is well
justified: `test_k6_uplooking_zenith_coupling_characterization` measures the sec-law
error at 0.14 % (VIS) to 2.16 % (LWIR), i.e. small but not negligible, and a silent
mapping would be a Rule-17 violation.

**Workaround used.** `atmosphere.model = "simple"` throughout, with the MODTRAN K-ladder
used as an external comparison rather than as the model.

**Suggested fix.** Owner-run MODTRAN batch 2 with an off-vertical up-looking axis (the
plan already schedules the SST full-column ladder there), then widen the family's axes.

---

## G10.1-4: The point-source refusal has no "use sub-pixel instead" auto-path

**Severity**: Low (usability; the error message is already actionable)
**Status**: OPEN
**Where**: `radiant/optics/stage.py::_validate_psf_regime_consistency`

**What happens.** A declared `scene_type = "point_source"` raises when
`sqrt(A_t)/d > 0.1 · PSF_FWHM` — for this camera and nozzle, at any slant range below
6.952 km. Conversely a declared `scene_type = "sub_pixel"` at 2 km is silently *promoted*
to `point_source` with a `UserWarning`. The two declarations are therefore not symmetric:
one raises, one warns and overrides.

**Why it matters.** A detection-range sweep naturally crosses the boundary. A scenario
that walks a target in from 60 km to 1 km has to change `scene_type` mid-sweep, and it
has to know the 0.1 · FWHM rule to know where.

**Workaround used.** The MODTRAN anchor rungs at 1, 3 and 5 km column depth are run with
`scene_type = "sub_pixel"`; the atmospheric column product is regime-independent, so τ
and `L_path` are unaffected. That is structural, not incidental: `AtmosphereStage` runs
*before* `OpticsStage` finalizes the regime (Rule 10) and reads no regime input at all —
τ depends only on the two altitudes and ζ_low. Spot-checked at the 10 km rung, where both
declarations resolve to `point_source`: `max |Δτ| = 0.0` across the whole grid. The
detection walk stays above 6.952 km slant range throughout, so it never crosses.

**Suggested fix.** Either let `scene_type = "auto"` (already the default) be documented
as the answer for range sweeps, or make the two declarations symmetric — both warn-and-
correct, or both raise.

---

## Not gaps (checked, behaved as documented)

* **`geometry.scene_class` assertion** — accepts the agreeing label silently, raises
  `GeometrySpecificationError` naming asserted *and* derived plus both altitudes on
  disagreement. Exactly ADR-0011 decision 8.
* **Metric relevance + Gap-96 override** — the class turns 10 ground-projection metrics
  off by default; an explicit `performance.metrics.sampling` flag wins in both
  directions; GSD stays absent under force-enable because it is *undefined* at
  `incidence_angle_rad ≥ π/2`, which is a computability gate rather than a relevance
  default.
* **Horizon guard** — clean at 87.5°, `UserWarning` at 88.5°, raises at 89.7°. The bands
  match `RADIANT_Geometry.md` §4.1 exactly.
* **Rule-4 dual-path consistency** — silent at all eight sweep points, worst residual
  7.671 × 10⁻⁴ against a 2.0 × 10⁻² tolerance.
* **SCNR ≡ SNR in the point-source regime** — a definitional identity, not a bug (the
  point-source signal is already background-subtracted).
* **NEDT of 454–3269 mK** — correct for a 0.5 ms track camera against a dim MWIR sky;
  NEDT is background-referenced and is not this sensor's requirement metric.
