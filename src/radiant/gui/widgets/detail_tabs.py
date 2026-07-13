"""The bottom detail dock's tabbed panel (arch doc §4.5).

:class:`DetailTabs` is the mockup's ``.dtabs`` strip as a real ``QTabWidget`` carrying the
five v1 detail tabs — **Spectral**, **MTF**, **Noise Budget**, **Variables**, and
**YAML** — each its own widget class in its own file (Rule 19 spirit). The Console tab is
GUI plan Phase 8 and is intentionally absent from this v1 five-tab set.

Every tab renders from the **public** API surface (one GUI action ↔ one API call, GUI plan
§4.1): the four result-driven tabs from a :class:`~radiant.api.ChainResult`, and the YAML
tab from the live :class:`~radiant.api.sensor.Sensor` (its serialize surface). Pre-result
each tab shows its own themed "evaluate first" state; :meth:`show_result` fills all five on
every successful evaluation (GUI plan Phase 4 Task B).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtWidgets import QTabWidget, QWidget

from radiant.gui.widgets.mtf_tab import MtfTab
from radiant.gui.widgets.noise_budget_tab import NoiseBudgetTab
from radiant.gui.widgets.spectral_tab import SpectralTab
from radiant.gui.widgets.variable_explorer_tab import VariableExplorerTab
from radiant.gui.widgets.yaml_tab import YamlTab

if TYPE_CHECKING:
    from radiant.api import ChainResult
    from radiant.api.sensor import Sensor

# The tab labels in order (arch doc §4.5, sans the Phase-8 Console tab).
TAB_LABELS: Final[tuple[str, ...]] = ("Spectral", "MTF", "Noise Budget", "Variables", "YAML")


class DetailTabs(QTabWidget):
    """The five-tab detail panel, each tab live from the public API surface.

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detailTabs")
        self.setDocumentMode(True)

        self._spectral = SpectralTab(self)
        self._mtf = MtfTab(self)
        self._noise = NoiseBudgetTab(self)
        self._variables = VariableExplorerTab(self)
        self._yaml = YamlTab(self)

        self.addTab(self._spectral, "Spectral")
        self.addTab(self._mtf, "MTF")
        self.addTab(self._noise, "Noise Budget")
        self.addTab(self._variables, "Variables")
        self.addTab(self._yaml, "YAML")

    # -- accessors ----------------------------------------------------------

    @property
    def spectral_tab(self) -> SpectralTab:
        """The Spectral tab (selectable source / atmosphere / in-band figures)."""
        return self._spectral

    @property
    def mtf_tab(self) -> MtfTab:
        """The MTF tab (per-term MTF@Nyquist table + overlay)."""
        return self._mtf

    @property
    def noise_tab(self) -> NoiseBudgetTab:
        """The Noise Budget tab (table + bars + per-term describe)."""
        return self._noise

    @property
    def variables_tab(self) -> VariableExplorerTab:
        """The Variable Explorer tab (``inspect_result`` as a tree)."""
        return self._variables

    @property
    def yaml_tab(self) -> YamlTab:
        """The YAML tab (provenance-coloured current config + Export)."""
        return self._yaml

    def tab_labels(self) -> list[str]:
        """The tab labels in order (Spectral … YAML)."""
        return [self.tabText(i) for i in range(self.count())]

    # -- result delivery ----------------------------------------------------

    def show_result(self, result: ChainResult, sensor: Sensor | None) -> None:
        """Populate every tab on a fresh evaluation (GUI plan Phase 4 Task B).

        The four result-driven tabs render from *result*; the YAML tab renders the live
        *sensor*'s current config (its serialize surface — the config the evaluation ran
        on). A ``None`` *sensor* leaves the YAML tab in its evaluate-first state.
        """
        self._spectral.show_result(result)
        self._mtf.show_result(result)
        self._noise.show_result(result)
        self._variables.show_result(result)
        if sensor is not None:
            self._yaml.show_sensor(sensor)
