"""Stage 1: target and background spectral radiance computation."""

from radiant.source.backgrounds import (
    CMB_BACKGROUND,
    BlackbodyBackground,
    ConstantBackground,
    TabulatedBackground,
)
from radiant.source.brdf_lambertian import LambertianBRDF
from radiant.source.brdf_phong import PhongBRDF
from radiant.source.combined import CombinedSource
from radiant.source.emitted import ThermalSource
from radiant.source.material import SurfaceMaterial
from radiant.source.point_source_blackbody import BlackbodyIntensitySource
from radiant.source.point_source_direct import DirectIntensitySource
from radiant.source.protocol import SpectralRadianceSource
from radiant.source.reflected import ReflectedSolarSource
from radiant.source.resolvers import (
    ResolvedTarget,
    resolve_direct_intensity,
    resolve_direct_radiance,
    resolve_geometry,
    resolve_physical_object,
    resolve_sub_pixel,
)
from radiant.source.shape import TargetShape
from radiant.source.shapes import Box, Cone, Cylinder, FlatPlate, Sphere
from radiant.source.tabulated import TabulatedRadianceSource

__all__ = [
    "BlackbodyBackground",
    "BlackbodyIntensitySource",
    "Box",
    "CMB_BACKGROUND",
    "CombinedSource",
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
