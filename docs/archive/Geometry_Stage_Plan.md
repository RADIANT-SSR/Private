> **HISTORICAL — archived 2026-07-12 (completed by the coding agent; all four phases landed same-day).** Phase 0 design record (`4890a10`: ADR-0006, CU-093/094/095 filed, Gaps 83/84); Phase 1 GeometryStage (`664fd08`, zero drift); Phase 2 downstream consumption (`65720f0`, CU-096 narrowed, goldens intact); Phase 3 collapses (`f44c37a` + closures `17a3598`: CU-090, CU-093, CU-005 addendum); Phase 4 dead-code deletion + closeout (`967f900`, CU-094). Along the way: CU-096/097/098/099 filed (Rule 21). Completion definition verified — geometry-first 9-stage chain, all v1 input modes Level-0 tested, deferred modes gap-filed, docs lock-step, zero golden drift.

# Geometry Stage Plan — Geometry as Stage 0 of the Chain

**Status:** Complete (2026-07-12) — archived
**Owner decision record:** ADR-0006 (created by Phase 0 of this plan)
**CUs referenced:** CU-090 (open), CU-093, CU-094 (filed by Phase 0)
**Driver:** GUI mockup review (2026-07-12) exposed that scene geometry — where the sensor,
target, and sun are — is consumed by nearly every stage but owned by none. The chain and
the GUI must both open with geometry definition.

---

## 1. Problem Statement (verified against code, 2026-07-12)

Scene geometry currently lives in five places with no owner:

| Location | Contents | Consumers |
|---|---|---|
| `atmosphere/_schema.py:118-213` | the entire `geometry.*` namespace (7 ParameterDefs) | atmosphere, platform, performance, source `_inferrer`, MODTRAN |
| `source/_schema.py:93` | `source.target.range_m` (slant range), `projected_area_m2` | regime classification, detection range |
| `platform/_schema.py:128` | `platform.h_sensor` — duplicate of `geometry.sensor_altitude_m` (CU-090) | atmosphere no-atmosphere subcase, 32 test/scenario files |
| `core/geometry.py:258-367` | `ObserverGeometry` / `TargetGeometry` / `SceneGeometry` dataclasses | **none** (zero consumers; flat-Earth model; unused attitude fields) |
| `core/los_geometry.py` | `LineOfSightGeometry` — the real runtime contract | built by source `_inferrer`, consumed by AtmosphereStage |

Concrete defects:

1. **CU-090** — two independent parameters name sensor altitude; no consistency link.
2. **CU-093 (new)** — `source.target.range_m` (drives regime classification and detection
   range, `performance/stage.py:357`) and `slant_range_spherical_m(altitude, zenith)`
   (drives GIQE ground metrics, `performance/stage.py:547`) can silently disagree.
3. **CU-094 (new)** — the three core geometry dataclasses are dead code (Rule 27).
4. SourceStage reaches forward into `detector.*`/`optics.*` for IFOV
   (`source/stage.py:111-112`) because range/geometry has no upstream home —
   the parameter dependency graph contradicts the documented linear chain.
5. Three geometry input paths are half-built with no front door:
   `theta_o_from_eta` (deliberately unwired, CU-005), `core/solar_geometry.py`
   (tested, **zero runtime consumers**), `core/orbit.py` (wired only through the
   opt-in `Sensor.set_ground_velocity_from_orbit()` helper).

## 2. Target Architecture

New chain order (9 stages):

```
geometry → source → atmosphere → optics → platform
        → spectral_integration → detector → readout → performance
```

**`GeometryStage`** (new, `src/radiant/geometry/`) is a pure Stage (Rule 6) that emits
no radiometric frames — only validated, derived stage outputs (precedent: SourceStage
publishes descriptors and LOS today):

- **Owns** the `geometry.*` parameter namespace (moved out of `atmosphere/_schema.py`,
  names unchanged) plus the renamed `geometry.target_range_m`
  (alias: `source.target.range_m`) and absorbed `geometry.sensor_altitude_m`
  (alias: `platform.h_sensor`).
- **Resolves one input mode** (§3) into the canonical internal representation.
- **Validates once**: bounds, under-specification (no complete mode), over-specification
  (two modes, or one mode plus a redundant value that disagrees) → actionable error
  (Rule 15/16).
- **Derives once** and publishes `stage_outputs["geometry"]`:
  `los_geometry` (`LineOfSightGeometry`), `slant_range_m`, `ground_range_m`,
  `incidence_angle_rad`, solar geometry echo (θ_s, Δφ, illumination mode),
  `input_mode` (which mode resolved — for `result.inspect()` and the GUI).
- Downstream stages consume published values; no stage re-derives slant range.

**Formula standard:** spherical Earth (`slant_range_spherical_m`,
`incidence_angle_rad` from `core/geometry.py`) — already what platform and
performance use. The flat-Earth `SceneGeometry` model is deleted (owner decision,
2026-07-12).

**Owner decisions (2026-07-12, recorded in ADR-0006):**
1. Rename into `geometry.*` with `deprecated_aliases` (machinery exists,
   `core/parameters.py:121,304-316`) — old names warn and redirect.
2. Delete `ObserverGeometry`/`TargetGeometry`/`SceneGeometry`; keep the module's live
   functions (`slant_range_spherical_m`, `incidence_angle_rad`, Euler helpers).
3. Execution: per-phase commits on main, full suite green before each.

This supersedes the `SensorDescriptor` stub (Use_Case_Matrix §4.4) — sensor altitude
lives in `geometry.*`, not a separate descriptor.

## 3. Geometry Input Modes — every way to define the scene, simple → complex

The canonical internal representation every mode resolves to:
`{h_sensor, h_target, θ_o (target-side path zenith), slant_range, θ_s, Δφ_solar,
solar_illumination, v_ground}` — all SI, all radians (Rule 2). A mode is a
*minimal complete specification*; everything else is derived with
`Provenance.DERIVED`. Setting values from two modes that disagree is
over-specification and raises; setting no complete mode falls back to documented
defaults (nadir, extended-scene).

### Viewing geometry (sensor ↔ target)

| # | Mode | User supplies | Derivation | Machinery today | Disposition |
|---|------|---------------|------------|-----------------|-------------|
| V0 | **Direct range** | slant range only | θ_o defaults nadir; altitudes unset → no-atmosphere/lab semantics | `source.target.range_m` (works today) | **v1** (Phase 1) |
| V1 | **Altitude + path zenith** | h_sensor, θ_o (target-side), [h_target] | range, ground range, incidence via spherical Earth | canonical today (`geometry.sensor_altitude_m` + `path_zenith_rad`) | **v1** (Phase 1) — the reference mode |
| V2 | **Altitude + off-nadir look angle η** | h_sensor, η (sensor-side) | θ_o via corrected sine rule, then as V1 | `theta_o_from_eta` exists, tested, deliberately unwired (CU-005 deferral) | **v1** (Phase 1) — this plan is the "SensorDescriptor follow-on" CU-005 named; wiring it closes that deferral |
| V3 | **Altitude + ground range** | h_sensor, ground distance to target | θ_o from spherical triangle, then as V1 | ground-range forward calc exists (`performance/ground_range.py`); inverse needed | **v1** (Phase 1) — small inverse function, Level 0 tested |
| V4 | **Altitude + elevation/grazing angle** | h_sensor, target-side elevation angle | θ_o = π/2 − elevation, then as V1 | trivial complement | **v1** (Phase 1) — converter at boundary |
| V5 | **Two geodetic points** | sensor lat/lon/alt + target lat/lon/alt | great-circle ground range → V3 path; also gives Δφ geometry for solar | none (new spherical-Earth two-point solver) | **follow-on** — gaps.md entry; schema reserves names |
| V6 | **Circular orbit** | orbital altitude, [η or θ_o] | h_sensor = h_orbit; v_ground from `core/orbit.py`; then V1/V2 | `core/orbit.py` complete + tested; wired only via opt-in API helper | **v1** (Phase 1) — mode wraps existing functions; retires the manual `set_ground_velocity_from_orbit()` footgun for orbital scenarios |
| V7 | **Orbital elements / TLE + epoch** | Keplerian set or TLE, target lat/lon, time | full propagation → time-resolved V5 | none (`RADIANT_Geometry_Orbital.md` scopes the theory) | **deferred** — gaps.md entry; out of this plan (no propagator) |
| V8 | **Trajectory / ephemeris time series** | platform track (t, pos, vel), target track | per-timestep geometry, sweep integration | none; `SweepResult` machinery is adjacent | **deferred** — gaps.md entry (pairs with V7) |

### Solar geometry

| # | Mode | User supplies | Derivation | Machinery today | Disposition |
|---|------|---------------|------------|-----------------|-------------|
| S0 | **None / thermal** | `solar_illumination = off` | θ_s, Δφ = None (T1 chains) | works today | **v1** (unchanged) |
| S1 | **Direct angles** | solar zenith θ_s + relative azimuth Δφ | none | canonical today | **v1** (unchanged) |
| S2 | **Sun elevation + azimuth** | solar elevation, azimuth | θ_s = π/2 − elevation | trivial complement | **v1** (Phase 1) — converter |
| S3 | **Site + time** | target latitude, day-of-year, local solar time (or LTAN for sun-sync orbits) | θ_s via declination + hour angle | `core/solar_geometry.py` complete, tested, **zero consumers** | **v1** (Phase 1) — pure wiring of existing helpers; makes sun-sync trade studies one-line |
| S4 | **Full ephemeris** | epoch + positions | exact sun vector | none | **deferred** with V7/V8 — gaps.md entry |

### Explicitly out of mode scope

- **Target aspect/orientation** (yaw/pitch/roll of the target shape relative to LOS)
  stays in `source.target.shape.*` — it is a target property consumed by the
  projected-area machinery (`source/shapes/`), not scene geometry. The seam is noted
  in `RADIANT_Geometry.md` so a future aspect-angle mode has a documented home.
- **Platform attitude** (sensor yaw/pitch/roll) — nothing downstream consumes it
  today; deleted with the dead dataclasses (CU-094). Returns only when a consumer
  (pointing budget, agility model) exists.

### Mode resolution rules (normative, tested in Phase 1)

1. Exactly one viewing mode and one solar mode resolve per run. Mode detection is by
   which parameters carry user-set provenance — no separate "mode" switch parameter
   for v1 modes that share the V1 spine (V2/V3/V4 are alternate entries into V1).
2. Redundant values from the same mode family (e.g., both η and θ_o; both range and
   altitude+zenith) must agree within 1% or GeometryStage raises an actionable
   over-specification error naming both parameters and both implied values.
3. Every derived value is published with `Provenance.DERIVED` and appears in
   `result.inspect()` with the mode that produced it.
4. Under-specification falls back to documented defaults (nadir, sun-overhead for
   T2/T3, extended scene) — never a silent NaN (Rule 16).

## 4. Non-Goals (scope fence)

- **No regime redesign.** Tentative classification stays in SourceStage, final in
  OpticsStage (Rule 10). SourceStage's IFOV reads (`detector.pixel_pitch_x_um`,
  `optics.focal_length_m`) stay — that is sensor definition, not scene geometry.
- **No physics changes.** Same formulas, same defaults ⇒ golden baselines must not
  drift. Any drift is a stop-and-investigate event.
- **No orbital propagation.** V7/V8 are surveyed (§3) and gap-filed, not built.
  `RADIANT_Geometry_Orbital.md` scope is untouched; the new doc cross-references it.
- **No GUI implementation.** This plan makes the codebase GUI-ready; screens come after.

## 5. Phases

Each phase = one atomic landing on main. Gate for every phase:
`pytest -v` (full suite, zero golden drift unless the phase says otherwise),
`mypy --strict src/radiant/core src/radiant/api`, `import-linter --config pyproject.toml`,
`ruff check src/`, `python scripts/check_org_rules.py`.

### Phase 0 — Design record (docs only)
1. File **CU-093** (range redundancy) and **CU-094** (dead dataclasses) in
   `docs/tracking/Cleanup_Backlog.md` (Rule 21).
2. File **gaps.md entries** for the deferred input modes: V5 (two geodetic points),
   V7 (orbital elements/TLE), V8 (trajectory time series), S4 (solar ephemeris).
3. Write **`docs/adr/0006-geometry-stage.md`**: the decision, the three owner rulings,
   the input-mode taxonomy (§3), the SensorDescriptor supersession, alias/deprecation
   policy, zero-drift requirement, CU-005 closure path (V2 wires the reserved converter).
4. This plan file lands in the same commit.

**Docs:** ADR-0006 (create), Cleanup_Backlog.md (edit), gaps.md (edit), this plan (create).

### Phase 1 — GeometryStage module (additive; zero user-visible change for existing inputs)
1. Level 0 tests **first** (Rule 18): per-mode derivation tests (V0–V4, V6, S0–S3)
   against hand-computed spherical-Earth values; LOS construction; mode-resolution
   matrix (each over/under-specification case); alias redirect + provenance behavior.
2. Create `src/radiant/geometry/`:
   - `_schema.py` — the 7 `geometry.*` ParameterDefs **moved verbatim** from
     `atmosphere/_schema.py`; `geometry.target_range_m` (moved from
     `source/_schema.py` `TARGET_RANGE`, `deprecated_aliases={"source.target.range_m"}`);
     new mode-entry params (`geometry.sensor_off_nadir_rad` [V2],
     `geometry.ground_range_m` [V3], `geometry.elevation_angle_rad` [V4],
     `geometry.orbit_altitude_m` [V6], `geometry.solar_elevation_rad` [S2],
     `geometry.site_latitude_rad` / `day_of_year` / `local_solar_time_h` /
     `ltan_h` [S3]) — every one a `ParameterDef` (Rule 12).
     `geometry.sensor_altitude_m` gains `deprecated_aliases={"platform.h_sensor"}`
     **only after** the Phase 3 audit — until then `platform.h_sensor` stays put.
   - `modes.py` — mode detection + resolution to the canonical representation
     (the §3 rules). One concern, one module (Rule 19).
   - `stage.py` — `GeometryStage.run()`: resolve mode, validate, build
     `LineOfSightGeometry` (logic lifted from `source/_inferrer.py:270-340`),
     derive scalars, publish.
   - Inverse ground-range solver (V3) gets its own module per Rule 19 if it is more
     than a core-function call; V2 calls the existing `theta_o_from_eta`; V4/S2 are
     boundary complements inside `modes.py`; V6 calls `core/orbit.py`; S3 calls
     `core/solar_geometry.py`. **No new physics** — wiring and inversion only.
3. Register: `api/session.py` stage list (before `SourceStage`),
   `api/_param_registry.py` (import GEO_PARAMS; drop the moved defs from ATMO/SRC lists).
4. `pyproject.toml` import-linter contract: `radiant.geometry` may import
   `radiant.core` only.
5. Back-compat within the phase: downstream stages still read `params.get("geometry.*")`
   directly — unchanged, since names didn't change. `source.target.range_m` readers
   keep working via alias. New modes are additive; existing scenarios resolve as
   V0/V1 exactly as before.

**Docs (lock-step, Rule 20):**
- **Create `docs/architecture/RADIANT_Geometry.md`** — the stage spec: input-mode
  taxonomy (from §3, normative), parameter table, published-outputs contract,
  mode-resolution rules, formula standard (spherical Earth), relationship to
  `RADIANT_Geometry_Orbital.md`, `core/los_geometry.py`, and the target-aspect seam.
- **Edit `RADIANT_Master_Architecture.md`** — stage list, document map row.
- **Edit `RADIANT_Signal_Chain_Architecture.md`** — chain order, stage table,
  `stage_outputs["geometry"]` contract.
- **Edit `RADIANT_Parameter_System.md`** — namespace ownership table
  (`geometry.*` owner = GeometryStage), alias mechanics, new mode-entry params.
- **Edit `RADIANT_Use_Case_Matrix.md`** — §4.4 SensorDescriptor stub replaced by a
  pointer to ADR-0006; geometry-contract note (§ item 7) updated.
- **Edit `RADIANT_File_Tree.md`** — new package.
- **Edit `CLAUDE.md`** — package layout, signal-chain sentence, import-rules table row.
- **Edit `docs/guides/parameter_reference.md`** — new params; `geometry.target_range_m`
  canonical; `source.target.range_m` marked deprecated-alias.
- **Edit `docs/guides/configuration.md`** — a "defining your scene geometry" section
  with one YAML example per v1 mode (this is the GUI-workflow doc seed).
- **Edit `mkdocs.yml`** — nav entry for the new architecture doc if the nav lists
  architecture pages explicitly.
- **`CHANGELOG.md` [Unreleased]** — new stage + new input modes (public surface),
  parameter rename with alias (public surface), CU-005 η-input surface now live.

### Phase 2 — Downstream stages consume published geometry (zero-drift re-plumb)
1. `source/_inferrer.py` — stop rebuilding LOS from params; `SourceStage` reads
   `state.stage_outputs["geometry"]["los_geometry"]`. The inferrer keeps descriptor
   logic only. Source's `range_m` regime input reads the published slant range
   (user range if set, derived otherwise — the stage output already encodes precedence).
2. `atmosphere/stage.py` — read LOS from `stage_outputs["geometry"]` (source
   republishes nothing). Update the "run SourceStage before AtmosphereStage" error text.
3. `platform/stage.py:259-295`, `performance/stage.py:288,307,451-543` — consume
   published `slant_range_m` / `ground_range_m` / `incidence_angle_rad` instead of
   recomputing from params.
4. Unit-test fixtures that ran SourceStage standalone gain a GeometryStage-first
   setup (or a published-geometry fixture).
5. Gate: **byte-identical golden results** (precedent: CU-009 landed the same kind of
   re-plumb with zero drift).

**Docs (lock-step):**
- **Edit `RADIANT_Signal_Chain_Architecture.md`** — data-flow table: who reads
  `stage_outputs["geometry"]`.
- **Edit `RADIANT_Metric_Dependencies.md`** — ground-range/GSD/detection-range
  dependency rows now point at geometry outputs.
- **Edit `RADIANT_Atmosphere.md`** — geometry params no longer atmosphere-owned;
  LOS arrives from GeometryStage.
- **Edit `RADIANT_Source_Target_System.md`** — inferrer no longer builds LOS.
- **Edit `docs/guides/regime_selection.md`** — range precedence description.
- **`CHANGELOG.md`** — no entry if truly zero-drift and no public surface moved
  (internal re-plumb); entry required if error messages/behavior changed.

### Phase 3 — Collapse the duplicates; enforce consistency
1. **CU-090 execution**: audit all 32 `platform.h_sensor` set-sites; confirm no site
   sets it and `geometry.sensor_altitude_m` to different values; fold via
   `deprecated_aliases` on `geometry.sensor_altitude_m`; delete the
   `platform.h_sensor` ParameterDef; update the atmosphere no-atmosphere
   provenance check (`atmosphere/stage.py:132`) to the canonical name
   (alias preserves user-set provenance — verify with a test).
2. **CU-093 execution**: the §3 rule-2 over-specification check live in GeometryStage —
   user-set `geometry.target_range_m` vs. user-set altitude+zenith implying a different
   range (tolerance 1%) → actionable `RadiantError`.
3. Migrate internal call sites, scenarios, examples (16 files for range;
   32 for h_sensor) to canonical names; aliases stay for external users one cycle.
4. Close **CU-090**, **CU-093**, and **CU-005's residual** (η-surface now shipped)
   with commit SHAs (Rule 22).

**Docs (lock-step):**
- **Edit `docs/guides/parameter_reference.md`** and **`docs/guides/configuration.md`** —
  canonical names throughout; deprecation table.
- **Edit `RADIANT_Config_Format.md`** — YAML examples use canonical names.
- **Edit `RADIANT_Parameter_System.md`** — deprecated-alias table (two entries).
- **Edit scenario walkthroughs** only where they name the old params.
- **`CHANGELOG.md`** — deprecations (public surface); new over-specification error
  (**behavior change**: previously-silent disagreement now raises — state direction).

### Phase 4 — Delete dead code; close out
1. **CU-094 execution**: delete `ObserverGeometry`, `TargetGeometry`, `SceneGeometry`
   (+ their tests + `core/__init__.py` exports; grep for `to_dict` round-trip
   consumers in `io/` first). Live functions stay. Close CU-094 with SHA.
2. Re-audit **CU-082**'s geometry-GUI records against the new stage (it names
   GUI kickoff as its re-audit trigger; this plan is the pre-GUI landing).
3. Final docs sweep + archive.

**Docs (lock-step):**
- **Edit `RADIANT_Conventions.md`** / **`RADIANT_Reference_Frames.md`** — remove/fix
  any reference to the deleted dataclasses.
- **Edit `RADIANT_GUI_Architecture.md`** — workflow section opens with the Geometry
  screen (input-mode picker maps 1:1 to §3 modes); stage-tab order matches the
  9-stage chain (this is the driver of the whole plan — the GUI doc must record it).
- **Edit `dev_tools/gui_mockups/README.md`** — note the mockups predate the
  geometry-first chain (they open at Source) so the next design iteration adds
  the Geometry screen.
- **`CHANGELOG.md`** — removed public classes (public surface).
- **Move this plan to `docs/archive/`** with HISTORICAL banner in the same commit
  that completes Phase 4 (Rule 24).

## 6. Risk Register

| Risk | Mitigation |
|---|---|
| Golden drift from re-plumb | Same formulas/defaults; per-phase full-suite gate; CU-009 precedent proves zero-drift is achievable |
| `platform.h_sensor` semantics differ from plain altitude (space-subcase provenance check) | Phase 3 audits all 32 sites **before** folding; provenance-preservation test |
| Alias machinery untested at this scale | Phase 1 Level 0 tests cover set/get/provenance through both alias names |
| Mode-resolution ambiguity (user sets a mix of mode params) | §3 rules are a tested decision matrix — every cell (pair of user-set groups) has an expected outcome in the Phase 1 test suite |
| Hidden consumer of deleted dataclasses | Phase 4 greps `io/`, `api/`, serialization paths before deletion |
| MODTRAN deck rendering reads `geometry.*` (`modtran.py:1076-1087`) | Names unchanged — no MODTRAN change expected; deck-render tests in gate |
| Doc sprawl (13+ docs touched) | Each phase lists its exact doc set above; PR checklist Rule-20 line enforces |

## 7. Completion Definition

- Chain runs geometry-first; all geometry derivations happen exactly once.
- All v1 input modes (V0–V4, V6, S0–S3) resolve, validate, and are Level-0 tested;
  deferred modes (V5, V7, V8, S4) are gap-filed.
- CU-090, CU-093, CU-094 closed with SHAs; CU-005 residual closed; CU-082 re-audited.
- `docs/architecture/RADIANT_Geometry.md` exists and matches shipped code.
- All listed docs updated; `CHANGELOG.md` entries filed; zero golden drift
  (except the new, documented over-specification error path).
- This file lives in `docs/archive/` with a HISTORICAL banner.
