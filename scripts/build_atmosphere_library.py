"""Build the shipped atmosphere library from the real MODTRAN run set.

Repackages the MODTRAN 6 run matrix (tracked in git under
``modtran/real_runs/`` since 2026-08-02) into the committed NPZ library under
``data/atmospheres/`` per ``docs/archive/MODTRAN_Run_Matrix_Plan.md`` §7.2.

Families produced (see ``data/atmospheres/MANIFEST.md`` for the full
design record):

- ``profiles/<profile>.npz``          — A1–A6 nadir full columns, one per
  standard atmosphere, ``TabulatedAtmosphere.from_npz`` format. The
  us_standard and tropical files carry real downwelling sky radiance
  (``atm_emission_down``) from the up-looking H2/H4 runs at the 48.2°
  diffusivity angle; the other four profiles have no H-run and omit the
  key (loader default: zero downwelling).
- ``us_standard_zenith_fan/``         — A1 + B1–B3 as an
  ``InterpolatedAtmosphere`` 1-D grid over ``path_zenith_rad``
  (0/30/45/60°), each with the H2 downwelling attached.
- ``midlat_summer_ladders/``          — C1–C6 (sensor 35 km) and
  A3 + G1–G5 (sensor 100 km) as a 2-D grid over
  ``(sensor_altitude_m, target_altitude_m)``; the 100 km states are
  duplicated at a 40,000 km sensor node so every orbital sensor altitude
  falls inside the interpolation hull (vacuum above TOA — exact).
- ``midlat_summer_boost_ladder/``     — A3 + G1–G5 + G7–G11 (sensor 100 km)
  as a 2-D grid over ``(sensor_altitude_m, target_altitude_m)`` spanning
  target 0–100 km; the 100 km rung is the **synthesized** exact vacuum
  node (τ ≡ 1, L_path ≡ 0), closing the hull to the Gap 95 exo handoff.
  Orbital 40,000 km duplicate as for the ladders (boost plan §4.1/§4.2).
- ``midlat_summer_boost_offnadir/``   — A3/G3/G5/G9/G11 (nadir), I1–I4+G6
  (45°), I5–I9 (60°) plus the synthesized 100 km vacuum rung at every
  zenith, as a 3-D grid over ``(sensor_altitude_m, target_altitude_m,
  path_zenith_rad)``; zenith interpolates in airmass sec(θ) space
  (CU-160). Orbital duplicate (boost plan §4.3).
- ``midlat_summer_sensor_ladder/``    — F2 (3 km) + J1/J2 (10/20 km) +
  C1 (35 km) + A3 (100 km) as a 1-D grid over ``sensor_altitude_m``,
  ground target nadir; orbital 40,000 km duplicate (boost plan §4.5).
- ``midlat_summer_uplooking_ladder/`` — K1–K5 (ground sensor looking
  **up** a vertical partial column to targets at 1/3/5/10/20 km) as a 1-D
  grid over ``target_altitude_m``, plus the synthesized exact
  zero-length node at 0 km. This is the **up-looking** family
  (Geometry-Flexibility Phase 2, GF-10): its radiance product is the
  *downward* path radiance ``path_radiance_toward_lower``, a different
  physical quantity from every other family's upwelling ``path_radiance``,
  so it uses a different NPZ key and is refused by the down-looking
  loaders. See :mod:`radiant.atmosphere.interpolated` and the MANIFEST.
- ``midlat_summer_uplooking_zenith_fan/`` — the batch-2 N block plus the
  K ladder as a 2-D up-looking grid over
  ``(target_altitude_m, path_zenith_rad)``: targets 0/1/3/5/10/20 km ×
  lower-endpoint zenith 0° / 48.2° / 60° (sec ζ = 1 / 1.4999 / 2). The
  zenith axis interpolates in sec-space (CU-160); it is the axis the
  vertical-only up-looking refusal was waiting for (GF-10).
- ``midlat_summer_sst_column_fan/``   — the batch-2 M block plus H5: a
  ground observer's **full column to space** (0 → 100 km) as a 1-D
  up-looking grid over ``path_zenith_rad`` at sec ζ = 1/1.5/2/3/4/5. The
  SST anchor family. M6–M8 (85/88/89.5°) are ``dev_only`` in the run
  matrix and are deliberately NOT shipped — the sec-space mapping is
  unvalidated past the 88.8° airmass ceiling.
- ``midlat_summer_uplooking_sensor_ladder/`` — the batch-2 P block plus
  H5: an **elevated** observer's full column to space at the 48.2°
  diffusivity angle, as a 1-D up-looking grid over ``sensor_altitude_m``
  (0/1/5/10/20/29/50 km) plus the synthesized zero-length node at the
  100 km atmosphere top. These are the same runs the CU-181 downwelling
  ladder is built from.
- ``midlat_summer_upwelling_offnadir/`` — the batch-2 O block plus J1/A3/I5:
  a down-looking **ground-target** grid over
  ``(sensor_altitude_m, path_zenith_rad)`` — sensor 10/100 km (+ the
  orbital duplicate) × LOS zenith 0° / 48.2° / 60°. The upwelling
  reciprocals of the up-looking columns, and the emission-height anchors
  CU-224's down-looking thermal term needs.
- ``validation/``                     — off-grid single points (C7, G6 at
  45°; H1 nadir up-looking; O1/O2, the 1 km and 5 km nadir upwelling
  anchors that have no zenith column and so cannot join the rectangular
  O grid) kept as data but NOT interpolation nodes.
  K6 (the up-looking 45° coupling anchor) is deliberately **not** shipped:
  it is a holdout, consumed only by the ``skipif``-guarded characterization
  test against the staged tape7.

Downwelling (``atm_emission_down``, CU-181). Every down-looking
midlat_summer node carries the up-looking 48.2° diffusivity-angle sky
radiance **at that node's target altitude**, interpolated from the
measured rung ladder H5 (0 km) + P1–P6 (1/5/10/20/29/50 km) by
:func:`scripts.downwelling_altitude.downwelling_at_altitude`. Before
batch 2 the single ground-level H5 value was attached to every node
regardless of target altitude; ground-target nodes are therefore
unchanged and only elevated-target nodes move.

Spectral treatment: every array is slit-degraded with a triangular
FWHM = 5 cm⁻¹ kernel on the native uniform 1 cm⁻¹ wavenumber grid, then
decimated to 2 cm⁻¹ sampling, and stored float32 (test fixtures stay at
full resolution elsewhere; this library feeds band-integrating sensor
metrics, which are insensitive to the slit — plan §7.2).

Usage::

    python scripts/build_atmosphere_library.py

Deterministic: same input files → byte-identical NPZ content arrays.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from radiant.atmosphere.interpolated import (  # noqa: E402
    FAMILY_DIRECTION_KEY,
    UPLOOKING_RADIANCE_KEY,
)
from radiant.atmosphere.modtran import Tape7Reader  # noqa: E402
from scripts.downwelling_altitude import downwelling_at_altitude  # noqa: E402

REAL_RUNS = REPO / "modtran" / "real_runs"
OUT_ROOT = REPO / "src" / "radiant" / "data" / "tables" / "atmospheres"

# Triangular slit: FWHM = 5 samples (5 cm⁻¹ on the 1 cm⁻¹ grid),
# base = 9 samples. Decimate by 2 afterwards (2 cm⁻¹ sampling).
_KERNEL = np.array([1, 2, 3, 4, 5, 4, 3, 2, 1], dtype=np.float64)
_KERNEL /= _KERNEL.sum()
_EDGE = len(_KERNEL) // 2  # samples lost per edge after 'valid' convolution
_DECIMATE = 2

# Deg → rad without importing math for one constant.
_DEG = np.pi / 180.0

# Solar geometry shared by EVERY shipped down-looking run (run matrix:
# solar_zenith_deg = 30, solar_azimuth_deg = 0 on all A/B/C/G rows).
SOLAR_ZENITH_RAD = 30.0 * _DEG
SOLAR_AZIMUTH_RAD = 0.0


def _full_geometry(sensor_km: float, target_km: float, path_zenith_rad: float) -> dict[str, float]:
    """All five ``AtmosphericGeometry`` fields for a run (CU-167 / boost plan §4.6).

    Recording the constant fields (not just the interpolation axes) lets
    ``InterpolatedAtmosphere``'s non-axis mismatch check compare queries
    against the RECORDED run geometry instead of silently substituting —
    e.g. an airborne-sensor query against the 100 km zenith fan, or a
    solar zenith other than the 30° every shipped run used, now warns.
    """
    return {
        "sensor_altitude_m": sensor_km * 1000.0,
        "target_altitude_m": target_km * 1000.0,
        "path_zenith_rad": path_zenith_rad,
        "solar_zenith_rad": SOLAR_ZENITH_RAD,
        "solar_azimuth_rad": SOLAR_AZIMUTH_RAD,
    }


# run id -> profile name for the Block A anchors.
PROFILE_RUNS: dict[str, str] = {
    "A1": "us_standard",
    "A2": "tropical",
    "A3": "midlat_summer",
    "A4": "midlat_winter",
    "A5": "subarctic_summer",
    "A6": "subarctic_winter",
}

# profile -> up-looking H-run supplying real downwelling sky radiance
# (48.2° diffusivity angle). H5 (midlat_summer) landed with the boost
# expansion (plan §4.4); the remaining three profiles have no H-run.
DOWNWELLING_RUNS: dict[str, str] = {
    "us_standard": "H2",
    "tropical": "H4",
    "midlat_summer": "H5",
}

# CU-181: measured midlat_summer downwelling rung ladder — the sky radiance an
# observer at each altitude sees looking up at the 48.2° diffusivity angle.
# H5 is the ground rung (already shipped); P1–P6 are the batch-2 P block, run
# at the identical profile/aerosol/visibility/angle with only the lower
# endpoint lifted. Ordered ascending in altitude, which
# ``downwelling_at_altitude`` requires. run -> observer altitude [km].
DOWNWELLING_RUNGS: dict[str, float] = {
    "H5": 0.0,
    "P1": 1.0,
    "P2": 5.0,
    "P3": 10.0,
    "P4": 20.0,
    "P5": 29.0,
    "P6": 50.0,
}

# Zenith fan (us_standard full column): run -> RADIANT LOS zenith [rad].
ZENITH_FAN: dict[str, float] = {
    "A1": 0.0,
    "B1": 30.0 * _DEG,
    "B2": 45.0 * _DEG,
    "B3": 60.0 * _DEG,
}

# Ladders (midlat_summer, nadir): run -> (sensor km, target km).
LADDER: dict[str, tuple[float, float]] = {
    "C1": (35.0, 0.0),
    "C2": (35.0, 1.0),
    "C3": (35.0, 5.0),
    "C4": (35.0, 10.0),
    "C5": (35.0, 20.0),
    "C6": (35.0, 29.0),
    "A3": (100.0, 0.0),
    "G1": (100.0, 1.0),
    "G2": (100.0, 5.0),
    "G3": (100.0, 10.0),
    "G4": (100.0, 20.0),
    "G5": (100.0, 29.0),
}
# Sensor node duplicated for the orbital hull (plan §7.2): every
# 100 km state is re-emitted at this sensor altitude — the added path is
# vacuum, so interpolating between identical values is exact.
ORBITAL_NODE_KM = 40_000.0

# Boost ladder (midlat_summer, nadir, sensor 100 km): run -> target km.
# Extends the 0–29 km ladder rungs with G7–G11 (35–80 km); the 100 km
# rung is the synthesized vacuum node below (boost plan §4.1).
BOOST_LADDER: dict[str, float] = {
    "A3": 0.0,
    "G1": 1.0,
    "G2": 5.0,
    "G3": 10.0,
    "G4": 20.0,
    "G5": 29.0,
    "G7": 35.0,
    "G8": 40.0,
    "G9": 50.0,
    "G10": 60.0,
    "G11": 80.0,
}
BOOST_SENSOR_KM = 100.0

# Synthesized exact vacuum rung: target at the atmosphere top, τ ≡ 1,
# L_path ≡ 0 — a physical identity (zero absorbing column above), NOT
# fabricated data. Closes the interpolation hull to the Gap 95 exo
# handoff at 100 km (boost plan §4.2).
VACUUM_TARGET_KM = 100.0

# Off-nadir boost grid (midlat_summer, sensor 100 km): run -> (target km,
# zenith deg). Nadir column reuses the boost-ladder tape7s; 45°/60°
# columns are the I-block + G6 (boost plan §4.3). Synthesized vacuum rung
# added at every zenith column below.
BOOST_OFFNADIR: dict[str, tuple[float, float]] = {
    "A3": (0.0, 0.0),
    "G3": (10.0, 0.0),
    "G5": (29.0, 0.0),
    "G9": (50.0, 0.0),
    "G11": (80.0, 0.0),
    "I1": (0.0, 45.0),
    "G6": (10.0, 45.0),
    "I2": (29.0, 45.0),
    "I3": (50.0, 45.0),
    "I4": (80.0, 45.0),
    "I5": (0.0, 60.0),
    "I6": (10.0, 60.0),
    "I7": (29.0, 60.0),
    "I8": (50.0, 60.0),
    "I9": (80.0, 60.0),
}
OFFNADIR_ZENITHS_DEG: tuple[float, ...] = (0.0, 45.0, 60.0)

# Sensor ladder (midlat_summer, ground target, nadir): run -> sensor km.
# Closes the airborne-sensor hull for ground targets (boost plan §4.5);
# A3 (100 km) is duplicated at the orbital node as for the ladders.
SENSOR_LADDER: dict[str, float] = {
    "F2": 3.0,
    "J1": 10.0,
    "J2": 20.0,
    "C1": 35.0,
    "A3": 100.0,
}

# Up-looking partial-column ladder (midlat_summer, GROUND sensor, vertical):
# run -> target km.  The K block (plan §8.3 batch 1) is the first up-looking
# run family: H1 = 0 is the path's LOWER endpoint, so MODTRAN's Card-3 ANGLE
# is the lower-endpoint zenith unchanged (CU-065; confirmed by the delivered
# Card-3 echo).  The radiance MODTRAN reports is the radiance *at the
# observer*, i.e. travelling DOWNWARD out of the segment's lower end — the
# ``L_toward_lower`` product of ``atmosphere.segments``, not the upwelling
# ``path_radiance`` every other family carries.
UPLOOKING_LADDER: dict[str, float] = {
    "K1": 1.0,
    "K2": 3.0,
    "K3": 5.0,
    "K4": 10.0,
    "K5": 20.0,
}
UPLOOKING_SENSOR_KM = 0.0

# Synthesized exact zero-length node for the up-looking ladder: a target at
# the sensor's own altitude has no column between the endpoints, so τ ≡ 1 and
# L ≡ 0 exactly.  Same G-block principle as the boost ladder's 100 km rung (a
# vacuum identity, never a MODTRAN run) — but at the OTHER end of the axis,
# because an up-looking ladder's path GROWS with target altitude: τ → 1 is the
# h_tgt → h_sensor limit, not the h_tgt → TOA limit.  Closes the hull so a
# target below the 1 km bottom rung interpolates instead of being refused.
UPLOOKING_ZERO_LENGTH_TARGET_KM = 0.0

# --- Batch-2 families (2026-08-02 delivery) --------------------------------

# N block + K block: the up-looking zenith fan. run -> (target km, zenith deg).
# The rectangular grid InterpolatedAtmosphere needs is targets {0,1,3,5,10,20}
# km × lower-endpoint zenith {0, 48.2, 60}° (sec ζ = 1 / 1.4999 / 2); the ζ = 0
# column is the delivered K ladder (Rule 27 — not re-run), the other two are
# N1–N5 and N6–N10. Three sec rungs is the minimum that can *test* linearity in
# sec rather than assume it (CU-160). The target = 0 row at every zenith is the
# synthesized zero-length identity, added below.
UPLOOKING_ZENITH_FAN: dict[str, tuple[float, float]] = {
    "K1": (1.0, 0.0),
    "K2": (3.0, 0.0),
    "K3": (5.0, 0.0),
    "K4": (10.0, 0.0),
    "K5": (20.0, 0.0),
    "N1": (1.0, 48.2),
    "N2": (3.0, 48.2),
    "N3": (5.0, 48.2),
    "N4": (10.0, 48.2),
    "N5": (20.0, 48.2),
    "N6": (1.0, 60.0),
    "N7": (3.0, 60.0),
    "N8": (5.0, 60.0),
    "N9": (10.0, 60.0),
    "N10": (20.0, 60.0),
}
UPLOOKING_FAN_ZENITHS_DEG: tuple[float, ...] = (0.0, 48.2, 60.0)

# M block + H5: the SST full-column fan, ground observer → 100 km.
# run -> lower-endpoint zenith [deg]; sec ζ = 1 / 1.5 / 2 / 3 / 4 / 5.
# M6–M8 (85/88/89.5°, sec 11.5/28.7/114.6) are ``dev_only`` in the run matrix
# and are NOT shipped: they sit outside the uniform sec ladder and, for M7/M8,
# at or past InterpolatedAtmosphere's 88.8° airmass ceiling, where the sec-space
# mapping is unvalidated. They are physics anchors, not library nodes.
SST_COLUMN_FAN: dict[str, float] = {
    "M1": 0.0,
    "H5": 48.2,
    "M2": 60.0,
    "M3": 70.529,
    "M4": 75.522,
    "M5": 78.463,
}
SST_TARGET_KM = 100.0

# P block + H5: the elevated-observer full-column ladder at the 48.2°
# diffusivity angle. run -> observer (lower endpoint) altitude [km]. Same runs
# as DOWNWELLING_RUNGS — there they supply another family's ``atm_emission_down``,
# here they are library nodes in their own right (run matrix P-row note).
UPLOOKING_SENSOR_LADDER: dict[str, float] = dict(DOWNWELLING_RUNGS)
UPLOOKING_SENSOR_LADDER_ZENITH_DEG = 48.2

# O block + J1/A3/I5: the down-looking upwelling grid over
# (sensor altitude, LOS zenith) for a GROUND target.
# run -> (sensor km, zenith deg). The zenith is the run matrix's
# ``path_zenith_deg_radiant`` — the LOWER-endpoint (ground) zenith, the same
# convention every other family records (ex-CU-223); MODTRAN's Card-3 ANGLE for
# these rows is 180° − that, which is why the deck echoes read 180/131.8/120.
# O1 (1 km) and O2 (5 km) are nadir-only and have no zenith column, so they
# cannot join this rectangular grid — they ship under validation/ instead.
UPWELLING_OFFNADIR: dict[str, tuple[float, float]] = {
    "J1": (10.0, 0.0),
    "O3": (10.0, 48.2),
    "O4": (10.0, 60.0),
    "A3": (100.0, 0.0),
    "O5": (100.0, 48.2),
    "I5": (100.0, 60.0),
}
UPWELLING_OFFNADIR_ZENITHS_DEG: tuple[float, ...] = (0.0, 48.2, 60.0)
UPWELLING_OFFNADIR_SENSORS_KM: tuple[float, ...] = (10.0, 100.0)

# Self-describing direction marker written into every up-looking NPZ.  The key
# and value come from the runtime module that reads them, so builder and
# loader cannot drift apart (Rule 26: the artifact names its generator, and
# the generator names the contract it writes).
UPLOOKING_MARKERS: dict[str, str] = {FAMILY_DIRECTION_KEY: "up"}

# Off-grid validation points: run -> (sensor km, target km, LOS zenith rad).
# Full five-field geometry is emitted via _full_geometry (CU-167 / §4.6);
# H1 is the up-looking downwelling anchor (sensor at ground, "target" = TOA).
VALIDATION: dict[str, tuple[float, float, float]] = {
    "C7": (35.0, 10.0, 45.0 * _DEG),
    "G6": (100.0, 10.0, 45.0 * _DEG),
    "H1": (0.0, 100.0, 0.0),
    # Batch-2 O block, nadir rungs: matched down-looking partners of the K1/K3
    # up-looking columns. Nadir-only, so they cannot join the rectangular
    # (sensor × zenith) upwelling grid; shipped as data, not as grid nodes.
    "O1": (1.0, 0.0, 0.0),
    "O2": (5.0, 0.0, 0.0),
}


def _degrade(values: np.ndarray) -> np.ndarray:
    """Triangular-slit degrade (5 cm⁻¹ FWHM) + decimate to 2 cm⁻¹.

    Operates on arrays ordered ascending in wavelength — which is
    uniform (descending) in wavenumber, so a symmetric sample-space
    kernel is a proper wavenumber-space slit. 'valid' convolution trims
    ``_EDGE`` samples per end (no edge bias), then every ``_DECIMATE``-th
    sample is kept.
    """
    smoothed = np.convolve(values, _KERNEL, mode="valid")
    return smoothed[::_DECIMATE]


def _load_degraded(run: str) -> dict[str, np.ndarray]:
    """Read a staged tape7 and return slit-degraded RADIANT-unit arrays."""
    wl, tau, l_path, _l_ground = Tape7Reader(REAL_RUNS / f"{run}.tp7").to_radiant_units()
    return {
        "wavelength_um": _degrade(wl),  # slit-mean wavelength ≈ decimated grid
        "transmittance": np.clip(_degrade(tau), 0.0, 1.0),
        "path_radiance": np.maximum(_degrade(l_path), 0.0),
    }


def _load_downwelling(run: str) -> np.ndarray:
    """Degraded downwelling sky radiance from an up-looking H-run."""
    _wl, _tau, l_path, _ = Tape7Reader(REAL_RUNS / f"{run}.tp7").to_radiant_units()
    return np.maximum(_degrade(l_path), 0.0)


class _DownwellingLadder:
    """The measured downwelling-vs-altitude ladder for one profile (CU-181).

    Loads the rung runs once and answers ``at(target_km)`` for every node the
    families need. The physics lives in
    :func:`scripts.downwelling_altitude.downwelling_at_altitude`; this class is
    only the MODTRAN-reading shell around it (Rule 19).
    """

    def __init__(self, rungs: dict[str, float]) -> None:
        ordered = sorted(rungs.items(), key=lambda item: item[1])
        self.altitudes_km = np.array([alt for _run, alt in ordered], dtype=np.float64)
        self.runs = [run for run, _alt in ordered]
        self.values = np.vstack([_load_downwelling(run) for run in self.runs])

    def at(self, target_km: float) -> np.ndarray:
        """Downwelling sky radiance [W/m²/sr/µm] at a target altitude [km]."""
        return downwelling_at_altitude(self.altitudes_km, self.values, target_km)


def _vacuum_arrays(wl: np.ndarray, downwelling: np.ndarray) -> dict[str, np.ndarray]:
    """Synthesized vacuum node: τ ≡ 1, L_path ≡ 0 (boost plan §4.2).

    A physical identity (no absorbing column above the atmosphere top),
    not fabricated data. ``atm_emission_down`` is the caller's
    altitude-resolved downwelling at the same node — at the 100 km
    atmosphere top that is the matching identity, exactly zero: an observer
    there has no sky above it (CU-181; before batch 2 this node carried the
    ground-level H5 constant, the entry's worst single case).
    """
    return {
        "wavelength_um": np.asarray(wl, dtype=np.float64),
        "transmittance": np.ones_like(wl),
        "path_radiance": np.zeros_like(wl),
        "atm_emission_down": downwelling,
    }


def _load_uplooking_degraded(run: str) -> dict[str, np.ndarray]:
    """Degraded up-looking segment products from a K-block tape7.

    MODTRAN reports the radiance **at the observer**.  For a K run the
    observer sits at ``H1 = 0``, the path's lower endpoint, so that radiance
    is travelling downward out of the segment — the ``L_toward_lower``
    product of :mod:`radiant.atmosphere.segments`, NOT the upwelling
    ``path_radiance`` every down-looking family stores.  The key is named to
    say so: a down-looking reader asking for ``path_radiance`` gets a missing
    key error instead of a plausible-looking wrong number.

    ``transmittance`` keeps its usual name because τ is reciprocal
    (``RADIANT_Atmosphere.md`` §4.4) — one value per segment, direction-free.
    """
    wl, tau, l_path, _l_ground = Tape7Reader(REAL_RUNS / f"{run}.tp7").to_radiant_units()
    return {
        "wavelength_um": _degrade(wl),
        "transmittance": np.clip(_degrade(tau), 0.0, 1.0),
        UPLOOKING_RADIANCE_KEY: np.maximum(_degrade(l_path), 0.0),
    }


def _uplooking_zero_length_arrays(wl: np.ndarray) -> dict[str, np.ndarray]:
    """Synthesized exact zero-length node: τ ≡ 1, L_toward_lower ≡ 0.

    A target at the sensor's own altitude has no air between the endpoints.
    This is a physical identity, not fabricated data — the up-looking
    counterpart of the boost ladder's synthesized 100 km vacuum rung.
    """
    return {
        "wavelength_um": np.asarray(wl, dtype=np.float64),
        "transmittance": np.ones_like(wl),
        UPLOOKING_RADIANCE_KEY: np.zeros_like(wl),
    }


def _save(
    path: Path,
    arrays: dict[str, np.ndarray],
    geometry: dict[str, float] | None,
    markers: dict[str, str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        key: np.asarray(vals, dtype=np.float32) for key, vals in arrays.items()
    }
    if geometry is not None:
        payload["geometry"] = np.array(geometry, dtype=object)
    for key, value in (markers or {}).items():
        payload[key] = np.array(value)
    np.savez_compressed(path, **payload)
    print(f"  wrote {path.relative_to(REPO)}  ({path.stat().st_size / 1024:.0f} KiB)")


def main() -> int:
    if not REAL_RUNS.exists():
        print(
            f"ERROR: {REAL_RUNS} not found. The real MODTRAN run set is "
            "gitignored local data — stage it before regenerating the library "
            "(see modtran/real_runs/README.md).",
            file=sys.stderr,
        )
        return 1

    print("Profiles (tabulated, one per standard atmosphere):")
    for run, profile in PROFILE_RUNS.items():
        arrays = _load_degraded(run)
        down_run = DOWNWELLING_RUNS.get(profile)
        if down_run is not None:
            arrays["atm_emission_down"] = _load_downwelling(down_run)
        # Geometry is provenance for the tabulated profiles (the loader is
        # geometry-agnostic) but recorded anyway per CU-167 / plan §4.6.
        _save(
            OUT_ROOT / "profiles" / f"{profile}.npz",
            arrays,
            geometry=_full_geometry(100.0, 0.0, 0.0),
        )

    print("Zenith fan (us_standard, interpolated over path_zenith_rad):")
    h2_down = _load_downwelling("H2")
    for run, zenith_rad in ZENITH_FAN.items():
        arrays = _load_degraded(run)
        arrays["atm_emission_down"] = h2_down
        _save(
            OUT_ROOT / "us_standard_zenith_fan" / f"zen{round(zenith_rad / _DEG):02d}.npz",
            arrays,
            geometry=_full_geometry(100.0, 0.0, zenith_rad),
        )

    # Altitude-resolved up-looking 48.2° downwelling — attached to EVERY
    # down-looking midlat_summer family node at that node's TARGET altitude
    # (CU-181; plan §4.4 attached the ground rung alone).
    ms_down = _DownwellingLadder(DOWNWELLING_RUNGS)
    print(
        "Downwelling ladder (CU-181): rungs "
        + ", ".join(
            f"{run}@{alt:g} km" for run, alt in zip(ms_down.runs, ms_down.altitudes_km, strict=True)
        )
    )

    print("Ladders (midlat_summer, interpolated over sensor x target altitude):")
    for run, (sensor_km, target_km) in LADDER.items():
        arrays = _load_degraded(run)
        arrays["atm_emission_down"] = ms_down.at(target_km)  # CU-181
        _save(
            OUT_ROOT / "midlat_summer_ladders" / f"s{sensor_km:05.0f}_t{target_km:02.0f}.npz",
            arrays,
            geometry=_full_geometry(sensor_km, target_km, 0.0),
        )
        if sensor_km == 100.0:
            # Orbital-hull duplicate (identical state; vacuum above TOA).
            _save(
                OUT_ROOT
                / "midlat_summer_ladders"
                / f"s{ORBITAL_NODE_KM:05.0f}_t{target_km:02.0f}.npz",
                arrays,
                geometry=_full_geometry(ORBITAL_NODE_KM, target_km, 0.0),
            )

    print("Boost ladder (midlat_summer, nadir, targets 0-100 km, sensor 100 km + orbital):")
    ref_wl: np.ndarray | None = None
    for run, target_km in BOOST_LADDER.items():
        arrays = _load_degraded(run)
        arrays["atm_emission_down"] = ms_down.at(target_km)
        if ref_wl is None:
            ref_wl = arrays["wavelength_um"]
        for sensor_km in (BOOST_SENSOR_KM, ORBITAL_NODE_KM):
            _save(
                OUT_ROOT
                / "midlat_summer_boost_ladder"
                / f"s{sensor_km:05.0f}_t{target_km:03.0f}.npz",
                arrays,
                geometry=_full_geometry(sensor_km, target_km, 0.0),
            )
    assert ref_wl is not None
    vac = _vacuum_arrays(ref_wl, ms_down.at(VACUUM_TARGET_KM))
    for sensor_km in (BOOST_SENSOR_KM, ORBITAL_NODE_KM):
        _save(
            OUT_ROOT
            / "midlat_summer_boost_ladder"
            / f"s{sensor_km:05.0f}_t{VACUUM_TARGET_KM:03.0f}.npz",
            vac,
            geometry=_full_geometry(sensor_km, VACUUM_TARGET_KM, 0.0),
        )

    print("Off-nadir boost grid (midlat_summer, sensor 100 km, zenith 0/45/60 + orbital):")
    for run, (target_km, zenith_deg) in BOOST_OFFNADIR.items():
        arrays = _load_degraded(run)
        arrays["atm_emission_down"] = ms_down.at(target_km)
        for sensor_km in (BOOST_SENSOR_KM, ORBITAL_NODE_KM):
            _save(
                OUT_ROOT
                / "midlat_summer_boost_offnadir"
                / f"s{sensor_km:05.0f}_t{target_km:03.0f}_z{zenith_deg:02.0f}.npz",
                arrays,
                geometry=_full_geometry(sensor_km, target_km, zenith_deg * _DEG),
            )
    # Synthesized 100 km vacuum rung at EVERY zenith column (plan §4.2,
    # widened 2026-07-19): the identity holds at all zeniths, so the
    # 80–100 km band is inside the hull off-nadir too.
    for zenith_deg in OFFNADIR_ZENITHS_DEG:
        for sensor_km in (BOOST_SENSOR_KM, ORBITAL_NODE_KM):
            _save(
                OUT_ROOT
                / "midlat_summer_boost_offnadir"
                / f"s{sensor_km:05.0f}_t{VACUUM_TARGET_KM:03.0f}_z{zenith_deg:02.0f}.npz",
                vac,
                geometry=_full_geometry(sensor_km, VACUUM_TARGET_KM, zenith_deg * _DEG),
            )

    print("Sensor ladder (midlat_summer, ground target, nadir, 3-100 km + orbital):")
    for run, sensor_km in SENSOR_LADDER.items():
        arrays = _load_degraded(run)
        # Ground target on every rung, so the CU-181 ladder returns the ground
        # rung (H5) here — this family's downwelling is unchanged by batch 2.
        arrays["atm_emission_down"] = ms_down.at(0.0)
        _save(
            OUT_ROOT / "midlat_summer_sensor_ladder" / f"s{sensor_km:05.0f}.npz",
            arrays,
            geometry=_full_geometry(sensor_km, 0.0, 0.0),
        )
    # Orbital-hull duplicate of the 100 km (= TOA) node (A3), so LEO/GEO
    # sensors fall inside the 1-D hull (vacuum above TOA — exact).
    a3_arrays = _load_degraded("A3")
    a3_arrays["atm_emission_down"] = ms_down.at(0.0)
    _save(
        OUT_ROOT / "midlat_summer_sensor_ladder" / f"s{ORBITAL_NODE_KM:05.0f}.npz",
        a3_arrays,
        geometry=_full_geometry(ORBITAL_NODE_KM, 0.0, 0.0),
    )

    print("Up-looking ladder (midlat_summer, ground sensor, vertical, targets 0-20 km):")
    up_ref_wl: np.ndarray | None = None
    for run, target_km in UPLOOKING_LADDER.items():
        arrays = _load_uplooking_degraded(run)
        if up_ref_wl is None:
            up_ref_wl = arrays["wavelength_um"]
        _save(
            OUT_ROOT / "midlat_summer_uplooking_ladder" / f"t{target_km:03.0f}.npz",
            arrays,
            geometry=_full_geometry(UPLOOKING_SENSOR_KM, target_km, 0.0),
            markers=UPLOOKING_MARKERS,
        )
    assert up_ref_wl is not None
    _save(
        OUT_ROOT
        / "midlat_summer_uplooking_ladder"
        / f"t{UPLOOKING_ZERO_LENGTH_TARGET_KM:03.0f}.npz",
        _uplooking_zero_length_arrays(up_ref_wl),
        geometry=_full_geometry(UPLOOKING_SENSOR_KM, UPLOOKING_ZERO_LENGTH_TARGET_KM, 0.0),
        markers=UPLOOKING_MARKERS,
    )

    print("Up-looking zenith fan (midlat_summer, ground sensor, targets 0-20 km x sec 1/1.5/2):")
    fan_ref_wl: np.ndarray | None = None
    for run, (target_km, zenith_deg) in UPLOOKING_ZENITH_FAN.items():
        arrays = _load_uplooking_degraded(run)
        if fan_ref_wl is None:
            fan_ref_wl = arrays["wavelength_um"]
        _save(
            OUT_ROOT
            / "midlat_summer_uplooking_zenith_fan"
            / f"t{target_km:03.0f}_z{zenith_deg:04.1f}.npz",
            arrays,
            geometry=_full_geometry(UPLOOKING_SENSOR_KM, target_km, zenith_deg * _DEG),
            markers=UPLOOKING_MARKERS,
        )
    assert fan_ref_wl is not None
    # Zero-length identity at every zenith column: a target at the sensor's own
    # altitude has no air between the endpoints at ANY zenith (τ ≡ 1, L ≡ 0),
    # which is what closes the fan's rectangular grid at its target = 0 row.
    for zenith_deg in UPLOOKING_FAN_ZENITHS_DEG:
        _save(
            OUT_ROOT
            / "midlat_summer_uplooking_zenith_fan"
            / f"t{UPLOOKING_ZERO_LENGTH_TARGET_KM:03.0f}_z{zenith_deg:04.1f}.npz",
            _uplooking_zero_length_arrays(fan_ref_wl),
            geometry=_full_geometry(
                UPLOOKING_SENSOR_KM, UPLOOKING_ZERO_LENGTH_TARGET_KM, zenith_deg * _DEG
            ),
            markers=UPLOOKING_MARKERS,
        )

    print("SST column fan (midlat_summer, ground sensor -> 100 km, sec 1/1.5/2/3/4/5):")
    for run, zenith_deg in SST_COLUMN_FAN.items():
        _save(
            OUT_ROOT / "midlat_summer_sst_column_fan" / f"z{zenith_deg:06.3f}.npz",
            _load_uplooking_degraded(run),
            geometry=_full_geometry(UPLOOKING_SENSOR_KM, SST_TARGET_KM, zenith_deg * _DEG),
            markers=UPLOOKING_MARKERS,
        )

    print("Up-looking sensor ladder (midlat_summer, observer 0-50 km -> 100 km at 48.2 deg):")
    up_ladder_ref_wl: np.ndarray | None = None
    for run, sensor_km in UPLOOKING_SENSOR_LADDER.items():
        arrays = _load_uplooking_degraded(run)
        if up_ladder_ref_wl is None:
            up_ladder_ref_wl = arrays["wavelength_um"]
        _save(
            OUT_ROOT / "midlat_summer_uplooking_sensor_ladder" / f"s{sensor_km:03.0f}.npz",
            arrays,
            geometry=_full_geometry(
                sensor_km, SST_TARGET_KM, UPLOOKING_SENSOR_LADDER_ZENITH_DEG * _DEG
            ),
            markers=UPLOOKING_MARKERS,
        )
    assert up_ladder_ref_wl is not None
    # Observer AT the atmosphere top: zero-length column (τ ≡ 1, L ≡ 0), the
    # same identity as the fan's target = 0 row, at the other end of the axis.
    _save(
        OUT_ROOT / "midlat_summer_uplooking_sensor_ladder" / f"s{SST_TARGET_KM:03.0f}.npz",
        _uplooking_zero_length_arrays(up_ladder_ref_wl),
        geometry=_full_geometry(
            SST_TARGET_KM, SST_TARGET_KM, UPLOOKING_SENSOR_LADDER_ZENITH_DEG * _DEG
        ),
        markers=UPLOOKING_MARKERS,
    )

    print("Upwelling off-nadir grid (midlat_summer, ground target, sensor 10/100 km + orbital):")
    ground_down = ms_down.at(0.0)
    for run, (sensor_km, zenith_deg) in UPWELLING_OFFNADIR.items():
        arrays = _load_degraded(run)
        arrays["atm_emission_down"] = ground_down  # ground target: the H5 rung
        sensors = (sensor_km, ORBITAL_NODE_KM) if sensor_km == BOOST_SENSOR_KM else (sensor_km,)
        for out_sensor_km in sensors:
            _save(
                OUT_ROOT
                / "midlat_summer_upwelling_offnadir"
                / f"s{out_sensor_km:05.0f}_z{zenith_deg:04.1f}.npz",
                arrays,
                geometry=_full_geometry(out_sensor_km, 0.0, zenith_deg * _DEG),
            )

    print("Validation points (off-grid, not interpolation nodes):")
    for run, (sensor_km, target_km, zenith_rad) in VALIDATION.items():
        arrays = _load_degraded(run)
        _save(
            OUT_ROOT / "validation" / f"{run}.npz",
            arrays,
            geometry=_full_geometry(sensor_km, target_km, zenith_rad),
        )

    print("Done. See data/atmospheres/MANIFEST.md for the design record.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
