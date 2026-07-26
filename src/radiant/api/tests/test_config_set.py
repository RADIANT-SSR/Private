"""Tests for ``ConfigurationSet`` — multi-configuration core model.

Covers the Phase 1 test list of ``docs/plans/Multi_Configuration_Plan.md`` §6
against the model ratified in ``docs/adr/0010-multi-configuration-model.md``:
materialization/isolation/provenance, the single-store invariant, the
consistency-group story, CRUD edge cases, ``evaluate_all`` ordering and
failure capture, per-configuration wavelength grids, the degenerate
single-configuration case, and the ``compare`` adapter.
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from radiant.api import (
    ConfigRun,
    ConfigSetError,
    ConfigSetRunResult,
    ConfigurationSet,
    OperationCancelledError,
    Sensor,
    compare_configs,
)
from radiant.api.errors import ApiValidationError
from radiant.core.exceptions import RadiantError
from radiant.core.parameters import UnknownParameterError

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"

# Small spectral grid: these are bookkeeping tests, not physics tests, and a
# coarse grid keeps the full-chain evaluations in this module quick.
_WL_POINTS = 40


def _sensor(points: int = _WL_POINTS) -> Sensor:
    """The shared minimal MWIR example, on a coarse spectral grid."""
    return Sensor.from_yaml(_EXAMPLE, wavelength_points=points)


def _set(*names: str, points: int = _WL_POINTS) -> ConfigurationSet:
    """A ConfigurationSet over the example sensor with the given names."""
    return ConfigurationSet(_sensor(points), names=list(names) if names else None)


def _evaluate(obj: Any) -> Any:
    """Evaluate suppressing the chain's physical-regime UserWarnings."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return obj.evaluate()


def _evaluate_all(cs: ConfigurationSet, **kwargs: Any) -> ConfigSetRunResult:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return cs.evaluate_all(**kwargs)


# ---------------------------------------------------------------------------
# Materialization, isolation, provenance
# ---------------------------------------------------------------------------


class TestMaterialization:
    def test_configured_values_land_per_configuration(self) -> None:
        cs = _set("MWIR", "LWIR")
        cs.configure("spectral_integration.filter_min_um", [3.95, 8.0])
        cs.configure("spectral_integration.filter_max_um", [4.45, 12.0])
        mwir = cs.sensor_for("MWIR")
        lwir = cs.sensor_for("LWIR")
        assert mwir.get_input("spectral_integration.filter_min_um") == pytest.approx(
            3.95, rel=1e-12
        )
        assert lwir.get_input("spectral_integration.filter_min_um") == pytest.approx(8.0, rel=1e-12)
        assert lwir.get_input("spectral_integration.filter_max_um") == pytest.approx(
            12.0, rel=1e-12
        )

    def test_non_configured_inputs_identical_across_configurations(self) -> None:
        cs = _set("A", "B", "C")
        cs.configure("detector.qe_value", [0.75, 0.62, 0.50])
        shared = dict(cs.base._params.inputs())
        for name in cs.names():
            materialized = dict(cs.sensor_for(name)._params.inputs())
            del materialized["detector.qe_value"]
            assert materialized == shared

    def test_provenance_source_names_the_configuration(self) -> None:
        cs = _set("MWIR", "LWIR")
        cs.configure("detector.qe_value", [0.75, 0.62])
        assert cs.sensor_for("MWIR").resolved("detector.qe_value").source == "config:MWIR"
        assert cs.sensor_for("LWIR").resolved("detector.qe_value").source == "config:LWIR"
        # explain() therefore names the owning configuration with no new machinery
        assert "config:LWIR" in cs.sensor_for("LWIR").explain("detector.qe_value")

    def test_materialized_sensor_is_isolated_from_the_set(self) -> None:
        cs = _set("A", "B")
        cs.configure("detector.qe_value", [0.75, 0.62])
        sensor_a = cs.sensor_for("A")

        # Edits to the set do not reach an already-materialized sensor...
        cs.set_value("detector.qe_value", "A", 0.10)
        cs.base.set("optics.aperture_diameter_m", 0.9)
        assert sensor_a.get_input("detector.qe_value") == pytest.approx(0.75, rel=1e-12)
        assert sensor_a.get("optics.aperture_diameter_m") == pytest.approx(0.30, rel=1e-12)

        # ...and edits to a materialized sensor do not reach the set.
        sensor_a.set("detector.dark_rate_e_per_s", 5.0)
        assert cs.base._params.inputs()["detector.dark_rate_e_per_s"] == pytest.approx(
            100.0, rel=1e-12
        )
        assert cs.sensor_for("B").get("detector.dark_rate_e_per_s") == pytest.approx(
            100.0, rel=1e-12
        )

    def test_unknown_configuration_named_actionably(self) -> None:
        cs = _set("A", "B")
        with pytest.raises(ConfigSetError, match="no configuration named 'ZZ'") as excinfo:
            cs.sensor_for("ZZ")
        assert excinfo.value.context["configuration"] == "ZZ"
        assert excinfo.value.action  # Rule 15: every field populated


# ---------------------------------------------------------------------------
# Single-store invariant (ADR-0010 D-B)
# ---------------------------------------------------------------------------


class TestSingleStoreInvariant:
    def test_configure_moves_a_base_set_parameter(self) -> None:
        cs = _set("A", "B")
        assert "detector.qe_value" in cs.base._params.inputs()
        cs.configure("detector.qe_value")
        # Seeded N-wide from the shared value, and removed from the base.
        assert cs.configured()["detector.qe_value"] == (0.70, 0.70)
        assert "detector.qe_value" not in cs.base._params.inputs()
        assert cs.is_configured("detector.qe_value")

    def test_configure_seeds_a_never_set_parameter_from_its_default(self) -> None:
        cs = _set("A", "B", "C")
        assert "detector.fill_factor" not in cs.base._params.inputs()
        cs.configure("detector.fill_factor")
        assert cs.configured()["detector.fill_factor"] == (1.0, 1.0, 1.0)  # schema default
        assert cs.sensor_for("B").get("detector.fill_factor") == pytest.approx(1.0, rel=1e-12)

    def test_seeding_still_works_after_a_required_parameter_was_configured(self) -> None:
        # Configuring a *required* parameter takes it out of the base, so the
        # base alone no longer resolves — seeding a later parameter must not
        # depend on that.
        cs = _set("A", "B")
        cs.configure("detector.qe_value", [0.75, 0.62])
        cs.configure("detector.fill_factor")
        assert cs.configured()["detector.fill_factor"] == (1.0, 1.0)
        assert cs.validate_all() == {"A": None, "B": None}

    def test_double_store_is_unrepresentable_through_the_api(self) -> None:
        cs = _set("A", "B")
        cs.configure("detector.qe_value", [0.75, 0.62])
        ops: list[Callable[[], None]] = [
            lambda: cs.set_value("detector.qe_value", "A", 0.5),
            lambda: cs.set_values("detector.qe_value", [0.5, 0.4]),
            lambda: cs.add("C"),
            lambda: cs.remove("B"),
        ]
        for op in ops:
            op()
            assert "detector.qe_value" not in cs.base._params.inputs()
            assert "detector.qe_value" in cs.configured()

    def test_base_side_back_door_is_caught_not_silently_shadowed(self) -> None:
        cs = _set("A", "B")
        cs.configure("detector.qe_value", [0.75, 0.62])
        cs.base.set("detector.qe_value", 0.4)  # bypasses the set's API
        with pytest.raises(ConfigSetError, match="configured but the base also holds") as excinfo:
            cs.sensor_for("A")
        assert excinfo.value.context["params"] == ["detector.qe_value"]

    def test_configuring_twice_is_rejected(self) -> None:
        cs = _set("A", "B")
        cs.configure("detector.qe_value", [0.75, 0.62])
        with pytest.raises(ConfigSetError, match="already configured"):
            cs.configure("detector.qe_value", [0.1, 0.2])

    def test_unconfigure_keeps_configuration_one_by_default(self) -> None:
        cs = _set("A", "B", "C")
        cs.configure("detector.qe_value", [0.75, 0.62, 0.50])
        cs.unconfigure("detector.qe_value")
        assert not cs.is_configured("detector.qe_value")
        assert cs.base.get_input("detector.qe_value") == pytest.approx(0.75, rel=1e-12)
        for name in cs.names():
            assert cs.sensor_for(name).get_input("detector.qe_value") == pytest.approx(
                0.75, rel=1e-12
            )

    def test_unconfigure_keep_override(self) -> None:
        cs = _set("A", "B", "C")
        cs.configure("detector.qe_value", [0.75, 0.62, 0.50])
        cs.unconfigure("detector.qe_value", keep="C")
        assert cs.base.get_input("detector.qe_value") == pytest.approx(0.50, rel=1e-12)

    def test_unconfigure_unknown_keep_and_unconfigured_param_are_actionable(self) -> None:
        cs = _set("A", "B")
        cs.configure("detector.qe_value", [0.75, 0.62])
        with pytest.raises(ConfigSetError, match="no configuration named 'ZZ'"):
            cs.unconfigure("detector.qe_value", keep="ZZ")
        with pytest.raises(ConfigSetError, match="is not configured"):
            cs.unconfigure("optics.aperture_diameter_m")

    def test_dense_column_length_enforced_never_padded(self) -> None:
        cs = _set("A", "B", "C")
        with pytest.raises(ConfigSetError, match="needs exactly 3 values"):
            cs.configure("detector.qe_value", [0.75, 0.62])
        cs.configure("detector.qe_value")
        with pytest.raises(ConfigSetError, match="needs exactly 3 values"):
            cs.set_values("detector.qe_value", [0.1, 0.2, 0.3, 0.4])


# ---------------------------------------------------------------------------
# Immediate schema validation of configured values
# ---------------------------------------------------------------------------


class TestConfiguredValueValidation:
    def test_out_of_bounds_value_rejected_at_edit_time_naming_the_configuration(self) -> None:
        cs = _set("A", "B")
        with pytest.raises(ConfigSetError, match="'B'") as excinfo:
            cs.configure("detector.fill_factor", [0.9, 1.5])
        assert excinfo.value.context["configuration"] == "B"
        assert "out of bounds" in excinfo.value.why
        # Rejected atomically: nothing was configured, nothing left the base.
        assert not cs.is_configured("detector.fill_factor")

    def test_enum_value_rejected_naming_the_configuration(self) -> None:
        cs = _set("A", "B")
        with pytest.raises(ConfigSetError, match="'B'") as excinfo:
            cs.configure("atmosphere.standard_atmosphere", ["midlat_summer", "not_a_model"])
        assert excinfo.value.context["configuration"] == "B"

    def test_type_error_rejected_at_edit_time(self) -> None:
        cs = _set("A", "B")
        cs.configure("detector.qe_value")
        with pytest.raises(ConfigSetError, match="'A'"):
            cs.set_value("detector.qe_value", "A", "not-a-number")

    def test_set_value_converts_from_a_caller_unit(self) -> None:
        cs = _set("A", "B")
        cs.configure("optics.aperture_diameter_m")
        cs.set_value("optics.aperture_diameter_m", "B", 50.0, unit="cm")
        assert cs.configured()["optics.aperture_diameter_m"][1] == pytest.approx(0.50, rel=1e-12)
        assert cs.sensor_for("B").get("optics.aperture_diameter_m") == pytest.approx(
            0.50, rel=1e-12
        )
        assert cs.sensor_for("A").get("optics.aperture_diameter_m") == pytest.approx(
            0.30, rel=1e-12
        )

    def test_unknown_dotpath_keeps_the_did_you_mean_suggestion(self) -> None:
        cs = _set("A", "B")
        with pytest.raises(UnknownParameterError, match="Did you mean"):
            cs.configure("optics.apreture_diameter_m")
        with pytest.raises(UnknownParameterError, match="Did you mean"):
            cs.is_configured("optics.apreture_diameter_m")

    def test_set_value_on_a_shared_parameter_is_actionable(self) -> None:
        cs = _set("A", "B")
        with pytest.raises(ConfigSetError, match="is not configured") as excinfo:
            cs.set_value("detector.qe_value", "A", 0.5)
        assert "configure" in excinfo.value.action


# ---------------------------------------------------------------------------
# Consistency groups (plan §6 Phase 1)
# ---------------------------------------------------------------------------


class TestConsistencyGroups:
    def test_over_constrained_group_names_the_configuration(self) -> None:
        # The example sets both focal_length_m and aperture_diameter_m (f/4);
        # configuring f_number away from 4.0 over-constrains the group.
        cs = _set("A", "B")
        cs.configure("optics.f_number", [4.0, 6.0])
        # 'A' is consistent with the base (f/4) and resolves cleanly.
        assert cs.sensor_for("A").get("optics.f_number") == pytest.approx(4.0, rel=1e-12)
        with pytest.raises(ConfigSetError, match="configuration 'B' does not resolve") as excinfo:
            cs.sensor_for("B")
        assert "over-constrained" in excinfo.value.why
        assert excinfo.value.context["configuration"] == "B"

        status = cs.validate_all()
        assert status["A"] is None
        assert isinstance(status["B"], ConfigSetError)

    def test_after_resetting_the_base_each_configuration_derives_its_own_focal_length(
        self,
    ) -> None:
        cs = _set("A", "B")
        cs.configure("optics.f_number", [4.0, 6.0])
        cs.base.reset("optics.focal_length_m")  # let the group derive it per configuration
        assert cs.validate_all() == {"A": None, "B": None}
        aperture = 0.30
        assert cs.sensor_for("A").get("optics.focal_length_m") == pytest.approx(
            4.0 * aperture, rel=1e-12
        )
        assert cs.sensor_for("B").get("optics.focal_length_m") == pytest.approx(
            6.0 * aperture, rel=1e-12
        )
        # The derived member is in neither store — exactly as for a bare Sensor.
        assert "optics.focal_length_m" not in cs.base._params.inputs()
        assert "optics.focal_length_m" not in cs.configured()


# ---------------------------------------------------------------------------
# Configuration CRUD
# ---------------------------------------------------------------------------


class TestCrud:
    def test_default_set_is_one_configuration(self) -> None:
        cs = ConfigurationSet(_sensor())
        assert len(cs.names()) == 1
        assert cs.active == cs.baseline == cs.names()[0]
        assert dict(cs.configured()) == {}

    def test_add_seeds_from_configuration_one_and_copy_from_duplicates(self) -> None:
        cs = _set("A", "B")
        cs.configure("detector.qe_value", [0.75, 0.62])
        cs.add("C")
        assert cs.names() == ("A", "B", "C")
        assert cs.configured()["detector.qe_value"] == (0.75, 0.62, 0.75)
        cs.add("D", copy_from="B")
        assert cs.configured()["detector.qe_value"] == (0.75, 0.62, 0.75, 0.62)

    def test_add_rejects_duplicate_and_unknown_copy_from(self) -> None:
        cs = _set("A", "B")
        with pytest.raises(ConfigSetError, match="already exists"):
            cs.add("B")
        with pytest.raises(ConfigSetError, match="no configuration named 'ZZ'"):
            cs.add("C", copy_from="ZZ")
        assert cs.names() == ("A", "B")

    def test_ninth_configuration_rejected_actionably(self) -> None:
        cs = _set(*[f"c{i}" for i in range(8)])
        assert len(cs) == ConfigurationSet.MAX_CONFIGS
        with pytest.raises(ConfigSetError, match="at most 8") as excinfo:
            cs.add("c8")
        assert excinfo.value.context["max"] == 8
        assert excinfo.value.action
        with pytest.raises(ConfigSetError, match="at most 8"):
            ConfigurationSet(_sensor(), names=[f"c{i}" for i in range(9)])

    def test_construction_rejects_duplicates_empty_and_blank_names(self) -> None:
        with pytest.raises(ConfigSetError, match="duplicate"):
            ConfigurationSet(_sensor(), names=["A", "A"])
        with pytest.raises(ConfigSetError, match="at least one configuration"):
            ConfigurationSet(_sensor(), names=[])
        with pytest.raises(ConfigSetError, match="non-empty string"):
            ConfigurationSet(_sensor(), names=["A", "  "])
        with pytest.raises(ConfigSetError, match="must be a Sensor"):
            ConfigurationSet("not-a-sensor")  # type: ignore[arg-type]

    def test_remove_drops_the_column_and_reassigns_designations(self) -> None:
        cs = _set("A", "B", "C")
        cs.configure("detector.qe_value", [0.75, 0.62, 0.50])
        cs.active = "B"
        cs.baseline = "B"
        cs.remove("B")
        assert cs.names() == ("A", "C")
        assert cs.configured()["detector.qe_value"] == (0.75, 0.50)
        assert cs.active == "A" and cs.baseline == "A"

    def test_remove_last_configuration_rejected(self) -> None:
        cs = _set("solo")
        with pytest.raises(ConfigSetError, match="only configuration"):
            cs.remove("solo")

    def test_rename_keeps_position_values_and_designations(self) -> None:
        cs = _set("A", "B")
        cs.configure("detector.qe_value", [0.75, 0.62])
        cs.set_wavelength_points("B", 30)
        cs.active = "B"
        cs.baseline = "B"
        cs.rename("B", "LWIR")
        assert cs.names() == ("A", "LWIR")
        assert cs.configured()["detector.qe_value"] == (0.75, 0.62)
        assert cs.active == "LWIR" and cs.baseline == "LWIR"
        assert _evaluate(cs.sensor_for("LWIR")).wavelength_um.size == 30
        with pytest.raises(ConfigSetError, match="already taken"):
            cs.rename("A", "LWIR")

    def test_reorder_keeps_value_alignment(self) -> None:
        cs = _set("A", "B", "C")
        cs.configure("detector.qe_value", [0.75, 0.62, 0.50])
        cs.reorder(["C", "A", "B"])
        assert cs.names() == ("C", "A", "B")
        assert cs.configured()["detector.qe_value"] == (0.50, 0.75, 0.62)
        assert cs.sensor_for("A").get_input("detector.qe_value") == pytest.approx(0.75, rel=1e-12)
        assert cs.sensor_for("C").get_input("detector.qe_value") == pytest.approx(0.50, rel=1e-12)

    def test_reorder_must_be_a_permutation(self) -> None:
        cs = _set("A", "B", "C")
        for bad in (["A", "B"], ["A", "B", "D"], ["A", "B", "C", "C"]):
            with pytest.raises(ConfigSetError, match="permutation"):
                cs.reorder(bad)
        assert cs.names() == ("A", "B", "C")

    def test_baseline_and_active_must_name_a_member(self) -> None:
        cs = _set("A", "B")
        with pytest.raises(ConfigSetError, match="no configuration named 'ZZ'"):
            cs.baseline = "ZZ"
        with pytest.raises(ConfigSetError, match="no configuration named 'ZZ'"):
            cs.active = "ZZ"
        cs.baseline = "B"
        cs.active = "B"
        assert cs.baseline == "B" and cs.active == "B"
        assert "B" in cs and "ZZ" not in cs

    def test_repr_names_the_state(self) -> None:
        cs = _set("A", "B")
        cs.configure("detector.qe_value")
        text = repr(cs)
        assert "A" in text and "detector.qe_value" in text


# ---------------------------------------------------------------------------
# evaluate_all
# ---------------------------------------------------------------------------


class TestEvaluateAll:
    def test_active_configuration_is_evaluated_first(self) -> None:
        cs = _set("A", "B", "C")
        cs.active = "C"
        run = _evaluate_all(cs)
        assert run.names == ("C", "A", "B")
        assert run.n_failed == 0
        cs.active = "B"
        assert _evaluate_all(cs).names == ("B", "A", "C")

    def test_one_failing_configuration_captured_others_complete(self) -> None:
        cs = _set("good", "bad")
        cs.configure("optics.f_number", [4.0, 6.0])  # 'bad' over-constrains the group
        run = _evaluate_all(cs)
        assert run.n_failed == 1
        assert set(run.failures) == {"bad"}
        assert isinstance(run.failures["bad"], RadiantError)
        assert run.entry_for("good").ok
        assert run.result_for("good").metrics["snr"] > 0.0
        with pytest.raises(ConfigSetError, match="has no result"):
            run.result_for("bad")

    def test_run_result_lookup_of_an_unknown_configuration_is_actionable(self) -> None:
        cs = _set("A", "B")
        run = _evaluate_all(cs)
        with pytest.raises(ConfigSetError, match="no configuration named 'ZZ'"):
            run.entry_for("ZZ")

    def test_progress_called_per_configuration(self) -> None:
        cs = _set("A", "B", "C")
        calls: list[tuple[int, int]] = []
        _evaluate_all(cs, progress=lambda done, total: calls.append((done, total)))
        assert calls == [(1, 3), (2, 3), (3, 3)]

    def test_cancel_aborts_before_the_next_configuration(self) -> None:
        cs = _set("A", "B", "C")
        seen: list[str] = []

        def cancel() -> bool:
            return len(seen) >= 2

        original = cs.sensor_for

        def counting_sensor_for(name: str) -> Sensor:
            seen.append(name)
            return original(name)

        cs.sensor_for = counting_sensor_for  # type: ignore[method-assign]
        with pytest.raises(OperationCancelledError) as excinfo:
            _evaluate_all(cs, cancel=cancel)
        assert isinstance(excinfo.value, RadiantError)
        assert excinfo.value.done == 2
        assert excinfo.value.total == 3
        assert len(seen) == 2  # no further evaluations after cancel

    def test_cancel_before_any_work(self) -> None:
        cs = _set("A", "B")
        with pytest.raises(OperationCancelledError) as excinfo:
            _evaluate_all(cs, cancel=lambda: True)
        assert excinfo.value.done == 0

    def test_run_result_carries_the_baseline_designation(self) -> None:
        cs = _set("A", "B")
        cs.baseline = "B"
        assert _evaluate_all(cs).baseline == "B"


# ---------------------------------------------------------------------------
# Per-configuration wavelength grids (ADR-0010 D-F)
# ---------------------------------------------------------------------------


class TestWavelengthPoints:
    def test_point_count_differs_per_configuration(self) -> None:
        cs = _set("A", "B")
        cs.set_wavelength_points("B", 25)
        assert _evaluate(cs.sensor_for("A")).wavelength_um.size == _WL_POINTS
        assert _evaluate(cs.sensor_for("B")).wavelength_um.size == 25

    def test_shared_default_applies_to_configurations_without_an_override(self) -> None:
        cs = _set("A", "B")
        cs.set_wavelength_points(None, 20)
        cs.set_wavelength_points("B", 35)
        assert _evaluate(cs.sensor_for("A")).wavelength_um.size == 20
        assert _evaluate(cs.sensor_for("B")).wavelength_um.size == 35

    def test_band_driven_span_differs_with_a_shared_point_count(self) -> None:
        cs = _set("MWIR", "LWIR")
        cs.configure("spectral_integration.filter_min_um", [3.95, 8.0])
        cs.configure("spectral_integration.filter_max_um", [4.45, 12.0])
        mwir = _evaluate(cs.sensor_for("MWIR")).wavelength_um
        lwir = _evaluate(cs.sensor_for("LWIR")).wavelength_um
        assert mwir.size == lwir.size == _WL_POINTS  # shared count — the free path
        assert mwir[0] == pytest.approx(3.95, rel=1e-12)
        assert mwir[-1] == pytest.approx(4.45, rel=1e-12)
        assert lwir[0] == pytest.approx(8.0, rel=1e-12)
        assert lwir[-1] == pytest.approx(12.0, rel=1e-12)

    def test_invalid_point_counts_rejected(self) -> None:
        cs = _set("A", "B")
        for bad in (1, 0, -5, 2.5, True):
            with pytest.raises(ConfigSetError, match="integer >= 2"):
                cs.set_wavelength_points("A", bad)  # type: ignore[arg-type]
        with pytest.raises(ConfigSetError, match="no configuration named 'ZZ'"):
            cs.set_wavelength_points("ZZ", 100)


class TestWavelengthPointsAccessor:
    """CU-210 — the point-count state is readable, not write-only."""

    def test_shared_default_is_the_base_grid_until_one_is_set(self) -> None:
        cs = _set("A", "B")
        assert cs.wavelength_points() == _WL_POINTS
        cs.set_wavelength_points(None, 123)
        assert cs.wavelength_points() == 123

    def test_override_reads_back_and_none_means_inherits(self) -> None:
        cs = _set("A", "B")
        assert cs.wavelength_points("A") is None  # inherits the shared default
        cs.set_wavelength_points("A", 77)
        assert cs.wavelength_points("A") == 77
        assert cs.wavelength_points("B") is None
        # The reader distinguishes "inherits" from "equals the default".
        cs.set_wavelength_points(None, 77)
        assert cs.wavelength_points("B") is None
        assert cs.wavelength_points() == 77

    def test_round_trips_through_save_and_load(self, tmp_path: Path) -> None:
        cs = _set("MWIR", "LWIR")
        cs.set_wavelength_points("LWIR", 31)
        cs.set_wavelength_points(None, 22)
        loaded = ConfigurationSet.load(cs.save(tmp_path / "study.yaml"))
        assert loaded.wavelength_points() == 22
        assert loaded.wavelength_points("LWIR") == 31
        assert loaded.wavelength_points("MWIR") is None

    def test_rename_rekeys_the_override(self) -> None:
        """The ``_wl_points`` dict is keyed by name, so a rename must move the entry."""
        cs = _set("A", "B")
        cs.set_wavelength_points("B", 30)
        cs.rename("B", "LWIR")
        assert cs.wavelength_points("LWIR") == 30
        with pytest.raises(ConfigSetError, match="no configuration named 'B'"):
            cs.wavelength_points("B")

    def test_duplicate_copies_the_source_override(self) -> None:
        cs = _set("A", "B")
        cs.set_wavelength_points("B", 30)
        cs.add("C", copy_from="B")
        assert cs.wavelength_points("C") == 30
        cs.add("D")  # seeded from configuration #1, which has no override
        assert cs.wavelength_points("D") is None

    def test_remove_drops_the_override(self) -> None:
        cs = _set("A", "B")
        cs.set_wavelength_points("B", 30)
        cs.remove("B")
        cs.add("B")
        assert cs.wavelength_points("B") is None

    def test_none_clears_an_override_and_the_shared_default(self) -> None:
        cs = _set("A", "B")
        cs.set_wavelength_points("A", 60)
        cs.set_wavelength_points(None, 44)
        cs.set_wavelength_points("A", None)
        assert cs.wavelength_points("A") is None
        assert _evaluate(cs.sensor_for("A")).wavelength_um.size == 44
        cs.set_wavelength_points(None, None)
        assert cs.wavelength_points() == _WL_POINTS
        assert _evaluate(cs.sensor_for("A")).wavelength_um.size == _WL_POINTS

    def test_clearing_an_unknown_configuration_is_still_actionable(self) -> None:
        cs = _set("A", "B")
        with pytest.raises(ConfigSetError, match="no configuration named 'ZZ'"):
            cs.set_wavelength_points("ZZ", None)

    def test_sensor_exposes_its_own_point_count(self) -> None:
        sensor = _sensor(37)
        assert sensor.wavelength_points == 37
        assert sensor.with_wavelength_points(9).wavelength_points == 9
        assert sensor.wavelength_points == 37  # the original is untouched


class TestSetValuesUnit:
    """CU-211 — ``set_values`` converts a whole column from the caller's unit."""

    def test_column_is_converted_once_at_the_boundary(self) -> None:
        cs = _set("A", "B")
        cs.configure("geometry.sensor_altitude_m", [500_000.0, 600_000.0])
        cs.set_values("geometry.sensor_altitude_m", [450.0, 700.0], unit="km")
        assert cs.configured()["geometry.sensor_altitude_m"] == pytest.approx(
            (450_000.0, 700_000.0), rel=1e-12
        )

    def test_matches_per_row_set_value_conversion(self) -> None:
        """One ``set_values(unit=)`` must equal N ``set_value(unit=)`` calls."""
        column = _set("A", "B")
        column.configure("geometry.sensor_altitude_m", [500_000.0, 600_000.0])
        column.set_values("geometry.sensor_altitude_m", [450.0, 700.0], unit="km")

        rows = _set("A", "B")
        rows.configure("geometry.sensor_altitude_m", [500_000.0, 600_000.0])
        rows.set_value("geometry.sensor_altitude_m", "A", 450.0, unit="km")
        rows.set_value("geometry.sensor_altitude_m", "B", 700.0, unit="km")

        assert column.configured() == rows.configured()

    def test_omitted_unit_is_the_input_unit_as_before(self) -> None:
        cs = _set("A", "B")
        cs.configure("geometry.sensor_altitude_m", [500_000.0, 600_000.0])
        cs.set_values("geometry.sensor_altitude_m", [450_000.0, 700_000.0])
        assert cs.configured()["geometry.sensor_altitude_m"] == pytest.approx(
            (450_000.0, 700_000.0), rel=1e-12
        )

    def test_a_rejected_value_leaves_the_whole_column_untouched(self) -> None:
        """Atomicity survives the unit seam: convert-then-validate, then commit."""
        cs = _set("A", "B")
        cs.configure("geometry.sensor_altitude_m", [500_000.0, 600_000.0])
        before = cs.configured()["geometry.sensor_altitude_m"]
        with pytest.raises(ConfigSetError, match="'B'"):
            cs.set_values("geometry.sensor_altitude_m", [450.0, -700.0], unit="km")
        assert cs.configured()["geometry.sensor_altitude_m"] == before

    def test_unknown_unit_is_rejected_actionably(self) -> None:
        cs = _set("A", "B")
        cs.configure("geometry.sensor_altitude_m", [500_000.0, 600_000.0])
        before = cs.configured()["geometry.sensor_altitude_m"]
        with pytest.raises(ConfigSetError):
            cs.set_values("geometry.sensor_altitude_m", [450.0, 700.0], unit="furlong")
        assert cs.configured()["geometry.sensor_altitude_m"] == before


class TestClone:
    """``clone()`` — the set-level thread-isolation snapshot (GUI Phase 4a)."""

    def test_copies_names_table_designations_and_grids(self) -> None:
        cs = _set("MWIR", "LWIR")
        cs.configure("detector.qe_value", [0.70, 0.55])
        cs.set_wavelength_points("LWIR", 31)
        cs.set_wavelength_points(None, 22)
        cs.active = "LWIR"
        cs.baseline = "LWIR"

        copy = cs.clone()
        assert copy.names() == cs.names()
        assert dict(copy.configured()) == dict(cs.configured())
        assert copy.active == "LWIR"
        assert copy.baseline == "LWIR"
        # Both wavelength-point stores travel: the per-configuration override and
        # the shared default (neither has a public read accessor — CU-210).
        assert _evaluate(copy.sensor_for("LWIR")).wavelength_um.size == 31
        assert _evaluate(copy.sensor_for("MWIR")).wavelength_um.size == 22

    def test_is_fully_independent_in_both_directions(self) -> None:
        cs = _set("A", "B")
        cs.configure("detector.qe_value", [0.70, 0.55])
        copy = cs.clone()

        copy.set_value("detector.qe_value", "A", 0.10)
        copy.base.set("optics.aperture_diameter_m", 0.9)
        copy.add("C")
        assert cs.configured()["detector.qe_value"] == (0.70, 0.55)
        assert cs.base.inputs()["optics.aperture_diameter_m"] == pytest.approx(0.30, rel=1e-12)
        assert cs.names() == ("A", "B")

        cs.set_value("detector.qe_value", "B", 0.99)
        assert copy.configured()["detector.qe_value"][1] == pytest.approx(0.55, rel=1e-12)

    def test_clone_evaluates_identically(self) -> None:
        cs = _set("A", "B")
        cs.configure("spectral_integration.filter_max_um", [5.0, 4.6])
        original = _evaluate_all(cs)
        copied = _evaluate_all(cs.clone())
        for name in cs.names():
            assert original.result_for(name).metrics["snr"] == pytest.approx(
                copied.result_for(name).metrics["snr"], rel=1e-12
            )


class TestSensorWithWavelengthPoints:
    def test_returns_a_clone_leaving_the_original_untouched(self) -> None:
        s = _sensor(points=50)
        other = s.with_wavelength_points(20)
        assert other is not s
        assert _evaluate(other).wavelength_um.size == 20
        assert _evaluate(s).wavelength_um.size == 50
        # Independent state: an edit to the clone does not reach the original.
        other.set("detector.qe_value", 0.1)
        assert s.get("detector.qe_value") == pytest.approx(0.70, rel=1e-12)

    def test_rejects_fewer_than_two_points(self) -> None:
        s = _sensor()
        for bad in (1, 0, -3, 2.5, True, "40"):
            with pytest.raises(ApiValidationError, match="integer >= 2"):
                s.with_wavelength_points(bad)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Degenerate case: one configuration ≡ a bare Sensor
# ---------------------------------------------------------------------------


class TestDegenerateCase:
    def test_single_configuration_metrics_identical_to_a_bare_sensor(self) -> None:
        bare = _evaluate(_sensor())
        cs = ConfigurationSet(_sensor())
        run = _evaluate_all(cs)
        assert run.n_failed == 0
        metrics = run.result_for(cs.names()[0]).metrics
        assert set(metrics) == set(bare.metrics)
        for name, value in bare.metrics.items():
            assert metrics[name] == pytest.approx(value, rel=1e-12, abs=1e-30)

    def test_single_configuration_inputs_identical_to_the_base(self) -> None:
        cs = ConfigurationSet(_sensor())
        assert dict(cs.sensor_for(cs.names()[0])._params.inputs()) == dict(
            _sensor()._params.inputs()
        )


# ---------------------------------------------------------------------------
# compare() adapter
# ---------------------------------------------------------------------------


class TestCompareAdapter:
    def test_matches_a_hand_built_compare_configs_call(self) -> None:
        cs = _set("MWIR", "LWIR")
        cs.configure("detector.qe_value", [0.75, 0.62])
        run = _evaluate_all(cs)
        adapted = cs.compare(run)
        hand = compare_configs(
            [(name, run.result_for(name)) for name in cs.names()],
            baseline=0,
        )
        assert adapted.labels == hand.labels == ("MWIR", "LWIR")
        assert adapted.baseline_index == hand.baseline_index == 0
        assert [r.name for r in adapted.rows] == [r.name for r in hand.rows]
        for got, want in zip(adapted.rows, hand.rows, strict=True):
            assert got.values == want.values
            assert got.deltas == want.deltas
            assert got.best_index == want.best_index

    def test_columns_follow_set_order_not_evaluation_order(self) -> None:
        cs = _set("MWIR", "LWIR")
        cs.configure("detector.qe_value", [0.75, 0.62])
        cs.active = "LWIR"
        run = _evaluate_all(cs)
        assert run.names == ("LWIR", "MWIR")  # evaluation order
        assert cs.compare(run).labels == ("MWIR", "LWIR")  # stable comparison order

    def test_baseline_designation_selects_the_delta_reference(self) -> None:
        cs = _set("MWIR", "LWIR")
        cs.configure("detector.qe_value", [0.75, 0.62])
        cs.baseline = "LWIR"
        cmp_ = cs.compare(_evaluate_all(cs))
        assert cmp_.baseline_index == 1
        assert cmp_.row("snr").deltas[1] == 0.0

    def test_a_failed_configuration_blocks_comparison_by_name(self) -> None:
        cs = _set("good", "bad")
        cs.configure("optics.f_number", [4.0, 6.0])
        run = _evaluate_all(cs)
        with pytest.raises(ConfigSetError, match=r"\['bad'\]") as excinfo:
            cs.compare(run)
        assert excinfo.value.context["failed"] == ["bad"]
        assert "compare_configs" in excinfo.value.action


# ---------------------------------------------------------------------------
# Result-object surface
# ---------------------------------------------------------------------------


class TestRunResultSurface:
    def test_config_run_ok_flag(self) -> None:
        ok = ConfigRun(name="A", result=None, error=None)
        bad = ConfigRun(name="B", result=None, error=ConfigSetError("boom"))
        assert ok.ok and not bad.ok
        run = ConfigSetRunResult(entries=(ok, bad), baseline="A")
        assert run.names == ("A", "B")
        assert run.n_failed == 1
        assert list(run.failures) == ["B"]


# ---------------------------------------------------------------------------
# Phase 3 — per-configuration warning attribution
# ---------------------------------------------------------------------------


class TestWarningAttribution:
    """A warning raised by configuration X belongs to X and to nothing else."""

    def test_real_chain_warning_lands_only_on_the_configuration_that_raised_it(self) -> None:
        # Real physics-chain warning path, not a stub: ReadoutStage warns when
        # the ADC full scale is badly mismatched to the full well (>10x either
        # way) and again when the ADC clips. gain = 1 e-/DN at 16 bits reaches
        # 6.55e4 e- against a 2e6 e- well (ratio 0.033), so 'mismatched' warns
        # in that configuration only — 'matched' keeps the example's 32 e-/DN.
        cs = _set("matched", "mismatched")
        cs.configure("readout.gain_e_per_dn", [32.0, 1.0])
        run = cs.evaluate_all()  # deliberately NOT wrapped: capture is internal

        assert run.n_failed == 0
        assert run.entry_for("matched").warnings == ()
        offending = run.entry_for("mismatched").warnings
        assert len(offending) >= 1
        assert all(w.startswith("UserWarning: ") for w in offending)
        assert any("badly mismatched" in w for w in offending)
        # Attribution is exclusive: the run-level view names only the offender.
        assert set(run.warnings) == {"mismatched"}
        assert run.n_warnings == len(offending)

    def test_capture_is_per_configuration_not_per_pass(self, monkeypatch: Any) -> None:
        # Two configurations warn with distinct messages; neither inherits the
        # other's. A single capture window around the whole pass would put both
        # messages on both configurations (or on neither).
        cs = _set("A", "B", "C")
        original = ConfigurationSet.sensor_for

        def warning_sensor_for(self: ConfigurationSet, name: str) -> Sensor:
            sensor = original(self, name)
            if name in ("A", "C"):
                warnings.warn(f"probe from {name}", UserWarning, stacklevel=1)
            return sensor

        monkeypatch.setattr(ConfigurationSet, "sensor_for", warning_sensor_for)
        run = cs.evaluate_all()

        assert run.entry_for("A").warnings == ("UserWarning: probe from A",)
        assert run.entry_for("B").warnings == ()
        assert run.entry_for("C").warnings == ("UserWarning: probe from C",)
        assert run.n_warnings == 2

    def test_a_failing_configuration_still_reports_the_warnings_it_raised(
        self, monkeypatch: Any
    ) -> None:
        cs = _set("good", "bad")
        original = ConfigurationSet.sensor_for

        def warn_then_fail(self: ConfigurationSet, name: str) -> Sensor:
            if name == "bad":
                warnings.warn("about to fail", UserWarning, stacklevel=1)
                raise ConfigSetError(what="configuration 'bad' does not resolve")
            return original(self, name)

        monkeypatch.setattr(ConfigurationSet, "sensor_for", warn_then_fail)
        run = cs.evaluate_all()

        bad = run.entry_for("bad")
        assert not bad.ok
        assert bad.warnings == ("UserWarning: about to fail",)
        assert run.entry_for("good").warnings == ()

    def test_captured_warnings_are_logged_not_dropped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        cs = _set("matched", "mismatched")
        cs.configure("readout.gain_e_per_dn", [32.0, 1.0])
        with caplog.at_level(logging.WARNING, logger="radiant.api.config_set"):
            cs.evaluate_all()
        logged = [rec.getMessage() for rec in caplog.records]
        assert any("Configuration 'mismatched' warned" in m for m in logged)
        assert not any("Configuration 'matched' warned" in m for m in logged)

    def test_capture_does_not_leak_the_always_filter_to_the_caller(self) -> None:
        cs = _set("A", "B")
        before = list(warnings.filters)
        _evaluate_all(cs)
        assert list(warnings.filters) == before


# ---------------------------------------------------------------------------
# Phase 3 — baseline deltas with a metric absent from one configuration
# ---------------------------------------------------------------------------


class TestBaselineDeltaSemantics:
    @staticmethod
    def _three_configs() -> ConfigurationSet:
        """A, B, C differing in QE; C computes no saturation-group metrics."""
        cs = _set("A", "B", "C")
        cs.configure("detector.qe_value", [0.70, 0.50, 0.60])
        # Gap 96 metric selection: deselecting the saturation group in C alone
        # makes well_margin_dB / adc_margin_dB / dynamic_range_dB genuinely
        # absent from C's result — the "metric missing in one configuration"
        # case the plan calls for.
        cs.configure("performance.metrics.saturation", [True, True, False])
        return cs

    def test_absent_metric_is_none_never_zero(self) -> None:
        cs = self._three_configs()
        cmp_ = cs.compare(_evaluate_all(cs))
        row = cmp_.row("well_margin_dB")
        assert row.values[2] is None
        assert row.deltas[2] is None
        assert row.values[0] is not None and row.values[1] is not None
        # The present configurations still carry real numbers (Rule 17: absent
        # is absent, it does not zero-fill the column or blank the others).
        assert row.unit == "dB"

    def test_deltas_are_measured_against_the_named_baseline(self) -> None:
        cs = self._three_configs()
        cs.baseline = "B"
        cmp_ = cs.compare(_evaluate_all(cs))
        assert cmp_.labels == ("A", "B", "C")
        assert cmp_.baseline_index == 1
        snr = cmp_.row("snr")
        assert snr.deltas[1] == 0.0
        base_value = snr.values[1]
        assert base_value is not None
        for i in (0, 2):
            value, delta = snr.values[i], snr.deltas[i]
            assert value is not None and delta is not None
            assert delta == pytest.approx(value - base_value, rel=1e-12)

    def test_delta_is_none_when_the_baseline_itself_lacks_the_metric(self) -> None:
        cs = self._three_configs()
        cs.baseline = "C"  # C has no saturation metrics
        cmp_ = cs.compare(_evaluate_all(cs))
        row = cmp_.row("well_margin_dB")
        assert row.values[0] is not None and row.values[1] is not None
        assert row.deltas == (None, None, None)  # no reference ⇒ no delta, not 0.0

    def test_column_order_is_set_order_independent_of_baseline_and_active(self) -> None:
        cs = self._three_configs()
        cs.active = "C"
        cs.baseline = "B"
        run = _evaluate_all(cs)
        assert run.names == ("C", "A", "B")  # evaluation order
        assert cs.compare(run).labels == cs.names() == ("A", "B", "C")


# ---------------------------------------------------------------------------
# Phase 3 — failed-configuration ergonomics and summary()
# ---------------------------------------------------------------------------


class TestFailedConfigurationErgonomics:
    @staticmethod
    def _one_failing() -> tuple[ConfigurationSet, ConfigSetRunResult]:
        cs = _set("good", "bad")
        cs.configure("optics.f_number", [4.0, 6.0])  # 'bad' over-constrains
        return cs, _evaluate_all(cs)

    def test_compare_raises_rather_than_dropping_the_failed_column(self) -> None:
        cs, run = self._one_failing()
        with pytest.raises(ConfigSetError) as excinfo:
            cs.compare(run)
        exc = excinfo.value
        assert exc.context["failed"] == ["bad"]
        assert "run.failures" in exc.action
        # The documented escape hatch actually works on the surviving subset.
        survivors = [(n, run.result_for(n)) for n in run.names if run.entry_for(n).ok]
        assert [label for label, _ in survivors] == ["good"]

    def test_documented_subset_escape_hatch_compares_the_survivors(self) -> None:
        cs = _set("good", "also_good", "bad")
        cs.configure("optics.f_number", [4.0, 4.0, 6.0])
        run = _evaluate_all(cs)
        assert run.n_failed == 1
        survivors = [(n, run.result_for(n)) for n in cs.names() if run.entry_for(n).ok]
        cmp_ = compare_configs(survivors, baseline=0)
        assert cmp_.labels == ("good", "also_good")

    def test_summary_renders_a_partially_failed_pass_without_raising(self) -> None:
        _cs, run = self._one_failing()
        text = run.summary()
        lines = text.splitlines()
        assert len(lines) == len(run.entries) + 1
        good_line = next(ln for ln in lines if ln.startswith("good"))
        bad_line = next(ln for ln in lines if ln.startswith("bad"))
        assert "ok" in good_line
        assert "FAILED" in bad_line
        assert "does not resolve" in bad_line
        assert "1 of 2 configuration(s) failed" in lines[-1]

    def test_summary_metric_values_all_carry_units(self) -> None:
        cs = _set("A", "B")
        cs.configure("detector.qe_value", [0.70, 0.50])
        line = _evaluate_all(cs).summary().splitlines()[0]
        assert "snr = " in line and "[dimensionless]" in line
        assert "nedt_K = " in line and "[K]" in line
        assert "gsd_geometric_mean_m = " in line and "[m]" in line
        # Every "name = value" pair on the line is followed by a [unit] token.
        assert line.count(" = ") == line.count("[")

    def test_summary_omits_a_headline_metric_the_configuration_did_not_compute(
        self,
    ) -> None:
        cs = _set("full", "no_radiometry")
        cs.configure("performance.metrics.radiometric", [True, False])
        lines = _evaluate_all(cs).summary().splitlines()
        full_line = next(ln for ln in lines if ln.startswith("full"))
        thin_line = next(ln for ln in lines if ln.startswith("no_radiometry"))
        assert "snr = " in full_line and "nedt_K = " in full_line
        assert "snr = " not in thin_line and "nedt_K = " not in thin_line
        assert "0" not in thin_line.split("ok")[1].split("gsd")[0]  # not zero-filled
        assert "gsd_geometric_mean_m = " in thin_line

    def test_summary_marks_the_baseline_and_counts_warnings(self) -> None:
        cs = _set("matched", "mismatched")
        cs.configure("readout.gain_e_per_dn", [32.0, 1.0])
        cs.baseline = "mismatched"
        lines = cs.evaluate_all().summary().splitlines()
        marked = [ln for ln in lines if " * " in ln]
        assert len(marked) == 1 and marked[0].startswith("mismatched")
        assert "warning" in marked[0]
        assert "warning" not in next(ln for ln in lines if ln.startswith("matched"))
        assert "baseline: 'mismatched'" in lines[-1]
