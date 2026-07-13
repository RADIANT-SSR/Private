"""The Spectral detail tab (arch doc §4.5): the three spectral-radiance figures.

:class:`SpectralTab` shows one of the three ``result.plot`` spectral accessors —
source (``spectral_source``), atmosphere (``spectral_atmosphere``), or in-band
(``spectral_inband``) — selected on a small themed combo box and rendered in an embedded
matplotlib canvas. Every figure is produced by the **public** ``result.plot`` surface
(one GUI action ↔ one API call, GUI plan §4.1); no plotting logic lives in GUI code.

Pre-result the tab shows a themed "evaluate first" state; :meth:`show_result` fills it on
every successful evaluation. An accessor that raises :class:`ApiValidationError` (a frame
absent for this regime) surfaces its actionable message in place of the figure rather than
a blank or a faked plot (Rules 15/17).

All colour/typography comes from the QSS theme via object names (GUI plan §4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from radiant.api.errors import ApiValidationError
from radiant.api.inspect import ResultPlotNamespace
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas

if TYPE_CHECKING:
    from radiant.api import ChainResult

_EMPTY: Final[str] = "Spectral radiance — evaluate to populate."

# (combo label, result.plot accessor). Discovered order matches arch doc §4.4
# (Source → Atmosphere → Spectral Integration).
_FIGURES: Final[tuple[tuple[str, str], ...]] = (
    ("Source", "spectral_source"),
    ("Atmosphere", "spectral_atmosphere"),
    ("In-band", "spectral_inband"),
)


class SpectralTab(QWidget):
    """Selectable source / atmosphere / in-band spectral figures (arch doc §4.5).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("spectralTab")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._stack = QStackedWidget(self)

        # Pre-evaluate empty state.
        self._empty = QLabel(_EMPTY, self)
        self._empty.setObjectName("detailPlaceholderMsg")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)

        # Populated content: a selector row over the matplotlib canvas.
        self._content = QWidget(self)
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(10, 8, 10, 10)
        content_layout.setSpacing(8)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)
        selector_label = QLabel("Frame", self._content)
        selector_label.setObjectName("spectralSelectorLabel")
        self._selector = QComboBox(self._content)
        self._selector.setObjectName("spectralSelector")
        for label, accessor in _FIGURES:
            self._selector.addItem(label, accessor)
        self._selector.currentIndexChanged.connect(self._render_current)
        selector_row.addWidget(selector_label)
        selector_row.addWidget(self._selector)
        selector_row.addStretch(1)

        self._canvas = MatplotlibCanvas(self._content)
        self._message = QLabel("", self._content)
        self._message.setObjectName("detailPlaceholderMsg")
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        self._message.setVisible(False)

        content_layout.addLayout(selector_row)
        content_layout.addWidget(self._canvas, 1)
        content_layout.addWidget(self._message)

        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._content)
        outer.addWidget(self._stack)

        self._result: ChainResult | None = None

    # -- accessors (tests) --------------------------------------------------

    @property
    def selector(self) -> QComboBox:
        """The frame selector combo box."""
        return self._selector

    @property
    def canvas(self) -> MatplotlibCanvas:
        """The embedded matplotlib canvas."""
        return self._canvas

    def is_populated(self) -> bool:
        """True once a result has been shown (content page active)."""
        return self._stack.currentWidget() is self._content

    def current_accessor(self) -> str:
        """The ``result.plot`` accessor the selector currently names."""
        return str(self._selector.currentData())

    # -- result delivery ----------------------------------------------------

    def show_result(self, result: ChainResult) -> None:
        """Store *result* and render the currently-selected spectral figure."""
        self._result = result
        self._stack.setCurrentWidget(self._content)
        self._render_current()

    def _render_current(self) -> None:
        """Render the selected accessor's figure (or its actionable error message)."""
        if self._result is None:
            return
        accessor = str(self._selector.currentData())
        try:
            figure = getattr(ResultPlotNamespace(self._result), accessor)()
        except ApiValidationError as exc:
            # A frame absent for this regime — show the actionable text, never a blank.
            self._message.setText(str(exc))
            self._message.setVisible(True)
            self._canvas.setVisible(False)
            return
        self._message.setVisible(False)
        self._canvas.setVisible(True)
        self._canvas.show_figure(figure)
