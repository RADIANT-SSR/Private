"""Gap 59 — day/night solar toggle, chain level.

An MWIR ambient mixed scene (T3Mixed: ε < 1 target reflecting solar) must
lose its reflected-solar signal at night and keep its thermal signal:

    signal(day) > signal(night) > 0

and 'night' must be inert for a pure-thermal LWIR scene (T1Thermal never
carried a solar term).
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.api.session import RadiantSession


def _run(band: tuple[float, float], illumination: str, *, hot_target: bool):
    session = RadiantSession(wavelength_um=np.linspace(band[0], band[1], 151))
    params = session.default_params()
    params.set("source.scene_type", "extended")
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.7)  # reflective enough to matter
    params.set("source.target.is_hot_target", hot_target)
    params.set("geometry.solar_illumination", illumination)
    params.set("geometry.solar_zenith_rad", 0.3)
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "us_standard")
    params.set("geometry.sensor_altitude_m", 3000.0)
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.6)
    params.set("optics.transmission_scalar", 0.7)
    params.set("detector.pixel_pitch_x_um", 20.0)
    params.set("detector.pixel_pitch_y_um", 20.0)
    params.set("detector.qe_value", 0.6)
    params.set("detector.dark_rate_e_per_s", 1e4)
    params.set("detector.detector_temperature_K", 120.0)
    params.set("spectral_integration.filter_min_um", band[0])
    params.set("spectral_integration.filter_max_um", band[1])
    params.set("spectral_integration.integration_time_s", 1e-3)
    params.set("readout.read_noise_e_rms", 50.0)
    params.resolve()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return session.run(params)


@pytest.mark.level2
class TestSolarIlluminationChain:
    def test_mwir_mixed_scene_day_exceeds_night(self) -> None:
        """T3Mixed MWIR: the daytime reflected-solar term is real and the
        nighttime signal is pure thermal (still positive)."""
        day = _run((3.5, 5.0), "day", hot_target=False)
        night = _run((3.5, 5.0), "night", hot_target=False)
        s_day = day.stage_outputs["spectral_integration"]["signal_e"]
        s_night = night.stage_outputs["spectral_integration"]["signal_e"]
        assert s_night > 0.0
        assert s_day > s_night, (
            f"day signal {s_day:.4e} should exceed night {s_night:.4e} "
            "(reflected-solar term removed at night)"
        )

    def test_night_inert_for_pure_thermal(self) -> None:
        """T1Thermal (is_hot_target) never had a solar term — day == night."""
        day = _run((8.0, 12.0), "day", hot_target=True)
        night = _run((8.0, 12.0), "night", hot_target=True)
        s_day = day.stage_outputs["spectral_integration"]["signal_e"]
        s_night = night.stage_outputs["spectral_integration"]["signal_e"]
        assert s_day == pytest.approx(s_night, rel=1e-12)
