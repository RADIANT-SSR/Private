"""The master configuration selector (arch doc §4.2b, multi-configuration Phase 4a).

:class:`ConfigurationBar` is the persistent control that chooses **which
configuration of the loaded study the whole window displays** (plan §4 item 2,
ADR-0010 D-3). It renders one compact tab per configuration, in set order, each
carrying that configuration's stable accent chip from the theme token set
(:attr:`~radiant.gui.themes.tokens.Theme.config_accents`, both themes, §4 item 7).

**Zero visibility for a single-configuration session.** A set with exactly one
configuration is the ordinary single-model session, and the bar hides itself
completely — no strip, no label, no reserved height — so today's window is
unchanged byte for byte (the zero-regression requirement of plan §4 item 7). The
host additionally hides the dock the bar lives in, so the layout does not even
carry an empty band.

Selecting a tab is **display state only**: it emits
:attr:`configurationSelected`, and the host sets ``ConfigurationSet.active`` and
re-binds the panels. The bar owns no sensor, no set, and no API call (R-API —
one GUI action ↔ one API call, made by the host).

Since Phase 4c the strip also carries a trailing **manage** affordance — the gear
button at its right end emits :attr:`manageRequested`, which the host answers with the
same configuration manager dialog its Edit menu opens (§4.2d). Creating, renaming,
reordering, and removing configurations all live there; the bar itself still owns no
set and makes no API call.

Styling is entirely themed via object names (GUI plan §4.9); the only colour this
file names is the token tuple it reads from the active theme, never a literal.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QWidget

from radiant.gui.themes import active_theme
from radiant.gui.themes.tokens import Theme

# Side of the square accent chip drawn on each tab, in device-independent px.
# Geometry, not a design token (GUI plan §4.9 keeps colours/fonts in themes/).
_CHIP_PX: int = 10

# The manage affordance's glyph and label — text content, not a style token.
_MANAGE_GLYPH = "⚙"
_MANAGE_TOOLTIP = "Add, rename, reorder, or remove configurations (Edit → Configurations…)"

# Layout items pinned to the right of the tabs: the stretch and the manage button.
# New tabs are inserted before them.
_TRAILING_ITEMS: int = 2


class ConfigurationBar(QWidget):
    """A compact tab strip selecting the displayed configuration.

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    configurationSelected(str):
        Emitted with a configuration's name when the user picks its tab. Not
        emitted for programmatic updates (:meth:`set_configurations`,
        :meth:`set_active`), so a host re-binding its state cannot re-enter.
    manageRequested():
        Emitted when the user clicks the trailing gear — the host opens the
        configuration manager (§4.2d).
    """

    configurationSelected = Signal(str)
    manageRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("configurationBar")

        self._names: list[str] = []
        self._active: str | None = None
        self._theme: Theme = active_theme()
        self._buttons: list[QPushButton] = []
        self._updating: bool = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(6)
        self._label = QLabel("CONFIGURATIONS", self)
        self._label.setObjectName("configurationBarLabel")
        layout.addWidget(self._label)
        self._layout = layout
        layout.addStretch(1)

        # The manage affordance sits after the stretch, pinned to the right end, so
        # adding tabs never pushes it around. It is built once and never rebuilt.
        manage = QPushButton(_MANAGE_GLYPH, self)
        manage.setObjectName("configurationManageButton")
        manage.setFlat(True)
        manage.setCursor(Qt.CursorShape.PointingHandCursor)
        manage.setToolTip(_MANAGE_TOOLTIP)
        manage.clicked.connect(self.manageRequested.emit)
        layout.addWidget(manage)
        self._manage_button = manage

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.idClicked.connect(self._on_clicked)

        self.setVisible(False)  # nothing to choose between until a set arrives

    # -- accessors ----------------------------------------------------------

    @property
    def names(self) -> tuple[str, ...]:
        """The configuration names currently offered, in set order."""
        return tuple(self._names)

    @property
    def active_name(self) -> str | None:
        """The name of the currently selected configuration (``None`` when empty)."""
        return self._active

    @property
    def buttons(self) -> list[QPushButton]:
        """The configuration tabs, in set order (tests click these)."""
        return list(self._buttons)

    @property
    def manage_button(self) -> QPushButton:
        """The trailing gear that opens the configuration manager (§4.2d)."""
        return self._manage_button

    def accent_for(self, name: str) -> str:
        """The theme accent colour assigned to configuration *name*.

        Assignment is by **position** in the set, so a configuration keeps its
        colour as long as its position holds, and the same position yields the
        matching hue in the light and dark token sets. A set larger than the
        accent tuple (not reachable while ``MAX_CONFIGS`` is 8) wraps.
        """
        accents = self._theme.config_accents
        index = self._names.index(name) if name in self._names else 0
        return accents[index % len(accents)]

    # -- update -------------------------------------------------------------

    def set_configurations(self, names: Sequence[str], active: str | None) -> None:
        """Rebuild the strip for *names*, selecting *active*.

        Hides the whole bar when there are fewer than two configurations — a
        one-configuration session must look exactly like today's single-model
        GUI. Emits nothing: this is the host pushing its state down.
        """
        self._names = list(names)
        if active in self._names:
            self._active = active
        else:
            self._active = self._names[0] if self._names else None
        self._rebuild()
        self.setVisible(len(self._names) > 1)

    def set_active(self, name: str) -> None:
        """Select *name*'s tab without emitting :attr:`configurationSelected`."""
        if name not in self._names:
            return
        self._active = name
        self._updating = True
        try:
            for index, button in enumerate(self._buttons):
                button.setChecked(self._names[index] == name)
        finally:
            self._updating = False

    def set_theme(self, theme: Theme) -> None:
        """Adopt *theme* and repaint the accent chips (the View → theme toggle).

        The chips are painted pixmaps, outside QSS's reach, so they are rebuilt
        from the new token set here — the same pattern the schematic viewer and
        the detector illustration use.
        """
        self._theme = theme
        self._rebuild()

    # -- internal -----------------------------------------------------------

    def _rebuild(self) -> None:
        """Rebuild the tabs from the current names / active / theme state."""
        for button in self._buttons:
            self._group.removeButton(button)
            self._layout.removeWidget(button)
            button.deleteLater()
        self._buttons = []

        # Below two configurations there is nothing to select, and the bar is
        # hidden anyway — build no tabs at all, so a single-configuration session
        # carries no selector widgets whatsoever.
        names = self._names if len(self._names) > 1 else []
        accents = self._theme.config_accents
        self._updating = True
        try:
            for index, name in enumerate(names):
                button = QPushButton(name, self)
                button.setObjectName("configurationTab")
                button.setCheckable(True)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setIcon(self._accent_icon(accents[index % len(accents)]))
                button.setIconSize(QSize(_CHIP_PX, _CHIP_PX))
                button.setToolTip(f"Display configuration {name!r}")
                button.setChecked(name == self._active)
                # Insert before the trailing stretch + manage button, so the tabs stay
                # left-aligned and the gear stays pinned to the right end.
                self._layout.insertWidget(self._layout.count() - _TRAILING_ITEMS, button)
                self._group.addButton(button, index)
                self._buttons.append(button)
        finally:
            self._updating = False

    @staticmethod
    def _accent_icon(colour: str) -> QIcon:
        """A small solid square of *colour* as the tab's accent chip."""
        pixmap = QPixmap(_CHIP_PX, _CHIP_PX)
        pixmap.fill(QColor(colour))
        return QIcon(pixmap)

    def _on_clicked(self, index: int) -> None:
        """Emit the user's pick (programmatic updates are suppressed)."""
        if self._updating or not (0 <= index < len(self._names)):
            return
        name = self._names[index]
        if name == self._active:
            return
        self._active = name
        self.configurationSelected.emit(name)


__all__ = ["ConfigurationBar"]
