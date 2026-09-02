"""Fit SimpleAtmosphere's calibrated gas-band region table (CU-161).

Derives, per spectral region, the three-parameter transmittance model

    OD_region(w) = floor + k · w^b        [nadir full column, w in cm PWV]

from the real MODTRAN 6 water ladder (runs D4 / A1 / D5: us_standard,
rural 23 km, H₂O ×0.5 / ×1 / ×2 — geometric spacing makes the exponent
solvable in closed form), then converts it into the constants pasted
into ``radiant.atmosphere.simple``:

- ``floor_add`` = max(0, floor − OD_nonwater_model): the well-mixed-gas
  absorption (CO₂/N₂O/O₃/O₂/CH₄) the 3-species model lacked, minus what
  its Rayleigh+aerosol already provide in that region (never negative —
  regions where aerosol over-absorbs, e.g. the VIS, get no floor).
- ``(k, b)``: the water term, replacing the former linear-in-w
  Lorentzian-wing model whose MWIR response was ~5× too steep.

Anchors are band means of ``Tape7Reader.to_radiant_units`` transmittance
over the staged run set (``modtran/real_runs/``, gitignored, 2026-07-17).
Cross-validation against the six profile anchors (A2–A6) is printed.

**One grid, both sides (CU-336).** ``floor_add`` is a *difference* of two band
ODs — the measured one and the model's non-water reference — so the two must be
measured the same way or the difference carries the discrepancy between the two
measurements. They were not: the reference was evaluated on a uniform-λ grid
(``linspace(0.30, 14.29, 3000)``) while the measured ODs come off MODTRAN's
native grid, which is uniform in **wavenumber** (1 cm⁻¹, so Δλ ∝ λ² — dense in
the blue, sparse in the LWIR). Since :func:`_band_od` is an unweighted mean over
the samples inside the band, the two grids weight a band differently, and for
the λ⁻⁴-steep Rayleigh term that difference is large: the reference came out
**0.0222 OD low at 0.45–0.70 µm and 0.0114 low at 0.70–1.30 µm** (≤ 0.0004
beyond 1.3 µm), biasing those floors high by the same amount. The reference is
now evaluated on the tape7 grid itself, so both sides share one grid, one band
mask, and one estimator; the anchor grid is asserted identical across the staged
runs before it is used.

That convention also fixes a *coverage* mismatch in the first region: the tape7
grid starts at 0.374953 µm, so the measured 0.30–0.45 µm OD was always the
0.375–0.45 µm mean while the reference spanned the full 0.30–0.45 µm — including
0.30–0.375 µm, where Rayleigh alone is enormous. The inflated reference masked a
real deficit; on the shared grid the 0.30–0.45 µm row picks up a floor. Note the
residual limitation: that row is fitted from 0.375–0.45 µm and applied across
0.30–0.45 µm (no anchor data exists below 0.375 µm).

Usage::

    python scripts/fit_simple_atmosphere_gas_bands.py

Prints the ``_CALIBRATED_GAS_REGIONS`` table to paste into simple.py.

**The consumer no longer reads this table as a step function (CU-267).**
``SimpleAtmosphere._region_params`` joins ``(floor_od, k_h2o, b_h2o)``
across every interior region edge with a C¹ smoothstep ramp of half-width
``GAS_REGION_BLEND_HALF_WIDTH_UM`` (0.02 µm), so τ(λ) is continuous and a
band-mean τ no longer depends on the sampling grid. Two consequences for
anyone re-running this fit:

- **Every region must stay wider than 2·hw = 0.04 µm.** Below that the two
  edge ramps of a region overlap and its calibrated coefficients are never
  reached anywhere. Changing ``REGIONS`` below to a finer partition is
  therefore not free — ``test_gas_region_blend.py::
  test_blend_ramps_never_overlap`` fails, and the fix is a decision (narrow
  the blend, or coarsen the partition), not a table paste.
- **The fitted coefficients are still region-mean values**, exactly as this
  script derives them; the blend touches only the 0.04 µm neighbourhood of
  each edge and leaves region interiors bit-identical. So a refit does not
  need to compensate for the blend — but a refit that *moves* an edge moves
  the ramp with it, and the shipped golden baselines will move at the
  ≤ 1 % level for any band that straddles the new edge.
"""

from __future__ import annotations

import sys
import warnings
from dataclasses import replace
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from radiant.atmosphere.modtran import Tape7Reader  # noqa: E402

REAL_RUNS = REPO / "modtran" / "real_runs"

# Spectral partition [µm]. First/last regions clamp to (0, ∞) in the model.
SEGMENTS: tuple[tuple[float, float], ...] = (
    (0.30, 0.45),
    (0.45, 0.70),
    (0.70, 1.30),
    (1.30, 1.50),
    (1.50, 1.75),
    (1.75, 2.05),
    (2.05, 2.40),
    (2.40, 3.10),
    (3.10, 3.50),
    (3.50, 5.00),
    (5.00, 7.50),
    (7.50, 8.00),
    # CU-330 split the former single 8.00–10.00 µm row at the measured
    # O₃ ν₂ band edges: the clean window, the band core, and the tail.
    (8.00, 9.40),
    (9.40, 9.90),
    (9.90, 10.00),
    (10.00, 12.00),
    (12.00, 14.29),
)

LADDER = (("D4", 0.7), ("A1", 1.4), ("D5", 2.8))
PROFILES = (("A6", 0.42), ("A4", 0.85), ("A5", 2.08), ("A3", 2.92), ("A2", 4.11))

B_MIN, B_MAX = 0.10, 2.50  # exponent guard for noisy/transparent segments


def _band_od(wl: np.ndarray, tau: np.ndarray, lo: float, hi: float) -> float:
    band = (wl >= lo) & (wl <= hi)
    return -float(np.log(max(float(tau[band].mean()), 1e-9)))


def _model_nonwater_od(wl: np.ndarray) -> dict[tuple[float, float], float]:
    """Pre-existing Rayleigh+aerosol band OD (w→0) at the anchor geometry.

    "Pre-existing" means *excluding* the calibrated gas floor this script
    derives. When CU-161 first ran, ``floor_od`` did not exist and the
    model's w→0 transmittance was Rayleigh + aerosol by construction.
    Now that the floors ship, evaluating the model as-is returns
    ``Rayleigh + aerosol + floor_od`` and ``floor_add`` would come out
    ≈ 0 for every region — the generator would silently zero its own
    table on a re-run. The regions are therefore zeroed-floor for the
    duration of this evaluation, which restores the original convention
    exactly (same code path, the one term removed) and makes the script
    reproduce the table it generated.

    ``wl`` is the grid to evaluate on [µm], and the caller passes the tape7
    grid the measured band ODs come off (CU-336 — see the module docstring).
    """
    from radiant.api.session import RadiantSession
    from radiant.atmosphere import simple as simple_mod
    from radiant.atmosphere.simple import SimpleAtmosphere
    from radiant.core.los_geometry import LineOfSightGeometry

    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    for key, val in [
        ("source.target.temperature", 300.0),
        ("source.target.emissivity", 0.95),
        ("atmosphere.model", "simple"),
        ("geometry.sensor_altitude_m", 100_000.0),
        ("optics.aperture_diameter_m", 0.08),
        ("optics.focal_length_m", 0.20),
        ("optics.transmission_scalar", 0.60),
        ("detector.pixel_pitch_x_um", 17.0),
        ("detector.pixel_pitch_y_um", 17.0),
        ("detector.qe_value", 0.55),
        ("detector.dark_rate_e_per_s", 1000.0),
        ("spectral_integration.filter_min_um", 0.30),
        ("spectral_integration.filter_max_um", 14.29),
        ("spectral_integration.integration_time_s", 0.015),
        ("readout.read_noise_e_rms", 20.0),
        ("readout.gain_e_per_dn", 2.0),
        ("readout.adc_bits", 14),
    ]:
        params.set(key, val)
    params.resolve()
    atm = SimpleAtmosphere(precipitable_water_cm=1e-9)
    # ADR-0011: the sensor endpoint travels on the LOS contract. The anchor
    # geometry is the nadir full column ground → 100 km (`h_sensor` = the
    # column top), matching the `geometry.sensor_altitude_m` set above.
    los = LineOfSightGeometry(
        h_tgt=0.0,
        h_sensor=100_000.0,
        theta_o=0.0,
        h_atm_top=1.0e5,
        theta_s=None,
        delta_phi=None,
    )
    shipped_regions = simple_mod._CALIBRATED_GAS_REGIONS
    simple_mod._CALIBRATED_GAS_REGIONS = tuple(
        replace(region, floor_od=0.0) for region in shipped_regions
    )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            q = atm.evaluate(wl, los, params)
        tau = np.asarray(q.tau_up)
    finally:
        simple_mod._CALIBRATED_GAS_REGIONS = shipped_regions
    return {seg: _band_od(wl, tau, *seg) for seg in SEGMENTS}


def main() -> int:
    if not REAL_RUNS.exists():
        print(f"ERROR: {REAL_RUNS} not staged.", file=sys.stderr)
        return 1

    spectra = {}
    for run, _w in (*LADDER, *PROFILES):
        wl, tau, _, _ = Tape7Reader(REAL_RUNS / f"{run}.tp7").to_radiant_units()
        spectra[run] = (wl, tau)

    # CU-336: the non-water reference is measured on the same grid as the band
    # ODs it is subtracted from. Every staged run is one MODTRAN spectral setup
    # (1 cm⁻¹, 0.374953–14.388489 µm), so there is a single anchor grid — but
    # say so out loud rather than assume it, because a future run set mixing
    # resolutions would silently reintroduce the very bias this closes.
    anchor_grid = spectra["A1"][0]
    for run, (wl_run, _tau) in spectra.items():
        if wl_run.shape != anchor_grid.shape or not np.array_equal(wl_run, anchor_grid):
            print(
                f"ERROR: {run}.tp7 is on a different spectral grid than A1.tp7 "
                f"({wl_run.size} vs {anchor_grid.size} points). The fit subtracts a "
                "model band OD from a measured one, so both must be measured on one "
                "grid (CU-336). Re-run the staged decks with a single spectral setup, "
                "or extend this script to resample onto a common grid.",
                file=sys.stderr,
            )
            return 1
    nonwater = _model_nonwater_od(anchor_grid)

    rows = []
    print(f"{'segment':16} {'OD0':>7} {'k':>8} {'b':>6} {'nonwater':>9} {'floor_add':>9}")
    for lo, hi in SEGMENTS:
        od = [_band_od(*spectra[run], lo, hi) for run, _w in LADDER]
        d1, d2 = od[1] - od[0], od[2] - od[1]
        if d1 <= 1e-4:  # no measurable water response in this segment
            k, b, od0 = 0.0, 1.0, od[1]
        else:
            b = float(np.clip(np.log2(max(d2, 1e-9) / d1), B_MIN, B_MAX))
            k = d1 / (1.4**b - 0.7**b)
            od0 = od[0] - k * 0.7**b
            if od0 < 0.0:
                # Deeply saturated segment: the 3-point closed form wants a
                # negative floor. Refit floor-free, anchored exactly at the
                # default column (w = 1.4) with the exponent from the
                # endpoint ratio — symmetric error at the extremes.
                b = float(np.clip(np.log(od[2] / od[0]) / np.log(4.0), B_MIN, B_MAX))
                k = od[1] / 1.4**b
                od0 = 0.0
        floor_add = max(od0 - nonwater[(lo, hi)], 0.0)
        rows.append((lo, hi, floor_add, k, b))
        print(
            f"{lo:5.2f}–{hi:5.2f} µm  {od0:7.3f} {k:8.4f} {b:6.3f} "
            f"{nonwater[(lo, hi)]:9.3f} {floor_add:9.3f}"
        )

    print("\n# Paste into radiant/atmosphere/simple.py:")
    print("_CALIBRATED_GAS_REGIONS: tuple[_GasRegion, ...] = (")
    for lo, hi, floor, k, b in rows:
        print(
            f"    _GasRegion(lo_um={lo}, hi_um={hi}, "
            f"floor_od={floor:.4f}, k_h2o={k:.4f}, b_h2o={b:.3f}),"
        )
    print(")")

    # Cross-validation: reconstruct each profile anchor's per-window τ from
    # the fit (floor_add + nonwater ≈ OD0) and compare.
    print("\nCross-validation (fit τ − real τ), water-relevant windows:")
    checks = [
        (0.70, 1.30),
        (1.50, 1.75),
        (3.50, 5.00),
        (8.00, 9.40),
        (9.40, 9.90),
        (9.90, 10.00),
        (10.00, 12.00),
    ]
    for run, w in PROFILES:
        deltas = []
        for lo, hi in checks:
            row = next(r for r in rows if r[0] == lo)
            od0_fit = row[2] + nonwater[(lo, hi)]
            tau_fit = float(np.exp(-(od0_fit + row[3] * w ** row[4])))
            tau_real = float(np.exp(-_band_od(*spectra[run], lo, hi)))
            deltas.append(f"{lo:g}–{hi:g}:{tau_fit - tau_real:+.3f}")
        print(f"  {run} (w={w}): " + "  ".join(deltas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
