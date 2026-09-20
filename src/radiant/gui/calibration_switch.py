"""Companion withdrawals for a cal-point mode switch (CU-377 F-07).

``calibration.cal_point_mode`` chooses how the NUC cal points are declared:
blackbody temperatures, or fractions of the scene flux (Gap 122 item 5). The
stage rejects a mixed state (Rule 16 — a set value silently doing nothing is
the CU-093 failure class): under ``flux_fraction`` every temperature-anchored
input is over-specification, and the calibration form hides the other mode's
rows. Before this module a mode flip on a configuration with cal temperatures
set failed on every re-evaluation until each temperature was unset by hand,
and the refusal named only the first (usability-audit F-07 b9). The switch is
now one logical action — set the mode, withdraw the other mode's explicit
inputs — under the Gap 117 companion-reset pattern of
:mod:`radiant.gui.architecture_switch`, undoable as one step.

The temperature-anchored list mirrors ``_validate_flux_mode`` in
``radiant.calibration.stage``; the flux list is that mode's own cal points,
withdrawn on the way back so the temperature mode never carries inert flux
inputs. Literals here because ``radiant.gui`` may import only ``radiant.api``
+ ``radiant.core`` (import rules), as for every stage manifest (CU-120).
"""

from __future__ import annotations

from typing import Final

MODE_DOTPATH: Final[str] = "calibration.cal_point_mode"

#: Rejected as over-specification under ``flux_fraction``.
_TEMPERATURE_ANCHORED: Final[tuple[str, ...]] = (
    "calibration.cal_temp_low_K",
    "calibration.cal_temp_mid_K",
    "calibration.cal_temp_high_K",
    "calibration.source_temp_uncertainty_K",
    "calibration.source_uniformity_K",
    "calibration.band_center_uncertainty_um",
    "calibration.source_emissivity_uncertainty",
)

#: The flux mode's own cal points — inert (hidden) under ``temperature``.
_FLUX_POINTS: Final[tuple[str, ...]] = (
    "calibration.cal_flux_low",
    "calibration.cal_flux_mid",
    "calibration.cal_flux_high",
)


def companion_resets_for(dotpath: str, new_value: object) -> tuple[str, ...]:
    """The dot-paths a switch of *dotpath* to *new_value* withdraws."""
    if dotpath != MODE_DOTPATH:
        return ()
    if new_value == "flux_fraction":
        return _TEMPERATURE_ANCHORED
    if new_value == "temperature":
        return _FLUX_POINTS
    return ()


__all__ = ["MODE_DOTPATH", "companion_resets_for"]
