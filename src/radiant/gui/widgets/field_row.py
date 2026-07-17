"""The shared schema-driven field-row widget — one label + one value button (§4.4).

This is the single building block for every "labelled schema parameter, click the
value to open the editor" row in the Geometry screen, factored out so the two surfaces
that use it — the Inputs-tab :class:`~radiant.gui.widgets.geometry_mode_form.GeometryModeForm`
and the Schematic-tab :class:`~radiant.gui.widgets.geometry_angle_panel.GeometryAnglePanel`
(target dimensions + RPY) — render **identically by construction** rather than by two
independent approximations (owner feedback 2026-07-14: "the target boxes should be just
like the geometry boxes"). Both instantiate :class:`FieldRow`, so they share the same
label treatment (:class:`ElidingLabel`), the same value-button style, and the same QSS
object names (``geoModeFieldRow`` / ``geoModeFieldLabel`` / ``geoModeFieldValue``) — a
future divergence is impossible without editing this one widget.

The value button is display-only chrome: it carries the resolved value in the row's
display unit (R-UNITS) and, when clicked, calls the ``on_edit`` handler its owner
supplied (which opens the shared
:class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog` — one
``sensor.set`` on commit, the same validate-on-a-clone reject path everywhere). The row
never touches a ``Sensor`` itself; it is pure presentation + an edit-intent hook.

One widget class per file (Rule 19). All colour/typography comes from the QSS theme via
the object names above (GUI plan §4.9); this module holds no colour/font literal.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics, QResizeEvent
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QSizePolicy, QWidget

# The value shown for a field the user has not provided (inert default): a visible
# "not set via this door" state, not a swallowed value.
UNSET = "—"


class ElidingLabel(QLabel):
    """A field label that elides with an ellipsis instead of forcing its full text width.

    The geometry/target field labels are raw dot-path leaves (e.g. ``sensor_off_nadir_rad``,
    ``shape_radius_m``); a plain :class:`QLabel` demands its full text width as a hard
    minimum, which pushed the field row past the right-column accordion and tripped its
    horizontal scrollbar (owner bug 2026-07-14). This label reports a *small* minimum width
    (so the row shrinks to the column and the value field stays fully visible), keeps its
    full width as the *preferred* hint (so a wide column still shows the whole name), and
    elides the displayed text to the available width — the full name stays available as a
    hover tooltip. QSS styling is preserved (the base :class:`QLabel` still paints the text,
    only the string is elided).
    """

    _MIN_CHARS = 4

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full = text
        self.setToolTip(text)
        super().setText(text)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt override
        """A few characters wide, so the row can shrink to the column (value stays visible)."""
        fm = QFontMetrics(self.font())
        return QSize(fm.averageCharWidth() * self._MIN_CHARS, super().minimumSizeHint().height())

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt override
        """The full label width when the column has room (elides only when it does not)."""
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance(self._full), super().sizeHint().height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 — Qt override
        super().resizeEvent(event)
        fm = QFontMetrics(self.font())
        super().setText(fm.elidedText(self._full, Qt.TextElideMode.ElideRight, self.width()))


class FieldRow(QWidget):
    """One schema-driven parameter field: a label + a value button that opens the editor.

    The value button carries the resolved value in the row's display unit (R-UNITS)
    and, when enabled, calls ``on_edit(dotpath)`` on click — the owner wires that to the
    full :class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`
    (the same value+unit+reject path the parameter tree uses). Disabled (a non-active
    mode's field) it is greyed and inert.
    """

    def __init__(self, dotpath: str, label: str, on_edit: Callable[[str], None]) -> None:
        super().__init__(None)
        self._dotpath = dotpath
        self._on_edit = on_edit
        self.setObjectName("geoModeFieldRow")

        row = QGridLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setHorizontalSpacing(10)
        # The value field takes the slack (column 1 stretches); the label keeps its natural
        # width (column 0). This makes the field editors *expand to the available column
        # width* rather than forcing a fixed too-wide row that overflows the right-column
        # accordion and trips its horizontal scrollbar (owner bug 2026-07-14).
        row.setColumnStretch(0, 0)
        row.setColumnStretch(1, 1)

        self._label = ElidingLabel(label, self)
        self._label.setObjectName("geoModeFieldLabel")
        self._label.setWordWrap(False)

        self._value = QPushButton(UNSET, self)
        self._value.setObjectName("geoModeFieldValue")
        self._value.setCursor(Qt.CursorShape.PointingHandCursor)
        # Expand horizontally to fill the column (shrinking to a modest minimum) so a long
        # value never pushes the row wider than its column — no horizontal clip/scrollbar.
        # Bounded above (owner report 2026-07-16): in a wide stage-center pane an unbounded
        # value button became a giant bar and starved the label column into ellipses
        # ("Fill fac…"); the cap returns that width to the labels. Narrow columns (the
        # schematic accordion) sit below the cap and are unaffected.
        self._value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._value.setMinimumWidth(64)
        self._value.setMaximumWidth(280)
        self._value.clicked.connect(lambda: self._on_edit(self._dotpath))

        row.addWidget(self._label, 0, 0)
        row.addWidget(self._value, 0, 1)

    @property
    def dotpath(self) -> str:
        """The parameter this row edits."""
        return self._dotpath

    def set_value_text(self, text: str) -> None:
        """Set the displayed value+unit text."""
        self._value.setText(text)

    def value_text(self) -> str:
        """The displayed value+unit text (for tests)."""
        return self._value.text()

    def set_editable(self, editable: bool) -> None:
        """Enable/disable the field (only the active mode's fields are editable)."""
        self.setEnabled(editable)
        self._value.setEnabled(editable)

    @property
    def value_button(self) -> QPushButton:
        """The clickable value button (opens the editor)."""
        return self._value


__all__ = ["UNSET", "ElidingLabel", "FieldRow"]
