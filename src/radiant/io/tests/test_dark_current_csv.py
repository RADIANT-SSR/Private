"""Level 0 tests for radiant.io.dark_current_csv (Gap: scenario 2.1).

Anchors are hand calculations (Rule 18):

- Current-density conversion: J = 1e-9 A/cm² on a 20 µm pixel:
  A_pix = (20e-4 cm)² = 4e-6 cm² → I = 4e-15 A →
  N = I / q = 4e-15 / 1.602176634e-19 = 24,966.03 e⁻/s.
- Arrhenius interpolation: ln(J) linear in 1/T. Points
  (60 K, 1e-10) and (80 K, 1e-8): at 1/T = midpoint (T = 480/7 K),
  J = geometric mean = 1e-9 A/cm².
"""

from __future__ import annotations

from pathlib import Path

import pytest

from radiant.io.dark_current_csv import (
    DarkCurrentCsvParseError,
    DarkCurrentCurve,
    load_dark_current_csv,
)

PITCH_20UM_M = 20.0e-6


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


class TestLoad:
    def test_vendor_format(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "jdark.csv",
            "T_K,Jdark_A_cm2\n60,1e-10\n77,2.5e-9\n90,4e-8\n",
        )
        curve = load_dark_current_csv(p)
        assert curve.temperature_K == pytest.approx([60.0, 77.0, 90.0], rel=1e-12)
        assert curve.j_dark_A_cm2 == pytest.approx([1e-10, 2.5e-9, 4e-8], rel=1e-12)
        assert curve.n_points == 3

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(DarkCurrentCsvParseError, match="does not exist"):
            load_dark_current_csv(tmp_path / "nope.csv")

    def test_nonpositive_jdark_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "bad.csv", "T_K,J\n60,0.0\n77,1e-9\n")
        with pytest.raises(DarkCurrentCsvParseError, match="positive"):
            load_dark_current_csv(p)

    def test_nonpositive_temperature_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "bad.csv", "T_K,J\n0,1e-10\n77,1e-9\n")
        with pytest.raises(DarkCurrentCsvParseError, match="positive"):
            load_dark_current_csv(p)


class TestConversion:
    def test_current_density_to_rate_hand_anchor(self, tmp_path: Path) -> None:
        """1e-9 A/cm² on a 20 µm pixel → 24,966.03 e⁻/s (hand anchor)."""
        p = _write(tmp_path, "j.csv", "T_K,J\n70,1e-9\n80,1e-9\n")
        curve = load_dark_current_csv(p)
        rate = curve.dark_rate_e_per_s(75.0, pixel_pitch_m=PITCH_20UM_M)
        assert rate == pytest.approx(24966.03, rel=1e-6)

    def test_rate_scales_with_pixel_area(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "j.csv", "T_K,J\n70,1e-9\n80,1e-9\n")
        curve = load_dark_current_csv(p)
        r20 = curve.dark_rate_e_per_s(75.0, pixel_pitch_m=20.0e-6)
        r10 = curve.dark_rate_e_per_s(75.0, pixel_pitch_m=10.0e-6)
        assert r20 == pytest.approx(4.0 * r10, rel=1e-12)


class TestInterpolation:
    def test_arrhenius_midpoint(self, tmp_path: Path) -> None:
        """ln(J) linear in 1/T: geometric-mean J at the 1/T midpoint."""
        p = _write(tmp_path, "j.csv", "T_K,J\n60,1e-10\n80,1e-8\n")
        curve = load_dark_current_csv(p)
        t_mid = 480.0 / 7.0  # 1/T midpoint of 1/60 and 1/80
        j = curve.j_dark_at(t_mid)
        assert j == pytest.approx(1e-9, rel=1e-9)

    def test_exact_node_values(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "j.csv", "T_K,J\n60,1e-10\n77,2.5e-9\n90,4e-8\n")
        curve = load_dark_current_csv(p)
        assert curve.j_dark_at(77.0) == pytest.approx(2.5e-9, rel=1e-12)

    def test_out_of_range_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "j.csv", "T_K,J\n60,1e-10\n80,1e-8\n")
        curve = load_dark_current_csv(p)
        with pytest.raises(DarkCurrentCsvParseError, match="outside the measured"):
            curve.j_dark_at(100.0)

    def test_temperature_at_rate_inverse(self, tmp_path: Path) -> None:
        """temperature_at_rate inverts dark_rate_e_per_s on the curve."""
        p = _write(tmp_path, "j.csv", "T_K,J\n60,1e-10\n80,1e-8\n")
        curve = load_dark_current_csv(p)
        rate_at_70 = curve.dark_rate_e_per_s(70.0, pixel_pitch_m=PITCH_20UM_M)
        t = curve.temperature_at_rate(rate_at_70, pixel_pitch_m=PITCH_20UM_M)
        assert t == pytest.approx(70.0, rel=1e-9)

    def test_temperature_at_rate_outside_range_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "j.csv", "T_K,J\n60,1e-10\n80,1e-8\n")
        curve = load_dark_current_csv(p)
        with pytest.raises(DarkCurrentCsvParseError, match="outside"):
            curve.temperature_at_rate(1e12, pixel_pitch_m=PITCH_20UM_M)


class TestRoundTrip:
    def test_to_dict_from_dict(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "j.csv", "T_K,J\n60,1e-10\n80,1e-8\n")
        curve = load_dark_current_csv(p)
        clone = DarkCurrentCurve.from_dict(curve.to_dict())
        assert clone.temperature_K == pytest.approx(curve.temperature_K, rel=1e-15)
        assert clone.j_dark_A_cm2 == pytest.approx(curve.j_dark_A_cm2, rel=1e-15)
