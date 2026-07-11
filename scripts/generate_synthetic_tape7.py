#!/usr/bin/env python
"""Generate synthetic tape7 OUTPUT files for every run in the MODTRAN matrix.

Reads docs/plans/modtran_run_matrix.csv and, for each of the 39 runs,
writes a synthetic (NOT real MODTRAN) tape7 to modtran/synthetic/. The
purpose is to exercise RADIANT's MODTRAN backend plumbing and unblock
scenario work (1.1, 6.2) before real MODTRAN access is available --
NOT to validate SimpleAtmosphere's physics. See
modtran/synthetic/README.md for what is and is not independent here.

Physics summary:
- TOT TRANS, PTH THRML: real HITRAN line-by-line data (H2O, CO2, O3)
  via RADIS, on an independently-built 9-layer atmosphere (layers.py),
  combined via the standard discretized Schwarzschild equation
  (emission.py). Genuinely independent of RADIANT's own atmosphere
  model.
- SOL SCAT / SNGL SCAT: a simplified single-scatter estimate
  (aerosol.py) using the same Koschmieder/Angstrom formulas RADIANT's
  own SimpleAtmosphere uses -- NOT independent, NOT multiple-scattering
  DISORT.
- SURF EMIS, THRML SCT, GRND RFLT, DRCT RFLT: 0 (unmodeled; every run
  in the matrix has surface_albedo_surref = 0, so ground-reflection
  terms are legitimately zero regardless of method).

Compute strategy: the 39 runs reduce to 8 unique (profile, h2o_scale,
o3_scale) atmospheric columns. Each column's 9 layers x 3 species (27
RADIS calls) are computed ONCE and cached under
modtran/synthetic/_cache/; every run then derives its own
transmittance/radiance from the cached per-layer optical depths via
layer-overlap + airmass scaling (Beer-Lambert), with no further RADIS
calls. 8 x 9 x 3 = 216 RADIS calls total, parallelized across
available cores.

Usage::

    python scripts/generate_synthetic_tape7.py [--workers N] [--run-id ID]
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.synth_modtran import aerosol, emission, hitran_layers, layers, resample, tape7_writer

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MATRIX_CSV = _REPO_ROOT / "docs" / "plans" / "modtran_run_matrix.csv"
_OUTPUT_DIR = _REPO_ROOT / "modtran" / "synthetic"
_CACHE_DIR = _OUTPUT_DIR / "_cache"

_V1_CM1 = 700.0
_V2_CM1 = 25000.0
_DV_CM1 = 1.0


def _config_key(profile: str, h2o_scale: str, o3_scale: str) -> str:
    return f"{profile}__h2o{h2o_scale}__o3{o3_scale}"


def _layer_cache_path(config_key: str, layer_idx: int, species: str) -> Path:
    return _CACHE_DIR / config_key / f"layer{layer_idx:02d}_{species}.npz"


def _compute_layer_species(
    config_key: str, profile: str, h2o_scale: float, o3_scale: float, layer_idx: int, species: str
) -> str:
    """Worker: compute one (config, layer, species) optical depth and cache it."""
    cache_path = _layer_cache_path(config_key, layer_idx, species)
    if cache_path.exists():
        return f"cached {cache_path.name}"
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    layer_stack = layers.build_layers(profile, h2o_scale, o3_scale)
    layer = layer_stack[layer_idx]
    w_fine, tau_fine = hitran_layers.layer_optical_depth_vertical(layer, species, _V1_CM1, _V2_CM1)
    trans_fine = np.exp(-tau_fine)
    w_grid, trans_grid = resample.bin_average_transmittance(
        w_fine, trans_fine, _V1_CM1, _V2_CM1, _DV_CM1
    )
    tau_grid = -np.log(np.clip(trans_grid, 1e-300, 1.0))

    np.savez_compressed(cache_path, wavenumber_cm1=w_grid, optical_depth=tau_grid)
    return f"computed {cache_path.name}"


def _load_layer_species(
    config_key: str, layer_idx: int, species: str
) -> tuple[np.ndarray, np.ndarray]:
    data = np.load(_layer_cache_path(config_key, layer_idx, species))
    return data["wavenumber_cm1"], data["optical_depth"]


def precompute_all_columns(configs: set[tuple[str, str, str]], workers: int) -> None:
    """Run every (config, layer, species) RADIS calc, parallelized, with caching."""
    n_layers = len(layers.LAYER_BOUNDARIES_KM) - 1
    jobs = []
    for profile, h2o_scale, o3_scale in configs:
        config_key = _config_key(profile, h2o_scale, o3_scale)
        for layer_idx in range(n_layers):
            for species in hitran_layers.SPECIES:
                jobs.append(
                    (config_key, profile, float(h2o_scale), float(o3_scale), layer_idx, species)
                )

    print(
        f"Precomputing {len(jobs)} (config, layer, species) HITRAN calcs with {workers} workers..."
    )
    t0 = time.time()
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_compute_layer_species, *job): job for job in jobs}
        for future in as_completed(futures):
            job = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 -- report and keep going
                print(f"  FAILED {job}: {exc}")
                raise
            done += 1
            elapsed = time.time() - t0
            print(f"  [{done}/{len(jobs)}] {result} ({elapsed:.0f}s elapsed)")
    print(f"Precompute done in {time.time() - t0:.0f}s")


def _combined_layer_tau(config_key: str, layer_idx: int) -> tuple[np.ndarray, np.ndarray]:
    """Sum H2O+CO2+O3 vertical optical depth for one cached layer.

    Overlap fraction and airmass scaling are applied by the caller
    (synthesize_run) once, after this per-species sum -- both are
    linear in optical depth, so this order is equivalent and avoids
    reloading/rescaling per species.
    """
    w = None
    total_tau = None
    for species in hitran_layers.SPECIES:
        w_s, tau_vertical = _load_layer_species(config_key, layer_idx, species)
        if w is None:
            w = w_s
            total_tau = np.zeros_like(tau_vertical)
        total_tau = total_tau + tau_vertical
    return w, total_tau


def _run_layer_overlap_fraction(
    layer_idx: int, layer_stack: list, z_lo_km: float, z_hi_km: float
) -> float:
    layer = layer_stack[layer_idx]
    overlap = layers.layer_overlap_km(layer, z_lo_km, z_hi_km)
    return overlap / layer.thickness_km if layer.thickness_km > 0 else 0.0


def synthesize_run(row: dict[str, str]) -> None:
    profile = row["profile"]
    h2o_scale = row["h2o_scale"]
    o3_scale = row["o3_scale"]
    config_key = _config_key(profile, h2o_scale, o3_scale)
    layer_stack = layers.build_layers(profile, float(h2o_scale), float(o3_scale))

    h1_km = float(row["h1_sensor_km"])
    h2_km = float(row["h2_target_km"])
    z_lo, z_hi = min(h1_km, h2_km), max(h1_km, h2_km)
    if z_hi <= z_lo:
        z_hi = z_lo + 1e-6

    is_irradiance = row["iemsct"] == "3"
    zenith_deg_str = row["path_zenith_deg_radiant"].strip()
    if is_irradiance:
        geom_zenith_rad = math.radians(float(row["solar_zenith_deg"]))
    else:
        geom_zenith_rad = math.radians(float(zenith_deg_str)) if zenith_deg_str else 0.0
    airmass = layers.airmass_factor(geom_zenith_rad)

    n_layers = len(layer_stack)
    w_grid = None
    layer_dtau_by_idx: dict[int, np.ndarray] = {}
    for layer_idx in range(n_layers):
        frac = _run_layer_overlap_fraction(layer_idx, layer_stack, z_lo, z_hi)
        if frac <= 0.0:
            continue
        w, tau_vertical_sum = _combined_layer_tau(config_key, layer_idx)
        if w_grid is None:
            w_grid = w
        layer_dtau_by_idx[layer_idx] = tau_vertical_sum * frac * airmass

    if w_grid is None:
        raise RuntimeError(f"{row['run_id']}: no layers overlapped [{z_lo},{z_hi}] km")

    total_tau_gas = np.zeros_like(w_grid)
    for dtau in layer_dtau_by_idx.values():
        total_tau_gas = total_tau_gas + dtau

    tau_aer_vertical = aerosol.aerosol_vertical_optical_depth(
        w_grid, row["aerosol"], float(row["vis_km"])
    )
    tau_aer_slant = tau_aer_vertical * airmass * aerosol.aerosol_column_fraction(z_lo, z_hi)
    total_tau = total_tau_gas + tau_aer_slant
    total_transmittance = np.exp(-np.clip(total_tau, 0.0, 700.0))

    if is_irradiance:
        path_thermal = np.zeros_like(w_grid)
    else:
        # Order layers NEAR-to-FAR relative to the sensor at h1_km.
        involved = sorted(
            layer_dtau_by_idx.keys(), key=lambda i: abs(layer_stack[i].z_mid_km - h1_km)
        )
        temps_near_to_far = [layer_stack[i].temperature_K for i in involved]
        dtau_near_to_far = [layer_dtau_by_idx[i] for i in involved]
        path_thermal = emission.path_thermal_radiance_W_cm2_sr_cm1(
            w_grid, temps_near_to_far, dtau_near_to_far
        )

    solar_zenith_rad = math.radians(float(row["solar_zenith_deg"]))
    sol_scat = aerosol.single_scatter_path_radiance_W_cm2_sr_cm1(
        w_grid, row["aerosol"], float(row["vis_km"]), tau_aer_slant, total_tau, solar_zenith_rad
    )

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUTPUT_DIR / f"{row['run_id']}.synthetic.tp7"
    tape7_writer.write_synthetic_tape7(
        out_path, row["run_id"], w_grid, total_transmittance, path_thermal, sol_scat
    )
    print(f"  wrote {out_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument(
        "--run-id", type=str, default=None, help="Only synthesize this one run (debug)."
    )
    parser.add_argument(
        "--skip-precompute", action="store_true", help="Assume cache is already populated."
    )
    args = parser.parse_args()

    import os

    workers = args.workers or max(1, (os.cpu_count() or 4) - 2)

    with _MATRIX_CSV.open() as f:
        rows = list(csv.DictReader(f))
    if args.run_id:
        rows = [r for r in rows if r["run_id"] == args.run_id]
        if not rows:
            raise SystemExit(f"No run_id={args.run_id!r} in the matrix.")

    configs = {(r["profile"], r["h2o_scale"], r["o3_scale"]) for r in rows}
    if not args.skip_precompute:
        precompute_all_columns(configs, workers)

    print(f"Synthesizing {len(rows)} tape7 files...")
    for row in rows:
        synthesize_run(row)
    print("Done.")


if __name__ == "__main__":
    main()
