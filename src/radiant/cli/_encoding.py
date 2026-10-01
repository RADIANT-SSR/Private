"""Force the CLI's output streams to UTF-8 (CU-385, Rule 30).

RADIANT's parameter descriptions, units, and error messages carry `µ`, `°`,
`α`, `λ`, `ε`, `Ω` and `τ`. Python picks the console's locale encoding for
``sys.stdout`` — cp1252 on a default Windows terminal — so writing any of them
raises ``UnicodeEncodeError`` mid-command. ``radiant schema`` was unusable
without ``PYTHONIOENCODING=utf-8``, and worse, a ``ParameterBoundsError``
message containing `µm` could itself die on the way to the screen: the
diagnostic failing exactly when it is needed.

Forcing the streams to UTF-8 cannot lose information. On a console whose code
page is not UTF-8 the characters may render as replacement glyphs, which is a
display limitation of that console; the alternative — ASCII-folding the
descriptions — would discard load-bearing unit symbols for every platform to
suit one.
"""

from __future__ import annotations

import io
import sys
from typing import TextIO

__all__ = ["force_utf8_streams"]


def _reconfigure(stream: TextIO | None) -> None:
    """Switch *stream* to UTF-8 in place when it supports reconfiguration.

    A stream that cannot be reconfigured is left untouched, which is the
    correct outcome rather than a swallowed failure: pytest's capture object,
    a plain ``io.StringIO``, and a closed or redirected handle are all
    legitimately non-reconfigurable, and none of them is a console that needs
    this fix. Only the narrow errors those cases raise are caught — never a
    bare ``Exception`` (Rule 17).
    """
    if stream is None:
        return
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8")
    except (ValueError, OSError, io.UnsupportedOperation):
        # Detached, closed, or not a real text stream — nothing to do.
        return


def force_utf8_streams() -> None:
    """Make ``sys.stdout`` and ``sys.stderr`` UTF-8. Idempotent; safe anywhere."""
    _reconfigure(sys.stdout)
    _reconfigure(sys.stderr)
