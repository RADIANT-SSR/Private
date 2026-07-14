"""Tests for the stage-output display-unit table (R-UNITS, Gap 87 workaround).

The GUI's per-stage Outputs readout labels every scalar ``stage_outputs`` value with the
canonical unit this table supplies. These tests pin the contract the readout relies on:
the owner-reported dimensional keys carry their unit, dimensionless numerics map to a bare
``""``, and every entry uses a canonical unit string from ``RADIANT_Conventions.md``.
"""

from __future__ import annotations

from radiant.api.stage_output_units import STAGE_OUTPUT_UNITS, stage_output_unit

# The canonical unit strings the table is allowed to emit (RADIANT_Conventions.md), plus
# ``""`` for a dimensionless numeric. A typo (e.g. "m2" for "m²") would fail this.
_CANONICAL_UNITS = {"", "m", "m²", "sr", "e-", "e-/s", "e-/K", "e-/DN", "DN", "K", "s", "W/m²"}


def test_owner_reported_optics_outputs_carry_their_unit() -> None:
    """The exact keys from the owner screenshot: A_collect → m², Omega_pixel → sr."""
    assert stage_output_unit("optics", "A_collect") == "m²"
    assert stage_output_unit("optics", "Omega_pixel") == "sr"


def test_electron_rate_is_electrons_per_second() -> None:
    """e_rate_per_s is an electron rate (e-/s), not a bare inverse-second."""
    assert stage_output_unit("spectral_integration", "e_rate_per_s") == "e-/s"


def test_readout_gain_and_dn_units() -> None:
    """Digital-number outputs and gain use DN / e-/DN (Conventions §charge)."""
    assert stage_output_unit("readout", "signal_dn_final") == "DN"
    assert stage_output_unit("readout", "gain_e_per_dn") == "e-/DN"
    # A mid-key unit token the old suffix logic missed (ends in _final, not _e).
    assert stage_output_unit("readout", "signal_e_final") == "e-"


def test_dimensionless_numerics_map_to_empty_string() -> None:
    """Fractions/ratios render as a bare number (no bogus unit)."""
    assert stage_output_unit("platform", "EE_box") == ""
    assert stage_output_unit("spectral_integration", "qe_scalar") == ""
    assert stage_output_unit("readout", "well_fill_fraction") == ""


def test_unknown_key_returns_empty_string() -> None:
    """An unlisted (stage, key) is honest: bare number, never a guessed unit."""
    assert stage_output_unit("optics", "does_not_exist") == ""
    assert stage_output_unit("no_such_stage", "A_collect") == ""


def test_every_table_entry_uses_a_canonical_unit_string() -> None:
    """Guard against a typo'd unit (e.g. 'm2' instead of 'm²')."""
    for (stage, key), unit in STAGE_OUTPUT_UNITS.items():
        assert unit in _CANONICAL_UNITS, f"{stage}.{key} has non-canonical unit {unit!r}"
