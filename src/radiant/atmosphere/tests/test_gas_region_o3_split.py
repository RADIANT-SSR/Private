"""Level-0 tests for the CU-330 ozone split of the 8–10 µm gas region.

Until CU-330 the calibrated table carried **one** region across
8.00–10.00 µm — a 2 µm slab spanning both the clean 8–9.4 µm window and
the 9.6 µm O₃ ν₂ fundamental — so ``τ(λ)`` had no identifiable ozone
structure anywhere and the ozone share of the well-mixed-gas floor was a
free parameter (the blocker recorded against CU-324 item 2).

The re-fit partitions that row at the measured band edges:

    8.00–9.40 µm   the clean window: continuum + water only
    9.40–9.90 µm   the O₃ ν₂ band core
    9.90–10.00 µm  the band's long-wave tail

These tests pin the *structure* the split creates, not the fit that
produced the numbers (that lives in
``tests/integration/test_gas_region_o3_fit_cu330.py``, which re-runs the
CU-161 closed form against the delivered ladder):

(a) the partition itself — three rows at the measured edges, the old
    slab gone, and every neighbouring region untouched;
(b) identifiability — the band core's water-independent floor stands a
    factor of several above the window either side of it, so the O₃
    opacity is a named quantity rather than an average;
(c) the ozone share the table now determines — the in-feature floor
    above the adjacent window's floor — which is what removes CU-324
    item 2's free parameter;
(d) the CU-267 blend invariants at the two new edges: continuity, the
    exact arithmetic-mean edge value, and the no-overlap width bound,
    whose binding region is now the 0.10 µm tail rather than the
    0.20 µm 1.30–1.50 µm region.
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

#: The window / band-core / tail boundaries the re-fit adopted [µm].
WINDOW = (8.00, 9.40)
CORE = (9.40, 9.90)
TAIL = (9.90, 10.00)


def _region(lo_um: float, hi_um: float) -> _GasRegion:
    for region in _CALIBRATED_GAS_REGIONS:
        if region.lo_um == lo_um and region.hi_um == hi_um:
            return region
    raise AssertionError(f"no calibrated region spans {lo_um}–{hi_um} µm")


def _coeffs(lam: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return SimpleAtmosphere._region_params(np.asarray(lam, dtype=np.float64))  # noqa: SLF001


# ----------------------------------------------------------------------
# (a) The partition
# ----------------------------------------------------------------------


@pytest.mark.level0
def test_the_flat_8_to_10_micron_slab_is_gone() -> None:
    """No region spans the whole 8–10 µm band any more.

    This is the CU-330 premise stated as an assertion: a single region
    covering both the window and the O₃ band is exactly the shape that
    cannot carry an ozone signature.
    """
    spans = [(r.lo_um, r.hi_um) for r in _CALIBRATED_GAS_REGIONS]
    assert (8.00, 10.00) not in spans
    assert not any(lo <= 9.00 and hi >= 9.80 for lo, hi in spans), (
        f"a region still spans the O₃ band and the window either side: {spans}"
    )


@pytest.mark.level0
def test_the_three_sub_regions_tile_the_old_slab_exactly() -> None:
    """Window + core + tail cover 8.00–10.00 µm with no gap and no overlap."""
    rows = [r for r in _CALIBRATED_GAS_REGIONS if 8.00 <= r.lo_um < 10.00]
    assert [(r.lo_um, r.hi_um) for r in rows] == [WINDOW, CORE, TAIL]
    assert rows[0].lo_um == 8.00
    assert rows[-1].hi_um == 10.00
    for lower, upper in zip(rows[:-1], rows[1:], strict=True):
        assert lower.hi_um == upper.lo_um


@pytest.mark.level0
def test_the_neighbouring_regions_are_untouched() -> None:
    """7.50–8.00 and 10.00–12.00 keep their CU-161 coefficients.

    The split is local: it re-fits one row, so every other row must be
    bit-identical or the change is not the one that was authorised.
    """
    below = _region(7.50, 8.00)
    above = _region(10.00, 12.00)
    assert (below.floor_od, below.k_h2o, below.b_h2o) == (0.9424, 0.9210, 0.673)
    assert (above.floor_od, above.k_h2o, above.b_h2o) == (0.0471, 0.0602, 1.750)


# ----------------------------------------------------------------------
# (b) Identifiability — the point of the exercise
# ----------------------------------------------------------------------


@pytest.mark.level0
def test_the_band_core_floor_towers_over_the_window() -> None:
    """The water-independent floor is what carries ozone.

    ``floor_od`` is the well-mixed-gas absorption; ozone is the only
    well-mixed absorber with a strong 9.4–9.9 µm feature, so a band-core
    floor several times the adjacent window's *is* the ozone signature.
    A ratio near 1 would mean the split found nothing.
    """
    window, core, tail = _region(*WINDOW), _region(*CORE), _region(*TAIL)
    assert core.floor_od / window.floor_od > 5.0
    assert core.floor_od > tail.floor_od > window.floor_od


@pytest.mark.level0
def test_the_water_term_weakens_where_the_gas_term_takes_over() -> None:
    """Inside the band the water coefficient drops and its exponent rises.

    Physically: the ozone band is opaque enough that the residual water
    response there is the LWIR continuum's, not a line-absorption
    response — a smaller ``k`` on a steeper (more continuum-like)
    exponent.  Read as a consistency check on the fit: if the split had
    merely re-labelled water absorption as gas floor, ``k`` would have
    risen with the floor rather than fallen.
    """
    window, core, tail = _region(*WINDOW), _region(*CORE), _region(*TAIL)
    assert core.k_h2o < window.k_h2o
    assert tail.k_h2o < window.k_h2o
    assert core.b_h2o > window.b_h2o
    assert tail.b_h2o > core.b_h2o


# ----------------------------------------------------------------------
# (c) The ozone share CU-324 item 2 was missing
# ----------------------------------------------------------------------


@pytest.mark.level0
def test_the_table_now_determines_the_ozone_share_of_the_in_feature_floor() -> None:
    """The share is arithmetic on the table, not a fitted parameter.

    In-feature floor = continuum floor (the adjacent window's, which
    contains no ozone) + the ozone excess.  So

        share_O₃ = (floor_core − floor_window) / floor_core

    is read off two committed numbers.  Before the split there was one
    region and therefore no second number to subtract — that is the
    literal content of "one free parameter with nothing on the τ side to
    pin it".
    """
    window, core = _region(*WINDOW), _region(*CORE)
    share = (core.floor_od - window.floor_od) / core.floor_od
    assert share == pytest.approx(0.8317, abs=5.0e-4)
    assert 0.0 < share < 1.0


# ----------------------------------------------------------------------
# (d) CU-267 blend invariants at the two new edges
# ----------------------------------------------------------------------


@pytest.mark.level0
def test_the_tail_is_the_narrowest_region_and_still_clears_the_blend() -> None:
    """The no-overlap bound's binding region is now 9.90–10.00 µm.

    CU-267's invariant is ``width > 2·hw``; the narrowest region used to
    be 1.30–1.50 µm (0.20 µm, 5× the 0.04 µm full ramp width) and is now
    the 0.10 µm ozone tail, still 2.5×.  Pinning *which* region binds is
    what makes a future narrowing fail loudly here.
    """
    widths = {(r.lo_um, r.hi_um): r.hi_um - r.lo_um for r in _CALIBRATED_GAS_REGIONS}
    narrowest = min(widths, key=lambda key: widths[key])
    assert narrowest == TAIL
    assert widths[narrowest] == pytest.approx(0.10, abs=1.0e-12)
    assert widths[narrowest] > 2.0 * HW


@pytest.mark.level0
@pytest.mark.parametrize("edge_um", [9.40, 9.90])
def test_the_new_edges_carry_the_arithmetic_mean_of_their_two_regions(edge_um: float) -> None:
    """S(0.5) = 0.5 exactly, so the edge value is the mean (CU-267 (c))."""
    below = next(r for r in _CALIBRATED_GAS_REGIONS if r.hi_um == edge_um)
    above = next(r for r in _CALIBRATED_GAS_REGIONS if r.lo_um == edge_um)
    floor, k, b = _coeffs(np.array([edge_um]))
    assert float(floor[0]) == pytest.approx(0.5 * (below.floor_od + above.floor_od), abs=1.0e-12)
    assert float(k[0]) == pytest.approx(0.5 * (below.k_h2o + above.k_h2o), abs=1.0e-12)
    assert float(b[0]) == pytest.approx(0.5 * (below.b_h2o + above.b_h2o), abs=1.0e-12)


@pytest.mark.level0
@pytest.mark.parametrize("edge_um", [9.40, 9.90])
def test_the_new_edges_are_continuous(edge_um: float) -> None:
    """No step survives at either new edge — the CU-267 failure mode."""
    # Not vacuous: the wavelength must actually be a region boundary, or
    # continuity here would be the trivial constancy of one flat region.
    assert edge_um in {r.lo_um for r in _CALIBRATED_GAS_REGIONS[1:]}
    lam = np.array([edge_um - 1.0e-9, edge_um, edge_um + 1.0e-9])
    for values in _coeffs(lam):
        assert float(values[0]) == pytest.approx(float(values[2]), abs=1.0e-6)


@pytest.mark.level0
def test_the_new_regions_keep_a_strip_of_exactly_calibrated_coefficients() -> None:
    """Interior wavelengths reach the table values bit-identically.

    The 0.50 µm core keeps 0.46 µm of un-blended interior and the
    0.10 µm tail keeps 0.06 µm — the property that makes the fitted
    coefficients meaningful rather than decorative.
    """
    for lo_um, hi_um in (WINDOW, CORE, TAIL):
        region = _region(lo_um, hi_um)
        interior = np.array([lo_um + HW + 1.0e-6, 0.5 * (lo_um + hi_um), hi_um - HW - 1.0e-6])
        floor, k, b = _coeffs(interior)
        assert np.all(floor == region.floor_od)
        assert np.all(k == region.k_h2o)
        assert np.all(b == region.b_h2o)


@pytest.mark.level0
def test_transmittance_is_lower_inside_the_band_than_either_side() -> None:
    """The whole point, read on τ rather than on the coefficients.

    A vertical full column at the shipped default humidity (us_standard,
    PWV 1.4 cm, ground → 100 km, nadir).  Measured on the pre-CU-330
    table the three wavelengths agreed to six figures — τ = 0.656360
    at 8.70 µm and 0.656361 at 9.60 µm — because they shared one flat
    region.  They now read 0.7336 / 0.3784 / 0.6740: the band is a
    factor 1.94 below the window and 1.78 below the far side.
    """
    lam = np.array([8.70, 9.60, 10.30])
    atm = SimpleAtmosphere(precipitable_water_cm=1.4)
    geometry = AtmosphericGeometry(
        sensor_altitude_m=1.0e5, target_altitude_m=0.0, path_zenith_rad=0.0
    )
    tau = np.asarray(atm.build_state(lam, geometry).transmittance.values)
    assert tau[0] / tau[1] > 1.9
    assert tau[2] / tau[1] > 1.7
