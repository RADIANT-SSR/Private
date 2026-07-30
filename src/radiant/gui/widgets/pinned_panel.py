"""The right-rail Pinned panel: user-pinnable metric cards (arch doc §4.5).

:class:`PinnedPanel` is the top section of the persistent right rail. It shows a set
of :class:`~radiant.gui.widgets.pinned_card.PinnedCard` cells, a header with the pin
count, and a ``+ Pin…`` action that opens the
:class:`~radiant.gui.widgets.pin_picker_dialog.PinPickerDialog` to pin any metric on
the result surface. This is the relocation of the shipped global metric-badge row into
a pinnable, extensible rail (badges → pinnable cards).

The **default pinned set** is the five v1 performance metrics — SNR · NEDT · NIIRS ·
GSD · MTF@Nyquist (:data:`radiant.gui.metric_format.BADGE_METRICS`) — so the summary the
old badge row gave is present on launch. The pin set (metric **and** stage-output pins)
**persists across sessions** via ``QSettings`` (CU-115): every pin/unpin is saved and the
set is restored on construction, falling back to the default set when none is stored or
the stored value is unreadable. Tests inject a scratch ``QSettings`` so they never touch
the real user config.

One widget class per file (Rule 19). Styling is entirely themed via object names
(GUI plan §4.9); this file holds no colour/font/size literal.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.metric_format import BADGE_METRICS
from radiant.gui.widgets.pin_picker_dialog import PinPickerDialog
from radiant.gui.widgets.pinned_card import PinnedCard

if TYPE_CHECKING:
    from radiant.api import ChainResult

_log = logging.getLogger(__name__)

_ADD_LABEL: str = "+ Pin…"
# The source-stage line for the default performance-metric cards.
_PERFORMANCE_SOURCE: str = "performance"

# QSettings coordinates for cross-session pin persistence (CU-115).
_SETTINGS_ORG: str = "RADIANT"
_SETTINGS_APP: str = "GUI"
_PINS_SETTINGS_KEY: str = "rightRail/pinnedPins"


@dataclass(frozen=True)
class _PinSpec:
    """A pinned value's identity: pin key, display label, source stage, headline?

    ``output`` is ``None`` for a **metric** pin (read from the metric surface) or
    ``(stage, key, unit)`` for a **stage-output** pin (re-read from ``stage_outputs``
    on each evaluation) — the CU-115 Step-B "pin any stage output value" capability.
    """

    key: str
    label: str
    source: str
    primary: bool
    output: tuple[str, str, str] | None = None


# The ratified default pinned set (arch doc §4.5) — the five performance metrics, in
# the shipped badge order. Derived from BADGE_METRICS so the keys/labels stay in one place.
_DEFAULT_PINS: tuple[_PinSpec, ...] = tuple(
    _PinSpec(key=metric_key, label=label, source=_PERFORMANCE_SOURCE, primary=primary)
    for _badge_key, label, metric_key, primary in BADGE_METRICS
)


def _spec_to_dict(spec: _PinSpec) -> dict[str, object]:
    """JSON-serialisable form of a pin spec (``output`` tuple → list)."""
    return {
        "key": spec.key,
        "label": spec.label,
        "source": spec.source,
        "primary": spec.primary,
        "output": list(spec.output) if spec.output is not None else None,
    }


def _spec_from_dict(d: dict[str, object]) -> _PinSpec:
    out = d.get("output")
    return _PinSpec(
        key=str(d["key"]),
        label=str(d["label"]),
        source=str(d["source"]),
        primary=bool(d["primary"]),
        output=(str(out[0]), str(out[1]), str(out[2])) if isinstance(out, list) else None,
    )


def _load_pins(settings: QSettings) -> list[_PinSpec]:
    """Restore the persisted pin set, or the default set when none/invalid (CU-115)."""
    raw = settings.value(_PINS_SETTINGS_KEY)
    if not raw:
        return list(_DEFAULT_PINS)
    try:
        data = json.loads(str(raw))
        return [_spec_from_dict(d) for d in data]
    except (ValueError, TypeError, KeyError, IndexError):
        _log.debug("Pinned-panel settings unreadable; falling back to defaults.")
        return list(_DEFAULT_PINS)


class PinnedPanel(QWidget):
    """The Pinned rail section: metric cards + a ``+ Pin…`` action (arch doc §4.5).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None, *, settings: QSettings | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pinnedPanel")

        # Pin set persists across sessions via QSettings (CU-115). Use IniFormat
        # explicitly (cross-platform + test-isolatable via QSettings.setPath) rather
        # than the platform-native store. Tests inject a scratch QSettings so they
        # never touch the real user config.
        self._settings: QSettings = settings or QSettings(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, _SETTINGS_ORG, _SETTINGS_APP
        )
        self._result: ChainResult | None = None
        self._pins: list[_PinSpec] = _load_pins(self._settings)
        self._cards: dict[str, PinnedCard] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        header = QWidget(self)
        header.setObjectName("railSectionHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        self._title = QLabel("Pinned", header)
        self._title.setObjectName("railSectionTitle")
        self._count = QLabel("", header)
        self._count.setObjectName("railSectionCount")
        header_layout.addWidget(self._title)
        header_layout.addWidget(self._count)
        layout.addWidget(header)

        self._cards_host = QWidget(self)
        self._cards_layout = QVBoxLayout(self._cards_host)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(7)
        layout.addWidget(self._cards_host)

        self._add_button = QPushButton(_ADD_LABEL, self)
        self._add_button.setObjectName("pinAddButton")
        self._add_button.clicked.connect(self._on_add_clicked)
        layout.addWidget(self._add_button)

        layout.addStretch(1)

        self._rebuild_cards()

    # -- accessors ----------------------------------------------------------

    @property
    def cards(self) -> dict[str, PinnedCard]:
        """The pinned cards keyed by metric/pin key, in pin order."""
        return dict(self._cards)

    @property
    def add_button(self) -> QPushButton:
        """The ``+ Pin…`` action button."""
        return self._add_button

    @property
    def pinned_keys(self) -> list[str]:
        """The pinned metric keys, in display order (session-scoped)."""
        return [spec.key for spec in self._pins]

    # -- result delivery ----------------------------------------------------

    def update_from_result(self, result: ChainResult) -> None:
        """Store *result* and refresh every card's value from its metric surface."""
        self._result = result
        for card in self._cards.values():
            card.update_from_result(result)

    def set_stale(self, stale: bool) -> None:
        """Mark (or clear) every card's shown value as stale (§8.4)."""
        for card in self._cards.values():
            card.set_stale(stale)

    # -- pin / unpin --------------------------------------------------------

    def pin(self, key: str, label: str, source: str = _PERFORMANCE_SOURCE) -> None:
        """Add a **metric** card for *key* (no-op if pinned); refresh from the last result."""
        if any(spec.key == key for spec in self._pins):
            return
        self._pins.append(_PinSpec(key=key, label=label, source=source, primary=False))
        self._save_pins()
        self._rebuild_cards()

    def pin_stage_output(self, stage: str, key: str, label: str, unit: str) -> None:
        """Pin a **stage-output** value ``stage_outputs[stage][key]`` (arch doc §4.5, CU-115).

        The card re-reads the value from ``stage_outputs`` on each evaluation and shows it
        with *unit* (R-UNITS). The pin key is the composite ``"<stage>.<key>"`` so a stage
        output never collides with a same-named metric. No-op if already pinned.
        """
        pin_key = f"{stage}.{key}"
        if any(spec.key == pin_key for spec in self._pins):
            return
        self._pins.append(
            _PinSpec(
                key=pin_key,
                label=label,
                source=stage,
                primary=False,
                output=(stage, key, unit),
            )
        )
        self._save_pins()
        self._rebuild_cards()

    def unpin(self, key: str) -> None:
        """Remove the card for *key* (no-op if not pinned)."""
        self._pins = [spec for spec in self._pins if spec.key != key]
        self._save_pins()
        self._rebuild_cards()

    # -- internal -----------------------------------------------------------

    def _save_pins(self) -> None:
        """Persist the current pin set to QSettings (CU-115)."""
        self._settings.setValue(
            _PINS_SETTINGS_KEY, json.dumps([_spec_to_dict(s) for s in self._pins])
        )

    def _rebuild_cards(self) -> None:
        """Rebuild the card widgets from the current pin list and refresh them."""
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards = {}
        for spec in self._pins:
            card = PinnedCard(
                spec.key,
                spec.label,
                spec.source,
                primary=spec.primary,
                output_ref=spec.output,
                parent=self._cards_host,
            )
            card.unpinRequested.connect(self.unpin)
            self._cards_layout.addWidget(card)
            self._cards[spec.key] = card
        if self._result is not None:
            self.update_from_result(self._result)
        self._update_count()

    def _update_count(self) -> None:
        """Refresh the header count line (``N pinned``)."""
        n = len(self._pins)
        self._count.setText(f"{n} pinned")

    def _on_add_clicked(self) -> None:
        """Open the metric picker and pin the chosen metric (needs a result first)."""
        if self._result is None:
            return
        dialog = PinPickerDialog(self._result, self.pinned_keys, self)
        if exec_dialog(dialog) == QDialog.DialogCode.Accepted:
            key = dialog.selected_key()
            if key is not None:
                self.pin(key, key)


__all__ = ["PinnedPanel"]
