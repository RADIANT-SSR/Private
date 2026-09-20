"""One explicit door per geometry family — the resolve-time seam (CU-377).

One computation, one module (Rule 19): a pure provenance read over the
ADR-0006 manifest (:mod:`radiant.geometry.mode_manifest`) that refuses a
parameter set holding explicit inputs in **two doors of one family** — or both
hour-angle entries of the S3 site-and-time door (``ltan_h`` and
``local_solar_time_h``, mode-resolution rule 5).

It is deliberately stricter than the resolvers. ``resolve_viewing`` /
``resolve_solar`` tolerate two doors that *agree* (ADR-0006 rule 2 — a
redundant, consistent entry is accepted at Evaluate and labelled
"(consistent)"). The GUI contract ratified for CU-377 is one door per family:
the family's mode selector is the switch, and a second door entered outside it
is refused *at the door*, before the operator is wedged between two explicit
values that can only be untangled one reset at a time (usability-audit F-05).
Exposed to view layers as :meth:`radiant.api.sensor.Sensor.validate_geometry_modes`
and applied differentially by the GUI's edit guard (only a conflict an edit
*introduces* is a rejection — a config file that carries an agreeing pair
still evaluates).

No physics, no file I/O, no mutation, and no resolve: the read works on a
half-entered configuration, which is exactly when the GUI needs it.
"""

from __future__ import annotations

from radiant.core.parameters import ParameterSet, Provenance
from radiant.geometry.errors import GeometrySpecificationError
from radiant.geometry.mode_manifest import MODE_FAMILIES, GeometryModeFamily

__all__ = ["validate_mode_doors"]

_NOT_EXPLICIT: frozenset[Provenance] = frozenset({Provenance.DEFAULT, Provenance.DERIVED})

#: The S3 door's two mutually exclusive hour-angle entries (mode-resolution rule 5).
_S3_HOUR_ANGLE = ("geometry.local_solar_time_h", "geometry.ltan_h")


def _explicit(params: ParameterSet) -> set[str]:
    """Dot-paths holding an explicit (user / config / preset / sampled) input."""
    return {
        name
        for name, provenance in params.input_provenances().items()
        if provenance not in _NOT_EXPLICIT
    }


def _open_doors(family: GeometryModeFamily, explicit: set[str]) -> list[tuple[str, str]]:
    """``(mode_key, dot-path)`` for every explicit input among the family's doors."""
    return [
        (mode.key, dotpath)
        for mode in family.modes
        for dotpath in mode.params
        if dotpath in explicit
    ]


def validate_mode_doors(params: ParameterSet) -> None:
    """Raise if any geometry family holds explicit inputs in more than one door.

    Raises
    ------
    GeometrySpecificationError
        Naming the family and every conflicting parameter (each one a
        ``context`` key, so a locator can map the error to its family); or the
        ``ltan_h`` / ``local_solar_time_h`` pair inside the S3 door. A no-op
        otherwise.
    """
    explicit = _explicit(params)
    for family in MODE_FAMILIES:
        opened = _open_doors(family, explicit)
        modes = list(dict.fromkeys(mode_key for mode_key, _ in opened))
        if len(modes) > 1:
            names = [dotpath for _, dotpath in opened]
            listed = " and ".join(names) if len(names) == 2 else ", ".join(names)
            raise GeometrySpecificationError(
                what=(
                    f"Two {family.key} doors are set: {listed} — they are different "
                    "entries for the same quantity"
                ),
                why=(
                    f"The {family.key} family takes exactly one input mode; a second "
                    "explicit door leaves two values to reconcile on every evaluation."
                ),
                action=(
                    f"Switch doors with the {family.key} mode selector on the Geometry "
                    "screen (it withdraws the other door's value), or reset all but one "
                    "of these parameters."
                ),
                context={dotpath: params.inputs().get(dotpath) for dotpath in names},
            )
    if all(name in explicit for name in _S3_HOUR_ANGLE):
        lst, ltan = _S3_HOUR_ANGLE
        raise GeometrySpecificationError(
            what=(
                f"Both {ltan} and {lst} are set — they are mutually exclusive entries "
                "for the same quantity"
            ),
            why=(
                "LTAN is converted to local solar time internally; providing both "
                "over-specifies the sun's hour angle."
            ),
            action=(
                "Pick one on the site-and-time card (local solar time, or LTAN for a "
                "sun-synchronous orbit) — the toggle withdraws the other — or reset one."
            ),
            context={name: params.inputs().get(name) for name in _S3_HOUR_ANGLE},
        )
