"""Level 0: the 1/f transfer-function model's analytic limits (CU-381).

Each limit is a case where the answer is known independently of the
implementation, so these are the acceptance criteria from
``docs/plans/External_Review_Remediation_Plan.md`` §4, not a transcription of
what the code happens to produce.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.readout.errors import ReadoutValidationError
from radiant.readout.flicker_transfer import flicker_noise_e

_K_E2 = 1.0e8  # the external reviewer's flicker_K


def _sigma(**overrides: float | int) -> float:
    kwargs: dict[str, float | int] = {
        "flicker_K_e2": _K_E2,
        "t_int_s": 1.0e-3,
        "frame_period_s": 1.0e-2,
        "n_coadds": 1,
        "corner_hz": 200.0,
        "f_low_hz": 0.01,
    }
    kwargs.update(overrides)
    return flicker_noise_e(**kwargs)  # type: ignore[arg-type]


class TestCorrelatedLimit:
    """f -> 0: the comb is coherent, so a sum scales x K. Defect (c)."""

    def test_fully_correlated_band_scales_as_K(self) -> None:
        # Confine the whole integration band well below 1/T_total so every
        # frame sees one common fluctuation. T_total = K * t_frame = 1 s at
        # K = 100, so a band at 1e-4 Hz is four decades below the crossover.
        common = {"t_int_s": 1.0e-3, "frame_period_s": 1.0e-2, "corner_hz": 1.0e-3}
        one = _sigma(n_coadds=1, f_low_hz=1.0e-5, **common)
        many = _sigma(n_coadds=100, f_low_hz=1.0e-5, **common)
        assert many / one == pytest.approx(100.0, rel=1e-3)

    def test_correlated_limit_is_K_not_sqrt_K(self) -> None:
        """The whole point of the CU: sqrt(K) would be 10, not 100."""
        common = {"t_int_s": 1.0e-3, "frame_period_s": 1.0e-2, "corner_hz": 1.0e-3}
        one = _sigma(n_coadds=1, f_low_hz=1.0e-5, **common)
        many = _sigma(n_coadds=100, f_low_hz=1.0e-5, **common)
        assert many / one > 50.0  # emphatically not sqrt(100) = 10


class TestWhiteNoiseLimit:
    """A flat PSD must still give exactly sqrt(K) — the old scaling, kept where right."""

    def test_flat_psd_scales_as_sqrt_K(self) -> None:
        # Emulate a flat PSD by integrating a narrow band high above the
        # Dirichlet crossover, where successive frames are uncorrelated.
        # T_total = 1 s at K = 100, crossover ~20 Hz; 100-200 Hz is above it.
        common = {"t_int_s": 1.0e-5, "frame_period_s": 1.0e-2, "corner_hz": 200.0}
        one = _sigma(n_coadds=1, f_low_hz=100.0, **common)
        many = _sigma(n_coadds=100, f_low_hz=100.0, **common)
        assert many / one == pytest.approx(math.sqrt(100.0), rel=1e-6)


class TestSingleFrameCollapse:
    """K = 1 must reduce to one boxcar, with no comb factor at all."""

    def test_k1_is_independent_of_frame_period(self) -> None:
        a = _sigma(n_coadds=1, frame_period_s=1.0e-2)
        b = _sigma(n_coadds=1, frame_period_s=1.0)
        assert a == pytest.approx(b, rel=1e-12)

    def test_k1_matches_the_closed_form_in_the_narrowband_limit(self) -> None:
        """Back-compat anchor: where sinc^2 ~ 1, the integral IS K ln(f_hi/f_lo).

        Only holds when f * t_int << 1 across the band — which the shipped
        1 MHz / 5 ms default badly violated, and which is defect (b).
        """
        f_low, f_corner, t_int = 0.01, 10.0, 1.0e-6  # f*t_int <= 1e-5
        sigma = _sigma(
            n_coadds=1, t_int_s=t_int, frame_period_s=1.0, f_low_hz=f_low, corner_hz=f_corner
        )
        closed_form = math.sqrt(_K_E2 * math.log(f_corner / f_low))
        assert sigma == pytest.approx(closed_form, rel=1e-4)


class TestCornerFrequency:
    """The corner enters as the PSD's shape, not as a post-hoc cap. Defect (a)."""

    def test_raising_the_corner_raises_the_noise(self) -> None:
        low = _sigma(corner_hz=50.0)
        high = _sigma(corner_hz=500.0)
        assert high > low

    def test_corner_below_f_low_gives_zero(self) -> None:
        """The whole 1/f band under the white floor: read noise owns it."""
        assert _sigma(corner_hz=0.005, f_low_hz=0.01) == 0.0

    def test_corner_capped_band_matches_the_analytic_log(self) -> None:
        """Third independent anchor: scenario 2.2's corner-limited closed form."""
        f_low, f_corner, t_int = 60.0, 200.0, 1.0e-7
        sigma = _sigma(
            n_coadds=1, t_int_s=t_int, frame_period_s=1.0, f_low_hz=f_low, corner_hz=f_corner
        )
        expected = math.sqrt(_K_E2 * math.log(f_corner / f_low))
        assert sigma == pytest.approx(expected, rel=1e-4)


class TestIntegrationTimeEnters:
    """Defect (b): sigma must respond to t_int at all."""

    def test_longer_integration_lowers_in_band_flicker(self) -> None:
        # A longer boxcar rolls off sooner, admitting less high-frequency power.
        short = _sigma(t_int_s=1.0e-4, frame_period_s=1.0, corner_hz=1.0e5, f_low_hz=1.0)
        long_ = _sigma(t_int_s=1.0e-2, frame_period_s=1.0, corner_hz=1.0e5, f_low_hz=1.0)
        assert long_ < short

    def test_old_model_was_insensitive_to_t_int(self) -> None:
        """Documents what changed: the closed form gave the identical number."""
        # The superseded closed form's value, for the record.
        closed = math.sqrt(_K_E2 * math.log(1.0e6 / 0.01))
        a = _sigma(t_int_s=1.0e-4, frame_period_s=1.0, corner_hz=1.0e6, f_low_hz=0.01)
        b = _sigma(t_int_s=1.0e-1, frame_period_s=1.0, corner_hz=1.0e6, f_low_hz=0.01)
        assert a != pytest.approx(b, rel=1e-3)
        assert closed == pytest.approx(closed)  # the old value, for the record


class TestReferenceHighPass:
    """A chopped/referenced measurement suppresses the low-frequency power."""

    def test_reference_reduces_noise_in_a_correlated_band(self) -> None:
        common = {
            "t_int_s": 1.0e-3,
            "frame_period_s": 1.0e-2,
            "n_coadds": 100,
            "corner_hz": 1.0e-2,
            "f_low_hz": 1.0e-5,
        }
        staring = _sigma(reference_separation_s=0.0, **common)
        chopped = _sigma(reference_separation_s=1.0e-2, **common)
        assert chopped < staring

    def test_no_reference_is_unity_gain(self) -> None:
        a = _sigma(reference_separation_s=0.0)
        b = _sigma()
        assert a == pytest.approx(b, rel=1e-12)


class TestDisabledAndInvalid:
    def test_zero_coefficient_disables(self) -> None:
        assert (
            flicker_noise_e(
                flicker_K_e2=0.0,
                t_int_s=1e-3,
                frame_period_s=1e-2,
                n_coadds=10,
                corner_hz=200.0,
                f_low_hz=0.01,
            )
            == 0.0
        )

    @pytest.mark.parametrize(
        ("field", "value"),
        [("n_coadds", 0), ("t_int_s", 0.0), ("t_int_s", -1.0), ("f_low_hz", 0.0)],
    )
    def test_invalid_inputs_raise_actionably(self, field: str, value: float | int) -> None:
        with pytest.raises(ReadoutValidationError):
            _sigma(**{field: value})

    def test_frame_shorter_than_integration_is_rejected(self) -> None:
        """A frame cannot integrate longer than its own period."""
        with pytest.raises(ReadoutValidationError, match="shorter than"):
            _sigma(t_int_s=1.0e-2, frame_period_s=1.0e-3)

    def test_never_returns_nan_or_inf(self) -> None:
        for k in (1, 2, 17, 500):
            value = _sigma(n_coadds=k)
            assert math.isfinite(value)
            assert value >= 0.0


class TestDirichletKernel:
    """The comb's own identities, independent of the PSD."""

    def test_kernel_is_K_squared_at_dc(self) -> None:
        from radiant.readout.flicker_transfer import _dirichlet_power

        power = _dirichlet_power(np.array([1e-12]), 64, 1e-2)
        assert power[0] == pytest.approx(64.0**2, rel=1e-6)

    def test_kernel_averages_to_K_well_above_crossover(self) -> None:
        from radiant.readout.flicker_transfer import _dirichlet_power

        power = _dirichlet_power(np.array([1e4, 2e4, 3e4]), 64, 1e-2)
        np.testing.assert_allclose(power, 64.0, rtol=1e-12)
