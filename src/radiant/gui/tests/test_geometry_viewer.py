"""Tests for the ``ViewerState`` adapter + viewer import contract (2D-schematic pivot).

The ADR-0007 Part A/B PyVista scene library was removed once the 2D ``QPainter`` schematic
fully replaced it (CU-132); the arc / triad / shape-library / angle-truth coverage now
lives against the 2D canvas in ``test_schematic_view.py``. What remains here is
engine-independent: the ``ViewerState`` field mapping from ``stage_outputs`` + params
(ADR-0007 §2 rebind) and the import-linter contract that the viewer imports no physics
stage (gui → api + core).
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.viewer.viewer_state import ViewerState  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture(scope="module")
def evaluated() -> tuple[Sensor, object]:
    """The mwir_leo_minimal sensor and one evaluated result (shared, read-only)."""
    sensor = Sensor.from_yaml(_EXAMPLE)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = sensor.evaluate()
    return sensor, result


class TestViewerStateMapping:
    """The ADR-0007 §2 rebind: ViewerState fields ← stage_outputs + params."""

    def test_geometry_outputs_map_by_field(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        sensor, result = evaluated
        geo = result.stage_outputs["geometry"]
        vs = ViewerState.from_chain_result(result, sensor)

        assert vs.observer_altitude_m == geo["h_sensor_m"]
        assert vs.observer_look_angle_rad == geo["eta_rad"]
        assert vs.target_altitude_m == geo["h_target_m"]
        assert vs.solar_zenith_rad == geo["theta_s_rad"]
        assert vs.relative_azimuth_rad == geo["delta_phi_rad"]

    def test_regime_from_optics(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        """The final regime comes from stage_outputs['optics'] (Rule 10)."""
        _sensor, result = evaluated
        regime = result.stage_outputs["optics"]["regime"]
        vs = ViewerState.from_chain_result(result, _sensor)
        assert vs.regime_override == regime.value  # enum → literal

    def test_shape_and_sampling_from_params(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        sensor, result = evaluated
        vs = ViewerState.from_chain_result(result, sensor)
        assert vs.target_shape == "none"  # mwir example declares no discrete shape
        assert vs.focal_length_m == sensor.get("optics.focal_length_m")
        # get() returns canonical metres despite the ``_um`` input-unit name.
        assert vs.pixel_pitch_m == sensor.get("detector.pixel_pitch_x_um")

    def test_attitude_defaults_to_identity(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        """Platform attitude has no stage owner (CU-122) → defaults to zero."""
        sensor, result = evaluated
        vs = ViewerState.from_chain_result(result, sensor)
        assert vs.observer_yaw_rad == 0.0
        assert vs.observer_pitch_rad == 0.0
        assert vs.observer_roll_rad == 0.0

    def test_day_scene_has_sun(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        sensor, result = evaluated
        vs = ViewerState.from_chain_result(result, sensor)
        assert vs.has_sun is True

    def test_night_scene_drops_sun_instead_of_crashing(self) -> None:
        """Night publishes theta_s_rad = None; the adapter must record "no sun"
        rather than dying on float(None) (owner bug 2026-07-18)."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set("geometry.solar_illumination", "night")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = sensor.evaluate()
        assert result.stage_outputs["geometry"]["theta_s_rad"] is None

        vs = ViewerState.from_chain_result(result, sensor)
        assert vs.has_sun is False
        # Inert placeholders — never drawn (the scene hides all sun elements).
        assert vs.solar_zenith_rad == 0.0
        assert vs.relative_azimuth_rad == 0.0


class TestGeneralizedGeometryMapping:
    """ADR-0011: the generalized-geometry fields bind verbatim, with down-looking defaults.

    ``theta_o_rad`` / ``los_direction`` / ``scene_class`` / ``observer_class`` /
    ``target_class`` drive the schematic's *composition* — which endpoint is the lower one
    and where the ground plane sits — so they must arrive from the stage unchanged (§6.3),
    and a result that lacks them must still compose the pre-ADR-0011 down-looking scene.
    """

    def test_generalized_fields_map_verbatim(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        sensor, result = evaluated
        geo = result.stage_outputs["geometry"]
        vs = ViewerState.from_chain_result(result, sensor)

        assert vs.theta_o_rad == geo["theta_o_rad"]
        assert vs.los_direction == geo["los_direction"]
        assert vs.scene_class == geo["scene_class"]
        assert vs.observer_class == geo["observer_class"]
        assert vs.target_class == geo["target_class"]

    def test_example_is_a_down_looking_air_to_ground_scene(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        """The v1 baseline composition — an 8 km sensor over a sea-level target."""
        sensor, result = evaluated
        vs = ViewerState.from_chain_result(result, sensor)
        assert vs.los_direction == "down"
        assert vs.scene_class == "air_to_ground"
        assert vs.observer_class == "air"
        assert vs.target_class == "ground"
        # θ_o and η are read at different vertices of the same triangle, so θ_o is never
        # the smaller of the two (they coincide only at nadir).
        assert vs.theta_o_rad >= vs.observer_look_angle_rad

    def test_partial_stage_outputs_default_to_down_looking(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        """A result without the ADR-0011 keys binds the pre-Phase-4 down-looking defaults."""

        class _PartialResult:
            """A chain result whose geometry stage published none of the new keys."""

            stage_outputs: dict[str, dict[str, object]] = {"geometry": {}, "optics": {}}

        sensor, _result = evaluated
        vs = ViewerState.from_chain_result(_PartialResult(), sensor)  # type: ignore[arg-type]
        assert vs.los_direction == "down"
        assert vs.theta_o_rad == 0.0
        assert vs.scene_class == ""
        assert vs.observer_class == ""
        assert vs.target_class == ""

    def test_default_state_is_a_down_looking_baseline(self) -> None:
        vs = ViewerState.default()
        assert vs.los_direction == "down"
        assert vs.scene_class == "air_to_ground"
        assert vs.observer_class == "air"
        assert vs.target_class == "ground"


class TestViewerImportsNoPhysicsStage:
    """The viewer package must not import any physics stage (gui → api + core)."""

    def test_no_physics_stage_import(self) -> None:
        viewer_root = Path(__file__).resolve().parents[1] / "viewer"
        stage_re = re.compile(
            r"^\s*(?:from|import)\s+radiant\.(geometry|source|atmosphere|optics|platform"
            r"|spectral_integration|detector|readout|performance)\b",
            re.MULTILINE,
        )
        offenders: dict[str, list[str]] = {}
        for path in viewer_root.rglob("*.py"):
            hits = stage_re.findall(path.read_text(encoding="utf-8"))
            if hits:
                offenders[str(path)] = hits
        assert not offenders, f"physics-stage imports in the viewer: {offenders}"

    def test_no_pyvista_import_in_viewer(self) -> None:
        """The 2D schematic drops PyVista/VTK entirely (CU-132)."""
        viewer_root = Path(__file__).resolve().parents[1] / "viewer"
        pv_re = re.compile(r"^\s*(?:from|import)\s+(pyvista|pyvistaqt|vtk)\b", re.MULTILINE)
        offenders = {
            str(path): pv_re.findall(path.read_text(encoding="utf-8"))
            for path in viewer_root.rglob("*.py")
            if pv_re.findall(path.read_text(encoding="utf-8"))
        }
        assert not offenders, f"pyvista imports remain in the viewer: {offenders}"
