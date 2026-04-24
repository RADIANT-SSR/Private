"""S8 user-supplied at-source radiance → TargetDescriptor converter.

Spec form S8 (Target Definition Matrix §1): the user supplies an
absolute spectral radiance ``L_t_source(λ)`` already at the target plane.
No physical model is applied on the way in — the user owns the physics.
The boundary converter routes the radiance through
:class:`~radiant.core.descriptors.T6TabulatedAtSource` (ADR-0003), which
AtmosphereStage propagates via the normal up-leg arm.

``target_location == 'at_aperture'`` is rejected — that cell is the S9
(T5AtAperture) domain and bypasses atmospheric transport.

Rule 19 — this module owns exactly the S8 boundary conversion.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from radiant.core.descriptors import (
    NoAtmosphereSubcase,
    SceneType,
    T6TabulatedAtSource,
    TargetDescriptor,
    TargetLocation,
)
from radiant.core.parameters import ParameterBoundsError
from radiant.core.spectral import SpectralData
from radiant.source.converters._csv import load_two_column_csv


def load_user_radiance_csv(path: Path | str) -> SpectralData:
    """Load a user-radiance CSV into a :class:`SpectralData`.

    Parameters
    ----------
    path:
        Filesystem path to a two-column ``(wavelength_um, L_t_source)``
        CSV file.  Units are the canonical ``W/m²/sr/µm`` — no scaling
        is applied by the loader (Rule 2: boundary conversion already
        happened at authoring time).

    Returns
    -------
    SpectralData
        Radiance tabulated on the CSV's native wavelength grid.  The
        downstream converter feeds this through
        :class:`~radiant.source.tabulated.TabulatedRadianceSource` when
        the grid differs from the chain grid.
    """
    return load_two_column_csv(
        path,
        value_unit="W/m^2/sr/um",
        column_label="L_t_source",
        sd_name="source.target.user_radiance",
        sd_source_prefix="source.converters.user_radiance",
    )


def _validate_L_t_source(L_values: np.ndarray) -> None:
    """Raise :class:`ParameterBoundsError` on empty or negative radiance.

    Rule 17: no silent clipping — negative radiance is unphysical and
    must surface a clear error at the boundary rather than propagating
    into the atmospheric up-leg.
    """
    if L_values.size == 0:
        raise ParameterBoundsError(
            what=(
                "user_radiance: L_t_source SpectralData has zero samples"
            ),
            why=(
                "The converter needs at least one (λ, L) pair to emit a "
                "T6TabulatedAtSource descriptor."
            ),
            action=(
                "Supply L_t_source on the chain grid (at least two "
                "points for the SpectralData constructor)."
            ),
            context={},
        )
    if np.any(L_values < 0.0):
        bad = float(L_values.min())
        raise ParameterBoundsError(
            what=(
                f"user_radiance: L_t_source = {bad} W/m²/sr/µm is "
                "negative"
            ),
            why=(
                "Spectral radiance is non-negative by definition "
                "(photon-count is non-negative); negative values "
                "typically indicate a unit error or an authoring bug "
                "in the user CSV / SpectralData."
            ),
            action=(
                "Clamp the radiance at zero in the source CSV or verify "
                "that the units are W/m²/sr/µm and not a signed quantity "
                "(e.g. difference radiance)."
            ),
            context={"min_L": bad, "floor": 0.0},
        )


def user_radiance_to_descriptor(
    L_t_source: SpectralData,
    *,
    scene_type: SceneType,
    target_location: TargetLocation,
    no_atmosphere_subcase: NoAtmosphereSubcase | None = None,
    h_tgt: float | None = None,
    A_t: float | None = None,
    shape: object | None = None,
) -> TargetDescriptor:
    """Convert a user-supplied ``L_t_source(λ)`` into a T6TabulatedAtSource.

    Parameters
    ----------
    L_t_source:
        :class:`SpectralData` in ``W/m²/sr/µm`` at the target plane.
        Must be non-negative everywhere.
    scene_type, target_location, no_atmosphere_subcase, h_tgt:
        Matrix-axes metadata, passed through to T6TabulatedAtSource.
        ``at_aperture`` is rejected — S9 is the T5AtAperture domain and
        carries aperture-plane radiance, not target-plane radiance.
    A_t, shape:
        Optional projected-area surface; passed through to the
        descriptor.

    Returns
    -------
    TargetDescriptor
        :class:`T6TabulatedAtSource` with ``L_t_source`` populated and
        ``A_t`` / shape from the matrix-Q3 resolution.

    Raises
    ------
    ParameterBoundsError
        * ``target_location == 'at_aperture'``.
        * ``L_t_source`` with negative or empty values.
    """
    if target_location == "at_aperture":
        raise ParameterBoundsError(
            what=(
                "user_radiance: target_location='at_aperture' is not "
                "supported"
            ),
            why=(
                "S8 supplies radiance at the target plane, which flows "
                "through the atmospheric up-leg to the aperture.  "
                "At-aperture (S9) inputs bypass atmosphere entirely — "
                "use T5AtAperture directly for S9."
            ),
            action=(
                "Set target_location to 'terrestrial', 'airborne', or "
                "'no_atmosphere', or remove user_radiance and supply "
                "L_t_aperture via T5."
            ),
            context={"target_location": target_location},
        )

    _validate_L_t_source(
        np.asarray(L_t_source.values, dtype=np.float64)
    )

    return T6TabulatedAtSource(
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
        L_t_source=L_t_source,
        A_t=A_t,
        shape=shape,
    )


__all__ = [
    "load_user_radiance_csv",
    "user_radiance_to_descriptor",
]
