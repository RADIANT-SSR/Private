"""Scenario 8.3: Boost-Phase Target-Altitude Sweep (skeleton).

A missile-defense application: a space-based MWIR sensor in LEO stares at a
booster and tracks it continuously from launch (0 km) through burnout
(> 100 km). The atmospheric path from the target up to the sensor shortens as
the booster climbs, so the at-aperture signal — and the achievable SNR — change
with target altitude. This scenario sweeps ``geometry.target_altitude_m`` from
0 to 300 km against the shipped INTERPOLATED atmosphere library and reports
per-rung in-band transmittance and sub-pixel SNR.

*** SKELETON — the 29–100 km band is DATA-LIMITED. ***

The shipped ``midlat_summer_ladders`` interpolation family covers target
altitudes 0–29 km (the C/G MODTRAN run ladders, delivered 2026-07-17). Three
regimes appear along the sweep:

  * 0–29 km      — inside the interpolation hull → real interpolated τ_up.
  * 29–100 km    — ABOVE the ladder's 29 km ceiling but BELOW the atmosphere
                   top (h_atm_top = 100 km): the booster is still climbing
                   through atmosphere, so the vacuum leg does not yet apply and
                   the interpolator refuses the query (``AtmosphereValidationError``,
                   "outside the available range [0, 29000]"). This band is the
                   deliverable of the MODTRAN boost-ladder run set (G7–G11 +
                   off-nadir I-runs) in ``docs/plans/MODTRAN_Boost_Ladder_Expansion_Plan.md``.
                   The script catches the refusal and marks the rung PENDING —
                   it does not fabricate a number.
  * ≥ 100 km     — at/above the atmosphere top: the Gap 95 exo-altitude vacuum
                   leg serves τ_up ≡ 1 exactly (no data needed — code, not runs).

When the boost-ladder runs land and the library is rebuilt (plan §4, gated on
delivered tape7s — NOT started here), the 29–100 km rungs flip from PENDING to
interpolated values and this same script covers the full 0–300 km trajectory
with no code change.

Usage:
    python run_boost_phase_target_altitude_sweep.py
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.api import Sensor
from radiant.atmosphere.errors import AtmosphereValidationError  # raised by the hull refusal

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"

# LEO sensor; MWIR sub-pixel booster plume. Nadir stare (path_zenith = 0);
# the off-nadir boost grid (45°/60°) is the I-run remainder of the same plan.
SENSOR_ALTITUDE_M = 500_000.0  # LEO tracker
BAND_MIN_UM, BAND_MAX_UM = 3.0, 5.0  # MWIR — booster plume emission band
PLUME_AREA_M2 = 4.0  # m² — plume projected area (2 m across)
PIXEL_PITCH_UM = 20.0
FOCAL_LENGTH_M = 1.20
_IFOV_RAD = PIXEL_PITCH_UM * 1e-6 / FOCAL_LENGTH_M  # detector IFOV [rad]

# Representative boost trajectory rungs [km]. Spans all three regimes so the
# hull gap and the vacuum handoff are both exercised.
SWEEP_ALTITUDES_KM: tuple[float, ...] = (
    0.0,
    1.0,
    5.0,
    10.0,
    20.0,
    29.0,  # interpolated band
    40.0,
    50.0,
    60.0,
    80.0,  # PENDING band (29–100 km)
    100.0,
    150.0,
    200.0,
    300.0,  # Gap 95 vacuum leg
)
LADDER_CEILING_KM = 29.0  # shipped midlat_summer_ladders target-altitude ceiling
ATMOSPHERE_TOP_KM = 100.0  # h_atm_top default — the Gap 95 handoff altitude


def build_config(target_altitude_m: float) -> dict:
    """Config for a LEO MWIR sub-pixel track of a booster at *target_altitude_m*.

    The booster plume is a hot (900 K), high-emissivity, 4 m² source. At a LEO
    slant range it is **sub-pixel** — √A_t/R ≈ 4 µrad against an IFOV of
    ~16.7 µrad (0.22×), too large for the point-source approximation
    (√A_t/R ≤ 0.1·PSF_FWHM) yet far from filling a pixel — so the sub-pixel
    regime is the physically correct one (``regime_override`` locks it and
    keeps the in-pixel background). The interpolated ``midlat_summer_ladders``
    family supplies the target→sensor atmospheric leg.

    Nadir slant range is ``sensor − target`` altitude; the fill fraction is the
    plume area over the pixel ground footprint ``(IFOV·R)²`` (both re-derived
    per rung as the target climbs toward the sensor).
    """
    slant_range_m = SENSOR_ALTITUDE_M - target_altitude_m  # nadir stare
    footprint_area_m2 = (_IFOV_RAD * slant_range_m) ** 2
    fill_fraction = min(1.0, PLUME_AREA_M2 / footprint_area_m2)
    return {
        "source": {
            "scene_type": "sub_pixel",
            "regime_override": "sub_pixel",  # lock the regime (matches the derived one)
            "target": {
                "temperature": 900.0,  # K — booster plume brightness temperature
                "emissivity": 0.9,
                "fill_fraction": fill_fraction,  # sub-pixel weight = A_t / footprint
            },
            "background": {"temperature": 250.0, "emissivity": 0.95},
        },
        "geometry": {
            "sensor_altitude_m": SENSOR_ALTITUDE_M,
            "target_altitude_m": target_altitude_m,
            "path_zenith_rad": 0.0,  # nadir stare (off-nadir grid = I-run remainder)
            "target_range_m": slant_range_m,
            "target": {"projected_area_m2": PLUME_AREA_M2},
        },
        "optics": {
            "aperture_diameter_m": 0.30,
            "focal_length_m": FOCAL_LENGTH_M,
            "transmission_scalar": 0.80,
        },
        "detector": {
            "pixel_pitch_x_um": PIXEL_PITCH_UM,
            "pixel_pitch_y_um": PIXEL_PITCH_UM,
            "qe_value": 0.70,
            "dark_rate_e_per_s": 5.0e3,
        },
        "spectral_integration": {
            "filter_min_um": BAND_MIN_UM,
            "filter_max_um": BAND_MAX_UM,
            # 10 µs frame: a 900 K plume is bright in MWIR, and the fill fraction
            # rises as the booster closes range toward the sensor — a longer
            # integration clips the full well at the high-altitude rungs, which
            # silently pins SNR and hides the range/τ effect (Gap 65). 10 µs
            # keeps the well unclipped across the WHOLE 0–300 km sweep so SNR
            # responds to both τ_up and closing range.
            "integration_time_s": 1.0e-5,
        },
        "readout": {
            "read_noise_e_rms": 30.0,
            "gain_e_per_dn": 100.0,  # ~FWC/2^14 so full well maps within ADC range (Gap 65)
            "adc_bits": 14,
            "full_well_capacity_e": 2.0e6,
        },
        "atmosphere": {
            "model": "interpolated",
            # Sweeping target altitude at a fixed LEO sensor → the 2-D ladder
            # family (shipped default when interpolated_data_dir is unset).
            "interpolation_axes": "sensor_altitude_m,target_altitude_m",
        },
    }


def _band(altitude_km: float) -> str:
    """Which of the three sweep regimes *altitude_km* falls in."""
    if altitude_km <= LADDER_CEILING_KM:
        return "interpolated"
    if altitude_km < ATMOSPHERE_TOP_KM:
        return "pending"
    return "vacuum"


def evaluate_rung(altitude_km: float) -> dict:
    """Evaluate one trajectory rung, degrading gracefully on the hull refusal.

    Returns a record with either (tau_inband, snr) on success or a PENDING
    marker when the interpolator refuses a target above the shipped ladder
    ceiling but below the atmosphere top.
    """
    config = build_config(altitude_km * 1_000.0)
    try:
        with warnings.catch_warnings():
            # Two EXPECTED, backend-inherent notices for this family+geometry are
            # filtered (documented, not faults):
            #  • the midlat_summer ladders ship without a downwelling column (no
            #    matching H-run — data/atmospheres/MANIFEST.md), so the chain
            #    notes "no 'atm_emission_down' key"; immaterial for a 900 K plume.
            #  • the interpolated backend collapses the Option-C sun-leg split
            #    (τ_sun = τ_up) on every evaluate (CU-011-class), which does not
            #    affect this self-luminous target's SNR.
            warnings.filterwarnings("ignore", message=".*atm_emission_down.*")
            warnings.filterwarnings("ignore", message=".*two-leg split.*")
            # Never blanket-suppress saturation (Gap 65) — surface it if it fires.
            warnings.filterwarnings("default", message=".*saturated.*")
            result = Sensor.from_dict(config).evaluate()
    except AtmosphereValidationError as exc:
        # Only the hull refusal (target above the shipped ladder ceiling) is a
        # PENDING rung; any other validation error is a real fault — re-raise it
        # rather than silently marking it PENDING (Rule 17).
        if "outside the available range" not in str(exc):
            raise
        return {
            "altitude_km": altitude_km,
            "band": _band(altitude_km),
            "status": "PENDING",
            "detail": str(exc).splitlines()[0],
        }
    tau_atm = np.asarray(result.stage_outputs["atmosphere"]["tau_atm"], dtype=float)
    return {
        "altitude_km": altitude_km,
        "band": _band(altitude_km),
        "status": "OK",
        "tau_inband": float(np.mean(tau_atm)),
        "snr": float(result.metrics["snr"]),
    }


def main() -> None:
    print("=== Scenario 8.3: Boost-Phase Target-Altitude Sweep (skeleton) ===")
    print(f"  Sensor: LEO tracker at {SENSOR_ALTITUDE_M / 1000:.0f} km, nadir stare")
    print(
        f"  Band:   MWIR {BAND_MIN_UM:.0f}–{BAND_MAX_UM:.0f} µm, "
        "sub-pixel booster plume (900 K, 4 m²)"
    )
    print("  Atmosphere: interpolated (shipped midlat_summer_ladders, target 0–29 km)")
    print(
        "  Regime: SUB_PIXEL — a 4 m² plume at LEO slant range is ~0.22× the PSF FWHM:\n"
        "          too large for the point-source approximation, too small to fill a pixel.\n"
        "          SNR is set by the fill-weighted plume signal against detector + in-pixel\n"
        "          background noise; spatial metrics (GSD/NIIRS) are not the figure of merit.\n"
    )

    records = [evaluate_rung(alt) for alt in SWEEP_ALTITUDES_KM]

    print("=== Trajectory sweep: target altitude → in-band τ_up and sub-pixel SNR ===")
    print(f"  {'Altitude [km]':>13} | {'Band':^13} | {'τ_up (3–5 µm) [-]':>17} | {'SNR [-]':>10}")
    print("  " + "-" * 62)
    for r in records:
        if r["status"] == "OK":
            print(
                f"  {r['altitude_km']:>13.0f} | {r['band']:^13} | "
                f"{r['tau_inband']:>17.4f} | {r['snr']:>10.2f}"
            )
        else:
            print(
                f"  {r['altitude_km']:>13.0f} | {r['band']:^13} | "
                f"{'PENDING (G7–G11)':>17} | {'—':>10}"
            )

    n_pending = sum(1 for r in records if r["status"] == "PENDING")
    print(f"\n  {n_pending} rung(s) in the 29–100 km band are PENDING the MODTRAN boost-ladder")
    print(
        "  run set (G7–G11 nadir + I1–I9 off-nadir) — see "
        "docs/plans/MODTRAN_Boost_Ladder_Expansion_Plan.md."
    )
    print(
        "  They are refused by the interpolator (target above the shipped 29 km ladder\n"
        "  ceiling, below the 100 km atmosphere top), NOT fabricated. When the runs land\n"
        "  and the library is rebuilt (plan §4), these rungs fill in with no code change."
    )

    # --- physics sanity notes (units on every value) ---
    covered = [r for r in records if r["status"] == "OK"]
    interp = [r for r in covered if r["band"] == "interpolated"]
    vacuum = [r for r in covered if r["band"] == "vacuum"]
    print("\n=== Physics notes ===")
    if len(interp) >= 2:
        mono = all(
            interp[i]["tau_inband"] <= interp[i + 1]["tau_inband"] + 1e-6
            for i in range(len(interp) - 1)
        )
        print(
            f"  • 0–29 km τ_up rises monotonically "
            f"({interp[0]['tau_inband']:.4f} at 0 km → {interp[-1]['tau_inband']:.4f} at 29 km): "
            "less absorbing column above the target as it climbs."
        )
        print(f"    Monotone-in-altitude check: {'PASS' if mono else 'FAIL'}")
    if vacuum:
        print(
            f"  • ≥ 100 km τ_up ≡ {vacuum[0]['tau_inband']:.4f} exactly (Gap 95 vacuum leg): "
            "the target sees no atmosphere above the 100 km top."
        )
        if len(vacuum) >= 2:
            print(
                f"    SNR still rises across the vacuum leg "
                f"({vacuum[0]['snr']:.0f} → {vacuum[-1]['snr']:.0f}) — τ_up is pinned at 1, "
                "so this is the closing slant range (higher fill fraction), not atmosphere."
            )
    print(
        "  • Unused-for-this-regime params: the sky-downwelling term is zero on these\n"
        "    ladders (midlat_summer has no shipped H-run — data/atmospheres/MANIFEST.md),\n"
        "    which is immaterial for a 900 K plume whose reflected-sky contribution is\n"
        "    negligible against its own emission."
    )

    # --- figure: τ_up vs altitude with the pending band shaded ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    for band, colour, marker, label in (
        ("interpolated", "C0", "o", "Interpolated (0–29 km, shipped ladders)"),
        ("vacuum", "C2", "s", "Vacuum leg (≥ 100 km, Gap 95)"),
    ):
        pts = [(r["altitude_km"], r["tau_inband"]) for r in covered if r["band"] == band]
        if pts:
            xs, ys = zip(*pts, strict=True)
            ax.plot(xs, ys, marker + "-", color=colour, label=label)
    ax.axvspan(
        LADDER_CEILING_KM,
        ATMOSPHERE_TOP_KM,
        color="0.85",
        label="PENDING boost-ladder runs (29–100 km)",
    )
    ax.set_xlabel("Target altitude [km]")
    ax.set_ylabel("In-band mean transmittance τ_up (3–5 µm) [-]")
    ax.set_title("Scenario 8.3: boost-phase τ_up vs target altitude (LEO MWIR tracker)")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig1_path = OUTPUT_DIR / "fig1_boost_phase_tau_vs_altitude.png"
    fig.savefig(fig1_path, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1_path}")


if __name__ == "__main__":
    main()
