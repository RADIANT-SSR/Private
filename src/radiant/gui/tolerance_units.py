"""Unit handling for Monte-Carlo tolerance fields (Qt-free, unit-tested directly).

A :class:`~radiant.core.parameters.Tolerance` stores its parameters in the
owning parameter's **input unit**, but the parameter editor shows — and lets the
operator type — values in whatever **display unit** the row is currently using
(the owner's display-unit rule: what you see and what you enter are the same
unit, no mental math). Converting between the two is not one conversion, because
the fields of a tolerance do not all mean the same *kind* of quantity:

============  =============  =========================================
Field         Kind           Conversion
============  =============  =========================================
``std``       difference     scale only — **never** the affine offset
``low``       absolute       the full registry conversion (offset included)
``high``      absolute       the full registry conversion (offset included)
``sigma``     dimensionless  none — it is a shape parameter, not a length
``std_fraction``  dimensionless  none — already a fraction of nominal
============  =============  =========================================

The distinction is load-bearing wherever the dimension is **affine**, which in
RADIANT means temperature (``radiant.core.units._AFFINE_CONVERSIONS``). A
gaussian spread of 1 °C is a spread of 1 K, not 274.15 K: a standard deviation
is a *difference* between two temperatures, and the +273.15 offset cancels. A
uniform tolerance between 20 °C and 30 °C, by contrast, really is between
293.15 K and 303.15 K, because those endpoints are absolute temperatures. Using
one rule for both fields would be wrong for one of them in every affine case.

``sigma`` is dimensionless because :meth:`Tolerance.sample` draws
``lognormal(mean=0, sigma=sigma) * nominal`` — a multiplicative shape parameter
that scales the nominal rather than adding to it, so it carries no unit at all.

Both legs route **through the canonical unit**, exactly as
:func:`radiant.gui.param_format.display_in_unit` does: the multiplicative
registry stores only the display→canonical direction, so the return leg needs
:func:`~radiant.core.units.inverse_convert`. No ad-hoc unit maths lives here.

The difference conversion is obtained as ``f(x) - f(0)``, which strips whatever
additive offset the route applies and leaves the pure scale. For a purely
multiplicative dimension (every non-temperature unit) ``f(0)`` is ``0`` and the
expression reduces to the plain conversion.
"""

from __future__ import annotations

from typing import Final

from radiant.core.units import convert, inverse_convert

#: How each tolerance field transforms under a change of unit.
ABSOLUTE: Final[str] = "absolute"
DIFFERENCE: Final[str] = "difference"
DIMENSIONLESS: Final[str] = "dimensionless"

#: Field name -> kind. Covers every key :class:`Tolerance` accepts, including
#: ``std_fraction`` (which the editor does not surface today but the engine does).
FIELD_KINDS: Final[dict[str, str]] = {
    "std": DIFFERENCE,
    "low": ABSOLUTE,
    "high": ABSOLUTE,
    "sigma": DIMENSIONLESS,
    "std_fraction": DIMENSIONLESS,
}


def field_kind(field: str) -> str:
    """The unit-transformation kind of tolerance *field*.

    An unknown field is treated as :data:`DIMENSIONLESS` — the conservative
    choice, since it leaves the number untouched rather than applying a
    conversion whose correctness is unknown.
    """
    return FIELD_KINDS.get(field, DIMENSIONLESS)


def _reexpress(value: float, from_unit: str, to_unit: str, canonical_unit: str) -> float:
    """*value* re-expressed from *from_unit* to *to_unit*, routed via the canonical unit.

    The multiplicative registry only stores the display→canonical direction, so
    the outbound leg is :func:`~radiant.core.units.inverse_convert`; affine
    (temperature) pairs register both directions and are handled by the same two
    calls. This mirrors :func:`radiant.gui.param_format.display_in_unit`.
    """
    canonical = convert(value, from_unit, canonical_unit)
    return float(inverse_convert(canonical, canonical_unit, to_unit))


def convert_tolerance_value(
    value: float,
    field: str,
    from_unit: str,
    to_unit: str,
    canonical_unit: str,
) -> float:
    """Convert one tolerance *field*'s *value* between units, per its kind.

    Parameters
    ----------
    value:
        The number as entered or as stored.
    field:
        The tolerance parameter name (``"std"`` / ``"low"`` / ``"high"`` /
        ``"sigma"`` / ``"std_fraction"``).
    from_unit, to_unit:
        Source and destination units. Equal units (and empty units, the
        dimensionless case) short-circuit to *value* unchanged.
    canonical_unit:
        The parameter's canonical unit — the hub both legs route through.

    Returns
    -------
    float
        *value* expressed in *to_unit*.

    Raises
    ------
    KeyError
        Propagated from the units registry when either leg is unregistered.
        Callers surface this rather than inventing a conversion (Rule 2).
    """
    kind = field_kind(field)
    if kind is DIMENSIONLESS or from_unit == to_unit or not from_unit or not to_unit:
        return float(value)
    if kind is DIFFERENCE:
        # Strip any additive offset: a spread is a difference of two values, so
        # only the scale survives (1 °C of spread == 1 K of spread).
        zero = _reexpress(0.0, from_unit, to_unit, canonical_unit)
        return _reexpress(float(value), from_unit, to_unit, canonical_unit) - zero
    return _reexpress(float(value), from_unit, to_unit, canonical_unit)


def field_unit_label(field: str, unit: str) -> str:
    """The suffix shown beside a tolerance field's entry box.

    Dimensionless fields get an explanatory suffix rather than a unit, so the
    operator is never left guessing whether a bare number is metres or a ratio.
    A dimensional field in the empty (dimensionless-parameter) unit shows
    nothing — there is no unit to state.
    """
    if field == "sigma":
        return "(shape, ×nominal)"
    if field == "std_fraction":
        return "(fraction of nominal)"
    return unit


__all__ = [
    "ABSOLUTE",
    "DIFFERENCE",
    "DIMENSIONLESS",
    "FIELD_KINDS",
    "field_kind",
    "convert_tolerance_value",
    "field_unit_label",
]
