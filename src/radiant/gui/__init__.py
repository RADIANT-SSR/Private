"""RADIANT desktop GUI (PySide6) — a view over the scripting API.

The GUI contains no physics and no data model of its own: every action maps to
exactly one :class:`~radiant.api.sensor.Sensor` / ``ChainResult`` call (GUI plan
§4.1, ``docs/plans/GUI_Development_Plan.md``). This package is only importable
when the optional ``gui`` extra is installed (``pip install "radiant[gui]"``);
core RADIANT stays fully functional without it.

The public entry point is :func:`launch_gui`. Importing this module pulls in
PySide6, so callers that must degrade gracefully when Qt is absent should import
it lazily and catch :class:`ImportError` (the ``radiant gui`` CLI subcommand does
exactly this and re-raises an actionable error).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from radiant.gui.app import launch_gui

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor  # noqa: F401  (re-exported name for callers)

__all__ = ["launch_gui"]
