"""Shared pytest-qt configuration for the GUI test suite.

Forces the Qt ``offscreen`` platform plugin so the whole suite runs headless in
CI and on a developer machine without a display (GUI plan §4.10). The env var
must be set **before** any :class:`QApplication` is constructed, so it is set at
module import — earlier than any fixture body runs.

Skips the entire GUI suite cleanly if PySide6 (the optional ``gui`` extra) is not
installed, so a core-only checkout does not error out collecting these tests.

**Widget lifetime (CU-212).** ``pytest-qt``'s ``addWidget`` *closes* a widget at
teardown but does not force its C++ deletion, so every window a module opens stays
alive for the rest of the session. Past ~two dozen accumulated main windows, the
app-wide ``apply_theme`` re-polish (``QApplication.setStyleSheet``, which walks the
whole live widget tree) segfaults — a threshold, not a regression, and one that made
the gate battery a function of how many GUI tests exist. :func:`_release_widgets`
below is the session-wide fix that replaces the per-module ``_release_windows``
copies Phases 4b–4d carried: after **every** test it closes, re-parents, and
``deleteLater``s each remaining top-level widget, drains the deferred-delete queue,
and closes any matplotlib figures the test opened.
"""

from __future__ import annotations

import os

import pytest

# Headless Qt — set before QApplication exists (pytest-qt builds it lazily).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# The GUI suite is meaningless without the gui extra; skip collection if absent.
pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")


@pytest.fixture(autouse=True)
def _isolate_qsettings(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """Point every persisted GUI preference at a fresh per-test temp dir (CU-115).

    Without isolation a window test writes to — and reads back from — the real user
    config, leaking state between tests *and* onto the developer's machine.

    Two mechanisms are needed, because the GUI has two persistence surfaces that
    construct :class:`QSettings` differently:

    * :class:`~radiant.gui.widgets.pinned_panel.PinnedPanel` passes ``IniFormat``
      explicitly, so redirecting the ``UserScope`` INI path is enough for it.
    * :class:`~radiant.gui.settings_store.SettingsStore` uses the
      ``QSettings(organization, application)`` constructor, and **that constructor
      ignores** :meth:`QSettings.setDefaultFormat`: on macOS it resolves to
      ``NativeFormat`` and writes straight to
      ``~/Library/Preferences/com.RADIANT.RADIANT GUI.plist`` no matter what the
      default format or the INI path is set to. Redirecting the path alone was
      therefore silently ineffective for it — the theme, recent-files, and panel
      state of a real user were being overwritten by every GUI test run, which is
      how a developer's chosen dark theme kept reverting to the light default.

    The store is isolated by swapping the ``QSettings`` symbol its module resolves
    for a temp-file factory. Only the *default* construction goes through it, so a
    test that injects its own :class:`QSettings` is unaffected.
    """
    from PySide6.QtCore import QSettings

    from radiant.gui import settings_store as settings_store_module

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))

    ini_path = tmp_path / "radiant-gui-settings.ini"

    def _scratch_qsettings(*_args: object, **_kwargs: object) -> QSettings:
        """Ignore the requested org/app and hand back a throwaway INI-backed store."""
        return QSettings(str(ini_path), QSettings.Format.IniFormat)

    monkeypatch.setattr(settings_store_module, "QSettings", _scratch_qsettings)
    yield


@pytest.fixture(autouse=True)
def _release_widgets():  # type: ignore[no-untyped-def]
    """Delete every top-level widget a test leaves behind, after each test (CU-212).

    ``QWidget.close()`` hides a widget; only ``deleteLater()`` plus a turn of the
    event loop actually frees the C++ object, and only a freed object is out of the
    tree ``QApplication.setStyleSheet`` walks. Without this, windows accumulate for
    the whole session and the theme test's first ``apply_theme`` eventually crashes
    the interpreter.

    The teardown is deliberately defensive rather than clever:

    * it iterates a **snapshot** of ``topLevelWidgets()`` — deleting a parent can
      remove children from the live list mid-iteration;
    * a widget already destroyed on the C++ side raises ``RuntimeError`` on any
      access, which is skipped (the object is gone, which is the goal);
    * the deferred-delete queue is drained explicitly via ``sendPostedEvents(None,
      QEvent.Type.DeferredDelete)``, because a plain ``processEvents`` only delivers
      those events when the *outermost* event loop unwinds — which never happens
      inside a test;
    * matplotlib figures are closed too — the suite's canvases hold ``pyplot``
      figures, which leak independently of Qt ("More than 20 figures have been
      opened").

    Widgets the ``QApplication`` itself owns transiently (e.g. Qt's internal
    tooltip/menu windows) are left alone: they carry no ``parent()`` and no test
    reference, and Qt reuses them.
    """
    yield

    import contextlib

    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:  # pragma: no cover - pytest-qt always builds one
        return
    for widget in list(app.topLevelWidgets()):
        with contextlib.suppress(RuntimeError):
            widget.close()
            widget.setParent(None)
            widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()

    try:
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover - matplotlib ships with the gui extra
        return
    plt.close("all")
