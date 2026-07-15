"""Canonical display units for the scalar ``stage_outputs`` a GUI/CLI renders.

RADIANT stage outputs are *computed* quantities, not parameters, so — unlike the
``_schema.py`` :class:`~radiant.core.parameters.ParameterDef` surface — they carry no
per-field unit metadata (Gap 87 notes there is no per-output unit accessor). Yet the
owner's R-UNITS hard rule requires every displayed numeric to carry its unit, and the
GUI's per-stage *Outputs* readout must therefore label ``stage_outputs["optics"]
["A_collect"]`` as ``m²`` and ``["Omega_pixel"]`` as ``sr`` rather than as bare numbers.

This module is the **single authoritative source** for those display units: a table keyed
by ``(stage, output_key)`` → canonical unit string, drawn from
``docs/architecture/RADIANT_Conventions.md`` (length **m**, area **m²**, solid angle
**sr**, charge **e-**, temperature **K**, time **s**, digital number **DN**, in-band
irradiance **W/m²**). It covers exactly the finite set of *scalar* outputs the
outputs-bearing stages emit (Source, Optics, Platform, Spectral-Integration, Detector,
Readout — Performance uses the metric registry via :meth:`ChainResult.metric_records`).
The Source rows back the Phase-PS-1 Source-stage Outputs readout (its ``regime_tentative``
enum and ``regime_override`` string need no unit and are rendered unadorned).

The table lists only **dimensional** numerics and the genuinely **dimensionless** ones
(fractions/ratios such as ``EE_box``, ``qe_scalar``, ``well_fill_fraction``,
``scatter_tis``), which map to ``""`` and render as a bare number — matching how the
parameter formatter (:func:`radiant.gui.param_format.format_value`) shows a dimensionless
parameter. Non-numeric outputs (status enums like ``well_status``, mode strings like
``transmission_input_mode``, booleans) are absent: they need no unit and a caller shows
them unadorned. An unlisted key returns ``""`` (honest — a bare number beats a wrong unit).

No unit arithmetic happens here (Rule 2 — this is display metadata only). The longer-term
fix is for each stage to *declare* its output units at the emission site rather than this
central hand-maintained table (tracked as CU-118, aligned with Gap 87).
"""

from __future__ import annotations

from typing import Final

# (stage, output_key) -> canonical unit string (RADIANT_Conventions.md). ``""`` marks a
# genuinely dimensionless numeric (fraction/ratio), rendered as a bare number. Grouped by
# stage; keys mirror the ``with_stage_output(...)`` sites in each stage's ``stage.py``.
STAGE_OUTPUT_UNITS: Final[dict[tuple[str, str], str]] = {
    # -- Source ---------------------------------------------------------------
    ("source", "projected_area_m2"): "m²",  # target projected area facing the sensor
    ("source", "range_m"): "m",  # target slant range
    ("source", "fill_fraction"): "",  # in-pixel fill fraction
    ("source", "angular_extent_rad"): "rad",  # target angular extent
    # -- Optics ---------------------------------------------------------------
    ("optics", "A_collect"): "m²",  # clear collecting area
    ("optics", "Omega_pixel"): "sr",  # pixel solid angle
    ("optics", "scatter_tis"): "",  # total integrated scatter — fraction
    # -- Platform -------------------------------------------------------------
    ("platform", "jitter_sigma_x_m"): "m",
    ("platform", "jitter_sigma_y_m"): "m",
    ("platform", "smear_width_m"): "m",
    ("platform", "EE_box"): "",  # ensquared-energy fraction
    # -- Spectral integration -------------------------------------------------
    ("spectral_integration", "signal_e"): "e-",
    ("spectral_integration", "e_rate_per_s"): "e-/s",
    ("spectral_integration", "background_e"): "e-",
    ("spectral_integration", "contrast_e"): "e-",
    ("spectral_integration", "contrast_reference_signal_e"): "e-",
    ("spectral_integration", "ds_dt_e_per_K"): "e-/K",
    ("spectral_integration", "nearfield_e"): "e-",
    ("spectral_integration", "stray_e"): "e-",
    ("spectral_integration", "qe_scalar"): "",  # quantum efficiency — fraction
    # -- Detector -------------------------------------------------------------
    ("detector", "signal_e"): "e-",
    ("detector", "background_e"): "e-",
    ("detector", "nearfield_e"): "e-",
    ("detector", "stray_e"): "e-",
    ("detector", "dark_e"): "e-",
    ("detector", "glow_e"): "e-",
    # -- Readout --------------------------------------------------------------
    ("readout", "electronics_sigma_m"): "m",
    ("readout", "contrast_e_final"): "e-",
    ("readout", "signal_e_final"): "e-",
    ("readout", "signal_dn_final"): "DN",
    ("readout", "signal_dn_pre_coadd"): "DN",
    ("readout", "gain_e_per_dn"): "e-/DN",
    ("readout", "well_fill_fraction"): "",  # fraction of full well
    ("readout", "total_well_e"): "e-",
    ("readout", "full_well_capacity_e"): "e-",
    ("readout", "sigma_temporal_e"): "e-",
    ("readout", "sigma_spatial_e"): "e-",
    ("readout", "sigma_total_e"): "e-",
    ("readout", "read_noise_e"): "e-",
    ("readout", "quantization_noise_e"): "e-",
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
