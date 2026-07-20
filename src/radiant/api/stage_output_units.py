"""Canonical display units for the scalar ``stage_outputs`` a GUI/CLI renders.

RADIANT stage outputs are *computed* quantities, not parameters, so — unlike the
``_schema.py`` :class:`~radiant.core.parameters.ParameterDef` surface — they carry no
per-field unit metadata (Gap 87 notes there is no per-output unit accessor). Yet the
owner's R-UNITS hard rule requires every displayed numeric to carry its unit, and the
GUI's per-stage *Outputs* readout must therefore label ``stage_outputs["optics"]
["A_collect"]`` as ``m²`` and ``["Omega_pixel"]`` as ``sr`` rather than as bare numbers.

Each outputs-bearing stage **declares its own** output units in an ``OUTPUT_UNITS``
mapping next to the ``with_stage_output(...)`` emission sites in its ``stage.py``
(CU-118); this module only **aggregates** those per-stage tables into the flattened
``(stage, output_key)`` → canonical-unit view the GUI/CLI consume. Units follow
``docs/architecture/RADIANT_Conventions.md`` (length **m**, area **m²**, solid angle
**sr**, charge **e-**, temperature **K**, time **s**, digital number **DN**, in-band
irradiance **W/m²**). Covered stages are Source, Optics, Platform, Spectral-Integration,
Detector, Readout — Performance uses the metric registry via
:meth:`ChainResult.metric_records`.
The Source rows back the Phase-PS-1 Source-stage Outputs readout (its ``regime_tentative``
enum and ``regime_override`` string need no unit and are rendered unadorned).

The table lists only **dimensional** numerics and the genuinely **dimensionless** ones
(fractions/ratios such as ``EE_box``, ``qe_scalar``, ``well_fill_fraction``,
``scatter_tis``), which map to ``""`` and render as a bare number — matching how the
parameter formatter (:func:`radiant.gui.param_format.format_value`) shows a dimensionless
parameter. Non-numeric outputs (status enums like ``well_status``, mode strings like
``transmission_input_mode``, booleans) are absent: they need no unit and a caller shows
them unadorned. An unlisted key returns ``""`` (honest — a bare number beats a wrong unit).

No unit arithmetic happens here (Rule 2 — this is display metadata only). Per-stage
declaration keeps each unit next to the code that emits the value (CU-118, aligned with
Gap 87), so a new scalar output's unit is added in the same file as its
``with_stage_output`` call.
"""

from __future__ import annotations

from typing import Final

from radiant.detector.stage import OUTPUT_UNITS as _DETECTOR_UNITS
from radiant.optics.stage import OUTPUT_UNITS as _OPTICS_UNITS
from radiant.platform.stage import OUTPUT_UNITS as _PLATFORM_UNITS
from radiant.readout.stage import OUTPUT_UNITS as _READOUT_UNITS
from radiant.source.stage import OUTPUT_UNITS as _SOURCE_UNITS
from radiant.spectral_integration.stage import OUTPUT_UNITS as _SPECTRAL_UNITS

# Per-stage output-unit tables, each owned and declared by the stage that emits the
# outputs (CU-118) — no longer a central hand-maintained literal here. Aggregated into
# the ``(stage, key)`` view the GUI/CLI consume.
_STAGE_UNIT_TABLES: Final[dict[str, dict[str, str]]] = {
    "source": _SOURCE_UNITS,
    "optics": _OPTICS_UNITS,
    "platform": _PLATFORM_UNITS,
    "spectral_integration": _SPECTRAL_UNITS,
    "detector": _DETECTOR_UNITS,
    "readout": _READOUT_UNITS,
}

# Flattened ``(stage, output_key) -> unit`` view assembled from the per-stage tables.
STAGE_OUTPUT_UNITS: Final[dict[tuple[str, str], str]] = {
    (stage, key): unit
    for stage, table in _STAGE_UNIT_TABLES.items()
    for key, unit in table.items()
}


def stage_output_unit(stage: str, key: str) -> str:
    """Canonical display unit for scalar ``stage_outputs[stage][key]``.

    Returns the canonical unit string from :data:`STAGE_OUTPUT_UNITS`, or ``""`` for a
    dimensionless numeric or any key not in the table. ``""`` renders as a bare number
    (R-UNITS: a bare number is honest for a dimensionless quantity; a *wrong* unit is not,
    so an unlisted key is left unadorned rather than guessed).
    """
    return STAGE_OUTPUT_UNITS.get((stage, key), "")


__all__ = ["STAGE_OUTPUT_UNITS", "stage_output_unit"]
