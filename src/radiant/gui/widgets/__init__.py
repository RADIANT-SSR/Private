"""RADIANT GUI widgets — one widget class per file.

Convention (Rule 19 spirit, GUI plan §4.2): **each widget class lives in its own
module**, named for the widget it defines (e.g. ``pinned_card.py`` →
``PinnedCard``, ``messages_panel.py`` → ``MessagesPanel``). A developer finds a
widget by scanning file names, not by reading a multi-purpose module. Do not
bundle unrelated widgets into one file because they share a phase.

Styling rule (GUI plan §4.9, review-blocking): **no widget in this package
hardcodes a colour, font, or size.** All visual tokens come from
:mod:`radiant.gui.themes`; a widget sets structure and ``objectName`` only, and
the theme's QSS targets it.

The contextual-layout retrofit (arch doc §4, owner-ratified 2026-07-13) introduces
the persistent right rail (:class:`RightRail` = :class:`PinnedPanel` + Edit Config
(YAML) button + :class:`MessagesPanel`) and retires the global metric-badge row
(``KpiBadgeRow`` / ``MetricBadge``) and the floating chain-warning strip
(``WarningStrip``): the metrics became pinnable :class:`PinnedCard` cells and the
warnings moved into the Messages panel.

Step B (2026-07-13) dissolves the bottom detail tabs (``DetailTabs``) into the per-stage
contextual center (:class:`StageCenter`) and the global :class:`InspectorDialog` tool
(arch doc §4.7): the MTF and Noise Budget tabs became the embeddable :class:`MtfPanel` /
:class:`NoiseBudgetPanel`, the Spectral tab's figures became per-stage plot sections, the
Variable Explorer tab became the Inspector, and the read-only YAML tab was superseded by
the right-rail Edit Config (YAML) modal.
"""

from __future__ import annotations

from radiant.gui.widgets.central_canvas import CentralCanvas
from radiant.gui.widgets.geometry_readout import GeometryReadout
from radiant.gui.widgets.health_dot import HealthDot
from radiant.gui.widgets.inspector_dialog import InspectorDialog
from radiant.gui.widgets.message_item import MessageItem
from radiant.gui.widgets.messages_panel import MessagesPanel
from radiant.gui.widgets.mtf_panel import MtfPanel
from radiant.gui.widgets.noise_budget_panel import NoiseBudgetPanel
from radiant.gui.widgets.outputs_readout import OutputsReadout
from radiant.gui.widgets.parameter_panel import ParameterPanel
from radiant.gui.widgets.pin_picker_dialog import PinPickerDialog
from radiant.gui.widgets.pinned_card import PinnedCard
from radiant.gui.widgets.pinned_panel import PinnedPanel
from radiant.gui.widgets.plot_placeholder import PlotPlaceholder
from radiant.gui.widgets.right_rail import RightRail
from radiant.gui.widgets.run_button import RunButton
from radiant.gui.widgets.saturation_banner import SaturationBanner
from radiant.gui.widgets.stage_center import StageCenter, StagePane
from radiant.gui.widgets.stage_chip import StageChip
from radiant.gui.widgets.stage_strip import StageStrip
from radiant.gui.widgets.yaml_editor_dialog import YamlEditorDialog

__all__ = [
    "CentralCanvas",
    "GeometryReadout",
    "HealthDot",
    "InspectorDialog",
    "MessageItem",
    "MessagesPanel",
    "MtfPanel",
    "NoiseBudgetPanel",
    "OutputsReadout",
    "ParameterPanel",
    "PinPickerDialog",
    "PinnedCard",
    "PinnedPanel",
    "PlotPlaceholder",
    "RightRail",
    "RunButton",
    "SaturationBanner",
    "StageCenter",
    "StagePane",
    "StageChip",
    "StageStrip",
    "YamlEditorDialog",
]
