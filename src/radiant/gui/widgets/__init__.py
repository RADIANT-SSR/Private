"""RADIANT GUI widgets — one widget class per file.

Convention (Rule 19 spirit, GUI plan §4.2): **each widget class lives in its own
module**, named for the widget it defines (e.g. ``parameter_tree.py`` →
``ParameterTree``, ``metric_badge.py`` → ``MetricBadge``). A developer finds a
widget by scanning file names, not by reading a multi-purpose module. Do not
bundle unrelated widgets into one file because they share a phase.

Styling rule (GUI plan §4.9, review-blocking): **no widget in this package
hardcodes a colour, font, or size.** All visual tokens come from
:mod:`radiant.gui.themes`; a widget sets structure and ``objectName`` only, and
the theme's QSS targets it.

Phase 1 populates the shell chrome with static, behaviour-free widgets: the
signal-chain strip (:class:`StageStrip` / :class:`StageChip` / :class:`HealthDot`),
the KPI badge row (:class:`KpiBadgeRow` / :class:`MetricBadge` / :class:`RunButton`),
the central canvas (:class:`CentralCanvas` / :class:`PlotPlaceholder`), the parameter
dock body (:class:`ParameterPanel`), and the detail tabs (:class:`DetailTabs`). Later
phases wire behaviour into these and add the geometry viewer.
"""

from __future__ import annotations

from radiant.gui.widgets.central_canvas import CentralCanvas
from radiant.gui.widgets.detail_tabs import DetailTabs
from radiant.gui.widgets.health_dot import HealthDot
from radiant.gui.widgets.kpi_badge_row import KpiBadgeRow
from radiant.gui.widgets.metric_badge import MetricBadge
from radiant.gui.widgets.parameter_panel import ParameterPanel
from radiant.gui.widgets.plot_placeholder import PlotPlaceholder
from radiant.gui.widgets.run_button import RunButton
from radiant.gui.widgets.stage_chip import StageChip
from radiant.gui.widgets.stage_strip import StageStrip

__all__ = [
    "CentralCanvas",
    "DetailTabs",
    "HealthDot",
    "KpiBadgeRow",
    "MetricBadge",
    "ParameterPanel",
    "PlotPlaceholder",
    "RunButton",
    "StageChip",
    "StageStrip",
]
