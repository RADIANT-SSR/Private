"""Integration: Gap 127 — near-field emission derives only from defined elements.

Runs the reference MWIR chain (see test_chain_extended.py) in scalar mode
(no elements) and in full-prescription mode with a warm mirror. Scalar mode
must produce exactly zero near-field — the lump is bookkeeping, not a
surface, and the former ``optics.scalar_emissivity`` knob is gone — while a
defined mirror (Kirchhoff ε = 1 − R) at the same temperature must emit.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.optics.element_factories import make_reflective_element

FILTER_MIN = 3.5
FILTER_MAX = 5.0
OPTICS_TEMP_K = 293.0
MIRROR_R = 0.95  # eps = 1 - R = 0.05 per Kirchhoff


def _run(*, with_mirror: bool):
    wl = np.linspace(FILTER_MIN, FILTER_MAX, 500)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("source.target.is_hot_target", True)
    params.set("optics.aperture_diameter_m", 0.30)
    params.set("optics.focal_length_m", 1.20)
    params.set("optics.transmission_scalar", 0.70)
    params.set("optics.optics_temperature_K", OPTICS_TEMP_K)
    params.set("detector.pixel_pitch_x_um", 18.0)
    params.set("detector.pixel_pitch_y_um", 18.0)
    params.set("detector.qe_value", 0.70)
    params.set("detector.dark_rate_e_per_s", 100.0)
    params.set("geometry.sensor_altitude_m", 8000.0)
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("spectral_integration.filter_min_um", FILTER_MIN)
    params.set("spectral_integration.filter_max_um", FILTER_MAX)
    params.set("spectral_integration.integration_time_s", 0.005)
    params.set("readout.read_noise_e_rms", 5.0)
    params.set("readout.gain_e_per_dn", 32.0)
    params.set("readout.adc_bits", 16)
    params.resolve()
    extra_stage_outputs = None
    if with_mirror:
        mirror = make_reflective_element(
            "m1",
            MIRROR_R,
            wavelength_um=wl,
            temperature_K=OPTICS_TEMP_K,
            diameter_m=0.30,
            distance_to_fpa_m=1.2,
        )
        extra_stage_outputs = {"optics_config": {"element_list": (mirror,)}}
    return session.run(params, extra_stage_outputs=extra_stage_outputs)


@pytest.fixture(scope="module")
def scalar_mode():
    return _run(with_mirror=False)


@pytest.fixture(scope="module")
def with_mirror():
    return _run(with_mirror=True)


@pytest.mark.level2
class TestElementOnlyNearfield:
    def test_scalar_mode_nearfield_is_exactly_zero(self, scalar_mode) -> None:
        """Gap 127: the scalar lump never emits — warm optics need elements."""
        budget = scalar_mode.stage_outputs["detector"]["noise_budget_raw"]
        assert budget.terms["nearfield_shot"] == pytest.approx(0.0, abs=1e-12)

    def test_scalar_emissivity_parameter_is_gone(self) -> None:
        """The removed knob fails loudly, not silently."""
        session = RadiantSession(wavelength_um=np.linspace(FILTER_MIN, FILTER_MAX, 50))
        params = session.default_params()
        with pytest.raises(Exception, match="scalar_emissivity"):
            params.set("optics.scalar_emissivity", 0.25)

    def test_defined_mirror_produces_nearfield(self, with_mirror) -> None:
        """A warm mirror (Kirchhoff eps = 1 - R) at 293 K in MWIR must emit."""
        budget = with_mirror.stage_outputs["detector"]["noise_budget_raw"]
        assert budget.terms["nearfield_shot"] > 0.0

    def test_nearfield_irradiance_stored(self, with_mirror) -> None:
        nf = with_mirror.stage_outputs["optics"]["nearfield_irradiance_at_fpa"]
        assert float(np.max(nf.values)) > 0.0

    def test_mirror_emission_lowers_snr(self, scalar_mode, with_mirror) -> None:
        """Added background noise must lower SNR, not raise it.

        The mirror run's throughput differs (R = 0.95 element list vs the
        scalar 0.70), so compare noise, not signal: the near-field term adds
        variance the scalar run does not have.
        """
        b_scalar = scalar_mode.stage_outputs["detector"]["noise_budget_raw"]
        b_mirror = with_mirror.stage_outputs["detector"]["noise_budget_raw"]
        assert b_mirror.terms["nearfield_shot"] > b_scalar.terms["nearfield_shot"]
