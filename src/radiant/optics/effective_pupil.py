"""Effective pupil — the cold stop as a slightly undersized aperture stop (Gap 128).

A cooled instrument's cold stop **is** the system aperture stop. It is built
slightly smaller than the geometric primary so that alignment and thermal
tolerances cannot let the FPA see past it to warm structure. That single
physical fact has one modelling consequence: the pupil the system actually
works with is smaller than the primary, and *everything* derived from the
pupil must use the smaller one —

- ``A_collect``           [m²]  — signal scales as the effective clear area,
- ``N_eff = f / D_eff``   [-]   — the working f/#,
- the complex pupil function   — diffraction PSF **and** MTF (Rule 4: one
  pupil, both spatial paths),
- ``Ω_cone``              [sr]  — the étendue cone the FPA accepts, and hence
  the warm-optics near-field (``etendue_cone.py``).

Signal and near-field therefore scale together, as they physically do:
undersizing buys tolerancing margin and costs photons.

Owner-ratified model rules (2026-09-09, `docs/plans/Nearfield_Etendue_Model.md`
§2 rule 4):

``D_eff = (1 − u) · D_primary``  with ``u = optics.cold_stop_undersize_frac``
``obs_eff = max(ε_primary, ε_cold_stop)``

At the defaults (``u = 0``, ``ε_cold_stop = 0``) the effective pupil is the
primary pupil **bit-for-bit** — ``(1 − 0.0) · D`` and ``max(ε, 0.0)`` are exact
in IEEE-754 — so no existing result moves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from radiant.optics.errors import OpticsValidationError

# Largest undersizing the "slight undersize for tolerancing" model describes.
# At u = 0.5 the stop has already thrown away 75 % of the collecting area; past
# that the parameter is no longer describing a cold stop but a different system.
MAX_UNDERSIZE_FRAC: float = 0.5


@dataclass(frozen=True)
class EffectivePupil:
    """The pupil every downstream computation sees, after the cold stop.

    Attributes
    ----------
    diameter_m:
        Effective clear pupil diameter ``D_eff`` [m].
    obscuration_ratio:
        Effective central obscuration ratio ``obs_eff`` [-], dimensionless.
    f_number:
        Effective (working) f-number ``N_eff = f / D_eff`` [-].
    primary_diameter_m:
        The geometric primary diameter ``D`` [m] this was derived from,
        retained for provenance and reporting.
    undersize_frac:
        The applied fractional pupil-diameter reduction ``u`` [-].
    """

    diameter_m: float
    obscuration_ratio: float
    f_number: float
    primary_diameter_m: float
    undersize_frac: float


def resolve_effective_pupil(
    aperture_diameter_m: float,
    obscuration_ratio: float,
    f_number: float,
    cold_stop_undersize_frac: float,
    cold_stop_obscuration_ratio: float,
) -> EffectivePupil:
    """Derive the effective pupil from the primary plus the two cold-stop terms.

    Parameters
    ----------
    aperture_diameter_m:
        Geometric clear diameter of the primary ``D`` [m]; must be > 0.
    obscuration_ratio:
        Central obscuration of the primary ``ε = D_sec / D`` [-], in [0, 1).
    f_number:
        The primary's f-number ``N = f / D`` [-]; must be > 0. ``optics.f_number``
        always refers to the primary — ``N_eff`` is derived here, never entered.
    cold_stop_undersize_frac:
        ``u`` [-], the fractional reduction of the pupil *diameter* the cold
        stop imposes, in [0, :data:`MAX_UNDERSIZE_FRAC`).
    cold_stop_obscuration_ratio:
        Central obscuration the cold shield imposes [-], in [0, 1). The
        effective obscuration is the larger of this and the primary's.

    Returns
    -------
    EffectivePupil
        ``D_eff`` [m], ``obs_eff`` [-], ``N_eff`` [-].
    """
    if not math.isfinite(aperture_diameter_m) or aperture_diameter_m <= 0.0:
        raise OpticsValidationError(
            f"resolve_effective_pupil: aperture_diameter_m = {aperture_diameter_m} "
            "is invalid. The primary clear diameter must be a positive finite "
            "number in metres."
        )
    if not math.isfinite(f_number) or f_number <= 0.0:
        raise OpticsValidationError(
            f"resolve_effective_pupil: f_number = {f_number} is invalid. "
            "The primary f/# must be a positive finite number."
        )
    if not math.isfinite(cold_stop_undersize_frac) or not (
        0.0 <= cold_stop_undersize_frac < MAX_UNDERSIZE_FRAC
    ):
        raise OpticsValidationError(
            f"resolve_effective_pupil: optics.cold_stop_undersize_frac = "
            f"{cold_stop_undersize_frac} is invalid. It is the fractional "
            f"reduction of the pupil DIAMETER a cold stop imposes for "
            f"tolerancing, so it must satisfy 0 ≤ u < {MAX_UNDERSIZE_FRAC} "
            "(0 = the cold stop matches the primary; 0.05 = a 5 % undersized "
            "stop, which collects (1 − 0.05)² ≈ 90 % of the light)."
        )
    if not math.isfinite(cold_stop_obscuration_ratio) or not (
        0.0 <= cold_stop_obscuration_ratio < 1.0
    ):
        raise OpticsValidationError(
            f"resolve_effective_pupil: optics.cold_stop_obscuration_ratio = "
            f"{cold_stop_obscuration_ratio} is invalid. It is a diameter ratio, "
            "so it must satisfy 0 ≤ ε < 1 (1 would block the pupil entirely)."
        )

    # (1 - 0.0) * D and max(eps, 0.0) are exact at the defaults, so the default
    # effective pupil IS the primary pupil bit-for-bit.
    diameter_eff_m = (1.0 - cold_stop_undersize_frac) * aperture_diameter_m
    obs_eff = max(obscuration_ratio, cold_stop_obscuration_ratio)

    # N_eff = f / D_eff, written as N · (D / D_eff) so that u = 0 reproduces the
    # user's own f/# bit-for-bit (D / D == 1.0 exactly) rather than re-deriving
    # it from f and D, which the consistency group permits to disagree by up to
    # FNUMBER_CONSISTENCY_RTOL.
    f_number_eff = f_number * (aperture_diameter_m / diameter_eff_m)

    return EffectivePupil(
        diameter_m=diameter_eff_m,
        obscuration_ratio=obs_eff,
        f_number=f_number_eff,
        primary_diameter_m=aperture_diameter_m,
        undersize_frac=cold_stop_undersize_frac,
    )
