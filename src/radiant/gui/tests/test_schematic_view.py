"""Tests for the 2D geometry schematic viewer (Pass 1 — renderer core, ADR-0007).

The PyVista/VTK raster viewer was replaced by a pure-Qt 2D orthographic schematic
(owner-ratified 2026-07-14). Everything here renders **offscreen** via ``QWidget.grab()``
— fully faithful, no VTK, no segfault-prone live interactor.

Coverage:

* :class:`TestProjectionParity` — the ported ``geometry.js`` projection/direction math
  reproduces known reference outputs (``dirFromAzZen`` + a projected point).
* :class:`TestSceneBuild` — the abstract scene binds the stage-derived directions and
  honours the not-to-scale rule (display distance independent of raw altitude).
* :class:`TestSchematicCanvas` — the canvas renders bound to a real evaluation, draws the
  vectors + legend, and yaw/pitch rotation changes the projection.
* :class:`TestGeometryViewerWidget` — the embedded widget's preserved public surface
  (mode/availability, show_result render, Pass-2 stubs, theme swap, guard panel).
* :class:`TestGeometryPaneIntegration` — the Geometry center tabs "Inputs | Schematic"
  and the viewer renders after a full-chain evaluate.
* :class:`TestDownLookingRegression`, :class:`TestUpLookingComposition`,
  :class:`TestLevelComposition`, :class:`TestGeneralizedAnnotations`,
  :class:`TestSceneClassAngleTruth` — the ADR-0011 generalized-geometry compositions
  (Geometry-Flexibility plan Phase 4): the down-looking layout pinned unchanged, the
  up-looking and level layouts, the θ_o / ζ_low arcs + the level-arm Δh pill, and the
  angle-truth check parametrized over every scene class the viewer composes.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtGui import QColor, QImage  # noqa: E402

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.core.viewing_triangle import eta_from_theta_o  # noqa: E402
from radiant.gui.themes.tokens import DARK, LIGHT  # noqa: E402
from radiant.gui.viewer import angle_catalog, angle_truth  # noqa: E402
from radiant.gui.viewer.projection import (  # noqa: E402
    compute_angles,
    dir_from_az_zen,
    make_camera,
)
from radiant.gui.viewer.scene import palette  # noqa: E402
from radiant.gui.viewer.schematic_view import (  # noqa: E402
    _ELEVATED_ENDPOINT_Z,
    _GROUND_ENDPOINT_Z,
    _SENSOR_DIST,
    _SUN_DIST,
    SchematicScene,
    SchematicView,
    _area_label,
    _format_km,
    _level_sag_label,
    build_scene,
)
from radiant.gui.viewer.viewer_state import ViewerState  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

# -- ADR-0011 scene-class fixtures ---------------------------------------------
# One physically-consistent (h_sensor, h_target, θ_o) triple per scene class the viewer
# composes. η is solved from θ_o with the CORE viewing-triangle law of sines (gui → core is
# legal), so these are real triangles, not hand-waved angle pairs — and η therefore carries
# the Earth-centre central angle that separates it from θ_o.
_SCENE_CASES: dict[str, dict[str, float | str]] = {
    "space_to_ground_down": {
        "h_sensor_m": 705_000.0,
        "h_target_m": 0.0,
        "theta_o_deg": 25.0,
        "los_direction": "down",
        "observer_class": "space",
        "target_class": "ground",
    },
    "ground_to_air_up": {
        "h_sensor_m": 0.0,
        "h_target_m": 12_000.0,
        "theta_o_deg": 150.0,
        "los_direction": "up",
        "observer_class": "ground",
        "target_class": "air",
    },
    "ground_to_space_up": {
        "h_sensor_m": 0.0,
        "h_target_m": 400_000.0,
        "theta_o_deg": 150.0,
        "los_direction": "up",
        "observer_class": "ground",
        "target_class": "space",
    },
    "space_to_space_up": {
        # LEO → GEO: r_target/r_sensor ≈ 6.1, so the ray only reaches the sensor shell for
        # θ_o ≳ 170.6° — the law of sines rejects anything shallower.
        "h_sensor_m": 550_000.0,
        "h_target_m": 35_786_000.0,
        "theta_o_deg": 175.0,
        "los_direction": "up",
        "observer_class": "space",
        "target_class": "space",
    },
    "air_to_air_level": {
        "h_sensor_m": 5_000.0,
        "h_target_m": 5_000.0,
        "theta_o_deg": 90.5,
        "los_direction": "level",
        "observer_class": "air",
        "target_class": "air",
    },
}


def _case_state_and_geometry(
    case: str, **overrides: object
) -> tuple[ViewerState, dict[str, object]]:
    """A bound :class:`ViewerState` plus the ``stage_outputs["geometry"]`` it came from.

    The pair is built the way the production adapter builds it — every angle in the state is
    the verbatim stage value — so an angle-truth assertion over the two is a real check of
    the viewer's binding, not a tautology over one dict.
    """
    spec = _SCENE_CASES[case]
    theta_o = math.radians(float(spec["theta_o_deg"]))
    h_sensor = float(spec["h_sensor_m"])
    h_target = float(spec["h_target_m"])
    eta = eta_from_theta_o(theta_o, h_sensor, h_target)
    geometry: dict[str, object] = {
        "theta_o_rad": theta_o,
        "eta_rad": eta,
        "theta_s_rad": math.radians(35.0),
        "delta_phi_rad": math.radians(12.0),
        "los_direction": str(spec["los_direction"]),
        "h_sensor_m": h_sensor,
        "h_target_m": h_target,
        "scene_class": f"{spec['observer_class']}_to_{spec['target_class']}",
        "observer_class": str(spec["observer_class"]),
        "target_class": str(spec["target_class"]),
    }
    base = ViewerState.default().__dict__
    state = ViewerState(
        **{
            **base,
            "observer_altitude_m": h_sensor,
            "target_altitude_m": h_target,
            "observer_look_angle_rad": eta,
            "theta_o_rad": theta_o,
            "solar_zenith_rad": math.radians(35.0),
            "relative_azimuth_rad": math.radians(12.0),
            "los_direction": geometry["los_direction"],
            "scene_class": geometry["scene_class"],
            "observer_class": geometry["observer_class"],
            "target_class": geometry["target_class"],
            **overrides,
        }
    )
    return state, geometry


def _arc_subtended_rad(canvas: SchematicView, scene: SchematicScene, name: str) -> float:
    """The angle the DRAWN arc for *name* actually subtends about its apex [rad].

    Reads the arc polyline and its apex back off the canvas and measures the angle between
    the first and last spokes — i.e. what a user sees, not what the state says. Only the
    zenith-type arcs are measurable this way; the relative-azimuth arc is a ground-plane
    sweep about the origin rather than an apex arc, and is covered by the recomputation
    check instead.
    """
    pts = canvas._arc_points(scene, name)  # noqa: SLF001 — exercises the draw path
    apex = canvas._arc_apex(scene, name)  # noqa: SLF001
    first = pts[0] - apex
    last = pts[-1] - apex
    cos_t = float(np.dot(first, last) / (np.linalg.norm(first) * np.linalg.norm(last)))
    return math.acos(max(-1.0, min(1.0, cos_t)))


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


@pytest.fixture(scope="module")
def evaluated() -> tuple[Sensor, object]:
    sensor = Sensor.from_yaml(_EXAMPLE)
    return sensor, _evaluate(sensor)


@pytest.fixture
def offnadir_sphere() -> tuple[Sensor, object]:
    """An off-nadir sensor with a discrete sphere target (fresh, mutable)."""
    sensor = Sensor.from_yaml(_EXAMPLE)
    sensor.set("geometry.path_zenith_rad", 0.4)
    sensor.set("geometry.target.shape", "sphere")
    sensor.set("geometry.target.shape_radius_m", 1.0)
    return sensor, _evaluate(sensor)


def _has_color(img: QImage, hex_color: str, tol: int = 24, step: int = 2) -> bool:
    """True when a pixel close to *hex_color* appears in *img* (swatch/vector present)."""
    target = QColor(hex_color)
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            c = img.pixelColor(x, y)
            if (
                abs(c.red() - target.red())
                + abs(c.green() - target.green())
                + abs(c.blue() - target.blue())
            ) <= tol:
                return True
    return False


class TestProjectionParity:
    """The ported geometry.js math reproduces known reference outputs (verbatim port)."""

    def test_dir_from_az_zen_reference_cases(self) -> None:
        # Zenith direction: az/zen = 0 → straight up (+Z).
        assert np.allclose(dir_from_az_zen(0.0, 0.0), [0.0, 0.0, 1.0], atol=1e-12)
        # Due East on the horizon: az=90, zen=90 → +X.
        assert np.allclose(dir_from_az_zen(90.0, 90.0), [1.0, 0.0, 0.0], atol=1e-9)
        # A general case: az=45, zen=30 (sin30=0.5, sin45=cos45).
        s = 0.5 * math.sqrt(0.5)
        cz = math.cos(math.radians(30))
        assert np.allclose(dir_from_az_zen(45.0, 30.0), [s, s, cz], atol=1e-9)

    def test_camera_project_reference_point(self) -> None:
        """make_camera(35,22,100,400,300).project((2,0,0)) matches the geometry.js formula."""
        cam = make_camera(35.0, 22.0, 100.0, 400.0, 300.0)
        p = cam.project(np.array([2.0, 0.0, 0.0]))
        # Independently hand-computed from the geometry.js project() closure.
        assert p.x == pytest.approx(563.8304, abs=1e-3)
        assert p.y == pytest.approx(342.9731, abs=1e-3)
        assert p.depth == pytest.approx(-1.063622, abs=1e-5)

    def test_top_down_drops_z(self) -> None:
        """At pitch=90 (top-down) a +Z point projects to the canvas anchor (Z dropped)."""
        cam = make_camera(0.0, 90.0, 100.0, 200.0, 200.0)
        p = cam.project(np.array([0.0, 0.0, 5.0]))
        assert p.x == pytest.approx(200.0, abs=1e-6)
        assert p.y == pytest.approx(200.0, abs=1e-6)


class TestTargetAreaLabel:
    """The projected-area leader pill (CU-168) surfaces a target sized only by area."""

    def _state(self, **overrides: object) -> ViewerState:
        base = ViewerState.default()
        return ViewerState(**{**base.__dict__, **overrides})

    def test_no_area_no_label(self) -> None:
        """No projected area (extended scene) → no pill."""
        assert _area_label(0.0, 0.0, 10e-6, 1.0) is None

    def test_label_shows_area_and_pixel_multiple(self) -> None:
        """Maritime geometry: 240 m², 2.91e-5 rad extent, 15 µm / 0.75 m → 1.5 px."""
        label = _area_label(240.0, 2.9115e-5, 15e-6, 0.75)
        assert label == "A_t  240 m²  ·  1.5 px"

    def test_label_omits_px_when_ifov_unknown(self) -> None:
        """No focal length → area only, no fabricated pixel multiple."""
        assert _area_label(240.0, 2.9e-5, 15e-6, 0.0) == "A_t  240 m²"

    def test_scene_carries_label_for_point_target(self) -> None:
        """A shape='none' target with an area still gets the pill (the CU-168 case)."""
        scene = build_scene(
            self._state(
                target_shape="none",
                projected_area_m2=240.0,
                angular_extent_rad=2.9115e-5,
                pixel_pitch_m=15e-6,
                focal_length_m=0.75,
            )
        )
        assert scene.is_point is True  # bare marker — the size would otherwise be invisible
        assert scene.target_area_label == "A_t  240 m²  ·  1.5 px"

    def test_scene_label_none_when_no_area(self) -> None:
        scene = build_scene(self._state(target_shape="none", projected_area_m2=0.0))
        assert scene.target_area_label is None


class TestSceneBuild:
    """The abstract scene binds stage directions and honours the not-to-scale rule."""

    def _state(self, **overrides: object) -> ViewerState:
        base = ViewerState.default()
        return ViewerState(**{**base.__dict__, **overrides})

    def test_glyphs_sit_at_fixed_abstract_distance(self) -> None:
        scene = build_scene(self._state(target_shape="sphere"))
        assert np.linalg.norm(scene.sun_pos) == pytest.approx(_SUN_DIST, abs=1e-9)
        assert np.linalg.norm(scene.sensor_pos) == pytest.approx(_SENSOR_DIST, abs=1e-9)

    def test_display_distance_independent_of_raw_altitude(self) -> None:
        """Not-to-scale: a 75x change in raw altitude does not move the glyphs."""
        low = build_scene(self._state(observer_altitude_m=8_000.0))
        high = build_scene(self._state(observer_altitude_m=600_000.0))
        assert np.allclose(low.sensor_pos, high.sensor_pos)
        assert np.allclose(low.sun_pos, high.sun_pos)

    def test_sphere_and_box_have_wireframe_edges(self) -> None:
        assert build_scene(self._state(target_shape="sphere")).target_edges
        assert build_scene(self._state(target_shape="box")).target_edges

    def test_none_shape_is_point_reticle(self) -> None:
        scene = build_scene(self._state(target_shape="none"))
        assert scene.is_point
        assert scene.target_edges == ()

    def test_relative_azimuth_places_sun_off_sensor(self) -> None:
        """The sun sits at the relative azimuth from the sensor (relative geometry kept)."""
        scene = build_scene(self._state(relative_azimuth_rad=math.radians(30.0)))
        # Sensor is at azimuth 0; a nonzero relative azimuth gives the sun a +X component.
        assert scene.sun_pos[0] != pytest.approx(0.0, abs=1e-6)

    def test_night_scene_carries_no_sun(self) -> None:
        """A night state (has_sun=False) flows through to the scene flag."""
        scene = build_scene(self._state(has_sun=False))
        assert scene.has_sun is False


class TestNightHidesSunElements:
    """Night (owner bug 2026-07-18): every sun-derived element disappears."""

    def _night_scene(self, **overrides: object):  # type: ignore[no-untyped-def]
        base = ViewerState.default()
        state = ViewerState(**{**base.__dict__, "has_sun": False, **overrides})
        return build_scene(state)

    def test_sun_legend_row_absent(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        day = canvas._legend_entries(build_scene(ViewerState.default()))
        night = canvas._legend_entries(self._night_scene())
        assert any(label == "SUN → TARGET" for label, _c, _d in day)
        assert not any("SUN" in label for label, _c, _d in night)

    def test_sun_ground_vector_absent_for_airborne_target(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        vectors = canvas._ground_vectors(self._night_scene(target_altitude_m=9_000.0))
        labels = [label for label, *_rest in vectors]
        assert labels == ["SENSOR → GROUND"]

    def test_sun_arcs_not_drawable(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        scene = self._night_scene()
        for name in ("sun_zenith", "phase_angle", "relative_azimuth"):
            assert canvas._arc_points(scene, name) == []
        # The sensor's off-nadir arc survives — it does not involve the sun.
        assert canvas._arc_points(scene, "off_nadir")

    def test_fit_points_exclude_sun(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        scene = self._night_scene()
        assert not any(np.allclose(p, scene.sun_pos) for p in canvas._fit_points(scene))

    def test_night_canvas_renders_without_sun_color(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The night render succeeds and paints no amber (sun-family) pixels."""
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.resize(900, 600)
        base = ViewerState.default()
        canvas.set_state(ViewerState(**{**base.__dict__, "has_sun": False}))
        img = canvas.grab().toImage()
        assert img.width() == 900 and img.height() == 600
        assert not _has_color(img, palette.SOLAR_FAMILY)
        assert _has_color(img, palette.SATELLITE_FAMILY)


class TestSchematicCanvas:
    """The QPainter canvas renders and rotates."""

    def test_renders_bound_to_evaluation(self, qtbot, evaluated) -> None:  # type: ignore[no-untyped-def]
        sensor, result = evaluated
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.resize(900, 600)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        img = canvas.grab().toImage()
        assert img.width() == 900 and img.height() == 600
        # Both physics vector colours are painted (sun amber + sensor blue → vectors/legend).
        assert _has_color(img, palette.SOLAR_FAMILY)
        assert _has_color(img, palette.SATELLITE_FAMILY)

    def test_legend_panel_is_drawn(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """The VECTORS legend pill (theme.panel fill) appears top-left."""
        sensor, result = offnadir_sphere
        canvas = SchematicView(theme=LIGHT)
        qtbot.addWidget(canvas)
        canvas.resize(900, 600)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        img = canvas.grab().toImage()
        # The legend pill is filled with theme.panel over the theme.bg background.
        assert _has_color(img, LIGHT.panel, tol=6, step=1)

    def test_yaw_rotation_changes_projection(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        sensor, result = offnadir_sphere
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.resize(600, 400)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        canvas.set_orientation(0.0, 22.0)
        img_a = canvas.grab().toImage()
        canvas.set_orientation(90.0, 22.0)
        img_b = canvas.grab().toImage()
        assert canvas.yaw_deg == 90.0
        assert img_a != img_b  # a different yaw produces a different render

    def test_pitch_is_clamped(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.set_orientation(10.0, 200.0)
        assert canvas.pitch_deg == pytest.approx(89.0, rel=1e-9)
        canvas.set_orientation(10.0, -50.0)
        assert canvas.pitch_deg == pytest.approx(2.0, rel=1e-9)


class TestFitToViewport:
    """Owner report 2026-07-14: the scene must be CENTRED + framed, never bottom-anchored.

    The orthographic camera fits the projected scene bounding box into the *live* paint rect
    with a symmetric margin and centres it — so the schematic stays centred at any size and
    the too-tall-canvas bottom-anchoring is gone. Also asserts the canvas *fills* its viewport
    (Expanding policy + a sensible minimum) rather than reporting an unbounded size.
    """

    def _canvas(self, qtbot, offnadir_sphere, w: int, h: int) -> SchematicView:  # type: ignore[no-untyped-def]
        sensor, result = offnadir_sphere
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        canvas.resize(w, h)
        return canvas

    def test_scene_bbox_is_centred_in_rect(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        canvas = self._canvas(qtbot, offnadir_sphere, 760, 620)
        bounds = canvas.projected_content_bounds()
        assert bounds is not None
        min_x, min_y, max_x, max_y = bounds
        cx, cy = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0
        # The scene bbox centre lands on the rect centre (both axes), not near the bottom.
        assert cx == pytest.approx(760 / 2, abs=2.0)
        assert cy == pytest.approx(620 / 2, abs=2.0)

    def test_scene_fits_with_margin_not_flush(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        canvas = self._canvas(qtbot, offnadir_sphere, 760, 620)
        min_x, min_y, max_x, max_y = canvas.projected_content_bounds()  # type: ignore[misc]
        # Every side clears the rect edge by a real margin — the scene is framed, not clipped.
        assert min_x > 8.0 and min_y > 8.0
        assert max_x < 760 - 8.0 and max_y < 620 - 8.0

    def test_centring_holds_when_tall(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """A tall panel keeps the scene centred (the exact regression the owner saw)."""
        canvas = self._canvas(qtbot, offnadir_sphere, 760, 1000)
        min_x, min_y, max_x, max_y = canvas.projected_content_bounds()  # type: ignore[misc]
        assert (min_x + max_x) / 2.0 == pytest.approx(760 / 2, abs=2.0)
        assert (min_y + max_y) / 2.0 == pytest.approx(1000 / 2, abs=2.0)
        # Not bottom-anchored: the top margin is a real fraction of the panel, not ~0.
        assert min_y > 40.0

    def test_centring_holds_when_wide(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        canvas = self._canvas(qtbot, offnadir_sphere, 1200, 600)
        min_x, min_y, max_x, max_y = canvas.projected_content_bounds()  # type: ignore[misc]
        assert (min_x + max_x) / 2.0 == pytest.approx(1200 / 2, abs=2.0)
        assert (min_y + max_y) / 2.0 == pytest.approx(600 / 2, abs=2.0)

    def test_canvas_fills_not_grows_unbounded(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The canvas policy fills its viewport with a sane minimum — no unbounded growth."""
        from PySide6.QtWidgets import QSizePolicy

        canvas = SchematicView()
        qtbot.addWidget(canvas)
        assert canvas.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
        assert canvas.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
        # A concrete, bounded sizeHint + minimum — never the degenerate (-1, -1) a scroll
        # area would inflate.
        hint = canvas.sizeHint()
        assert hint.isValid() and 300 <= hint.height() <= 1200
        assert canvas.minimumSize().width() >= 360 and canvas.minimumSize().height() >= 360

    def test_bounds_none_before_state(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        assert canvas.projected_content_bounds() is None


class TestGeometryViewerWidget:
    """The embedded widget's preserved public surface (2D pivot)."""

    def test_mode_is_schematic_and_available(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        assert viewer.mode == "schematic"
        assert viewer.is_available and not viewer.is_degraded
        assert viewer.canvas is not None

    def test_show_result_renders(self, qtbot, evaluated) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = evaluated
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.resize(720, 520)
        viewer.show_result(result, sensor)
        assert viewer.canvas is not None and viewer.canvas.scene is not None

    def test_pass2_stubs_track_state_without_error(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """set_angle_revealed / set_triad_visible are no-op-safe stubs that track state."""
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = offnadir_sphere
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.show_result(result, sensor)
        viewer.set_angle_revealed("sun_zenith", True)
        assert viewer.revealed_angles == frozenset({"sun_zenith"})
        viewer.set_angle_revealed("sun_zenith", False)
        assert viewer.revealed_angles == frozenset()
        viewer.set_triad_visible(True)
        assert viewer.triad_visible is True

    def test_set_theme_repaints(self, qtbot, evaluated) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = evaluated
        viewer = GeometryViewer(theme=LIGHT)
        qtbot.addWidget(viewer)
        viewer.show_result(result, sensor)
        viewer.set_theme(DARK)
        assert viewer.canvas is not None and viewer.canvas.theme is DARK

    def test_guard_panel_on_build_failure(self, qtbot, evaluated) -> None:  # type: ignore[no-untyped-def]
        """A build failure surfaces the actionable guard panel (minimal, near-unreachable)."""
        from PySide6.QtWidgets import QLabel

        from radiant.gui.viewer import viewer_widget
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = evaluated
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)

        def _boom(_result, _params):  # type: ignore[no-untyped-def]
            raise RuntimeError("bad state")

        monkey = pytest.MonkeyPatch()
        monkey.setattr(viewer_widget.ViewerState, "from_chain_result", staticmethod(_boom))
        try:
            viewer.show_result(result, sensor)
        finally:
            monkey.undo()

        assert viewer.is_degraded and viewer.mode == "unavailable"
        assert "bad state" in (viewer.unavailable_reason or "")
        panels = [w for w in viewer.findChildren(QLabel) if w.objectName() == "viewerUnavailable"]
        assert panels and "unavailable" in panels[0].text().lower()

    def test_guard_panel_recovers_on_next_good_result(self, qtbot, evaluated) -> None:  # type: ignore[no-untyped-def]
        """CU-163: the guard panel is not one-way — a later clean evaluate
        rebuilds the canvas and re-enters schematic mode."""
        from PySide6.QtWidgets import QLabel

        from radiant.gui.viewer import viewer_widget
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = evaluated
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)

        # Force one transient adapter failure → guard panel.
        def _boom(_result, _params):  # type: ignore[no-untyped-def]
            raise RuntimeError("transient")

        monkey = pytest.MonkeyPatch()
        monkey.setattr(viewer_widget.ViewerState, "from_chain_result", staticmethod(_boom))
        try:
            viewer.show_result(result, sensor)
        finally:
            monkey.undo()
        assert viewer.is_degraded and viewer.canvas is None

        # A subsequent good evaluate must restore the schematic.
        viewer.show_result(result, sensor)
        assert viewer.is_available and viewer.mode == "schematic"
        assert viewer.unavailable_reason is None
        assert viewer.canvas is not None
        # The guard panel is gone, not merely hidden behind the restored canvas.
        panels = [w for w in viewer.findChildren(QLabel) if w.objectName() == "viewerUnavailable"]
        assert not panels
        # View controls still route to the rebuilt canvas without error.
        viewer.set_triad_visible(True)
        viewer.set_angle_revealed("theta_o", True)

    def test_close_viewer_is_safe(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.close_viewer()  # no VTK window to release — must not raise


class TestGeometryPaneIntegration:
    """The Geometry center tabs "Inputs | Schematic" and renders on evaluate."""

    def test_pane_tabs_and_viewer(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.stage_views import STAGE_COMPOSITIONS
        from radiant.gui.widgets.stage_center import StagePane

        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        qtbot.addWidget(pane)
        assert pane.has_tabs
        assert pane.tab_titles() == ["Inputs", "Schematic"]
        assert pane.geometry_viewer is not None

        sensor = Sensor.from_yaml(_EXAMPLE)
        pane.bind_sensor(sensor, {})
        pane.populate(_evaluate(sensor))
        viewer = pane.geometry_viewer
        assert viewer is not None and viewer.is_available
        assert viewer.canvas is not None and viewer.canvas.scene is not None

    def test_schematic_canvas_fills_bounded_window_not_balloons(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Mounted in a bounded window the Schematic canvas fills the viewport, never taller.

        Owner report 2026-07-14: the tall "Inputs" tab inflated the shared stack and ballooned
        the sibling "Schematic" canvas past the window height (scene then bottom-anchored). The
        canvas must stay within the window it is shown in.
        """
        from PySide6.QtWidgets import QMainWindow, QTabWidget

        from radiant.gui.stage_views import STAGE_COMPOSITIONS
        from radiant.gui.widgets.stage_center import StagePane

        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        win = QMainWindow()
        qtbot.addWidget(win)
        win.setCentralWidget(pane)
        win.resize(1000, 760)
        win.show()
        tabs = pane.findChild(QTabWidget)
        assert tabs is not None
        tabs.setCurrentIndex(1)  # Schematic

        sensor = Sensor.from_yaml(_EXAMPLE)
        pane.bind_sensor(sensor, {})
        pane.populate(_evaluate(sensor))
        for _ in range(4):
            qtbot.wait(1)

        canvas = pane.geometry_viewer.canvas  # type: ignore[union-attr]
        assert canvas is not None
        # The canvas must not balloon taller than the window it lives in.
        assert canvas.height() <= win.height()
        # And it still frames the scene centred within that bounded height.
        bounds = canvas.projected_content_bounds()
        assert bounds is not None
        cy = (bounds[1] + bounds[3]) / 2.0
        assert cy == pytest.approx(canvas.height() / 2, abs=3.0)


class TestShapeLibrary:
    """CU-131: the full shape library draws distinct wireframes reflecting dim aspect ratio."""

    def _state(self, **overrides: object) -> ViewerState:
        base = ViewerState.default()
        return ViewerState(**{**base.__dict__, **overrides})

    def test_each_shape_has_wireframe_edges(self) -> None:
        for shape in ("sphere", "cylinder", "cone", "box", "flat_plate"):
            scene = build_scene(self._state(target_shape=shape))
            assert scene.target_edges, f"{shape} drew no edges"
            assert not scene.is_point

    def test_shapes_are_distinct(self) -> None:
        """cylinder / cone / box are no longer the same box stand-in (Pass-1 gap closed)."""
        counts = {
            shape: len(build_scene(self._state(target_shape=shape)).target_edges)
            for shape in ("box", "cylinder", "cone", "flat_plate")
        }
        # Box=12 edges; cylinder/cone/plate use their own generators with different counts.
        assert counts["box"] == 12
        assert counts["cylinder"] != counts["box"]
        assert counts["cone"] != counts["box"]
        assert counts["flat_plate"] != counts["box"]

    def test_none_shape_is_point_reticle(self) -> None:
        scene = build_scene(self._state(target_shape="none"))
        assert scene.is_point
        assert scene.target_edges == ()

    def test_dimensions_change_the_wireframe_aspect(self) -> None:
        """A long cylinder and a squat cylinder produce different wireframes (aspect ratio)."""
        long_cyl = build_scene(
            self._state(target_shape="cylinder", target_radius_m=1.0, target_length_m=8.0)
        )
        squat_cyl = build_scene(
            self._state(target_shape="cylinder", target_radius_m=2.0, target_length_m=1.0)
        )
        # Compare the top-ring height (max z) — a long cylinder reaches higher than a squat one.
        long_top = max(float(b[2]) for e in long_cyl.target_edges for b in e)
        squat_top = max(float(b[2]) for e in squat_cyl.target_edges for b in e)
        assert long_top > squat_top

    def test_display_size_ignores_metric_magnitude(self) -> None:
        """Not-to-scale: scaling both dims by 1000 (same ratio) leaves the wireframe unchanged."""
        small = build_scene(
            self._state(
                target_shape="box", target_length_m=2.0, target_width_m=1.0, target_height_m=1.0
            )
        )
        huge = build_scene(
            self._state(
                target_shape="box",
                target_length_m=2000.0,
                target_width_m=1000.0,
                target_height_m=1000.0,
            )
        )
        for (a0, b0), (a1, b1) in zip(small.target_edges, huge.target_edges, strict=True):
            assert np.allclose(a0, a1) and np.allclose(b0, b1)


class TestAngleArcs:
    """CU-128: revealed arcs draw + carry a degree value pill sourced from the stage."""

    def test_revealing_an_arc_changes_the_render(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        sensor, result = offnadir_sphere
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.resize(900, 600)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        before = canvas.grab().toImage()
        canvas.set_revealed_angles({"sun_zenith"})
        after = canvas.grab().toImage()
        assert canvas.revealed_angles == frozenset({"sun_zenith"})
        assert before != after

    def test_azimuth_arc_paints_its_family_colour(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        sensor, result = offnadir_sphere
        canvas = SchematicView(theme=LIGHT)
        qtbot.addWidget(canvas)
        canvas.resize(900, 600)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        canvas.set_revealed_angles({"relative_azimuth"})
        img = canvas.grab().toImage()
        assert _has_color(img, palette.AZIMUTH_FAMILY, tol=40)

    def test_arc_label_reads_stage_value_in_degrees(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """The pinned value is the stage angle (via ViewerState) converted to degrees (§6.3)."""
        sensor, result = offnadir_sphere
        vs = ViewerState.from_chain_result(result, sensor)
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.set_state(vs)
        ann = angle_catalog.annotation("off_nadir")
        text = canvas._arc_label_text(ann)  # noqa: SLF001 — exercises the display path
        expected_deg = math.degrees(result.stage_outputs["geometry"]["eta_rad"])
        assert f"{expected_deg:.1f}" in text and "°" in text

    def test_phase_arc_is_symbol_only(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """No stage-output phase angle → symbol alone, never a fabricated number (§6.3)."""
        sensor, result = offnadir_sphere
        vs = ViewerState.from_chain_result(result, sensor)
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.set_state(vs)
        ann = angle_catalog.annotation("phase_angle")
        assert canvas._arc_label_text(ann) == ann.symbol  # noqa: SLF001


class TestLeaderLabels:
    """CU-129: altitude leader-label magnitudes come verbatim from the stage-bound state."""

    def test_altitude_km_bound_from_state(self) -> None:
        base = ViewerState.default()
        vs = ViewerState(**{**base.__dict__, "observer_altitude_m": 705_000.0})
        scene = build_scene(vs)
        assert scene.altitude_km == pytest.approx(705.0, abs=1e-9)

    def test_format_km_matches_owner_example(self) -> None:
        assert _format_km(705.0) == "705 km"
        assert _format_km(8.0) == "8.0 km"
        assert _format_km(0.5) == "500 m"


class TestRpyTriad:
    """CU-130: the on-target body-axes triad renders and follows the ZYX Euler orientation."""

    def _state(self, **overrides: object) -> ViewerState:
        base = ViewerState.default()
        return ViewerState(**{**base.__dict__, **overrides})

    def test_triad_toggle_changes_render(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        sensor, result = offnadir_sphere
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.resize(900, 600)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        off = canvas.grab().toImage()
        canvas.set_triad_visible(True)
        on = canvas.grab().toImage()
        assert canvas.triad_visible is True
        assert off != on

    def test_yaw_rotates_roll_axis_onto_scene_y(self) -> None:
        """A yaw of π/2 rotates the body +X (roll) axis onto scene +Y (mockup Euler)."""
        scene = build_scene(self._state(target_shape="box", target_yaw_rad=math.pi / 2))
        roll_dir = dict(scene.body_axes)["roll"]
        assert roll_dir[1] == pytest.approx(1.0, abs=1e-9)
        assert roll_dir[0] == pytest.approx(0.0, abs=1e-9)

    def test_pitch_change_moves_the_body_wireframe(self) -> None:
        flat = build_scene(self._state(target_shape="box"))
        tilted = build_scene(self._state(target_shape="box", target_pitch_rad=0.5))
        assert not np.allclose(
            np.array([a for e in flat.target_edges for a in e]),
            np.array([a for e in tilted.target_edges for a in e]),
        )


class TestAngleTruthConsistency:
    """CU-133 (binding, §6.3): viewer-local angle recomputation == stage output."""

    def test_recomputation_matches_stage_within_tolerance(self, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        sensor, result = offnadir_sphere
        geo = result.stage_outputs["geometry"]
        vs = ViewerState.from_chain_result(result, sensor)
        tol = angle_truth.ANGLE_CONSISTENCY_ABS_TOL_RAD
        worst = 0.0
        for name, key in angle_truth.ANGLE_TRUTH_KEYS.items():
            recomputed = angle_truth.recompute_angle_rad(vs, name)
            stage_value = float(geo[key])
            err = abs(recomputed - stage_value)
            worst = max(worst, err)
            assert err <= tol, f"{name}: viewer {recomputed} vs stage {stage_value} (Δ={err})"
        assert float(geo["eta_rad"]) > 0.1  # the fixture exercised a non-trivial off-nadir

    def test_tolerance_is_explicit_and_tight(self) -> None:
        assert angle_truth.ANGLE_CONSISTENCY_ABS_TOL_RAD == 1e-9

    def test_compute_angles_round_trips_construction(self) -> None:
        """compute_angles on scene-built directions reproduces the input zenith/azimuth."""
        sun = dir_from_az_zen(30.0, 40.0)
        sen = dir_from_az_zen(0.0, 20.0)
        a = compute_angles(sun, sen)
        assert math.degrees(a.theta_s_rad) == pytest.approx(40.0, abs=1e-9)
        assert math.degrees(a.theta_v_rad) == pytest.approx(20.0, abs=1e-9)
        assert math.degrees(a.delta_phi_rad) == pytest.approx(30.0, abs=1e-9)


class TestAnnotationFrameSplit:
    """CU-128: the catalog frame split matches the Phase-5 GeometryReadout grouping."""

    def test_annotation_frames(self) -> None:
        frames = {a.name: a.frame for a in angle_catalog.annotations()}
        assert frames["off_nadir"] == angle_catalog.FRAME_GROUND
        assert frames["sun_zenith"] == angle_catalog.FRAME_TARGET
        assert frames["relative_azimuth"] == angle_catalog.FRAME_TARGET
        assert frames["phase_angle"] == angle_catalog.FRAME_TARGET

    def test_stage_keys_grouped_like_the_readout(self) -> None:
        from radiant.gui.widgets import geometry_readout as gr

        target_keys: set[str] = set()
        ground_keys: set[str] = set()
        for title, keys in gr._GROUPS:  # noqa: SLF001 — reading the readout's own grouping
            if title == gr._TARGET_FRAME:
                target_keys = set(keys)
            elif title == gr._GROUND_FRAME:
                ground_keys = set(keys)
        for ann in angle_catalog.annotations():
            if ann.stage_key is None:
                continue
            if ann.frame == angle_catalog.FRAME_TARGET:
                assert ann.stage_key in target_keys
            else:
                assert ann.stage_key in ground_keys


class TestViewerRevealWiring:
    """CU-128/130: GeometryViewer forwards reveal/triad toggles to the canvas."""

    def test_reveal_and_triad_reach_the_canvas(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = offnadir_sphere
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.show_result(result, sensor)
        viewer.set_angle_revealed("relative_azimuth", True)
        assert viewer.canvas is not None
        assert viewer.canvas.revealed_angles == frozenset({"relative_azimuth"})
        viewer.set_triad_visible(True)
        assert viewer.canvas.triad_visible is True
        viewer.set_angle_revealed("relative_azimuth", False)
        assert viewer.canvas.revealed_angles == frozenset()


class TestAngleOverlay:
    """The angle-arc reveal selector is an on-canvas bottom-left overlay (2026-07-14 relayout)."""

    def test_overlay_is_a_child_of_the_canvas(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The interactive ANGLES selector is parented to the SchematicView canvas."""
        from radiant.gui.viewer.angle_overlay import AngleToggleOverlay

        canvas = SchematicView()
        qtbot.addWidget(canvas)
        overlay = canvas.angle_overlay
        assert isinstance(overlay, AngleToggleOverlay)
        assert overlay.parent() is canvas
        # One checkbox per annotatable angle, sourced from the single catalog.
        for ann in angle_catalog.annotations():
            assert overlay.angle_checkbox(ann.name) is not None

    def test_toggling_overlay_checkbox_reveals_the_arc(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """A checkbox on the overlay calls set_angle_revealed → the canvas reveals that arc."""
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = offnadir_sphere
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.show_result(result, sensor)
        assert viewer.canvas is not None
        overlay = viewer.canvas.angle_overlay
        overlay.angle_checkbox("relative_azimuth").setChecked(True)
        assert viewer.revealed_angles == frozenset({"relative_azimuth"})
        assert viewer.canvas.revealed_angles == frozenset({"relative_azimuth"})
        overlay.angle_checkbox("relative_azimuth").setChecked(False)
        assert viewer.canvas.revealed_angles == frozenset()

    def test_overlay_anchors_bottom_left_after_resize(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The overlay re-pins to the canvas bottom-left corner when the canvas resizes."""
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.show()  # resizeEvent only fires once the widget is realised
        canvas.resize(900, 700)
        overlay = canvas.angle_overlay
        geo = overlay.geometry()
        # Left-anchored (small inset) and its bottom clears the canvas bottom by the inset.
        assert geo.left() < canvas.width() / 2
        assert geo.bottom() < canvas.height()
        assert canvas.height() - geo.bottom() < 40  # near the bottom edge, not floating high
        # A second, different size keeps it bottom-left (repositioned, not stale).
        canvas.resize(600, 500)
        geo2 = overlay.geometry()
        assert geo2.left() < canvas.width() / 2
        assert canvas.height() - geo2.bottom() < 40


class TestDimensionPanel:
    """CU-131 + owner request: the side panel exposes ALL per-shape dimension inputs."""

    def _panel(self, qtbot):  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.geometry_angle_panel import GeometryAnglePanel

        panel = GeometryAnglePanel()
        qtbot.addWidget(panel)
        panel.set_shape_choices(("none", "sphere", "cylinder", "flat_plate", "box", "cone"))
        return panel

    def test_visible_dimensions_per_shape(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = self._panel(qtbot)
        cases = {
            "sphere": {"geometry.target.shape_radius_m"},
            "cylinder": {"geometry.target.shape_radius_m", "geometry.target.shape_length_m"},
            "flat_plate": {"geometry.target.shape_length_m", "geometry.target.shape_width_m"},
            "box": {
                "geometry.target.shape_length_m",
                "geometry.target.shape_width_m",
                "geometry.target.shape_height_m",
            },
            "cone": {"geometry.target.shape_base_radius_m", "geometry.target.shape_height_m"},
            "none": set(),
        }
        for shape, expected in cases.items():
            panel.set_shape(shape)
            assert set(panel.visible_dimensions()) == expected

    def test_dimension_edit_emits_edit_request(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Clicking a dimension value field emits one editRequested(dotpath) — the owner
        opens the shared editor dialog and performs the one sensor.set."""
        panel = self._panel(qtbot)
        panel.set_shape("sphere")
        captured: list[str] = []
        panel.editRequested.connect(captured.append)
        panel.dimension_row("geometry.target.shape_radius_m").value_button.click()
        assert captured == ["geometry.target.shape_radius_m"]

    def test_rpy_edit_emits_edit_request(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Clicking an RPY value field emits one editRequested(dotpath) — same edit path."""
        panel = self._panel(qtbot)
        captured: list[str] = []
        panel.editRequested.connect(captured.append)
        panel.rpy_row("geometry.target.shape_yaw_rad").value_button.click()
        assert captured == ["geometry.target.shape_yaw_rad"]

    def test_fields_and_combo_match_the_geometry_form_by_construction(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The target dim/RPY fields + shape combo reuse the SAME widget types + QSS object
        names as GeometryModeForm's fields, so the two pages cannot visually diverge again
        (owner feedback 2026-07-14). A regression to bespoke widgets fails here."""
        from radiant.gui.widgets.field_row import FieldRow
        from radiant.gui.widgets.geometry_mode_form import GeometryModeForm, _FieldRow

        # The shared FieldRow IS the geometry form's field row (one building block).
        assert _FieldRow is FieldRow

        panel = self._panel(qtbot)
        panel.set_shape("cylinder")
        # Every dim + RPY field is the shared FieldRow with the geometry field object names.
        rows = [
            panel.dimension_row("geometry.target.shape_radius_m"),
            panel.dimension_row("geometry.target.shape_length_m"),
            panel.rpy_row("geometry.target.shape_yaw_rad"),
        ]
        for row in rows:
            assert isinstance(row, FieldRow)
            assert row.objectName() == "geoModeFieldRow"
            assert row.value_button.objectName() == "geoModeFieldValue"
        # The shape combo carries the geometry mode-selector object name (styled combo).
        form = GeometryModeForm()
        qtbot.addWidget(form)
        assert panel.shape_combo.objectName() == form.selector("solar").objectName()
        assert panel.shape_combo.objectName() == "geoModeSelector"


class TestGeometryInputsFitColumn:
    """Owner bug 2026-07-14: the Schematic-tab Geometry inputs must fit their column.

    The right-column accordion form was wider than its column (long mode-selector combos + a
    long single-line title + full-width dot-path labels), so the QToolBox page showed a
    horizontal scrollbar and clipped the value fields. The form's field editors + combos must
    now size to the available column width, so the inputs page never scrolls horizontally.
    """

    def _mounted_window(self, qtbot, width: int):  # type: ignore[no-untyped-def]
        """A bounded window with the Geometry StagePane on its Schematic tab, evaluated.

        Returns the window (kept alive by the caller) so its child pane is not GC-collected.
        """
        from PySide6.QtWidgets import QMainWindow, QTabWidget

        from radiant.gui.stage_views import STAGE_COMPOSITIONS
        from radiant.gui.widgets.stage_center import StagePane

        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        win = QMainWindow()
        qtbot.addWidget(win)
        win.setCentralWidget(pane)
        win.resize(width, 820)
        win.show()
        pane.findChild(QTabWidget).setCurrentIndex(1)  # Schematic
        sensor = Sensor.from_yaml(_EXAMPLE)
        pane.bind_sensor(sensor, {})
        pane.populate(_evaluate(sensor))
        for _ in range(4):
            qtbot.wait(1)
        return win

    def _inputs_scrollarea(self, panel):  # type: ignore[no-untyped-def]
        """The QToolBox inner scroll area that hosts the Geometry inputs form (its ancestor)."""
        from PySide6.QtWidgets import QScrollArea

        form = panel.geometry_form
        for area in panel.findChildren(QScrollArea):
            if area.isAncestorOf(form):
                return area
        raise AssertionError("no scroll area hosts the geometry inputs form")

    def test_inputs_form_fits_column_no_horizontal_scrollbar(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """At a realistic column width the inputs page has no horizontal scrollbar."""
        win = self._mounted_window(qtbot, 1440)
        panel = win.centralWidget().geometry_panel
        assert panel is not None
        area = self._inputs_scrollarea(panel)
        # No horizontal overflow: the scrolled content is not wider than the viewport.
        assert area.horizontalScrollBar().maximum() == 0
        # The form's minimum width fits inside the viewport it is shown in.
        assert panel.geometry_form.minimumSizeHint().width() <= area.viewport().width()

    def test_no_value_field_clipped(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Every value button's right edge stays within the form (no clipped value)."""
        from PySide6.QtWidgets import QPushButton

        win = self._mounted_window(qtbot, 1440)
        form = win.centralWidget().geometry_panel.geometry_form  # type: ignore[union-attr]
        for btn in form.findChildren(QPushButton):
            if btn.objectName() == "geoModeFieldValue" and btn.isVisible():
                right = btn.mapTo(form, btn.rect().topRight()).x()
                assert right <= form.width() + 1

    def test_fits_when_column_dragged_narrow(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Even a narrow column keeps the inputs page free of a horizontal scrollbar."""
        win = self._mounted_window(qtbot, 1440)
        panel = win.centralWidget().geometry_panel
        assert panel is not None
        panel.setMinimumWidth(240)
        panel.resize(240, panel.height())
        for _ in range(4):
            qtbot.wait(1)
        assert self._inputs_scrollarea(panel).horizontalScrollBar().maximum() == 0


class TestElevatedTargetGroundVectors:
    """Owner request 2026-07-14: an elevated target (altitude > 0) also shows ground vectors.

    A SENSOR→GROUND and a SUN→GROUND vector, both landing at the target's ground projection
    (nadir footprint), plus matching conditional legend rows. A ground target (altitude 0) has
    target == ground, so the vectors are degenerate and absent (unchanged behaviour).
    """

    def _state(self, **overrides: object) -> ViewerState:
        base = ViewerState.default()
        return ViewerState(**{**base.__dict__, **overrides})

    def test_elevated_target_builds_both_ground_vectors(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        scene = build_scene(self._state(target_altitude_m=5_000.0))
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        vectors = canvas._ground_vectors(scene)  # noqa: SLF001 — exercises the build path
        labels = [label for label, *_ in vectors]
        assert labels == ["SENSOR → GROUND", "SUN → GROUND"]
        # SENSOR→GROUND starts at the sensor; SUN→GROUND starts at the sun; both end at ground.
        by_label = {label: (start, end) for label, start, end, _color in vectors}
        assert np.allclose(by_label["SENSOR → GROUND"][0], scene.sensor_pos)
        assert np.allclose(by_label["SUN → GROUND"][0], scene.sun_pos)
        for _label, (_start, end) in by_label.items():
            assert np.allclose(end, scene.ground_point)

    def test_intersection_is_target_ground_projection(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The ground intersection is the target's nadir projection (directly below it)."""
        scene = build_scene(self._state(target_altitude_m=5_000.0))
        # Nadir footprint: same x, y as the body, on the ground plane z = 0.
        assert scene.ground_point[2] == pytest.approx(0.0, abs=1e-12)
        assert np.allclose(scene.ground_point, [scene.target_top[0], scene.target_top[1], 0.0])

    def test_ground_target_has_no_ground_vectors(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        scene = build_scene(self._state(target_altitude_m=0.0))
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        assert not scene.airborne
        assert canvas._ground_vectors(scene) == []  # noqa: SLF001

    def test_legend_shows_ground_rows_only_when_elevated(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        elevated = [
            row[0]
            for row in canvas._legend_entries(build_scene(self._state(target_altitude_m=5_000.0)))
        ]  # noqa: SLF001, E501
        grounded = [
            row[0]
            for row in canvas._legend_entries(build_scene(self._state(target_altitude_m=0.0)))
        ]  # noqa: SLF001, E501
        assert "SENSOR → GROUND" in elevated and "SUN → GROUND" in elevated
        assert "SENSOR → GROUND" not in grounded and "SUN → GROUND" not in grounded

    def test_ground_vectors_use_allowlisted_palette(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The ground variants reuse the physics palette (sensor = blue, sun = amber)."""
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        scene = build_scene(self._state(target_altitude_m=5_000.0))
        vectors = {label: color for label, _s, _e, color in canvas._ground_vectors(scene)}  # noqa: SLF001
        assert vectors["SENSOR → GROUND"] == palette.SATELLITE_FAMILY
        assert vectors["SUN → GROUND"] == palette.SOLAR_FAMILY

    def test_elevated_render_paints_both_ground_colours(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The full render of an elevated target paints the sensor-blue + sun-amber vectors."""
        canvas = SchematicView(theme=LIGHT)
        qtbot.addWidget(canvas)
        canvas.resize(900, 600)
        canvas.set_state(self._state(target_shape="sphere", target_altitude_m=5_000.0))
        img = canvas.grab().toImage()
        assert _has_color(img, palette.SATELLITE_FAMILY)
        assert _has_color(img, palette.SOLAR_FAMILY)


class TestDownLookingRegression:
    """ADR-0011 Phase 4, hard constraint: the DOWN-looking layout is bit-for-bit unchanged.

    The generalized compositions may only *add* branches. These values were captured from
    the pre-change ``build_scene`` for :meth:`ViewerState.default` and are pinned here, so
    any drift in the original layout — a moved glyph, a re-anchored sun, a changed target
    lift — fails immediately rather than silently restyling every existing scene.
    """

    def test_default_state_scene_fields_are_pinned(self) -> None:
        scene = build_scene(ViewerState.default())
        assert scene.los_direction == "down"
        assert np.allclose(
            scene.sun_dir, [0.11925324669497092, 0.561042415054222, 0.8191520442889918], atol=1e-15
        )
        assert np.allclose(
            scene.sensor_dir, [0.0, 0.3420201433256687, 0.9396926207859084], atol=1e-15
        )
        assert np.allclose(
            scene.sun_pos, [0.5366396101273692, 2.524690867743999, 3.686184199300463], atol=1e-15
        )
        assert np.allclose(
            scene.sensor_pos, [0.0, 1.1970705016398404, 3.2889241727506793], atol=1e-15
        )
        assert np.allclose(scene.target_top, [0.0, 0.0, 2.0], atol=1e-15)
        assert scene.target_z == pytest.approx(0.0, abs=1e-15)
        assert np.allclose(scene.target_center, [0.0, 0.0, 1.0], atol=1e-15)
        assert np.allclose(scene.ground_point, [0.0, 0.0, 0.0], atol=1e-15)
        assert scene.airborne is False
        assert scene.is_point is False
        assert len(scene.target_edges) == 120
        assert scene.altitude_km == pytest.approx(8.0, abs=1e-12)
        assert scene.target_altitude_km == pytest.approx(0.0, abs=1e-12)
        assert scene.has_sun is True
        # The new annotations are inert for the unchanged layout.
        assert scene.show_target_altitude is False
        assert scene.level_sag_label is None

    def test_eta_ray_is_the_sensor_placement_ray_when_down_looking(self) -> None:
        """The off-nadir arc still rides the SENSOR→TARGET vector (no visual change)."""
        scene = build_scene(ViewerState.default())
        assert np.allclose(scene.eta_dir, scene.sensor_dir, atol=1e-15)

    def test_airborne_target_layout_unchanged(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A down-looking elevated target keeps its lift, ground vectors, and h_t pill."""
        base = ViewerState.default()
        scene = build_scene(ViewerState(**{**base.__dict__, "target_altitude_m": 5_000.0}))
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        assert scene.airborne is True
        assert scene.show_target_altitude is True
        assert scene.target_z == pytest.approx(0.9, abs=1e-12)
        labels = [label for label, *_rest in canvas._ground_vectors(scene)]  # noqa: SLF001
        assert labels == ["SENSOR → GROUND", "SUN → GROUND"]

    def test_missing_stage_keys_fall_back_to_down(self) -> None:
        """A state built without the ADR-0011 fields composes the original layout."""
        base = ViewerState.default()
        legacy = ViewerState(
            **{
                k: v
                for k, v in base.__dict__.items()
                if k
                not in (
                    "theta_o_rad",
                    "los_direction",
                    "scene_class",
                    "observer_class",
                    "target_class",
                )
            }
        )
        assert legacy.los_direction == "down"
        scene = build_scene(legacy)
        assert np.allclose(scene.sensor_pos, build_scene(base).sensor_pos, atol=1e-15)


class TestUpLookingComposition:
    """Up-looking scenes (ground→air, ground→space, air→space, space→space up).

    The SENSOR is the path's lower endpoint, so it anchors the layout and the target is
    carried above it: the SENSOR→TARGET vector ascends. Where the ground plane sits is the
    scene class's job — at the sensor for a ground observer, below both endpoints for an
    airborne or space one.
    """

    def test_sensor_sits_on_the_ground_plane_for_a_ground_observer(self) -> None:
        state, _geo = _case_state_and_geometry("ground_to_air_up")
        scene = build_scene(state)
        assert scene.sensor_pos[2] == pytest.approx(_GROUND_ENDPOINT_Z, abs=1e-12)

    def test_sensor_is_lifted_for_an_elevated_observer(self) -> None:
        """A space observer looking up gets the both-elevated cue, not a buried glyph."""
        state, _geo = _case_state_and_geometry("space_to_space_up")
        scene = build_scene(state)
        assert scene.sensor_pos[2] == pytest.approx(_ELEVATED_ENDPOINT_Z, abs=1e-12)
        assert scene.sensor_pos[2] > _GROUND_ENDPOINT_Z

    @pytest.mark.parametrize(
        "case", ["ground_to_air_up", "ground_to_space_up", "space_to_space_up"]
    )
    def test_los_ascends_sensor_below_target(self, case: str) -> None:
        state, _geo = _case_state_and_geometry(case)
        scene = build_scene(state)
        assert scene.sensor_pos[2] < scene.target_z
        assert scene.sensor_pos[2] < scene.target_top[2]
        # The drawn SENSOR→TARGET vector has a positive vertical component (ascending).
        assert (scene.target_top - scene.sensor_pos)[2] > 0.0

    def test_glyph_distance_is_still_the_fixed_abstract_radius(self) -> None:
        """Not-to-scale: the sensor sits _SENSOR_DIST from the target however far it is."""
        near, _geo = _case_state_and_geometry("ground_to_air_up")  # 12 km
        far, _geo2 = _case_state_and_geometry("ground_to_space_up")  # 400 km
        for state in (near, far):
            scene = build_scene(state)
            anchor = np.array([0.0, 0.0, scene.target_z])
            assert float(np.linalg.norm(scene.sensor_pos - anchor)) == pytest.approx(
                _SENSOR_DIST, abs=1e-9
            )

    def test_display_geometry_ignores_metric_altitude(self) -> None:
        """A 33x altitude change at fixed θ_o must not move a single glyph."""
        state, _geo = _case_state_and_geometry("ground_to_air_up")
        taller = ViewerState(**{**state.__dict__, "target_altitude_m": 400_000.0})
        a, b = build_scene(state), build_scene(taller)
        assert np.allclose(a.sensor_pos, b.sensor_pos)
        assert a.target_z == pytest.approx(b.target_z, abs=1e-12)

    def test_both_altitude_pills_present_with_units(self) -> None:
        state, _geo = _case_state_and_geometry("ground_to_space_up")
        scene = build_scene(state)
        assert scene.show_target_altitude is True
        assert _format_km(scene.altitude_km) == "0 m"
        assert _format_km(scene.target_altitude_km) == "400 km"

    def test_ground_vectors_and_legend_rows_are_omitted(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Looking up, the LOS never terminates on the ground — no ground-frame pair."""
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        state, _geo = _case_state_and_geometry("ground_to_space_up")
        scene = build_scene(state)
        assert scene.airborne is True  # the target IS above MSL …
        assert canvas._ground_vectors(scene) == []  # noqa: SLF001 — … but no ground pair
        labels = [row[0] for row in canvas._legend_entries(scene)]  # noqa: SLF001
        assert "SENSOR → GROUND" not in labels and "SUN → GROUND" not in labels
        assert "SENSOR → TARGET" in labels and "ZENITH" in labels

    def test_night_up_looking_scene_renders_without_sun(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView(theme=LIGHT)
        qtbot.addWidget(canvas)
        canvas.resize(900, 600)
        state, _geo = _case_state_and_geometry("ground_to_space_up", has_sun=False)
        canvas.set_state(state)
        img = canvas.grab().toImage()
        assert img.width() == 900 and img.height() == 600
        assert not _has_color(img, palette.SOLAR_FAMILY)
        assert _has_color(img, palette.SATELLITE_FAMILY)

    def test_canvas_renders_and_is_framed(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView(theme=LIGHT)
        qtbot.addWidget(canvas)
        state, _geo = _case_state_and_geometry("ground_to_air_up")
        canvas.set_state(state)
        canvas.resize(820, 640)
        bounds = canvas.projected_content_bounds()
        assert bounds is not None
        min_x, min_y, max_x, max_y = bounds
        assert (min_x + max_x) / 2.0 == pytest.approx(820 / 2, abs=2.0)
        assert (min_y + max_y) / 2.0 == pytest.approx(640 / 2, abs=2.0)


class TestLevelComposition:
    """Level arms: both endpoints lifted to one abstract height, LOS drawn horizontal."""

    def test_both_endpoints_share_the_elevated_height(self) -> None:
        state, _geo = _case_state_and_geometry("air_to_air_level")
        scene = build_scene(state)
        assert scene.sensor_pos[2] == pytest.approx(_ELEVATED_ENDPOINT_Z, abs=1e-12)
        # The target rides the true θ_o ray, so it clears the sensor by the arm's own
        # (sub-degree) tilt — the horizon guard admits at most ±2° off horizontal.
        drop = _SENSOR_DIST * math.sin(math.radians(2.0))
        assert scene.target_z == pytest.approx(_ELEVATED_ENDPOINT_Z, abs=drop)
        assert scene.target_z > scene.sensor_pos[2]

    def test_los_is_horizontal_within_the_guard_band(self) -> None:
        state, _geo = _case_state_and_geometry("air_to_air_level")
        scene = build_scene(state)
        # Measure the LOS between the two endpoint anchors (the target's body height is not
        # part of the path).
        los = np.array([0.0, 0.0, scene.target_z]) - scene.sensor_pos
        elevation_deg = math.degrees(math.asin(los[2] / float(np.linalg.norm(los))))
        assert abs(elevation_deg) < 2.0

    def test_sag_pill_carries_the_core_tangent_depression_with_units(self) -> None:
        """Δh comes from the CORE horizon-guard classifier, not a restated formula."""
        from radiant.core.viewing_triangle import classify_horizon_topology

        state, _geo = _case_state_and_geometry("air_to_air_level")
        scene = build_scene(state)
        expected = classify_horizon_topology(state.theta_o_rad, 5_000.0, 5_000.0).dh_m
        assert expected is not None
        assert scene.level_sag_label == f"Δh  {_format_km(expected / 1000.0)}"
        assert scene.level_sag_label.endswith(" m")

    def test_sag_matches_the_versine_identity(self) -> None:
        """Δh = (R_E + h)(1 − sin ζ_low) — an independent check of the value shown."""
        from radiant.core.constants import R_EARTH_M

        theta_o = math.radians(90.5)
        expected_m = (R_EARTH_M + 5_000.0) * (1.0 - math.sin(theta_o))
        label = _level_sag_label(theta_o, 5_000.0, "level")
        assert label == f"Δh  {_format_km(expected_m / 1000.0)}"

    @pytest.mark.parametrize("case", ["space_to_ground_down", "ground_to_space_up"])
    def test_sag_pill_hidden_for_non_level_scenes(self, case: str) -> None:
        state, _geo = _case_state_and_geometry(case)
        assert build_scene(state).level_sag_label is None

    def test_sag_undefined_below_the_level_domain(self) -> None:
        """A "level" state with θ_o < π/2 is not a level arm — no fabricated sag."""
        assert _level_sag_label(math.radians(80.0), 5_000.0, "level") is None

    def test_both_pills_show_for_a_level_arm(self) -> None:
        state, _geo = _case_state_and_geometry("air_to_air_level")
        scene = build_scene(state)
        assert scene.show_target_altitude is True
        assert _format_km(scene.altitude_km) == "5.0 km"
        assert _format_km(scene.target_altitude_km) == "5.0 km"

    def test_ground_vectors_omitted(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        state, _geo = _case_state_and_geometry("air_to_air_level")
        assert canvas._ground_vectors(build_scene(state)) == []  # noqa: SLF001

    def test_level_canvas_renders(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView(theme=LIGHT)
        qtbot.addWidget(canvas)
        canvas.resize(880, 600)
        state, _geo = _case_state_and_geometry("air_to_air_level")
        canvas.set_state(state)
        img = canvas.grab().toImage()
        assert img.width() == 880 and img.height() == 600
        assert _has_color(img, palette.SATELLITE_FAMILY)


class TestGeneralizedAnnotations:
    """The two ADR-0011 arcs (θ_o, ζ_low) — catalog, toggles, arcs, and pinned values."""

    def test_catalog_carries_both_new_annotations(self) -> None:
        names = {a.name for a in angle_catalog.annotations()}
        assert {"path_zenith", "lower_zenith"} <= names
        assert angle_catalog.annotation("path_zenith").symbol == "θ_o"
        assert angle_catalog.annotation("lower_zenith").symbol == "ζ_low"
        assert angle_catalog.annotation("path_zenith").stage_key == "theta_o_rad"

    def test_overlay_gains_a_toggle_for_each(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        for name in ("path_zenith", "lower_zenith"):
            assert canvas.angle_overlay.angle_checkbox(name) is not None

    @pytest.mark.parametrize("case", sorted(_SCENE_CASES))
    def test_new_arcs_are_drawable_in_every_scene_class(self, qtbot, case: str) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        state, _geo = _case_state_and_geometry(case)
        canvas.set_state(state)
        scene = build_scene(state)
        for name in ("path_zenith", "lower_zenith"):
            assert canvas._arc_points(scene, name), f"{case}: {name} drew nothing"  # noqa: SLF001

    def test_obtuse_path_zenith_arc_renders(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """θ_o > π/2 (up-looking): the arc must sweep the obtuse angle, not fold back."""
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        state, geo = _case_state_and_geometry("ground_to_space_up")
        canvas.set_state(state)
        scene = build_scene(state)
        subtended = _arc_subtended_rad(canvas, scene, "path_zenith")
        assert subtended > math.pi / 2.0
        assert subtended == pytest.approx(float(geo["theta_o_rad"]), abs=1e-9)

    def test_lower_zenith_arc_moves_to_the_sensor_when_looking_up(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        up_state, _g = _case_state_and_geometry("ground_to_space_up")
        up_scene = build_scene(up_state)
        assert np.allclose(canvas._arc_apex(up_scene, "lower_zenith"), up_scene.sensor_pos)  # noqa: SLF001
        down_state, _g2 = _case_state_and_geometry("space_to_ground_down")
        down_scene = build_scene(down_state)
        assert np.allclose(canvas._arc_apex(down_scene, "lower_zenith"), down_scene.target_top)  # noqa: SLF001

    def test_arc_labels_pin_the_stage_value_in_degrees(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        state, geo = _case_state_and_geometry("ground_to_space_up")
        canvas.set_state(state)
        theta_text = canvas._arc_label_text(angle_catalog.annotation("path_zenith"))  # noqa: SLF001
        zeta_text = canvas._arc_label_text(angle_catalog.annotation("lower_zenith"))  # noqa: SLF001
        assert theta_text == f"θ_o {math.degrees(float(geo['theta_o_rad'])):.1f}°"
        expected_zeta = math.degrees(angle_truth.stage_angle_rad(geo, "lower_zenith"))
        assert zeta_text == f"ζ_low {expected_zeta:.1f}°"
        # ζ_low is NOT π − θ_o on a curved Earth — the two differ by the central angle.
        assert expected_zeta == pytest.approx(32.0996, abs=1e-3)
        assert abs(expected_zeta - (180.0 - 150.0)) > 2.0

    def test_revealing_a_new_arc_changes_the_render(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView(theme=LIGHT)
        qtbot.addWidget(canvas)
        canvas.resize(860, 620)
        state, _geo = _case_state_and_geometry("ground_to_air_up")
        canvas.set_state(state)
        before = canvas.grab().toImage()
        canvas.set_revealed_angles({"path_zenith", "lower_zenith"})
        after = canvas.grab().toImage()
        assert canvas.revealed_angles == frozenset({"path_zenith", "lower_zenith"})
        assert before != after


class TestSceneClassAngleTruth:
    """CU-133 extended (§6.3): every scene class the viewer composes tracks stage truth.

    Both halves are asserted: the viewer-local recomputation of each stage-backed angle, and
    — for the zenith arcs — the angle the DRAWN arc actually subtends about its apex.
    """

    @pytest.mark.parametrize("case", sorted(_SCENE_CASES))
    def test_recomputation_matches_stage(self, case: str) -> None:
        state, geo = _case_state_and_geometry(case)
        tol = angle_truth.ANGLE_CONSISTENCY_ABS_TOL_RAD
        for name in angle_truth.ANGLE_TRUTH_KEYS:
            recomputed = angle_truth.recompute_angle_rad(state, name)
            expected = angle_truth.stage_angle_rad(geo, name)
            assert abs(recomputed - expected) <= tol, (
                f"{case}/{name}: viewer {recomputed} vs stage {expected}"
            )

    @pytest.mark.parametrize("case", sorted(_SCENE_CASES))
    def test_drawn_arcs_subtend_the_stage_angle(self, qtbot, case: str) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        state, geo = _case_state_and_geometry(case)
        canvas.set_state(state)
        scene = build_scene(state)
        tol = angle_truth.ANGLE_CONSISTENCY_ABS_TOL_RAD
        for name in ("off_nadir", "sun_zenith", "path_zenith", "lower_zenith"):
            drawn = _arc_subtended_rad(canvas, scene, name)
            expected = angle_truth.stage_angle_rad(geo, name)
            assert abs(drawn - expected) <= tol, f"{case}/{name}: drawn {drawn} vs {expected}"

    def test_lower_zenith_transform_matches_the_core_triangle(self) -> None:
        """ζ_low = π − η (up) reproduces the core lower-endpoint solution's θ_o = π − ζ_up."""
        from radiant.core.viewing_triangle import solve_from_lower_zenith

        _state, geo = _case_state_and_geometry("ground_to_space_up")
        zeta_low = angle_truth.stage_angle_rad(geo, "lower_zenith")
        solved = solve_from_lower_zenith(
            zeta_low_rad=zeta_low,
            h_low_m=float(geo["h_sensor_m"]),
            h_high_m=float(geo["h_target_m"]),
        )
        assert solved.theta_o_rad == pytest.approx(float(geo["theta_o_rad"]), abs=1e-9)

    def test_level_arm_lower_zenith_equals_path_zenith(self) -> None:
        _state, geo = _case_state_and_geometry("air_to_air_level")
        assert angle_truth.stage_angle_rad(geo, "lower_zenith") == pytest.approx(
            float(geo["theta_o_rad"]), abs=1e-12
        )
