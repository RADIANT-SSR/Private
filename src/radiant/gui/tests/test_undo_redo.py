"""Undo / redo tests for the parameter-edit stack (GUI plan Phase 9, arch doc §10).

Drives the Edit → Undo / Redo ``QUndoStack`` end to end, offscreen: a parameter edit pushes
a named command, undo restores the previous value and re-evaluates, redo re-applies it, and a
whole-config swap (YAML-editor Apply / console Refresh) clears the stack (the documented
Phase-9 behaviour). Golden results are untouched — the GUI is a view over the scripting API.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QKeySequence

from radiant.api.config_set import ConfigurationSet
from radiant.api.sensor import Sensor
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.settings_store import SettingsStore
from radiant.gui.widgets.target_shape_panel import NOMINAL_SHAPE_DIMENSIONS

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_APERTURE = "optics.aperture_diameter_m"
_WAIT_MS = 15000


def _window(qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = SettingsStore(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE), path=str(_EXAMPLE), settings=settings)
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


def _edit(window, dotpath: str, value: float) -> None:
    """Mimic the panel's edit path: apply the value, then signal the window."""
    window.sensor.set(dotpath, value)
    window._on_parameter_edited(dotpath)


class TestUndoRedo:
    def test_edit_pushes_named_command(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A parameter edit records one reversible, human-labelled command."""
        window = _window(qtbot, tmp_path)
        _edit(window, _APERTURE, 0.6)
        assert window._undo_stack.count() == 1
        assert window._undo_stack.canUndo()
        assert window.action("edit.undo").isEnabled()
        assert window._undo_stack.command(0).text() == f"Set {_APERTURE} = 0.6 m"

    def test_undo_restores_value_and_reevaluates(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Undo restores the previous value, refreshes the panel, and re-evaluates."""
        window = _window(qtbot, tmp_path)
        original = window.sensor.get_input(_APERTURE)
        _edit(window, _APERTURE, 0.6)
        assert window.sensor.get_input(_APERTURE) == 0.6

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()

        assert window.sensor.get_input(_APERTURE) == original
        # The parameter panel re-read the restored value (view matches the sensor).
        assert window.parameter_panel.value_text(_APERTURE).startswith(f"{original:g}")
        assert window.action("edit.redo").isEnabled()

    def test_redo_reapplies_value(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Redo re-applies the undone edit and re-evaluates."""
        window = _window(qtbot, tmp_path)
        _edit(window, _APERTURE, 0.6)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.redo").trigger()
        assert window.sensor.get_input(_APERTURE) == 0.6

    def test_config_swap_clears_the_stack(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A whole-document Apply (YAML editor / console) resets the undo history.

        Since Phase 4e the Apply hand-off is a ``ConfigurationSet`` (the document), not a
        bare sensor; a plain session's degenerate set *is* its sensor, so the assertion
        that the swapped-in object becomes ``window.sensor`` is unchanged.
        """
        window = _window(qtbot, tmp_path)
        _edit(window, _APERTURE, 0.6)
        assert window._undo_stack.count() == 1

        replacement = Sensor.load(_EXAMPLE)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window._apply_new_document(ConfigurationSet(replacement))

        assert window._undo_stack.count() == 0
        assert not window.action("edit.undo").isEnabled()
        assert window.sensor is replacement


class TestCU141ShapeMacroUndo:
    """CU-141: a shape pick + the dims seeded alongside it reverse in a single Undo."""

    def test_shape_and_seeded_dims_undo_as_one_macro(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _window(qtbot, tmp_path)
        # GT-0 (2026-07-16): the shape editor left Source; the macro contract is
        # exercised through the Geometry pane's shared panel.
        panel = window._central.stage_center.pane("geometry").geometry_panel
        assert panel is not None

        shape = "box"
        dims = list(NOMINAL_SHAPE_DIMENSIONS[shape])
        shape_before = window.sensor.get("geometry.target.shape")
        for dp in dims:
            assert float(window.sensor.get(dp)) == 0.0
        before = window._undo_stack.count()

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            panel.shape_combo.setCurrentText(shape)  # shape pick → seeds dims → one macro

        # Exactly ONE new stack entry — the macro — not the shape plus N separate commands.
        assert window._undo_stack.count() == before + 1
        assert window.sensor.get("geometry.target.shape") == shape
        for dp in dims:
            assert float(window.sensor.get(dp)) > 0.0

        # A single Undo reverses the shape AND every seeded dimension atomically.
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window._undo_stack.undo()
        assert window.sensor.get("geometry.target.shape") == shape_before
        for dp in dims:
            assert float(window.sensor.get(dp)) == 0.0


class TestCU142EvaluateShortcut:
    """CU-142: Evaluate keeps F5 and gains a macOS-reachable Ctrl+Return alternate."""

    def test_evaluate_has_f5_and_ctrl_return(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _window(qtbot, tmp_path)
        seqs = window.action("run.evaluate").shortcuts()
        assert QKeySequence("F5") in seqs
        assert QKeySequence("Ctrl+Return") in seqs
