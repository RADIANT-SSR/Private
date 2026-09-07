"""Structural error predicates for the calibration stage (Gap 120, plan Phase 3).

The GUI may import only ``radiant.api`` + ``radiant.core`` (import rules), so
the calibration package's structural routing seams are re-exported here — the
same bridge pattern as :mod:`radiant.api.readout_architecture` (Gap 117). A
message surface routes on the exception TYPE, never its text: a mid-switch
calibration config (scheme active, cal point not yet entered) is an expected
incomplete state handled as an advisory beside the calibration inputs, not a
"Parameter Rejected" modal per evaluation.
"""

from __future__ import annotations

from radiant.calibration.errors import (
    is_calibration_config_incomplete as _is_calibration_config_incomplete,
)

__all__ = ["is_calibration_config_incomplete"]


def is_calibration_config_incomplete(exc: BaseException) -> bool:
    """True when *exc* says a calibration config is incomplete, not wrong."""
    return _is_calibration_config_incomplete(exc)
