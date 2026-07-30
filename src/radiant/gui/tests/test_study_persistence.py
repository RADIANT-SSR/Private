"""Multi-configuration Phase 4e: study persistence, YAML document, console, polish.

Category D — the GUI half of plan §4 item 7 and the §6 "4e" test list. Six surfaces
are covered, each against the *public* API so a failure means the GUI diverged from
``radiant.api``, never that a physics value moved:

* **Open / save / recent round-trip on a study** — open, edit a configured value, save,
  reopen: identical set state, and the file reached the Recent menu.
* **The YAML document** (:mod:`radiant.gui.document_yaml`) — a study serializes with its
  ``configurations:`` section, a plain session without one, and both re-parse.
* **The YAML editor** — study text carries the section; editing a configured value in it
  updates the live set; invalid section text shows the actionable dialog and leaves the
  session untouched; deleting the section collapses the study to a plain session and
  hides the selector.
* **The console ``configs`` object** — it is the live document (not a copy), a console
  mutation raises the stale banner, and Refresh re-adopts the whole study.
* **The shared grid-points field** (CU-213) — it round-trips through the manager and
  reverses in one undo.
* **The dirty-marking matrix** — every model-changing path marks the document dirty; a
  selector switch does **not** (``active`` is view state, written on save).

Window release is the session-wide ``_release_widgets`` fixture's job (conftest.py,
CU-212).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtWidgets import QDialog, QMessageBox  # noqa: E402

from radiant.api.config_set import ConfigurationSet  # noqa: E402
from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.document_yaml import (  # noqa: E402
    is_study,
    load_document_from_text,
    serialize_document,
)
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets import yaml_editor_dialog as yed  # noqa: E402
from radiant.gui.widgets.configuration_manager_dialog import (  # noqa: E402
    ConfigurationManagerDialog,
)

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

_FILTER_MIN = "spectral_integration.filter_min_um"
_FILTER_MAX = "spectral_integration.filter_max_um"
_APERTURE = "optics.aperture_diameter_m"
_SECTION_KEY = "configurations:"

_WAIT_MS = 20000  # headroom over an 8-configuration evaluate-all pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _dual_band_set() -> ConfigurationSet:
    """The MWIR/LWIR two-configuration study the 4a–4d fixtures use."""
    cs = ConfigurationSet(Sensor.load(_EXAMPLE), names=["MWIR", "LWIR"])
    cs.configure(_FILTER_MIN, [3.5, 8.0])
    cs.configure(_FILTER_MAX, [5.0, 12.0])
    return cs


def _dual_band_study(tmp_path: Path, name: str = "dual_band_study.yaml") -> Path:
    path = tmp_path / name
    _dual_band_set().save(path)
    return path


def _open_study(qtbot, tmp_path: Path) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """Open the two-configuration study in a window and await its first pass."""
    return _open_file(qtbot, _dual_band_study(tmp_path))


def _open_file(qtbot, path: Path) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
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


def _act(qtbot, window: RADIANTMainWindow, action) -> None:  # type: ignore[no-untyped-def]
    """Run an action that schedules a re-evaluation and wait the run out."""
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        action()


def _edit_shared(window: RADIANTMainWindow, dotpath: str, value: float) -> None:
    """Mimic the parameter panel's edit path: apply the value, then signal the window."""
    window.sensor.set(dotpath, value)
    window._on_parameter_edited(dotpath)


def _state(cs: ConfigurationSet) -> dict[str, Any]:
    """Everything a round trip must preserve, as one comparable mapping."""
    return {
        "names": cs.names(),
        "active": cs.active,
        "baseline": cs.baseline,
        "configured": {p: tuple(v) for p, v in cs.configured().items()},
        "shared_points": cs.wavelength_points(),
        "overrides": {n: cs.wavelength_points(n) for n in cs.names()},
        # ``inputs()``, not ``get_input()``: a study's base holds the *shared* inputs
        # only, and resolving it alone would raise for the configured dot-paths that
        # deliberately live in the section (the single-store invariant, ADR-0010 D-B).
        "shared_inputs": dict(cs.base.inputs()),
    }


# ---------------------------------------------------------------------------
# Open / save / recent round-trip
# ---------------------------------------------------------------------------


class TestStudyRoundTrip:
    """Plan §6 4e: GUI open → edit → save → reopen reproduces the set exactly."""

    def test_open_edit_save_reopen_preserves_the_set(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None

        # Edit one configuration's own value through the write path the table editor
        # drives (one atomic ``set_values`` call + one scope command).
        _act(qtbot, window, lambda: window._commit_configured_values(_FILTER_MIN, [3.7, 8.0]))
        assert cs.configured()[_FILTER_MIN] == pytest.approx((3.7, 8.0), rel=1e-12)
        expected = _state(cs)

        saved = tmp_path / "resaved_study.yaml"
        window._save_to_path(saved)
        assert window._dirty is False

        assert _state(ConfigurationSet.load(saved)) == expected

    def test_saved_study_file_carries_the_section(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        saved = tmp_path / "with_section.yaml"
        window._save_to_path(saved)
        assert _SECTION_KEY in saved.read_text(encoding="utf-8")

    def test_saved_plain_session_carries_no_section(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Zero regression: a single-model session still writes today's file format."""
        window = _open_plain(qtbot)
        saved = tmp_path / "plain.yaml"
        window._save_to_path(saved)
        assert _SECTION_KEY not in saved.read_text(encoding="utf-8")
        # And it still loads through the plain reader.
        assert Sensor.load(saved).get_input(_APERTURE) == pytest.approx(0.3, rel=1e-12)

    def test_recent_menu_reopens_a_study_as_a_study(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A study opened from Open Recent comes back as the full set, selector visible."""
        window = _open_study(qtbot, tmp_path)
        path = window._current_path
        assert path is not None
        entries = [a.text() for a in window._recent_menu.actions()]
        assert str(path) in entries

        # Switch the window to a plain session, then re-open the study from Recent.
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window._adopt_sensor(
                Sensor.load(_EXAMPLE), path=None, dirty=False, add_recent=False, evaluate=True
            )
        assert window._configuration_bar_dock.isVisibleTo(window) is False

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window._open_recent(str(path))
        cs = window.configuration_set
        assert cs is not None
        assert cs.names() == ("MWIR", "LWIR")
        assert cs.is_configured(_FILTER_MIN)
        assert window._configuration_bar_dock.isVisibleTo(window) is True


# ---------------------------------------------------------------------------
# The document serialization (Qt-free)
# ---------------------------------------------------------------------------


class TestDocumentYaml:
    """``gui/document_yaml`` decides study-vs-plain once, for every surface."""

    def test_is_study_is_false_for_a_bare_set(self) -> None:
        assert is_study(ConfigurationSet(Sensor.load(_EXAMPLE))) is False
        assert is_study(None) is False

    def test_is_study_is_true_for_a_one_configuration_set_with_a_column(self) -> None:
        """A configured column makes a one-configuration set a study *document*.

        Its file must carry the section, or the column would be lost on reload.
        """
        cs = ConfigurationSet(Sensor.load(_EXAMPLE))
        cs.configure(_FILTER_MIN, [3.6])
        assert is_study(cs) is True
        assert _SECTION_KEY in serialize_document(cs)

    def test_study_text_carries_the_section_plain_text_does_not(self) -> None:
        assert _SECTION_KEY in serialize_document(_dual_band_set())
        assert _SECTION_KEY not in serialize_document(ConfigurationSet(Sensor.load(_EXAMPLE)))

    def test_round_trip_through_the_text(self) -> None:
        cs = _dual_band_set()
        assert _state(load_document_from_text(serialize_document(cs))) == _state(cs)

    def test_plain_text_round_trips_to_a_degenerate_set(self) -> None:
        plain = ConfigurationSet(Sensor.load(_EXAMPLE))
        parsed = load_document_from_text(serialize_document(plain))
        assert len(parsed) == 1
        assert parsed.configured() == {}
        assert is_study(parsed) is False


# ---------------------------------------------------------------------------
# The YAML editor modal
# ---------------------------------------------------------------------------


class TestStudyYamlEditor:
    """The Edit Config (YAML) modal edits the whole study (the 4a deferral, closed)."""

    def test_editor_opens_on_a_study_and_shows_the_section(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        dialog = window.open_yaml_editor()
        assert dialog is not None
        qtbot.addWidget(dialog)
        text = dialog.yaml_text()
        assert _SECTION_KEY in text
        assert "MWIR" in text and "LWIR" in text
        assert text == serialize_document(window.configuration_set)

    def test_editor_on_a_plain_session_shows_no_section(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _open_plain(qtbot)
        dialog = window.open_yaml_editor()
        assert dialog is not None
        qtbot.addWidget(dialog)
        assert _SECTION_KEY not in dialog.yaml_text()

    def test_editing_a_configured_value_updates_the_set(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Apply on edited section text becomes the new session state."""
        window = _open_study(qtbot, tmp_path)
        dialog = window.open_yaml_editor()
        assert dialog is not None
        qtbot.addWidget(dialog)
        # The section writes its columns as YAML block lists; ``- 3.5`` is MWIR's
        # filter_min row and appears exactly once in the document.
        text = dialog.yaml_text()
        assert text.count("- 3.5\n") == 1
        dialog.editor.setPlainText(text.replace("- 3.5\n", "- 3.7\n"))

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            dialog.apply_button.click()

        cs = window.configuration_set
        assert cs is not None
        assert cs.names() == ("MWIR", "LWIR")
        assert cs.configured()[_FILTER_MIN] == pytest.approx((3.7, 8.0), rel=1e-12)
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert window._dirty is True

    def test_invalid_section_shows_the_actionable_error_and_changes_nothing(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        """A dense-column violation is refused with what/why/action; the study survives."""
        window = _open_study(qtbot, tmp_path)
        cs_before = window.configuration_set
        assert cs_before is not None
        state_before = _state(cs_before)

        # Capture the exception where the dialog renders it, so the assertion is on the
        # actionable payload the analyst reads, not on a dialog attribute.
        raised: list[BaseException] = []

        class _Recorder(QDialog):
            """A real QDialog: `exec_dialog` deleteLater()s what it runs (CU-216)."""

            def __init__(self, exc: BaseException, _label: str, _parent: object = None) -> None:
                super().__init__()
                raised.append(exc)

            def exec(self) -> int:
                return 0

        monkeypatch.setattr(yed, "ActionableErrorDialog", _Recorder)

        dialog = window.open_yaml_editor()
        assert dialog is not None
        qtbot.addWidget(dialog)
        applied: list[object] = []
        dialog.configApplied.connect(applied.append)
        # One value for two configurations — the section's dense-column rule (§3.3).
        text = dialog.yaml_text()
        assert "    - 3.5\n    - 8.0\n" in text
        dialog.editor.setPlainText(text.replace("    - 3.5\n    - 8.0\n", "    - 3.5\n"))
        dialog.apply_button.click()

        assert len(raised) == 1
        # The io layer's ConfigError names the offending parameter and the counts.
        message = str(raised[0])
        assert _FILTER_MIN in message
        assert "2" in message  # the configuration count the column had to match
        assert applied == []
        assert window.configuration_set is cs_before
        assert _state(cs_before) == state_before
        assert dialog.result() != QDialog.DialogCode.Accepted

    def test_removing_the_section_collapses_to_a_plain_session(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Deleting the section is a legal edit: a degenerate set, selector hidden."""
        window = _open_study(qtbot, tmp_path)
        dialog = window.open_yaml_editor()
        assert dialog is not None
        qtbot.addWidget(dialog)
        assert _SECTION_KEY in dialog.yaml_text()

        # Drop the section *and* give the two dot-paths it owned a shared value —
        # exactly the document a plain session writes. Deleting the section alone
        # would leave them set nowhere (the single-store invariant), which is the
        # separate "does not resolve" path the from-scratch rule already covers.
        plain_text = serialize_document(ConfigurationSet(Sensor.load(_EXAMPLE)))
        assert _SECTION_KEY not in plain_text
        dialog.editor.setPlainText(plain_text)

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            dialog.apply_button.click()

        cs = window.configuration_set
        assert cs is not None
        assert len(cs) == 1
        assert cs.configured() == {}
        assert is_study(cs) is False
        assert window._configuration_bar_dock.isVisibleTo(window) is False
        assert cs.base.get_input(_APERTURE) == pytest.approx(0.3, rel=1e-12)


# ---------------------------------------------------------------------------
# The console `configs` object
# ---------------------------------------------------------------------------


class TestConsoleConfigs:
    """``configs`` is the live document; Refresh re-adopts the whole set."""

    def test_configs_is_the_live_set_and_base_is_the_plain_sensor(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _open_plain(qtbot)
        console = window.console
        assert console.namespace_config_set() is window.configuration_set
        # The degenerate set is observably its sensor.
        assert console.namespace_config_set().base is window.sensor

    def test_configs_is_the_live_set_in_a_study(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        assert window.console.namespace_config_set() is window.configuration_set

    def test_a_configs_mutation_raises_the_stale_banner(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        assert window.console.is_stale() is False
        window.console.run_command(f"configs.set_value({_FILTER_MIN!r}, 'MWIR', 3.8)")
        assert window.console.is_stale() is True

    def test_refresh_readopts_the_whole_study(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A console edit of one configuration survives Refresh — no collapse to one."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        window.console.run_command(f"configs.set_value({_FILTER_MIN!r}, 'LWIR', 8.5)")

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.console.refresh_button.click()

        after = window.configuration_set
        assert after is cs  # the same live document, re-read
        assert after.names() == ("MWIR", "LWIR")
        assert after.configured()[_FILTER_MIN] == pytest.approx((3.5, 8.5), rel=1e-12)
        assert window.console.is_stale() is False
        assert window._dirty is True

    def test_refresh_adopts_a_rebound_configs(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """``configs = ConfigurationSet.load(...)`` in the console becomes the session."""
        window = _open_plain(qtbot)
        other = _dual_band_study(tmp_path, "other_study.yaml")
        window.console.run_command(f"configs = ConfigurationSet.load(r{str(other)!r})")

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.console.refresh_button.click()

        cs = window.configuration_set
        assert cs is not None
        assert cs.names() == ("MWIR", "LWIR")
        assert window._configuration_bar_dock.isVisibleTo(window) is True

    def test_refresh_still_adopts_a_rebound_sensor_in_a_plain_session(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Zero regression for the pre-4e console workflow."""
        window = _open_plain(qtbot)
        window.console.run_command(f"sensor = Sensor.load(r{str(_EXAMPLE)!r})")
        replacement = window.console.namespace_sensor()

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.console.refresh_button.click()

        assert window.sensor is replacement


# ---------------------------------------------------------------------------
# CU-213 — the shared grid-points field
# ---------------------------------------------------------------------------


class TestSharedGridPoints:
    """The study-wide spectral point count is editable in the manager and undoable."""

    def _manage(  # type: ignore[no-untyped-def]
        self, qtbot, window: RADIANTMainWindow, monkeypatch, script
    ) -> None:
        """Drive Edit → Configurations… for real, running *script* on the live dialog."""
        holder: list[ConfigurationManagerDialog] = []
        original_init = ConfigurationManagerDialog.__init__

        def _init(self: ConfigurationManagerDialog, config_set: Any, parent: Any = None) -> None:
            original_init(self, config_set, parent)
            holder.append(self)

        def _exec(self: ConfigurationManagerDialog) -> int:
            script(self)
            return int(QDialog.DialogCode.Accepted)

        monkeypatch.setattr(ConfigurationManagerDialog, "__init__", _init)
        monkeypatch.setattr(ConfigurationManagerDialog, "exec", _exec)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.configurations").trigger()
        assert holder, "the manager dialog was never built"

    def test_field_shows_the_shared_default(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        dialog = ConfigurationManagerDialog(cs, window)
        qtbot.addWidget(dialog)
        assert dialog.shared_points_editor.text() == str(cs.wavelength_points())

    def test_editing_it_round_trips_and_undoes(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        before = cs.wavelength_points()
        assert before is not None
        target = before + 37

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.shared_points_editor.setText(str(target))
            dialog.shared_points_editor.editingFinished.emit()

        self._manage(qtbot, window, monkeypatch, _script)
        assert cs.wavelength_points() == target
        # Every blank per-row placeholder now names the new number.
        assert window._dirty is True

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.undo").trigger()
        assert cs.wavelength_points() == before

        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.action("edit.redo").trigger()
        assert cs.wavelength_points() == target

    def test_it_persists_through_save_and_reopen(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        target = 321

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog.shared_points_editor.setText(str(target))
            dialog.shared_points_editor.editingFinished.emit()

        self._manage(qtbot, window, monkeypatch, _script)
        saved = tmp_path / "shared_points.yaml"
        window._save_to_path(saved)
        assert ConfigurationSet.load(saved).wavelength_points() == target

    def test_a_blank_field_restores_the_current_value(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Blank has no "inherit" meaning above the shared default, so it is refused."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        dialog = ConfigurationManagerDialog(cs, window)
        qtbot.addWidget(dialog)
        dialog.shared_points_editor.setText("")
        dialog.shared_points_editor.editingFinished.emit()
        assert dialog.shared_points_editor.text() == str(cs.wavelength_points())
        assert dialog.shape().shared_wavelength_points == cs.wavelength_points()


# ---------------------------------------------------------------------------
# Dirty-marking matrix
# ---------------------------------------------------------------------------


class TestDirtyMatrix:
    """Every model change dirties the document; a selector switch does not."""

    def test_a_configured_value_edit_dirties(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        assert window._dirty is False
        _act(qtbot, window, lambda: window._commit_configured_values(_FILTER_MIN, [3.7, 8.0]))
        assert window._dirty is True

    def test_a_shared_edit_dirties(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        assert window._dirty is False
        _act(qtbot, window, lambda: _edit_shared(window, _APERTURE, 0.42))
        assert window._dirty is True
        assert window.configuration_set is not None
        assert window.configuration_set.base.inputs()[_APERTURE] == pytest.approx(0.42, rel=1e-12)

    def test_configure_dirties(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        assert window._dirty is False
        _act(qtbot, window, lambda: window.configuration_scope.request_configure(_APERTURE))
        assert window._dirty is True

    def test_unconfigure_dirties(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Ok)
        assert window._dirty is False
        _act(qtbot, window, lambda: window.configuration_scope.request_unconfigure(_FILTER_MIN))
        assert window._dirty is True

    def test_a_manager_transaction_dirties(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        assert window._dirty is False

        def _script(dialog: ConfigurationManagerDialog) -> None:
            dialog._working.add("SWIR")

        TestSharedGridPoints()._manage(qtbot, window, monkeypatch, _script)
        assert window._dirty is True
        assert window.configuration_set is not None
        assert "SWIR" in window.configuration_set.names()

    def test_a_selector_switch_does_not_dirty(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """``active`` is view state: written on save, never a reason for a ``*``."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        assert window._dirty is False

        window._on_configuration_selected("LWIR")
        assert cs.active == "LWIR"
        assert window._dirty is False
        assert "*" not in window.windowTitle()

        # And the switch is nevertheless captured by the next save (write-on-save).
        saved = tmp_path / "active_lwir.yaml"
        window._save_to_path(saved)
        assert ConfigurationSet.load(saved).active == "LWIR"

    def test_the_title_names_a_study(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        assert "(2 configurations)" in window.windowTitle()
        assert window.windowTitle().startswith("dual_band_study.yaml")

    def test_a_plain_session_title_is_unchanged(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _open_plain(qtbot)
        assert "configuration" not in window.windowTitle()
