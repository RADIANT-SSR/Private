"""Level 0 tests for radiant.io.qe_csv — vendor QE curve import (Gap: scenario 2.1).

Anchors are hand values, not values computed by other RADIANT code
(Rule 18).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.io.qe_csv import QeCsvParseError, QeCurve, load_qe_csv


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


class TestVendorFormats:
    def test_nm_percent_format(self, tmp_path: Path) -> None:
        """InSb vendor format: wavelength_nm, QE_pct → µm, fraction."""
        p = _write(
            tmp_path,
            "insb.csv",
            "wavelength_nm,QE_pct\n3000,70.0\n4000,82.5\n5000,78.0\n",
        )
        curve = load_qe_csv(p)
        assert curve.wavelength_um == pytest.approx([3.0, 4.0, 5.0], rel=1e-12)
        assert curve.qe == pytest.approx([0.70, 0.825, 0.78], rel=1e-12)
        assert curve.n_points == 3

    def test_um_fraction_format(self, tmp_path: Path) -> None:
        """HgCdTe vendor format: lambda_um, quantum_efficiency → unchanged."""
        p = _write(
            tmp_path,
            "hgcdte.csv",
            "lambda_um,quantum_efficiency\n3.0,0.65\n4.2,0.80\n5.2,0.72\n",
        )
        curve = load_qe_csv(p)
        assert curve.wavelength_um == pytest.approx([3.0, 4.2, 5.2], rel=1e-12)
        assert curve.qe == pytest.approx([0.65, 0.80, 0.72], rel=1e-12)

    def test_explicit_units_override_header(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "odd.csv", "x,y\n3000,70\n5000,80\n")
        curve = load_qe_csv(p, wavelength_unit="nm", qe_unit="percent")
        assert curve.wavelength_um == pytest.approx([3.0, 5.0], rel=1e-12)
        assert curve.qe == pytest.approx([0.70, 0.80], rel=1e-12)

    def test_percent_symbol_header(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "pct.csv", "Wavelength (nm),QE [%]\n4000,50\n5000,60\n")
        curve = load_qe_csv(p)
        assert curve.qe == pytest.approx([0.50, 0.60], rel=1e-12)


class TestEvaluate:
    def test_interpolation_midpoint(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "q.csv", "lambda_um,qe\n4.0,0.60\n5.0,0.80\n")
        curve = load_qe_csv(p)
        out = curve.evaluate(np.array([4.5]))
        assert out == pytest.approx([0.70], abs=1e-12)  # linear midpoint

    def test_out_of_range_error_default(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "q.csv", "lambda_um,qe\n4.0,0.6\n5.0,0.8\n")
        curve = load_qe_csv(p)
        with pytest.raises(QeCsvParseError, match="outside the measured"):
            curve.evaluate(np.array([3.5]))

    def test_out_of_range_zero(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "q.csv", "lambda_um,qe\n4.0,0.6\n5.0,0.8\n")
        curve = load_qe_csv(p)
        out = curve.evaluate(np.array([3.5, 4.0, 5.5]), out_of_range="zero")
        assert out == pytest.approx([0.0, 0.6, 0.0], abs=1e-12)

    def test_out_of_range_clamp(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "q.csv", "lambda_um,qe\n4.0,0.6\n5.0,0.8\n")
        curve = load_qe_csv(p)
        out = curve.evaluate(np.array([3.5, 5.5]), out_of_range="clamp")
        assert out == pytest.approx([0.6, 0.8], abs=1e-12)

    def test_band_averaged_qe_flat_curve(self, tmp_path: Path) -> None:
        """A flat QE curve band-averages to itself (hand anchor)."""
        p = _write(tmp_path, "flat.csv", "lambda_um,qe\n3.0,0.75\n5.0,0.75\n")
        curve = load_qe_csv(p)
        assert curve.band_averaged_qe(3.5, 4.5) == pytest.approx(0.75, rel=1e-12)

    def test_band_averaged_qe_linear_ramp(self, tmp_path: Path) -> None:
        """Linear ramp 0.6→0.8 over 4–5 µm: mean over [4, 5] is 0.7."""
        p = _write(tmp_path, "ramp.csv", "lambda_um,qe\n4.0,0.6\n5.0,0.8\n")
        curve = load_qe_csv(p)
        assert curve.band_averaged_qe(4.0, 5.0) == pytest.approx(0.70, rel=1e-9)


class TestValidation:
    def test_qe_above_one_fraction_mode_raises(self, tmp_path: Path) -> None:
        """QE > 1 in fraction mode → actionable error naming qe_unit."""
        p = _write(tmp_path, "bad.csv", "lambda_um,qe\n4.0,70.0\n5.0,80.0\n")
        with pytest.raises(QeCsvParseError, match="qe_unit"):
            load_qe_csv(p)

    def test_negative_qe_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "neg.csv", "lambda_um,qe\n4.0,-0.1\n5.0,0.8\n")
        with pytest.raises(QeCsvParseError, match="negative"):
            load_qe_csv(p)

    def test_ambiguous_wavelength_unit_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "amb.csv", "x,y\n4.0,0.6\n5.0,0.8\n")
        with pytest.raises(QeCsvParseError, match="wavelength_unit"):
            load_qe_csv(p)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(QeCsvParseError, match="does not exist"):
            load_qe_csv(tmp_path / "nope.csv")

    def test_nonpositive_wavelength_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "zero.csv", "lambda_um,qe\n0.0,0.6\n5.0,0.8\n")
        with pytest.raises(QeCsvParseError, match="positive"):
            load_qe_csv(p)


class TestRoundTrip:
    def test_to_dict_from_dict(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "q.csv", "lambda_um,qe\n4.0,0.6\n5.0,0.8\n")
        curve = load_qe_csv(p)
        clone = QeCurve.from_dict(curve.to_dict())
        assert clone.wavelength_um == pytest.approx(curve.wavelength_um, rel=1e-15)
        assert clone.qe == pytest.approx(curve.qe, rel=1e-15)
        assert clone.source_file == curve.source_file
