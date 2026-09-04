"""Tests for the Optics element-train editor (GUI Capability Expansion plan GS-4).

The Elements tab is the ADR-0009 D2 declarative-document editor: table rows ⇌ the
``optical_elements`` entry dicts, the ε column is **derived read-only** (Rule 5), and
the attached train persists through ``Sensor.save`` (D4). Tests drive the real widget on
the shipped example config, offscreen.

**Commit-on-edit (owner-ratified 2026-09-03).** There is no *Apply train* button: every
completed edit — a cell, a combo, a CSV pick, a spectrum, Add, Remove, reorder — commits
through one ``Sensor.set_optical_elements`` call as it is made (io-parser validation,
Kirchhoff checks). A row that does not validate is held as a visible **pending draft**
with the parser's message inline — no modal, nothing stored — and commits on the next
edit that validates. These tests assert the commit at edit time; the internal
``apply_train`` routine every handler routes through is exercised only where a test needs
the return value.
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
    def test_added_rows_commit_immediately_and_derive_epsilon(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The GS-4 checkpoint, commit-on-edit: each Add lands, ε shows derived (1−R)."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})

        editor._add_mirror.click()
        # The first Add is already in the document — no Apply, nothing held back.
        assert sensor.optical_elements() is not None
        editor._add_mirror.click()
        with qtbot.waitSignal(editor.elementsApplied, timeout=5000) as blocker:
            editor._add_refractive.click()
        assert blocker.args == [ELEMENT_EDIT_PATH]
        assert editor.table.rowCount() == 3

        document = sensor.optical_elements()
        assert document is not None and len(document) == 3
        # Rule 5: the epsilon column shows the Kirchhoff-derived value (1 - 0.97).
        assert editor.table.item(0, 7) is not None
        assert editor.table.item(0, 7).text() == "0.0300"
        # The epsilon cell is read-only.
        from PySide6.QtCore import Qt

        assert not (editor.table.item(0, 7).flags() & Qt.ItemFlag.ItemIsEditable)

    def test_committed_train_runs_full_prescription_and_changes_results(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        baseline = _evaluate(sensor.clone())
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        editor._add_refractive.click()

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

    def test_removing_the_last_row_detaches_the_document(self, qtbot) -> None:  # type: ignore[no-untyped-def]
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
        editor._remove.click()  # the row lands selected; Remove commits at once
        assert editor.table.rowCount() == 0
        assert sensor.optical_elements() is None

    def test_save_load_round_trip_preserves_authored_train(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """ADR-0009 D4 through the GUI editor: author → save → load → table repopulates."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        editor._add_refractive.click()

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


class TestCommitOnEdit:
    """Owner-ratified 2026-09-03: the tab commits like every other parameter surface.

    The model this replaces held drafts that looked committed — the owner edited
    0.97 → 0.5, saw no SNR change, and lost the edit on navigation. Every test here
    asserts the write happened *at edit time*, with no Apply anywhere.
    """

    def test_no_apply_affordance_remains(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from PySide6.QtWidgets import QPushButton

        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(Sensor.from_yaml(_EXAMPLE), {})
        labels = [b.text() for b in editor.findChildren(QPushButton)]
        assert not any("Apply" in label for label in labels), labels
        assert not hasattr(editor, "apply_button")

    def test_cell_edit_commits_the_document(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()

        with qtbot.waitSignal(editor.elementsApplied, timeout=5000):
            editor.table.item(0, 3).setText("0.5")

        document = sensor.optical_elements()
        assert document is not None
        assert document[0]["reflectance"] == pytest.approx(0.5, abs=1e-12)

    def test_transfer_combo_change_commits(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        editor.table.cellWidget(0, 1).setCurrentText("REFRACTIVE")

        document = sensor.optical_elements()
        assert document is not None
        assert document[0]["transfer_mode"] == "REFRACTIVE"
        assert "transmittance" in document[0]

    def test_invalid_row_is_a_pending_draft_and_the_next_edit_commits_it(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """No modal, nothing stored, the draft stays — and it commits when it validates."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.show()
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        committed = sensor.optical_elements()
        assert committed is not None

        from radiant.gui.widgets import optical_element_editor as oee

        shown: list[str] = []
        monkeypatch.setattr(oee, "exec_dialog", lambda dialog: shown.append("modal") or 0)

        # Blank the R/T value: the io parser rejects a non-numeric, non-path field.
        editor.table.item(0, 3).setText("")

        assert shown == []  # never a modal per keystroke
        assert editor.pending_message
        assert "Not committed" in editor.pending_message
        assert "discards the invalid draft" in editor.pending_message
        assert editor.detail_message.isVisible()
        assert editor.detail_message.property("state") == "pending"
        assert editor.table.item(0, 3).text() == ""  # the draft is still on screen
        assert sensor.optical_elements() == committed  # nothing stored

        editor.table.item(0, 3).setText("0.6")

        assert not editor.pending_message
        assert editor.detail_message.property("state") == "normal"
        document = sensor.optical_elements()
        assert document is not None
        assert document[0]["reflectance"] == pytest.approx(0.6, abs=1e-12)
        assert shown == []

    def test_navigation_away_discards_only_the_invalid_draft(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A re-bind (the host's re-render) drops a pending draft — never a valid edit."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        editor.table.item(0, 4).setText("250.0")  # valid: committed on the spot
        editor.table.item(0, 3).setText("")  # invalid: held

        editor.bind_sensor(sensor, {})  # the operator navigates away and back

        assert not editor.pending_message
        assert editor.table.item(0, 3).text() == "0.97"  # the draft is gone
        document = sensor.optical_elements()
        assert document is not None
        assert document[0]["temperature_K"] == pytest.approx(250.0, abs=1e-12)

    def test_csv_pick_commits_and_a_bad_csv_pends(self, qtbot, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets import optical_element_editor as oee

        csv = tmp_path / "coating.csv"
        csv.write_text("3.0,0.8\n5.0,0.9\n", encoding="utf-8")
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        editor.table.setCurrentCell(0, 3)

        monkeypatch.setattr(
            oee.QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *a, **k: (str(csv), "CSV files (*.csv)")),
        )
        editor._browse.click()

        document = sensor.optical_elements()
        assert document is not None
        assert str(document[0]["reflectance"]).endswith("coating.csv")

        shown: list[str] = []
        monkeypatch.setattr(oee, "exec_dialog", lambda dialog: shown.append("modal") or 0)
        missing = tmp_path / "no_such_coating.csv"
        monkeypatch.setattr(
            oee.QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *a, **k: (str(missing), "CSV files (*.csv)")),
        )
        editor._browse.click()

        assert shown == []  # a bad pick pends, it does not pop a dialog
        assert "not found" in editor.pending_message
        assert editor.table.item(0, 3).text() == str(missing)  # the pick is still shown
        assert sensor.optical_elements() == document  # nothing stored

    def test_programmatic_reload_does_not_commit(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """No commit storm: re-rendering the table is not an edit (the ε refill included)."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        editor._add_refractive.click()

        calls: list[object] = []
        original = sensor.set_optical_elements
        monkeypatch.setattr(
            sensor,
            "set_optical_elements",
            lambda entries: calls.append(entries) or original(entries),
        )

        editor.bind_sensor(sensor, {})  # a full re-render: rows, ε column, badges
        editor.table.selectRow(1)  # selection-driven refreshes are not edits either

        assert calls == []

    def test_reorder_commits_the_new_order(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        editor._add_refractive.click()
        editor.table.setCurrentCell(1, 0)
        editor._up.click()

        document = sensor.optical_elements()
        assert document is not None
        assert [entry["name"] for entry in document] == ["element", "mirror"]
        assert [editor.table.item(row, 0).text() for row in range(2)] == ["element", "mirror"]

    def test_one_edit_is_one_commit(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()

        calls: list[object] = []
        original = sensor.set_optical_elements
        monkeypatch.setattr(
            sensor,
            "set_optical_elements",
            lambda entries: calls.append(entries) or original(entries),
        )
        editor.table.item(0, 4).setText("250.0")

        assert len(calls) == 1


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

    def test_draft_row_previews_from_the_table(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The detail reads the table (entries= override), not the stored document.

        With commit-on-edit the two agree the instant an edit lands, so the override is
        shown to still be the source by pending an *invalid* row and typing a valid value
        into another cell: the figure follows the table.
        """
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.show()
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        editor.table.setCurrentCell(0, 0)
        editor.refresh_coating_detail()
        assert editor.detail_canvas.isVisible()

        editor.table.item(0, 0).setText("gold_M1")  # renamed in the table and committed
        editor.refresh_coating_detail()
        assert editor.detail_canvas.isVisible()
        assert sensor.optical_elements()[0]["name"] == "gold_M1"

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


class TestEntryFaithfulness:
    """CU-344: a commit round-trips every entry byte-faithfully.

    The tab has seven columns and the element schema has many more keys, so serializing
    the *rendering* rewrites every row on every commit: it invents the keys the columns
    default, drops the keys no column shows, and rewrites the case of the ones it does.
    The measured consequence was an edit to one row changing the physics of rows the
    operator never touched (SNR 220.5 [-] vs 58.5 [-] on the same authored study). The
    fix carries each row's source entry and overlays only the cells the table owns; these
    tests pin that, so a new column or key can never silently reintroduce the rewrite.
    """

    # A deliberately minimal document: no geometry keys at all, a refractive row that
    # carries a `reflectance` the table has no column for, and an upper-case `kind`.
    _MINIMAL: list[dict[str, object]] = [
        {"name": "M1", "transfer_mode": "REFLECTIVE", "reflectance": 0.97},
        {"name": "M2", "transfer_mode": "REFLECTIVE", "reflectance": 0.97},
        {
            "name": "band_filter",
            "transfer_mode": "REFRACTIVE",
            "kind": "FILTER",
            "transmittance": 0.9,
            "reflectance": 0.02,
            "temperature_K": 240.0,
        },
    ]

    @staticmethod
    def _bound(qtbot, document: list[dict[str, object]]):  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements([dict(entry) for entry in document])
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        return sensor, editor

    def test_absent_keys_render_as_empty_cells(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """No invented 0.1 / 1.0 / 293.0 — an unspecified key is a blank cell."""
        _sensor, editor = self._bound(qtbot, self._MINIMAL)
        for row in range(3):
            assert editor.table.item(row, 5).text() == ""  # Diam (m)
            assert editor.table.item(row, 6).text() == ""  # →FPA (m)
        assert editor.table.item(0, 4).text() == ""  # T (K), unspecified on the mirrors
        assert editor.table.item(2, 4).text() == "240.0"  # …and shown where it is authored

    def test_rendering_the_table_round_trips_the_document(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Render → serialize with no edit at all is the identity on every entry."""
        _sensor, editor = self._bound(qtbot, self._MINIMAL)
        assert editor.entries() == self._MINIMAL

    def test_one_row_edit_leaves_every_other_row_byte_identical(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The CU-344 pin: an edit to row 1 touches row 1's edited key and nothing else."""
        sensor, editor = self._bound(qtbot, self._MINIMAL)
        editor.table.item(1, 3).setText("0.5")  # M2's reflectance

        committed = sensor.optical_elements()
        assert committed is not None and len(committed) == 3
        assert committed[0] == self._MINIMAL[0]
        assert committed[2] == self._MINIMAL[2]
        expected = dict(self._MINIMAL[1]) | {"reflectance": 0.5}
        assert committed[1] == expected

    def test_a_refractive_rows_reflectance_survives_an_edit_to_it(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The key with no column rides through the row's *own* edit untouched."""
        sensor, editor = self._bound(qtbot, self._MINIMAL)
        editor.table.item(2, 4).setText("250.0")

        committed = sensor.optical_elements()
        assert committed is not None
        assert committed[2] == dict(self._MINIMAL[2]) | {"temperature_K": 250.0}

    def test_kind_case_is_not_rewritten_as_a_side_effect(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """``kind: FILTER`` stays ``FILTER`` — the combo spells it, the document owns it."""
        sensor, editor = self._bound(qtbot, self._MINIMAL)
        editor.table.item(0, 3).setText("0.5")

        committed = sensor.optical_elements()
        assert committed is not None
        assert committed[2]["kind"] == "FILTER"

    def test_choosing_a_different_kind_writes_the_combo_spelling(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Case preservation is not case *pinning*: a real choice writes its own text."""
        from PySide6.QtWidgets import QComboBox

        sensor, editor = self._bound(qtbot, self._MINIMAL)
        kind = editor.table.cellWidget(2, 2)
        assert isinstance(kind, QComboBox)
        kind.setCurrentText("window")

        committed = sensor.optical_elements()
        assert committed is not None
        assert committed[2]["kind"] == "window"

    def test_typing_into_an_empty_cell_writes_the_key(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A blank cell writes nothing; a value typed into it is a real edit."""
        sensor, editor = self._bound(qtbot, self._MINIMAL)
        editor.table.item(0, 5).setText("0.3")  # Diam (m), previously unspecified

        committed = sensor.optical_elements()
        assert committed is not None
        assert committed[0] == dict(self._MINIMAL[0]) | {"diameter_m": 0.3}
        assert "diameter_m" not in committed[1]

    def test_clearing_a_cell_removes_the_key(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor, editor = self._bound(qtbot, self._MINIMAL)
        editor.table.item(2, 4).setText("")  # clear the filter's temperature

        committed = sensor.optical_elements()
        assert committed is not None
        assert "temperature_K" not in committed[2]

    def test_a_transfer_flip_retires_the_old_modes_value_key(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The one deliberate deletion: a flip is an operator act, not a side effect."""
        from PySide6.QtWidgets import QComboBox

        sensor, editor = self._bound(qtbot, self._MINIMAL)
        transfer = editor.table.cellWidget(2, 1)
        assert isinstance(transfer, QComboBox)
        transfer.setCurrentText("REFLECTIVE")

        committed = sensor.optical_elements()
        assert committed is not None
        flipped = committed[2]
        assert flipped["transfer_mode"] == "REFLECTIVE"
        assert flipped["reflectance"] == pytest.approx(0.9, abs=1e-12)  # the value cell
        assert "transmittance" not in flipped
        assert "kind" not in flipped

    def test_an_unknown_schema_key_rides_through(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Any key the table has no column for survives — not just today's schema."""
        document = [dict(self._MINIMAL[0]) | {"provenance_note": "vendor coating run 7"}]
        sensor, editor = self._bound(qtbot, document)
        editor.table.item(0, 3).setText("0.5")

        committed = sensor.optical_elements()
        assert committed is not None
        assert committed[0]["provenance_note"] == "vendor coating run 7"
