"""RADIANT GUI design-system themes (QSS stylesheets).

This package is the single home for every colour, font, and size token in the
GUI (GUI plan §4.9, review-blocking): **no widget anywhere hardcodes a visual
token outside this package.** The light theme is the v1 launch default and the
dark theme is the alternate; both derive from the same token set distilled from
the mockups (``RADIANT_GUI_Architecture.md`` §8).

Phase 1 **Task B** (this task) fills the package:

* :mod:`~radiant.gui.themes.tokens` — the single owner of every colour, font,
  spacing, and radius value (light default :data:`~radiant.gui.themes.tokens.LIGHT`,
  dark alternate :data:`~radiant.gui.themes.tokens.DARK`).
* :mod:`~radiant.gui.themes.stylesheet` — :func:`build_stylesheet` renders one QSS
  template over either token set; :func:`apply_theme` installs it (plus a matching
  base palette and font) on the :class:`QApplication` at bootstrap.
"""

from __future__ import annotations

from radiant.gui.themes.stylesheet import apply_theme, build_stylesheet
from radiant.gui.themes.tokens import DARK, LIGHT, Theme

__all__ = ["apply_theme", "build_stylesheet", "Theme", "LIGHT", "DARK"]
