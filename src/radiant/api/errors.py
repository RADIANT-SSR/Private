"""Stage-scoped RADIANT error types (Rule 15, CU-043 migration).

Every exception the api package raises on purpose derives from
:class:`~radiant.core.exceptions.RadiantError`, so user code can catch
framework rejections with a single ``except RadiantError``. The classes
co-inherit the built-in type they historically raised as (``ValueError`` /
``RuntimeError``) per the Rule 15 back-compat carve-out — existing
``except ValueError`` and ``pytest.raises(ValueError, ...)`` call sites
keep working unchanged.
"""

from __future__ import annotations

from typing import Any

from radiant.core.exceptions import RadiantError

__all__ = ["ApiValidationError", "SpectralBandError"]


class ApiValidationError(RadiantError, ValueError):
    """A ``radiant.api`` computation rejected an input value or argument."""


class SpectralBandError(ApiValidationError):
    """The filter band edges are inverted or coincide, so there is no grid to evaluate on.

    Raised by :meth:`Sensor._wavelength_grid` before any stage runs (Rule 16),
    carrying the structured ``what`` / ``why`` / ``action`` / ``context`` payload.
    Structurally distinct so a message surface routes it as an advisory beside
    the spectral inputs (CU-373 F-21): widening a band upward is two edits and
    always passes through this state, so it must not be a modal — and it must
    name the edges, not the internal grid ("wavelength_um must be strictly
    ascending" blamed the emissivity table).
    """

    def __init__(
        self, *, what: str, why: str, action: str, context: dict[str, Any] | None = None
    ) -> None:
        self.what = what
        self.why = why
        self.action = action
        self.context = dict(context or {})
        super().__init__(f"{what} | Why: {why} | Action: {action}")
