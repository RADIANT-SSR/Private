"""The shipped up-looking library reaches a chain result (CU-226).

Before this landing ``atmosphere.model='interpolated'`` on an up-looking scene
resolved and loaded ``midlat_summer_uplooking_ladder/`` and then raised a
capability error at ``AtmosphereStage`` — the data was queryable but not
reachable, so the shipped MODTRAN runs changed no computed result.

What is pinned here:

* the chain completes and its observer leg carries the **library's** τ and
  downwelling radiance, not the parametric model's;
* the illumination leg is *bit-identical* to a pure-``simple`` run of the same
  scene, which is the measurable statement of the hybrid: only the observer leg
  moved;
* the model split is declared (``UserWarning``) and recorded in provenance;
* a down-looking interpolated scene is untouched.

Values are compared against the run family's own NPZ, so the anchor is the
MODTRAN output itself rather than another RADIANT computation (Rule: tests use
known-good values, not values computed by other RADIANT code).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.api.sensor import Sensor
from radiant.atmosphere.interpolated import TAU_FLOOR

_CONFIG = Path(__file__).resolve().parents[2] / "examples" / "mwir_leo_minimal.yaml"
_LIB = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "radiant"
    / "data"
    / "tables"
    / "atmospheres"
    / "midlat_summer_uplooking_ladder"
)

# The 10 km rung — a node of the ladder, so the interpolator returns it exactly.
_NODE_M = 10_000.0
_NODE_NPZ = _LIB / "t010.npz"


def _run(model: str, h_tgt_m: float = _NODE_M):
    """Evaluate the shipped MWIR example as a ground sensor looking straight up."""
    sensor = (
        Sensor.load(_CONFIG)
        .set("geometry.sensor_altitude_m", 0.0)
        .set("geometry.target_altitude_m", h_tgt_m)
        .set("atmosphere.model", model)
    )
    if model == "interpolated":
        sensor = sensor.set("atmosphere.interpolation_axes", "target_altitude_m")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = sensor.evaluate()
    return result, [str(w.message) for w in caught]


@pytest.fixture(scope="module")
def interpolated():  # type: ignore[no-untyped-def]
    return _run("interpolated")


@pytest.fixture(scope="module")
def simple():  # type: ignore[no-untyped-def]
    return _run("simple")


class TestChainReachesTheLibrary:
    def test_chain_completes(self, interpolated) -> None:  # type: ignore[no-untyped-def]
        """The capability error CU-226 reported is gone."""
        result, _ = interpolated
        assert result.metrics.get("snr") is not None

    def test_observer_leg_is_the_library_column(self, interpolated) -> None:  # type: ignore[no-untyped-def]
        """τ_up and L_path_up equal the t010 MODTRAN run, resampled to the chain grid."""
        result, _ = interpolated
        q = result.stage_outputs["atmosphere"]["atm_quantities"]
        lam = np.asarray(q.wavelength_um, dtype=np.float64)
        with np.load(_NODE_NPZ, allow_pickle=True) as data:
            wl_n = np.asarray(data["wavelength_um"], dtype=np.float64)
            tau_n = np.asarray(data["transmittance"], dtype=np.float64)
            l_n = np.asarray(data["path_radiance_toward_lower"], dtype=np.float64)
        # CU-306: τ is carried onto the chain grid in **log-τ** — the same
        # optical-depth space the geometry interpolation runs in — so the
        # anchor is the log-space resample of the node column, not the
        # linear-in-τ one. Radiance is not Beer-Lambert and stays linear.
        tau_expected = np.exp(np.interp(lam, wl_n, np.log(np.clip(tau_n, TAU_FLOOR, 1.0))))
        assert np.asarray(q.tau_up) == pytest.approx(tau_expected, abs=1e-12)
        assert np.asarray(q.L_path_up) == pytest.approx(np.interp(lam, wl_n, l_n), abs=1e-12)

    def test_it_differs_from_the_parametric_model(self, interpolated, simple) -> None:  # type: ignore[no-untyped-def]
        """The whole point: the library changes the answer it is supposed to change."""
        tau_i = np.asarray(interpolated[0].stage_outputs["atmosphere"]["atm_quantities"].tau_up)
        tau_s = np.asarray(simple[0].stage_outputs["atmosphere"]["atm_quantities"].tau_up)
        assert not np.allclose(tau_i, tau_s, atol=1e-6)

    def test_illumination_leg_is_the_companion_unchanged(self, interpolated, simple) -> None:  # type: ignore[no-untyped-def]
        """Only the observer leg moved — the companion serves the rest bit-identically."""
        q_i = interpolated[0].stage_outputs["atmosphere"]["atm_quantities"]
        q_s = simple[0].stage_outputs["atmosphere"]["atm_quantities"]
        for field in ("tau_sun", "E_TOA", "E_sky_scattered", "E_sky_thermal"):
            np.testing.assert_array_equal(
                np.asarray(getattr(q_i, field)), np.asarray(getattr(q_s, field))
            )


class TestTheSplitIsDeclared:
    def test_user_warning_names_both_models(self, interpolated) -> None:  # type: ignore[no-untyped-def]
        _, messages = interpolated
        assert any("TWO atmosphere models" in m for m in messages)

    def test_provenance_records_the_split(self, interpolated) -> None:  # type: ignore[no-untyped-def]
        result, _ = interpolated
        split = result.stage_outputs["atmosphere"]["topology_provenance"]["backend_split"]
        assert "InterpolatedAtmosphere" in split and "companion" in split

    def test_simple_run_declares_one_model(self, simple) -> None:  # type: ignore[no-untyped-def]
        result, messages = simple
        assert result.stage_outputs["atmosphere"]["topology_provenance"]["backend_split"] == (
            "all legs: SimpleAtmosphere"
        )
        assert not any("TWO atmosphere models" in m for m in messages)


class TestGroundToSpaceReachesTheFullColumnFamily:
    """The capability the batch-2 M block shipped for (CU-224 checklist, ex-CU-308).

    ``midlat_summer_sst_column_fan`` is a ground observer's *whole* column,
    ground → the 100 km atmosphere top. It was built for ground-to-SPACE
    scenes — targets at 400 km and beyond — and until now the up-looking
    topology refused every one of them, because a library-backed observer leg
    with ``h_tgt ≥ h_atm_top`` was refused outright.

    The refusal now asks the family how far up it measured. This one measured
    the entire column, so the remaining path to the target is vacuum and the
    composed observer leg is *identically* the family's own top-of-column run —
    which is what the second test here checks against the delivered M1 tape7's
    stored τ, not against another RADIANT computation.
    """

    _FAN_DIR = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "radiant"
        / "data"
        / "tables"
        / "atmospheres"
        / "midlat_summer_sst_column_fan"
    )
    #: The M1 run — vertical, ground → 100 km. The fan's ζ = 0 node.
    _M1_NPZ = _FAN_DIR / "z00.000.npz"
    _EXO_TARGET_M = 400_000.0

    @pytest.fixture(scope="class")
    def exo(self):  # type: ignore[no-untyped-def]
        """A ground sensor looking straight up at a 400 km target."""
        sensor = (
            Sensor.load(_CONFIG)
            .set("geometry.sensor_altitude_m", 0.0)
            .set("geometry.target_altitude_m", self._EXO_TARGET_M)
            .set("atmosphere.model", "interpolated")
            .set("atmosphere.interpolation_axes", "path_zenith_rad")
            .set("atmosphere.interpolated_data_dir", str(self._FAN_DIR))
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = sensor.evaluate()
        return result, [str(w.message) for w in caught]

    def test_the_chain_completes_with_finite_products(self, exo) -> None:  # type: ignore[no-untyped-def]
        result, _ = exo
        assert result.metrics.get("snr") is not None
        q = result.stage_outputs["atmosphere"]["atm_quantities"]
        for field in ("tau_up", "tau_full_up", "L_path_up", "L_path_full", "E_TOA"):
            values = np.asarray(getattr(q, field))
            assert np.all(np.isfinite(values)), field

    def test_the_illumination_is_the_exo_vacuum_identity(self, exo) -> None:  # type: ignore[no-untyped-def]
        """Above the atmosphere there is no column over the target: τ_sun ≡ 1, E_sky ≡ 0."""
        q = exo[0].stage_outputs["atmosphere"]["atm_quantities"]
        np.testing.assert_array_equal(np.asarray(q.tau_sun), np.ones_like(q.wavelength_um))
        np.testing.assert_array_equal(np.asarray(q.E_sky_scattered), np.zeros_like(q.wavelength_um))
        np.testing.assert_array_equal(np.asarray(q.E_sky_thermal), np.zeros_like(q.wavelength_um))

    def test_the_observer_leg_is_the_m1_full_column_run(self, exo) -> None:  # type: ignore[no-untyped-def]
        """The measured anchor: the composed answer IS the delivered M1 column.

        Nothing in the composition interpolates *toward* the exo target and
        nothing extrapolates past the fan's top: the vacuum identity says the
        answer is the ζ = 0 node itself, carried onto the chain grid in log-τ
        (CU-306's convention, the same space the geometry interpolation uses).
        """
        q = exo[0].stage_outputs["atmosphere"]["atm_quantities"]
        lam = np.asarray(q.wavelength_um, dtype=np.float64)
        with np.load(self._M1_NPZ, allow_pickle=True) as data:
            wl_n = np.asarray(data["wavelength_um"], dtype=np.float64)
            tau_n = np.asarray(data["transmittance"], dtype=np.float64)
            l_n = np.asarray(data["path_radiance_toward_lower"], dtype=np.float64)
        tau_expected = np.exp(np.interp(lam, wl_n, np.log(np.clip(tau_n, TAU_FLOOR, 1.0))))
        assert np.asarray(q.tau_up) == pytest.approx(tau_expected, abs=1e-12)
        assert np.asarray(q.L_path_up) == pytest.approx(np.interp(lam, wl_n, l_n), abs=1e-12)

    def test_the_split_and_the_clamp_are_both_declared(self, exo) -> None:  # type: ignore[no-untyped-def]
        """Rule 16 / the CU-224 ratification condition: both are inspectable."""
        result, messages = exo
        topology = result.stage_outputs["atmosphere"]["topology_provenance"]
        assert "InterpolatedAtmosphere" in topology["backend_split"]
        assert "companion" in topology["backend_split"]
        assert any("TWO atmosphere models" in m for m in messages)
        segment = topology["observer_segment_provenance"]
        assert segment["target_ceiling_m"] == pytest.approx(100_000.0, abs=0.0)
        assert segment["target_altitude_served_m"] == pytest.approx(100_000.0, abs=0.0)
        assert "vacuum" in segment["exo_target_vacuum_clamp"]

    def test_the_partial_column_ladder_still_refuses_the_same_scene(self) -> None:
        """Same scene, a family that stops at 20 km: refused, not clamped."""
        from radiant.core.parameters import ParameterBoundsError

        sensor = (
            Sensor.load(_CONFIG)
            .set("geometry.sensor_altitude_m", 0.0)
            .set("geometry.target_altitude_m", self._EXO_TARGET_M)
            .set("atmosphere.model", "interpolated")
            .set("atmosphere.interpolation_axes", "target_altitude_m")
        )
        with (
            warnings.catch_warnings(),
            pytest.raises(ParameterBoundsError, match="at or above h_atm_top"),
        ):
            warnings.simplefilter("ignore")
            sensor.evaluate()


class TestDownLookingUntouched:
    def test_down_looking_interpolated_takes_no_companion(self) -> None:
        """A down-looking family must not acquire a second backend (zero drift)."""
        from radiant.atmosphere.loaders import build_atmosphere_model

        sensor = (
            Sensor.load(_CONFIG)
            .set("geometry.sensor_altitude_m", 500_000.0)
            .set("geometry.target_altitude_m", 0.0)
            .set("atmosphere.model", "interpolated")
            .set("atmosphere.interpolation_axes", "sensor_altitude_m")
        )
        sensor.resolve()
        model = build_atmosphere_model(sensor._params)
        assert model.family_direction == "down"
        assert model.uplooking_companion is None
