"""Locate the MODTRAN executable in a cross-platform way (CU-151, Rule 30).

Leaf module — standard library only — so both :mod:`radiant.atmosphere.modtran`
(the :class:`ModtranConfig` field default) and :mod:`radiant.atmosphere._schema`
(the parameter default) can share one definition without an import cycle.

The default is a *convenience*: MODTRAN availability is authoritatively checked
at run time via ``binary_path.exists()`` (which raises
:class:`~radiant.atmosphere.modtran.ModtranUnavailableError` with actionable
guidance). Resolving the default here just avoids shipping a POSIX-only path that
can never exist on Windows.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

# Platform-appropriate fallbacks used only when ``modtran`` is not on PATH.
_POSIX_DEFAULT = "/usr/local/bin/modtran"
_WINDOWS_DEFAULT = r"C:\Program Files\MODTRAN\modtran.exe"


def default_modtran_binary() -> Path:
    """Best-guess MODTRAN executable path for the current platform.

    Prefers an executable named ``modtran`` on ``PATH``; otherwise returns the
    conventional install location for the platform. Never raises — the returned
    path may not exist, which the runtime check surfaces as an actionable error.
    """
    found = shutil.which("modtran")
    if found:
        return Path(found)
    if sys.platform.startswith("win"):
        return Path(_WINDOWS_DEFAULT)
    return Path(_POSIX_DEFAULT)


def default_modtran_binary_str() -> str:
    """String form of :func:`default_modtran_binary`, for the ``str`` schema default."""
    return str(default_modtran_binary())
