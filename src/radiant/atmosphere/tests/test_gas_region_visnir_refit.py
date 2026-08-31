"""Level-0 tests for the CU-335 VIS/NIR/SWIR re-fit of the gas table.

The calibrated gas table was fitted by CU-161 on 2026-07-17, when the
model's Rayleigh optical depth was ~8× too large.  ``floor_add`` is
defined as ``max(0, OD_measured − OD_Rayleigh+aerosol)``, so an inflated
Rayleigh term drove the VIS/NIR floors to the zero clamp.  CU-253 then
cut Rayleigh by ~8× and the fit was never re-run: the shipped floors
below ~1.5 µm stayed at zero, and the model ran too transmissive in the
visible.

CU-335 re-runs the repaired generator (`scripts/fit_simple_atmosphere_gas_bands.py`)
over the same delivered ladder with the same closed form.  Only the
water-independent ``floor_od`` column moves — ``k_h2o`` and ``b_h2o`` are
fitted from the MODTRAN ladder alone and never see the model's Rayleigh
term, so their bit-identity across the re-fit is the check that the
re-fit changed the calibration reference and not the fit.

Coverage:

(a) **the shipped table** — every row's three coefficients pinned to the
    generator's printed output, so a hand edit or a partial paste fails;
(b) **what moved and what did not** — ``k``/``b`` bit-identical on all
    seventeen rows; floors bit-identical from 5.00 µm up (including the
    CU-330 ozone triple); the VIS/NIR floors lifted off the zero clamp;
(c) **direction and magnitude** — every moved floor moved *up* (less
    transmissive), by the CU-330-predicted amounts, and the residual
    MWIR motion is the Rayleigh $\\lambda^{-4}$ tail at ≤ 0.001 OD;
(d) **the CU-267 blend invariants survive the re-fit** — no ramp
    overlap, continuity at every edge, and the exact arithmetic-mean
    edge value with the new floors.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.atmosphere.protocol import AtmosphericGeometry
from radiant.atmosphere.simple import (
    _CALIBRATED_GAS_REGIONS,
    GAS_REGION_BLEND_HALF_WIDTH_UM,
    SimpleAtmosphere,
    _GasRegion,
)

HW: float = GAS_REGION_BLEND_HALF_WIDTH_UM

#: The shipped table after the CU-335 re-fit, exactly as
#: ``scripts/fit_simple_atmosphere_gas_bands.py`` prints it:
#: ``(lo_um, hi_um, floor_od, k_h2o, b_h2o)``.
EXPECTED_TABLE: tuple[tuple[float, float, float, float, float], ...] = (
    (0.30, 0.45, 0.0000, 0.0000, 1.000),
    (0.45, 0.70, 0.1597, 0.0025, 0.874),
    (0.70, 1.30, 0.0517, 0.1245, 0.434),
    (1.30, 1.50, 0.0000, 1.0933, 0.327),
    (1.50, 1.75, 0.0219, 0.0282, 0.645),
    (1.75, 2.05, 0.0000, 1.1186, 0.216),
    (2.05, 2.40, 0.0749, 0.0320, 0.843),
    (2.40, 3.10, 0.7444, 0.9666, 0.560),
    (3.10, 3.50, 0.1371, 0.5824, 0.457),
    (3.50, 5.00, 0.4498, 0.0944, 0.808),
    (5.00, 7.50, 1.3543, 1.7850, 0.530),
    (7.50, 8.00, 0.9424, 0.9210, 0.673),
    (8.00, 9.40, 0.1494, 0.0992, 1.204),
    (9.40, 9.90, 0.8877, 0.0409, 1.701),
    (9.90, 10.00, 0.3013, 0.0379, 1.805),
    (10.00, 12.00, 0.0471, 0.0602, 1.750),
    (12.00, 14.29, 0.5956, 0.1398, 1.583),
)

#: ``floor_od`` as it shipped *before* CU-335 — the CU-161 vintage for
#: everything except the 8–10 µm triple, which is CU-330's.  Written out
#: so the tests can state exactly which rows the re-fit was allowed to
#: move, rather than asserting a delta against a value they compute.
FLOOR_BEFORE: dict[tuple[float, float], float] = {
    (0.30, 0.45): 0.0000,
    (0.45, 0.70): 0.0000,
    (0.70, 1.30): 0.0000,
    (1.30, 1.50): 0.0000,
    (1.50, 1.75): 0.0133,
    (1.75, 2.05): 0.0000,
    (2.05, 2.40): 0.0725,
    (2.40, 3.10): 0.7434,
    (3.10, 3.50): 0.1366,
    (3.50, 5.00): 0.4497,
    (5.00, 7.50): 1.3543,
    (7.50, 8.00): 0.9424,
    (8.00, 9.40): 0.1494,
    (9.40, 9.90): 0.8877,
    (9.90, 10.00): 0.3013,
    (10.00, 12.00): 0.0471,
    (12.00, 14.29): 0.5956,
}

#: Rows at and beyond 5 µm, where Rayleigh is nine orders below the gas
#: opacity and the CU-253 correction is therefore invisible.  This set
#: includes the three CU-330 ozone rows, whose bit-identity is what says
#: CU-335 did not disturb the 2026-08-29 re-fit.
UNMOVED_FROM_UM: float = 5.00


def _region(lo_um: float, hi_um: float) -> _GasRegion:
    for region in _CALIBRATED_GAS_REGIONS:
        if region.lo_um == lo_um and region.hi_um == hi_um:
            return region
    raise AssertionError(f"no calibrated region spans {lo_um}–{hi_um} µm")


def _coeffs(lam: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return SimpleAtmosphere._region_params(np.asarray(lam, dtype=np.float64))  # noqa: SLF001


# ----------------------------------------------------------------------
# (a) The shipped table
# ----------------------------------------------------------------------


@pytest.mark.level0
def test_the_table_has_the_same_seventeen_regions_as_before() -> None:
    """The re-fit moved coefficients, never a partition boundary.

    A moved edge would drag the CU-267 ramp with it and move every band
    that straddles it, which is a different change with a different
    review.  CU-335 is a re-calibration of the existing partition.
    """
    partition = tuple((r.lo_um, r.hi_um) for r in _CALIBRATED_GAS_REGIONS)
    assert partition == tuple((lo, hi) for lo, hi, _f, _k, _b in EXPECTED_TABLE)


@pytest.mark.level0
@pytest.mark.parametrize("row", EXPECTED_TABLE, ids=lambda r: f"{r[0]}-{r[1]}um")
def test_every_shipped_row_matches_the_generator_output(
    row: tuple[float, float, float, float, float],
) -> None:
    """Bit-exact pin of the table the generator printed.

    Equality, not ``approx``: the table is a pasted generator artifact
    (Rule 26), so any difference at all means the paste and the
    generator have diverged.
    """
    lo_um, hi_um, floor_od, k_h2o, b_h2o = row
    region = _region(lo_um, hi_um)
    assert region.floor_od == floor_od
    assert region.k_h2o == k_h2o
    assert region.b_h2o == b_h2o


# ----------------------------------------------------------------------
# (b) What moved and what did not
# ----------------------------------------------------------------------


@pytest.mark.level0
def test_the_water_fit_is_bit_identical_across_the_refit() -> None:
    """``k_h2o`` and ``b_h2o`` cannot move, and did not.

    The water term is solved in closed form from three MODTRAN band
    optical depths (D4/A1/D5) with no reference to the RADIANT model at
    all.  Only ``floor_add = max(0, OD0 − OD_Rayleigh+aerosol)`` reads
    the model, so only it can respond to CU-253's Rayleigh cut.  A
    moved ``k`` or ``b`` here would mean the ladder or the closed form
    changed — a different finding entirely.
    """
    pre_refit_water = {
        (0.30, 0.45): (0.0000, 1.000),
        (0.45, 0.70): (0.0025, 0.874),
        (0.70, 1.30): (0.1245, 0.434),
        (1.30, 1.50): (1.0933, 0.327),
        (1.50, 1.75): (0.0282, 0.645),
        (1.75, 2.05): (1.1186, 0.216),
        (2.05, 2.40): (0.0320, 0.843),
        (2.40, 3.10): (0.9666, 0.560),
        (3.10, 3.50): (0.5824, 0.457),
        (3.50, 5.00): (0.0944, 0.808),
        (5.00, 7.50): (1.7850, 0.530),
        (7.50, 8.00): (0.9210, 0.673),
        (8.00, 9.40): (0.0992, 1.204),
        (9.40, 9.90): (0.0409, 1.701),
        (9.90, 10.00): (0.0379, 1.805),
        (10.00, 12.00): (0.0602, 1.750),
        (12.00, 14.29): (0.1398, 1.583),
    }
    for (lo_um, hi_um), (k_h2o, b_h2o) in pre_refit_water.items():
        region = _region(lo_um, hi_um)
        assert region.k_h2o == k_h2o, f"k_h2o moved at {lo_um}–{hi_um} µm"
        assert region.b_h2o == b_h2o, f"b_h2o moved at {lo_um}–{hi_um} µm"


@pytest.mark.level0
def test_floors_from_5um_up_are_bit_identical_including_the_ozone_triple() -> None:
    """Nothing at or beyond 5 µm moved — the CU-330 rows least of all.

    Rayleigh scattering falls as $\\lambda^{-4}$: at 5 µm its vertical
    optical depth is below $10^{-5}$, four orders under the smallest
    gas floor in the table, so an 8× correction to it cannot reach the
    fourth decimal the table carries.  The three CU-330 ozone rows were
    re-fitted on 2026-08-29 against the same convention and must come
    through this re-fit untouched.
    """
    for region in _CALIBRATED_GAS_REGIONS:
        if region.lo_um < UNMOVED_FROM_UM:
            continue
        before = FLOOR_BEFORE[(region.lo_um, region.hi_um)]
        assert region.floor_od == before, (
            f"{region.lo_um}–{region.hi_um} µm floor moved {before} → {region.floor_od}"
        )


@pytest.mark.level0
def test_the_vis_and_nir_floors_are_off_the_zero_clamp() -> None:
    """The defect CU-335 fixes, stated directly.

    0.45–0.70 and 0.70–1.30 µm shipped at ``floor_od = 0`` because the
    pre-CU-253 Rayleigh term over-supplied the measured opacity and the
    generator clamps ``floor_add`` at zero rather than going negative.
    With Rayleigh corrected there is real well-mixed absorption left to
    account for (O₃ Chappuis, O₂ B/A bands, the water continuum below
    the ladder's resolution) and the clamp no longer binds.
    """
    assert _region(0.45, 0.70).floor_od > 0.0
    assert _region(0.70, 1.30).floor_od > 0.0


@pytest.mark.level0
def test_the_uv_row_stays_clamped_because_the_aerosol_still_over_absorbs() -> None:
    """0.30–0.45 µm keeps ``floor_od = 0`` — the clamp still binds there.

    The generator measures ``OD0 = 0.768`` against a model non-water
    ``0.859`` at 0.30–0.45 µm: even after the Rayleigh cut the rural-23
    aerosol alone over-supplies the band, so ``floor_add`` clamps.  That
    over-absorption is the separately-recorded VIS aerosol limitation,
    not something a gas floor may cancel by going negative.
    """
    assert _region(0.30, 0.45).floor_od == 0.0


# ----------------------------------------------------------------------
# (c) Direction and magnitude
# ----------------------------------------------------------------------


@pytest.mark.level0
def test_no_floor_decreased_so_the_model_is_never_more_transmissive() -> None:
    """Every moved floor moved up: τ falls or holds, never rises.

    Correcting an over-estimated Rayleigh term removes opacity the
    model was supplying for free, and the fit hands the same opacity
    back through the floor.  A floor that *fell* would mean the re-fit
    had found the old model under-absorbing, which contradicts the
    sign of the CU-253 correction.
    """
    for region in _CALIBRATED_GAS_REGIONS:
        before = FLOOR_BEFORE[(region.lo_um, region.hi_um)]
        assert region.floor_od >= before, (
            f"{region.lo_um}–{region.hi_um} µm floor fell {before} → {region.floor_od}"
        )


@pytest.mark.level0
@pytest.mark.parametrize(
    ("band", "predicted"),
    [
        ((0.45, 0.70), 0.1597),
        ((0.70, 1.30), 0.0517),
    ],
)
def test_the_vis_nir_floors_land_where_cu330_predicted(
    band: tuple[float, float], predicted: float
) -> None:
    """CU-330 measured these two floors before CU-335 was authorised.

    The 2026-08-29 generator repair printed 0.1597 and 0.0517 for the
    two rows and recorded them in the CU-335 entry as the expected
    landing point.  Re-deriving them a day later on the same ladder
    must reproduce them, or the ladder or the model moved underneath
    the measurement.
    """
    assert _region(*band).floor_od == pytest.approx(predicted, abs=5.0e-5)


@pytest.mark.level0
def test_the_mwir_rows_move_only_by_the_rayleigh_tail() -> None:
    """2.40–5.00 µm moves, but by ≤ 0.001 OD — the $\\lambda^{-4}$ tail.

    These three rows are *not* bit-identical across the re-fit, which
    the CU-335 charter did not anticipate.  The motion is real and it is
    tiny: Rayleigh's vertical OD is ~$3\\times10^{-4}$ at 2.4 µm and
    ~$4\\times10^{-5}$ at 4 µm, so removing 7/8 of it leaves a few parts
    in ten thousand of optical depth to reassign to the floor.  At
    0.001 OD the induced τ change is 0.1 %, below every golden tolerance
    in the suite.  Pinned as a bound so a future re-fit that moves them
    by more than the tail cannot pass silently.
    """
    for lo_um, hi_um in ((2.40, 3.10), (3.10, 3.50), (3.50, 5.00)):
        delta = _region(lo_um, hi_um).floor_od - FLOOR_BEFORE[(lo_um, hi_um)]
        assert 0.0 < delta <= 1.05e-3, f"{lo_um}–{hi_um} µm moved {delta:+.4f}, not a Rayleigh tail"


@pytest.mark.level0
def test_the_vis_floor_dominates_the_change() -> None:
    """0.45–0.70 µm carries 62 % of the total floor motion in the table.

    Rayleigh's $\\lambda^{-4}$ makes the correction overwhelmingly a
    visible-band effect; the ordering (VIS > NIR > SWIR > MWIR > 0) is
    the signature that this re-fit followed a Rayleigh change and not,
    say, a change to the water ladder.
    """
    moved = {
        (r.lo_um, r.hi_um): r.floor_od - FLOOR_BEFORE[(r.lo_um, r.hi_um)]
        for r in _CALIBRATED_GAS_REGIONS
    }
    total = sum(moved.values())
    assert moved[(0.45, 0.70)] / total > 0.6
    assert moved[(0.45, 0.70)] > moved[(0.70, 1.30)] > moved[(1.50, 1.75)]
    assert moved[(1.50, 1.75)] > moved[(2.05, 2.40)] > moved[(2.40, 3.10)]


@pytest.mark.level0
def test_the_visible_column_transmittance_drops(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end direction: a nadir full column loses ~14 % of its VIS τ.

    The floors are table constants; this asserts that they reach τ with
    the expected sign and size.  The comparison run zeroes the two
    re-fitted VIS/NIR floors, which *is* the pre-CU-335 table in those
    rows, so the ratio is the whole user-visible effect of the change at
    0.55 µm on a us_standard full column.
    """
    geometry = AtmosphericGeometry(
        sensor_altitude_m=1.0e5, target_altitude_m=0.0, path_zenith_rad=0.0
    )
    # Two samples: the model requires a grid, and both sit in the interior
    # of the 0.45–0.70 µm region so neither reads a blend ramp.
    wavelength_um = np.array([0.55, 0.56])

    def column_tau() -> float:
        atm = SimpleAtmosphere(standard_atmosphere="us_standard", precipitable_water_cm=1.4)
        state = atm.build_state(wavelength_um, geometry)
        return float(np.asarray(state.transmittance.values)[0])

    after = column_tau()
    monkeypatch.setattr(
        "radiant.atmosphere.simple._CALIBRATED_GAS_REGIONS",
        tuple(
            _GasRegion(r.lo_um, r.hi_um, FLOOR_BEFORE[(r.lo_um, r.hi_um)], r.k_h2o, r.b_h2o)
            for r in _CALIBRATED_GAS_REGIONS
        ),
    )
    before = column_tau()

    assert after < before
    assert 0.10 < 1.0 - after / before < 0.17


# ----------------------------------------------------------------------
# (d) The CU-267 blend invariants survive the re-fit
# ----------------------------------------------------------------------


@pytest.mark.level0
def test_blend_ramps_still_cannot_overlap() -> None:
    """Every region is still wider than the full blend width.

    CU-335 moved no edge, so this holds by construction — but it is the
    invariant a re-fit is most likely to break by re-partitioning, and
    asserting it here means the CU-335 table is self-validating rather
    than relying on the CU-267 suite having been run.
    """
    for region in _CALIBRATED_GAS_REGIONS:
        assert region.hi_um - region.lo_um > 2.0 * HW, f"{region} is narrower than the ramp"


@pytest.mark.level0
@pytest.mark.parametrize("edge_um", [r.lo_um for r in _CALIBRATED_GAS_REGIONS[1:]])
def test_the_floor_is_continuous_across_every_edge(edge_um: float) -> None:
    """No step in ``floor_od`` anywhere, with the new values in place.

    The re-fit put a 0.16 OD discontinuity where the table previously
    had 0.00 → 0.00 at the 0.45 µm and 0.70 µm edges, so the blend now
    carries real work there.  Sampled either side of each ramp and
    through it, the coefficient must vary by no more than the ramp's own
    span between adjacent samples.
    """
    lam = np.linspace(edge_um - 3.0 * HW, edge_um + 3.0 * HW, 601)
    floor, _k, _b = _coeffs(lam)
    span = float(np.ptp(floor))
    assert float(np.abs(np.diff(floor)).max()) <= span / 50.0 + 1e-12


@pytest.mark.level0
def test_the_070um_edge_carries_the_new_arithmetic_mean_floor() -> None:
    """Hand anchor: floor at 0.70 µm is (0.1597 + 0.0517)/2 = 0.1057.

    Before CU-335 this same hand value was (0.0 + 0.0)/2 = 0.0 — the
    docstring anchor in ``test_gas_region_blend.py`` says so.  The edge
    is the one place the two re-fitted rows meet, so it is the sharpest
    single-number statement that both moved.
    """
    floor, _k, _b = _coeffs(np.array([0.70]))
    assert float(floor[0]) == pytest.approx(0.1057, rel=1e-12, abs=1e-15)


@pytest.mark.level0
def test_interior_wavelengths_still_carry_the_exact_table_floor() -> None:
    """A λ at least ``hw`` from every edge reads the raw new floor.

    The re-fit must not have made any region so narrow, or any floor so
    large, that the ramps eat the calibrated interior — this is what
    keeps the calibration meaningful at all.
    """
    for region in _CALIBRATED_GAS_REGIONS:
        lam = np.linspace(region.lo_um + HW, region.hi_um - HW, 23)
        floor, _k, _b = _coeffs(lam)
        assert np.all(floor == region.floor_od), f"floor_od moved inside {region}"
