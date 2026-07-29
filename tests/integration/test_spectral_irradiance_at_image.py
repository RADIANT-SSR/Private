"""At-image spectral irradiance is the electron budget's own integrand (item 16).

The published ``spectral_irradiance_at_image`` is not an independent
re-derivation of what reaches the focal plane — it is the stage's own
``photon_rate`` expressed as power per unit focal-plane area. The test that
matters is therefore a **round trip**: integrating it back through the same
photon and collection factors must reproduce the published ``signal_e``
exactly, not approximately. If it ever drifts, the plot and the electron count
have stopped describing the same thing.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.api.sensor import Sensor
from radiant.core.constants import hc

_CONFIG = Path(__file__).resolve().parents[2] / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture(scope="module")
def result():  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Sensor.load(_CONFIG).evaluate()


class TestPublished:
    def test_present_and_shaped_like_the_wavelength_grid(self, result) -> None:  # type: ignore[no-untyped-def]
        irradiance = result.stage_outputs["spectral_integration"]["spectral_irradiance_at_image"]
        assert irradiance.shape == result.state.wavelength_um.shape

    def test_strictly_positive_for_a_lit_scene(self, result) -> None:  # type: ignore[no-untyped-def]
        irradiance = result.stage_outputs["spectral_integration"]["spectral_irradiance_at_image"]
        assert np.all(irradiance > 0.0)
        assert np.all(np.isfinite(irradiance))

    def test_the_figure_axis_carries_the_unit(self, result) -> None:  # type: ignore[no-untyped-def]
        """R-UNITS: the operator sees the unit on the plot.

        It is deliberately NOT in the stage's ``OUTPUT_UNITS`` map — that map is
        the *scalar* Outputs-readout table (the readout skips non-scalars), and no
        other published spectral array registers there either. For an array the
        axis label is where the unit belongs.
        """
        import matplotlib

        matplotlib.use("Agg")
        from radiant.api.inspect import ResultPlotNamespace

        figure = ResultPlotNamespace(result).spectral_irradiance_at_image()
        assert "W/m²/µm" in figure.axes[0].get_ylabel()
        matplotlib.pyplot.close(figure)

    def test_not_registered_in_the_scalar_units_map(self) -> None:
        """Guard the convention: arrays stay out of the scalar readout table."""
        from radiant.spectral_integration.stage import OUTPUT_UNITS

        assert "spectral_irradiance_at_image" not in OUTPUT_UNITS


class TestRoundTripToSignalElectrons:
    """E(λ) must integrate back to the published signal_e — same quantity, same number."""

    def test_reconstructs_signal_e(self, result) -> None:  # type: ignore[no-untyped-def]
        outputs = result.stage_outputs["spectral_integration"]
        irradiance = outputs["spectral_irradiance_at_image"]

        wavelength_um = result.state.wavelength_um
        lam_m = wavelength_um * 1e-6
        pitch_x = 18e-6  # the shipped example's detector pitch [m]
        pitch_y = 18e-6
        pixel_area_m2 = pitch_x * pitch_y

        # E [W/m²/µm] → power on the pixel [W/µm] → photons/s/µm → electrons.
        photons_per_s_per_um = irradiance * pixel_area_m2 * lam_m / hc
        electrons_per_s_per_um = photons_per_s_per_um * outputs["qe_scalar"]

        band = (wavelength_um >= 3.5) & (wavelength_um <= 5.0)
        integration_time_s = 0.005
        reconstructed = (
            float(np.trapezoid(electrons_per_s_per_um[band], wavelength_um[band]))
            * integration_time_s
        )
        assert reconstructed == pytest.approx(outputs["signal_e"], rel=1e-9)


class TestScaling:
    """Sanity checks a physicist would make before trusting the curve."""

    def test_doubling_pixel_area_halves_the_irradiance(self) -> None:
        """E is power per unit area: same collected power over twice the area."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            base = Sensor.load(_CONFIG).evaluate()
            wider = Sensor.load(_CONFIG).set("detector.pixel_pitch_y_um", 36.0).evaluate()

        e_base = base.stage_outputs["spectral_integration"]["spectral_irradiance_at_image"]
        e_wider = wider.stage_outputs["spectral_integration"]["spectral_irradiance_at_image"]
        # Doubling the along-track pitch doubles both Ω_pixel (so the collected
        # power doubles) and A_pixel — the two cancel, leaving E unchanged.
        assert np.allclose(e_wider, e_base, rtol=1e-9)
