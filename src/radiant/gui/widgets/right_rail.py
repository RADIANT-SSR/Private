"""The persistent right rail: Pinned · Edit Config (YAML) · Messages · Evaluate footer (§4.5).

:class:`RightRail` is the always-visible right-side column of the contextual layout. Top
to bottom it stacks three sections plus a pinned footer (arch doc §4.5):

1. :class:`~radiant.gui.widgets.pinned_panel.PinnedPanel` — the pinnable metric cards
   (default set = the five performance metrics; the relocated, now-extensible badge row);
2. the **Edit Config (YAML)** button — opens the roomy
   :class:`~radiant.gui.widgets.yaml_editor_dialog.YamlEditorDialog`; the rail itself owns
   no sensor, so the click is surfaced as :attr:`editConfigRequested` and the main window
   builds the dialog against the live sensor;
3. :class:`~radiant.gui.widgets.messages_panel.MessagesPanel` — the warnings + errors list
   (the relocated warning strip, widened to carry errors);
4. the **Evaluate (F5)** footer — the accent
   :class:`~radiant.gui.widgets.run_button.RunButton`, pinned at the bottom-right of the
   rail as a persistent footer (owner feedback 2026-07-13: the Evaluate button belongs in
   the persistence area at the bottom-right, not floating in the center). It sits below the
   Messages panel (which takes the vertical stretch), so it never scrolls away; the main
   window owns the F5 shortcut and the click → evaluate wiring.

One widget class per file (Rule 19). Styling is entirely themed via object names
(GUI plan §4.9); this file holds no colour/font/size literal.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from radiant.gui.widgets.messages_panel import MessagesPanel
from radiant.gui.widgets.pinned_panel import PinnedPanel
from radiant.gui.widgets.run_button import RunButton

_YAML_LABEL: str = "⧉  Edit Config (YAML)"
_YAML_CAP: str = "opens a roomy editor; Apply re-parses through the framework"


class RightRail(QWidget):
    """The persistent right column: Pinned / YAML button / Messages (arch doc §4.5).

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    editConfigRequested():
        Emitted when the Edit Config (YAML) button is clicked; the main window opens the
        editor against the live sensor.
    """

    editConfigRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rightRail")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        self._pinned = PinnedPanel(self)
        layout.addWidget(self._pinned)

        yaml_section = QFrame(self)
        yaml_section.setObjectName("railYamlSection")
        yaml_layout = QVBoxLayout(yaml_section)
        yaml_layout.setContentsMargins(0, 0, 0, 0)
        yaml_layout.setSpacing(6)
        self._yaml_button = QPushButton(_YAML_LABEL, yaml_section)
        self._yaml_button.setObjectName("yamlEditButton")
        self._yaml_button.clicked.connect(self.editConfigRequested)
        yaml_cap = _make_caption(_YAML_CAP, yaml_section)
        yaml_layout.addWidget(self._yaml_button)
        yaml_layout.addWidget(yaml_cap)
        layout.addWidget(yaml_section)

        self._messages = MessagesPanel(self)
        layout.addWidget(self._messages, 1)

        # Evaluate (F5) footer: the accent Run button pinned at the bottom-right of the
        # rail (owner feedback 2026-07-13). It sits after the stretchy Messages panel, so
        # it stays visible at the foot of the rail rather than scrolling away.
        footer = QFrame(self)
        footer.setObjectName("railFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(0)
        footer_layout.addStretch(1)
        self._run_button = RunButton(footer)
        footer_layout.addWidget(self._run_button)
        layout.addWidget(footer)

    # -- accessors ----------------------------------------------------------

    @property
    def pinned(self) -> PinnedPanel:
        """The Pinned metric-card panel."""
        return self._pinned

    @property
    def messages(self) -> MessagesPanel:
        """The Messages (warnings + errors) panel."""
        return self._messages

    @property
    def yaml_button(self) -> QPushButton:
        """The Edit Config (YAML) button."""
        return self._yaml_button

    @property
    def run_button(self) -> RunButton:
        """The accent Evaluate (F5) button, pinned at the bottom-right rail footer (§4.5)."""
        return self._run_button


def _make_caption(text: str, parent: QWidget) -> QWidget:
    """A themed muted caption line under the YAML button (object name only)."""
    from PySide6.QtWidgets import QLabel

    label = QLabel(text, parent)
    label.setObjectName("yamlEditCaption")
    label.setWordWrap(True)
    return label


__all__ = ["RightRail"]
