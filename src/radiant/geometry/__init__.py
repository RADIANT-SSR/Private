"""radiant.geometry — Stage 0: scene geometry (ADR-0006).

Owns the ``geometry.*`` parameter namespace, resolves the user's chosen
input mode (V0–V4/V6 viewing, S0–S3 solar) to the canonical internal
representation, and publishes every derived geometric quantity exactly
once via ``stage_outputs["geometry"]``.
"""

from radiant.geometry.errors import GeometrySpecificationError as GeometrySpecificationError
from radiant.geometry.stage import GeometryStage as GeometryStage
