# RADIANT Geometry & Orbital Mechanics

**Date:** 2026-07-12
**Status:** Authoritative — written against shipped `src/radiant/core/` (2026-07-12 doc-reconciliation pass).
**Depends on:** RADIANT_Conventions.md (coordinate axioms, angular units), RADIANT_Parameter_System.md
**Scope:** The viewing-geometry, line-of-sight/path, orbital-mechanics, and solar-geometry computations that live in `radiant.core` and feed the geometry-derived performance metrics (GSD, ground range, swath, access rate, revisit) and the platform ground-velocity used by the smear cascade. RADIANT_Conventions.md fixes the coordinate *frame* (handedness, +Z, Euler order); this document covers the *computations* built on that frame. It fills the one architecture-doc gap the 2026-07 reconciliation found: a tested, API-consumed subsystem that had no dedicated doc.

---

## 0. Why this document exists

The coordinate-system axioms are in RADIANT_Conventions.md §1, but the actual
geodetic and orbital *math* — slant range on a curved Earth, incidence-angle
inflation, circular-orbit velocity, J2 nodal regression, sun-synchronous
inclination, revisit interval, solar zenith — lives in `radiant.core` with no
architecture-doc home. These are pure functions (no `ChainState`, no stage), and
several are consumed directly by the public API (`Sensor.set_ground_velocity_from_orbit`)
and by performance metrics (`performance/gsd.py`, `ground_range.py`,
`swath_width.py`, `access_rate.py`). This document is that home.

**Module map:**

| Module | Owns |
|--------|------|
| `core/geometry.py` | Spherical-Earth slant range, incidence angle, Euler↔rotation-matrix, `ObserverGeometry` / `TargetGeometry` / `SceneGeometry` (GSD, ground range, IFOV) |
| `core/los_geometry.py` | `LineOfSightGeometry` — the atmospheric-path geometry (slant range through atmosphere, airmass, Earth-intercept test) SourceStage publishes for AtmosphereStage |
| `core/orbit.py` | Circular-orbit velocity, period, ground-track speed |
| `core/repeat_ground_track.py` | J2 nodal regression, sun-synchronous inclination, equatorial track spacing, first-order revisit interval |
| `core/solar_geometry.py` | Solar declination (Spencer series), LTAN→local-solar-time, solar zenith angle |

All angles are radians internally (Conventions §5); `_deg` / `_rad` suffixes mark
the boundary unit. All lengths are metres (Conventions §3).

---

## 1. Earth-radius conventions (two, deliberately)

RADIANT uses **two** Earth radii in separate geometric contexts, and this is
intentional (documented in `core/constants.py`):

| Constant | Value [m] | Where used |
|----------|-----------|------------|
| `constants.R_EARTH_M` | `6.378137e6` (WGS-84 equatorial semi-major axis) | Line-of-sight boundary converters, airmass, ray-sphere intersect (`los_geometry.py`) |
| `geometry.EARTH_RADIUS_M` | `6_371_000.0` (US Standard 1976 mean radius) | Slant range / incidence (`geometry.py`) and all orbital mechanics (`orbit.py`, `repeat_ground_track.py`) |

The two differ by ~0.1%. Slant-range and orbital kinematics use the **mean**
radius (a whole-Earth average is the right choice for a sub-satellite ground
track); the atmospheric-path/airmass geometry uses the **equatorial** radius.
A single unified geoid is out of v1 scope (see §7).

---

## 2. Viewing geometry (`geometry.py`, `SceneGeometry`)

### 2.1 Slant range — spherical Earth

`slant_range_spherical_m(altitude_m, zenith_rad)` intersects the line of sight
with a spherical Earth of radius `EARTH_RADIUS_M`:

- At `zenith_rad = 0` (nadir) it returns `altitude_m` exactly.
- `zenith_rad` must be below the horizon angle `arcsin(R_E / (R_E + h))`; at or
  beyond the horizon the ray misses the Earth and the function raises (no silent
  NaN, Rule 16/17).

The flat-Earth approximation `h / cos(zenith)` over-predicts at large off-nadir
angles; the ray-sphere solve is exact for the spherical model.

### 2.2 Incidence angle

`incidence_angle_rad(altitude_m, zenith_rad)` returns the angle between the line
of sight and the **local surface normal** at the target. Earth curvature makes it
exceed the sensor off-nadir angle:

```
sin(incidence) = (R_E + h) / R_E · sin(zenith)
```

At nadir, incidence = 0; at 45° from 600 km, incidence ≈ 50.7°. This is the angle
that matters for BRDF and projected-area effects at the ground, not the sensor
look angle.

### 2.3 `SceneGeometry` — the derived-quantity aggregate

`SceneGeometry(observer, target)` composes an `ObserverGeometry` (altitude, look
angle, azimuth) and a `TargetGeometry` and exposes:

| Method | Formula |
|--------|---------|
| `altitude_difference_m` | `observer.altitude − target.altitude` |
| `slant_range_m` | line-of-sight distance at the look angle |
| `ground_range_m` | `altitude_difference · tan(look_angle)` |
| `gsd_m(f, pitch)` | `pitch · slant_range / f` (accounts for off-nadir via slant range) |
| `ifov_rad(f, pitch)` | `pitch / f` |

`gsd_m` / `ifov_rad` raise `CoreValidationError` on non-positive focal length or
pitch. These feed the `gsd_*_m` and `ground_range_m` performance metrics.

### 2.4 Attitude — Euler ↔ rotation matrix

`euler_to_rotation_matrix(yaw, pitch, roll)` and its inverse
`rotation_matrix_to_euler` implement the Conventions §1 **3-2-1 (ZYX)** convention
(yaw about +Z, then pitch about the once-rotated +Y, then roll about the
twice-rotated +X). These are the only attitude transforms in the codebase; no
physics module contains its own rotation math (Conventions §1 interface rule).

---

## 3. Line-of-sight / atmospheric-path geometry (`los_geometry.py`)

`LineOfSightGeometry` is the geometry object **SourceStage publishes** for
AtmosphereStage (Rule 6 pre-chain construction; see RADIANT_Atmosphere.md §6.5 and
CU-009). It carries the sensor/target altitudes, the path zenith, and — only for
solar-interacting targets — the solar zenith/azimuth (`theta_s` / `delta_phi` are
`None` for pure-thermal `T1Thermal` targets).

| Method | Meaning |
|--------|---------|
| `slant_range_atm` | geometric path length through the atmosphere (uses `R_EARTH_M`, the WGS-84 equatorial radius — §1) |
| `path_airmass_up` | relative air mass along the up-path; `sec(zenith)` at small angles, spherical correction near the horizon |
| `intercepts_earth(h_sensor)` | whether the line of sight strikes the Earth (distinguishes ground/limb/space targets) |

`theta_o_from_eta(eta, h_sensor, h_tgt)` converts an off-nadir angle at the sensor
to the zenith angle at the target endpoint — the conversion the MODTRAN Card-3
ANGLE deck-side needs (RADIANT_Atmosphere.md §5.2, CU-065).

---

## 4. Orbital mechanics (`orbit.py`)

Circular-orbit kinematics for a LEO platform, from the WGS-84 gravitational
parameter `constants.mu_earth_m3_s2` and the mean radius `EARTH_RADIUS_M`. Orbit
radius `a = R_E + h`.

| Function | Formula |
|----------|---------|
| `orbital_velocity_m_s(h)` | `v = √(μ/a)` — inertial speed |
| `orbital_period_s(h)` | `T = 2π √(a³/μ)` |
| `ground_track_speed_m_s(h)` | `v_g = v · R_E / a` — the nadir point traces a smaller circle than the satellite |

`ground_track_speed_m_s` is what `Sensor.set_ground_velocity_from_orbit()` calls to
populate `platform.ground_velocity_m_s` (the along-track velocity the smear MTF and
the dwell-time feasibility check consume — RADIANT_Spatial_Complete.md §7,
RADIANT_Scan_Timing.md). **Earth rotation is neglected** — this is the
non-rotating-Earth ground speed; the true sub-satellite speed varies with latitude
and orbit direction by up to ~6% (deferred, §7).

---

## 5. Repeat ground track, sun-sync, revisit (`repeat_ground_track.py`)

J2 secular theory from `constants.J2_earth`. Constants: solar day `_SOLAR_DAY_S =
86400 s`, sun-sync rate `_SUN_SYNC_RATE_DEG_PER_DAY = 360/365.2422 ≈ 0.9856 °/day`.

| Function | Formula / meaning |
|----------|-------------------|
| `nodal_regression_rate_deg_per_day(h, i)` | `Ω̇ = −1.5 · n · J2 · (R_E/a)² · cos i` — negative (westward) for prograde, positive for retrograde/sun-sync |
| `sun_synchronous_inclination_deg(h)` | solves `Ω̇(i) = 0.9856 °/day` for `i ∈ (90°, 180°)`; raises if no solution exists at that altitude (`\|cos i\| > 1`) |
| `equatorial_ground_track_spacing_m(h)` | `2π R_E · T_orbit / T_solar_day` — how far the Earth turns under the orbit per revolution |
| `revisit_interval_days(h, swath, lat)` | first-order coverage estimate: `spacing(lat) / (swath · orbits_per_day)`, `spacing(lat) = spacing_eq · cos(lat)` |

`revisit_interval_days` is explicitly a **first-order coverage estimate**, not an
exact repeat-cycle revisit: it assumes uniform track interleaving and ignores
swath overlap at the poles. All functions raise `RepeatGroundTrackError` on
out-of-range inputs.

---

## 6. Solar geometry (`solar_geometry.py`)

| Function | Basis |
|----------|-------|
| `solar_declination_deg(day_of_year)` | Spencer's Fourier-series approximation (accurate ~0.01°), `day_of_year ∈ [1, 366]` |
| `local_solar_time_from_ltan(ltan_hours)` | identity with a documented approximation — a sun-sync orbit holds ~constant local solar time along the daylit track, so LTAN ≈ local solar time at any target on the pass (target-longitude and within-pass nodal drift neglected, < a few minutes for LEO) |
| `solar_zenith_angle_rad(lat, day_of_year, local_solar_time_hr)` | standard declination/hour-angle spherical-astronomy formula |

These feed the reflective-source illumination path (solar zenith) and the
day/night feasibility of reflective-band scenarios. All raise
`SolarGeometryError` on out-of-range inputs.

---

## 7. Assumptions and what is NOT modeled (v1)

**Assumptions:** spherical Earth (two fixed radii, §1); circular orbits only (no
eccentricity); J2-only geopotential (no higher zonal/tesseral harmonics);
non-rotating Earth for ground-track speed; plane-of-date solar geometry.

**Deferred to v2** (consistent with RADIANT_Scope_Decisions.md):
- Ellipsoidal / geoid Earth model (a single WGS-84 ellipsoid replacing the two
  spherical radii of §1).
- Earth-rotation correction to ground-track speed (latitude- and direction-
  dependent true sub-satellite velocity).
- Elliptical orbits, drag decay, and full SGP4/analytic ephemeris.
- Exact repeat-cycle revisit (integer orbit/day resonance) replacing the §5
  first-order coverage estimate.
- Atmospheric refraction of the line of sight near the horizon (also noted in
  RADIANT_Atmosphere.md §11).

---

## 8. How the rest of RADIANT consumes this

- **Public API:** `Sensor.set_ground_velocity_from_orbit()` → `ground_track_speed_m_s`
  → `platform.ground_velocity_m_s` (identity-grouped with `geometry.ground_speed_m_s`,
  RADIANT_Parameter_System.md §Consistency-Groups).
- **Performance metrics:** `performance/gsd.py` (`SceneGeometry.gsd_m`),
  `ground_range.py` (`SceneGeometry.ground_range_m`), `swath_width.py`,
  `access_rate.py`, and the diffraction-limit ground projection all build on
  `SceneGeometry` and the orbital functions.
- **Atmosphere:** `LineOfSightGeometry` (slant range, airmass, Earth-intercept)
  is published by SourceStage and consumed by AtmosphereStage (§3).

Nothing here is a chain stage; these are pure geometry/physics helpers invoked by
the API/metric layer, consistent with the Rule-6 separation (geometry is
configuration-time, not a propagating `ChainState` quantity —
RADIANT_Signal_Chain_Architecture.md §6).
