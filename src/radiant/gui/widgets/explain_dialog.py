"""Modal dialog rendering ``Sensor.explain(dotpath)`` for one parameter.

:class:`ExplainDialog` backs the parameter tree's right-click **Explain** action
(arch doc §4.3). It shows the human-readable provenance walkthrough
:meth:`~radiant.api.sensor.Sensor.explain` returns — value + units, description,
provenance, source, and any consistency-group derivation — verbatim, in the mono
face the design system uses for values.

Design decision (recorded per the task): Explain renders in a **themed modal dialog**,
not the status bar or a detail tab. Arch doc §4.3 lists Explain among the right-click
actions without fixing a surface; the menu structure (§10) already exposes
"Tools → Explain Parameter…", so a dialog is the surface consistent with that menu and
keeps the multi-line explanation readable without stealing the transient status bar or
a not-yet-built detail tab. Recorded in arch doc §4.3.

One widget class per file (Rule 19). Styling is entirely from the design-system QSS
theme via object names (GUI plan §4.9).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class ExplainDialog(QDialog):
    """Modal view of ``Sensor.explain(dotpath)`` for a single parameter (§4.3).

    Parameters
    ----------
    dotpath:
        The parameter explained (shown in the header and window title).
    explanation:
        The text returned by :meth:`~radiant.api.sensor.Sensor.explain`.
    parent:
        The owning widget, if any.
    """

    def __init__(
        self,
        dotpath: str,
        explanation: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("explainDialog")
        self.setWindowTitle(f"Explain — {dotpath}")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        header = QLabel(dotpath, self)
        header.setObjectName("explainDialogHeader")
        header.setWordWrap(True)
        layout.addWidget(header)

        self._body = QPlainTextEdit(self)
        self._body.setObjectName("explainDialogBody")
        self._body.setReadOnly(True)
        self._body.setPlainText(explanation)
        layout.addWidget(self._body)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @property
    def body(self) -> QPlainTextEdit:
        """The read-only pane holding the explanation text."""
        return self._body


__all__ = ["ExplainDialog"]
