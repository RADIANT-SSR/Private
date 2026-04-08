"""Parameter definitions for the optics stage (scalar-mode subset).

Only the subset needed by :mod:`radiant.optics.aperture` and
:mod:`radiant.optics.telescope` (task 2B.3) is defined here. The full
RADIANT_Optics.md §10 inventory (WFE, filters, elements, nearfield,
stray light, apodization) will be added by later tasks.

The consistency group for ``(aperture_diameter_m, focal_length_m,
f_number)`` is named ``fnumber`` to match the resolver in
:func:`radiant.optics.aperture.resolve_fnumber_group`.
"""

from __future__ import annotations

from radiant.core.parameters import ParameterDef

# ---------------------------------------------------------------------------
# Aperture geometry
# ---------------------------------------------------------------------------

APERTURE_DIAMETER_M = ParameterDef(
    name="optics.aperture_diameter_m",
    description="Clear entrance-pupil diameter of the primary [m].",
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=None,  # required
    bounds=(1e-4, 20.0),
    group="fnumber",
    tags=frozenset({"optics", "aperture"}),
)

OBSCURATION_RATIO = ParameterDef(
    name="optics.obscuration_ratio",
    description=(
        "Central obscuration ratio ``D_secondary / D_primary``. Defaults to 0 "
        "(unobscured). Must satisfy 0 ≤ ε < 1."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 0.99),
    tags=frozenset({"optics", "aperture"}),
    default_justification="Most operational apertures are unobscured; Cassegrains override.",
)

# ---------------------------------------------------------------------------
# Focal length / f-number consistency group
# ---------------------------------------------------------------------------

FOCAL_LENGTH_M = ParameterDef(
    name="optics.focal_length_m",
    description="Effective focal length of the telescope [m].",
    dtype=float,
    canonical_unit="m",
    input_unit="m",
    default=None,  # required (or derivable from f/# and D)
    bounds=(1e-4, 100.0),
    group="fnumber",
    tags=frozenset({"optics", "aperture"}),
)

F_NUMBER = ParameterDef(
    name="optics.f_number",
    description=(
        "Dimensionless f/# = focal_length_m / aperture_diameter_m. Part of "
        "the {D, f, f/#} consistency group; supply any two and the third "
        "is derived."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=None,  # derived when omitted
    bounds=(0.3, 200.0),
    group="fnumber",
    tags=frozenset({"optics", "aperture"}),
)

# ---------------------------------------------------------------------------
# Scalar transmission (Mode 1 only for 2B.3)
# ---------------------------------------------------------------------------

TRANSMISSION_SCALAR = ParameterDef(
    name="optics.transmission_scalar",
    description=(
        "Flat broadband optical throughput ``τ_opt`` (Mode 1 of "
        "RADIANT_Optics.md §5.1). Dimensionless in [0, 1]."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.7,
    bounds=(0.0, 1.0),
    tags=frozenset({"optics", "throughput"}),
    default_justification=(
        "0.7 is a typical end-to-end broadband throughput for a two-mirror "
        "telescope with an ambient-temperature filter stack, per "
        "RADIANT_Optics.md examples."
    ),
)


ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    APERTURE_DIAMETER_M,
    OBSCURATION_RATIO,
    FOCAL_LENGTH_M,
    F_NUMBER,
    TRANSMISSION_SCALAR,
)
