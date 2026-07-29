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
        for a, b in zip(sorted_h, sorted_h[1:], strict=False):
            assert tau_up_by_h[b] >= tau_up_by_h[a] - 1e-12, (
                f"τ_up not monotonic: h={a} m → {tau_up_by_h[a]}, h={b} m → {tau_up_by_h[b]}"
            )

        assert tau_up_by_h[29000.0] > tau_up_by_h[1000.0], (
            "τ_up(29 km) should exceed τ_up(1 km) at 10 µm"
        )


# ---------------------------------------------------------------------------
# MODTRAN-pinned assertions (Gap 39 — MODTRAN_Run_Matrix_Plan §8)
# ---------------------------------------------------------------------------

# Band-mean τ_up(h_tgt) extracted 2026-07-17 from the real MODTRAN 6
# C-ladder (midlat_summer, sensor 35 km, nadir — the exact Cell 43
# geometry): runs C2–C6 of docs/plans/modtran_run_matrix.csv, parsed via
# Tape7Reader.to_radiant_units(), arithmetic mean of total transmittance
# over the stated wavelength window. These constants are committed
# goldens; the generating tape7s live gitignored in modtran/real_runs/
# (a skipif-guarded consistency test in test_modtran_real_runs.py
# re-derives them from the files where present).
#
# h_tgt [m] -> (tau_mean 8–13 µm, tau_mean 10–12 µm window)
MODTRAN_C_LADDER_TAU: dict[float, tuple[float, float]] = {
    1000.0: (0.694822, 0.803384),
    5000.0: (0.891342, 0.977861),
    10000.0: (0.925255, 0.990453),
    20000.0: (0.951597, 0.994288),
    29000.0: (0.981652, 0.998192),
}


@pytest.mark.level2
class TestTableCModtranPinned:
    """Gap 39: A3 partial-column τ_up pinned against real MODTRAN.

    Characterization (re-measured 2026-07-18 after the CU-161 gas-band
    recalibration): the pre-CU-161 model was consistently *optimistic*
    (up to +0.12 band-mean τ at h_tgt = 1 km, saturating at τ = 1.000
    by 20 km with no stratospheric absorbers). The calibrated model —
    well-mixed gas floor on the molecular scale height + curve-of-growth
    water — is 3–5× tighter and two-sided: Δτ(8–13 µm) ∈ [−0.026, +0.031]
    across the ladder, Δτ(10–12 µm window) ∈ [−0.009, +0.006]. The
    remaining structure is the partial-column scaling approximation
    (region-mean b applied to the traversed column fraction), not a
    missing species.
    """

    def test_modtran_reference_monotonic(self) -> None:
        """Sanity on the pinned constants: τ_up rises with h_tgt in both
        windows (less atmosphere above the target)."""
        hs = sorted(MODTRAN_C_LADDER_TAU)
        for lo_h, hi_h in zip(hs, hs[1:], strict=False):
            assert MODTRAN_C_LADDER_TAU[hi_h][0] > MODTRAN_C_LADDER_TAU[lo_h][0]
            assert MODTRAN_C_LADDER_TAU[hi_h][1] > MODTRAN_C_LADDER_TAU[lo_h][1]

    @pytest.mark.parametrize("h_tgt_m", TABLE_C_ALTITUDES_M)
    def test_tau_up_parity_with_modtran(self, airborne_results, h_tgt_m: float) -> None:
        """Chain τ_up (simple A3 partial column) vs the MODTRAN golden.

        Asserts the characterized envelope (CU-161 model, 2026-07-18):
        simple minus MODTRAN in [-0.04, +0.05] for the 8–13 µm band mean
        and [-0.02, +0.02] for the 10–12 µm window mean — the measured
        worst cases (−0.026/+0.031 band, −0.009/+0.006 window) with
        margin. Pre-CU-161 the envelope was one-sided and 3–5× wider
        ([-0.01, +0.13] / [-0.01, +0.09]); a regression past these
        bounds means the water/gas calibration drifted — update bounds
        only with a model change (same PR, Rule 20/29).
        """
        atm_q = airborne_results[h_tgt_m].stage_outputs["atmosphere"]["atm_quantities"]
        tau_up = np.asarray(atm_q.tau_up, dtype=np.float64)

        band_813 = float(tau_up.mean())  # LWIR_WL spans exactly 8–13 µm
        window = (LWIR_WL >= 10.0) & (LWIR_WL <= 12.0)
        band_1012 = float(tau_up[window].mean())

        ref_813, ref_1012 = MODTRAN_C_LADDER_TAU[h_tgt_m]
        d813 = band_813 - ref_813
        d1012 = band_1012 - ref_1012

        assert -0.04 <= d813 <= 0.05, (
            f"h={h_tgt_m} m: simple−MODTRAN τ (8–13 µm) = {d813:+.4f} outside "
            "the Gap-39/CU-161 characterized envelope [-0.04, +0.05]"
        )
        assert -0.02 <= d1012 <= 0.02, (
            f"h={h_tgt_m} m: simple−MODTRAN τ (10–12 µm) = {d1012:+.4f} outside "
            "the Gap-39/CU-161 characterized envelope [-0.02, +0.02]"
        )
