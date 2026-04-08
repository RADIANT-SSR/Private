"""Parameter definitions for the source stage.

Only the subset needed by :mod:`radiant.source.blackbody` and
:mod:`radiant.source.emitted` (task 2B.1) is defined here. Additional
parameters for reflected-solar, background, and point-source variants
will be added by later Phase 2 tasks.
"""

from __future__ import annotations

from radiant.core.parameters import ParameterDef

# ---------------------------------------------------------------------------
# Target thermal parameters
# ---------------------------------------------------------------------------

TARGET_TEMPERATURE = ParameterDef(
    name="source.target.temperature",
    description="Target surface kinetic temperature (blackbody / graybody).",
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=300.0,
    bounds=(0.0, 5000.0),
    tags=frozenset({"thermal", "source", "target"}),
    default_justification=(
        "300 K is Earth ambient — a neutral default for terrestrial thermal "
        "imaging scenarios. User overrides for specific scenes."
    ),
)

TARGET_EMISSIVITY = ParameterDef(
    name="source.target.emissivity",
    description=(
        "Scalar target emissivity used when no spectral emissivity table is "
        "supplied. Graybody approximation: ε(λ) = const."
    ),
    dtype=float,
    canonical_unit="",  # dimensionless
    input_unit="",
    default=0.95,
    bounds=(0.0, 1.0),
    tags=frozenset({"thermal", "source", "target"}),
    default_justification=(
        "0.95 is typical for painted / oxidized natural surfaces in the LWIR "
        "and a conservative non-unity default."
    ),
)


ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    TARGET_TEMPERATURE,
    TARGET_EMISSIVITY,
)
