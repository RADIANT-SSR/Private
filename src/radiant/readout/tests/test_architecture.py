"""Tests for the readout-architecture schema and dispatch skeleton (Gap 117 Phase 0).

Covers the five digital-pixel (DROIC) v1 parameters from
``docs/plans/Digital_Pixel_Readout_Plan.md`` §3, the cross-parameter
validation matrix (Rule 16), the ``digital_counting`` not-implemented
dispatch, and the serialization round trip. Counting physics is Phase 1;
nothing here asserts counting results.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import (
    ParameterBoundsError,
    ParameterEnumError,
    ParameterSet,
    Provenance,
)
from radiant.io.config import load_config, save_config
from radiant.readout._schema import ALL_PARAMETERS as RO_PARAMS
from radiant.readout.errors import ReadoutValidationError
from radiant.readout.stage import ReadoutStage

_COUNTING_ONLY = (
    "readout.counter_bits",
    "readout.count_packet_e",
    "readout.residue_readout",
    "readout.max_count_rate_hz",
)


def _params(**overrides: object) -> ParameterSet:
    """Readout-only ParameterSet with optional dot-path overrides."""
    ps = ParameterSet(list(RO_PARAMS))
    for name, value in overrides.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


def _state() -> ChainState:
    return ChainState(wavelength_um=np.linspace(3.5, 5.0, 10))


class TestSchemaDefs:
    """The five v1 parameters exist with the plan §3 shapes."""

    @pytest.fixture()
    def defs(self) -> dict[str, object]:
        return {p.name: p for p in RO_PARAMS}

    @pytest.mark.level1
    def test_architecture_enum(self, defs) -> None:  # type: ignore[no-untyped-def]
        d = defs["readout.architecture"]
        assert d.dtype is str
        assert d.default == "analog_well"
        assert d.enum_values == ("analog_well", "digital_counting")

    @pytest.mark.level1
    def test_counter_bits(self, defs) -> None:  # type: ignore[no-untyped-def]
        d = defs["readout.counter_bits"]
        assert d.dtype is int
        assert d.default == 16
        assert d.bounds == (1, 32)

    @pytest.mark.level1
    def test_count_packet_e(self, defs) -> None:  # type: ignore[no-untyped-def]
        d = defs["readout.count_packet_e"]
        assert d.dtype is float
        assert d.default == 0.0  # 0.0 = unset sentinel; required when counting
        assert d.bounds == (0.0, 1.0e7)
        assert d.canonical_unit == "e-"

    @pytest.mark.level1
    def test_residue_readout(self, defs) -> None:  # type: ignore[no-untyped-def]
        d = defs["readout.residue_readout"]
        assert d.dtype is bool
        assert d.default is True

    @pytest.mark.level1
    def test_max_count_rate_hz(self, defs) -> None:  # type: ignore[no-untyped-def]
        d = defs["readout.max_count_rate_hz"]
        assert d.dtype is float
        assert d.default == 0.0  # 0.0 = unset sentinel; no dead-time ceiling
        assert d.canonical_unit == "Hz"

    @pytest.mark.level1
    def test_architecture_rejects_unknown_value(self) -> None:
        with pytest.raises(ParameterEnumError, match="readout.architecture"):
            _params(readout__architecture="digital_wishing")

    @pytest.mark.level1
    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("readout.counter_bits", 0),
            ("readout.counter_bits", 33),
            ("readout.count_packet_e", -1.0),
            ("readout.count_packet_e", 2.0e7),
            ("readout.max_count_rate_hz", -1.0),
        ],
    )
    def test_out_of_bounds_rejected(self, name: str, value: float) -> None:
        with pytest.raises(ParameterBoundsError, match=name.replace(".", r"\.")):
            _params(**{name.replace(".", "__"): value})


class TestArchitectureValidation:
    """Rule 16 cross-parameter matrix — errors are actionable (Rule 15)."""

    @pytest.mark.level1
    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("readout.counter_bits", 12),
            ("readout.count_packet_e", 5000.0),
            ("readout.residue_readout", False),
            ("readout.max_count_rate_hz", 1.0e6),
        ],
    )
    def test_counting_param_under_analog_rejected(self, name: str, value: object) -> None:
        ps = _params(**{name.replace(".", "__"): value})
        with pytest.raises(ReadoutValidationError, match="analog_well") as exc:
            ReadoutStage().run(_state(), ps)
        assert name in str(exc.value)
        assert "digital_counting" in str(exc.value)  # actionable: names the fix

    @pytest.mark.level1
    def test_counting_param_rejected_even_at_default_value(self) -> None:
        """Explicitly setting the default value still over-specifies analog."""
        ps = _params(readout__residue_readout=True)
        with pytest.raises(ReadoutValidationError, match="residue_readout"):
            ReadoutStage().run(_state(), ps)

    @pytest.mark.level1
    def test_explicit_analog_with_counting_param_rejected(self) -> None:
        ps = _params(readout__architecture="analog_well", readout__counter_bits=16)
        with pytest.raises(ReadoutValidationError, match="counter_bits"):
            ReadoutStage().run(_state(), ps)

    @pytest.mark.level1
    def test_count_packet_required_when_counting(self) -> None:
        ps = _params(readout__architecture="digital_counting")
        with pytest.raises(ReadoutValidationError, match="count_packet_e") as exc:
            ReadoutStage().run(_state(), ps)
        assert "required" in str(exc.value)
        # Structural routing seam (Gap 117 Phase 3): the missing-packet state
        # is the dedicated incomplete-config subclass, and the published
        # predicate recognizes it — message surfaces route on this, so a
        # class change here silently reintroduces the modal-wall regression.
        from radiant.readout.errors import (
            CountingConfigIncompleteError,
            is_counting_config_incomplete,
        )

        assert isinstance(exc.value, CountingConfigIncompleteError)
        assert is_counting_config_incomplete(exc.value)

    @pytest.mark.level1
    def test_count_packet_zero_is_unset(self) -> None:
        """An explicit 0.0 packet is the unset sentinel — still required."""
        ps = _params(
            readout__architecture="digital_counting",
            readout__count_packet_e=0.0,
        )
        with pytest.raises(ReadoutValidationError, match="required"):
            ReadoutStage().run(_state(), ps)

    @pytest.mark.level1
    def test_explicit_full_well_under_counting_rejected(self) -> None:
        ps = _params(
            readout__architecture="digital_counting",
            readout__count_packet_e=5000.0,
            readout__full_well_capacity_e=100000.0,
        )
        with pytest.raises(ReadoutValidationError, match="full_well_capacity_e") as exc:
            ReadoutStage().run(_state(), ps)
        assert "over-specifies" in str(exc.value)

    @pytest.mark.level1
    def test_default_full_well_under_counting_passes_validation(self) -> None:
        """The schema *default* full well passes silently (plan §3) — the run
        proceeds into the counting branch and stops only on the bare state's
        missing detector budget (Phase 2: dispatch is live)."""
        ps = _params(
            readout__architecture="digital_counting",
            readout__count_packet_e=5000.0,
        )
        with pytest.raises(ReadoutValidationError, match="noise_budget_raw"):
            ReadoutStage().run(_state(), ps)


class TestDispatchSkeleton:
    @pytest.mark.level1
    def test_digital_counting_dispatch_is_live(self) -> None:
        """A fully valid counting config enters the counting branch (Phase 2):
        on a bare state it fails on the missing detector budget, exactly like
        the analog branch — not on a not-implemented error."""
        ps = _params(
            readout__architecture="digital_counting",
            readout__counter_bits=16,
            readout__count_packet_e=5000.0,
            readout__residue_readout=True,
            readout__max_count_rate_hz=2.0e6,
        )
        with pytest.raises(ReadoutValidationError, match="noise_budget_raw"):
            ReadoutStage().run(_state(), ps)

    @pytest.mark.level1
    def test_analog_default_unaffected(self) -> None:
        """All five new parameters at defaults: the analog path still fails
        only on the missing detector budget, exactly as before Phase 0."""
        with pytest.raises(ReadoutValidationError, match="noise_budget_raw"):
            ReadoutStage().run(_state(), _params())


class TestSerializationRoundTrip:
    @pytest.mark.level1
    def test_yaml_round_trip_preserves_values_and_provenance(self, tmp_path: Path) -> None:
        ps = ParameterSet(list(RO_PARAMS))
        ps.set("readout.architecture", "digital_counting")
        ps.set("readout.counter_bits", 14)
        ps.set("readout.count_packet_e", 4500.0)
        ps.set("readout.residue_readout", False)
        ps.set("readout.max_count_rate_hz", 2.5e6)
        ps.resolve()

        path = save_config(ps, tmp_path / "droic.yaml", scope="inputs")
        ps2 = ParameterSet(list(RO_PARAMS))
        load_config(path, ps2)
        ps2.resolve()

        for name in ("readout.architecture", *_COUNTING_ONLY):
            rv1, rv2 = ps.get_resolved(name), ps2.get_resolved(name)
            assert rv2.value == rv1.value, name
            assert type(rv2.value) is type(rv1.value), name  # bool stays bool, int stays int
            # Explicit inputs stay explicit (config_file on reload, by design),
            # so stage validation sees the same explicit/defaulted split.
            assert rv2.provenance is Provenance.CONFIG_FILE, name

    @pytest.mark.level1
    def test_defaults_stay_defaults_through_round_trip(self, tmp_path: Path) -> None:
        """Unset counting params reload as DEFAULT provenance — critical for
        the explicit-set validation matrix (a round trip must not convert a
        defaulted counting parameter into an explicit over-specification)."""
        ps = _params(readout__read_noise_e_rms=7.0)  # unrelated explicit input
        path = save_config(ps, tmp_path / "analog.yaml", scope="inputs")
        ps2 = ParameterSet(list(RO_PARAMS))
        load_config(path, ps2)
        ps2.resolve()

        for name in ("readout.architecture", *_COUNTING_ONLY):
            assert ps2.get_resolved(name).provenance is Provenance.DEFAULT, name
        # And the reloaded set still runs the analog path without an
        # architecture-validation error (fails later only on the bare state).
        with pytest.raises(ReadoutValidationError, match="noise_budget_raw"):
            ReadoutStage().run(_state(), ps2)
