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
- ``validation/``                     — off-grid single points (C7, G6 at
  45°; H1 nadir up-looking) kept as data but NOT interpolation nodes.

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
# (48.2° diffusivity angle). Only two H-runs exist at that angle.
DOWNWELLING_RUNS: dict[str, str] = {
    "us_standard": "H2",
    "tropical": "H4",
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

# Off-grid validation points: run -> geometry description dict.
VALIDATION: dict[str, dict[str, float]] = {
    "C7": {"sensor_altitude_m": 35_000.0, "target_altitude_m": 10_000.0,
           "path_zenith_rad": 45.0 * _DEG},
    "G6": {"sensor_altitude_m": 100_000.0, "target_altitude_m": 10_000.0,
           "path_zenith_rad": 45.0 * _DEG},
    "H1": {"sensor_altitude_m": 0.0, "target_altitude_m": 100_000.0,
           "path_zenith_rad": 0.0},
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
        _save(OUT_ROOT / "profiles" / f"{profile}.npz", arrays, geometry=None)

    print("Zenith fan (us_standard, interpolated over path_zenith_rad):")
    h2_down = _load_downwelling("H2")
    for run, zenith_rad in ZENITH_FAN.items():
        arrays = _load_degraded(run)
        arrays["atm_emission_down"] = h2_down
        _save(
            OUT_ROOT / "us_standard_zenith_fan" / f"zen{round(zenith_rad / _DEG):02d}.npz",
            arrays,
            geometry={"path_zenith_rad": zenith_rad},
        )

    print("Ladders (midlat_summer, interpolated over sensor x target altitude):")
    for run, (sensor_km, target_km) in LADDER.items():
        arrays = _load_degraded(run)
        _save(
            OUT_ROOT / "midlat_summer_ladders" / f"s{sensor_km:05.0f}_t{target_km:02.0f}.npz",
            arrays,
            geometry={
                "sensor_altitude_m": sensor_km * 1000.0,
                "target_altitude_m": target_km * 1000.0,
            },
        )
        if sensor_km == 100.0:
            # Orbital-hull duplicate (identical state; vacuum above TOA).
            _save(
                OUT_ROOT
                / "midlat_summer_ladders"
                / f"s{ORBITAL_NODE_KM:05.0f}_t{target_km:02.0f}.npz",
                arrays,
                geometry={
                    "sensor_altitude_m": ORBITAL_NODE_KM * 1000.0,
                    "target_altitude_m": target_km * 1000.0,
                },
            )

    print("Validation points (off-grid, not interpolation nodes):")
    for run, geom in VALIDATION.items():
        arrays = _load_degraded(run)
        _save(OUT_ROOT / "validation" / f"{run}.npz", arrays, geometry=geom)

    print("Done. See data/atmospheres/MANIFEST.md for the design record.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
