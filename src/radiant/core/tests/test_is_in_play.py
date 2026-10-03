"""Level 0: ``ParameterSet.is_in_play`` — the over-specification guard predicate (CU-392).

Guards must ask "is this value in play?" rather than "did the user touch this?".
Three shipped defects came from conflating them, each making the obvious
clearing gesture raise instead of work: a dark rate zeroed before entering a
density (Gap 135), an activation energy set to its own default under a
predictive dark model (Gap 123), and a count packet set to its own default
under an analog well (CU-392).

Built from core primitives only — a core test may not reach the api or io
layers (import-linter contract).
"""

from __future__ import annotations

import pytest

from radiant.core.parameters import ParameterDef, ParameterSet


def _schema() -> list[ParameterDef]:
    """A miniature schema spanning the dtypes a real guard covers."""
    return [
        # default IS the no-op (the common case)
        ParameterDef(
            name="x.packet_e",
            description="",
            dtype=float,
            canonical_unit="e-",
            input_unit="e-",
            default=0.0,
            bounds=(0.0, 1e9),
        ),
        # a non-zero default, so 0.0 is NOT the default
        ParameterDef(
            name="x.rate",
            description="",
            dtype=float,
            canonical_unit="1/s",
            input_unit="1/s",
            default=100.0,
            bounds=(0.0, 1e12),
        ),
        # non-float dtypes: 0.0 is meaningless for these
        ParameterDef(
            name="x.bits",
            description="",
            dtype=int,
            canonical_unit="",
            input_unit="",
            default=16,
            bounds=(1, 32),
        ),
        ParameterDef(
            name="x.mode",
            description="",
            dtype=str,
            canonical_unit="",
            input_unit="",
            default="up",
            enum_values=("up", "up_down"),
        ),
        ParameterDef(
            name="x.flag",
            description="",
            dtype=bool,
            canonical_unit="",
            input_unit="",
            default=True,
        ),
    ]


def _resolved(**sets: object) -> ParameterSet:
    ps = ParameterSet(_schema())
    for name, value in sets.items():
        ps.set(f"x.{name}", value)
    ps.resolve()
    return ps


class TestNeverSet:
    @pytest.mark.level0
    @pytest.mark.parametrize("name", ["x.packet_e", "x.rate", "x.bits", "x.mode", "x.flag"])
    def test_an_untouched_parameter_is_not_in_play(self, name: str) -> None:
        assert _resolved().is_in_play(name) is False


class TestSetToItsOwnDefault:
    """The universal rule: that cannot over-specify anything."""

    @pytest.mark.level0
    @pytest.mark.parametrize(
        ("key", "default"),
        [("packet_e", 0.0), ("rate", 100.0), ("bits", 16), ("mode", "up"), ("flag", True)],
    )
    def test_explicitly_setting_the_default_is_not_in_play(self, key: str, default: object) -> None:
        assert _resolved(**{key: default}).is_in_play(f"x.{key}") is False

    @pytest.mark.level0
    def test_this_is_why_zero_is_not_the_universal_no_op(self) -> None:
        """int 16, str 'up' and bool True are all no-ops; none of them is 0.0."""
        ps = _resolved(bits=16, mode="up", flag=True)
        assert not any(ps.is_in_play(n) for n in ("x.bits", "x.mode", "x.flag"))


class TestSetToSomethingReal:
    @pytest.mark.level0
    @pytest.mark.parametrize(
        ("key", "value"), [("packet_e", 8000.0), ("bits", 20), ("mode", "up_down"), ("flag", False)]
    )
    def test_a_changed_value_is_in_play(self, key: str, value: object) -> None:
        assert _resolved(**{key: value}).is_in_play(f"x.{key}") is True


class TestInertValues:
    """The per-parameter escape: a no-op that is NOT the default."""

    @pytest.mark.level0
    def test_zero_is_inert_for_a_rate_whose_default_is_not_zero(self) -> None:
        ps = _resolved(rate=0.0)
        assert ps.is_in_play("x.rate") is True  # without the escape
        assert ps.is_in_play("x.rate", inert_values=(0.0,)) is False  # with it

    @pytest.mark.level0
    def test_a_real_value_stays_in_play_with_the_escape_declared(self) -> None:
        assert _resolved(rate=250.0).is_in_play("x.rate", inert_values=(0.0,)) is True

    @pytest.mark.level0
    def test_several_inert_values_are_all_honoured(self) -> None:
        ps = _resolved(rate=0.0)
        assert ps.is_in_play("x.rate", inert_values=(0.0, 1.0)) is False

    @pytest.mark.level0
    def test_an_escape_that_does_not_match_leaves_it_in_play(self) -> None:
        assert _resolved(rate=250.0).is_in_play("x.rate", inert_values=(0.0, 1.0)) is True
