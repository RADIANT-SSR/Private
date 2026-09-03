"""Per-configuration optical elements on the Elements tab (Gap 103 v1.1).

The GUI half of the Configuration-Set Expansion plan Phase 2 (§4a, owner-ratified
2026-09-02): the Elements tab renders the **active configuration's effective train**,
a scope control chooses whether *Apply* writes the shared ``optical_elements`` document
or that configuration's replace-by-name overrides, and the override write is a **diff**
against the shared document — one ``set_element_override`` call carrying only what
differs, or ``clear_element_override`` when nothing does.

These are the plan's §4c matrix, driven on the real widget (and, where the contract is
the host's, the real window) offscreen. A single-configuration session is asserted to
show no scope control and behave exactly as it did before.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.config_set import ConfigurationSet  # noqa: E402
from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.config_scope import ConfigurationScope  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
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


def _study(**overrides: list[dict[str, Any]]) -> ConfigurationSet:
    """A two-configuration study whose base carries the shared element train.

    Keyword arguments seed per-configuration element overrides, e.g.
    ``_study(LWIR=[{...band_filter...}])``.
    """
    base = Sensor.load(_EXAMPLE)
    base.set_optical_elements(_SHARED_TRAIN)
    config_set = ConfigurationSet(base, names=["MWIR", "LWIR"])
    for name, entries in overrides.items():
        config_set.set_element_override(name, entries)
    return config_set


def _cold_filter(transmittance: float = 0.55) -> list[dict[str, Any]]:
    """A one-entry override of the shared ``band_filter`` (a different passband)."""
    entry = dict(_SHARED_TRAIN[1])
    entry["transmittance"] = transmittance
    return [entry]


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


def _row_of(editor: OpticalElementEditor, name: str) -> int:
    for row in range(editor.table.rowCount()):
        if editor.table.item(row, _COL_NAME).text() == name:
            return row
    raise AssertionError(f"no {name!r} row in the table")


def _choose_configuration_scope(editor: OpticalElementEditor) -> None:
    """Pick the This-configuration scope (index 1) — the operator's combo action."""
    editor.scope_selector.setCurrentIndex(1)


class TestScopeControl:
    """§4c: scope-control default, and its absence outside a multi-member study."""

    def test_plain_session_shows_no_scope_control(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.load(_EXAMPLE)
        sensor.set_optical_elements(_SHARED_TRAIN)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        assert editor.scope_row.isHidden()
        assert editor.table.rowCount() == 2

    def test_one_configuration_set_shows_no_scope_control(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A degenerate set has no second member to differ from — no scope question."""
        base = Sensor.load(_EXAMPLE)
        base.set_optical_elements(_SHARED_TRAIN)
        editor = _bind(qtbot, ConfigurationSet(base))
        assert editor.scope_row.isHidden()

    def test_study_opens_in_shared_scope(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = _bind(qtbot, _study())
        assert not editor.scope_row.isHidden()
        assert editor.scope_selector.currentText() == "Shared document"
        assert editor.scope_selector.itemText(1) == "This configuration"

    def test_scope_note_names_the_active_configuration(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = _bind(qtbot, _study())
        assert "MWIR" in editor._scope_note.text()
        _choose_configuration_scope(editor)
        assert "MWIR" in editor._scope_note.text()


class TestEffectiveTrainRender:
    """§4c: the effective train, badged on overridden rows only, re-rendered on switch."""

    def test_overridden_row_carries_the_badge_and_shows_the_override_value(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = _bind(qtbot, _study(MWIR=_cold_filter()))
        filter_row = _row_of(editor, _FILTER)
        mirror_row = _row_of(editor, _MIRROR)
        assert editor.override_badge_text(filter_row) == "overridden — MWIR"
        assert editor.override_badge_text(mirror_row) is None
        # The row shows the override's value, not the shared 0.9.
        assert editor.entries()[filter_row]["transmittance"] == pytest.approx(0.55, abs=1e-12)
        assert editor.entries()[mirror_row]["reflectance"] == pytest.approx(0.97, abs=1e-12)

    def test_inherited_configuration_shows_the_shared_train_unbadged(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(MWIR=_cold_filter())
        config_set.active = "LWIR"
        editor = _bind(qtbot, config_set)
        filter_row = _row_of(editor, _FILTER)
        assert editor.override_badge_text(filter_row) is None
        assert editor.entries()[filter_row]["transmittance"] == pytest.approx(0.9, abs=1e-12)

    def test_switching_configuration_re_renders_the_effective_train(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A selector click re-renders the tab for the newly displayed configuration."""
        config_set = _study(LWIR=_cold_filter())
        path = tmp_path / "elements_study.yaml"
        config_set.save(path)
        window = RADIANTMainWindow(config_set=ConfigurationSet.load(path), path=str(path))
        qtbot.addWidget(window)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            pass
        editor = window.central_canvas.stage_center.pane("optics").element_editor
        assert editor is not None
        assert not editor.scope_row.isHidden()
        assert editor.override_badge_text(_row_of(editor, _FILTER)) is None

        window.configuration_bar.buttons[1].click()

        assert editor.override_badge_text(_row_of(editor, _FILTER)) == "overridden — LWIR"
        assert editor.entries()[_row_of(editor, _FILTER)]["transmittance"] == pytest.approx(
            0.55, abs=1e-12
        )


class TestSharedApply:
    """§4c: Shared-scope Apply edits the shared document only."""

    def test_shared_apply_leaves_overrides_verbatim(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(MWIR=_cold_filter())
        before = config_set.element_overrides("MWIR")
        editor = _bind(qtbot, config_set)
        editor.table.item(_row_of(editor, _MIRROR), _COL_TEMP).setText("275.0")
        assert editor.apply_train()

        shared = config_set.base.optical_elements()
        assert shared is not None
        assert shared[0]["temperature_K"] == pytest.approx(275.0, abs=1e-12)
        assert config_set.element_overrides("MWIR") == before

    def test_shared_apply_does_not_absorb_the_override_value(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The overridden row displays one configuration's value; shared keeps its own."""
        config_set = _study(MWIR=_cold_filter())
        editor = _bind(qtbot, config_set)
        assert editor.apply_train()
        shared = config_set.base.optical_elements()
        assert shared is not None
        assert shared[1]["transmittance"] == pytest.approx(0.9, abs=1e-12)
        assert config_set.effective_optical_elements("MWIR")[1]["transmittance"] == pytest.approx(
            0.55, abs=1e-12
        )

    def test_overridden_row_is_read_only_in_shared_scope(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from PySide6.QtCore import Qt

        editor = _bind(qtbot, _study(MWIR=_cold_filter()))
        filter_row = _row_of(editor, _FILTER)
        mirror_row = _row_of(editor, _MIRROR)
        assert not (editor.table.item(filter_row, _COL_VALUE).flags() & Qt.ItemFlag.ItemIsEditable)
        assert editor.table.item(mirror_row, _COL_VALUE).flags() & Qt.ItemFlag.ItemIsEditable

    def test_selection_actions_are_refused_for_an_overridden_row(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Removing the shared element an override replaces would orphan the override.

        The λ-table editor is refused on the same row for the same reason the row is
        read-only: a shared Apply writes the shared entry back, so the spectrum it
        collected would be discarded.
        """
        editor = _bind(qtbot, _study(MWIR=_cold_filter()))
        editor.table.setCurrentCell(_row_of(editor, _FILTER), _COL_NAME)
        assert not editor._remove.isEnabled()
        assert "overridden in MWIR" in editor._remove.toolTip()
        assert not editor._spectrum.isEnabled()
        editor.table.setCurrentCell(_row_of(editor, _MIRROR), _COL_NAME)
        assert editor._remove.isEnabled()
        assert editor._spectrum.isEnabled()

    def test_apply_lands_on_the_document_not_the_materialization(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A one-member study displays a materialization; the train must reach the set.

        The displayed sensor of any set whose members carry configured values is a
        throwaway `sensor_for` materialization, which the next switch or evaluation
        discards. Applying the train to it would silently lose the edit (Rule 17), so
        the shared Apply targets the set's base — the object `save` writes.
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
        assert editor.scope_row.isHidden()  # one member: no scope question

        editor.table.item(_row_of(editor, _MIRROR), _COL_TEMP).setText("275.0")
        assert editor.apply_train()
        shared = config_set.base.optical_elements()
        assert shared is not None
        assert shared[0]["temperature_K"] == pytest.approx(275.0, abs=1e-12)

    def test_plain_session_apply_is_unchanged(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Zero regression: with no study, Apply is still one set_optical_elements."""
        sensor = Sensor.load(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        assert editor.apply_train()
        document = sensor.optical_elements()
        assert document is not None and len(document) == 1


class TestConfigurationScopeApply:
    """§4c: diff-based Apply, drop-on-equality, and the structural exclusions."""

    def test_editing_one_element_stores_exactly_one_override(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        config_set = _study()
        editor = _bind(qtbot, config_set)
        _choose_configuration_scope(editor)
        editor.table.item(_row_of(editor, _FILTER), _COL_VALUE).setText("0.55")
        assert editor.apply_train()

        overrides = config_set.element_overrides("MWIR")
        assert overrides is not None
        assert len(overrides) == 1
        assert overrides[0]["name"] == _FILTER
        assert overrides[0]["transmittance"] == pytest.approx(0.55, abs=1e-12)
        # The shared document is untouched, and the other member still inherits.
        assert config_set.base.optical_elements()[1]["transmittance"] == pytest.approx(
            0.9, abs=1e-12
        )
        assert config_set.element_overrides("LWIR") is None
        # The applied row now renders badged.
        assert editor.override_badge_text(_row_of(editor, _FILTER)) == "overridden — MWIR"

    def test_unedited_apply_stores_no_override(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """An empty diff is an inheriting configuration, not an override of nothing."""
        config_set = _study()
        editor = _bind(qtbot, config_set)
        _choose_configuration_scope(editor)
        assert editor.apply_train()
        assert config_set.element_overrides("MWIR") is None

    def test_editing_back_to_equality_clears_the_override(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        config_set = _study(MWIR=_cold_filter())
        editor = _bind(qtbot, config_set)
        _choose_configuration_scope(editor)
        assert editor.override_badge_text(_row_of(editor, _FILTER)) == "overridden — MWIR"
        editor.table.item(_row_of(editor, _FILTER), _COL_VALUE).setText("0.9")
        assert editor.apply_train()

        assert config_set.element_overrides("MWIR") is None
        assert editor.override_badge_text(_row_of(editor, _FILTER)) is None

    def test_editing_one_of_two_overridden_entries_back_keeps_the_other(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The diff is per entry: dropping one override does not disturb the other."""
        both = [dict(_SHARED_TRAIN[0], reflectance=0.9), *_cold_filter()]
        config_set = _study(MWIR=both)
        editor = _bind(qtbot, config_set)
        _choose_configuration_scope(editor)
        editor.table.item(_row_of(editor, _MIRROR), _COL_VALUE).setText("0.97")
        assert editor.apply_train()

        overrides = config_set.element_overrides("MWIR")
        assert overrides is not None
        assert [entry["name"] for entry in overrides] == [_FILTER]

    def test_invalid_override_names_the_configuration_and_stores_nothing(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        config_set = _study()
        editor = _bind(qtbot, config_set)
        _choose_configuration_scope(editor)
        editor.table.item(_row_of(editor, _FILTER), _COL_VALUE).setText("no_such_filter.csv")

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
        assert config_set.element_overrides("MWIR") is None

    def test_structure_buttons_are_disabled_in_configuration_scope(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """An override replaces by name — it never adds, removes, or reorders."""
        editor = _bind(qtbot, _study())
        assert editor._add_mirror.isEnabled()
        _choose_configuration_scope(editor)
        for button in (editor._add_mirror, editor._add_refractive, editor._remove, editor._up):
            assert not button.isEnabled()
            assert "never adds or removes" in button.toolTip()

    def test_names_are_read_only_in_configuration_scope(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from PySide6.QtCore import Qt

        editor = _bind(qtbot, _study())
        _choose_configuration_scope(editor)
        for row in range(editor.table.rowCount()):
            assert not (editor.table.item(row, _COL_NAME).flags() & Qt.ItemFlag.ItemIsEditable)


class TestCoatingDetail:
    """§4c: the coating-detail pane shows the effective element for this configuration."""

    def test_detail_pane_reads_the_effective_entries(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from matplotlib.figure import Figure

        editor = _bind(qtbot, _study(MWIR=_cold_filter()))
        editor.show()

        from radiant.gui.widgets import optical_element_editor as oee

        seen: list[dict[str, Any]] = []

        def _capture(sensor: Any, name: str, *, entries: Any = None, **kwargs: Any) -> Figure:
            seen.append({"name": name, "entries": entries})
            return Figure()

        monkeypatch.setattr(oee, "plot_coating_detail", _capture)
        editor.table.setCurrentCell(_row_of(editor, _FILTER), _COL_NAME)
        editor.refresh_coating_detail()

        assert seen[-1]["name"] == _FILTER
        overridden = next(e for e in seen[-1]["entries"] if e["name"] == _FILTER)
        assert overridden["transmittance"] == pytest.approx(0.55, abs=1e-12)


class TestRoundTrip:
    """§4c: a GUI-authored override survives save/load through the io section."""

    def test_gui_authored_override_round_trips(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        config_set = _study()
        editor = _bind(qtbot, config_set)
        _choose_configuration_scope(editor)
        editor.table.item(_row_of(editor, _FILTER), _COL_TEMP).setText("120.0")
        assert editor.apply_train()

        path = tmp_path / "authored_study.yaml"
        config_set.save(path)
        reloaded = ConfigurationSet.load(path)

        overrides = reloaded.element_overrides("MWIR")
        assert overrides is not None
        assert [entry["name"] for entry in overrides] == [_FILTER]
        assert overrides[0]["temperature_K"] == pytest.approx(120.0, abs=1e-12)
        assert reloaded.element_overrides("LWIR") is None
        effective = reloaded.effective_optical_elements("MWIR")
        assert effective is not None
        assert effective[1]["temperature_K"] == pytest.approx(120.0, abs=1e-12)
        assert effective[0]["temperature_K"] == pytest.approx(293.0, abs=1e-12)

        # And the reloaded document renders the same way in a fresh editor.
        reopened = _bind(qtbot, reloaded)
        assert reopened.override_badge_text(_row_of(reopened, _FILTER)) == "overridden — MWIR"
