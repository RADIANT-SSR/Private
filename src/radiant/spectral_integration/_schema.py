"""Parameter definitions for the spectral integration stage.

Defines the filter bandpass and integration time — the two knobs
that control the spectral-to-scalar collapse.
"""

from __future__ import annotations

from radiant.core.parameters import ParameterDef

FILTER_MIN_UM = ParameterDef(
    name="spectral_integration.filter_min_um",
    description="Short-wavelength edge of the filter bandpass [µm].",
    dtype=float,
    canonical_unit="um",
    input_unit="um",
    default=None,
    bounds=(0.1, 30.0),
    tags=frozenset({"spectral_integration", "filter"}),
)

FILTER_MAX_UM = ParameterDef(
    name="spectral_integration.filter_max_um",
    description="Long-wavelength edge of the filter bandpass [µm].",
    dtype=float,
    canonical_unit="um",
    input_unit="um",
    default=None,
    bounds=(0.1, 30.0),
    tags=frozenset({"spectral_integration", "filter"}),
)

INTEGRATION_TIME_S = ParameterDef(
    name="spectral_integration.integration_time_s",
    description="Detector integration time [s].",
    dtype=float,
    canonical_unit="s",
    input_unit="s",
    default=None,
    bounds=(1e-9, 100.0),
    tags=frozenset({"spectral_integration", "timing"}),
)


ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    FILTER_MIN_UM,
    FILTER_MAX_UM,
    INTEGRATION_TIME_S,
)
