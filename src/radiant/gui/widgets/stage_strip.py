"""The 9-stage geometry-first signal-chain strip (§4.2).

:class:`StageStrip` is the horizontal band of :class:`~radiant.gui.widgets.stage_chip.StageChip`
tiles in ADR-0006 chain order (Geometry → … → Performance). GUI plan Phase 1 ships
it static: every chip carries a ``stale`` health dot and no click behaviour. Phase 4
makes the chips clickable (navigation only, no API call) and drives the dots from the
per-stage health the chain reports.

``STAGES`` is the canonical chain definition (order, title, one-line physics
sub-caption) consumed by this strip; it is the single source of the strip's content.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtWidgets import QHBoxLayout, QWidget

from radiant.gui.widgets.stage_chip import StageChip

# (eyebrow namespace token, display title, one-line physics sub-caption), in
# ADR-0006 geometry-first chain order. The nine v1 stages (arch doc §4.2).
STAGES: Final[tuple[tuple[str, str, str], ...]] = (
    ("geometry", "Geometry", "ranges · angles"),
    ("source", "Source", "L_src(λ)"),
    ("atmosphere", "Atmosphere", "τ · L_path"),
    ("optics", "Optics", "PSF · MTF"),
    ("platform", "Platform", "smear · jitter"),
    ("spectral", "Spectral Int.", "∫ dλ"),
    ("detector", "Detector", "QE · noise"),
    ("readout", "Readout", "TDI · ADC"),
    ("performance", "Performance", "SNR · NIIRS"),
)

# The ordered stage titles, exported so tests and later phases can assert chain order
# without re-deriving it from the tuple above.
STAGE_TITLES: Final[tuple[str, ...]] = tuple(title for _, title, _ in STAGES)


class StageStrip(QWidget):
    """The static, 9-chip signal-chain strip (Phase 1 shell).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stageStrip")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self._chips: list[StageChip] = []
        for index, (eyebrow, title, subtitle) in enumerate(STAGES, start=1):
            chip = StageChip(index, eyebrow, title, subtitle, status="stale", parent=self)
            self._chips.append(chip)
            layout.addWidget(chip, 1)

    @property
    def chips(self) -> list[StageChip]:
        """The stage chips, in chain order (Geometry first)."""
        return list(self._chips)
