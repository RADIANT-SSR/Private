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
        """With no sensor: app-name title (WS-A3), the welcome surface + its status hint (§4.4a)."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        # Title carries the version/build label (e.g. "RADIANT v0.1.0 (+abc123)").
        assert window.windowTitle().startswith("RADIANT v")
        assert "mission template" in window.statusBar().currentMessage()
        assert window.sensor is None
        assert window.is_welcome()


class TestLayoutRegions:
    def test_shell_regions_present(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The named placeholder regions the theme/later phases anchor to exist."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)

        assert window.centralWidget().objectName() == "visualizationArea"
        dock_names = {d.objectName() for d in window.findChildren(QDockWidget)}
        # Contextual layout: stage strip, left parameter dock, right rail — no bottom
        # detail dock (its tabs dissolved into the per-stage center + Inspector, §4.7).
        assert {"stageStripDock", "parameterDock", "rightRailDock"} <= dock_names
        assert "detailDock" not in dock_names

    def test_chrome_content_wired_in(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The static Phase-1 chrome (strip, KPI badges, tabs) is populated."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)

        # 10-stage strip in chain order, all dots stale (calibration joined
        # between readout and performance — Gap 120, ADR-0012).
        assert [c.stage_title for c in window.stage_strip.chips][0] == "Geometry"
        assert len(window.stage_strip.chips) == 10
        assert all(c.dot.status == "stale" for c in window.stage_strip.chips)

        # Right-rail Pinned panel: the five default performance metrics awaiting
        # evaluation (em-dash values) — the relocated metric badges (arch doc §4.5).
        cards = window.right_rail.pinned.cards
        assert list(cards.keys()) == [
            "snr",
            "nedt_K",
            "niirs",
            "gsd_geometric_mean_m",
            "mtf_at_nyquist",
        ]
        assert all(c.value_text() == "—" for c in cards.values())

        # Parameter dock: disabled filter, empty tree (no config loaded).
        assert not window.parameter_panel.filter_box.isEnabled()
        assert window.parameter_panel.tree.topLevelItemCount() == 0

        # Contextual center: the pre-evaluate placeholder is shown; the global Inspector
        # tool is disabled until a result exists (§4.6).
        assert window.central_canvas.stage_center.is_placeholder()
        assert not window.action("tools.inspector").isEnabled()

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

    def test_action_enablement_on_empty_window(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """On a bare (no-sensor) window, only the sensor-independent actions are enabled.

        Phase 9 wired the File / Edit / View menus: New / Open and the View toggles work
        without a loaded sensor, while sensor-gated actions (Save, Evaluate, Console) and
        the empty-stack Undo/Redo stay disabled; Sweep / Monte Carlo / Batch remain disabled
        through v1 (D4). This supersedes the Phase-1 "only Quit enabled" assertion.
        """
        window = RADIANTMainWindow()
        qtbot.addWidget(window)

        # Enabled without a sensor.
        for key in (
            "file.quit",
            "file.new",
            "file.open",
            "view.theme",
            "view.toggle_params",
            "view.toggle_rail",
        ):
            assert window.action(key).isEnabled(), key

        # Disabled without a sensor / with an empty undo stack / deferred to v1.1.
        for key in (
            "file.save",
            "file.save_as",
            "edit.undo",
            "edit.redo",
            "run.evaluate",
            "run.sweep",
            "tools.scripting_window",
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


class TestDocumentSwapHygiene:
    """Live-review fixes 2026-09-07: a fresh document never wears the old one's state."""

    def test_blank_config_invites_editing_and_clears_pins(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from pathlib import Path as _Path

        from radiant.api.sensor import Sensor

        example = _Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
        window = RADIANTMainWindow(Sensor.load(example))
        qtbot.addWidget(window)
        with qtbot.waitSignal(window.evaluationFinished, timeout=15000):
            pass
        snr_card = window.right_rail.pinned.cards["snr"]
        assert snr_card.value_text() not in ("", "—")  # populated by the evaluate

        window._on_blank_config()

        # Pinned cards return to awaiting — the old SNR described the old config.
        assert snr_card.value_text() == "—"
        # The center placeholder invites the edit instead of "Open a configuration".
        placeholder = window._central.stage_center.plot_placeholder
        assert "double-click" in placeholder._message.text()
        assert "Open a configuration" not in placeholder._message.text()

    def test_blank_config_stage_screens_are_editable(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Live review 2026-09-07 second pass: building a config through the
        stage screens must not require a first evaluation."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        window._on_blank_config()
        center = window._central.stage_center
        for namespace in ("geometry", "readout", "calibration", "performance"):
            center.select_stage(namespace)
            assert not center.is_placeholder(), namespace
        form = center._panes["calibration"].calibration_inputs_form
        assert form is not None and form._sensor is not None
