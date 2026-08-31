"""Level-0 anchors for the 9.6 µm ozone emission placement (CU-324 item 2).

The construction under test has three claims, and each gets a test that fails
if it stops holding:

1. the ozone **share** of the well-mixed-gas floor is arithmetic on the two
   committed table rows, not a coefficient anybody chose;
2. the placement is **continuous in λ** — it rides the same CU-267 smoothstep
   the floor it apportions rides, because it is computed from that floor;
3. it is a **placement**: τ is bit-identical everywhere, and the only thing
   that moves is the altitude the 9.6 µm emission comes from.

Hand truths only (Rule 18): the share is recomputed here from the table's own
``floor_od`` fields, and the smoothstep is written out longhand.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere import simple as simple_mod
from radiant.atmosphere.ozone_placement import (
    OZONE_BAND_UM,
    OZONE_LAYER_CENTRE_M,
    OZONE_LAYER_WIDTH_M,
    ozone_continuum_regions,
    ozone_share_of_gas_floor,
)
from radiant.atmosphere.segment_simple import column_segment_optical_depth
from radiant.atmosphere.segments import ColumnSegmentSpec
from radiant.atmosphere.simple import (
    _CALIBRATED_GAS_REGIONS,
    GAS_REGION_BLEND_HALF_WIDTH_UM,
    PROFILE_PWV_CM,
    SimpleAtmosphere,
    _o3_continuum_regions,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError


def _atm(profile: str = "midlat_summer") -> SimpleAtmosphere:
    return SimpleAtmosphere(
        standard_atmosphere=profile,
        precipitable_water_cm=PROFILE_PWV_CM[profile],
        visibility_km=23.0,
        aerosol_type="rural",
    )


def _shipped_share(lam: np.ndarray) -> np.ndarray:
    """The share exactly as ``_segment_emission_temperature_K`` computes it.

    Reads the table through the module (``simple_mod._CALIBRATED_GAS_REGIONS``)
    rather than through this file's import, so that a monkeypatched table
    reaches both floors — the library's own call-time semantics.
    """
    live = simple_mod._CALIBRATED_GAS_REGIONS
    floor, _k, _b = SimpleAtmosphere._region_params(lam, live)
    continuum, _ck, _cb = SimpleAtmosphere._region_params(lam, _o3_continuum_regions(live))
    return ozone_share_of_gas_floor(floor, continuum)


def _band_rows() -> tuple[float, float]:
    """``(band floor_od, clean-window floor_od)`` read off the shipped table."""
    lo_um, hi_um = OZONE_BAND_UM
    index = next(
        i for i, r in enumerate(_CALIBRATED_GAS_REGIONS) if r.lo_um == lo_um and r.hi_um == hi_um
    )
    return _CALIBRATED_GAS_REGIONS[index].floor_od, _CALIBRATED_GAS_REGIONS[index - 1].floor_od


# ---------------------------------------------------------------------------
# 1. The share is arithmetic on the table
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_the_share_is_the_bands_excess_over_its_clean_window() -> None:
    """``(floor_band − floor_window) / floor_band``, computed from the rows.

    Not a decimal: the expectation is rebuilt here from the same two committed
    ``floor_od`` fields, so a re-fit of either row moves both sides together
    and this test keeps meaning what it says.  With the CU-330 calibration it
    evaluates to 0.8317; the assertion is the *formula*, and the value below
    is only a guard that the two rows still resolve an ozone band at all.
    """
    band_floor, window_floor = _band_rows()
    expected = (band_floor - window_floor) / band_floor

    lam = np.linspace(*OZONE_BAND_UM, 41)
    interior = lam[
        (lam > OZONE_BAND_UM[0] + GAS_REGION_BLEND_HALF_WIDTH_UM)
        & (lam < OZONE_BAND_UM[1] - GAS_REGION_BLEND_HALF_WIDTH_UM)
    ]
    share = _shipped_share(interior)

    np.testing.assert_allclose(share, expected, rtol=1e-14, atol=0.0)
    assert expected == pytest.approx(0.8317, abs=5e-4), (
        "the calibrated rows no longer give the CU-330 share — re-audit CU-324 item 2"
    )


@pytest.mark.level0
def test_the_share_is_exactly_zero_outside_the_ozone_band() -> None:
    """Outside the band the two tables are the same table, bit for bit.

    This is what bounds the change's blast radius: a wavelength grid that
    never reaches 9.6 µm gets a share array of exact zeros, so no layer
    species is constructed and the emission temperature is bit-identical to
    the pre-CU-324 four-species form.
    """
    hw = GAS_REGION_BLEND_HALF_WIDTH_UM
    lam = np.concatenate(
        [
            np.linspace(0.4, OZONE_BAND_UM[0] - hw, 200),
            np.linspace(OZONE_BAND_UM[1] + hw, 14.0, 200),
        ]
    )
    share = _shipped_share(lam)
    assert np.all(share == 0.0)


@pytest.mark.level0
def test_the_continuum_table_differs_from_the_shipped_one_in_exactly_one_row() -> None:
    """Only the band's ``floor_od`` is substituted — water coefficients stay."""
    continuum_regions = _o3_continuum_regions(_CALIBRATED_GAS_REGIONS)
    assert len(continuum_regions) == len(_CALIBRATED_GAS_REGIONS)
    differing = [
        (shipped, continuum)
        for shipped, continuum in zip(_CALIBRATED_GAS_REGIONS, continuum_regions, strict=True)
        if shipped != continuum
    ]
    assert len(differing) == 1
    shipped, continuum = differing[0]
    assert (shipped.lo_um, shipped.hi_um) == OZONE_BAND_UM
    assert (continuum.k_h2o, continuum.b_h2o) == (shipped.k_h2o, shipped.b_h2o)
    assert continuum.floor_od == _band_rows()[1]


# ---------------------------------------------------------------------------
# 2. Continuity across the CU-267 blend ramps
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("edge_um", list(OZONE_BAND_UM))
def test_the_share_rides_the_same_smoothstep_the_floor_does(edge_um: float) -> None:
    """The share's ramp is the floors' ramp, longhand.

    Both floors pass through ``S(u) = u²(3 − 2u)``, so the share inside a ramp
    is a ratio of two smoothsteps — written out here from the table rows
    rather than taken from the implementation.  A second, parallel ramp
    implementation for the share would drift from the floor's and fail here.
    """
    hw = GAS_REGION_BLEND_HALF_WIDTH_UM
    lam = np.linspace(edge_um - 0.999 * hw, edge_um + 0.999 * hw, 41)

    lo_region, hi_region = next(
        (a, b)
        for a, b in zip(_CALIBRATED_GAS_REGIONS[:-1], _CALIBRATED_GAS_REGIONS[1:], strict=True)
        if b.lo_um == edge_um
    )
    _o3c = _o3_continuum_regions(_CALIBRATED_GAS_REGIONS)
    lo_cont, hi_cont = next(
        (a, b) for a, b in zip(_o3c[:-1], _o3c[1:], strict=True) if b.lo_um == edge_um
    )

    u = 0.5 + (lam - edge_um) / (2.0 * hw)
    s = u * u * (3.0 - 2.0 * u)
    floor = lo_region.floor_od + (hi_region.floor_od - lo_region.floor_od) * s
    continuum = lo_cont.floor_od + (hi_cont.floor_od - lo_cont.floor_od) * s
    expected = 1.0 - continuum / floor

    # 1e-9 absorbs the ``1 − continuum/floor`` cancellation at the ramp foot
    # (the share is 4e-6 there); a parallel ramp implementation would drift by
    # order 0.1, seven decades above this.
    np.testing.assert_allclose(_shipped_share(lam), expected, rtol=1e-9, atol=1e-15)


@pytest.mark.level0
def test_the_share_is_continuous_and_bounded_across_the_whole_band() -> None:
    """No step anywhere: max jump between adjacent samples is ramp-sized.

    Sampled at 0.1 nm across both edges, a discontinuous placement would show
    a jump of the full 0.8317; the smoothstep's own slope over one sample is
    three orders below that.
    """
    lam = np.arange(9.30, 10.00, 1.0e-4)
    share = _shipped_share(lam)
    assert float(share.min()) >= 0.0
    assert float(share.max()) <= 1.0
    assert float(np.max(np.abs(np.diff(share)))) < 0.01


# ---------------------------------------------------------------------------
# 3. It is a placement: τ untouched, emission altitude raised
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("zeta_deg", [0.0, 48.2])
def test_the_split_partitions_the_gas_floor_without_changing_it(zeta_deg: float) -> None:
    """The split is exhaustive, non-negative, and sums back to the floor.

    The two parts are what the emission model places at two altitudes; their
    sum is the optical depth the chain already had.
    """
    lam = np.linspace(8.0, 12.0, 501)
    atm = _atm()
    spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e5, zeta_low_rad=math.radians(zeta_deg))
    _od, _air_mass, _lengths, species_od = column_segment_optical_depth(atm, lam, spec)

    share = _shipped_share(lam)
    od_ozone = share * species_od["gas"]
    od_wellmixed = species_od["gas"] - od_ozone

    assert np.all(od_ozone >= 0.0)
    assert np.all(od_wellmixed >= 0.0)
    assert float(od_ozone.max()) > 0.0, (
        "the grid must reach the ozone band for this to mean anything"
    )
    np.testing.assert_allclose(od_ozone + od_wellmixed, species_od["gas"], rtol=1e-15, atol=0.0)


@pytest.mark.level0
def test_moving_the_ozone_layer_moves_the_thermal_radiance_but_not_tau(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """τ is bit-identical under a placement change; the emission is not.

    The standing invariant of the whole CU-321/CU-324 construction, tested the
    only way that can actually fail: move the placement (the layer from 25 km
    to 5 km) and read both products off the shipped ``evaluate``.  ``τ`` — up,
    down, sun leg and full path — must come back bit-for-bit identical while
    the path thermal radiance moves, which is exactly what "this redistributes
    opacity in altitude and never changes the total" means.
    """
    lam = np.linspace(8.0, 12.0, 401)
    los = LineOfSightGeometry(
        h_tgt=0.0,
        h_sensor=1.0e5,
        theta_o=math.radians(30.0),
        theta_s=math.radians(40.0),
        delta_phi=0.0,
    )

    high = _atm().evaluate(lam, los, params=None)  # type: ignore[arg-type]
    monkeypatch.setattr("radiant.atmosphere.simple.OZONE_LAYER_CENTRE_M", 5_000.0)
    low = _atm().evaluate(lam, los, params=None)  # type: ignore[arg-type]

    for field in ("tau_up", "tau_sun", "tau_full_up"):
        np.testing.assert_array_equal(
            getattr(high, field),
            getattr(low, field),
            err_msg=f"{field} moved under a pure placement change",
        )
    in_band = (lam >= 9.42) & (lam <= 9.88)
    assert not np.array_equal(high.L_path_up[in_band], low.L_path_up[in_band]), (
        "moving the ozone layer 20 km changed nothing — the placement is not wired in"
    )
    # …and it moves it the right way: a 5 km layer sits in warm troposphere.
    assert np.all(low.L_path_up[in_band] > high.L_path_up[in_band])


@pytest.mark.level0
@pytest.mark.parametrize("escape", ["upper", "lower"])
def test_the_ozone_band_now_emits_from_colder_air_than_its_window(escape: str) -> None:
    """The sign of the whole item, on a tall column, in both directions.

    9.6 µm emission belongs at the ozone layer, ~25 km up; 9.0 µm emission
    belongs to the well-mixed floor a few kilometres up.  On a ground-to-space
    column the ICAO profile is 288 K at the bottom and 216.65 K above the
    tropopause, so placing the band's opacity high must make its ``T_eff``
    fall **below** the neighbouring window's.  Before the split the two were
    within a few tenths of a kelvin of each other — the defect this closes.

    Rule 27: one escape geometry serves both directions, so the assertion is
    parameterised rather than duplicated.
    """
    lam = np.array([9.00, 9.60])
    atm = _atm()
    spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e5, zeta_low_rad=0.0)
    _od, _air_mass, _lengths, species_od = column_segment_optical_depth(atm, lam, spec)

    t_eff = atm._segment_emission_temperature_K(
        lam,
        h_low_m=0.0,
        h_high_m=1.0e5,
        od_slant_mol=species_od["mol"],
        od_slant_aer=species_od["aer"],
        od_slant_h2o=species_od["h2o"],
        od_slant_gas=species_od["gas"],
        escape=escape,
    )
    assert float(t_eff[1]) < float(t_eff[0]) - 1.0, (
        f"9.6 µm ({t_eff[1]:.2f} K) must emit colder than 9.0 µm ({t_eff[0]:.2f} K)"
    )
    assert float(t_eff.min()) >= 216.65 - 1e-9


@pytest.mark.level0
def test_the_layer_geometry_is_the_documented_stratospheric_profile() -> None:
    """The two placement constants are the published profile, not a fit.

    A guard, not a derivation: if a future edit tunes these against the
    parity, the zero-fit construction CU-321 and CU-324 both rest on has been
    abandoned and that has to be a deliberate, visible act.
    """
    assert OZONE_LAYER_CENTRE_M == 25_000.0
    assert OZONE_LAYER_WIDTH_M == 5_000.0
    assert OZONE_BAND_UM == (9.40, 9.90)


# ---------------------------------------------------------------------------
# 4. Failure modes
# ---------------------------------------------------------------------------


def _band_index() -> int:
    return next(
        i for i, r in enumerate(_CALIBRATED_GAS_REGIONS) if (r.lo_um, r.hi_um) == OZONE_BAND_UM
    )


@pytest.mark.level0
def test_a_table_with_no_ozone_band_row_is_refused() -> None:
    """A re-partition that removes the band must raise, not point at nothing.

    This is the case where the share would be *meaningless*: the module is
    configured for a region the table no longer has.  Same for a band with no
    clean window below it to read the continuum from.
    """
    flat = tuple(r for r in _CALIBRATED_GAS_REGIONS if (r.lo_um, r.hi_um) != OZONE_BAND_UM)
    with pytest.raises(ParameterBoundsError, match="no calibrated gas region spans"):
        ozone_continuum_regions(flat)

    with pytest.raises(ParameterBoundsError, match="first region"):
        ozone_continuum_regions(_CALIBRATED_GAS_REGIONS[_band_index() :])


@pytest.mark.level0
def test_a_band_below_its_own_continuum_is_refused() -> None:
    """A negative excess is not a band — the one arithmetic case that must raise."""
    import dataclasses

    index = _band_index()
    inverted = list(_CALIBRATED_GAS_REGIONS)
    inverted[index] = dataclasses.replace(
        inverted[index], floor_od=inverted[index - 1].floor_od - 0.01
    )
    with pytest.raises(ParameterBoundsError, match="sits below the window floor"):
        ozone_continuum_regions(tuple(inverted))


@pytest.mark.level0
def test_a_band_flat_against_its_window_gives_a_zero_share_not_an_error() -> None:
    """No excess ⇒ no ozone to place ⇒ share 0.  This is correct, not degraded.

    It is also load-bearing: ``fit_simple_atmosphere_gas_bands.py`` zeroes
    **every** floor for its non-water reference evaluation, which flattens the
    band against its window by construction.  Raising there would abort the
    generator; returning 0 is the physically right answer, because a table
    with no calibrated gas floor has no ozone opacity to apportion.
    """
    import dataclasses

    index = _band_index()
    flattened = list(_CALIBRATED_GAS_REGIONS)
    flattened[index] = dataclasses.replace(flattened[index], floor_od=flattened[index - 1].floor_od)
    continuum = ozone_continuum_regions(tuple(flattened))
    lam = np.linspace(9.3, 10.0, 71)
    floor, _k, _b = SimpleAtmosphere._region_params(lam, tuple(flattened))
    cont_floor, _ck, _cb = SimpleAtmosphere._region_params(lam, continuum)
    assert np.all(ozone_share_of_gas_floor(floor, cont_floor) == 0.0)


# ---------------------------------------------------------------------------
# 5. Generator idempotency — the live table, read at call time
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_the_gas_floor_evaluation_reads_the_live_table_not_an_import_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rebinding ``_CALIBRATED_GAS_REGIONS`` must reach every evaluation path.

    ``scripts/fit_simple_atmosphere_gas_bands.py`` derives each region's
    ``floor_od`` as the measured OD in excess of what Rayleigh + aerosol
    already supply, and it isolates that "pre-existing" term by rebinding this
    module's table to zeroed floors for the duration of one ``evaluate`` call.
    Any evaluation path that captured the table at **import** — a default
    argument, a module-level derived constant — silently ignores the
    rebinding, re-includes the shipped floors in the reference, and refits
    every floor to ~0: the generator zeroes its own table on a re-run.

    CU-330 repaired exactly that non-idempotency; CU-324 item 2 reintroduced
    it through the ``regions`` parameter's default argument (Python binds
    defaults once, at class-body evaluation) and through a module-level ozone
    continuum table. This test is the spec for both seams, held at the unit
    level so it fails in a second rather than through a 25-anchor fit.
    """
    import dataclasses

    lam = np.linspace(0.45, 12.0, 200)
    zeroed = tuple(dataclasses.replace(r, floor_od=0.0) for r in _CALIBRATED_GAS_REGIONS)
    monkeypatch.setattr("radiant.atmosphere.simple._CALIBRATED_GAS_REGIONS", zeroed)

    # 1. The blended floor — the τ path the generator's reference runs through.
    floor, _k, _b = SimpleAtmosphere._region_params(lam)
    assert np.all(floor == 0.0), "the region table's floor survived the rebinding"

    # 2. The partial-column gas OD built on it.
    assert np.all(SimpleAtmosphere._gas_floor_vertical_od(lam, 8.0) == 0.0)

    # 3. The ozone continuum table, derived from the live table rather than
    #    snapshotted — with no floor anywhere there is no ozone to place.
    continuum = _o3_continuum_regions(zeroed)
    cont_floor, _ck, _cb = SimpleAtmosphere._region_params(lam, continuum)
    assert np.all(ozone_share_of_gas_floor(floor, cont_floor) == 0.0)

    # 4. And the whole thing evaluates rather than raising, which is what the
    #    generator actually needs from it.
    t_eff = _atm()._segment_emission_temperature_K(
        lam,
        h_low_m=0.0,
        h_high_m=1.0e5,
        od_slant_mol=np.full_like(lam, 0.1),
        od_slant_aer=np.full_like(lam, 0.05),
        od_slant_h2o=np.full_like(lam, 0.2),
        od_slant_gas=np.zeros_like(lam),
        escape="upper",
    )
    assert np.all(np.isfinite(t_eff))


@pytest.mark.level0
def test_restoring_the_table_restores_the_shipped_share(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The call-time derivation is memoised on the table's VALUE, not cached once.

    A cache keyed on anything but the table's own value would hand the
    restored table the zeroed table's continuum (or vice versa), which is the
    same import-snapshot defect wearing a cache. Rebinding twice and reading
    the share both times is what proves it.
    """
    import dataclasses

    lam = np.linspace(9.3, 10.0, 71)
    shipped_share = _shipped_share(lam)
    assert float(shipped_share.max()) > 0.5

    zeroed = tuple(dataclasses.replace(r, floor_od=0.0) for r in _CALIBRATED_GAS_REGIONS)
    monkeypatch.setattr("radiant.atmosphere.simple._CALIBRATED_GAS_REGIONS", zeroed)
    assert np.all(_shipped_share(lam) == 0.0)

    monkeypatch.undo()
    np.testing.assert_array_equal(_shipped_share(lam), shipped_share)


@pytest.mark.level0
def test_a_bad_floor_pair_is_refused() -> None:
    good = np.array([0.5, 0.9, 0.2])
    with pytest.raises(ParameterBoundsError, match="shape"):
        ozone_share_of_gas_floor(good, np.array([0.1, 0.2]))
    with pytest.raises(ParameterBoundsError, match="not finite"):
        ozone_share_of_gas_floor(good, np.array([0.1, float("nan"), 0.2]))
    with pytest.raises(ParameterBoundsError, match="negative"):
        ozone_share_of_gas_floor(good, np.array([0.1, -0.2, 0.1]))
    with pytest.raises(ParameterBoundsError, match="continuum floor exceeds"):
        ozone_share_of_gas_floor(good, np.array([0.1, 0.95, 0.1]))


@pytest.mark.level0
def test_a_zero_floor_carries_no_ozone_rather_than_dividing_by_zero() -> None:
    """The VIS/UV rows calibrate ``floor_od = 0``; the share there is 0, not NaN."""
    zeros = np.zeros(4)
    share = ozone_share_of_gas_floor(zeros, zeros)
    assert np.all(share == 0.0)
    assert np.all(np.isfinite(share))
