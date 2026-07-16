"""The 9-stage geometry-first signal-chain strip (§4.2).

:class:`StageStrip` is the horizontal band of :class:`~radiant.gui.widgets.stage_chip.StageChip`
tiles in ADR-0006 chain order (Geometry → … → Performance). GUI plan Phase 4 makes
the chips clickable — a click is **navigation only** (no API call): the strip emits
the clicked stage's real schema :attr:`~radiant.gui.widgets.stage_chip.StageChip.namespace`
so the host can scroll the parameter panel to it and swap the canvas to that stage's
default visualization. The strip also drives the per-stage health dots live
(:meth:`set_all_status` / :meth:`set_status`) and the selected-chip state
(:meth:`select`).

``STAGES`` is the canonical chain definition consumed by this strip: each row is
``(namespace, eyebrow, title, subtitle)`` where **namespace** is the real
parameter/schema namespace (``spectral_integration``, not the shortened eyebrow
``spectral`` — CU-106) and eyebrow/title/subtitle are display text. A construction-time
check asserts every namespace is a real chain stage, so the eyebrow-vs-namespace drift
CU-106 flagged cannot silently return.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from radiant.gui.errors import GuiValidationError
from radiant.gui.param_format import chain_namespace_order
from radiant.gui.widgets.stage_chip import StageChip

# (real schema namespace, eyebrow display token, display title, physics sub-caption),
# in ADR-0006 geometry-first chain order. The nine v1 stages (arch doc §4.2). The
# 6th stage's namespace is ``spectral_integration`` (its eyebrow abbreviates to
# ``spectral`` for the tile); keeping the two separate is the CU-106 fix.
STAGES: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("geometry", "geometry", "Geometry", "ranges · angles"),
    ("source", "source", "Source", "L_src(λ)"),
    ("atmosphere", "atmosphere", "Atmosphere", "τ · L_path"),
    ("optics", "optics", "Optics", "PSF · MTF"),
    ("platform", "platform", "Platform", "smear · jitter"),
    ("spectral_integration", "spectral", "Spectral Int.", "∫ dλ"),
    ("detector", "detector", "Detector", "QE · noise"),
    ("readout", "readout", "Readout", "TDI · ADC"),
    ("performance", "performance", "Performance", "SNR · NIIRS"),
)

# The ordered stage titles, exported so tests and later phases can assert chain order
# without re-deriving it from the tuple above.
STAGE_TITLES: Final[tuple[str, ...]] = tuple(title for _, _, title, _ in STAGES)

# The ordered real schema namespaces (what a chip click navigates to).
STAGE_NAMESPACES: Final[tuple[str, ...]] = tuple(namespace for namespace, _, _, _ in STAGES)


class StageStrip(QWidget):
    """The 9-chip signal-chain strip: clickable navigation + live health dots.

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    stageClicked(str):
        Emitted with a stage's real schema namespace when its chip is clicked
        (navigation only — no API call).
    """

    stageClicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stageStrip")

        # Guard (CU-106): every chip namespace must be a real chain stage, so a
        # future edit to STAGES cannot silently reintroduce the eyebrow/namespace
        # drift that would make click-to-navigate a no-op.
        chain = set(chain_namespace_order())
        unknown = [ns for ns in STAGE_NAMESPACES if ns not in chain]
        if unknown:
            raise GuiValidationError(
                f"StageStrip namespaces are not chain stages: {unknown} "
                f"(known stages: {sorted(chain)})"
            )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self._chips: list[StageChip] = []
        self._by_namespace: dict[str, StageChip] = {}
        self._selected: str | None = None
        for index, (namespace, eyebrow, title, subtitle) in enumerate(STAGES, start=1):
            chip = StageChip(
                index, namespace, eyebrow, title, subtitle, status="stale", parent=self
            )
            chip.clicked.connect(self.stageClicked)
            self._chips.append(chip)
            self._by_namespace[namespace] = chip
            layout.addWidget(chip, 1)

    # -- accessors ----------------------------------------------------------

    @property
    def chips(self) -> list[StageChip]:
        """The stage chips, in chain order (Geometry first)."""
        return list(self._chips)

    @property
    def selected_namespace(self) -> str | None:
        """The currently selected stage namespace, or ``None`` if none is selected."""
        return self._selected

    def chip(self, namespace: str) -> StageChip:
        """The chip for *namespace* (raises :class:`KeyError` on an unknown stage)."""
        return self._by_namespace[namespace]

    # -- selection ----------------------------------------------------------

    def select(self, namespace: str) -> None:
        """Mark *namespace*'s chip selected and deselect the rest (§8.4 focus styling)."""
        self._selected = namespace
        for chip in self._chips:
            chip.set_selected(chip.namespace == namespace)

    # -- health -------------------------------------------------------------

    def set_status(self, namespace: str, status: str) -> None:
        """Set one stage's health status (dot + chip tint)."""
        self._by_namespace[namespace].set_status(status)

    def set_all_status(self, status: str) -> None:
        """Set every stage's health status at once (the whole-run health states)."""
        for chip in self._chips:
            chip.set_status(status)
