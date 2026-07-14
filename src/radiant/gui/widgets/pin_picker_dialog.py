"""Modal picker to pin an arbitrary metric onto the right-rail Pinned panel (§4.5).

:class:`PinPickerDialog` backs the Pinned panel's ``+ Pin…`` action. It lists the
metrics on the current result's metric surface (:meth:`ChainResult.metric_records`)
that are not already pinned, each with its value + unit (R-UNITS), and returns the
selected metric key so the caller can add a :class:`~radiant.gui.widgets.pinned_card.PinnedCard`.

**Scope (Step A):** the picker offers the **metric surface** only. Pinning an
arbitrary intermediate ``stage_outputs`` value is deferred to the contextual-layout
Step B (per-stage center views), where each stage output has a natural in-place pin
affordance — tracked as **CU-115**. Pinning any performance/GIQE metric is available
now, which covers the ratified default set and the common "pin one more metric" case.

One widget class per file (Rule 19). Styling is entirely themed via object names
(GUI plan §4.9); this file sets structure and text only.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.metric_format import format_metric_value

if TYPE_CHECKING:
    from radiant.api import ChainResult

_EMPTY_TEXT: str = "Every available metric is already pinned."
_HEADER: str = "Pin a metric from the result surface"


class PinPickerDialog(QDialog):
    """Modal list of pinnable metrics; :meth:`selected_key` is the chosen metric key.

    Parameters
    ----------
    result:
        The current :class:`~radiant.api.ChainResult`; its metric surface supplies
        the candidate list (with values + units).
    already_pinned:
        Metric keys already on the Pinned panel — excluded from the list.
    parent:
        The owning widget, if any.
    """

    def __init__(
        self,
        result: ChainResult,
        already_pinned: Iterable[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("pinPickerDialog")
        self.setWindowTitle("Pin a value")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        header = QLabel(_HEADER, self)
        header.setObjectName("pinPickerHeader")
        header.setWordWrap(True)
        layout.addWidget(header)

        pinned = set(already_pinned)
        self._list = QListWidget(self)
        self._list.setObjectName("pinPickerList")
        for rec in result.metric_records():
            if rec.name in pinned:
                continue
            value = format_metric_value(rec.value, rec.unit)
            item = QListWidgetItem(f"{rec.name}    {value}", self._list)
            item.setData(_KEY_ROLE, rec.name)
        layout.addWidget(self._list, 1)

        if self._list.count() == 0:
            empty = QLabel(_EMPTY_TEXT, self)
            empty.setObjectName("pinPickerEmpty")
            empty.setWordWrap(True)
            layout.addWidget(empty)
        else:
            self._list.setCurrentRow(0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self._ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_button.setEnabled(self._list.count() > 0)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._list.itemDoubleClicked.connect(lambda _item: self.accept())
        layout.addWidget(buttons)

    @property
    def list_widget(self) -> QListWidget:
        """The candidate-metric list (for tests)."""
        return self._list

    def selected_key(self) -> str | None:
        """The metric key of the current selection, or ``None`` when the list is empty."""
        item = self._list.currentItem()
        if item is None:
            return None
        key = item.data(_KEY_ROLE)
        return str(key) if key is not None else None


# Qt user-data role for the metric key carried by each list item.
_KEY_ROLE: int = 0x0100 + 1  # Qt.UserRole + 1


__all__ = ["PinPickerDialog"]
