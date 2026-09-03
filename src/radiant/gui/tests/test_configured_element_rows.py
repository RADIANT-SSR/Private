"""Configured element rows on the Elements tab (Gap 103 v1.1).

The GUI half of the Configuration-Set Expansion plan Phase 2 (§3a-bis, owner-ratified in
the 2026-09-02 live review): an element **row** configures exactly like a parameter. The
tab renders the displayed configuration's effective train; a row menu configures /
un-configures a row through ``ConfigurationSet.configure_element`` /
``unconfigure_element``; a configured row carries the red "C"; and editing one of its
cells writes **that configuration's entry only** (D-8), leaving every other
configuration's entry verbatim.

These are the plan's re-targeted §4c matrix, driven on the real widget (and, where the
contract is the host's, the real window) offscreen. A single-configuration session is
asserted to show none of it and behave exactly as it did before.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtWidgets import QMessageBox, QStyleOptionViewItem  # noqa: E402

from radiant.api.config_set import ConfigurationSet  # noqa: E402
from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.config_scope import ConfigurationScope  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.configure_menu import (  # noqa: E402
    CONFIGURE_TEXT,
    unconfigure_element_text,
)
from radiant.gui.widgets.configured_name_delegate import CONFIGURED_ROLE  # noqa: E402
from radiant.gui.widgets.optical_element_editor import (  # noqa: E402
    OpticalElementEditor,
)

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

_WAIT_MS = 20000  # headroom over a two-configuration evaluate-all pass

# Column indices of the editor's table (the widget's own layout, restated here so a
# column move breaks these tests loudly rather than silently asserting the wrong cell).
_COL_NAME = 0
_COL_VALUE = 3
_COL_TEMP = 4

_MIRROR = "M1"
_FILTER = "band_filter"
_MIRROR_ROW = 0
_FILTER_ROW = 1

_CELL = QRect(0, 0, 220, 20)

_SHARED_TRAIN: list[dict[str, Any]] = [
    {
        "name": _MIRROR,
        "transfer_mode": "REFLECTIVE",
        "reflectance": 0.97,
        "temperature_K": 293.0,
        "diameter_m": 0.3,
        "distance_to_fpa_m": 1.0,
    },
    {
        "name": _FILTER,
        "transfer_mode": "REFRACTIVE",
        "kind": "filter",
        "transmittance": 0.9,
        "temperature_K": 240.0,
        "diameter_m": 0.05,
        "distance_to_fpa_m": 0.05,
    },
]


def _study(*, configure: int | None = None) -> ConfigurationSet:
    """A two-configuration study whose base carries the shared element train.

    ``configure=<row>`` promotes that row to a configured row through the API (the
    scripting half), for the tests whose subject is what the GUI does *with* one.
    """
    base = Sensor.load(_EXAMPLE)
    base.set_optical_elements(_SHARED_TRAIN)
    config_set = ConfigurationSet(base, names=["MWIR", "LWIR"])
    if configure is not None:
        config_set.configure_element(configure)
    return config_set


def _bind(qtbot, config_set: ConfigurationSet | None) -> OpticalElementEditor:  # type: ignore[no-untyped-def]
    """An editor bound to *config_set*'s scope and displayed sensor.

    The displayed sensor is the set's base: in a study the editor reads its train from
    the configuration set (the effective document), and uses the sensor only for the
    coating-detail figure, so a materialization would cost a full resolve for nothing.
    """
    editor = OpticalElementEditor()
    qtbot.addWidget(editor)
    scope = ConfigurationScope()
    scope.bind(config_set)
    editor.set_configuration_scope(scope)
    editor.bind_sensor(config_set.base if config_set is not None else None, {})
    return editor


def _trigger(editor: OpticalElementEditor, row: int, text: str) -> None:
    """Fire the row-menu action labelled *text* — the operator's right-click action."""
    menu = editor.row_menu(row)
    assert menu is not None, "no row menu (not a study?)"
    actions = [action for action in menu.actions() if action.text() == text]
    assert actions, f"no {text!r} action in {[a.text() for a in menu.actions()]}"
    actions[0].trigger()


def _configure_row(editor: OpticalElementEditor, row: int) -> None:
    _trigger(editor, row, CONFIGURE_TEXT)


def _unconfigure_row(editor: OpticalElementEditor, row: int, first: str = "MWIR") -> None:
    _trigger(editor, row, unconfigure_element_text(first))


def _accept(monkeypatch) -> list[str]:  # type: ignore[no-untyped-def]
    """Auto-accept the confirmation dialog, returning the texts it was shown with."""
    shown: list[str] = []

    def _question(_parent: Any, _title: str, text: str, *args: Any, **kwargs: Any) -> Any:
        shown.append(text)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "question", _question)
    return shown


def _badge_rect(editor: OpticalElementEditor, row: int):  # type: ignore[no-untyped-def]
    """Where the red "C" is painted for *row*'s name cell (``None`` when shared)."""
    delegate = editor.name_delegate
    index = editor.table.model().index(row, _COL_NAME)
    option = QStyleOptionViewItem()
    option.rect = _CELL
    delegate.initStyleOption(option, index)
    return delegate.badge_rect(option, index)


class TestSingleConfigurationSessionIsUnchanged:
    """A session with one configuration shows none of this and behaves as before."""

    def test_plain_session_shows_no_study_note_and_no_row_menu(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.load(_EXAMPLE)
        sensor.set_optical_elements(_SHARED_TRAIN)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        assert editor.study_note.isHidden()
        assert editor.row_menu(_FILTER_ROW) is None
        assert editor.table.rowCount() == 2
        assert not editor.is_row_configured(_FILTER_ROW)

    def test_one_configuration_set_offers_no_configure_action(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A degenerate set has no second member to differ from — nothing to configure."""
        base = Sensor.load(_EXAMPLE)
        base.set_optical_elements(_SHARED_TRAIN)
        editor = _bind(qtbot, ConfigurationSet(base))
        assert editor.study_note.isHidden()
        assert editor.row_menu(_FILTER_ROW) is None

    def test_plain_session_apply_is_unchanged(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Zero regression: with no study, Apply is still one set_optical_elements."""
        sensor = Sensor.load(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()  # noqa: SLF001
        assert editor.apply_train()
        document = sensor.optical_elements()
        assert document is not None and len(document) == 1

    def test_apply_lands_on_the_document_not_the_materialization(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A one-member study displays a materialization; the train must reach the set.

        The displayed sensor of any set whose members carry configured values is a
        throwaway ``sensor_for`` materialization, which the next switch or evaluation
        discards. Applying the train to it would silently lose the edit (Rule 17), so
        Apply targets the set's base — the object ``save`` writes.
        """
        base = Sensor.load(_EXAMPLE)
        base.set_optical_elements(_SHARED_TRAIN)
        config_set = ConfigurationSet(base)
        config_set.configure("optics.aperture_diameter_m", [0.3])
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        scope = ConfigurationScope()
        scope.bind(config_set)
        editor.set_configuration_scope(scope)
        editor.bind_sensor(config_set.sensor_for(config_set.active), {})

        editor.table.item(_MIRROR_ROW, _COL_TEMP).setText("275.0")
        assert editor.apply_train()
        shared = config_set.base.optical_elements()
        assert shared is not None
        assert shared[0]["temperature_K"] == pytest.approx(275.0, abs=1e-12)


class TestConfigureRoundTrip:
    """§4c: configure / un-configure a row through the GUI action (D-6 keep-first)."""

    def test_study_shows_the_note_naming_the_displayed_configuration(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = _bind(qtbot, _study())
        assert not editor.study_note.isHidden()
        assert "MWIR" in editor.study_note.text()

    def test_configure_action_seeds_every_configuration(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        config_set = _study()
        editor = _bind(qtbot, config_set)
        _configure_row(editor, _FILTER_ROW)

        assert config_set.is_element_configured(_FILTER_ROW)
        assert config_set.configured_element_indices() == (_FILTER_ROW,)
        # Dense and seeded from the shared entry: promotion changes no result.
        for name in config_set.names():
            entry = config_set.element_for(_FILTER_ROW, name)
            assert entry["name"] == _FILTER
            assert entry["transmittance"] == pytest.approx(0.9, abs=1e-12)
        # The row left the shared document (single store).
        shared = config_set.base.optical_elements()
        assert shared is not None
        assert [entry["name"] for entry in shared] == [_MIRROR]
        assert editor.is_row_configured(_FILTER_ROW)

    def test_configure_marks_the_session_edited(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Configuring writes the document, so the host must hear about it."""
        editor = _bind(qtbot, _study())
        with qtbot.waitSignal(editor.elementsApplied, timeout=1000):
            _configure_row(editor, _FILTER_ROW)

    def test_unconfigure_action_states_the_kept_entry_and_collapses(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        config_set = _study(configure=_FILTER_ROW)
        config_set.set_element_for(
            _FILTER_ROW, "LWIR", dict(_SHARED_TRAIN[1], name="cirrus_filter")
        )
        editor = _bind(qtbot, config_set)
        shown = _accept(monkeypatch)

        _unconfigure_row(editor, _FILTER_ROW)

        assert len(shown) == 1
        # D-6: the confirmation names the configuration whose entry survives and the
        # entries that are discarded.
        assert "MWIR" in shown[0] and _FILTER in shown[0]
        assert "LWIR: cirrus_filter" in shown[0]
        assert not config_set.is_element_configured(_FILTER_ROW)
        shared = config_set.base.optical_elements()
        assert shared is not None
        assert [entry["name"] for entry in shared] == [_MIRROR, _FILTER]
        assert not editor.is_row_configured(_FILTER_ROW)

    def test_cancelling_the_unconfigure_keeps_every_entry(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)
        monkeypatch.setattr(
            QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel
        )

        _unconfigure_row(editor, _FILTER_ROW)

        assert config_set.is_element_configured(_FILTER_ROW)
        assert editor.is_row_configured(_FILTER_ROW)

    def test_an_unapplied_row_cannot_be_configured_yet_and_says_so(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = _bind(qtbot, _study())
        editor._add_mirror.click()  # noqa: SLF001
        menu = editor.row_menu(editor.table.rowCount() - 1)
        assert menu is not None
        action = menu.actions()[0]
        assert action.text() == CONFIGURE_TEXT
        assert not action.isEnabled()
        assert "Apply the train first" in action.toolTip()


class TestConfiguredBadge:
    """§4c: the red "C" marks configured rows, and only those."""

    def test_badge_is_painted_after_the_name_of_a_configured_row_only(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = _bind(qtbot, _study(configure=_FILTER_ROW))

        assert editor.table.item(_FILTER_ROW, _COL_NAME).data(CONFIGURED_ROLE) is True
        assert editor.table.item(_MIRROR_ROW, _COL_NAME).data(CONFIGURED_ROLE) is None
        rect = _badge_rect(editor, _FILTER_ROW)
        assert rect is not None
        assert rect.right() <= _CELL.right()
        assert _badge_rect(editor, _MIRROR_ROW) is None

    def test_badge_tooltip_names_the_configuration_being_edited(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = _bind(qtbot, _study(configure=_FILTER_ROW))
        item = editor.table.item(_FILTER_ROW, _COL_NAME)
        assert item.toolTip().startswith(_FILTER)  # the full value survives
        assert "configured — one entry per configuration" in item.toolTip()
        assert "editing edits MWIR only" in item.toolTip()

    def test_a_configured_row_keeps_its_editable_name_cell(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The name is part of the entry, so it configures with the row — and is typed."""
        editor = _bind(qtbot, _study(configure=_FILTER_ROW))
        item = editor.table.item(_FILTER_ROW, _COL_NAME)
        assert item.flags() & Qt.ItemFlag.ItemIsEditable
        index = editor.table.model().index(_FILTER_ROW, _COL_NAME)
        option = QStyleOptionViewItem()
        option.rect = _CELL
        widget = editor.name_delegate.createEditor(editor.table.viewport(), option, index)
        assert widget is not None

    def test_value_cells_still_tooltip_their_full_text(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = _bind(qtbot, _study(configure=_FILTER_ROW))
        item = editor.table.item(_FILTER_ROW, _COL_VALUE)
        assert item.toolTip() == item.text() == "0.9"

    def test_the_eps_column_keeps_its_rule_5_tooltip(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = _bind(qtbot, _study())
        assert "Kirchhoff" in editor.table.item(_FILTER_ROW, 7).toolTip()


class TestInlineEditRouting:
    """§4c: D-8 — an edit lands on the displayed configuration, or on the shared row."""

    def test_editing_a_configured_row_edits_the_displayed_configuration_only(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)
        editor.table.item(_FILTER_ROW, _COL_VALUE).setText("0.55")
        assert editor.apply_train()

        assert config_set.element_for(_FILTER_ROW, "MWIR")["transmittance"] == pytest.approx(
            0.55, abs=1e-12
        )
        # The other configuration's entry is verbatim.
        assert config_set.element_for(_FILTER_ROW, "LWIR")["transmittance"] == pytest.approx(
            0.9, abs=1e-12
        )
        assert config_set.effective_optical_elements("LWIR")[1]["transmittance"] == pytest.approx(
            0.9, abs=1e-12
        )

    def test_editing_a_name_on_a_configured_row_is_per_configuration(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Row identity is positional: the name configures with the row."""
        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)
        editor.table.item(_FILTER_ROW, _COL_NAME).setText("filter_b02")
        assert editor.apply_train()

        assert config_set.element_for(_FILTER_ROW, "MWIR")["name"] == "filter_b02"
        assert config_set.element_for(_FILTER_ROW, "LWIR")["name"] == _FILTER

    def test_editing_a_shared_row_edits_the_shared_document(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)
        editor.table.item(_MIRROR_ROW, _COL_TEMP).setText("275.0")
        assert editor.apply_train()

        shared = config_set.base.optical_elements()
        assert shared is not None
        assert [entry["name"] for entry in shared] == [_MIRROR]
        assert shared[0]["temperature_K"] == pytest.approx(275.0, abs=1e-12)
        # Every configuration inherits it, and no configured entry was disturbed.
        for name in config_set.names():
            effective = config_set.effective_optical_elements(name)
            assert effective is not None
            assert effective[0]["temperature_K"] == pytest.approx(275.0, abs=1e-12)
            assert effective[1]["transmittance"] == pytest.approx(0.9, abs=1e-12)

    def test_an_unedited_apply_changes_nothing(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(configure=_FILTER_ROW)
        before = {name: config_set.effective_optical_elements(name) for name in config_set.names()}
        editor = _bind(qtbot, config_set)
        assert editor.apply_train()
        for name in config_set.names():
            assert config_set.effective_optical_elements(name) == before[name]

    def test_an_invalid_entry_names_the_configuration_and_stores_nothing(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)
        editor.table.item(_FILTER_ROW, _COL_VALUE).setText("no_such_filter.csv")
        editor.table.item(_MIRROR_ROW, _COL_TEMP).setText("275.0")

        from radiant.gui.widgets import optical_element_editor as oee

        shown: list[Any] = []
        monkeypatch.setattr(
            oee.ActionableErrorDialog,
            "__init__",
            lambda self, exc, path, parent=None: shown.append(exc) or None,
        )
        monkeypatch.setattr(oee, "exec_dialog", lambda dialog: 0)

        assert not editor.apply_train()
        assert len(shown) == 1
        assert "MWIR" in str(shown[0])
        # Nothing was written — not even the valid shared row ahead of the bad one.
        assert config_set.element_for(_FILTER_ROW, "MWIR")["transmittance"] == pytest.approx(
            0.9, abs=1e-12
        )
        assert config_set.base.optical_elements()[0]["temperature_K"] == pytest.approx(
            293.0, abs=1e-12
        )


class TestSharedStructure:
    """§3a-bis: row count and order are shared — add / remove change every member."""

    def test_adding_a_row_seeds_it_shared_for_every_configuration(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)
        editor._add_mirror.click()  # noqa: SLF001
        assert editor.apply_train()

        assert config_set.element_count() == 3
        assert config_set.configured_element_indices() == (_FILTER_ROW,)
        for name in config_set.names():
            effective = config_set.effective_optical_elements(name)
            assert effective is not None
            assert [entry["name"] for entry in effective] == [_MIRROR, _FILTER, "mirror"]

    def test_removing_a_configured_row_confirms_then_drops_every_entry(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)
        shown = _accept(monkeypatch)

        editor.table.setCurrentCell(_FILTER_ROW, _COL_NAME)
        editor._remove.click()  # noqa: SLF001
        assert editor.apply_train()

        assert len(shown) == 1
        assert "MWIR: band_filter" in shown[0] and "LWIR: band_filter" in shown[0]
        assert config_set.configured_element_indices() == ()
        assert config_set.element_count() == 1
        for name in config_set.names():
            effective = config_set.effective_optical_elements(name)
            assert effective is not None
            assert [entry["name"] for entry in effective] == [_MIRROR]

    def test_cancelling_the_removal_keeps_the_row(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)
        monkeypatch.setattr(
            QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel
        )
        editor.table.setCurrentCell(_FILTER_ROW, _COL_NAME)
        editor._remove.click()  # noqa: SLF001
        assert editor.table.rowCount() == 2
        assert config_set.is_element_configured(_FILTER_ROW)

    def test_a_structure_edit_that_would_shift_a_configured_row_is_refused(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A configured row keeps its position, so the affordance says so up front."""
        editor = _bind(qtbot, _study(configure=_FILTER_ROW))
        editor.table.setCurrentCell(_MIRROR_ROW, _COL_NAME)
        assert not editor._remove.isEnabled()  # noqa: SLF001
        assert "row 1" in editor._remove.toolTip()  # noqa: SLF001
        assert "Un-configure" in editor._remove.toolTip()  # noqa: SLF001
        assert not editor._down.isEnabled()  # noqa: SLF001

        editor.table.setCurrentCell(_FILTER_ROW, _COL_NAME)
        assert editor._remove.isEnabled()  # noqa: SLF001 — the last row shifts nothing
        assert not editor._up.isEnabled()  # noqa: SLF001 — moving it would shift it

    def test_structure_edits_are_free_while_no_row_is_configured(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = _bind(qtbot, _study())
        editor.table.setCurrentCell(_MIRROR_ROW, _COL_NAME)
        assert editor._remove.isEnabled()  # noqa: SLF001
        assert editor._down.isEnabled()  # noqa: SLF001


class TestCoatingDetail:
    """§4c: the coating-detail pane shows the displayed configuration's entry."""

    def test_detail_pane_reads_the_displayed_members_entry(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from matplotlib.figure import Figure

        config_set = _study(configure=_FILTER_ROW)
        config_set.set_element_for(_FILTER_ROW, "MWIR", dict(_SHARED_TRAIN[1], transmittance=0.55))
        editor = _bind(qtbot, config_set)
        editor.show()

        from radiant.gui.widgets import optical_element_editor as oee

        seen: list[dict[str, Any]] = []

        def _capture(sensor: Any, name: str, *, entries: Any = None, **kwargs: Any) -> Figure:
            seen.append({"name": name, "entries": entries})
            return Figure()

        monkeypatch.setattr(oee, "plot_coating_detail", _capture)
        editor.table.setCurrentCell(_FILTER_ROW, _COL_NAME)
        editor.refresh_coating_detail()

        assert seen[-1]["name"] == _FILTER
        entry = next(e for e in seen[-1]["entries"] if e["name"] == _FILTER)
        assert entry["transmittance"] == pytest.approx(0.55, abs=1e-12)


class TestRoundTrip:
    """§4c: a GUI-configured row survives save/load through the io element document."""

    def test_gui_configured_row_round_trips(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        config_set = _study()
        editor = _bind(qtbot, config_set)
        _configure_row(editor, _FILTER_ROW)
        editor.table.item(_FILTER_ROW, _COL_TEMP).setText("120.0")
        assert editor.apply_train()

        path = tmp_path / "authored_study.yaml"
        config_set.save(path)
        reloaded = ConfigurationSet.load(path)

        assert reloaded.configured_element_indices() == (_FILTER_ROW,)
        assert reloaded.element_for(_FILTER_ROW, "MWIR")["temperature_K"] == pytest.approx(
            120.0, abs=1e-12
        )
        assert reloaded.element_for(_FILTER_ROW, "LWIR")["temperature_K"] == pytest.approx(
            240.0, abs=1e-12
        )
        effective = reloaded.effective_optical_elements("MWIR")
        assert effective is not None
        assert effective[0]["temperature_K"] == pytest.approx(293.0, abs=1e-12)

        # And the reloaded document renders the same way in a fresh editor.
        reopened = _bind(qtbot, reloaded)
        assert reopened.is_row_configured(_FILTER_ROW)
        assert not reopened.is_row_configured(_MIRROR_ROW)


class TestHostReRendersOnSwitch:
    """The window re-renders the tab for the newly displayed configuration."""

    def test_switching_configuration_shows_that_configurations_entry(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(configure=_FILTER_ROW)
        config_set.set_element_for(_FILTER_ROW, "LWIR", dict(_SHARED_TRAIN[1], transmittance=0.55))
        path = tmp_path / "elements_study.yaml"
        config_set.save(path)
        window = RADIANTMainWindow(config_set=ConfigurationSet.load(path), path=str(path))
        qtbot.addWidget(window)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            pass
        editor = window.central_canvas.stage_center.pane("optics").element_editor
        assert editor is not None
        assert not editor.study_note.isHidden()
        assert editor.is_row_configured(_FILTER_ROW)
        assert editor.entries()[_FILTER_ROW]["transmittance"] == pytest.approx(0.9, abs=1e-12)

        window.configuration_bar.buttons[1].click()

        assert "LWIR" in editor.study_note.text()
        assert editor.entries()[_FILTER_ROW]["transmittance"] == pytest.approx(0.55, abs=1e-12)
