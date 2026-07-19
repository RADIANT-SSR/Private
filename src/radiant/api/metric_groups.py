"""Public API surface for the performance metric-group taxonomy (Gap 96).

Re-exports the metric-group selection metadata from
:mod:`radiant.performance.metric_selection` so that view layers — the GUI, the
CLI — can enumerate the five metric groups and their enabling
``performance.metrics.*`` parameters without importing a physics stage directly
(the import-linter contract forbids ``radiant.gui`` → ``radiant.performance``;
``radiant.api`` is the sanctioned bridge). The GUI's metric-selection card binds
its checkboxes to :data:`GROUP_PARAMS`.
"""

from __future__ import annotations

from radiant.performance.metric_selection import (
    GROUP_PARAMS,
    METRIC_GROUPS,
    group_of,
    resolve_selection,
)

__all__ = ["GROUP_PARAMS", "METRIC_GROUPS", "group_of", "resolve_selection"]
