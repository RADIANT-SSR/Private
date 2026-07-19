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
_SYNTHETIC_B1 = _REPO_ROOT / "modtran" / "synthetic" / "B1.synthetic.tp7"

BAND_MIN, BAND_MAX = 3.5, 5.0


def _write_named_header_tape7(path: Path, n_points: int = 60, trans_scale: float = 1.0) -> None:
    """Hand-authored IEMSCT=2-style tape7 with a named column header."""
    nu = np.linspace(5000.0, 2000.0, n_points)  # descending cm-1 → 2–5 µm
    trans = trans_scale * (0.5 + 0.4 * np.exp(-(((nu - 3500.0) / 900.0) ** 2)))
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
    path.write_text("\n".join(lines), encoding="utf-8")


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


def _run_chain(
    atmosphere_overrides: dict[str, object],
    record: list[warnings.WarningMessage] | None = None,
) -> ChainResult:
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
    with warnings.catch_warnings(record=True) as caught:
        # The parity tests ignore the (identical) two-leg-collapse
        # UserWarning both routes emit; the sun-leg tests pass `record`
        # to assert on exactly which warnings fired.
        warnings.simplefilter("always" if record is not None else "ignore", UserWarning)
        result = session.run(p)
    if record is not None:
        record.extend(caught)
    return result


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


@pytest.mark.level2
class TestTape7SunLegImport:
    """CU-011 file flavor: tape7_sun_path splits tau_sun from tau_up and the
    assembly's direct-solar term consumes the split."""

    def _sun_overrides(self, main: Path, sun: Path | None, tmp_path: Path) -> dict[str, object]:
        overrides: dict[str, object] = {
            "atmosphere.model": "modtran",
            "atmosphere.modtran.tape7_path": str(main),
            "atmosphere.modtran.binary_path": str(tmp_path / "no_modtran_binary"),
            "atmosphere.modtran.allow_fallback": False,
            # T3Mixed target (temperature + emissivity < 1) with a daytime
            # sun at 30 deg: theta_s propagates, so the assembly's
            # direct-solar term rho * tau_sun * E_TOA * cos(theta_s) / pi
            # is live and consumes tau_sun.
            "geometry.solar_zenith_rad": float(np.deg2rad(30.0)),
        }
        if sun is not None:
            overrides["atmosphere.modtran.tape7_sun_path"] = str(sun)
        return overrides

    def test_sun_file_splits_tau_and_feeds_assembly(self, tmp_path: Path) -> None:
        main = tmp_path / "up_leg.tp7"
        _write_named_header_tape7(main)
        # A distinctly more opaque sun leg (slant path): scale the same
        # spectral shape down so the split is unambiguous.
        sun = tmp_path / "sun_leg.tp7"
        _write_named_header_tape7(sun, trans_scale=0.6)

        rec_single: list[warnings.WarningMessage] = []
        result_single = _run_chain(self._sun_overrides(main, None, tmp_path), record=rec_single)
        rec_split: list[warnings.WarningMessage] = []
        result_split = _run_chain(self._sun_overrides(main, sun, tmp_path), record=rec_split)

        # Warning killed with the sun file, kept without it.
        assert any("two-leg" in str(w.message) for w in rec_single)
        assert not any("two-leg" in str(w.message) for w in rec_split)

        atm_single = result_single.stage_outputs["atmosphere"]["atm_quantities"]
        atm_split = result_split.stage_outputs["atmosphere"]["atm_quantities"]

        # Single file: aliased. Two files: split, sun leg from the sun file.
        np.testing.assert_array_equal(atm_single.tau_sun, atm_single.tau_up)
        assert not np.allclose(atm_split.tau_sun, atm_split.tau_up)
        # atol bounds the %12.6f column truncation in the two files;
        # exact 0.6x scaling would need untruncated values.
        np.testing.assert_allclose(
            atm_split.tau_sun, 0.6 * np.asarray(atm_split.tau_up), rtol=0, atol=5e-6
        )
        # Up leg is identical in both runs — only the sun leg changed.
        np.testing.assert_array_equal(atm_split.tau_up, atm_single.tau_up)

        # Assembly consumption: the direct-solar term scales with tau_sun,
        # so the darker sun leg must reduce the collected signal [e-].
        s_single = result_single.stage_outputs["spectral_integration"]["signal_e"]
        s_split = result_split.stage_outputs["spectral_integration"]["signal_e"]
        assert s_split < s_single

    @pytest.mark.skipif(
        not (_SYNTHETIC_A1.exists() and _SYNTHETIC_B1.exists()),
        reason=(
            "modtran/synthetic A1/B1 tape7s not generated (gitignored); "
            "run scripts/generate_synthetic_tape7.py"
        ),
    )
    def test_synthetic_a1_up_b1_sun(self, tmp_path: Path) -> None:
        """A1 (nadir) up leg + B1 (30 deg slant, the designed sun-leg block):
        non-zero theta_s ⇒ tau_sun ≠ tau_up."""
        rec: list[warnings.WarningMessage] = []
        result = _run_chain(self._sun_overrides(_SYNTHETIC_A1, _SYNTHETIC_B1, tmp_path), record=rec)
        assert not any("two-leg" in str(w.message) for w in rec)

        atm = result.stage_outputs["atmosphere"]["atm_quantities"]
        assert not np.allclose(atm.tau_sun, atm.tau_up)
        # The slant (30 deg) sun column is more opaque than the nadir
        # up column wherever the band absorbs at all.
        assert float(np.mean(atm.tau_sun)) < float(np.mean(atm.tau_up))
