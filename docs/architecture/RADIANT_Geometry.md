# RADIANT Geometry Stage — Scene Geometry as Stage 0

**Status:** Active (2026-07-12; direction-general since 2026-07-26) — normative spec for `src/radiant/geometry/`; decision records ADR-0006 and ADR-0011
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

**Every entered viewing angle is referenced to the path's LOWER endpoint**
(ADR-0011 decision 3). This is exactly back-compatible: in every scene the
sensor is above the target, so the target *is* the lower endpoint and each
entry means precisely what it always meant. When the sensor is the lower
endpoint (up-looking), θ_o is derived as $\pi - \zeta_{up}$ and the published
`viewing_mode` label says so.

| Mode | Entry parameters | Derivation |
|------|------------------|------------|
| V0 direct range | `geometry.target_range_m` | range drives regime classification; angles default to nadir. On a **level** path with no angle entry the range is the chord that builds the triangle: $\varphi = 2\arcsin(d/2r)$, $\theta_o = \pi/2 + \varphi/2$ |
| V1 path zenith (reference) | `geometry.path_zenith_rad` | LOS zenith **at the lower endpoint**. Sensor above target ⇒ identical to θ_o (all classic scenes). Sensor below ⇒ it is the sensor's own zenith and θ_o = π − ζ_up (`core.viewing_triangle.solve_from_lower_zenith`) |
| V2 off-boresight | `geometry.sensor_off_nadir_rad` | Off-**boresight** angle at the sensor; the reference axis is resolved from the altitudes, never declared. Sensor above target ⇒ the classic off-nadir η, θ_o via spherical sine rule (`core.los_geometry.theta_o_from_eta`). Sensor at or below ⇒ zenith-referenced, so the entry already is ζ_low |
| V3 ground range | `geometry.ground_range_m` | Direction-free: the surface arc between the two ground points fixes the central angle Δ = arc / R_E whichever endpoint is higher; θ_o via the spherical viewing triangle (`core.viewing_triangle`) |
| V4 elevation | `geometry.elevation_angle_rad` | Elevation above the horizontal **at the lower endpoint**; ζ_low = π/2 − elevation. **Signed** since ADR-0011 — a negative elevation is legal and means the path leaves its lower endpoint on a descending shoulder (a level arm sags below the horizontal) |
| V6 circular orbit | `geometry.circular_orbit` (bool) | ground speed + orbital period from `core.orbit` at `sensor_altitude_m` |

`geometry.sensor_altitude_m` (required) and `geometry.target_altitude_m`
anchor every mode, and their ordering — never a user switch — derives the LOS
direction (`down` / `up` / `level`, published as `los_direction`).

### Solar family (resolves to θ_s, Δφ)

| Mode | Entry parameters | Derivation |
|------|------------------|------------|
| S0 night | `geometry.solar_illumination = "night"` | θ_s = Δφ = None (thermal-only scene) |
| S1 direct (reference) | `geometry.solar_zenith_rad` | θ_s taken directly |
| S2 elevation | `geometry.solar_elevation_rad` | θ_s = π/2 − elevation |
| S3 site + time | `geometry.site_latitude_rad`, `geometry.day_of_year`, `geometry.local_solar_time_h` *or* `geometry.ltan_h` | θ_s via declination + hour angle (`core.solar_geometry`) |

`geometry.solar_azimuth_rad` supplies Δφ in every lit mode (wrapped to [−π, π]).

### LOS-rate family (resolves to ω, the line-of-sight angular rate)

Target kinematics (Gap 111) ship **both doors, provenance-resolved** (ADR-0011
decision 10):

| Mode | Entry parameters | Derivation |
|------|------------------|------------|
| K0 platform-only (default) | *(none)* | ω = ground-track speed / slant range — the value `platform/smear.py` already derives. `None` when the endpoints are coincident (no LOS to rotate) |
| K1 direct rate | `geometry.los_angular_rate_rad_s` | taken as given; needs no geometry, so it is the door that still works for a coincident-endpoint scene |
| K2 target velocity | `geometry.target_speed_m_s`, `geometry.target_heading_rad`, `geometry.target_climb_rad` | ω = \|v_rel,⊥\| / R with v_rel = v_target − v_sensor (`geometry/los_rate.py`) |

Heading is measured in the target's local horizontal plane **from the
observer's ground azimuth** — the same zero and sense `delta_phi` uses
(Δφ = φ_s − φ_o with φ_o ≡ 0) — and climb is the velocity's elevation above
that plane. The platform's ground track is modelled as **cross-track** to the
LOS azimuth plane (the push-broom convention `platform/smear.py` already
assumes, RADIANT having no track-azimuth input), which is what makes the K0
limit reduce *exactly* to the smear arm's rate at every θ_o rather than only at
nadir. Both doors set must agree within 1 % (rule 2 below) or the stage raises.

### Mode-resolution rules (normative; enforced in `geometry/modes.py`)

1. **Detection is by provenance.** A parameter left at DEFAULT provenance was
   not provided. Mode-entry defaults are inert; there is no mode switch.
2. **Redundant entries must agree.** Two or more user-set entries for the
   same canonical quantity must agree within 1 % (relative, 1e-6 rad absolute
   floor) or the stage raises `GeometrySpecificationError` naming every
   entry and its implied value.
3. **Every derived value is published with its mode label**
   (`viewing_mode` / `solar_mode` / `kinematics_mode` / `los_rate_mode`) so
   `result.inspect()` shows how each number was produced.
4. **No entries at all → documented defaults** (nadir view; 0.5 rad solar
   zenith in day mode) — never a silent NaN (Rule 16).
5. `geometry.ltan_h` and `geometry.local_solar_time_h` are mutually
   exclusive; setting both raises.
6. A user-set `geometry.ground_speed_m_s` that disagrees (>1 %) with the
   circular-orbit derivation raises.

### Machine-readable manifest (`geometry/mode_manifest.py`)

The family → mode → parameter structure above is also stated as **data** in
`geometry/mode_manifest.py` (`MODE_FAMILIES`: family key, anchor params, ordered
modes with their entry dot-paths, default door — viewing, solar, kinematics,
and the LOS-rate family) together with
`active_mode_key(family, is_provided, get_value)` — the provenance-based
detection a view layer uses to show which door a config currently sits in.
View layers consume it through the public bridge `radiant.api.geometry_modes`
(pure re-export, the `radiant.api.metric_groups` precedent), so the GUI's
Geometry screen transcribes no grouping of its own (CU-120; it keeps only
display labels). The manifest is hand-maintained next to the resolvers;
`geometry/tests/test_mode_manifest.py` proves per mode that it matches the
resolver behaviour and the `mode_entry` / `solar_site` schema tags, so it
cannot drift silently.

## 3. Published Contract — `stage_outputs["geometry"]`

| Key | Type | Meaning |
|-----|------|---------|
| `los_geometry` | `LineOfSightGeometry` | the Source → Atmosphere contract object (ADR-0002), built here. Carries **both** endpoints since ADR-0011: `h_sensor` joins `h_tgt`, which is what lets the object own the altitude/hemisphere invariant and the horizon guard, and what makes it the single source of truth for the sensor altitude inside `radiant.atmosphere` (guardrail G2 — no backend side-load) |
| `theta_o_rad` | float | canonical target-side path zenith, domain **[0, π] closed** (π = target directly overhead; obtuse ⇒ up-looking) |
| `los_direction` | str | `down` / `up` / `level` — derived from the altitude pair, never a user switch (ADR-0011 decision 1); read straight off `los_geometry` so there is one definition |
| `eta_rad` | float \| None | interior angle at the sensor (sine rule); the familiar off-nadir look angle when the sensor is above the target, obtuse when below |
| `slant_range_m` | float \| None | target ↔ sensor slant range (spherical triangle, θ_o-based) |
| `ground_range_m` | float \| None | surface arc between the two ground points |
| `incidence_angle_rad` | float \| None | LOS vs target local vertical (≡ θ_o on a spherical Earth); `None` alongside the ranges in the coincident-endpoint case |
| `target_range_m` | float \| None | user-declared slant range (V0); None if unset |
| `h_sensor_m`, `h_target_m` | float | anchor altitudes |
| `scene_class` | str | derived observer×target band label, e.g. `ground_to_air` (§3.1) |
| `observer_class`, `target_class` | str | the two pieces: `ground` / `air` / `space` |
| `los_angular_rate_rad_s` | float \| None | relative LOS angular rate [rad/s] (Gap 111); `None` only for coincident endpoints |
| `theta_s_rad`, `delta_phi_rad` | float \| None | solar geometry (None at night) |
| `solar_illumination` | str | `day` / `night` |
| `ground_speed_m_s` | float | direct or orbit-derived |
| `orbital_period_s` | float \| None | circular-orbit mode only |
| `viewing_mode`, `solar_mode`, `kinematics_mode`, `los_rate_mode` | str | which input mode resolved each family |

`eta_rad` / `slant_range_m` / `ground_range_m` are `None` in exactly one case:
**coincident endpoints** — equal altitudes with no separation supplied at all
(no angle entry, no ground range, no target range), where the two endpoints
are the same point and there is no path. That is the $\varphi \to 0$ limit of
the level solution, not a carve-out: an equal-altitude scene carrying *any*
separation resolves to the full horizontal triangle (guardrail G4 — the
pre-ADR-0011 collocated no-triangle carve-out is retired).

### 3.1 Scene class — derived, never mandatory (ADR-0011 decision 8)

`geometry/scene_class.py` derives the observer × target label from the two
altitudes and publishes it beside the (already derived) `los_direction`:

| Band | Altitude | Source of the boundary |
|---|---|---|
| `ground` | h < 1 km | **classification convention only — no physics depends on it** |
| `air` | 1 km ≤ h ≤ 100 km | between the two boundaries |
| `space` | h > 100 km | the `h_atm_top` (Kármán-line) convention |

Both boundaries are closed from below: 1 km exactly and 100 km exactly are
`air`. A scene at 999 m and one at 1001 m compute **identically** — the label
is the only difference. **Physics never branches on the class**: it drives
defaults, metric relevance (the Phase 3 scene-class → relevance map, guardrail
G3), validation, and GUI composition only.

`geometry.scene_class` is an **optional assertion**, never required (`auto` =
unset). When set and it disagrees with the derivation the stage raises
`GeometrySpecificationError` naming asserted vs. derived and both altitudes —
the CU-093 redundant-entry pattern, which is what catches a wrong-magnitude
altitude typo (600 m where 600 km was meant) that pure derivation would render
as a self-consistent scene of the wrong class.

View layers consume the scene-class → default-metric-relevance map through the
public bridge **`radiant.api.scene_relevance`** (a pure re-export of
`radiant.performance.scene_relevance` — the `radiant.api.geometry_modes` /
`metric_groups` precedent), so the GUI's scene-class steering card
(Geometry-Flexibility Phase 4) shows which metrics a class turns off by default
without importing a physics stage and without a second copy of the map
(guardrail G3). In the GUI the assertion is the mission-type entry point: the
card renders the derived chip, the assertion field (one `sensor.set` per edit),
and the relevance preview, and an asserted-vs-derived mismatch tints the card
in-context.

**Consumers** (Geometry_Stage_Plan Phase 2, shipped): SourceStage adopts the
published `los_geometry` (descriptor-adjusted in `_adjust_scene_los` — T1
solar-strip, at_aperture → None, and the `no_atmosphere` `h_tgt` → 0 override,
which since ADR-0011 applies only on a down-looking path: rewriting `h_tgt`
while keeping `h_sensor` and θ_o would otherwise fabricate a triple that
violates the hemisphere invariant) and feeds the
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
η-referenced helpers in `core/geometry.py`.

**The implementation is direction-general** since Geometry-Flexibility Phase 1
([ADR-0011](../adr/0011-generalized-viewing-geometry.md)). The 2026-07-11
"v1 has no uplooking geometry" ruling is superseded and **the code restriction
is no longer in force**: `h_sensor <= h_target` and $\theta_o \ge \pi/2$ are
accepted inputs, not errors. The same triangle is simply read from the other
vertex — symmetric solutions, not a parallel module (Rule 27):

- **θ_o domain is the closed interval $[0, \pi]$.** $\pi$ is attained exactly
  by the vertical up-looking geometry (ground sensor with the target at its
  zenith; a LEO sensor directly beneath a GEO target) and is an ordinary
  scene, not an edge case. *(ADR-0011 writes the domain as $[0, \pi)$; that is
  a notation slip (owner-confirmed 2026-07-26, plan §8.3) — the closed interval is
  what the geometry requires and what is implemented, with the discrepancy
  noted at the domain validator.)*
- **Altitude/hemisphere invariant** (derived, enforced):
  $h_{sensor} > h_{target} \iff \theta_o < \pi/2$ and
  $h_{sensor} \le h_{target} \iff \theta_o > \pi/2$; equal altitudes give
  $\theta_o = \pi/2 + \varphi/2$. A user-supplied combination that violates it
  is not a viewing geometry at all and raises an actionable error naming both
  altitudes and the hemisphere the angle implies.
- **Root selection** follows the altitude ordering. Down-looking keeps the
  historical `+` root of the law of cosines *verbatim* (zero drift); level
  degenerates the `−` root to zero so the chord is the `+` root; up-looking
  takes the **near** (`−`) root — the `+` root there is the far,
  through-the-Earth intersection, which is what made a vertical LEO→GEO LOS
  falsely report an Earth intercept.
- **Unambiguous entry** for near-level geometry is `solve_from_lower_zenith`:
  a ray leaving the lower endpoint crosses the higher shell exactly once,
  whether it ascends monotonically or descends to a perigee first.

### 4.1 Horizon guard

Near-horizontal paths are guarded, not approximated: v1.x models no
refraction, so the band where refraction dominates must fail loudly rather
than return a plausible wrong number (Rule 17; ADR-0011 decision 6 as refined
by plan §8.3). The guard keys on the segment's **tangent-point topology**, not
on $|\theta_o - \pi/2|$ alone — a pure angular test over-rejects benign short
horizontal arms and a blanket equal-altitude exemption under-rejects long
transits. `classify_horizon_topology` classifies; `check_horizon_guard`
applies the verdict; `LineOfSightGeometry.__post_init__` calls it.

| Topology | Test | Condition | Thresholds (module constants) | Action |
|---|---|---|---|---|
| **endpoint_minimum** — the foot of the perpendicular from the Earth centre lies *outside* the segment (every ordinary up/down slant) | angular band at the **lower** endpoint, $\lvert \zeta_{low} - 90^\circ \rvert$ | $< 0.5^\circ$ | `GUARD_HARD_RAD` | raise |
| | | $0.5^\circ$–$2^\circ$ | `GUARD_WARN_RAD` | compute + quantified `UserWarning` |
| | | $> 2^\circ$ | — | clean |
| **interior_tangent** — the foot lies *on* the segment, so the ray dips to a tangent point between the endpoints (level and near-level arms) | tangent-height depression $\Delta h = (R_E + h_{low})(1 - \sin \zeta_{low}) \approx L^2/8R_E$ | $< 100$ m | `GUARD_DH_CLEAN_M` | clean |
| | | $100$ m – $2$ km | `GUARD_DH_RAISE_M` | compute + quantified `UserWarning` |
| | | $> 2$ km | — | raise (limb-like transit) |

Worked reference points: two 30 m towers 8 km apart → $\Delta h \approx 1.3$ m,
clean; two aircraft at 10 km, 200 km apart → $\Delta h \approx 784$ m, warns;
500 km at 5 km altitude → $\Delta h \approx 4.9$ km, raises. **Thresholds are
provisional**, calibrated in Phase 2 against a MODTRAN refraction on/off deck
pair. They are named module constants precisely so recalibration is a one-line
change.

The angular thresholds are **stored in radians** — `GUARD_HARD_RAD =
math.radians(0.5)`, `GUARD_WARN_RAD = math.radians(2.0)` — and every comparison
is made in radians (Rule 2: radians are the canonical internal angular unit).
The degrees in the table above are presentation only; they appear in code
solely inside error and warning message text. `horizon_band_action` accordingly
takes and returns a band in radians, and `HorizonGuardResult` carries
`band_rad` (CU-222). The threshold comparison carries 1e-12 rad of slack so
that a band landing *exactly* on a ratified threshold resolves to the
permissive side no matter how the caller constructed the angle — without it,
`math.radians(89.5)` and $\pi/2 -$ `math.radians(0.5)` differ by ~1e-16 rad and
would flip the verdict at 89.5° exactly.

Two consequences worth stating plainly:

- A *down-looking* $\theta_o$ in roughly $(88^\circ, 90^\circ)$ now warns where the old
  schema bound (89.5°) accepted it silently. No shipped scenario or golden
  baseline is near that band (the existing set tops out around 75°), so no
  computed result moves.
- A pre-ADR-0011 `LineOfSightGeometry` that does not carry `h_sensor` cannot
  see the topology, so only the conservative angular band applies. That is
  exactly the legacy down-looking case, and it is why level and near-level
  geometry **must** supply the sensor endpoint.

### 4.2 What Phase 1 does *not* change

The atmosphere remains direction-blind: every backend integrates the column
*above* the target out to the sensor, which is the target→sensor leg only when
the sensor is the upper endpoint. `AtmosphereStage` therefore refuses, before
backend dispatch, any path whose sensor sits at or below the target while the
path's lower endpoint is still inside the modelled column — with an error
naming the pending capability (direction-aware atmosphere, Phase 2, Gaps
108/109), not a backend-internal zenith-ceiling message. The one up-looking
composition that runs today is the wholly-vacuum one (both endpoints at or
above `h_atm_top`): the LEO→GEO quick win. See `RADIANT_Atmosphere.md` §4.2a–b.

### 4.3 CU-096 carve-out — Phase 3 re-audit (guardrail G4)

CU-096 itself (θ_o vs η in platform/performance) was **resolved 2026-07-23**
(commit `b5be390`). What survives is the residue it named: four
*partial-fixture* fallbacks — the smear width in `platform/stage.py` and the
GSD, ground-range, and diffraction-ground-projection helpers in
`performance/stage.py` — which derive geometry from `geometry.path_zenith_rad`
whenever `GeometryStage` published nothing. Guardrail G4 requires them to be
re-audited at Phase 3 close; the audit's findings (2026-07-27):

1. **Not reachable from the live chain.** `ChainRunner` always runs
   `GeometryStage` first, and the only scene for which it publishes no slant
   range — coincident endpoints — is refused upstream by the source stage's
   limb-crossing guard before any consumer is reached. The fallbacks are
   exercised only by the deliberate partial-stage fixtures
   (`performance/tests/test_off_nadir_theta_o_fallback.py` and the
   platform-stage unit fixtures).
2. **Their premise narrowed in Phase 1, and the narrowing is caught.**
   `geometry.path_zenith_rad` is now the zenith at the path's **lower
   endpoint** (ADR-0011 decision 3), which equals θ_o only while
   `h_sensor > h_target`. The fallbacks still read it as θ_o unconditionally —
   but `core.viewing_triangle._validate_hemisphere` (Phase 1) rejects the
   mismatch with an actionable `ParameterBoundsError` that names the
   supplementary-hemisphere value, so an up-looking partial fixture **raises**
   rather than silently computing the wrong slant range. No silent-wrong-answer
   exposure remains.
3. **Retirement is not zero-drift-provable and is therefore deferred, not
   silent.** Deleting the fallbacks changes those fixtures from "computes a
   GSD/smear" to "skips", which is a behavioural change in the test surface;
   the right retirement is the contract decision *"`PerformanceStage` and
   `PlatformStage` require `GeometryStage`"*, which belongs with the Phase 5
   scenario close-out rather than with a metrics phase. **Deferral record:**
   gating stage — Phase 5 (validation and scenario close-out); re-audit date —
   at Phase 5 close.

## 5. Parameters

Thirty-two `ParameterDef`s in `geometry/_schema.py` — the seven canonical
definitions moved verbatim from `atmosphere/_schema.py`, plus
`geometry.target_range_m` (moved from `source/_schema.py`;
`source.target.range_m` survives as a deprecated alias, warn-and-redirect),
plus nine viewing/solar mode-entry parameters, plus the four **target-kinematics**
parameters (`los_angular_rate_rad_s`; `target_speed_m_s` / `target_heading_rad` /
`target_climb_rad`) and the optional **`geometry.scene_class`** assertion
(not a mode door — see §3.1 — and therefore deliberately outside the mode
manifest), plus the ten **`geometry.target.*` target-extent
parameters** (shape, five dimensions, three orientation angles, projected area)
moved from `source.target.*` per ADR-0008 (the old `source.target.*` names survive
as deprecated aliases). Note: these extent params are **not** input-mode-form
parameters — they are rendered by the GUI `TargetShapePanel`, not the V/S mode
forms, and are excluded from the mode-form manifest. Phase A moves the parameter
namespace only; relocating the projected-area **computation** and the tentative
regime classification into this stage is ADR-0008 Phase B. See
`docs/guides/parameter_reference.md` for the full table with units, bounds, and
defaults.

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
