"""The full-well saturation banner (arch doc §4.4, §7.2 row 8; owner amendment 2).

:class:`SaturationBanner` is a **persistent, non-dismissible** banner shown whenever
the detector well clips (``result.well_status().is_saturated``), so silent full-well
clipping is never invisible — three scenarios lost time to it (CU-101 / Gap 65). It
reads the :class:`radiant.api.WellStatus` result surface (CU-101), never a
``stage_outputs`` dict-hop, and renders the supporting numbers **with their units**
(fill fraction ×, total e- vs capacity e- — R-UNITS, GUI plan §4.6) so the owner sees
*how far* into clipping the well is. It clears on a subsequent unsaturated result.

Placement (arch doc §4.4): below the KPI badge row, above the plot canvas — the
:class:`~radiant.gui.widgets.central_canvas.CentralCanvas` owns that stacking.

Styling is entirely from the design-system QSS theme via the ``#saturationBanner``
object name (error token, GUI plan §4.9); this file holds no colour/font/size literal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QWidget

if TYPE_CHECKING:
    from radiant.api import WellStatus

# Leading marker + heading for the banner text. A glyph, not a style token.
_HEADING: str = "⚠ Detector well saturated"


def _format_banner_text(status: WellStatus) -> str:
    """Compose the banner line: heading plus the well numbers, each with its unit.

    Every value carries its unit (R-UNITS): the fill fraction as a ``×`` multiple
    and the accumulated versus capacity charge in electrons. Reads only the public
    :class:`~radiant.api.WellStatus` fields (CU-101).
    """
    return (
        f"{_HEADING} — well fill {status.fill_fraction:.3g}× "
        f"({status.total_well_e:,.0f} e- accumulated vs "
        f"{status.full_well_capacity_e:,.0f} e- capacity). "
        "The signal is hard-clipped; SNR / NEDT / NIIRS reflect the clipped value."
    )


class SaturationBanner(QLabel):
    """A non-dismissible themed banner, visible only while the well is saturated.

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("saturationBanner")
        self.setWordWrap(True)
        # Hidden until an evaluation reports a saturated well.
        self.setVisible(False)

    def update_from_status(self, status: WellStatus) -> None:
        """Show the banner (with the well numbers) iff *status* is saturated.

        A saturated status paints the banner and its numbers; an unsaturated one
        hides it (clearing a banner from a previous saturated result).
        """
        if status.is_saturated:
            self.setText(_format_banner_text(status))
            self.setVisible(True)
        else:
            self.clear()
            self.setVisible(False)

    def clear_banner(self) -> None:
        """Force-hide the banner (e.g. when no result is displayed)."""
        self.clear()
        self.setVisible(False)
