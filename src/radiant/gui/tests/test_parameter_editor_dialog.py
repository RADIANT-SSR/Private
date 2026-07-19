"""Parameter Editor dialog tests (GUI plan Phase 3 checkpoint punch-list).

These prove the "open it up" box the owner asked for: it shows the full dot-path and
description, lets the user set a value **with a unit** in one ``sensor.set`` (verified
canonical round-trip via the public API — 8 km → 8000 m), keeps the live sensor untouched
and the dialog open on a rejected value (rendering the actionable error inline), opens a
derived parameter read-only, and drives the right editor per dtype (enum → combo, bool →
checkbox). Both entry points (double-click a non-Value column, right-click "Edit…") route
to the same dialog. Every expected value is read from the live API so the assertions
cannot drift from the schema.

Modal dialogs are constructed and inspected directly (never ``exec()``-ed, which would
block the offscreen event loop); the panel's dialog class is patched to a non-blocking
capture where a panel flow raises one. Widget visibility is checked with ``isVisibleTo``
because the top-level dialog is never shown offscreen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QLabel, QLineEdit

from radiant.api.sensor import Sensor
from radiant.api.units import _CONVERSIONS
from radiant.gui.param_format import display_in_unit, provenance_from_explain, provenance_label
from radiant.gui.widgets import parameter_editor_dialog as dialog_mod
from radiant.gui.widgets import parameter_panel as panel_mod
from radiant.gui.widgets.parameter_editor_dialog import (
    ParameterEditorDialog,
    convertible_units,
    default_browse_dir,
    path_picker_kind,
)
from radiant.gui.widgets.parameter_panel import ParameterPanel

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

# Stable probes in the example config.
_ALT = "geometry.sensor_altitude_m"  # float, canonical m, editable, bounds (0, 1e8)
_ENUM = "geometry.solar_illumination"  # str enum (day/night)
_BOOL = "geometry.circular_orbit"  # bool
_DERIVED = "optics.f_number"  # ⚡ derived (read-only)
_TEMP = "source.target.temperature"  # float, canonical K — only K is registered


@pytest.fixture
def sensor() -> Sensor:
    """A Sensor loaded from a real example config (resolves cleanly)."""
    return Sensor.from_yaml(_EXAMPLE)


@pytest.fixture
def panel(sensor: Sensor, qtbot) -> ParameterPanel:  # type: ignore[no-untyped-def]
    """A ParameterPanel populated from the example sensor."""
    p = ParameterPanel()
    qtbot.addWidget(p)
    p.populate(sensor)
    return p


def _dialog(sensor: Sensor, dotpath: str, qtbot, on_committed: Any = None) -> ParameterEditorDialog:  # type: ignore[no-untyped-def]
    d = ParameterEditorDialog(sensor, dotpath, on_committed)
    qtbot.addWidget(d)
    return d


class _CapturingDialog:
    """Non-blocking stand-in for the editor dialog: records ctor args, never blocks."""

    calls: list[tuple[Any, ...]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        type(self).calls.append(args)

    def exec(self) -> int:
        return 0


@pytest.fixture(autouse=True)
def _reset_captures() -> None:
    _CapturingDialog.calls = []


class TestUnitEnumeration:
    def test_convertible_units_come_from_the_public_registry(self) -> None:
        """The unit list is the registry's convert-to-canonical set, not a hardcode."""
        expected = sorted({frm for (frm, to) in _CONVERSIONS if to == "m"} | {"m"})
        assert convertible_units("m", "m") == expected
        assert "km" in expected and "cm" in expected

    def test_input_and_canonical_units_always_offered(self) -> None:
        """Even a single-unit dimension still lists its own units (never empty)."""
        units = convertible_units("K", "K")
        assert "K" in units and units  # temperature: only K is convertible, still present


class TestUnitComboPopup:
    """Item 1: the unit dropdown popup no longer clips unit names to ~2 characters."""

    def test_popup_view_is_sized_to_its_widest_item(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The combo adjusts to contents and its popup is at least its widest label wide."""
        d = _dialog(sensor, _ALT, qtbot)
        combo = d.unit_combo
        assert combo is not None
        assert combo.sizeAdjustPolicy() == QComboBox.SizeAdjustPolicy.AdjustToContents
        metrics = combo.fontMetrics()
        widest = max(metrics.horizontalAdvance(combo.itemText(i)) for i in range(combo.count()))
        # No 2-char clip: the popup view is at least as wide as its widest unit label.
        assert combo.view().minimumWidth() >= widest


class TestDisplayUnits:
    """Item 2: the dialog opens showing the value in the row's chosen display unit."""

    def test_opens_in_the_given_display_unit(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Told to display km, the combo, Current line, and editor all read km."""
        current_m = sensor.get_input(_ALT)
        d = ParameterEditorDialog(sensor, _ALT, None, None, display_unit="km")
        qtbot.addWidget(d)
        assert d.unit_combo is not None
        assert d.unit_combo.currentData() == "km"
        # Current line and editor show the km value (no ad-hoc maths — via the seam).
        expected_km = display_in_unit(current_m, "m", "km", "m")
        assert "km" in d._current_label.text()
        assert f"{expected_km:g}" in d._current_label.text()
        assert float(d.value_editor.text()) == pytest.approx(expected_km, abs=0)

    def test_bounds_shown_in_display_unit(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The bounds line is re-expressed in the display unit (km), not the input m."""
        d = ParameterEditorDialog(sensor, _ALT, None, None, display_unit="km")
        qtbot.addWidget(d)
        lo, hi = sensor.parameter_def(_ALT).bounds  # in input_unit m
        bounds_texts = [lbl.text() for lbl in d.findChildren(QLabel) if "–" in lbl.text()]
        assert bounds_texts, "expected a bounds row"
        text = bounds_texts[0]
        assert text.endswith("km")
        assert f"{display_in_unit(hi, 'm', 'km', 'm'):g}" in text

    def test_non_multiplicative_unit_falls_back_to_canonical(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A temperature (only K registered) given an offset unit falls back to K safely."""
        d = ParameterEditorDialog(sensor, _TEMP, None, None, display_unit="degC")
        qtbot.addWidget(d)
        assert d.unit_combo is not None
        # 'degC' is not a registered (multiplicative) conversion → dialog falls back to K.
        assert d.unit_combo.currentData() == "K"
        assert "K" in d._current_label.text()


class TestOpensInformative:
    def test_shows_full_path_and_description(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The box shows the full dot-path (untruncated) and the schema description."""
        d = _dialog(sensor, _ALT, qtbot)
        assert d.path_label.text() == _ALT
        assert d.description_label.text() == sensor.parameter_def(_ALT).description
        assert d.description_label.isVisibleTo(d)

    def test_current_value_carries_unit_and_provenance(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Current row shows value + unit and the provenance label from the API."""
        d = _dialog(sensor, _ALT, qtbot)
        prov = provenance_label(provenance_from_explain(sensor.explain(_ALT)))
        text = d._current_label.text()
        assert "m" in text and prov in text

    def test_unit_combo_populated_and_defaults_to_input_unit(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A dimensional parameter gets a unit combo defaulting to its input_unit."""
        d = _dialog(sensor, _ALT, qtbot)
        assert d.unit_combo is not None
        units = [d.unit_combo.itemData(i) for i in range(d.unit_combo.count())]
        assert set(units) == set(convertible_units("m", "m"))
        assert d.unit_combo.currentData() == sensor.parameter_def(_ALT).input_unit

    def test_both_entry_points_open_the_dialog(
        self, panel: ParameterPanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Double-click a non-Value column and right-click 'Edit…' both open the box."""
        monkeypatch.setattr(panel_mod, "ParameterEditorDialog", _CapturingDialog)
        item = panel._items[_ALT]

        panel._on_double_click(panel.tree.indexFromItem(item, 0))  # Parameter column
        panel._open_editor_dialog(_ALT)  # right-click "Edit…" path

        assert len(_CapturingDialog.calls) == 2
        assert all(call[1] == _ALT for call in _CapturingDialog.calls)

    def test_double_click_value_column_does_not_open_dialog(
        self, panel: ParameterPanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The Value column keeps its fast in-place editor — no dialog there."""
        monkeypatch.setattr(panel_mod, "ParameterEditorDialog", _CapturingDialog)
        panel._on_double_click(panel.tree.indexFromItem(panel._items[_ALT], 1))
        assert not _CapturingDialog.calls


class TestUnitRoundTrip:
    def test_set_altitude_in_km_reports_canonical_metres(
        self, sensor: Sensor, panel: ParameterPanel, qtbot
    ) -> None:  # type: ignore[no-untyped-def]
        """Enter 8 km → sensor canonical is 8000 m and the tree shows the chosen 8 km.

        The canonical round-trip is unchanged (8 km → 8000 m internally); the display
        change (owner feedback 2026-07-13) is that the tree adopts the user's chosen
        unit, so the row reads ``8 km``, not ``8000 m``.
        """
        d = _dialog(sensor, _ALT, qtbot, on_committed=panel._after_dialog_commit)
        assert d.unit_combo is not None
        d.value_editor.setText("8")
        d.unit_combo.setCurrentIndex(d.unit_combo.findData("km"))
        # Preview confirms the canonical value before Apply.
        assert d.preview_label.text() == "= 8000 m"

        d.apply(close=False)

        assert sensor.get(_ALT) == pytest.approx(8000.0, abs=0)  # canonical metres
        assert sensor.get_input(_ALT) == pytest.approx(8000.0, abs=0)
        assert panel.value_text(_ALT).endswith("8 km")  # tree shows the user's unit
        assert panel.display_unit(_ALT) == "km"  # chosen unit adopted as display unit
        assert provenance_label(provenance_from_explain(sensor.explain(_ALT))) == "user-set"

    def test_apply_reexpresses_current_and_bounds_in_chosen_unit(
        self, sensor: Sensor, qtbot
    ) -> None:  # type: ignore[no-untyped-def]
        """CU-111: after Apply (no close), the Current + Bounds rows adopt the combo unit.

        Opening in metres then applying 8 km should leave the informative rows reading
        km (not the original ``8000 m``), agreeing with the combo the user just set.
        """
        d = _dialog(sensor, _ALT, qtbot)  # opens in the input unit (m)
        assert d.unit_combo is not None
        d.value_editor.setText("8")
        d.unit_combo.setCurrentIndex(d.unit_combo.findData("km"))
        d.apply(close=False)
        assert d._display_unit == "km"
        assert "8 km" in d._current_label.text()
        assert "m" not in d._current_label.text().replace("km", "")  # no stray metres
        assert d._bounds_label is not None
        assert d._bounds_label.text().rstrip().endswith("km")

    def test_apply_and_close_accepts_the_dialog(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Apply & Close commits then dismisses (accepted); Apply alone keeps it open."""
        d = _dialog(sensor, _ALT, qtbot)
        assert d.unit_combo is not None
        d.value_editor.setText("500")
        d.unit_combo.setCurrentIndex(d.unit_combo.findData("km"))
        d.apply(close=True)
        assert sensor.get(_ALT) == pytest.approx(500000.0, abs=0)
        assert d.result() == QDialog.DialogCode.Accepted


class TestRejection:
    def test_out_of_bounds_keeps_dialog_open_and_sensor_untouched(
        self, sensor: Sensor, qtbot
    ) -> None:  # type: ignore[no-untyped-def]
        """A rejected value renders the error inline, keeps open, never touches sensor."""
        d = _dialog(sensor, _ALT, qtbot)
        assert d.unit_combo is not None
        before = sensor.get(_ALT)

        d.value_editor.setText("999999999")  # km → far above the 1e8 m bound
        d.unit_combo.setCurrentIndex(d.unit_combo.findData("km"))
        d.apply(close=False)

        assert sensor.get(_ALT) == before  # sensor unchanged (validated on a clone)
        assert d.error_frame.isVisibleTo(d)  # inline actionable error shown
        assert d.result() != QDialog.DialogCode.Accepted  # dialog stayed open
        rendered = "\n".join(lbl.text() for lbl in d.error_frame.findChildren(QLabel))
        assert "out of bounds" in rendered

    def test_a_following_good_apply_clears_the_error(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A valid value after a rejected one drops the inline error and commits."""
        d = _dialog(sensor, _ALT, qtbot)
        assert d.unit_combo is not None
        d.unit_combo.setCurrentIndex(d.unit_combo.findData("km"))
        d.value_editor.setText("999999999")
        d.apply(close=False)
        assert d.error_frame.isVisibleTo(d)

        d.value_editor.setText("600")
        d.apply(close=False)
        assert not d.error_frame.isVisibleTo(d)
        assert sensor.get(_ALT) == pytest.approx(600000.0, abs=0)


class TestReadOnlyDerived:
    def test_derived_param_opens_read_only(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A ⚡ derived parameter opens informative-only: editors disabled, no commit."""
        d = _dialog(sensor, _DERIVED, qtbot)
        assert d.read_only
        assert not d.value_editor.isEnabled()
        if d.unit_combo is not None:
            assert not d.unit_combo.isEnabled()
        before = sensor.get(_DERIVED)
        d.apply(close=False)  # read-only apply is a no-op
        assert sensor.get(_DERIVED) == before


class TestEditorTypes:
    def test_enum_opens_combo_with_schema_choices_and_no_unit(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """An enum parameter opens a combo of its schema choices and no unit selector."""
        d = _dialog(sensor, _ENUM, qtbot)
        assert isinstance(d.value_editor, QComboBox)
        items = [d.value_editor.itemText(i) for i in range(d.value_editor.count())]
        assert items == list(sensor.parameter_def(_ENUM).enum_values)
        assert d.unit_combo is None  # non-numeric: no unit boundary

    def test_bool_opens_checkbox(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A bool parameter opens a checkbox and no unit selector."""
        d = _dialog(sensor, _BOOL, qtbot)
        assert isinstance(d.value_editor, QCheckBox)
        assert d.unit_combo is None

    def test_float_opens_line_edit(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A plain float parameter opens a permissive line edit (API validates)."""
        d = _dialog(sensor, _ALT, qtbot)
        assert isinstance(d.value_editor, QLineEdit)

    def test_enum_edit_commits_through_the_api(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Selecting an enum value and applying flips it via one sensor.set."""
        d = _dialog(sensor, _ENUM, qtbot)
        assert isinstance(d.value_editor, QComboBox)
        choices = list(sensor.parameter_def(_ENUM).enum_values)
        target = next(c for c in choices if c != sensor.get(_ENUM))
        d.value_editor.setCurrentIndex(choices.index(target))
        d.apply(close=False)
        assert sensor.get(_ENUM) == target


class TestPathBrowse:
    """Path-typed parameters get a Browse… picker next to the line edit
    (owner request 2026-07-18: "need a link" on atmosphere.interpolated_data_dir)."""

    def test_path_picker_kind_follows_the_naming_convention(self) -> None:
        """The schema types paths as str; the *_path/*_file/*_dir leaf marks them."""
        assert path_picker_kind("atmosphere.interpolated_data_dir") == "dir"
        assert path_picker_kind("atmosphere.modtran.cache_dir") == "dir"
        assert path_picker_kind("atmosphere.modtran.tape7_path") == "file"
        assert path_picker_kind("atmosphere.tabulated_transmittance_file") == "file"
        assert path_picker_kind("geometry.sensor_altitude_m") is None
        assert path_picker_kind("geometry.solar_illumination") is None

    def test_dir_param_gets_browse_button(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        d = _dialog(sensor, "atmosphere.interpolated_data_dir", qtbot)
        assert isinstance(d.value_editor, QLineEdit)
        assert d.browse_button is not None
        assert d.browse_button.isEnabled()

    def test_file_param_gets_browse_button(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        d = _dialog(sensor, "atmosphere.modtran.tape7_path", qtbot)
        assert d.browse_button is not None

    def test_non_path_params_get_no_browse_button(self, sensor: Sensor, qtbot) -> None:  # type: ignore[no-untyped-def]
        assert _dialog(sensor, _ALT, qtbot).browse_button is None
        assert _dialog(sensor, _ENUM, qtbot).browse_button is None
        assert _dialog(sensor, _BOOL, qtbot).browse_button is None

    def test_dir_picker_fills_the_editor(  # type: ignore[no-untyped-def]
        self, sensor: Sensor, qtbot, monkeypatch, tmp_path
    ) -> None:
        """Choosing a directory writes it into the value editor; commit stays on Apply."""
        d = _dialog(sensor, "atmosphere.interpolated_data_dir", qtbot)
        chosen = str(tmp_path / "atmospheres")
        monkeypatch.setattr(
            dialog_mod.QFileDialog,
            "getExistingDirectory",
            staticmethod(lambda *a, **k: chosen),
        )
        assert d.browse_button is not None
        d.browse_button.click()
        assert isinstance(d.value_editor, QLineEdit)
        assert d.value_editor.text() == chosen

    def test_file_picker_cancel_leaves_editor_untouched(  # type: ignore[no-untyped-def]
        self, sensor: Sensor, qtbot, monkeypatch
    ) -> None:
        d = _dialog(sensor, "atmosphere.modtran.tape7_path", qtbot)
        assert isinstance(d.value_editor, QLineEdit)
        before = d.value_editor.text()
        monkeypatch.setattr(
            dialog_mod.QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *a, **k: ("", "")),
        )
        assert d.browse_button is not None
        d.browse_button.click()
        assert d.value_editor.text() == before


class TestBrowseStartLocation:
    """The picker opens on RADIANT's shipped data, not an arbitrary cwd (2026-07-18)."""

    def test_atmosphere_params_start_in_shipped_atmospheres(self) -> None:
        start = default_browse_dir("atmosphere.interpolated_data_dir")
        assert start is not None
        assert start.name == "atmospheres"
        assert start.is_dir()

    def test_detector_params_start_in_shipped_detectors(self) -> None:
        start = default_browse_dir("detector.qe_table_path")
        assert start is not None
        assert start.name == "detectors"

    def test_unmapped_namespace_falls_back_to_data_root(self) -> None:
        start = default_browse_dir("optics.zernike_file")
        assert start is not None
        assert start.name == "data"
