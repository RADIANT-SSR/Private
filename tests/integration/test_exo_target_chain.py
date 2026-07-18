"""Integration: exo-altitude target over an atmospheric background (Gap 95).

The missile-defense driver scenario: a sub-pixel target above the
atmospheric column (h_tgt = 101 km) viewed from LEO (500 km) must run
end-to-end with an exact vacuum target leg — τ_up ≡ 1, L_path_up ≡ 0 —
while the ground→sensor full column (τ_full_up, L_path_full) survives to
the background/noise branch. Exercised on the shipped interpolated
ladder library (the axes-matched default) so the whole out-of-the-box
configuration path is covered.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.api.session import RadiantSession


def _params(session: RadiantSession, h_tgt_m: float):  # type: ignore[no-untyped-def]
    p = session.default_params()
    p.set("source.target.temperature", 700.0)  # hot booster body [K]
    p.set("source.target.emissivity", 0.9)
    p.set("geometry.target.shape", "sphere")
    p.set("geometry.target.shape_radius_m", 2.0)
    p.set("atmosphere.model", "interpolated")
    p.set("atmosphere.interpolation_axes", "sensor_altitude_m,target_altitude_m")
    p.set("geometry.sensor_altitude_m", 500_000.0)
    p.set("geometry.target_altitude_m", h_tgt_m)
    p.set("optics.aperture_diameter_m", 0.30)
    p.set("optics.focal_length_m", 0.75)
    p.set("optics.transmission_scalar", 0.60)
    p.set("detector.pixel_pitch_x_um", 17.0)
    p.set("detector.pixel_pitch_y_um", 17.0)
    p.set("detector.qe_value", 0.55)
    p.set("detector.dark_rate_e_per_s", 1000.0)
    p.set("spectral_integration.filter_min_um", 8.0)
    p.set("spectral_integration.filter_max_um", 13.0)
    p.set("spectral_integration.integration_time_s", 0.015)
    p.set("readout.read_noise_e_rms", 20.0)
    p.set("readout.gain_e_per_dn", 2.0)
    p.set("readout.adc_bits", 14)
    p.resolve()
    return p


@pytest.mark.level2
def test_exo_target_chain_runs_with_vacuum_leg_and_full_column_background() -> None:
    wl = np.linspace(8.0, 13.0, 251)
    session = RadiantSession(wavelength_um=wl)
    params = _params(session, h_tgt_m=101_000.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = session.run(params)

    q = result.stage_outputs["atmosphere"]["atm_quantities"]
    # Vacuum target leg — exact identities [dimensionless / W/m²/sr/µm].
    np.testing.assert_array_equal(q.tau_up, np.ones_like(wl))
    np.testing.assert_array_equal(q.tau_sun, np.ones_like(wl))
    np.testing.assert_array_equal(q.L_path_up, np.zeros_like(wl))
    # The background column is a real atmosphere, not vacuum.
    assert q.tau_full_up.min() < 1.0
    assert q.L_path_full.max() > 0.0
    # And the chain completes with a finite detection metric.
    assert np.isfinite(float(result.metrics["snr"]))
    assert float(result.metrics["snr"]) > 0.0


@pytest.mark.level2
def test_exo_background_column_matches_surface_target_run() -> None:
    """The exo run's background column equals a surface-target run's —
    the Gap 95 branch changes only the target leg."""
    wl = np.linspace(8.0, 13.0, 251)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        session_exo = RadiantSession(wavelength_um=wl)
        r_exo = session_exo.run(_params(session_exo, h_tgt_m=101_000.0))
        session_surf = RadiantSession(wavelength_um=wl)
        r_surf = session_surf.run(_params(session_surf, h_tgt_m=0.0))

    q_exo = r_exo.stage_outputs["atmosphere"]["atm_quantities"]
    q_surf = r_surf.stage_outputs["atmosphere"]["atm_quantities"]
    np.testing.assert_array_equal(q_exo.tau_full_up, q_surf.tau_full_up)
    np.testing.assert_array_equal(q_exo.L_path_full, q_surf.L_path_full)
