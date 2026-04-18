"""Access area rate — ground area covered per unit time.

    access_rate = swath_width × ground_speed
"""

from __future__ import annotations


def compute_access_rate_m2_s(swath_width_m: float, ground_speed_m_s: float) -> float:
    """Area coverage rate [m²/s].

    Parameters
    ----------
    swath_width_m : float
        Swath width at ground [m].
    ground_speed_m_s : float
        Ground-track speed [m/s].

    Returns
    -------
    float
        Access area rate in m²/s.
    """
    return swath_width_m * ground_speed_m_s
