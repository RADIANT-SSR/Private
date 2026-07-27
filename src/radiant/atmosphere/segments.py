"""Path-segment data contract — the Phase-2 direction-aware atmosphere primitive.

Guardrail **G1** of ``docs/plans/Geometry_Flexibility_Plan.md`` §3.5 forbids
adding new direction-aware products as further flat fields on
:class:`~radiant.atmosphere._quantities.AtmosphericQuantities`.  New products
enter instead as **path-segment composition**: a line of sight is decomposed
into segments, each segment is evaluated independently, and the topology
layer composes them.  This module is the data contract for that primitive —
nothing else.  It performs no physics (Rule 19: one computation, one module;
this file holds zero computations, only the validated types).

Two segment shapes cover every v1.x topology (ADR-0011 §3.2):

``ColumnSegmentSpec``
    A slant column between two distinct altitudes, keyed to the **lower**
    endpoint's zenith angle.  Transmittance is reciprocal (RADIANT_Atmosphere.md
    §4.4) so one ``tau`` serves both travel directions, and the lower-endpoint
    key matches the MODTRAN Card-3 ANGLE convention already implemented
    (``render_tape5``'s ``H1 <= H2`` branch; CU-065).

``LevelArmSpec``
    A constant-altitude arm of a given geometric length.  Its zenith is
    π/2 by construction, which is *inside* the horizon guard band, so it can
    never be expressed as a ``ColumnSegmentSpec`` — the two are genuinely
    different computations with different validity conditions, which is why
    they are separate types rather than one type with a degenerate case.

The evaluated product is :class:`SegmentQuantities`.  Its two radiance fields
are **direction-specific** — that is the whole point of the Phase 2 upgrade:

``L_toward_upper``
    Radiance emerging at the segment's upper end travelling upward — what a
    sensor placed *above* the segment sees.  This is the sense of today's
    ``AtmosphericQuantities.L_path_up``.

``L_toward_lower``
    Radiance emerging at the segment's lower end travelling downward — what a
    sensor placed *below* the segment sees.  This is the **new** up-path
    product that Gap 108 / Gap 109 need (sky radiance, ground-to-air scenes).

Composition (performed by the topology layer, not here) is the usual formal
solution over a partitioned path::

    tau(A ∪ B)            = tau(A) · tau(B)
    L_toward_upper(A ∪ B) = L_toward_upper(A) · tau(B) + L_toward_upper(B)
    L_toward_lower(A ∪ B) = L_toward_lower(B) · tau(A) + L_toward_lower(A)

with ``A`` the lower segment and ``B`` the upper one.

Zero drift
----------
Nothing in this module is imported by any pre-existing evaluate path.  The
eight-field ``AtmosphericQuantities`` contract and every down-looking code
path are untouched; these products are additive and reachable only from the
newly-legal up-looking / level topologies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

import numpy as np

from radiant.atmosphere.protocol import ZENITH_CEILING_RAD
from radiant.core.parameters import ParameterBoundsError

__all__ = [
    "ColumnSegmentSpec",
    "LevelArmSpec",
    "PathSegmentSpec",
    "SegmentQuantities",
    "SegmentDirection",
    "validate_wavelength_grid",
]

# Direction discriminator for the two radiance products.
SegmentDirection: TypeAlias = Literal["toward_upper", "toward_lower"]

# τ ∈ [0, 1] with one-ULP slack either side; energy terms clamped at zero with
# the same slack.  These mirror the tolerances in ``_quantities.py`` — they are
# floating-point slop allowances, not physics parameters.
_TAU_TOLERANCE: float = 1e-12
_ENERGY_NEGATIVE_TOLERANCE: float = 1e-12


# ---------------------------------------------------------------------------
# Segment specifications
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ColumnSegmentSpec:
    """A slant atmospheric column between two altitudes.

    Parameters
    ----------
    h_low_m:
        Lower endpoint altitude above MSL [m].  Must be finite and ``≥ 0``.
    h_high_m:
        Upper endpoint altitude above MSL [m].  Must be finite and
        ``≥ h_low_m``.  Equality is legal and is the exact vacuum limit
        (zero-length segment → ``tau = 1``, ``L = 0``).
    zeta_low_rad:
        Zenith angle of the segment at its **lower** endpoint [rad], measured
        from the local vertical there.  Domain ``[0, ZENITH_CEILING_RAD]``
        (0 – 89.5°).  ``0`` is the vertical column.

    Notes
    -----
    The zenith is keyed to the lower endpoint for two reasons (ADR-0011
    decision 3): it is the endpoint that both travel directions share, and it
    is the angle MODTRAN's Card 3 wants when ``H1 ≤ H2``.

    The upper bound is ``ZENITH_CEILING_RAD`` (89.5°), the existing
    plane-parallel-with-spherical-correction airmass ceiling.  A zenith in the
    sliver ``(89.5°, 90°)`` is *geometrically* admissible — the Phase 1
    horizon guard only warns there for an endpoint-minimum path — but there is
    no trustworthy column airmass in that band, so this spec **refuses**
    rather than returning a plausible-looking wrong number (Rule 17).  A
    near-horizontal path in that sliver is an interior-tangent path and must
    be expressed as a :class:`LevelArmSpec`, which uses the true chord length
    at the mean altitude and carries no airmass at all.
    """

    h_low_m: float
    h_high_m: float
    zeta_low_rad: float

    kind: Literal["column"] = field(default="column", init=False, repr=False)

    def __post_init__(self) -> None:
        _require_finite("ColumnSegmentSpec.h_low_m", self.h_low_m)
        _require_finite("ColumnSegmentSpec.h_high_m", self.h_high_m)
        _require_finite("ColumnSegmentSpec.zeta_low_rad", self.zeta_low_rad)

        if self.h_low_m < 0.0:
            raise ParameterBoundsError(
                what=f"ColumnSegmentSpec.h_low_m = {self.h_low_m} m is negative",
                why="Segment endpoints are altitudes above mean sea level.",
                action="Set h_low_m ≥ 0 m.",
                context={"h_low_m": self.h_low_m},
            )
        if self.h_high_m < self.h_low_m:
            raise ParameterBoundsError(
                what=(
                    f"ColumnSegmentSpec: h_high_m = {self.h_high_m} m is below "
                    f"h_low_m = {self.h_low_m} m"
                ),
                why=(
                    "A column segment is keyed to its LOWER endpoint (ADR-0011 "
                    "decision 3); the endpoints must be ordered so that "
                    "'lower' and 'upper' mean what they say.  Direction is "
                    "carried by which radiance field you read "
                    "(L_toward_upper / L_toward_lower), never by the endpoint "
                    "order."
                ),
                action=(
                    "Swap the two altitudes so h_low_m ≤ h_high_m, and read the "
                    "direction you need off SegmentQuantities."
                ),
                context={"h_low_m": self.h_low_m, "h_high_m": self.h_high_m},
            )
        if self.zeta_low_rad < 0.0 or self.zeta_low_rad > math.pi:
            raise ParameterBoundsError(
                what=(
                    f"ColumnSegmentSpec.zeta_low_rad = {self.zeta_low_rad} rad "
                    f"({math.degrees(self.zeta_low_rad):.4f}°) is outside [0, π]"
                ),
                why="A zenith angle at the lower endpoint lies in [0, π].",
                action="Wrap zeta_low_rad into [0, π] rad.",
                context={"zeta_low_rad": self.zeta_low_rad},
            )
        if self.zeta_low_rad > ZENITH_CEILING_RAD:
            raise ParameterBoundsError(
                what=(
                    f"ColumnSegmentSpec.zeta_low_rad = {self.zeta_low_rad} rad "
                    f"({math.degrees(self.zeta_low_rad):.4f}°) exceeds the column "
                    f"airmass ceiling of {math.degrees(ZENITH_CEILING_RAD):.1f}°"
                ),
                why=(
                    "The column segment integrates a vertical optical depth and "
                    "multiplies by the plane-parallel-with-spherical-correction "
                    "airmass, which loses physical meaning as the path approaches "
                    "the horizontal.  In the sliver just past the ceiling "
                    f"({math.degrees(ZENITH_CEILING_RAD):.1f}°–90°) the geometry "
                    "layer only warns (the Phase 1 endpoint-minimum horizon band), "
                    "but the atmosphere has no trustworthy column there and "
                    "refuses rather than returning a wrong number (Rule 17)."
                ),
                action=(
                    "For a near-horizontal or level path use LevelArmSpec — it "
                    "uses the true chord length at the mean altitude and needs no "
                    "airmass.  Otherwise reduce zeta_low_rad below "
                    f"{math.degrees(ZENITH_CEILING_RAD):.1f}°."
                ),
                context={
                    "zeta_low_rad": self.zeta_low_rad,
                    "zenith_ceiling_rad": ZENITH_CEILING_RAD,
                    "h_low_m": self.h_low_m,
                    "h_high_m": self.h_high_m,
                },
            )

    @property
    def thickness_m(self) -> float:
        """Vertical extent of the segment [m], ``≥ 0``."""
        return self.h_high_m - self.h_low_m


@dataclass(frozen=True)
class LevelArmSpec:
    """A constant-altitude (horizontal) path arm.

    Parameters
    ----------
    altitude_m:
        Altitude of the arm above MSL [m].  Must be finite and ``≥ 0``.
    length_m:
        Geometric path length along the arm [m].  Must be finite and ``≥ 0``.
        Zero length is legal and is the exact vacuum limit.

    Notes
    -----
    The arm is the *interior-tangent* topology of plan §8.3: its lowest point
    is in the middle, not at an endpoint, so the endpoint angular horizon band
    does not apply to it.  The governing guard is the tangent-height
    depression ``Δh ≈ L² / 8 R_E`` enforced upstream in
    :mod:`radiant.core.viewing_triangle`; the ~2 km raise threshold there is
    what bounds the sag this model's constant-density assumption has to
    tolerate (see :mod:`radiant.atmosphere.level_arm`).

    The arm carries **no zenith angle**: at constant altitude the local zenith
    is π/2 everywhere along it, which is inside the column airmass's
    unreliable band.  That is the reason this is a separate type rather than a
    ``ColumnSegmentSpec`` with ``h_low_m == h_high_m``: the two need different
    optical-depth computations (calibrated column integral vs. local
    extinction × true chord length), so per Rule 19 they are different
    modules, and the specs that select them are different types.
    """

    altitude_m: float
    length_m: float

    kind: Literal["level_arm"] = field(default="level_arm", init=False, repr=False)

    def __post_init__(self) -> None:
        _require_finite("LevelArmSpec.altitude_m", self.altitude_m)
        _require_finite("LevelArmSpec.length_m", self.length_m)

        if self.altitude_m < 0.0:
            raise ParameterBoundsError(
                what=f"LevelArmSpec.altitude_m = {self.altitude_m} m is negative",
                why="The arm altitude is measured above mean sea level.",
                action="Set altitude_m ≥ 0 m.",
                context={"altitude_m": self.altitude_m},
            )
        if self.length_m < 0.0:
            raise ParameterBoundsError(
                what=f"LevelArmSpec.length_m = {self.length_m} m is negative",
                why=(
                    "The arm length is a geometric path length.  Direction is "
                    "carried by which radiance field you read, never by the sign "
                    "of the length."
                ),
                action="Set length_m ≥ 0 m (0 m is the exact vacuum limit).",
                context={"length_m": self.length_m},
            )


#: Discriminated union of the two segment shapes.  Narrow on ``.kind``.
PathSegmentSpec: TypeAlias = ColumnSegmentSpec | LevelArmSpec


# ---------------------------------------------------------------------------
# Evaluated segment product
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SegmentQuantities:
    """Evaluated radiometric product of one path segment.

    Parameters
    ----------
    wavelength_um:
        1-D strictly-ascending, strictly-positive wavelength grid [µm].  The
        chain spectral grid.  Carried so the contract can validate that all
        three spectral arrays share it (the same shape-validating rule
        ``AtmosphericQuantities`` applies); it is not an extra physical
        product.
    tau:
        Segment transmittance, dimensionless ∈ [0, 1].  **One** array for the
        segment: transmittance is reciprocal (RADIANT_Atmosphere.md §4.4), so
        the same value applies whichever endpoint the light entered from.
    L_toward_upper:
        Radiance emerging at the segment's upper end travelling upward
        [W/m²/sr/µm].  What a sensor above the segment sees.
    L_toward_lower:
        Radiance emerging at the segment's lower end travelling downward
        [W/m²/sr/µm].  What a sensor below the segment sees.
    provenance:
        Free-form dict of the inputs and intermediate scalars the product was
        built from (Rule: intermediate values inspectable).  Never consumed by
        physics.

    Notes
    -----
    The two radiance fields are different products, not two views of one.
    They differ through the single-scatter phase angle (a photon scattered
    upward and a photon scattered downward leave at supplementary scattering
    angles) and, for optically thick segments, through which end of the
    segment dominates the escaping thermal emission.
    """

    wavelength_um: np.ndarray
    tau: np.ndarray
    L_toward_upper: np.ndarray
    L_toward_lower: np.ndarray
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._validate_grid()
        self._validate_tau()
        self._validate_nonneg("L_toward_upper", self.L_toward_upper)
        self._validate_nonneg("L_toward_lower", self.L_toward_lower)

    # -- validation ----------------------------------------------------

    def _validate_grid(self) -> None:
        lam = np.asarray(self.wavelength_um)
        if lam.ndim != 1:
            raise ParameterBoundsError(
                what=f"SegmentQuantities.wavelength_um must be 1-D, got shape {lam.shape}",
                why="A segment product is a spectral vector keyed by wavelength.",
                action="Pass the 1-D chain wavelength grid.",
                context={"shape": lam.shape},
            )
        if lam.size < 2:
            raise ParameterBoundsError(
                what=(f"SegmentQuantities.wavelength_um needs ≥ 2 samples, got {lam.size}"),
                why="Spectral quantities require a non-trivial wavelength grid.",
                action="Provide at least two wavelength samples.",
                context={"n_samples": int(lam.size)},
            )
        if not np.all(np.diff(lam) > 0.0):
            raise ParameterBoundsError(
                what="SegmentQuantities.wavelength_um must be strictly ascending",
                why="Downstream band integrals and interpolation assume monotone λ.",
                action="Sort the wavelength grid ascending before constructing.",
                context={},
            )
        if np.any(lam <= 0.0):
            raise ParameterBoundsError(
                what="SegmentQuantities.wavelength_um must be strictly positive",
                why="Wavelength is a positive length; λ ≤ 0 has no Planck value.",
                action="Remove non-positive wavelengths from the grid.",
                context={"min_um": float(np.min(lam))},
            )
        shape = lam.shape
        for name in ("tau", "L_toward_upper", "L_toward_lower"):
            arr = np.asarray(getattr(self, name))
            if arr.shape != shape:
                raise ParameterBoundsError(
                    what=(
                        f"SegmentQuantities.{name} shape {arr.shape} does not "
                        f"match wavelength_um shape {shape}"
                    ),
                    why="All spectral fields on a segment product share one grid.",
                    action="Regenerate the field on the chain wavelength grid.",
                    context={"field": name, "shape": arr.shape},
                )

    def _validate_tau(self) -> None:
        a = np.asarray(self.tau)
        lo = float(a.min())
        hi = float(a.max())
        if lo < -_TAU_TOLERANCE or hi > 1.0 + _TAU_TOLERANCE:
            raise ParameterBoundsError(
                what=f"SegmentQuantities.tau out of [0, 1] (min={lo:g}, max={hi:g})",
                why=(
                    "Segment transmittance is a probability of transmission.  "
                    "Values outside [0, 1] mean the optical depth went negative "
                    "— a backend bug, not a clamp target (Rule 17)."
                ),
                action="Inspect the segment evaluator that produced this array.",
                context={"min": lo, "max": hi},
            )

    @staticmethod
    def _validate_nonneg(name: str, arr: np.ndarray) -> None:
        a = np.asarray(arr)
        lo = float(a.min())
        if lo < -_ENERGY_NEGATIVE_TOLERANCE:
            raise ParameterBoundsError(
                what=f"SegmentQuantities.{name} has negative values (min={lo:g})",
                why=(
                    "Emergent spectral radiance must be ≥ 0.  A negative value "
                    "is a physics bug; Rule 17 forbids silent clipping."
                ),
                action=(
                    "Fix the evaluator; if the negativity is floating-point "
                    "cancellation noise, snap to 0 before constructing."
                ),
                context={"field": name, "min": lo},
            )

    # -- convenience ---------------------------------------------------

    def radiance_toward(self, direction: SegmentDirection) -> np.ndarray:
        """Return the radiance field for *direction* [W/m²/sr/µm]."""
        if direction == "toward_upper":
            return self.L_toward_upper
        if direction == "toward_lower":
            return self.L_toward_lower
        raise ParameterBoundsError(
            what=f"SegmentQuantities.radiance_toward: unknown direction {direction!r}",
            why="A segment carries exactly two directional radiance products.",
            action="Pass 'toward_upper' or 'toward_lower'.",
            context={"direction": direction},
        )


# ---------------------------------------------------------------------------
# Shared validation helpers
# ---------------------------------------------------------------------------


def validate_wavelength_grid(wavelength_um: np.ndarray, where: str) -> np.ndarray:
    """Validate and normalise a chain wavelength grid [µm] (Rule 16).

    Returns the grid as a ``float64`` array.  Raises
    :class:`~radiant.core.parameters.ParameterBoundsError` naming *where* if
    the grid is not 1-D, has fewer than two samples, is not strictly
    ascending, or contains a non-positive value.

    Lives with the segment contract because every segment evaluator applies
    exactly this check to exactly this input.
    """
    lam = np.asarray(wavelength_um, dtype=np.float64)
    if lam.ndim != 1:
        raise ParameterBoundsError(
            what=f"{where}: wavelength_um must be 1-D, got shape {lam.shape}",
            why="Segment products are spectral vectors keyed by wavelength.",
            action="Pass the 1-D chain wavelength grid.",
            context={"shape": lam.shape},
        )
    if lam.size < 2:
        raise ParameterBoundsError(
            what=f"{where}: wavelength_um needs ≥ 2 samples, got {lam.size}",
            why="Spectral quantities require a non-trivial wavelength grid.",
            action="Provide at least two wavelength samples.",
            context={"n_samples": int(lam.size)},
        )
    if not np.all(np.diff(lam) > 0.0):
        raise ParameterBoundsError(
            what=f"{where}: wavelength_um must be strictly ascending",
            why="Band integrals and spectral-region lookups assume monotone λ.",
            action="Sort the wavelength grid ascending.",
            context={},
        )
    if np.any(lam <= 0.0):
        raise ParameterBoundsError(
            what=f"{where}: wavelength_um must be strictly positive",
            why="Wavelength is a positive length; λ ≤ 0 has no Planck value.",
            action="Remove non-positive wavelengths from the grid.",
            context={"min_um": float(np.min(lam))},
        )
    return lam


def _require_finite(name: str, value: float) -> None:
    """Raise an actionable error if *value* is NaN or infinite (Rule 16/17)."""
    if not math.isfinite(value):
        raise ParameterBoundsError(
            what=f"{name} = {value} is not finite",
            why=(
                "NaN or infinity in a segment specification propagates silently "
                "through every downstream radiometric product (Rule 17)."
            ),
            action=f"Supply a finite value for {name}.",
            context={"field": name, "value": value},
        )
