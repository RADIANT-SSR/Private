# RADIANT Scan & Timing

**Status**: DESIGN TARGET — mostly unimplemented (see Implementation Status below)
**Scope**: Scan modes (stare, pushbroom, whiskbroom, step-stare), timing computation per mode, integration time derivation and consistency, ground-velocity computation, and the motion parameters that feed the spatial PSF cascade.
**Sister documents**: RADIANT_Conventions.md, RADIANT_Spatial_Complete.md, RADIANT_Detector_Complete.md, RADIANT_Parameter_System.md

> **Implementation status (2026-07-11, Gap 74).** The `TimingState` /
> `ScanTimingStage` subsystem described below is a design target — there is no
> `ScanMode` enum, no line-rate/frame-rate derivation, and no cross-track or
> target-motion smear kernel. **What is implemented** is the single feasibility
> guard the capability audit flagged as silently missing (Gap 74, minimum
> slice): the pushbroom/TDI per-line **dwell-time** constraint. When a
> `platform.ground_velocity_m_s` is set, `PerformanceStage` computes
> `t_dwell = GSD_along / v_ground`, stores it as the `max_integration_time_s`
> metric, and warns (`UserWarning`) when `spectral_integration.integration_time_s`
> exceeds it — the along-track image then smears more than one ground sample per
> integration, so the reported SNR is optimistic and (for TDI) the timing is
> unphysical. Implementation: `radiant.performance.scan_feasibility`
> (`scan_feasibility()` → `ScanFeasibility`), wired in
> `performance/stage.py:_compute_scan_feasibility`. The full subsystem remains
> future work; §84's `t_int ≤ line_period · n_tdi` form reduces to
> `t_int ≤ t_dwell` when `line_period = GSD_along / v_ground` (see §3.2).

---

## 1. Design Philosophy

Scan and timing live in their own module because they are the bridge between *platform parameters* (orbit, altitude, velocity) and *spatial parameters* (smear, t_int, dwell). Three rules:

1. **Scan mode is a knob, not a code path.** Stare, pushbroom, whiskbroom, step-stare are all expressed as a single `ScanMode` enum. The downstream chain (spatial, detector, readout) does not branch on scan mode; it consumes the `TimingState` outputs and computes whatever is appropriate.
2. **Integration time is a derivable, in a consistency group.** A user may specify `t_int` directly, *or* specify a related quantity (line rate, frame rate, dwell time, duty cycle) and let RADIANT solve. The consistency group rules from RADIANT_Parameter_System.md handle conflicts.
3. **Ground velocity is computed once, not assumed.** Whether the user gives orbital elements, an altitude+inclination shortcut, or a hand-typed `m/s`, the platform velocity at the surface is computed and stored on `TimingState` so every consumer (smear, dwell, line rate) reads from the same number.

---

## 2. The `TimingState` Contract

```python
@dataclass(frozen=True)
class TimingState:
    scan_mode: ScanMode                          # STARE | PUSHBROOM | WHISKBROOM | STEP_STARE
    derivation_chain: tuple[str, ...]

    # ---- Time ------------------------------------------------------------
    integration_time_s: float
    frame_period_s: float | None                 # STARE / STEP_STARE
    line_period_s: float | None                  # PUSHBROOM
    dwell_time_per_pixel_s: float | None         # WHISKBROOM
    settle_time_s: float | None                  # STEP_STARE
    duty_cycle: float                            # t_int / frame_period (always populated)

    # ---- Velocity --------------------------------------------------------
    ground_velocity_m_s: float                   # along-track ground projection
    ground_velocity_source: VelocitySource       # ORBIT | AIRCRAFT | OVERRIDE
    altitude_m: float                            # echoed from platform for convenience

    # ---- Motion to spatial cascade ---------------------------------------
    platform_smear_m: tuple[float, float]        # (along, cross) at FPA
    target_motion_smear_m: tuple[float, float]   # at FPA, includes TDI factor
    n_tdi_realized: int                          # echoed; affects target smear
```

`TimingState` is built by `ScanTimingStage`, which sits between source/atmosphere/optics and the detector — temporally, it has to be available before the detector signal is computed (because t_int multiplies the photon flux), but logically it needs `optics.focal_length_m` and `detector.pixel_pitch_x_um` to compute smear at the FPA. The architecture handles this by running `ScanTimingStage` after `OpticsStage` and before `DetectorStage`.

---

## 3. Scan Modes

```python
class ScanMode(StrEnum):
    STARE      = "stare"
    PUSHBROOM  = "pushbroom"
    WHISKBROOM = "whiskbroom"
    STEP_STARE = "step_stare"
```

### 3.1 Stare (framing sensor)

A 2D area array integrates for `t_int`, then reads out, then waits, then integrates again. The image footprint is fixed during integration (modulo platform jitter and orbital motion).

**Timing relations:**
```
frame_period_s ≥ t_int + readout_time_s
duty_cycle      = t_int / frame_period
frame_rate_hz   = 1 / frame_period
```

**Signal:** signal accumulates during `t_int` only. Smear comes from platform motion across the integration time, not across the frame period.

**Required parameters:** `t_int`, `frame_period` *or* `frame_rate`. Both `frame_period` and `frame_rate` set is a consistency-group conflict.

### 3.2 Pushbroom

A 1D linear array (or a 2D array operating as N parallel pushbroom lines via TDI) sweeps through the scene as the platform moves. Each across-track column is one detector; lines are built up in time.

**Timing relations:**
```
ifov_along_rad   = pixel_pitch_y / focal_length
gsd_along_m      = ifov_along_rad · slant_range
line_period_s    = gsd_along_m / ground_velocity_m_s     # one ground sample per line
t_int            ≤ line_period_s · n_tdi                  # t_int can be longer w/ TDI
duty_cycle       = t_int / line_period_s
```

**TDI in pushbroom:** N_TDI stages each integrate for `line_period_s`, accumulating charge as the image sweeps across them. The effective integration time per ground sample is `N_TDI × line_period_s`. The detector module handles charge accumulation; the timing module handles the per-stage period.

**Required parameters:** `t_int` *or* derivation from `ground_velocity` + `gsd_along` + `n_tdi`. The framework prefers derivation when geometry is fully specified.

### 3.3 Whiskbroom

A small detector (often 1×1 or a small linear array) is scanned across the FOV by a moving mirror. Each pixel dwells on a ground sample for `dwell_time_per_pixel`, then steps to the next.

**Timing relations:**
```
n_pixels_cross    = (fov_cross_rad / ifov_cross_rad)
scan_period_s     = scan_line_time_s = dwell_time_per_pixel · n_pixels_cross
line_period_s     = gsd_along_m / ground_velocity_m_s
n_lines_per_scan  = scan_period_s / line_period_s         # how many along-track samples drift past during one cross-track sweep
t_int             = dwell_time_per_pixel                  # by definition
```

**Constraint:** `n_lines_per_scan ≤ 1`, otherwise the cross-track sweep takes longer than a ground line and the framework warns about "scan-rate-limited along-track gaps."

**Required parameters:** `dwell_time_per_pixel`, `fov_cross`, and `gsd_along` (or platform velocity).

### 3.4 Step-stare

Stare-mode framing on a pointable mount: the sensor stares for `t_int`, reads out, slews to the next mosaic position, settles, and stares again.

**Timing relations:**
```
frame_period_s = t_int + readout_time_s + slew_time_s + settle_time_s
revisit_time_s = n_mosaic_positions · frame_period_s
duty_cycle     = t_int / frame_period_s                 (typically very low)
```

**Smear during settle:** if `settle_time_s` is short relative to settle dynamics, residual oscillation appears as additional jitter. The framework adds `platform.jitter_rms_during_settle` (default 0) into the jitter total when `scan_mode = step_stare`.

**Required parameters:** `t_int`, `slew_time_s`, `settle_time_s`, `n_mosaic_positions` (for revisit reporting only — does not affect per-frame metrics).

---

## 4. Integration Time Derivation (Consistency Group)

`scan.integration_time_consistency_group` contains:

```
{ t_int_s, frame_period_s, frame_rate_hz, line_period_s,
  duty_cycle, ground_velocity_m_s, gsd_along_m, n_tdi }
```

The user specifies any compatible subset; RADIANT solves the rest. Conflicts raise `ConsistencyGroupConflict` with a list of constraints and an explanation of which one to drop.

**Derivation modes:**
1. **Direct**: user specifies `t_int_s`. Used as-is. Other timing quantities are computed for reporting.
2. **From scan**: user specifies `scan_mode` and the geometry; RADIANT computes `t_int` per the scan-mode equations in §3.
3. **From frame rate**: user specifies `frame_rate_hz` and `duty_cycle`; `t_int = duty_cycle / frame_rate_hz`.
4. **Mixed**: user specifies a subset that determines `t_int` uniquely; RADIANT solves.

If `scan.integration_time_mode = "auto"` (default), RADIANT picks the highest-confidence derivation available, in the order Direct > From scan > From frame rate. The choice is recorded in `derivation_chain`.

---

## 5. Ground Velocity

```python
class VelocitySource(StrEnum):
    ORBIT    = "orbit"
    AIRCRAFT = "aircraft"
    OVERRIDE = "override"
```

### 5.1 Orbital

For LEO and above, the user supplies `platform.orbit_altitude_km` and `platform.orbit_inclination_deg` (or a full set of Keplerian elements; the framework only uses semi-major axis and inclination for ground velocity).

```
v_orbit  = √(μ_earth / (R_earth + altitude))           # circular orbit
v_ground = v_orbit · (R_earth / (R_earth + altitude)) · cos(inclination_effect)
```

`cos(inclination_effect)` reduces the along-track ground velocity for non-equatorial orbits relative to the surface beneath, accounting for Earth rotation. For a polar orbit at LEO, this is ~6800 m/s. For a sun-synchronous orbit at 705 km, ~6750 m/s.

For higher orbits the calculation still applies; geostationary returns ~0 (and ground velocity is set to a logged 0.0).

### 5.2 Aircraft

User supplies `platform.airspeed_m_s` directly (or in `kts` with `_kts` suffix). For aircraft, ground velocity ≈ true airspeed projected to the ground; cross-wind effects are neglected in v1.

### 5.3 Override

User supplies `platform.ground_velocity_m_s` directly. Used as-is; no orbital or aircraft computation. Useful for unit tests, ground sensors (`= 0`), and hypothetical platforms.

The chosen `VelocitySource` is recorded on `TimingState.ground_velocity_source` so a downstream metric can report which assumption produced the smear.

---

## 6. Motion Parameters Feeding the Spatial Model

The timing module computes the *physical* smear distances at the FPA, in meters, for both along-track and cross-track. The spatial cascade then convolves the PSF with rectangles of those widths (per RADIANT_Spatial_Complete.md §6).

### 6.1 Platform smear

```
v_image_m_per_s = ground_velocity_m_s · focal_length_m / slant_range_m
platform_smear_along_m = v_image_m_per_s · t_int_s
platform_smear_cross_m = 0       (unless dual-axis platform; rare)
```

### 6.2 Target motion smear

```
v_target_image_x = target.velocity_x_m_s · focal_length / slant_range
v_target_image_y = target.velocity_y_m_s · focal_length / slant_range
t_int_eff        = n_tdi · t_int_s   if pushbroom_with_TDI else t_int_s
target_smear_x_m = v_target_image_x · t_int_eff
target_smear_y_m = v_target_image_y · t_int_eff
```

In **tracked** mode (per RADIANT_Spatial_Complete.md §8), the platform smear is suppressed for the target PSF and applied to the background PSF only; the target-motion smear above still applies because it represents target motion *relative to the tracker*.

### 6.3 Jitter

Jitter does not depend on scan mode or velocity; the timing module passes through `platform.jitter_rms_urad` to the spatial cascade unchanged. (Step-stare mode adds a settle-time jitter component as noted in §3.4.)

### 6.4 What the spatial cascade receives

`TimingState.platform_smear_m` and `TimingState.target_motion_smear_m` are tuples of `(along_m, cross_m)` at the FPA. The spatial cascade reads them and convolves rectangles. No additional unit conversion or geometry math happens in the spatial module — that's why this module exists.

---

## 7. Parameter Inventory

All parameters under `scan.*` and `platform.*`.

### 7.1 Scan

Parameter types, defaults, units, and bounds are the canonical [Parameter Reference](../guides/parameter_reference.md) (auto-generated from the schema — the single source of truth, Rule 27). Which scan mode each parameter serves:

- `scan.t_int_s` — direct integration-time mode.
- `scan.frame_period_s`, `scan.frame_rate_hz` — stare / step-stare.
- `scan.line_period_s` — pushbroom.
- `scan.dwell_time_per_pixel_s` — whiskbroom.
- `scan.settle_time_s`, `scan.slew_time_s`, `scan.n_mosaic_positions` — step-stare.
- `scan.readout_time_s` — analog readout overhead.
- `scan.fov_cross_rad` — whiskbroom; derived from array width.

### 7.2 Platform / velocity

Parameter types, defaults, units, and bounds are the canonical [Parameter Reference](../guides/parameter_reference.md) (auto-generated from the schema — the single source of truth, Rule 27). Which velocity source each parameter serves:

- `platform.velocity_source` — inferred when unset (`orbit` / `aircraft` / `override`).
- `platform.orbit_altitude_km`, `platform.orbit_inclination_deg` — orbit source.
- `platform.airspeed_m_s` — aircraft source.
- `platform.ground_velocity_m_s` — override source.
- `platform.slant_range_m` — from altitude + look angle.
- `platform.look_angle_deg` — nadir-pointing default.

### 7.3 Target motion

Parameter types, defaults, units, and bounds are the canonical [Parameter Reference](../guides/parameter_reference.md) (auto-generated from the schema — the single source of truth, Rule 27). The parameters are `target.velocity_x_m_s`, `target.velocity_y_m_s`, and `target.tracked`.

---

## 8. Validation

| Check | Bound |
|-------|-------|
| `t_int_s > 0` | hard |
| `t_int_s ≤ frame_period_s` (or `line_period_s · n_tdi`) | hard |
| `0 ≤ duty_cycle ≤ 1` | hard |
| `ground_velocity_m_s ≥ 0` | hard |
| Whiskbroom: `n_lines_per_scan ≤ 1` | soft warn |
| Step-stare: `revisit_time` reported | informational |
| `platform.altitude_m > 0` | hard |
| Consistency-group conflicts | hard, with diagnostic |

---

## 9. Out of Scope for v1

- Stare-while-scan modes (compound scan).
- Variable line rate within a single acquisition (constant per scenario).
- Asynchronous detector + scanner clock skew.
- Cross-wind drift correction in airborne ground velocity.
- Earth curvature corrections to slant range below the spherical-Earth threshold (handled in atmosphere module per `RADIANT_Atmosphere.md` §4.2).

---
