"""Tests for the Optics **Transmission** tab (owner-ratified 2026-09-09/10).

The Optics stage's *Elements* and *Throughput* tabs were two halves of one question —
**how is optical transmission defined?** — split across the tab strip. The consolidation
folds both into one **Transmission** tab whose top-to-bottom order is: the mode selector,
the mode banner, the active mode's editor (the ``optics.transmission_scalar`` field, moved
off the *Inputs* form, or the element-train table with its Gap-116 coating drill-down), the
τ(λ) figures, and the Gap-128 cold-stop / effective-pupil strip.

What these tests pin, beyond "the tab exists":

* **The mode reflects the document, never a guess.** A config with an ``optical_elements``
  list opens in *Element train*; anything else opens in *Scalar throughput*.
* **Switching is non-destructive in-session but honest on disk.** Leaving element mode
  detaches the document (so the physics stops running full-prescription) while the rows
  stay in the table, inactive, and switching back re-commits them — but a **save** writes
  only the active mode, so a file with an element list means element mode, period.
* **The effective-pupil strip shows evaluated values with units**, read verbatim from
  ``stage_outputs["optics"]``, beside the two editable cold-stop parameters.

Every test drives the real widgets on the shipped example config, offscreen.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtCore import QSettings  # noqa: E402

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.settings_store import SettingsStore  # noqa: E402
from radiant.gui.stage_views import STAGE_COMPOSITIONS  # noqa: E402
from radiant.gui.widgets.field_row import FieldRow  # noqa: E402
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402
from radiant.gui.widgets.transmission_mode_selector import (  # noqa: E402
    MODE_ELEMENT,
    MODE_SCALAR,
)
from radiant.gui.widgets.transmission_panel import TransmissionPanel  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000

# A minimal but legal two-element train (the io parser is the validator, as always).
_TRAIN: list[dict[str, Any]] = [
    {"name": "M1", "transfer_mode": "REFLECTIVE", "reflectance": 0.97, "temperature_K": 280.0},
    {
        "name": "band_filter",
        "transfer_mode": "REFRACTIVE",
        "kind": "filter",
        "transmittance": 0.9,
        "temperature_K": 240.0,
    },
]


def _evaluate(sensor: Sensor) -> Any:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


def _pane(qtbot, sensor: Sensor, *, populate: bool = True) -> StagePane:  # type: ignore[no-untyped-def]
    """A bound Optics StagePane on *sensor* (populated from one evaluation by default)."""
    pane = StagePane("optics", STAGE_COMPOSITIONS["optics"])
    qtbot.addWidget(pane)
    pane.bind_sensor(sensor, {})
    if populate:
        pane.populate(_evaluate(sensor))
    return pane


def _panel(qtbot, sensor: Sensor, **kwargs: Any) -> tuple[StagePane, TransmissionPanel]:  # type: ignore[no-untyped-def]
    """The pane **and** its Transmission panel.

    The pane comes back with it deliberately: ``qtbot.addWidget`` does not keep a widget
    alive on the C++ side, so a test that dropped the pane would find its children already
    deleted (conftest ``_release_widgets``).
    """
    pane = _pane(qtbot, sensor, **kwargs)
    panel = pane.transmission_panel
    assert panel is not None
    return pane, panel


def _window(qtbot, tmp_path: Path) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    settings = SettingsStore(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE), settings=settings)
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


# ---------------------------------------------------------------------------
# Composition — one tab, and nothing left behind
# ---------------------------------------------------------------------------


class TestComposition:
    def test_tab_strip_absorbs_elements_and_throughput(self) -> None:
        titles = [sv.title for sv in STAGE_COMPOSITIONS["optics"].subviews]
        assert titles == ["Inputs", "Transmission", "MTF", "PSF + Pupil"]
        assert "Elements" not in titles
        assert "Throughput" not in titles

    def test_transmission_tab_declares_its_sections(self) -> None:
        """Mode panel, both τ figures, and the effective-pupil strip, in one tab."""
        subviews = {sv.title: sv for sv in STAGE_COMPOSITIONS["optics"].subviews}
        tab = subviews["Transmission"]
        assert tab.transmission_panel is True
        assert tab.effective_pupil is True
        assert [p.method for p in tab.plots] == [
            "optical_throughput",
            "optical_throughput_terms",
        ]


# ---------------------------------------------------------------------------
# The mode reflects the loaded configuration — it is never invented
# ---------------------------------------------------------------------------


class TestModeReflectsConfig:
    def test_config_without_elements_opens_in_scalar(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        _pane_ref, panel = _panel(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert panel.mode == MODE_SCALAR
        assert panel.selector.mode == MODE_SCALAR
        assert panel.selector.button(MODE_SCALAR).isChecked()
        assert panel.element_editor.table.rowCount() == 0

    def test_config_with_elements_opens_in_element_train(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements([dict(e) for e in _TRAIN])
        _pane_ref, panel = _panel(qtbot, sensor)
        assert panel.mode == MODE_ELEMENT
        assert panel.selector.button(MODE_ELEMENT).isChecked()
        assert panel.element_editor.table.rowCount() == len(_TRAIN)

    def test_banner_states_the_active_definition(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The banner names the definition in force and what it makes irrelevant."""
        _scalar_pane, scalar = _panel(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert "Scalar throughput defines transmission" in scalar.banner.text()

        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements([dict(e) for e in _TRAIN])
        _element_pane, element = _panel(qtbot, sensor)
        assert "Element train defines transmission (2 elements)" in element.banner.text()
        assert "scalar τ ignored" in element.banner.text()

    def test_scalar_field_lives_here_and_shows_its_value(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """τ_opt is a shared FieldRow on this tab — its one home (2026-09-09/10)."""
        _pane_ref, panel = _panel(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert isinstance(panel.scalar_row(), FieldRow)
        assert panel.scalar_row().dotpath == "optics.transmission_scalar"
        assert panel.scalar_value_text() not in ("", "—")

    def test_each_mode_shows_only_its_own_figure(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The two modes do not describe the same structure, so they do not share a figure.

        Scalar mode has no elements — the combined overlay would rightly refuse, and a
        pane of refusal messages is not an honest scalar view. Element mode's overlay
        already carries the assembled τ_opt as its bold SYSTEM curve, so the standalone
        system figure beside it would draw the same line twice.
        """
        pane = _pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        sections = {s.method: s for s in pane._plot_sections}  # noqa: SLF001
        assert not sections["optical_throughput"].isHidden()
        assert sections["optical_throughput_terms"].isHidden()

        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements([dict(e) for e in _TRAIN])
        element_pane = _pane(qtbot, sensor)
        element_sections = {s.method: s for s in element_pane._plot_sections}  # noqa: SLF001
        assert not element_sections["optical_throughput_terms"].isHidden()
        assert element_sections["optical_throughput"].isHidden()

    def test_switching_mode_swaps_the_figure(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The selector is what moves them, live — not just the load-time state."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements([dict(e) for e in _TRAIN])
        pane = _pane(qtbot, sensor)
        panel = pane.transmission_panel
        assert panel is not None
        sections = {s.method: s for s in pane._plot_sections}  # noqa: SLF001

        panel.selector.button(MODE_SCALAR).click()
        assert sections["optical_throughput_terms"].isHidden()
        assert not sections["optical_throughput"].isHidden()

        panel.selector.button(MODE_ELEMENT).click()
        assert not sections["optical_throughput_terms"].isHidden()
        assert sections["optical_throughput"].isHidden()


# ---------------------------------------------------------------------------
# Mode switching — non-destructive in session, single-mode on disk
# ---------------------------------------------------------------------------


class TestModeSwitching:
    def test_switching_to_scalar_detaches_the_document_but_holds_the_rows(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements([dict(e) for e in _TRAIN])
        _pane_ref, panel = _panel(qtbot, sensor)

        with qtbot.waitSignal(panel.parameterEdited, timeout=5000):
            panel.selector.button(MODE_SCALAR).click()

        assert panel.mode == MODE_SCALAR
        # The physics stops running full-prescription…
        assert sensor.optical_elements() is None
        assert _evaluate(sensor).stage_outputs["optics"]["transmission_input_mode"] != (
            "full_prescription"
        )
        # …but the authored rows are still on screen, inactive, so the operator can A/B.
        assert panel.element_editor.table.rowCount() == len(_TRAIN)
        assert not panel.element_editor.is_active
        assert not panel.element_editor.table.isEnabled()
        assert panel.held_element_rows() == len(_TRAIN)

    def test_held_rows_survive_a_rebind(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The host re-binds after every edit; a held draft must not be silently wiped."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements([dict(e) for e in _TRAIN])
        pane = _pane(qtbot, sensor)
        panel = pane.transmission_panel
        assert panel is not None
        panel.selector.button(MODE_SCALAR).click()

        panel.element_editor.bind_sensor(sensor, {})  # the host's re-materialize beat
        assert panel.element_editor.table.rowCount() == len(_TRAIN)

    def test_held_banner_warns_that_the_rows_are_not_saved(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements([dict(e) for e in _TRAIN])
        _pane_ref, panel = _panel(qtbot, sensor)
        panel.selector.button(MODE_SCALAR).click()

        assert panel.banner.property("state") == "held"
        text = panel.banner.text()
        assert "2 element row(s)" in text
        assert "writes no optical_elements section" in text

    def test_switching_back_reattaches_the_same_train(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements([dict(e) for e in _TRAIN])
        _pane_ref, panel = _panel(qtbot, sensor)
        panel.selector.button(MODE_SCALAR).click()
        assert sensor.optical_elements() is None

        with qtbot.waitSignal(panel.parameterEdited, timeout=5000):
            panel.selector.button(MODE_ELEMENT).click()

        assert panel.mode == MODE_ELEMENT
        assert sensor.optical_elements() == _TRAIN
        assert panel.element_editor.is_active
        assert panel.element_editor.table.isEnabled()
        assert panel.held_element_rows() == 0


# ---------------------------------------------------------------------------
# Saving writes only the active mode (no hidden inactive state in configs)
# ---------------------------------------------------------------------------


class TestSaveWritesActiveMode:
    def _optics_pane(self, window: RADIANTMainWindow) -> StagePane:
        window.stage_strip.stageClicked.emit("optics")
        return window.central_canvas.stage_center.pane("optics")

    def test_element_mode_writes_the_element_list(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _window(qtbot, tmp_path)
        panel = self._optics_pane(window).transmission_panel
        assert panel is not None
        window.sensor.set_optical_elements([dict(e) for e in _TRAIN])
        panel.bind_sensor(window.sensor, {})
        assert panel.mode == MODE_ELEMENT

        out = tmp_path / "element_mode.yaml"
        window._save_to_path(out)  # noqa: SLF001
        assert "optical_elements" in out.read_text(encoding="utf-8")
        assert Sensor.load(out).optical_elements() is not None

    def test_scalar_mode_writes_no_element_list_and_says_so(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A file with an element list means element mode, period — and the save says it."""
        window = _window(qtbot, tmp_path)
        panel = self._optics_pane(window).transmission_panel
        assert panel is not None
        window.sensor.set_optical_elements([dict(e) for e in _TRAIN])
        panel.bind_sensor(window.sensor, {})
        panel.selector.button(MODE_SCALAR).click()
        assert panel.held_element_rows() == len(_TRAIN)

        out = tmp_path / "scalar_mode.yaml"
        window._save_to_path(out)  # noqa: SLF001
        assert "optical_elements" not in out.read_text(encoding="utf-8")
        assert Sensor.load(out).optical_elements() is None
        # Non-modal: the status bar names what was deliberately left out.
        message = window.statusBar().currentMessage()
        assert "2 inactive element row(s)" in message
        assert "were not written" in message

    def test_a_plain_scalar_save_carries_no_note(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Nothing held ⇒ nothing to warn about (the note is not boilerplate)."""
        window = _window(qtbot, tmp_path)
        self._optics_pane(window)
        out = tmp_path / "plain.yaml"
        window._save_to_path(out)  # noqa: SLF001
        assert window.statusBar().currentMessage() == f"Saved {out.name}"


# ---------------------------------------------------------------------------
# The Gap-128 cold-stop / effective-pupil strip
# ---------------------------------------------------------------------------


class TestEffectivePupilStrip:
    def test_cold_stop_parameters_are_shared_field_rows(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        pane = _pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        strip = pane.effective_pupil_readout
        assert strip is not None
        assert strip.field_dotpaths() == (
            "optics.cold_stop_undersize_frac",
            "optics.cold_stop_obscuration_ratio",
        )
        for dotpath in strip.field_dotpaths():
            assert isinstance(strip.row(dotpath), FieldRow)

    def test_derived_values_show_the_evaluated_pupil_with_units(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """D_eff [m], f/#_eff [-], A_collect [m²], Ω_cone [sr] — the scenario spec."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        pane = _pane(qtbot, sensor)
        strip = pane.effective_pupil_readout
        assert strip is not None
        assert strip.derived_keys() == ("D_eff_m", "f_number_eff", "A_collect", "Omega_cone")

        outputs = _evaluate(sensor).stage_outputs["optics"]
        assert strip.derived_text("D_eff_m").endswith(" m")
        assert strip.derived_text("f_number_eff").endswith(" [-]")
        assert strip.derived_text("A_collect").endswith(" m²")
        assert strip.derived_text("Omega_cone").endswith(" sr")
        # Rendered verbatim from the stage outputs — no GUI-side physics (Rules 2/6).
        assert strip.derived_text("D_eff_m").startswith(f"{float(outputs['D_eff_m']):g}")

    def test_values_are_dashes_before_the_first_evaluation(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The strip never guesses: unpopulated reads ``—``, not a plausible number."""
        pane = _pane(qtbot, Sensor.from_yaml(_EXAMPLE), populate=False)
        strip = pane.effective_pupil_readout
        assert strip is not None
        assert all(strip.derived_text(key) == "—" for key in strip.derived_keys())

    def test_editing_a_cold_stop_parameter_moves_the_pupil(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        """One sensor.set → re-evaluate → D_eff shrinks by (1 − u), live on this strip."""
        window = _window(qtbot, tmp_path)
        window.stage_strip.stageClicked.emit("optics")
        pane = window.central_canvas.stage_center.pane("optics")
        strip = pane.effective_pupil_readout
        assert strip is not None
        before = float(window.last_result.stage_outputs["optics"]["D_eff_m"])

        from radiant.gui.widgets import effective_pupil_readout as epr

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText("0.10")
            self.apply(close=True)
            return 0

        monkeypatch.setattr(epr.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            strip._open_editor("optics.cold_stop_undersize_frac")  # noqa: SLF001

        after = float(window.last_result.stage_outputs["optics"]["D_eff_m"])
        assert after == pytest.approx(before * 0.90, rel=1e-9)
        assert strip.derived_text("D_eff_m").startswith(f"{after:g}")
