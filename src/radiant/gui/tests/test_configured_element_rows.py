"""Configured element rows on the Elements tab (Gap 103 v1.1).

The GUI half of the Configuration-Set Expansion plan Phase 2 (§3a-bis, owner-ratified in
the 2026-09-02 live review): an element **row** configures exactly like a parameter. The
tab renders the displayed configuration's effective train; a row menu configures /
un-configures a row through ``ConfigurationSet.configure_element`` /
``unconfigure_element``; a configured row carries the red "C"; and editing one of its
cells writes **that configuration's entry only** (D-8), leaving every other
configuration's entry verbatim.

**Commit-on-edit (owner-ratified 2026-09-03).** The tab has no Apply: every edit below
commits as it is made, in a study exactly as in a single-configuration session, so each
test asserts the document *immediately after the edit*. A row that does not validate is a
held pending draft with the parser's message inline — naming the configuration when the
row is configured — not a modal.

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

    def test_plain_session_commit_is_unchanged(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Zero regression: with no study, an edit is still one set_optical_elements."""
        sensor = Sensor.load(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()  # noqa: SLF001
        document = sensor.optical_elements()
        assert document is not None and len(document) == 1

    def test_commit_lands_on_the_document_not_the_materialization(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A one-member study displays a materialization; the train must reach the set.

        The displayed sensor of any set whose members carry configured values is a
        throwaway ``sensor_for`` materialization, which the next switch or evaluation
        discards. Committing the train to it would silently lose the edit (Rule 17), so
        the commit targets the set's base — the object ``save`` writes.
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

    def test_an_added_row_is_in_the_document_and_configurable_at_once(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Commit-on-edit retires the unapplied-row limbo state (2026-09-03).

        The Add templates are complete valid entries, so the append commits; the row is
        therefore a row of the document immediately, and the configure action is live on
        it — no "Apply the train first" hint, because there is no Apply.
        """
        config_set = _study()
        editor = _bind(qtbot, config_set)
        editor._add_mirror.click()  # noqa: SLF001
        new_row = editor.table.rowCount() - 1

        assert config_set.element_count() == 3
        menu = editor.row_menu(new_row)
        assert menu is not None
        action = menu.actions()[0]
        assert action.text() == CONFIGURE_TEXT
        assert action.isEnabled()

        action.trigger()
        assert config_set.is_element_configured(new_row)
        assert editor.is_row_configured(new_row)


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
    """§4c: D-8 — an edit lands on the displayed configuration, or on the shared row.

    Commit-on-edit (2026-09-03): each edit below is asserted *without* any Apply.
    """

    def test_editing_a_configured_row_edits_the_displayed_configuration_only(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)
        editor.table.item(_FILTER_ROW, _COL_VALUE).setText("0.55")

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

        assert config_set.element_for(_FILTER_ROW, "MWIR")["name"] == "filter_b02"
        assert config_set.element_for(_FILTER_ROW, "LWIR")["name"] == _FILTER

    def test_editing_a_shared_row_edits_the_shared_document(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)
        editor.table.item(_MIRROR_ROW, _COL_TEMP).setText("275.0")

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

    def test_binding_and_rendering_write_nothing(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """No commit storm: a re-render is not an edit, in a study either."""
        config_set = _study(configure=_FILTER_ROW)
        before = {name: config_set.effective_optical_elements(name) for name in config_set.names()}
        editor = _bind(qtbot, config_set)

        writes: list[str] = []
        monkeypatch.setattr(
            type(config_set),
            "set_element_for",
            lambda self, *a, **k: writes.append("element_for"),
        )
        monkeypatch.setattr(
            type(config_set.base),
            "set_optical_elements",
            lambda self, *a, **k: writes.append("shared"),
        )

        editor.bind_sensor(config_set.base, {})  # the host's re-render on a switch
        editor.table.selectRow(_MIRROR_ROW)

        assert writes == []
        for name in config_set.names():
            assert config_set.effective_optical_elements(name) == before[name]

    def test_an_invalid_entry_pends_naming_the_configuration_and_stores_nothing(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """§3a-bis commit-on-edit: a bad configured entry is held, not modal, not stored."""
        from radiant.gui.widgets import optical_element_editor as oee

        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)

        shown: list[Any] = []
        monkeypatch.setattr(oee, "exec_dialog", lambda dialog: shown.append("modal") or 0)

        editor.table.item(_FILTER_ROW, _COL_VALUE).setText("no_such_filter.csv")

        assert shown == []  # a draft that does not validate is never a modal
        assert "MWIR" in editor.pending_message  # the API's message names the member
        assert "Not committed" in editor.pending_message
        assert config_set.element_for(_FILTER_ROW, "MWIR")["transmittance"] == pytest.approx(
            0.9, abs=1e-12
        )

        # A second edit while the draft is pending stores nothing either — not even this
        # valid shared row, because the train as a whole does not validate.
        editor.table.item(_MIRROR_ROW, _COL_TEMP).setText("275.0")
        assert editor.pending_message
        assert config_set.base.optical_elements()[0]["temperature_K"] == pytest.approx(
            293.0, abs=1e-12
        )

        # The edit that makes the train valid commits both changes at once.
        editor.table.item(_FILTER_ROW, _COL_VALUE).setText("0.55")

        assert not editor.pending_message
        assert shown == []
        assert config_set.element_for(_FILTER_ROW, "MWIR")["transmittance"] == pytest.approx(
            0.55, abs=1e-12
        )
        assert config_set.element_for(_FILTER_ROW, "LWIR")["transmittance"] == pytest.approx(
            0.9, abs=1e-12
        )
        assert config_set.base.optical_elements()[0]["temperature_K"] == pytest.approx(
            275.0, abs=1e-12
        )

    def test_a_value_the_parser_cannot_resolve_pends_until_it_is_retyped(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The mid-restructure case on a shared row: held in the table, then committed."""
        config_set = _study()
        editor = _bind(qtbot, config_set)
        editor.table.item(_MIRROR_ROW, _COL_VALUE).setText("mirror_coating.csv")
        assert editor.pending_message  # the path does not resolve — held, not stored
        assert editor.table.item(_MIRROR_ROW, _COL_VALUE).text() == "mirror_coating.csv"

        editor.table.item(_MIRROR_ROW, _COL_VALUE).setText("0.93")

        assert not editor.pending_message
        shared = config_set.base.optical_elements()
        assert shared is not None
        assert shared[_MIRROR_ROW]["reflectance"] == pytest.approx(0.93, abs=1e-12)

    def test_a_configured_row_edit_writes_only_the_displayed_member(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """D-8 at the call level: one set_element_for, for MWIR, per edit."""
        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)

        seen: list[tuple[int, str]] = []
        original = type(config_set).set_element_for

        def _record(self: Any, index: int, config: str, entry: Any, **kwargs: Any) -> None:
            seen.append((index, config))
            original(self, index, config, entry, **kwargs)

        monkeypatch.setattr(type(config_set), "set_element_for", _record)
        editor.table.item(_FILTER_ROW, _COL_TEMP).setText("120.0")

        assert seen == [(_FILTER_ROW, "MWIR")]
        assert config_set.element_for(_FILTER_ROW, "LWIR")["temperature_K"] == pytest.approx(
            240.0, abs=1e-12
        )


class TestSharedStructure:
    """§3a-bis: row count and order are shared — add / remove change every member.

    Each structural edit commits as it is made and the table re-reads the document
    (a removal renumbers the positions row identity is).
    """

    def test_adding_a_row_seeds_it_shared_for_every_configuration(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)
        editor._add_mirror.click()  # noqa: SLF001

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


class TestConfigureButton:
    """The visible twin of the row menu (owner live-review, 2026-09-03).

    A right-click-only affordance is invisible — the operator's report was "I don't
    see how you actually set one of these to be configured". The button next to
    Spectrum… is the discoverable entrance; it dispatches to the same handlers as
    the menu, so the two can never disagree.
    """

    def test_hidden_outside_a_study(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = _bind(qtbot, None)
        assert editor._configure.isVisibleTo(editor) is False  # noqa: SLF001

    def test_visible_and_row_tracking_in_a_study(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(configure=_FILTER_ROW)
        editor = _bind(qtbot, config_set)
        assert editor._configure.isVisibleTo(editor) is True  # noqa: SLF001
        editor._table.selectRow(_MIRROR_ROW)  # noqa: SLF001
        assert editor._configure.isEnabled()  # noqa: SLF001
        assert editor._configure.text() == "Configure across configurations…"  # noqa: SLF001
        editor._table.selectRow(_FILTER_ROW)  # noqa: SLF001
        assert "Un-configure" in editor._configure.text()  # noqa: SLF001
        assert "MWIR" in editor._configure.text()  # noqa: SLF001

    def test_click_configures_and_unconfigures(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from PySide6.QtWidgets import QMessageBox

        config_set = _study()
        editor = _bind(qtbot, config_set)
        row = _FILTER_ROW
        editor._table.selectRow(row)  # noqa: SLF001
        editor._configure.click()  # noqa: SLF001
        assert config_set.configured_element_indices() == (_FILTER_ROW,)
        # Reload leaves the selection behind; re-select and collapse it again.
        editor._table.selectRow(_FILTER_ROW)  # noqa: SLF001
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Ok)
        editor._configure.click()  # noqa: SLF001
        assert config_set.configured_element_indices() == ()


class TestBrowseSpectralFile:
    """The CSV file… button (owner live-review, 2026-09-03).

    Typing a path or scalar stays legal; the button is the navigable route to a
    saved spectral CSV. The picked path lands in the value cell exactly as if
    typed — the io parser stays the single validator — replaces any inline λ-table
    on the cell, and commits on the spot (2026-09-03).
    """

    def test_pick_writes_the_cell_clears_an_inline_table_and_commits(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch, tmp_path
    ) -> None:
        from radiant.gui.widgets import optical_element_editor as mod

        csv = tmp_path / "filter_b2.csv"
        csv.write_text("3.4,0.1\n5.0,0.9\n", encoding="utf-8")
        config_set = _study()
        editor = _bind(qtbot, config_set)
        editor._table.selectRow(_FILTER_ROW)  # noqa: SLF001
        item = editor._table.item(_FILTER_ROW, 3)  # noqa: SLF001
        item.setData(mod._SPECTRUM_ROLE, {"wavelength_um": [3.4, 5.0], "values": [0.5, 0.5]})  # noqa: SLF001
        monkeypatch.setattr(
            mod.QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *a, **k: (str(csv), "CSV files (*.csv)")),
        )
        editor._browse.click()  # noqa: SLF001
        assert item.text() == str(csv)
        assert item.toolTip() == str(csv)
        assert item.data(mod._SPECTRUM_ROLE) is None  # noqa: SLF001
        # One pick, one commit — the picked file is in the document already.
        shared = config_set.base.optical_elements()
        assert shared is not None
        assert str(shared[_FILTER_ROW]["transmittance"]) == str(csv)

    def test_cancel_changes_nothing(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets import optical_element_editor as mod

        editor = _bind(qtbot, _study())
        editor._table.selectRow(_FILTER_ROW)  # noqa: SLF001
        before = editor._table.item(_FILTER_ROW, 3).text()  # noqa: SLF001
        monkeypatch.setattr(
            mod.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
        )
        editor._browse.click()  # noqa: SLF001
        assert editor._table.item(_FILTER_ROW, 3).text() == before  # noqa: SLF001

    def test_lands_enabled_with_the_first_row_selected(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Auto-selection (2026-09-03) makes every selection-driven button live at bind."""
        editor = _bind(qtbot, _study())
        assert editor._table.currentRow() == 0  # noqa: SLF001
        assert editor._browse.isEnabled() is True  # noqa: SLF001
        assert editor._configure.isEnabled() is True  # noqa: SLF001


class TestNoApplyButton:
    """Commit-on-edit retires the Apply affordance entirely (Rule 27 — one commit model).

    The owner's live-review verdict, 2026-09-03: "Why do we have this button? Why aren't
    updates made when a value changes like all other parameters?"
    """

    def test_a_study_has_no_apply_button(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from PySide6.QtWidgets import QPushButton

        editor = _bind(qtbot, _study(configure=_FILTER_ROW))
        labels = [button.text() for button in editor.findChildren(QPushButton)]
        assert not any("Apply" in label for label in labels), labels

    def test_the_hint_says_edits_commit_as_they_are_made(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = _bind(qtbot, _study())
        hints = [label.text() for label in editor.findChildren(type(editor.study_note))]
        assert any("commits as you make it" in text for text in hints), hints
        assert "committed as you edit" in editor.study_note.text()


class TestThreeBandStudyIsEntryFaithful:
    """CU-344 on the shape that found it: a three-band study with configured rows.

    The live-review reproduction, reduced to a fixture the repo owns. The document is the
    scenario's: mirrors that specify **no** geometry keys, configured refractive rows that
    carry a ``reflectance`` the table has no column for and an upper-case ``kind``, and
    per-configuration spectral-CSV transmittances. Row 1 is configured **through the GUI**
    and its value cell edited to 0.5; the committed effective train must equal, entry by
    entry, the train the same two acts produce through the scripting API — which is the
    oracle here precisely because it writes only what it is asked to.

    Before the fix this diverged on every row (invented ``diameter_m``/
    ``distance_to_fpa_m``, dropped ``reflectance``, ``FILTER`` → ``filter``), and the
    invented ``diameter_m`` alone moved SNR from 58.5 [-] to 220.5 [-].
    """

    _EDITED_ROW = 1

    @staticmethod
    def _document(root: Path) -> Path:
        """Write the scenario-shaped study (plus its per-band CSVs) under *root*."""
        for band, value in (("b1", 0.88), ("b2", 0.86)):
            (root / f"filter_{band}.csv").write_text(
                f"# wavelength_um, transmittance\n3.0,{value}\n6.0,{value}\n",
                encoding="utf-8",
            )
        # The band edges are configured below, so they must not also sit in the shared
        # body (ADR-0010 D-B: a parameter is shared **or** configured, never both).
        base = "\n".join(
            line
            for line in _EXAMPLE.read_text(encoding="utf-8").splitlines()
            if "filter_min_um" not in line and "filter_max_um" not in line
        )
        study = root / "three_band_study.yaml"
        study.write_text(
            base + "\n" + "configurations:\n"
            "  active: B1\n"
            "  baseline: B1\n"
            "  names: [B1, B2]\n"
            "  parameters:\n"
            "    spectral_integration.filter_min_um: [3.6, 4.0]\n"
            "    spectral_integration.filter_max_um: [4.0, 4.4]\n"
            "optical_elements:\n"
            "- {name: M1_primary, transfer_mode: REFLECTIVE, reflectance: 0.97, "
            "temperature_K: 293.0}\n"
            "- {name: M2_secondary, transfer_mode: REFLECTIVE, reflectance: 0.97, "
            "temperature_K: 293.0}\n"
            "- configured:\n"
            "    B1: {name: band_filter, transfer_mode: REFRACTIVE, kind: FILTER, "
            "reflectance: 0.02, temperature_K: 240.0, transmittance: filter_b1.csv}\n"
            "    B2: {name: band_filter, transfer_mode: REFRACTIVE, kind: FILTER, "
            "reflectance: 0.02, temperature_K: 240.0, transmittance: filter_b2.csv}\n",
            encoding="utf-8",
        )
        return study

    def _reference(self, path: Path) -> list[dict[str, Any]]:
        """The oracle: configure row 1 and set its reflectance to 0.5, via the API."""
        config_set = ConfigurationSet.load(path)
        config_set.configure_element(self._EDITED_ROW)
        entry = dict(config_set.element_for(self._EDITED_ROW, config_set.active))
        entry["reflectance"] = 0.5
        config_set.set_element_for(self._EDITED_ROW, config_set.active, entry)
        effective = config_set.effective_optical_elements(config_set.active)
        assert effective is not None
        return effective

    def test_gui_commit_equals_the_api_authored_train(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        path = self._document(tmp_path)
        reference = self._reference(path)

        config_set = ConfigurationSet.load(path)
        editor = _bind(qtbot, config_set)
        _trigger(editor, self._EDITED_ROW, CONFIGURE_TEXT)
        editor.table.item(self._EDITED_ROW, _COL_VALUE).setText("0.5")

        committed = config_set.effective_optical_elements(config_set.active)
        assert committed is not None
        assert len(committed) == len(reference)
        for index, (got, want) in enumerate(zip(committed, reference, strict=True)):
            assert got == want, f"row {index} diverged from the API-authored entry"

    def test_the_untouched_configuration_keeps_its_entries(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """The other band's train must not move when B1's row 1 is edited."""
        path = self._document(tmp_path)
        config_set = ConfigurationSet.load(path)
        before = config_set.effective_optical_elements("B2")
        editor = _bind(qtbot, config_set)
        _trigger(editor, self._EDITED_ROW, CONFIGURE_TEXT)
        editor.table.item(self._EDITED_ROW, _COL_VALUE).setText("0.5")

        assert config_set.effective_optical_elements("B2") == before
