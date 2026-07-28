"""Stage-scoped RADIANT error types (Rule 15, CU-043 migration).

Every exception the atmosphere package raises on purpose derives from
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

__all__ = [
    "AtmosphereValidationError",
    "AtmosphereStateError",
    "TurbulenceSpecificationError",
]


class AtmosphereValidationError(RadiantError, ValueError):
    """A ``radiant.atmosphere`` computation rejected an input value or argument."""


class AtmosphereStateError(RadiantError, RuntimeError):
    """A ``radiant.atmosphere`` stage was invoked in an invalid chain state.

    E.g. a required upstream stage output is missing. Co-inherits
    :class:`RuntimeError` per the Rule 15 back-compat carve-out.
    """


class TurbulenceSpecificationError(RadiantError):
    """The turbulence inputs are over-specified or mutually contradictory.

    Raised when ``atmosphere.cn2_profile`` selects a profile-driven Fried
    parameter *and* ``atmosphere.r0_m`` is explicitly user-set to a value the
    profile does not reproduce (the CU-093 redundant-entry pattern: two live
    inputs for one canonical quantity, disagreeing by more than 1 %), or when
    a profile is selected alongside an explicit ``r0_m = 0`` ("turbulence
    off").

    Inherits :class:`RadiantError` only, per the Rule 15 guidance for new
    exception classes — it has no historical ``ValueError`` call sites to
    preserve.
    """

    def __init__(
        self,
        what: str,
        why: str = "",
        action: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        self.what = what
        self.why = why
        self.action = action
        self.context = context or {}
        parts: list[str] = [what]
        if why:
            parts.append(f"Why: {why}")
        if action:
            parts.append(f"Action: {action}")
        super().__init__(" | ".join(parts))
