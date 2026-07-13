"""Themed "visualization not yet available (Gap N)" panel (GUI plan §4.1).

:class:`StageGapPanel` is what the central canvas shows when a selected stage's
arch-doc §4.4 default figure is one the ``result.plot`` surface does **not** carry
(the spectral-radiance figures for Source, Atmosphere, Spectral Integration). Ground
rule §4.1 forbids faking a figure or reaching into stage internals to build one — the
missing figure is filed in ``docs/tracking/gaps.md`` and this panel names the gap so
the owner sees an honest "tracked, not yet built" state rather than a blank or a
plausible-but-wrong plot.

All colour/typography comes from the QSS theme via object names (GUI plan §4.9); this
file sets structure and text only.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_HEADER: Final[str] = "Visualization not yet available"
_TRACKED: Final[str] = "Tracked in docs/tracking/gaps.md — the figure is not faked (GUI plan §4.1)."


class StageGapPanel(QWidget):
    """A centered panel naming the gap that blocks a stage's default figure.

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stageGapPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._header = QLabel(_HEADER, self)
        self._header.setObjectName("stageGapHeader")
        self._header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._detail = QLabel("", self)
        self._detail.setObjectName("stageGapDetail")
        self._detail.setWordWrap(True)
        self._detail.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._tracked = QLabel(_TRACKED, self)
        self._tracked.setObjectName("stageGapTracked")
        self._tracked.setWordWrap(True)
        self._tracked.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._header)
        layout.addWidget(self._detail)
        layout.addWidget(self._tracked)

        self._gap_number: int | None = None

    def show_gap(self, gap_number: int, figure_detail: str) -> None:
        """Name the *gap_number* and the missing *figure_detail* this stage needs."""
        self._gap_number = gap_number
        self._detail.setText(f"{figure_detail}  —  Gap {gap_number}")

    @property
    def gap_number(self) -> int | None:
        """The gap number currently displayed (``None`` before the first :meth:`show_gap`)."""
        return self._gap_number

    def detail_text(self) -> str:
        """The detail line currently shown (for tests)."""
        return self._detail.text()
