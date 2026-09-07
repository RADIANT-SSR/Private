"""Calibration stage — radiometric calibration error model (Gap 120, ADR-0012).

Terms-only stage between Readout and Performance: contributes post-NUC
residual fixed-pattern noise terms (after readout's TDI/coadd scaling, so
they are structurally exempt from sqrt(N) averaging) and calibration-scale
bias terms to the accuracy budget. Transforms no frame, collapses no
spectrum.

See ``docs/architecture/RADIANT_Calibration.md`` and
``docs/plans/Calibration_Model_Plan.md``.
"""

from radiant.calibration.errors import (
    CalibrationConfigIncompleteError,
    CalibrationValidationError,
    is_calibration_config_incomplete,
)
from radiant.calibration.stage import CalibrationStage

__all__ = [
    "CalibrationConfigIncompleteError",
    "CalibrationStage",
    "CalibrationValidationError",
    "is_calibration_config_incomplete",
]
