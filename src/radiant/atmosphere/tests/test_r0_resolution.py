"""Level-0 tests for Fried-parameter resolution (Gap 110).

Covers the four resolution rules (direct wins / profile when alone /
CU-093 agreement raise / explicit-zero contradiction), the reference-wavelength
convention, and the zero-drift guarantee for the pre-Gap-110 path.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.atmosphere.cn2_hufnagel_valley import HufnagelValleyCn2
from radiant.atmosphere.cn2_profiles import warn_if_site_elevation_inert
from radiant.atmosphere.cn2_tabulated import TabulatedCn2Profile
from radiant.atmosphere.errors import TurbulenceSpecificationError
from radiant.atmosphere.r0_resolution import resolve_fried_parameter
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet

GRID = np.linspace(0.45, 0.55, 11)  # band centre = 0.50 µm exactly
GROUND_TO_SPACE = LineOfSightGeometry(h_tgt=800.0e3, h_sensor=0.0, theta_o=math.pi)


def _params(**overrides: object) -> ParameterSet:
    from radiant.atmosphere._schema import ALL_PARAMETERS as ATM_PARAMS

    ps = ParameterSet(list(ATM_PARAMS), [])
    for dotpath, value in overrides.items():
        ps.set(dotpath.replace("__", "."), value)
    ps.resolve()
    return ps


class TestDirectPath:
    @pytest.mark.level0
    def test_default_is_turbulence_off(self) -> None:
        res = resolve_fried_parameter(_params(), GROUND_TO_SPACE, GRID)
        assert res.r0_m == 0.0
        assert res.mode == "off"
        assert res.path is None

    @pytest.mark.level0
    def test_direct_r0_is_passed_through_bit_identically(self) -> None:
        res = resolve_fried_parameter(_params(atmosphere__r0_m=0.0731), GROUND_TO_SPACE, GRID)
        assert res.r0_m == 0.0731
        assert res.mode == "direct"
        assert res.path is None

    @pytest.mark.level0
    def test_direct_path_never_touches_the_geometry(self) -> None:
        """No LOS is needed when no profile is selected — the pre-Gap-110 path."""
        res = resolve_fried_parameter(_params(atmosphere__r0_m=0.1), None, GRID)
        assert res.r0_m == 0.1

    @pytest.mark.level0
    def test_unregistered_schema_is_turbulence_off(self) -> None:
        """A partial-chain fixture with no atmosphere schema behaves as before."""
        empty = ParameterSet([], [])
        empty.resolve()
        res = resolve_fried_parameter(empty, GROUND_TO_SPACE, GRID)
        assert res.r0_m == 0.0
        assert res.mode == "off"


class TestProfilePath:
    @pytest.mark.level0
    def test_hv_profile_gives_the_literature_value(self) -> None:
        res = resolve_fried_parameter(
            _params(atmosphere__cn2_profile="hufnagel_valley"), GROUND_TO_SPACE, GRID
        )
        assert res.mode == "profile"
        assert 0.048 <= res.r0_m <= 0.052
        assert res.reference_wavelength_um == pytest.approx(0.50, rel=1e-12)
        assert res.path is not None

    @pytest.mark.level0
    def test_reference_wavelength_is_the_band_centre(self) -> None:
        grid = np.linspace(3.0, 5.0, 101)  # centre 4.0 µm
        res = resolve_fried_parameter(
            _params(atmosphere__cn2_profile="hufnagel_valley"), GROUND_TO_SPACE, grid
        )
        assert res.reference_wavelength_um == pytest.approx(4.0, rel=1e-12)
        # r0 ∝ λ^(6/5): the MWIR value must exceed the visible one accordingly.
        vis = resolve_fried_parameter(
            _params(atmosphere__cn2_profile="hufnagel_valley"), GROUND_TO_SPACE, GRID
        )
        assert res.r0_m / vis.r0_m == pytest.approx((4.0 / 0.5) ** 1.2, rel=1e-9)

    @pytest.mark.level0
    def test_hv_parameters_are_honoured(self) -> None:
        weak = resolve_fried_parameter(
            _params(
                atmosphere__cn2_profile="hufnagel_valley",
                atmosphere__cn2_hv_ground_strength=1.7e-15,
            ),
            GROUND_TO_SPACE,
            GRID,
        )
        strong = resolve_fried_parameter(
            _params(atmosphere__cn2_profile="hufnagel_valley"), GROUND_TO_SPACE, GRID
        )
        assert weak.r0_m > strong.r0_m

    @pytest.mark.level0
    def test_wave_type_is_honoured(self) -> None:
        down = LineOfSightGeometry(h_tgt=0.0, h_sensor=500.0e3, theta_o=0.0)
        plane = resolve_fried_parameter(
            _params(atmosphere__cn2_profile="hufnagel_valley"), down, GRID
        )
        spherical = resolve_fried_parameter(
            _params(
                atmosphere__cn2_profile="hufnagel_valley",
                atmosphere__turbulence_wave_type="spherical",
            ),
            down,
            GRID,
        )
        assert spherical.r0_m > plane.r0_m

    @pytest.mark.level0
    def test_tabulated_profile_is_consumed_from_the_injection(self) -> None:
        h = np.linspace(0.0, 100_000.0, 401)
        table = TabulatedCn2Profile(altitude_m=h, cn2_m23=HufnagelValleyCn2().cn2(h), label="hv")
        res = resolve_fried_parameter(
            _params(atmosphere__cn2_profile="tabulated", atmosphere__cn2_tabulated_file="x.csv"),
            GROUND_TO_SPACE,
            GRID,
            tabulated_profile=table,
        )
        assert 0.048 <= res.r0_m <= 0.052

    @pytest.mark.level0
    def test_vacuum_path_turns_turbulence_off_rather_than_raising(self) -> None:
        """LEO → GEO: no atmosphere on the path (the retired ScopeError case)."""
        leo_geo = LineOfSightGeometry(h_tgt=35_786.0e3, h_sensor=500.0e3, theta_o=math.pi)
        res = resolve_fried_parameter(
            _params(atmosphere__cn2_profile="hufnagel_valley"), leo_geo, GRID
        )
        assert res.mode == "off"
        assert res.r0_m == 0.0
        assert res.path is not None and res.path.negligible is True


class TestAgreementRules:
    @pytest.mark.level0
    def test_agreeing_direct_value_wins_and_keeps_the_cross_check(self) -> None:
        hv = resolve_fried_parameter(
            _params(atmosphere__cn2_profile="hufnagel_valley"), GROUND_TO_SPACE, GRID
        ).r0_m
        res = resolve_fried_parameter(
            _params(atmosphere__cn2_profile="hufnagel_valley", atmosphere__r0_m=hv * 1.005),
            GROUND_TO_SPACE,
            GRID,
        )
        assert res.mode == "direct"
        assert res.r0_m == pytest.approx(hv * 1.005, rel=1e-15)
        assert res.path is not None

    @pytest.mark.level0
    def test_disagreement_beyond_one_percent_raises(self) -> None:
        with pytest.raises(TurbulenceSpecificationError, match="Over-specified turbulence"):
            resolve_fried_parameter(
                _params(atmosphere__cn2_profile="hufnagel_valley", atmosphere__r0_m=0.20),
                GROUND_TO_SPACE,
                GRID,
            )

    @pytest.mark.level0
    def test_disagreement_error_carries_both_values(self) -> None:
        with pytest.raises(TurbulenceSpecificationError) as excinfo:
            resolve_fried_parameter(
                _params(atmosphere__cn2_profile="hufnagel_valley", atmosphere__r0_m=0.20),
                GROUND_TO_SPACE,
                GRID,
            )
        ctx = excinfo.value.context
        assert ctx["r0_m_user"] == 0.20
        assert 0.048 <= ctx["r0_m_profile"] <= 0.052
        assert ctx["reference_wavelength_um"] == pytest.approx(0.50, rel=1e-12)

    @pytest.mark.level0
    def test_profile_with_explicit_zero_r0_is_a_contradiction(self) -> None:
        with pytest.raises(TurbulenceSpecificationError, match="turbulence off"):
            resolve_fried_parameter(
                _params(atmosphere__cn2_profile="hufnagel_valley", atmosphere__r0_m=0.0),
                GROUND_TO_SPACE,
                GRID,
            )

    @pytest.mark.level0
    def test_profile_without_a_los_is_actionable(self) -> None:
        with pytest.raises(TurbulenceSpecificationError, match="line of sight"):
            resolve_fried_parameter(_params(atmosphere__cn2_profile="hufnagel_valley"), None, GRID)

    @pytest.mark.level0
    def test_empty_wavelength_grid_is_actionable(self) -> None:
        with pytest.raises(TurbulenceSpecificationError, match="empty"):
            resolve_fried_parameter(
                _params(atmosphere__cn2_profile="hufnagel_valley"),
                GROUND_TO_SPACE,
                np.array([]),
            )


_MWIR_GRID = np.linspace(3.5, 5.0, 51)  # band centre = 4.25 µm


class TestR0ReferenceWavelength:
    """CU-228 — an r₀ quoted at one wavelength must not be applied at another.

    Kolmogorov gives r₀ ∝ λ^(6/5), so the astronomer's habitual 0.5 µm seeing
    value used verbatim in the MWIR makes the turbulence MTF about an order of
    magnitude too aggressive.
    """

    def test_unset_reference_is_bit_identical_to_the_old_behaviour(self) -> None:
        """The default must not move a single existing result."""
        res = resolve_fried_parameter(_params(**{"atmosphere.r0_m": 0.10}), None, _MWIR_GRID)
        assert res.r0_m == 0.10

    def test_declared_reference_rescales_by_the_six_fifths_power(self) -> None:
        """Hand value: 0.10 m at 0.5 µm → 0.10·(4.25/0.5)^1.2 = 1.304 m at 4.25 µm."""
        res = resolve_fried_parameter(
            _params(**{"atmosphere.r0_m": 0.10, "atmosphere.r0_reference_wavelength_um": 0.5}),
            None,
            _MWIR_GRID,
        )
        assert res.r0_m == pytest.approx(0.10 * (4.25 / 0.5) ** 1.2, rel=1e-12)
        assert res.r0_m == pytest.approx(1.304, abs=0.001)
        assert "rescaled" in res.detail  # provenance records both values

    def test_reference_equal_to_the_band_is_a_no_op(self) -> None:
        res = resolve_fried_parameter(
            _params(**{"atmosphere.r0_m": 0.08, "atmosphere.r0_reference_wavelength_um": 0.5}),
            None,
            GRID,  # band centre 0.50 µm
        )
        assert res.r0_m == pytest.approx(0.08, rel=1e-12)

    def test_unreferenced_r0_far_from_the_habitual_wavelength_warns(self) -> None:
        """The case that is almost certainly a mis-entered visible seeing value."""
        with pytest.warns(UserWarning, match="r0_reference_wavelength_um"):
            resolve_fried_parameter(_params(**{"atmosphere.r0_m": 0.10}), None, _MWIR_GRID)

    def test_unreferenced_r0_near_the_habitual_wavelength_is_quiet(self) -> None:
        """No false alarm for a scene genuinely working near 0.5 µm."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            resolve_fried_parameter(_params(**{"atmosphere.r0_m": 0.10}), None, GRID)

    def test_turbulence_off_is_quiet_and_unscaled(self) -> None:
        """r₀ = 0 means off; there is nothing to rescale and nothing to warn about."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            res = resolve_fried_parameter(
                _params(**{"atmosphere.r0_m": 0.0, "atmosphere.r0_reference_wavelength_um": 0.5}),
                None,
                _MWIR_GRID,
            )
        assert res.r0_m == 0.0
        assert res.mode == "off"


class TestSiteElevationWiring:
    """CU-262 — ``geometry.site_elevation_m`` reaches the HV surface term."""

    @staticmethod
    def _params_with_geometry(**overrides: object) -> ParameterSet:
        from radiant.atmosphere._schema import ALL_PARAMETERS as ATM_PARAMS
        from radiant.geometry._schema import ALL_PARAMETERS as GEO_PARAMS

        ps = ParameterSet([*ATM_PARAMS, *GEO_PARAMS], [])
        ps.set("geometry.sensor_altitude_m", 0.0)  # required; unused by the resolver
        for dotpath, value in overrides.items():
            ps.set(dotpath, value)
        ps.resolve()
        return ps

    @pytest.mark.level0
    def test_default_site_elevation_is_bit_identical(self) -> None:
        """Registering the geometry schema must not move the sea-level answer."""
        without = resolve_fried_parameter(
            _params(**{"atmosphere.cn2_profile": "hufnagel_valley"}), GROUND_TO_SPACE, GRID
        )
        with_geometry = resolve_fried_parameter(
            self._params_with_geometry(**{"atmosphere.cn2_profile": "hufnagel_valley"}),
            GROUND_TO_SPACE,
            GRID,
        )
        assert with_geometry.r0_m == without.r0_m
        assert with_geometry.detail == without.detail

    @pytest.mark.level0
    def test_elevated_site_recovers_the_hv_5_7_anchor(self) -> None:
        """A 900 m observatory looking up: without the site elevation the HV-5/7
        defining value (r₀ = 5 cm at 0.5 µm, vertical) is lost — the CU-262
        symptom was 15.0 cm.  With it declared, the anchor comes back to within
        the 5 % the free-atmosphere slab below the site genuinely buys.
        """
        los = LineOfSightGeometry(h_tgt=800.0e3, h_sensor=900.0, theta_o=math.pi)
        broken = resolve_fried_parameter(
            self._params_with_geometry(**{"atmosphere.cn2_profile": "hufnagel_valley"}), los, GRID
        )
        fixed = resolve_fried_parameter(
            self._params_with_geometry(
                **{"atmosphere.cn2_profile": "hufnagel_valley", "geometry.site_elevation_m": 900.0}
            ),
            los,
            GRID,
        )
        assert broken.r0_m == pytest.approx(0.150, abs=0.002)  # the defect
        assert fixed.r0_m == pytest.approx(0.052, abs=0.002)  # HV-5/7 restored
        assert fixed.path is not None
        assert "900 m MSL" in fixed.path.detail

    @pytest.mark.level0
    def test_site_above_the_path_lower_endpoint_raises(self) -> None:
        """Declaring a 900 m site while looking up from sea level describes two
        different scenes; RADIANT refuses rather than modelling a path that runs
        underground."""
        from radiant.core.parameters import ParameterBoundsError

        with pytest.raises(ParameterBoundsError, match="below the ground"):
            resolve_fried_parameter(
                self._params_with_geometry(
                    **{
                        "atmosphere.cn2_profile": "hufnagel_valley",
                        "geometry.site_elevation_m": 900.0,
                    }
                ),
                GROUND_TO_SPACE,  # h_sensor = 0 m MSL
                GRID,
            )

    @pytest.mark.level0
    def test_tabulated_profile_is_not_shifted_by_the_site(self) -> None:
        """A measured table already carries its own site; the parameter is
        HV-only by design — and CU-302 makes that inertness audible."""
        h = np.linspace(0.0, 30.0e3, 3001)
        table = TabulatedCn2Profile(altitude_m=h, cn2_m23=HufnagelValleyCn2().cn2(h), label="hv")
        plain = resolve_fried_parameter(
            self._params_with_geometry(**{"atmosphere.cn2_profile": "tabulated"}),
            GROUND_TO_SPACE,
            GRID,
            tabulated_profile=table,
        )
        with pytest.warns(UserWarning, match="has no effect on this run"):
            elevated = resolve_fried_parameter(
                self._params_with_geometry(
                    **{"atmosphere.cn2_profile": "tabulated", "geometry.site_elevation_m": 900.0}
                ),
                GROUND_TO_SPACE,
                GRID,
                tabulated_profile=table,
            )
        assert elevated.r0_m == plain.r0_m


class TestSiteElevationInertWarning:
    """CU-302 — a site elevation that cannot reach the selected profile warns."""

    @pytest.mark.level0
    def test_direct_profile_warns_and_names_the_reason(self) -> None:
        params = TestSiteElevationWiring._params_with_geometry(
            **{
                "atmosphere.cn2_profile": "direct",
                "atmosphere.r0_m": 0.10,  # m
                "geometry.site_elevation_m": 2635.0,  # m MSL
            }
        )
        with pytest.warns(UserWarning) as record:
            res = resolve_fried_parameter(params, GROUND_TO_SPACE, GRID)
        text = "\n".join(str(w.message) for w in record)
        assert "2635 m MSL has no effect" in text
        assert "no Cn² profile at all" in text
        assert "hufnagel_valley" in text
        assert res.r0_m == pytest.approx(0.10, abs=1e-12)  # m — unchanged

    @pytest.mark.level0
    def test_tabulated_profile_warns_about_the_table_carrying_its_own_site(self) -> None:
        h = np.linspace(0.0, 30.0e3, 3001)
        table = TabulatedCn2Profile(altitude_m=h, cn2_m23=HufnagelValleyCn2().cn2(h), label="hv")
        params = TestSiteElevationWiring._params_with_geometry(
            **{"atmosphere.cn2_profile": "tabulated", "geometry.site_elevation_m": 2635.0}
        )
        with pytest.warns(UserWarning) as record:
            resolve_fried_parameter(params, GROUND_TO_SPACE, GRID, tabulated_profile=table)
        text = "\n".join(str(w.message) for w in record)
        assert "2635 m MSL has no effect" in text
        assert "carries its own altitudes" in text

    @pytest.mark.level0
    def test_hufnagel_valley_does_not_warn(self) -> None:
        """The one consumer of the parameter must stay silent."""
        params = TestSiteElevationWiring._params_with_geometry(
            **{"atmosphere.cn2_profile": "hufnagel_valley", "geometry.site_elevation_m": 900.0}
        )
        los = LineOfSightGeometry(h_tgt=800.0e3, h_sensor=900.0, theta_o=math.pi)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            resolve_fried_parameter(params, los, GRID)
        assert [
            str(w.message) for w in caught if "has no effect on this run" in str(w.message)
        ] == []

    @pytest.mark.level0
    @pytest.mark.parametrize("profile", ["direct", "tabulated", "hufnagel_valley"])
    def test_sea_level_site_never_warns(self, profile: str) -> None:
        """The schema default (0 m MSL) is 'not declared', not 'declared and ignored'."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            warn_if_site_elevation_inert(profile, 0.0)
        assert caught == []
