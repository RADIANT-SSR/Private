"""Phase 6 acceptance — app-shell polish.

Pure-Python coverage:
  * ``theme.SUPPORTED_THEMES`` advertises the spec'd themes (dark_teal,
    light_blue, system).
  * ``theme.apply_theme`` raises on unknown stylesheet names.
  * ``status_bar_text.status_bar_right_text`` formats regime + projected
    area with the unit token (Jason's hard rule).
  * ``window_persistence`` keys are namespaced under ``RADIANT/Geometry``
    and round-trip through QSettings.

Qt-required coverage:
  * Settings dialog has Theme + Default-frame controls populated.
  * About dialog instantiates and shows the product name.
  * Shortcuts dialog enumerates every binding from
    ``SHORTCUT_BINDINGS``.

Skips QtInteractor-bearing tests by default — see test_interaction_phase5
for the rationale.
"""

from __future__ import annotations

import math
import os
from typing import Iterator

import pytest

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.app.status_bar_text import status_bar_right_text
from dev_tools.geometry_gui_v2.app.theme import (
    DEFAULT_DARK_THEME,
    DEFAULT_LIGHT_THEME,
    SUPPORTED_THEMES,
    SYSTEM_THEME_KEY,
    apply_theme,
)


# --- theme registry -------------------------------------------------------


def test_supported_themes_includes_dark_light_and_system() -> None:
    assert DEFAULT_DARK_THEME in SUPPORTED_THEMES.values()
    assert DEFAULT_LIGHT_THEME in SUPPORTED_THEMES.values()
    assert SYSTEM_THEME_KEY in SUPPORTED_THEMES.values()


def test_default_dark_theme_matches_spec() -> None:
    """PLAN_v2.md §14 step 1 names ``dark_teal.xml`` as the default."""
    assert DEFAULT_DARK_THEME == "dark_teal.xml"


def test_default_light_theme_matches_spec() -> None:
    """PLAN_v2.md §14 step 1 names ``light_blue.xml`` as the alternate."""
    assert DEFAULT_LIGHT_THEME == "light_blue.xml"


def test_apply_theme_rejects_unknown_stylesheet() -> None:
    """A corrupted ``QSettings`` entry must surface as an error rather than
    silently apply nothing."""

    class _SentinelApp:
        def setStyleSheet(self, _s: str) -> None: ...

    with pytest.raises(ValueError, match="unknown theme"):
        apply_theme(_SentinelApp(), "not_a_real_theme.xml")


def test_apply_theme_system_clears_stylesheet() -> None:
    """System theme = clear stylesheet (no qt-material applied)."""

    class _SentinelApp:
        def __init__(self) -> None:
            self.cleared = False

        def setStyleSheet(self, s: str) -> None:
            self.cleared = (s == "")

    app = _SentinelApp()
    apply_theme(app, SYSTEM_THEME_KEY)
    assert app.cleared, "apply_theme(system) should clear the stylesheet"


# --- status bar formatter -------------------------------------------------


def test_status_bar_right_text_for_default_state_is_unit_bearing() -> None:
    """Default scene is a 1 m sphere @ 600 km — the projected area must
    appear with the m² unit token."""
    text = status_bar_right_text(SceneState.default())
    assert "m\u00b2" in text, f"status bar text missing m² unit: {text!r}"
    assert "A_t" in text


def test_status_bar_right_text_includes_regime_and_origin_marker() -> None:
    """Format: ``REGIME [auto|override]  ·  A_t = ... m²``."""
    text = status_bar_right_text(SceneState.default())
    assert "[auto]" in text or "[override]" in text
    assert "\u00b7" in text  # the middle-dot separator


def test_status_bar_right_text_changes_with_target_radius() -> None:
    """Doubling the radius quadruples the projected area for a sphere — the
    formatter should reflect that."""
    import dataclasses

    base = SceneState.default()
    big = dataclasses.replace(base, target_radius_m=2.0)
    base_text = status_bar_right_text(base)
    big_text = status_bar_right_text(big)
    assert base_text != big_text, "status bar text must depend on state"
    # The projected area for r=1 sphere is π m²; for r=2 it's 4π. The
    # numeric values must be present in their respective strings.
    assert f"{math.pi:.4g}" in base_text
    assert f"{4 * math.pi:.4g}" in big_text


# --- Qt-required tests ----------------------------------------------------

os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qt_app() -> Iterator[object]:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_about_dialog_instantiates_with_product_name(qt_app) -> None:
    from dev_tools.geometry_gui_v2.app.dialogs.about import (
        PRODUCT_NAME,
        AboutDialog,
    )

    dlg = AboutDialog()
    # Confirm the spec'd product naming (D2 resolved 2026-04-26).
    assert PRODUCT_NAME == "RADIANT Geometry Module"
    # The dialog's window title doesn't carry the product name (it just says
    # "About"); confirm the label *content* mentions it.
    from PySide6.QtWidgets import QLabel

    label_texts = " ".join(lbl.text() for lbl in dlg.findChildren(QLabel))
    assert PRODUCT_NAME in label_texts


def test_shortcuts_dialog_enumerates_all_bindings(qt_app) -> None:
    from PySide6.QtWidgets import QLabel

    from dev_tools.geometry_gui_v2.app.dialogs.shortcuts import (
        SHORTCUT_BINDINGS,
        ShortcutsDialog,
    )

    dlg = ShortcutsDialog()
    label_texts = " ".join(lbl.text() for lbl in dlg.findChildren(QLabel))
    for key, action in SHORTCUT_BINDINGS:
        assert key in label_texts, f"binding {key!r} missing from dialog"
        assert action in label_texts, f"action {action!r} missing from dialog"


def test_settings_dialog_populates_theme_and_frame_combos(qt_app) -> None:
    from PySide6.QtWidgets import QComboBox

    from dev_tools.geometry_gui_v2.app.dialogs.settings import SettingsDialog
    from dev_tools.geometry_gui_v2.app.interaction_state import DisplayFrame

    dlg = SettingsDialog(
        current_theme_xml=DEFAULT_DARK_THEME,
        current_frame=DisplayFrame.BODY,
    )

    # Theme combo: must contain at least the three spec themes by data.
    theme_combo = dlg.findChild(QComboBox, "settings_theme_combo")
    assert theme_combo is not None
    theme_data = {
        theme_combo.itemData(i) for i in range(theme_combo.count())
    }
    assert DEFAULT_DARK_THEME in theme_data
    assert DEFAULT_LIGHT_THEME in theme_data
    assert SYSTEM_THEME_KEY in theme_data

    # Frame combo: must contain all three display frames, with Body
    # currently selected.
    frame_combo = dlg.findChild(QComboBox, "settings_frame_combo")
    assert frame_combo is not None
    frame_data = {
        frame_combo.itemData(i) for i in range(frame_combo.count())
    }
    assert frame_data == {
        DisplayFrame.WORLD,
        DisplayFrame.BODY,
        DisplayFrame.SENSOR,
    }
    assert frame_combo.currentData() is DisplayFrame.BODY


def test_settings_dialog_accessors_return_chosen_values(qt_app) -> None:
    from dev_tools.geometry_gui_v2.app.dialogs.settings import SettingsDialog
    from dev_tools.geometry_gui_v2.app.interaction_state import DisplayFrame

    dlg = SettingsDialog(
        current_theme_xml=DEFAULT_LIGHT_THEME,
        current_frame=DisplayFrame.SENSOR,
    )
    assert dlg.selected_theme() == DEFAULT_LIGHT_THEME
    assert dlg.selected_default_frame() is DisplayFrame.SENSOR


# --- window persistence ---------------------------------------------------


def test_window_persistence_keys_namespace_under_radiant_geometry(
    qt_app,
) -> None:
    from PySide6.QtCore import QSettings

    from dev_tools.geometry_gui_v2.app.window_persistence import (
        APP_NAME,
        ORG_NAME,
    )

    assert ORG_NAME == "RADIANT"
    assert APP_NAME == "Geometry"

    # QSettings constructed with the same org/app must round-trip.
    s = QSettings(ORG_NAME, APP_NAME)
    s.setValue("test/roundtrip_phase6", "marker_value")
    s.sync()

    s2 = QSettings(ORG_NAME, APP_NAME)
    assert s2.value("test/roundtrip_phase6") == "marker_value"
    s2.remove("test/roundtrip_phase6")
    s2.sync()


def test_load_theme_returns_string(qt_app) -> None:
    """``load_theme`` must always return a usable string (default on first
    launch, persisted value otherwise)."""
    from dev_tools.geometry_gui_v2.app.window_persistence import load_theme

    value = load_theme()
    assert isinstance(value, str)
    assert value  # non-empty
