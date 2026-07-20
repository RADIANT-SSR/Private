"""Tests for the Geometry screen — stage-0 input forms + derived-angle readout (Phase 5).

These drive the real widgets on the shipped example config, offscreen. The contracts:

* the Qt-free mode manifest covers every ``geometry.*`` schema parameter, and its
  dot-paths all still exist in the live schema (drift guard);
* each input mode round-trips — selecting a mode, setting its field through the public
  API, and refreshing shows the value and detects that mode as active;
* mode switching enables the active mode's fields and disables the rest;
* the derived-angle readout groups target-frame vs ground-frame and renders every value
  from ``stage_outputs["geometry"]`` **exactly**, each with its unit;
* a real over-/under-specified geometry surfaces the stage's error with the offending
  mode selector highlighted and the Geometry screen selected;
* values display in the shared session display unit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import radiant.gui.widgets.actionable_error_dialog as aed
from radiant.api.sensor import Sensor
from radiant.gui.geometry_modes import (
    KINEMATICS_FAMILY,
    MODE_FAMILIES,
    SOLAR_FAMILY,
    VIEWING_FAMILY,
    active_mode_key,
    all_mode_params,
    implicated_families,
)
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.param_format import format_value
from radiant.gui.widgets.geometry_mode_form import GeometryModeForm
from radiant.gui.widgets.geometry_readout import GeometryReadout

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000


@pytest.fixture(scope="module")
def sensor() -> Sensor:
    """A sensor loaded from the shipped example config."""
    return Sensor.load(_EXAMPLE)


@pytest.fixture(scope="module")
def geometry_outputs(sensor: Sensor) -> dict:  # type: ignore[type-arg]
    """``stage_outputs["geometry"]`` from one real evaluation of the example config."""
    return sensor.evaluate().stage_outputs["geometry"]


def _load_window(qtbot):  # type: ignore[no-untyped-def]
    """Build a window on the example config and wait for its auto-evaluation."""
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


def _bound_form(qtbot, sensor: Sensor) -> GeometryModeForm:
    """A GeometryModeForm bound to *sensor* with a fresh display-unit store."""
    form = GeometryModeForm()
    qtbot.addWidget(form)
    form.bind_sensor(sensor, {})
    return form


# ---------------------------------------------------------------------------
# Mode manifest (Qt-free)
# ---------------------------------------------------------------------------


class TestModeManifest:
    def test_manifest_covers_every_geometry_parameter(self, sensor: Sensor) -> None:
        """Every ``geometry.*`` input-mode schema parameter appears exactly once in the manifest.

        The ``geometry.target.*`` extent params (shape, dimensions,
        orientation, projected area — migrated from ``source.target.*`` per
        ADR-0008) are rendered by ``TargetShapePanel``, not the V/S input-mode
        forms, so they are excluded from the mode-manifest coverage set.
        """
        schema_geometry = {
            p
            for p in sensor.parameter_defs()
            if p.startswith("geometry.") and not p.startswith("geometry.target.")
        }
        manifest = set(all_mode_params())
        assert manifest == schema_geometry
        assert len(all_mode_params()) == len(schema_geometry)  # no duplicates

    def test_manifest_dotpaths_exist_in_schema(self, sensor: Sensor) -> None:
        """Drift guard: every named dot-path resolves in the live schema."""
        defs = sensor.parameter_defs()
        assert all(dotpath in defs for dotpath in all_mode_params())

    def test_three_families_present(self) -> None:
        """The manifest exposes the viewing, solar, and kinematics selectors."""
        assert {f.key for f in MODE_FAMILIES} == {"viewing", "solar", "kinematics"}

    def test_implicated_family_viewing_disagreement(self) -> None:
        """A viewing disagreement (two angle doors) localises to the viewing selector."""
        ctx = {"geometry.path_zenith_rad": 0.5, "geometry.sensor_off_nadir_rad": 0.1}
        assert implicated_families("Over-specified viewing geometry", ctx) == {"viewing"}

    def test_implicated_family_solar_ltan_conflict(self) -> None:
        """The ltan/local-time mutual-exclusion error localises to the solar selector."""
        ctx = {"ltan_h": 10.0, "local_solar_time_h": 12.0}
        assert implicated_families("Both ltan_h and local_solar_time_h set", ctx) == {"solar"}

    def test_implicated_family_kinematics_orbit_conflict(self) -> None:
        """A circular-orbit speed conflict localises to the kinematics selector."""
        ctx = {"derived_m_s": 6900.0, "explicit_m_s": 5000.0}
        assert implicated_families("derives a ground-track speed", ctx) == {"kinematics"}

    def test_implicated_family_range_vs_angle(self) -> None:
        """A range-vs-angle slant conflict localises to the viewing selector."""
        ctx = {
            "geometry.target_range_m": 1e5,
            "implied_slant_range_m": 2e5,
            "viewing_mode": "path_zenith (default)",
        }
        assert implicated_families("target_range_m disagrees", ctx) == {"viewing"}

    def test_active_mode_defaults_when_nothing_provided(self, sensor: Sensor) -> None:
        """With only the anchor altitude set, each family sits in its default door."""

        def provided(dotpath: str) -> bool:
            from radiant.gui.param_format import safe_provenance

            prov = safe_provenance(sensor, dotpath)
            return prov not in ("", "default")

        def value(dotpath: str):  # type: ignore[no-untyped-def]
            try:
                return sensor.get_input(dotpath)
            except KeyError:
                return None

        assert active_mode_key(VIEWING_FAMILY, provided, value) == "V1"
        assert active_mode_key(SOLAR_FAMILY, provided, value) == "S1"
        assert active_mode_key(KINEMATICS_FAMILY, provided, value) == "direct"


# ---------------------------------------------------------------------------
# GeometryModeForm
# ---------------------------------------------------------------------------


class TestGeometryModeForm:
    def test_every_field_rendered(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """Every manifest dot-path has a field row in the form."""
        form = _bound_form(qtbot, sensor)
        for dotpath in all_mode_params():
            assert form.field_value_text(dotpath)  # a rendered value (— if unset)

    def test_default_active_modes(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """The example config (nadir default) opens on the default door per family."""
        form = _bound_form(qtbot, sensor)
        assert form.active_mode("viewing") == "V1"
        assert form.active_mode("solar") == "S1"
        assert form.active_mode("kinematics") == "direct"

    def test_mode_switch_enables_only_active_fields(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """Selecting a viewing mode enables its field and disables the other doors."""
        form = _bound_form(qtbot, sensor)
        form.select_mode("viewing", "V2")
        assert form.is_field_editable("geometry.sensor_off_nadir_rad")  # active door
        assert not form.is_field_editable("geometry.path_zenith_rad")  # V1 door
        assert not form.is_field_editable("geometry.ground_range_m")  # V3 door
        # Anchors are always editable regardless of the active mode.
        assert form.is_field_editable("geometry.sensor_altitude_m")

        form.select_mode("viewing", "V3")
        assert form.is_field_editable("geometry.ground_range_m")
        assert not form.is_field_editable("geometry.sensor_off_nadir_rad")

    def test_mode_roundtrip_via_public_api(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Set a mode's field through the public API → sensor + form both reflect it.

        Drives each viewing door: setting its parameter makes the stage adopt that mode
        (provenance detection) and the form shows the value with the sensor agreeing.
        """
        cases = {
            "V2": ("geometry.sensor_off_nadir_rad", 0.1),
            "V3": ("geometry.ground_range_m", 2000.0),
            "V4": ("geometry.elevation_angle_rad", 1.4),
        }
        for mode_key, (dotpath, value) in cases.items():
            sensor = Sensor.load(_EXAMPLE)
            sensor.set(dotpath, value)  # one public-API call, the sanctioned edit
            form = _bound_form(qtbot, sensor)
            # The sensor reflects the set (round-trip via the public surface).
            assert sensor.get_input(dotpath) == pytest.approx(value)
            # The form detected the mode and shows the value (formatted with its unit).
            assert form.active_mode("viewing") == mode_key
            unit = sensor.parameter_def(dotpath).input_unit
            assert form.field_value_text(dotpath) == format_value(value, unit)

    def test_values_carry_units(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """A dimensional field shows its unit suffix (R-UNITS)."""
        form = _bound_form(qtbot, sensor)
        assert form.field_value_text("geometry.sensor_altitude_m").endswith("m")
        assert form.field_value_text("geometry.solar_zenith_rad").endswith("rad")

    def test_display_unit_store_is_shared(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """A display unit in the shared store re-expresses the value (owner feedback)."""
        store: dict[str, str] = {"geometry.sensor_altitude_m": "km"}
        form = GeometryModeForm()
        qtbot.addWidget(form)
        form.bind_sensor(sensor, store)
        # 8000 m in the example → shown as 8 km.
        assert form.field_value_text("geometry.sensor_altitude_m") == "8 km"

    def test_highlight_localises_and_clears(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """A viewing conflict tints only the viewing selector; clear resets all."""
        form = _bound_form(qtbot, sensor)
        ctx = {"geometry.path_zenith_rad": 0.5, "geometry.sensor_off_nadir_rad": 0.1}
        families = form.highlight_error("Over-specified viewing geometry", ctx)
        assert families == {"viewing"}
        assert form.is_conflicting("viewing")
        assert not form.is_conflicting("solar")
        assert not form.is_conflicting("kinematics")
        form.clear_highlight()
        assert not form.is_conflicting("viewing")


# ---------------------------------------------------------------------------
# Derived-angle readout — frame grouping + exact values
# ---------------------------------------------------------------------------


class TestGeometryReadout:
    def test_frame_groups_present(self, qtbot, geometry_outputs: dict) -> None:  # type: ignore[no-untyped-def, type-arg]
        """The readout groups target-frame vs ground/platform frame vs resolution."""
        readout = GeometryReadout()
        qtbot.addWidget(readout)
        readout.populate(geometry_outputs)
        titles = readout.group_titles()
        assert "Target-frame angles" in titles
        assert "Ground / platform frame" in titles
        # θ_o and θ_s sit in the target frame; the ranges sit in the ground frame.
        assert "theta_o_rad" in readout.group_keys("Target-frame angles")
        assert "theta_s_rad" in readout.group_keys("Target-frame angles")
        assert "slant_range_m" in readout.group_keys("Ground / platform frame")
        assert "ground_range_m" in readout.group_keys("Ground / platform frame")

    def test_values_match_stage_outputs_exactly(self, qtbot, geometry_outputs: dict) -> None:  # type: ignore[no-untyped-def, type-arg]
        """Every rendered value equals the stage output verbatim, with its unit."""
        readout = GeometryReadout()
        qtbot.addWidget(readout)
        readout.populate(geometry_outputs)
        # Every scalar output key is rendered (structured objects like los_geometry skipped).
        scalar_keys = {
            key
            for key, val in geometry_outputs.items()
            if val is None or isinstance(val, (bool, int, float, str))
        }
        assert readout.rendered_keys() == scalar_keys
        for key in scalar_keys:
            from radiant.gui.widgets.geometry_readout import _unit_for

            expected = format_value(geometry_outputs[key], _unit_for(key))
            assert readout.value_text(key) == expected

    def test_dimensional_values_have_units(self, qtbot, geometry_outputs: dict) -> None:  # type: ignore[no-untyped-def, type-arg]
        """Angles carry ``rad`` and ranges carry ``m`` (no bare dimensional number)."""
        readout = GeometryReadout()
        qtbot.addWidget(readout)
        readout.populate(geometry_outputs)
        assert readout.value_text("theta_o_rad").endswith("rad")
        assert readout.value_text("slant_range_m").endswith("m")

    def test_default_is_scrollable(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The default (accordion) form keeps its own inner scroll area."""
        readout = GeometryReadout()
        qtbot.addWidget(readout)
        assert readout._scroll is not None  # noqa: SLF001

    def test_flat_readout_has_no_inner_scroll(self, qtbot, geometry_outputs: dict) -> None:  # type: ignore[no-untyped-def, type-arg]
        """scrollable=False drops the inner scroll so the enclosing pane owns scrolling.

        Bug fix 2026-07-14: nesting the readout's inner scroll inside the pane's outer
        scroll clipped the derived table to a short sliver; the Inputs tab uses the flat
        form so one full-height scrollbar spans the whole table.
        """
        readout = GeometryReadout(scrollable=False)
        qtbot.addWidget(readout)
        readout.populate(geometry_outputs)
        assert readout._scroll is None  # noqa: SLF001
        # The table still renders every scalar row (content sizes the widget, not a scroll).
        assert "theta_o_rad" in readout.rendered_keys()

    def test_inputs_tab_readout_is_flat(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Geometry Inputs-tab readout is the flat (pane-scrolled) form, not inner-scroll."""
        from radiant.gui.stage_views import STAGE_COMPOSITIONS
        from radiant.gui.widgets.stage_center import StagePane

        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        qtbot.addWidget(pane)
        assert pane.geometry_readout is not None
        assert pane.geometry_readout._scroll is None  # noqa: SLF001


# ---------------------------------------------------------------------------
# Integration — window wiring, conflict highlight, exact readout on the pane
# ---------------------------------------------------------------------------


class TestGeometryScreenIntegration:
    def test_geometry_pane_has_form_and_readout(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Geometry stage pane composes the input form + the angle readout."""
        window = _load_window(qtbot)
        pane = window.central_canvas.stage_center.pane("geometry")
        assert pane.geometry_form is not None
        assert pane.geometry_readout is not None

    def test_pane_readout_matches_stage_outputs(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """After evaluate, the pane's readout renders the live stage outputs exactly."""
        window = _load_window(qtbot)
        window.central_canvas.select_stage("geometry")
        result = window._last_result
        assert result is not None
        outputs = result.stage_outputs["geometry"]
        readout = window.central_canvas.stage_center.pane("geometry").geometry_readout
        assert readout is not None
        from radiant.gui.widgets.geometry_readout import _unit_for

        assert readout.value_text("theta_o_rad") == format_value(
            outputs["theta_o_rad"], _unit_for("theta_o_rad")
        )
        assert readout.value_text("slant_range_m") == format_value(
            outputs["slant_range_m"], _unit_for("slant_range_m")
        )

    def test_conflict_highlights_viewing_selector(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """A real over-specified viewing geometry tints the viewing selector + navigates.

        Two disagreeing viewing doors are set through the public API, forcing the stage's
        ``GeometrySpecificationError`` at evaluate; the window highlights the viewing
        selector and shows the Geometry screen (Phase 5 task 3). The actionable dialog is
        captured so it does not block the event loop.
        """
        window = _load_window(qtbot)
        shown: list[aed.ActionableErrorDialog] = []
        monkeypatch.setattr(aed.ActionableErrorDialog, "exec", lambda self: shown.append(self) or 0)

        # A genuine, schema-valid pair that disagrees on θ_o → the stage over-spec error.
        window.sensor.set("geometry.path_zenith_rad", 0.5)
        window.sensor.set("geometry.sensor_off_nadir_rad", 0.1)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit("geometry.path_zenith_rad")

        assert len(shown) == 1  # the stage's actionable error surfaced
        form = window.central_canvas.stage_center.pane("geometry").geometry_form
        assert form is not None
        assert form.is_conflicting("viewing")
        assert not form.is_conflicting("solar")
        # The window jumped to the Geometry screen so the tint is visible.
        assert window.central_canvas.selected_stage == "geometry"

    def test_tree_edit_syncs_geometry_form_immediately(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """CU-121: a geometry value edited in the tree re-syncs the Geometry form at once.

        Firing the tree-edit signal (``parameterEdited``) updates the form synchronously,
        before the debounced re-evaluate lands — the two surfaces are no longer a cycle
        out of step.
        """
        window = _load_window(qtbot)
        form = window.central_canvas.stage_center.pane("geometry").geometry_form
        assert form is not None
        # Change altitude as a tree edit would (public API), then fire the tree-edit
        # signal WITHOUT waiting for the debounced evaluate.
        window.sensor.set("geometry.sensor_altitude_m", 654321.0)
        window.parameter_panel.parameterEdited.emit("geometry.sensor_altitude_m")
        # The form already shows the new value — no evaluation was awaited.
        assert "654321" in form.field_value_text("geometry.sensor_altitude_m")

    def test_clean_run_clears_conflict(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Resolving the conflict on a clean re-run clears the selector tint."""
        window = _load_window(qtbot)
        monkeypatch.setattr(aed.ActionableErrorDialog, "exec", lambda self: 0)

        window.sensor.set("geometry.path_zenith_rad", 0.5)
        window.sensor.set("geometry.sensor_off_nadir_rad", 0.1)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit("geometry.path_zenith_rad")
        form = window.central_canvas.stage_center.pane("geometry").geometry_form
        assert form is not None
        assert form.is_conflicting("viewing")

        # Remove the redundant door: one θ_o source, a clean run, tint cleared.
        window.sensor.reset("geometry.sensor_off_nadir_rad")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit("geometry.sensor_off_nadir_rad")
        assert not form.is_conflicting("viewing")
