"""Radiometric regime and target input path enumerations.

These enums classify how a target is observed (regime) and how it was
specified by the user (input path). Both are consumed by multiple stages
in the signal chain.

See RADIANT_Source_Target_System.md §2 and §6.
"""

from __future__ import annotations

from enum import Enum


class RadiometricRegime(Enum):
    """How the target is resolved relative to the sensor PSF.

    Determined tentatively in SourceStage, finalized in OpticsStage.
    """

    POINT_SOURCE = "point_source"
    SUB_PIXEL = "sub_pixel"
    EXTENDED = "extended"


class TargetInputPath(Enum):
    """Which of the five user input paths produced a ResolvedTarget.

    See RADIANT_Source_Target_System.md §6 for the five paths.
    """

    DIRECT_RADIANCE = "direct_radiance"
    GEOMETRY = "geometry"
    SUB_PIXEL = "sub_pixel"
    DIRECT_INTENSITY = "direct_intensity"
    PHYSICAL_OBJECT = "physical_object"
