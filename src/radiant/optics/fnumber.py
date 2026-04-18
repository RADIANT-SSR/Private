"""Consistency group resolver for ``(D, f, f/#)``.

Resolves the aperture-focal-length-fnumber triple: exactly two of
the three must be provided, and the third is derived from
``f/# = f / D``.  If all three are given, they must be mutually
consistent to within ``FNUMBER_CONSISTENCY_RTOL``.

See RADIANT_Optics.md section 3.
"""

from __future__ import annotations

import math

# Fractional tolerance at which the consistency group accepts the user
# over-specifying two entries plus a derivable third. Chosen to match
# MODTRAN-style rounding in datasheets (~0.1 %).
FNUMBER_CONSISTENCY_RTOL: float = 1e-3


def resolve_fnumber_group(
    aperture_diameter_m: float | None,
    focal_length_m: float | None,
    f_number: float | None,
) -> tuple[float, float, float]:
    """Resolve the ``(D, f, f/#)`` consistency group.

    Exactly two of the three inputs must be provided; the third is
    derived from ``f/# = f / D``. If all three are provided, they must
    be mutually consistent to within ``FNUMBER_CONSISTENCY_RTOL``.

    Parameters
    ----------
    aperture_diameter_m:
        Clear entrance-pupil diameter in metres. ``> 0`` if provided.
    focal_length_m:
        Effective focal length in metres. ``> 0`` if provided.
    f_number:
        Dimensionless ``f/#``. ``> 0`` if provided.

    Returns
    -------
    (aperture_diameter_m, focal_length_m, f_number)
        The resolved triple, all positive floats.

    Raises
    ------
    ValueError
        If fewer than two inputs are supplied; if any supplied input
        is non-positive; or if all three are supplied but disagree by
        more than ``FNUMBER_CONSISTENCY_RTOL``.
    """
    # Positivity check on whatever was supplied.
    for name, val in (
        ("aperture_diameter_m", aperture_diameter_m),
        ("focal_length_m", focal_length_m),
        ("f_number", f_number),
    ):
        if val is not None and (not math.isfinite(val) or val <= 0.0):
            raise ValueError(
                f"resolve_fnumber_group: {name} = {val} is invalid. "
                f"Must be a positive finite number."
            )

    supplied = sum(v is not None for v in (aperture_diameter_m, focal_length_m, f_number))
    if supplied < 2:
        raise ValueError(
            "resolve_fnumber_group: at least two of "
            "{aperture_diameter_m, focal_length_m, f_number} must be supplied. "
            "The third is derived from f/# = focal_length_m / aperture_diameter_m."
        )

    if supplied == 2:
        if aperture_diameter_m is None:
            assert focal_length_m is not None and f_number is not None
            aperture_diameter_m = focal_length_m / f_number
        elif focal_length_m is None:
            assert aperture_diameter_m is not None and f_number is not None
            focal_length_m = aperture_diameter_m * f_number
        else:
            assert aperture_diameter_m is not None and focal_length_m is not None
            f_number = focal_length_m / aperture_diameter_m
        return float(aperture_diameter_m), float(focal_length_m), float(f_number)

    # All three supplied — verify consistency.
    assert aperture_diameter_m is not None and focal_length_m is not None and f_number is not None
    derived = focal_length_m / aperture_diameter_m
    if not math.isclose(derived, f_number, rel_tol=FNUMBER_CONSISTENCY_RTOL):
        raise ValueError(
            f"resolve_fnumber_group: over-specified and inconsistent. "
            f"focal_length_m / aperture_diameter_m = "
            f"{focal_length_m} / {aperture_diameter_m} = {derived:.6f}, "
            f"but f_number = {f_number:.6f} "
            f"(relative discrepancy "
            f"{abs(derived - f_number) / f_number:.2e} > "
            f"{FNUMBER_CONSISTENCY_RTOL:.0e}). "
            "Remove one of the three inputs or fix the mismatch."
        )
    return float(aperture_diameter_m), float(focal_length_m), float(f_number)
