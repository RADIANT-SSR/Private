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

from PySide6.QtWidgets import QComboBox, QLabel  # noqa: E402

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


class TestF05SelectorSwitchesTheFamily:
    """F-05: a second viewing door entered through the dock was accepted, failed on
    every re-evaluation, and the selector changed nothing."""

    def test_second_door_is_refused_at_the_door(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Complete configuration. (2) path_zenith_rad = 0.3 (V1).
        (3) ground_range_m = 300000 (V3) through the editor."""
        window = _complete_window(qtbot, monkeypatch)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, _ZENITH, "0.3")
        dialog = _dialog_set(window, _GROUND, "300000")
        assert _GROUND not in window.sensor.inputs()
        assert dialog.error_frame.isVisibleTo(dialog)
        rendered = "\n".join(lbl.text() for lbl in dialog.error_frame.findChildren(QLabel))
        assert "Two viewing doors are set" in rendered
        assert "selector" in rendered.lower()
        assert not _form(window).is_conflicting("viewing")

    def test_selector_withdraws_and_seeds_as_one_undo_step(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Complete configuration, path zenith 10° at 500 km. (2) Pick
        Ground range (V3) on the Viewing selector. (3) Edit → Undo."""
        window = _complete_window(qtbot, monkeypatch)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, _ZENITH, "10")
        assert window.last_result is not None
        theta_o = window.last_result.stage_outputs["geometry"]["theta_o_rad"]
        ground = window.sensor.geometry_door_values()[_GROUND]
        assert ground is not None and ground > 0.0
        form = _form(window)
        before = window._undo_stack.count()  # noqa: SLF001

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form.choose_mode("viewing", "V3")

        inputs = window.sensor.inputs()
        assert _ZENITH not in inputs  # the other door was withdrawn …
        assert inputs[_GROUND] == pytest.approx(ground, rel=1e-9)  # … and V3 seeded
        assert form.active_mode("viewing") == "V3"
        assert form.is_field_editable(_GROUND)
        assert not form.is_field_editable(_ZENITH)
        assert not form.is_conflicting("viewing")
        assert not window.right_rail.messages.has_error()
        # The switch re-expressed the scene: same θ_o through the new door.
        assert window.last_result is not None
        assert window.last_result.stage_outputs["geometry"]["theta_o_rad"] == pytest.approx(
            theta_o, rel=1e-9
        )
        # One undo step reverses both moves.
        assert window._undo_stack.count() == before + 1  # noqa: SLF001
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()
        inputs = window.sensor.inputs()
        assert inputs[_ZENITH] == pytest.approx(math.radians(10.0), rel=1e-9)
        assert _GROUND not in inputs
        assert form.active_mode("viewing") == "V1"

    def test_user_pick_on_the_combo_drives_the_switch(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """The combo's own user-pick signal (not a programmatic select) runs the switch."""
        window = _complete_window(qtbot, monkeypatch)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, _ZENITH, "10")
        form = _form(window)
        combo = form.selector("viewing")
        index = combo.findData("V4")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            combo.activated.emit(index)
        inputs = window.sensor.inputs()
        assert _ZENITH not in inputs
        assert inputs[_ELEV] == pytest.approx(math.pi / 2 - math.radians(10.0), rel=1e-9)
        assert form.active_mode("viewing") == "V4"

    def test_a_door_with_no_inverse_is_remembered(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Site + time (S3) cannot be seeded from θ_s; the choice holds while its
        rows are empty, then provenance detection takes over."""
        window = _complete_window(qtbot, monkeypatch)
        form = _form(window)
        form.choose_mode("solar", "S3")
        assert form.active_mode("solar") == "S3"
        assert form.is_field_editable("geometry.site_latitude_rad")
        assert not form.is_field_editable("geometry.solar_zenith_rad")
        assert "geometry.site_latitude_rad" not in window.sensor.inputs()
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, "geometry.site_latitude_rad", "30")
        assert form.active_mode("solar") == "S3"

    def test_circular_orbit_switch_and_back_keep_the_speed(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Kinematics: direct → circular sets the flag; circular → direct seeds the
        orbital ground speed and withdraws the flag."""
        window = _complete_window(qtbot, monkeypatch)
        form = _form(window)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form.choose_mode("kinematics", "circular")
        assert window.sensor.inputs()["geometry.circular_orbit"] is True
        assert window.last_result is not None
        speed = window.last_result.stage_outputs["geometry"]["ground_speed_m_s"]
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form.choose_mode("kinematics", "direct")
        inputs = window.sensor.inputs()
        assert "geometry.circular_orbit" not in inputs
        assert inputs["geometry.ground_speed_m_s"] == pytest.approx(speed, rel=1e-9)


class TestF48InactiveDoorsShowDerivedValues:
    """F-48 (live): inactive doors displayed schema defaults (ground range 0 m,
    elevation 90°) rather than the values derived from the active door."""

    def test_inactive_doors_read_the_derived_values(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Complete configuration at 500 km. (2) path zenith 10°.
        (3) Read the greyed ground-range and elevation rows. (4) Switch to V3, read
        the greyed zenith."""
        window = _complete_window(qtbot, monkeypatch)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, _ZENITH, "10")
        form = _form(window)
        doors = window.sensor.geometry_door_values()
        assert doors[_GROUND] is not None and doors[_ELEV] is not None
        assert form.field_value_text(_GROUND) == format_value(doors[_GROUND], "m")
        assert form.field_value_text(_GROUND) != "0 m"
        assert form.field_value_text(_ELEV) == _deg(float(doors[_ELEV]))
        assert form.field_value_text(_ELEV) != "90 deg"
        assert "derived" in form.field_tooltip(_GROUND).lower()
        assert form.field_tooltip(_ZENITH) == ""  # the active door is an input

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form.choose_mode("viewing", "V3")
        assert form.field_value_text(_ZENITH) == "10 deg"
        assert not form.is_field_editable(_ZENITH)


class TestF25SiteAndTimeHourAngleToggle:
    """F-25: the S3 card offered LTAN and local solar time as two live fields of one
    mode; entering both over-specified on every re-evaluation."""

    def test_toggle_makes_the_two_entries_exclusive(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Complete configuration; Solar → Site + time. (2) Local solar
        time 10 h. (3) Flip the toggle to LTAN, enter 10.5 h. (4) Try local solar time
        again through the editor."""
        window = _complete_window(qtbot, monkeypatch)
        form = _form(window)
        form.choose_mode("solar", "S3")
        toggle = form.subdoor_selector("S3")
        assert toggle is not None
        assert not toggle.isHidden()
        assert form.is_field_editable("geometry.local_solar_time_h")
        assert not form.is_field_editable("geometry.ltan_h")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, "geometry.local_solar_time_h", "10")
        assert window.sensor.inputs()["geometry.local_solar_time_h"] == 10.0

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form.choose_subdoor("S3", 1)
        assert "geometry.local_solar_time_h" not in window.sensor.inputs()
        assert form.active_subdoor("S3") == 1
        assert form.is_field_editable("geometry.ltan_h")
        assert not form.is_field_editable("geometry.local_solar_time_h")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, "geometry.ltan_h", "10.5")
        assert window.sensor.inputs()["geometry.ltan_h"] == 10.5

        dialog = _dialog_set(window, "geometry.local_solar_time_h", "9")
        assert "geometry.local_solar_time_h" not in window.sensor.inputs()
        assert dialog.error_frame.isVisibleTo(dialog)

    def test_toggle_hides_off_the_s3_door(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _complete_window(qtbot, monkeypatch)
        form = _form(window)
        toggle = form.subdoor_selector("S3")
        assert toggle is not None
        assert toggle.isHidden()  # S1 is active


class TestF07DoorEntryWithdrawsTheOtherDoor:
    """F-07: thermal ↔ reflective, point intensity and cal-point-mode switches each
    needed N resets in the right order."""

    def test_reflectance_withdraws_the_thermal_pair_in_one_step(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Steps (thermal → reflective): (1) Complete configuration with temperature
        and emissivity set. (2) source.target.reflectance = 0.5 through the editor.
        (3) Edit → Undo."""
        window = _complete_window(qtbot, monkeypatch)
        dialog = _dialog(window, "source.target.reflectance")
        qtbot.addWidget(dialog)
        dialog.value_editor.setText("0.5")
        assert dialog.withdrawals == ("source.target.temperature", "source.target.emissivity")
        before = window._undo_stack.count()  # noqa: SLF001
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            dialog.apply(close=True)
        inputs = window.sensor.inputs()
        assert inputs["source.target.reflectance"] == 0.5
        assert "source.target.temperature" not in inputs
        assert "source.target.emissivity" not in inputs
        assert not dialog.error_frame.isVisibleTo(dialog)
        assert window._undo_stack.count() == before + 1  # noqa: SLF001
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()
        inputs = window.sensor.inputs()
        assert inputs["source.target.temperature"] == 300.0
        assert inputs["source.target.emissivity"] == 0.95
        assert "source.target.reflectance" not in inputs

    def test_going_back_is_the_mirror(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _complete_window(qtbot, monkeypatch)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, "source.target.reflectance", "0.5")
        dialog = _dialog(window, "source.target.temperature")
        qtbot.addWidget(dialog)
        dialog.value_editor.setText("320")
        assert dialog.withdrawals == ("source.target.reflectance",)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            dialog.apply(close=True)
        inputs = window.sensor.inputs()
        assert inputs["source.target.temperature"] == 320.0
        assert "source.target.reflectance" not in inputs

    def test_point_intensity_withdraws_the_thermal_pair(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """b5: a point intensity entered on a thermal configuration was rejected until
        the temperature was reset."""
        window = _complete_window(qtbot, monkeypatch)
        dialog = _dialog(window, "source.target.point_intensity_band_W_per_sr")
        qtbot.addWidget(dialog)
        dialog.value_editor.setText("10")
        assert dialog.withdrawals == ("source.target.temperature", "source.target.emissivity")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            dialog.apply(close=True)
        inputs = window.sensor.inputs()
        assert inputs["source.target.point_intensity_band_W_per_sr"] == 10.0
        assert "source.target.temperature" not in inputs
        assert not dialog.error_frame.isVisibleTo(dialog)

    def test_cal_point_mode_flip_withdraws_the_temperature_inputs(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """b9: (1) Complete configuration, scheme one_point, cal_temp_low_K = 300.
        (2) cal_point_mode = flux_fraction. (3) cal_flux_low = 0.5."""
        window = _complete_window(qtbot, monkeypatch)
        modals = _capture_modals(monkeypatch, "radiant.gui.main_window")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, "calibration.scheme", "one_point")
            _dialog_set(window, "calibration.cal_temp_low_K", "300")
        assert window.last_result is not None
        dialog = _dialog(window, "calibration.cal_point_mode")
        qtbot.addWidget(dialog)
        editor = dialog.value_editor
        assert isinstance(editor, QComboBox)
        editor.setCurrentText("flux_fraction")
        assert dialog.withdrawals == ("calibration.cal_temp_low_K",)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            dialog.apply(close=True)
        inputs = window.sensor.inputs()
        assert inputs["calibration.cal_point_mode"] == "flux_fraction"
        assert "calibration.cal_temp_low_K" not in inputs
        # The mid-switch incompleteness (no flux point yet) is an advisory, not a
        # modal per re-evaluation; entering the flux point completes the switch.
        assert modals == []
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, "calibration.cal_flux_low", "0.5")
        assert window.last_result is not None
        assert not window.right_rail.messages.has_error()
        assert modals == []
