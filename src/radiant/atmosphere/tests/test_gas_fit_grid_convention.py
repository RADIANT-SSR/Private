"""Level-0: the gas fit's two band optical depths are measured on one grid (CU-336).

``floor_add = max(0, OD_measured − OD_nonwater)`` is a *difference* of two band
optical depths.  Both are formed the same way — ``−ln`` of the unweighted mean of
the transmittance samples inside the band — so the difference is only meaningful
if the two are sampled the same way.  They were not: the measured side comes off
MODTRAN's native grid, which is uniform in **wavenumber** (1 cm⁻¹, so
$\\Delta\\lambda \\propto \\lambda^2$ — dense in the blue, sparse in the LWIR), while
the generator evaluated its non-water reference on a uniform-λ grid.

Nothing here needs the MODTRAN run set.  The estimator's grid sensitivity is a
property of the model's own $\\lambda^{-4}$-steep Rayleigh term, so it is
measurable, and the recovery invariant is exact arithmetic:

(a) **the defect, sized** — the same non-water reference read on the two grids
    differs by the offsets CU-335 measured and CU-336 removed;
(b) **the invariant** — a known optical depth added to a reference spectrum is
    recovered exactly when both sides share a grid, and is recovered wrong by
    precisely the grid offset when they do not;
(c) **the shipped table** — the two VIS/NIR floors carry the corrected values,
    and the 0.45 µm edge no longer steps.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.atmosphere.protocol import AtmosphericGeometry
from radiant.atmosphere.simple import (
    _CALIBRATED_GAS_REGIONS,
    SimpleAtmosphere,
    _GasRegion,
)

#: The generator's anchor geometry: nadir, ground to the 100 km column top.
_GEOMETRY = AtmosphericGeometry(sensor_altitude_m=1.0e5, target_altitude_m=0.0, path_zenith_rad=0.0)

#: MODTRAN's delivered resolution, in wavenumber [cm⁻¹].
_TAPE7_STEP_CM1 = 1.0

#: The offsets CU-335 measured and recorded as its residual, per band [OD].
#: ``native − uniform-λ``, i.e. how much the old convention under-read the
#: reference and therefore over-fitted the floor.
_MEASURED_OFFSET: dict[tuple[float, float], float] = {
    (0.45, 0.70): 0.0222,
    (0.70, 1.30): 0.0114,
    (3.50, 5.00): 0.0004,
}


def _floor_free_table() -> tuple[_GasRegion, ...]:
    """The table with every ``floor_od`` zeroed — the generator's convention."""
    return tuple(
        _GasRegion(r.lo_um, r.hi_um, 0.0, r.k_h2o, r.b_h2o) for r in _CALIBRATED_GAS_REGIONS
    )


def _uniform_lambda_grid(lo: float, hi: float) -> np.ndarray:
    """The grid the generator used to use: uniform in wavelength."""
    return np.linspace(lo, hi, 400)


def _uniform_wavenumber_grid(lo: float, hi: float) -> np.ndarray:
    """MODTRAN's weighting: uniform in wavenumber, at the delivered 1 cm⁻¹."""
    nu_hi, nu_lo = 1.0e4 / lo, 1.0e4 / hi
    n_points = max(int(round((nu_hi - nu_lo) / _TAPE7_STEP_CM1)) + 1, 2)
    return np.sort(1.0e4 / np.linspace(nu_lo, nu_hi, n_points))


def _nonwater_tau(monkeypatch: pytest.MonkeyPatch, grid: np.ndarray) -> np.ndarray:
    """Rayleigh + aerosol transmittance at w → 0 with the floors removed."""
    monkeypatch.setattr("radiant.atmosphere.simple._CALIBRATED_GAS_REGIONS", _floor_free_table())
    atm = SimpleAtmosphere(precipitable_water_cm=1e-9)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        state = atm.build_state(grid, _GEOMETRY)
    return np.asarray(state.transmittance.values)


def _band_od(tau: np.ndarray) -> float:
    """The generator's band optical depth: −ln of the band-mean τ."""
    return -math.log(max(float(np.mean(tau)), 1e-9))


def _region(lo_um: float, hi_um: float) -> _GasRegion:
    for region in _CALIBRATED_GAS_REGIONS:
        if region.lo_um == lo_um and region.hi_um == hi_um:
            return region
    raise AssertionError(f"no calibrated region spans {lo_um}–{hi_um} µm")


# ----------------------------------------------------------------------
# (a) The defect, sized on the model alone
# ----------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("band", list(_MEASURED_OFFSET), ids=lambda b: f"{b[0]}-{b[1]}um")
def test_the_two_grids_disagree_by_the_recorded_offset(
    band: tuple[float, float], monkeypatch: pytest.MonkeyPatch
) -> None:
    """One spectrum, two grids, two band optical depths — and the gap is the bias.

    A band mean weights the samples it is given.  A wavenumber-uniform grid
    puts $\\propto \\lambda^{-2}$ more of them at the blue end of a visible band,
    where a $\\lambda^{-4}$ Rayleigh term makes τ smallest, so it reads a larger
    optical depth than a wavelength-uniform grid over the same interval.  The
    old generator subtracted the λ-uniform number from a ν-uniform one, so the
    whole of this gap landed in ``floor_add``.

    Beyond 1.3 µm Rayleigh is four orders down and the two agree to 0.0004,
    which is why the SWIR/MWIR/LWIR rows barely moved.
    """
    lam_od = _band_od(_nonwater_tau(monkeypatch, _uniform_lambda_grid(*band)))
    nu_od = _band_od(_nonwater_tau(monkeypatch, _uniform_wavenumber_grid(*band)))
    assert nu_od - lam_od == pytest.approx(_MEASURED_OFFSET[band], abs=0.002)


@pytest.mark.level0
def test_the_bias_is_one_signed_toward_an_over_large_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mixed grid never under-fitted a floor, on any band in the table.

    ``floor_add = OD_measured(ν grid) − OD_reference(λ grid)``, and the
    reference read low on every band because τ falls monotonically toward the
    blue everywhere Rayleigh matters.  That one-sidedness is why the fix moves
    every floor the same way (down) rather than scattering them.
    """
    for region in _CALIBRATED_GAS_REGIONS:
        band = (region.lo_um, region.hi_um)
        lam_od = _band_od(_nonwater_tau(monkeypatch, _uniform_lambda_grid(*band)))
        nu_od = _band_od(_nonwater_tau(monkeypatch, _uniform_wavenumber_grid(*band)))
        assert nu_od >= lam_od - 1e-9, f"{band}: the λ grid read HIGHER, by {lam_od - nu_od:.5f}"


# ----------------------------------------------------------------------
# (b) The invariant: one grid recovers a known optical depth exactly
# ----------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("band", [(0.45, 0.70), (0.70, 1.30), (3.50, 5.00)])
def test_one_grid_recovers_an_added_optical_depth_exactly(
    band: tuple[float, float], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fit's arithmetic, verified against a known-good answer.

    Take the non-water reference, multiply it by ``exp(−Δ)`` for a known
    constant Δ, and the generator's subtraction must return Δ — that is the
    whole content of ``floor_add``.  A constant factor survives the band mean
    exactly (``mean(c·τ) = c·mean(τ)``), so on a single grid the recovery is an
    identity and holds to machine precision *whichever* grid is used.  That is
    the sense in which the two references "agree": not that the two grids give
    the same band OD, but that the quantity the fit extracts is grid-invariant
    once both sides share one.
    """
    delta = 0.1234
    for grid_builder in (_uniform_lambda_grid, _uniform_wavenumber_grid):
        tau = _nonwater_tau(monkeypatch, grid_builder(*band))
        recovered = _band_od(tau * math.exp(-delta)) - _band_od(tau)
        assert recovered == pytest.approx(delta, abs=1e-12)


@pytest.mark.level0
def test_mixing_the_grids_recovers_the_added_depth_wrong_by_the_offset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """And the old convention's error is exactly the offset, not something else.

    Same known Δ, but measured on the wavenumber grid and referenced against
    the wavelength grid — the pre-CU-336 arithmetic.  What comes back is
    ``Δ + offset``, which is the statement that the whole of the floor bias was
    the grid mismatch and none of it was the fit.
    """
    band = (0.45, 0.70)
    delta = 0.1234
    measured = _band_od(
        _nonwater_tau(monkeypatch, _uniform_wavenumber_grid(*band)) * math.exp(-delta)
    )
    reference = _band_od(_nonwater_tau(monkeypatch, _uniform_lambda_grid(*band)))
    assert measured - reference == pytest.approx(delta + _MEASURED_OFFSET[band], abs=0.002)


# ----------------------------------------------------------------------
# (c) The shipped table carries the corrected convention
# ----------------------------------------------------------------------


@pytest.mark.level0
def test_the_shipped_visnir_floors_are_the_corrected_ones() -> None:
    """0.1375 and 0.0402 — the CU-335 values less the measured offsets."""
    assert _region(0.45, 0.70).floor_od == 0.1375
    assert _region(0.70, 1.30).floor_od == 0.0402


@pytest.mark.level0
def test_the_045um_edge_no_longer_steps_by_a_measurement_convention() -> None:
    """0.1262 → 0.1375 across 0.45 µm, where the table used to jump 0.0000 → 0.1597.

    The short-λ deficit the floor absorbs is a smooth function of wavelength
    (CU-337: most of it is the aerosol model), so a 0.16 OD step at one region
    edge described the old reference's grid, not the atmosphere.  Sized against
    the neighbouring real step at 0.70 µm (0.1375 → 0.0402) so the bound is a
    comparison rather than a bare constant.
    """
    uv, vis, nir = (
        _region(0.30, 0.45).floor_od,
        _region(0.45, 0.70).floor_od,
        _region(0.70, 1.30).floor_od,
    )
    assert abs(vis - uv) < 0.2 * abs(vis - nir)
