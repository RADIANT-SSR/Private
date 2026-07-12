# RADIANT Geometry Stage — Scene Geometry as Stage 0

**Status:** Active (2026-07-12) — normative spec for `src/radiant/geometry/`; decision record ADR-0006
**Scope:** the GeometryStage contract: parameters, input modes, published outputs, validation rules. The underlying orbital/geometric *theory* (slant range derivations, GSD, J2 sun-sync, revisit) lives in [RADIANT_Geometry_Orbital.md](RADIANT_Geometry_Orbital.md).

---

## 1. Role and Chain Position

`GeometryStage` is stage 0 of the signal chain (ADR-0006):

```
geometry → source → atmosphere → optics → platform
        → spectral_integration → detector → readout → performance
```

It is a pure `Stage` (Rule 6) that emits **no radiometric frames**. Its entire
product is `stage_outputs["geometry"]`: the validated, mode-resolved scene
geometry — where the sensor, target, and sun are — derived exactly once so no
downstream stage re-derives a geometric quantity.

Why stage 0: regime classification, atmospheric path length, smear, GSD, and
detection range all *derive from* scene geometry. Placing it first makes the
chain order, the parameter dependency graph, and the (future) GUI screen order
tell the same story.

## 2. Input Modes

The user expresses the scene in exactly one **mode** per family. Full
taxonomy and rationale: ADR-0006; deferred modes are Gap 83 (two-point
geodetic) and Gap 84 (TLE/trajectory/ephemeris).

### Viewing family (resolves to θ_o, the target-side path zenith)

| Mode | Entry parameters | Derivation |
|------|------------------|------------|
| V0 direct range | `geometry.target_range_m` | range drives regime classification; angles default to nadir |
| V1 path zenith (reference) | `geometry.path_zenith_rad` | θ_o taken directly |
| V2 off-nadir | `geometry.sensor_off_nadir_rad` | θ_o via spherical sine rule (`core.los_geometry.theta_o_from_eta`) |
| V3 ground range | `geometry.ground_range_m` | θ_o via the spherical viewing triangle (`core.viewing_triangle`) |
| V4 elevation | `geometry.elevation_angle_rad` | θ_o = π/2 − elevation |
| V6 circular orbit | `geometry.circular_orbit` (bool) | ground speed + orbital period from `core.orbit` at `sensor_altitude_m` |

`geometry.sensor_altitude_m` (required) and `geometry.target_altitude_m`
anchor every mode.

### Solar family (resolves to θ_s, Δφ)

| Mode | Entry parameters | Derivation |
|------|------------------|------------|
| S0 night | `geometry.solar_illumination = "night"` | θ_s = Δφ = None (thermal-only scene) |
| S1 direct (reference) | `geometry.solar_zenith_rad` | θ_s taken directly |
| S2 elevation | `geometry.solar_elevation_rad` | θ_s = π/2 − elevation |
| S3 site + time | `geometry.site_latitude_rad`, `geometry.day_of_year`, `geometry.local_solar_time_h` *or* `geometry.ltan_h` | θ_s via declination + hour angle (`core.solar_geometry`) |

`geometry.solar_azimuth_rad` supplies Δφ in every lit mode (wrapped to [−π, π]).

### Mode-resolution rules (normative; enforced in `geometry/modes.py`)

1. **Detection is by provenance.** A parameter left at DEFAULT provenance was
   not provided. Mode-entry defaults are inert; there is no mode switch.
2. **Redundant entries must agree.** Two or more user-set entries for the
   same canonical quantity must agree within 1 % (relative, 1e-6 rad absolute
   floor) or the stage raises `GeometrySpecificationError` naming every
   entry and its implied value.
3. **Every derived value is published with its mode label**
   (`viewing_mode` / `solar_mode` / `kinematics_mode`) so `result.inspect()`
   shows how each number was produced.
4. **No entries at all → documented defaults** (nadir view; 0.5 rad solar
   zenith in day mode) — never a silent NaN (Rule 16).
5. `geometry.ltan_h` and `geometry.local_solar_time_h` are mutually
   exclusive; setting both raises.
6. A user-set `geometry.ground_speed_m_s` that disagrees (>1 %) with the
   circular-orbit derivation raises.

## 3. Published Contract — `stage_outputs["geometry"]`

| Key | Type | Meaning |
|-----|------|---------|
| `los_geometry` | `LineOfSightGeometry` | the Source → Atmosphere contract object (ADR-0002), built here |
| `theta_o_rad` | float | canonical target-side path zenith |
| `eta_rad` | float | sensor-side off-nadir angle (sine rule) |
| `slant_range_m` | float | target ↔ sensor slant range (spherical triangle, θ_o-based) |
| `ground_range_m` | float | surface arc, nadir point → target |
| `incidence_angle_rad` | float | LOS vs target local vertical (≡ θ_o on a spherical Earth) |
| `target_range_m` | float \| None | user-declared slant range (V0); None if unset |
| `h_sensor_m`, `h_target_m` | float | anchor altitudes |
| `theta_s_rad`, `delta_phi_rad` | float \| None | solar geometry (None at night) |
| `solar_illumination` | str | `day` / `night` |
| `ground_speed_m_s` | float | direct or orbit-derived |
| `orbital_period_s` | float \| None | circular-orbit mode only |
| `viewing_mode`, `solar_mode`, `kinematics_mode` | str | which input mode resolved each family |

**Consumers** (Geometry_Stage_Plan Phase 2, shipped): SourceStage adopts the
published `los_geometry` (descriptor-adjusted in `_adjust_scene_los` — T1
solar-strip, at_aperture → None, no_atmosphere h_tgt override) and feeds the
published θ_o to shape view directions; AtmosphereStage receives the adopted
LOS through source's output as before (ADR-0002 unchanged); PlatformStage
consumes `slant_range_m` for velocity smear; PerformanceStage consumes
`slant_range_m` / `incidence_angle_rad` (GSD, diffraction ground projection),
`ground_range_m`, and `ground_speed_m_s` (access rate — enables the V6
circular-orbit mode end-to-end). Legacy (altitude, angle) fallbacks survive
only for partial fixtures that run a stage without GeometryStage; CU-096
tracks retiring them.

## 4. Formula Standard

All viewing solutions use one spherical triangle (Earth centre, target,
sensor) on `constants.R_EARTH_M` (6371.0 km mean radius, the single
canonical Earth radius since CU-097), implemented in
`core/viewing_triangle.py` — the θ_o-referenced counterpart of the
η-referenced helpers in `core/geometry.py`. Downlooking only
(`h_sensor > h_target`); uplooking is rejected loudly (owner ruling
2026-07-11). One unification remains tracked: CU-096 (θ_o vs η in
platform/performance).

## 5. Parameters

Seventeen `ParameterDef`s in `geometry/_schema.py` — the seven canonical
definitions moved verbatim from `atmosphere/_schema.py`, plus
`geometry.target_range_m` (moved from `source/_schema.py`;
`source.target.range_m` survives as a deprecated alias, warn-and-redirect),
plus nine mode-entry parameters. See `docs/guides/parameter_reference.md`
for the full table with units, bounds, and defaults.

## 6. Boundaries and Seams

- **Target aspect/orientation** (yaw/pitch/roll of a shaped target relative
  to the LOS) is a *target property*, owned by `source.target.shape.*` and
  the projected-area machinery — not scene geometry. A future aspect-angle
  input mode would extend this stage; the seam is here by design.
- **Platform attitude** has no consumer and no parameters (deleted with the
  dead core dataclasses, CU-094). It returns only with a consuming model
  (pointing budget, agility).
- **Regime classification** stays in SourceStage (tentative) and OpticsStage
  (final) per Rule 10 — geometry supplies the range, not the verdict.
- **Time-resolved geometry** (orbital elements, trajectories, ephemerides) is
  out of scope for v1 — Gap 84.
