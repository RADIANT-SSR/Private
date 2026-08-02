"""The interpolated-library family picker + its Messages-rail coverage check (CU-239).

Category D — the GUI half of CU-239 layer 1 (the API payload landed 2026-07-30). What
these assert:

1. **The catalogue is the list.** The picker enumerates
   ``shipped_atmosphere_families()`` exactly — the row count comes from the API, never
   from a number typed here — plus one free-text escape hatch at the end.
2. **Choosing writes derived values.** One user action writes
   ``atmosphere.interpolation_axes`` (and ``atmosphere.interpolated_data_dir`` for a
   family no axes key can reach), announced as one edit the host can undo in one step.
3. **The scene's recommendation is pre-selected, not applied.** For the CU's own
   reproduction — a 20 km target under the default ``path_zenith_rad`` axes — the picker
   pre-selects ``midlat_summer_ladders`` as a *proposal* and writes nothing until the
   operator applies it, because adopting a family can change the atmosphere profile.
4. **The profile-mismatch caveat surfaces**, verbatim from the API.
5. **The boost ladder is selectable by name** (ex-CU-296) and selecting it writes the
   bundled directory, the only route to its 24 runs.
6. **The coverage check reaches the Messages rail on edit**, not only at Evaluate — and
   clears again when the config is fixed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api import shipped_atmosphere_families  # noqa: E402
from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.atmosphere_family_picker import (  # noqa: E402
    AXES_PARAM,
    CUSTOM_LABEL,
    DATA_DIR_PARAM,
    RECOMMENDED_SUFFIX,
    AtmosphereFamilyPicker,
)
from radiant.gui.widgets.atmosphere_inputs_form import _INTERPOLATED_FIELDS  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

_LADDERS = "midlat_summer_ladders"
_BOOST = "midlat_summer_boost_ladder"
_ZENITH_FAN = "us_standard_zenith_fan"


def _interpolated_sensor(**overrides: Any) -> Sensor:
    """The shipped example on the interpolated backend: LEO nadir → 20 km target.

    This is the CU-239 operator scenario verbatim — the axes parameter still carries
    its ``path_zenith_rad`` default, which selects a ground-target-only family. The
    example's own 8 km sensor is raised to LEO so the line of sight is down-looking
    (an 8 km sensor under a 20 km target would be an *up*-looking scene, a different
    family direction entirely).
    """
    sensor = (
        Sensor.load(_EXAMPLE)
        .set("atmosphere.model", "interpolated")
        .set("geometry.sensor_altitude_m", 500_000.0)
        .set("geometry.target_altitude_m", 20_000.0)
    )
    for dotpath, value in overrides.items():
        sensor.set(dotpath.replace("__", "."), value)
    return sensor


def _picker(qtbot, sensor: Sensor | None) -> AtmosphereFamilyPicker:  # type: ignore[no-untyped-def]
    picker = AtmosphereFamilyPicker()
    qtbot.addWidget(picker)
    picker.bind_sensor(sensor, {})
    return picker


class TestCatalogueIsTheList:
    def test_the_picker_enumerates_every_shipped_family_plus_the_escape_hatch(  # type: ignore[no-untyped-def]
        self, qtbot
    ) -> None:
        picker = _picker(qtbot, _interpolated_sensor())
        families = shipped_atmosphere_families()

        # The count comes from the API — adding a family must not need a test edit.
        assert picker.combo.count() == len(families) + 1
        assert picker.combo.itemText(picker.combo.count() - 1) == CUSTOM_LABEL
        for index, family in enumerate(families):
            label = picker.combo.itemText(index)
            assert family.name in label
            assert family.profile in label

    def test_the_free_text_axes_row_is_gone_from_the_form_manifest(self) -> None:
        """The picker replaced the row — it did not appear next to it (Rule 27)."""
        assert AXES_PARAM not in [dotpath for _, dotpath in _INTERPOLATED_FIELDS]
        assert DATA_DIR_PARAM in [dotpath for _, dotpath in _INTERPOLATED_FIELDS]

    def test_the_coverage_line_carries_its_units(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        picker = _picker(qtbot, _interpolated_sensor())
        picker.select_family_by_name(_LADDERS)
        text = picker.coverage_text()
        assert "km" in text
        assert "degrees" in text
        assert "sensor_altitude_m,target_altitude_m" in text

    def test_an_unbound_picker_offers_nothing_and_says_so(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        picker = _picker(qtbot, None)
        assert picker.combo.isEnabled() is False
        assert picker.selected_family() is None


class TestChoosingWritesDerivedValues:
    def test_choosing_a_family_writes_its_axes_string(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = _interpolated_sensor()
        picker = _picker(qtbot, sensor)
        assert sensor.get_input(AXES_PARAM) == "path_zenith_rad"

        with qtbot.waitSignal(picker.parametersEdited, timeout=1000) as blocker:
            picker.select_family_by_name(_LADDERS)

        assert sensor.get_input(AXES_PARAM) == "sensor_altitude_m,target_altitude_m"
        assert blocker.args == [[AXES_PARAM]]
        # The scene is now covered, so the picker sits on the configured family.
        assert picker.is_proposal_pending is False
        assert picker.selected_family() is not None
        assert picker.selected_family().name == _LADDERS

    def test_choosing_a_default_dispatch_family_clears_a_stale_directory(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A directory set for another family must not quietly outlive the choice."""
        boost = next(f for f in shipped_atmosphere_families() if f.name == _BOOST)
        sensor = _interpolated_sensor()
        sensor.set(DATA_DIR_PARAM, boost.bundled_dir)
        picker = _picker(qtbot, sensor)

        picker.select_family_by_name(_LADDERS)

        assert sensor.get_input(AXES_PARAM) == "sensor_altitude_m,target_altitude_m"
        assert sensor.get_input(DATA_DIR_PARAM) == ""

    def test_binding_alone_writes_nothing(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The picker is a read until the operator acts (the profile-safety rule)."""
        sensor = _interpolated_sensor()
        picker = _picker(qtbot, sensor)
        picker.refresh()

        assert sensor.get_input(AXES_PARAM) == "path_zenith_rad"
        assert sensor.get_input(DATA_DIR_PARAM) == ""
        assert picker.is_proposal_pending is True  # proposed, not applied


class TestSceneRecommendation:
    def test_the_scene_recommendation_is_marked_and_preselected(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The CU-239 reproduction: 20 km target, default axes."""
        picker = _picker(qtbot, _interpolated_sensor())

        assert picker.recommended_family is not None
        assert picker.recommended_family.name == _LADDERS
        selected = picker.selected_family()
        assert selected is not None
        assert selected.name == _LADDERS
        assert picker.is_proposal_pending is True
        # The list marks it, and the note says what is wrong with what is configured.
        marked = [
            picker.combo.itemText(i)
            for i in range(picker.combo.count())
            if RECOMMENDED_SUFFIX in picker.combo.itemText(i)
        ]
        assert len(marked) == 1
        assert _LADDERS in marked[0]
        assert "Not applied yet" in picker.coverage_text()
        assert _ZENITH_FAN in picker.coverage_text()
        assert picker.apply_button.isVisibleTo(picker) is True

    def test_applying_the_proposal_writes_it_and_clears_the_pending_state(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = _interpolated_sensor()
        picker = _picker(qtbot, sensor)
        assert picker.is_proposal_pending is True

        picker.apply_button.click()

        assert sensor.get_input(AXES_PARAM) == "sensor_altitude_m,target_altitude_m"
        assert picker.is_proposal_pending is False
        assert picker.apply_button.isVisibleTo(picker) is False
        assert picker.coverage_text().startswith("Covers ")

    def test_a_ground_target_scene_needs_no_proposal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Zero regression: a covered config shows the configured family, plainly."""
        sensor = _interpolated_sensor().set("geometry.target_altitude_m", 0.0)
        picker = _picker(qtbot, sensor)

        assert picker.is_proposal_pending is False
        assert picker.configured_family is not None
        assert picker.configured_family.name == _ZENITH_FAN


class TestProfileSafety:
    def test_a_profile_mismatch_is_surfaced_beside_the_family(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Choosing a family must never silently change the requested profile."""
        sensor = _interpolated_sensor().set("atmosphere.standard_atmosphere", "tropical")
        picker = _picker(qtbot, sensor)
        picker.select_family_by_name(_LADDERS)  # rendered with midlat_summer

        warning = picker.warning_text()
        assert "tropical" in warning
        assert "midlat_summer" in warning
        assert "changes the atmosphere profile" in warning

    def test_no_caveat_when_the_profile_matches(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = _interpolated_sensor().set("atmosphere.standard_atmosphere", "midlat_summer")
        picker = _picker(qtbot, sensor)
        picker.select_family_by_name(_LADDERS)

        assert picker.warning_text() == ""


class TestBoostLadderReachability:
    def test_the_boost_ladder_is_offered_by_name(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Ex-CU-296: 24 runs no axes key could select are now one click away."""
        picker = _picker(qtbot, _interpolated_sensor())
        labels = [picker.combo.itemText(i) for i in range(picker.combo.count())]
        assert any(_BOOST in label for label in labels)

    def test_selecting_it_writes_the_bundled_directory_as_one_compound_edit(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = _interpolated_sensor()
        picker = _picker(qtbot, sensor)

        with qtbot.waitSignal(picker.parametersEdited, timeout=1000) as blocker:
            picker.select_family_by_name(_BOOST)

        boost = next(f for f in shipped_atmosphere_families() if f.name == _BOOST)
        assert sensor.get_input(AXES_PARAM) == boost.interpolation_axes
        assert sensor.get_input(DATA_DIR_PARAM) == boost.bundled_dir
        # Two parameters, one action — the host records one undo step.
        assert blocker.args == [[AXES_PARAM, DATA_DIR_PARAM]]
        # And the picker keeps showing the boost family, not the ladders that own the
        # same axes key: the directory is what distinguishes them.
        assert picker.configured_family is not None
        assert picker.configured_family.name == _BOOST

    def test_the_directory_it_writes_really_carries_the_runs(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = _interpolated_sensor()
        picker = _picker(qtbot, sensor)
        picker.select_family_by_name(_BOOST)

        written = Path(str(sensor.get_input(DATA_DIR_PARAM)))
        assert written.is_dir()
        assert len(sorted(written.glob("*.npz"))) == 24


class TestMessagesRailOnEdit:
    """The coverage check fires on edit, not only at Evaluate (CU-239 layer 3 → GUI)."""

    def _window(self, qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
        window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
        qtbot.addWidget(window)
        with qtbot.waitSignal(window.evaluationFinished, timeout=20000):
            pass
        return window

    def test_an_edit_into_a_mismatched_family_reports_before_any_evaluation(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Fail-on-old-code: before CU-239's rail surfacing this was silent until the run."""
        window = self._window(qtbot)
        assert window.right_rail.messages.has_error() is False

        window.sensor.set("atmosphere.model", "interpolated")
        window.sensor.set("geometry.sensor_altitude_m", 500_000.0)
        window.sensor.set("geometry.target_altitude_m", 20_000.0)
        # One ordinary edit signal — the same one every form emits.
        window.parameter_panel.parameterEdited.emit("geometry.target_altitude_m")

        # The refusal is in the rail *now*, with the remedy, before the debounced run.
        assert window.evaluation_scheduled is True
        assert window.right_rail.messages.has_error() is True
        text = str(window.right_rail.messages.error)
        assert "target_altitude_m" in text
        assert "sensor_altitude_m,target_altitude_m" in text  # the exact axes to set
        assert _LADDERS in text

    def test_fixing_the_axes_clears_the_advisory_it_raised(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = self._window(qtbot)
        window.sensor.set("atmosphere.model", "interpolated")
        window.sensor.set("geometry.sensor_altitude_m", 500_000.0)
        window.sensor.set("geometry.target_altitude_m", 20_000.0)
        window.parameter_panel.parameterEdited.emit("geometry.target_altitude_m")
        assert window.right_rail.messages.has_error() is True

        window.sensor.set(AXES_PARAM, "sensor_altitude_m,target_altitude_m")
        window.parameter_panel.parameterEdited.emit(AXES_PARAM)

        assert window.right_rail.messages.has_error() is False

    def test_a_simple_model_edit_never_raises_an_advisory(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """No-op for every backend but interpolated — the rail stays clean."""
        window = self._window(qtbot)
        window.sensor.set("geometry.sensor_altitude_m", 500_000.0)
        window.sensor.set("geometry.target_altitude_m", 20_000.0)
        window.parameter_panel.parameterEdited.emit("geometry.target_altitude_m")

        assert window.right_rail.messages.has_error() is False
