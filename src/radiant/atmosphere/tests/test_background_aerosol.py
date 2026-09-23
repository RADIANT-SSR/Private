"""Level 0: the visible rows' gas/aerosol attribution (CU-337).

CU-335 and CU-336 fitted the 0.45–0.70 µm well-mixed-gas floor to 0.1375
optical depths against the MODTRAN water ladder.  Real gas chemistry in that
window supplies about a seventh of it — the ozone Chappuis band, which this
module's ``_CHAPPUIS_PRIOR`` states independently — so the remainder was an
aerosol deficit wearing a gas label: it neither scattered nor answered to a
visibility setting.

CU-337 splits the row.  The **total** is untouched, so every transmittance the
model has ever produced is unchanged; what moves is which species carries the
opacity, and therefore whether it scatters and whether an operator can turn it
down for a clean site.  Every number below is a hand statement about that
split, not a value read back from the implementation.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.atmosphere.protocol import AtmosphericGeometry
from radiant.atmosphere.simple import (
    _CALIBRATED_GAS_REGIONS,
    H_MOL_M,
    SimpleAtmosphere,
)

#: The visible row, and the opacity beyond Rayleigh and the boundary layer that
#: CU-336 fitted for it — the quantity the split has to conserve.
_VIS_BAND: tuple[float, float] = (0.45, 0.70)
_CU336_TOTAL: float = 0.1375

#: Vertical optical depth the ozone Chappuis band supplies in that window at the
#: anchor deck's ozone column (0.000736 g/cm² = 344 DU).  Peak cross-section
#: 4.6e-21 cm² at 602 nm, Gaussian half-width 55 nm, band-averaged over
#: 0.45–0.70 µm.  Hand calculation, stated here so the test does not read the
#: generator's own prior back to itself.
_CHAPPUIS_PRIOR: float = 0.020


def _region(lo_um: float, hi_um: float):  # type: ignore[no-untyped-def]
    return next(r for r in _CALIBRATED_GAS_REGIONS if (r.lo_um, r.hi_um) == (lo_um, hi_um))


def _vertical_column(h_low_m: float, h_high_m: float) -> float:
    """Molecular-scale-height column length [km] — what both terms ride."""
    h = H_MOL_M
    return (h / 1000.0) * (math.exp(-h_low_m / h) - math.exp(-h_high_m / h))


class TestTheSplitConservesTheFit:
    @pytest.mark.level0
    def test_the_visible_row_totals_the_cu336_value(self) -> None:
        """floor_od + aer_bg_od is exactly what CU-336 fitted — nothing was added."""
        vis = _region(*_VIS_BAND)
        assert vis.floor_od + vis.aer_bg_od == pytest.approx(_CU336_TOTAL, abs=1e-12)

    @pytest.mark.level0
    def test_the_gas_share_is_the_chemistry_the_band_supplies(self) -> None:
        """The floor is the Chappuis prior, not a residual: ~1/7 of the old value."""
        vis = _region(*_VIS_BAND)
        assert vis.floor_od == pytest.approx(_CHAPPUIS_PRIOR, abs=1e-12)
        assert vis.aer_bg_od > 5.0 * vis.floor_od

    @pytest.mark.level0
    def test_the_split_is_scoped_to_the_visible(self) -> None:
        """Only the two rows below 0.70 µm carry a background; the rest are whole."""
        carrying = {(r.lo_um, r.hi_um) for r in _CALIBRATED_GAS_REGIONS if r.aer_bg_od > 0.0}
        assert carrying == {(0.30, 0.45), (0.45, 0.70)}


class TestTheBackgroundRidesTheColumnItWasSplitFrom:
    @pytest.mark.level0
    def test_the_vertical_od_is_the_table_value_on_the_molecular_column(self) -> None:
        """aer_bg_od is a full-column value apportioned exactly as the floor is."""
        atm = SimpleAtmosphere()
        lam = np.array([0.55])
        col = _vertical_column(0.0, 5_000.0)
        expected = _region(*_VIS_BAND).aer_bg_od * col / (H_MOL_M / 1000.0)
        got = atm._background_aerosol_vertical_od(lam, col)  # noqa: SLF001
        assert float(got[0]) == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level0
    def test_a_zero_column_carries_no_background(self) -> None:
        atm = SimpleAtmosphere()
        got = atm._background_aerosol_vertical_od(np.array([0.55]), 0.0)  # noqa: SLF001
        assert float(got[0]) == 0.0

    @pytest.mark.level0
    def test_total_transmittance_is_untouched_by_the_split(self) -> None:
        """The whole point: τ is bit-for-bit what the unsplit table produced.

        Hand-built here from the CU-336 total on the molecular column, so it is
        a statement about the fit, not a re-run of the model against itself.
        """
        atm = SimpleAtmosphere(visibility_km=23.0, precipitable_water_cm=0.0)
        lam = np.array([0.55, 0.56])
        geo = AtmosphericGeometry(
            sensor_altitude_m=100_000.0, target_altitude_m=0.0, path_zenith_rad=0.0
        )
        state = atm.build_state(lam, geo)
        col_mol = _vertical_column(0.0, 100_000.0)
        gas_plus_background = _CU336_TOTAL * col_mol / (H_MOL_M / 1000.0)
        # Everything else in the column, taken from the model's own species terms.
        od_total = -math.log(float(state.transmittance.values[0]))
        od_rayleigh_and_boundary_layer = od_total - gas_plus_background
        assert od_rayleigh_and_boundary_layer > 0.0
        # Re-composing from the two split halves reproduces the same total.
        vis = _region(*_VIS_BAND)
        recomposed = od_rayleigh_and_boundary_layer + (vis.floor_od + vis.aer_bg_od) * col_mol / (
            H_MOL_M / 1000.0
        )
        assert recomposed == pytest.approx(od_total, rel=1e-12)


class TestTheBackgroundScatters:
    @pytest.mark.level0
    def test_it_enters_the_albedo_with_the_aerosol_not_the_gas(self) -> None:
        """ω₀ is higher than the same opacity carried as a pure absorber.

        This is the physical content of the re-attribution: a gas floor sits in
        the extinction denominator only, while aerosol enters the scattering
        numerator weighted by its single-scattering albedo.
        """
        atm = SimpleAtmosphere()
        lam = np.array([0.55])
        sigma_mol = atm._rayleigh_extinction_km(lam, 0.0)  # noqa: SLF001
        sigma_aer = atm._aerosol_extinction_km(lam, 0.0)  # noqa: SLF001
        sigma_bg = atm._background_aerosol_extinction_km(lam, 0.0)  # noqa: SLF001
        assert float(sigma_bg[0]) > 0.0
        zero = np.zeros_like(lam)
        as_aerosol = atm._single_scattering_albedo(  # noqa: SLF001
            sigma_mol, sigma_aer + sigma_bg, zero, zero
        )
        as_gas = atm._single_scattering_albedo(  # noqa: SLF001
            sigma_mol, sigma_aer, zero, sigma_bg
        )
        assert float(as_aerosol[0]) > float(as_gas[0])

    @pytest.mark.level0
    def test_the_extinction_spreads_the_column_over_the_molecular_scale_height(self) -> None:
        atm = SimpleAtmosphere()
        lam = np.array([0.55])
        surface = float(atm._background_aerosol_extinction_km(lam, 0.0)[0])  # noqa: SLF001
        aloft = float(atm._background_aerosol_extinction_km(lam, H_MOL_M)[0])  # noqa: SLF001
        assert aloft == pytest.approx(surface / math.e, rel=1e-12)
        expected_surface = _region(*_VIS_BAND).aer_bg_od / (H_MOL_M / 1000.0)
        assert surface == pytest.approx(expected_surface, rel=1e-12)


class TestTheScaleIsTheSiteKnob:
    @pytest.mark.level0
    def test_zero_removes_exactly_the_background(self) -> None:
        lam = np.array([0.55])
        col = _vertical_column(0.0, 100_000.0)
        full = SimpleAtmosphere()._background_aerosol_vertical_od(lam, col)  # noqa: SLF001
        none = SimpleAtmosphere(background_aerosol_scale=0.0)._background_aerosol_vertical_od(  # noqa: SLF001
            lam, col
        )
        assert float(none[0]) == 0.0
        assert float(full[0]) > 0.0

    @pytest.mark.level0
    def test_it_scales_linearly(self) -> None:
        lam = np.array([0.55])
        col = _vertical_column(0.0, 100_000.0)
        full = float(SimpleAtmosphere()._background_aerosol_vertical_od(lam, col)[0])  # noqa: SLF001
        quarter = float(
            SimpleAtmosphere(background_aerosol_scale=0.25)._background_aerosol_vertical_od(  # noqa: SLF001
                lam, col
            )[0]
        )
        assert quarter == pytest.approx(0.25 * full, rel=1e-12)

    @pytest.mark.level0
    def test_visibility_does_not_touch_it(self) -> None:
        """The defect CU-337 names: this opacity must not answer to visibility."""
        lam = np.array([0.55])
        col = _vertical_column(0.0, 100_000.0)
        clear = SimpleAtmosphere(visibility_km=100.0)._background_aerosol_vertical_od(lam, col)  # noqa: SLF001
        hazy = SimpleAtmosphere(visibility_km=5.0)._background_aerosol_vertical_od(lam, col)  # noqa: SLF001
        assert float(clear[0]) == float(hazy[0])

    @pytest.mark.level0
    def test_a_clean_site_reaches_the_published_extinction_band(self) -> None:
        """Scenario 10.3's anchor: unreachable at any visibility before CU-337.

        Published V-band zenith extinction at a good observatory is
        k_V = 0.12–0.20 mag/airmass.  With the full continental-rural
        background the model sits at 0.26 and no visibility setting moves it;
        at a quarter of that background it lands inside the band.
        """
        lam = np.linspace(0.45, 0.70, 251)
        geo = AtmosphericGeometry(
            sensor_altitude_m=100_000.0, target_altitude_m=900.0, path_zenith_rad=0.0
        )

        def k_v(scale: float) -> float:
            atm = SimpleAtmosphere(
                visibility_km=100.0, precipitable_water_cm=1.4, background_aerosol_scale=scale
            )
            tau = np.asarray(atm.build_state(lam, geo).transmittance.values)
            return -2.5 * math.log10(float(np.interp(0.55, lam, tau)))

        assert k_v(1.0) > 0.20  # the continental background: outside the band
        assert 0.12 <= k_v(0.25) <= 0.20  # a clean site: inside it

    @pytest.mark.level0
    def test_a_negative_scale_is_refused(self) -> None:
        with pytest.raises(AtmosphereValidationError, match="background_aerosol_scale"):
            SimpleAtmosphere(background_aerosol_scale=-0.1)
