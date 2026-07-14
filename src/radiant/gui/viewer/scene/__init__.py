"""Scene library — Qt-free, PyVista-only (lifted from ``geometry_gui_v2`` per ADR-0007).

Contract (ADR-0007 §2, the prototype's C7): this package imports **no Qt binding** and
**no physics stage** — it reads a :class:`~radiant.gui.viewer.viewer_state.ViewerState`
(passed in by the GUI) plus ``radiant.core`` helpers only. That keeps the gui→api+core
import-linter contract intact; the plotter object is consumed by the Qt shell via
``pyvistaqt.QtInteractor``, but PyVista itself does not depend on Qt.

The ``build_static_scene`` re-export is *lazy* via ``__getattr__`` so pure-constant
modules (:mod:`scene.style`, :mod:`scene.palette`) can be imported in environments
without PyVista; PyVista is imported the first time ``build_static_scene`` is touched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from radiant.gui.viewer.scene.builder import build_static_scene as build_static_scene

__all__ = ["build_static_scene"]


def __getattr__(name: str) -> Any:
    if name == "build_static_scene":
        from radiant.gui.viewer.scene.builder import build_static_scene

        return build_static_scene
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
