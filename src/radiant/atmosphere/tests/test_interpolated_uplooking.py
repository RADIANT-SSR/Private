"""Up-looking family contract on ``InterpolatedAtmosphere`` (GF-10).

Level 0 — the interpolation identity and the refusals, on synthetic points
whose exact answers are known analytically.  The shipped K-block family's
physics goldens live in
``tests/integration/test_shipped_atmosphere_library.py``; this module is the
contract: which queries are legal, which are refused, and that the
interpolation convention is log-τ exactly as the down-looking families use.

Why the refusals are tested as hard as the numbers: an up-looking family and
a down-looking family carry *different physical products* (downwelling vs
upwelling path radiance) under superficially similar names.  Every path by
which one could be served through the other's entry point is a Rule-17
silent-wrong-answer, so each is pinned.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.atmosphere.interpolated import (
    FAMILY_DIRECTION_KEY,
    UPLOOKING_RADIANCE_KEY,
    GeometryPoint,
    InterpolatedAtmosphere,
    UplookingColumnProduct,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.spectral import SpectralData

_LIB = Path(__file__).resolve().parents[3] / "radiant" / "data" / "tables" / "atmospheres"
_UPLOOKING_DIR = _LIB / "midlat_summer_uplooking_ladder"

_WL = np.array([4.0, 6.0, 8.0, 10.0, 12.0], dtype=np.float64)


def _spectral(name: str, values: np.ndarray, unit: str) -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=_WL.copy(),
        values=np.asarray(values, dtype=np.float64),
        unit=unit,
        source="test fixture",
    )


def _point(target_m: float, tau: float, l_down: float) -> GeometryPoint:
    """One synthetic up-looking node: grey τ and grey downwelling radiance."""
    return GeometryPoint(
        coordinates={
            "sensor_altitude_m": 0.0,
            "target_altitude_m": target_m,
            "path_zenith_rad": 0.0,
            "solar_zenith_rad": 0.0,
            "solar_azimuth_rad": 0.0,
        },
        transmittance=_spectral("tau", np.full_like(_WL, tau), ""),
        path_radiance=_spectral("L_toward_lower", np.full_like(_WL, l_down), "W/m²/sr/µm"),
        atm_emission_down=_spectral("unused", np.zeros_like(_WL), "W/m²/sr/µm"),
    )


def _uplooking_family() -> InterpolatedAtmosphere:
    """Two-node synthetic family: τ = 1 at 0 m, τ = 0.25 at 10 km."""
    return InterpolatedAtmosphere(
        [_point(0.0, 1.0, 0.0), _point(10_000.0, 0.25, 4.0)],
        axes=["target_altitude_m"],
        family_direction="up",
    )


def _downlooking_family() -> InterpolatedAtmosphere:
    return InterpolatedAtmosphere(
        [_point(0.0, 1.0, 0.0), _point(10_000.0, 0.25, 4.0)],
        axes=["target_altitude_m"],
    )


def _up_los(h_tgt: float, h_sensor: float = 0.0, theta_o: float = math.pi) -> LineOfSightGeometry:
    return LineOfSightGeometry(theta_o=theta_o, h_tgt=h_tgt, h_sensor=h_sensor)


# ---------------------------------------------------------------------------
# Construction and defaults
# ---------------------------------------------------------------------------


class TestFamilyDirection:
    @pytest.mark.level0
    def test_default_direction_is_down(self) -> None:
        """Zero drift: every pre-GF-10 construction is a down-looking family."""
        assert _downlooking_family().family_direction == "down"

    @pytest.mark.level0
    def test_unknown_direction_refused(self) -> None:
        with pytest.raises(AtmosphereValidationError, match="family_direction"):
            InterpolatedAtmosphere(
                [_point(0.0, 1.0, 0.0), _point(10_000.0, 0.25, 4.0)],
                axes=["target_altitude_m"],
                family_direction="sideways",
            )

    @pytest.mark.level0
    def test_evaluate_refuses_an_uplooking_family(self) -> None:
        """The eight-field down-looking bundle is closed to up-looking data."""
        from radiant.core.parameters import ParameterSet

        family = _uplooking_family()
        with pytest.raises(AtmosphereValidationError, match="UPWELLING"):
            family.evaluate(_WL, _up_los(5_000.0), ParameterSet([], []))

    @pytest.mark.level0
    def test_uplooking_query_refuses_a_downlooking_family(self) -> None:
        family = _downlooking_family()
        with pytest.raises(AtmosphereValidationError, match="DOWNWELLING"):
            family.uplooking_column_product(_WL, _up_los(5_000.0))


# ---------------------------------------------------------------------------
# The interpolation identity
# ---------------------------------------------------------------------------


class TestUplookingInterpolation:
    @pytest.mark.level0
    def test_node_is_reproduced_exactly(self) -> None:
        """A query landing on a node returns that node, not an average."""
        product = _uplooking_family().uplooking_column_product(_WL, _up_los(10_000.0))
        assert isinstance(product, UplookingColumnProduct)
        np.testing.assert_allclose(product.tau, 0.25, rtol=1e-12)
        np.testing.assert_allclose(product.L_toward_lower, 4.0, rtol=1e-12)

    @pytest.mark.level0
    def test_tau_interpolates_in_log_space(self) -> None:
        """Truth anchor (analytic): log-τ linear in the altitude axis.

        Between τ = 1 (0 m) and τ = 0.25 (10 km), the 5 km midpoint of
        ``ln τ`` is ``exp((ln 1 + ln 0.25) / 2) = 0.5`` — the geometric
        mean, not the arithmetic mean 0.625.  This is the same convention
        the down-looking ladder families use.
        """
        product = _uplooking_family().uplooking_column_product(_WL, _up_los(5_000.0))
        np.testing.assert_allclose(product.tau, 0.5, rtol=1e-12)

    @pytest.mark.level0
    def test_radiance_interpolates_linearly(self) -> None:
        """L is additive, so it interpolates linearly: midpoint of 0 and 4."""
        product = _uplooking_family().uplooking_column_product(_WL, _up_los(5_000.0))
        np.testing.assert_allclose(product.L_toward_lower, 2.0, rtol=1e-12)

    @pytest.mark.level0
    def test_zero_length_segment_is_the_exact_vacuum_identity(self) -> None:
        product = _uplooking_family().uplooking_column_product(_WL, _up_los(1e-9))
        np.testing.assert_allclose(product.tau, 1.0, rtol=1e-9)
        np.testing.assert_allclose(product.L_toward_lower, 0.0, atol=1e-9)

    @pytest.mark.level0
    def test_above_the_hull_refuses_rather_than_extrapolates(self) -> None:
        with pytest.raises(AtmosphereValidationError, match="outside the available range"):
            _uplooking_family().uplooking_column_product(_WL, _up_los(50_000.0))

    @pytest.mark.level0
    def test_provenance_names_the_segment_and_the_direction(self) -> None:
        product = _uplooking_family().uplooking_column_product(_WL, _up_los(5_000.0))
        assert product.provenance["family_direction"] == "up"
        assert product.provenance["segment_kind"] == "column"
        assert product.provenance["radiance_product"] == "L_toward_lower"
        # The segment is keyed to its LOWER endpoint (ADR-0011 decision 3),
        # which for an up-looking path is the sensor.
        assert product.provenance["h_low_m"] == pytest.approx(0.0, abs=1e-12)
        assert product.provenance["h_high_m"] == pytest.approx(5_000.0, abs=1e-9)
        assert product.provenance["zeta_low_rad"] == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Refusals — every way to get a plausible-looking wrong number
# ---------------------------------------------------------------------------


class TestUplookingRefusals:
    @pytest.mark.level0
    def test_downlooking_los_refused(self) -> None:
        los = LineOfSightGeometry(theta_o=0.0, h_tgt=0.0, h_sensor=5_000.0)
        with pytest.raises(AtmosphereValidationError, match="down.-looking"):
            _uplooking_family().uplooking_column_product(_WL, los)

    @pytest.mark.level0
    def test_off_vertical_query_refused_and_points_at_the_simple_backend(self) -> None:
        """The family is a vertical ladder; there is no up-looking zenith fan.

        Serving a 45° slant from the vertical column via the sec-law would be
        ~2.5% low in band-mean LWIR τ (measured against the K6 holdout), so the
        query is refused, not approximated.
        """
        los = _up_los(5_000.0, theta_o=math.pi - math.radians(45.0))
        with pytest.raises(AtmosphereValidationError) as exc:
            _uplooking_family().uplooking_column_product(_WL, los)
        message = str(exc.value)
        assert "VERTICAL" in message
        assert "simple" in message
        assert "45.0000" in message

    @pytest.mark.level0
    def test_elevated_sensor_refused(self) -> None:
        """The runs integrate from ground up; a different lower endpoint is a
        different column (the lowest 100 m hold ~8% of the aerosol column)."""
        los = _up_los(9_000.0, h_sensor=3_000.0)
        with pytest.raises(AtmosphereValidationError, match="rendered lower endpoint"):
            _uplooking_family().uplooking_column_product(_WL, los)

    @pytest.mark.level0
    def test_sensor_within_a_metre_is_accepted(self) -> None:
        """A ground sensor on a 0.5 m tripod is the same column."""
        product = _uplooking_family().uplooking_column_product(_WL, _up_los(5_000.0, h_sensor=0.5))
        np.testing.assert_allclose(product.tau, 0.5, rtol=1e-3)

    @pytest.mark.level0
    def test_legacy_los_without_sensor_altitude_refused(self) -> None:
        """G2: the sensor endpoint comes from the LOS, never from params."""
        los = LineOfSightGeometry(theta_o=0.3, h_tgt=0.0)
        with pytest.raises(Exception, match="h_sensor"):
            _uplooking_family().uplooking_column_product(_WL, los)


# ---------------------------------------------------------------------------
# The shipped family's on-disk contract
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _UPLOOKING_DIR.exists(), reason="shipped up-looking family not present")
class TestShippedUplookingNpzContract:
    @pytest.mark.level0
    def test_every_node_carries_the_direction_marker_and_the_downward_key(self) -> None:
        files = sorted(_UPLOOKING_DIR.glob("*.npz"))
        assert len(files) == 6
        for npz_file in files:
            with np.load(npz_file, allow_pickle=True) as data:
                assert str(data[FAMILY_DIRECTION_KEY]) == "up"
                assert UPLOOKING_RADIANCE_KEY in data
                # The upwelling name must NOT be present: a down-looking
                # reader has to fail, not read the wrong-direction product.
                assert "path_radiance" not in data.files
                assert "atm_emission_down" not in data.files

    @pytest.mark.level0
    def test_tabulated_reader_refuses_an_uplooking_file(self) -> None:
        from radiant.atmosphere.tabulated import TabulatedAtmosphere

        with pytest.raises(AtmosphereValidationError, match="path_radiance"):
            TabulatedAtmosphere.from_npz(_UPLOOKING_DIR / "t010.npz")
