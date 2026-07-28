"""Choosing a convolution-kernel size that is both odd and fits the PSF grid.

Every PSF-degradation kernel this stage builds — jitter, smear, turbulence —
needs a size that satisfies three constraints at once:

* **odd**, so the kernel has a single centre sample and the convolution does not
  shift the PSF by half a sample (the kernel builders enforce this and reject an
  even size);
* **no larger than the PSF grid**, since a kernel wider than the array it is
  convolved into cannot be padded into place;
* **at least a few samples**, so a narrow degradation still gets a kernel with
  some shape rather than a bare delta.

Getting these in the wrong order is what CU-235 was: each call site forced the
size odd with ``| 1`` and *then* clamped it with ``min(size, grid)``. The shipped
PSF grid is 1024 — **even** — so any degradation wide enough to reach the clamp
came back out even again and the kernel builder raised, aborting the whole chain
evaluation. It was reachable from ordinary inputs: a 7000 m/s LEO ground-track
speed at the shipped 5 ms integration time produces a 5250 µm smear against a
2176.8 µm half-grid.

The fix is to clamp first and force odd **downward** last, which is what this
module does once for all three call sites (Rule 19: one computation, one home).
Stepping down rather than up matters — stepping up from an even clamp would
re-exceed the grid, which is the constraint the clamp existed to enforce.
"""

from __future__ import annotations

from typing import Final

from radiant.platform.errors import PlatformValidationError

#: Smallest kernel worth building: a 3-sample kernel still has a centre and two
#: shoulders, so it can express *some* spread. Anything narrower is a delta.
DEFAULT_MINIMUM: Final[int] = 3


def odd_kernel_size(
    requested: int,
    grid_size: int,
    minimum: int = DEFAULT_MINIMUM,
) -> int:
    """The largest **odd** kernel size that is ``<= grid_size`` and near *requested*.

    Parameters
    ----------
    requested:
        The size the physics asked for (e.g. enough samples to cover ±4σ). May
        be even, may exceed *grid_size*; both are handled.
    grid_size:
        The PSF array's side length. The returned size never exceeds it.
    minimum:
        Floor for the returned size. Must be odd and must fit within
        *grid_size*.

    Returns
    -------
    int
        An odd size in ``[minimum, grid_size]``.

    Raises
    ------
    PlatformValidationError
        When *minimum* is even or non-positive, or when *grid_size* cannot hold
        it — both are programming errors rather than user-input errors, but they
        are reported actionably rather than silently producing a bad kernel.
    """
    if minimum <= 0 or minimum % 2 == 0:
        raise PlatformValidationError(
            f"odd_kernel_size: minimum must be a positive odd integer, got {minimum}."
        )
    if grid_size < minimum:
        raise PlatformValidationError(
            f"odd_kernel_size: PSF grid is {grid_size} samples, which cannot hold "
            f"the minimum kernel size {minimum}. The PSF grid is too small to "
            "carry a degradation kernel; increase the PSF sampling."
        )

    size = min(int(requested), int(grid_size))
    # Force odd by stepping DOWN, never up: stepping up from an even clamped
    # value would re-exceed the grid, which is exactly what the clamp prevents.
    if size % 2 == 0:
        size -= 1
    return max(size, minimum)


__all__ = ["DEFAULT_MINIMUM", "odd_kernel_size"]
