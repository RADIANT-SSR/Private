"""One stage card in the signal-chain strip (§4.2).

:class:`StageChip` renders a single stage as the mockup's ``.stage`` card: a
corner index badge, the namespace eyebrow, the stage title, a one-line physics
sub-caption, and a :class:`~radiant.gui.widgets.health_dot.HealthDot`. It is a
static, behaviour-free tile in GUI plan Phase 1 — clickable navigation and live
health wiring land in Phase 4. All colour/typography comes from the QSS theme via
object names (GUI plan §4.9); this file sets structure and text only.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from radiant.gui.widgets.health_dot import HealthDot


class StageChip(QFrame):
    """A single, static stage tile for the signal-chain strip.

    Parameters
    ----------
    index:
        1-based position in the chain (rendered as the corner badge).
    eyebrow:
        The lowercase namespace token shown above the title (e.g. ``"geometry"``);
        displayed upper-cased (Qt QSS has no ``text-transform``, so we upper here).
    title:
        The stage's display name (e.g. ``"Geometry"``).
    subtitle:
        A one-line physics descriptor (e.g. ``"ranges · angles"``).
    status:
        Initial health status for the dot; Phase 1 always ``"stale"``.
    parent:
        The owning widget, if any.
    """

    def __init__(
        self,
        index: int,
        eyebrow: str,
        title: str,
        subtitle: str,
        *,
        status: str = "stale",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("stageChip")
        self._title = title

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

    @property
    def stage_title(self) -> str:
        """The stage's display title (e.g. ``"Geometry"``)."""
        return self._title

    @property
    def dot(self) -> HealthDot:
        """The chip's :class:`HealthDot` (Phase 4 updates its status)."""
        return self._dot
