"""The welcome screen — mission-template cards + Blank config + Open recent (§4.4a).

Shown in the central canvas when no configuration is loaded (a bare launch, or
File → New), replacing what used to be dead space with the onboarding surface
the 2026-08-31 owner-confirmed brief specifies: a quiet grid of mission cards
(name, one-line blurb, mono specs line), a **Blank config** card preserving the
old File → New behaviour, and the recent-files list. Picking a card emits a
signal; the main window drives the ordinary load pipeline (one action ↔ one
API call — a card is File → Open with a known path).

Cards are plain ``QPushButton`` subclasses, so keyboard traversal, Enter/Space
activation, and the ``focus`` ring come from Qt + the theme for free. With no
templates on disk (a wheel install — ``discover_templates`` returns empty) the
grid section is absent and the screen degrades to Blank + Recent.

One widget class per file (Rule 19): ``_TemplateCard`` and ``_RecentList`` are
private helpers of :class:`WelcomeScreen`. No colour/font/size literal —
styling via object names (GUI plan §4.9).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.mission_templates import TemplateInfo, discover_templates

# Cards flow into this many columns (layout geometry, not a design token).
_COLUMNS = 3


class _TemplateCard(QPushButton):
    """One clickable mission card: name, blurb, mono specs line."""

    def __init__(self, info: TemplateInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("welcomeCard")
        self.info = info
        self.setToolTip(str(info.path))
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        name = QLabel(info.name, self)
        name.setObjectName("welcomeCardName")
        name.setWordWrap(True)
        blurb = QLabel(info.blurb, self)
        blurb.setObjectName("welcomeCardBlurb")
        blurb.setWordWrap(True)
        specs = QLabel(info.specs, self)
        specs.setObjectName("welcomeCardSpecs")
        for label in (name, blurb, specs):
            # Labels must not steal the card's click.
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            layout.addWidget(label)
        layout.addStretch(1)


class WelcomeScreen(QWidget):
    """Template cards + Blank config + Open recent for the no-config state.

    Parameters
    ----------
    recent_files:
        Recent config paths, most recent first (the SettingsStore list).
    templates:
        The template records; ``None`` runs :func:`discover_templates`.
    parent:
        The owning widget, if any.

    Signals
    -------
    templateChosen(str):
        A mission card was activated; the argument is the template path.
    blankRequested():
        The Blank config card was activated (the classic File → New).
    recentChosen(str):
        A recent-file row was activated; the argument is the config path.
    """

    templateChosen = Signal(str)
    blankRequested = Signal()
    recentChosen = Signal(str)

    def __init__(
        self,
        recent_files: list[str] | None = None,
        templates: tuple[TemplateInfo, ...] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("welcomeScreen")
        self._templates = discover_templates() if templates is None else templates

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setObjectName("welcomeScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)
        body = QWidget(scroll)
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        title = QLabel("Start a scenario", body)
        title.setObjectName("welcomeTitle")
        layout.addWidget(title)
        subtitle = QLabel(
            "Every template loads a complete, runnable mission and evaluates immediately — "
            "tune from there. Or start blank.",
            body,
        )
        subtitle.setObjectName("welcomeSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        grid_host = QWidget(body)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 8, 0, 8)
        grid.setSpacing(10)
        self._cards: list[_TemplateCard] = []
        for index, info in enumerate(self._templates):
            card = _TemplateCard(info, grid_host)
            card.clicked.connect(lambda _c=False, p=str(info.path): self.templateChosen.emit(p))
            grid.addWidget(card, index // _COLUMNS, index % _COLUMNS)
            self._cards.append(card)
        # The Blank card completes the grid (always present, even off-repo).
        blank = QPushButton(grid_host)
        blank.setObjectName("welcomeBlankCard")
        blank_layout = QVBoxLayout(blank)
        blank_name = QLabel("Blank config", blank)
        blank_name.setObjectName("welcomeCardName")
        blank_hint = QLabel("Start from schema defaults and set everything yourself.", blank)
        blank_hint.setObjectName("welcomeCardBlurb")
        blank_hint.setWordWrap(True)
        for label in (blank_name, blank_hint):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            blank_layout.addWidget(label)
        blank_layout.addStretch(1)
        blank.clicked.connect(self.blankRequested)
        n = len(self._templates)
        grid.addWidget(blank, n // _COLUMNS, n % _COLUMNS)
        self._blank_card = blank
        layout.addWidget(grid_host)

        self._recent_buttons: list[QPushButton] = []
        recent = [p for p in (recent_files or []) if Path(p).exists()]
        if recent:
            recent_title = QLabel("Open recent", body)
            recent_title.setObjectName("welcomeRecentTitle")
            layout.addWidget(recent_title)
            for path in recent:
                row = QPushButton(Path(path).name, body)
                row.setObjectName("welcomeRecentRow")
                row.setToolTip(path)
                row.clicked.connect(lambda _c=False, p=path: self.recentChosen.emit(p))
                layout.addWidget(row)
                self._recent_buttons.append(row)
        layout.addStretch(1)

    # -- accessors (tests) ---------------------------------------------------

    @property
    def cards(self) -> list[_TemplateCard]:
        """The mission cards, in display order."""
        return self._cards

    @property
    def blank_card(self) -> QPushButton:
        """The always-present Blank config card."""
        return self._blank_card

    @property
    def recent_rows(self) -> list[QPushButton]:
        """The recent-file rows (absent entries filtered out)."""
        return self._recent_buttons


__all__ = ["WelcomeScreen"]
