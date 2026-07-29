"""GeometryStage exceptions (Rule 15 — actionable, RadiantError-rooted)."""

from __future__ import annotations

from typing import Any

from radiant.core.exceptions import RadiantError


class GeometrySpecificationError(RadiantError):
    """The scene-geometry inputs are over- or under-specified.

    Raised when two input modes imply disagreeing values for the same
    canonical quantity (e.g. ``geometry.path_zenith_rad`` and
    ``geometry.sensor_off_boresight_rad`` both user-set but inconsistent),
    or when mutually exclusive entries are combined
    (``local_solar_time_h`` and ``ltan_h``).
    """

    def __init__(
        self,
        what: str,
        why: str = "",
        action: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        self.what = what
        self.why = why
        self.action = action
        self.context = context or {}
        parts: list[str] = [what]
        if why:
            parts.append(f"Why: {why}")
        if action:
            parts.append(f"Action: {action}")
        super().__init__(" | ".join(parts))
