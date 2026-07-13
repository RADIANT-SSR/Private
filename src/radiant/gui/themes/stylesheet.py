"""QSS generator — turns a :class:`~radiant.gui.themes.tokens.Theme` into a stylesheet.

One QSS template is rendered over either token set (:data:`~radiant.gui.themes.tokens.LIGHT`
or :data:`~radiant.gui.themes.tokens.DARK`), so the light default and the dark alternate
are byte-for-byte the same rules with different colours — exactly the arch-doc §8 contract
("both derive from the same token set"). :func:`apply_theme` installs the result on a
:class:`QApplication`, together with a matching base palette so even widgets Qt paints
from the palette (not the stylesheet) pick up the theme — no unstyled gray-Qt leaks.

Every colour/font/size in the emitted QSS comes from :mod:`radiant.gui.themes.tokens`;
this module contains no literals of its own (only structural QSS: selectors, property
names, layout px that are geometry, not design tokens — kept minimal).
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from radiant.gui.themes import tokens
from radiant.gui.themes.tokens import Theme

# The theme most recently installed by :func:`apply_theme`. Widgets that must
# paint a token colour Qt cannot reach through QSS (e.g. a per-item error tint on
# a ``QTreeWidgetItem``, which carries no object name or property selector) read
# it from here so the colour value still lives in :mod:`radiant.gui.themes.tokens`
# — never as a literal in the widget file. Defaults to the light launch theme so
# widgets constructed before :func:`apply_theme` runs (e.g. in offscreen tests)
# still get a valid token set.
_ACTIVE_THEME: Theme = tokens.LIGHT


def active_theme() -> Theme:
    """Return the :class:`Theme` most recently installed by :func:`apply_theme`.

    The single sanctioned way for a widget to read a design-system colour it
    cannot express through QSS. The returned value is a token set, so no widget
    ever hardcodes a colour — it references a token by name (GUI plan §4.9).
    """
    return _ACTIVE_THEME


def build_stylesheet(theme: Theme) -> str:
    """Return the full application QSS for *theme*.

    The stylesheet styles every top-level widget class the Phase 1 shell uses
    (window, panels, menu bar + menus, dock widgets + titles, status bar, buttons,
    inputs, combo boxes, trees/tables + headers, tabs, scrollbars, tooltips) plus
    the named shell regions (``#stageStrip``, ``#visualizationArea``, the dock
    object names). Later phases add rules for the widgets they introduce; they read
    colours from :mod:`~radiant.gui.themes.tokens`, never inline.
    """
    t = theme
    return f"""
/* ============================================================ *
 * RADIANT GUI — generated QSS ({t.name} theme)                  *
 * Source of every value: radiant.gui.themes.tokens ({t.name})   *
 * ============================================================ */

/* -- Base window / generic widget -------------------------------------- */
QWidget {{
    background-color: {t.bg};
    color: {t.ink};
    font-family: {tokens.FONT_SANS};
    font-size: {tokens.FONT_SIZE_BASE_PT}px;
}}
QMainWindow {{
    background-color: {t.bg};
}}
QMainWindow::separator {{
    background-color: {t.line};
    width: {tokens.BORDER_WIDTH};
    height: {tokens.BORDER_WIDTH};
}}
QToolTip {{
    background-color: {t.panel};
    color: {t.ink};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-radius: {tokens.RADIUS_CHIP};
    padding: 4px 6px;
    font-family: {tokens.FONT_MONO};
}}

/* -- Menu bar + menus (§10) -------------------------------------------- */
QMenuBar {{
    background-color: {t.panel};
    color: {t.ink_2};
    border-bottom: {tokens.BORDER_WIDTH} solid {t.line};
    padding: 2px 4px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 4px 10px;
    border-radius: {tokens.RADIUS_CONTROL};
}}
QMenuBar::item:selected {{
    background-color: {t.panel_2};
    color: {t.ink};
}}
QMenuBar::item:disabled {{
    color: {t.muted_2};
}}
QMenu {{
    background-color: {t.panel};
    color: {t.ink};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-radius: {tokens.RADIUS_CONTROL};
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 22px 5px 14px;
    border-radius: {tokens.RADIUS_CHIP};
}}
QMenu::item:selected {{
    background-color: {t.accent_soft};
    color: {t.ink};
}}
QMenu::item:disabled {{
    color: {t.muted_2};
}}
QMenu::separator {{
    height: {tokens.BORDER_WIDTH};
    background-color: {t.line};
    margin: 4px 6px;
}}

/* -- Dock widgets + titles (§4.3, §4.5) -------------------------------- */
QDockWidget {{
    color: {t.ink_2};
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}
QDockWidget::title {{
    background-color: {t.panel_2};
    color: {t.muted};
    padding: 7px 12px;
    border-bottom: {tokens.BORDER_WIDTH} solid {t.line};
    /* panel-title role, §8.2: 12.5px / 600, uppercase, tracked */
    font-size: 12px;
    font-weight: 600;
}}
QDockWidget > QWidget {{
    background-color: {t.panel};
    border: {tokens.BORDER_WIDTH} solid {t.line};
}}

/* -- Named shell regions (main_window.py object names) ----------------- */
#visualizationArea {{
    background-color: {t.panel};
}}
#parameterDock QWidget, #detailDock QWidget {{
    background-color: {t.panel};
}}

/* -- Signal-chain strip + stage chips (§4.2) --------------------------- */
#stageStrip {{
    background-color: {t.panel_2};
    border-bottom: {tokens.BORDER_WIDTH} solid {t.line};
}}
QFrame#stageChip {{
    background-color: {t.panel};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-radius: 6px;
}}
QFrame#stageChip:hover {{
    border-color: {t.line_2};
    background-color: {t.panel_3};
}}
QLabel#stageChipNum {{
    color: {t.muted};
    font-family: {tokens.FONT_MONO};
    font-size: 9.5px;
}}
QLabel#stageChipEyebrow {{
    color: {t.muted};
    font-size: 10.5px;
    font-weight: 500;
}}
QLabel#stageChipTitle {{
    color: {t.ink};
    font-size: 14px;
    font-weight: 600;
}}
QLabel#stageChipSub {{
    color: {t.muted};
    font-family: {tokens.FONT_MONO};
    font-size: 10.5px;
}}

/* -- Health dots (§8.4) — colour keyed on the [status] property --------- */
QFrame#healthDot {{
    border-radius: 5px;
}}
QFrame#healthDot[status="ok"] {{
    background-color: {t.ok};
    border: 2px solid {t.ok_soft};
}}
QFrame#healthDot[status="warn"] {{
    background-color: {t.warn};
    border: 2px solid {t.warn_soft};
}}
QFrame#healthDot[status="err"] {{
    background-color: {t.err};
    border: 2px solid {t.err_soft};
}}
QFrame#healthDot[status="stale"] {{
    background-color: {t.stale};
    border: 2px solid {t.stale_soft};
}}

/* -- KPI badge row (§4.4) ---------------------------------------------- */
#kpiRow {{
    background-color: {t.panel};
    border-bottom: {tokens.BORDER_WIDTH} solid {t.line};
}}
QFrame#metricBadge {{
    border-right: {tokens.BORDER_WIDTH} solid {t.line};
}}
QLabel#metricLabel {{
    color: {t.muted};
    font-size: 10.5px;
    font-weight: 500;
}}
QLabel#metricValue {{
    color: {t.ink};
    font-family: {tokens.FONT_MONO};
    font-size: 17px;
    font-weight: 600;
}}
QLabel#metricCaption {{
    color: {t.muted};
    font-size: 10.5px;
}}
/* Metric-value colour by state/flag. Equal-specificity selectors: order matters,
 * later wins. Base ink → primary accent → awaiting muted → failed err → stale warn
 * (§8.4: a stale value's marker is warn, so stale wins when set). */
QFrame#metricBadge[primary="true"] QLabel#metricValue {{
    color: {t.accent};
}}
QFrame#metricBadge[state="awaiting"] QLabel#metricValue {{
    color: {t.muted_2};
}}
QFrame#metricBadge[state="failed"] QLabel#metricValue {{
    color: {t.err};
}}
QFrame#metricBadge[state="failed"] QLabel#metricCaption {{
    color: {t.err};
}}
QFrame#metricBadge[stale="true"] QLabel#metricValue {{
    color: {t.warn};
}}

/* -- Full-well saturation banner (§4.4, owner amendment 2) -------------- *
 * Non-dismissible; error token, below the badge row and above the canvas. */
QLabel#saturationBanner {{
    background-color: {t.err_soft};
    color: {t.err};
    border: {tokens.BORDER_WIDTH} solid {t.err};
    border-radius: {tokens.RADIUS_CONTROL};
    padding: {tokens.PAD_INPUT};
    margin: 6px 14px 0px 14px;
    font-weight: 600;
}}

/* -- Chain-warning strip (§4.4, owner feedback 2026-07-13) ------------- *
 * Clickable, warn-token strip between the badge row and the canvas — the
 * chain UserWarnings of the last evaluation, distinct from the red
 * saturation banner. Hover deepens the border to read as clickable. */
QLabel#warningStrip {{
    background-color: {t.warn_soft};
    color: {t.warn};
    border: {tokens.BORDER_WIDTH} solid {t.warn};
    border-radius: {tokens.RADIUS_CONTROL};
    padding: {tokens.PAD_INPUT};
    margin: 6px 14px 0px 14px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#warningStrip:hover {{
    border-color: {t.ink};
}}

/* -- Warning list dialog (§4.4) — the expanded verbatim warning list --- */
#warningListDialog {{
    background-color: {t.panel};
}}
QLabel#warningDialogHeader {{
    color: {t.warn};
    font-size: 14px;
    font-weight: 600;
}}
QPlainTextEdit#warningDialogBody {{
    background-color: {t.panel_2};
    color: {t.ink_2};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-radius: {tokens.RADIUS_CONTROL};
    font-family: {tokens.FONT_MONO};
    font-size: 12px;
}}

/* -- Stale notice: shown when the last evaluation failed (Phase 3 task 4) */
QLabel#staleNotice {{
    background-color: {t.warn_soft};
    color: {t.warn};
    border: {tokens.BORDER_WIDTH} solid {t.warn};
    border-radius: {tokens.RADIUS_CONTROL};
    padding: {tokens.PAD_INPUT};
    margin: 6px 14px 0px 14px;
    font-weight: 600;
}}

/* -- Busy indicator (status-bar evaluate spinner, §3.2) ---------------- */
QProgressBar#busyIndicator {{
    background-color: {t.panel_2};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-radius: {tokens.RADIUS_CHIP};
    height: 8px;
}}
QProgressBar#busyIndicator::chunk {{
    background-color: {t.accent};
    border-radius: {tokens.RADIUS_CHIP};
}}

/* -- Embedded matplotlib canvas surround (§4.4) ------------------------ *
 * The figure itself is matplotlib's; only this surround is themed. */
QFrame#matplotlibCanvas {{
    background-color: {t.panel};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-radius: {tokens.RADIUS_PANEL};
    margin: 12px 14px;
}}

/* -- Plot placeholder (§4.4 empty canvas) ------------------------------ */
#plotPlaceholder {{
    background-color: {t.panel};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-radius: {tokens.RADIUS_PANEL};
    margin: 12px 14px;
}}
QLabel#plotPlaceholderMsg {{
    color: {t.muted};
    font-size: 13px;
}}

/* -- Parameter dock body (§4.3) ---------------------------------------- */
#parameterPanel {{
    background-color: {t.panel};
}}
QLabel#detailPlaceholderMsg, QLabel#parameterEmptyMsg {{
    color: {t.muted};
    font-size: 13px;
}}

/* -- Parameter edit: rejected-value banner (§4.3, Rules 15/17) --------- */
QLabel#parameterErrorBanner {{
    background-color: {t.err_soft};
    color: {t.err};
    border: {tokens.BORDER_WIDTH} solid {t.err};
    border-radius: {tokens.RADIUS_CONTROL};
    padding: {tokens.PAD_INPUT};
    font-size: 11px;
}}

/* -- Error / explain dialogs (§4.3, §11) ------------------------------- */
#actionableErrorDialog, #unexpectedErrorDialog, #explainDialog {{
    background-color: {t.panel};
}}
QLabel#errorDialogHeader {{
    color: {t.err};
    font-size: 14px;
    font-weight: 600;
}}
QLabel#explainDialogHeader {{
    color: {t.ink};
    font-family: {tokens.FONT_MONO};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#errorDialogKey {{
    color: {t.muted};
    font-weight: 600;
}}
QLabel#errorDialogValue {{
    color: {t.ink};
    font-family: {tokens.FONT_MONO};
}}
QPlainTextEdit#errorDialogTraceback, QPlainTextEdit#explainDialogBody {{
    background-color: {t.panel_2};
    color: {t.ink_2};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-radius: {tokens.RADIUS_CONTROL};
    font-family: {tokens.FONT_MONO};
    font-size: 12px;
}}

/* -- Parameter Editor dialog (§4.3, Phase 3 checkpoint) ---------------- *
 * The "open it up" box: full dot-path + description + value/unit entry, a
 * canonical preview, and an inline actionable-error area. Reuses the shared
 * errorDialogKey/errorDialogValue/errorDialogHeader label roles above. */
#parameterEditorDialog {{
    background-color: {t.panel};
}}
QLabel#paramEditorPath {{
    color: {t.ink};
    font-family: {tokens.FONT_MONO};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#paramEditorDescription {{
    color: {t.muted};
    font-size: 12px;
}}
QLabel#paramEditorPreview {{
    color: {t.accent};
    font-family: {tokens.FONT_MONO};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#paramEditorDerivedNote {{
    color: {t.warn};
    font-family: {tokens.FONT_MONO};
    font-size: 12px;
}}
QFrame#paramEditorError {{
    background-color: {t.err_soft};
    border: {tokens.BORDER_WIDTH} solid {t.err};
    border-radius: {tokens.RADIUS_CONTROL};
}}

/* -- Status bar (§4.1) ------------------------------------------------- */
QStatusBar {{
    background-color: {t.panel_2};
    color: {t.muted};
    border-top: {tokens.BORDER_WIDTH} solid {t.line};
    font-family: {tokens.FONT_MONO};
    font-size: 11px;
}}
QStatusBar::item {{
    border: none;
}}

/* -- Buttons (§8.3) ---------------------------------------------------- */
QPushButton {{
    background-color: {t.panel};
    color: {t.ink};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-radius: {tokens.RADIUS_CONTROL};
    padding: {tokens.PAD_BUTTON};
    font-weight: 500;
}}
QPushButton:hover {{
    border-color: {t.line_2};
    background-color: {t.panel_2};
}}
QPushButton:pressed {{
    background-color: {t.panel_3};
}}
QPushButton:disabled {{
    color: {t.muted_2};
    border-color: {t.line};
}}
QPushButton:focus {{
    border-color: {t.focus};
    outline: none;
}}
/* The Run/Evaluate accent button opts in with objectName "runButton" (Phase 3). */
QPushButton#runButton {{
    background-color: {t.accent};
    color: #ffffff;
    border-color: {t.accent};
    font-weight: 600;
}}
QPushButton#runButton:hover {{
    background-color: {t.accent};
    border-color: {t.ink};
}}

/* -- Inputs: line edit, spin box (§8.3) -------------------------------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {t.panel};
    color: {t.ink};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-radius: {tokens.RADIUS_CONTROL};
    padding: {tokens.PAD_INPUT};
    selection-background-color: {t.focus_soft};
    selection-color: {t.ink};
    /* values are always mono (§8.2) */
    font-family: {tokens.FONT_MONO};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {t.focus};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {t.muted};
    background-color: {t.panel_2};
}}

/* -- Combo boxes (§8.3) ------------------------------------------------ */
QComboBox {{
    background-color: {t.panel};
    color: {t.ink};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-radius: {tokens.RADIUS_CONTROL};
    padding: {tokens.PAD_INPUT};
    font-family: {tokens.FONT_MONO};
}}
QComboBox:hover {{
    border-color: {t.line_2};
}}
QComboBox:focus {{
    border-color: {t.focus};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background-color: {t.panel};
    color: {t.ink};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    selection-background-color: {t.accent_soft};
    selection-color: {t.ink};
    outline: none;
}}

/* -- In-cell editors: delegate-spawned editors inside an item view -------
 * The edit delegate (parameter_delegate.py) opens a line edit / spin box /
 * combo *inside* the parameter-tree viewport, over the (usually selected) row.
 * They inherit the generic input rules above — including PAD_INPUT's 5 px
 * vertical padding — which, in a ~20 px row, clips the mono glyphs top and
 * bottom to illegible slivers (Phase 2 checkpoint bug, 2026-07-12). Descendant
 * selectors (matched only inside a QAbstractItemView, so the standalone filter
 * box is untouched) give them near-zero vertical padding and re-assert
 * ink-on-panel — legible digits in both themes, over the selection highlight. */
QAbstractItemView QLineEdit,
QAbstractItemView QAbstractSpinBox,
QAbstractItemView QComboBox {{
    background-color: {t.panel};
    color: {t.ink};
    padding: {tokens.PAD_CELL_EDITOR};
    selection-background-color: {t.focus_soft};
    selection-color: {t.ink};
}}

/* -- Trees / tables + headers (§4.3, §4.5) ----------------------------- */
QTreeView, QTableView, QListView {{
    background-color: {t.panel};
    alternate-background-color: {t.panel_2};
    color: {t.ink};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-radius: {tokens.RADIUS_CONTROL};
    selection-background-color: {t.focus_soft};
    selection-color: {t.ink};
    outline: none;
}}
QTreeView::item, QTableView::item, QListView::item {{
    padding: 3px 4px;
}}
QTreeView::item:hover, QTableView::item:hover, QListView::item:hover {{
    background-color: {t.panel_2};
}}
QTreeView::item:selected, QTableView::item:selected, QListView::item:selected {{
    background-color: {t.focus_soft};
    color: {t.ink};
}}
QHeaderView::section {{
    background-color: {t.panel_2};
    color: {t.muted};
    border: none;
    border-right: {tokens.BORDER_WIDTH} solid {t.line};
    border-bottom: {tokens.BORDER_WIDTH} solid {t.line};
    padding: 5px 8px;
    font-weight: 600;
}}

/* -- Tabs (§4.5 detail panel) ----------------------------------------- */
QTabWidget {{
    background-color: {t.panel};
}}
QTabWidget::pane {{
    background-color: {t.panel};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-radius: {tokens.RADIUS_CONTROL};
    top: -1px;
}}
/* The tab-bar strip itself — including the empty region to the right of the
 * last tab — is themed so macOS does not paint a default-gray band there. */
QTabBar {{
    background-color: {t.panel_2};
    border-bottom: {tokens.BORDER_WIDTH} solid {t.line};
}}
QTabWidget::tab-bar {{
    alignment: left;
}}
QTabBar::tab {{
    background-color: {t.panel_2};
    color: {t.muted};
    border: {tokens.BORDER_WIDTH} solid {t.line};
    border-bottom: none;
    border-top-left-radius: {tokens.RADIUS_CONTROL};
    border-top-right-radius: {tokens.RADIUS_CONTROL};
    padding: 7px 14px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {t.panel};
    color: {t.ink};
}}
QTabBar::tab:hover:!selected {{
    color: {t.ink};
    background-color: {t.panel_3};
}}

/* -- Scrollbars (§8) --------------------------------------------------- */
QScrollBar:vertical {{
    background-color: {t.bg};
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {t.line_2};
    border-radius: {tokens.RADIUS_CHIP};
    min-height: 28px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {t.muted};
}}
QScrollBar:horizontal {{
    background-color: {t.bg};
    height: 12px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background-color: {t.line_2};
    border-radius: {tokens.RADIUS_CHIP};
    min-width: 28px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {t.muted};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
    background: none;
    border: none;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

/* -- Labels ------------------------------------------------------------ */
QLabel {{
    background: transparent;
    color: {t.ink};
}}
QLabel:disabled {{
    color: {t.muted};
}}
"""


def _base_palette(theme: Theme) -> QPalette:
    """A QPalette seeded from *theme* tokens.

    QSS drives the look, but Qt still consults the palette for a handful of
    native-drawn pixels (window frame fill, disabled text, tooltips, some
    focus rects). Seeding it from the same tokens keeps those from flashing the
    default gray — closing the "unstyled gray-Qt leak" the theme test guards.
    """
    p = QPalette()
    bg = QColor(theme.bg)
    panel = QColor(theme.panel)
    panel_2 = QColor(theme.panel_2)
    ink = QColor(theme.ink)
    muted = QColor(theme.muted)
    accent = QColor(theme.accent)
    focus_soft = QColor(theme.focus_soft)

    p.setColor(QPalette.ColorRole.Window, bg)
    p.setColor(QPalette.ColorRole.WindowText, ink)
    p.setColor(QPalette.ColorRole.Base, panel)
    p.setColor(QPalette.ColorRole.AlternateBase, panel_2)
    p.setColor(QPalette.ColorRole.Text, ink)
    p.setColor(QPalette.ColorRole.Button, panel_2)
    p.setColor(QPalette.ColorRole.ButtonText, ink)
    p.setColor(QPalette.ColorRole.ToolTipBase, panel)
    p.setColor(QPalette.ColorRole.ToolTipText, ink)
    p.setColor(QPalette.ColorRole.Highlight, accent)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.PlaceholderText, muted)
    p.setColor(QPalette.ColorRole.Link, accent)
    # Disabled group — keep secondary text readable, not default gray.
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, muted)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, muted)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, muted)
    # Selection tint for list/tree items handled by QSS; palette echoes it.
    p.setColor(QPalette.ColorRole.Midlight, focus_soft)
    return p


def apply_theme(app: QApplication, theme: Theme = tokens.LIGHT) -> None:
    """Install *theme* on *app*: base font, palette, and generated stylesheet.

    Parameters
    ----------
    app:
        The live :class:`QApplication`.
    theme:
        The token set to apply. Defaults to :data:`~radiant.gui.themes.tokens.LIGHT`,
        the v1 launch default (Phase 0 checkpoint amendment 1). Pass
        :data:`~radiant.gui.themes.tokens.DARK` for the alternate; the Phase 9
        View-menu toggle simply re-invokes this with the other theme.
    """
    global _ACTIVE_THEME
    _ACTIVE_THEME = theme
    base_font = app.font()
    base_font.setPointSize(tokens.FONT_SIZE_BASE_PT)
    app.setFont(base_font)
    app.setPalette(_base_palette(theme))
    app.setStyleSheet(build_stylesheet(theme))


__all__ = ["build_stylesheet", "apply_theme", "active_theme"]
