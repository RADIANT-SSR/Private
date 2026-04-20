"""Tests for SourceStage wrapper (Stage 4 Option C).

Covers:
- Descriptor publication (TargetDescriptor / BackgroundDescriptor /
  LineOfSightGeometry)
- Tentative regime classification (IFOV-based)
- Fill-fraction and regime override
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.regime import RadiometricRegime
from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS

# Minimal optics/detector params needed for IFOV calculation.
from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS
from radiant.source._schema import ALL_PARAMETERS as SRC_PARAMS
from radiant.source.stage import SourceStage, _classify_regime


def _make_params(
    T: float = 300.0,
    eps: float = 0.95,
    area_m2: float = 0.0,
    range_m: float = 0.0,
    fill_fraction: float = 1.0,
    regime_override: str = "auto",
    bg_T: float = 290.0,
    bg_eps: float = 0.95,
    pixel_pitch_um: float = 18.0,
    focal_length_m: float = 1.2,
) -> ParameterSet:
    from radiant.api._param_registry import _FNUMBER_GROUP

    schema = list(SRC_PARAMS) + list(OPT_PARAMS) + list(DET_PARAMS)
    ps = ParameterSet(schema, [_FNUMBER_GROUP])
    ps.set("source.target.temperature", T)
    ps.set("source.target.emissivity", eps)
    ps.set("source.target.projected_area_m2", area_m2)
    ps.set("source.target.range_m", range_m)
    ps.set("source.target.fill_fraction", fill_fraction)
    ps.set("source.regime_override", regime_override)
    ps.set("source.background.temperature", bg_T)
    ps.set("source.background.emissivity", bg_eps)
    ps.set("detector.pixel_pitch_x_um", pixel_pitch_um)
    ps.set("detector.pixel_pitch_y_um", pixel_pitch_um)
    ps.set("detector.qe_value", 0.7)
    ps.set("optics.focal_length_m", focal_length_m)
    ps.set("optics.aperture_diameter_m", 0.3)
    ps.set("optics.transmission_scalar", 0.7)
    ps.resolve()
    return ps


class TestSourceStage:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.0, 5.0, 100)

    def test_no_at_target_frame_in_stage_4(self, wl: np.ndarray) -> None:
        """Stage 4 removes the at_target radiance frame entirely."""
        import warnings as _w

        state = ChainState(wavelength_um=wl)
        with _w.catch_warnings():
            _w.simplefilter("ignore", UserWarning)
            out = SourceStage().run(state, _make_params())
        assert "at_target" not in out.frames

    def test_publishes_target_descriptor(self, wl: np.ndarray) -> None:
        import warnings as _w

        from radiant.core.descriptors import TargetDescriptor

        state = ChainState(wavelength_um=wl)
        with _w.catch_warnings():
            _w.simplefilter("ignore", UserWarning)
            out = SourceStage().run(state, _make_params(T=300.0))
        target = out.stage_outputs["source"]["target"]
        assert isinstance(target, TargetDescriptor)

    def test_default_regime_extended(self, wl: np.ndarray) -> None:
        """No area/range → defaults to EXTENDED."""
        import warnings as _w

        state = ChainState(wavelength_um=wl)
        with _w.catch_warnings():
            _w.simplefilter("ignore", UserWarning)
            out = SourceStage().run(state, _make_params())
        assert out.stage_outputs["source"]["regime_tentative"] == RadiometricRegime.EXTENDED

    def test_name(self) -> None:
        assert SourceStage().name == "source"

    def test_no_L_background_stage_output_in_stage_4(self, wl: np.ndarray) -> None:
        """Stage 4 removes the L_background stage_output entirely."""
        import warnings as _w

        state = ChainState(wavelength_um=wl)
        with _w.catch_warnings():
            _w.simplefilter("ignore", UserWarning)
            out = SourceStage().run(state, _make_params())
        assert "L_background" not in out.stage_outputs["source"]

    def test_fill_fraction_stored(self, wl: np.ndarray) -> None:
        import warnings as _w

        state = ChainState(wavelength_um=wl)
        # Stage-2 inferrer warns on terrestrial sub-pixel GroundBackground
        # placeholder — expected for this fill_fraction=0.3 fixture; we
        # only care that the fill_fraction value round-trips.
        with _w.catch_warnings():
            _w.simplefilter("ignore", UserWarning)
            out = SourceStage().run(state, _make_params(fill_fraction=0.3))
        assert out.stage_outputs["source"]["fill_fraction"] == 0.3

    def test_angular_extent_stored(self, wl: np.ndarray) -> None:
        """When area and range are provided, angular_extent is computed."""
        area, R = 1.0, 10000.0
        state = ChainState(wavelength_um=wl)
        out = SourceStage().run(state, _make_params(area_m2=area, range_m=R))
        expected = math.sqrt(area) / R
        assert out.stage_outputs["source"]["angular_extent_rad"] == pytest.approx(
            expected, rel=1e-10
        )

    # ------------------------------------------------------------------
    # Option C descriptors (Stage 2 additive bridge, ADR-0002)
    # ------------------------------------------------------------------

    def test_descriptors_published(self, wl: np.ndarray) -> None:
        """SourceStage publishes target/background/los_geometry keys.

        Stage 4 Option C: SourceStage publishes descriptors only — the
        legacy ``at_target`` frame and ``L_background`` stage_output have
        been removed.  AtmosphereStage owns the ε·B(T_t) assembly.
        """
        import warnings as _w

        from radiant.core.descriptors import GroundBackground, T1Thermal
        from radiant.core.los_geometry import LineOfSightGeometry

        state = ChainState(wavelength_um=wl)
        with _w.catch_warnings():
            _w.simplefilter("ignore", UserWarning)
            out = SourceStage().run(state, _make_params())
        src = out.stage_outputs["source"]

        # New descriptor keys present.
        assert "target" in src
        assert "background" in src
        assert "los_geometry" in src

        # The inferrer synthesises a T1Thermal from the scalar ε+T legacy
        # surface.
        assert isinstance(src["target"], T1Thermal)
        # Default fixture is fill_fraction=1 ⇒ extended terrestrial
        # (no atmosphere.model in this partial-schema fixture → falls
        # back to terrestrial), so background should be None (Decision #13:
        # extended terrestrial skips the background term).
        assert src["background"] is None or isinstance(src["background"], GroundBackground)
        # LOS is populated for every non-at_aperture scenario.
        assert isinstance(src["los_geometry"], LineOfSightGeometry)

        # Stage 4: SourceStage does not publish at_target frame or
        # L_background stage_output.
        assert "at_target" not in out.frames
        assert "L_background" not in src

    def test_descriptor_target_carries_expected_values(self, wl: np.ndarray) -> None:
        """T1Thermal descriptor carries the scalar ε, T from the param surface."""
        from radiant.core.descriptors import T1Thermal

        state = ChainState(wavelength_um=wl)
        out = SourceStage().run(state, _make_params(T=350.0, eps=0.8))
        target = out.stage_outputs["source"]["target"]
        assert isinstance(target, T1Thermal)
        assert target.T_t == pytest.approx(350.0, rel=1e-12)
        # Grey emissivity: all samples equal.
        assert target.epsilon is not None
        assert np.allclose(target.epsilon.values, 0.8)

    def test_descriptor_sub_pixel_builds_ground_background(self, wl: np.ndarray) -> None:
        """fill_fraction < 1 → scene_type='sub_pixel' → GroundBackground placeholder."""
        import warnings as _w

        from radiant.core.descriptors import GroundBackground

        state = ChainState(wavelength_um=wl)
        with _w.catch_warnings():
            _w.simplefilter("ignore", UserWarning)
            out = SourceStage().run(state, _make_params(fill_fraction=0.3))
        bg = out.stage_outputs["source"]["background"]
        assert isinstance(bg, GroundBackground)
        target = out.stage_outputs["source"]["target"]
        assert target.scene_type == "sub_pixel"


# ======================================================================
# _classify_regime unit tests
# ======================================================================


class TestClassifyRegime:
    """Tests for the tentative regime classification function."""

    # IFOV = pixel_pitch / focal_length = 18e-6 / 1.2 = 1.5e-5 rad
    PIXEL_PITCH_M: float = 18e-6
    FOCAL_LENGTH_M: float = 1.2
    IFOV: float = 18e-6 / 1.2  # 1.5e-5 rad

    def test_no_geometry_is_extended(self) -> None:
        regime, ang = _classify_regime(
            projected_area_m2=None,
            range_m=None,
            fill_fraction=1.0,
            pixel_pitch_m=self.PIXEL_PITCH_M,
            focal_length_m=self.FOCAL_LENGTH_M,
            regime_override="auto",
        )
        assert regime == RadiometricRegime.EXTENDED
        assert ang == float("inf")

    def test_large_target_is_extended(self) -> None:
        """angular_extent >> 2 × IFOV → EXTENDED."""
        # angular_extent = sqrt(100) / 1000 = 0.01 rad >> 2 * 1.5e-5
        regime, ang = _classify_regime(
            projected_area_m2=100.0,
            range_m=1000.0,
            fill_fraction=1.0,
            pixel_pitch_m=self.PIXEL_PITCH_M,
            focal_length_m=self.FOCAL_LENGTH_M,
            regime_override="auto",
        )
        assert regime == RadiometricRegime.EXTENDED
        assert ang == pytest.approx(0.01, rel=1e-10)

    def test_tiny_target_is_point_source(self) -> None:
        """angular_extent << 0.25 × IFOV → POINT_SOURCE."""
        # Need angular_extent <= 0.25 * 1.5e-5 = 3.75e-6 rad
        # sqrt(A)/R = 3e-6 → A = (3e-6 * 1e6)^2 = 9 m², R = 1e6 m
        regime, ang = _classify_regime(
            projected_area_m2=9.0,
            range_m=1e6,
            fill_fraction=1.0,
            pixel_pitch_m=self.PIXEL_PITCH_M,
            focal_length_m=self.FOCAL_LENGTH_M,
            regime_override="auto",
        )
        assert regime == RadiometricRegime.POINT_SOURCE
        assert ang == pytest.approx(3e-6, rel=1e-10)

    def test_intermediate_target_is_subpixel(self) -> None:
        """0.25 × IFOV < angular_extent < 2 × IFOV → SUB_PIXEL."""
        # IFOV = 1.5e-5, need 3.75e-6 < ang < 3e-5
        # Use ang = 1e-5 → sqrt(A)/R = 1e-5 → A=1.0, R=1e5
        regime, ang = _classify_regime(
            projected_area_m2=1.0,
            range_m=1e5,
            fill_fraction=1.0,
            pixel_pitch_m=self.PIXEL_PITCH_M,
            focal_length_m=self.FOCAL_LENGTH_M,
            regime_override="auto",
        )
        assert regime == RadiometricRegime.SUB_PIXEL
        assert ang == pytest.approx(1e-5, rel=1e-10)

    def test_fill_fraction_forces_subpixel(self) -> None:
        """fill_fraction < 1.0 overrides IFOV-based classification."""
        regime, _ = _classify_regime(
            projected_area_m2=100.0,  # would be extended
            range_m=1000.0,
            fill_fraction=0.5,
            pixel_pitch_m=self.PIXEL_PITCH_M,
            focal_length_m=self.FOCAL_LENGTH_M,
            regime_override="auto",
        )
        assert regime == RadiometricRegime.SUB_PIXEL

    def test_regime_override_forces(self) -> None:
        """Explicit regime_override bypasses all classification."""
        regime, _ = _classify_regime(
            projected_area_m2=100.0,  # would be extended
            range_m=1000.0,
            fill_fraction=1.0,
            pixel_pitch_m=self.PIXEL_PITCH_M,
            focal_length_m=self.FOCAL_LENGTH_M,
            regime_override="point_source",
        )
        assert regime == RadiometricRegime.POINT_SOURCE

    def test_boundary_exactly_2_ifov_is_extended(self) -> None:
        """Angular extent exactly 2 × IFOV → EXTENDED (inclusive boundary)."""
        ang_target = 2.0 * self.IFOV  # = 3e-5 rad
        # sqrt(A) / R = 3e-5 → A = (3e-5 * R)^2
        R = 1e6
        A = (ang_target * R) ** 2
        regime, _ = _classify_regime(
            projected_area_m2=A,
            range_m=R,
            fill_fraction=1.0,
            pixel_pitch_m=self.PIXEL_PITCH_M,
            focal_length_m=self.FOCAL_LENGTH_M,
            regime_override="auto",
        )
        assert regime == RadiometricRegime.EXTENDED

    def test_boundary_exactly_025_ifov_is_point(self) -> None:
        """Angular extent exactly 0.25 × IFOV → POINT_SOURCE (inclusive)."""
        ang_target = 0.25 * self.IFOV
        R = 1e6
        A = (ang_target * R) ** 2
        regime, _ = _classify_regime(
            projected_area_m2=A,
            range_m=R,
            fill_fraction=1.0,
            pixel_pitch_m=self.PIXEL_PITCH_M,
            focal_length_m=self.FOCAL_LENGTH_M,
            regime_override="auto",
        )
        assert regime == RadiometricRegime.POINT_SOURCE
