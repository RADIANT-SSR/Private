"""A wrapping horizontal layout — one computation, one module (Rule 19).

:class:`FlowLayout` lays its items out left to right and wraps to a new line when the
next item would overflow the width, reporting a height that depends on the width
(``hasHeightForWidth``) so the host can grow vertically instead of clipping. It is
Qt's canonical flow-layout example reduced to what RADIANT needs (CU-376 F-38: the
Performance stage's *Compute:* checkbox row showed two of five groups at 1024×640).

Styling is untouched (no colour, font or size literal); spacing comes from the host
style's layout spacing when not set explicitly.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QWidget

__all__ = ["FlowLayout"]


class FlowLayout(QLayout):
    """Left-to-right layout that wraps to the next line when the width runs out."""

    def __init__(self, parent: QWidget | None = None, spacing: int = -1) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    # -- QLayout interface --------------------------------------------------

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802 — Qt override
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 — Qt override
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 — Qt override
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802 — Qt override
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 — Qt override
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 — Qt override
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802 — Qt override
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt override
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802 — Qt override
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    # -- layout -------------------------------------------------------------

    def _gap(self) -> int:
        if self._spacing >= 0:
            return self._spacing
        parent = self.parentWidget()
        if parent is None:
            return 8
        return parent.style().layoutSpacing(
            QSizePolicy.ControlType.PushButton,
            QSizePolicy.ControlType.PushButton,
            Qt.Orientation.Horizontal,
        )

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y = area.x(), area.y()
        line_height = 0
        gap = self._gap()
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + gap
            if next_x - gap > area.right() + 1 and line_height > 0:
                x = area.x()
                y = y + line_height + gap
                next_x = x + hint.width() + gap
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()
