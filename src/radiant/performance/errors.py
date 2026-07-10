"""Stage-scoped RADIANT error types (Rule 15, CU-043 migration).

Every exception the performance package raises on purpose derives from
:class:`~radiant.core.exceptions.RadiantError`, so user code can catch
framework rejections with a single ``except RadiantError``. The classes
co-inherit the built-in type they historically raised as (``ValueError`` /
``RuntimeError``) per the Rule 15 back-compat carve-out — existing
``except ValueError`` and ``pytest.raises(ValueError, ...)`` call sites
keep working unchanged.
"""

from __future__ import annotations

from radiant.core.exceptions import RadiantError

__all__ = ["PerformanceValidationError"]


class PerformanceValidationError(RadiantError, ValueError):
    """A ``radiant.performance`` computation rejected an input value or argument."""
