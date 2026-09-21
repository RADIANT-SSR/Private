"""A plots-beside-panel splitter that stacks when the pane is too narrow (CU-363).

One widget class per file (Rule 19). A stage sub-view that arranges its figures
beside an inputs panel gives the figures a readable minimum width (CU-241) and
the panel its own; at the default 1440×900 layout the two minimums summed to
more than the sub-view's viewport, so the scroll area grew the content sideways
and the panel's right edge — the value boxes — was clipped behind a horizontal
scrollbar ("2048" read "204", "18 µm" read "18 µ"). Neither minimum is wrong;
side-by-side is simply the wrong arrangement at that width. This splitter
watches its enclosing scroll viewport and flips to a vertical stack whenever
the side-by-side minimum no longer fits, back to horizontal when it does.
"""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt
from PySide6.QtWidgets import QScrollArea, QSplitter, QWidget

__all__ = ["ResponsiveSplitter"]


class ResponsiveSplitter(QSplitter):
    """Horizontal by preference; vertical when its children cannot fit side by side."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._viewport: QWidget | None = None

    def side_by_side_min_width(self) -> int:
        """The width the children need beside each other (their minimums plus handles)."""
        total = 0
        for index in range(self.count()):
            child = self.widget(index)
            total += max(child.minimumSizeHint().width(), child.minimumWidth())
        return total + self.handleWidth() * max(self.count() - 1, 0)

    def fit_to(self, available_width: int) -> Qt.Orientation:
        """Choose the orientation for *available_width* and apply it; return it."""
        wanted = (
            Qt.Orientation.Horizontal
            if available_width >= self.side_by_side_min_width()
            else Qt.Orientation.Vertical
        )
        if wanted != self.orientation():
            self.setOrientation(wanted)
            # The size hint just changed shape; the enclosing scroll area only
            # re-fits its content on a layout request, so post one.
            self.updateGeometry()
            parent = self.parentWidget()
            if parent is not None and parent.layout() is not None:
                parent.layout().activate()
                parent.updateGeometry()
            # The scroll area re-fits its content widget only on its own layout
            # request, and a request from a child stops at the viewport.
            area = self._viewport.parentWidget() if self._viewport is not None else None
            if isinstance(area, QScrollArea):
                QCoreApplication.postEvent(area, QEvent(QEvent.Type.LayoutRequest))
        return wanted

    def follow(self, viewport: QWidget) -> None:
        """Track *viewport*'s width (the enclosing scroll area's) from now on."""
        if viewport is self._viewport:
            return
        if self._viewport is not None:
            self._viewport.removeEventFilter(self)
        self._viewport = viewport
        viewport.installEventFilter(self)
        self.fit_to(viewport.width())

    def showEvent(self, event: QEvent) -> None:  # noqa: N802 — Qt override
        super().showEvent(event)
        if self._viewport is None:
            self._attach_to_viewport()
        else:
            self.fit_to(self._viewport.width())

    def _attach_to_viewport(self) -> None:
        """Fallback: follow the nearest enclosing scroll area's viewport."""
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                self.follow(parent.viewport())
                return
            parent = parent.parentWidget()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt override
        if watched is self._viewport and event.type() == QEvent.Type.Resize:
            self.fit_to(watched.width())  # type: ignore[attr-defined]
        return super().eventFilter(watched, event)
