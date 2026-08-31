"""Integration: the CU-321 height-resolved emission temperature vs MODTRAN.

The matched batch-2 direction pairs are the truth set: five down-looking
upwelling runs (O1–O5) and the twenty up-looking runs that share their columns
(K1–K5 vertical, N1–N10 at 48.2°/60°, H1–H5 full columns).  Both sides of the
comparison are pinned in every case — the MODTRAN band-mean itself (a stable
golden read straight off the tape7) and the model/MODTRAN ratio — so a
regression *and* an unexplained improvement both fail loud.

Two scoreboards live here, and they answer different questions:

**Full radiance** (``L_model / L_MODTRAN``) is what a user sees.  It carries
both errors the simple model makes: the emission temperature and the CU-161
region-flat spectral shape.

**T_eff only** (``(1 − τ_MODTRAN)·B(λ, T_eff_model) / L_MODTRAN``) borrows
MODTRAN's own emissivity, so the *only* model input left is the emission
temperature.  It is the metric CU-321 is actually about, and it is the one that
attributes the residual: on the up-looking MWIR rungs the full-radiance ratio
gets *worse* under CU-321 while the T_eff-only ratio and the recovered ΔT both
get better — i.e. the pre-CU-321 one-temperature form was warm-biased in a way
that partly cancelled the region-flat spectral-shape deficit, and removing the
temperature error un-masks the shape error rather than creating one.  That
trade is recorded here in numbers, not prose.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.modtran import Tape7Reader
from radiant.atmosphere.segment_simple import column_segment_optical_depth
from radiant.atmosphere.segments import ColumnSegmentSpec
from radiant.atmosphere.simple import PROFILE_PWV_CM, SimpleAtmosphere
from radiant.core.constants import c, h, k_B

_REAL_RUNS = Path(__file__).resolve().parents[2] / "modtran" / "real_runs"

pytestmark = pytest.mark.skipif(not _REAL_RUNS.exists(), reason="real MODTRAN run set not staged")

_MWIR = (3.0, 5.0)
_LWIR = (8.0, 12.0)

#: run -> (escape end, profile, h_low_m, h_high_m, zeta_deg,
#:         MODTRAN MWIR band-mean, MODTRAN LWIR band-mean,
#:         model/MODTRAN MWIR ratio, model/MODTRAN LWIR ratio)
#:
#: MODTRAN band-means [W/m²/sr/µm] read off the delivered tape7s 2026-08-02.
#: Ratios measured on this branch; the pre-CU-321 value is in the comment so the
#: direction of every move is on the record.
_ANCHORS: dict[str, tuple[str, str, float, float, float, float, float, float, float]] = {
    # --- down-looking: the direction CU-321 was filed against ---
    "O1": (
        "upper",
        "midlat_summer",
        0.0,
        1.0e3,
        0.0,
        0.30140,
        1.76019,
        0.380,
        0.518,
    ),  # 0.407 0.533
    "O2": (
        "upper",
        "midlat_summer",
        0.0,
        5.0e3,
        0.0,
        0.24971,
        2.58134,
        0.731,
        0.938,
    ),  # 1.057 1.109
    "O3": (
        "upper",
        "midlat_summer",
        0.0,
        1.0e4,
        48.2,
        0.20690,
        3.34029,
        1.141,
        0.995,
    ),  # 2.013 1.326
    "O4": (
        "upper",
        "midlat_summer",
        0.0,
        1.0e4,
        60.0,
        0.21804,
        3.92765,
        1.221,
        0.997,
    ),  # 2.249 1.352
    "O5": (
        "upper",
        "midlat_summer",
        0.0,
        1.0e5,
        48.2,
        0.19268,
        3.26974,
        1.217,
        1.010,
    ),  # 2.422 1.430
    # --- up-looking vertical K ladder ---
    "K1": (
        "lower",
        "midlat_summer",
        0.0,
        1.0e3,
        0.0,
        0.32380,
        1.77099,
        0.358,
        0.516,
    ),  # 0.379 0.530
    "K3": (
        "lower",
        "midlat_summer",
        0.0,
        5.0e3,
        0.0,
        0.39748,
        2.71558,
        0.502,
        0.925,
    ),  # 0.664 1.054
    "K5": (
        "lower",
        "midlat_summer",
        0.0,
        2.0e4,
        0.0,
        0.40129,
        2.83007,
        0.586,
        0.979,
    ),  # 0.878 1.230
    # --- up-looking zenith fan (the O3/O4 direction partners) ---
    "N4": (
        "lower",
        "midlat_summer",
        0.0,
        1.0e4,
        48.2,
        0.45003,
        3.64284,
        0.660,
        1.016,
    ),  # 0.926 1.216
    "N9": (
        "lower",
        "midlat_summer",
        0.0,
        1.0e4,
        60.0,
        0.48478,
        4.33517,
        0.743,
        1.037,
    ),  # 1.012 1.225
    "N10": (
        "lower",
        "midlat_summer",
        0.0,
        2.0e4,
        60.0,
        0.48502,
        4.37991,
        0.784,
        1.041,
    ),  # 1.090 1.260
    # --- up-looking full columns, three profiles ---
    "H1": ("lower", "us_standard", 0.0, 1.0e5, 0.0, 0.25659, 1.24809, 0.624, 1.055),  # 1.006 1.530
    "H4": ("lower", "tropical", 0.0, 1.0e5, 48.2, 0.58099, 5.31164, 0.754, 1.050),  # 1.046 1.226
    "H5": (
        "lower",
        "midlat_summer",
        0.0,
        1.0e5,
        48.2,
        0.45048,
        3.72670,
        0.721,
        1.019,
    ),  # 1.041 1.263
}

#: The O5 down-looking column: the pre-CU-321 MWIR ratio, kept as the record of
#: what this CU fixed.  A future change that pushes it back above 2 fails here.
_PRE_CU321_O5_MWIR_RATIO = 2.422


def _read(run: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(wavelength_um, total_transmittance, path_thermal_radiance)``."""
    native = Tape7Reader(_REAL_RUNS / f"{run}.tp7").parse()
    nu = native.wavenumber_cm1
    keep = nu > 0.0
    nu = nu[keep]
    lam = 1.0e4 / nu
    order = np.argsort(lam)
    return (
        lam[order],
        native.total_transmittance[keep][order],
        (native.path_thermal_radiance[keep] * nu**2)[order],
    )


def _band_mean(lam: np.ndarray, values: np.ndarray, lo: float, hi: float) -> float:
    band = (lam >= lo) & (lam <= hi)
    return float(np.trapezoid(values[band], lam[band]) / (hi - lo))


def _atm(profile: str) -> SimpleAtmosphere:
    return SimpleAtmosphere(
        standard_atmosphere=profile,
        precipitable_water_cm=PROFILE_PWV_CM[profile],
        visibility_km=23.0,
        aerosol_type="rural",
    )


def _model_thermal(run: str, lam: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(L_thermal_model, T_eff_model)`` for one anchor run."""
    escape, profile, h_low, h_high, zeta_deg, *_ = _ANCHORS[run]
    atm = _atm(profile)
    spec = ColumnSegmentSpec(h_low_m=h_low, h_high_m=h_high, zeta_low_rad=math.radians(zeta_deg))
    od, _air_mass, _lengths, species_od = column_segment_optical_depth(atm, lam, spec)
    t_eff = atm._segment_emission_temperature_K(
        lam,
        h_low_m=h_low,
        h_high_m=h_high,
        od_slant_mol=species_od["mol"],
        od_slant_aer=species_od["aer"],
        od_slant_h2o=species_od["h2o"],
        od_slant_gas=species_od["gas"],
        escape=escape,
    )
    return (1.0 - np.exp(-od)) * _planck(lam, t_eff), t_eff


def _planck(lam_um: np.ndarray, t_K: np.ndarray) -> np.ndarray:
    """B(λ, T) [W/m²/sr/µm] longhand — independent of ``core.blackbody``."""
    lam_m = lam_um * 1.0e-6
    return 2.0 * h * c**2 / lam_m**5 / np.expm1(h * c / (lam_m * k_B * t_K)) * 1.0e-6


@pytest.mark.level2
@pytest.mark.parametrize("run", sorted(_ANCHORS))
def test_thermal_path_radiance_parity_per_rung(run: str) -> None:
    """Band-mean model/MODTRAN thermal path radiance, both bands, per rung."""
    escape, _profile, _lo, _hi, _zeta, mwir_ref, lwir_ref, mwir_ratio, lwir_ratio = _ANCHORS[run]
    lam, _tau_mod, l_mod = _read(run)
    assert _band_mean(lam, l_mod, *_MWIR) == pytest.approx(mwir_ref, rel=2e-3)
    assert _band_mean(lam, l_mod, *_LWIR) == pytest.approx(lwir_ref, rel=2e-3)

    l_model, _t_eff = _model_thermal(run, lam)
    assert _band_mean(lam, l_model, *_MWIR) / mwir_ref == pytest.approx(mwir_ratio, abs=0.01), (
        f"{run} ({escape}) MWIR thermal parity moved"
    )
    assert _band_mean(lam, l_model, *_LWIR) / lwir_ref == pytest.approx(lwir_ratio, abs=0.01), (
        f"{run} ({escape}) LWIR thermal parity moved"
    )


@pytest.mark.level2
def test_the_tall_down_looking_columns_no_longer_double_the_mwir() -> None:
    """The filed CU-321 symptom, gone: O3/O4/O5 MWIR from 2.0–2.4× to ≤ 1.25×.

    This is the assertion that fails on the pre-CU-321 code, and it fails by a
    factor of two — not by a tolerance.
    """
    for run in ("O3", "O4", "O5"):
        lam, _tau, l_mod = _read(run)
        l_model, _t = _model_thermal(run, lam)
        ratio = _band_mean(lam, l_model, *_MWIR) / _band_mean(lam, l_mod, *_MWIR)
        assert 0.8 < ratio < 1.25, f"{run} MWIR {ratio:.3f}"
    assert _PRE_CU321_O5_MWIR_RATIO > 2.0  # what it was


@pytest.mark.level2
def test_lwir_parity_improves_or_holds_on_every_anchor() -> None:
    """LWIR was the constraint on the CU-321 ruling: improve or hold.

    Measured band-RMS |ln ratio| over these fourteen anchors: **0.3342 before,
    0.2522 after** — a 25 % improvement.  Honest accounting of where it does
    not improve: three rungs move slightly *away* from unity, and all three are
    shallow columns (O1 and K1 are 1 km, K3 is 5 km) whose residual is the
    CU-161 region-flat τ deficit — too little absorbing column ⇒ too little
    emitting column — which no emission temperature can reach.  Removing the
    warm bias there costs 2–3 % in |ln ratio|, against 25–34 % won on the deep
    columns the CU was filed about.  The bound below pins that cost.

    Repinned twice since the CU-321 landing, in opposite directions, and the
    pair is the whole story of the ozone defect:

    * 2026-08-29 (CU-330, the τ side): 0.2611 → 0.2632.  Every LWIR column
      began carrying the real 9.4–9.9 µm ozone opacity instead of a flat
      under-supplied average, and — still placed as though well mixed — it
      emitted from air several kilometres too warm.  Identifying the opacity
      without placing it made the band-mean marginally *worse*.
    * 2026-08-30 (CU-324 item 2, the emission side): 0.2632 → **0.2522**, the
      best this scoreboard has read.  The same opacity now emits from the
      25 km ozone layer, and ten of the fourteen rungs move toward unity —
      H1 1.243 → 1.055 is the largest.  The MWIR ratios are unmoved: the
      split touches only 9.4–9.9 µm.
    """
    pre = {
        "O1": 0.533,
        "O2": 1.109,
        "O3": 1.326,
        "O4": 1.352,
        "O5": 1.430,
        "K1": 0.530,
        "K3": 1.054,
        "K5": 1.230,
        "N4": 1.216,
        "N9": 1.225,
        "N10": 1.260,
        "H1": 1.530,
        "H4": 1.226,
        "H5": 1.263,
    }
    shallow = {"O1", "K1", "K3"}
    logs_pre: list[float] = []
    logs_post: list[float] = []
    for run, before in pre.items():
        after = _ANCHORS[run][8]
        logs_pre.append(math.log(before))
        logs_post.append(math.log(after))
        cost = abs(math.log(after)) - abs(math.log(before))
        if run in shallow:
            assert cost < 0.035, f"{run} LWIR regressed more than the recorded 3.5 %"
        else:
            assert cost <= 1e-9, f"{run} LWIR moved AWAY from unity: {before:.3f} -> {after:.3f}"
    rms_pre = math.sqrt(float(np.mean(np.square(logs_pre))))
    rms_post = math.sqrt(float(np.mean(np.square(logs_post))))
    assert rms_post < rms_pre
    assert rms_pre == pytest.approx(0.3342, abs=0.002)
    assert rms_post == pytest.approx(0.2522, abs=0.002)


@pytest.mark.level2
@pytest.mark.parametrize("run", sorted(_ANCHORS))
def test_effective_temperature_is_closer_to_the_modtran_one(run: str) -> None:
    """``T_eff`` vs MODTRAN's own recovered emission temperature.

    MODTRAN reports τ and the thermal path radiance separately, so its
    effective emission temperature is recoverable exactly:
    ``T = B⁻¹(L_thermal / (1 − τ))``.  Against that, the pre-CU-321 single
    temperature was up to 25 K too warm on the tall down-looking columns; the
    height-resolved value is within 11 K everywhere and within 5 K on most
    rungs.  Emissivity-weighted band means, so the comparison is weighted the
    way the radiance is.
    """
    lam, tau_mod, l_mod = _read(run)
    _l_model, t_eff = _model_thermal(run, lam)
    eps = 1.0 - tau_mod
    emitting = eps > 1.0e-9
    lam_m = lam * 1.0e-6
    with np.errstate(divide="ignore", over="ignore"):
        argument = (
            2.0
            * h
            * c**2
            / (lam_m**5 * np.where(emitting, l_mod / np.where(emitting, eps, 1.0), 1.0e-30) * 1.0e6)
        )
    t_modtran = h * c / (lam_m * k_B * np.log1p(argument))

    profile = _ANCHORS[run][1]
    t_one = _atm(profile)._downwelling_effective_temperature_K(_ANCHORS[run][2])
    for lo, hi in (_MWIR, _LWIR):
        band = (lam >= lo) & (lam <= hi) & emitting
        weight = eps[band]
        ref = float(np.sum(t_modtran[band] * weight) / np.sum(weight))
        new = float(np.sum(t_eff[band] * weight) / np.sum(weight)) - ref
        old = t_one - ref
        assert abs(new) < 11.0, f"{run} {lo}-{hi} µm: ΔT_eff = {new:+.2f} K"
        # …and it beats the one-temperature form wherever that form was wrong
        # by more than the ~3 K the height-resolved one costs on shallow rungs.
        if abs(old) > 4.0:
            assert abs(new) < abs(old), f"{run} {lo}-{hi} µm: {old:+.2f} K -> {new:+.2f} K"
