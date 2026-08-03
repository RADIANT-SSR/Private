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

The **figure arrives already styled**: since the 2026-08-03 owner ruling (arch doc
§4.4 "Figure styling"), every ``result.plot.*`` figure is rendered under the
token-derived house style in ``radiant.api.plot_style``, with the light/dark variant
selected by the producer through ``plot_theme(dark=…)`` (see ``StageCenter``). This
widget still restyles nothing itself — only the *surround* (margins / border) is
themed, via the ``#matplotlibCanvas`` object name (GUI plan §4.9); this file holds
no colour, font, or size literal.
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

        The prior figure is released first, so re-evaluations do not accumulate
        matplotlib figures. Phase 4 selects a per-stage figure via :meth:`show_figure`;
        this stays the no-stage default.
        """
        self._embed(ResultPlotNamespace(result).mtf())

    def show_figure(self, figure: Figure) -> None:
        """Embed an already-produced *figure* (a ``result.plot.*`` return value).

        Phase 4's stage strip picks the per-stage default figure from the
        ``result.plot`` surface (one GUI action ↔ one API call) and hands the figure
        here; the prior figure is released first so re-renders do not leak figures.
        """
        self._embed(figure)

    def has_figure(self) -> bool:
        """True once a figure has been embedded (after the first evaluation)."""
        return self._canvas is not None

    # -- internals ----------------------------------------------------------

    def _embed(self, figure: Figure) -> None:
        """Swap in a new figure, releasing the previous one."""
        self._discard_current()
        canvas = FigureCanvasQTAgg(figure)
        self._layout.addWidget(canvas)
        self._figure = figure
        self._canvas = canvas
        canvas.draw_idle()

    def _discard_current(self) -> None:
        """Remove the embedded canvas widget and drop its figure reference (CU-116).

        Every figure this canvas is handed is **pyplot-free** — ``result.plot.*``
        builds them with :func:`radiant.api.plot._subplots` (a bare
        ``matplotlib.figure.Figure``), and the GUI's own dialogs construct ``Figure``
        directly — so there is no ``pyplot`` figure manager to tear down: dropping the
        last reference is what frees the figure, and ordinary garbage collection does
        the rest. The former ``plt.close()`` here was the process-global counterpart of
        that reference drop; it is what made the GUI's retained figures visible as
        matplotlib's 20-figure ``max_open_warning``, and calling it on a *live* pane's
        figure from inside a Qt signal handler deadlocked under the offscreen platform
        plugin (the route this CU rejected).
        """
        if self._canvas is not None:
            self._layout.removeWidget(self._canvas)
            self._canvas.setParent(None)
            self._canvas.deleteLater()
            self._canvas = None
        self._figure = None
