"""A smear wider than the PSF grid must clamp, not crash (CU-235).

``PlatformStage`` forced each kernel size odd and *then* clamped it to the PSF
grid, which is 1024 samples — even. Any degradation wide enough to reach the
clamp therefore came back out even, and the kernel builder rejected it with
``npix must be a positive odd integer, got 1024``, aborting the whole chain
evaluation. The clamp existed precisely to make an over-wide smear survivable,
so it was the guard itself that crashed.

Reachable from ordinary inputs: a 7000 m/s LEO ground-track speed at the shipped
5 ms integration time gives a 5250 µm smear against a 2176.8 µm half-grid.

:mod:`radiant.platform.tests.test_kernel_size` pins the size arithmetic. This
pins the behaviour that matters: the chain completes, and the caller is told
that the truncation costs it dual-path agreement.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from radiant.api.sensor import Sensor

_CONFIG = Path(__file__).resolve().parents[2] / "examples" / "mwir_leo_minimal.yaml"

# Fast enough that the smear exceeds the PSF grid extent at the shipped 5 ms
# integration time — a plausible LEO ground-track speed, not a pathological one.
_WIDE_SMEAR_VELOCITY_M_S = 7000.0


def _evaluate(velocity_m_s: float):  # type: ignore[no-untyped-def]
    sensor = Sensor.load(_CONFIG).set("platform.ground_velocity_m_s", velocity_m_s)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


class TestWideSmearCompletes:
    def test_chain_does_not_raise(self) -> None:
        """The evaluation that used to abort on an even kernel size now returns."""
        assert _evaluate(_WIDE_SMEAR_VELOCITY_M_S) is not None

    def test_smear_kernel_is_odd_and_fits_the_grid(self) -> None:
        result = _evaluate(_WIDE_SMEAR_VELOCITY_M_S)
        psf = result.stage_outputs["platform"]["effective_psf"]
        kernel = dict(psf.kernels)["smear"]
        size = kernel.shape[0]
        assert size % 2 == 1, "a truncated kernel must still have a centre sample"
        assert size <= psf.data.shape[0], "the kernel must fit the array it pads into"

    def test_radiometry_still_computed(self) -> None:
        assert _evaluate(_WIDE_SMEAR_VELOCITY_M_S).metrics.get("snr") is not None


class TestTruncationIsAnnounced:
    """Clipping without telling the caller is a Rule-17 violation."""

    def test_user_warning_names_the_consequence(self) -> None:
        sensor = Sensor.load(_CONFIG).set(
            "platform.ground_velocity_m_s", _WIDE_SMEAR_VELOCITY_M_S
        )
        with pytest.warns(UserWarning, match="smear kernel is TRUNCATED"):
            sensor.evaluate()

    def test_warning_states_what_it_costs_and_what_to_do(self) -> None:
        sensor = Sensor.load(_CONFIG).set(
            "platform.ground_velocity_m_s", _WIDE_SMEAR_VELOCITY_M_S
        )
        with pytest.warns(UserWarning) as record:
            sensor.evaluate()
        texts = [str(w.message) for w in record]
        truncation = next(t for t in texts if "TRUNCATED" in t)
        # Names the affected metrics ...
        assert "RER" in truncation
        # ... and gives the operator a lever.
        assert "integration_time_s" in truncation


class TestNormalVelocityUnaffected:
    """Regression guard: a smear that fits the grid is untouched by the clamp fix."""

    def test_modest_velocity_kernel_is_well_inside_the_grid(self) -> None:
        result = _evaluate(200.0)
        psf = result.stage_outputs["platform"]["effective_psf"]
        kernel = dict(psf.kernels)["smear"]
        assert kernel.shape[0] % 2 == 1
        assert kernel.shape[0] < psf.data.shape[0]

    def test_modest_velocity_emits_no_truncation_warning(self) -> None:
        sensor = Sensor.load(_CONFIG).set("platform.ground_velocity_m_s", 200.0)
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            sensor.evaluate()
        assert not [w for w in record if "TRUNCATED" in str(w.message)]
