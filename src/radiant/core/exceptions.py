"""Exception hierarchy for RADIANT.

All RADIANT-defined exceptions inherit from :class:`RadiantError`.  This
gives callers a single base class to catch when they want to distinguish
"the framework rejected my input" from "an unrelated programming error
crashed the chain" (e.g. a bare ``KeyError`` from a buggy stage).

Concrete subclasses MAY co-inherit from a built-in exception type
(``ValueError``, ``RuntimeError``) to preserve back-compat with existing
``except ValueError`` / ``pytest.raises(ValueError, ...)`` patterns.  See
``ParameterBoundsError`` and ``ModtranUnavailableError`` for the canonical
patterns.

Per RADIANT_Master_Architecture.md §C12 and Rule 15:

- Errors must be actionable — carry a structured ``what / why / action``
  payload where the call site has enough context to populate it.
- ``assert`` is for developer invariants only; never use ``assert`` to
  validate user input.
- Physics-layer code never returns ``NaN``/``inf`` silently — raise an
  actionable :class:`RadiantError` subclass instead.

Lives under :mod:`radiant.core` so every module in the framework — including
the rest of ``core`` — may import it without violating the import-linter
"core has no radiant imports" contract.  Re-exported at the top level via
:mod:`radiant` for end-user convenience.
"""

from __future__ import annotations


class RadiantError(Exception):
    """Base class for all RADIANT-defined exceptions.

    Catching :class:`RadiantError` covers every error the framework raises
    on purpose (parameter bounds, Kirchhoff violations, MODTRAN unavailable,
    config parse failures, etc.) without also swallowing unrelated bugs
    like ``AttributeError`` or ``KeyError``.

    Subclasses MAY co-inherit from a built-in exception type to keep
    existing ``except ValueError`` patterns working — that is a deliberate
    back-compat carve-out, not a recommendation for new code.  New
    RADIANT exception classes SHOULD inherit from :class:`RadiantError`
    only.
    """
