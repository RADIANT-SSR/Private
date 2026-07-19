"""Tests for YAML templates — every template must load and produce valid output."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent / "examples" / "templates"
)


def _template_paths() -> list[Path]:
    """Collect all .yaml files in examples/templates/."""
    if not _TEMPLATES_DIR.is_dir():
        return []
    return sorted(_TEMPLATES_DIR.glob("*.yaml"))


def _template_ids() -> list[str]:
    return [p.stem for p in _template_paths()]


class TestTemplateFiles:
    """Validate that template YAML files are well-formed."""

    @pytest.mark.level1
    def test_templates_exist(self) -> None:
        paths = _template_paths()
        assert len(paths) >= 12, f"Expected ≥12 templates, found {len(paths)}"

    @pytest.mark.level1
    @pytest.mark.parametrize("path", _template_paths(), ids=_template_ids())
    def test_template_valid_yaml(self, path: Path) -> None:
        """Each template must be valid YAML."""
        with open(path, encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
        assert isinstance(config, dict), f"{path.name}: not a dict"

    @pytest.mark.level1
    @pytest.mark.parametrize("path", _template_paths(), ids=_template_ids())
    def test_template_has_required_sections(self, path: Path) -> None:
        """Each template must have source, optics, detector, spectral_integration, readout."""
        with open(path, encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
        required = ["source", "optics", "detector", "spectral_integration", "readout"]
        for section in required:
            assert section in config, f"{path.name}: missing '{section}'"

    @pytest.mark.level1
    @pytest.mark.parametrize("path", _template_paths(), ids=_template_ids())
    def test_template_positive_values(self, path: Path) -> None:
        """Key physical parameters must be positive."""
        with open(path, encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
        checks = [
            ("optics", "aperture_diameter_m"),
            ("optics", "focal_length_m"),
            ("detector", "pixel_pitch_x_um"),
            ("spectral_integration", "filter_min_um"),
            ("spectral_integration", "filter_max_um"),
            ("spectral_integration", "integration_time_s"),
        ]
        for section, key in checks:
            val = config.get(section, {}).get(key)
            if val is not None:
                assert val > 0, f"{path.name}: {section}.{key} = {val} must be > 0"

    @pytest.mark.level1
    @pytest.mark.parametrize("path", _template_paths(), ids=_template_ids())
    def test_template_filter_range_valid(self, path: Path) -> None:
        """filter_min_um must be less than filter_max_um."""
        with open(path, encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
        si = config.get("spectral_integration", {})
        fmin = si.get("filter_min_um")
        fmax = si.get("filter_max_um")
        if fmin is not None and fmax is not None:
            assert fmin < fmax, f"{path.name}: filter_min ({fmin}) ≥ filter_max ({fmax})"

    @pytest.mark.level2
    @pytest.mark.parametrize("path", _template_paths(), ids=_template_ids())
    def test_template_loads_via_sensor(self, path: Path) -> None:
        """Each template must load successfully via Sensor.from_yaml()."""
        from radiant.api import Sensor

        sensor = Sensor.from_yaml(str(path))
        result = sensor.evaluate()
        snr = result.metrics.get("snr")
        assert snr is not None, f"{path.name}: 'snr' not in result.metrics"
        assert snr >= 0, f"{path.name}: SNR = {snr}, expected >= 0"
        import math

        assert math.isfinite(snr), f"{path.name}: SNR = {snr}, not finite"
