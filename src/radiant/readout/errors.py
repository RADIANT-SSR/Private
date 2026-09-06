"""Stage-scoped RADIANT error types (Rule 15, CU-043 migration).

Every exception the readout package raises on purpose derives from
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
    "ArchitectureOverSpecificationError",
    "CountingConfigIncompleteError",
    "ReadoutValidationError",
    "is_counting_config_incomplete",
    "is_readout_architecture_conflict",
]


class ReadoutValidationError(RadiantError, ValueError):
    """A ``radiant.readout`` computation rejected an input value or argument."""


class CountingConfigIncompleteError(ReadoutValidationError):
    """``digital_counting`` selected but its required parameters are not set yet.

    Structurally distinct from a *rejected* input (Gap 117 Phase 3, the CU-322
    advisory pattern): every value present is legal — the config is mid-switch
    and merely incomplete (``readout.count_packet_e`` still unset). Message
    surfaces route this beside the readout inputs as an advisory rather than a
    "Parameter Rejected" modal; the remedy is to finish the switch, not to
    revert an input.
    """


def is_counting_config_incomplete(exc: BaseException) -> bool:
    """True when *exc* says a counting config is incomplete, not wrong.

    The structural seam a message surface routes on — exception type, never
    message text (same contract as
    ``radiant.atmosphere.errors.is_coverage_refusal``).
    """
    return isinstance(exc, CountingConfigIncompleteError)


class ArchitectureOverSpecificationError(ReadoutValidationError):
    """A parameter combination that mixes the two readout architectures.

    Raised at evaluate time (Rule 16 runs in the stage) for the two Gap 117
    over-specification states: a counting-only parameter explicitly set under
    ``analog_well``, or an explicit ``full_well_capacity_e`` under
    ``digital_counting``. Structurally distinct so message surfaces can route
    an *evaluate-time* occurrence as an advisory beside the readout inputs —
    the state is reachable through any mutation surface (console, YAML edit,
    undo/redo, a config file authored with both), and a modal per evaluation
    turns a fixable configuration into a wall of dialogs (live review
    2026-09-06). The rejection itself is unchanged and ratified (plan §3).
    """


def is_readout_architecture_conflict(exc: BaseException) -> bool:
    """True when *exc* is a Gap 117 architecture over-specification.

    Structural, never message text — the routing seam for evaluate-time
    surfaces (the modal remains correct for an edit-time rejection).
    """
    return isinstance(exc, ArchitectureOverSpecificationError)
