"""Structural error predicate for the optics transmission modes (CU-373 F-09).

The GUI may import only ``radiant.api`` + ``radiant.core`` (import rules), so the
optics package's routing seam is re-exported here — the same bridge pattern as
:mod:`radiant.api.readout_architecture` and :mod:`radiant.api.calibration_state`.
A message surface routes on the exception TYPE, never its text: a transmission
mode selected without its inputs (``key_elements`` with no element yet) is an
expected mid-switch state handled as an advisory beside the optics inputs, not a
"Parameter Rejected" modal per evaluation.
"""

from __future__ import annotations

from radiant.optics.errors import (
    is_transmission_config_incomplete as _is_transmission_config_incomplete,
)

__all__ = ["is_transmission_config_incomplete"]


def is_transmission_config_incomplete(exc: BaseException) -> bool:
    """True when *exc* says a transmission mode lacks its inputs (not a wrong value)."""
    return _is_transmission_config_incomplete(exc)
