"""Tests for the S12 radiance-temperature boundary converter.

Step 2.2 of the Target Definition Matrix Implementation Plan — scalar
T_R + band converts to T1Thermal(T_t=T_R, ε≡1).  Round-trip parity
between the converter + Planck band integral + the inversion harness
lives in ``test_invert_band_radiance.py``; this file focuses on the
converter's input validation and descriptor wiring.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.descriptors import T1Thermal
from radiant.core.parameters import ParameterBoundsError
from radiant.source.converters.invert_band_radiance import (
    integrate_planck_over_band,
    invert_band_radiance_to_temperature,
)
from radiant.source.converters.radiance_temperature import (
    radiance_temperature_to_descriptor,
)


def _lwir_grid(n: int = 61) -> np.ndarray:
    return np.linspace(8.0, 14.0, n, dtype=np.float64)


class TestHappyPath:
    @pytest.mark.level0
    def test_emits_T1Thermal_with_epsilon_1(self) -> None:
        lam = _lwir_grid()
        desc = radiance_temperature_to_descriptor(
            T_R_K=300.0,
            band_um=(8.0, 12.0),
            wavelength_um=lam,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )
        assert isinstance(desc, T1Thermal)
        assert desc.T_t == pytest.approx(300.0, abs=1e-12)
        assert desc.epsilon is not None
        np.testing.assert_allclose(desc.epsilon.values, np.ones_like(lam), atol=0.0)

    @pytest.mark.level0
    def test_passes_through_shape_and_area(self) -> None:
        lam = _lwir_grid(n=11)
        desc = radiance_temperature_to_descriptor(
            T_R_K=500.0,
            band_um=(3.0, 5.0),
            wavelength_um=lam,
            scene_type="point_source",
            target_location="airborne",
            h_tgt=3000.0,
            A_t=12.5,
            shape=None,
        )
        assert isinstance(desc, T1Thermal)
        assert desc.A_t == 12.5
        assert desc.h_tgt == 3000.0


class TestRoundTripAnchors:
    """Round-trip parity: T_R → L_band → invert → T_R across three bands."""

    @pytest.mark.parametrize(
        "T_R, band",
        [
            (300.0, (8.0, 12.0)),  # Anchor 1 — LWIR
            (500.0, (3.0, 5.0)),  # Anchor 2 — MWIR
            (2000.0, (0.7, 1.0)),  # Anchor 3 — visible Wien
        ],
    )
    @pytest.mark.level0
    def test_roundtrip_within_1e_3_K(self, T_R: float, band: tuple[float, float]) -> None:
        lam = _lwir_grid(n=21)
        desc = radiance_temperature_to_descriptor(
            T_R_K=T_R,
            band_um=band,
            wavelength_um=lam,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )
        assert isinstance(desc, T1Thermal)
        # Converter emits T1Thermal(T_t=T_R) — the L_band identity holds
        # by construction since ε ≡ 1.  Verify via the inversion helper.
        n_quad = 401 if band[0] < 2.0 else 201  # Wien band needs density
        L_band = integrate_planck_over_band(desc.T_t, band, n_quad=n_quad)
        T_rec = invert_band_radiance_to_temperature(L_band, band, n_quad=n_quad)
        assert abs(T_rec - T_R) < 1.0e-3, f"Band round-trip: T_R={T_R}, T_rec={T_rec}, band={band}"


class TestRejectsInvalidInputs:
    @pytest.mark.level0
    def test_T_R_non_positive_raises(self) -> None:
        lam = _lwir_grid(n=5)
        with pytest.raises(ParameterBoundsError, match="non-positive"):
            radiance_temperature_to_descriptor(
                T_R_K=0.0,
                band_um=(8.0, 12.0),
                wavelength_um=lam,
                scene_type="extended",
                target_location="terrestrial",
            )

    @pytest.mark.level0
    def test_T_R_above_ceiling_raises(self) -> None:
        lam = _lwir_grid(n=5)
        with pytest.raises(ParameterBoundsError, match="ceiling"):
            radiance_temperature_to_descriptor(
                T_R_K=15_000.0,
                band_um=(8.0, 12.0),
                wavelength_um=lam,
                scene_type="extended",
                target_location="terrestrial",
            )

    @pytest.mark.level0
    def test_T_R_nan_raises(self) -> None:
        lam = _lwir_grid(n=5)
        with pytest.raises(ParameterBoundsError, match="not finite"):
            radiance_temperature_to_descriptor(
                T_R_K=float("nan"),
                band_um=(8.0, 12.0),
                wavelength_um=lam,
                scene_type="extended",
                target_location="terrestrial",
            )

    @pytest.mark.level0
    def test_inverted_band_raises(self) -> None:
        lam = _lwir_grid(n=5)
        with pytest.raises(ParameterBoundsError, match="inverted|degenerate"):
            radiance_temperature_to_descriptor(
                T_R_K=300.0,
                band_um=(12.0, 8.0),
                wavelength_um=lam,
                scene_type="extended",
                target_location="terrestrial",
            )

    @pytest.mark.level0
    def test_non_positive_band_raises(self) -> None:
        lam = _lwir_grid(n=5)
        with pytest.raises(ParameterBoundsError, match="non-positive"):
            radiance_temperature_to_descriptor(
                T_R_K=300.0,
                band_um=(0.0, 12.0),
                wavelength_um=lam,
                scene_type="extended",
                target_location="terrestrial",
            )

    @pytest.mark.level0
    def test_at_aperture_rejected(self) -> None:
        lam = _lwir_grid(n=5)
        with pytest.raises(ParameterBoundsError, match="at_aperture"):
            radiance_temperature_to_descriptor(
                T_R_K=300.0,
                band_um=(8.0, 12.0),
                wavelength_um=lam,
                scene_type="extended",
                target_location="at_aperture",
            )
