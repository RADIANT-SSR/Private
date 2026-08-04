"""Font-family resolution for the GUI theme (CU-169 / CU-103).

The design leads its font stacks with IBM Plex (``tokens.FONT_SANS`` /
``FONT_MONO``), which is usually not installed on the host. Naming a missing
family in the QSS makes Qt populate its font-alias table and log, on every
launch::

    qt.qpa.fonts: Populating font family aliases took 173 ms. Replace uses of
    missing font family "IBM Plex Mono" with one that exists to avoid this cost.

This module (a) registers any IBM Plex ``.ttf`` bundled under
``radiant/gui/assets/fonts/`` so the design font is used when shipped (CU-103),
and (b) rewrites each font stack to drop families Qt does not have, so the
stylesheet only ever names available families — no alias population, no warning
(CU-169). The rendered UI is unchanged (Qt already fell back to the same
families); only the warning and its ~170 ms cost go away.

One computation per module (Rule 19): font-stack availability resolution.
"""

from __future__ import annotations

from pathlib import Path

_ASSETS_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_registered = False


def register_bundled_fonts() -> int:
    """Register every ``.ttf`` / ``.otf`` under ``gui/assets/fonts/`` with Qt.

    Idempotent (only runs once per process). Returns the number of font files
    registered — 0 when the directory is absent, which is the current state: the
    design fonts are not yet bundled (CU-103), so :func:`resolve_stack` falls the
    stacks back to installed families instead.
    """
    global _registered
    if _registered:
        return 0
    from PySide6.QtGui import QFontDatabase

    count = 0
    if _ASSETS_FONTS.is_dir():
        for path in sorted(_ASSETS_FONTS.iterdir()):
            if path.suffix.lower() in (".ttf", ".ttc", ".otf") and (
                QFontDatabase.addApplicationFont(str(path)) != -1
            ):
                count += 1
    _registered = True
    return count


def _available_families() -> set[str] | None:
    """Installed font-family names, or ``None`` when no QApplication exists.

    Without a running application Qt cannot report its font database, so the
    caller leaves the stacks unchanged (a headless context never renders, so the
    warning does not arise there).
    """
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        return None
    from PySide6.QtGui import QFontDatabase

    return set(QFontDatabase.families())


def resolve_stack(stack: str, available: set[str] | None) -> str:
    """Drop quoted family names Qt does not have from a CSS *stack*.

    Keeps the available quoted families (in order) plus any unquoted generic
    keyword (``sans-serif`` / ``monospace``), so the resulting stack leads with a
    family Qt resolves directly — no missing-family alias population. If nothing
    named is available it returns just the generic keyword. ``available=None``
    (no app) returns the stack unchanged.
    """
    if available is None:
        return stack
    kept: list[str] = []
    for token in stack.split(","):
        entry = token.strip()
        if entry.startswith('"') and entry.endswith('"'):
            if entry.strip('"') in available:
                kept.append(entry)
        elif entry:
            kept.append(entry)  # generic keyword (sans-serif / monospace) — always keep
    return ", ".join(kept) if kept else stack


def resolve_fonts_in(sheet: str) -> str:
    """Rewrite the ``FONT_SANS`` / ``FONT_MONO`` stacks in *sheet* to available families.

    Replaces every occurrence of the raw token stacks with their resolved form,
    so a missing design font (IBM Plex) is never named in the applied stylesheet.
    A no-op when no application exists (nothing to resolve against).
    """
    from radiant.gui.themes import tokens

    available = _available_families()
    if available is None:
        return sheet
    return sheet.replace(tokens.FONT_SANS, resolve_stack(tokens.FONT_SANS, available)).replace(
        tokens.FONT_MONO, resolve_stack(tokens.FONT_MONO, available)
    )


def mono_font(point_size: float | None = None) -> QFont:  # noqa: F821 — runtime import
    """A :class:`QFont` for the design mono stack's first available family.

    The sanctioned way for a widget to put the §8.2 "values are always mono"
    rule on text Qt cannot reach through QSS (e.g. a specific QTreeWidget
    column, which has no stylesheet selector). Resolution mirrors
    :func:`resolve_stack`: the first installed family in ``tokens.FONT_MONO``
    wins, falling back to Qt's fixed-pitch default when none is. *point_size*
    None keeps the application's current size.
    """
    from PySide6.QtGui import QFont, QFontDatabase

    from radiant.gui.themes import tokens

    available = _available_families()
    family: str | None = None
    if available is not None:
        for token in tokens.FONT_MONO.split(","):
            entry = token.strip()
            if entry.startswith('"') and entry.strip('"') in available:
                family = entry.strip('"')
                break
    if family is None:
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    else:
        font = QFont(family)
    if point_size is not None:
        font.setPointSizeF(point_size)
    return font
