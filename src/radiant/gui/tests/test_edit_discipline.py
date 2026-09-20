"""Pinning tests for CU-372 — GUI edit discipline (GUI usability audit 2026-09).

Each test reproduces one finding's numbered steps from **Blank config** (or the
complete eleven-parameter configuration the audit built from it) through the real
entry paths — the Parameters dock's in-place delegate, the Parameter Editor dialog,
the dock's Reset to Default, the YAML editor's Apply — and asserts the fixed
behaviour. Every test here failed on the pre-fix code; the finding numbers refer to
``docs/reports/gui_usability_audit_2026-09/``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

import pytest
from PySide6.QtWidgets import QLabel  # noqa: E402

from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog  # noqa: E402

_WAIT_MS = 15000
_ALT = "geometry.sensor_altitude_m"

# The audit's minimal complete configuration (Findings_Bootstrap_Recovery §1), in
# the quiet optics-first order.
_COMPLETE: tuple[tuple[str, str], ...] = (
    ("optics.aperture_diameter_m", "0.3"),
    ("optics.f_number", "4"),
    ("detector.pixel_pitch_x_um", "18"),
    ("detector.pixel_pitch_y_um", "18"),
    ("detector.qe_value", "0.7"),
    ("spectral_integration.filter_min_um", "3.4"),
    ("spectral_integration.filter_max_um", "5.0"),
    ("spectral_integration.integration_time_s", "0.005"),
    ("source.target.temperature", "300"),
    ("source.target.emissivity", "0.95"),
    (_ALT, "500000"),
)


def _blank_window(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """Blank config exactly as the welcome screen's card produces it."""
    window = RADIANTMainWindow()
    qtbot.addWidget(window)
    window._on_blank_config()  # noqa: SLF001 — the Blank card's slot
    return window


def _dialog_set(window: RADIANTMainWindow, dotpath: str, text: str) -> ParameterEditorDialog:
    """Enter *text* for *dotpath* through the Parameter Editor's accept path."""
    panel = window.parameter_panel
    dialog = ParameterEditorDialog(
        window.sensor,
        dotpath,
        panel._after_dialog_commit,
        panel,  # noqa: SLF001
    )
    dialog.value_editor.setText(text)
    dialog.apply(close=True)
    return dialog


def _capture_modals(monkeypatch, module: str) -> list[object]:  # type: ignore[no-untyped-def]
    opened: list[object] = []
    monkeypatch.setattr(f"{module}.exec_dialog", lambda dlg, *a, **k: opened.append(dlg) or 0)
    return opened


def _complete_window(qtbot, monkeypatch) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """Blank config built up to the audit's complete configuration (optics-first)."""
    window = _blank_window(qtbot)
    _capture_modals(monkeypatch, "radiant.gui.main_window")
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        for dotpath, text in _COMPLETE:
            _dialog_set(window, dotpath, text)
    assert window.last_result is not None, "the complete configuration must evaluate"
    return window


class TestF01DockShowsCommittedValues:
    """F-01: on an unresolved configuration every dock row read `—` with no
    provenance, including the values just accepted through the dialog."""

    def test_accepted_value_shows_with_provenance_before_config_resolves(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Blank config. (2) Set geometry.sensor_altitude_m = 500000 through
        the editor dialog (accepted). (3) Look at the dock row."""
        window = _blank_window(qtbot)
        _capture_modals(monkeypatch, "radiant.gui.main_window")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, _ALT, "500000")
        panel = window.parameter_panel
        assert panel.value_text(_ALT) == "500000 m"
        assert panel.source_text(_ALT) == "user-set"
        # A row nothing has set still reads unset — the fallback is per row.
        assert panel.value_text("optics.aperture_diameter_m") == "—"
        assert panel.source_text("optics.aperture_diameter_m") == ""

    def test_changed_only_lists_the_set_rows_on_an_incomplete_config(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """*Changed only* listed nothing until the configuration resolved."""
        window = _blank_window(qtbot)
        _capture_modals(monkeypatch, "radiant.gui.main_window")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, _ALT, "500000")
        panel = window.parameter_panel
        panel._changed_only.setChecked(True)  # noqa: SLF001
        assert panel.visible_dotpaths() == {_ALT}


class TestF02InPlaceEditorOnBlankConfig:
    """F-02 / F-46: the in-place Value-column editor had no differential guard, so on
    a blank configuration every edit was rejected with the cycle diagnostic (headless:
    a modal from inside the editor-close sequence; natively: a silent revert)."""

    def test_in_place_edit_is_accepted_on_blank_config(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Blank config. (2) Double-click the Value cell of
        geometry.sensor_altitude_m, type 500000, Enter (the delegate's commit)."""
        window = _blank_window(qtbot)
        window_modals = _capture_modals(monkeypatch, "radiant.gui.main_window")
        panel_modals = _capture_modals(monkeypatch, "radiant.gui.widgets.parameter_panel")
        panel = window.parameter_panel
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            panel._commit_edit(_ALT, 500000.0)  # noqa: SLF001 — the delegate's commit
        assert window.sensor.peek_input(_ALT) == 500000.0
        assert panel.value_text(_ALT) == "500000 m"
        assert panel.source_text(_ALT) == "user-set"
        assert not panel.has_error(_ALT)
        assert window_modals == [] and panel_modals == []

    def test_every_audit_parameter_enters_in_place_in_geometry_first_order(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """The audit's inline run rejected 11 of 11; all eleven now enter and evaluate."""
        window = _blank_window(qtbot)
        _capture_modals(monkeypatch, "radiant.gui.main_window")
        panel_modals = _capture_modals(monkeypatch, "radiant.gui.widgets.parameter_panel")
        panel = window.parameter_panel
        geometry_first = sorted(_COMPLETE, key=lambda item: item[0] != _ALT)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            for dotpath, text in geometry_first:
                panel._commit_edit(dotpath, float(text))  # noqa: SLF001
                assert not panel.has_error(dotpath), dotpath
        assert panel_modals == []
        assert window.last_result is not None

    def test_bad_in_place_value_on_blank_config_is_rejected_inline_not_modal(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """F-46: a value wrong on its own terms still fails — inline, never a modal."""
        window = _blank_window(qtbot)
        panel_modals = _capture_modals(monkeypatch, "radiant.gui.widgets.parameter_panel")
        panel = window.parameter_panel
        aperture = "optics.aperture_diameter_m"
        panel._commit_edit(aperture, -5.0)  # noqa: SLF001
        assert window.sensor.peek_input(aperture) is None  # never reached the sensor
        assert panel.value_text(aperture) == "—"
        assert panel.has_error(aperture)
        assert "out of bounds" in panel.error_banner.text()
        assert panel_modals == []

    def test_dialog_and_in_place_paths_reject_identically(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """One resolver, both paths: the dialog's verdict is the delegate's verdict."""
        from radiant.gui.edit_guard import validate_edit

        window = _blank_window(qtbot)
        sensor = window.sensor
        panel = window.parameter_panel
        dialog = ParameterEditorDialog(sensor, _ALT, panel._after_dialog_commit, panel)  # noqa: SLF001
        for value in ("500000", "-1"):
            _c, rejection, _u = dialog._try_resolve(value, None)  # noqa: SLF001
            verdict = validate_edit(sensor, _ALT, value, None)
            assert (rejection is None) == (verdict.rejection is None)
            if rejection is not None:
                assert str(rejection) == str(verdict.rejection)


class TestF03ResetToDefaultIsClean:
    """F-03: Reset to Default on a consistency-group member reported a rejection but
    applied the reset anyway — row stale, no undo step, no re-evaluate, not dirty."""

    def test_reset_that_would_break_the_group_is_refused_and_changes_nothing(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Complete configuration with aperture and f-number set (focal
        length derived). (2) Right-click optics.f_number ▸ Reset to Default."""
        window = _complete_window(qtbot, monkeypatch)
        panel_modals = _capture_modals(monkeypatch, "radiant.gui.widgets.parameter_panel")
        panel = window.parameter_panel
        f_number = "optics.f_number"
        undo_before = window._undo_stack.count()  # noqa: SLF001
        dirty_before = window._dirty  # noqa: SLF001

        panel._reset_to_default(f_number)  # noqa: SLF001

        # Refused: the input is still there, the row still says so, nothing moved.
        assert window.sensor.peek_input(f_number) == 4.0
        assert panel.value_text(f_number) == "4"
        assert panel.source_text(f_number) == "user-set"
        assert window._undo_stack.count() == undo_before  # noqa: SLF001
        assert window._dirty == dirty_before  # noqa: SLF001
        assert not window.evaluation_scheduled
        # The refusal names what is missing, under a header that says "reset".
        assert len(panel_modals) == 1
        modal = panel_modals[0]
        assert modal.header_text == "Cannot reset “optics.f_number”"
        assert panel.has_error(f_number)
        assert "optics.focal_length_m" in panel.error_banner.text()

    def test_legal_reset_applies_with_undo_dirty_and_reevaluation(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """The other half of the contract: an accepted reset says so everywhere."""
        window = _complete_window(qtbot, monkeypatch)
        _capture_modals(monkeypatch, "radiant.gui.widgets.parameter_panel")
        panel = window.parameter_panel
        jitter = "platform.jitter_rms_urad"
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, jitter, "5")
        assert panel.source_text(jitter) == "user-set"
        window._dirty = False  # noqa: SLF001 — isolate the reset's own dirty mark
        undo_before = window._undo_stack.count()  # noqa: SLF001

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            panel._reset_to_default(jitter)  # noqa: SLF001

        assert window.sensor.peek_input(jitter) is None
        assert panel.source_text(jitter) == "default"
        assert window._undo_stack.count() == undo_before + 1  # noqa: SLF001
        assert window.action("edit.undo").isEnabled()
        assert window._dirty  # noqa: SLF001


class TestF32YamlApplyValidates:
    """F-32: the YAML editor's Apply admitted an out-of-bounds value into the live
    sensor, reported it as "incomplete", and the editor then could not be reopened."""

    def test_out_of_bounds_apply_is_refused_inline_and_changes_nothing(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Complete configuration. (2) Right rail ▸ Edit Config (YAML).
        (3) Change aperture_diameter_m: 0.3 to -1.0. (4) Apply."""
        window = _complete_window(qtbot, monkeypatch)
        yaml_modals = _capture_modals(monkeypatch, "radiant.gui.widgets.yaml_editor_dialog")
        document_before = window.configuration_set
        dialog = window.open_yaml_editor()
        assert dialog is not None
        qtbot.addWidget(dialog)
        text = dialog.yaml_text()
        assert "aperture_diameter_m: 0.3" in text
        dialog.editor.setPlainText(
            text.replace("aperture_diameter_m: 0.3", "aperture_diameter_m: -1.0")
        )

        dialog.apply_button.click()

        assert dialog.result() != 1  # not accepted: the dialog stays open with the text
        assert "aperture_diameter_m: -1.0" in dialog.yaml_text()
        assert dialog.error_frame.isVisibleTo(dialog)
        rejection = dialog.last_rejection
        assert rejection is not None and "out of bounds" in str(rejection)
        assert yaml_modals == []
        # The live document is untouched — same object, same value, undo history kept.
        assert window.configuration_set is document_before
        assert window.sensor.peek_input("optics.aperture_diameter_m") == 0.3
        assert window.parameter_panel.value_text("optics.aperture_diameter_m") == "0.3 m"

    def test_incomplete_document_is_still_admitted(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Deleting a required value is a legal edit (incomplete, not wrong)."""
        window = _complete_window(qtbot, monkeypatch)
        dialog = window.open_yaml_editor()
        assert dialog is not None
        qtbot.addWidget(dialog)
        text = dialog.yaml_text()
        assert "  qe_value: 0.7\n" in text
        dialog.editor.setPlainText(text.replace("  qe_value: 0.7\n", ""))
        dialog.apply_button.click()  # an unresolvable document adopts without evaluating
        assert dialog.result() == 1  # accepted
        assert window.sensor.peek_input("detector.qe_value") is None
        assert "incomplete" in window.statusBar().currentMessage()

    def test_editor_opens_on_an_unresolvable_document(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """A document that cannot resolve (reached through the API, as a script would)
        still opens in the editor, so it can be repaired there."""
        window = _complete_window(qtbot, monkeypatch)
        window.sensor.set("optics.aperture_diameter_m", -1.0)  # bypasses the GUI guards
        dialog = window.open_yaml_editor()  # raised ParameterBoundsError before the fix
        assert dialog is not None
        qtbot.addWidget(dialog)
        assert "aperture_diameter_m: -1.0" in dialog.yaml_text()


class TestF04DerivedTakeover:
    """F-04: a derived group member's editor was read-only with no take-over
    affordance; swapping which member is the input needed a reset plus a set."""

    def test_typing_into_a_derived_member_takes_it_over(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Aperture 0.3 m and f-number 4 set; focal length shows ⚡ 1.2 m
        derived. (2) Open the editor on optics.focal_length_m, type 1.8, Apply."""
        window = _complete_window(qtbot, monkeypatch)
        panel = window.parameter_panel
        focal = "optics.focal_length_m"
        assert panel.value_text(focal) == "⚡ 1.2 m"
        assert panel.source_text(focal) == "derived"
        dialog = ParameterEditorDialog(window.sensor, focal, panel._after_dialog_commit, panel)  # noqa: SLF001
        qtbot.addWidget(dialog)
        assert not dialog.read_only
        assert dialog.takeover_release == "optics.f_number"
        dialog.value_editor.setText("1.8")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            dialog.apply(close=True)
        assert window.sensor.inputs()[focal] == 1.8
        assert "optics.f_number" not in window.sensor.inputs()
        assert panel.value_text(focal) == "1.8 m"
        assert panel.source_text(focal) == "user-set"
        assert panel.value_text("optics.f_number") == "⚡ 6"
        assert panel.source_text("optics.f_number") == "derived"
        assert panel.value_text("optics.aperture_diameter_m") == "0.3 m"

    def test_takeover_can_release_the_other_sibling(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """The selector is a real choice: releasing the aperture keeps the f-number."""
        window = _complete_window(qtbot, monkeypatch)
        panel = window.parameter_panel
        dialog = ParameterEditorDialog(
            window.sensor,
            "optics.focal_length_m",
            panel._after_dialog_commit,
            panel,  # noqa: SLF001
        )
        qtbot.addWidget(dialog)
        combo = dialog.release_combo
        assert combo is not None
        combo.setCurrentIndex(combo.findData("optics.aperture_diameter_m"))
        dialog.value_editor.setText("1.8")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            dialog.apply(close=True)
        assert "optics.aperture_diameter_m" not in window.sensor.inputs()
        assert window.sensor.inputs()["optics.f_number"] == 4.0
        assert panel.value_text("optics.aperture_diameter_m") == "⚡ 0.45 m"


class TestF06OverConstrainedGroupRejectedAtTheDoor:
    """F-06: an over-constrained group authored on a blank configuration was admitted
    (bounds-only fallback), surfaced only when the configuration completed, then
    raised a modal on every further edit naming the first-set member."""

    def test_disagreeing_third_member_is_rejected_on_its_own_row(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Steps: (1) Blank config. (2) Aperture 0.3, focal length 1.2, then f-number 6."""
        window = _blank_window(qtbot)
        _capture_modals(monkeypatch, "radiant.gui.main_window")
        panel = window.parameter_panel
        _dialog_set(window, "optics.aperture_diameter_m", "0.3")
        _dialog_set(window, "optics.focal_length_m", "1.2")
        dialog = ParameterEditorDialog(
            window.sensor,
            "optics.f_number",
            panel._after_dialog_commit,
            panel,  # noqa: SLF001
        )
        qtbot.addWidget(dialog)
        dialog.value_editor.setText("6")
        dialog.apply(close=False)
        # Refused at the door, on the row being edited, with the group's own message.
        assert dialog.error_frame.isVisibleTo(dialog)
        rendered = "\n".join(lbl.text() for lbl in dialog.error_frame.findChildren(QLabel))
        assert "over-constrained" in rendered
        assert "optics.f_number" not in window.sensor.inputs()
        # A consistent value is accepted.
        dialog.value_editor.setText("4")
        dialog.apply(close=True)
        assert window.sensor.inputs()["optics.f_number"] == 4.0

    def test_the_remaining_parameters_then_enter_without_a_modal(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Step (3): enter the remaining eight — ten modals before, none now."""
        window = _blank_window(qtbot)
        opened = _capture_modals(monkeypatch, "radiant.gui.main_window")
        panel = window.parameter_panel
        _dialog_set(window, "optics.aperture_diameter_m", "0.3")
        _dialog_set(window, "optics.focal_length_m", "1.2")
        rejected = ParameterEditorDialog(
            window.sensor,
            "optics.f_number",
            panel._after_dialog_commit,
            panel,  # noqa: SLF001
        )
        qtbot.addWidget(rejected)
        rejected.value_editor.setText("6")
        rejected.apply(close=False)
        rest = [(d, v) for d, v in _COMPLETE if not d.startswith("optics.")]
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            for dotpath, text in rest:
                _dialog_set(window, dotpath, text)
        assert opened == []
        assert window.last_result is not None


class TestF20UndoRestoresProvenance:
    """F-20: Edit ▸ Undo of a first-time set wrote the schema default back as a
    user-set value (jitter `0 µrad user-set`), so provenance lied afterwards."""

    def test_undo_of_a_first_time_set_returns_the_row_to_default(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """J-1.2 step 28: platform.jitter_rms_urad set to 5, then Edit ▸ Undo."""
        window = _complete_window(qtbot, monkeypatch)
        panel = window.parameter_panel
        jitter = "platform.jitter_rms_urad"
        assert panel.source_text(jitter) == "default"
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, jitter, "5")
        assert panel.value_text(jitter) == "5 µrad"
        assert panel.source_text(jitter) == "user-set"

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()

        assert window.sensor.peek_input(jitter) is None  # the input is withdrawn
        assert panel.value_text(jitter) == "0 µrad"
        assert panel.source_text(jitter) == "default"
        panel._changed_only.setChecked(True)  # noqa: SLF001
        assert jitter not in panel.visible_dotpaths()

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.redo").trigger()
        assert panel.value_text(jitter) == "5 µrad"
        assert panel.source_text(jitter) == "user-set"

    def test_edits_on_a_blank_config_are_undoable(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """The undo baseline no longer waits for the first clean evaluation."""
        window = _blank_window(qtbot)
        _capture_modals(monkeypatch, "radiant.gui.main_window")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, _ALT, "500000")
        assert window._undo_stack.count() == 1  # noqa: SLF001
        assert window._undo_stack.command(0).text() == f"Set {_ALT} = 500000 m"  # noqa: SLF001
        window.action("edit.undo").trigger()
        assert window.sensor.peek_input(_ALT) is None
        assert window.parameter_panel.value_text(_ALT) == "—"

    def test_takeover_undoes_as_one_step(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """F-04's take-over moved two inputs; one Undo restores both (macro)."""
        window = _complete_window(qtbot, monkeypatch)
        panel = window.parameter_panel
        focal = "optics.focal_length_m"
        dialog = ParameterEditorDialog(window.sensor, focal, panel._after_dialog_commit, panel)  # noqa: SLF001
        qtbot.addWidget(dialog)
        dialog.value_editor.setText("1.8")
        before = window._undo_stack.count()  # noqa: SLF001
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            dialog.apply(close=True)
        assert window._undo_stack.count() == before + 1  # noqa: SLF001
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()
        assert window.sensor.inputs()["optics.f_number"] == 4.0
        assert focal not in window.sensor.inputs()
        assert panel.value_text(focal) == "⚡ 1.2 m"


class TestF37AnglesToggleReachesEditedRows:
    """F-37: View ▸ Angles in Degrees did not change a row edited through the dialog —
    the dialog's chosen unit was a sticky per-row override that outranked the toggle."""

    def test_toggle_wins_over_the_dialog_unit_and_entry_follows(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """T-U: path_zenith_rad typed as 30 with degrees on; toggle off; type 0.5; toggle on."""
        from radiant.gui import display_units

        window = _complete_window(qtbot, monkeypatch)
        panel = window.parameter_panel
        zenith = "geometry.path_zenith_rad"
        toggle = window.action("view.angles_deg")
        assert toggle.isChecked()
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            _dialog_set(window, zenith, "30")  # the dialog opens in deg: 30 deg
        assert panel.value_text(zenith) == "30 deg"
        assert window.sensor.peek_input(zenith) == pytest.approx(0.5235987755982988)

        toggle.trigger()  # degrees OFF
        assert not display_units.angles_in_degrees()
        assert panel.value_text(zenith) == "0.523599 rad"  # the row follows the toggle
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            panel._commit_edit(zenith, 0.5)  # noqa: SLF001 — typed "in radians"
        assert window.sensor.peek_input(zenith) == pytest.approx(0.5)  # stored as 0.5 rad
        assert panel.value_text(zenith) == "0.5 rad"

        toggle.trigger()  # degrees ON again
        assert panel.value_text(zenith) == "28.6479 deg"
        display_units.set_angles_in_degrees(True)

    def test_a_genuine_per_row_unit_survives_the_toggle(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """mrad on a rad row is a real choice, not the toggle's business."""
        from radiant.gui import display_units

        window = _complete_window(qtbot, monkeypatch)
        panel = window.parameter_panel
        zenith = "geometry.path_zenith_rad"
        panel.display_units[zenith] = "mrad"
        window.action("view.angles_deg").trigger()
        assert panel.display_units.get(zenith) == "mrad"
        window.action("view.angles_deg").trigger()
        display_units.set_angles_in_degrees(True)
