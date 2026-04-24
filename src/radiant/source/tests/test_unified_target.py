"""Tests for ResolvedTarget and the five input paths.

Truth anchors:
1. All geometry paths compute correct projected area
2. Path 1, 2, 5 produce identical spectral_radiance for same target
3. Composite of single sphere = bare sphere through resolver

Cross-model consistency:
- All 5 input paths for the same thermal target produce consistent
  ResolvedTarget fields (within physics-relevant precision).

See RADIANT_Source_Target_System.md §2 and §6.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.regime import RadiometricRegime, TargetInputPath
from radiant.source.backgrounds.blackbody import BlackbodyBackground
from radiant.source.emitted import ThermalSource
from radiant.source.material import SurfaceMaterial
from radiant.source.point_source_blackbody import BlackbodyIntensitySource
from radiant.source.resolvers.direct import resolve_direct_radiance
from radiant.source.resolvers.geometry import resolve_geometry
from radiant.source.resolvers.intensity import resolve_direct_intensity
from radiant.source.resolvers.physical import resolve_physical_object
from radiant.source.resolvers.resolved_target import ResolvedTarget
from radiant.source.resolvers.sub_pixel import resolve_sub_pixel
from radiant.source.shapes import Sphere

WAV = np.linspace(3.0, 5.0, 200)
VZ = np.array([0.0, 0.0, 1.0])


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture()
def thermal_source() -> ThermalSource:
    return ThermalSource(temperature_K=500.0, emissivity=0.9)


@pytest.fixture()
def background() -> BlackbodyBackground:
    return BlackbodyBackground(temperature_K=290.0, emissivity=0.95)


@pytest.fixture()
def material() -> SurfaceMaterial:
    return SurfaceMaterial(name="test", temperature_K=500.0, emissivity=0.9)


# ======================================================================
# ResolvedTarget basic
# ======================================================================


class TestResolvedTarget:
    def test_frozen(self, thermal_source: ThermalSource, background: BlackbodyBackground) -> None:
        rt = ResolvedTarget(
            name="test",
            input_path=TargetInputPath.DIRECT_RADIANCE,
            derivation_chain=("test",),
            radiance_source=thermal_source,
            background_source=background,
            projected_area_m2=1.0,
            angular_extent_rad=1e-4,
            range_m=10000.0,
            tentative_regime=RadiometricRegime.EXTENDED,
        )
        with pytest.raises(AttributeError):
            rt.name = "changed"  # type: ignore[misc]

    def test_spectral_radiance(self, thermal_source: ThermalSource, background: BlackbodyBackground) -> None:
        rt = ResolvedTarget(
            name="test",
            input_path=TargetInputPath.DIRECT_RADIANCE,
            derivation_chain=("test",),
            radiance_source=thermal_source,
            background_source=background,
            projected_area_m2=1.0,
            angular_extent_rad=1e-4,
            range_m=10000.0,
            tentative_regime=RadiometricRegime.EXTENDED,
        )
        L = rt.spectral_radiance(WAV)
        expected = 0.9 * planck_spectral_radiance(WAV, 500.0)
        np.testing.assert_allclose(L, expected, rtol=1e-10)

    def test_spectral_intensity(self, thermal_source: ThermalSource, background: BlackbodyBackground) -> None:
        area = 0.5
        rt = ResolvedTarget(
            name="test",
            input_path=TargetInputPath.DIRECT_RADIANCE,
            derivation_chain=("test",),
            radiance_source=thermal_source,
            background_source=background,
            projected_area_m2=area,
            angular_extent_rad=1e-4,
            range_m=10000.0,
            tentative_regime=RadiometricRegime.EXTENDED,
        )
        I = rt.spectral_intensity(WAV)
        expected = 0.9 * planck_spectral_radiance(WAV, 500.0) * area
        np.testing.assert_allclose(I, expected, rtol=1e-10)


# ======================================================================
# Path 1: Direct radiance
# ======================================================================


class TestDirectRadiance:
    def test_basic(self, thermal_source: ThermalSource, background: BlackbodyBackground) -> None:
        rt = resolve_direct_radiance(
            name="direct",
            radiance_source=thermal_source,
            background_source=background,
            projected_area_m2=1.0,
            range_m=10000.0,
        )
        assert rt.input_path == TargetInputPath.DIRECT_RADIANCE
        assert rt.projected_area_m2 == 1.0
        assert rt.range_m == 10000.0
        assert rt.tentative_regime == RadiometricRegime.EXTENDED

    def test_negative_range_raises(self, thermal_source: ThermalSource, background: BlackbodyBackground) -> None:
        with pytest.raises(ValueError, match="range_m"):
            resolve_direct_radiance(
                name="bad",
                radiance_source=thermal_source,
                background_source=background,
                projected_area_m2=1.0,
                range_m=-100.0,
            )


# ======================================================================
# Path 2: Geometry
# ======================================================================


class TestGeometry:
    def test_sphere_area(self, background: BlackbodyBackground, material: SurfaceMaterial) -> None:
        sphere = Sphere(radius_m=0.5)
        rt = resolve_geometry(
            name="sphere",
            shapes=(sphere,),
            material=material,
            view_direction=VZ,
            background_source=background,
            range_m=10000.0,
        )
        assert rt.input_path == TargetInputPath.GEOMETRY
        assert rt.projected_area_m2 == pytest.approx(
            math.pi * 0.25, rel=1e-12
        )
        assert rt.shapes is not None
        assert rt.materials is not None

    def test_radiance_matches_material(self, background: BlackbodyBackground, material: SurfaceMaterial) -> None:
        sphere = Sphere(radius_m=0.5)
        rt = resolve_geometry(
            name="sphere",
            shapes=(sphere,),
            material=material,
            view_direction=VZ,
            background_source=background,
            range_m=10000.0,
        )
        expected = 0.9 * planck_spectral_radiance(WAV, 500.0)
        np.testing.assert_allclose(rt.spectral_radiance(WAV), expected, rtol=1e-10)

    def test_angular_extent(self, background: BlackbodyBackground, material: SurfaceMaterial) -> None:
        sphere = Sphere(radius_m=0.5)
        rt = resolve_geometry(
            name="sphere",
            shapes=(sphere,),
            material=material,
            view_direction=VZ,
            background_source=background,
            range_m=10000.0,
        )
        expected = math.sqrt(math.pi * 0.25) / 10000.0
        assert rt.angular_extent_rad == pytest.approx(expected, rel=1e-10)


# ======================================================================
# Path 3: Sub-pixel
# ======================================================================


class TestSubPixel:
    def test_basic(self, thermal_source: ThermalSource, background: BlackbodyBackground) -> None:
        rt = resolve_sub_pixel(
            name="sub",
            target_source=thermal_source,
            background_source=background,
            fill_fraction=0.1,
            range_m=10000.0,
        )
        assert rt.input_path == TargetInputPath.SUB_PIXEL
        assert rt.tentative_regime == RadiometricRegime.SUB_PIXEL
        assert rt.projected_area_m2 == 0.0

    def test_invalid_ff_raises(self, thermal_source: ThermalSource, background: BlackbodyBackground) -> None:
        with pytest.raises(ValueError, match="fill_fraction"):
            resolve_sub_pixel(
                name="bad",
                target_source=thermal_source,
                background_source=background,
                fill_fraction=0.0,
                range_m=10000.0,
            )


# ======================================================================
# Path 4: Direct intensity
# ======================================================================


class TestDirectIntensity:
    def test_basic(self, background: BlackbodyBackground) -> None:
        isrc = BlackbodyIntensitySource(
            temperature_K=500.0, projected_area_m2=0.01, emissivity=1.0,
        )
        rt = resolve_direct_intensity(
            name="point",
            intensity_source=isrc,
            background_source=background,
            range_m=50000.0,
        )
        assert rt.input_path == TargetInputPath.DIRECT_INTENSITY
        assert rt.tentative_regime == RadiometricRegime.POINT_SOURCE
        assert rt.projected_area_m2 == 0.0
        assert rt.angular_extent_rad == 0.0


# ======================================================================
# Path 5: Physical object
# ======================================================================


class TestPhysicalObject:
    def test_matches_geometry_path(self, background: BlackbodyBackground, material: SurfaceMaterial) -> None:
        """Path 5 computes same radiance and area as Path 2."""
        sphere = Sphere(radius_m=0.5)
        rt2 = resolve_geometry(
            name="geom",
            shapes=(sphere,),
            material=material,
            view_direction=VZ,
            background_source=background,
            range_m=10000.0,
        )
        rt5 = resolve_physical_object(
            name="phys",
            shapes=(sphere,),
            material=material,
            view_direction=VZ,
            background_source=background,
            range_m=10000.0,
        )
        assert rt5.input_path == TargetInputPath.PHYSICAL_OBJECT
        assert rt5.projected_area_m2 == pytest.approx(
            rt2.projected_area_m2, rel=1e-12
        )
        np.testing.assert_allclose(
            rt5.spectral_radiance(WAV),
            rt2.spectral_radiance(WAV),
            rtol=1e-12,
        )


# ======================================================================
# Cross-path consistency
# ======================================================================


class TestCrossPathConsistency:
    """Paths 1, 2, and 5 for the same thermal sphere produce identical
    spectral_radiance(WAV) and projected_area_m2.
    """

    def test_paths_1_2_5_consistent(self) -> None:
        T = 500.0
        eps = 0.9
        r = 0.5
        range_m = 10000.0
        area = math.pi * r ** 2
        bg = BlackbodyBackground(temperature_K=290.0, emissivity=0.95)

        # Path 1: direct radiance
        src = ThermalSource(temperature_K=T, emissivity=eps)
        rt1 = resolve_direct_radiance(
            name="p1",
            radiance_source=src,
            background_source=bg,
            projected_area_m2=area,
            range_m=range_m,
        )

        # Path 2: geometry
        mat = SurfaceMaterial(name="test", temperature_K=T, emissivity=eps)
        sphere = Sphere(radius_m=r)
        rt2 = resolve_geometry(
            name="p2",
            shapes=(sphere,),
            material=mat,
            view_direction=VZ,
            background_source=bg,
            range_m=range_m,
        )

        # Path 5: physical object
        rt5 = resolve_physical_object(
            name="p5",
            shapes=(sphere,),
            material=mat,
            view_direction=VZ,
            background_source=bg,
            range_m=range_m,
        )

        # Projected areas match.
        assert rt1.projected_area_m2 == pytest.approx(rt2.projected_area_m2, rel=1e-10)
        assert rt2.projected_area_m2 == pytest.approx(rt5.projected_area_m2, rel=1e-10)

        # Spectral radiance matches.
        L1 = rt1.spectral_radiance(WAV)
        L2 = rt2.spectral_radiance(WAV)
        L5 = rt5.spectral_radiance(WAV)
        np.testing.assert_allclose(L1, L2, rtol=1e-10)
        np.testing.assert_allclose(L2, L5, rtol=1e-12)

    def test_path_4_intensity_consistent(self) -> None:
        """Path 4 intensity = Path 1 radiance × area."""
        T = 500.0
        eps = 0.9
        area = math.pi * 0.25
        bg = BlackbodyBackground(temperature_K=290.0)

        # Path 1
        src = ThermalSource(temperature_K=T, emissivity=eps)
        rt1 = resolve_direct_radiance(
            name="p1",
            radiance_source=src,
            background_source=bg,
            projected_area_m2=area,
            range_m=10000.0,
        )

        # Path 4: intensity source with same physics
        isrc = BlackbodyIntensitySource(
            temperature_K=T, projected_area_m2=area, emissivity=eps,
        )

        # The intensity from Path 4 = radiance from Path 1 × area.
        I_p4 = isrc.spectral_intensity(WAV)
        I_p1 = rt1.spectral_intensity(WAV)
        np.testing.assert_allclose(I_p4, I_p1, rtol=1e-10)

    def test_regime_override(self) -> None:
        src = ThermalSource(temperature_K=500.0, emissivity=0.9)
        bg = BlackbodyBackground(temperature_K=290.0)
        rt = resolve_direct_radiance(
            name="forced",
            radiance_source=src,
            background_source=bg,
            projected_area_m2=1.0,
            range_m=10000.0,
            regime_override=RadiometricRegime.POINT_SOURCE,
        )
        assert rt.tentative_regime == RadiometricRegime.POINT_SOURCE
        assert rt.regime_override == RadiometricRegime.POINT_SOURCE

    def test_derivation_chain_present(self) -> None:
        src = ThermalSource(temperature_K=500.0, emissivity=0.9)
        bg = BlackbodyBackground(temperature_K=290.0)
        rt = resolve_direct_radiance(
            name="test",
            radiance_source=src,
            background_source=bg,
            projected_area_m2=1.0,
            range_m=10000.0,
        )
        assert len(rt.derivation_chain) > 0
