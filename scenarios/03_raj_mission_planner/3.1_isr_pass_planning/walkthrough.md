# Scenario 3.1 — Orbit Geometry & Pass Planning

**Persona:** Raj, collection planner tasking a sun-synchronous imager.
**Question:** From a 600 km orbit, (1) what are the orbit kinematics
(period, ground speed, revisit)? (2) How far off-nadir can I point before
image quality falls below the NIIRS floor, and how wide is my access
corridor? (3) What is my area-coverage rate?

This scenario is the first consumer of the new `radiant.core.orbit`
model, which turns a circular LEO altitude into orbital period, orbital
velocity, and sub-satellite ground-track speed — the last of which the
signal chain cannot compute but `performance.access_rate` needs.

---

## Inputs (mission format — non-RADIANT)

| File | Format | Represents |
|------|--------|-----------|
| `inputs/raj_orbit_sensor.xlsx` | Excel workbook (`MissionConfig` sheet) | Orbit altitude, collection constraints (max slew, NIIRS floor), and the sensor optical/detector configuration |

`inputs/create_spreadsheet.py` regenerates it. Values are transcribed into
the run script as constants so the run is self-contained and reproducible.

---

## What the run produces

`scripts/run_pass_planning.py` (run from the repo root):

1. **Orbit kinematics** from `radiant.core.orbit` — period, orbital
   velocity, ground-track speed, orbits/day.
2. **Off-nadir image-quality table** — GSD, NIIRS, SNR, ground range, and
   swath as pointing sweeps 0 → 45° (the chain's off-nadir-corrected
   metrics via `geometry.path_zenith_rad`), plus the largest angle meeting
   the NIIRS floor.
3. **Access corridor & coverage rate** — the cross-track access half-width
   at the agility limit and at the NIIRS-quality limit, the nadir swath,
   and the area-coverage rate (nadir swath × ground-track speed, composed
   through `performance.access_rate`).
4. **Two figures** — GSD/NIIRS vs off-nadir angle (`fig1`), and the access
   corridor ground-range curve (`fig2`).

---

## Results (600 km orbit)

**Orbit kinematics:**

| Quantity | Value |
|----------|-------|
| Orbital period | 5792 s (96.5 min) |
| Orbital velocity (inertial) | 7.56 km/s |
| Ground-track speed (sub-satellite) | 6.91 km/s |
| Orbits per day | 14.9 |

**Off-nadir image quality:**

| Off-nadir | GSD | NIIRS | SNR | Ground range | Swath |
|-----------|-----|-------|-----|--------------|-------|
| 0° | 0.65 m | 6.76 | 83.2 | 0 km | 5.2 km |
| 15° | 0.68 m | 6.71 | 84.8 | 146 km | 5.4 km |
| 30° | 0.80 m | 6.50 | 86.0 | 312 km | 5.9 km |
| 45° | 1.05 m | 6.10 | 86.6 | 527 km | 7.1 km |

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-07-22). Dominant mover: CU-253 — the 8×-too-large Rayleigh optical depth
was corrected, raising τ and halving `E_sky_scattered` in this 0.45–0.70 µm
reflective band, which trims SNR by 0.7 % at nadir and 4.6 % at 45° (the
scattered-sky term contributed more at longer slant paths, so its removal
flattens the off-nadir SNR rise); CU-267's gas-region blend contributes a
further ≤ 0.2 % τ reduction in this band. CU-224 is not a factor — Planck
emission is negligible at 0.45–0.70 µm.*

- **GSD grows with off-nadir angle** (roughly ∝ 1/cos² through the slant-
  range and projection stretch), dragging NIIRS from 6.76 at nadir to 6.10
  at 45°. The **NIIRS floor of 6.0 is met across the entire 0–45° slew
  range** — the quality limit no longer binds inside the agility envelope.
- **SNR rises slightly** off-nadir — the ground footprint per pixel grows
  faster than the slant-range path loss for this extended sunlit scene, so
  each pixel collects more photons. Image *quality* (NIIRS/GSD) still
  degrades because resolution, not SNR, is the binding term.
- **Coverage:** nadir swath 5.2 km, area-coverage rate **35.9 km²/s**,
  ≈104,000 km² per daylight pass.
- **Key planning insight:** at this configuration the spacecraft can *slew*
  to 45° (527 km cross-track reach) and still *image at spec* over that
  whole range — NIIRS = 6.10 at the 45° agility limit, just above the 6.0
  floor. Agility, not image quality, sets the usable access corridor here;
  a tighter NIIRS floor (or a longer slant path) would reintroduce a
  quality-limited corridor narrower than the slew envelope.

---

## Physics / modeling notes (house rule: explain the non-obvious)

- **Regime = EXTENDED.** The sunlit surface fills the pixel; point-source
  and sub-pixel machinery is unused.
- **Ground-track speed < orbital speed** by the factor R_E/a: the nadir
  point traces a circle of radius R_E while the satellite traces a circle
  of radius a = R_E + h. The model neglects Earth rotation (a few-percent,
  direction-dependent cross-term at LEO) — this is the non-rotating-Earth
  ground speed, adequate for coverage-rate sizing.
- **`access_rate` is composed, not chain-native.** The signal chain has no
  concept of platform velocity, so it cannot produce a coverage rate. The
  orbit model supplies `ground_track_speed_m_s`, which multiplies the
  chain's `swath_width_m` through `performance.access_rate` — the
  scenario stitches the two together. That composition is the gap the
  orbit model was built to close.
- **NIIRS extrapolation warnings** appear at large off-nadir angles (GSD
  above the GIQE-5 calibration range) — the framework's Gap 22 flagging
  fires correctly, and the runner opts into the extrapolated trend via
  `performance.niirs.allow_extrapolated` (CU-178). The NIIRS values in the
  off-nadir tail carry reduced confidence and are read as a relative trend;
  the floor is met across the full 0–45° slew here, so no in-range crossing
  is reported.

---

## Truth anchors for the orbit model

Verified in `src/radiant/core/tests/test_orbit.py` (10 Level-0 tests)
before this scenario consumed the model:

1. 500 km orbit → v = 7.616 km/s, T = 94.5 min (standard LEO figures).
2. ISS ~420 km → T ≈ 92.8 min (published ISS period ~92–93 min).
3. Ground-track speed at 500 km = 7062 m/s = v · R_E/a, and always < v.
4. Period identity T = 2π a / v.
