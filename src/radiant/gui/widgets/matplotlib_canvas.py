"""The embedded matplotlib canvas for the visualization area (§4.4).

:class:`MatplotlibCanvas` wraps a ``FigureCanvasQTAgg`` and renders the figures the
scripting API already produces via ``result.plot.*`` — **no plotting logic is
reimplemented in GUI code** (one GUI action ↔ one API call, GUI plan §4.1). The
figures come from :class:`radiant.api.inspect.ResultPlotNamespace`, the public
``result.plot`` surface.

Default post-evaluate figure (arch doc §4.4): the **MTF** view
(``result.plot.mtf()`` — the system MTF and all contributor terms). The §4.4 table
maps the Performance stage's default visualization to "System MTF; SNR summary";
the MTF overlay is the on-spec choice and, usefully for the D2 checkpoint, it
visibly responds when the owner changes the aperture diameter. Phase 4 wires the
stage strip and swaps this per active stage.

The **figure itself is matplotlib's** — its colours are not restyled to the theme
(arch doc §4.4). Only the widget *surround* (margins / border) is themed, via the
``#matplotlibCanvas`` object name (GUI plan §4.9); this file holds no colour, font,
or size literal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from radiant.api.inspect import ResultPlotNamespace

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from radiant.api import ChainResult


class MatplotlibCanvas(QFrame):
    """A themed surround hosting one ``FigureCanvasQTAgg`` (live in Phase 3).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("matplotlibCanvas")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # The currently embedded figure/canvas (None until the first result).
        self._figure: Figure | None = None
        self._canvas: FigureCanvasQTAgg | None = None

    def show_result(self, result: ChainResult) -> None:
        """Render *result*'s default figure (``result.plot.mtf()``) into the canvas.

        The prior figure is closed first, so re-evaluations do not accumulate
        matplotlib figures.
        """
        figure = ResultPlotNamespace(result).mtf()
        self._embed(figure)

    def has_figure(self) -> bool:
        """True once a figure has been embedded (after the first evaluation)."""
        return self._canvas is not None

    # -- internals ----------------------------------------------------------

    def _embed(self, figure: Figure) -> None:
        """Swap in a new figure, discarding and closing the previous one."""
        self._discard_current()
        canvas = FigureCanvasQTAgg(figure)
        self._layout.addWidget(canvas)
        self._figure = figure
        self._canvas = canvas
        canvas.draw_idle()

    def _discard_current(self) -> None:
        """Remove the embedded canvas widget and close its figure (frees pyplot)."""
        if self._canvas is not None:
            self._layout.removeWidget(self._canvas)
            self._canvas.setParent(None)
            self._canvas.deleteLater()
            self._canvas = None
        if self._figure is not None:
            # Close the pyplot-managed figure so repeated re-evaluations do not
            # leak figures. Imported lazily (matplotlib is the optional gui extra).
            import matplotlib.pyplot as plt

            plt.close(self._figure)
            self._figure = None
