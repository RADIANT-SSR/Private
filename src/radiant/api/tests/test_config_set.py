"""Tests for ``ConfigurationSet`` — multi-configuration core model.

Covers the Phase 1 test list of ``docs/plans/Multi_Configuration_Plan.md`` §6
against the model ratified in ``docs/adr/0010-multi-configuration-model.md``:
materialization/isolation/provenance, the single-store invariant, the
consistency-group story, CRUD edge cases, ``evaluate_all`` ordering and
failure capture, per-configuration wavelength grids, the degenerate
single-configuration case, and the ``compare`` adapter.
"""

from __future__ import annotations

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
        assert lwir.get_input("spectral_integration.filter_min_um") == pytest.approx(
            8.0, rel=1e-12
        )
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
