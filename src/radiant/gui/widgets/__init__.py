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

Phase 1 (Task A) ships this package empty — the shell has no bespoke widgets yet.
Phases 2+ add the parameter tree, metric badges, detail tabs, and the geometry
viewer here.
"""

from __future__ import annotations

__all__: list[str] = []
