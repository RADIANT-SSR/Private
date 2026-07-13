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
from radiant.gui.param_format import provenance_from_explain, provenance_label
from radiant.gui.widgets import parameter_panel as panel_mod
from radiant.gui.widgets.parameter_editor_dialog import (
    ParameterEditorDialog,
    convertible_units,
)
from radiant.gui.widgets.parameter_panel import ParameterPanel

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

# Stable probes in the example config.
_ALT = "geometry.sensor_altitude_m"  # float, canonical m, editable, bounds (0, 1e8)
_ENUM = "geometry.solar_illumination"  # str enum (day/night)
_BOOL = "geometry.circular_orbit"  # bool
_DERIVED = "optics.f_number"  # ⚡ derived (read-only)


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

    def __init__(self, *args: Any) -> None:
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
        """Enter 8 km → the sensor reports 8000 m canonical and the tree shows 8000 m."""
        d = _dialog(sensor, _ALT, qtbot, on_committed=panel._after_dialog_commit)
        assert d.unit_combo is not None
        d.value_editor.setText("8")
        d.unit_combo.setCurrentIndex(d.unit_combo.findData("km"))
        # Preview confirms the canonical value before Apply.
        assert d.preview_label.text() == "= 8000 m"

        d.apply(close=False)

        assert sensor.get(_ALT) == pytest.approx(8000.0, abs=0)  # canonical metres
        assert sensor.get_input(_ALT) == pytest.approx(8000.0, abs=0)
        assert panel.value_text(_ALT).endswith("8000 m")  # tree refreshed via callback
        assert provenance_label(provenance_from_explain(sensor.explain(_ALT))) == "user-set"

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
