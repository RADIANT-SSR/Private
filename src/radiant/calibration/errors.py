"""Stage-scoped RADIANT error types for the calibration stage (Rule 15).

Every exception the calibration package raises on purpose derives from
:class:`~radiant.core.exceptions.RadiantError`. Mirrors the readout
package's Gap 117 structure: a *rejected* input is distinct from a config
that is merely *incomplete* mid-switch, so message surfaces can route the
latter as an advisory rather than a modal (the CU-322 pattern; the Phase 3
scheme selector hits the identical seam).
"""

from __future__ import annotations

from radiant.core.exceptions import RadiantError

__all__ = [
    "CalibrationConfigIncompleteError",
    "CalibrationValidationError",
    "is_calibration_config_incomplete",
]


class CalibrationValidationError(RadiantError, ValueError):
    """A ``radiant.calibration`` computation rejected an input value or argument."""


class CalibrationConfigIncompleteError(CalibrationValidationError):
    """An active scheme is selected but its required parameters are not set yet.

    Structurally distinct from a rejected input: every value present is legal —
    the config is mid-switch (``calibration.scheme = two_point`` with a cal
    temperature still unset). The remedy is to finish the switch, not to revert
    an input. Message surfaces route on the type, never the text.
    """


def is_calibration_config_incomplete(exc: BaseException) -> bool:
    """True when *exc* says a calibration config is incomplete, not wrong.

    The structural seam a message surface routes on (same contract as
    ``radiant.readout.errors.is_counting_config_incomplete``).
    """
    return isinstance(exc, CalibrationConfigIncompleteError)
