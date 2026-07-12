"""Stage 7 (Option C) full-chain integration for the three no_atmosphere sub-cases.

Exercises one representative cell from each sub-case — per matrix §3.3
and the Option C implementation plan:

* **D-58** — LWIR extended space scene (vacuum path, ColdSpaceBackground).
  The legacy ``atmosphere.model = "exo"`` surface already routes here,
  so this cell runs via the full ``RadiantSession`` chain.

* **D-ground G13** — LWIR extended ground-test scene with a
  :class:`UserSpectralBackground`.  The legacy parameter surface has no
  scalar L_bg channel, so the SourceStage inferrer raises (by design —
  matrix §7 + ADR-0002 Decision #15).  This cell runs through a
  descriptor-driven harness that seeds the ``source`` stage-output keys
  directly, then drives AtmosphereStage → PerformanceStage as the full
  downstream chain.  This exercises the Option C landing path that the
  SensorDescriptor follow-on will formalise.

* **D-lab L13** — LWIR dark-cal blackbody-standard scene (no
  illumination).  Same descriptor-driven harness as G13; the
  lab_test regime differs only in the background radiance and target
  emissivity.

Each integration test checks:
  - at_aperture radiance is finite and positive on the full grid.
  - target radiance matches ε · B(T_t) (vacuum / no transport) to ~1%.
  - SNR is finite and positive (the chain ran to completion).
  - The validator *does* raise when the sub-case preconditions are
    violated (matrix §7), proving the guard wired through AtmosphereStage.
"""

from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.api.session import RadiantSession
from radiant.atmosphere.stage import AtmosphereStage
from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.chain import ChainRunner, ChainState
from radiant.core.descriptors import (
    T1Thermal,
    UserSpectralBackground,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.regime import RadiometricRegime
from radiant.core.spectral import SpectralData
from radiant.detector.stage import DetectorStage
from radiant.optics.stage import OpticsStage
from radiant.performance.stage import PerformanceStage
from radiant.platform.stage import PlatformStage
from radiant.readout.stage import ReadoutStage
from radiant.spectral_integration.stage import SpectralIntegrationStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


LWIR_WL = np.linspace(8.0, 13.0, 501)


def _grey_sd(wl: np.ndarray, value: float, name: str = "eps") -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=wl,
        values=np.full_like(wl, value),
        unit="",
        source="test",
    )


def _user_lbg(wl: np.ndarray, L_value: float) -> UserSpectralBackground:
    return UserSpectralBackground(
        L_bg=SpectralData(
            name="test.user_L_bg",
            wavelength_um=wl,
            values=np.full_like(wl, L_value),
            unit="W/m²/sr/µm",
            source="test",
        )
    )


class _InjectedSource:
    """Stand-in SourceStage that injects pre-built descriptors into
    ``stage_outputs["source"]`` instead of running the legacy inferrer.

    Used to exercise the ground_test / lab_test sub-cases, whose legacy
    parameter surface has no L_bg channel (the inferrer raises by
    design — matrix §7).  The shape and keys mirror SourceStage so every
    downstream stage (AtmosphereStage onward) is unchanged.
    """

    def __init__(
        self,
        target: T1Thermal,
        background: UserSpectralBackground | None,
        los: LineOfSightGeometry,
        regime_tentative: RadiometricRegime = RadiometricRegime.EXTENDED,
        angular_extent_rad: float = float("inf"),
    ) -> None:
        self._target = target
        self._background = background
        self._los = los
        self._regime = regime_tentative
        self._angular = angular_extent_rad

    @property
    def name(self) -> str:
        return "source"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        state = state.with_stage_output("source", "regime_tentative", self._regime)
        state = state.with_stage_output("source", "projected_area_m2", 0.0)
        state = state.with_stage_output("source", "range_m", 0.0)
        state = state.with_stage_output("source", "fill_fraction", 1.0)
        state = state.with_stage_output("source", "angular_extent_rad", self._angular)
        state = state.with_stage_output("source", "regime_override", "auto")
        state = state.with_stage_output("source", "target", self._target)
        state = state.with_stage_output("source", "background", self._background)
        return state.with_stage_output("source", "los_geometry", self._los)


def _seed_optics_detector_readout(params: ParameterSet) -> None:
    """Seed a minimal LWIR imaging system for the integration scenarios."""
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.45)
    params.set("optics.transmission_scalar", 0.62)
    params.set("detector.pixel_pitch_x_um", 20.0)
    params.set("detector.pixel_pitch_y_um", 20.0)
    params.set("detector.qe_value", 0.55)
    params.set("detector.dark_rate_e_per_s", 800.0)
    params.set("spectral_integration.filter_min_um", 8.0)
    params.set("spectral_integration.filter_max_um", 13.0)
    params.set("spectral_integration.integration_time_s", 0.010)
    params.set("readout.read_noise_e_rms", 12.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)


def _run_injected_chain(
    target: T1Thermal,
    background: UserSpectralBackground | None,
    los: LineOfSightGeometry,
    params: ParameterSet,
) -> ChainState:
    """Run a chain with a custom ``_InjectedSource`` in place of SourceStage."""
    runner = ChainRunner([
        _InjectedSource(target, background, los),
        AtmosphereStage(),
        OpticsStage(),
        PlatformStage(),
        SpectralIntegrationStage(),
        DetectorStage(),
        ReadoutStage(),
        PerformanceStage(),
    ])
    return runner.run(params, LWIR_WL)


# ---------------------------------------------------------------------------
# D-58 — LWIR space extended (full RadiantSession chain)
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestD58LWIRSpaceExtended:
    """Full-chain integration for the Table D-58 space sub-case.

    The Cell 58 anchor test pins the *exact* SNR / NEDT / L_aperture
    values; this test is the looser regression: the chain runs, the
    metrics are finite and sensible, the target arm agrees with
    ε·B(T_t) (vacuum transport).
    """

    def test_runs_to_completion_and_produces_sane_metrics(self) -> None:
        session = RadiantSession(wavelength_um=LWIR_WL)
        params = session.default_params()
        params.set("source.target.temperature", 285.0)
        params.set("source.target.emissivity", 0.98)
        params.set("atmosphere.model", "exo")
        params.set("geometry.sensor_altitude_m", 800_000.0)
        _seed_optics_detector_readout(params)
        params.resolve()

        result = session.run(params)

        # SNR + NEDT finite and positive.
        assert math.isfinite(result.metrics["snr"])
        assert result.metrics["snr"] > 0.0
        assert math.isfinite(result.metrics["nedt_K"])
        assert result.metrics["nedt_K"] > 0.0

        # At-aperture target radiance is strictly positive (ε·B(T>0)).
        L = result.frames["at_aperture"].spectral_radiance
        assert np.all(np.isfinite(L))
        assert np.all(L > 0.0)

        # Vacuum transport: L_aperture ≈ ε · B(T_t).  Pick λ = 10 µm.
        idx10 = int(np.argmin(np.abs(LWIR_WL - 10.0)))
        L_expected = 0.98 * planck_spectral_radiance(np.array([10.0]), 285.0)[0]
        assert L[idx10] == pytest.approx(L_expected, rel=5e-3)

    def test_space_subcase_single_altitude_suffices(self) -> None:
        """CU-090/ADR-0006: one user-set geometry.sensor_altitude_m is all the
        space sub-case needs — the old failure mode (forgetting the separate
        platform.h_sensor stop-gap while the altitude was set) is structurally
        impossible now that h_sensor is a deprecated alias of the canonical
        altitude.  The positive/user-set guard itself stays covered by the
        assembly unit tests and test_sensor_below_space_target_raises."""
        session = RadiantSession(wavelength_um=LWIR_WL)
        params = session.default_params()
        params.set("source.target.temperature", 285.0)
        params.set("source.target.emissivity", 0.98)
        params.set("atmosphere.model", "exo")
        params.set("geometry.sensor_altitude_m", 800_000.0)
        # NOTE: no separate h_sensor — the canonical altitude feeds the
        # Earth-limb precondition check directly.
        _seed_optics_detector_readout(params)
        params.resolve()

        result = session.run(params)
        assert np.all(np.isfinite(result.frames["at_aperture_target"].spectral_radiance))


# ---------------------------------------------------------------------------
# D-ground G13 — LWIR extended ground-test
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestG13LWIRGroundTestExtended:
    """Full downstream-chain integration for Table D-ground G13.

    Uses ``_InjectedSource`` to bypass the legacy inferrer (which raises
    by design for ground_test without a L_bg channel).  Everything from
    AtmosphereStage onward is the real chain.
    """

    def test_runs_to_completion_and_produces_sane_metrics(self) -> None:
        T_t = 320.0
        eps_value = 0.96
        L_bg_value = 1.2  # W/m²/sr/µm — test-range background

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="ground_test",
                h_tgt=0.0,
                epsilon=_grey_sd(LWIR_WL, eps_value),
                T_t=T_t,
            )
        background = _user_lbg(LWIR_WL, L_bg_value)
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)

        params = build_parameter_set()
        # These source.* values are unused by the injected source but still
        # required by the schema (so params.resolve() completes).
        params.set("source.target.temperature", T_t)
        params.set("source.target.emissivity", eps_value)
        params.set("atmosphere.model", "exo")
        params.set("geometry.sensor_altitude_m", 0.0)  # on test range
        _seed_optics_detector_readout(params)
        params.resolve()

        state = _run_injected_chain(target, background, los, params)

        # Vacuum transport: target arm equals ε·B(T_t).
        L_t = state.frames["at_aperture_target"].spectral_radiance
        assert np.all(np.isfinite(L_t))
        assert np.all(L_t > 0.0)
        idx10 = int(np.argmin(np.abs(LWIR_WL - 10.0)))
        L_expected = eps_value * planck_spectral_radiance(np.array([10.0]), T_t)[0]
        assert L_t[idx10] == pytest.approx(L_expected, rel=5e-3)

        # Background frame equals the user-supplied spectrum bit-for-bit
        # (no transport in ExoAtmosphere).
        L_bg_frame = state.frames["at_aperture_background"].spectral_radiance
        np.testing.assert_allclose(L_bg_frame, L_bg_value, atol=1e-12)

        # PerformanceStage produced finite SNR/NEDT.
        snr = state.metrics["snr"]
        assert math.isfinite(snr) and snr > 0.0
        nedt = state.metrics["nedt_K"]
        assert math.isfinite(nedt) and nedt > 0.0

    def test_ground_test_without_user_background_raises(self) -> None:
        """Matrix §7: ground_test + background=None at AtmosphereStage."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="ground_test",
                h_tgt=0.0,
                epsilon=_grey_sd(LWIR_WL, 0.96),
                T_t=320.0,
            )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)

        params = build_parameter_set()
        params.set("source.target.temperature", 320.0)
        params.set("source.target.emissivity", 0.96)
        params.set("atmosphere.model", "exo")
        params.set("geometry.sensor_altitude_m", 0.0)
        _seed_optics_detector_readout(params)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="UserSpectralBackground"):
            _run_injected_chain(target, background=None, los=los, params=params)


# ---------------------------------------------------------------------------
# D-lab L13 — LWIR dark-cal blackbody-standard
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestL13LWIRLabDarkCalBlackbody:
    """Full downstream-chain integration for Table D-lab L13.

    L13 is a dark-cal scenario: blackbody-standard target (ε ≈ 1) in a
    thermally-controlled chamber, no illumination.  Differs from G13
    only in the sub-case tag, target emissivity, and the chamber
    background radiance.
    """

    def test_runs_to_completion_and_produces_sane_metrics(self) -> None:
        T_t = 310.0            # calibration blackbody
        eps_value = 0.999      # near-perfect emitter
        L_bg_value = 0.3       # chamber wall radiance

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="lab_test",
                h_tgt=0.0,
                epsilon=_grey_sd(LWIR_WL, eps_value),
                T_t=T_t,
            )
        background = _user_lbg(LWIR_WL, L_bg_value)
        # Dark-cal: no illumination (no θ_s).
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=None, delta_phi=None)

        params = build_parameter_set()
        params.set("source.target.temperature", T_t)
        params.set("source.target.emissivity", eps_value)
        params.set("atmosphere.model", "exo")
        params.set("geometry.sensor_altitude_m", 0.0)  # in the lab
        _seed_optics_detector_readout(params)
        params.resolve()

        state = _run_injected_chain(target, background, los, params)

        # Vacuum transport: target arm equals ε·B(T_t).
        L_t = state.frames["at_aperture_target"].spectral_radiance
        assert np.all(np.isfinite(L_t))
        assert np.all(L_t > 0.0)
        idx10 = int(np.argmin(np.abs(LWIR_WL - 10.0)))
        L_expected = eps_value * planck_spectral_radiance(np.array([10.0]), T_t)[0]
        assert L_t[idx10] == pytest.approx(L_expected, rel=5e-3)

        # Background frame equals the user-supplied spectrum bit-for-bit.
        L_bg_frame = state.frames["at_aperture_background"].spectral_radiance
        np.testing.assert_allclose(L_bg_frame, L_bg_value, atol=1e-12)

        # Chain ran to completion — finite SNR/NEDT.
        snr = state.metrics["snr"]
        assert math.isfinite(snr) and snr > 0.0
        nedt = state.metrics["nedt_K"]
        assert math.isfinite(nedt) and nedt > 0.0

    def test_lab_test_without_user_background_raises(self) -> None:
        """Matrix §7: lab_test + background=None at AtmosphereStage."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="lab_test",
                h_tgt=0.0,
                epsilon=_grey_sd(LWIR_WL, 0.999),
                T_t=310.0,
            )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)

        params = build_parameter_set()
        params.set("source.target.temperature", 310.0)
        params.set("source.target.emissivity", 0.999)
        params.set("atmosphere.model", "exo")
        params.set("geometry.sensor_altitude_m", 0.0)
        _seed_optics_detector_readout(params)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="UserSpectralBackground"):
            _run_injected_chain(target, background=None, los=los, params=params)
