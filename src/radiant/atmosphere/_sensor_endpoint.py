"""Sensor-endpoint resolution at the atmosphere boundary (guardrail G2).

Since ADR-0011 / Geometry-Flexibility Phase 1 the sensor altitude is carried
on the :class:`~radiant.core.los_geometry.LineOfSightGeometry` contract
published by ``GeometryStage`` (``los.h_sensor``).  **That is the only
source of truth for it inside this package.**  No atmosphere backend reads
``geometry.sensor_altitude_m`` from the :class:`ParameterSet` any more:
guardrail G2 of ``docs/plans/Geometry_Flexibility_Plan.md`` §3.5 deletes
every side-load, because two live sources for one quantity is exactly the
CU-090 / CU-093 disease ADR-0006 cured.

The parameter itself is unchanged — it is still the user-facing input door
(``geometry.sensor_altitude_m``, a required parameter), and ``GeometryStage``
is the one place that reads it and puts it on the LOS.

One computation, one module (Rule 19): resolving the sensor endpoint is the
only thing this module does.
"""

from __future__ import annotations

from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError

__all__ = ["require_sensor_altitude_m"]


def require_sensor_altitude_m(los: LineOfSightGeometry, where: str) -> float:
    """Return the sensor altitude [m] carried by *los*, or raise.

    Parameters
    ----------
    los:
        The line-of-sight geometry published by ``GeometryStage`` (via
        ``SourceStage``'s descriptor adjustment).  Must carry ``h_sensor``.
    where:
        Call-site label used in the error text (e.g.
        ``"SimpleAtmosphere.evaluate"``).

    Raises
    ------
    ParameterBoundsError
        If ``los.h_sensor`` is ``None`` — a pre-ADR-0011 payload that does
        not carry the sensor endpoint.  There is deliberately **no**
        fallback to ``params["geometry.sensor_altitude_m"]``: silently
        reading a second source is what guardrail G2 forbids, and a
        mismatch between the two would be invisible (Rule 17).
    """
    h_sensor = los.h_sensor
    if h_sensor is None:
        raise ParameterBoundsError(
            what=(
                f"{where}: the LineOfSightGeometry does not carry the sensor "
                f"endpoint (h_sensor is None) — h_tgt = {los.h_tgt} m, "
                f"theta_o = {los.theta_o} rad"
            ),
            why=(
                "Since ADR-0011 (Geometry-Flexibility Phase 1) the sensor "
                "altitude travels on the LOS contract, and it is the single "
                "source of truth for every atmosphere backend (plan §3.5 "
                "guardrail G2).  Falling back to "
                "params['geometry.sensor_altitude_m'] here would restore the "
                "two-live-sources failure mode ADR-0006 removed, and a "
                "disagreement between the two would be silent."
            ),
            action=(
                "Run the chain through GeometryStage, which populates "
                "h_sensor from the required geometry.sensor_altitude_m "
                "parameter.  A hand-built test fixture (typically "
                "'los = LineOfSightGeometry(h_tgt=..., theta_o=...)' in a "
                "src/radiant/*/tests/ module) must pass h_sensor=<sensor "
                "altitude in m> explicitly."
            ),
            context={
                "h_sensor": None,
                "h_tgt": los.h_tgt,
                "theta_o": los.theta_o,
                "where": where,
            },
        )
    return float(h_sensor)
