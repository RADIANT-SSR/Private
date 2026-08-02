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


def _thermal_surface_cleared() -> Sensor:
    """The shipped MWIR example with its (ε, T) surface reset back to DEFAULT.

    Every door below is mutually exclusive with the legacy (ε, T) surface, so
    the YAML's own ε and T have to go before a *different* pair can be the
    conflict under test.
    """
    s = Sensor.from_yaml(_MWIR_YAML).reset("source.target.temperature")
    return s.reset("source.target.emissivity")


@pytest.mark.level1
class TestBrightnessPlusRadianceTemperature:
    """CU-293 — the S11 + S12 pair is refused at *both* entry points.

    Before CU-293 the S11 builder dispatched first and never checked S12, so
    ``evaluate()`` silently ignored a user-supplied ``radiance_temperature_K``
    (Rule 17) while the CU-244 seam already rejected the pair.  Owner ruling
    2026-08-01, same class as CU-256/CU-264: over-specification raises.
    """

    @staticmethod
    def _pair(s: Sensor) -> Sensor:
        s.set("source.target.brightness_temperature_K", 320.0)  # K
        s.set("source.target.radiance_temperature_K", 300.0)  # K
        s.set("source.target.radiance_temperature_band_lo_um", 3.0)  # µm
        s.set("source.target.radiance_temperature_band_hi_um", 5.0)  # µm
        return s

    def test_seam_raises(self) -> None:
        s = self._pair(Sensor())
        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            s.validate_target_spec()

    def test_evaluate_raises(self) -> None:
        """The defect: this evaluated cleanly before CU-293, T_R discarded."""
        s = self._pair(_thermal_surface_cleared())
        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            s.evaluate()

    def test_same_error_from_seam_and_evaluate(self) -> None:
        s = self._pair(_thermal_surface_cleared())
        with pytest.raises(ParameterBoundsError) as seam:
            s.validate_target_spec()
        with pytest.raises(ParameterBoundsError) as evaluated:
            s.evaluate()
        assert str(seam.value) == str(evaluated.value)

    def test_error_names_both_surfaces_and_is_actionable(self) -> None:
        s = self._pair(Sensor())
        with pytest.raises(ParameterBoundsError) as excinfo:
            s.validate_target_spec()
        exc = excinfo.value
        assert exc.what and exc.why and exc.action  # Rule 15 fields populated
        assert "brightness_temperature" in exc.what
        assert "radiance_temperature" in exc.what
        assert "S11" in exc.what and "S12" in exc.what
        assert exc.context["radiance_temperature_K_set"] is True

    def test_band_edges_are_not_required_for_the_refusal(self) -> None:
        """Exclusivity is over ``radiance_temperature_K`` alone.

        The band-edge *completeness* check is the inferrer's (module scope:
        over-specification only), so an S11 + bare-T_R pair is still a
        conflict even though the S12 spec is incomplete.
        """
        s = Sensor()
        s.set("source.target.brightness_temperature_K", 320.0)  # K
        s.set("source.target.radiance_temperature_K", 300.0)  # K
        with pytest.raises(ParameterBoundsError, match="S11 vs S12"):
            s.validate_target_spec()

    def test_each_surface_alone_still_passes(self) -> None:
        a = Sensor().set("source.target.brightness_temperature_K", 320.0)  # K
        a.validate_target_spec()
        b = Sensor().set("source.target.radiance_temperature_K", 300.0)  # K
        b.set("source.target.radiance_temperature_band_lo_um", 3.0)  # µm
        b.set("source.target.radiance_temperature_band_hi_um", 5.0)  # µm
        b.validate_target_spec()


@pytest.mark.level1
class TestMovedIntensityDoorGuards:
    """CU-293 (ex-CU-294) — the S8/S10/S10b guards now also run at the seam.

    These conflicts always raised at ``evaluate()``; what CU-294 recorded is
    that they were *inlined* in the inferrer, so the GUI's clone-validate edit
    discipline could commit a config it already knew was invalid.  Each case
    below asserts both entry points and their text identity.
    """

    @pytest.fixture()
    def intensity_csv(self, tmp_path: Path) -> Path:
        p = tmp_path / "I_source.csv"
        p.write_text(
            "wavelength_um,intensity_W_per_sr_per_um\n3.0,10.0\n5.5,10.0\n",
            encoding="utf-8",
        )
        return p

    @pytest.fixture()
    def radiance_csv(self, tmp_path: Path) -> Path:
        p = tmp_path / "L_source.csv"
        p.write_text(
            "wavelength_um,L_W_per_m2_per_sr_per_um\n3.0,4.0\n5.5,6.0\n",
            encoding="utf-8",
        )
        return p

    @staticmethod
    def _assert_both_doors_agree(configure: object) -> ParameterBoundsError:
        """Seam and evaluate both raise, with character-identical text."""
        assert callable(configure)
        seam_sensor = configure(_thermal_surface_cleared())
        with pytest.raises(ParameterBoundsError) as seam:
            seam_sensor.validate_target_spec()
        eval_sensor = configure(_thermal_surface_cleared())
        with pytest.raises(ParameterBoundsError) as evaluated:
            eval_sensor.evaluate()
        assert str(seam.value) == str(evaluated.value)
        return seam.value

    # --- S8 (user_radiance_path) --------------------------------------------

    def test_s8_plus_epsilon_T(self, radiance_csv: Path) -> None:
        def configure(s: Sensor) -> Sensor:
            s.set("source.target.user_radiance_path", str(radiance_csv))
            s.set("source.target.temperature", 300.0)  # K
            return s

        exc = self._assert_both_doors_agree(configure)
        assert "user_radiance_path" in exc.what
        assert "source.target.temperature" in exc.what

    def test_s8_plus_s10_csv(self, radiance_csv: Path, intensity_csv: Path) -> None:
        def configure(s: Sensor) -> Sensor:
            s.set("source.target.user_radiance_path", str(radiance_csv))
            s.set("source.target.user_intensity_path", str(intensity_csv))
            return s

        exc = self._assert_both_doors_agree(configure)
        assert "S8 vs S10" in exc.what

    # --- S10b (point_intensity_*) -------------------------------------------

    def test_s10b_blackbody_plus_scalar(self) -> None:
        def configure(s: Sensor) -> Sensor:
            s.set("source.scene_type", "point_source")
            s.set("source.target.point_intensity_temperature_K", 500.0)  # K
            s.set("source.target.point_intensity_band_W_per_sr", 25.0)  # W/sr
            return s

        exc = self._assert_both_doors_agree(configure)
        assert "point_intensity_temperature_K" in exc.what
        assert "point_intensity_band_W_per_sr" in exc.what

    def test_s10b_plus_epsilon_T(self) -> None:
        def configure(s: Sensor) -> Sensor:
            s.set("source.scene_type", "point_source")
            s.set("source.target.point_intensity_temperature_K", 500.0)  # K
            s.set("source.target.emissivity", 0.9)
            return s

        exc = self._assert_both_doors_agree(configure)
        assert "point-intensity" in exc.what
        assert "emissivity" in exc.what

    def test_s10b_plus_s10_csv(self, intensity_csv: Path) -> None:
        def configure(s: Sensor) -> Sensor:
            s.set("source.scene_type", "point_source")
            s.set("source.target.point_intensity_band_W_per_sr", 25.0)  # W/sr
            s.set("source.target.user_intensity_path", str(intensity_csv))
            return s

        exc = self._assert_both_doors_agree(configure)
        assert "user_intensity_path" in exc.what

    # --- S10 (user_intensity_path) ------------------------------------------

    def test_s10_plus_epsilon_T(self, intensity_csv: Path) -> None:
        def configure(s: Sensor) -> Sensor:
            s.set("source.scene_type", "point_source")
            s.set("source.target.user_intensity_path", str(intensity_csv))
            s.set("source.target.temperature", 300.0)  # K
            return s

        exc = self._assert_both_doors_agree(configure)
        assert "user_intensity_path" in exc.what
        assert "source.target.temperature" in exc.what

    # --- still-clean single-door specs --------------------------------------

    def test_single_s8_door_passes(self, radiance_csv: Path) -> None:
        s = Sensor().set("source.target.user_radiance_path", str(radiance_csv))
        s.validate_target_spec()

    def test_single_s10b_blackbody_door_passes(self) -> None:
        s = Sensor().set("source.target.point_intensity_temperature_K", 500.0)  # K
        s.set("source.target.point_intensity_area_m2", 0.36)  # m²
        s.validate_target_spec()

    def test_single_s10_door_passes(self, intensity_csv: Path) -> None:
        s = Sensor().set("source.target.user_intensity_path", str(intensity_csv))
        s.validate_target_spec()


@pytest.mark.level1
class TestEmissivityPathDoor:
    """CU-318 — the S1-with-ε(λ) door's guard now runs at the seam too.

    It was the last door whose exclusivity guard was inlined in the inferrer
    (CU-293 moved the other three but did not name this one).  The pair
    **unique** to this door — ``emissivity_path`` + scalar
    ``source.target.emissivity`` — reached only ``evaluate()`` before CU-318,
    so the GUI clone-validate seam (CU-244) let an operator commit it.  That
    pair is asserted symmetric (seam and evaluate, identical text).

    The other nine rivals in the guard's list all *open a door of their own*
    that the inferrer dispatches before the ε(λ) door, so at ``evaluate()``
    they never reach this guard — the ε(λ) surface is discarded in silence
    (measured 2026-08-02; the CU-318 entry's "caught earlier by other doors'
    symmetric guards" holds only for the two rivals whose own door raises for
    an unrelated reason).  The seam is therefore deliberately **stricter** than
    ``evaluate()`` for those pairs: it refuses an over-specified spec the
    inferrer would silently narrow.  Only the seam side is asserted below —
    pinning the evaluate-side silence would freeze a Rule-17 defect.
    """

    @pytest.fixture()
    def eps_csv(self, tmp_path: Path) -> Path:
        p = tmp_path / "eps.csv"
        p.write_text(
            "wavelength_um,emissivity\n3.0,0.80\n5.5,0.92\n",
            encoding="utf-8",
        )
        return p

    @pytest.fixture()
    def radiance_csv(self, tmp_path: Path) -> Path:
        p = tmp_path / "L_source.csv"
        p.write_text(
            "wavelength_um,L_W_per_m2_per_sr_per_um\n3.0,4.0\n5.5,6.0\n",
            encoding="utf-8",
        )
        return p

    @pytest.fixture()
    def intensity_csv(self, tmp_path: Path) -> Path:
        p = tmp_path / "I_source.csv"
        p.write_text(
            "wavelength_um,intensity_W_per_sr_per_um\n3.0,10.0\n5.5,10.0\n",
            encoding="utf-8",
        )
        return p

    # --- the pair unique to this door ---------------------------------------

    def test_scalar_emissivity_pair_raises_at_the_seam(self, eps_csv: Path) -> None:
        """The defect: this passed the seam before CU-318."""
        s = Sensor().set("source.target.emissivity_path", str(eps_csv))
        s.set("source.target.emissivity", 0.95)
        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            s.validate_target_spec()

    def test_scalar_emissivity_pair_raises_at_evaluate(self, eps_csv: Path) -> None:
        s = _thermal_surface_cleared()
        s.set("source.target.emissivity_path", str(eps_csv))
        s.set("source.target.emissivity", 0.95)
        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            s.evaluate()

    def test_same_error_from_seam_and_evaluate(self, eps_csv: Path) -> None:
        def configure() -> Sensor:
            s = _thermal_surface_cleared()
            s.set("source.target.emissivity_path", str(eps_csv))
            s.set("source.target.emissivity", 0.95)
            return s

        with pytest.raises(ParameterBoundsError) as seam:
            configure().validate_target_spec()
        with pytest.raises(ParameterBoundsError) as evaluated:
            configure().evaluate()
        assert str(seam.value) == str(evaluated.value)

    def test_error_is_actionable_and_names_both_surfaces(self, eps_csv: Path) -> None:
        s = Sensor().set("source.target.emissivity_path", str(eps_csv))
        s.set("source.target.emissivity", 0.95)
        with pytest.raises(ParameterBoundsError) as excinfo:
            s.validate_target_spec()
        exc = excinfo.value
        assert exc.what and exc.why and exc.action  # Rule 15 fields populated
        assert "emissivity_path" in exc.what
        assert "source.target.emissivity" in exc.what
        assert exc.context["conflict"] == "source.target.emissivity"

    # --- every other rival in the guard's list is refused at the seam --------

    @pytest.mark.parametrize(
        ("conflict", "value"),
        [
            ("source.target.reflectance", 0.3),
            ("source.target.albedo", 0.3),
            ("source.target.brightness_temperature_K", 320.0),  # K
            ("source.target.radiance_temperature_K", 300.0),  # K
        ],
    )
    def test_scalar_rivals_refused_at_the_seam(
        self, eps_csv: Path, conflict: str, value: float
    ) -> None:
        s = Sensor().set("source.target.emissivity_path", str(eps_csv))
        s.set(conflict, value)
        with pytest.raises(ParameterBoundsError):
            s.validate_target_spec()

    def test_path_rivals_refused_at_the_seam(
        self,
        eps_csv: Path,
        radiance_csv: Path,
        intensity_csv: Path,
        rho_csv: Path,
        tmp_path: Path,
    ) -> None:
        t_b_csv = tmp_path / "T_b.csv"
        t_b_csv.write_text(
            "wavelength_um,brightness_temperature_K\n3.0,320.0\n5.5,320.0\n",
            encoding="utf-8",
        )
        for conflict, path in (
            ("source.target.reflectance_path", rho_csv),
            ("source.target.albedo_path", rho_csv),
            ("source.target.brightness_temperature_path", t_b_csv),
            ("source.target.user_radiance_path", radiance_csv),
            ("source.target.user_intensity_path", intensity_csv),
        ):
            s = Sensor().set("source.target.emissivity_path", str(eps_csv))
            s.set(conflict, str(path))
            with pytest.raises(ParameterBoundsError):
                s.validate_target_spec()

    # --- clean single-door spec ---------------------------------------------

    def test_single_emissivity_path_door_passes(self, eps_csv: Path) -> None:
        s = Sensor().set("source.target.emissivity_path", str(eps_csv))
        s.set("source.target.temperature", 300.0)  # K
        s.validate_target_spec()
