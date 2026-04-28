"""Status-bar right-side text — regime + projected area.

Phase 6 (PLAN_v2.md §14 step 3): the status bar's right side reads
``SUB_PIXEL [auto]  ·  A_t = 12.57 m²``. Pure formatter so it can be
unit-tested without a Qt context.

The left-side text (frame indicator) reuses ``frame_indicator_text``
from ``app/interaction_state.py`` — Rule 19 keeps that here-once,
referenced from both the HUD overlay and the status bar.

Rule 19: own file. Status-bar formatting is its own concern, distinct
from the readout-panel formatter (``view_model.format_readout``) which
produces per-row table strings.
"""

from __future__ import annotations

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.app.view_model import (
    classify_regime,
    projected_area_m2,
)


def status_bar_right_text(state: SceneState) -> str:
    """Format the right-side status-bar string for ``state``.

    Example: ``SUB_PIXEL [auto]  ·  A_t = 12.5664 m²``.

    Regime label is upper-case (matches the underlying enum value); the
    ``[auto]`` / ``[override]`` tag follows the spec wording. Projected
    area always carries its unit (``m²``) — Jason's hard rule.
    """
    regime, _reason = classify_regime(state)
    A_t = projected_area_m2(state)
    override_tag = "auto" if state.regime_override == "auto" else "override"
    return (
        f"{regime.value.upper()} [{override_tag}]"
        f"  \u00b7  A_t = {A_t:.4g} m\u00b2"
    )
