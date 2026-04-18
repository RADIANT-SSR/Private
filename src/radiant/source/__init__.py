"""Stage 1: target and background spectral radiance computation."""

from radiant.source.background_blackbody import (
    BlackbodyBackground,
    CMB_BACKGROUND,
)
from radiant.source.background_constant import ConstantBackground
from radiant.source.background_tabulated import TabulatedBackground
from radiant.source.brdf_lambertian import LambertianBRDF
from radiant.source.brdf_phong import PhongBRDF
from radiant.source.combined import CombinedSource
from radiant.source.composite import CompositeTarget
from radiant.source.emitted import ThermalSource
from radiant.source.material import SurfaceMaterial
from radiant.source.point_source_blackbody import BlackbodyIntensitySource
from radiant.source.point_source_direct import DirectIntensitySource
from radiant.source.shapes import Box, Cone, Cylinder, FlatPlate, Sphere
from radiant.source.protocol import SpectralRadianceSource
from radiant.source.reflected import ReflectedSolarSource
from radiant.source.shape import TargetShape
from radiant.source.sub_pixel import SubPixelSource
from radiant.source.tabulated import TabulatedRadianceSource
from radiant.source.resolved_target import ResolvedTarget
from radiant.source.resolve_direct import resolve_direct_radiance
from radiant.source.resolve_geometry import resolve_geometry
from radiant.source.resolve_intensity import resolve_direct_intensity
from radiant.source.resolve_physical import resolve_physical_object
from radiant.source.resolve_sub_pixel import resolve_sub_pixel

__all__ = [
    "BlackbodyBackground",
    "BlackbodyIntensitySource",
    "Box",
    "CMB_BACKGROUND",
    "CombinedSource",
    "CompositeTarget",
    "Cone",
    "ConstantBackground",
    "Cylinder",
    "DirectIntensitySource",
    "FlatPlate",
    "LambertianBRDF",
    "PhongBRDF",
    "ReflectedSolarSource",
    "ResolvedTarget",
    "SpectralRadianceSource",
    "Sphere",
    "SubPixelSource",
    "SurfaceMaterial",
    "TabulatedBackground",
    "TabulatedRadianceSource",
    "TargetShape",
    "ThermalSource",
    "resolve_direct_intensity",
    "resolve_direct_radiance",
    "resolve_geometry",
    "resolve_physical_object",
    "resolve_sub_pixel",
]
