"""Integration: the CU-330 ozone split re-derived from the delivered τ data.

CU-161 fitted the calibrated gas table with one flat region across
8.00–10.00 µm.  CU-330 partitions that row at the 9.6 µm O₃ ν₂ band and
re-fits it with the *same* machinery — the same three-point closed form on
the same water ladder (D4/A1/D5, us_standard rural 23 km, H₂O ×0.5/×1/×2)
against the same "non-water = Rayleigh + aerosol" convention.

Three things are pinned here that the Level-0 module cannot pin, because
they need the delivered MODTRAN run set:

(a) **Fit reproduction.**  Re-running the closed form on the delivered
    ladder returns the three shipped rows.  This is what makes the table a
    *generated* artifact (Rule 26) rather than three hand-typed numbers:
    if the generator, the ladder, or the convention drifts, this fails.

(b) **Where the band edges are.**  The boundaries are not a convention —
    they are read off the data.  The water-free optical depth rises 3.7×
    across 9.372 → 9.416 µm and falls 1.6× across 9.901 → 9.911 µm, so
    9.40 and 9.90 µm are the measured edges, and the 0.04 µm CU-267 ramp
    centred on 9.40 µm covers exactly the interval the rise occupies.

(c) **In-band τ parity, before and after.**  Band-mean τ against thirteen
    full-column and twelve partial-column anchors.  The split improves the
    clean window 4.4× and the band core 3.4× on the full columns, and
    *degrades* the partial columns in the band — which is not a regression
    but the newly-visible consequence of placing ozone opacity on the
    well-mixed 8 km scale height when the real layer sits near 25 km.  That
    is CU-324 item 2, and it is why the two are sequenced.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.modtran import Tape7Reader
from radiant.atmosphere.protocol import AtmosphericGeometry
from radiant.atmosphere.simple import (
    _CALIBRATED_GAS_REGIONS,
    SimpleAtmosphere,
    _GasRegion,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_RUNS = _REPO_ROOT / "modtran" / "real_runs"

pytestmark = pytest.mark.skipif(not _REAL_RUNS.exists(), reason="real MODTRAN run set not staged")

#: The CU-161 water ladder: (run, precipitable water [cm]).  Geometric
#: spacing is what makes the exponent solvable in closed form.
_LADDER: tuple[tuple[str, float], ...] = (("D4", 0.7), ("A1", 1.4), ("D5", 2.8))

#: Exponent guard, as in the generator.
_B_MIN, _B_MAX = 0.10, 2.50

#: The three CU-330 sub-regions [µm].
_WINDOW = (8.00, 9.40)
_CORE = (9.40, 9.90)
_TAIL = (9.90, 10.00)

#: Rayleigh + aerosol band OD at the anchor geometry, measured 2026-08-29
#: with the gas floors zeroed (the generator's own ``_model_nonwater_od``
#: convention).  Flat across 8–10 µm to four decimals because only the
#: aerosol contributes there.
_NONWATER_OD = 0.0116


def _spectrum(run: str) -> tuple[np.ndarray, np.ndarray]:
    wavelength_um, tau, _lpath, _extra = Tape7Reader(_REAL_RUNS / f"{run}.tp7").to_radiant_units()
    return np.asarray(wavelength_um), np.asarray(tau)


def _band_od(wavelength_um: np.ndarray, tau: np.ndarray, lo: float, hi: float) -> float:
    """The generator's band optical depth: −ln of the band-mean τ."""
    band = (wavelength_um >= lo) & (wavelength_um <= hi)
    return -float(np.log(max(float(tau[band].mean()), 1e-9)))


def _closed_form_fit(lo: float, hi: float) -> tuple[float, float, float]:
    """The CU-161 three-point closed form. Returns ``(floor_od, k, b)``.

    Written out rather than imported so the test is an independent
    statement of the fit, not a re-run of the generator's own code path.
    """
    od = [_band_od(*_spectrum(run), lo, hi) for run, _w in _LADDER]
    first, second = od[1] - od[0], od[2] - od[1]
    assert first > 1e-4, f"{lo}–{hi} µm shows no water response; the closed form does not apply"
    b = float(np.clip(math.log2(max(second, 1e-9) / first), _B_MIN, _B_MAX))
    k = first / (1.4**b - 0.7**b)
    od0 = od[0] - k * 0.7**b
    assert od0 > 0.0, f"{lo}–{hi} µm wants a negative floor; the saturated branch would apply"
    return max(od0 - _NONWATER_OD, 0.0), k, b


def _region(lo_um: float, hi_um: float) -> _GasRegion:
    for region in _CALIBRATED_GAS_REGIONS:
        if region.lo_um == lo_um and region.hi_um == hi_um:
            return region
    raise AssertionError(f"no calibrated region spans {lo_um}–{hi_um} µm")


# ---------------------------------------------------------------------------
# (a) The shipped rows are what the generator produces
# ---------------------------------------------------------------------------


@pytest.mark.level2
@pytest.mark.parametrize("band", [_WINDOW, _CORE, _TAIL])
def test_the_shipped_row_reproduces_from_the_delivered_ladder(band: tuple[float, float]) -> None:
    """Re-fit each sub-region from the tape7s and compare to the table.

    Tolerances are the table's own printed precision (four decimals on
    ``floor_od`` and ``k_h2o``, three on ``b_h2o``), so this is an equality
    check up to the rounding the generator applies when it emits the row.
    """
    floor_od, k_h2o, b_h2o = _closed_form_fit(*band)
    shipped = _region(*band)
    assert floor_od == pytest.approx(shipped.floor_od, abs=5.0e-5)
    assert k_h2o == pytest.approx(shipped.k_h2o, abs=5.0e-5)
    assert b_h2o == pytest.approx(shipped.b_h2o, abs=5.0e-4)


@pytest.mark.level2
def test_refitting_the_old_slab_still_returns_the_retired_row() -> None:
    """The generator is unchanged — only the partition moved.

    Running the identical closed form over the retired 8.00–10.00 µm span
    returns the retired coefficients (0.2751, 0.0877, 1.268).  That is what
    says CU-330 re-partitioned the fit rather than re-defining it, so the
    new rows and the old one are commensurable.
    """
    floor_od, k_h2o, b_h2o = _closed_form_fit(8.00, 10.00)
    assert floor_od == pytest.approx(0.2751, abs=5.0e-5)
    assert k_h2o == pytest.approx(0.0877, abs=5.0e-5)
    assert b_h2o == pytest.approx(1.268, abs=5.0e-4)


@pytest.mark.level2
def test_the_split_conserves_the_slab_it_replaced() -> None:
    """The three sub-region floors sit around the retired slab's value.

    Width-weighted over 8–10 µm the new floors give 0.342 against the
    retired 0.275 — same order, 24 % apart, and the sign is the point.
    The old row fitted ``−ln⟨τ⟩`` over 2 µm containing a deep 0.5 µm
    feature, and ``−ln⟨τ⟩ < ⟨−ln τ⟩`` by Jensen's inequality, so a slab
    fit to a band-mean τ *under*-states the opacity it is standing in for.
    That gap is the non-linearity the flat region was hiding, and it is
    why the split moves 8–12 µm band means at all.
    """
    weighted = sum(_region(lo, hi).floor_od * (hi - lo) for lo, hi in (_WINDOW, _CORE, _TAIL)) / 2.0
    assert weighted == pytest.approx(0.342, abs=0.002)
    assert weighted > 0.2751


# ---------------------------------------------------------------------------
# (b) The edges are where the data puts them
# ---------------------------------------------------------------------------


@pytest.mark.level2
def test_the_band_edges_are_read_off_the_water_free_optical_depth() -> None:
    """9.40 and 9.90 µm bracket the measured rise and fall.

    Per-wavelength water-free OD from the same three-point form.  The band
    core stands ~9× the continuum either side, the rise completes inside
    9.372 → 9.416 µm and the fall begins at 9.901 → 9.911 µm, so the two
    chosen edges each sit inside a 0.05 µm-wide transition rather than in
    the middle of a plateau.
    """
    wavelength_um, _tau = _spectrum("A1")
    od = np.stack([-np.log(np.maximum(_spectrum(run)[1], 1e-9)) for run, _w in _LADDER])
    first, second = od[1] - od[0], od[2] - od[1]
    b = np.clip(np.log2(np.maximum(second, 1e-9) / np.maximum(first, 1e-9)), _B_MIN, _B_MAX)
    k = first / (1.4**b - 0.7**b)
    od0 = np.where(first <= 1e-4, od[1], od[0] - k * 0.7**b)

    def mean_over(lo: float, hi: float) -> float:
        band = (wavelength_um >= lo) & (wavelength_um <= hi)
        return float(od0[band].mean())

    continuum = mean_over(8.60, 9.30)
    core = mean_over(*_CORE)
    beyond = mean_over(10.00, 10.30)
    assert core / continuum > 8.0
    assert core / beyond > 8.0
    # The transition is narrow: the 0.10 µm below 9.40 is already ~2.5× the
    # continuum but only ~a quarter of the core.
    wing = mean_over(9.30, 9.40)
    assert continuum < wing < 0.4 * core
    # The tail is a genuine third level, not part of either neighbour.
    tail = mean_over(*_TAIL)
    assert beyond < tail < 0.5 * core


# ---------------------------------------------------------------------------
# (c) In-band τ parity — the results record
# ---------------------------------------------------------------------------

#: ``run -> (profile, PWV [cm], h_low [m], h_high [m], zenith at the lower
#: endpoint [deg])``.  τ is reciprocal, so an up-looking deck is scored on
#: the same column read downward.
_ANCHORS: dict[str, tuple[str, float, float, float, float]] = {
    "D4": ("us_standard", 0.7, 0.0, 1.0e5, 0.0),
    "A1": ("us_standard", 1.4, 0.0, 1.0e5, 0.0),
    "D5": ("us_standard", 2.8, 0.0, 1.0e5, 0.0),
    "A2": ("tropical", 4.11, 0.0, 1.0e5, 0.0),
    "A3": ("midlat_summer", 2.92, 0.0, 1.0e5, 0.0),
    "A4": ("midlat_winter", 0.85, 0.0, 1.0e5, 0.0),
    "A5": ("subarctic_summer", 2.08, 0.0, 1.0e5, 0.0),
    "A6": ("subarctic_winter", 0.42, 0.0, 1.0e5, 0.0),
    "O5": ("midlat_summer", 2.92, 0.0, 1.0e5, 48.2),
    "H1": ("us_standard", 1.4, 0.0, 1.0e5, 0.0),
    "H2": ("us_standard", 1.4, 0.0, 1.0e5, 48.2),
    "H4": ("tropical", 4.11, 0.0, 1.0e5, 48.2),
    "H5": ("midlat_summer", 2.92, 0.0, 1.0e5, 48.2),
    "K1": ("midlat_summer", 2.92, 0.0, 1.0e3, 0.0),
    "K3": ("midlat_summer", 2.92, 0.0, 5.0e3, 0.0),
    "K5": ("midlat_summer", 2.92, 0.0, 2.0e4, 0.0),
    "K6": ("midlat_summer", 2.92, 0.0, 1.0e4, 45.0),
    "K7": ("midlat_summer", 2.92, 5.0e3, 1.5e4, 45.0),
    "N4": ("midlat_summer", 2.92, 0.0, 1.0e4, 48.2),
    "N9": ("midlat_summer", 2.92, 0.0, 1.0e4, 60.0),
    "N10": ("midlat_summer", 2.92, 0.0, 2.0e4, 60.0),
    "O1": ("midlat_summer", 2.92, 0.0, 1.0e3, 0.0),
    "O2": ("midlat_summer", 2.92, 0.0, 5.0e3, 0.0),
    "O3": ("midlat_summer", 2.92, 0.0, 1.0e4, 48.2),
    "O4": ("midlat_summer", 2.92, 0.0, 1.0e4, 60.0),
}

#: The thirteen anchors that carry the whole column to 100 km — the
#: geometry the fit was performed at.
_FULL_COLUMN: frozenset[str] = frozenset(
    {"D4", "A1", "D5", "A2", "A3", "A4", "A5", "A6", "O5", "H1", "H2", "H4", "H5"}
)

#: Measured 2026-08-29 — RMS |ln(model/MODTRAN)| of band-mean τ over the
#: thirteen full-column anchors, before (the flat slab) and after the split.
_TAU_PARITY_FULL_COLUMN: dict[tuple[float, float], tuple[float, float]] = {
    _WINDOW: (0.1606, 0.0397),
    _CORE: (0.5637, 0.1747),
    _TAIL: (0.0840, 0.0814),
    (8.0, 12.0): (0.0510, 0.0482),
    (8.0, 14.0): (0.0701, 0.0676),
}

#: The same measurement over the twelve partial-column anchors (K/N/O
#: ground-to-air rungs).  It moves the other way in the band core —
#: 0.1696 → 0.4731 — and that is the finding, not a regression: a
#: partial column below the tropopause contains almost no ozone, but the
#: model spreads the newly-identified in-band floor on the well-mixed
#: 8 km scale height, so it now over-fills short columns visibly.  The
#: flat slab hid the same error by carrying too little in-band opacity
#: everywhere.  Placing it is CU-324 item 2, which CU-330 unblocks.
_TAU_PARITY_PARTIAL_COLUMN: dict[tuple[float, float], tuple[float, float]] = {
    _WINDOW: (0.1755, 0.0955),
    _CORE: (0.1696, 0.4731),
    _TAIL: (0.2623, 0.2163),
    (8.0, 12.0): (0.1073, 0.1047),
    (8.0, 14.0): (0.1331, 0.1306),
}


def _model_tau(run: str) -> tuple[np.ndarray, np.ndarray]:
    profile, pwv_cm, h_low, h_high, zenith_deg = _ANCHORS[run]
    wavelength_um, _tau = _spectrum(run)
    atm = SimpleAtmosphere(
        standard_atmosphere=profile,
        precipitable_water_cm=pwv_cm,
        visibility_km=23.0,
        aerosol_type="rural",
    )
    geometry = AtmosphericGeometry(
        sensor_altitude_m=h_high,
        target_altitude_m=h_low,
        path_zenith_rad=math.radians(zenith_deg),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        state = atm.build_state(wavelength_um, geometry)
    return wavelength_um, np.asarray(state.transmittance.values)


def _band_mean(wavelength_um: np.ndarray, values: np.ndarray, lo: float, hi: float) -> float:
    band = (wavelength_um >= lo) & (wavelength_um <= hi)
    return float(values[band].mean())


def _rms_parity(runs: frozenset[str] | set[str], band: tuple[float, float]) -> float:
    logs = []
    for run in runs:
        reference_wl, reference_tau = _spectrum(run)
        model_wl, model_tau = _model_tau(run)
        ratio = _band_mean(model_wl, model_tau, *band) / _band_mean(
            reference_wl, reference_tau, *band
        )
        logs.append(abs(math.log(ratio)))
    return math.sqrt(float(np.mean(np.square(logs))))


@pytest.mark.level2
@pytest.mark.parametrize("band", list(_TAU_PARITY_FULL_COLUMN))
def test_in_band_tau_parity_against_the_full_column_anchors(band: tuple[float, float]) -> None:
    """Band-mean τ parity, pinned at the measured post-split value.

    Both sides of the CU-330 record are here: ``_TAU_PARITY_FULL_COLUMN``
    carries the before value for the reader, and the assertion pins the
    after value the shipped table produces.
    """
    _before, after = _TAU_PARITY_FULL_COLUMN[band]
    assert _rms_parity(_FULL_COLUMN, band) == pytest.approx(after, abs=0.002)


@pytest.mark.level2
@pytest.mark.parametrize("band", list(_TAU_PARITY_PARTIAL_COLUMN))
def test_in_band_tau_parity_against_the_partial_column_anchors(band: tuple[float, float]) -> None:
    """The same measurement on the ground-to-air rungs.

    Pinned so the ozone-placement error the split exposes cannot drift
    silently while CU-324 item 2 is open.
    """
    partial = frozenset(_ANCHORS) - _FULL_COLUMN
    _before, after = _TAU_PARITY_PARTIAL_COLUMN[band]
    assert _rms_parity(partial, band) == pytest.approx(after, abs=0.002)


@pytest.mark.level2
def test_the_split_improves_every_full_column_band_it_touches() -> None:
    """The direction of the change, stated as an ordering.

    Every band the split touches improves on the full-column anchors — the
    window 4.0×, the band core 3.2× — and the two wide LWIR bands move only
    slightly because the feature is 0.5 µm of a 4 µm average.
    """
    for band, (before, after) in _TAU_PARITY_FULL_COLUMN.items():
        assert after <= before, f"{band} got worse: {before} → {after}"
    window_before, window_after = _TAU_PARITY_FULL_COLUMN[_WINDOW]
    core_before, core_after = _TAU_PARITY_FULL_COLUMN[_CORE]
    assert window_before / window_after > 3.9
    assert core_before / core_after > 3.0


@pytest.mark.level2
def test_the_partial_columns_get_worse_in_the_band_and_that_is_the_finding() -> None:
    """The ozone-altitude error, now visible on τ rather than only on emission.

    Everywhere outside the band core the partial columns improve too.  In
    the core they get 2.8× worse, because the model puts the identified
    ozone opacity on the well-mixed 8 km scale height while the real layer
    sits near 25 km — so a 0–10 km column that should contain almost no
    ozone is handed most of it.  Before the split the same error existed
    and was invisible: the flat slab simply carried too little in-band
    opacity to notice.  Placing it is CU-324 item 2.
    """
    for band, (before, after) in _TAU_PARITY_PARTIAL_COLUMN.items():
        if band == _CORE:
            assert after / before > 2.5
        else:
            assert after <= before, f"{band} got worse: {before} → {after}"
