"""CalibrationStage — radiometric calibration error model (Gap 120, ADR-0012).

Terms-only stage (PlatformStage precedent) registered between ReadoutStage
and PerformanceStage. The chain position is load-bearing: residual-FPN
noise terms are appended AFTER readout's TDI/coadd scaling has been applied
to temporal terms, so calibration residuals are structurally exempt from
sqrt(N) averaging — correlated errors do not average down. Do not move this
stage without re-reading ADR-0012 and the contract tests.

Phase 0 (plan §11): ``scheme = "none"`` is a recorded no-op — no noise
terms, no bias terms, a stage-outputs block stating the model is off.
Active schemes validate their configuration (Rule 16) and then raise the
actionable phase-gate error; the physics lands in Phase 1
(``nuc_residual.py``, ``gain_drift.py``, ``offset_drift.py``,
``cal_source_bias.py`` per plan §5).

This stage adds no PSF kernel and no MTF term: residual FPN is spatial
*noise*, not a spatial *degradation* — neither Rule 4 path gains a
contributor and the consistency check is unaffected (plan §2.5).
"""

from __future__ import annotations

import logging

from radiant.calibration.errors import (
    CalibrationConfigIncompleteError,
    CalibrationValidationError,
)
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet

logger = logging.getLogger(__name__)

#: Sentinel: cal temperatures default to 0.0 = "unset" (see _schema.py).
_UNSET = 0.0


def _validate_active_scheme(scheme: str, params: ParameterSet) -> None:
    """Rule 16: validate an active scheme's configuration before any physics.

    Raises the *incomplete* subtype when required cal points are unset (a
    mid-switch config — advisory routing) and the plain validation error
    when values present are unphysical (a rejected input — modal routing).
    """
    t_low: float = params.get("calibration.cal_temp_low_K")
    t_high: float = params.get("calibration.cal_temp_high_K")

    if t_low == _UNSET:
        raise CalibrationConfigIncompleteError(
            f"calibration.scheme = '{scheme}' needs a cal point, but "
            "calibration.cal_temp_low_K is unset.\n"
            "  Why: an active NUC scheme corrects at known cal-source "
            "temperatures; without them there is nothing to correct at.\n"
            "  Action: set calibration.cal_temp_low_K (and cal_temp_high_K "
            "for two_point), or set calibration.scheme = 'none'."
        )
    if scheme == "two_point":
        if t_high == _UNSET:
            raise CalibrationConfigIncompleteError(
                "calibration.scheme = 'two_point' needs two cal points, but "
                "calibration.cal_temp_high_K is unset.\n"
                "  Why: two-point NUC corrects per-pixel gain and offset at "
                "two cal-source temperatures.\n"
                "  Action: set calibration.cal_temp_high_K above "
                f"cal_temp_low_K = {t_low} K, or use scheme = 'one_point'."
            )
        if t_high <= t_low:
            raise CalibrationValidationError(
                f"calibration.cal_temp_high_K = {t_high} K must exceed "
                f"cal_temp_low_K = {t_low} K.\n"
                "  Why: two-point NUC is ill-conditioned as the cal points "
                "converge (plan §15) and undefined when inverted.\n"
                "  Action: separate the cal temperatures (high > low)."
            )


class CalibrationStage:
    """Stage protocol implementation for the calibration error model."""

    @property
    def name(self) -> str:
        return "calibration"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        scheme: str = params.get("calibration.scheme")

        if scheme == "none":
            logger.debug("calibration: scheme=none — model off, no terms emitted")
            return state.with_stage_output("calibration", "scheme", "none").with_stage_output(
                "calibration", "enabled", False
            )

        # Rule 16: validate before compute — even while the physics is
        # phase-gated, a broken active config is reported as itself.
        _validate_active_scheme(scheme, params)

        raise CalibrationConfigIncompleteError(
            f"calibration.scheme = '{scheme}' is configured but the "
            "calibration physics has not landed yet (Gap 120 Phase 0 — "
            "schema and chain skeleton only).\n"
            "  Why: docs/plans/Calibration_Model_Plan.md Phase 1 delivers "
            "the NUC-residual, drift, and cal-source-bias models.\n"
            "  Action: set calibration.scheme = 'none' until Phase 1 lands."
        )
