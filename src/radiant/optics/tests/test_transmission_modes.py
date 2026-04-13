"""Tests for radiant.optics.transmission_modes.

Category C validation for the five transmission input modes:
- Mode 1: scalar broadcast
- Mode 3: telescope + filters product
- Mode 5: full element list
- Cross-mode consistency: Mode 1 vs Mode 5 single element
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.spectral import SpectralData
from radiant.optics.element import ElementKind, OpticalElement, make_lumped_element
from radiant.optics.filters import FilterSpec, FilterType
from radiant.optics.transmission_modes import (
    TransmissionInputMode,
    resolve_transmission,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WL = np.linspace(3.0, 5.0, 50)


def _flat_spectral(value: float, name: str = "test") -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=WL.copy(),
        values=np.full_like(WL, value),
        unit="",
        source="test fixture",
    )


def _mirror(R: float, name: str = "m") -> OpticalElement:
    return OpticalElement(
        name=name,
        kind=ElementKind.MIRROR,
        temperature_K=290.0,
        transmittance=_flat_spectral(0.0, f"{name}.tau"),
        reflectance=_flat_spectral(R, f"{name}.rho"),
        diameter_m=0.3,
        distance_to_fpa_m=1.0,
    )


# ---------------------------------------------------------------------------
# Mode 1: Scalar
# ---------------------------------------------------------------------------


class TestScalarMode:
    """Verify Mode 1 scalar transmission."""

    def test_flat_at_scalar(self) -> None:
        result = resolve_transmission(
            TransmissionInputMode.SCALAR, WL, transmission_scalar=0.7,
        )
        np.testing.assert_allclose(result.transmission.values, 0.7, atol=1e-12)
        assert result.mode == TransmissionInputMode.SCALAR

    def test_single_lumped_element(self) -> None:
        result = resolve_transmission(
            TransmissionInputMode.SCALAR, WL, transmission_scalar=0.7,
        )
        assert len(result.elements) == 1
        assert result.elements[0].kind == ElementKind.LUMPED

    def test_emissivity_consistent(self) -> None:
        """Lumped element emissivity = 1 - T = 0.3."""
        result = resolve_transmission(
            TransmissionInputMode.SCALAR, WL, transmission_scalar=0.7,
        )
        np.testing.assert_allclose(
            result.elements[0].emissivity.values, 0.3, atol=1e-12,
        )

    def test_missing_scalar_raises(self) -> None:
        with pytest.raises(ValueError, match="transmission_scalar"):
            resolve_transmission(TransmissionInputMode.SCALAR, WL)


# ---------------------------------------------------------------------------
# Mode 2: Spectral file
# ---------------------------------------------------------------------------


class TestSpectralFileMode:
    """Verify Mode 2 spectral file transmission."""

    def test_uses_preloaded(self) -> None:
        tau_sd = _flat_spectral(0.8, "preloaded")
        result = resolve_transmission(
            TransmissionInputMode.SPECTRAL_FILE, WL,
            transmission_spectral=tau_sd,
        )
        np.testing.assert_allclose(result.transmission.values, 0.8, atol=1e-12)
        assert len(result.elements) == 1

    def test_missing_spectral_raises(self) -> None:
        with pytest.raises(ValueError, match="transmission_spectral"):
            resolve_transmission(TransmissionInputMode.SPECTRAL_FILE, WL)


# ---------------------------------------------------------------------------
# Mode 3: Telescope + filters
# ---------------------------------------------------------------------------


class TestTelescopeFilterMode:
    """Verify Mode 3 telescope + filter stack."""

    def test_telescope_times_filter(self) -> None:
        """telescope_tau=0.9 * bandpass peak=0.95 -> in-band 0.855."""
        bp = FilterSpec(
            filter_type=FilterType.BANDPASS,
            center_um=4.0,
            fwhm_um=1.0,
            peak_transmission=0.95,
            oob_rejection=1e-4,
            name="bp",
        )
        result = resolve_transmission(
            TransmissionInputMode.TELESCOPE_PLUS_FILTERS, WL,
            telescope_transmission=0.9,
            filter_specs=(bp,),
        )
        # At band center, should be ~0.9 * 0.95 = 0.855
        idx = np.argmin(np.abs(WL - 4.0))
        # Filter clips at 1 - 2*0.005 = 0.99 for T, so T=0.95 < 0.99 is fine
        assert result.transmission.values[idx] == pytest.approx(
            0.9 * 0.95, abs=0.01,
        )

    def test_oob_near_zero(self) -> None:
        """Out-of-band: telescope * filter_oob."""
        bp = FilterSpec(
            filter_type=FilterType.BANDPASS,
            center_um=4.0,
            fwhm_um=0.5,
            peak_transmission=0.95,
            oob_rejection=1e-4,
            name="bp",
        )
        result = resolve_transmission(
            TransmissionInputMode.TELESCOPE_PLUS_FILTERS, WL,
            telescope_transmission=0.9,
            filter_specs=(bp,),
        )
        # Well out-of-band (3.0 um)
        assert result.transmission.values[0] == pytest.approx(
            0.9 * 1e-4, abs=1e-5,
        )

    def test_elements_include_telescope_and_filter(self) -> None:
        bp = FilterSpec(
            filter_type=FilterType.BANDPASS,
            center_um=4.0,
            fwhm_um=1.0,
            name="bp",
        )
        result = resolve_transmission(
            TransmissionInputMode.TELESCOPE_PLUS_FILTERS, WL,
            telescope_transmission=0.9,
            filter_specs=(bp,),
        )
        # 1 telescope lumped + 1 filter element
        assert len(result.elements) == 2

    def test_missing_telescope_raises(self) -> None:
        with pytest.raises(ValueError, match="telescope_transmission"):
            resolve_transmission(
                TransmissionInputMode.TELESCOPE_PLUS_FILTERS, WL,
            )


# ---------------------------------------------------------------------------
# Mode 4: Key elements
# ---------------------------------------------------------------------------


class TestKeyElementsMode:
    """Verify Mode 4 key elements + residual."""

    def test_key_elements_with_residual(self) -> None:
        m = _mirror(0.98, "primary")
        result = resolve_transmission(
            TransmissionInputMode.KEY_ELEMENTS, WL,
            key_elements=(m,),
            residual_transmission=0.9,
        )
        # Net = 0.98 * 0.9 = 0.882
        np.testing.assert_allclose(
            result.transmission.values, 0.98 * 0.9, atol=1e-12,
        )

    def test_includes_residual_element(self) -> None:
        m = _mirror(0.98, "primary")
        result = resolve_transmission(
            TransmissionInputMode.KEY_ELEMENTS, WL,
            key_elements=(m,),
            residual_transmission=0.85,
        )
        # key_elements + residual lumped
        assert len(result.elements) == 2
        assert result.elements[-1].kind == ElementKind.LUMPED

    def test_empty_key_elements_raises(self) -> None:
        with pytest.raises(ValueError, match="key_elements"):
            resolve_transmission(
                TransmissionInputMode.KEY_ELEMENTS, WL,
                key_elements=(),
            )


# ---------------------------------------------------------------------------
# Mode 5: Full prescription
# ---------------------------------------------------------------------------


class TestFullPrescriptionMode:
    """Verify Mode 5 full element list."""

    def test_two_mirrors(self) -> None:
        m1 = _mirror(0.98, "primary")
        m2 = _mirror(0.95, "secondary")
        result = resolve_transmission(
            TransmissionInputMode.FULL_PRESCRIPTION, WL,
            full_elements=(m1, m2),
        )
        np.testing.assert_allclose(
            result.transmission.values, 0.98 * 0.95, atol=1e-12,
        )

    def test_elements_unchanged(self) -> None:
        m1 = _mirror(0.98, "primary")
        m2 = _mirror(0.95, "secondary")
        result = resolve_transmission(
            TransmissionInputMode.FULL_PRESCRIPTION, WL,
            full_elements=(m1, m2),
        )
        assert result.elements == (m1, m2)

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="full_elements"):
            resolve_transmission(
                TransmissionInputMode.FULL_PRESCRIPTION, WL,
                full_elements=(),
            )


# ---------------------------------------------------------------------------
# Cross-mode consistency
# ---------------------------------------------------------------------------


class TestCrossMode:
    """Mode 1 vs Mode 5 consistency for equivalent inputs."""

    def test_scalar_vs_single_lumped(self) -> None:
        """Scalar tau=0.7 and Mode 5 with equivalent lumped element
        should produce identical transmission."""
        mode1 = resolve_transmission(
            TransmissionInputMode.SCALAR, WL,
            transmission_scalar=0.7,
        )

        tau_sd = _flat_spectral(0.7, "tau")
        lumped = make_lumped_element(tau_sd, 290.0, 0.3, 1.0)
        mode5 = resolve_transmission(
            TransmissionInputMode.FULL_PRESCRIPTION, WL,
            full_elements=(lumped,),
        )

        np.testing.assert_allclose(
            mode1.transmission.values,
            mode5.transmission.values,
            atol=1e-12,
        )

    def test_all_modes_produce_elements(self) -> None:
        """Every mode should produce at least one element."""
        # Mode 1
        r1 = resolve_transmission(
            TransmissionInputMode.SCALAR, WL, transmission_scalar=0.7,
        )
        assert len(r1.elements) >= 1

        # Mode 2
        r2 = resolve_transmission(
            TransmissionInputMode.SPECTRAL_FILE, WL,
            transmission_spectral=_flat_spectral(0.8),
        )
        assert len(r2.elements) >= 1

        # Mode 3
        r3 = resolve_transmission(
            TransmissionInputMode.TELESCOPE_PLUS_FILTERS, WL,
            telescope_transmission=0.9,
            filter_specs=(),
        )
        assert len(r3.elements) >= 1

        # Mode 4
        r4 = resolve_transmission(
            TransmissionInputMode.KEY_ELEMENTS, WL,
            key_elements=(_mirror(0.98),),
        )
        assert len(r4.elements) >= 1

        # Mode 5
        r5 = resolve_transmission(
            TransmissionInputMode.FULL_PRESCRIPTION, WL,
            full_elements=(_mirror(0.98),),
        )
        assert len(r5.elements) >= 1
