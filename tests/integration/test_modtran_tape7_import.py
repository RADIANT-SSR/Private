"""Integration: first-class tape7 file import via atmosphere.modtran.tape7_path.

The tape7 import must reproduce the historical side-door exactly: parsing
the same tape7 with Tape7Reader, writing the arrays to full-precision
CSVs, and running atmosphere.model='tabulated'. The data are identical —
only the plumbing differs — so every chain output must match bit-for-bit.

Two fixtures are exercised:
- a hand-authored named-header tape7 (always runs), and
- the run-matrix synthetic tape7 ``modtran/synthetic/A1.synthetic.tp7``
  (skipped when not generated — it is gitignored; regenerate with
  ``python scripts/generate_synthetic_tape7.py``). Synthetic-derived
  numbers are pipeline-exercise data, NOT physics validation
  (modtran/synthetic/README.md).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.atmosphere.modtran import Tape7Reader
from radiant.io.results import ChainResult

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SYNTHETIC_A1 = _REPO_ROOT / "modtran" / "synthetic" / "A1.synthetic.tp7"

BAND_MIN, BAND_MAX = 3.5, 5.0


def _write_named_header_tape7(path: Path, n_points: int = 60) -> None:
    """Hand-authored IEMSCT=2-style tape7 with a named column header."""
    nu = np.linspace(5000.0, 2000.0, n_points)  # descending cm-1 → 2–5 µm
    trans = 0.5 + 0.4 * np.exp(-(((nu - 3500.0) / 900.0) ** 2))
    pth_thrml = 1.0e-6 * (nu / 3000.0) ** 2
    sol_scat = 5.0e-7 * np.ones_like(nu)
    header = (
        "   FREQ   TOT TRANS   PTH THRML   THRML SCT   SURF EMIS   "
        "SOL SCAT   SNGL SCAT   GRND RFLT   DRCT RFLT   TOTAL RAD"
    )
    lines = [header]
    for i in range(n_points):
        lines.append(
            f"{nu[i]:12.2f}{trans[i]:12.6f}{pth_thrml[i]:12.4e}{0.0:12.4e}"
            f"{0.0:12.4e}{sol_scat[i]:12.4e}{0.0:12.4e}{0.0:12.4e}"
            f"{0.0:12.4e}{0.0:12.4e}"
        )
    path.write_text("\n".join(lines))


def _write_side_door_csvs(tape7: Path, tmp_dir: Path) -> tuple[str, str]:
    """The historical side-door: Tape7Reader → full-precision CSVs.

    Full precision (17 significant digits — exact float64 round-trip) so
    any output difference vs. the direct import is attributable to
    plumbing, not CSV truncation.
    """
    wl_um, trans, path_radiance, _ground_reflected = Tape7Reader(tape7).to_radiant_units()
    trans_path = tmp_dir / "side_door_transmittance.csv"
    with trans_path.open("w") as f:
        f.write("wavelength_um,transmittance\n")
        for wl, t in zip(wl_um, trans, strict=True):
            f.write(f"{wl:.17g},{t:.17g}\n")
    radiance_path = tmp_dir / "side_door_path_radiance.csv"
    with radiance_path.open("w") as f:
        f.write("wavelength_um,path_radiance_W_m2_sr_um\n")
        for wl, lp in zip(wl_um, path_radiance, strict=True):
            f.write(f"{wl:.17g},{lp:.17g}\n")
    return str(trans_path), str(radiance_path)


def _run_chain(atmosphere_overrides: dict[str, object]) -> ChainResult:
    wl = np.linspace(BAND_MIN, BAND_MAX, 200)
    session = RadiantSession(wavelength_um=wl)
    p = session.default_params()
    p.set("source.target.temperature", 300.0)
    p.set("source.target.emissivity", 0.95)
    p.set("optics.aperture_diameter_m", 0.15)
    p.set("optics.focal_length_m", 0.5)
    p.set("optics.transmission_scalar", 0.8)
    p.set("detector.pixel_pitch_x_um", 25.0)
    p.set("detector.pixel_pitch_y_um", 25.0)
    p.set("detector.qe_value", 0.6)
    p.set("detector.dark_rate_e_per_s", 1e5)
    p.set("geometry.sensor_altitude_m", 100_000.0)
    p.set("spectral_integration.filter_min_um", BAND_MIN)
    p.set("spectral_integration.filter_max_um", BAND_MAX)
    p.set("spectral_integration.integration_time_s", 0.005)
    p.set("readout.read_noise_e_rms", 30.0)
    p.set("readout.gain_e_per_dn", 20.0)
    p.set("readout.adc_bits", 14)
    for dotpath, value in atmosphere_overrides.items():
        p.set(dotpath, value)
    p.resolve()
    with warnings.catch_warnings():
        # Both routes emit the same two-leg-collapse UserWarning; it is
        # not the subject of this parity test.
        warnings.simplefilter("ignore", UserWarning)
        return session.run(p)


def _assert_parity(tape7: Path, tmp_path: Path) -> None:
    trans_csv, radiance_csv = _write_side_door_csvs(tape7, tmp_path)
    result_import = _run_chain(
        {
            "atmosphere.model": "modtran",
            "atmosphere.modtran.tape7_path": str(tape7),
            # Binary deliberately absent and fallback OFF: the file must win.
            "atmosphere.modtran.binary_path": str(tmp_path / "no_modtran_binary"),
            "atmosphere.modtran.allow_fallback": False,
        }
    )
    result_side_door = _run_chain(
        {
            "atmosphere.model": "tabulated",
            "atmosphere.tabulated_transmittance_file": trans_csv,
            "atmosphere.tabulated_path_radiance_file": radiance_csv,
        }
    )

    tau_import = np.asarray(result_import.stage_outputs["atmosphere"]["tau_atm"])
    tau_side = np.asarray(result_side_door.stage_outputs["atmosphere"]["tau_atm"])
    np.testing.assert_array_equal(tau_import, tau_side)

    lp_import = np.asarray(result_import.stage_outputs["atmosphere"]["L_path"])
    lp_side = np.asarray(result_side_door.stage_outputs["atmosphere"]["L_path"])
    np.testing.assert_array_equal(lp_import, lp_side)

    s_import = result_import.stage_outputs["spectral_integration"]["signal_e"]
    s_side = result_side_door.stage_outputs["spectral_integration"]["signal_e"]
    assert s_import == s_side  # [e-] — exact, identical data through both routes

    assert result_import.metrics["snr"] == result_side_door.metrics["snr"]


@pytest.mark.level2
class TestTape7ImportParity:
    def test_hand_authored_tape7_matches_tabulated_side_door(self, tmp_path: Path) -> None:
        tape7 = tmp_path / "hand_authored.tp7"
        _write_named_header_tape7(tape7)
        _assert_parity(tape7, tmp_path)

    @pytest.mark.skipif(
        not _SYNTHETIC_A1.exists(),
        reason=(
            "modtran/synthetic/A1.synthetic.tp7 not generated (gitignored); "
            "run scripts/generate_synthetic_tape7.py"
        ),
    )
    def test_synthetic_a1_matches_tabulated_side_door(self, tmp_path: Path) -> None:
        _assert_parity(_SYNTHETIC_A1, tmp_path)
