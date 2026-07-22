"""Build the shipped atmosphere library from the real MODTRAN run set.

Repackages the 2026-07-17 MODTRAN 6 run matrix (staged, gitignored, in
``modtran/real_runs/``) into the committed NPZ library under
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
- ``validation/``                     — off-grid single points (C7, G6 at
  45°; H1 nadir up-looking) kept as data but NOT interpolation nodes.

All midlat_summer families carry the H5 up-looking 48.2° downwelling as
``atm_emission_down`` (boost plan §4.4); see the MANIFEST for the
elevated-target simplification note.

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

from radiant.atmosphere.modtran import Tape7Reader  # noqa: E402

REAL_RUNS = REPO / "modtran" / "real_runs"
OUT_ROOT = REPO / "data" / "atmospheres"

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

# Off-grid validation points: run -> (sensor km, target km, LOS zenith rad).
# Full five-field geometry is emitted via _full_geometry (CU-167 / §4.6);
# H1 is the up-looking downwelling anchor (sensor at ground, "target" = TOA).
VALIDATION: dict[str, tuple[float, float, float]] = {
    "C7": (35.0, 10.0, 45.0 * _DEG),
    "G6": (100.0, 10.0, 45.0 * _DEG),
    "H1": (0.0, 100.0, 0.0),
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


def _vacuum_arrays(wl: np.ndarray, downwelling: np.ndarray) -> dict[str, np.ndarray]:
    """Synthesized vacuum node: τ ≡ 1, L_path ≡ 0 (boost plan §4.2).

    A physical identity (no absorbing column above the atmosphere top),
    not fabricated data. ``atm_emission_down`` carries the family's H-run
    downwelling so the interpolated downwelling is continuous across the
    target axis — the up-path identity (τ, L_path) is what closes the
    Gap 95 exo handoff; the downwelling is the constant-per-family
    simplification documented in the MANIFEST.
    """
    return {
        "wavelength_um": np.asarray(wl, dtype=np.float64),
        "transmittance": np.ones_like(wl),
        "path_radiance": np.zeros_like(wl),
        "atm_emission_down": downwelling,
    }


def _save(path: Path, arrays: dict[str, np.ndarray], geometry: dict[str, float] | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        key: np.asarray(vals, dtype=np.float32) for key, vals in arrays.items()
    }
    if geometry is not None:
        payload["geometry"] = np.array(geometry, dtype=object)
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

    # H5 up-looking 48.2° downwelling — attached to EVERY midlat_summer
    # family node (ladders, boost, off-nadir, sensor-ladder; plan §4.4).
    ms_down = _load_downwelling("H5")

    print("Ladders (midlat_summer, interpolated over sensor x target altitude):")
    for run, (sensor_km, target_km) in LADDER.items():
        arrays = _load_degraded(run)
        arrays["atm_emission_down"] = ms_down  # plan §4.4 (was zero pre-boost)
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
        arrays["atm_emission_down"] = ms_down
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
    vac = _vacuum_arrays(ref_wl, ms_down)
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
        arrays["atm_emission_down"] = ms_down
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
        arrays["atm_emission_down"] = ms_down
        _save(
            OUT_ROOT / "midlat_summer_sensor_ladder" / f"s{sensor_km:05.0f}.npz",
            arrays,
            geometry=_full_geometry(sensor_km, 0.0, 0.0),
        )
    # Orbital-hull duplicate of the 100 km (= TOA) node (A3), so LEO/GEO
    # sensors fall inside the 1-D hull (vacuum above TOA — exact).
    a3_arrays = _load_degraded("A3")
    a3_arrays["atm_emission_down"] = ms_down
    _save(
        OUT_ROOT / "midlat_summer_sensor_ladder" / f"s{ORBITAL_NODE_KM:05.0f}.npz",
        a3_arrays,
        geometry=_full_geometry(ORBITAL_NODE_KM, 0.0, 0.0),
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
