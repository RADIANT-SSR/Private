# CU-009 — Stage-2 inferrer: wire `_infer_los` to the existing `geometry.*` params (kill the nadir/Kármán hardcode)

**Category:** B (core abstraction — inferrer routing through already-registered parameters) with C-level radiometric impact on any *future* scenario whose YAML actually sets a non-nadir / non-default geometry. The fix itself adds zero new schema parameters; it lights up an existing parameter surface that has been registered but unread by the producer side.
**Triggered from:** [docs/tracking/Cleanup_Backlog.md](Cleanup_Backlog.md) CU-009, escalated 2026-04-26 after stage-deferral expired (Stage 5 landed without producer-side wiring) and audit found the original "register `source.observer_geometry.*` namespace" framing creates redundant parameter names for quantities the AtmosphereStage schema already owns.
**Scope:** ~30–60 lines of production code in [src/radiant/source/_inferrer.py](../src/radiant/source/_inferrer.py) (`_infer_los` reads three already-registered `geometry.*` params; `_view_direction_from_los` reads from the canonical name instead of the unregistered `geometry.observer_zenith_rad`). One new schema entry — `geometry.observer_zenith_rad` only if it's kept as a separate concept; otherwise removed in favor of `geometry.path_zenith_rad`. New Level 0 tests; **zero existing-baseline drift** under the recommended approach.

---

## Problem statement

[src/radiant/source/_inferrer.py:286–292](../src/radiant/source/_inferrer.py#L286) returns `LineOfSightGeometry(h_tgt=h_tgt_m, theta_o=0.0)` with `theta_s` and `delta_phi` unset and `h_atm_top` defaulting to `1.0e5` m (Kármán line). Only `h_tgt` reads from a parameter (`geometry.target_altitude_m`). Every scenario the inferrer touches therefore lands at **nadir, Kármán-line, no solar geometry** — regardless of YAML intent.

Stage 6's E_sky decomposition ([atmosphere/assembly.py:786](../src/radiant/atmosphere/assembly.py#L786) `_assemble_t3`, [assembly.py:1112](../src/radiant/atmosphere/assembly.py#L1112) `_assemble_ground_background`) has the *capability* to consume real `θ_s` and `Δφ` — the consumer side is wired. The producer side (`_infer_los`) never supplies them. Reflective / two-leg / sky-decomposition scenarios silently fire as sun-overhead-and-on-axis.

### What the audit found (the part that changes the framing)

The CU-009 backlog entry's recommendation — *"register `source.observer_geometry.theta_o`, `source.observer_geometry.theta_s`, `source.observer_geometry.delta_phi`, and `source.observer_geometry.h_atm_top` (optional; default 1e5) as `ParameterDef`s on the SourceStage schema"* — would create a second namespace for parameters that the AtmosphereStage schema **already owns and that downstream stages already consume**:

| `LineOfSightGeometry` field | Existing registered parameter | Owning schema | Default | Downstream consumers (today) |
|---|---|---|---|---|
| `theta_o` | `geometry.path_zenith_rad` | [atmosphere/_schema.py:144](../src/radiant/atmosphere/_schema.py#L144) | 0.0 rad | [platform/stage.py:240](../src/radiant/platform/stage.py#L240), [performance/stage.py:265,304](../src/radiant/performance/stage.py#L265), [atmosphere/modtran.py:245](../src/radiant/atmosphere/modtran.py#L245) |
| `theta_s` | `geometry.solar_zenith_rad` | [atmosphere/_schema.py:156](../src/radiant/atmosphere/_schema.py#L156) | 0.5 rad (~28.6°) | [atmosphere/simple.py:473,743,825](../src/radiant/atmosphere/simple.py#L473), [atmosphere/modtran.py:727](../src/radiant/atmosphere/modtran.py#L727) |
| `delta_phi` | `geometry.solar_azimuth_rad` | [atmosphere/_schema.py:168](../src/radiant/atmosphere/_schema.py#L168) | 0.0 rad | (registered, no live consumer yet) |
| `h_atm_top` | (none — class default 1e5 m) | — | 1e5 m | (Stage-7+ ADR territory) |

The inferrer is the **outlier**. Every other stage that needs LOS geometry already pulls from `geometry.*`. The CU-009 fix is "wire `_infer_los` to the params that already exist," not "register a parallel namespace."

### Latent finding folded into this task

[src/radiant/source/_inferrer.py:323](../src/radiant/source/_inferrer.py#L323) (`_view_direction_from_los`) reads `geometry.observer_zenith_rad` with a `try/except KeyError → 0.0` fallback. **That parameter is not registered in any schema** (verified via repo-wide grep on `_schema.py`). The fallback silently masks the missing registration. Three downstream consumers (`source/material.py`, `source/reflected.py`, `source/combined.py`) accept an `observer_zenith_rad` argument that flows from a different code path entirely. The unregistered name is a Rule-12 violation (every parameter has a `ParameterDef`) and a Rule-17 violation (silent-on-missing-key). It is folded into CU-009 because the surgery — replacing the unregistered read with the canonical `geometry.path_zenith_rad` — is the same one-line change in the same file with the same semantics (`theta_o` at the target).

### Why a fix is needed now

- **CU-007 ordering.** When CU-007 lands (MWIR-routes-to-T3Mixed), `_assemble_t3` will consume `theta_s` for the six MWIR baseline cells. If CU-009 lands AFTER CU-007, those cells re-baseline twice — once for T3 routing and again when `theta_s` finally gets plumbed. Landing CU-009 first means CU-007's MWIR snapshot refresh captures the *correct* solar geometry on the first cut.
- **CU-011 unblocking.** The MODTRAN `tau_sun = tau` alias (CU-011) has no exercise path until non-zero `theta_s` reaches the backend. Today it can't, even with mixed backends, because `_infer_los` zeros out the geometry before MODTRAN sees it.
- **CU-005 unblocking.** The `theta_o_from_eta` boundary converter is reserved for the SensorDescriptor follow-on, but its near-term resolution depends on which schema field is canonical for `theta_o`. CU-009 makes the answer visible (`geometry.path_zenith_rad`) so CU-005's re-audit is no longer blocked on a phantom parameter.
- **Rule 17 (no silent failures).** A producer that hardcodes one of three documented angles to zero, ignores two others, and offers no schema seam to override is the silent-defaulting antipattern Rule 17 was written to prevent.

### Affected scenarios (under recommended Approach A)

**Zero existing-baseline drift on landing.** All 14 baseline scenarios in `tests/integration/snapshots/option_c_baseline.yaml` and the per-scenario source-stage snapshots take schema defaults for `geometry.path_zenith_rad`/`solar_zenith_rad`/`solar_azimuth_rad`. None of them set the geometry params explicitly. Bit-invariance survives because:

1. **LWIR T1Thermal cells (Cells 28, 58 + 3 LWIR templates)** — `_assemble_t1` does not consume `theta_s` or `delta_phi`; the `theta_o = 0` default matches the current hardcode exactly.
2. **MWIR cells (6 of 14)** — currently route through `T1Thermal` under the CU-007 suppression wrapper; same argument as the LWIR rows. They will re-baseline only when CU-007 lands and switches them to `T3Mixed` — which is CU-007's regression burden, not CU-009's.
3. **SWIR/VNIR T1Thermal cells (5 of 14)** — same predicate as LWIR (T1Thermal ignores solar geometry).
4. **Anchor cells 28, 58** — explicit verification: both fixtures (`tests/integration/test_option_c_anchors.py:69 ANCHOR_TOLERANCE = 1e-6`) take all geometry defaults; both are LWIR T1Thermal extended; bit-invariant by construction.

**Future scenarios** — any user-authored YAML that sets `geometry.path_zenith_rad`, `geometry.solar_zenith_rad`, or `geometry.solar_azimuth_rad` to a non-default value lands on the new path. Reflective / sky-decomposition scenarios will *finally* see their YAML respected.

---

## Required reading (do not skip)

1. [CLAUDE.md](../CLAUDE.md) — Rules 5 (Kirchhoff derivation; this CU does not change derivation but enables the geometry it consumes), 12 (every parameter has a `ParameterDef` — the latent `geometry.observer_zenith_rad` finding), 16 (validate before compute), 17 (no silent failures — the Kármán/nadir hardcode is the antipattern), 19 (one computation, one module — do *not* split routing into a new module), 20 (doc-and-code lock-step — Source / Atmosphere docs both touch).
2. [docs/RADIANT_Source.md](RADIANT_Source.md) — `_infer_los` contract; matrix §3.2 LOS rules; §4.3 at-aperture pass-through.
3. [docs/architecture/RADIANT_Atmosphere.md](RADIANT_Atmosphere.md) — `LineOfSightGeometry` consumer contract on the AtmosphereStage side; how `theta_s`/`delta_phi` enter `_assemble_t3` / `_assemble_ground_background` / `_diffuse_sky_term` / `_direct_solar_term`.
4. [docs/architecture/RADIANT_Parameter_System.md](RADIANT_Parameter_System.md) — `ParameterDef` rules; the `geometry.*` namespace ownership convention.
5. [src/radiant/core/los_geometry.py](../src/radiant/core/los_geometry.py) — `LineOfSightGeometry` dataclass (`kw_only=True` post-CU-006); validation invariants; the `theta_o ∈ [0, π/2)` half-open guard; `theta_s ∈ [0, π]` and `delta_phi ∈ [−π, π]` ranges.
6. [src/radiant/atmosphere/_schema.py:120–190](../src/radiant/atmosphere/_schema.py#L120) — the four `geometry.*` params (`sensor_altitude_m`, `target_altitude_m`, `path_zenith_rad`, `solar_zenith_rad`, `solar_azimuth_rad`).
7. [src/radiant/source/_inferrer.py:257–331](../src/radiant/source/_inferrer.py#L257) — `_infer_los` and `_view_direction_from_los` (the two functions you will edit).
8. [src/radiant/atmosphere/assembly.py:786–870](../src/radiant/atmosphere/assembly.py#L786) — `_assemble_t3` (verify the consumer accepts non-zero `theta_s`/`delta_phi` correctly; should already, since `_assemble_t1` is the one that ignores them).
9. [docs/reports/cu_tasks/CU-007_MWIR_T3Mixed_Routing_Task.md](CU-007_MWIR_T3Mixed_Routing_Task.md) and [docs/reports/cu_tasks/CU-008_GroundBackground_Spectral_Task.md](CU-008_GroundBackground_Spectral_Task.md) — pattern this task follows (multi-approach decision, stop triggers, Category-B-with-C-radiometric-audit validation, ordering relative to other escalated CUs).
10. [docs/architecture/RADIANT_Testing_Validation.md](RADIANT_Testing_Validation.md) §5.3 — golden-snapshot review protocol (this CU should not refresh any snapshot; if one moves, stop and investigate).

---

## Approach decision (recorded — Approach A confirmed 2026-04-26)

The schema design space is **not** "where to register four new params." The `geometry.*` parameters that map to `LineOfSightGeometry`'s fields are already registered on `atmosphere/_schema.py` and consumed by multiple downstream stages. The real question is "which of three routes does the producer side take?"

### Approach A — Wire existing `geometry.*` params into `_infer_los` (recommended; confirmed by Jason 2026-04-26)

`_infer_los` reads `geometry.path_zenith_rad`, `geometry.solar_zenith_rad`, `geometry.solar_azimuth_rad` from the same `ParameterSet` it already accepts. Routing rule:

- `theta_o = params.get("geometry.path_zenith_rad")` (always; default 0.0).
- `theta_s` and `delta_phi`: pass the param values when the *target descriptor type* implies solar interaction (T2Reflective, T3Mixed); pass `None` when it doesn't (T1Thermal — pure-thermal, sun is irrelevant). The "T1 ⇒ None, T2/T3 ⇒ populated" predicate matches `LineOfSightGeometry`'s docstring intent ("`None` for pure-thermal scenarios where the sun is not used") and avoids invalidating Cells 28/58 (LWIR T1Thermal — bit-invariant under any default choice that keeps `theta_o = 0`).
- `h_atm_top` stays at the dataclass default of `1.0e5` m. A proper Kármán-line override is Stage-7+ / SensorDescriptor territory and not in scope here.

**Wrinkle:** `_infer_los` is called *before* the target descriptor is built (line 1801, where the descriptor is built immediately after at line 1817). The "T1 vs T2/T3" predicate at the LOS site cannot read `target_descriptor.__class__` because the descriptor doesn't exist yet. Two ways to resolve this:

- **A.1 (preferred).** Re-order: build `target_descriptor` first, then call `_infer_los(target_location, params, target_descriptor=target_descriptor)`. The LOS function reads `target_descriptor.__class__.__name__` (or an `isinstance` check) to decide whether to populate `theta_s`/`delta_phi`. Adds one parameter to `_infer_los`'s signature; minimal blast radius.
- **A.2.** Always populate `theta_s`/`delta_phi` regardless of target type. T1Thermal's assembly ignores them by construction (`_assemble_t1` does not reference them); the values become inert metadata for T1 cells. Smaller diff, but the `LineOfSightGeometry` docstring's "`None` for pure-thermal" semantic intent is lost — the field becomes unused-but-not-None for T1 cells.

**Recommendation: A.1.** Preserves the documented `None`-means-no-solar contract; explicit predicate at the routing site; one extra arg through one function call.

**Pros (Approach A overall).**
- Zero new schema parameters. No namespace duplication.
- Leverages already-tested cross-stage parameter infrastructure (Rule 12 already satisfied).
- Bit-invariance for all 14 baseline scenarios and both anchor cells (defaults match the current hardcode exactly).
- Cleans up the `_view_direction_from_los` unregistered-`geometry.observer_zenith_rad` reader in the same surgery (it becomes a read of the canonical `geometry.path_zenith_rad`).
- Sets up CU-007 to land cleanly afterward — when MWIR rows switch to T3Mixed, the correct `theta_s` is already plumbed; the CU-007 snapshot refresh captures the new physics on the first cut, no double-shift.
- Unblocks CU-005 (the boundary-converter follow-on now has a canonical `theta_o` schema field to convert *into*) and CU-011 (the MODTRAN single-τ alias has an exercise path the moment a YAML sets non-zero `theta_s`).

**Cons.**
- The "T1 ⇒ None, T2/T3 ⇒ populated" predicate is a small new piece of routing logic in `_inferrer.py`. Documented in the function docstring, covered by Level-0 tests, but new.
- Re-orders the descriptor/LOS construction in the inferrer's main entry point (lines ~1800–1820). Mechanical but worth a careful review.

### Approach B — Register `source.observer_geometry.*` namespace (the CU-009 entry's literal suggestion)

Add `source.observer_geometry.theta_o`, `source.observer_geometry.theta_s`, `source.observer_geometry.delta_phi`, `source.observer_geometry.h_atm_top` as new `ParameterDef`s on the `SourceStage` schema. Inferrer reads from the new namespace.

**Pros.** SourceStage owns its own input contract (matches the per-stage schema convention).

**Cons.**
- Two registered names for the same physical quantity (`source.observer_geometry.theta_o` vs `geometry.path_zenith_rad`). Which is canonical when they disagree? The schema-resolver has no rule.
- Either silently shadows the existing `geometry.*` params, or requires a precedence rule, or requires alias plumbing. All three are anti-patterns relative to "one parameter, one name."
- Downstream consumers (platform smear, performance GSD, MODTRAN) read from `geometry.*`. Forcing the source side to use a different name introduces a divergence that the next reader will trip over.
- **Reject.**

### Approach C — Add `geometry.sensor_off_nadir_rad`; convert `theta_o` via `theta_o_from_eta`

Add a single new parameter `geometry.sensor_off_nadir_rad`; inferrer computes `theta_o = theta_o_from_eta(eta, h_sensor, h_tgt)` using the boundary converter at [los_geometry.py:386](../src/radiant/core/los_geometry.py#L386). This wires CU-005 in the same stroke.

**Pros.**
- Resolves CU-005 simultaneously.
- Captures the sensor-pointing semantics that LEO operators actually use (off-nadir, not target-zenith).

**Cons.**
- Bigger scope; couples two CUs that the backlog has already separated for good reason.
- CU-005's status text already records "deferred to post-CU-009 re-audit" — landing them together short-circuits the re-audit step.
- If both `geometry.path_zenith_rad` and `geometry.sensor_off_nadir_rad` exist, you need a precedence rule for which wins. That's a Rule-17 / Rule-19 swamp.
- **Reject for this CU.** Deferred to CU-005's post-CU-009 re-audit, which will decide whether to introduce `sensor_off_nadir_rad` or document the deferral behind the SensorDescriptor ADR.

**Confirmed: Approach A (with sub-variant A.1).** Approach B is rejected as namespace duplication; Approach C is rejected as scope creep that pre-empts CU-005's deferred decision.

---

## Implementation steps (after approach decision)

1. **Branch.** `git switch -c chore/cu-009-observer-geometry`.
2. **Tests first (Level 0).** New file `src/radiant/source/tests/test_inferrer_los_routing.py`:
   - **A1.** `_infer_los` with `target_location="terrestrial"`, default params: returns `LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=None, delta_phi=None, h_atm_top=1e5)`. Asserts the "no solar interaction by default" baseline (T1Thermal target).
   - **A2.** Set `geometry.path_zenith_rad=0.4` (~22.9°). Build a T1Thermal target. Assert `los.theta_o == 0.4`, `los.theta_s is None`, `los.delta_phi is None`. Documents that T1 still gets `None` for solar fields even when the params are non-default.
   - **A3.** Build a T3Mixed target (MWIR ambient, ε=0.95, T=290K, with non-zero reflectance) with `geometry.path_zenith_rad=0.3`, `geometry.solar_zenith_rad=0.6`, `geometry.solar_azimuth_rad=0.5`. Assert `los.theta_o == 0.3`, `los.theta_s == 0.6`, `los.delta_phi == 0.5`. Documents the "T3 ⇒ populated" path.
   - **A4.** Build a T2Reflective target with the same non-default params. Same assertions as A3 (T2 also implies solar interaction).
   - **A5.** `target_location="at_aperture"` with all non-default geometry params: `_infer_los` returns `None`. Documents the at-aperture pass-through.
   - **A6.** `target_location="no_atmosphere"` with all non-default geometry params: `_infer_los` returns a `LineOfSightGeometry` whose `theta_s/delta_phi` follow the same T1/T2/T3 rule as terrestrial (no_atmosphere doesn't change the routing predicate). Verify `h_tgt` stays 0 per matrix §7.
   - **A7.** Negative `geometry.path_zenith_rad`: `LineOfSightGeometry.__post_init__` raises `ParameterBoundsError` with the half-open `[0, π/2)` message. Verifies that out-of-range values surface loudly rather than being clamped.
   - **A8.** `geometry.path_zenith_rad = π/2 − 1e-12` (just below the horizon): construction succeeds; `path_airmass_up` is finite. Documents the half-open-interval guard works at the limit.
   - **A9.** `_view_direction_from_los` reads `geometry.path_zenith_rad` (the canonical name) instead of `geometry.observer_zenith_rad`. With `geometry.path_zenith_rad=0.5`, view_dir is `(sin(0.5), 0, cos(0.5))`. Verifies the latent-finding fix.
3. **Run the new tests.** A1, A5, A8, A9 should pass on the current (pre-fix) code. A2, A3, A4, A6, A7 should fail (the params are read but `_infer_los` ignores them).
4. **Production change — `_infer_los`** ([src/radiant/source/_inferrer.py:257](../src/radiant/source/_inferrer.py#L257)).
   - Add a `target_descriptor: TargetDescriptor | None = None` argument.
   - Read `theta_o = float(params.get("geometry.path_zenith_rad"))` with the existing `KeyError → 0.0` fallback (matches the source-only unit-test pattern at line 287).
   - If `target_descriptor is None` (legacy callers / source-only fixtures): pass `theta_s=None, delta_phi=None` (back-compat with current behavior).
   - Otherwise inspect `isinstance(target_descriptor, (T2Reflective, T3Mixed))`:
     - If true: read `theta_s = float(params.get("geometry.solar_zenith_rad"))` and `delta_phi = float(params.get("geometry.solar_azimuth_rad"))`.
     - Else: `theta_s = None, delta_phi = None`.
   - Construct `LineOfSightGeometry(h_tgt=h_tgt_m, theta_o=theta_o, theta_s=theta_s, delta_phi=delta_phi)`. `h_atm_top` stays at the dataclass default; no override surface in this CU.
   - Update the docstring (lines 257–283) to describe the new behavior; remove the "θ_o = 0 rad (nadir)" claim and replace with "θ_o = `geometry.path_zenith_rad` (default 0.0 rad)."
5. **Production change — `_infer_los` caller** ([src/radiant/source/_inferrer.py:1800–1820](../src/radiant/source/_inferrer.py#L1800)).
   - Re-order: build `target_descriptor` first, then call `_infer_los(target_location, params, target_descriptor=target_descriptor)`.
   - The current ordering (LOS first, target second) is mechanical — verify no other code path between these two construction sites relies on `los` existing before `target` is built (grep for both within the function body).
6. **Production change — `_view_direction_from_los`** ([src/radiant/source/_inferrer.py:295–331](../src/radiant/source/_inferrer.py#L295)).
   - Change line 323 from `params.get("geometry.observer_zenith_rad")` to `params.get("geometry.path_zenith_rad")`.
   - Keep the `try/except KeyError → 0.0` fallback (still wanted for source-only unit-test fixtures that don't register the AtmosphereStage schema).
   - Update the docstring's "the observer zenith angle ``theta_o`` is the only LOS scalar surfaced today" line to reference the canonical parameter.
7. **Latent-finding cleanup.** Search the test suite for any reference to `geometry.observer_zenith_rad`. If a fixture sets it (vs reads it), update the fixture to set `geometry.path_zenith_rad` instead. If no fixture sets it, the unregistered name disappears entirely. Document the cleanup in the commit body.
8. **Run the new tests.** All nine should now pass.
9. **Full regression gate.**
   ```
   pytest src/ -q                       # +9 new tests; existing source-stage tests unchanged
   pytest tests/integration/ -q         # zero baseline drift expected
   mypy --strict src/radiant/core src/radiant/api
   ruff check src/
   ruff format --check src/
   lint-imports --config pyproject.toml
   ```
   - **Expected:** 14 baseline rows in `tests/integration/snapshots/option_c_baseline.yaml` bit-invariant (`numpy.array_equal` on `L_aperture`; metric scalars unchanged to floating-point identity).
   - **Expected:** Anchor cells 28/58 (`tests/integration/test_option_c_anchors.py:69 ANCHOR_TOLERANCE`) bit-invariant (`rel ≤ 1e-6` of pinned values; numerically should be exact).
   - **Expected:** All per-scenario source-stage snapshot YAMLs under `src/radiant/source/tests/snapshots/` bit-invariant.
   - **Expected:** `mtf_at_nyquist` unchanged on every row (no spatial-frequency coupling).
10. **Doc updates (Rule 20).**
    - [docs/RADIANT_Source.md](RADIANT_Source.md) — `_infer_los` contract section: drop "θ_o = 0 rad (nadir)" from the defaults list; replace with "`theta_o` ← `geometry.path_zenith_rad`; `theta_s`, `delta_phi` ← `geometry.solar_zenith_rad`, `geometry.solar_azimuth_rad` for T2/T3 targets, `None` for T1." Note the latent-finding cleanup (`_view_direction_from_los` now reads from the canonical name).
    - [docs/architecture/RADIANT_Atmosphere.md](RADIANT_Atmosphere.md) — `LineOfSightGeometry` consumer-side section: clarify that the producer side now respects `geometry.solar_zenith_rad` / `geometry.solar_azimuth_rad` for T2/T3 targets. (No new params to document.)
    - [docs/architecture/RADIANT_Parameter_System.md](RADIANT_Parameter_System.md) — append a one-line note in the `geometry.*` section: "Consumed by AtmosphereStage, PlatformStage, PerformanceStage, and (post-CU-009) by SourceStage's `_infer_los` for `LineOfSightGeometry` construction." No new parameter rows to add.
11. **Move CU-009 to Resolved** in `docs/tracking/Cleanup_Backlog.md` with the commit hash and a one-line note: "wired `_infer_los` to `geometry.path_zenith_rad` / `geometry.solar_zenith_rad` / `geometry.solar_azimuth_rad`; latent unregistered `geometry.observer_zenith_rad` reader cleaned up; zero baseline drift; unblocks CU-005 / CU-011 follow-ons." (Rule 22 — phantom closure forbidden.)
12. **Commit.** Format: `chore(debt): CU-009 — wire _infer_los to existing geometry.* params; remove nadir/Kármán hardcode`. Body cites the three params now read, confirms anchor cells 28/58 and all 14 baseline rows bit-invariant, calls out the CU-007 ordering benefit ("MWIR T3Mixed routing now lands on correct geometry on first cut"), and confirms the `geometry.observer_zenith_rad` latent finding is closed in the same diff.

---

## Stop triggers

Stop and ask the user before continuing if any of these fire:

- **Anchor cell 28 or 58 (`CELL28_PINNED`, `CELL58_PINNED` at [tests/integration/test_option_c_anchors.py:69](../tests/integration/test_option_c_anchors.py#L69)) shifts at all.** Both are LWIR T1Thermal extended; their fixtures take all geometry defaults; `_assemble_t1` ignores `theta_s/delta_phi`. Any drift means either (a) the routing predicate is misclassifying the target descriptor, (b) `_assemble_t1` somewhere reads the solar fields, or (c) the new schema reads have a unit/range bug. Investigate before regenerating any snapshot.
- **Any of the 14 rows in `option_c_baseline.yaml` shifts** (numpy `==` mismatch on `L_aperture`, or metric drift on `snr`/`nedt_K`/`mtf_at_nyquist`). All 14 take schema defaults; under Approach A their values must be identical bit-for-bit. A shift indicates either the routing predicate or a hidden default was changed.
- **`mtf_at_nyquist` shifts on any row.** This CU is purely radiometric/geometric — no spatial-frequency coupling. Any drift is a sign of accidental scope crossing.
- **A test in `src/radiant/source/tests/test_inferrer.py` or `src/radiant/atmosphere/tests/` fails for a reason other than "the inferrer now reads three additional params."** Investigate — most likely the descriptor-construction reorder broke a fixture's expected call sequence.
- **You find yourself adding a new `ParameterDef` to any `_schema.py`.** Approach A explicitly registers zero new params. Approach B was rejected for namespace duplication; resurrecting it requires re-discussion.
- **You find yourself editing `radiant.atmosphere.assembly` or `radiant.core.los_geometry`.** This is a producer-side fix in `_inferrer.py`. The consumer side (`_assemble_t1`/`_assemble_t3`/`_assemble_ground_background`) and the dataclass itself should be unchanged. If you find yourself in those files, you have crossed scope.
- **The descriptor-construction reorder (step 5) requires touching anything beyond the ~20-line region around `_infer_los`'s call site.** If the reorder cascades, stop and ask — the function may have implicit ordering dependencies the audit missed.
- **You discover a third caller of `_infer_los` outside [_inferrer.py:1801](../src/radiant/source/_inferrer.py#L1801).** Today there's exactly one. A second caller would mean the back-compat `target_descriptor=None` path matters — verify before changing the signature.
- **The latent `geometry.observer_zenith_rad` cleanup turns up a fixture that *sets* the unregistered name (vs reads it).** That's a separate bug the audit didn't catch; pause and decide whether to fold it in or file as a new CU.

---

## Validation requirements (Category B with C-level radiometric audit on future-scenario coverage)

### Numerical truth anchors (≥3 required)

1. **Bit-invariance of LWIR T1Thermal hardcode → schema-default path.** For Cell 28 and Cell 58 (both LWIR T1Thermal extended, both take all geometry defaults), confirm `numpy.array_equal(L_aperture_pre, L_aperture_post)` and `metrics_pre == metrics_post` to floating-point identity. The pre-fix `LineOfSightGeometry(h_tgt, theta_o=0.0)` and the post-fix `LineOfSightGeometry(h_tgt, theta_o=0.0, theta_s=None, delta_phi=None)` (T1 routing path) construct dataclasses that are `==`-equal; downstream radiometry must be identical.
2. **Schema-default propagation for T3 routing.** For a synthetic MWIR T3Mixed scenario with no geometry params set in YAML (so `theta_o = 0.0`, `theta_s = 0.5`, `delta_phi = 0.0` from schema defaults), compute `_assemble_t3`'s `L_aperture` at one wavelength bin (e.g. λ = 4.0 µm, T_t = 290 K, ε = 0.95, ρ = 0.05) by hand using the matrix §6.1 closed form: `L = ε·B(λ,T)·τ_up + L_path_up + ρ·(τ_sun·E_sun·cos(0.5) + E_sky_diffuse)·τ_up`. Confirm the post-fix value matches the hand calculation to **rel ≤ 1e-6**.
3. **Non-default geometry round-trip.** Same synthetic MWIR T3Mixed scenario, but set `geometry.path_zenith_rad=0.3`, `geometry.solar_zenith_rad=0.7`, `geometry.solar_azimuth_rad=0.4` in the YAML. Confirm `los.theta_o == 0.3`, `los.theta_s == 0.7`, `los.delta_phi == 0.4` (schema reads work). Confirm `_assemble_t3`'s output now uses `cos(0.7)` instead of `cos(0.5)` for the direct-solar term (the `(cos(0.7)/cos(0.5))` ratio in `L_aperture` is the audit signal). Hand-compute the expected delta and confirm to **rel ≤ 1e-6**.

### Dimensional audit

| Stage                                        | Input units                  | Output units             | Conversion             | Check |
|----------------------------------------------|------------------------------|--------------------------|------------------------|-------|
| `geometry.path_zenith_rad` (param)           | rad                          | rad                      | none                   | ✓     |
| `geometry.solar_zenith_rad` (param)          | rad                          | rad                      | none                   | ✓     |
| `geometry.solar_azimuth_rad` (param)         | rad                          | rad                      | none                   | ✓     |
| `geometry.target_altitude_m` (param)         | m                            | m                        | none                   | ✓     |
| `LineOfSightGeometry.theta_o`                | rad                          | rad                      | passthrough            | ✓     |
| `LineOfSightGeometry.theta_s`                | rad                          | rad                      | passthrough            | ✓     |
| `LineOfSightGeometry.delta_phi`              | rad                          | rad                      | passthrough            | ✓     |
| `LineOfSightGeometry.slant_range_atm`        | (m, rad) → m                 | m                        | spherical Earth        | ✓     |
| `LineOfSightGeometry.path_airmass_up`        | (m, rad) → dimensionless     | dimensionless            | divide                 | ✓     |
| `_assemble_t3` solar-leg cos(theta_s)        | rad                          | dimensionless            | math.cos               | ✓     |
| `_view_direction_from_los` (sin/cos theta_o) | rad                          | dimensionless            | math.{sin,cos}         | ✓     |

The radiometric W/m²/sr/µm dimensional path through `_assemble_t1` / `_assemble_t3` is unchanged by this CU; it was audited at Stage 6.

### Failure modes

- **`geometry.path_zenith_rad = -0.1` (negative).** `LineOfSightGeometry.__post_init__` should raise `ParameterBoundsError` with the half-open `[0, π/2)` message. Verify the exception surfaces (no silent clamp).
- **`geometry.path_zenith_rad = π/2` (exactly horizon).** Should raise (half-open interval excludes the endpoint where `path_airmass_up` diverges). Verify.
- **`geometry.path_zenith_rad = π/2 − 1e-12` (just below).** Should construct; `path_airmass_up` should be finite (large but not `inf`). Verify.
- **`geometry.solar_zenith_rad = π + 0.1` (out of range).** `LineOfSightGeometry.__post_init__` should raise `ParameterBoundsError` with the `[0, π]` message. Verify.
- **`geometry.solar_azimuth_rad = 4·π` (out of range).** Should raise (the field's bounds are `[−2π, 2π]` per the schema, but `LineOfSightGeometry` requires `[−π, π]`). The boundary case is at the param-level: the schema accepts `4π`, the descriptor rejects it. Verify the rejection message points the user at `delta_phi`'s tighter range.
- **MWIR scenario with T1Thermal target and `geometry.solar_zenith_rad=0.7`.** Routing predicate returns T1 ⇒ `theta_s = None`. The non-default param is silently *unused* for T1 cells. Document explicitly in the docstring; verify in test A2 that the param value does not propagate.
- **Source-only unit test that registers SourceStage's schema but not AtmosphereStage's.** `params.get("geometry.path_zenith_rad")` raises `KeyError`; the inferrer's `try/except KeyError → 0.0` fallback fires. Verify the source-only test flow still works (this is the source-fixture back-compat path; do not remove the `KeyError` fallback).
- **`target_descriptor=None` (legacy caller of `_infer_los`).** Routing predicate falls through to the `theta_s=None, delta_phi=None` branch. Verify A1's assertions cover this.

### Assumptions

- **`LineOfSightGeometry`'s "`None` for pure-thermal" semantic is the right contract.** The dataclass docstring explicitly says `theta_s: ... or None for pure-thermal scenarios where the sun is not used`. The routing predicate honors that intent. If a future descriptor type wants solar-aware-but-without-`theta_s`, the predicate has to be revisited.
- **The descriptor-type predicate is the right discriminator.** `isinstance(target_descriptor, (T2Reflective, T3Mixed))` covers all current solar-interacting descriptor types. New descriptor types (e.g. `T4` follow-on if introduced) must be added to the predicate or the routing decision becomes wrong silently. Document in the docstring; covered by A3 and A4 tests.
- **The `geometry.*` schema defaults are appropriate.** `path_zenith_rad=0.0`, `solar_zenith_rad=0.5` (~28.6°), `solar_azimuth_rad=0.0`. These have been the Atmosphere/Performance/Platform consumer defaults for several stages; this CU does not change them. If a scenario wants different defaults it sets them explicitly.
- **Cells 28/58 stay bit-invariant.** Both LWIR T1Thermal extended; routing predicate puts them on the `theta_s=None` branch which matches the pre-fix behavior. Verified at task-design time, must be re-verified at landing.
- **No baseline scenario sets `geometry.path_zenith_rad`/`solar_zenith_rad`/`solar_azimuth_rad`.** Verified by `grep -rE "geometry\.(path_zenith_rad|solar_zenith_rad|solar_azimuth_rad)" examples/` — zero hits across all 14 baseline YAMLs. Re-verify before final commit.

### Fragility analysis

- **Descriptor reorder fragility.** Step 5 re-orders the inferrer's main entry point so that `target_descriptor` is built before `_infer_los` is called. If the function body has hidden ordering dependencies (e.g. another helper expects `los` to exist before `target`), the reorder breaks them. Mitigation: grep for usages of `los`/`target` between lines 1800 and 1820 before reordering; run the full source-stage test suite immediately after the reorder.
- **Source-only fixture fragility.** Source-stage unit tests construct minimal `ParameterSet`s that do not register AtmosphereStage's schema. The `KeyError → 0.0` fallback in `_infer_los` is what keeps them working. Removing it would break ~20 fixture files. Mitigation: keep the fallback, add an A1-style test that documents the fallback semantics, cross-reference the AtmosphereStage schema dependency in `_infer_los`'s docstring.
- **CU-007 ordering fragility.** If CU-007 lands BEFORE CU-009, the six MWIR rows shift twice (T3-with-zero-θ_s when CU-007 lands; T3-with-correct-θ_s when CU-009 lands). Mitigation: land CU-009 first; CU-007's task doc has been written assuming `theta_s` is wired (it cites CU-009 as a deferred concern). Document the ordering in the commit body.
- **`geometry.observer_zenith_rad` removal fragility.** If a fixture or test sets the unregistered name explicitly (vs reads it), the latent-finding cleanup breaks the test silently — the param-set still accepts the assignment because there's no schema entry to reject it. Mitigation: grep for `geometry.observer_zenith_rad` after the cleanup; if any test sets it, the test was already broken (writing to an unregistered name is a no-op everywhere except `_view_direction_from_los`'s read site, which now reads from a different name).

### Cross-model consistency

- The `LineOfSightGeometry` produced by `_infer_los` for a given scenario must be `==`-equal to one constructed directly from the same params. This is a property of the dataclass, not the inferrer; verifiable by a Level-0 test that reads the params, calls `_infer_los`, and compares to a hand-built `LineOfSightGeometry(...)`.
- `_assemble_t3`'s output for a scenario built via the inferrer must equal `_assemble_t3`'s output for the same scenario built by direct dataclass construction (proves the inferrer is purely a routing layer, not introducing radiometric side-effects). Cover in Anchor #3.
- The view direction returned by `_view_direction_from_los` for `geometry.path_zenith_rad=θ` must equal `(sin θ, 0, cos θ)` exactly (cover in A9).

### Traceability

- Same inputs → identical outputs: yes. The routing is purely deterministic on the `ParameterSet` and the target-descriptor type. No RNG.
- Deterministic seed: N/A.
- Intermediate values inspectable: yes — `LineOfSightGeometry` is exposed on `ChainState.stage_outputs["source"]["los"]`; tests can assert on `los.theta_o`, `los.theta_s`, `los.delta_phi` directly.

---

## Out of scope (do not touch)

- **`LineOfSightGeometry`** ([core/los_geometry.py](../src/radiant/core/los_geometry.py)). The dataclass is the contract; this CU is a producer-side wiring fix. The dataclass's validation, derived properties (`slant_range_atm`, `path_airmass_up`, `intercepts_earth`), and serialisers (`to_dict` / `from_dict`) are unchanged.
- **`theta_o_from_eta`** ([core/los_geometry.py:386](../src/radiant/core/los_geometry.py#L386)). The boundary converter for sensor-side η → target-side θ_o is reserved for CU-005's post-CU-009 re-audit. Do not wire it in this CU.
- **`_assemble_t1` / `_assemble_t2` / `_assemble_t3`** ([atmosphere/assembly.py](../src/radiant/atmosphere/assembly.py)). Consumer-side; unchanged. T3's `theta_s` consumption was wired at Stage 6.
- **`_assemble_ground_background`** ([atmosphere/assembly.py:1112](../src/radiant/atmosphere/assembly.py#L1112)). Consumer-side; unchanged.
- **MODTRAN backend's `tau_sun = tau` alias** ([atmosphere/modtran.py:730–752](../src/radiant/atmosphere/modtran.py#L730)). That's CU-011, blocked on CU-009 — it now becomes unblocked but is its own task.
- **`source.target.is_hot_target` parameter and MWIR T3 routing.** That's CU-007, escalated separately. The two CUs are independent; CU-009 lands first to give CU-007's snapshot refresh the correct geometry on the first cut.
- **`source.background.material` parameter and spectral ε_g(λ).** That's CU-008, escalated separately.
- **Adding new sub-pixel reflective scenarios to the baseline.** This CU does not author scenarios. If a future user-authored scenario exercises the new geometry path, that scenario's snapshot is the new test fixture; this CU should not pre-author it.
- **`h_atm_top` schema parameter.** Stays at the dataclass default `1.0e5` m. A user-overridable Kármán-line value is Stage-7 / SensorDescriptor territory.
- **Adding `geometry.sensor_off_nadir_rad`.** That's Approach C, rejected. CU-005's re-audit will decide whether to introduce it.
- **The unrelated `dev_tools/geometry_gui/` modifications in the working tree.** Jason's parallel in-progress work; explicitly off-limits per task brief.

---

## Completion criteria

- [ ] CU-009 entry in [docs/tracking/Cleanup_Backlog.md](Cleanup_Backlog.md) moved to Resolved with this task's commit hash, a one-line summary citing the three params now read by `_infer_los`, the latent-finding cleanup of `geometry.observer_zenith_rad`, and the zero-baseline-drift confirmation (Rule 22).
- [ ] New `src/radiant/source/tests/test_inferrer_los_routing.py` covers the nine Level 0 anchors (A1–A9) plus the failure-mode cases above.
- [ ] `_view_direction_from_los` no longer reads `geometry.observer_zenith_rad`; the unregistered name appears nowhere in `src/radiant/`.
- [ ] `pytest src/`, `pytest tests/integration/`, `mypy --strict`, `ruff check`, `ruff format --check`, `lint-imports` all green.
- [ ] All 14 baseline rows in `option_c_baseline.yaml` bit-invariant; all per-scenario source-stage snapshots bit-invariant; anchor cells 28/58 bit-invariant.
- [ ] `docs/RADIANT_Source.md`, `docs/architecture/RADIANT_Atmosphere.md`, and `docs/architecture/RADIANT_Parameter_System.md` updated per Rule 20.
- [ ] CU-005's "blocked on CU-009" status refreshed to "ready for re-audit" in the same commit (the `theta_o`-canonical-name question is now answered).
- [ ] CU-011's "blocked on CU-009" status refreshed to "exercise path now possible" in the same commit (a YAML can now plumb non-zero `theta_s` through to MODTRAN).
- [ ] Structured Category-B-with-C-radiometric-audit report attached to the commit body or PR description: Numerical Truth Anchors (≥3), Dimensional Audit, Failure Modes, Assumptions, Fragility, Traceability, Cross-Model Consistency, Integration & Regression — with explicit confirmation that no baseline scenario shifted and that the descriptor-reorder did not cascade beyond the ~20-line region around `_infer_los`'s call site.
