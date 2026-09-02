"""Tests for the welcome screen — mission templates at File → New (§4.4a).

The owner-confirmed brief (2026-08-31): a bare window shows mission-template
cards + Blank config + Open recent; picking a card drives the ordinary open
pipeline, auto-evaluates, and surfaces the template's tune-next guidance as
clickable rows that reveal the named parameter. File → New returns to the
welcome surface; its Blank card performs the classic blank-adopt.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.mission_templates import discover_templates, templates_dir  # noqa: E402
from radiant.gui.widgets.message_item import SEVERITY_INFO  # noqa: E402
from radiant.gui.widgets.parameter_delegate import DOTPATH_ROLE  # noqa: E402
from radiant.gui.widgets.welcome_screen import WelcomeScreen  # noqa: E402

_WAIT_MS = 60000


def _bare_window(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    window = RADIANTMainWindow()
    qtbot.addWidget(window)
    return window


def _welcome_widget(window: RADIANTMainWindow) -> WelcomeScreen:
    widget = window._welcome_overlay  # noqa: SLF001
    assert isinstance(widget, WelcomeScreen)
    return widget


class TestDiscovery:
    def test_repo_templates_are_found(self) -> None:
        found = discover_templates()
        assert len(found) >= 3
        for info in found:
            assert info.name and info.blurb and info.specs
            assert 3 <= len(info.tune_next) <= 5

    def test_missing_directory_degrades_to_empty(self, tmp_path: Path) -> None:
        assert discover_templates(tmp_path / "nope") == ()

    def test_file_without_metadata_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "bare.yaml").write_text(
            "source:\n  target:\n    temperature: 300.0\n", encoding="utf-8"
        )
        assert discover_templates(tmp_path) == ()

    def test_templates_dir_resolves_inside_the_repo(self) -> None:
        found = templates_dir()
        assert found is not None and found.name == "templates"


class TestWelcomeSurface:
    def test_bare_launch_shows_welcome_with_cards(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _bare_window(qtbot)
        assert window.is_welcome()
        welcome = _welcome_widget(window)
        assert len(welcome.cards) == len(discover_templates())
        assert welcome.blank_card is not None
        # Cards are keyboard citizens: focusable buttons.
        assert all(card.focusPolicy() != 0 for card in welcome.cards)

    def test_blank_card_adopts_a_blank_sensor(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _bare_window(qtbot)
        _welcome_widget(window).blank_card.click()
        assert not window.is_welcome()
        assert window.sensor is not None

    def test_file_new_returns_to_welcome(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _bare_window(qtbot)
        _welcome_widget(window).blank_card.click()
        assert not window.is_welcome()
        window._on_new()  # noqa: SLF001 — clean state, no discard guard
        assert window.is_welcome()
        assert window.sensor is None

    def test_off_repo_welcome_still_offers_blank(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        screen = WelcomeScreen(recent_files=["/no/such/file.yaml"], templates=())
        qtbot.addWidget(screen)
        assert screen.cards == []
        assert screen.blank_card is not None
        assert screen.recent_rows == []  # nonexistent recents are filtered


class TestTemplateFlow:
    def _pick_ground_to_air(self, qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
        window = _bare_window(qtbot)
        welcome = _welcome_widget(window)
        card = next(c for c in welcome.cards if "Ground" in c.info.name)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
                card.click()
        return window

    def test_card_loads_evaluates_and_shows_workspace(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = self._pick_ground_to_air(qtbot)
        assert not window.is_welcome()
        assert window.last_result is not None
        assert window.last_result.snr() > 0

    def test_guidance_rows_appear_and_reveal_parameters(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = self._pick_ground_to_air(qtbot)
        messages = window.right_rail.messages
        layout = messages._items_layout  # noqa: SLF001
        rows = [
            layout.itemAt(i).widget()
            for i in range(layout.count())
            if layout.itemAt(i).widget() is not None
        ]
        guidance = [r for r in rows if r.property("severity") == SEVERITY_INFO]
        assert 3 <= len(guidance) <= 5
        assert "Tune next" in guidance[0].text()
        # Activate the first row: the named parameter is revealed + selected.
        with qtbot.waitSignal(messages.guidanceClicked, timeout=1000):
            guidance[0].clicked.emit()
        current = window.parameter_panel.tree.currentItem()
        assert current is not None
        assert str(current.data(0, DOTPATH_ROLE)).startswith("geometry.")

    def test_guidance_clears_on_the_next_document(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = self._pick_ground_to_air(qtbot)
        window._on_new()  # noqa: SLF001
        _welcome_widget(window).blank_card.click()
        messages = window.right_rail.messages
        layout = messages._items_layout  # noqa: SLF001
        rows = [
            layout.itemAt(i).widget()
            for i in range(layout.count())
            if layout.itemAt(i).widget() is not None
        ]
        assert not [r for r in rows if r.property("severity") == SEVERITY_INFO]
