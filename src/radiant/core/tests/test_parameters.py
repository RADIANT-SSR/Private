"""Level 0 tests for radiant.core.parameters.

Covers: ParameterDef, Tolerance, ConsistencyGroup, ResolvedValue, ParameterSet.
All tests use @pytest.mark.level0.  pytest.approx always specifies rel= or abs=.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from radiant.core.parameters import (
    ConsistencyGroup,
    ParameterDef,
    ParameterSet,
    Provenance,
    ResolvedValue,
    Tolerance,
)

# ---------------------------------------------------------------------------
# Helpers — minimal schema used by many tests
# ---------------------------------------------------------------------------


def _make_fno_schema() -> tuple[list[ParameterDef], list[ConsistencyGroup]]:
    """Return a 3-param schema (aperture, focal_length, f_number) + fno group."""
    schema = [
        ParameterDef(
            name="sensor.optics.aperture_diameter",
            description="Clear aperture diameter",
            dtype=float,
            canonical_unit="m",
            input_unit="m",
        ),
        ParameterDef(
            name="sensor.optics.focal_length",
            description="Effective focal length",
            dtype=float,
            canonical_unit="m",
            input_unit="m",
        ),
        ParameterDef(
            name="sensor.optics.f_number",
            description="Focal ratio (f/#)",
            dtype=float,
            canonical_unit="",
            input_unit="",
        ),
    ]
    fno_group = ConsistencyGroup(
        name="optics_fno",
        parameters=(
            "sensor.optics.f_number",
            "sensor.optics.focal_length",
            "sensor.optics.aperture_diameter",
        ),
        constraint="f_number = focal_length / aperture_diameter",
        derivations={
            "sensor.optics.f_number": lambda p: (
                p["sensor.optics.focal_length"] / p["sensor.optics.aperture_diameter"]
            ),
            "sensor.optics.focal_length": lambda p: (
                p["sensor.optics.f_number"] * p["sensor.optics.aperture_diameter"]
            ),
            "sensor.optics.aperture_diameter": lambda p: (
                p["sensor.optics.focal_length"] / p["sensor.optics.f_number"]
            ),
        },
    )
    return schema, [fno_group]


def _make_ps() -> ParameterSet:
    schema, groups = _make_fno_schema()
    return ParameterSet(schema, groups)


# ---------------------------------------------------------------------------
# ParameterDef tests
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_parameterdef_frozen() -> None:
    """ParameterDef is a frozen dataclass — assignment raises FrozenInstanceError."""
    pdef = ParameterDef(
        name="x.y",
        description="test",
        dtype=float,
        canonical_unit="m",
        input_unit="m",
    )
    with pytest.raises(FrozenInstanceError):
        pdef.name = "new_name"  # type: ignore[misc]


@pytest.mark.level0
def test_parameterdef_invalid_dtype() -> None:
    """dtype not in (float, int, str, bool) raises ValueError."""
    with pytest.raises(ValueError, match="dtype must be float"):
        ParameterDef(
            name="x.y",
            description="test",
            dtype=list,
            canonical_unit="",
            input_unit="",
        )


@pytest.mark.level0
def test_parameterdef_enum_values_requires_str() -> None:
    """enum_values with non-str dtype raises ValueError."""
    with pytest.raises(ValueError, match="enum_values requires dtype=str"):
        ParameterDef(
            name="x.y",
            description="test",
            dtype=int,
            canonical_unit="",
            input_unit="",
            enum_values=("a", "b"),
        )


@pytest.mark.level0
def test_parameterdef_bounds_requires_numeric() -> None:
    """bounds with non-numeric dtype raises ValueError."""
    with pytest.raises(ValueError, match="bounds requires numeric dtype"):
        ParameterDef(
            name="x.y",
            description="test",
            dtype=str,
            canonical_unit="",
            input_unit="",
            bounds=(0.0, 1.0),
        )


# ---------------------------------------------------------------------------
# Tolerance tests
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_tolerance_gaussian_absolute() -> None:
    """gaussian with std= draws near the nominal."""
    rng = np.random.default_rng(42)
    tol = Tolerance("gaussian", {"std": 0.01})
    samples = [tol.sample(1.0, rng) for _ in range(1000)]
    mean = float(np.mean(samples))
    assert mean == pytest.approx(1.0, abs=0.05)


@pytest.mark.level0
def test_tolerance_gaussian_fractional() -> None:
    """gaussian with std_fraction= uses std = fraction * nominal."""
    rng = np.random.default_rng(42)
    tol = Tolerance("gaussian", {"std_fraction": 0.1})
    samples = [tol.sample(2.0, rng) for _ in range(1000)]
    mean = float(np.mean(samples))
    # std should be 0.2; mean should be near 2.0
    assert mean == pytest.approx(2.0, abs=0.1)


@pytest.mark.level0
def test_tolerance_uniform_in_range() -> None:
    """uniform samples lie in [low, high]."""
    rng = np.random.default_rng(42)
    tol = Tolerance("uniform", {"low": 0.5, "high": 1.5})
    samples = [tol.sample(1.0, rng) for _ in range(1000)]
    assert all(0.5 <= s <= 1.5 for s in samples)
    mean = float(np.mean(samples))
    assert mean == pytest.approx(1.0, abs=0.05)


@pytest.mark.level0
def test_tolerance_truncated_gaussian_in_bounds() -> None:
    """truncated_gaussian samples stay within [low, high]."""
    rng = np.random.default_rng(42)
    tol = Tolerance("truncated_gaussian", {"std": 0.5, "low": 0.0, "high": 2.0})
    samples = [tol.sample(1.0, rng) for _ in range(500)]
    assert all(0.0 <= s <= 2.0 for s in samples)


@pytest.mark.level0
def test_tolerance_log_normal_positive() -> None:
    """log_normal samples are always positive."""
    rng = np.random.default_rng(42)
    tol = Tolerance("log_normal", {"sigma": 0.1})
    samples = [tol.sample(1.0, rng) for _ in range(500)]
    assert all(s > 0.0 for s in samples)


@pytest.mark.level0
def test_tolerance_unknown_distribution() -> None:
    """Unknown distribution raises ValueError."""
    rng = np.random.default_rng(42)
    tol = Tolerance("banana_distribution", {})
    with pytest.raises(ValueError, match="Unknown distribution"):
        tol.sample(1.0, rng)


# ---------------------------------------------------------------------------
# ParameterSet — basic consistency group tests
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_derive_f_number_from_aperture_and_fl() -> None:
    """Set aperture=0.3m, fl=1.2m → derive f_number=4.0."""
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", 0.3)
    ps.set("sensor.optics.focal_length", 1.2)
    ps.resolve()
    assert ps.get("sensor.optics.f_number") == pytest.approx(4.0, rel=1e-12)


@pytest.mark.level0
def test_derive_focal_length_from_aperture_and_fno() -> None:
    """Set aperture=0.3m, fno=4.0 → derive fl=1.2m."""
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", 0.3)
    ps.set("sensor.optics.f_number", 4.0)
    ps.resolve()
    assert ps.get("sensor.optics.focal_length") == pytest.approx(1.2, rel=1e-12)


@pytest.mark.level0
def test_derive_aperture_from_fl_and_fno() -> None:
    """Set fl=1.2m, fno=4.0 → derive aperture=0.3m."""
    ps = _make_ps()
    ps.set("sensor.optics.focal_length", 1.2)
    ps.set("sensor.optics.f_number", 4.0)
    ps.resolve()
    assert ps.get("sensor.optics.aperture_diameter") == pytest.approx(0.3, rel=1e-12)


@pytest.mark.level0
def test_all_three_consistent_no_error() -> None:
    """Setting all three parameters consistently resolves without error."""
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", 0.3)
    ps.set("sensor.optics.focal_length", 1.2)
    ps.set("sensor.optics.f_number", 4.0)
    ps.resolve()  # must not raise
    assert ps.get("sensor.optics.f_number") == pytest.approx(4.0, rel=1e-12)


@pytest.mark.level0
def test_all_three_inconsistent_raises() -> None:
    """Setting all three inconsistently raises ValueError mentioning both values."""
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", 0.3)
    ps.set("sensor.optics.focal_length", 1.2)
    ps.set("sensor.optics.f_number", 5.0)  # inconsistent: should be 4.0
    with pytest.raises(ValueError) as exc_info:
        ps.resolve()
    msg = str(exc_info.value)
    # Must show the user-specified value AND the computed value
    assert "5.0" in msg
    assert "4.0" in msg


@pytest.mark.level0
def test_missing_required_parameter_raises() -> None:
    """Missing required parameter raises ValueError naming the parameter."""
    ps = _make_ps()
    # Only set one — the group needs N-1 = 2, so the one remaining is still unknown
    # But if we set none, all three are unset and also required with no default
    ps.set("sensor.optics.aperture_diameter", 0.3)
    # focal_length and f_number are both unset — only one can be derived
    with pytest.raises(ValueError) as exc_info:
        ps.resolve()
    msg = str(exc_info.value)
    # One of the missing required params should be named
    assert "sensor.optics." in msg


@pytest.mark.level0
def test_get_before_resolve_raises_runtime_error() -> None:
    """`get()` before `resolve()` raises RuntimeError."""
    ps = _make_ps()
    with pytest.raises(RuntimeError, match="resolve"):
        ps.get("sensor.optics.f_number")


@pytest.mark.level0
def test_set_unknown_parameter_raises_key_error() -> None:
    """`set()` with an unknown parameter name raises KeyError."""
    ps = _make_ps()
    with pytest.raises(KeyError, match="sensor.optics.nonexistent"):
        ps.set("sensor.optics.nonexistent", 1.0)


# ---------------------------------------------------------------------------
# explain() tests
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_explain_derived_contains_provenance_info() -> None:
    """explain() on a derived parameter mentions DERIVED and source parameters."""
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", 0.3)
    ps.set("sensor.optics.focal_length", 1.2)
    ps.resolve()
    text = ps.explain("sensor.optics.f_number")
    assert "derived" in text.lower()
    # Should mention what it was derived from
    assert "focal_length" in text or "aperture_diameter" in text


@pytest.mark.level0
def test_explain_default_mentions_default() -> None:
    """explain() on a default parameter mentions 'default'."""
    schema = [
        ParameterDef(
            name="sensor.detector.qe",
            description="Quantum efficiency",
            dtype=float,
            canonical_unit="",
            input_unit="",
            default=0.8,
            default_justification="Typical CMOS QE",
        )
    ]
    ps = ParameterSet(schema)
    ps.resolve()
    text = ps.explain("sensor.detector.qe")
    assert "default" in text.lower()
    assert "Typical CMOS QE" in text


@pytest.mark.level0
def test_explain_user_set_mentions_user() -> None:
    """explain() on a user-set parameter mentions user provenance."""
    schema = [
        ParameterDef(
            name="sensor.detector.qe",
            description="Quantum efficiency",
            dtype=float,
            canonical_unit="",
            input_unit="",
        )
    ]
    ps = ParameterSet(schema)
    ps.set("sensor.detector.qe", 0.7)
    ps.resolve()
    text = ps.explain("sensor.detector.qe")
    assert "user" in text.lower() or "user_set" in text.lower()


# ---------------------------------------------------------------------------
# Provenance tests
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_to_provenance_record_fields() -> None:
    """`to_provenance_record()` returns a dict with required top-level fields."""
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", 0.3)
    ps.set("sensor.optics.focal_length", 1.2)
    ps.resolve()
    record = ps.to_provenance_record("0.1.0")
    assert "radiant_version" in record
    assert "resolved_at" in record
    assert "parameters" in record
    assert record["radiant_version"] == "0.1.0"


@pytest.mark.level0
def test_to_provenance_record_json_round_trip() -> None:
    """Provenance record serializes to JSON and back preserving values."""
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", 0.3)
    ps.set("sensor.optics.focal_length", 1.2)
    ps.resolve()
    record = ps.to_provenance_record("0.1.0")
    serialized = json.dumps(record)
    restored = json.loads(serialized)
    assert restored["radiant_version"] == "0.1.0"
    ap = restored["parameters"]["sensor.optics.aperture_diameter"]
    assert ap["value"] == pytest.approx(0.3, rel=1e-12)
    fl = restored["parameters"]["sensor.optics.focal_length"]
    assert fl["value"] == pytest.approx(1.2, rel=1e-12)
    fno = restored["parameters"]["sensor.optics.f_number"]
    assert fno["provenance"] == "derived"
    assert fno["value"] == pytest.approx(4.0, rel=1e-12)


# ---------------------------------------------------------------------------
# Monte Carlo tests
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_sample_returns_new_parameter_set() -> None:
    """`sample()` returns a new ParameterSet (distinct object)."""
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", 0.3)
    ps.set("sensor.optics.focal_length", 1.2)
    ps.set_tolerance("sensor.optics.aperture_diameter", Tolerance("gaussian", {"std": 0.001}))
    ps.resolve()
    rng = np.random.default_rng(99)
    sampled = ps.sample(rng)
    assert sampled is not ps


@pytest.mark.level0
def test_sample_produces_different_values() -> None:
    """Multiple samples produce different values for toleranced parameters."""
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", 0.3)
    ps.set("sensor.optics.focal_length", 1.2)
    ps.set_tolerance("sensor.optics.aperture_diameter", Tolerance("gaussian", {"std": 0.01}))
    ps.resolve()
    rng = np.random.default_rng(7)
    vals = {ps.sample(rng).get("sensor.optics.aperture_diameter") for _ in range(10)}
    assert len(vals) > 1  # Not all identical


@pytest.mark.level0
def test_sample_stays_in_bounds_with_truncated_gaussian() -> None:
    """Sampled values from truncated_gaussian stay within declared bounds."""
    schema = [
        ParameterDef(
            name="sensor.detector.qe",
            description="Quantum efficiency",
            dtype=float,
            canonical_unit="",
            input_unit="",
            bounds=(0.0, 1.0),
        )
    ]
    ps = ParameterSet(schema)
    ps.set("sensor.detector.qe", 0.8)
    ps.set_tolerance(
        "sensor.detector.qe",
        Tolerance("truncated_gaussian", {"std": 0.05, "low": 0.0, "high": 1.0}),
    )
    ps.resolve()
    rng = np.random.default_rng(11)
    for _ in range(100):
        s = ps.sample(rng)
        val = s.get("sensor.detector.qe")
        assert 0.0 <= val <= 1.0


# ---------------------------------------------------------------------------
# Error message quality tests
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_error_msg_missing_required_contains_param_name() -> None:
    """Missing required param: error contains the parameter name."""
    schema = [
        ParameterDef(
            name="sensor.optics.aperture_diameter",
            description="Clear aperture",
            dtype=float,
            canonical_unit="m",
            input_unit="m",
        )
    ]
    ps = ParameterSet(schema)
    with pytest.raises(ValueError) as exc_info:
        ps.resolve()
    assert "sensor.optics.aperture_diameter" in str(exc_info.value)


@pytest.mark.level0
def test_error_msg_missing_required_contains_set_instruction() -> None:
    """Missing required param: error contains instruction on how to set it."""
    schema = [
        ParameterDef(
            name="sensor.optics.aperture_diameter",
            description="Clear aperture",
            dtype=float,
            canonical_unit="m",
            input_unit="m",
        )
    ]
    ps = ParameterSet(schema)
    with pytest.raises(ValueError) as exc_info:
        ps.resolve()
    msg = str(exc_info.value)
    assert "Set it via" in msg or "params.set" in msg


@pytest.mark.level0
def test_error_msg_unknown_param_key_error() -> None:
    """set() with unknown param: KeyError contains the parameter name."""
    ps = _make_ps()
    with pytest.raises(KeyError) as exc_info:
        ps.set("sensor.optics.does_not_exist", 1.0)
    assert "sensor.optics.does_not_exist" in str(exc_info.value)


@pytest.mark.level0
def test_error_msg_over_constrained_shows_both_values() -> None:
    """Over-constrained group: error shows both the user-specified and computed values."""
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", 0.3)
    ps.set("sensor.optics.focal_length", 1.2)
    ps.set("sensor.optics.f_number", 5.0)  # inconsistent; computed = 4.0
    with pytest.raises(ValueError) as exc_info:
        ps.resolve()
    msg = str(exc_info.value)
    assert "5.0" in msg  # user-specified
    assert "4.0" in msg  # computed


@pytest.mark.level0
def test_error_msg_wrong_type_shows_param_name_and_expected_type() -> None:
    """Wrong type: error message shows the parameter name and expected type."""
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", "not_a_float")
    with pytest.raises(ValueError) as exc_info:
        ps.resolve()
    msg = str(exc_info.value)
    assert "sensor.optics.aperture_diameter" in msg
    assert "float" in msg


# ---------------------------------------------------------------------------
# Chained consistency group test
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_chained_groups_resolve_in_multiple_passes() -> None:
    """Two chained groups resolve correctly even if listed in reverse order.

    Group 1: B = 2 * A
    Group 2: C = B + 1
    Set A = 5 → expect B = 10, C = 11.
    """
    schema = [
        ParameterDef(
            name="chain.A", description="A", dtype=float, canonical_unit="", input_unit=""
        ),
        ParameterDef(
            name="chain.B", description="B", dtype=float, canonical_unit="", input_unit=""
        ),
        ParameterDef(
            name="chain.C", description="C", dtype=float, canonical_unit="", input_unit=""
        ),
    ]
    group1 = ConsistencyGroup(
        name="g1",
        parameters=("chain.A", "chain.B"),
        constraint="B = 2 * A",
        derivations={
            "chain.B": lambda p: 2.0 * p["chain.A"],
            "chain.A": lambda p: p["chain.B"] / 2.0,
        },
    )
    group2 = ConsistencyGroup(
        name="g2",
        parameters=("chain.B", "chain.C"),
        constraint="C = B + 1",
        derivations={
            "chain.C": lambda p: p["chain.B"] + 1.0,
            "chain.B": lambda p: p["chain.C"] - 1.0,
        },
    )
    # Declare groups in reverse order to test that ordering doesn't matter
    ps = ParameterSet(schema, [group2, group1])
    ps.set("chain.A", 5.0)
    ps.resolve()
    assert ps.get("chain.B") == pytest.approx(10.0, rel=1e-12)
    assert ps.get("chain.C") == pytest.approx(11.0, rel=1e-12)


# ---------------------------------------------------------------------------
# Circular dependency test
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_circular_dependency_raises_value_error() -> None:
    """Circular groups (A←→B) where neither is user-set raises ValueError.

    We set up:
      Group 1: A derived from B
      Group 2: B derived from A
    Neither A nor B is user-provided, and neither has a default.
    The fixed-point loop must detect the cycle and raise.
    """
    schema = [
        ParameterDef(name="cyc.A", description="A", dtype=float, canonical_unit="", input_unit=""),
        ParameterDef(name="cyc.B", description="B", dtype=float, canonical_unit="", input_unit=""),
        ParameterDef(
            name="cyc.C",
            description="C",
            dtype=float,
            canonical_unit="",
            input_unit="",
            default=1.0,
        ),
    ]
    # A depends on B and B depends on A — true cycle
    group_ab = ConsistencyGroup(
        name="g_ab",
        parameters=("cyc.A", "cyc.B"),
        constraint="A = B * 2 (and B = A / 2)",
        derivations={
            "cyc.A": lambda p: p["cyc.B"] * 2.0,
            "cyc.B": lambda p: p["cyc.A"] / 2.0,
        },
    )
    ps = ParameterSet(schema, [group_ab])
    # Do NOT set either A or B — the cycle has no entry point
    ps.set("cyc.C", 1.0)
    with pytest.raises(ValueError, match="[Cc]ircular|[Cc]ycle|could not be resolved"):
        ps.resolve()


# ---------------------------------------------------------------------------
# ResolvedValue serialization tests
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_resolved_value_to_dict_json_serializable() -> None:
    """ResolvedValue.to_dict() returns a JSON-serializable dict."""
    rv = ResolvedValue(
        name="sensor.optics.aperture_diameter",
        value=0.3,
        input_value=0.3,
        canonical_unit="m",
        input_unit="m",
        provenance=Provenance.USER_SET,
        source="user",
        derived_from=None,
    )
    d = rv.to_dict()
    serialized = json.dumps(d)
    restored = json.loads(serialized)
    assert restored["value"] == pytest.approx(0.3, rel=1e-12)
    assert restored["canonical_unit"] == "m"
    assert restored["provenance"] == "user_set"
    assert restored["source"] == "user"
    assert restored["derived_from"] is None


@pytest.mark.level0
def test_resolved_value_round_trip_all_fields() -> None:
    """ResolvedValue.to_dict() round-trip preserves all fields."""
    rv = ResolvedValue(
        name="sensor.optics.f_number",
        value=4.0,
        input_value=4.0,
        canonical_unit="",
        input_unit="",
        provenance=Provenance.DERIVED,
        source="derived: f_number = focal_length / aperture_diameter",
        derived_from={
            "sensor.optics.focal_length": 1.2,
            "sensor.optics.aperture_diameter": 0.3,
        },
    )
    d = rv.to_dict()
    serialized = json.dumps(d)
    restored = json.loads(serialized)
    assert restored["value"] == pytest.approx(4.0, rel=1e-12)
    assert restored["provenance"] == "derived"
    fl_key = "sensor.optics.focal_length"
    ap_key = "sensor.optics.aperture_diameter"
    assert restored["derived_from"][fl_key] == pytest.approx(1.2, rel=1e-12)
    assert restored["derived_from"][ap_key] == pytest.approx(0.3, rel=1e-12)
    assert "timestamp" in restored


# ---------------------------------------------------------------------------
# Fuzzy match / "did you mean?" suggestions
# ---------------------------------------------------------------------------


class TestParameterSuggestions:
    """Verify that KeyError messages include 'did you mean?' suggestions."""

    def _make_ps(self) -> ParameterSet:
        schema = [
            ParameterDef(
                name="optics.focal_length_m",
                description="",
                dtype=float,
                canonical_unit="m",
                input_unit="m",
                default=1.0,
            ),
            ParameterDef(
                name="optics.aperture_diameter_m",
                description="",
                dtype=float,
                canonical_unit="m",
                input_unit="m",
                default=0.3,
            ),
            ParameterDef(
                name="detector.pixel_pitch_x_um",
                description="",
                dtype=float,
                canonical_unit="m",
                input_unit="um",
                default=18.0,
            ),
            ParameterDef(
                name="atmosphere.model",
                description="",
                dtype=str,
                canonical_unit="",
                input_unit="",
                default="simple",
                enum_values=("simple",),
            ),
        ]
        return ParameterSet(schema)

    @pytest.mark.level0
    def test_set_close_match(self) -> None:
        """Typo in set() suggests the correct name."""
        ps = self._make_ps()
        with pytest.raises(KeyError, match="Did you mean"):
            ps.set("optics.focal_length", 1.2)

    @pytest.mark.level0
    def test_set_suggests_correct_name(self) -> None:
        """Suggestion includes the actual parameter name."""
        ps = self._make_ps()
        with pytest.raises(KeyError, match="optics.focal_length_m"):
            ps.set("optics.focal_length", 1.2)

    @pytest.mark.level0
    def test_set_mode_vs_model(self) -> None:
        """Gap #7 scenario: atmosphere.mode → suggests atmosphere.model."""
        ps = self._make_ps()
        with pytest.raises(KeyError, match="atmosphere.model"):
            ps.set("atmosphere.mode", "simple")

    @pytest.mark.level0
    def test_set_no_match(self) -> None:
        """Completely unrelated name gives no suggestions."""
        ps = self._make_ps()
        with pytest.raises(KeyError, match="Unknown parameter"):
            ps.set("completely.unrelated.thing", 42)

    @pytest.mark.level0
    def test_set_no_match_no_did_you_mean(self) -> None:
        """No 'Did you mean' when there's no close match."""
        ps = self._make_ps()
        with pytest.raises(KeyError) as exc_info:
            ps.set("completely.unrelated.thing", 42)
        assert "Did you mean" not in str(exc_info.value)

    @pytest.mark.level0
    def test_get_close_match(self) -> None:
        """Typo in get() suggests the correct name."""
        ps = self._make_ps()
        ps.resolve()
        with pytest.raises(KeyError, match="Did you mean"):
            ps.get("detector.pixel_pitch_x")

    @pytest.mark.level0
    def test_get_suggests_correct_name(self) -> None:
        """get() suggestion includes the actual parameter name."""
        ps = self._make_ps()
        ps.resolve()
        with pytest.raises(KeyError, match="detector.pixel_pitch_x_um"):
            ps.get("detector.pixel_pitch_x")

    @pytest.mark.level0
    def test_set_tolerance_close_match(self) -> None:
        """Typo in set_tolerance() suggests the correct name."""
        ps = self._make_ps()
        tol = Tolerance(distribution="gaussian", params={"std": 0.01})
        with pytest.raises(KeyError, match="Did you mean"):
            ps.set_tolerance("optics.aperture_diameter", tol)

    @pytest.mark.level0
    def test_load_dict_close_match(self) -> None:
        """Typo in load_dict() suggests the correct name (delegates to set)."""
        ps = self._make_ps()
        with pytest.raises(KeyError, match="Did you mean"):
            ps.load_dict({"optics.focal_length": 1.2})


# ---------------------------------------------------------------------------
# clear_input (CU-046)
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_clear_input_removes_value_and_allows_rederivation() -> None:
    """Clearing an input lets the consistency group re-derive the parameter."""
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", 0.30)
    ps.set("sensor.optics.focal_length", 1.5)
    assert ps.clear_input("sensor.optics.focal_length") is True
    ps.set("sensor.optics.f_number", 4.0)
    ps.resolve()
    # focal_length derives from the group (0.30 m x f/4), not the cleared 1.5 m
    assert ps.get("sensor.optics.focal_length") == pytest.approx(1.2, rel=1e-12)


@pytest.mark.level0
def test_clear_input_invalidates_resolution() -> None:
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", 0.30)
    ps.set("sensor.optics.focal_length", 1.5)
    ps.resolve()
    assert ps.get("sensor.optics.f_number") == pytest.approx(5.0, rel=1e-12)
    ps.clear_input("sensor.optics.focal_length")
    with pytest.raises(RuntimeError, match="not resolved"):
        ps.get("sensor.optics.f_number")


@pytest.mark.level0
def test_clear_input_absent_is_noop_and_keeps_resolution() -> None:
    """Clearing a never-set input returns False and does not invalidate."""
    ps = _make_ps()
    ps.set("sensor.optics.aperture_diameter", 0.30)
    ps.set("sensor.optics.focal_length", 1.5)
    ps.resolve()
    assert ps.clear_input("sensor.optics.f_number") is False
    # Still resolved — no invalidation for a no-op clear.
    assert ps.get("sensor.optics.f_number") == pytest.approx(5.0, rel=1e-12)


@pytest.mark.level0
def test_clear_input_unknown_name_suggests() -> None:
    ps = _make_ps()
    with pytest.raises(KeyError, match="Did you mean"):
        ps.clear_input("sensor.optics.focal_lenght")


class TestUnitAwareSet:
    """Gap 6: set() accepts a caller-native unit and converts at the boundary.

    Truth anchors (Dr. Chen's scenario-6.3 native units):
      1. 30 cm aperture → 0.30 m canonical (input_unit m).
      2. 5 ms integration time → 0.005 s canonical.
      3. 70 % QE → 0.70 fraction.
    """

    def _pset(self) -> ParameterSet:
        return ParameterSet(
            [
                ParameterDef(
                    name="t.length_m",
                    description="length",
                    dtype=float,
                    canonical_unit="m",
                    input_unit="m",
                    default=1.0,
                ),
                ParameterDef(
                    name="t.pitch_um",
                    description="pitch",
                    dtype=float,
                    canonical_unit="m",
                    input_unit="um",
                    default=18.0,
                ),
                ParameterDef(
                    name="t.time_s",
                    description="time",
                    dtype=float,
                    canonical_unit="s",
                    input_unit="s",
                    default=1.0,
                ),
                ParameterDef(
                    name="t.fraction",
                    description="fraction",
                    dtype=float,
                    canonical_unit="",
                    input_unit="",
                    default=0.5,
                    bounds=(0.0, 1.0),
                ),
                ParameterDef(
                    name="t.mode",
                    description="mode",
                    dtype=str,
                    canonical_unit="",
                    input_unit="",
                    default="a",
                ),
            ]
        )

    @pytest.mark.level0
    def test_cm_to_m(self) -> None:
        ps = self._pset()
        ps.set("t.length_m", 30.0, unit="cm")
        ps.resolve()
        assert ps.get("t.length_m") == pytest.approx(0.30, rel=1e-12)

    @pytest.mark.level0
    def test_ms_to_s(self) -> None:
        ps = self._pset()
        ps.set("t.time_s", 5.0, unit="ms")
        ps.resolve()
        assert ps.get("t.time_s") == pytest.approx(5.0e-3, rel=1e-12)

    @pytest.mark.level0
    def test_percent_to_fraction(self) -> None:
        ps = self._pset()
        ps.set("t.fraction", 70.0, unit="%")
        ps.resolve()
        assert ps.get("t.fraction") == pytest.approx(0.70, rel=1e-12)

    def test_cross_unit_to_nonsi_input_unit(self) -> None:
        """cm input on a µm-input-unit parameter: cm → m → µm → canonical m."""
        ps = self._pset()
        ps.set("t.pitch_um", 0.0018, unit="cm")
        ps.resolve()
        assert ps.get("t.pitch_um") == pytest.approx(18e-6, rel=1e-12)

    def test_same_unit_passthrough(self) -> None:
        ps = self._pset()
        ps.set("t.pitch_um", 18.0, unit="um")
        ps.resolve()
        assert ps.get("t.pitch_um") == pytest.approx(18e-6, rel=1e-12)

    def test_no_unit_is_historical_behavior(self) -> None:
        ps = self._pset()
        ps.set("t.length_m", 0.30)
        ps.resolve()
        assert ps.get("t.length_m") == pytest.approx(0.30, rel=1e-12)

    def test_bounds_checked_after_conversion(self) -> None:
        """150 % → 1.5 fraction must fail the [0, 1] bounds check."""
        ps = self._pset()
        ps.set("t.fraction", 150.0, unit="%")
        with pytest.raises(ValueError, match="out of bounds"):
            ps.resolve()

    def test_unknown_unit_actionable_error(self) -> None:
        ps = self._pset()
        with pytest.raises(ValueError, match="no registered conversion"):
            ps.set("t.length_m", 1.0, unit="furlong")

    def test_unit_on_str_param_rejected(self) -> None:
        ps = self._pset()
        with pytest.raises(ValueError, match="numeric"):
            ps.set("t.mode", "a", unit="m")

    def test_provenance_records_original(self) -> None:
        ps = self._pset()
        ps.set("t.length_m", 30.0, unit="cm")
        ps.resolve()
        assert "30.0 cm" in ps.get_resolved("t.length_m").source


class TestDeprecatedAliases:
    """Gap 12: renamed parameters keep working via deprecated aliases."""

    def _pset(self) -> ParameterSet:
        return ParameterSet(
            [
                ParameterDef(
                    name="ns.new_name",
                    description="renamed",
                    dtype=float,
                    canonical_unit="",
                    input_unit="",
                    default=1.0,
                    bounds=(0.0, 1.0),
                    deprecated_aliases=frozenset({"ns.old_name"}),
                ),
            ]
        )

    def test_set_via_alias_warns_and_redirects(self) -> None:
        ps = self._pset()
        with pytest.warns(DeprecationWarning, match="ns.new_name"):
            ps.set("ns.old_name", 0.25)
        ps.resolve()
        assert ps.get("ns.new_name") == pytest.approx(0.25, rel=1e-12)

    def test_get_via_alias_warns(self) -> None:
        ps = self._pset()
        ps.set("ns.new_name", 0.5)
        ps.resolve()
        with pytest.warns(DeprecationWarning):
            assert ps.get("ns.old_name") == pytest.approx(0.5, rel=1e-12)

    def test_canonical_name_no_warning(self) -> None:
        import warnings as _warnings

        ps = self._pset()
        with _warnings.catch_warnings():
            _warnings.simplefilter("error", DeprecationWarning)
            ps.set("ns.new_name", 0.5)
            ps.resolve()
            assert ps.get("ns.new_name") == pytest.approx(0.5, rel=1e-12)

    def test_unknown_name_still_suggests(self) -> None:
        ps = self._pset()
        with pytest.raises(KeyError, match="Did you mean"):
            ps.set("ns.new_nam", 0.5)

    def test_alias_collision_with_real_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="collides"):
            ParameterSet(
                [
                    ParameterDef(
                        name="ns.a",
                        description="a",
                        dtype=float,
                        canonical_unit="",
                        input_unit="",
                        default=0.0,
                    ),
                    ParameterDef(
                        name="ns.b",
                        description="b",
                        dtype=float,
                        canonical_unit="",
                        input_unit="",
                        default=0.0,
                        deprecated_aliases=frozenset({"ns.a"}),
                    ),
                ]
            )

    def test_self_alias_rejected(self) -> None:
        with pytest.raises(ValueError, match="alias itself"):
            ParameterDef(
                name="ns.a",
                description="a",
                dtype=float,
                canonical_unit="",
                input_unit="",
                default=0.0,
                deprecated_aliases=frozenset({"ns.a"}),
            )


# ---------------------------------------------------------------------------
# required_unless (Gap 66)
# ---------------------------------------------------------------------------


def _make_required_unless_schema() -> list[ParameterDef]:
    """A required scalar superseded by an optional path parameter."""
    return [
        ParameterDef(
            name="det.scalar",
            description="required scalar",
            dtype=float,
            canonical_unit="",
            input_unit="",
            default=None,
            required_unless="det.table_path",
        ),
        ParameterDef(
            name="det.table_path",
            description="superseding table path",
            dtype=str,
            canonical_unit="",
            input_unit="",
            default="",
        ),
    ]


class TestRequiredUnless:
    @pytest.mark.level0
    def test_neither_set_raises_with_hint(self) -> None:
        ps = ParameterSet(_make_required_unless_schema())
        with pytest.raises(ValueError, match="det.scalar"):
            ps.resolve()
        try:
            ps.resolve()
        except ValueError as exc:
            assert "supersedes" in str(exc)
            assert "det.table_path" in str(exc)

    @pytest.mark.level0
    def test_alternative_set_silences_requirement(self) -> None:
        ps = ParameterSet(_make_required_unless_schema())
        ps.set("det.table_path", "some/file.csv", Provenance.USER_SET, "test")
        ps.resolve()  # must not raise
        # The skipped parameter is left unresolved, not phantom-populated.
        with pytest.raises(KeyError, match="not resolved"):
            ps.get("det.scalar")
        assert ps.get("det.table_path") == "some/file.csv"

    @pytest.mark.level0
    def test_empty_string_alternative_does_not_silence(self) -> None:
        ps = ParameterSet(_make_required_unless_schema())
        ps.set("det.table_path", "", Provenance.USER_SET, "test")
        with pytest.raises(ValueError, match="det.scalar"):
            ps.resolve()

    @pytest.mark.level0
    def test_both_set_scalar_still_resolves(self) -> None:
        ps = ParameterSet(_make_required_unless_schema())
        ps.set("det.scalar", 0.7, Provenance.USER_SET, "test")
        ps.set("det.table_path", "some/file.csv", Provenance.USER_SET, "test")
        ps.resolve()
        assert ps.get("det.scalar") == pytest.approx(0.7, abs=1e-12)

    @pytest.mark.level0
    def test_required_unless_on_defaulted_param_rejected(self) -> None:
        with pytest.raises(ValueError, match="required_unless only applies"):
            ParameterDef(
                name="ns.a",
                description="a",
                dtype=float,
                canonical_unit="",
                input_unit="",
                default=1.0,
                required_unless="ns.b",
            )

    @pytest.mark.level0
    def test_required_unless_self_reference_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot reference itself"):
            ParameterDef(
                name="ns.a",
                description="a",
                dtype=float,
                canonical_unit="",
                input_unit="",
                default=None,
                required_unless="ns.a",
            )
