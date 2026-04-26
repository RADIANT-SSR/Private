"""Table C smoke tests — airborne scenarios (1 km ≲ h_tgt ≲ 30 km).

These integration tests verify that Stage 5 A3 partial-column atmosphere
flows end-to-end through the full RADIANT chain for airborne targets.
They cover Cell 43 (LWIR extended, thermal graybody) of
``docs/RADIANT_Use_Case_Matrix.md`` Table C at five target altitudes
between 1 km and 29 km.

Each test is a smoke test — the chain must run to completion, produce a
finite SNR, and show the physics-required monotonicity: τ_up(h_tgt) rises
as h_tgt increases (less atmosphere above the target → less absorption
→ higher up-leg transmission).

Reference: ``docs/Option_C_Implementation_Plan.md`` Stage 5.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.api.session import RadiantSession


LWIR_WL = np.linspace(8.0, 13.0, 501)


def _run_airborne_lwir_extended(h_tgt_m: float):
    """Run the Cell 43 airborne LWIR extended scenario at target altitude ``h_tgt_m``."""
    session = RadiantSession(wavelength_um=LWIR_WL)
    params = session.default_params()

    # Target: 290 K blackbody-ish, ε=0.95 (airborne thermal signature).
    params.set("source.target.temperature", 290.0)
    params.set("source.target.emissivity", 0.95)

    # Atmosphere: midlat summer simple backend (A3 partial column for h_tgt > 0).
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")

    # Target location axis: airborne (h_tgt > 0).
    params.set("geometry.target_altitude_m", h_tgt_m)
    # Sensor at 35 km (high-altitude recon above the full column).
    params.set("geometry.sensor_altitude_m", 35000.0)

    # Optics: 0.10 m aperture, f/2.5.
    params.set("optics.aperture_diameter_m", 0.10)
    params.set("optics.focal_length_m", 0.25)
    params.set("optics.transmission_scalar", 0.60)

    # Detector: 17 µm pitch, QE 0.55.
    params.set("detector.pixel_pitch_x_um", 17.0)
    params.set("detector.pixel_pitch_y_um", 17.0)
    params.set("detector.qe_value", 0.55)
    params.set("detector.dark_rate_e_per_s", 1000.0)

    # Spectral: LWIR 8–13 µm, 15 ms integration.
    params.set("spectral_integration.filter_min_um", 8.0)
    params.set("spectral_integration.filter_max_um", 13.0)
    params.set("spectral_integration.integration_time_s", 0.015)

    # Readout: 20 e- RMS read noise, 14-bit ADC, 2 e-/DN.
    params.set("readout.read_noise_e_rms", 20.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)

    params.resolve()
    return session.run(params)


# Five altitudes spanning the Table C band.
TABLE_C_ALTITUDES_M = (1000.0, 5000.0, 10000.0, 20000.0, 29000.0)


@pytest.fixture(scope="module")
def airborne_results() -> dict[float, object]:
    """Run Cell 43 LWIR extended at each Table C target altitude."""
    return {h: _run_airborne_lwir_extended(h) for h in TABLE_C_ALTITUDES_M}


@pytest.mark.level2
class TestTableCAirborneLWIRExtended:
    """Stage 5 A3 smoke tests — Cell 43 at five airborne altitudes."""

    @pytest.mark.parametrize("h_tgt_m", TABLE_C_ALTITUDES_M)
    def test_chain_runs_to_completion(self, airborne_results, h_tgt_m: float) -> None:
        result = airborne_results[h_tgt_m]
        assert result is not None, f"chain returned None at h_tgt={h_tgt_m} m"
        assert "snr" in result.metrics
        assert "nedt_K" in result.metrics

    @pytest.mark.parametrize("h_tgt_m", TABLE_C_ALTITUDES_M)
    def test_snr_finite_and_positive(self, airborne_results, h_tgt_m: float) -> None:
        snr = float(airborne_results[h_tgt_m].metrics["snr"])
        assert math.isfinite(snr), f"non-finite SNR at h_tgt={h_tgt_m} m: {snr}"
        assert snr > 0.0, f"non-positive SNR at h_tgt={h_tgt_m} m: {snr}"

    @pytest.mark.parametrize("h_tgt_m", TABLE_C_ALTITUDES_M)
    def test_nedt_finite_and_positive(self, airborne_results, h_tgt_m: float) -> None:
        nedt = float(airborne_results[h_tgt_m].metrics["nedt_K"])
        assert math.isfinite(nedt), f"non-finite NEDT at h_tgt={h_tgt_m} m: {nedt}"
        assert nedt > 0.0, f"non-positive NEDT at h_tgt={h_tgt_m} m: {nedt}"

    @pytest.mark.parametrize("h_tgt_m", TABLE_C_ALTITUDES_M)
    def test_L_aperture_finite(self, airborne_results, h_tgt_m: float) -> None:
        L = airborne_results[h_tgt_m].frames["at_aperture"].spectral_radiance
        assert np.all(np.isfinite(L)), f"non-finite L_aperture at h_tgt={h_tgt_m} m"
        assert np.all(L >= 0.0), f"negative L_aperture at h_tgt={h_tgt_m} m"

    def test_tau_up_monotonic_in_h_tgt(self, airborne_results) -> None:
        """τ_up must rise as h_tgt rises — less atmosphere above target → less absorption.

        This is the core A3 physics check: at h_tgt=29 km the column above the
        target is nearly vacuum, so τ_up should be much closer to 1 than at
        h_tgt=1 km. A mid-band wavelength (10 µm) is used to land well inside
        the LWIR atmospheric window.
        """
        idx_10um = int(np.argmin(np.abs(LWIR_WL - 10.0)))
        tau_up_by_h: dict[float, float] = {}
        for h in TABLE_C_ALTITUDES_M:
            atm_q = airborne_results[h].stage_outputs["atmosphere"]["atm_quantities"]
            tau_up_by_h[h] = float(atm_q.tau_up[idx_10um])

        sorted_h = sorted(TABLE_C_ALTITUDES_M)
        for a, b in zip(sorted_h, sorted_h[1:]):
            assert tau_up_by_h[b] >= tau_up_by_h[a] - 1e-12, (
                f"τ_up not monotonic: h={a} m → {tau_up_by_h[a]}, "
                f"h={b} m → {tau_up_by_h[b]}"
            )

        assert tau_up_by_h[29000.0] > tau_up_by_h[1000.0], (
            "τ_up(29 km) should exceed τ_up(1 km) at 10 µm"
        )
