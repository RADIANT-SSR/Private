"""Modal-dialog lifetime: a session must not accumulate hidden dialogs (CU-216).

Category A (with a D-flavoured window-level check). A ``QDialog`` built with the
main window as its parent and closed by ``exec()`` returning is *hidden*, not
destroyed — Qt keeps it as a child of the window. Before this fix, ten
``Edit → Configurations…`` open/close cycles left **10 live dialogs** under the
window (measured offscreen), and a later ``View → Light/Dark theme`` re-polished
every one of them: ``apply_theme`` calls ``QApplication.setStyleSheet``, which
walks the whole live widget tree. That is the interactive half of CU-212, whose
only existing mitigation (``conftest.py::_release_widgets``) lives in the test
session and never runs for an analyst.

The tests below pin the three halves of the contract:

* the window-level behaviour — repeated open/close cycles leave the child count flat;
* :func:`~radiant.gui.dialog_lifetime.exec_dialog`'s two guarantees — it returns the
  dialog's own result code, and the dialog stays readable until the next event-loop
  turn (the sweep/manager handlers read ``sweep_result`` / ``shape()`` after it returns);
* the *builder* carve-out — a builder that hands an un-exec'd dialog to its caller
  (``open_yaml_editor``) must **not** free it, or the caller is left holding a corpse.

A static guard keeps new call sites on the helper, since a single missed
``dialog.exec()`` silently reopens the leak.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.dialog_lifetime import exec_dialog  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.configuration_manager_dialog import (  # noqa: E402
    ConfigurationManagerDialog,
)
from radiant.gui.widgets.inspector_dialog import InspectorDialog  # noqa: E402
from radiant.gui.widgets.schema_browser_dialog import SchemaBrowserDialog  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 20000
_CYCLES = 10  # the CU's own reproduction count


def _drain_deferred_deletes() -> None:
    """Deliver the posted ``DeferredDelete`` events, so the count is deterministic.

    ``deleteLater()`` only posts an event, and a plain ``processEvents`` delivers
    deferred deletes only as the **outermost** event loop unwinds — which never
    happens inside a test. ``sendPostedEvents(None, DeferredDelete)`` is the
    explicit drain the CU-212 release fixture uses for the same reason.
    """
    app = QApplication.instance()
    assert app is not None, "pytest-qt builds the QApplication"
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _live_dialogs(window: RADIANTMainWindow) -> list[QDialog]:
    """Every dialog still parented to *window*, after the delete queue is drained."""
    _drain_deferred_deletes()
    return list(window.findChildren(QDialog))


def _window(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """The shipped example in a window, settled past its first auto-evaluation."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestNoAccumulation:
    """The window-level symptom the CU describes, measured before and after."""

    def test_cancelling_the_configuration_manager_leaves_no_live_dialogs(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """Ten Edit → Configurations… cancels used to leave ten live dialogs; now zero.

        Only the modal loop is replaced (Cancel), so the shipped handler — which owns
        the ``exec()`` and therefore the deletion — runs end to end.
        """
        window = _window(qtbot)
        monkeypatch.setattr(
            ConfigurationManagerDialog, "exec", lambda self: int(QDialog.DialogCode.Rejected)
        )
        assert _live_dialogs(window) == []

        for _ in range(_CYCLES):
            window.action("edit.configurations").trigger()

        assert _live_dialogs(window) == [], (
            f"{len(_live_dialogs(window))} dialog(s) survived {_CYCLES} open/close cycles"
        )

    def test_reopening_the_schema_browser_leaves_no_live_dialogs(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """A second, independently-wired handler (Tools → Parameter Schema Browser)."""
        window = _window(qtbot)
        monkeypatch.setattr(
            SchemaBrowserDialog, "exec", lambda self: int(QDialog.DialogCode.Rejected)
        )

        for _ in range(_CYCLES):
            window.action("tools.schema").trigger()

        assert _live_dialogs(window) == []

    def test_reopening_the_inspector_leaves_no_live_dialogs(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The **non-modal** half of the same symptom (CU-283).

        ``Tools → Inspector`` is shown with ``show()``, not ``exec()``, so
        :func:`exec_dialog` never sees it; closing a non-modal dialog hides it and
        Qt keeps it parented to the window. Measured before the fix: **10 live
        ``InspectorDialog`` children after 10 open/close cycles**. The handler now
        sets ``WA_DeleteOnClose`` on the instance it shows, so ``close()`` destroys
        it — while ``open_inspector`` itself (the builder tests call) is untouched
        and still hands back a dialog that outlives the call.
        """
        window = _window(qtbot)
        assert [d for d in _live_dialogs(window) if isinstance(d, InspectorDialog)] == []

        for _ in range(_CYCLES):
            window.action("tools.inspector").trigger()
            for dialog in window.findChildren(InspectorDialog):
                dialog.close()

        survivors = [d for d in _live_dialogs(window) if isinstance(d, InspectorDialog)]
        assert survivors == [], (
            f"{len(survivors)} InspectorDialog(s) survived {_CYCLES} open/close cycles"
        )


class TestExecDialogContract:
    """:func:`exec_dialog`'s two guarantees, unit-level."""

    def test_returns_the_dialogs_own_result_code(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = QDialog()
        qtbot.addWidget(dialog)
        dialog.exec = lambda: int(QDialog.DialogCode.Accepted)  # type: ignore[method-assign]

        assert exec_dialog(dialog) == QDialog.DialogCode.Accepted

    def test_dialog_is_readable_until_the_next_event_loop_turn(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The handlers read results off the dialog *after* the call — that must work.

        ``_on_run_sweep`` reads ``dialog.sweep_result`` and
        ``_on_manage_configurations`` reads ``dialog.shape()`` after the modal loop
        returns. ``deleteLater`` only posts, so both are still valid; the object is
        freed on the following loop turn.
        """
        dialog = QDialog()
        qtbot.addWidget(dialog)
        dialog.exec = lambda: int(QDialog.DialogCode.Accepted)  # type: ignore[method-assign]
        dialog.setObjectName("still-alive")

        exec_dialog(dialog)
        assert dialog.objectName() == "still-alive"  # not yet freed — attributes readable

        _drain_deferred_deletes()
        with pytest.raises(RuntimeError):  # C++ object gone — the point of the fix
            dialog.objectName()

    def test_exceptions_from_the_modal_loop_still_free_the_dialog(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The deletion is in a ``finally``: a raising dialog must not leak either."""
        dialog = QDialog()
        qtbot.addWidget(dialog)

        def _boom() -> int:
            raise RuntimeError("modal loop blew up")

        dialog.exec = _boom  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="modal loop blew up"):
            exec_dialog(dialog)

        _drain_deferred_deletes()
        with pytest.raises(RuntimeError):
            dialog.objectName()


class TestBuilderCarveOut:
    """Builders that *return* an un-exec'd dialog keep it alive for their caller."""

    def test_open_yaml_editor_returns_a_dialog_that_survives_a_loop_turn(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """``open_yaml_editor`` hands the dialog out; deleting it there would break
        every caller (tests drive Apply/Revert on it without a modal loop)."""
        window = _window(qtbot)
        dialog = window.open_yaml_editor()
        assert dialog is not None

        _drain_deferred_deletes()
        assert dialog.isEnabled()  # still a live C++ object — no RuntimeError

    def test_open_inspector_returns_a_dialog_that_survives_a_loop_turn(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _window(qtbot)
        dialog = window.open_inspector()  # a result exists after the first pass
        assert dialog is not None

        _drain_deferred_deletes()
        assert dialog.isEnabled()


class TestStaticGuard:
    """One missed call site silently reopens the leak, so scan for them."""

    # ``app.py`` runs the ``QApplication`` event loop, not a dialog; ``dialog_lifetime``
    # is the one module that legitimately calls ``QDialog.exec`` directly.
    _EXEMPT = {"app.py", "dialog_lifetime.py"}
    _DIRECT_EXEC = re.compile(r"\.exec\(\)")

    def test_no_module_calls_dialog_exec_directly(self) -> None:
        gui = Path(__file__).resolve().parents[1]
        offenders: list[str] = []
        for path in sorted(gui.rglob("*.py")):
            if path.name in self._EXEMPT or "tests" in path.parts:
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if self._DIRECT_EXEC.search(line):
                    offenders.append(f"{path.relative_to(gui)}:{lineno}: {line.strip()}")

        assert offenders == [], (
            "modal dialogs must run through radiant.gui.dialog_lifetime.exec_dialog so "
            "they are destroyed rather than accumulated under their parent (CU-216); "
            "if a call site is genuinely not a dialog, exempt its module with a reason:\n"
            + "\n".join(offenders)
        )
