"""Pinning tests for CU-377 — mode and door switching (GUI usability audit 2026-09).

Each test reproduces one finding's numbered steps from **Blank config** (or the
complete eleven-parameter configuration the audit built from it) through the real
entry paths — the Geometry screen's mode selectors and sub-door toggle, the shared
Parameter Editor dialog — and asserts the fixed behaviour under the owner ruling of
2026-09-20: a family's selector switches the family (withdraw the other doors, seed
the chosen one, one undo step), a second door entered outside the selector is
refused at the door, inactive doors show derived values, a blank configuration opens
on the documented default doors, the S3 hour angle is a toggle, a source door entry
or a cal-point mode flip withdraws the other door's inputs, and a bench is entered
through the slant-range door. Every test here failed on the pre-fix code; the finding
numbers refer to ``docs/reports/gui_usability_audit_2026-09/``.
"""

from __future__ import annotations

import math

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtWidgets import QComboBox  # noqa: E402

from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.param_format import format_value  # noqa: E402
from radiant.gui.widgets.geometry_mode_form import GeometryModeForm  # noqa: E402
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog  # noqa: E402

_WAIT_MS = 15000
_ALT = "geometry.sensor_altitude_m"
_ZENITH = "geometry.path_zenith_rad"
_GROUND = "geometry.ground_range_m"
_ELEV = "geometry.elevation_angle_rad"
_RANGE = "geometry.target_range_m"

# The audit's minimal complete configuration (Findings_Bootstrap_Recovery §1).
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
    window = RADIANTMainWindow()
    qtbot.addWidget(window)
    window._on_blank_config()  # noqa: SLF001 — the Blank card's slot
    return window


def _dialog(window: RADIANTMainWindow, dotpath: str) -> ParameterEditorDialog:
    panel = window.parameter_panel
    return ParameterEditorDialog(window.sensor, dotpath, panel._after_dialog_commit, panel)  # noqa: SLF001


def _dialog_set(window: RADIANTMainWindow, dotpath: str, text: str) -> ParameterEditorDialog:
    """Enter *text* for *dotpath* through the Parameter Editor's accept path."""
    dialog = _dialog(window, dotpath)
    editor = dialog.value_editor
    if isinstance(editor, QComboBox):
        editor.setCurrentText(text)
    else:
        editor.setText(text)
    dialog.apply(close=True)
    return dialog


def _capture_modals(monkeypatch, module: str) -> list[object]:  # type: ignore[no-untyped-def]
    opened: list[object] = []
    monkeypatch.setattr(f"{module}.exec_dialog", lambda dlg, *a, **k: opened.append(dlg) or 0)
    return opened


def _complete_window(qtbot, monkeypatch) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    window = _blank_window(qtbot)
    _capture_modals(monkeypatch, "radiant.gui.main_window")
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        for dotpath, text in _COMPLETE:
            _dialog_set(window, dotpath, text)
    assert window.last_result is not None, "the complete configuration must evaluate"
    return window


def _form(window: RADIANTMainWindow) -> GeometryModeForm:
    form = window.central_canvas.stage_center.pane("geometry").geometry_form
    assert form is not None
    return form


def _deg(value: float) -> str:
    return format_value(math.degrees(value), "deg")


class TestF15F26BlankConfigOpensOnDefaultDoors:
    """F-15 / F-26: on a blank configuration the cards opened on V2 / S2 / direct / K1
    (every unresolved provenance counted as "provided") and showed `—` for defaults."""

    def test_every_family_opens_on_its_documented_default(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Blank config. (2) Geometry workspace, read the four selectors."""
        window = _blank_window(qtbot)
        form = _form(window)
        assert form.active_mode("viewing") == "V1"
        assert form.active_mode("solar") == "S1"
        assert form.active_mode("kinematics") == "direct"
        assert form.active_mode("los_rate") == "K0"
        # The default door is enterable out of the box …
        assert form.is_field_editable(_ZENITH)
        assert not form.is_field_editable("geometry.sensor_off_boresight_rad")
        # … and defaulted fields show their schema default, not an unknown.
        assert form.field_value_text("geometry.target_altitude_m") == "0 m"
        assert form.field_value_text("geometry.solar_illumination") == "day"
        assert form.field_value_text(_ZENITH) == "0 deg"
        # A required parameter with no default still reads unset.
        assert form.field_value_text(_ALT) == "—"
