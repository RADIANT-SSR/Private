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


@pytest.mark.level1
class TestIntensityDoorExtentConflicts:
    """CU-256 — the S10/S10b intensity door refuses a declared target extent.

    An intensity ``I(λ)`` [W/sr/µm] and a declared projected area / shape are
    two mutually exclusive descriptions of the same target (owner ruling
    2026-07-29).  Before CU-256 the extent was silently discarded: T7 publishes
    a fictitious reference area, so ``angular_extent_rad`` came out as a
    ~1e-11 rad sentinel and the matrix §7 point-source validity guard never
    fired on a 20-pixel-wide target.
    """

    @pytest.fixture()
    def intensity_csv(self, tmp_path: Path) -> Path:
        p = tmp_path / "I_source.csv"
        p.write_text(
            "wavelength_um,intensity_W_per_sr_per_um\n3.0,10.0\n5.5,10.0\n",
            encoding="utf-8",
        )
        return p

    # --- still-passing cases -------------------------------------------------

    def test_blackbody_door_alone_passes(self) -> None:
        """The door's own emitting area (point_intensity_area_m2) is not an extent."""
        s = Sensor().set("source.target.point_intensity_temperature_K", 500.0)
        s.set("source.target.point_intensity_area_m2", 0.36)  # m²
        s.set("source.target.point_intensity_emissivity", 0.9)
        s.validate_target_spec()  # no raise

    def test_scalar_door_alone_passes(self) -> None:
        s = Sensor().set("source.target.point_intensity_band_W_per_sr", 25.0)
        s.validate_target_spec()

    def test_csv_door_alone_passes(self, intensity_csv: Path) -> None:
        s = Sensor().set("source.target.user_intensity_path", str(intensity_csv))
        s.validate_target_spec()

    def test_declared_extent_without_the_door_passes(self) -> None:
        s = Sensor().set("geometry.target.projected_area_m2", 500.0)  # m²
        s.set("source.target.temperature", 800.0)  # K
        s.set("source.target.emissivity", 0.9)
        s.validate_target_spec()

    # --- raising cases -------------------------------------------------------

    def test_blackbody_door_plus_projected_area_raises(self) -> None:
        s = Sensor().set("source.target.point_intensity_temperature_K", 500.0)
        s.set("source.target.point_intensity_area_m2", 500.0)  # m²
        s.set("geometry.target.projected_area_m2", 500.0)  # m²
        with pytest.raises(ParameterBoundsError) as excinfo:
            s.validate_target_spec()
        exc = excinfo.value
        assert exc.what and exc.why and exc.action  # Rule 15 fields populated
        assert "point_intensity_temperature_K" in exc.what
        assert "geometry.target.projected_area_m2" in exc.what
        # The action names which parameter to drop, both ways round.
        assert "remove geometry.target.projected_area_m2" in exc.action
        assert exc.context["geometry.target.projected_area_m2"] == pytest.approx(500.0, rel=1e-12)

    def test_scalar_door_plus_projected_area_raises(self) -> None:
        s = Sensor().set("source.target.point_intensity_band_W_per_sr", 25.0)  # W/sr
        s.set("geometry.target.projected_area_m2", 4.0)  # m²
        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            s.validate_target_spec()

    def test_csv_door_plus_projected_area_raises(self, intensity_csv: Path) -> None:
        s = Sensor().set("source.target.user_intensity_path", str(intensity_csv))
        s.set("geometry.target.projected_area_m2", 4.0)  # m²
        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            s.validate_target_spec()

    def test_door_plus_declared_shape_raises(self) -> None:
        s = Sensor().set("source.target.point_intensity_band_W_per_sr", 25.0)  # W/sr
        s.set("geometry.target.shape", "sphere")
        s.set("geometry.target.shape_radius_m", 1.0)  # m
        with pytest.raises(ParameterBoundsError) as excinfo:
            s.validate_target_spec()
        assert "geometry.target.shape" in excinfo.value.what

    def test_deprecated_area_alias_also_raises(self) -> None:
        """The old source.target.projected_area_m2 alias resolves to the canonical name."""
        s = Sensor().set("source.target.point_intensity_band_W_per_sr", 25.0)  # W/sr
        s.set("source.target.projected_area_m2", 4.0)  # m²
        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            s.validate_target_spec()

    # --- evaluate-time identity (defence in depth, matching CU-244) ----------

    def test_same_error_from_seam_and_evaluate(self) -> None:
        s = Sensor.from_yaml(_MWIR_YAML)
        s.set("source.target.temperature", 0.0)  # unset the YAML's (ε, T) surface
        s = s.reset("source.target.temperature")
        s = s.reset("source.target.emissivity")
        s.set("source.scene_type", "point_source")
        s.set("source.target.point_intensity_temperature_K", 500.0)  # K
        s.set("source.target.point_intensity_area_m2", 500.0)  # m²
        s.set("source.target.point_intensity_emissivity", 0.9)
        s.set("geometry.target.projected_area_m2", 500.0)  # m²
        s.set("geometry.target_range_m", 25_000.0)  # m

        with pytest.raises(ParameterBoundsError) as seam:
            s.validate_target_spec()
        with pytest.raises(ParameterBoundsError) as evaluated:
            s.evaluate()
        assert str(seam.value) == str(evaluated.value)
