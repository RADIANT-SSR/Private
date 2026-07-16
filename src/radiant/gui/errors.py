"""GUI-scoped RADIANT error types (Rule 15, CU-043 pattern).

Every exception the GUI package raises on purpose derives from
:class:`~radiant.core.exceptions.RadiantError`, so user/host code can catch
framework rejections with a single ``except RadiantError`` (and the
``tests/test_exceptions.py`` no-bare-builtin-raises guard stays green). The
class co-inherits the built-in type it historically raised as (``ValueError``)
per the Rule 15 back-compat carve-out — existing ``except ValueError`` and
``pytest.raises(ValueError, ...)`` call sites keep working unchanged.
"""

from __future__ import annotations

from radiant.core.exceptions import RadiantError

__all__ = ["GuiValidationError"]


class GuiValidationError(RadiantError, ValueError):
    """A ``radiant.gui`` widget rejected an input value or internal-state argument."""
