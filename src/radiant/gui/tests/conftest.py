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
