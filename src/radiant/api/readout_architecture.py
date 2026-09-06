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
from radiant.readout.errors import (
    is_readout_architecture_conflict as _is_readout_architecture_conflict,
)

__all__ = ["is_counting_config_incomplete", "is_readout_architecture_conflict"]


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


def is_readout_architecture_conflict(exc: BaseException) -> bool:
    """True when *exc* is a Gap 117 architecture over-specification.

    The mixed-architecture states (counting-only parameters under
    ``analog_well``; explicit ``full_well_capacity_e`` under
    ``digital_counting``) are reachable through any mutation surface — console,
    YAML edit, undo/redo, a config file authored with both — and are detected
    at evaluate time. An evaluate-time occurrence routes beside the readout
    inputs as an advisory; the rejection itself is unchanged (plan §3).
    """
    return _is_readout_architecture_conflict(exc)
