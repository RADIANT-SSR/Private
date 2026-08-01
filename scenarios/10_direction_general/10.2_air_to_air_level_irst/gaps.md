# Scenario 10.2 — Gaps

Every RADIANT limitation this scenario hit, with the workaround actually used.
Open items are mirrored into `docs/tracking/gaps.md` (Rule 6 of
`docs/guides/scenario_testing.md`) by the orchestrating session; nothing here
edits the registry directly.

---

## Gap A — T7 point-intensity door bypasses the matrix-§7 point-source angular-size guard

**Severity**: Medium
**Status**: OPEN
**File**: `src/radiant/source/_inferrer.py` (T7 branch) →
`src/radiant/optics/stage.py::_validate_psf_regime_consistency`

**Description.** `OpticsStage._validate_psf_regime_consistency` implements the
matrix-§7 validity check for a declared point source: it raises
`ParameterBoundsError` when $\sqrt{A_t}/d > 0.1\,\text{PSF FWHM}$, because
pre-integrating a resolved target into a delta function silently drops spatial
structure (Rule 17). The guard reads
`stage_outputs["source"]["angular_extent_rad"]`.

When the target is built through the **T7 point-intensity door**
(`source.target.point_intensity_temperature_K` / `_area_m2` / `_emissivity`),
`SourceStage` publishes `projected_area_m2 = 1e-12` and
`angular_extent_rad = 4e-11` — sentinel values — **regardless of a user-set
`geometry.target.projected_area_m2`**. The guard therefore never fires on that
door.

**Evidence (reproducible).** With `geometry.target.projected_area_m2 = 500.0`
at 25 km slant range (a target subtending 20 pixels) the T7 door evaluates
silently and reports `POINT_SOURCE`. The *same* geometry through the T1 thermal
door raises:

> `OpticsStage: point_source target has resolved angular extent √A_t/d =
> 8.944e-04 rad, which is 19.495× PSF_FWHM (4.588e-05 rad)`

and the T1 door also (correctly) rejects this scenario's own 0.36 m² target at
25 km, at 1.170× PSF FWHM.

**Why it matters.** The guard exists precisely so a point-source
approximation cannot be applied outside its domain without the user knowing.
The IRST use case reaches RADIANT almost exclusively through T7 (targets are
specified in W/sr), so the door most likely to need the guard is the one that
does not run it.

**Impact.** SNR, contrast SNR and `detection_range_m` for any T7 target of
finite extent. One-sided and bounded: over-concentrating the target's energy
makes the reported EE_box — hence SNR — mildly optimistic, by roughly
$1/\sqrt{1 + (\text{extent}/\text{FWHM})^2}$ = 0.967 at this scenario's nominal
point.

**Workaround used.** The runner computes $\sqrt{A_t}/d$, the system PSF FWHM
and their ratio itself, prints the ratio against the 0.1 bound at every sweep
point, and reports the range beyond which the bound would be met (130.8 km for
this target). The scenario therefore states its own validity rather than
relying on the (inert) guard.

---

## Gap B — `detection_range_m` holds total noise constant, so it depends on the range it is evaluated at

**Severity**: Medium
**Status**: RESOLVED 2026-08-01 — promoted to CU-263 and fixed there. The solvers
now use the shot-consistent criterion `S(R)/√(S(R) + N₀²) = threshold` with
`N₀² = σ_ref² − S_ref` the target-free floor (option (a) of the suggested fix,
in the exact form option (c) asked for). Re-measured on this sweep: the spread
is **1.00×** (198.6 km referenced at 25 km, 198.9 km at 100 km) and the nominal
50 km answer moved **150.9 km → 198.8 km (+31.7 %)**. The record below is the
original finding as filed.
**File**: `src/radiant/performance/detection_generic.py`,
`src/radiant/performance/detection_path_aware.py`,
`src/radiant/performance/detection_beer_lambert.py`

**Description.** The detection-range solvers scale the signal along the path,
$S(R) = S_{ref}(R_{ref}/R)^2\,\tau(R)/\tau(R_{ref})$, while holding the **total**
noise fixed at its reference value. That is exact only in a background-limited
system. When the target's own shot noise dominates — as it does for a bright
point source at short range — the frozen noise is largely a term that vanishes
as the target recedes, and the answer becomes strongly reference-dependent.

**Evidence.** Identical configuration, range swept:

| reference range | `detection_range_m` | total noise | of which target shot | target-free floor |
|---:|---:|---:|---:|---:|
| 25 km | 123.4 km | 735.5 e⁻ rms | 732.2 e⁻ rms | 70.1 e⁻ rms |
| 100 km | 182.5 km | 116.4 e⁻ rms | 92.9 e⁻ rms | 70.2 e⁻ rms |

a factor 1.48 spread for one design against one target. Re-solving against the
target-free floor (70.2 e⁻ rms) gives 200.2 km.

*Post-fix (2026-08-01):* 198.6 km referenced at 25 km, 198.8 km at 50 km,
198.9 km at 100 km — a 1.00× spread. The 0.4 km residual is the band-mean τ
model's own reference dependence (α_eff 0.01812 → 0.01809 km⁻¹), not the noise
treatment. The 200.2 km floor-only solve is now an upper bound the chain sits
0.7 % below, because the chain keeps the target's residual shot noise.

**Why it matters.** Detection range is the headline number for an IRST. A
metric whose value depends on where the analyst happened to place the target is
not usable as a figure of merit, and nothing in the result object says so.

**Impact.** `detection_range_m` in the point-source regime, all scene classes —
this is not direction-specific.

**Suggested fix.** Either (a) recompute the shot-noise term at the trial range
inside the root find, or (b) surface the reference-range dependence in the
metric record (a `reference_range_m` field plus a note), or (c) solve against
the target-independent noise floor and document that as the definition. Any of
the three; silently returning a reference-dependent number is the problem.

**Workaround used (superseded by the fix).** The runner printed the noise
decomposition at both ends of the sweep, explained the mechanism, and re-solved
against the target-free floor to publish the number an engineer would actually
quote. It now prints the same decomposition as *evidence that the fix holds*,
with the floor-only solve retained as a cross-check bound.

---

## Gap C — no atmospheric refraction model; the guard band is the whole treatment

**Severity**: Low for this scenario, by design
**Status**: WORKAROUND (ratified exclusion — ADR-0011 decision 5/6)

**Description.** RADIANT models no refraction. Near-horizontal paths are
guard-banded instead: clean below 100 m tangent depression, a quantified
`UserWarning` to 2 km, `ParameterBoundsError` beyond. The warning names the
excluded physics but does not size it, so the analyst cannot tell from the
message whether the caveat matters.

**Impact.** 6 of the 16 sweep points (75–100 km) fall in the warning shoulder
and carry an unsized caveat.

**Workaround used.** The runner sizes it: with the standard $k = 4/3$
effective-Earth factor the tangent sag at 100 km falls from 195.9 m to 146.9 m,
the modelled ray samples air ~32.6 m lower than the real one on average, and
with $H_\rho = 6.5$ km and a band optical depth of 1.810 that is worth
**0.91 %** in band transmittance — two orders of magnitude smaller than the
band-model error Gap D measures on the same arm. The scenario proceeds and says
so.

**Note.** This is a *ratified exclusion*, not a defect. It is logged because a
scenario in the warning shoulder needs the number, and today every such
scenario has to derive it independently. A one-line magnitude estimate in the
guard's own warning context would remove that duplication.

---

## Gap D — the simple level arm cannot reproduce band saturation in the MWIR

**Severity**: High for long-arm MWIR work
**Status**: OPEN (a known limitation, quantified here for the level arm)
**File**: `src/radiant/atmosphere/simple.py` (CU-161 region-flat spectral shape)

**Description.** The analytic level arm exponentiates a single extinction
coefficient over the chord. Its *per-wavelength* transmittance is exactly
exponential — which is correct physics — but its band mean can only be
sub-exponential to the extent that $k(\lambda)$ varies inside the band. In the
MWIR the simple model's $k(\lambda)$ is essentially flat across 3.5–5.0 µm
(CU-161), so the band-mean effective extinction is flat too, and MODTRAN's real
band saturation is not reproduced at all.

**Evidence** (MODTRAN L16–L20 at 10 km altitude, midlat summer, 23 km
visibility, rural aerosol):

| band | α(5 km)/α(100 km), MODTRAN | α(5 km)/α(100 km), model | model/MODTRAN τ at 100 km |
|---|---:|---:|---:|
| MWIR 3.5–5.0 µm | 7.60× | 1.01× | **0.334** (−66.6 %) |
| LWIR 8–12 µm | 2.43× | 1.25× | 0.756 (−24.4 %) |

**Impact.** SNR, contrast SNR and detection range at long range on any level (or
near-level) MWIR arm. The error is one-sided: the model is too opaque, so
RADIANT is **pessimistic**.

**Workaround used.** The scenario anchors against the delivered L-grid, states
the usable band (within ~5 % to 25 km; treat > 50 km MWIR as a lower bound),
and reports the direction of the bias next to every headline number.

**Follow-on.** The decks for a horizontal `InterpolatedAtmosphere` family at
constant altitude already exist (L1–L25); wiring one would remove this gap for
the air-to-air class entirely.

---

## Not gaps — things that worked

- `scene_class` derivation, publication, and the optional
  `geometry.scene_class` assertion: correct and silent.
- The V0 chord door on a level path (`φ = 2 asin(d/2r)`, `θ_o = π/2 + φ/2`):
  exact to machine precision against the closed form.
- The horizon guard's topology split (`interior_tangent` vs `endpoint_minimum`)
  and its Δh thresholds: crossover at 71.45 km matched the analytic prediction.
- Both Gap 111 kinematics doors, their agreement check, and the raise on
  disagreement.
- Scene-class metric relevance (guardrail G3): all ten ground-projection metrics
  suppressed, all three target-plane metrics present, no per-metric branching
  visible from the outside.
- `SkyBackground` auto-selection from the LOS termination.
- The Rule-4 dual-path consistency check: silent, residual 1.0e−03 against a
  2e−02 tolerance.
