"""Modal-dialog lifetime for the GUI (CU-216).

A :class:`~PySide6.QtWidgets.QDialog` constructed with a parent and closed by
``exec()`` returning is **hidden, not destroyed**: Qt keeps it as a child of the
parent widget until the parent itself dies. Opening ``Edit → Configurations…``
fifty times in one session therefore leaves fifty live dialogs under the main
window. Nothing looks wrong until ``View → Light/Dark theme``, whose app-wide
``QApplication.setStyleSheet`` re-polishes the **entire live widget tree** —
including every accumulated dialog. That is the interactive half of CU-212,
whose test-side crash is fixed only inside the test session (by
``gui/tests/conftest.py::_release_widgets``); an analyst who works for hours and
then toggles the theme walks the same growing tree.

The fix is the *lifetime*, not the re-polish: narrowing ``apply_theme`` to "only
the windows it owns" is not an option, because the app-level stylesheet is
precisely what dialogs created *later* inherit.

:func:`exec_dialog` is therefore the one way a RADIANT GUI handler runs a modal
dialog. It runs the modal loop and schedules the dialog for C++ deletion as the
loop unwinds, so a session's dialog count stays flat no matter how many times
the analyst opens one.

Use it wherever a handler **owns** the modal loop. Do **not** use it in a builder
that *returns* an un-exec'd dialog for a caller to drive (``RADIANTMainWindow``'s
``open_yaml_editor`` / ``open_inspector``): those hand out an object that must
outlive the call, and the deletion belongs to whichever handler later exec's it.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

__all__ = ["exec_dialog"]


def exec_dialog(dialog: QDialog) -> int:
    """Run *dialog* modally and schedule its destruction; return its result code.

    ``deleteLater()`` only *posts* a deferred-delete event, so every attribute the
    caller reads off the dialog after this returns (``SweepDialog.sweep_result``,
    ``ConfigurationManagerDialog.shape()``, ``SpectralTableDialog.spectrum()``) is
    still valid: the C++ object survives until control reaches an event loop,
    which is after the handler has finished with it.

    Parameters
    ----------
    dialog:
        A dialog this call owns the modal loop for. Ownership transfers: the
        caller must not retain it past the surrounding handler.

    Returns
    -------
    int
        The dialog's ``QDialog.DialogCode`` result, as ``exec()`` returned it.
    """
    try:
        return int(dialog.exec())
    finally:
        dialog.deleteLater()
