"""Gap 57 — standard-atmosphere presets carry their standard water column.

Selecting a climate profile previously changed only the downwelling
emission temperature; ``precipitable_water_cm`` stayed at its US-standard
schema default (1.4 cm), so "tropical" silently ran US-standard
transmission. ``build_atmosphere_model`` now applies the profile's
McClatchey/MODTRAN standard column when (and only when) the user leaves
``precipitable_water_cm`` at its default.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.atmosphere.loaders import build_atmosphere_model
from radiant.atmosphere.simple import PROFILE_PWV_CM


def _params(profile: str, pwv: float | None):
    session = RadiantSession(wavelength_um=np.linspace(3.5, 5.0, 50))
    params = session.default_params()
    # Minimal required set so resolve() succeeds; only the atmosphere
    # parameters matter to the loader under test.
    params.set("source.scene_type", "extended")
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("optics.aperture_diameter_m", 0.1)
    params.set("optics.focal_length_m", 0.4)
    params.set("detector.pixel_pitch_x_um", 20.0)
    params.set("detector.pixel_pitch_y_um", 20.0)
    params.set("detector.qe_value", 0.7)
    params.set("geometry.sensor_altitude_m", 3000.0)
    params.set("spectral_integration.filter_min_um", 3.5)
    params.set("spectral_integration.filter_max_um", 5.0)
    params.set("spectral_integration.integration_time_s", 1e-3)
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", profile)
    if pwv is not None:
        params.set("atmosphere.precipitable_water_cm", pwv)
    params.resolve()
    return params


class TestProfilePwvCoupling:
    @pytest.mark.level0
    def test_profile_default_pwv_applied(self) -> None:
        """Default PWV + tropical profile → tropical water column."""
        model = build_atmosphere_model(_params("tropical", None))
        assert model.precipitable_water_cm == pytest.approx(4.11, abs=1e-9)

    @pytest.mark.level0
    @pytest.mark.parametrize("profile", sorted(PROFILE_PWV_CM))
    def test_every_profile_maps(self, profile: str) -> None:
        model = build_atmosphere_model(_params(profile, None))
        assert model.precipitable_water_cm == pytest.approx(PROFILE_PWV_CM[profile], abs=1e-9)

    @pytest.mark.level0
    def test_explicit_pwv_wins(self) -> None:
        """A user-set PWV overrides the profile column."""
        model = build_atmosphere_model(_params("tropical", 1.0))
        assert model.precipitable_water_cm == pytest.approx(1.0, abs=1e-9)

    @pytest.mark.level0
    def test_us_standard_default_unchanged(self) -> None:
        """Default-everything is bit-identical to the schema default."""
        model = build_atmosphere_model(_params("us_standard", None))
        assert model.precipitable_water_cm == pytest.approx(1.4, abs=1e-12)

    @pytest.mark.level0
    def test_explicit_default_value_wins(self) -> None:
        """Explicitly setting PWV to 1.4 also blocks the coupling (provenance,
        not value, decides)."""
        model = build_atmosphere_model(_params("tropical", 1.4))
        assert model.precipitable_water_cm == pytest.approx(1.4, abs=1e-12)
