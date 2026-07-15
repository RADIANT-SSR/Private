"""The Detector illustration — a Qt-drawn pixel schematic with its size (arch doc §4.4.1).

:class:`DetectorIllustration` is the **[GUI-only]** detector schematic named in arch doc
§4.4.1 (Detector row "Detector illustration with size"): a small, clean, **not-to-scale**
diagram of one detector pixel drawn with :class:`QPainter`, labelled with its cross-track and
along-track pixel pitch (``detector.pixel_pitch_x_um`` / ``pixel_pitch_y_um``, in µm — units on
the labels, R-UNITS) and its photosensitive fraction (``detector.fill_factor``). Like the
geometry schematic (ADR-0007) it is drawn from the live parameters, so editing the pixel pitch
or fill factor on the Detector **Inputs** tab redraws it (edit-and-watch); no framework plot is
needed (arch doc §4.4.1: "no framework plot needed").

The pixel **cell** is drawn preserving the *x:y aspect ratio* of the two pitches (a 2:1 pixel
draws twice as wide as tall) though the overall size is not to scale; the inner filled rectangle
is the photosensitive area, its side scaled by ``sqrt(fill_factor)`` so its **area** is the fill
fraction of the cell.

All colour comes from the design-system :class:`~radiant.gui.themes.tokens.Theme` (default the
light launch theme; :meth:`set_theme` swaps it on the Phase-9 toggle) — this file holds **no**
colour or font literal (GUI plan §4.9, review-blocking); the labels paint in the inherited
widget font. One widget class per file (Rule 19).
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from radiant.gui.themes.tokens import LIGHT, Theme

# Layout constants (geometry, not style — no colour/font literals here).
_MIN_W_PX: Final[int] = 240
_MIN_H_PX: Final[int] = 200
_MARGIN_PX: Final[int] = 44  # room for the dimension labels around the cell
_MAX_CELL_PX: Final[int] = 220  # cap the cell so a wide pixel stays inside the widget
_UNSET_MSG: Final[str] = "Set the pixel pitch to draw the detector."


class DetectorIllustration(QWidget):
    """A not-to-scale pixel schematic labelled with pitch (µm) and fill factor.

    Parameters
    ----------
    parent:
        The owning widget, if any.
    theme:
        The design-system :class:`Theme` the schematic colours follow (default: the light
        launch theme). :meth:`set_theme` swaps it and repaints.
    """

    def __init__(self, parent: QWidget | None = None, theme: Theme | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detectorIllustration")
        self._theme: Theme = theme if theme is not None else LIGHT
        self._pitch_x_um: float = 0.0
        self._pitch_y_um: float = 0.0
        self._fill_factor: float = 1.0
        self.setMinimumSize(_MIN_W_PX, _MIN_H_PX)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt override
        """A sensible default size for the schematic (fills its column, never grows)."""
        return QSize(_MIN_W_PX + 60, _MIN_H_PX + 40)

    # -- state --------------------------------------------------------------

    def set_pixel_geometry(
        self, pitch_x_um: float, pitch_y_um: float, fill_factor: float
    ) -> None:
        """Set the pixel pitch (µm, cross/along-track) + fill factor and repaint."""
        self._pitch_x_um = float(pitch_x_um)
        self._pitch_y_um = float(pitch_y_um)
        self._fill_factor = max(0.0, min(1.0, float(fill_factor)))
        self.update()

    def set_theme(self, theme: Theme) -> None:
        """Adopt *theme* and repaint (Phase-9 theme toggle)."""
        self._theme = theme
        self.update()

    @property
    def theme(self) -> Theme:
        """The active schematic theme."""
        return self._theme

    @property
    def pixel_geometry(self) -> tuple[float, float, float]:
        """The bound ``(pitch_x_um, pitch_y_um, fill_factor)`` (for tests)."""
        return (self._pitch_x_um, self._pitch_y_um, self._fill_factor)

    # -- painting -----------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 — Qt override
        """Draw the pixel cell (x:y aspect), the fill-factor inner area, and the labels."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        theme = self._theme
        painter.fillRect(self.rect(), QColor(theme.panel))

        if self._pitch_x_um <= 0.0 or self._pitch_y_um <= 0.0:
            painter.setPen(QColor(theme.muted))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, _UNSET_MSG)
            painter.end()
            return

        cell = self._cell_rect()
        # The pixel cell (outer boundary).
        painter.setPen(QPen(QColor(theme.ink_2), 2))
        painter.setBrush(QColor(theme.panel_2))
        painter.drawRect(cell)

        # The photosensitive area — area = fill_factor of the cell (side ∝ sqrt(ff)).
        scale = self._fill_factor**0.5
        inner_w = cell.width() * scale
        inner_h = cell.height() * scale
        inner = QRectF(
            cell.center().x() - inner_w / 2.0,
            cell.center().y() - inner_h / 2.0,
            inner_w,
            inner_h,
        )
        painter.setPen(QPen(QColor(theme.accent), 1))
        painter.setBrush(QColor(theme.accent_soft))
        painter.drawRect(inner)

        self._draw_labels(painter, cell)
        painter.end()

    def _cell_rect(self) -> QRectF:
        """The pixel-cell rectangle: x:y aspect from the pitches, centred, within margins."""
        avail_w = max(1.0, self.width() - 2 * _MARGIN_PX)
        avail_h = max(1.0, self.height() - 2 * _MARGIN_PX)
        # Preserve the pixel's x:y aspect; fit inside the available box, capped.
        aspect = self._pitch_x_um / self._pitch_y_um  # width / height
        if avail_w / avail_h > aspect:
            cell_h = min(avail_h, float(_MAX_CELL_PX))
            cell_w = cell_h * aspect
        else:
            cell_w = min(avail_w, float(_MAX_CELL_PX))
            cell_h = cell_w / aspect
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        return QRectF(cx - cell_w / 2.0, cy - cell_h / 2.0, cell_w, cell_h)

    def _draw_labels(self, painter: QPainter, cell: QRectF) -> None:
        """Label the width (pitch x), height (pitch y), and fill factor — units on each."""
        theme = self._theme
        painter.setPen(QColor(theme.ink))
        # Cross-track pitch (width) — centred under the cell.
        x_label = f"{self._pitch_x_um:g} µm (x)"
        below = QRectF(cell.left(), cell.bottom() + 6, cell.width(), 22)
        painter.drawText(below, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, x_label)
        # Along-track pitch (height) — to the left of the cell, vertical.
        y_label = f"{self._pitch_y_um:g} µm (y)"
        painter.save()
        painter.translate(cell.left() - 10, cell.center().y())
        painter.rotate(-90)
        painter.drawText(
            QRectF(-cell.height() / 2.0, -22, cell.height(), 22),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            y_label,
        )
        painter.restore()
        # Fill factor — centred in the photosensitive area.
        painter.setPen(QColor(theme.ink_2))
        painter.drawText(
            cell,
            Qt.AlignmentFlag.AlignCenter,
            f"fill {self._fill_factor * 100:g}%",
        )
        # A quiet "not to scale" caption, top-centre.
        painter.setPen(QColor(theme.muted))
        painter.drawText(
            QRectF(0, 6, self.width(), 18),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "detector pixel (not to scale)",
        )


__all__ = ["DetectorIllustration"]
