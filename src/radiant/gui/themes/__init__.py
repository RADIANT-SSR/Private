"""RADIANT GUI design-system themes (QSS stylesheets).

This package is the single home for every colour, font, and size token in the
GUI (GUI plan §4.9, review-blocking): **no widget anywhere hardcodes a visual
token outside this package.** The light theme is the v1 launch default and the
dark theme is the alternate; both derive from the same token set distilled from
the mockups (``RADIANT_GUI_Architecture.md`` §8).

Phase 1 **Task A** ships this as an empty stub — the shell it scaffolds runs on
default Qt styling. Phase 1 **Task B** (a separate follow-up task) fills this
package with the QSS theme and a loader that applies it to the
:class:`QApplication`. Task A deliberately leaves the window unstyled so the
look-and-feel review happens against Task B's deliverable, not a placeholder.
"""

from __future__ import annotations

__all__: list[str] = []
