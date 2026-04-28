"""C7 enforcement (PLAN_v2.md §3): the ``scene/`` package must not import
any Qt binding.

The test blocks ``PySide6``, ``PySide2``, ``PyQt5``, and ``PyQt6`` in
``sys.modules``, then forces a fresh import of every module under
``dev_tools.geometry_gui_v2.scene``. If any scene module imports a Qt
binding (directly or transitively), the import raises an ImportError
that the test surfaces.

This is the C7 canary: the production GUI is going to lift ``scene/``
into ``radiant.gui.scene`` as a Qt-free reusable library, and Trame
deployment (CU-033) depends on the same property. We catch any drift
the moment a scene-side file picks up a Qt import.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
import unittest.mock

import pytest

# This test is meaningful only once PyVista is installed (the C7 invariant
# is "imports PyVista without dragging Qt in"). Before ``install_deps.sh``
# runs, skip cleanly so the rest of the suite stays green.
pytest.importorskip("pyvista")


_QT_BINDINGS = ("PySide6", "PySide2", "PyQt5", "PyQt6")


def _purge_scene_modules() -> None:
    """Remove every cached ``dev_tools.geometry_gui_v2.scene*`` module so the
    next import reads fresh — otherwise the patched ``sys.modules`` is bypassed
    by the import system's module cache."""
    for name in list(sys.modules):
        if name.startswith("dev_tools.geometry_gui_v2.scene"):
            del sys.modules[name]


def test_scene_package_imports_without_any_qt_binding() -> None:
    blocked = {name: None for name in _QT_BINDINGS}

    _purge_scene_modules()
    with unittest.mock.patch.dict(sys.modules, blocked):
        import dev_tools.geometry_gui_v2.scene as scene_pkg

        # Walk every submodule and force-import. This catches a Qt import
        # that lives in a submodule the top-level __init__ doesn't pull in.
        for module_info in pkgutil.walk_packages(
            scene_pkg.__path__, prefix=scene_pkg.__name__ + "."
        ):
            importlib.import_module(module_info.name)

        for binding in _QT_BINDINGS:
            assert sys.modules.get(binding) is None, (
                f"scene package transitively imported {binding} — C7 violation"
            )


def test_scene_build_runs_without_any_qt_binding() -> None:
    """Even calling ``build_scene`` (which constructs a ``pv.Plotter``) must
    not pull a Qt binding through. PyVista's default plotter uses VTK's own
    rendering window, not Qt — that's the property C7 protects."""
    blocked = {name: None for name in _QT_BINDINGS}

    _purge_scene_modules()
    with unittest.mock.patch.dict(sys.modules, blocked):
        from dev_tools.geometry_gui_v2.app.state import SceneState
        from dev_tools.geometry_gui_v2.scene import build_scene

        # off_screen=True so the test never tries to pop a window.
        import pyvista as pv

        plotter = pv.Plotter(off_screen=True)
        try:
            build_scene(SceneState.default(), plotter=plotter)
        finally:
            plotter.close()

        for binding in _QT_BINDINGS:
            assert sys.modules.get(binding) is None, (
                f"build_scene transitively imported {binding} — C7 violation"
            )
