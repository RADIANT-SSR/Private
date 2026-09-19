"""Stage-scoped RADIANT error types (Rule 15, CU-043 migration).

Every exception the optics package raises on purpose derives from
:class:`~radiant.core.exceptions.RadiantError`, so user code can catch
framework rejections with a single ``except RadiantError``. The classes
co-inherit the built-in type they historically raised as (``ValueError`` /
``RuntimeError``) per the Rule 15 back-compat carve-out — existing
``except ValueError`` and ``pytest.raises(ValueError, ...)`` call sites
keep working unchanged.
"""

from __future__ import annotations

from radiant.core.exceptions import RadiantError

__all__ = [
    "OpticsValidationError",
    "TransmissionConfigIncompleteError",
    "is_transmission_config_incomplete",
]


class OpticsValidationError(RadiantError, ValueError):
    """A ``radiant.optics`` computation rejected an input value or argument."""


class TransmissionConfigIncompleteError(OpticsValidationError):
    """A transmission input mode is selected but its inputs are not provided yet.

    ``key_elements`` with no element, ``spectral_file`` with no curve,
    ``telescope_plus_filters`` with no telescope throughput, ``scalar`` with no
    scalar: every value present is legal — the mode is mid-switch and merely
    incomplete. Structurally distinct so a message surface can route it as an
    advisory beside the optics inputs (CU-373 F-09), never a modal per evaluation.
    """


def is_transmission_config_incomplete(exc: BaseException) -> bool:
    """True when *exc* says a transmission mode lacks its inputs (structural, never text)."""
    return isinstance(exc, TransmissionConfigIncompleteError)
