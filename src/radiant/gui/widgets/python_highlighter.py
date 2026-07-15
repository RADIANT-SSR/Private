"""A lightweight Python syntax highlighter for the script Editor (arch doc §4.6.1, Pass 2).

:class:`PythonHighlighter` colours keywords, strings, numbers, comments, and ``def``/``class``
names in a :class:`~radiant.gui.widgets.script_tab.ScriptTab` code pane. It is a small,
self-contained :class:`~PySide6.QtGui.QSyntaxHighlighter` — enough to give the MATLAB-style
Editor a legible, coloured feel without pulling in a parser.

**Colour source.** The five highlight roles come from the active
:class:`~radiant.gui.themes.Theme`'s
``syntax_*`` tokens (``syntax_keyword`` / ``syntax_string`` / ``syntax_number`` /
``syntax_function`` / ``syntax_comment``), which already exist per-theme (§8.1) for exactly this
console/editor use. The widget holds **no** colour literal — it reads the tokens like the other
custom-drawn widgets read their theme — and :meth:`set_theme` re-applies them so the Editor
follows the app's light/dark toggle in step (the QSS-styled chrome re-themes automatically;
these ``QColor`` formats are the one part QSS cannot reach, so the toggle re-applies them here).
"""

from __future__ import annotations

import keyword
import re
from typing import Final

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

from radiant.gui.themes import Theme, active_theme

# The Python keyword set (plus the soft keywords) as one alternation, matched on word
# boundaries so `information` does not match `in`. Sourced from the stdlib so it tracks the
# running interpreter's grammar rather than a hand-maintained list.
_KEYWORDS: Final[str] = r"\b(?:" + "|".join(keyword.kwlist + keyword.softkwlist) + r")\b"

# A numeric literal: ints, floats, scientific notation, and hex/bin/oct. Kept deliberately
# loose (highlighting, not lexing) — a false positive only mis-tints, never mis-runs.
_NUMBER: Final[str] = r"\b(?:0[xXbBoO][0-9a-fA-F_]+|\d[\d_]*\.?[\d_]*(?:[eE][+-]?\d+)?j?)\b"

# The name in a `def name(...)` / `class name(...)` header (the function role).
_FUNCTION: Final[str] = r"\b(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)"

# A `#` comment to end-of-line.
_COMMENT: Final[str] = r"#[^\n]*"

# Single- and double-quoted strings (single-line; the triple-quote/multi-line case is left to
# the per-line comment/string fallback — acceptable for a highlight-only pass).
_STRING: Final[str] = r"'[^'\\]*(?:\\.[^'\\]*)*'|\"[^\"\\]*(?:\\.[^\"\\]*)*\""


class PythonHighlighter(QSyntaxHighlighter):
    """Colour Python source in a text document from the active theme's ``syntax_*`` tokens."""

    def __init__(self, document: QTextDocument, theme: Theme | None = None) -> None:
        super().__init__(document)
        self._rules: list[tuple[QRegularExpression, int, QTextCharFormat]] = []
        self.set_theme(theme if theme is not None else active_theme())

    def set_theme(self, theme: Theme) -> None:
        """Rebuild the highlight formats from *theme* and re-colour the document.

        Called on construction and whenever the app light/dark theme toggles, so the Editor's
        keyword/string/number colours track the rest of the GUI (the QSS-styled background and
        border re-theme on their own; only these glyph colours need re-application).
        """
        keyword_fmt = self._format(theme.syntax_keyword, bold=True)
        string_fmt = self._format(theme.syntax_string)
        number_fmt = self._format(theme.syntax_number)
        function_fmt = self._format(theme.syntax_function, bold=True)
        comment_fmt = self._format(theme.syntax_comment, italic=True)

        # Order matters: strings and comments are applied last so a `#` or quote inside them is
        # not re-tinted as a keyword/number. `_apply_rule` overwrites earlier formats, so the
        # later rules win on overlap. The function rule uses capture group 1 (the name only).
        self._rules = [
            (QRegularExpression(_KEYWORDS), 0, keyword_fmt),
            (QRegularExpression(_NUMBER), 0, number_fmt),
            (QRegularExpression(_FUNCTION), 1, function_fmt),
            (QRegularExpression(_STRING), 0, string_fmt),
            (QRegularExpression(_COMMENT), 0, comment_fmt),
        ]
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt override
        """Apply each rule to one line of the document (the Qt highlighter contract)."""
        for expression, group, fmt in self._rules:
            iterator = expression.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                start = match.capturedStart(group)
                length = match.capturedLength(group)
                if length > 0:
                    self.setFormat(start, length, fmt)

    @staticmethod
    def _format(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        """A char format in *color* (a theme token), optionally bold / italic."""
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.DemiBold)
        if italic:
            fmt.setFontItalic(True)
        return fmt


# Validate the regexes at import time (a bad pattern is a programmer error, caught eagerly).
for _pattern in (_KEYWORDS, _NUMBER, _FUNCTION, _COMMENT, _STRING):
    re.compile(_pattern)


__all__ = ["PythonHighlighter"]
