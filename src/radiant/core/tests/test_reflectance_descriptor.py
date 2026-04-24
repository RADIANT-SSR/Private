"""Step 6.1 — ReflectanceDescriptor protocol (Q4 stub).

Verifies that:
1. :class:`ScalarLambertianReflectance` wraps a scalar ρ(λ) SpectralData and
   returns ρ angle-independently (Lambertian definition).
2. :class:`~radiant.source.brdf_lambertian.LambertianBRDF` implements the
   :class:`~radiant.core.reflectance.ReflectanceDescriptor` protocol
   (``runtime_checkable`` structural isinstance).
3. :class:`~radiant.source.brdf_phong.PhongBRDF` implements the same protocol.
4. :class:`~radiant.core.descriptors.T2Reflective` accepts only a
   :class:`ReflectanceDescriptor` — raw :class:`SpectralData` is rejected.
   Gap H invariant: the boundary converter wraps the SpectralData in a
   :class:`ScalarLambertianReflectance` adapter before construction so
   downstream consumers can rely on the protocol.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.descriptors import T2Reflective
from radiant.core.reflectance import (
    ReflectanceDescriptor,
    ScalarLambertianReflectance,
)
from radiant.core.spectral import SpectralData
from radiant.source.brdf_lambertian import LambertianBRDF
from radiant.source.brdf_phong import PhongBRDF

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


_WL_VIS = np.linspace(0.4, 0.7, 16, dtype=np.float64)
_VIEW = np.asarray([0.0, 0.0, 1.0], dtype=np.float64)
_ILLUM = np.asarray([0.0, 0.0, 1.0], dtype=np.float64)


def _make_rho_spectral(value: float = 0.3) -> SpectralData:
    return SpectralData(
        name="test.reflectance",
        wavelength_um=_WL_VIS,
        values=np.full_like(_WL_VIS, value),
        unit="dimensionless",
        source="test_reflectance_descriptor",
    )


# ---------------------------------------------------------------------------
# 1. ScalarLambertianReflectance: angle-independent pass-through
# ---------------------------------------------------------------------------


class TestScalarLambertianReflectance:
    def test_returns_rho_independent_of_geometry(self) -> None:
        rho_val = 0.3
        adapter = ScalarLambertianReflectance(
            reflectance=_make_rho_spectral(rho_val)
        )

        # Same ρ regardless of view / illumination vectors.
        r_on_axis = adapter.reflectance_at(_WL_VIS, _VIEW, _ILLUM)
        r_off_axis = adapter.reflectance_at(
            _WL_VIS,
            np.asarray([1.0, 0.0, 0.0], dtype=np.float64),
            np.asarray([0.0, 1.0, 0.0], dtype=np.float64),
        )

        np.testing.assert_allclose(
            r_on_axis, np.full_like(_WL_VIS, rho_val), rtol=0, atol=1e-12
        )
        np.testing.assert_array_equal(r_on_axis, r_off_axis)

    def test_resamples_onto_requested_grid(self) -> None:
        adapter = ScalarLambertianReflectance(reflectance=_make_rho_spectral(0.5))
        lam_q = np.linspace(0.5, 0.6, 32, dtype=np.float64)
        r = adapter.reflectance_at(lam_q, _VIEW, _ILLUM)
        assert r.shape == lam_q.shape
        # Flat ρ = 0.5 must survive resample exactly (up to fp noise).
        np.testing.assert_allclose(
            r, np.full_like(lam_q, 0.5), rtol=0, atol=1e-12
        )

    def test_satisfies_protocol(self) -> None:
        adapter = ScalarLambertianReflectance(reflectance=_make_rho_spectral(0.2))
        assert isinstance(adapter, ReflectanceDescriptor)

    def test_rejects_out_of_range_reflectance(self) -> None:
        bad = SpectralData(
            name="test.bad",
            wavelength_um=_WL_VIS,
            values=np.full_like(_WL_VIS, 1.5),
            unit="dimensionless",
            source="test_reflectance_descriptor",
        )
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            ScalarLambertianReflectance(reflectance=bad)

    def test_rejects_negative_reflectance(self) -> None:
        bad = SpectralData(
            name="test.bad",
            wavelength_um=_WL_VIS,
            values=np.full_like(_WL_VIS, -0.1),
            unit="dimensionless",
            source="test_reflectance_descriptor",
        )
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            ScalarLambertianReflectance(reflectance=bad)


# ---------------------------------------------------------------------------
# 2. LambertianBRDF implements ReflectanceDescriptor
# ---------------------------------------------------------------------------


class TestLambertianBRDFProtocol:
    def test_implements_protocol_runtime_checkable(self) -> None:
        brdf = LambertianBRDF(reflectance=0.4)
        assert isinstance(brdf, ReflectanceDescriptor)

    def test_reflectance_at_returns_rho_not_brdf(self) -> None:
        rho = 0.4
        brdf = LambertianBRDF(reflectance=rho)
        r = brdf.reflectance_at(_WL_VIS, _VIEW, _ILLUM)
        # Protocol returns ρ (dimensionless), NOT ρ/π (BRDF in sr⁻¹).
        np.testing.assert_allclose(
            r, np.full_like(_WL_VIS, rho), rtol=0, atol=1e-12
        )
        # And the evaluate() path (sr⁻¹) still returns ρ/π.
        brdf_sr = brdf.evaluate(_WL_VIS)
        np.testing.assert_allclose(
            brdf_sr, np.full_like(_WL_VIS, rho / math.pi), rtol=0, atol=1e-12
        )

    def test_reflectance_at_array_reflectance(self) -> None:
        rho_arr = np.linspace(0.1, 0.9, _WL_VIS.size, dtype=np.float64)
        brdf = LambertianBRDF(reflectance=rho_arr)
        r = brdf.reflectance_at(_WL_VIS, _VIEW, _ILLUM)
        np.testing.assert_array_equal(r, rho_arr)


# ---------------------------------------------------------------------------
# 3. PhongBRDF implements ReflectanceDescriptor
# ---------------------------------------------------------------------------


class TestPhongBRDFProtocol:
    def test_implements_protocol_runtime_checkable(self) -> None:
        brdf = PhongBRDF(reflectance=0.5, specular_fraction=0.2, phong_exponent=20.0)
        assert isinstance(brdf, ReflectanceDescriptor)

    def test_reflectance_at_returns_total_rho(self) -> None:
        rho = 0.5
        brdf = PhongBRDF(
            reflectance=rho, specular_fraction=0.3, phong_exponent=10.0
        )
        r = brdf.reflectance_at(_WL_VIS, _VIEW, _ILLUM)
        # Phong.reflectance_at exposes TOTAL hemispherical ρ (ρ_d + ρ_s = ρ),
        # not the angle-resolved BRDF.  The split between ρ_d and ρ_s lives
        # in the BRDF.evaluate path.
        np.testing.assert_allclose(
            r, np.full_like(_WL_VIS, rho), rtol=0, atol=1e-12
        )


# ---------------------------------------------------------------------------
# 4. T2Reflective accepts a ReflectanceDescriptor only (Gap H invariant)
# ---------------------------------------------------------------------------


class TestT2ReflectiveAcceptsReflectanceDescriptor:
    def test_rejects_raw_spectral_data(self) -> None:
        """Gap H: raw SpectralData is not a valid ``rho`` for ``T2Reflective``.

        The supported entry path is
        ``radiant.source.converters.reflectance.reflectance_to_descriptor``,
        which wraps the SpectralData in a ``ScalarLambertianReflectance``
        adapter.  Passing the SpectralData directly bypasses the protocol
        invariant that downstream consumers rely on.
        """
        from radiant.core.parameters import ParameterBoundsError

        rho_sd = _make_rho_spectral(0.3)
        with pytest.raises(
            ParameterBoundsError,
            match="rho must be a ReflectanceDescriptor",
        ):
            T2Reflective(
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
                rho=rho_sd,  # type: ignore[arg-type]
            )

    def test_accepts_scalar_lambertian_reflectance(self) -> None:
        adapter = ScalarLambertianReflectance(reflectance=_make_rho_spectral(0.3))
        desc = T2Reflective(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            rho=adapter,
        )
        # The descriptor stores the adapter as-is (stub behavior).
        assert desc.rho is adapter
        assert isinstance(desc.rho, ReflectanceDescriptor)

    def test_accepts_lambertian_brdf(self) -> None:
        brdf = LambertianBRDF(reflectance=0.3)
        desc = T2Reflective(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            rho=brdf,
        )
        assert desc.rho is brdf
        assert isinstance(desc.rho, ReflectanceDescriptor)

    def test_rho_none_still_raises(self) -> None:
        """Preserves the existing required-rho contract."""
        from radiant.core.parameters import ParameterBoundsError

        with pytest.raises(ParameterBoundsError, match="rho is required"):
            T2Reflective(
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
                rho=None,
            )

    def test_mwir_warning_fires_on_scalar_lambertian_adapter(self) -> None:
        """MWIR Rule-17 warning fires when the adapter's stored grid overlaps 3–5 µm.

        Gap H: post-wrap, the authoritative MWIR warning runs against the
        ``ScalarLambertianReflectance`` adapter's stored SpectralData.  The
        raw-SpectralData path was removed (Gap H negative test above).
        """
        wl_mwir = np.linspace(3.5, 4.5, 8, dtype=np.float64)
        rho_mwir = SpectralData(
            name="test.mwir",
            wavelength_um=wl_mwir,
            values=np.full_like(wl_mwir, 0.2),
            unit="dimensionless",
            source="test_reflectance_descriptor",
        )
        adapter = ScalarLambertianReflectance(reflectance=rho_mwir)
        with pytest.warns(UserWarning, match="MWIR"):
            T2Reflective(
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
                rho=adapter,
            )
