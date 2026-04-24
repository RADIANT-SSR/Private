"""S10 user-supplied at-source intensity → TargetDescriptor converter.

Spec form S10 (Target Definition Matrix §1): the user supplies an
absolute spectral intensity ``I_t_source(λ)`` [W/sr/µm] for an
unresolved (point-source) target.  No physical model is applied on
the way in — the user owns the physics.  The boundary converter
routes the intensity through
:class:`~radiant.core.descriptors.T7IntensityAtSource` (ADR-0004),
which AtmosphereStage propagates via the T7 up-leg arm.

``target_location == 'at_aperture'`` is rejected — the aperture
integrates radiance, not intensity; at-aperture inputs belong on
:class:`T5AtAperture`.  ``scene_type != 'point_source'`` is rejected —
intensity is the point-source radiometric quantity (matrix §7 row S10);
resolved targets must use radiance via T1 / T3 / T6.

Rule 19 — this module owns exactly the S10 boundary conversion.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from radiant.core.descriptors import (
    NoAtmosphereSubcase,
    SceneType,
    T7IntensityAtSource,
    TargetDescriptor,
    TargetLocation,
)
from radiant.core.parameters import ParameterBoundsError
from radiant.core.spectral import SpectralData
from radiant.source.converters._csv import load_two_column_csv


def load_user_intensity_csv(path: Path | str) -> SpectralData:
    """Load a user-intensity CSV into a :class:`SpectralData`.

    Parameters
    ----------
    path:
        Filesystem path to a two-column ``(wavelength_um, I_t_source)``
        CSV file.  Units are the canonical ``W/sr/um`` — no scaling
        is applied by the loader (Rule 2: boundary conversion already
        happened at authoring time).

    Returns
    -------
    SpectralData
        Intensity tabulated on the CSV's native wavelength grid.  The
        downstream caller resamples onto the chain grid before building
        the T7 descriptor.
    """
    return load_two_column_csv(
        path,
        value_unit="W/sr/um",
        column_label="I_t_source",
        sd_name="source.target.user_intensity",
        sd_source_prefix="source.converters.user_intensity",
    )


def _validate_I_t_source(I_values: np.ndarray) -> None:
    """Raise :class:`ParameterBoundsError` on empty or negative intensity.

    Rule 17: no silent clipping — negative intensity is unphysical
    (photon flux per solid angle is non-negative) and must surface a
    clear error at the boundary rather than propagating into the
    atmospheric up-leg.
    """
    if I_values.size == 0:
        raise ParameterBoundsError(
            what="user_intensity: I_t_source SpectralData has zero samples",
            why=(
                "The converter needs at least one (λ, I) pair to emit a "
                "T7IntensityAtSource descriptor."
            ),
            action=(
                "Supply I_t_source on the chain grid (at least two "
                "points for the SpectralData constructor)."
            ),
            context={},
        )
    if np.any(I_values < 0.0):
        bad = float(I_values.min())
        raise ParameterBoundsError(
            what=(
                f"user_intensity: I_t_source = {bad} W/sr/µm is negative"
            ),
            why=(
                "Spectral intensity is non-negative by definition "
                "(photon flux per solid angle is non-negative); "
                "negative values typically indicate a unit error or an "
                "authoring bug in the user CSV / SpectralData."
            ),
            action=(
                "Clamp the intensity at zero in the source CSV or verify "
                "that the units are W/sr/µm and not a signed quantity."
            ),
            context={"min_I": bad, "floor": 0.0},
        )


def user_intensity_to_descriptor(
    I_t_source: SpectralData,
    *,
    scene_type: SceneType,
    target_location: TargetLocation,
    no_atmosphere_subcase: NoAtmosphereSubcase | None = None,
    h_tgt: float | None = None,
) -> TargetDescriptor:
    """Convert a user-supplied ``I_t_source(λ)`` into a T7IntensityAtSource.

    Parameters
    ----------
    I_t_source:
        :class:`SpectralData` in ``W/sr/um`` at the target plane.
        Must be non-negative everywhere.
    scene_type, target_location, no_atmosphere_subcase, h_tgt:
        Matrix-axes metadata, passed through to T7IntensityAtSource.
        ``at_aperture`` is rejected — the aperture integrates radiance,
        not intensity; at-aperture scenes belong on T5AtAperture.
        ``scene_type`` must be ``"point_source"`` — intensity is the
        point-source radiometric quantity (matrix §7 row S10).

    Returns
    -------
    TargetDescriptor
        :class:`T7IntensityAtSource` with ``I_t_source`` populated.  The
        descriptor carries no ``A_t`` or ``shape`` — the reference area
        used internally by the assembly arm is an implementation detail
        (ADR-0004).

    Raises
    ------
    ParameterBoundsError
        * ``target_location == 'at_aperture'``.
        * ``scene_type != 'point_source'``.
        * ``I_t_source`` with negative or empty values.
    """
    if target_location == "at_aperture":
        raise ParameterBoundsError(
            what=(
                "user_intensity: target_location='at_aperture' is not "
                "supported"
            ),
            why=(
                "S10 supplies intensity at the target plane; the "
                "aperture integrates radiance, not intensity.  "
                "At-aperture inputs (S9) belong on T5AtAperture."
            ),
            action=(
                "Set target_location to 'terrestrial', 'airborne', or "
                "'no_atmosphere', or remove user_intensity and supply "
                "L_t_aperture via T5."
            ),
            context={"target_location": target_location},
        )

    if scene_type != "point_source":
        raise ParameterBoundsError(
            what=(
                f"user_intensity: scene_type = {scene_type!r} is not "
                f"'point_source'"
            ),
            why=(
                "Intensity I(λ) [W/sr/µm] is the point-source "
                "radiometric quantity (matrix §7 row S10).  Extended "
                "and sub_pixel cells carry radiance L(λ) and must use "
                "T1 / T3 / T6."
            ),
            action=(
                "Set scene_type='point_source' or switch to a "
                "radiance-carrying input (user_radiance / thermal / "
                "reflective)."
            ),
            context={"scene_type": scene_type},
        )

    _validate_I_t_source(
        np.asarray(I_t_source.values, dtype=np.float64)
    )

    return T7IntensityAtSource(
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
        I_t_source=I_t_source,
    )


__all__ = [
    "load_user_intensity_csv",
    "user_intensity_to_descriptor",
]
