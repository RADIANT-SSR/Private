"""The Transmission tab's **mode selector** — scalar τ_opt vs. an element train.

:class:`TransmissionModeSelector` is the segmented control at the top of the Optics
**Transmission** tab (owner-ratified 2026-09-09/10, consolidating the old *Elements* and
*Throughput* tabs). RADIANT accepts optical transmission in exactly two mutually exclusive
forms, and the selector is the one place the analyst chooses between them:

* **Scalar throughput** — the single ``optics.transmission_scalar`` τ_opt, flat across the
  band.
* **Element train** — the declarative ``optical_elements`` document, whose per-element
  net throughputs multiply into τ_opt(λ).

The selector carries **no state of its own beyond the checked button**: the host
(:class:`~radiant.gui.widgets.transmission_panel.TransmissionPanel`) sets it from the
loaded configuration (a config with an element list opens in *Element train*, otherwise
*Scalar*) and reacts to :attr:`modeSelected`. A programmatic :meth:`set_mode` never emits,
so reflecting the document can never be mistaken for an operator choice.

Two checkable buttons in an exclusive ``QButtonGroup`` — the same segmented-control idiom
(and the same QSS treatment) as the configuration-bar tabs, so a mode choice reads like
every other "pick one of these" control in the window. All colour/typography comes from
the QSS theme via the ``transmissionModeButton`` object name (GUI plan §4.9); this file
holds no colour or font literal. One widget class per file (Rule 19).
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QWidget

#: The scalar-τ_opt transmission mode (``optics.transmission_scalar`` defines τ).
MODE_SCALAR: Final[str] = "scalar"
#: The element-train transmission mode (the ``optical_elements`` document defines τ).
MODE_ELEMENT: Final[str] = "element"

_LABELS: Final[tuple[tuple[str, str], ...]] = (
    (MODE_SCALAR, "Scalar throughput"),
    (MODE_ELEMENT, "Element train"),
)

_PROMPT: Final[str] = "Transmission defined by:"

_TOOLTIPS: Final[dict[str, str]] = {
    MODE_SCALAR: (
        "One scalar τ_opt, flat across the band (optics.transmission_scalar). "
        "Saving in this mode writes no optical_elements section."
    ),
    MODE_ELEMENT: (
        "The optical_elements document: each element's net throughput multiplies "
        "into τ_opt(λ), and the scalar τ_opt is ignored."
    ),
}


class TransmissionModeSelector(QWidget):
    """Segmented "Scalar throughput | Element train" control (Transmission tab).

    Signals
    -------
    modeSelected(str):
        Emitted with :data:`MODE_SCALAR` / :data:`MODE_ELEMENT` when the **operator**
        picks a mode. :meth:`set_mode` does not emit — reflecting the loaded document is
        not a choice.
    """

    modeSelected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("transmissionModeSelector")

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        prompt = QLabel(_PROMPT, self)
        prompt.setObjectName("geoModeGroupHeading")
        row.addWidget(prompt)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for index, (mode, label) in enumerate(_LABELS):
            button = QPushButton(label, self)
            button.setObjectName("transmissionModeButton")
            button.setCheckable(True)
            button.setToolTip(_TOOLTIPS[mode])
            self._group.addButton(button, index)
            row.addWidget(button)
            self._buttons[mode] = button
            button.clicked.connect(lambda _checked, m=mode: self._on_clicked(m))
        row.addStretch(1)

        self._mode = MODE_SCALAR
        self._buttons[MODE_SCALAR].setChecked(True)

    # -- state ---------------------------------------------------------------

    @property
    def mode(self) -> str:
        """The checked mode (:data:`MODE_SCALAR` or :data:`MODE_ELEMENT`)."""
        return self._mode

    def set_mode(self, mode: str) -> None:
        """Check *mode* without emitting — the document reflecting itself, not a choice."""
        if mode not in self._buttons:
            return
        self._mode = mode
        self._buttons[mode].setChecked(True)

    def button(self, mode: str) -> QPushButton:
        """The segment button for *mode* (KeyError if unknown — tests / programmer error)."""
        return self._buttons[mode]

    # -- internal ------------------------------------------------------------

    def _on_clicked(self, mode: str) -> None:
        """Relay an operator click, ignoring a re-click of the already-active segment."""
        if mode == self._mode:
            return
        self._mode = mode
        self.modeSelected.emit(mode)


__all__ = ["TransmissionModeSelector", "MODE_SCALAR", "MODE_ELEMENT"]
