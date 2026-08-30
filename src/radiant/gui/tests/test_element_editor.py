"""Tests for the Optics element-train editor (GUI Capability Expansion plan GS-4).

The Elements tab is the ADR-0009 D2 declarative-document editor: table rows ⇌ the
``optical_elements`` entry dicts, *Apply* commits through exactly one
``Sensor.set_optical_elements`` call (io-parser validation, Kirchhoff checks), the ε
column is **derived read-only** (Rule 5), and the attached train persists through
``Sensor.save`` (D4). Tests drive the real widget on the shipped example config,
offscreen.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.stage_views import STAGE_COMPOSITIONS  # noqa: E402
from radiant.gui.widgets.optical_element_editor import (  # noqa: E402
    ELEMENT_EDIT_PATH,
    OpticalElementEditor,
)
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


class TestComposition:
    def test_optics_declares_elements_tab(self) -> None:
        spec = STAGE_COMPOSITIONS["optics"]
        titles = [sub.title for sub in spec.subviews]
        assert "Elements" in titles
        elements_tab = spec.subviews[titles.index("Elements")]
        assert elements_tab.element_editor

    def test_pane_mounts_editor(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        pane = StagePane("optics", STAGE_COMPOSITIONS["optics"])
        qtbot.addWidget(pane)
        pane.bind_sensor(sensor, {})
        assert pane.element_editor is not None


class TestEditorRoundTrip:
    def test_add_apply_attaches_document_and_derives_epsilon(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The GS-4 checkpoint: author a train, Apply once, ε shows derived (1−R)."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})

        editor._add_mirror.click()
        editor._add_mirror.click()
        editor._add_refractive.click()
        assert editor.table.rowCount() == 3

        with qtbot.waitSignal(editor.elementsApplied, timeout=5000) as blocker:
            assert editor.apply_train()
        assert blocker.args == [ELEMENT_EDIT_PATH]

        document = sensor.optical_elements()
        assert document is not None and len(document) == 3
        # Rule 5: the epsilon column shows the Kirchhoff-derived value (1 - 0.97).
        assert editor.table.item(0, 7) is not None
        assert editor.table.item(0, 7).text() == "0.0300"
        # The epsilon cell is read-only.
        from PySide6.QtCore import Qt

        assert not (editor.table.item(0, 7).flags() & Qt.ItemFlag.ItemIsEditable)

    def test_applied_train_runs_full_prescription_and_changes_results(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        baseline = _evaluate(sensor.clone())
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        editor._add_refractive.click()
        assert editor.apply_train()

        result = _evaluate(sensor)
        assert result.stage_outputs["optics"]["transmission_input_mode"] == "full_prescription"
        assert result.metrics["snr"] != baseline.metrics["snr"]

    def test_bind_reloads_attached_document(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements(
            [
                {
                    "name": "M1",
                    "transfer_mode": "REFLECTIVE",
                    "reflectance": 0.95,
                    "temperature_K": 280.0,
                    "diameter_m": 0.3,
                    "distance_to_fpa_m": 1.0,
                }
            ]
        )
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        assert editor.table.rowCount() == 1
        assert editor.table.item(0, 0).text() == "M1"
        entries = editor.entries()
        assert entries[0]["reflectance"] == pytest.approx(0.95, abs=1e-12)

    def test_empty_table_apply_detaches_document(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements(
            [
                {
                    "name": "M1",
                    "transfer_mode": "REFLECTIVE",
                    "reflectance": 0.95,
                    "temperature_K": 280.0,
                    "diameter_m": 0.3,
                    "distance_to_fpa_m": 1.0,
                }
            ]
        )
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor.table.removeRow(0)
        assert editor.apply_train()
        assert sensor.optical_elements() is None

    def test_invalid_document_never_touches_sensor(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """A parser rejection shows the actionable dialog; the sensor keeps its train."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        # Blank the R/T value: the io parser rejects a non-numeric non-path field.
        editor.table.item(0, 3).setText("")

        from radiant.gui.widgets import optical_element_editor as oee

        shown: list[str] = []
        monkeypatch.setattr(
            oee.ActionableErrorDialog, "exec", lambda self: shown.append("shown") or 0
        )
        assert not editor.apply_train()
        assert shown == ["shown"]
        assert sensor.optical_elements() is None

    def test_save_load_round_trip_preserves_authored_train(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """ADR-0009 D4 through the GUI editor: Apply → save → load → table repopulates."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        editor._add_refractive.click()
        assert editor.apply_train()

        path = tmp_path / "train.yaml"
        sensor.save(path)
        reloaded = Sensor.load(path)

        editor2 = OpticalElementEditor()
        qtbot.addWidget(editor2)
        editor2.bind_sensor(reloaded, {})
        assert editor2.table.rowCount() == 2
        assert _evaluate(reloaded).metrics["snr"] == pytest.approx(
            _evaluate(sensor).metrics["snr"], rel=1e-12
        )


class TestKindColumn:
    """Kind is a refractive-only descriptive label; reflective rows lock to mirror."""

    def test_reflective_row_locks_kind_to_mirror(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(Sensor.from_yaml(_EXAMPLE), {})
        editor._add_mirror.click()
        kind = editor.table.cellWidget(0, 2)
        assert kind.currentText() == "mirror"
        assert not kind.isEnabled()

    def test_switching_to_refractive_frees_kind(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(Sensor.from_yaml(_EXAMPLE), {})
        editor._add_mirror.click()
        transfer = editor.table.cellWidget(0, 1)
        transfer.setCurrentText("REFRACTIVE")
        kind = editor.table.cellWidget(0, 2)
        assert kind.isEnabled()
        assert kind.currentText() != "mirror"
        # entries() carries kind for the refractive row only.
        entry = editor.entries()[0]
        assert entry["kind"] == kind.currentText()


class TestCoatingDetail:
    """Gap 116: selecting a row draws that element's coating model."""

    def test_no_selection_shows_prompt(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(Sensor.from_yaml(_EXAMPLE), {})
        assert editor.detail_message.isVisible() or not editor.detail_canvas.isVisible()
        assert "Select an element" in editor.detail_message.text()

    def test_selecting_a_row_renders_the_detail_figure(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.show()
        editor.bind_sensor(Sensor.from_yaml(_EXAMPLE), {})
        editor._add_mirror.click()
        editor.table.setCurrentCell(0, 0)
        editor.refresh_coating_detail()
        assert editor.detail_canvas.isVisible()
        assert not editor.detail_message.isVisible()

    def test_draft_row_previews_before_apply(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The detail reads the table (entries= override), not the applied document."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.show()
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        assert sensor.optical_elements() is None  # nothing applied yet
        editor.table.setCurrentCell(0, 0)
        editor.refresh_coating_detail()
        assert editor.detail_canvas.isVisible()

    def test_unparsable_draft_shows_actionable_message(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.show()
        editor.bind_sensor(Sensor.from_yaml(_EXAMPLE), {})
        editor._add_mirror.click()
        editor.table.item(0, 3).setText("no_such_coating.csv")
        editor.table.setCurrentCell(0, 0)
        editor.refresh_coating_detail()
        assert not editor.detail_canvas.isVisible()
        assert "not found" in editor.detail_message.text()
