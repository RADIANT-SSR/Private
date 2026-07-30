"""Parameter-editing tests (GUI plan Phase 2, Task B).

These prove the editable half of the parameter panel: a committed edit is one
``sensor.set`` that flows through the API (value + provenance flip verified via the
public surface); a rejected edit reverts the row and leaves the live sensor untouched
(also verified via the API, not assumption); the schema drives every editor choice
(enum → combo with schema-sourced items); the right-click menu copies the dot-path,
explains, and resets to default; and the actionable / unexpected error dialogs render
their content honestly (Rules 15/17). Every expected value is read from the live API so
the assertions cannot drift from the schema.

Modal dialogs are constructed and inspected directly (never ``exec()``-ed, which would
block the offscreen event loop); where a panel flow raises one, the dialog class is
patched to a non-blocking capture so the flow completes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QSpinBox,
    QStyleOptionViewItem,
)

from radiant.api.sensor import Sensor
from radiant.core.parameters import ParameterBoundsError
from radiant.gui.param_format import provenance_label, safe_provenance
from radiant.gui.widgets import parameter_panel as panel_mod
from radiant.gui.widgets.actionable_error_dialog import ActionableErrorDialog
from radiant.gui.widgets.explain_dialog import ExplainDialog
from radiant.gui.widgets.parameter_panel import ParameterPanel
from radiant.gui.widgets.unexpected_error_dialog import UnexpectedErrorDialog

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

# A clean, standalone bounded float in the example config (default 300 K, bounds
# 0–5000 K) with no consistency-group entanglement — the reliable accept/reject probe.
_TEMP = "source.target.temperature"
# A length parameter (canonical/input m) for display-unit round-trips.
_ALT = "geometry.sensor_altitude_m"


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


class _CapturingDialog(QDialog):
    """Non-blocking stand-in for a modal dialog: records its ctor args, never blocks.

    A real :class:`QDialog` subclass, not a bare object: the production call sites run
    the modal loop through ``dialog_lifetime.exec_dialog``, which ``deleteLater()``s the
    dialog afterwards (CU-216), so a stand-in must have a real Qt lifetime. It is created
    parentless (the ctor args are only recorded, never forwarded) and the session-wide
    ``_release_widgets`` fixture cleans up anything the deferred delete has not.
    """

    calls: list[tuple[Any, ...]] = []

    def __init__(self, *args: Any) -> None:
        super().__init__()
        type(self).calls.append(args)

    def exec(self) -> int:
        return 0


@pytest.fixture(autouse=True)
def _reset_captures() -> None:
    _CapturingDialog.calls = []


class TestDisplayUnits:
    """Item 2 (owner feedback 2026-07-13): rows show — and accept — the user's unit."""

    def test_inline_edit_is_symmetric_in_the_display_unit(
        self, panel: ParameterPanel, sensor: Sensor
    ) -> None:
        """Type 550 into a km-displaying row → 550000 m canonical, row shows 550 km."""
        # Adopt km as the altitude row's display unit, as a dialog commit would.
        panel._after_dialog_commit(_ALT, "km")
        assert panel.display_unit(_ALT) == "km"
        assert panel.value_text(_ALT).endswith("km")

        # The inline editor seeds in the display unit (what you see is what you edit).
        seeded = panel._input_value_for(_ALT)
        assert float(seeded) == pytest.approx(sensor.get(_ALT) / 1000.0, abs=0)

        # The inline delegate commits the typed number interpreted in the display unit.
        panel._commit_edit(_ALT, "550")
        assert sensor.get(_ALT) == pytest.approx(550000.0, abs=0)  # canonical metres
        assert panel.value_text(_ALT).endswith("550 km")  # what you type is what you read

    def test_unsound_display_unit_falls_back_to_input_unit(self, panel: ParameterPanel) -> None:
        """An unregistered display unit falls back to the canonical/input unit — with its suffix."""
        # A genuinely unregistered token (degC/degF are now soundly convertible per WS-C, so
        # they are *kept*; see test_offset_temperature_display_converts). An unknown unit has
        # no path to the canonical unit and must fall back.
        panel._display_units[_TEMP] = "zorp"  # not a registered conversion of any kind
        panel.populate(panel._sensor)  # same sensor → preserves the override
        text = panel.value_text(_TEMP)
        assert text.endswith("300 K")  # fell back to the canonical/input unit, suffix present

    def test_offset_temperature_display_converts(self, panel: ParameterPanel) -> None:
        """An offset temperature unit (degC) is now soundly convertible (WS-C) and is used."""
        panel._display_units[_TEMP] = "degC"
        panel.populate(panel._sensor)  # same sensor → preserves the override
        text = panel.value_text(_TEMP)
        # 300 K → 26.85 °C, shown in the chosen unit (not fallen back to K).
        assert text.endswith("degC")
        assert "26.85" in text

    def test_never_edited_row_keeps_canonical_display(self, panel: ParameterPanel) -> None:
        """A row with no display-unit override still shows its schema input unit."""
        assert panel.display_unit(_ALT) == panel._sensor.parameter_def(_ALT).input_unit
        assert panel.value_text(_ALT).endswith("m")


class TestEditAccept:
    def test_accepted_edit_roundtrips_through_the_api(
        self, panel: ParameterPanel, sensor: Sensor
    ) -> None:
        """A valid commit calls sensor.set once; value + provenance flip, verified via API."""
        assert panel.value_text(_TEMP).endswith("300 K")
        assert panel.source_text(_TEMP) == "config"

        panel._commit_edit(_TEMP, 310.0)

        # The live sensor really holds the new value (public API, not assumption).
        assert sensor.get_input(_TEMP) == pytest.approx(310.0, abs=0)
        # The row refreshed: value + unit and the provenance badge (now user-set).
        assert panel.value_text(_TEMP).endswith("310 K")
        assert panel.source_text(_TEMP) == "user-set"
        assert provenance_label(safe_provenance(sensor, _TEMP)) == "user-set"
        assert not panel.has_error(_TEMP)

    def test_accepted_edit_emits_parameter_edited(self, panel: ParameterPanel, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The host-window stale hook fires with the edited dot-path."""
        with qtbot.waitSignal(panel.parameterEdited, timeout=1000) as blocker:
            panel._commit_edit(_TEMP, 305.0)
        assert blocker.args == [_TEMP]


class TestEditReject:
    def test_rejected_edit_reverts_row_and_leaves_sensor_untouched(
        self, panel: ParameterPanel, sensor: Sensor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An out-of-bounds value never sticks: row reverts, sensor unchanged (via API)."""
        monkeypatch.setattr(panel_mod, "ActionableErrorDialog", _CapturingDialog)

        before_val = sensor.get_input(_TEMP)
        before_text = panel.value_text(_TEMP)

        panel._commit_edit(_TEMP, 9999.0)  # bounds are [0, 5000] K

        # The value never reached the sensor or the display.
        assert sensor.get_input(_TEMP) == before_val
        assert panel.value_text(_TEMP) == before_text
        assert panel.source_text(_TEMP) == "config"  # provenance untouched
        # The rejected-edit state is shown inline (row tint flag + banner).
        assert panel.has_error(_TEMP)
        assert panel.error_banner.isVisibleTo(panel)  # offscreen: relative visibility
        assert "out of bounds" in panel.error_banner.text()
        # A modal was raised (captured, not blocked) carrying the rejecting exception.
        assert _CapturingDialog.calls, "reject must surface an ActionableErrorDialog"

    def test_a_following_accept_clears_the_error_state(
        self, panel: ParameterPanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A good edit after a bad one drops the rejected-edit tint and banner."""
        monkeypatch.setattr(panel_mod, "ActionableErrorDialog", _CapturingDialog)
        panel._commit_edit(_TEMP, 9999.0)
        assert panel.has_error(_TEMP)

        panel._commit_edit(_TEMP, 320.0)
        assert not panel.has_error(_TEMP)
        assert not panel.error_banner.isVisibleTo(panel)

    def test_target_spec_conflict_rejected_at_commit(
        self, panel: ParameterPanel, sensor: Sensor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CU-244: an edit introducing a target-spec over-specification is rejected.

        The example config carries a thermal (ε, T) target, so committing a
        reflectance value introduces the ρ-vs-(ε, T) conflict; the resolve-time
        seam rejects it at the door with the evaluate-time error text.
        """
        monkeypatch.setattr(panel_mod, "ActionableErrorDialog", _CapturingDialog)
        rho = "source.target.reflectance"
        before = sensor.get(rho)

        panel._commit_edit(rho, 0.3)

        assert sensor.get(rho) == before  # live sensor untouched
        assert panel.has_error(rho)
        assert "mutually exclusive" in panel.error_banner.text()
        assert _CapturingDialog.calls, "reject must surface an ActionableErrorDialog"


class TestEditorTypes:
    """The delegate opens the editor the ParameterDef dtype/enum calls for."""

    def _editor_for(self, panel: ParameterPanel, dotpath: str) -> Any:
        item = panel._items[dotpath]
        index = panel.tree.indexFromItem(item, 1)
        return panel._delegate.createEditor(panel.tree, QStyleOptionViewItem(), index)

    def test_enum_renders_combo_with_schema_choices(
        self, panel: ParameterPanel, sensor: Sensor
    ) -> None:
        """An enum parameter opens a combo whose items are the schema's enum_values."""
        dotpath = next(
            dp
            for dp, pd in sensor.parameter_defs().items()
            if pd.enum_values is not None and panel.is_editable(dp)
        )
        editor = self._editor_for(panel, dotpath)
        assert isinstance(editor, QComboBox)
        items = [editor.itemText(i) for i in range(editor.count())]
        assert items == list(sensor.parameter_def(dotpath).enum_values)

    def test_int_renders_spinbox(self, panel: ParameterPanel, sensor: Sensor) -> None:
        """An int parameter opens a spin box (bounds honoured when declared)."""
        dotpath = next(
            dp
            for dp, pd in sensor.parameter_defs().items()
            if pd.dtype is int and pd.enum_values is None and panel.is_editable(dp)
        )
        editor = self._editor_for(panel, dotpath)
        assert isinstance(editor, QSpinBox)

    def test_bool_renders_checkbox(self, panel: ParameterPanel, sensor: Sensor) -> None:
        """A bool parameter opens a checkbox (if the schema has one that is editable)."""
        candidate = next(
            (
                dp
                for dp, pd in sensor.parameter_defs().items()
                if pd.dtype is bool and panel.is_editable(dp)
            ),
            None,
        )
        if candidate is None:
            pytest.skip("no editable bool parameter in this schema")
        assert isinstance(self._editor_for(panel, candidate), QCheckBox)

    def test_float_renders_line_edit(self, panel: ParameterPanel) -> None:
        """A plain float parameter opens a permissive line edit (API validates on commit)."""
        assert isinstance(self._editor_for(panel, _TEMP), QLineEdit)


class TestContextMenu:
    def test_copy_dotpath_puts_full_path_on_clipboard(self, panel: ParameterPanel) -> None:
        panel._copy_dotpath(_TEMP)
        assert QApplication.clipboard().text() == _TEMP

    def test_explain_builds_dialog_with_sensor_explanation(
        self, panel: ParameterPanel, sensor: Sensor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Right-click Explain renders sensor.explain(dotpath) verbatim in the dialog."""
        monkeypatch.setattr(panel_mod, "ExplainDialog", _CapturingDialog)
        panel._explain(_TEMP)
        assert _CapturingDialog.calls, "Explain must raise an ExplainDialog"
        dotpath_arg, text_arg = _CapturingDialog.calls[0][0], _CapturingDialog.calls[0][1]
        assert dotpath_arg == _TEMP
        assert text_arg == sensor.explain(_TEMP)

    def test_reset_reverts_to_default_via_api(self, panel: ParameterPanel, sensor: Sensor) -> None:
        """Reset to Default clears the user override; value + provenance revert (via API)."""
        panel._commit_edit(_TEMP, 320.0)
        assert panel.source_text(_TEMP) == "user-set"

        panel._reset_to_default(_TEMP)

        assert sensor.get_input(_TEMP) == pytest.approx(300.0, abs=0)  # schema default
        assert panel.value_text(_TEMP).endswith("300 K")
        assert panel.source_text(_TEMP) != "user-set"


class TestErrorDialogs:
    def test_actionable_dialog_renders_what_why_action_context(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A structured RadiantError shows its four fields verbatim (Rules 15/17)."""
        exc = ParameterBoundsError(
            what="sensor.detector.operating_temp = 400 K is out of bounds",
            why="HgCdTe operates at cryogenic temperature (1–300 K)",
            action="Set operating_temp to 77–120 K for HgCdTe detectors",
            context={"param": "sensor.detector.operating_temp", "value": 400},
        )
        dialog = ActionableErrorDialog(exc, "sensor.detector.operating_temp")
        qtbot.addWidget(dialog)
        rendered = "\n".join(lbl.text() for lbl in dialog.findChildren(QLabel))
        assert "out of bounds" in rendered  # what
        assert "cryogenic temperature" in rendered  # why
        assert "77–120 K" in rendered  # action
        assert "operating_temp" in rendered  # context

    def test_actionable_dialog_tolerates_a_flat_error(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A flat CoreValidationError (the resolver's bounds error) shows as the 'what'."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        clone = sensor.clone()
        clone.set(_TEMP, 9999.0)
        with pytest.raises(Exception) as caught:  # noqa: PT011 — checking the dialog, not the type
            clone.get_input(_TEMP)
        dialog = ActionableErrorDialog(caught.value, _TEMP)
        qtbot.addWidget(dialog)
        rendered = "\n".join(lbl.text() for lbl in dialog.findChildren(QLabel))
        assert "out of bounds" in rendered

    def test_explain_dialog_shows_the_explanation(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = ExplainDialog(_TEMP, "line one\nline two")
        qtbot.addWidget(dialog)
        assert dialog.body.toPlainText() == "line one\nline two"

    def test_unexpected_dialog_hides_traceback_until_expanded(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = UnexpectedErrorDialog(RuntimeError("boom"), "Editing x")
        qtbot.addWidget(dialog)
        assert not dialog.details.isVisible()  # folded by default
        assert "RuntimeError" in dialog.details.toPlainText()  # traceback captured
