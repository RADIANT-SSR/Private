"""Tests for radiant.io.element_config.

Validates YAML deserialization of mixed-train optical element lists.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import numpy as np
import pytest

from radiant.io.element_config import ElementConfigError, load_element_list
from radiant.optics.element import ElementTransferMode

WL = np.linspace(3.0, 5.0, 50)


@pytest.fixture()
def tmp_yaml(tmp_path: Path) -> Path:
    """Write a valid mixed-train YAML config and return its path."""
    content = textwrap.dedent("""\
        optical_elements:
          - name: primary_mirror
            transfer_mode: REFLECTIVE
            reflectance: 0.98
            temperature_K: 290.0
            diameter_m: 0.35
            distance_to_fpa_m: 1.2

          - name: secondary_mirror
            transfer_mode: REFLECTIVE
            reflectance: 0.97
            temperature_K: 290.0
            diameter_m: 0.10
            distance_to_fpa_m: 0.8

          - name: field_lens
            transfer_mode: REFRACTIVE
            transmittance: 0.92
            kind: LENS
            temperature_K: 280.0
            diameter_m: 0.04
            distance_to_fpa_m: 0.3
    """)
    p = tmp_path / "sensor.yaml"
    p.write_text(content)
    return p


@pytest.fixture()
def cavity_yaml(tmp_path: Path) -> Path:
    """YAML with a cavity (detailed refractive) element."""
    content = textwrap.dedent("""\
        optical_elements:
          - name: primary_mirror
            transfer_mode: REFLECTIVE
            reflectance: 0.98
            temperature_K: 290.0
            diameter_m: 0.35
            distance_to_fpa_m: 1.2

          - name: dewar_window
            transfer_mode: REFRACTIVE
            kind: WINDOW
            R1: 0.04
            T1: 0.96
            R2: 0.04
            T2: 0.96
            alpha: 0.0
            n_refr: 1.5
            thickness_m: 0.003
            temperature_K: 280.0
            diameter_m: 0.04
            distance_to_fpa_m: 0.3
    """)
    p = tmp_path / "cavity_sensor.yaml"
    p.write_text(content)
    return p


class TestLoadElementList:
    """Verify YAML loading of element lists."""

    def test_basic_load(self, tmp_yaml: Path) -> None:
        """Load a valid mixed-train config."""
        elements = load_element_list(tmp_yaml, wavelength_um=WL)
        assert len(elements) == 3
        assert elements[0].name == "primary_mirror"
        assert elements[0].resolved_transfer_mode == ElementTransferMode.REFLECTIVE
        assert elements[1].name == "secondary_mirror"
        assert elements[2].name == "field_lens"
        assert elements[2].resolved_transfer_mode == ElementTransferMode.REFRACTIVE

    def test_reflective_properties(self, tmp_yaml: Path) -> None:
        """Reflective element has correct R and eps."""
        elements = load_element_list(tmp_yaml, wavelength_um=WL)
        m = elements[0]
        np.testing.assert_allclose(m.reflectance.values, 0.98, atol=1e-12)
        np.testing.assert_allclose(m.emissivity.values, 0.02, atol=1e-12)

    def test_simple_refractive_eps_zero(self, tmp_yaml: Path) -> None:
        """Simple refractive element has eps=0."""
        elements = load_element_list(tmp_yaml, wavelength_um=WL)
        lens = elements[2]
        np.testing.assert_allclose(lens.emissivity.values, 0.0, atol=1e-12)
        np.testing.assert_allclose(lens.transmittance.values, 0.92, atol=1e-12)

    def test_geometry_preserved(self, tmp_yaml: Path) -> None:
        """Geometry/thermal properties are loaded correctly."""
        elements = load_element_list(tmp_yaml, wavelength_um=WL)
        m = elements[0]
        assert m.temperature_K == 290.0
        assert m.diameter_m == 0.35
        assert m.distance_to_fpa_m == 1.2

    def test_cavity_element(self, cavity_yaml: Path) -> None:
        """Cavity element has correct T_sys and eps."""
        elements = load_element_list(cavity_yaml, wavelength_um=WL)
        window = elements[1]
        assert window.cavity is not None
        # Uncoated glass, no absorption: T_sys = 0.9216/0.9984, eps ≈ 0.
        np.testing.assert_allclose(
            window.transmittance.values, 0.9216 / 0.9984, rtol=1e-10,
        )
        np.testing.assert_allclose(window.emissivity.values, 0.0, atol=1e-14)

    def test_spectral_csv_file(self, tmp_path: Path) -> None:
        """Spectral property loaded from CSV file path."""
        # Write a CSV file.
        csv_path = tmp_path / "gold_reflectance.csv"
        csv_path.write_text("# wavelength_um, reflectance\n3.0, 0.98\n5.0, 0.97\n")
        content = textwrap.dedent(f"""\
            optical_elements:
              - name: gold_mirror
                transfer_mode: REFLECTIVE
                reflectance: gold_reflectance.csv
                temperature_K: 290.0
                diameter_m: 0.35
                distance_to_fpa_m: 1.2
        """)
        yaml_path = tmp_path / "spectral_sensor.yaml"
        yaml_path.write_text(content)

        elements = load_element_list(yaml_path)
        m = elements[0]
        assert len(m.reflectance.values) == 2
        np.testing.assert_allclose(m.reflectance.values, [0.98, 0.97], atol=1e-12)


class TestElementConfigErrors:
    """Error cases for YAML loading."""

    def test_missing_file(self) -> None:
        with pytest.raises(ElementConfigError, match="not found"):
            load_element_list("/nonexistent/sensor.yaml")

    def test_missing_optical_elements_key(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("optics:\n  aperture: 0.3\n")
        with pytest.raises(ElementConfigError, match="optical_elements"):
            load_element_list(p)

    def test_missing_required_field(self, tmp_path: Path) -> None:
        content = textwrap.dedent("""\
            optical_elements:
              - name: bad_mirror
                transfer_mode: REFLECTIVE
        """)
        p = tmp_path / "missing.yaml"
        p.write_text(content)
        with pytest.raises(ElementConfigError, match="reflectance"):
            load_element_list(p, wavelength_um=WL)

    def test_invalid_transfer_mode(self, tmp_path: Path) -> None:
        content = textwrap.dedent("""\
            optical_elements:
              - name: bad
                transfer_mode: ABSORPTIVE
                reflectance: 0.5
        """)
        p = tmp_path / "bad_mode.yaml"
        p.write_text(content)
        with pytest.raises(ElementConfigError, match="REFLECTIVE.*REFRACTIVE"):
            load_element_list(p, wavelength_um=WL)

    def test_spectral_file_not_found(self, tmp_path: Path) -> None:
        content = textwrap.dedent("""\
            optical_elements:
              - name: mirror
                transfer_mode: REFLECTIVE
                reflectance: nonexistent.csv
        """)
        p = tmp_path / "bad_path.yaml"
        p.write_text(content)
        with pytest.raises(ElementConfigError, match="not found"):
            load_element_list(p)

    def test_empty_element_list(self, tmp_path: Path) -> None:
        content = "optical_elements: []\n"
        p = tmp_path / "empty.yaml"
        p.write_text(content)
        with pytest.raises(ElementConfigError, match="non-empty"):
            load_element_list(p)
