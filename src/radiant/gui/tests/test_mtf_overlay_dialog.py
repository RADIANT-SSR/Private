"""Tests for the measured-MTF overlay dialog (Tier-2 GT-5 / GUI-4)."""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.widgets.mtf_overlay_dialog import MtfOverlayDialog  # noqa: E402

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture(scope="module")
def result():  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Sensor.from_yaml(_EXAMPLE).evaluate()


def _measured_csv(tmp_path: Path, result) -> Path:  # type: ignore[no-untyped-def]
    """Synthesize measured points ON the predicted curve (residual ≈ 0 anchor)."""
    # Use the system curve via the comparison itself: sample mid-band frequencies
    # and write predicted values as the "measurement".
    from radiant.api import compare_mtf
    from radiant.api.config_io import load_measured_curve_file  # noqa: F401

    # Two-pass trick: first write arbitrary frequencies with MTF=0.5, compare to
    # learn the predicted values, then rewrite the file with those values.
    freqs = np.array([5.0, 10.0, 20.0])  # cy/mm — mid-band for an 18 µm pitch
    path = tmp_path / "measured_mtf.csv"
    path.write_text("\n".join(f"{f:g},0.5" for f in freqs) + "\n", encoding="utf-8")
    curve = load_measured_curve_file(path)
    cmp0 = compare_mtf(result, curve, axis="x", frequency_unit="cy/mm")
    path.write_text(
        "\n".join(f"{f:g},{p:.8f}" for f, p in zip(freqs, cmp0.predicted, strict=True)) + "\n",
        encoding="utf-8",
    )
    return path


class TestOverlay:
    def test_points_on_curve_give_zero_residual(self, qtbot, tmp_path, result) -> None:  # type: ignore[no-untyped-def]
        dialog = MtfOverlayDialog(result)
        qtbot.addWidget(dialog)
        dialog._freq_unit.setCurrentText("cy/mm")  # noqa: SLF001
        path = _measured_csv(tmp_path, result)
        assert dialog.load_path(str(path))
        assert dialog.comparison is not None
        assert dialog.comparison.n_compared == 3
        assert dialog.comparison.rms_residual == pytest.approx(0.0, abs=1e-6)
        assert "RMS residual" in dialog.status_text

    def test_unparseable_file_reports_inline(self, qtbot, tmp_path, result) -> None:  # type: ignore[no-untyped-def]
        bad = tmp_path / "junk.csv"
        bad.write_text("no,numbers,here\n", encoding="utf-8")
        dialog = MtfOverlayDialog(result)
        qtbot.addWidget(dialog)
        assert not dialog.load_path(str(bad))
        assert "failed" in dialog.status_text
        assert dialog.comparison is None
