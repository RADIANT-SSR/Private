"""Modal dialog rendering a :class:`RadiantError`'s what / why / action / context.

:class:`ActionableErrorDialog` is the GUI's honest surface for a rejected parameter
edit (arch doc §4.3, §11; Rules 15/17). A :class:`~radiant.core.exceptions.RadiantError`
that carries the structured ``what`` / ``why`` / ``action`` / ``context`` payload
(e.g. :class:`~radiant.core.parameters.ParameterBoundsError`) is shown field by field,
verbatim; one that only carries a flat message (e.g. the
:class:`~radiant.core.exceptions.CoreValidationError` the parameter resolver raises for
an out-of-bounds or bad-enum value) shows that message as the "what". Nothing is
swallowed and nothing is paraphrased.

One widget class per file (Rule 19). Styling is entirely from the design-system QSS
theme via object names; this module sets structure and text only (GUI plan §4.9).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


def _payload(exc: BaseException) -> tuple[str, str, str, dict[str, Any]]:
    """Pull ``(what, why, action, context)`` from *exc*, tolerating flat errors.

    A structured RADIANT error (``ParameterBoundsError``) exposes the four fields;
    a flat one (``CoreValidationError``) exposes none, so its ``str`` becomes the
    ``what`` and the rest stay empty. Either way the user sees the real error.
    """
    what = str(getattr(exc, "what", "") or exc)
    why = str(getattr(exc, "why", "") or "")
    action = str(getattr(exc, "action", "") or "")
    context = getattr(exc, "context", None)
    return what, why, action, dict(context) if isinstance(context, dict) else {}


class ActionableErrorDialog(QDialog):
    """Modal what/why/action/context view of a rejected edit (Rules 15/17).

    Parameters
    ----------
    exc:
        The :class:`~radiant.core.exceptions.RadiantError` (or any exception) the
        edit raised.
    dotpath:
        The parameter the edit targeted, shown in the header.
    parent:
        The owning widget, if any.
    """

    def __init__(
        self,
        exc: BaseException,
        dotpath: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("actionableErrorDialog")
        self.setWindowTitle("Parameter Rejected")
        self.setModal(True)

        what, why, action, context = _payload(exc)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        header = QLabel(f"Cannot set “{dotpath}”", self)
        header.setObjectName("errorDialogHeader")
        header.setWordWrap(True)
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(6)
        self._add_field(form, "What", what)
        if why:
            self._add_field(form, "Why", why)
        if action:
            self._add_field(form, "Action", action)
        for key, value in context.items():
            self._add_field(form, f"context.{key}", str(value))
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _add_field(self, form: QFormLayout, label: str, text: str) -> None:
        """Add one label→value row; the value wraps and is selectable."""
        key = QLabel(label, self)
        key.setObjectName("errorDialogKey")
        value = QLabel(text, self)
        value.setObjectName("errorDialogValue")
        value.setWordWrap(True)
        value.setTextInteractionFlags(value.textInteractionFlags().TextSelectableByMouse)
        form.addRow(key, value)


__all__ = ["ActionableErrorDialog"]
