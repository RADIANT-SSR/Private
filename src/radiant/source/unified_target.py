"""Unified target resolver — five input paths to one ResolvedTarget.

Implements the ResolvedTarget contract and the five factory functions
that produce it, per RADIANT_Source_Target_System.md §2 and §6.

Every path through the source system produces the same frozen dataclass.
The signal chain consumes ResolvedTarget and never inspects how it was built.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from radiant.core.regime import RadiometricRegime, TargetInputPath
from radiant.source.background import BlackbodyBackground
from radiant.source.material import SurfaceMaterial
from radiant.source.protocol import SpectralRadianceSource
from radiant.source.shape import TargetShape


# ---------------------------------------------------------------------------
# ResolvedTarget
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedTarget:
    """Everything the chain needs to know about a target.

    Produced by exactly one of the five input paths. Immutable.
    The chain consumes this and never inspects how it was built.

    Attributes
    ----------
    name:
        Human-readable target label.
    input_path:
        Which of the 5 paths produced this.
    derivation_chain:
        Human-readable sequence of build steps.
    radiance_source:
        Produces L(λ) [W/m²/sr/µm] — the target surface radiance.
    background_source:
        Produces L_bg(λ) [W/m²/sr/µm].
    projected_area_m2:
        Area facing observer [m²]. 0 for pure point sources.
    angular_extent_rad:
        √(projected_area) / range [rad].
    range_m:
        Observer → target distance [m].
    tentative_regime:
        POINT_SOURCE, SUB_PIXEL, or EXTENDED. Finalized in OpticsStage.
    regime_override:
        If set, forces regime classification. None = auto.
    shapes:
        Preserved geometry (Paths 2 and 5 only).
    materials:
        Preserved materials (Paths 2 and 5 only).
    """

    name: str
    input_path: TargetInputPath
    derivation_chain: tuple[str, ...]

    radiance_source: SpectralRadianceSource
    background_source: SpectralRadianceSource

    projected_area_m2: float
    angular_extent_rad: float
    range_m: float

    tentative_regime: RadiometricRegime
    regime_override: RadiometricRegime | None = None

    shapes: tuple[TargetShape, ...] | None = None
    materials: tuple[SurfaceMaterial, ...] | None = None

    def spectral_radiance(
        self, wavelength_um: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """Target surface spectral radiance [W/m²/sr/µm]."""
        return self.radiance_source.spectral_radiance(wavelength_um)

    def spectral_intensity(
        self, wavelength_um: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """Target spectral intensity [W/sr/µm] = L(λ) × A_proj."""
        return (
            self.radiance_source.spectral_radiance(wavelength_um)
            * self.projected_area_m2
        )

    def background_radiance(
        self, wavelength_um: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """Background spectral radiance [W/m²/sr/µm]."""
        return self.background_source.spectral_radiance(wavelength_um)


# ---------------------------------------------------------------------------
# Path 1: Direct radiance
# ---------------------------------------------------------------------------


def resolve_direct_radiance(
    *,
    name: str,
    radiance_source: SpectralRadianceSource,
    background_source: SpectralRadianceSource,
    projected_area_m2: float,
    range_m: float,
    regime_override: RadiometricRegime | None = None,
) -> ResolvedTarget:
    """Path 1 — user provides L(λ) directly.

    Parameters
    ----------
    name:
        Target label.
    radiance_source:
        Source object producing L(λ) [W/m²/sr/µm].
    background_source:
        Source object producing L_bg(λ).
    projected_area_m2:
        Projected area [m²].
    range_m:
        Observer–target distance [m].
    regime_override:
        Force regime classification (optional).
    """
    _validate_range(range_m)
    _validate_area(projected_area_m2)

    angular_extent = _angular_extent(projected_area_m2, range_m)
    regime = regime_override or RadiometricRegime.EXTENDED

    return ResolvedTarget(
        name=name,
        input_path=TargetInputPath.DIRECT_RADIANCE,
        derivation_chain=("user-provided L(λ)",),
        radiance_source=radiance_source,
        background_source=background_source,
        projected_area_m2=projected_area_m2,
        angular_extent_rad=angular_extent,
        range_m=range_m,
        tentative_regime=regime,
        regime_override=regime_override,
    )


# ---------------------------------------------------------------------------
# Path 2: Geometry + materials
# ---------------------------------------------------------------------------


def resolve_geometry(
    *,
    name: str,
    shapes: tuple[TargetShape, ...],
    material: SurfaceMaterial,
    view_direction: npt.NDArray[np.float64],
    background_source: SpectralRadianceSource,
    range_m: float,
    solar_zenith_rad: float | None = None,
    observer_zenith_rad: float = 0.0,
    distance_au: float = 1.0,
    regime_override: RadiometricRegime | None = None,
) -> ResolvedTarget:
    """Path 2 — geometry + materials (canonical path).

    Creates a source from the material and computes projected area
    from the shapes. All shapes use the same material (v1).

    Parameters
    ----------
    name:
        Target label.
    shapes:
        Tuple of TargetShape primitives.
    material:
        Surface material (provides ε, T, BRDF).
    view_direction:
        Unit 3-vector, target → observer, scene frame.
    background_source:
        Background radiance source.
    range_m:
        Observer–target distance [m].
    solar_zenith_rad:
        Solar zenith [rad]. If None, thermal-only source.
    observer_zenith_rad:
        Observer zenith [rad].
    distance_au:
        Sun–target distance [AU].
    regime_override:
        Force regime classification (optional).
    """
    _validate_range(range_m)
    v = np.asarray(view_direction, dtype=np.float64)

    projected_area = sum(s.projected_area(v) for s in shapes)
    _validate_area(projected_area)

    source = material.create_source(
        solar_zenith_rad=solar_zenith_rad,
        observer_zenith_rad=observer_zenith_rad,
        distance_au=distance_au,
    )

    angular_extent = _angular_extent(projected_area, range_m)
    regime = regime_override or RadiometricRegime.EXTENDED

    return ResolvedTarget(
        name=name,
        input_path=TargetInputPath.GEOMETRY,
        derivation_chain=(
            f"geometry: {len(shapes)} shape(s)",
            f"material: {material.name}",
            f"projected_area: {projected_area:.6e} m²",
        ),
        radiance_source=source,
        background_source=background_source,
        projected_area_m2=projected_area,
        angular_extent_rad=angular_extent,
        range_m=range_m,
        tentative_regime=regime,
        regime_override=regime_override,
        shapes=shapes,
        materials=(material,),
    )


# ---------------------------------------------------------------------------
# Path 3: Sub-pixel parameters
# ---------------------------------------------------------------------------


def resolve_sub_pixel(
    *,
    name: str,
    target_source: SpectralRadianceSource,
    background_source: SpectralRadianceSource,
    fill_fraction: float,
    range_m: float,
    regime_override: RadiometricRegime | None = None,
) -> ResolvedTarget:
    """Path 3 — sub-pixel parameters.

    The radiance_source on the returned ResolvedTarget is the *target*
    source (not the mixed pixel radiance). The fill fraction is stored
    so the chain can perform the mixing. The background_source carries
    L_bg for the noise budget.

    Parameters
    ----------
    name:
        Target label.
    target_source:
        Source for target radiance L_target(λ).
    background_source:
        Source for background radiance L_bg(λ).
    fill_fraction:
        Target fill fraction in [0, 1].
    range_m:
        Observer–target distance [m].
    regime_override:
        Force regime (optional). Defaults to SUB_PIXEL.
    """
    _validate_range(range_m)
    if not (0.0 < fill_fraction <= 1.0):
        raise ValueError(
            f"resolve_sub_pixel: fill_fraction must be in (0, 1], "
            f"got {fill_fraction}"
        )

    regime = regime_override or RadiometricRegime.SUB_PIXEL

    return ResolvedTarget(
        name=name,
        input_path=TargetInputPath.SUB_PIXEL,
        derivation_chain=(
            f"sub-pixel: ff={fill_fraction:.6e}",
        ),
        radiance_source=target_source,
        background_source=background_source,
        projected_area_m2=0.0,
        angular_extent_rad=0.0,
        range_m=range_m,
        tentative_regime=regime,
        regime_override=regime_override,
    )


# ---------------------------------------------------------------------------
# Path 4: Direct intensity (point source)
# ---------------------------------------------------------------------------


def resolve_direct_intensity(
    *,
    name: str,
    intensity_source: SpectralRadianceSource,
    background_source: SpectralRadianceSource,
    range_m: float,
    regime_override: RadiometricRegime | None = None,
) -> ResolvedTarget:
    """Path 4 — user provides I(λ) directly.

    The ``intensity_source`` is treated as producing intensity values
    (W/sr/µm). It is stored as the radiance_source for chain access;
    the chain uses the POINT_SOURCE regime to interpret it correctly.
    ``projected_area_m2`` is set to 0.

    Parameters
    ----------
    name:
        Target label.
    intensity_source:
        Source producing I(λ) values. For BlackbodyIntensitySource,
        ``spectral_radiance()`` returns ε·B(λ,T) and
        ``spectral_intensity()`` returns A·ε·B(λ,T).
    background_source:
        Background radiance source.
    range_m:
        Observer–target distance [m].
    regime_override:
        Force regime (optional). Defaults to POINT_SOURCE.
    """
    _validate_range(range_m)

    regime = regime_override or RadiometricRegime.POINT_SOURCE

    return ResolvedTarget(
        name=name,
        input_path=TargetInputPath.DIRECT_INTENSITY,
        derivation_chain=("user-provided I(λ)",),
        radiance_source=intensity_source,
        background_source=background_source,
        projected_area_m2=0.0,
        angular_extent_rad=0.0,
        range_m=range_m,
        tentative_regime=regime,
        regime_override=regime_override,
    )


# ---------------------------------------------------------------------------
# Path 5: Physical object → integrated intensity
# ---------------------------------------------------------------------------


def resolve_physical_object(
    *,
    name: str,
    shapes: tuple[TargetShape, ...],
    material: SurfaceMaterial,
    view_direction: npt.NDArray[np.float64],
    background_source: SpectralRadianceSource,
    range_m: float,
    solar_zenith_rad: float | None = None,
    observer_zenith_rad: float = 0.0,
    distance_au: float = 1.0,
    regime_override: RadiometricRegime | None = None,
) -> ResolvedTarget:
    """Path 5 — physical object expected to be unresolved.

    Identical computation to Path 2 (same geometry integration), but
    the user expects the target to be unresolved. The regime hint
    is computed normally and may end up POINT_SOURCE or SUB_PIXEL.

    Parameters
    ----------
    name:
        Target label.
    shapes:
        Tuple of TargetShape primitives.
    material:
        Surface material.
    view_direction:
        Unit 3-vector, target → observer, scene frame.
    background_source:
        Background radiance source.
    range_m:
        Observer–target distance [m].
    solar_zenith_rad:
        Solar zenith [rad]. If None, thermal-only.
    observer_zenith_rad:
        Observer zenith [rad].
    distance_au:
        Sun–target distance [AU].
    regime_override:
        Force regime (optional).
    """
    _validate_range(range_m)
    v = np.asarray(view_direction, dtype=np.float64)

    projected_area = sum(s.projected_area(v) for s in shapes)
    _validate_area(projected_area)

    source = material.create_source(
        solar_zenith_rad=solar_zenith_rad,
        observer_zenith_rad=observer_zenith_rad,
        distance_au=distance_au,
    )

    angular_extent = _angular_extent(projected_area, range_m)
    regime = regime_override or RadiometricRegime.EXTENDED

    return ResolvedTarget(
        name=name,
        input_path=TargetInputPath.PHYSICAL_OBJECT,
        derivation_chain=(
            f"physical object: {len(shapes)} shape(s)",
            f"material: {material.name}",
            f"projected_area: {projected_area:.6e} m²",
        ),
        radiance_source=source,
        background_source=background_source,
        projected_area_m2=projected_area,
        angular_extent_rad=angular_extent,
        range_m=range_m,
        tentative_regime=regime,
        regime_override=regime_override,
        shapes=shapes,
        materials=(material,),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _angular_extent(projected_area_m2: float, range_m: float) -> float:
    """√(A_proj) / range [rad]."""
    if projected_area_m2 <= 0.0:
        return 0.0
    return math.sqrt(projected_area_m2) / range_m


def _validate_range(range_m: float) -> None:
    if range_m <= 0.0:
        raise ValueError(
            f"range_m must be positive, got {range_m}. "
            f"Distance from observer to target in meters."
        )


def _validate_area(projected_area_m2: float) -> None:
    if projected_area_m2 < 0.0:
        raise ValueError(
            f"projected_area_m2 must be >= 0, got {projected_area_m2}"
        )
