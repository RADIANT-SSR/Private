"""``AngleToggleOverlay`` — the on-canvas angle-arc reveal selector (bottom-left overlay).

The interactive counterpart to the QPainter-drawn **VECTORS** legend (top-left of the
:class:`~radiant.gui.viewer.schematic_view.SchematicView` canvas). Owner feedback
2026-07-14 moved the angle-arc reveal toggles **out** of the right-column accordion and
**onto the plot** as a compact bottom-left panel that mirrors the VECTORS legend at
top-left. Because the toggles must stay interactive (each checkbox reveals/hides its arc),
this is a real child ``QWidget`` overlaid on the canvas — not a painter overlay — parented
to the canvas, absolutely positioned bottom-left, and repositioned in the canvas
``resizeEvent`` so it never clips and always sits over the schematic.

One checkbox per annotatable angle, grouped by reference frame (target-frame vs
ground/platform-frame) exactly as the accordion page did. The annotation list is read from
the :mod:`~radiant.gui.viewer.angle_catalog` catalog (the single Qt-free source), so a new
annotatable angle appears here without transcription. Toggling a checkbox emits
:attr:`angleToggled`; the owning :class:`~radiant.gui.viewer.viewer_widget.GeometryViewer`
wires that to :meth:`GeometryViewer.set_angle_revealed`, so the reveal path is unchanged.

All colour/typography comes from the QSS theme via object names (GUI plan §4.9); this file
holds no colour or font literal. The panel chrome (``#angleOverlay`` background + border)
matches the VECTORS-legend treatment (theme ``panel`` fill, ``line`` border).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget

from radiant.gui.viewer import angle_catalog

if TYPE_CHECKING:
    from radiant.gui.viewer.angle_catalog import AngleAnnotation

# Frame tag → the overlay sub-header (aligned with the GeometryReadout group titles and
# the retired accordion "Angles" page — kept compact so the panel stays small over the plot).
_FRAME_TITLES: Final[Mapping[str, str]] = {
    angle_catalog.FRAME_TARGET: "Target-frame angles",
    angle_catalog.FRAME_GROUND: "Ground / platform frame",
}


class AngleToggleOverlay(QWidget):
    """A compact on-canvas panel of angle-arc reveal checkboxes (bottom-left overlay).

    Mounted as a child of the schematic canvas (parent = the
    :class:`~radiant.gui.viewer.schematic_view.SchematicView`), it mirrors the QPainter
    VECTORS legend at top-left. It is a pure view/control surface: it emits
    :attr:`angleToggled` and never touches the sensor or the canvas directly.

    Signals
    -------
    angleToggled(str, bool):
        An annotation checkbox changed — ``(annotation_name, revealed)``.
    """

    angleToggled = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("angleOverlay")
        # A styled background so the QSS ``#angleOverlay`` panel fill/border paints over the
        # canvas (a bare QWidget ignores QSS background-color without this attribute).
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._angle_checks: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 12, 10)
        layout.setSpacing(2)

        title = QLabel("ANGLES", self)
        title.setObjectName("angleOverlayTitle")
        layout.addWidget(title)

        by_frame: dict[str, list[AngleAnnotation]] = {}
        for ann in angle_catalog.annotations():
            by_frame.setdefault(ann.frame, []).append(ann)
        for frame, frame_title in _FRAME_TITLES.items():
            group = by_frame.get(frame)
            if not group:
                continue
            header = QLabel(frame_title, self)
            header.setObjectName("angleOverlayGroupHeader")
            layout.addWidget(header)
            for ann in group:
                check = QCheckBox(f"{ann.symbol}  ·  {ann.name.replace('_', ' ')}", self)
                check.setObjectName("angleOverlayToggle")
                check.toggled.connect(lambda on, name=ann.name: self.angleToggled.emit(name, on))
                layout.addWidget(check)
                self._angle_checks[ann.name] = check

    def angle_checkbox(self, name: str) -> QCheckBox:
        """The annotation checkbox for *name* (KeyError if unknown)."""
        return self._angle_checks[name]


__all__ = ["AngleToggleOverlay"]
