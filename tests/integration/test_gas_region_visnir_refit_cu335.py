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
    transmissive.  After the re-fit the model read 0.476, a 4.3 % OD
    overshoot, and after CU-336 it reads 0.457 — 0.1 %.

(c) **Band-mean τ parity across all three vintages**, against the thirteen
    full-column and twelve partial-column anchors.

**CU-336 (2026-09-01) is composed on top and this module tracks the composed
table.**  CU-335 recorded, as its own residual, that ``floor_add`` subtracts a
band optical depth measured on a uniform-λ grid from one measured on MODTRAN's
native wavenumber grid, biasing every floor high by +0.0222 OD at 0.45–0.70 µm
and +0.0114 at 0.70–1.30 µm.  The generator now measures both on the ladder's
grid.  The 0.70–1.30 µm parity CU-335 degraded (0.0312 → 0.0402) recovers past
its starting point (0.0286), the visible improves a further 2.6×, and the
0.30–0.45 µm row comes off the zero clamp — the same correction removed a
*coverage* mismatch there, the tape7 grid starting at 0.374953 µm.
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

#: The rows the composed CU-335 + CU-336 re-fit moved off their CU-161
#: vintage, and the floor each shipped with *before*.  CU-336 added the
#: 0.30–0.45 µm row: the coverage half of the grid correction took it off
#: the zero clamp.
_MOVED: dict[tuple[float, float], float] = {
    (0.30, 0.45): 0.0000,
    (0.45, 0.70): 0.0000,
    (0.70, 1.30): 0.0000,
    (1.50, 1.75): 0.0133,
    (2.05, 2.40): 0.0725,
    (2.40, 3.10): 0.7434,
}

#: The generator's non-water reference grid **since CU-336**: the tape7 grid
#: itself, so the reference and the ladder's band OD share one weighting.
#: Read from A1 at use time; every staged run carries the same grid.
_REFERENCE_RUN = "A1"

#: The grid the generator used *before* CU-336: uniform in λ over the table's
#: full span.  Kept because the difference between the two is the bias — see
#: ``test_the_nonwater_reference_grid_is_the_ladders``.
_PRE_CU336_GRID = np.linspace(0.30, 14.29, 3000)


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
    if first <= 1e-4:
        # The generator's no-measurable-water branch: the band's optical
        # depth is water-independent, so the whole of it is the floor and
        # the water term is switched off.  0.30–0.45 µm is the only row in
        # the table that takes it.
        return od[1], 0.0, 1.0
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
    reference_grid, _tau = _spectrum(_REFERENCE_RUN)
    floor_add = max(od0 - _nonwater_od(monkeypatch, reference_grid, band), 0.0)
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
    reference_grid, _tau = _spectrum(_REFERENCE_RUN)
    nonwater = _nonwater_od(monkeypatch, reference_grid, band)
    # Rayleigh dominates the non-water OD in the visible; scaling the whole
    # reference by 8 is a lower bound on the pre-CU-253 value, and even that
    # bound already exceeds OD0.
    assert od0 - 8.0 * nonwater < 0.0
    assert od0 - nonwater > 0.0


@pytest.mark.level2
def test_the_nonwater_reference_grid_is_the_ladders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The floor is grid-relative, and the grid is now the ladder's (CU-336).

    The generator used to measure its non-water reference on a uniform
    3000-point λ grid while the ladder's band OD came off the tape7 grid,
    which is uniform in *wavenumber* and therefore weights the short-λ end
    of a VIS band more heavily.  Where the spectrum is steep — Rayleigh
    goes as $\\lambda^{-4}$ — the two disagree, and the difference landed in
    the floor: +0.022 OD at 0.45–0.70 µm and +0.011 at 0.70–1.30 µm, both
    in the direction of an over-large floor.  Beyond 1.3 µm it is ≤ 0.0004.

    Both halves are pinned.  The offsets are what CU-335 recorded and
    CU-336 removed, so they stay measured here; and the reference is now
    read on the tape7 grid, which is what makes ``floor_add`` a difference
    of two like-for-like band means.  The 0.70–1.30 µm parity that moved
    the wrong way under CU-335 recovers in
    ``test_the_nir_window_parity_recovers``.
    """
    tape7_grid, _tau = _spectrum(_REFERENCE_RUN)
    for band, expected in (
        ((0.45, 0.70), 0.0222),
        ((0.70, 1.30), 0.0114),
        ((3.50, 5.00), 0.0004),
    ):
        pre_cu336 = _nonwater_od(monkeypatch, _PRE_CU336_GRID, band)
        native = _nonwater_od(monkeypatch, tape7_grid, band)
        assert native - pre_cu336 == pytest.approx(expected, abs=0.002)


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
    """0.45–0.70 µm at A1: 0.320 → 0.476 → 0.457 against MODTRAN's 0.456.

    This is the number the CU-335 entry was opened on.  Before that re-fit
    the model under-read the band's optical depth by 30 % (τ 14.6 % high);
    after it, it over-read by 4.3 % (τ 1.9 % low).  That residual overshoot
    was the mixed-grid artifact characterised above — the floor was fitted
    against a uniform-λ non-water reference and evaluated here on the tape7
    grid — and CU-336 removed it: the model now reads 0.4566, **0.1 %**
    over.  Two independent measurements agreeing to a part in a thousand is
    the strongest single statement that the grid was the whole residual.
    """
    reference_wl, reference_tau = _spectrum("A1")
    modtran_od = _band_od(reference_wl, reference_tau, 0.45, 0.70)
    model_wl, model_tau = _model_tau("A1")
    model_od = _band_od(model_wl, model_tau, 0.45, 0.70)

    assert modtran_od == pytest.approx(0.4561, abs=0.002)
    assert model_od == pytest.approx(0.4566, abs=0.002)
    assert abs(model_od / modtran_od - 1.0) < 0.01


# ---------------------------------------------------------------------------
# (c) Band-mean τ parity — the results record
# ---------------------------------------------------------------------------

#: RMS |ln(model/MODTRAN)| of band-mean τ over the thirteen full-column
#: anchors, at each of the three table vintages: the CU-161 floors, the
#: CU-335 re-fit (measured 2026-08-30), and the CU-336 grid correction
#: (measured 2026-09-01).  The assertion pins the last.
_TAU_PARITY_FULL_COLUMN: dict[tuple[float, float], tuple[float, float, float]] = {
    (0.45, 0.70): (0.1556, 0.0294, 0.0111),
    (0.70, 1.30): (0.0312, 0.0402, 0.0286),
    (0.45, 0.85): (0.1105, 0.0440, 0.0244),
    (0.85, 1.40): (0.0461, 0.0314, 0.0254),
    (0.40, 0.90): (0.1035, 0.0244, 0.0292),
    (1.50, 1.75): (0.0366, 0.0463, 0.0461),
    (2.05, 2.40): (0.0430, 0.0457, 0.0455),
    (3.50, 5.00): (0.1106, 0.1107, 0.1103),
    (8.00, 12.00): (0.0482, 0.0482, 0.0482),
}

#: The same measurement over the twelve partial-column anchors (K/N/O
#: ground-to-air rungs).
_TAU_PARITY_PARTIAL_COLUMN: dict[tuple[float, float], tuple[float, float, float]] = {
    (0.45, 0.70): (0.1456, 0.0214, 0.0180),
    (0.70, 1.30): (0.0263, 0.0675, 0.0567),
    (0.45, 0.85): (0.0938, 0.0434, 0.0274),
    (0.40, 0.90): (0.0893, 0.0266, 0.0298),
    (3.50, 5.00): (0.1812, 0.1812, 0.1810),
    (8.00, 12.00): (0.1047, 0.1047, 0.1047),
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

    All three vintages are here: the dict carries the CU-161 and CU-335
    values for the reader, and the assertion pins the CU-336 value the
    shipped table produces.
    """
    _cu161, _cu335, cu336 = _TAU_PARITY_FULL_COLUMN[band]
    assert _rms_parity(_FULL_COLUMN, band) == pytest.approx(cu336, abs=0.002)


@pytest.mark.level2
@pytest.mark.parametrize("band", list(_TAU_PARITY_PARTIAL_COLUMN), ids=lambda b: f"{b[0]}-{b[1]}um")
def test_band_mean_tau_parity_against_the_partial_column_anchors(
    band: tuple[float, float],
) -> None:
    """The same measurement on the ground-to-air rungs."""
    partial = frozenset(_ANCHORS) - _FULL_COLUMN
    _cu161, _cu335, cu336 = _TAU_PARITY_PARTIAL_COLUMN[band]
    assert _rms_parity(partial, band) == pytest.approx(cu336, abs=0.002)


@pytest.mark.level2
def test_the_visible_parity_improves_across_both_refits() -> None:
    """The headline result, stated as an ordering over the two vintages.

    0.45–0.70 µm improves 5.3× on the full columns under CU-335 and a
    further 2.6× under CU-336, 14× end to end; 0.45–0.85 µm improves 4.5×
    end to end.  0.40–0.90 µm is the one composite that gives a little back
    at the second step — see
    ``test_the_composite_vis_band_loses_a_cancellation``.
    """
    for band, factor in (((0.45, 0.70), 12.0), ((0.45, 0.85), 4.0)):
        cu161, _cu335, cu336 = _TAU_PARITY_FULL_COLUMN[band]
        assert cu161 / cu336 > factor, f"{band} improved only {cu161 / cu336:.2f}× since CU-161"
    for band in ((0.45, 0.70), (0.45, 0.85), (0.85, 1.40), (0.70, 1.30)):
        _cu161, cu335, cu336 = _TAU_PARITY_FULL_COLUMN[band]
        assert cu336 < cu335, f"{band} did not improve across CU-336: {cu335} -> {cu336}"


@pytest.mark.level2
def test_bands_beyond_3um_are_parity_identical() -> None:
    """MWIR and LWIR parity does not move — the change is a VIS/NIR one.

    The floors there moved by ≤ 0.001 OD (the Rayleigh tail), which is below
    the 0.002 resolution this parity metric is pinned at.  True of CU-335
    and of CU-336 separately, so it is asserted against both.
    """
    for band in ((3.50, 5.00), (8.00, 12.00)):
        cu161, cu335, cu336 = _TAU_PARITY_FULL_COLUMN[band]
        assert abs(cu335 - cu161) <= 0.002
        assert abs(cu336 - cu335) <= 0.002


@pytest.mark.level2
def test_the_nir_window_parity_recovers() -> None:
    """0.70–1.30 µm: 0.0312 → 0.0402 under CU-335, back to 0.0286 under CU-336.

    This row is the reason CU-336 exists.  CU-335 handed it a floor of
    0.0517 where a ladder-grid-consistent reference wants 0.0402 — the
    +0.0114 offset pinned in ``test_the_nonwater_reference_grid_is_the_ladders``
    — and the RMS rose even though the *bias* fell ~3×, because the residual
    stopped being one-sided.  With the convention corrected the floor lands
    at that 0.0402 and the parity comes back past where it started: better
    than the CU-161 vintage, not merely better than CU-335.
    """
    cu161, cu335, cu336 = _TAU_PARITY_FULL_COLUMN[(0.70, 1.30)]
    assert cu335 > cu161, "the CU-335 degradation this CU was opened on is gone from the record"
    assert cu336 < cu335, "CU-336 did not recover the NIR window"
    assert cu336 < cu161, "CU-336 recovered the degradation but not past the CU-161 baseline"


@pytest.mark.level2
def test_the_composite_vis_band_loses_a_cancellation() -> None:
    """0.40–0.90 µm reads slightly worse (0.0244 → 0.0292), and it is not a regression.

    Its two halves are each far more accurate than before: 0.40–0.45 µm was
    8–21 % too transmissive on every one of the thirteen full-column
    anchors under CU-335 — the 0.30–0.45 µm row was pinned at the zero clamp
    by the coverage mismatch — and lands inside 0.4 % under CU-336.  What
    the composite loses is the cancellation between that one-sided positive
    error and the small negative one over 0.45–0.90 µm.  Sub-band accuracy
    is the physics; a band mean that was right by cancellation was not.

    The bands that contain no such cancellation (every one asserted in
    ``test_the_visible_parity_improves_across_both_refits``) improve, and
    even this one is 3.5× better than the CU-161 vintage.
    """
    cu161, cu335, cu336 = _TAU_PARITY_FULL_COLUMN[(0.40, 0.90)]
    assert cu336 > cu335
    assert cu161 / cu336 > 3.0
    # The narrower band that carries the correction is the one to check.
    assert _rms_parity(_FULL_COLUMN, (0.40, 0.45)) < 0.02
