"""Smoke and contract tests for the RADIANT main window shell (GUI plan Phase 1).

Run headless::

    pytest src/radiant/gui/tests/ -v

Covers:
  * the window opens and closes cleanly (the checkpoint's core assertion);
  * the full v1 menu surface is present, with only Phase-1 actions enabled;
  * a programmatic trigger of an *enabled* action (Quit) has its effect —
    establishing the menu-action-trigger test pattern later phases reuse.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDockWidget

from radiant.gui.main_window import RADIANTMainWindow


class TestWindowLifecycle:
    def test_window_opens_and_closes(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The window shows and then closes without error (smoke test)."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        window.show()
        assert window.isVisible()

        assert window.close()
        assert not window.isVisible()

    def test_default_title_and_status(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """With no sensor, the title is the bare app name and status is Ready."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        assert window.windowTitle() == "RADIANT"
        assert window.statusBar().currentMessage() == "Ready"
        assert window.sensor is None


class TestLayoutRegions:
    def test_shell_regions_present(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The named placeholder regions the theme/later phases anchor to exist."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)

        assert window.centralWidget().objectName() == "visualizationArea"
        dock_names = {d.objectName() for d in window.findChildren(QDockWidget)}
        assert {"stageStripDock", "parameterDock", "detailDock"} <= dock_names

    def test_chrome_content_wired_in(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The static Phase-1 chrome (strip, KPI badges, tabs) is populated."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)

        # 9-stage strip in chain order, all dots stale.
        assert [c.stage_title for c in window.stage_strip.chips][0] == "Geometry"
        assert len(window.stage_strip.chips) == 9
        assert all(c.dot.status == "stale" for c in window.stage_strip.chips)

        # Five KPI badges awaiting evaluation (em-dash values).
        badges = window.central_canvas.kpi_row.badges
        assert list(badges.keys()) == ["SNR", "NEDT", "NIIRS", "GSD", "MTF@Nyquist"]
        assert all(b.value_text() == "—" for b in badges.values())

        # Parameter dock: disabled filter, empty tree; detail dock: five tabs.
        assert not window.parameter_panel.filter_box.isEnabled()
        assert window.parameter_panel.tree.topLevelItemCount() == 0
        assert window.detail_tabs.count() == 5

    def test_default_window_size(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The window opens at the mockup-matched 1440×900 default."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        assert window.size().width() == 1440
        assert window.size().height() == 900


class TestMenuSurface:
    def test_full_menu_surface_present(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Every arch-doc §10 menu is present as a top-level menu."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        titles = {a.text() for a in window.menuBar().actions()}
        for expected in ("&File", "&Edit", "&View", "&Run", "&Tools", "&Help"):
            assert expected in titles

    def test_only_quit_enabled_in_phase1(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Phase 1 implements only Quit; every other action is present-but-disabled."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)

        assert window.action("file.quit").isEnabled()
        # A representative sample of not-yet-implemented actions across menus.
        for key in (
            "file.open",
            "file.save",
            "edit.undo",
            "view.theme",
            "run.evaluate",
            "run.sweep",
            "tools.console",
            "help.about",
        ):
            assert not window.action(key).isEnabled(), key

    def test_quit_action_closes_window(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Triggering the enabled Quit action closes the window.

        This is the reusable menu-action-trigger pattern: fetch the QAction by its
        stable key and ``trigger()`` it, then assert the observable effect.
        """
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        window.show()
        assert window.isVisible()

        window.action("file.quit").trigger()
        assert not window.isVisible()

    def test_unknown_action_key_raises(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Looking up a non-existent action key is a programmer error (KeyError)."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        with pytest.raises(KeyError):
            window.action("nope.missing")
