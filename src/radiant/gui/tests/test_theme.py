"""Theme tests for the RADIANT GUI design system (GUI plan Phase 1, task 6).

Two contracts are enforced here:

1. **No unstyled gray-Qt leaks.** The generated stylesheet styles every top-level
   widget class the shell uses, applying it makes the app stylesheet non-empty, and
   the app palette resolves to the themed surface/text colours (not Qt's default
   gray). Both light (default) and dark themes are exercised.

2. **Token discipline (review-blocking, every later phase).** No file under
   ``radiant.gui`` *outside* ``themes/`` may contain a hex-colour literal or a
   font-family string. A mechanical grep fails the build if any leaks in — this is
   the enforcement that keeps :mod:`radiant.gui.themes` the single owner of visual
   values (GUI plan §4.9).
"""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtWidgets import QApplication, QLineEdit

from radiant.api.sensor import Sensor
from radiant.gui.themes import DARK, LIGHT, Theme, apply_theme, build_stylesheet
from radiant.gui.widgets.parameter_panel import ParameterPanel

# A clean bounded float in the shipped example config — the row the delegate opens
# a line-edit over (the exact case in the 2026-07-12 illegible-editor bug report).
_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_EDIT_ROW = "source.target.temperature"

# Every top-level widget class the Phase 1 shell (and the mockups) rely on. If the
# generated QSS does not name each of these, some widget renders in default Qt gray.
_REQUIRED_SELECTORS: tuple[str, ...] = (
    "QMainWindow",
    "QWidget",
    "QMenuBar",
    "QMenu",
    "QDockWidget",
    "QDockWidget::title",
    "QStatusBar",
    "QPushButton",
    "QLineEdit",
    "QComboBox",
    "QTreeView",
    "QTableView",
    "QHeaderView::section",
    "QTabBar::tab",
    "QScrollBar:vertical",
    "QToolTip",
)


@pytest.mark.parametrize("theme", [LIGHT, DARK], ids=lambda t: t.name)
class TestStylesheetCoverage:
    def test_stylesheet_non_empty(self, theme: Theme) -> None:
        """A theme produces a substantial, non-empty stylesheet."""
        qss = build_stylesheet(theme)
        assert qss.strip()
        assert len(qss) > 1000  # a real sheet, not a stub

    def test_every_widget_class_styled(self, theme: Theme) -> None:
        """Every required top-level widget class has a rule (no gray-Qt leaks)."""
        qss = build_stylesheet(theme)
        for selector in _REQUIRED_SELECTORS:
            assert selector in qss, f"{theme.name}: {selector} unstyled"

    def test_surface_and_ink_tokens_present(self, theme: Theme) -> None:
        """The theme's own bg/panel/ink/accent tokens appear in its stylesheet."""
        qss = build_stylesheet(theme)
        for token in (theme.bg, theme.panel, theme.ink, theme.accent, theme.line):
            assert token in qss, f"{theme.name}: token {token} missing from QSS"

    def test_font_stacks_present(self, theme: Theme) -> None:
        """Both the sans (UI) and mono (numeric) stacks are used."""
        qss = build_stylesheet(theme)
        assert "IBM Plex Sans" in qss
        assert "IBM Plex Mono" in qss


class TestThemesDiffer:
    def test_light_and_dark_differ(self) -> None:
        """Light and dark are the same rules with different colours."""
        assert LIGHT.bg != DARK.bg
        assert LIGHT.ink != DARK.ink
        assert build_stylesheet(LIGHT) != build_stylesheet(DARK)

    def test_same_token_names(self) -> None:
        """Both themes expose an identical field set (same token names)."""
        light_fields = {f.name for f in fields(LIGHT)}
        dark_fields = {f.name for f in fields(DARK)}
        assert light_fields == dark_fields


class TestApplyTheme:
    def test_apply_sets_app_stylesheet(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """apply_theme makes the app stylesheet non-empty and theme-specific."""
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        previous = app.styleSheet()
        try:
            apply_theme(app, LIGHT)
            assert app.styleSheet().strip()
            assert app.styleSheet() == build_stylesheet(LIGHT)
        finally:
            app.setStyleSheet(previous)

    def test_apply_seeds_themed_palette(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The app palette resolves to themed surface/text colours, not Qt gray."""
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        previous_palette = app.palette()
        previous_qss = app.styleSheet()
        try:
            apply_theme(app, LIGHT)
            pal = app.palette()
            assert pal.color(QPalette.ColorRole.Window) == QColor(LIGHT.bg)
            assert pal.color(QPalette.ColorRole.WindowText) == QColor(LIGHT.ink)
            assert pal.color(QPalette.ColorRole.Highlight) == QColor(LIGHT.accent)

            apply_theme(app, DARK)
            assert app.palette().color(QPalette.ColorRole.Window) == QColor(DARK.bg)
        finally:
            app.setPalette(previous_palette)
            app.setStyleSheet(previous_qss)


@pytest.mark.parametrize("theme", [LIGHT, DARK], ids=lambda t: t.name)
class TestInCellEditorLegible:
    """The delegate editor stays legible when opened over a *selected* tree row.

    Regression guard for the 2026-07-12 checkpoint bug: the in-cell line edit
    inherited the generic input padding (``PAD_INPUT`` = 5 px vertical), which in a
    ~16 px row clipped the mono glyphs top and bottom to illegible slivers. Two
    independent contracts are asserted, in both themes:

    * **Contrast** — the editor's effective Text colour differs from its Base
      (background) colour, so it is never ink-on-ink.
    * **Rendered legibility** — the actual rendered glyphs span most of the editor
      height (they are not clipped). This is the check that fails on the padding
      regression: the palette contrast alone passed even while the bug was live.
    """

    def _open_editor(self, theme: Theme, qtbot) -> QLineEdit:  # type: ignore[no-untyped-def]
        """Populate a panel, apply *theme*, select the row, open its editor."""
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        apply_theme(app, theme)
        panel = ParameterPanel()
        qtbot.addWidget(panel)
        panel.resize(420, 600)
        panel.populate(Sensor.from_yaml(_EXAMPLE))
        panel.show()
        item = panel._items[_EDIT_ROW]
        tree = panel.tree
        tree.setCurrentItem(item)  # the row is SELECTED (highlight painted behind)
        tree.scrollToItem(item)
        index = tree.indexFromItem(item, 1)
        tree.openPersistentEditor(item, 1)
        app.processEvents()
        editor = tree.indexWidget(index)
        assert isinstance(editor, QLineEdit)
        return editor

    def test_editor_text_contrasts_with_background(self, theme: Theme, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Effective Text colour differs from Base — never light-on-light ink."""
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        prev_qss, prev_pal = app.styleSheet(), app.palette()
        try:
            editor = self._open_editor(theme, qtbot)
            pal = editor.palette()
            assert pal.color(QPalette.ColorRole.Text) != pal.color(QPalette.ColorRole.Base)
        finally:
            app.setStyleSheet(prev_qss)
            app.setPalette(prev_pal)

    def test_editor_glyphs_are_not_clipped(self, theme: Theme, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The rendered digits span most of the editor height (padding-clip guard).

        The bug clipped the glyphs to a ~4 px band in a 16 px editor; the fix
        restores an ~11 px span. Asserting the ink band is at least 45 % of the
        editor height cleanly separates the two (and is font-fallback tolerant).
        """
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        prev_qss, prev_pal = app.styleSheet(), app.palette()
        try:
            editor = self._open_editor(theme, qtbot)
            img: QImage = editor.grab().toImage()
            bg = QColor(theme.panel)
            rows_with_ink = [
                y
                for y in range(img.height())
                if any(
                    (
                        abs(img.pixelColor(x, y).red() - bg.red())
                        + abs(img.pixelColor(x, y).green() - bg.green())
                        + abs(img.pixelColor(x, y).blue() - bg.blue())
                    )
                    > 120
                    for x in range(img.width())
                )
            ]
            assert rows_with_ink, f"{theme.name}: editor rendered no legible ink"
            ink_span = max(rows_with_ink) - min(rows_with_ink) + 1
            assert ink_span >= 0.45 * img.height(), (
                f"{theme.name}: glyphs clipped — ink spans {ink_span}px "
                f"of {img.height()}px editor (padding-clip regression)"
            )
        finally:
            app.setStyleSheet(prev_qss)
            app.setPalette(prev_pal)


class TestTokenDiscipline:
    """Mechanical enforcement of the review-blocking single-owner rule (§4.9)."""

    def _gui_python_files_outside_themes(self) -> list[Path]:
        """Every widget/app ``.py`` under ``radiant.gui`` that must own no visual literal.

        Excluded owners of visual literals:

        * ``themes/`` — the single owner of chrome tokens (GUI plan §4.9);
        * ``tests/`` — assertions legitimately reference token values;
        * ``viewer/scene/palette.py`` — the documented **physics-domain glyph palette**
          (ADR-0007 §3/§8.5). These colors encode physical meaning (sun = amber,
          sensor = blue, surface normal = green, target = teal) and are a separate
          allowed domain layer, kept in this one module. Theme-bound *chrome* for the
          viewer (viewport background, leader lines, label pill) still comes from a
          ``Theme`` via ``viewer/scene/chrome.py`` and holds no literal.

        Everything else — app.py, main_window.py, workers.py, widgets/, viewer/, package
        inits — is the target the review-blocking §4.9 rule governs.
        """
        gui_root = Path(__file__).resolve().parents[1]
        themes_dir = gui_root / "themes"
        tests_dir = gui_root / "tests"
        palette = gui_root / "viewer" / "scene" / "palette.py"
        return [
            p
            for p in gui_root.rglob("*.py")
            if themes_dir not in p.parents
            and tests_dir not in p.parents
            and p.parent != tests_dir
            and p != palette
            and "__pycache__" not in p.parts
        ]

    def test_no_hex_color_literals_outside_themes(self) -> None:
        """No ``#rrggbb`` (or #rgb / #rrggbbaa) literal lives outside themes/."""
        hex_re = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")
        offenders: dict[str, list[str]] = {}
        for path in self._gui_python_files_outside_themes():
            hits = hex_re.findall(path.read_text(encoding="utf-8"))
            if hits:
                offenders[str(path)] = hits
        assert not offenders, f"hex-colour literals outside themes/: {offenders}"

    def test_no_font_family_strings_outside_themes(self) -> None:
        """No font-family name or ``font-family``/``sans-serif`` token outside themes/."""
        forbidden = ("IBM Plex", "font-family", "sans-serif", "monospace", "Menlo")
        offenders: dict[str, list[str]] = {}
        for path in self._gui_python_files_outside_themes():
            text = path.read_text(encoding="utf-8")
            hits = [needle for needle in forbidden if needle in text]
            if hits:
                offenders[str(path)] = hits
        assert not offenders, f"font-family literals outside themes/: {offenders}"
