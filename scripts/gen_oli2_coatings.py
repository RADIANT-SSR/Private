#!/usr/bin/env python3
"""Generate the synthetic OLI-2 optical-coating curves for scenario 9.4 (Rule 26 manifest).

This script is the **generator** for every CSV under
``scenarios/09_flagship_missions/9.4_landsat_oli2_snr/data/`` — the committed
files are its output and are regenerated (byte-identical, LF newlines) by::

    python scripts/gen_oli2_coatings.py

No per-surface curves are published for OLI/OLI-2, so these are **synthetic**
coatings, anchored as follows (provenance detail:
``docs/validation/landsat_oli2_source_data.md``):

- ``mirror_protected_ag.csv`` — protected-silver reflectance R(lambda),
  piecewise-linear through vendor-typical anchor points (0.935 @ 0.40 um
  rising to 0.986 in the SWIR). Used for all four telescope mirrors.
- ``fpa_window_ar.csv`` — fused-silica FPA window, broadband AR both faces,
  flat T = 0.985.
- ``filter_b0N.csv`` — one interference-filter passband per OLI-2 band:
  super-Gaussian T(lambda) = floor + (T_pk - floor) * exp(-((lambda-lc)/sigma)^(2m)),
  m = 5, with the 50% points matched to the published [Irons 2012] band edges;
  T_pk = 0.90 (VNIR), 0.85 (SWIR), 0.80 (cirrus); blocking floor 1e-4.
- ``filter_butcher_block.csv`` — **historical** (no config file has used it since
  2026-09-03): the union (pointwise max) of the eight non-overlapping 30 m-band
  strips, mirroring the physical butcher-block filter assembly over the FPA. It
  was the ADR-0010 D-7 workaround for a study that could not give each band its
  own filter element (Gap 103); the pan strip (B8) overlaps green/red and was
  deliberately NOT in the composite, which is why the pan band needed a separate
  file. With configured element rows (Gap 103 v1.1) every band carries its own
  ``filter_b0N.csv`` entry, so this curve is generated for the record only.
- ``l_typ_b0N.csv`` — flat at-aperture radiance = L_typ [W/m2/sr/um] spanning
  each band's edges +/- 10 nm (the scenario's vacuum-path source term,
  mirroring scenario 9.1).

Deterministic: no RNG, no timestamps; rerunning must reproduce the committed
bytes exactly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "scenarios" / "09_flagship_missions" / "9.4_landsat_oli2_snr" / "data"

# Shared wavelength grid for coating curves [um]: covers every band with margin.
GRID_UM = np.round(np.arange(0.400, 2.500 + 1e-9, 0.005), 3)

# Protected-silver anchor points (lambda [um], R) — vendor-typical class curve.
PROTECTED_AG_ANCHORS: list[tuple[float, float]] = [
    (0.400, 0.935),
    (0.420, 0.945),
    (0.450, 0.955),
    (0.500, 0.965),
    (0.600, 0.975),
    (0.800, 0.980),
    (1.000, 0.982),
    (1.300, 0.984),
    (1.600, 0.985),
    (2.000, 0.986),
    (2.500, 0.986),
]

WINDOW_T = 0.985  # fused silica + broadband AR, both faces
FILTER_FLOOR = 1e-4  # out-of-band blocking
SUPER_GAUSS_M = 5  # super-Gaussian order (exponent 2m)

# Band table: (band id, 50% edge min [um], 50% edge max [um], peak T, L_typ [W/m2/sr/um]).
# Edges and L_typ per [Irons 2012]; peaks are vendor-typical assumptions.
BANDS: list[tuple[str, float, float, float, float]] = [
    ("b01", 0.435, 0.451, 0.90, 40.0),
    ("b02", 0.452, 0.512, 0.90, 40.0),
    ("b03", 0.533, 0.590, 0.90, 30.0),
    ("b04", 0.636, 0.673, 0.90, 22.0),
    ("b05", 0.851, 0.879, 0.90, 14.0),
    ("b06", 1.566, 1.651, 0.85, 4.0),
    ("b07", 2.107, 2.294, 0.85, 1.7),
    ("b08", 0.503, 0.676, 0.90, 23.0),
    ("b09", 1.363, 1.384, 0.80, 6.0),
]

# The eight non-overlapping 30 m bands forming the butcher-block composite (no b08/pan).
COMPOSITE_BANDS = ("b01", "b02", "b03", "b04", "b05", "b06", "b07", "b09")


def write_curve(path: Path, wavelength_um: np.ndarray, values: np.ndarray, header: str) -> None:
    """Write a two-column element CSV (comment header, LF newlines, 6 decimals)."""
    lines = [f"# {line}" for line in header.splitlines()]
    lines += [f"{w:.3f},{v:.6f}" for w, v in zip(wavelength_um, values, strict=True)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def filter_curve(edge_min_um: float, edge_max_um: float, peak_t: float) -> np.ndarray:
    """Super-Gaussian passband with 50% points at the published band edges."""
    center_um = 0.5 * (edge_min_um + edge_max_um)
    half_width_um = 0.5 * (edge_max_um - edge_min_um)
    # T(edge) = 0.5*peak  =>  ((edge-center)/sigma)^(2m) = ln 2.
    sigma_um = half_width_um / np.log(2.0) ** (1.0 / (2 * SUPER_GAUSS_M))
    shape = np.exp(-(((GRID_UM - center_um) / sigma_um) ** (2 * SUPER_GAUSS_M)))
    return FILTER_FLOOR + (peak_t - FILTER_FLOOR) * shape


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    anchors = np.asarray(PROTECTED_AG_ANCHORS)
    mirror_r = np.interp(GRID_UM, anchors[:, 0], anchors[:, 1])
    write_curve(
        DATA_DIR / "mirror_protected_ag.csv",
        GRID_UM,
        mirror_r,
        "Synthetic protected-silver mirror reflectance R(lambda) [-] vs wavelength [um].\n"
        "Generator: scripts/gen_oli2_coatings.py (piecewise-linear through vendor-typical\n"
        "anchors; assumption class, envelope +/-0.01 per surface). Used for OLI-2 M1-M4.",
    )

    write_curve(
        DATA_DIR / "fpa_window_ar.csv",
        GRID_UM,
        np.full_like(GRID_UM, WINDOW_T),
        "Synthetic FPA window transmittance T(lambda) [-] vs wavelength [um]: fused silica,\n"
        "broadband AR both faces, flat 0.985. Generator: scripts/gen_oli2_coatings.py.",
    )

    curves: dict[str, np.ndarray] = {}
    for band, edge_min, edge_max, peak_t, l_typ in BANDS:
        curves[band] = filter_curve(edge_min, edge_max, peak_t)
        write_curve(
            DATA_DIR / f"filter_{band}.csv",
            GRID_UM,
            curves[band],
            f"Synthetic OLI-2 {band.upper()} interference filter T(lambda) [-] vs [um]:\n"
            f"super-Gaussian (m={SUPER_GAUSS_M}), 50% points at published edges "
            f"{edge_min:.3f}-{edge_max:.3f} um,\n"
            f"peak {peak_t:.2f}, blocking floor {FILTER_FLOOR:g}. "
            "Generator: scripts/gen_oli2_coatings.py.",
        )
        # Radiance CSVs use the scenario-9.1 single-header convention: the user-radiance
        # loader skips exactly one non-numeric header row, not '#' comment blocks.
        (DATA_DIR / f"l_typ_{band}.csv").write_text(
            "wavelength_um,radiance_w_m2_sr_um\n"
            f"{edge_min - 0.010:.3f},{l_typ:.2f}\n"
            f"{edge_max + 0.010:.3f},{l_typ:.2f}\n",
            encoding="utf-8",
            newline="\n",
        )

    composite = np.maximum.reduce([curves[b] for b in COMPOSITE_BANDS])
    write_curve(
        DATA_DIR / "filter_butcher_block.csv",
        GRID_UM,
        composite,
        "Synthetic OLI-2 butcher-block composite filter T(lambda) [-] vs [um]: pointwise\n"
        "union (max) of the eight non-overlapping 30 m-band strips (B1-7, B9; pan excluded\n"
        "- it overlaps green/red). HISTORICAL: it was the shared element of the D-7-era\n"
        "study, whose per-configuration band edges selected its strip (Gap 103 workaround).\n"
        "Since 2026-09-03 every band carries its own filter_b0N.csv entry on a configured\n"
        "element row, and no config file references this curve.\n"
        "Generator: scripts/gen_oli2_coatings.py.",
    )

    n_files = 2 + 2 * len(BANDS) + 1
    print(f"Wrote {n_files} CSV files to {DATA_DIR}")  # noqa: T201 — CLI entry point


if __name__ == "__main__":
    main()
