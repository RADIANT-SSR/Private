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


# IFOV-based regime decision boundaries (Matrix §1.1 / §3.2), used by the
# SourceStage tentative classification and the descriptor inferrer (CU-044:
# single definition, shared by both sites).  A target of angular extent θ
# against a pixel IFOV is:
#   EXTENDED      when θ ≥ REGIME_EXTENDED_IFOV_MULTIPLE  × IFOV
#   POINT_SOURCE  when θ ≤ REGIME_POINT_SOURCE_IFOV_MULTIPLE × IFOV
#   SUB_PIXEL     otherwise.
# These are classification conventions, not physics: 2 IFOV ≈ the Nyquist
# footprint over which pixel-averaged radiance is scene radiance; ¼ IFOV
# puts ≥ 94 % of a centred pixel's response on the background.  OpticsStage
# re-finalizes against the PSF FWHM (Rule 10) with its own thresholds; user
# control is via ``source.regime_override``, not by tuning these.
REGIME_EXTENDED_IFOV_MULTIPLE: float = 2.0
REGIME_POINT_SOURCE_IFOV_MULTIPLE: float = 0.25


class TargetInputPath(Enum):
    """Which of the five user input paths produced a ResolvedTarget.

    See RADIANT_Source_Target_System.md §6 for the five paths.
    """

    DIRECT_RADIANCE = "direct_radiance"
    GEOMETRY = "geometry"
    SUB_PIXEL = "sub_pixel"
    DIRECT_INTENSITY = "direct_intensity"
    PHYSICAL_OBJECT = "physical_object"
