"""Derived scene class — the observer × target altitude-band label (ADR-0011 decision 8).

The scene class is the 3 × 3 grid of plan §2: the observer's altitude band
crossed with the target's, each in ``{ground, air, space}``, published together
with the (already derived) LOS direction as e.g. ``"ground_to_air"``.

**It is derived, never declared, and physics never branches on it.**  ADR-0011
decision 8 is explicit: the class drives *defaults, metric relevance,
validation, and GUI composition only* — the radiometry stays continuous in the
real inputs (altitudes, θ_o, τ).  Nothing in this module is consulted by a
physics computation; :class:`~radiant.geometry.stage.GeometryStage` publishes
the label into ``stage_outputs["geometry"]`` where non-physics layers (the Gap
96 metric-relevance map, the GUI's mission-type chip) read it as data.

Band boundaries
---------------
======  ==============================  ================================
Band    Altitude range                  Convention source
======  ==============================  ================================
ground  ``h < 1 km``                    classification convention only
air     ``1 km ≤ h ≤ 100 km``           between the two boundaries
space   ``h > 100 km``                  ``h_atm_top`` (Kármán line)
======  ==============================  ================================

The **1 km** floor is a *naming* convention with **no physical effect
whatsoever**: no transmittance, radiance, or geometry term changes as an
altitude crosses it.  It exists so that a tower, a mast, and a rooftop sensor
read as "ground" while an aircraft reads as "air"; a scene at 999 m and one at
1001 m compute identically and differ only in this label.  Both boundaries are
**closed from below**: exactly 1 km is ``air`` (ground is strictly below 1 km)
and exactly 100 km is ``air`` (space is strictly above 100 km), which keeps the
two thresholds consistent with each other and with the ``h_tgt >= h_atm_top``
vacuum carve-out in :class:`~radiant.core.los_geometry.LineOfSightGeometry`
(that carve-out triggers *at* 100 km, where this label still reads ``air`` —
the two are independent by design: one is physics, one is a name).

The **100 km** ceiling is the ``h_atm_top`` convention already used across
RADIANT (``LineOfSightGeometry.h_atm_top`` default = 1.0e5 m ≈ the Kármán
line), so "space" here means exactly "above the modelled atmospheric column".

Optional assertion
------------------
:func:`check_scene_class_assertion` implements the CU-093 redundant-entry
pattern for the optional ``geometry.scene_class`` parameter: a user may
*assert* the class they intend, and a disagreement with the derivation raises
:class:`~radiant.geometry.errors.GeometrySpecificationError` naming asserted
vs. derived and both altitudes.  It catches the wrong-magnitude altitude typo
(``600`` m instead of ``600_000`` m) that pure derivation would otherwise
render as a perfectly self-consistent scene of the wrong class.  The assertion
is **never required** — an unset parameter simply skips the check.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from radiant.core.parameters import ParameterBoundsError
from radiant.geometry.errors import GeometrySpecificationError

__all__ = [
    "ALTITUDE_BANDS",
    "GROUND_CEILING_M",
    "SCENE_CLASSES",
    "SCENE_CLASS_UNSET",
    "SPACE_FLOOR_M",
    "SceneClass",
    "check_scene_class_assertion",
    "classify_altitude",
    "derive_scene_class",
]

#: Top of the ``ground`` band [m] — classification convention, no physics.
GROUND_CEILING_M: Final[float] = 1.0e3

#: Floor of the ``space`` band [m] — the ``h_atm_top`` (Kármán line) convention.
SPACE_FLOOR_M: Final[float] = 1.0e5

#: The three altitude bands, low to high.
ALTITUDE_BANDS: Final[tuple[str, ...]] = ("ground", "air", "space")

#: The nine scene classes, ``"<observer>_to_<target>"``.
SCENE_CLASSES: Final[tuple[str, ...]] = tuple(
    f"{observer}_to_{target}" for observer in ALTITUDE_BANDS for target in ALTITUDE_BANDS
)

#: Inert sentinel value of ``geometry.scene_class`` meaning "derive it".
SCENE_CLASS_UNSET: Final[str] = "auto"


@dataclass(frozen=True, slots=True)
class SceneClass:
    """The derived scene class: both altitude bands plus the LOS direction.

    Attributes
    ----------
    observer_class:
        Altitude band of the sensor — ``"ground"`` / ``"air"`` / ``"space"``.
    target_class:
        Altitude band of the target.
    los_direction:
        ``"down"`` / ``"up"`` / ``"level"`` — carried, not re-derived: it is
        read off :class:`~radiant.core.los_geometry.LineOfSightGeometry` so
        there is exactly one definition of the direction (ADR-0011 decision 1).
    """

    observer_class: str
    target_class: str
    los_direction: str

    @property
    def key(self) -> str:
        """The published label, e.g. ``"ground_to_air"``."""
        return f"{self.observer_class}_to_{self.target_class}"


def classify_altitude(altitude_m: float) -> str:
    """Return the altitude band of *altitude_m* [m].

    ``ground`` below :data:`GROUND_CEILING_M`, ``space`` strictly above
    :data:`SPACE_FLOOR_M`, ``air`` in between (both boundary values inclusive
    of the ``air`` band — see the module docstring).

    Raises
    ------
    ParameterBoundsError
        If the altitude is negative or not finite.
    """
    if not math.isfinite(altitude_m):
        raise ParameterBoundsError(
            what=f"classify_altitude: altitude_m = {altitude_m} is not finite",
            why="An altitude band cannot be assigned to a NaN or infinite altitude.",
            action="Supply a finite altitude in metres above mean sea level.",
            context={"altitude_m": altitude_m},
        )
    if altitude_m < 0.0:
        raise ParameterBoundsError(
            what=f"classify_altitude: altitude_m = {altitude_m} m is negative",
            why="Altitudes are measured above mean sea level and must be non-negative.",
            action="Set the altitude to 0 m (sea level) or above.",
            context={"altitude_m": altitude_m},
        )
    if altitude_m < GROUND_CEILING_M:
        return "ground"
    if altitude_m > SPACE_FLOOR_M:
        return "space"
    return "air"


def derive_scene_class(
    h_sensor_m: float,
    h_target_m: float,
    los_direction: str,
) -> SceneClass:
    """Derive the scene class from the altitude pair and the LOS direction.

    Parameters
    ----------
    h_sensor_m:
        Sensor altitude above MSL [m].
    h_target_m:
        Target altitude above MSL [m].
    los_direction:
        ``"down"`` / ``"up"`` / ``"level"``, as already derived by
        :attr:`~radiant.core.los_geometry.LineOfSightGeometry.los_direction`.
        Passed in rather than re-derived so the two can never disagree.

    Returns
    -------
    SceneClass
        The observer band, the target band, and the direction.
    """
    return SceneClass(
        observer_class=classify_altitude(h_sensor_m),
        target_class=classify_altitude(h_target_m),
        los_direction=los_direction,
    )


def check_scene_class_assertion(
    asserted: str,
    derived: SceneClass,
    h_sensor_m: float,
    h_target_m: float,
) -> None:
    """Validate an optional user assertion against the derivation (CU-093 pattern).

    Parameters
    ----------
    asserted:
        The user's ``geometry.scene_class`` value.  :data:`SCENE_CLASS_UNSET`
        (or an empty string) means "not asserted" and skips the check —
        the assertion is **never** required (ADR-0011 decision 8).
    derived:
        The class derived from the altitudes.
    h_sensor_m, h_target_m:
        The altitudes that produced *derived*, named in the error so the user
        sees which number contradicts the intent.

    Raises
    ------
    GeometrySpecificationError
        If *asserted* is a scene class that differs from the derived one.
    ParameterBoundsError
        If *asserted* is not one of the nine class names (defence in depth —
        the schema enum normally rejects this first).
    """
    if asserted in (SCENE_CLASS_UNSET, ""):
        return
    if asserted not in SCENE_CLASSES:
        raise ParameterBoundsError(
            what=f"geometry.scene_class = {asserted!r} is not a scene class",
            why=(
                "The optional scene-class assertion must name one of the nine "
                "observer-to-target classes of the ADR-0011 taxonomy."
            ),
            action=f"Use one of: {', '.join(SCENE_CLASSES)} (or leave it unset).",
            context={"asserted": asserted, "valid": SCENE_CLASSES},
        )
    if asserted == derived.key:
        return
    raise GeometrySpecificationError(
        what=(
            f"geometry.scene_class asserts {asserted!r}, but the altitudes derive "
            f"{derived.key!r} (sensor {h_sensor_m:.6g} m ⇒ {derived.observer_class}, "
            f"target {h_target_m:.6g} m ⇒ {derived.target_class})"
        ),
        why=(
            "The scene class is derived from the altitude pair; asserting a "
            "different one means an altitude does not describe the scene you "
            "intend (the classic case is a wrong-magnitude entry — 600 m where "
            "600 km was meant — which derives a perfectly self-consistent scene "
            "of the wrong class). The assertion exists precisely to catch that; "
            f"band boundaries: ground < {GROUND_CEILING_M:.0f} m <= air <= "
            f"{SPACE_FLOOR_M:.0f} m < space."
        ),
        action=(
            "Correct the altitude that is in the wrong band, or set "
            "geometry.scene_class to the derived class (or leave it unset — "
            "the assertion is optional)."
        ),
        context={
            "asserted": asserted,
            "derived": derived.key,
            "geometry.sensor_altitude_m": h_sensor_m,
            "geometry.target_altitude_m": h_target_m,
            "observer_class": derived.observer_class,
            "target_class": derived.target_class,
        },
    )
