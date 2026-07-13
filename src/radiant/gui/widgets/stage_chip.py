"""One stage card in the signal-chain strip (§4.2).

:class:`StageChip` renders a single stage as the mockup's ``.stage`` card: a
corner index badge, the namespace eyebrow, the stage title, a one-line physics
sub-caption, and a :class:`~radiant.gui.widgets.health_dot.HealthDot`.

GUI plan Phase 4 makes the chip **clickable** (navigation only, no API call — it
emits its stage *namespace*, the real schema namespace, distinct from the shortened
eyebrow display; CU-106) and gives it a **selected** state and a chip-level **status**
tint. Per §8.4 a warned/errored/stale stage sets its background to the matching
``<status>-soft`` tint and its border to the ``<status>`` token, and a selected stage
uses the ``focus-soft`` background + ``focus`` border. All colour/typography comes
from the QSS theme via the ``status`` / ``selected`` dynamic properties and object
names (GUI plan §4.9); this file sets structure, text, and those properties only.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from radiant.gui.widgets.health_dot import VALID_STATUSES, HealthDot


class StageChip(QFrame):
    """A single, clickable stage tile for the signal-chain strip.

    Parameters
    ----------
    index:
        1-based position in the chain (rendered as the corner badge).
    namespace:
        The stage's **real** parameter/schema namespace (e.g. ``"geometry"``,
        ``"spectral_integration"``) — what a click navigates to. Distinct from the
        shortened *eyebrow* display (CU-106): the eyebrow may abbreviate.
    eyebrow:
        The lowercase token shown above the title (e.g. ``"spectral"``); displayed
        upper-cased (Qt QSS has no ``text-transform``, so we upper here).
    title:
        The stage's display name (e.g. ``"Geometry"``).
    subtitle:
        A one-line physics descriptor (e.g. ``"ranges · angles"``).
    status:
        Initial health status for the dot and chip tint; one of
        :data:`~radiant.gui.widgets.health_dot.VALID_STATUSES`.
    parent:
        The owning widget, if any.

    Signals
    -------
    clicked(str):
        Emitted with this chip's :attr:`namespace` when the tile is clicked
        (navigation only — no API call).
    """

    clicked = Signal(str)

    def __init__(
        self,
        index: int,
        namespace: str,
        eyebrow: str,
        title: str,
        subtitle: str,
        *,
        status: str = "stale",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("stageChip")
        self._namespace = namespace
        self._title = title
        self._status = ""
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(2)

        # Header row: index badge + eyebrow on the left, health dot on the right.
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        num = QLabel(str(index), self)
        num.setObjectName("stageChipNum")

        eyebrow_label = QLabel(eyebrow.upper(), self)
        eyebrow_label.setObjectName("stageChipEyebrow")

        self._dot = HealthDot(status, self)

        header.addWidget(num)
        header.addWidget(eyebrow_label)
        header.addStretch(1)
        header.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)

        title_label = QLabel(title, self)
        title_label.setObjectName("stageChipTitle")

        sub_label = QLabel(subtitle, self)
        sub_label.setObjectName("stageChipSub")

        outer.addLayout(header)
        outer.addWidget(title_label)
        outer.addWidget(sub_label)
        outer.addStretch(1)

        # Seed the chip-level status property (drives the §8.4 background tint).
        self.set_status(status)
        self._refresh_style()

    # -- accessors ----------------------------------------------------------

    @property
    def namespace(self) -> str:
        """The stage's real schema namespace (what a click navigates to)."""
        return self._namespace

    @property
    def stage_title(self) -> str:
        """The stage's display title (e.g. ``"Geometry"``)."""
        return self._title

    @property
    def dot(self) -> HealthDot:
        """The chip's :class:`HealthDot`."""
        return self._dot

    @property
    def status(self) -> str:
        """The current health status (one of :data:`VALID_STATUSES`)."""
        return self._status

    @property
    def selected(self) -> bool:
        """Whether this chip is the currently selected stage."""
        return self._selected

    # -- state --------------------------------------------------------------

    def set_status(self, status: str) -> None:
        """Set the chip + dot health status, re-polishing so the QSS tint updates.

        Raises :class:`ValueError` on an unknown status — an unstyled chip would be a
        silent failure (Rule 17), so a bad state is heard immediately (mirrors
        :meth:`HealthDot.set_status`).
        """
        if status not in VALID_STATUSES:
            raise ValueError(f"StageChip status must be one of {VALID_STATUSES}, got {status!r}")
        self._status = status
        self._dot.set_status(status)
        self.setProperty("status", status)
        self._refresh_style()

    def set_selected(self, selected: bool) -> None:
        """Mark this chip selected/unselected (drives the §8.4 focus styling)."""
        self._selected = selected
        self.setProperty("selected", "true" if selected else "false")
        self._refresh_style()

    # -- interaction --------------------------------------------------------

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        """Emit :attr:`clicked` with the namespace on a left-click inside the tile."""
        inside = self.rect().contains(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and inside:
            self.clicked.emit(self._namespace)
        super().mouseReleaseEvent(event)

    def _refresh_style(self) -> None:
        """Force a style re-polish so a status/selected change re-colours the chip."""
        style = self.style()
        style.unpolish(self)
        style.polish(self)
