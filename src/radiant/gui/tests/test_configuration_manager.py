"""Multi-configuration Phase 4c: the configuration manager dialog + CU-210/CU-211 GUI half.

Category D — the GUI half of plan §4 items 1 and 7 (`docs/archive/Multi_Configuration_Plan.md`
§5/§6 "4c"). These drive the real window offscreen and assert what 4c owes:

1. **CRUD drives the API object.** Add / Duplicate / Rename / Remove / Move / Set as
   Baseline are asserted through ``window.configuration_set`` state — never through
   widget internals — because the dialog's contract is "one action, one
   ``ConfigurationSet`` call".
2. **Every guard is actionable.** A ninth configuration, a duplicate or empty name, and
   removing the last configuration render the API's own what/why/action inline and
   change nothing.
3. **Removing the displayed configuration** is allowed and states its policy: the
   display moves to the first surviving configuration.
4. **Rename propagates** to the selector band, the configured badge tooltips, and the
   per-configuration ``wavelength_points`` key (the dict is name-keyed).
5. **Wavelength points round-trip** through the new ``ConfigurationSet.wavelength_points``
   reader (CU-210), including "blank = the shared default".
6. **Live validate_all status** shows the failing configuration's what-line and clears
   when the study is fixed — resolve-only, never a full evaluation.
7. **A degenerate session becomes a study**: Add reveals the selector and Save writes
   the ``configurations:`` section.
8. **Undo/redo of the whole transaction** restores the full shape, including the values
   a Remove dropped, with the selector kept in step.
9. **CU-211**: the per-configuration value boxes display and accept the parameter row's
   chosen display unit, with the conversion asserted numerically.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import (
    QDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
)

from radiant.api.config_set import ConfigurationSet
from radiant.api.sensor import Sensor
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.widgets.configuration_manager_dialog import (
    REMOVE_DISPLAYED_POLICY,
    ConfigurationManagerDialog,
)
from radiant.gui.widgets.configure_menu import CONFIGURATIONS_MENU_PATH, SINGLE_CONFIGURATION_HINT
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

_FILTER_MIN = "spectral_integration.filter_min_um"
_FILTER_MAX = "spectral_integration.filter_max_um"
_ALTITUDE = "geometry.sensor_altitude_m"
_F_NUMBER = "optics.f_number"

_WAIT_MS = 20000  # headroom over an 8-configuration evaluate-all pass


# Window release is the session-wide ``_release_widgets`` fixture's job (conftest.py,
# CU-212); the manager dialogs are children of their window and go with it.


def _dual_band_study(tmp_path: Path) -> Path:
    """The two-configuration MWIR/LWIR study the 4a/4b fixtures use."""
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
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


def _open_plain(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """Open the shipped single-configuration example and await its first pass."""
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


def _manage(  # type: ignore[no-untyped-def]
    qtbot,
    window: RADIANTMainWindow,
    monkeypatch,
    script: Callable[[ConfigurationManagerDialog], None],
    *,
    accept: bool = True,
    changes: bool = True,
    full_pass: bool = False,
) -> ConfigurationManagerDialog:
    """Drive Edit → Configurations… for real, running *script* on the live dialog.

    The window's own handler is exercised end to end — only the modal loop is
    replaced, so the clone/shape/undo path under test is the shipped one.

    *changes* says whether the transaction is expected to schedule a re-evaluation,
    and is **asserted both ways** through :attr:`RADIANTMainWindow.evaluation_scheduled`:
    a shape change must arm the debounce, a no-op transaction must leave it disarmed
    (CU-289 owner ruling, 2026-08-01). Asserting the scheduled state rather than
    awaiting the pass itself is what these tests actually owe — every one of them
    then asserts on synchronously-applied ``ConfigurationSet`` state or on a window
    surface ``_apply_shape_change`` refreshes *before* the debounce starts, so the
    awaited pass' result was discarded at ≈2 s per test and made the merge gate
    load-sensitive (CU-314). The debounce is a single-shot ``QTimer`` parented to the
    window, so a pending one starts no worker: it dies with the window at teardown.

    *full_pass* keeps the real wait, and belongs only to a test that reads
    ``window.last_run`` — the one surface that does not exist until the pass lands.
    """
    holder: list[ConfigurationManagerDialog] = []
    original_init = ConfigurationManagerDialog.__init__

    def _init(self: ConfigurationManagerDialog, config_set: Any, parent: Any = None) -> None:
        original_init(self, config_set, parent)
        holder.append(self)

    def _exec(self: ConfigurationManagerDialog) -> int:
        script(self)
        code = QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected
        return int(code)

    monkeypatch.setattr(ConfigurationManagerDialog, "__init__", _init)
    monkeypatch.setattr(ConfigurationManagerDialog, "exec", _exec)
    if full_pass:
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.configurations").trigger()
    else:
        window.action("edit.configurations").trigger()
        assert window.evaluation_scheduled is (changes and accept)
    return holder[0]


def _answer_name(monkeypatch, name: str) -> None:  # type: ignore[no-untyped-def]
    """Make the manager's name prompt answer *name*."""
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: (name, True)))


def _confirm(monkeypatch, ok: bool = True) -> None:  # type: ignore[no-untyped-def]
    """Answer every QMessageBox.question with Ok (or Cancel)."""
    button = QMessageBox.StandardButton.Ok if ok else QMessageBox.StandardButton.Cancel
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: button)


def _error_text(dialog: ConfigurationManagerDialog | ParameterEditorDialog) -> str:
    """Everything a dialog's inline refusal area is currently rendering."""
    return " ".join(label.text() for label in dialog.error_frame.findChildren(QLabel))


class TestCrudDrivesTheApi:
    def test_add_appends_a_configuration_and_seeds_its_column(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        _answer_name(monkeypatch, "SWIR")

        _manage(qtbot, window, monkeypatch, lambda d: d.action_button("add").click())

        assert cs.names() == ("MWIR", "LWIR", "SWIR")
        # Dense by construction: the new configuration seeds from configuration #1.
        assert cs.configured()[_FILTER_MIN] == pytest.approx((3.5, 8.0, 3.5), rel=1e-12)

    def test_duplicate_copies_the_source_column(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        _answer_name(monkeypatch, "LWIR-b")

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.select("LWIR")
            dialog.action_button("duplicate").click()

        _manage(qtbot, window, monkeypatch, _script)

        assert cs.names() == ("MWIR", "LWIR", "LWIR-b")
        assert cs.configured()[_FILTER_MIN] == pytest.approx((3.5, 8.0, 8.0), rel=1e-12)

    def test_rename_keeps_position_and_values(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        _answer_name(monkeypatch, "LWIR-B")

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.select("LWIR")
            dialog.action_button("rename").click()

        _manage(qtbot, window, monkeypatch, _script)

        assert cs.names() == ("MWIR", "LWIR-B")
        assert cs.configured()[_FILTER_MIN] == pytest.approx((3.5, 8.0), rel=1e-12)

    def test_remove_drops_the_configuration_and_its_column(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        _confirm(monkeypatch)

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.select("LWIR")
            dialog.action_button("remove").click()

        _manage(qtbot, window, monkeypatch, _script)

        assert cs.names() == ("MWIR",)
        assert cs.configured()[_FILTER_MIN] == pytest.approx((3.5,), rel=1e-12)

    def test_reorder_moves_the_values_with_the_name(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.select("LWIR")
            dialog.action_button("up").click()

        _manage(qtbot, window, monkeypatch, _script)

        assert cs.names() == ("LWIR", "MWIR")
        assert cs.configured()[_FILTER_MIN] == pytest.approx((8.0, 3.5), rel=1e-12)

    def test_move_past_the_end_is_refused_with_a_reason_not_a_wrap(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        messages: list[str] = []

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.select("MWIR")
            dialog.action_button("up").click()
            messages.append(dialog.status_line.text())

        _manage(qtbot, window, monkeypatch, _script, changes=False)

        assert cs.names() == ("MWIR", "LWIR")
        assert "already at the end" in messages[0]

    def test_set_as_baseline(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        assert cs.baseline == "MWIR"

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.select("LWIR")
            dialog.action_button("baseline").click()

        _manage(qtbot, window, monkeypatch, _script)

        assert cs.baseline == "LWIR"

    def test_the_selector_bands_gear_opens_the_same_manager(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        """Two entry points, one action: the gear must not grow a second code path."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        _answer_name(monkeypatch, "SWIR")
        holder: list[ConfigurationManagerDialog] = []
        original_init = ConfigurationManagerDialog.__init__

        def _init(self: ConfigurationManagerDialog, config_set: Any, parent: Any = None) -> None:
            original_init(self, config_set, parent)
            holder.append(self)

        def _exec(self: ConfigurationManagerDialog) -> int:
            self.action_button("add").click()
            return int(QDialog.DialogCode.Accepted)

        monkeypatch.setattr(ConfigurationManagerDialog, "__init__", _init)
        monkeypatch.setattr(ConfigurationManagerDialog, "exec", _exec)

        window.configuration_bar.manage_button.click()

        assert window.evaluation_scheduled is True
        assert len(holder) == 1
        assert cs.names() == ("MWIR", "LWIR", "SWIR")

    def test_cancel_applies_nothing(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        _answer_name(monkeypatch, "SWIR")

        _manage(
            qtbot,
            window,
            monkeypatch,
            lambda d: d.action_button("add").click(),
            accept=False,
        )

        assert cs.names() == ("MWIR", "LWIR")
        assert window.action("edit.undo").isEnabled() is False

    def test_the_scheduled_state_assert_catches_a_transaction_that_stops_scheduling(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        """Meta-test (CU-289): ``evaluation_scheduled`` is not an assert-on-nothing.

        The whole file's transaction coverage now rests on the claim that a shape
        change arms the debounce. Break exactly that — neuter the timer's ``start``
        so ``_apply_shape_change`` schedules nothing while every other step of the
        transaction still runs — and :func:`_manage`'s own assertion must fail. If it
        did not, the 31 sibling tests would be asserting on a constant.
        """
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        _answer_name(monkeypatch, "SWIR")
        monkeypatch.setattr(window._debounce, "start", lambda *args: None)

        with pytest.raises(AssertionError):
            _manage(qtbot, window, monkeypatch, lambda d: d.action_button("add").click())

        # The transaction itself still landed — only the scheduling was broken, which
        # is what makes this a test of the assert rather than of the transaction.
        assert cs.names() == ("MWIR", "LWIR", "SWIR")
        assert window.evaluation_scheduled is False


class TestGuardsAreActionable:
    def test_duplicate_name_is_refused_with_the_apis_reason(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        _answer_name(monkeypatch, "LWIR")
        rendered: list[str] = []

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.action_button("add").click()
            rendered.append(_error_text(dialog))
            assert dialog.error_frame.isVisibleTo(dialog)

        _manage(qtbot, window, monkeypatch, _script, changes=False)

        assert cs.names() == ("MWIR", "LWIR")
        assert "already exists" in rendered[0]
        assert "unique" in rendered[0]  # the why-line
        assert "different name" in rendered[0]  # the action-line

    def test_empty_name_is_refused_by_the_api_not_filtered_silently(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        _answer_name(monkeypatch, "   ")
        rendered: list[str] = []

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.action_button("add").click()
            rendered.append(_error_text(dialog))

        _manage(qtbot, window, monkeypatch, _script, changes=False)

        assert cs.names() == ("MWIR", "LWIR")
        assert "non-empty string" in rendered[0]

    def test_ninth_configuration_is_refused_naming_the_cap(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        rendered: list[str] = []

        def _script(dialog: ConfigurationManagerDialog) -> None:
            for index in range(7):  # 2 → 8 fills the set, the 9th must be refused
                _answer_name(monkeypatch, f"extra{index}")
                dialog.action_button("add").click()
            assert len(dialog.names) == ConfigurationSet.MAX_CONFIGS
            _answer_name(monkeypatch, "one-too-many")
            dialog.action_button("add").click()
            rendered.append(_error_text(dialog))

        _manage(qtbot, window, monkeypatch, _script)

        assert len(cs) == ConfigurationSet.MAX_CONFIGS
        assert "one-too-many" not in cs.names()
        assert f"at most {ConfigurationSet.MAX_CONFIGS}" in rendered[0]

    def test_removing_the_last_configuration_is_refused(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _open_plain(qtbot)
        cs = window.configuration_set
        assert cs is not None
        _confirm(monkeypatch)
        rendered: list[str] = []

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.action_button("remove").click()
            rendered.append(_error_text(dialog))

        _manage(qtbot, window, monkeypatch, _script, changes=False)

        assert len(cs) == 1
        assert "only configuration" in rendered[0]
        assert "at least one" in rendered[0]


class TestRemoveDisplayedPolicy:
    def test_removing_the_displayed_configuration_switches_the_display(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        """The policy the dialog states: the display moves to the first survivor."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        assert cs.active == "MWIR"
        _confirm(monkeypatch)
        announced: list[str] = []

        def _script(dialog: ConfigurationManagerDialog) -> None:
            assert REMOVE_DISPLAYED_POLICY in dialog.findChild(QLabel, "configManagerNote").text()
            dialog.select("MWIR")
            dialog.action_button("remove").click()
            announced.append(dialog.status_line.text())

        _manage(qtbot, window, monkeypatch, _script)

        assert cs.names() == ("LWIR",)
        assert cs.active == "LWIR"
        assert "displaying 'LWIR'" in announced[0]
        # The window followed: the displayed sensor is LWIR's band.
        assert window.sensor is not None
        assert window.sensor.get_input(_FILTER_MIN) == pytest.approx(8.0, rel=1e-12)

    def test_the_confirmation_states_the_policy_before_anything_happens(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        asked: list[str] = []

        def _capture(*args: Any, **kwargs: Any) -> QMessageBox.StandardButton:
            asked.append(str(args[2]))
            return QMessageBox.StandardButton.Cancel

        monkeypatch.setattr(QMessageBox, "question", _capture)

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.select("MWIR")
            dialog.action_button("remove").click()

        _manage(qtbot, window, monkeypatch, _script, changes=False)

        assert len(asked) == 1
        assert REMOVE_DISPLAYED_POLICY in asked[0]
        assert "2 configured parameter(s)" in asked[0]
        assert cs.names() == ("MWIR", "LWIR")  # cancelled — nothing happened


class TestRenamePropagates:
    def test_rename_reaches_the_bar_the_badges_and_the_grid_key(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        cs.set_wavelength_points("LWIR", 120)
        _answer_name(monkeypatch, "LWIR-B")

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.select("LWIR")
            dialog.action_button("rename").click()

        _manage(qtbot, window, monkeypatch, _script)

        assert window.configuration_bar.names == ("MWIR", "LWIR-B")
        assert [b.text() for b in window.configuration_bar.buttons] == ["MWIR", "LWIR-B"]
        assert "LWIR-B: 8 um" in window.configuration_scope.summary(_FILTER_MIN)
        assert "LWIR-B" in window.parameter_panel.configured_tooltip(_FILTER_MIN)
        # The name-keyed wavelength-points entry moved with the name (CU-210 reader).
        assert cs.wavelength_points("LWIR-B") == 120


class TestWavelengthPointsRow:
    def test_typing_a_count_sets_that_configurations_override(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        assert cs.wavelength_points("LWIR") is None

        def _script(dialog: ConfigurationManagerDialog) -> None:
            editor = dialog.points_editor("LWIR")
            editor.setText("150")
            editor.editingFinished.emit()

        _manage(qtbot, window, monkeypatch, _script)

        assert cs.wavelength_points("LWIR") == 150
        assert cs.wavelength_points("MWIR") is None
        assert cs.wavelength_points() == cs.base.wavelength_points

    def test_a_blank_row_states_the_shared_default_and_clears_the_override(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        cs.set_wavelength_points("LWIR", 150)
        shared = cs.wavelength_points()
        placeholders: list[str] = []

        def _script(dialog: ConfigurationManagerDialog) -> None:
            placeholders.append(dialog.points_editor("MWIR").placeholderText())
            assert dialog.points_editor("MWIR").text() == ""
            assert dialog.points_editor("LWIR").text() == "150"
            editor = dialog.points_editor("LWIR")
            editor.setText("")
            editor.editingFinished.emit()

        _manage(qtbot, window, monkeypatch, _script)

        # The blank row names the shared value *and* what blank means.
        assert placeholders[0] == f"shared: {shared} pts"
        assert cs.wavelength_points("LWIR") is None

    def test_an_out_of_range_count_is_refused_by_the_api(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        rendered: list[str] = []

        def _script(dialog: ConfigurationManagerDialog) -> None:
            editor = dialog.points_editor("LWIR")
            editor.setText("1")
            editor.editingFinished.emit()
            rendered.append(_error_text(dialog))

        _manage(qtbot, window, monkeypatch, _script, changes=False)

        assert cs.wavelength_points("LWIR") is None
        assert "integer >= 2" in rendered[0]

    def test_the_override_reaches_the_evaluated_grid(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """The point count is not decoration: the displayed configuration evaluates on it."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None

        def _script(dialog: ConfigurationManagerDialog) -> None:
            editor = dialog.points_editor("MWIR")
            editor.setText("64")
            editor.editingFinished.emit()

        # The one transaction test that reads ``window.last_run``, so the one that
        # keeps the real evaluate-all wait (CU-289 owner ruling).
        _manage(qtbot, window, monkeypatch, _script, full_pass=True)

        run = window.last_run
        assert run is not None
        assert run.result_for("MWIR").wavelength_um.size == 64


class TestValidateStatus:
    """Per-row status from ``validate_all`` — resolve-only, re-run on every change."""

    def _over_constrain(self, window: RADIANTMainWindow) -> None:
        """Make LWIR alone unresolvable: an f/# inconsistent with the shared optics."""
        cs = window.configuration_set
        assert cs is not None
        cs.configure(_F_NUMBER, [4.0, 6.0])

    def test_a_failing_configuration_shows_its_what_line(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        self._over_constrain(window)
        seen: dict[str, str] = {}

        def _script(dialog: ConfigurationManagerDialog) -> None:
            seen["MWIR"] = dialog.status_text("MWIR")
            seen["LWIR"] = dialog.status_text("LWIR")

        _manage(qtbot, window, monkeypatch, _script, changes=False)

        assert seen["MWIR"] == "OK"
        assert "LWIR" in seen["LWIR"]
        assert "does not resolve" in seen["LWIR"]

    def test_the_status_clears_once_the_study_is_fixed(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        self._over_constrain(window)
        cs = window.configuration_set
        assert cs is not None
        cs.set_values(_F_NUMBER, [4.0, 4.0])
        seen: list[str] = []

        def _script(dialog: ConfigurationManagerDialog) -> None:
            seen.append(dialog.status_text("LWIR"))

        _manage(qtbot, window, monkeypatch, _script, changes=False)

        assert seen[0] == "OK"

    def test_the_status_re_runs_inside_the_dialog_after_a_change(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        """Removing the failing configuration re-validates the survivors in place."""
        window = _open_study(qtbot, tmp_path)
        self._over_constrain(window)
        _confirm(monkeypatch)
        after: list[list[str]] = []

        def _script(dialog: ConfigurationManagerDialog) -> None:
            assert dialog.status_text("LWIR") != "OK"
            dialog.select("LWIR")
            dialog.action_button("remove").click()
            after.append([dialog.status_text(n) for n in dialog.names])

        _manage(qtbot, window, monkeypatch, _script)

        assert after[0] == ["OK"]


class TestDegenerateSessionBecomesAStudy:
    def test_add_reveals_the_selector_and_saves_the_section(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_plain(qtbot)
        cs = window.configuration_set
        assert cs is not None
        assert window.configuration_bar.isVisible() is False
        _answer_name(monkeypatch, "LWIR")

        _manage(qtbot, window, monkeypatch, lambda d: d.action_button("add").click())

        assert cs.names() == ("Configuration 1", "LWIR")
        assert window.configuration_bar.names == ("Configuration 1", "LWIR")
        assert window.configuration_bar.isVisibleTo(window.configuration_bar.parentWidget())
        # 4a's _write_document routes a study to ConfigurationSet.save — the section
        # is written, and the file reloads as the same two-configuration study.
        path = tmp_path / "became_a_study.yaml"
        window._write_document(path)
        assert "configurations:" in path.read_text(encoding="utf-8")
        assert ConfigurationSet.load(path).names() == ("Configuration 1", "LWIR")

    def test_the_manager_change_marks_the_document_dirty(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        assert window.windowTitle().startswith("*") is False
        _answer_name(monkeypatch, "SWIR")

        _manage(qtbot, window, monkeypatch, lambda d: d.action_button("add").click())

        assert window.windowTitle().startswith("*")

    def test_the_configure_guard_now_names_the_real_menu_path(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """4b's hint pointed at "the next sub-phase"; 4c gives it a real destination."""
        window = _open_plain(qtbot)
        window.configuration_scope.request_configure("optics.aperture_diameter_m")
        message = window.statusBar().currentMessage()
        assert message == SINGLE_CONFIGURATION_HINT
        assert CONFIGURATIONS_MENU_PATH in message
        assert window.action("edit.configurations").isEnabled()


class TestUndoRedoOfTheTransaction:
    def test_undo_of_a_remove_restores_the_column_values_exactly(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        cs.set_wavelength_points("LWIR", 90)
        before_min = tuple(cs.configured()[_FILTER_MIN])
        before_max = tuple(cs.configured()[_FILTER_MAX])
        _confirm(monkeypatch)

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.select("LWIR")
            dialog.action_button("remove").click()

        _manage(qtbot, window, monkeypatch, _script)
        assert cs.names() == ("MWIR",)

        window.action("edit.undo").trigger()
        assert window.evaluation_scheduled is True

        assert cs.names() == ("MWIR", "LWIR")
        assert cs.configured()[_FILTER_MIN] == pytest.approx(before_min, rel=1e-12)
        assert cs.configured()[_FILTER_MAX] == pytest.approx(before_max, rel=1e-12)
        assert cs.wavelength_points("LWIR") == 90
        # The selector came back with the restored study.
        assert window.configuration_bar.names == ("MWIR", "LWIR")

        window.action("edit.redo").trigger()
        assert window.evaluation_scheduled is True

        assert cs.names() == ("MWIR",)
        assert window.configuration_bar.names == ("MWIR",)

    def test_undo_of_a_rename_and_reorder_restores_names_order_and_designations(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        _answer_name(monkeypatch, "LWIR-B")

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.select("LWIR")
            dialog.action_button("rename").click()
            dialog.action_button("up").click()
            dialog.action_button("baseline").click()

        _manage(qtbot, window, monkeypatch, _script)
        assert cs.names() == ("LWIR-B", "MWIR")
        assert cs.baseline == "LWIR-B"

        window.action("edit.undo").trigger()
        assert window.evaluation_scheduled is True

        assert cs.names() == ("MWIR", "LWIR")
        assert cs.baseline == "MWIR"
        assert cs.active == "MWIR"
        assert cs.configured()[_FILTER_MIN] == pytest.approx((3.5, 8.0), rel=1e-12)
        assert window.configuration_bar.names == ("MWIR", "LWIR")

        window.action("edit.redo").trigger()
        assert window.evaluation_scheduled is True

        assert cs.names() == ("LWIR-B", "MWIR")
        assert cs.baseline == "LWIR-B"
        assert cs.configured()[_FILTER_MIN] == pytest.approx((8.0, 3.5), rel=1e-12)

    def test_undo_of_becoming_a_study_hides_the_selector_again(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        window = _open_plain(qtbot)
        cs = window.configuration_set
        assert cs is not None
        _answer_name(monkeypatch, "LWIR")

        _manage(qtbot, window, monkeypatch, lambda d: d.action_button("add").click())
        assert len(cs) == 2

        window.action("edit.undo").trigger()
        assert window.evaluation_scheduled is True

        assert cs.names() == ("Configuration 1",)
        assert window.configuration_bar.names == ("Configuration 1",)
        assert window.configuration_bar.isVisible() is False


class TestConfiguredValuesDisplayUnit:
    """CU-211 — the per-configuration boxes work in the parameter row's chosen unit.

    The surface moved in the 2026-07-26 refinement (the stand-alone table dialog was
    retired into the Parameter Editor's per-configuration mode, Rule 27), so these
    now drive that dialog; every contract they assert is unchanged.
    """

    def _dialog(self, window: RADIANTMainWindow, dotpath: str) -> ParameterEditorDialog:
        return ParameterEditorDialog(
            window.sensor,
            dotpath,
            None,
            window,
            display_unit=window.parameter_panel.display_unit(dotpath),
            scope=window.configuration_scope,
        )

    @staticmethod
    def _rows(dialog: ParameterEditorDialog):  # type: ignore[no-untyped-def]
        block = dialog.per_configuration
        assert block is not None
        return block

    def test_rows_display_and_accept_the_rows_chosen_unit(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        cs.configure(_ALTITUDE, [500_000.0, 600_000.0])
        # The analyst chose km for this row in the Parameter Editor.
        window.parameter_panel.display_units[_ALTITUDE] = "km"

        dialog = self._dialog(window, _ALTITUDE)
        qtbot.addWidget(dialog)
        rows = self._rows(dialog)

        # Display: the stored metres are shown as kilometres, and every row says km.
        assert rows.unit == "km"
        assert [float(rows.editor(i).text()) for i in range(2)] == pytest.approx(  # type: ignore[attr-defined]
            [500.0, 600.0], rel=1e-12
        )

        # Entry: typing 450 into a km row means 450 km, converted once at the API.
        editor = rows.editor(0)
        assert isinstance(editor, QLineEdit)
        editor.setText("450")
        dialog.apply(close=False)
        # The write is synchronous; only the re-evaluation it schedules is not (CU-289).
        assert window.evaluation_scheduled is True

        assert cs.configured()[_ALTITUDE] == pytest.approx((450_000.0, 600_000.0), rel=1e-12)

    def test_without_a_chosen_unit_the_table_is_unchanged(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Zero regression for the 4b behaviour: no override ⇒ the schema input unit."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        cs.configure(_ALTITUDE, [500_000.0, 600_000.0])

        dialog = self._dialog(window, _ALTITUDE)
        qtbot.addWidget(dialog)
        rows = self._rows(dialog)

        assert rows.unit == cs.base.parameter_def(_ALTITUDE).input_unit
        assert [float(rows.editor(i).text()) for i in range(2)] == pytest.approx(  # type: ignore[attr-defined]
            [500_000.0, 600_000.0], rel=1e-12
        )

    def test_a_rejected_row_leaves_the_column_untouched_in_display_units(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path
    ) -> None:
        """Atomicity survives the unit seam (the CU-211 acceptance criterion)."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        cs.configure(_ALTITUDE, [500_000.0, 600_000.0])
        window.parameter_panel.display_units[_ALTITUDE] = "km"
        before = tuple(cs.configured()[_ALTITUDE])

        dialog = self._dialog(window, _ALTITUDE)
        qtbot.addWidget(dialog)
        rows = self._rows(dialog)
        rows.editor(0).setText("450")  # type: ignore[attr-defined]
        rows.editor(1).setText("-700")  # type: ignore[attr-defined]  # below the schema bound
        dialog.apply(close=False)

        assert cs.configured()[_ALTITUDE] == pytest.approx(before, rel=1e-12)
        assert dialog.error_frame.isVisibleTo(dialog)
        assert "LWIR" in _error_text(dialog)
