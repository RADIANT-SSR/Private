"""The bottom detail dock's tabbed panel (§4.5).

:class:`DetailTabs` is the mockup's ``.dtabs`` strip as a real ``QTabWidget`` with the
five v1 detail tabs — Spectral, MTF, Noise Budget, Variables, YAML. GUI plan Phase 1
ships each tab as an empty themed placeholder page (a centred muted prompt); the tabs
themselves are selectable so the tab styling can be judged. Phase 4 fills the pages
(Spectral/MTF/Noise/Variables) and Phase 9 the YAML view. The Console tab is Phase 8
(arch doc §4.5) and is intentionally absent from this Phase-1 five-tab set.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

# (tab label, the phase that fills it) — the muted placeholder names the phase so the
# owner reads "not yet" rather than "broken". Order matches arch doc §4.5.
_TABS: Final[tuple[tuple[str, str], ...]] = (
    ("Spectral", "Phase 4"),
    ("MTF", "Phase 4"),
    ("Noise Budget", "Phase 4"),
    ("Variables", "Phase 4"),
    ("YAML", "Phase 9"),
)

# The tab labels in order, exported for tests / later phases.
TAB_LABELS: Final[tuple[str, ...]] = tuple(label for label, _ in _TABS)


def _placeholder_page(label: str, phase: str, parent: QWidget) -> QWidget:
    """A single empty tab page with a centred muted prompt."""
    page = QWidget(parent)
    page.setObjectName("detailPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(14, 14, 14, 14)

    message = QLabel(f"{label} — populated after Evaluate ({phase})", page)
    message.setObjectName("detailPlaceholderMsg")
    message.setAlignment(Qt.AlignmentFlag.AlignCenter)
    message.setWordWrap(True)

    layout.addStretch(1)
    layout.addWidget(message)
    layout.addStretch(1)
    return page


class DetailTabs(QTabWidget):
    """The five-tab detail panel with empty themed pages (Phase 1 shell).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detailTabs")
        self.setDocumentMode(True)
        for label, phase in _TABS:
            self.addTab(_placeholder_page(label, phase, self), label)

    def tab_labels(self) -> list[str]:
        """The tab labels in order (Spectral … YAML)."""
        return [self.tabText(i) for i in range(self.count())]
