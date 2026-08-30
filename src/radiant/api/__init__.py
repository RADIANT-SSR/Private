"""Public API: Sensor, ChainResult, and analysis result types."""

from radiant.api._progress import OperationCancelledError
from radiant.api.atmosphere_families import (
    AtmosphereFamilySuggestion,
    FamilyGap,
    ShippedFamily,
    is_atmosphere_coverage_refusal,
    shipped_atmosphere_families,
    shipped_family_for_axes,
    suggested_interpolation_axes,
)
from radiant.api.coating_detail import plot_coating_detail
from radiant.api.compare import (
    ComparisonError,
    ComparisonResult,
    ComparisonRow,
    MtfComparisonResult,
    compare_configs,
    compare_mtf,
)
from radiant.api.config_io import (
    ElementPreview,
    normalize_element_document,
    preview_optical_elements,
)
from radiant.api.config_set import (
    ConfigRun,
    ConfigSetError,
    ConfigSetRunResult,
    ConfigurationSet,
)
from radiant.api.error_budget import BudgetContributor, ErrorBudget
from radiant.api.sensitivity import SensitivityResult
from radiant.api.sensor import Sensor
from radiant.api.solve import SolveResult
from radiant.api.sweep import Sweep2DResult, SweepResult
from radiant.api.tolerance import MonteCarloResult
from radiant.io.results import ChainResult, NoiseExplanation, WellStatus

__all__ = [
    "Sensor",
    "SweepResult",
    "Sweep2DResult",
    "MonteCarloResult",
    "SensitivityResult",
    "ChainResult",
    "WellStatus",
    "NoiseExplanation",
    "ErrorBudget",
    "BudgetContributor",
    "OperationCancelledError",
    "SolveResult",
    "compare_mtf",
    "compare_configs",
    "ComparisonResult",
    "ComparisonRow",
    "ComparisonError",
    "MtfComparisonResult",
    "ElementPreview",
    "preview_optical_elements",
    "plot_coating_detail",
    "normalize_element_document",
    "ConfigurationSet",
    "ConfigSetRunResult",
    "ConfigRun",
    "ConfigSetError",
    "AtmosphereFamilySuggestion",
    "FamilyGap",
    "ShippedFamily",
    "is_atmosphere_coverage_refusal",
    "shipped_atmosphere_families",
    "shipped_family_for_axes",
    "suggested_interpolation_axes",
]
