"""Run every stage cross-parameter check that does not need computed state (CU-383).

The defect this closes: ``radiant validate`` reported *"Study OK — 3
configuration(s), 0 failed"* for a study in which two of the three could not
run. The architecture over-specification check that rejected them lived inside
``ReadoutStage.run``, so only ``evaluate`` reached it. The error itself was
precise and actionable; it was simply unreachable from the command whose job is
to find it. A validate that misses whole classes of configuration error teaches
operators not to rely on it.

The audit the CU asked for
--------------------------
Four stage-level cross-parameter validators exist. Three are functions of the
ParameterSet alone and run here:

===================  ==========================================================
Stage                Check
===================  ==========================================================
``readout``          architecture over-specification — counting-only parameters
                     under ``analog_well``, an explicit ``full_well_capacity_e``
                     under ``digital_counting``, up/down-only parameters under
                     ``counting_mode: up``.
``calibration``      active-scheme completeness, and the flux-fraction mode's
                     forbidden temperature anchors.
===================  ==========================================================

The fourth, ``optics._validate_psf_regime_consistency``, **cannot** move here:
it compares the scene's angular extent against the computed ``EffectivePSF``,
which does not exist before the chain runs. That is a real limit of pre-chain
validation, not an oversight — recorded so the next reader does not go looking.

Adding a stage
--------------
A new stage joins by exposing a module-level ``validate_params(params)`` and
being listed in :data:`_STAGE_VALIDATORS`. The function must raise
:class:`~radiant.core.exceptions.RadiantError` (Rule 15) and must not mutate
the ParameterSet.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from radiant.calibration import stage as calibration_stage
from radiant.core.parameters import ParameterSet
from radiant.readout import stage as readout_stage

__all__ = ["precheck_parameters", "stage_validator_names"]

#: Stage name -> params-only validator. Order matches the signal chain so the
#: first error a user sees is the earliest one in the chain.
_STAGE_VALIDATORS: tuple[tuple[str, Callable[[ParameterSet], None]], ...] = (
    ("readout", readout_stage.validate_params),
    ("calibration", calibration_stage.validate_params),
)


def stage_validator_names() -> Sequence[str]:
    """Names of the stages whose cross-parameter checks run pre-chain."""
    return tuple(name for name, _ in _STAGE_VALIDATORS)


def precheck_parameters(params: ParameterSet) -> None:
    """Raise the first stage cross-parameter error, or return cleanly.

    Fail-fast by design: these are configuration errors whose remedies are
    independent, and the caller (``radiant validate``) already reports
    per-configuration rather than per-parameter.

    Resolves *params* first if it is not resolved already. Every validator
    reads resolved values and provenance, so an unresolved set would otherwise
    surface as "ParameterSet not resolved" — a true statement that tells the
    caller nothing about their config. ``resolve()`` is idempotent.
    """
    if not params.is_resolved:
        params.resolve()
    for _name, validator in _STAGE_VALIDATORS:
        validator(params)
