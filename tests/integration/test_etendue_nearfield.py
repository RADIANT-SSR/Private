"""Integration: Gap 128 — étendue-conserving near-field, cold stop as pupil stop.

Three chain-level contracts, on the reference MWIR chain:

1. **Default bit-identity** — ``optics.cold_stop_undersize_frac = 0`` (the
   default) reproduces the run that never mentions the parameter, to the last
   bit. This is the regression gate for the whole change.
2. **One geometry** — near-field irradiance equals ``Ω_cone · ε · B(λ,T)`` for a
   single warm mirror, and is *independent* of anything about that mirror's
   size or position, because those are no longer inputs.
3. **Signal and near-field scale together** — undersizing the cold stop shrinks
   A_collect, raises N_eff, shrinks Ω_cone, and degrades the PSF/MTF, all from
   the one effective pupil (Rule 4: the dual-path consistency check stays green).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.core.blackbody import planck_spectral_radiance
from radiant.optics.element_factories import make_reflective_element
from radiant.optics.etendue_cone import etendue_cone_solid_angle_sr

FILTER_MIN = 3.5
FILTER_MAX = 5.0
OPTICS_TEMP_K = 293.0
MIRROR_R = 0.95  # eps = 1 - R = 0.05 [-] per Kirchhoff
APERTURE_M = 0.30
FOCAL_M = 1.80  # f/6 exactly


def _run(*, undersize: float | None = None, obscuration: float | None = None):
    wl = np.linspace(FILTER_MIN, FILTER_MAX, 500)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("source.target.is_hot_target", True)
    params.set("optics.aperture_diameter_m", APERTURE_M)
    params.set("optics.focal_length_m", FOCAL_M)
    params.set("optics.transmission_scalar", 0.70)
    params.set("optics.optics_temperature_K", OPTICS_TEMP_K)
    if undersize is not None:
        params.set("optics.cold_stop_undersize_frac", undersize)
    if obscuration is not None:
        params.set("optics.cold_stop_obscuration_ratio", obscuration)
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
    mirror = make_reflective_element("m1", MIRROR_R, wavelength_um=wl, temperature_K=OPTICS_TEMP_K)
    return session.run(params, extra_stage_outputs={"optics_config": {"element_list": (mirror,)}})


@pytest.fixture(scope="module")
def unset():
    """The parameter never mentioned — the pre-Gap-128 call shape."""
    return _run()


@pytest.fixture(scope="module")
def zero():
    """The parameter explicitly set to its default."""
    return _run(undersize=0.0, obscuration=0.0)


@pytest.fixture(scope="module")
def undersized():
    """A 10 % undersized cold stop."""
    return _run(undersize=0.10)


@pytest.mark.level2
class TestDefaultBitIdentity:
    """u = 0 must move nothing, to the last bit."""

    def test_metrics_bit_identical(self, unset, zero) -> None:
        for key, value in unset.metrics.items():
            if isinstance(value, float) and math.isfinite(value):
                assert zero.metrics[key] == value, f"{key} moved at u = 0"

    def test_signal_electrons_bit_identical(self, unset, zero) -> None:
        a = unset.frames["photoelectrons"].in_band_value
        b = zero.frames["photoelectrons"].in_band_value
        assert a == b

    def test_effective_pupil_is_the_primary(self, zero) -> None:
        out = zero.stage_outputs["optics"]
        assert out["D_eff_m"] == APERTURE_M  # m
        assert out["obscuration_eff"] == 0.0  # [-]
        assert out["f_number_eff"] == pytest.approx(6.0, rel=1e-12)  # [-]


@pytest.mark.level2
class TestOneGeometry:
    """The acceptance cone is the only near-field geometry."""

    def test_nearfield_matches_cone_hand_calc(self, unset) -> None:
        """E_nf(λ) = Ω_cone [sr] · ε [-] · B(λ, 293 K) [W/m²/sr/µm]."""
        out = unset.stage_outputs["optics"]
        nf = out["nearfield_irradiance_at_fpa"]
        omega = etendue_cone_solid_angle_sr(6.0)
        expected = (
            omega * (1.0 - MIRROR_R) * planck_spectral_radiance(nf.wavelength_um, OPTICS_TEMP_K)
        )
        np.testing.assert_allclose(nf.values, expected, rtol=1e-12)

    def test_published_cone_matches_f_number(self, unset) -> None:
        out = unset.stage_outputs["optics"]
        assert out["Omega_cone"] == pytest.approx(
            etendue_cone_solid_angle_sr(out["f_number_eff"]), rel=1e-15
        )

    def test_cone_is_below_the_paraxial_form(self, unset) -> None:
        """Exact form, not π/(4N²): 0.0217036 sr vs 0.0218166 sr at f/6."""
        omega = unset.stage_outputs["optics"]["Omega_cone"]
        assert omega == pytest.approx(0.0217036, abs=1e-7)
        assert omega < math.pi / (4.0 * 6.0**2)


@pytest.mark.level2
class TestUndersizedColdStop:
    """Signal and near-field scale together, from one pupil."""

    def test_pupil_shrinks(self, undersized) -> None:
        out = undersized.stage_outputs["optics"]
        assert out["D_eff_m"] == pytest.approx(0.27, rel=1e-12)  # m
        assert out["f_number_eff"] == pytest.approx(6.0 / 0.9, rel=1e-12)  # [-]

    def test_collecting_area_falls_as_one_minus_u_squared(self, unset, undersized) -> None:
        a0 = unset.stage_outputs["optics"]["A_collect"]  # m²
        a1 = undersized.stage_outputs["optics"]["A_collect"]  # m²
        assert a1 / a0 == pytest.approx(0.81, rel=1e-12)

    def test_nearfield_falls_with_the_cone(self, unset, undersized) -> None:
        """Near-field ∝ Ω_cone, so undersizing cuts it — it is not blocked, it shrinks."""
        nf0 = float(np.max(unset.stage_outputs["optics"]["nearfield_irradiance_at_fpa"].values))
        nf1 = float(
            np.max(undersized.stage_outputs["optics"]["nearfield_irradiance_at_fpa"].values)
        )
        omega0 = unset.stage_outputs["optics"]["Omega_cone"]  # sr
        omega1 = undersized.stage_outputs["optics"]["Omega_cone"]  # sr
        assert nf1 / nf0 == pytest.approx(omega1 / omega0, rel=1e-12)
        assert nf1 < nf0

    def test_diffraction_widens(self, unset, undersized) -> None:
        """A smaller pupil diffracts more — the PSF path sees the cold stop."""
        assert (
            undersized.metrics["diffraction_limit_angular_urad"]
            > unset.metrics["diffraction_limit_angular_urad"]
        )
        assert undersized.metrics["fwhm_x_m"] > unset.metrics["fwhm_x_m"]

    def test_mtf_at_nyquist_falls(self, unset, undersized) -> None:
        """The MTF product path sees the same cold stop (Rule 4)."""
        assert undersized.metrics["mtf_at_nyquist"] < unset.metrics["mtf_at_nyquist"]

    def test_dual_path_consistency_stays_green(self, undersized) -> None:
        """Rule 4: the effective pupil entered ONCE, so the two paths still agree."""
        check = undersized.stage_outputs["performance"]["dual_path_consistency"]
        assert check.passed_x and check.passed_y, check


@pytest.mark.level2
class TestColdShieldObscuration:
    """max(primary, cold shield) governs the effective obscuration."""

    def test_shield_obscuration_applies(self) -> None:
        result = _run(obscuration=0.30)
        assert result.stage_outputs["optics"]["obscuration_eff"] == 0.30  # [-]

    def test_shield_obscuration_reduces_collecting_area(self, unset) -> None:
        result = _run(obscuration=0.30)
        ratio = (
            result.stage_outputs["optics"]["A_collect"] / unset.stage_outputs["optics"]["A_collect"]
        )
        assert ratio == pytest.approx(1.0 - 0.30**2, rel=1e-12)


@pytest.mark.level2
class TestRemovedParametersFailLoudly:
    """The deleted knobs name Gap 128 rather than a nearest-neighbour guess."""

    @pytest.mark.parametrize(
        "name",
        [
            "optics.nearfield_fraction",
            "optics.cold_stop_efficiency",
            "optics.optics_distance_to_fpa_m",
        ],
    )
    def test_removed_parameter_message(self, name: str) -> None:
        session = RadiantSession(wavelength_um=np.linspace(FILTER_MIN, FILTER_MAX, 50))
        params = session.default_params()
        with pytest.raises(Exception, match="Gap 128") as exc:
            params.set(name, 0.1)
        assert "no longer exists" in str(exc.value)
