"""Multi-configuration Phase 4b: configure flow, red "C" badges, table editor, scoped undo.

Category D — the GUI half of ADR-0010 D-2 / D-6 / D-8. These drive the real window
offscreen on a real two-configuration study written by ``ConfigurationSet.save`` and
assert the contracts Phase 4b owes (plan §4 items 3–4, §6 "4b"):

1. **Configure across configurations.** The action seeds one value per configuration
   through the API, the red "C" appears in the parameter tree *and* in the per-stage
   form fields, and the badge tooltip lists every configuration's value **with units**
   in set order.
2. **Un-configure.** Keeps configuration #1's value as the shared value (D-6), states
   that value in the confirmation, and drops the badge everywhere.
3. **Table editor.** One row per configuration; editing one row changes only that
   column; an out-of-bounds value is refused with the offending configuration named
   and the set is left **exactly** as it was (no half-commit); Cancel writes nothing.
4. **Inline edit scope (D-8).** Editing a configured parameter while X is displayed
   changes X's column only.
5. **Scoped undo/redo.** configure / unconfigure / per-configuration edits all
   round-trip, restoring the **value and the scope** (which store the dot-path lives
   in is asserted after every step).
6. **Zero regression.** A single-configuration session shows no badge anywhere and the
   configure action refuses with an actionable message instead of silently no-op-ing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QMessageBox

from radiant.api.config_set import ConfigurationSet
from radiant.api.sensor import Sensor
from radiant.gui import main_window as main_window_module
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.themes import DARK, LIGHT
from radiant.gui.widgets import actionable_error_dialog as aed
from radiant.gui.widgets.configure_menu import (
    CONFIGURE_TEXT,
    EDIT_VALUES_TEXT,
    SINGLE_CONFIGURATION_HINT,
    unconfigure_text,
)
from radiant.gui.widgets.configured_values_dialog import ConfiguredValuesDialog
from radiant.gui.widgets.field_row import FieldRow

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

_FILTER_MIN = "spectral_integration.filter_min_um"
_FILTER_MAX = "spectral_integration.filter_max_um"
_APERTURE = "optics.aperture_diameter_m"

_WAIT_MS = 20000  # headroom over an 8-configuration evaluate-all pass


# Windows opened by the helpers below, released after each test. pytest-qt closes a
# registered widget at teardown but does not force its C++ deletion, so a module that
# opens one full main window per test leaves them alive for the rest of the session.
# The GUI suite runs every module in one process and ends with the app-wide
# ``apply_theme`` re-polish, which walks every live widget — accumulating 24 more
# windows here pushed that walk into a segmentation fault (CU-212). Releasing them is
# this module's own house-keeping, not a workaround for the code under test.
_OPEN_WINDOWS: list[RADIANTMainWindow] = []


@pytest.fixture(autouse=True)
def _release_windows() -> Any:  # type: ignore[misc]
    """Close, delete, and drain every window this module opened, after each test."""
    yield
    while _OPEN_WINDOWS:
        window = _OPEN_WINDOWS.pop()
        window.close()
        window.deleteLater()
    QApplication.processEvents()


def _dual_band_study(tmp_path: Path) -> Path:
    """Write the two-configuration MWIR/LWIR study the 4a fixtures use."""
    cs = ConfigurationSet(Sensor.load(_EXAMPLE), names=["MWIR", "LWIR"])
    cs.configure(_FILTER_MIN, [3.5, 8.0])
    cs.configure(_FILTER_MAX, [5.0, 12.0])
    path = tmp_path / "dual_band_study.yaml"
    cs.save(path)
    return path


def _open_study(qtbot, tmp_path: Path) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """Open the two-configuration study in a window and await its first pass."""
    path = _dual_band_study(tmp_path)
    window = RADIANTMainWindow(config_set=ConfigurationSet.load(path), path=str(path))
    qtbot.addWidget(window)
    _OPEN_WINDOWS.append(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


def _open_plain(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """Open the shipped single-configuration example and await its first pass."""
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    _OPEN_WINDOWS.append(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


def _field_rows(window: RADIANTMainWindow, dotpath: str) -> list[FieldRow]:
    """Every per-stage form field showing *dotpath* (there may be more than one)."""
    return [
        row
        for row in window.central_canvas.stage_center.findChildren(FieldRow)
        if row.dotpath == dotpath
    ]


def _act(qtbot, window: RADIANTMainWindow, action) -> None:  # type: ignore[no-untyped-def]
    """Run a scope-changing *action* and wait out the evaluation it schedules.

    Every configure / un-configure / configured-value write marks results stale and
    starts the 200 ms debounce, so a test that returns without awaiting the run would
    tear its window down with a worker mid-flight. Awaiting keeps the offscreen session
    the same shape a real one has.
    """
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        action()


def _configured(window: RADIANTMainWindow, dotpath: str) -> tuple[Any, ...]:
    """*dotpath*'s configured column, through the public API view."""
    cs = window.configuration_set
    assert cs is not None
    return tuple(cs.configured()[dotpath])


class TestConfigureAction:
    def test_configure_seeds_every_configuration_from_the_shared_value(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        shared = cs.base.inputs()[_APERTURE]

        _act(qtbot, window, lambda: window.configuration_scope.request_configure(_APERTURE))

        assert cs.is_configured(_APERTURE)
        assert _configured(window, _APERTURE) == pytest.approx((shared, shared), rel=1e-12)
        # The single-store invariant: it left the base (ADR-0010 D-B).
        assert _APERTURE not in cs.base.inputs()

    def test_badge_appears_in_the_parameter_tree_and_the_stage_form(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        panel = window.parameter_panel
        rows = _field_rows(window, _APERTURE)
        assert rows, "the optics form should carry an aperture field"
        assert panel.is_configured_row(_APERTURE) is False
        assert all(row.badge.isVisible() is False for row in rows)

        _act(qtbot, window, lambda: window.configuration_scope.request_configure(_APERTURE))

        assert panel.is_configured_row(_APERTURE) is True
        assert all(row.badge.isVisibleTo(row) for row in rows)

    def test_badge_tooltip_lists_every_configuration_with_units(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """The owner's spec: 'MWIR: 3.5 um · LWIR: 8 um' — set order, units, all N."""
        window = _open_study(qtbot, tmp_path)
        summary = window.configuration_scope.summary(_FILTER_MIN)
        assert summary == "MWIR: 3.5 um · LWIR: 8 um"
        assert summary in window.parameter_panel.configured_tooltip(_FILTER_MIN)
        rows = _field_rows(window, _FILTER_MIN)
        assert rows
        assert all(row.badge.toolTip() == summary for row in rows)

    def test_badge_tooltip_tracks_a_value_edit_live(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        _act(qtbot, window, lambda: window._commit_configured_values(_FILTER_MIN, [3.6, 8.0]))
        assert window.configuration_scope.summary(_FILTER_MIN) == "MWIR: 3.6 um · LWIR: 8 um"
        assert "3.6 um" in window.parameter_panel.configured_tooltip(_FILTER_MIN)

    def test_configuring_an_already_configured_parameter_is_refused(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        before = _configured(window, _FILTER_MIN)
        window.configuration_scope.request_configure(_FILTER_MIN)
        assert _configured(window, _FILTER_MIN) == before
        assert "already configured" in window.statusBar().currentMessage()

    def test_context_menu_offers_the_scope_actions_by_state(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A shared parameter offers Configure; a configured one offers table + collapse."""
        from PySide6.QtWidgets import QMenu

        from radiant.gui.widgets.configure_menu import add_configuration_actions

        window = _open_study(qtbot, tmp_path)
        scope = window.configuration_scope

        shared_menu = QMenu()
        add_configuration_actions(shared_menu, scope, _APERTURE)
        assert [a.text() for a in shared_menu.actions() if a.text()] == [CONFIGURE_TEXT]

        configured_menu = QMenu()
        add_configuration_actions(configured_menu, scope, _FILTER_MIN)
        assert [a.text() for a in configured_menu.actions() if a.text()] == [
            EDIT_VALUES_TEXT,
            unconfigure_text("MWIR"),
        ]


class TestUnconfigure:
    def test_unconfigure_keeps_configuration_ones_value(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """D-6: configuration #1's value becomes the shared value, and the badge goes."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Ok)

        _act(qtbot, window, lambda: window.configuration_scope.request_unconfigure(_FILTER_MIN))

        assert cs.is_configured(_FILTER_MIN) is False
        assert cs.base.inputs()[_FILTER_MIN] == pytest.approx(3.5, rel=1e-12)
        assert window.parameter_panel.is_configured_row(_FILTER_MIN) is False
        assert all(row.badge.isVisible() is False for row in _field_rows(window, _FILTER_MIN))

    def test_confirmation_states_the_kept_value_with_units(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        """Never a silent physics change: the prompt names the surviving value (plan §4)."""
        window = _open_study(qtbot, tmp_path)
        asked: list[str] = []

        def _capture(*args: Any, **kwargs: Any) -> QMessageBox.StandardButton:
            asked.append(str(args[2]))
            return QMessageBox.StandardButton.Cancel

        monkeypatch.setattr(QMessageBox, "question", _capture)
        window.configuration_scope.request_unconfigure(_FILTER_MIN)

        assert len(asked) == 1
        assert "MWIR's value, 3.5 um" in asked[0]
        # Cancelled — nothing changed.
        cs = window.configuration_set
        assert cs is not None
        assert cs.is_configured(_FILTER_MIN) is True


class TestTableEditor:
    def _dialog(self, window: RADIANTMainWindow, dotpath: str) -> ConfiguredValuesDialog:
        """Build the dialog the window would open (without entering its modal loop).

        Mirrors ``_on_edit_configured_values`` exactly, including the display unit it
        passes and the two-argument commit callback it builds (CU-211).
        """
        cs = window.configuration_set
        assert cs is not None
        return ConfiguredValuesDialog(
            dotpath,
            cs.base.parameter_def(dotpath),
            cs.names(),
            cs.configured()[dotpath],
            lambda values, unit: window._commit_configured_values(dotpath, values, unit),
            window.parameter_panel.display_unit(dotpath),
            window,
        )

    def test_one_row_per_configuration_seeded_with_its_value(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        dialog = self._dialog(window, _FILTER_MIN)
        qtbot.addWidget(dialog)
        assert dialog.names == ("MWIR", "LWIR")
        assert [dialog.editor(i).text() for i in range(2)] == ["3.5", "8.0"]  # type: ignore[attr-defined]

    def test_editing_one_row_changes_only_that_column(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        dialog = self._dialog(window, _FILTER_MIN)
        qtbot.addWidget(dialog)
        editor = dialog.editor(1)
        assert isinstance(editor, QLineEdit)
        editor.setText("9.0")
        _act(qtbot, window, dialog.apply_values)

        assert _configured(window, _FILTER_MIN) == pytest.approx((3.5, 9.0), rel=1e-12)

    def test_out_of_bounds_value_is_refused_naming_the_configuration(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path
    ) -> None:
        """Atomicity: the API validates the whole column, so nothing half-commits."""
        window = _open_study(qtbot, tmp_path)
        before = _configured(window, _FILTER_MIN)
        dialog = self._dialog(window, _FILTER_MIN)
        qtbot.addWidget(dialog)
        dialog.editor(0).setText("3.9")  # type: ignore[attr-defined]
        dialog.editor(1).setText("-5.0")  # type: ignore[attr-defined]  # below the schema bound
        dialog.apply_values()

        # Neither the good MWIR value nor the bad LWIR one landed.
        assert _configured(window, _FILTER_MIN) == before
        assert dialog.error_frame.isVisibleTo(dialog)
        rendered = " ".join(label.text() for label in dialog.error_frame.findChildren(QLabel))
        assert "LWIR" in rendered
        assert "out of bounds" in rendered or "not a valid value" in rendered

    def test_cancel_leaves_the_set_untouched(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        before = _configured(window, _FILTER_MIN)
        dialog = self._dialog(window, _FILTER_MIN)
        qtbot.addWidget(dialog)
        dialog.editor(0).setText("4.2")  # type: ignore[attr-defined]
        dialog.reject()
        assert _configured(window, _FILTER_MIN) == before


class TestInlineEditScope:
    def test_inline_edit_while_x_displayed_changes_x_only(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """ADR-0010 D-8, re-verified with the 4b undo path in place."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        assert cs.active == "MWIR"
        lwir_before = _configured(window, _FILTER_MIN)[1]

        window.sensor.set(_FILTER_MIN, 3.7)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_FILTER_MIN)

        assert _configured(window, _FILTER_MIN) == pytest.approx((3.7, lwir_before), rel=1e-12)
        assert _FILTER_MIN not in cs.base.inputs()
        # The recorded undo step names the configuration it applied to — the edit was
        # scoped, not shared (the status line has since been overwritten by the run).
        assert "in MWIR" in window._undo_stack.undoText()

    def test_inline_edit_updates_the_badge_tooltip(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        window.sensor.set(_FILTER_MIN, 3.7)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_FILTER_MIN)
        assert "MWIR: 3.7 um" in window.parameter_panel.configured_tooltip(_FILTER_MIN)


class TestScopedUndoRedo:
    def test_configure_undo_restores_the_shared_input_and_drops_the_column(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        shared_before = cs.base.inputs()[_APERTURE]

        _act(qtbot, window, lambda: window.configuration_scope.request_configure(_APERTURE))
        assert cs.is_configured(_APERTURE) is True

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()

        # Scope restored: back in the base store, not in the configured table.
        assert cs.is_configured(_APERTURE) is False
        assert cs.base.inputs()[_APERTURE] == pytest.approx(shared_before, rel=1e-12)
        assert window.parameter_panel.is_configured_row(_APERTURE) is False

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.redo").trigger()

        assert cs.is_configured(_APERTURE) is True
        assert _configured(window, _APERTURE) == pytest.approx(
            (shared_before, shared_before), rel=1e-12
        )
        assert window.parameter_panel.is_configured_row(_APERTURE) is True

    def test_unconfigure_undo_restores_the_exact_column(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        column_before = _configured(window, _FILTER_MIN)
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Ok)

        _act(qtbot, window, lambda: window.configuration_scope.request_unconfigure(_FILTER_MIN))
        assert cs.is_configured(_FILTER_MIN) is False

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()

        assert cs.is_configured(_FILTER_MIN) is True
        assert _configured(window, _FILTER_MIN) == pytest.approx(column_before, rel=1e-12)
        assert _FILTER_MIN not in cs.base.inputs()

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.redo").trigger()

        assert cs.is_configured(_FILTER_MIN) is False
        assert cs.base.inputs()[_FILTER_MIN] == pytest.approx(column_before[0], rel=1e-12)

    def test_per_configuration_edit_undo_restores_the_prior_column_value(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        column_before = _configured(window, _FILTER_MIN)

        window.sensor.set(_FILTER_MIN, 3.7)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_FILTER_MIN)
        assert window.action("edit.undo").isEnabled()

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()

        assert cs.is_configured(_FILTER_MIN) is True  # scope preserved
        assert _configured(window, _FILTER_MIN) == pytest.approx(column_before, rel=1e-12)

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.redo").trigger()

        assert _configured(window, _FILTER_MIN) == pytest.approx((3.7, column_before[1]), rel=1e-12)

    def test_table_editor_edit_undo_restores_the_prior_column(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        column_before = _configured(window, _FILTER_MIN)

        _act(qtbot, window, lambda: window._commit_configured_values(_FILTER_MIN, [3.6, 9.0]))
        assert _configured(window, _FILTER_MIN) == pytest.approx((3.6, 9.0), rel=1e-12)

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()
        assert _configured(window, _FILTER_MIN) == pytest.approx(column_before, rel=1e-12)

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.redo").trigger()
        assert _configured(window, _FILTER_MIN) == pytest.approx((3.6, 9.0), rel=1e-12)

    def test_configure_undo_of_a_defaulted_parameter_leaves_it_defaulted(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path
    ) -> None:
        """Undo must not pin today's default as an explicit user input."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        defaulted = next(
            dotpath
            for dotpath, pdef in cs.base.parameter_defs().items()
            if pdef.default is not None
            and dotpath not in cs.base.inputs()
            and dotpath not in cs.configured()
            and pdef.dtype is float
        )

        _act(qtbot, window, lambda: window.configuration_scope.request_configure(defaulted))
        assert cs.is_configured(defaulted) is True

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()

        assert cs.is_configured(defaulted) is False
        assert defaulted not in cs.base.inputs()

    def test_shared_edit_stays_undoable_alongside_scoped_edits(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """The 4a shared-edit command and the 4b scoped command share one stack."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        aperture_before = cs.base.inputs()[_APERTURE]

        window.sensor.set(_APERTURE, 0.5)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_APERTURE)
        window.sensor.set(_FILTER_MIN, 3.7)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_FILTER_MIN)

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()  # the configured edit
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()  # the shared edit

        assert cs.base.inputs()[_APERTURE] == pytest.approx(aperture_before, rel=1e-12)
        assert _configured(window, _FILTER_MIN)[0] == pytest.approx(3.5, rel=1e-12)


class TestSingleConfigurationZeroRegression:
    def test_configure_is_guarded_with_an_actionable_message(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _open_plain(qtbot)
        cs = window.configuration_set
        assert cs is not None

        window.configuration_scope.request_configure(_APERTURE)

        assert cs.is_configured(_APERTURE) is False
        assert cs.configured() == {}
        message = window.statusBar().currentMessage()
        assert message == SINGLE_CONFIGURATION_HINT
        assert "configuration manager" in message

    def test_no_badges_anywhere(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _open_plain(qtbot)
        assert window.configuration_scope.is_multi() is False
        assert all(
            window.parameter_panel.is_configured_row(dotpath) is False
            for dotpath in window.parameter_panel.row_dotpaths()
        )
        rows = window.central_canvas.stage_center.findChildren(FieldRow)
        assert rows
        assert all(row.badge.isVisible() is False for row in rows)

    def test_editing_still_takes_the_plain_shared_path(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """A single-configuration edit is still one shared, undoable sensor.set."""
        window = _open_plain(qtbot)
        shown: list[aed.ActionableErrorDialog] = []
        monkeypatch.setattr(aed.ActionableErrorDialog, "exec", lambda self: shown.append(self) or 0)
        cs = window.configuration_set
        assert cs is not None
        before = cs.base.inputs()[_APERTURE]

        window.sensor.set(_APERTURE, 0.42)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_APERTURE)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()

        assert shown == []
        assert cs.base.inputs()[_APERTURE] == pytest.approx(before, rel=1e-12)
        assert cs.configured() == {}


class TestThemeTogglesRepaintPaintedMarkers:
    """The "C" icon and the selector chips are painted, so QSS alone cannot re-theme them.

    The window's theme toggle must therefore push the new theme into the configuration
    bar (painted accent chips) and repaint the tree's painted badges. The app-wide
    stylesheet swap itself is exercised by ``test_view_menu``; here it is stubbed out —
    re-polishing every live widget mid-suite is heavy global state, and this test is
    about the two widget-level repaints the toggle owes, not about QSS.
    """

    def test_toggle_repaints_the_selector_chips_and_keeps_the_badges(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        light_accent = window.configuration_bar.accent_for("MWIR")
        assert light_accent == LIGHT.config_accents[0] or light_accent == DARK.config_accents[0]

        applied: list[str] = []
        monkeypatch.setattr(
            main_window_module, "apply_theme", lambda app, theme: applied.append(theme.name)
        )
        window._on_toggle_theme()

        assert applied  # the app-level theme swap still ran (stubbed here)
        # The selector's painted accent chips followed the theme — Phase 4a wired
        # ConfigurationBar.set_theme but nothing called it until this phase.
        assert window.configuration_bar.accent_for("MWIR") != light_accent
        # The configured badges survived the repaint.
        assert window.parameter_panel.is_configured_row(_FILTER_MIN) is True
        assert window.configuration_scope.summary(_FILTER_MIN) == "MWIR: 3.5 um · LWIR: 8 um"
