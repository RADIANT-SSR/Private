"""The central area: saturation banner and the contextual per-stage center (§4.4).

:class:`CentralCanvas` is the window's central widget. In the contextual layout (arch doc
§4.4, owner-ratified 2026-07-13) the **global metric-badge row is gone** — the performance
metrics now live in the right-rail *Pinned* panel (§4.5) — and the **chain-warning strip is
gone** — warnings now live in the right-rail *Messages* panel (§4.5). The accent Evaluate
(F5) button also moved **out** of the center: it is now the right-rail footer (§4.5, owner
feedback 2026-07-13 — the run action belongs in the persistence area at the bottom-right,
not floating in the center). What remains here, top to bottom:

1. the :class:`~radiant.gui.widgets.saturation_banner.SaturationBanner` — the persistent,
   non-dismissible full-well-clip banner. It is **retained in the center** (arch doc §4.4:
   the saturation banner renders at the top of the center column) — it is high-signal and
   deliberately kept out of the generic Messages list (Step-A placement decision);
2. a themed **stale notice** — shown when the last evaluation failed, so the still-displayed
   previous result is honestly marked stale;
3. the :class:`~radiant.gui.widgets.stage_center.StageCenter` — the per-stage contextual
   composite. Selecting a stage in the strip shows **only that stage's** outputs readout,
   plot(s), and relocated detail content (arch doc §4.4); this replaces the old
   single-canvas swap.

It keeps the ``visualizationArea`` object name the shell layout contract uses. This file
holds no colour/font/size literal (GUI plan §4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from radiant.gui.widgets.saturation_banner import SaturationBanner
from radiant.gui.widgets.stage_center import StageCenter

if TYPE_CHECKING:
    from radiant.api import ChainResult

_STALE_NOTICE: str = "Stale — last evaluation failed; showing the previous result."


class CentralCanvas(QWidget):
    """Saturation banner + stale notice + per-stage center (live in Phase 3).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Preserve the shell's named region so the theme / layout contract holds.
        self.setObjectName("visualizationArea")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._saturation_banner = SaturationBanner(self)
        self._stale_notice = QLabel(_STALE_NOTICE, self)
        self._stale_notice.setObjectName("staleNotice")
        self._stale_notice.setWordWrap(True)
        self._stale_notice.setVisible(False)

        # The per-stage contextual center: a placeholder pre-evaluate, then the selected
        # stage's composite. The last result and selected stage are remembered inside so
        # re-evaluations and stage clicks re-render the right composite.
        self._stage_center = StageCenter(self)

        layout.addWidget(self._saturation_banner)
        layout.addWidget(self._stale_notice)
        layout.addWidget(self._stage_center, 1)

    # -- accessors ----------------------------------------------------------

    @property
    def saturation_banner(self) -> SaturationBanner:
        """The full-well saturation banner (visible only when clipped)."""
        return self._saturation_banner

    @property
    def stale_notice(self) -> QLabel:
        """The themed 'last evaluation failed' stale notice (hidden until it is)."""
        return self._stale_notice

    @property
    def stage_center(self) -> StageCenter:
        """The per-stage contextual center (its pin signals wire to the right rail)."""
        return self._stage_center

    @property
    def selected_stage(self) -> str | None:
        """The stage whose composite is shown (``None`` → pre-evaluate placeholder)."""
        return self._stage_center.selected_stage

    # -- evaluate loop (Phase 3) --------------------------------------------

    def show_result(self, result: ChainResult) -> None:
        """Display a fresh *result*: saturation banner and the selected stage's composite.

        Clears any stale notice (the current result is live) and updates the saturation
        banner from ``result.well_status()``. The per-stage center then re-renders for the
        currently selected stage (or lands on the default stage on the first result). The
        performance metrics are delivered to the right-rail Pinned panel, and the chain
        warnings to the right-rail Messages panel, by the main window — not here.
        """
        self._stale_notice.setVisible(False)
        self._saturation_banner.update_from_status(result.well_status())
        self._stage_center.show_result(result)

    def select_stage(self, namespace: str | None) -> None:
        """Select *namespace*'s composite (arch doc §4.4). Navigation only.

        With no result yet the placeholder stays; the selection is remembered and rendered
        on the next result (the Phase-4A navigation behaviour, preserved).
        """
        self._stage_center.select_stage(namespace)

    def mark_stale(self) -> None:
        """Mark the displayed result stale after a failed evaluation (task 4).

        Leaves the previous composite in place (never a blank or partial mix) but shows the
        themed stale notice. The right-rail Pinned cards' ``→?`` stale marker is set by the
        main window (they own the metric values now).
        """
        self._stale_notice.setVisible(True)


__all__ = ["CentralCanvas"]
