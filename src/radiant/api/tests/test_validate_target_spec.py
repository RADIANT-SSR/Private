"""Tests for the resolve-time target-spec seam ``Sensor.validate_target_spec`` (CU-244).

Each mutual-exclusivity family the CU names is exercised both clean (one
surface set → no raise) and conflicting (pair set → ``ParameterBoundsError``
with actionable what/why/action), plus the text-identity lock: the seam's
error is character-identical to the one ``evaluate()`` raises, because both
run the same guard functions in :mod:`radiant.source.target_spec`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from radiant.api.sensor import Sensor
from radiant.core.parameters import ParameterBoundsError

# Path to the minimal MWIR config shipped with the repo.
_MWIR_YAML = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture()
def rho_csv(tmp_path: Path) -> Path:
    """A minimal valid two-column reflectance CSV spanning the MWIR band."""
    p = tmp_path / "rho.csv"
    p.write_text(
        "wavelength_um,reflectance\n3.0,0.30\n5.5,0.30\n",
        encoding="utf-8",
    )
    return p


@pytest.mark.level1
class TestCleanSpecs:
    """One surface per door is never a conflict — and an empty spec never raises."""

    def test_untouched_sensor_passes(self) -> None:
        Sensor().validate_target_spec()  # all defaults — no raise

    def test_single_scalar_reflectance_passes(self) -> None:
        s = Sensor().set("source.target.reflectance", 0.3)
        s.validate_target_spec()

    def test_single_albedo_passes(self) -> None:
        s = Sensor().set("source.target.albedo", 0.3)
        s.validate_target_spec()

    def test_single_reflectance_path_passes(self, rho_csv: Path) -> None:
        s = Sensor().set("source.target.reflectance_path", str(rho_csv))
        s.validate_target_spec()

    def test_legacy_epsilon_T_passes(self) -> None:
        s = Sensor().set("source.target.temperature", 300.0)
        s.set("source.target.emissivity", 0.95)
        s.validate_target_spec()

    def test_incomplete_s12_passes(self) -> None:
        """Completeness is evaluate()'s job: T_R without its band is NOT rejected here."""
        s = Sensor().set("source.target.radiance_temperature_K", 320.0)
        s.validate_target_spec()


@pytest.mark.level1
class TestConflictFamilies:
    """The four families CU-244 names, each rejected at resolve time."""

    def test_scalar_rho_plus_path(self, rho_csv: Path) -> None:
        s = Sensor().set("source.target.reflectance", 0.3)
        s.set("source.target.reflectance_path", str(rho_csv))
        with pytest.raises(ParameterBoundsError, match="over-specified"):
            s.validate_target_spec()

    def test_rho_plus_epsilon_T(self) -> None:
        s = Sensor().set("source.target.reflectance", 0.3)
        s.set("source.target.temperature", 300.0)
        with pytest.raises(ParameterBoundsError, match="source.target.temperature"):
            s.validate_target_spec()

    def test_rho_plus_brightness_temperature(self) -> None:
        s = Sensor().set("source.target.brightness_temperature_K", 300.0)
        s.set("source.target.reflectance", 0.3)
        with pytest.raises(ParameterBoundsError, match="thermal S11 vs"):
            s.validate_target_spec()

    def test_rho_plus_radiance_temperature(self) -> None:
        s = Sensor().set("source.target.radiance_temperature_K", 300.0)
        s.set("source.target.reflectance", 0.3)
        with pytest.raises(ParameterBoundsError, match="thermal S12 vs"):
            s.validate_target_spec()

    def test_albedo_alias_pair(self) -> None:
        s = Sensor().set("source.target.reflectance", 0.3)
        s.set("source.target.albedo", 0.3)
        with pytest.raises(ParameterBoundsError, match="over-specified"):
            s.validate_target_spec()

    def test_error_is_actionable(self, rho_csv: Path) -> None:
        s = Sensor().set("source.target.reflectance", 0.3)
        s.set("source.target.reflectance_path", str(rho_csv))
        with pytest.raises(ParameterBoundsError) as excinfo:
            s.validate_target_spec()
        exc = excinfo.value
        assert exc.what and exc.why and exc.action  # Rule 15 fields populated


@pytest.mark.level1
class TestEvaluateIdentity:
    """The seam raises the exact error evaluate() raises (requirement (a))."""

    def test_same_what_why_action_as_evaluate(self, rho_csv: Path) -> None:
        s = Sensor.from_yaml(_MWIR_YAML)
        s.set("source.target.reflectance", 0.3)
        s.set("source.target.reflectance_path", str(rho_csv))

        with pytest.raises(ParameterBoundsError) as seam:
            s.validate_target_spec()
        with pytest.raises(ParameterBoundsError) as evaluated:
            s.evaluate()
        assert str(seam.value) == str(evaluated.value)

    def test_evaluate_time_check_still_present(self, rho_csv: Path) -> None:
        """Defence in depth: the inferrer path still rejects on its own."""
        s = Sensor.from_yaml(_MWIR_YAML)
        s.set("source.target.reflectance", 0.3)
        s.set("source.target.reflectance_path", str(rho_csv))
        with pytest.raises(ParameterBoundsError, match="over-specified"):
            s.evaluate()
