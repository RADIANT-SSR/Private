"""Shared pytest-qt configuration for the GUI test suite.

Forces the Qt ``offscreen`` platform plugin so the whole suite runs headless in
CI and on a developer machine without a display (GUI plan §4.10). The env var
must be set **before** any :class:`QApplication` is constructed, so it is set at
module import — earlier than any fixture body runs.

Skips the entire GUI suite cleanly if PySide6 (the optional ``gui`` extra) is not
installed, so a core-only checkout does not error out collecting these tests.
"""

from __future__ import annotations

import os

import pytest

# Headless Qt — set before QApplication exists (pytest-qt builds it lazily).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# The GUI suite is meaningless without the gui extra; skip collection if absent.
pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")


@pytest.fixture(autouse=True)
def _isolate_qsettings(tmp_path):  # type: ignore[no-untyped-def]
    """Point org/app ``QSettings`` at a fresh per-test temp dir (CU-115).

    The pinned-panel now persists via ``QSettings`` (CU-115). Without isolation, a
    window test that pins/unpins would write to — and read back from — the real user
    config, leaking state between tests. Redirecting the ``UserScope`` IniFormat path
    per test gives every test an empty, throwaway settings store.
    """
    from PySide6.QtCore import QSettings

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    yield
