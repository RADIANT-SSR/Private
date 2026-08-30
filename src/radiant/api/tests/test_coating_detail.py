"""Tests for the Gap 116 single-element coating detail figure."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")

from radiant.api import Sensor, plot_coating_detail
from radiant.api.errors import ApiValidationError

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"


def _sensor() -> Sensor:
    return Sensor.from_yaml(_EXAMPLE)


def _coating_csv(tmp_path: Path) -> Path:
    """A sloped reflectance curve spanning 3.0-6.0 um (wider than any MWIR band)."""
    grid = np.linspace(3.0, 6.0, 61)
    values = 0.94 + 0.04 * (grid - grid[0]) / (grid[-1] - grid[0])
    path = tmp_path / "ag.csv"
    lines = ["# test coating"] + [f"{w:.4f},{v:.6f}" for w, v in zip(grid, values, strict=True)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _mirror_entry(value: Any) -> dict[str, Any]:
    return {
        "name": "M1",
        "transfer_mode": "REFLECTIVE",
        "reflectance": value,
        "temperature_K": 293.0,
        "diameter_m": 0.3,
        "distance_to_fpa_m": 1.0,
    }


def _title(fig: Any) -> str:
    ax = fig.axes[0]
    return str(ax.get_title() or ax.get_title(loc="left") or ax.get_title(loc="right"))


class TestNativeGrid:
    def test_spectral_source_keeps_full_stored_extent(self, tmp_path: Path) -> None:
        """The point of the detail view: the curve is NOT clipped to the run band."""
        s = _sensor()
        s.set_optical_elements([_mirror_entry(str(_coating_csv(tmp_path)))])
        fig = plot_coating_detail(s, "M1")
        x = fig.axes[0].lines[0].get_xdata()
        assert float(np.min(x)) == pytest.approx(3.0, abs=1e-9)
        assert float(np.max(x)) == pytest.approx(6.0, abs=1e-9)
        assert "native source grid" in _title(fig)

    def test_scalar_falls_back_to_evaluation_band(self) -> None:
        s = _sensor()
        s.set_optical_elements([_mirror_entry(0.97)])
        fig = plot_coating_detail(s, "M1")
        x = fig.axes[0].lines[0].get_xdata()
        lam_min = float(s.get("spectral_integration.filter_min_um"))
        lam_max = float(s.get("spectral_integration.filter_max_um"))
        assert float(np.min(x)) == pytest.approx(lam_min, rel=1e-12)
        assert float(np.max(x)) == pytest.approx(lam_max, rel=1e-12)
        assert "evaluation-band grid" in _title(fig)


class TestPanels:
    def test_mirror_gets_r_and_epsilon_panels_autoscaled(self, tmp_path: Path) -> None:
        """One panel per non-zero quantity, each zoomed to its own data range."""
        s = _sensor()
        s.set_optical_elements([_mirror_entry(str(_coating_csv(tmp_path)))])
        fig = plot_coating_detail(s, "M1")
        assert len(fig.axes) == 2  # R and Kirchhoff epsilon; T === 0 omitted
        r_lo, r_hi = fig.axes[0].get_ylim()
        # R spans 0.94-0.98: the autoscaled axis must sit near it, not at [0, 1.05].
        assert r_lo > 0.9
        assert r_hi < 1.0
        e_lo, e_hi = fig.axes[1].get_ylim()
        assert e_hi < 0.2  # epsilon = 1 - R lives near 0.02-0.06

    def test_simple_refractive_omits_zero_epsilon(self) -> None:
        s = _sensor()
        s.set_optical_elements(
            [
                {
                    "name": "window",
                    "transfer_mode": "REFRACTIVE",
                    "kind": "WINDOW",
                    "transmittance": 0.985,
                    "temperature_K": 240.0,
                    "diameter_m": 0.05,
                    "distance_to_fpa_m": 0.02,
                }
            ]
        )
        fig = plot_coating_detail(s, "window")
        assert len(fig.axes) == 1  # T only: simple refractive has epsilon === 0


class TestErrors:
    def test_unknown_name_lists_available_elements(self) -> None:
        s = _sensor()
        s.set_optical_elements([_mirror_entry(0.97)])
        with pytest.raises(ApiValidationError, match="'M1'"):
            plot_coating_detail(s, "M9")

    def test_no_document_is_actionable(self) -> None:
        with pytest.raises(ApiValidationError, match="set_optical_elements"):
            plot_coating_detail(_sensor(), "M1")


class TestEntriesOverride:
    def test_draft_entries_plot_without_an_attached_document(self) -> None:
        """The GUI passes its unapplied table through `entries=` — no Apply needed."""
        s = _sensor()
        fig = plot_coating_detail(s, "M1", entries=[_mirror_entry(0.97)])
        assert len(fig.axes) == 2
