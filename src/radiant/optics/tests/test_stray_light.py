"""Tests for radiant.optics.stray_light.

Category C validation for stray light computation:
- Veiling glare fraction scales in-FOV irradiance
- Absolute irradiance distributes as spectral density
- PST mode raises NotImplementedError
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.spectral import SpectralData
from radiant.optics.stray_light import (
    StrayLightConfig,
    StrayLightInputMode,
    compute_stray_light_irradiance,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WL = np.linspace(3.0, 5.0, 50)


def _flat_irradiance(value: float) -> SpectralData:
    return SpectralData(
        name="in_fov",
        wavelength_um=WL.copy(),
        values=np.full_like(WL, value),
        unit="W/m^2/um",
        source="test fixture",
    )


# ---------------------------------------------------------------------------
# Veiling glare
# ---------------------------------------------------------------------------


class TestVeilingGlare:
    """Verify veiling glare mode."""

    def test_fraction_scales_irradiance(self) -> None:
        """VGF=0.01 with 1.0 W/m^2/um -> 0.01 W/m^2/um."""
        config = StrayLightConfig(
            input_mode=StrayLightInputMode.VEILING_GLARE,
            veiling_glare_fraction=0.01,
        )
        e_in = _flat_irradiance(1.0)
        result = compute_stray_light_irradiance(config, WL, in_fov_irradiance=e_in)
        np.testing.assert_allclose(result.values, 0.01, atol=1e-12)

    def test_zero_fraction_is_zero(self) -> None:
        config = StrayLightConfig(
            input_mode=StrayLightInputMode.VEILING_GLARE,
            veiling_glare_fraction=0.0,
        )
        e_in = _flat_irradiance(100.0)
        result = compute_stray_light_irradiance(config, WL, in_fov_irradiance=e_in)
        np.testing.assert_allclose(result.values, 0.0, atol=1e-15)

    def test_missing_in_fov_raises(self) -> None:
        config = StrayLightConfig(
            input_mode=StrayLightInputMode.VEILING_GLARE,
            veiling_glare_fraction=0.01,
        )
        with pytest.raises(ValueError, match="in_fov_irradiance"):
            compute_stray_light_irradiance(config, WL)


# ---------------------------------------------------------------------------
# Absolute irradiance
# ---------------------------------------------------------------------------


class TestAbsoluteIrradiance:
    """Verify absolute irradiance mode."""

    def test_distributes_over_bandwidth(self) -> None:
        """1e-3 W/m^2 over 2 um bandwidth -> 5e-4 W/m^2/um."""
        config = StrayLightConfig(
            input_mode=StrayLightInputMode.ABSOLUTE_IRRADIANCE,
            absolute_irradiance_W_m2=1e-3,
        )
        result = compute_stray_light_irradiance(config, WL)
        bandwidth = WL[-1] - WL[0]  # 2.0 um
        expected = 1e-3 / bandwidth
        np.testing.assert_allclose(result.values, expected, rtol=1e-10)

    def test_flat_output(self) -> None:
        """Output should be spectrally flat."""
        config = StrayLightConfig(
            input_mode=StrayLightInputMode.ABSOLUTE_IRRADIANCE,
            absolute_irradiance_W_m2=0.01,
        )
        result = compute_stray_light_irradiance(config, WL)
        assert np.all(np.diff(result.values) == 0.0)

    def test_zero_irradiance(self) -> None:
        config = StrayLightConfig(
            input_mode=StrayLightInputMode.ABSOLUTE_IRRADIANCE,
            absolute_irradiance_W_m2=0.0,
        )
        result = compute_stray_light_irradiance(config, WL)
        np.testing.assert_allclose(result.values, 0.0, atol=1e-15)


# ---------------------------------------------------------------------------
# Spectral file
# ---------------------------------------------------------------------------


class TestSpectralFile:
    """Verify spectral file mode."""

    def test_uses_preloaded(self) -> None:
        preloaded = _flat_irradiance(0.05)
        config = StrayLightConfig(
            input_mode=StrayLightInputMode.SPECTRAL_FILE,
            spectral_file="/path/to/stray.csv",
        )
        result = compute_stray_light_irradiance(
            config, WL, preloaded_spectral=preloaded,
        )
        np.testing.assert_allclose(result.values, 0.05, atol=1e-12)

    def test_missing_preloaded_raises(self) -> None:
        config = StrayLightConfig(
            input_mode=StrayLightInputMode.SPECTRAL_FILE,
            spectral_file="/path/to/stray.csv",
        )
        with pytest.raises(ValueError, match="preloaded_spectral"):
            compute_stray_light_irradiance(config, WL)


# ---------------------------------------------------------------------------
# PST stub
# ---------------------------------------------------------------------------


class TestPstStub:
    """Verify PST mode raises NotImplementedError."""

    def test_raises(self) -> None:
        config = StrayLightConfig(
            input_mode=StrayLightInputMode.PST_FILE,
            pst_file="/path/to/pst.csv",
        )
        with pytest.raises(NotImplementedError, match="PST"):
            compute_stray_light_irradiance(config, WL)


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    """Input validation for StrayLightConfig."""

    def test_vgf_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="veiling_glare_fraction"):
            StrayLightConfig(
                input_mode=StrayLightInputMode.VEILING_GLARE,
                veiling_glare_fraction=1.5,
            )

    def test_negative_absolute(self) -> None:
        with pytest.raises(ValueError, match="absolute_irradiance"):
            StrayLightConfig(
                input_mode=StrayLightInputMode.ABSOLUTE_IRRADIANCE,
                absolute_irradiance_W_m2=-0.01,
            )

    def test_spectral_file_missing_path(self) -> None:
        with pytest.raises(ValueError, match="spectral_file"):
            StrayLightConfig(input_mode=StrayLightInputMode.SPECTRAL_FILE)

    def test_pst_file_missing_path(self) -> None:
        with pytest.raises(ValueError, match="pst_file"):
            StrayLightConfig(input_mode=StrayLightInputMode.PST_FILE)


# ---------------------------------------------------------------------------
# includes_thermal flag
# ---------------------------------------------------------------------------


class TestIncludesThermal:
    """Verify includes_thermal is just a flag, not affecting stray calc."""

    def test_flag_stored(self) -> None:
        config = StrayLightConfig(
            input_mode=StrayLightInputMode.VEILING_GLARE,
            veiling_glare_fraction=0.01,
            includes_thermal=True,
        )
        assert config.includes_thermal is True
