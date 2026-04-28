"""Scene library — Qt-free, PyVista-only.

Constraint C7 (PLAN_v2.md §3): this package must not import any Qt binding
(PySide6, PySide2, PyQt5, PyQt6). The :mod:`tests.test_scene_imports_without_qt`
test enforces this.

Structured to lift cleanly into ``radiant.gui.scene`` in a future production
GUI integration without modification (decision D5).

The ``build_scene`` re-export is *lazy* via ``__getattr__`` so that pure-constant
modules like :mod:`scene.style` can be imported in environments without
PyVista installed (e.g. before ``install_deps.sh`` runs). PyVista is only
imported the first time something actually touches ``build_scene``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dev_tools.geometry_gui_v2.scene.builder import build_scene as build_scene

__all__ = ["build_scene"]


def __getattr__(name: str) -> Any:
    if name == "build_scene":
        from dev_tools.geometry_gui_v2.scene.builder import build_scene

        return build_scene
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
