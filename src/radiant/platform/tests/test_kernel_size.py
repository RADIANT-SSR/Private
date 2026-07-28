"""Level-0 tests for odd_kernel_size (CU-235).

Every expected value here is arithmetic stated in the test, not a number taken
from other RADIANT code (Rule 18). The load-bearing case is the one that was
broken: an odd request clamped against an **even** grid.
"""

from __future__ import annotations

import pytest

from radiant.platform.errors import PlatformValidationError
from radiant.platform.kernel_size import DEFAULT_MINIMUM, odd_kernel_size


class TestTheClampParityBug:
    """CU-235: clamping an odd request to an even grid must not return an even size."""

    def test_odd_request_clamped_to_even_grid_stays_odd(self) -> None:
        """The exact shape of the bug: request 2001, grid 1024 → 1023, not 1024."""
        assert odd_kernel_size(2001, 1024) == 1023

    def test_result_never_exceeds_an_even_grid(self) -> None:
        """Stepping down, not up — 1025 would overflow the array being padded into."""
        assert odd_kernel_size(5000, 1024) <= 1024

    def test_odd_grid_is_reachable_exactly(self) -> None:
        """With an odd grid the full grid is a legal kernel size."""
        assert odd_kernel_size(5000, 1023) == 1023


class TestOrdinaryCases:
    def test_odd_request_within_grid_is_returned_unchanged(self) -> None:
        assert odd_kernel_size(69, 1024) == 69

    def test_even_request_within_grid_steps_down(self) -> None:
        assert odd_kernel_size(70, 1024) == 69

    @pytest.mark.parametrize("requested", [1, 2, 3])
    def test_small_requests_take_the_floor(self, requested: int) -> None:
        assert odd_kernel_size(requested, 1024) == DEFAULT_MINIMUM

    def test_result_is_always_odd(self) -> None:
        for requested in range(1, 60):
            for grid in (31, 32, 64, 1023, 1024):
                assert odd_kernel_size(requested, grid) % 2 == 1


class TestBounds:
    def test_result_is_within_minimum_and_grid(self) -> None:
        for requested in (1, 7, 100, 10_000):
            size = odd_kernel_size(requested, 65)
            assert DEFAULT_MINIMUM <= size <= 65

    def test_custom_odd_minimum_is_honoured(self) -> None:
        assert odd_kernel_size(1, 1024, minimum=9) == 9


class TestValidation:
    def test_even_minimum_rejected(self) -> None:
        with pytest.raises(PlatformValidationError, match="positive odd integer"):
            odd_kernel_size(11, 1024, minimum=4)

    def test_zero_minimum_rejected(self) -> None:
        with pytest.raises(PlatformValidationError, match="positive odd integer"):
            odd_kernel_size(11, 1024, minimum=0)

    def test_grid_too_small_for_the_minimum_raises_actionably(self) -> None:
        with pytest.raises(PlatformValidationError, match="too small"):
            odd_kernel_size(11, 2)
