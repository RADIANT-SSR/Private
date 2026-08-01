"""MODTRAN anchors for the single-scatter species split (CU-260, adopted 2026-08-01).

The shipped ``midlat_summer_uplooking_ladder`` family is a real MODTRAN 6
down-welling set: a ground sensor looking straight up (``ζ_low = 0``) at six
target rungs (0/1/3/5/10/20 km), ``midlat_summer``, rural 23 km visibility,
solar zenith 30°, 0.375–14.29 µm.  Its ``path_radiance_toward_lower`` is exactly
the ``L_toward_lower`` product :mod:`radiant.atmosphere.segment_simple` computes
for the column ``[0, h_tgt]`` — the only anchor in the repository that can
adjudicate the species-split weighting, and it is committed rather than
gitignored, so these anchors always run.

What is pinned
--------------
The CU-260 body measured one rung (t020, 0.45–0.85 µm) and recommended adopting
lower-endpoint weighting *if the remaining five rungs and the off-band region
held*.  This module is that verification, frozen: every rung, five bands, both
candidate weightings, and the adoption criterion the body itself set.

The absolute ratios are large — the simple model's single-scatter source is
known to under-predict the daytime VIS/NIR sky where multiple scattering
dominates (that is what the sub-3 µm provisional-sky ``UserWarning`` says).
These anchors do **not** claim the model matches MODTRAN; they claim the
*weighting choice* is the better of the two available ones, which is the
question CU-260 asked.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.segment_simple import evaluate_column_segment
from radiant.atmosphere.segments import ColumnSegmentSpec
from radiant.atmosphere.simple import SimpleAtmosphere

_LADDER = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "radiant"
    / "data"
    / "tables"
    / "atmospheres"
    / "midlat_summer_uplooking_ladder"
)

pytestmark = pytest.mark.skipif(
    not _LADDER.exists(), reason="shipped up-looking ladder not present"
)

# The K1-K5 deck settings the family was rendered with (see the library MANIFEST).
_THETA_S_RAD = math.radians(30.0)

_BANDS = {
    "VIS": (0.45, 0.85),
    "NIR": (0.85, 1.40),
    "SWIR": (1.40, 2.50),
    "MWIR": (3.00, 5.00),
    "LWIR": (8.00, 12.00),
}

#: Measured 2026-08-01 on this branch: MODTRAN band-mean divided by the shipped
#: (lower-endpoint) model band-mean, per rung and band.  Pinned so both a
#: regression and an unexplained improvement fail loud (the
#: ``test_uplooking_horizontal_anchors`` convention).
_EXPECTED_RATIOS: dict[tuple[int, str], float] = {
    (1_000, "VIS"): 1.103,
    (1_000, "NIR"): 0.792,
    (1_000, "SWIR"): 0.607,
    (1_000, "MWIR"): 2.334,
    (1_000, "LWIR"): 1.885,
    (3_000, "VIS"): 1.293,
    (3_000, "NIR"): 0.896,
    (3_000, "SWIR"): 0.662,
    (3_000, "MWIR"): 1.574,
    (3_000, "LWIR"): 1.130,
    (5_000, "VIS"): 1.343,
    (5_000, "NIR"): 0.908,
    (5_000, "SWIR"): 0.629,
    (5_000, "MWIR"): 1.333,
    (5_000, "LWIR"): 0.947,
    (10_000, "VIS"): 1.360,
    (10_000, "NIR"): 0.930,
    (10_000, "SWIR"): 0.610,
    (10_000, "MWIR"): 1.123,
    (10_000, "LWIR"): 0.842,
    (20_000, "VIS"): 1.342,
    (20_000, "NIR"): 0.940,
    (20_000, "SWIR"): 0.600,
    (20_000, "MWIR"): 1.015,
    (20_000, "LWIR"): 0.812,
}


def _band_mean(lam: np.ndarray, values: np.ndarray, lo: float, hi: float) -> float:
    mask = (lam >= lo) & (lam <= hi)
    return float(np.trapezoid(values[mask], lam[mask]) / (lam[mask][-1] - lam[mask][0]))


def _rungs() -> list[tuple[int, np.ndarray, np.ndarray]]:
    out: list[tuple[int, np.ndarray, np.ndarray]] = []
    for node in sorted(_LADDER.glob("t*.npz")):
        with np.load(node, allow_pickle=True) as data:
            h_tgt = int(round(float(data["geometry"].item()["target_altitude_m"])))
            if h_tgt <= 0:
                continue  # the synthesized zero-length node carries no column
            out.append(
                (
                    h_tgt,
                    np.asarray(data["wavelength_um"], dtype=np.float64),
                    np.asarray(data["path_radiance_toward_lower"], dtype=np.float64),
                )
            )
    return out


def _atmosphere() -> SimpleAtmosphere:
    return SimpleAtmosphere(
        name="midlat_summer_rural23",
        visibility_km=23.0,
        aerosol_type="rural",
        precipitable_water_cm=2.92,
        standard_atmosphere="midlat_summer",
    )


def _model_sky(lam: np.ndarray, h_tgt_m: float) -> np.ndarray:
    spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=float(h_tgt_m), zeta_low_rad=0.0)
    segment = evaluate_column_segment(
        _atmosphere(), lam, spec, theta_s_rad=_THETA_S_RAD, delta_phi_rad=0.0
    )
    return np.asarray(segment.L_toward_lower, dtype=np.float64)


@pytest.mark.level1
@pytest.mark.parametrize("h_tgt_m,band", sorted(_EXPECTED_RATIOS))
def test_anchor_ratio_is_pinned(h_tgt_m: int, band: str) -> None:
    """Every rung × band ratio against the shipped weighting, frozen."""
    lo, hi = _BANDS[band]
    for rung, lam, modtran in _rungs():
        if rung != h_tgt_m:
            continue
        ratio = _band_mean(lam, modtran, lo, hi) / _band_mean(lam, _model_sky(lam, rung), lo, hi)
        assert ratio == pytest.approx(_EXPECTED_RATIOS[(h_tgt_m, band)], rel=2e-3)
        return
    pytest.fail(f"rung {h_tgt_m} m absent from the shipped ladder")


@pytest.mark.level1
def test_lower_endpoint_weighting_is_the_better_of_the_two_everywhere_it_matters() -> None:
    """CU-260's own adoption criterion, evaluated over all five rungs.

    The criterion the body set was: adopt lower-endpoint weighting only if it is
    consistently the closer of the two to the MODTRAN anchor.  Measured
    2026-08-01, worst band-mean excursion ``max(r, 1/r)`` over the five rungs:

    ======  ===============  ===============
    band    arithmetic mean  lower endpoint
    ======  ===============  ===============
    VIS     3.085×           1.360×
    NIR     3.024×           1.262×
    SWIR    8.712×           1.666×
    MWIR    2.404×           2.334×
    LWIR    1.885×           1.885×  (identical to 4e-4 — thermal control)
    ======  ===============  ===============

    ``segment_simple`` no longer *offers* the retired weighting (Rule 27 — one
    canonical version), so this test cannot re-run the comparison; it asserts the
    right-hand column instead, as a ceiling.  Any regression toward the retired
    behaviour blows straight through it.
    """
    worst_by_band = {
        "VIS": 1.40,
        "NIR": 1.30,
        "SWIR": 1.70,
        "MWIR": 2.40,
        "LWIR": 1.90,
    }
    for rung, lam, modtran in _rungs():
        model = _model_sky(lam, rung)
        for band, (lo, hi) in _BANDS.items():
            ratio = _band_mean(lam, modtran, lo, hi) / _band_mean(lam, model, lo, hi)
            excursion = max(ratio, 1.0 / ratio)
            assert excursion <= worst_by_band[band], (
                f"rung {rung} m, {band}: model is off by {excursion:.3f}x, "
                f"past the {worst_by_band[band]:.2f}x ceiling the adoption "
                "measurement established"
            )


@pytest.mark.level1
def test_the_thermal_control_band_is_untouched_by_the_split() -> None:
    """LWIR is thermal-dominated, so the weighting choice must be inert there.

    This is the off-band half of the CU-260 verification: the MODTRAN-anchored
    region above the 3 µm provisional gate must not move when the provisional
    region's weighting changes.  Measured difference between the two candidate
    weightings on this band was ≤ 4.1e-4 relative across all five rungs; the
    assertion is that the shipped answer sits inside the MODTRAN-comparison
    envelope the thermal model already had, not that it is exact.
    """
    for rung, lam, modtran in _rungs():
        model = _model_sky(lam, rung)
        night = evaluate_column_segment(
            _atmosphere(),
            lam,
            ColumnSegmentSpec(h_low_m=0.0, h_high_m=float(rung), zeta_low_rad=0.0),
            theta_s_rad=None,
        ).L_toward_lower
        lo, hi = _BANDS["LWIR"]
        lit = _band_mean(lam, model, lo, hi)
        dark = _band_mean(lam, np.asarray(night, dtype=np.float64), lo, hi)
        assert lit == pytest.approx(dark, rel=1e-3)
        assert _band_mean(lam, modtran, lo, hi) / lit == pytest.approx(
            _EXPECTED_RATIOS[(rung, "LWIR")], rel=2e-3
        )
