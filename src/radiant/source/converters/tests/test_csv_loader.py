"""Tests for the shared two-column CSV reader in :mod:`_csv`.

Gap G Step G.1 — behavior-preserving refactor.  This suite enumerates
the contract exposed by :func:`load_two_column_csv` so the three path
surfaces wired in G.2 / G.3 (reflectance_path, albedo_path,
brightness_temperature_path) can delegate to it without duplicating
tests.

The existing user_radiance / user_intensity CSV tests re-run unchanged
(test_inferrer_user_radiance.py, test_inferrer_user_intensity.py) —
that's the byte-for-byte behavior-preservation check.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.core.parameters import ParameterBoundsError
from radiant.core.spectral import SpectralData
from radiant.source.converters._csv import load_two_column_csv

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


_DEFAULT_KWARGS = {
    "value_unit": "W/m^2/sr/um",
    "column_label": "L_t_source",
    "sd_name": "source.target.user_radiance",
    "sd_source_prefix": "source.converters.user_radiance",
}


def _write(path: Path, content: str) -> Path:
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# 1. Happy path — no header
# ---------------------------------------------------------------------------


def test_valid_two_column_no_header(tmp_path: Path) -> None:
    csv = _write(tmp_path / "r.csv", "8.0,1.0\n10.0,2.0\n12.0,3.0\n")
    sd = load_two_column_csv(csv, **_DEFAULT_KWARGS)
    assert isinstance(sd, SpectralData)
    np.testing.assert_allclose(sd.wavelength_um, [8.0, 10.0, 12.0])
    np.testing.assert_allclose(sd.values, [1.0, 2.0, 3.0])
    assert sd.unit == "W/m^2/sr/um"
    assert sd.name == "source.target.user_radiance"
    assert "source.converters.user_radiance" in sd.source
    assert str(csv) in sd.source


# ---------------------------------------------------------------------------
# 2. Happy path — auto-detect and skip header
# ---------------------------------------------------------------------------


def test_valid_two_column_with_header(tmp_path: Path) -> None:
    csv = _write(
        tmp_path / "r.csv",
        "wavelength_um,L_t_source\n8.0,1.0\n10.0,2.0\n12.0,3.0\n",
    )
    sd = load_two_column_csv(csv, **_DEFAULT_KWARGS)
    np.testing.assert_allclose(sd.wavelength_um, [8.0, 10.0, 12.0])
    np.testing.assert_allclose(sd.values, [1.0, 2.0, 3.0])


# ---------------------------------------------------------------------------
# 3. Missing file → ParameterBoundsError, path in context
# ---------------------------------------------------------------------------


def test_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.csv"
    with pytest.raises(ParameterBoundsError, match="not found") as exc:
        load_two_column_csv(missing, **_DEFAULT_KWARGS)
    assert exc.value.context["path"] == str(missing)
    assert exc.value.context["column_label"] == "L_t_source"


# ---------------------------------------------------------------------------
# 4. Empty file → ParameterBoundsError
# ---------------------------------------------------------------------------


def test_empty_file_raises(tmp_path: Path) -> None:
    csv = _write(tmp_path / "r.csv", "")
    with pytest.raises(ParameterBoundsError, match="empty") as exc:
        load_two_column_csv(csv, **_DEFAULT_KWARGS)
    assert exc.value.context["path"] == str(csv)


# ---------------------------------------------------------------------------
# 5. Single-row file → ParameterBoundsError (min 2 rows)
# ---------------------------------------------------------------------------


def test_single_row_file_raises(tmp_path: Path) -> None:
    csv = _write(tmp_path / "r.csv", "8.0,1.0\n")
    with pytest.raises(ParameterBoundsError, match="fewer than 2") as exc:
        load_two_column_csv(csv, **_DEFAULT_KWARGS)
    assert exc.value.context["row_count"] == 1


def test_single_row_file_with_header_raises(tmp_path: Path) -> None:
    csv = _write(tmp_path / "r.csv", "wl,val\n8.0,1.0\n")
    with pytest.raises(ParameterBoundsError, match="fewer than 2") as exc:
        load_two_column_csv(csv, **_DEFAULT_KWARGS)
    assert exc.value.context["row_count"] == 1


# ---------------------------------------------------------------------------
# 6. Malformed line (1 column) → ParameterBoundsError with line_number
# ---------------------------------------------------------------------------


def test_malformed_single_column_raises(tmp_path: Path) -> None:
    csv = _write(tmp_path / "r.csv", "8.0,1.0\n10.0\n12.0,3.0\n")
    with pytest.raises(
        ParameterBoundsError, match="fewer than 2 columns"
    ) as exc:
        load_two_column_csv(csv, **_DEFAULT_KWARGS)
    assert exc.value.context["line_number"] == 2


# ---------------------------------------------------------------------------
# 7. Non-float token → ParameterBoundsError with line_number
# ---------------------------------------------------------------------------


def test_nonfloat_token_raises(tmp_path: Path) -> None:
    csv = _write(tmp_path / "r.csv", "8.0,1.0\n10.0,abc\n12.0,3.0\n")
    with pytest.raises(ParameterBoundsError, match="floats") as exc:
        load_two_column_csv(csv, **_DEFAULT_KWARGS)
    assert exc.value.context["line_number"] == 2


def test_nonfloat_wavelength_raises(tmp_path: Path) -> None:
    csv = _write(
        tmp_path / "r.csv", "wl,val\n8.0,1.0\nbad,2.0\n12.0,3.0\n"
    )
    with pytest.raises(ParameterBoundsError, match="floats") as exc:
        load_two_column_csv(csv, **_DEFAULT_KWARGS)
    # Header auto-skipped, so the bad row is file line 3 (1-indexed).
    assert exc.value.context["line_number"] == 3


# ---------------------------------------------------------------------------
# 8. value_unit propagates to SpectralData.unit verbatim
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value_unit",
    ["W/m^2/sr/um", "W/sr/um", "dimensionless", "K"],
)
def test_value_unit_propagates_verbatim(
    tmp_path: Path, value_unit: str
) -> None:
    csv = _write(tmp_path / "r.csv", "8.0,1.0\n10.0,2.0\n")
    kwargs = dict(_DEFAULT_KWARGS)
    kwargs["value_unit"] = value_unit
    sd = load_two_column_csv(csv, **kwargs)
    assert sd.unit == value_unit


# ---------------------------------------------------------------------------
# 9. sd_name and sd_source_prefix propagate
# ---------------------------------------------------------------------------


def test_sd_name_and_source_prefix_propagate(tmp_path: Path) -> None:
    csv = _write(tmp_path / "r.csv", "8.0,1.0\n10.0,2.0\n")
    kwargs = dict(_DEFAULT_KWARGS)
    kwargs["sd_name"] = "my.custom.name"
    kwargs["sd_source_prefix"] = "my.custom.prefix"
    sd = load_two_column_csv(csv, **kwargs)
    assert sd.name == "my.custom.name"
    assert sd.source.startswith("my.custom.prefix")
    assert f"(CSV: {csv!s})" in sd.source


# ---------------------------------------------------------------------------
# Extra — column_label appears in error messages (useful for new callers)
# ---------------------------------------------------------------------------


def test_column_label_in_error_messages(tmp_path: Path) -> None:
    csv = tmp_path / "missing.csv"
    kwargs = dict(_DEFAULT_KWARGS)
    kwargs["column_label"] = "reflectance"
    with pytest.raises(ParameterBoundsError, match="reflectance"):
        load_two_column_csv(csv, **kwargs)


# ---------------------------------------------------------------------------
# String path coercion
# ---------------------------------------------------------------------------


def test_string_path_is_coerced(tmp_path: Path) -> None:
    csv = _write(tmp_path / "r.csv", "8.0,1.0\n10.0,2.0\n")
    sd = load_two_column_csv(str(csv), **_DEFAULT_KWARGS)
    np.testing.assert_allclose(sd.wavelength_um, [8.0, 10.0])
