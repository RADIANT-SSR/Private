"""A cavity's two faces may differ in FORM, not just in value (CU-400).

A real lens routinely carries a measured coating curve on one face and a nominal
number on the other. Structural validation parses an entry on its own native grid, but
a scalar has none — so the handler retried on the generic 0.4-20 µm fallback, which is
wider than any real coating table, and the spectral half then failed to resample onto
it. A structurally valid entry was refused for a band nobody had asked about.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.io.element_config import ElementConfigError, validate_element_entry

_BAND = "3.0,0.0100\n4.0,0.0040\n5.0,0.0120\n"


def _csv(tmp_path: Path, name: str = "ar.csv", text: str = _BAND) -> Path:
    path = tmp_path / name
    path.write_text("# AR coating R(lambda) [-] vs [um]\n" + text, encoding="utf-8")
    return path


def _cavity(**surfaces: object) -> dict[str, object]:
    return {
        "name": "L1",
        "kind": "lens",
        "transfer_mode": "REFRACTIVE",
        "thickness_m": 0.006,
        "alpha": 2.0,
        "temperature_K": 290.0,
        **surfaces,
    }


class TestMixedForms:
    @pytest.mark.level1
    def test_spectral_surface_one_and_scalar_surface_two(self, tmp_path: Path) -> None:
        """The combination the shipped transmission-doors example died on."""
        entry = _cavity(R1=str(_csv(tmp_path)), T2=0.988)
        element = validate_element_entry(entry, base_dir=tmp_path)
        assert element.cavity is not None

    @pytest.mark.level1
    def test_scalar_surface_one_and_spectral_surface_two(self, tmp_path: Path) -> None:
        """Order must not matter: the grid is the entry's, whichever face carries it."""
        entry = _cavity(R1=0.010, R2=str(_csv(tmp_path)))
        assert validate_element_entry(entry, base_dir=tmp_path).cavity is not None

    @pytest.mark.level1
    def test_an_inline_table_supplies_the_grid_too(self, tmp_path: Path) -> None:
        entry = _cavity(
            R1={"wavelength_um": [3.0, 5.0], "values": [0.01, 0.02]},
            R2=0.010,
        )
        assert validate_element_entry(entry, base_dir=tmp_path).cavity is not None

    @pytest.mark.level1
    def test_a_spectral_alpha_supplies_the_grid_for_scalar_coatings(self, tmp_path: Path) -> None:
        """alpha is a spectral input like any other — the custom-material path."""
        alpha = _csv(tmp_path, "alpha.csv", "3.0,0.8\n4.0,1.6\n5.0,3.3\n")
        entry = {
            "name": "L1",
            "kind": "lens",
            "transfer_mode": "REFRACTIVE",
            "thickness_m": 0.006,
            "alpha": str(alpha),
            "R1": 0.010,
            "R2": 0.010,
            "temperature_K": 290.0,
        }
        assert validate_element_entry(entry, base_dir=tmp_path).cavity is not None

    @pytest.mark.level1
    def test_the_two_faces_resolve_to_different_values(self, tmp_path: Path) -> None:
        """Not merely accepted — actually different, which is the point of the door."""
        entry = _cavity(R1=str(_csv(tmp_path)), R2=0.050)
        element = validate_element_entry(entry, base_dir=tmp_path)
        assert element.cavity is not None
        r1 = np.asarray(element.cavity.R1.values)
        r2 = np.asarray(element.cavity.R2.values)
        assert not np.allclose(r1, r2)
        assert np.allclose(r2, 0.050)


class TestScalarOnlyStillUsesTheFallback:
    @pytest.mark.level1
    def test_an_all_scalar_entry_validates(self) -> None:
        """It has no grid of its own, so the generic one is correct for it."""
        assert validate_element_entry(_cavity(R1=0.010, R2=0.010)).cavity is not None


class TestGenuineProblemsStillRaise:
    """The grid adoption must not become an amnesty."""

    @pytest.mark.level1
    def test_a_missing_file_is_still_actionable(self, tmp_path: Path) -> None:
        entry = _cavity(R1=str(tmp_path / "nope.csv"), T2=0.988)
        with pytest.raises(ElementConfigError, match="not found"):
            validate_element_entry(entry, base_dir=tmp_path)

    @pytest.mark.level1
    def test_two_spectral_inputs_on_disjoint_grids_still_fail(self, tmp_path: Path) -> None:
        """One grid wins and the parser raises its own mismatch error, as before."""
        near = _csv(tmp_path, "near.csv", "3.0,0.01\n5.0,0.02\n")
        far = _csv(tmp_path, "far.csv", "8.0,0.01\n12.0,0.02\n")
        entry = _cavity(R1=str(near), R2=str(far))
        with pytest.raises((ElementConfigError, Exception)):
            validate_element_entry(entry, base_dir=tmp_path)
