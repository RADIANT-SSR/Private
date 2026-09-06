"""Published readout-architecture seams for message surfaces (Gap 117 Phase 3).

The GUI may import :mod:`radiant.api` and :mod:`radiant.core` only, so the
structural error predicate the readout stage defines is re-published here —
the same pattern as
:func:`radiant.api.atmosphere_families.is_atmosphere_coverage_refusal`
(CU-322): routing is by exception type, never by message text.
"""

from __future__ import annotations

from radiant.readout.errors import (
    is_counting_config_incomplete as _is_counting_config_incomplete,
)

__all__ = ["is_counting_config_incomplete"]


def is_counting_config_incomplete(exc: BaseException) -> bool:
    """True when *exc* says a digital-counting config is incomplete, not wrong.

    An architecture switch to ``digital_counting`` leaves
    ``readout.count_packet_e`` unset until the operator enters the ROIC's
    charge packet; the evaluation failure in between is an expected mid-switch
    state. It belongs beside the readout inputs as an advisory, never in a
    modal headed "Parameter Rejected / Cannot set 'evaluate'" — that wording is
    for an input the framework refused to accept.
    """
    return _is_counting_config_incomplete(exc)
