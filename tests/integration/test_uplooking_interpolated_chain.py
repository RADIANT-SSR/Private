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
        assert np.asarray(q.tau_up) == pytest.approx(np.interp(lam, wl_n, tau_n), abs=1e-12)
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
