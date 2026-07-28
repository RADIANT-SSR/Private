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

**Multi-configuration (Phase 4b).** Given a
:class:`~radiant.gui.config_scope.ConfigurationScope`, the row also carries the red
"C" badge of a configured parameter (ADR-0010 D-2), **immediately right of the label**
(owner 2026-07-26 — the marker belongs to the parameter's name, not to its value) —
tooltip listing every configuration's value with units — and a right-click menu
offering the three scope actions (configure / edit configured values / un-configure).
Because every per-stage input form is built from this one widget, the badge and the
menu reach all nine stages by construction rather than by nine independent
implementations. The row still
makes no API call: it emits intent through the scope, and the window performs the
single ``ConfigurationSet`` call and records the undo command.

One widget class per file (Rule 19). All colour/typography comes from the QSS theme via
the object names above (GUI plan §4.9); this module holds no colour/font literal.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QFontMetrics, QResizeEvent
from PySide6.QtWidgets import QGridLayout, QLabel, QMenu, QPushButton, QSizePolicy, QWidget

from radiant.gui.widgets.configure_menu import add_configuration_actions
from radiant.gui.widgets.configured_badge import ConfiguredBadge

if TYPE_CHECKING:
    from radiant.gui.config_scope import ConfigurationScope

# The value shown for a field the user has not provided (inert default): a visible
# "not set via this door" state, not a swallowed value.
UNSET = "—"


# The uniform field-layout contract (owner request 2026-07-17: "consistent size and
# shape throughout the entire project"). Every FieldRow shares these — labels form a
# constant-width column (elide + tooltip beyond; a floor keeps narrow panels safe) and
# value boxes share one bounded shape. Changing the numbers here restyles every form.
LABEL_COLUMN_WIDTH = 170
LABEL_COLUMN_MIN = 70
VALUE_BOX_MIN = 72
VALUE_BOX_MAX = 280


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
        """The narrow floor (LABEL_COLUMN_MIN) so tight panels shrink without clipping."""
        return QSize(LABEL_COLUMN_MIN, super().minimumSizeHint().height())

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt override
        """The **uniform** column width (LABEL_COLUMN_WIDTH) — constant regardless of
        text length, so every label edge lines up across every form (owner request
        2026-07-17); long names elide with the tooltip carrying the full text."""
        return QSize(LABEL_COLUMN_WIDTH, super().sizeHint().height())

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
        self._scope: ConfigurationScope | None = None
        self._read_only = False
        self.setObjectName("geoModeFieldRow")

        row = QGridLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setHorizontalSpacing(10)
        # Three columns: label (0), the configured "C" badge (1, a fixed narrow slot
        # immediately right of the label — owner 2026-07-26), value field (2). The value
        # field takes the slack; the label keeps its natural width. This makes the field
        # editors *expand to the available column width* rather than forcing a fixed
        # too-wide row that overflows the right-column accordion and trips its horizontal
        # scrollbar (owner bug 2026-07-14).
        row.setColumnStretch(0, 0)
        row.setColumnStretch(1, 0)
        row.setColumnStretch(2, 1)

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
        self._value.setMinimumWidth(VALUE_BOX_MIN)
        self._value.setMaximumWidth(VALUE_BOX_MAX)
        self._value.clicked.connect(self._handle_clicked)

        # The configured-parameter marker (Phase 4b): hidden until a scope says this
        # dot-path carries one value per configuration. It sits **immediately right of
        # the label** (owner feedback 2026-07-26: "move the red C just to the right of
        # the variable name") — the marker belongs to the parameter's name, not to its
        # value. Its slot is a fixed narrow width whose size hint does not change with
        # visibility, so a row's label/value geometry is identical either way.
        self._badge = ConfiguredBadge(self)

        row.addWidget(self._label, 0, 0)
        row.addWidget(self._badge, 0, 1)
        row.addWidget(self._value, 0, 2)

        # Right-click offers the multi-configuration scope actions (no-op without a
        # scope — a session that has no document has nothing to configure).
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    @property
    def dotpath(self) -> str:
        """The parameter this row edits."""
        return self._dotpath

    # -- multi-configuration (Phase 4b) -------------------------------------

    def set_configuration_scope(self, scope: ConfigurationScope | None) -> None:
        """Bind (or clear) the :class:`ConfigurationScope` that drives the badge + menu.

        Re-binding disconnects the previous scope, so a document swap cannot leave a
        row listening to a stale set. The badge is refreshed immediately and then on
        every ``changed`` — one signal keeps every row in the window honest.
        """
        if self._scope is not None:
            self._scope.changed.disconnect(self.refresh_badge)
        self._scope = scope
        if scope is not None:
            scope.changed.connect(self.refresh_badge)
        self.refresh_badge()

    def refresh_badge(self) -> None:
        """Show or hide the red "C", with every configuration's value as its tooltip."""
        scope = self._scope
        if scope is not None and scope.is_configured(self._dotpath):
            self._badge.show_for(scope.summary(self._dotpath))
        else:
            self._badge.clear_badge()

    @property
    def badge(self) -> ConfiguredBadge:
        """The configured-parameter marker (visible only for a configured parameter)."""
        return self._badge

    def _show_context_menu(self, pos: QPoint) -> None:
        """Right-click menu: the three configuration scope actions (Phase 4b)."""
        scope = self._scope
        if scope is None or scope.configuration_set is None:
            return
        menu = QMenu(self)
        add_configuration_actions(menu, scope, self._dotpath)
        menu.exec(self.mapToGlobal(pos))

    def _handle_clicked(self) -> None:
        """Open the editor — unless this row mirrors a parameter another stage owns."""
        if self._read_only:
            return
        self._on_edit(self._dotpath)

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

    def set_read_only(self, reason: str) -> None:
        """Show this parameter but refuse edits — another stage owns it.

        Distinct from ``set_editable(False)``, which *disables* the row: a
        disabled row greys its value into the muted palette, which reads as
        "not applicable" and makes the number hard to read. A parameter that a
        different stage owns is fully applicable here — the operator needs to
        see it (owner walkthrough item 6: the sun geometry answers "why is my
        reflected term dark?") but must change it at its one owner, so the row
        stays legible, drops its edit affordance, and carries *reason* as its
        tooltip. The read-only state is sticky: a later
        :meth:`set_editable` (the per-scene relevance gating) cannot
        accidentally hand the row an editor it must not have.
        """
        self._read_only = True
        self.setEnabled(True)
        self._value.setEnabled(True)
        self._value.setCursor(Qt.CursorShape.ArrowCursor)
        self._value.setProperty("state", "readonly")
        self._value.style().unpolish(self._value)
        self._value.style().polish(self._value)
        self.setToolTip(reason)
        self._value.setToolTip(reason)

    @property
    def is_read_only(self) -> bool:
        """Whether this row mirrors a parameter another stage owns (no editing here)."""
        return self._read_only

    @property
    def value_button(self) -> QPushButton:
        """The clickable value button (opens the editor)."""
        return self._value


__all__ = [
    "UNSET",
    "LABEL_COLUMN_WIDTH",
    "LABEL_COLUMN_MIN",
    "VALUE_BOX_MIN",
    "VALUE_BOX_MAX",
    "ElidingLabel",
    "FieldRow",
]
