"""Pixel sampling phase resolution — the straddle-factor convention (Gap 129).

Maps ``detector.pixel_phase_mode`` (+ the ``specified`` offsets) to the
displacement of the geometric image point from the pixel centre, in
**pixel pitches**. ``None`` means "average over one pitch" — the
expectation the pitch-wide box integral of the pixel-convolved PSF already
computes (rect ⊛ rect = triangle).

Conventions
-----------
- ``average``    → ``None`` (uniform phase over one pitch; the default).
- ``centered``   → ``(0, 0)``   image on a pixel centre.
- ``worst_case`` → ``(0.5, 0.5)`` image on a four-pixel corner.
- ``specified``  → ``(phase_x, phase_y)``, each in [-0.5, 0.5].

Offsets are measured from the PSF grid centre (the chief-ray image point),
not from the degraded PSF's centroid — see RADIANT_Spatial_Complete.md §6.1.
"""

from __future__ import annotations

from typing import Final

from radiant.optics.errors import OpticsValidationError

PIXEL_PHASE_MODES: Final[tuple[str, ...]] = ("average", "centered", "worst_case", "specified")

_MAX_ABS_PHASE: Final[float] = 0.5


def resolve_pixel_phase(
    mode: str,
    phase_x: float = 0.0,
    phase_y: float = 0.0,
) -> tuple[float, float] | None:
    """Resolve a pixel-phase mode to an (x, y) offset in pixel pitches, or ``None``.

    Parameters
    ----------
    mode:
        One of :data:`PIXEL_PHASE_MODES`.
    phase_x, phase_y:
        Offsets in fractions of a pitch, consulted only for ``"specified"``.

    Returns
    -------
    ``None`` for ``"average"``; otherwise ``(dx_pix, dy_pix)``.

    Raises
    ------
    OpticsValidationError
        Unknown mode, or a specified offset outside [-0.5, 0.5].
    """
    if mode == "average":
        return None
    if mode == "centered":
        return (0.0, 0.0)
    if mode == "worst_case":
        return (_MAX_ABS_PHASE, _MAX_ABS_PHASE)
    if mode == "specified":
        for label, value in (("pixel_phase_x", phase_x), ("pixel_phase_y", phase_y)):
            if not (-_MAX_ABS_PHASE <= value <= _MAX_ABS_PHASE):
                raise OpticsValidationError(
                    f"detector.{label} = {value} is outside [-0.5, 0.5] pitch; "
                    "a phase beyond half a pitch is the neighbouring pixel's phase."
                )
        return (float(phase_x), float(phase_y))
    raise OpticsValidationError(
        f"Unknown pixel_phase_mode {mode!r}; expected one of {', '.join(PIXEL_PHASE_MODES)}."
    )
