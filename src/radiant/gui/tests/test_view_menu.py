"""View-menu tests — theme toggle, panel show/hide, stage jump (GUI plan Phase 9).

The light/dark **theme toggle** re-applies the design-system QSS and re-themes the
custom-painted widgets (the schematic viewer, the detector illustration read a stored
theme, not QSS); panel toggles show/hide the parameter dock and right rail and persist the
choice; the stage-jump shortcuts select a stage's composite. All offscreen; golden results
untouched (view-only).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from radiant.api.sensor import Sensor
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.settings_store import SettingsStore
from radiant.gui.themes import DARK, LIGHT, active_theme, apply_theme

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000


def _settings(tmp_path: Path) -> SettingsStore:
    return SettingsStore(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))


def _window(qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = _settings(tmp_path)
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE), path=str(_EXAMPLE), settings=settings)
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window, settings


class TestThemeToggle:
    def test_toggle_switches_light_and_dark(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """The View toggle flips the app stylesheet and re-themes a painted widget."""
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        prev_qss, prev_pal = app.styleSheet(), app.palette()
        try:
            apply_theme(app, LIGHT)
            window, settings = _window(qtbot, tmp_path)
            assert active_theme().name == LIGHT.name

            light_qss = app.styleSheet()
            # The toggle re-themes synchronously (re-applies QSS + repaints); it does not
            # re-run the chain, so there is no evaluation to await.
            window.action("view.theme").trigger()

            # The app stylesheet changed to the dark sheet ...
            assert active_theme().name == DARK.name
            assert app.styleSheet() != light_qss
            assert DARK.bg in app.styleSheet()
            # ... a custom-painted widget re-themed (the detector pixel illustration) ...
            illustration = window.central_canvas.stage_center.pane("detector").detector_illustration
            assert illustration is not None
            assert illustration.theme.name == DARK.name
            # ... and the choice is persisted for the next launch.
            assert settings.theme_name() == DARK.name

            # Toggling back returns to light.
            window.action("view.theme").trigger()
            assert active_theme().name == LIGHT.name
            assert illustration.theme.name == LIGHT.name
        finally:
            app.setStyleSheet(prev_qss)
            app.setPalette(prev_pal)
            apply_theme(app, LIGHT)


class TestPanelToggles:
    def test_parameter_panel_toggle_hides_and_persists(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """View → Show/Hide Parameter Panel hides the dock and persists the state."""
        window, settings = _window(qtbot, tmp_path)
        action = window.action("view.toggle_params")
        assert action.isChecked()  # visible by default
        action.trigger()  # → hide
        assert window._parameter_dock.isHidden()
        assert settings.panel_visible("parameters", True) is False

    def test_right_rail_toggle_hides_and_persists(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """View → Show/Hide Right Rail hides the rail and persists the state."""
        window, settings = _window(qtbot, tmp_path)
        action = window.action("view.toggle_rail")
        action.trigger()  # → hide
        assert window._right_rail_dock.isHidden()
        assert settings.panel_visible("right_rail", True) is False


class TestStageJump:
    def test_ctrl_number_selects_stage(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A stage-jump action selects that stage's composite (Ctrl+1 → Geometry)."""
        window, _ = _window(qtbot, tmp_path)
        window.action("view.stage_1").trigger()
        assert window.central_canvas.selected_stage == "geometry"
