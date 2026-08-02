"""Switching a scenario to the interpolated model, from the GUI's side (CU-322).

Category D — the GUI half of the interpolated-switch operator experience. The
three behaviours the entry's checklist names:

1. **The picker pre-selects a family the chain will actually serve** — including
   an ``explicit_dir_only`` row, which no axes string can reach and which the old
   axes-string recommendation could therefore never name. The proposal also fires
   when the *configured* family is a shipped one that this particular scene is
   outside of, which the axes-only coverage check cannot see.
2. **An uncovered scene gets one advisory, not a wall** — one Messages-rail item
   naming the closest miss, with its units, on edit rather than at Evaluate.
3. **An evaluate-time coverage refusal is not a "Parameter Rejected" modal** — it
   lands in the rail beside the atmosphere inputs; the modal stays for inputs the
   framework genuinely rejected.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.core.parameters import ParameterBoundsError  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets import actionable_error_dialog as aed  # noqa: E402
from radiant.gui.widgets.atmosphere_family_picker import (  # noqa: E402
    AXES_PARAM,
    DATA_DIR_PARAM,
    AtmosphereFamilyPicker,
)

_SCENARIOS = Path(__file__).resolve().parents[4] / "scenarios" / "10_direction_general"
_LEO_TO_GEO = _SCENARIOS / "10.4_leo_to_geo_exo" / "inputs" / "10.4_leo_to_geo_exo.gui.yaml"
_GROUND_TO_AIR = (
    _SCENARIOS
    / "10.1_ground_to_air_mwir_detection"
    / "inputs"
    / "10.1_ground_to_air_mwir_detection.gui.yaml"
)
_GROUND_TO_SPACE = (
    _SCENARIOS
    / "10.3_ground_to_space_sst_visible"
    / "inputs"
    / "10.3_ground_to_space_sst_visible.gui.yaml"
)

_SST_FAN = "midlat_summer_sst_column_fan"
_UP_LADDER = "midlat_summer_uplooking_ladder"
_UP_ZENITH_FAN = "midlat_summer_uplooking_zenith_fan"


def _interpolated(path: Path, **overrides: float) -> Sensor:
    """A shipped scenario switched to the interpolated backend, as an operator would."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sensor = Sensor.load(path).set("atmosphere.model", "interpolated")
    for dotpath, value in overrides.items():
        sensor.set(dotpath.replace("__", "."), value)
    return sensor


def _picker(qtbot, sensor: Sensor) -> AtmosphereFamilyPicker:  # type: ignore[no-untyped-def]
    picker = AtmosphereFamilyPicker()
    qtbot.addWidget(picker)
    picker.bind_sensor(sensor, {})
    return picker


class TestPickerPreSelection:
    def test_leo_to_geo_preselects_the_uplooking_ladder(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """10.4: an up-looking scene the axes default (``path_zenith_rad``) cannot reach."""
        picker = _picker(qtbot, _interpolated(_LEO_TO_GEO))

        assert picker.is_proposal_pending is True
        assert picker.recommended_family is not None
        assert picker.recommended_family.name == _UP_LADDER
        selected = picker.selected_family()
        assert selected is not None and selected.name == _UP_LADDER

    def test_a_ground_site_sst_scene_preselects_the_explicit_dir_sst_fan(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The row no axes string reaches, recommended by name (CU-322 defect (1) half two).

        10.3's geometry with the telescope at sea level: the only bundled family
        that measures the whole column from the ground at this zenith is the SST
        column fan, which lives in ``EXPLICIT_DIR_FAMILIES``. The pre-CU-322
        recommendation reasoned over axes strings only and could not name it.
        """
        sensor = _interpolated(_GROUND_TO_SPACE, geometry__sensor_altitude_m=0.0)
        picker = _picker(qtbot, sensor)

        assert picker.recommended_family is not None
        assert picker.recommended_family.name == _SST_FAN
        assert picker.recommended_family.explicit_dir_only is True
        assert picker.is_proposal_pending is True

    def test_applying_the_sst_proposal_writes_the_bundled_directory(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """An explicit-dir family needs both parameters, in one compound edit."""
        sensor = _interpolated(_GROUND_TO_SPACE, geometry__sensor_altitude_m=0.0)
        picker = _picker(qtbot, sensor)
        edits: list[list[str]] = []
        picker.parametersEdited.connect(edits.append)

        picker.apply_button.click()

        # The SST fan's axes string is the schema default, so only the directory
        # actually changes — which is exactly why no axes key can reach this family.
        assert sensor.get_input(AXES_PARAM) == "path_zenith_rad"
        assert sensor.get_input(DATA_DIR_PARAM) == picker.recommended_family.bundled_dir  # type: ignore[union-attr]
        assert edits and set(edits[0]) == {DATA_DIR_PARAM}
        assert picker.is_proposal_pending is False

    def test_an_off_vertical_up_scene_preselects_the_zenith_fan(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """10.1, the entry's defect (1): the vertical ladder is not the answer."""
        picker = _picker(qtbot, _interpolated(_GROUND_TO_AIR))

        assert picker.recommended_family is not None
        assert picker.recommended_family.name == _UP_ZENITH_FAN

    def test_the_proposal_fires_even_when_the_configured_axes_name_a_family(  # type: ignore[no-untyped-def]
        self, qtbot
    ) -> None:
        """The half ``validate_atmosphere_coverage`` cannot see, by construction.

        With ``interpolation_axes = 'target_altitude_m'`` the axes check passes —
        that string *does* name a shipped up-looking family — and the operator was
        then refused at Evaluate, because the family it names is rendered vertical
        and this scene's lower-endpoint zenith is 29.9 degrees.
        """
        sensor = _interpolated(_GROUND_TO_AIR).set(AXES_PARAM, "target_altitude_m")
        sensor.validate_atmosphere_coverage()  # the axes check is satisfied

        picker = _picker(qtbot, sensor)

        assert picker.configured_family is not None
        assert picker.configured_family.name == _UP_LADDER
        assert picker.is_proposal_pending is True
        selected = picker.selected_family()
        assert selected is not None and selected.name == _UP_ZENITH_FAN

    def test_the_highlighted_row_says_when_it_cannot_serve_the_scene(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Units explicit, and stated in the picker rather than found at Evaluate."""
        picker = _picker(qtbot, _interpolated(_GROUND_TO_AIR))
        picker.combo.setCurrentIndex(
            next(i for i, f in enumerate(picker.families) if f.name == _UP_LADDER)
        )
        picker._refresh_detail()  # noqa: SLF001 - the selection-changed render path

        text = picker.coverage_text()
        assert "Does not serve this scene" in text
        assert "degrees" in text


class TestOneAdvisoryPerScene:
    """The uncovered scene gets one sentence naming the closest miss."""

    def _window(self, qtbot, path: Path) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            window = RADIANTMainWindow(Sensor.load(path))
        qtbot.addWidget(window)
        with qtbot.waitSignal(window.evaluationFinished, timeout=30000):
            pass
        return window

    def test_the_elevated_sst_site_names_the_site_elevation_gap(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """10.3 as shipped: 900 m against a fan rendered from 0 m, plus M9-M13."""
        window = self._window(qtbot, _GROUND_TO_SPACE)
        assert window.right_rail.messages.has_error() is False

        window.sensor.set("atmosphere.model", "interpolated")
        window.parameter_panel.parameterEdited.emit("atmosphere.model")

        assert window.right_rail.messages.has_error() is True
        text = str(window.right_rail.messages.error)
        assert _SST_FAN in text
        assert "900 m" in text
        assert "M9-M13" in text

    def test_the_advisory_clears_when_the_scene_becomes_servable(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """It owns only the item it placed (Rule 17: the state stays honest)."""
        window = self._window(qtbot, _GROUND_TO_SPACE)
        window.sensor.set("atmosphere.model", "interpolated")
        window.parameter_panel.parameterEdited.emit("atmosphere.model")
        assert window.right_rail.messages.has_error() is True

        window.sensor.set("atmosphere.model", "simple")
        window.parameter_panel.parameterEdited.emit("atmosphere.model")

        assert window.right_rail.messages.has_error() is False

    def test_a_servable_scene_raises_no_advisory(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = self._window(qtbot, _GROUND_TO_AIR)
        window.sensor.set("atmosphere.model", "interpolated")
        window.sensor.set(AXES_PARAM, "target_altitude_m,path_zenith_rad")
        window.parameter_panel.parameterEdited.emit(AXES_PARAM)

        assert window.right_rail.messages.has_error() is False


class TestDialogRouting:
    """A coverage refusal is an advisory, not a rejected parameter."""

    def _window(self, qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            window = RADIANTMainWindow(Sensor.load(_GROUND_TO_AIR))
        qtbot.addWidget(window)
        with qtbot.waitSignal(window.evaluationFinished, timeout=30000):
            pass
        return window

    def test_an_evaluate_time_coverage_refusal_skips_the_rejection_modal(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """Fail-on-old-code: this reached the operator as *Cannot set "evaluate"*.

        The refusal is the real one — the vertical up-looking ladder declining a
        29.9 degree query — captured by evaluating 10.1 through that family.
        """
        shown: list[object] = []
        monkeypatch.setattr(aed.ActionableErrorDialog, "exec", lambda self: shown.append(self) or 0)
        window = self._window(qtbot)

        sensor = _interpolated(_GROUND_TO_AIR).set(AXES_PARAM, "target_altitude_m")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with pytest.raises(Exception) as excinfo:  # noqa: PT011 - the real refusal
                sensor.evaluate()
        refusal = excinfo.value

        window._on_eval_failed(refusal)  # noqa: SLF001 - the worker's failure slot

        assert shown == []
        assert window.right_rail.messages.error is refusal
        assert "does not cover this scene" in window.statusBar().currentMessage()

    def test_a_genuine_parameter_rejection_still_gets_the_modal(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """The modal is not disabled — only re-aimed (the control case)."""
        shown: list[object] = []
        monkeypatch.setattr(aed.ActionableErrorDialog, "exec", lambda self: shown.append(self) or 0)
        window = self._window(qtbot)

        window._on_eval_failed(  # noqa: SLF001
            ParameterBoundsError(
                what="sensor.detector.operating_temp = 5000 K is out of bounds",
                why="HgCdTe operates at cryogenic temperature",
                action="Set operating_temp to 77-120 K",
                context={"param": "sensor.detector.operating_temp"},
            )
        )

        assert len(shown) == 1
