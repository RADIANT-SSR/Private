"""Pinning tests for CU-372 — GUI edit discipline (GUI usability audit 2026-09).

Each test reproduces one finding's numbered steps from **Blank config** (or the
complete eleven-parameter configuration the audit built from it) through the real
entry paths — the Parameters dock's in-place delegate, the Parameter Editor dialog,
the dock's Reset to Default, the YAML editor's Apply — and asserts the fixed
behaviour. Every test here failed on the pre-fix code; the finding numbers refer to
``docs/reports/gui_usability_audit_2026-09/``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog  # noqa: E402

_WAIT_MS = 15000
_ALT = "geometry.sensor_altitude_m"

# The audit's minimal complete configuration (Findings_Bootstrap_Recovery §1), in
# the quiet optics-first order.
_COMPLETE: tuple[tuple[str, str], ...] = (
    ("optics.aperture_diameter_m", "0.3"),
    ("optics.f_number", "4"),
    ("detector.pixel_pitch_x_um", "18"),
    ("detector.pixel_pitch_y_um", "18"),
    ("detector.qe_value", "0.7"),
    ("spectral_integration.filter_min_um", "3.4"),
    ("spectral_integration.filter_max_um", "5.0"),
    ("spectral_integration.integration_time_s", "0.005"),
    ("source.target.temperature", "300"),
    ("source.target.emissivity", "0.95"),
    (_ALT, "500000"),
)


def _blank_window(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """Blank config exactly as the welcome screen's card produces it."""
    window = RADIANTMainWindow()
    qtbot.addWidget(window)
    window._on_blank_config()  # noqa: SLF001 — the Blank card's slot
    return window


def _dialog_set(window: RADIANTMainWindow, dotpath: str, text: str) -> ParameterEditorDialog:
    """Enter *text* for *dotpath* through the Parameter Editor's accept path."""
    panel = window.parameter_panel
    dialog = ParameterEditorDialog(
        window.sensor,
        dotpath,
        panel._after_dialog_commit,
        panel,  # noqa: SLF001
    )
    dialog.value_editor.setText(text)
    dialog.apply(close=True)
    return dialog


def _capture_modals(monkeypatch, module: str) -> list[object]:  # type: ignore[no-untyped-def]
    opened: list[object] = []
    monkeypatch.setattr(f"{module}.exec_dialog", lambda dlg, *a, **k: opened.append(dlg) or 0)
    return opened


class TestF01DockShowsCommittedValues:
    """F-01: on an unresolved configuration every dock row read `—` with no
    provenance, including the values just accepted through the dialog."""

    def test_accepted_value_shows_with_provenance_before_config_resolves(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Blank config. (2) Set geometry.sensor_altitude_m = 500000 through
        the editor dialog (accepted). (3) Look at the dock row."""
        window = _blank_window(qtbot)
        _capture_modals(monkeypatch, "radiant.gui.main_window")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, _ALT, "500000")
        panel = window.parameter_panel
        assert panel.value_text(_ALT) == "500000 m"
        assert panel.source_text(_ALT) == "user-set"
        # A row nothing has set still reads unset — the fallback is per row.
        assert panel.value_text("optics.aperture_diameter_m") == "—"
        assert panel.source_text("optics.aperture_diameter_m") == ""

    def test_changed_only_lists_the_set_rows_on_an_incomplete_config(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """*Changed only* listed nothing until the configuration resolved."""
        window = _blank_window(qtbot)
        _capture_modals(monkeypatch, "radiant.gui.main_window")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, _ALT, "500000")
        panel = window.parameter_panel
        panel._changed_only.setChecked(True)  # noqa: SLF001
        assert panel.visible_dotpaths() == {_ALT}
