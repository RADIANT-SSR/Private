"""Integration: the CU-335 VIS/NIR/SWIR re-fit, re-derived from the delivered τ data.

CU-161 fitted the calibrated gas table on 2026-07-17 against a model whose
Rayleigh optical depth was ~8× too large.  Because the well-mixed floor is
defined as the measured opacity *in excess of* what Rayleigh and aerosol
already supply — clamped at zero rather than allowed to go negative — the
inflated Rayleigh term drove every floor below ~1.5 µm to zero.  CU-253 cut
Rayleigh to its correct magnitude on 2026-07-28 and the fit was never re-run,
leaving the model too transmissive in the visible.  CU-335 re-runs it.

Three things are pinned here that the Level-0 module cannot pin, because they
need the delivered MODTRAN run set:

(a) **Fit reproduction.**  Re-running the CU-161 closed form on the delivered
    ladder, against a non-water reference measured from the model with the
    floors zeroed, returns the shipped floors.  This is what makes the table a
    *generated* artifact (Rule 26) rather than five hand-typed numbers.

(b) **The A1 anchor gap.**  The defect's headline measurement: over
    0.45–0.70 µm on the us_standard full column the model read band-OD 0.320
    against MODTRAN's 0.456 — τ 0.726 against 0.634, i.e. 14.6 % too
    transmissive.  After the re-fit the model reads 0.476, a 4.3 % OD
    overshoot (τ 1.9 % low).

(c) **Band-mean τ parity, before and after**, against the thirteen full-column
    and twelve partial-column anchors.  The visible improves 5.3× and the
    composite 0.40–0.90 µm band 4.2×; 0.70–1.30 µm gets *worse*, and the
    reason is measured and recorded here rather than left as noise.
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

#: The CU-161 water ladder: (run, precipitable water [cm]).
_LADDER: tuple[tuple[str, float], ...] = (("D4", 0.7), ("A1", 1.4), ("D5", 2.8))

#: Exponent guard, as in the generator.
_B_MIN, _B_MAX = 0.10, 2.50

#: The five rows CU-335 moved, and the floor each shipped with *before*.
_MOVED: dict[tuple[float, float], float] = {
    (0.45, 0.70): 0.0000,
    (0.70, 1.30): 0.0000,
    (1.50, 1.75): 0.0133,
    (2.05, 2.40): 0.0725,
    (2.40, 3.10): 0.7434,
}

#: The generator's non-water reference grid: uniform in λ over the table's
#: full span.  Reproduced here because the floor is defined *relative* to it
#: — see ``test_the_nonwater_reference_grid_is_the_generators``.
_GENERATOR_GRID = np.linspace(0.30, 14.29, 3000)


def _spectrum(run: str) -> tuple[np.ndarray, np.ndarray]:
    wavelength_um, tau, _lpath, _extra = Tape7Reader(_REAL_RUNS / f"{run}.tp7").to_radiant_units()
    return np.asarray(wavelength_um), np.asarray(tau)


def _band_od(wavelength_um: np.ndarray, tau: np.ndarray, lo: float, hi: float) -> float:
    """The generator's band optical depth: −ln of the band-mean τ."""
    band = (wavelength_um >= lo) & (wavelength_um <= hi)
    return -float(np.log(max(float(tau[band].mean()), 1e-9)))


def _floor_free_table() -> tuple[_GasRegion, ...]:
    return tuple(
        _GasRegion(r.lo_um, r.hi_um, 0.0, r.k_h2o, r.b_h2o) for r in _CALIBRATED_GAS_REGIONS
    )


def _nonwater_od(
    monkeypatch: pytest.MonkeyPatch, grid: np.ndarray, band: tuple[float, float]
) -> float:
    """Rayleigh + aerosol band OD on the anchor column, floors removed.

    The generator's convention: evaluate the model at w → 0 with every
    ``floor_od`` zeroed, so the reference is the *pre-existing* extinction
    the floor is defined in excess of.  Without the zeroing the floors would
    be counted twice and a re-run would silently null the table.
    """
    monkeypatch.setattr("radiant.atmosphere.simple._CALIBRATED_GAS_REGIONS", _floor_free_table())
    atm = SimpleAtmosphere(precipitable_water_cm=1e-9)
    geometry = AtmosphericGeometry(
        sensor_altitude_m=1.0e5, target_altitude_m=0.0, path_zenith_rad=0.0
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        state = atm.build_state(grid, geometry)
    return _band_od(grid, np.asarray(state.transmittance.values), *band)


def _closed_form_od0(lo: float, hi: float) -> tuple[float, float, float]:
    """The CU-161 three-point closed form. Returns ``(OD0, k, b)``.

    Written out rather than imported so the test is an independent
    statement of the fit, not a re-run of the generator's own code path.
    """
    od = [_band_od(*_spectrum(run), lo, hi) for run, _w in _LADDER]
    first, second = od[1] - od[0], od[2] - od[1]
    assert first > 1e-4, f"{lo}–{hi} µm shows no water response; the closed form does not apply"
    b = float(np.clip(math.log2(max(second, 1e-9) / first), _B_MIN, _B_MAX))
    k = first / (1.4**b - 0.7**b)
    return od[0] - k * 0.7**b, k, b


def _region(lo_um: float, hi_um: float) -> _GasRegion:
    for region in _CALIBRATED_GAS_REGIONS:
        if region.lo_um == lo_um and region.hi_um == hi_um:
            return region
    raise AssertionError(f"no calibrated region spans {lo_um}–{hi_um} µm")


# ---------------------------------------------------------------------------
# (a) The shipped rows are what the generator produces
# ---------------------------------------------------------------------------


@pytest.mark.level2
@pytest.mark.parametrize("band", list(_MOVED), ids=lambda b: f"{b[0]}-{b[1]}um")
def test_the_moved_row_reproduces_from_the_delivered_ladder(
    band: tuple[float, float], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-fit each moved region from the tape7s and compare to the table.

    Tolerance is the table's own printed precision (four decimals), so this
    is an equality check up to the rounding the generator applies.
    """
    od0, k_h2o, b_h2o = _closed_form_od0(*band)
    floor_add = max(od0 - _nonwater_od(monkeypatch, _GENERATOR_GRID, band), 0.0)
    shipped = _region(*band)
    assert floor_add == pytest.approx(shipped.floor_od, abs=5.0e-5)
    assert k_h2o == pytest.approx(shipped.k_h2o, abs=5.0e-5)
    assert b_h2o == pytest.approx(shipped.b_h2o, abs=5.0e-4)


@pytest.mark.level2
def test_the_pre_cu253_rayleigh_is_what_clamped_the_vis_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The defect's mechanism, reproduced rather than asserted.

    CU-253 cut Rayleigh by ~8×.  Restoring that factor to the *current*
    non-water reference pushes the 0.45–0.70 µm reference above the ladder's
    measured ``OD0``, so ``floor_add`` clamps to zero — which is exactly the
    row CU-161 shipped.  The clamp was not a modelling choice; it was the
    arithmetic of an over-large Rayleigh term.
    """
    band = (0.45, 0.70)
    od0, _k, _b = _closed_form_od0(*band)
    nonwater = _nonwater_od(monkeypatch, _GENERATOR_GRID, band)
    # Rayleigh dominates the non-water OD in the visible; scaling the whole
    # reference by 8 is a lower bound on the pre-CU-253 value, and even that
    # bound already exceeds OD0.
    assert od0 - 8.0 * nonwater < 0.0
    assert od0 - nonwater > 0.0


@pytest.mark.level2
def test_the_nonwater_reference_grid_is_the_generators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The floor is grid-relative, and the grid is a uniform-λ one.

    The generator measures its non-water reference on a uniform 3000-point
    λ grid while the ladder's band OD comes off the tape7 grid, which is
    uniform in *wavenumber* and therefore weights the short-λ end of a VIS
    band more heavily.  Where the spectrum is steep — Rayleigh goes as
    $\\lambda^{-4}$ — the two disagree, and the difference lands in the
    floor: +0.022 OD at 0.45–0.70 µm and +0.011 at 0.70–1.30 µm, both in
    the direction of an over-large floor.  Beyond 1.3 µm it is ≤ 0.0004.

    Pinned as a characterization, not a target: the mixed-grid convention is
    CU-161's and CU-335 deliberately did not change it (a new convention
    would be a new calibration, not a re-run).  This test is what makes the
    residual visible instead of silent — it is the measured reason the
    0.70–1.30 µm parity moves the wrong way in
    ``test_the_nir_window_parity_degrades_and_why``.
    """
    tape7_grid, _tau = _spectrum("A1")
    for band, expected in (
        ((0.45, 0.70), 0.0222),
        ((0.70, 1.30), 0.0114),
        ((3.50, 5.00), 0.0004),
    ):
        generator = _nonwater_od(monkeypatch, _GENERATOR_GRID, band)
        native = _nonwater_od(monkeypatch, tape7_grid, band)
        assert native - generator == pytest.approx(expected, abs=0.002)


# ---------------------------------------------------------------------------
# (b) The A1 anchor — the defect's headline number
# ---------------------------------------------------------------------------

#: ``run -> (profile, PWV [cm], h_low [m], h_high [m], zenith at the lower
#: endpoint [deg])``.  τ is reciprocal, so an up-looking deck is scored on the
#: same column read downward.
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

#: The thirteen anchors that carry the whole column to 100 km — the geometry
#: the fit was performed at.
_FULL_COLUMN: frozenset[str] = frozenset(
    {"D4", "A1", "D5", "A2", "A3", "A4", "A5", "A6", "O5", "H1", "H2", "H4", "H5"}
)


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


@pytest.mark.level2
def test_the_a1_visible_band_od_gap_closes() -> None:
    """0.45–0.70 µm at A1: 0.320 → 0.476 against MODTRAN's 0.456.

    This is the number the CU-335 entry was opened on.  Before the re-fit
    the model under-read the band's optical depth by 30 % (τ 14.6 % high);
    after it, it over-reads by 4.3 % (τ 1.9 % low).  The residual overshoot
    is the mixed-grid artifact characterised above — the floor is fitted
    against a uniform-λ non-water reference and evaluated here on the tape7
    grid — and it is a seventh of the error it replaced.
    """
    reference_wl, reference_tau = _spectrum("A1")
    modtran_od = _band_od(reference_wl, reference_tau, 0.45, 0.70)
    model_wl, model_tau = _model_tau("A1")
    model_od = _band_od(model_wl, model_tau, 0.45, 0.70)

    assert modtran_od == pytest.approx(0.4561, abs=0.002)
    assert model_od == pytest.approx(0.4757, abs=0.002)
    assert abs(model_od / modtran_od - 1.0) < 0.06


# ---------------------------------------------------------------------------
# (c) Band-mean τ parity — the results record
# ---------------------------------------------------------------------------

#: Measured 2026-08-30 — RMS |ln(model/MODTRAN)| of band-mean τ over the
#: thirteen full-column anchors, before (the CU-161 vintage floors) and after
#: the re-fit.
_TAU_PARITY_FULL_COLUMN: dict[tuple[float, float], tuple[float, float]] = {
    (0.45, 0.70): (0.1556, 0.0294),
    (0.70, 1.30): (0.0312, 0.0402),
    (0.45, 0.85): (0.1105, 0.0440),
    (0.85, 1.40): (0.0461, 0.0314),
    (0.40, 0.90): (0.1035, 0.0244),
    (1.50, 1.75): (0.0366, 0.0463),
    (2.05, 2.40): (0.0430, 0.0457),
    (3.50, 5.00): (0.1106, 0.1107),
    (8.00, 12.00): (0.0482, 0.0482),
}

#: The same measurement over the twelve partial-column anchors (K/N/O
#: ground-to-air rungs).
_TAU_PARITY_PARTIAL_COLUMN: dict[tuple[float, float], tuple[float, float]] = {
    (0.45, 0.70): (0.1456, 0.0214),
    (0.70, 1.30): (0.0263, 0.0675),
    (0.45, 0.85): (0.0938, 0.0434),
    (0.40, 0.90): (0.0893, 0.0266),
    (3.50, 5.00): (0.1812, 0.1812),
    (8.00, 12.00): (0.1047, 0.1047),
}


def _band_mean(wavelength_um: np.ndarray, values: np.ndarray, lo: float, hi: float) -> float:
    band = (wavelength_um >= lo) & (wavelength_um <= hi)
    return float(values[band].mean())


def _rms_parity(runs: frozenset[str] | set[str], band: tuple[float, float]) -> float:
    logs = []
    for run in sorted(runs):
        reference_wl, reference_tau = _spectrum(run)
        model_wl, model_tau = _model_tau(run)
        ratio = _band_mean(model_wl, model_tau, *band) / _band_mean(
            reference_wl, reference_tau, *band
        )
        logs.append(abs(math.log(ratio)))
    return math.sqrt(float(np.mean(np.square(logs))))


@pytest.mark.level2
@pytest.mark.parametrize("band", list(_TAU_PARITY_FULL_COLUMN), ids=lambda b: f"{b[0]}-{b[1]}um")
def test_band_mean_tau_parity_against_the_full_column_anchors(band: tuple[float, float]) -> None:
    """Band-mean τ parity, pinned at the measured post-refit value.

    Both sides of the CU-335 record are here: the dict carries the before
    value for the reader, and the assertion pins the after value the shipped
    table produces.
    """
    _before, after = _TAU_PARITY_FULL_COLUMN[band]
    assert _rms_parity(_FULL_COLUMN, band) == pytest.approx(after, abs=0.002)


@pytest.mark.level2
@pytest.mark.parametrize("band", list(_TAU_PARITY_PARTIAL_COLUMN), ids=lambda b: f"{b[0]}-{b[1]}um")
def test_band_mean_tau_parity_against_the_partial_column_anchors(
    band: tuple[float, float],
) -> None:
    """The same measurement on the ground-to-air rungs."""
    partial = frozenset(_ANCHORS) - _FULL_COLUMN
    _before, after = _TAU_PARITY_PARTIAL_COLUMN[band]
    assert _rms_parity(partial, band) == pytest.approx(after, abs=0.002)


@pytest.mark.level2
def test_the_visible_parity_improves_by_more_than_five_times() -> None:
    """The headline result, stated as an ordering.

    0.45–0.70 µm improves 5.3× on the full columns and 6.8× on the partial
    ones; the two composite visible bands the scenarios actually integrate
    over — 0.40–0.90 and 0.45–0.85 µm — improve 4.2× and 2.5×.
    """
    for band, factor in (((0.45, 0.70), 5.0), ((0.40, 0.90), 4.0), ((0.45, 0.85), 2.4)):
        before, after = _TAU_PARITY_FULL_COLUMN[band]
        assert before / after > factor, f"{band} improved only {before / after:.2f}×"


@pytest.mark.level2
def test_bands_beyond_3um_are_parity_identical() -> None:
    """MWIR and LWIR parity does not move — the change is a VIS/NIR one.

    The floors there moved by ≤ 0.001 OD (the Rayleigh tail), which is below
    the 0.002 resolution this parity metric is pinned at.
    """
    for band in ((3.50, 5.00), (8.00, 12.00)):
        before, after = _TAU_PARITY_FULL_COLUMN[band]
        assert abs(after - before) <= 0.002


@pytest.mark.level2
def test_the_nir_window_parity_degrades_and_why() -> None:
    """0.70–1.30 µm gets worse: 0.0312 → 0.0402 full column, and that is honest.

    The re-fit hands this row a floor of 0.0517 where a tape7-grid-consistent
    reference would want ~0.0383 — the +0.0114 mixed-grid offset pinned in
    ``test_the_nonwater_reference_grid_is_the_generators``.  The old row was
    under by 0.0383 and the new one is over by 0.0134, so the *bias* falls by
    ~3× while this particular RMS rises, because the residual is now spread
    unevenly across the profile anchors rather than sitting one-sided.

    Recorded rather than tuned away: correcting it means changing CU-161's
    non-water reference grid, which is a new calibration convention and needs
    its own authorisation.  Kept as a pinned characterization so the trade is
    visible to whoever takes that on.
    """
    before, after = _TAU_PARITY_FULL_COLUMN[(0.70, 1.30)]
    assert after > before
    # Still small in absolute terms — 4 % on a band mean — and an order below
    # the visible error the same change removes.
    assert after < 0.05
    vis_before, vis_after = _TAU_PARITY_FULL_COLUMN[(0.45, 0.70)]
    assert (vis_before - vis_after) > 10.0 * (after - before)
