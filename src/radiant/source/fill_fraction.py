"""Sub-pixel fill fraction from projected area and pixel geometry (Gap 97).

The sub-pixel signal mixes ``L_mixed = ff·L_target + (1−ff)·L_bg + L_path``,
where the fill fraction ``ff`` is the target's share of the pixel's instantaneous
field of view. When a target is specified by **radiance + projected area** (the
natural way for a resolved-but-undersampled body) rather than by an abstract
``fill_fraction``, RADIANT must derive ``ff`` from the geometry — otherwise the
projected area is silently ignored and ``ff`` falls back to its schema default of
1.0 (target fills the pixel), producing an extended-scene signal (Gap 97).

This is the exact inverse of the ``RADIANT_Source_Target_System.md`` Path-3
relation ``projected_area = fill_fraction × pixel_solid_angle × range²``:

    ff = Ω_target / Ω_pixel = A_proj / (R² · Ω_pixel),   Ω_pixel = (p_x · p_y)/f²

so that ``ff · Ω_pixel = A_proj / R² = Ω_target`` reproduces the point-source
solid angle exactly (``Ω_pixel`` here is the same one OpticsStage publishes and
SpectralIntegrationStage multiplies by — ``optics/aperture.py``). It clamps to
1.0 when the target overfills the pixel (angular area ≥ pixel solid angle).
"""

from __future__ import annotations


def fill_fraction_from_area(
    projected_area_m2: float,
    range_m: float,
    pixel_pitch_x_m: float,
    pixel_pitch_y_m: float,
    focal_length_m: float,
) -> float | None:
    """Areal fill fraction of a projected area within one pixel's IFOV footprint.

    Parameters
    ----------
    projected_area_m2:
        Target area facing the observer [m²].
    range_m:
        Observer→target distance [m].
    pixel_pitch_x_m, pixel_pitch_y_m:
        Detector pixel pitches [m]; their product over ``focal_length²`` is the
        pixel solid angle ``Ω_pixel`` (same convention as ``optics/aperture.py``).
    focal_length_m:
        System focal length [m].

    Returns
    -------
    float | None
        Fill fraction in ``(0, 1]`` — clamped to 1.0 when the target overfills
        the pixel. ``None`` when the geometry is insufficient to define it
        (non-positive area, range, pitch, or focal length), so the caller can
        fall back to the explicit ``fill_fraction`` parameter.
    """
    if (
        projected_area_m2 <= 0.0
        or range_m <= 0.0
        or pixel_pitch_x_m <= 0.0
        or pixel_pitch_y_m <= 0.0
        or focal_length_m <= 0.0
    ):
        return None
    omega_pixel = (pixel_pitch_x_m * pixel_pitch_y_m) / (focal_length_m * focal_length_m)
    omega_target = projected_area_m2 / (range_m * range_m)
    return min(1.0, omega_target / omega_pixel)
