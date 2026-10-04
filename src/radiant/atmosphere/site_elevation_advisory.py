"""Advisory: a ground sensor on high terrain that left ``site_elevation_m`` at 0 (CU-393).

The converse of :func:`~radiant.atmosphere.cn2_profiles.warn_if_site_elevation_inert`.
That one catches a *declared* elevation that cannot reach the selected profile — the
rarer direction, and the one an analyst notices because they typed something and saw
nothing change. This one catches the default trap, which is commoner and costlier:
the parameter is never typed at all.

``geometry.site_elevation_m`` defaults to 0 m, and the Hufnagel-Valley surface term is
evaluated at ``h - site_elevation_m``. A telescope on a 900 m ridge with the default
left in place therefore has its own boundary layer modelled 900 m *below* it, where the
100 m-scale-height surface term has already decayed to e^-9. The layer drops out of the
Cn² integral and r₀ comes back optimistic — **measured at 2.876× on scenario 10.3**,
which shipped that way for three months while its own walkthrough said the seeing
looked too good.

Why the predicate needs the observer class
------------------------------------------
The altitude test alone is not sufficient, and this is the whole reason the check
needed an owner ruling rather than an implementation. An up-looking **airborne** sensor
over sea-level terrain satisfies "lower endpoint well above 0 m, site elevation 0 m"
exactly as the mountaintop telescope does — and for the aircraft it is *correct*: the
terrain really is at sea level and the boundary layer really is far below it. The two
cases are indistinguishable from altitude alone.

The scene classifier already separates them. Owner ruling 2026-10-04: gate the advisory
on ``observer_class == "ground"``. This follows the CU-391 precedent exactly — scene
class gates the **validation**, never the physics, which is the distinction ADR-0011
decision 8 draws. Nothing here changes a number; it changes whether the analyst is told.
"""

from __future__ import annotations

import warnings
from typing import Final

__all__ = ["GROUND_OBSERVER_CLASS", "SITE_ELEVATION_FLOOR_M", "warn_if_site_elevation_defaulted"]

#: The observer class this advisory applies to. An ``"air"`` or ``"space"`` observer
#: over sea-level terrain satisfies the same altitude test and is correct.
GROUND_OBSERVER_CLASS: Final[str] = "ground"

#: Altitude above which a ground site's own boundary layer is materially lost [m MSL].
#: The HV surface term decays with a 100 m scale height, so at 200 m roughly 86 % of it
#: has already gone; below that the omission is within the model's own uncertainty and
#: the advisory would be noise.
SITE_ELEVATION_FLOOR_M: Final[float] = 200.0

#: The profile that consumes ``geometry.site_elevation_m``. ``"tabulated"`` carries its
#: own site in the measured table and ``"direct"`` has no profile at all, so for those
#: two a defaulted elevation is not a trap — it is irrelevant, which is the existing
#: inert-direction advisory's business.
_HV_PROFILE: Final[str] = "hufnagel_valley"


def warn_if_site_elevation_defaulted(
    *,
    profile_name: str,
    observer_class: str,
    site_elevation_m: float,
    site_elevation_is_default: bool,
    h_site_m: float,
) -> None:
    """Warn when a ground site above the floor leaves ``site_elevation_m`` unset.

    No-op unless every condition holds: the Hufnagel-Valley profile is selected, the
    scene classifier reads the observer as ground-based, the site sits above
    :data:`SITE_ELEVATION_FLOOR_M`, and the elevation is still at its schema default.

    Parameters
    ----------
    profile_name:
        The resolved ``atmosphere.cn2_profile`` selector value.
    observer_class:
        ``stage_outputs["geometry"]["observer_class"]`` — ``"ground"`` / ``"air"`` /
        ``"space"``.
    site_elevation_m:
        The resolved ``geometry.site_elevation_m`` [m MSL].
    site_elevation_is_default:
        True when the parameter carries DEFAULT provenance. Provenance, not value: an
        analyst who deliberately types 0 for a sea-level site has answered the question
        and is not warned, which is the same distinction CU-392's ``is_in_play`` draws.
    h_site_m:
        The ground site's altitude [m MSL] — for a ground observer this is the sensor
        endpoint.
    """
    if profile_name != _HV_PROFILE:
        return
    if observer_class != GROUND_OBSERVER_CLASS:
        return
    if not site_elevation_is_default:
        return
    if site_elevation_m != 0.0:
        return
    if h_site_m <= SITE_ELEVATION_FLOOR_M:
        return

    warnings.warn(
        f"AtmosphereStage: this is a ground-based sensor at {h_site_m:.0f} m MSL, but "
        "geometry.site_elevation_m is still at its 0 m default, so the "
        "Hufnagel-Valley surface layer is being evaluated at sea level — "
        f"{h_site_m:.0f} m below the site. The surface term decays with a 100 m scale "
        "height, so almost all of this site's own near-ground turbulence is dropping "
        "out of the Cn2 integral and the Fried parameter r0 is coming back optimistic "
        "(measured at 2.9x on a 900 m site). Set geometry.site_elevation_m to the "
        "terrain elevation beneath the line of sight. If the terrain really is at sea "
        "level, set it to 0 explicitly and this message stops.",
        UserWarning,
        stacklevel=2,
    )
