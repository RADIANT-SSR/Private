"""Level-0/1 tests for the path-segment data contract (``segments.py``).

The contract carries no physics, so these tests pin exactly what it promises:
the validation gates (Rule 16 — validate before compute) and the invariants
downstream composition relies on.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.protocol import ZENITH_CEILING_RAD
from radiant.atmosphere.segments import (
    ColumnSegmentSpec,
    LevelArmSpec,
    SegmentQuantities,
    validate_wavelength_grid,
)
from radiant.core.parameters import ParameterBoundsError


def _grid() -> np.ndarray:
    return np.linspace(3.0, 14.0, 12)


def _quantities(**overrides: np.ndarray) -> SegmentQuantities:
    lam = _grid()
    fields: dict[str, np.ndarray] = {
        "wavelength_um": lam,
        "tau": np.full_like(lam, 0.5),
        "L_toward_upper": np.full_like(lam, 1.0),
        "L_toward_lower": np.full_like(lam, 2.0),
    }
    fields.update(overrides)
    return SegmentQuantities(**fields)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ColumnSegmentSpec
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_column_spec_accepts_vertical_and_slant() -> None:
    """The canonical cases construct and expose their thickness."""
    vertical = ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e4, zeta_low_rad=0.0)
    assert vertical.thickness_m == pytest.approx(1.0e4, abs=0.0)
    assert vertical.kind == "column"

    slant = ColumnSegmentSpec(h_low_m=5.0e3, h_high_m=1.5e4, zeta_low_rad=math.radians(45.0))
    assert slant.thickness_m == pytest.approx(1.0e4, abs=0.0)


@pytest.mark.level0
def test_column_spec_zero_thickness_is_legal() -> None:
    """h_high == h_low is the exact vacuum limit, not an error."""
    spec = ColumnSegmentSpec(h_low_m=2.0e3, h_high_m=2.0e3, zeta_low_rad=0.3)
    assert spec.thickness_m == 0.0


@pytest.mark.level0
def test_column_spec_rejects_inverted_endpoints() -> None:
    with pytest.raises(ParameterBoundsError, match="below"):
        ColumnSegmentSpec(h_low_m=1.0e4, h_high_m=1.0e3, zeta_low_rad=0.0)


@pytest.mark.level0
def test_column_spec_rejects_negative_altitude() -> None:
    with pytest.raises(ParameterBoundsError, match="negative"):
        ColumnSegmentSpec(h_low_m=-1.0, h_high_m=1.0e3, zeta_low_rad=0.0)


@pytest.mark.level0
@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_column_spec_rejects_non_finite(bad: float) -> None:
    """Rule 17: NaN/inf never enters the pipeline silently."""
    with pytest.raises(ParameterBoundsError, match="not finite"):
        ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e3, zeta_low_rad=bad)


@pytest.mark.level0
def test_column_spec_accepts_the_ceiling_exactly() -> None:
    """The ceiling itself is admissible; only past it is refused."""
    spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e3, zeta_low_rad=ZENITH_CEILING_RAD)
    assert spec.zeta_low_rad == ZENITH_CEILING_RAD


@pytest.mark.level0
def test_column_spec_refuses_the_near_horizon_sliver() -> None:
    """(89.5°, 90°) — the column airmass has no meaning; the atmosphere refuses.

    An *endpoint-minimum* path in this sliver is already rejected upstream by
    the Phase-1 hard horizon guard (±0.5°), but an *interior-tangent* path
    (level or near-level) passes that guard on tangent-height depression
    instead and can arrive here — so this second, independent gate is what
    stops a level path being served by a column integral.  The refusal must
    name the level-arm alternative (Rule 15: actionable).
    """
    sliver = math.radians(89.8)
    assert ZENITH_CEILING_RAD < sliver < math.pi / 2.0
    with pytest.raises(ParameterBoundsError) as exc:
        ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e3, zeta_low_rad=sliver)
    assert "LevelArmSpec" in str(exc.value)


@pytest.mark.level0
def test_column_spec_refuses_downward_zenith() -> None:
    """A column keyed to its lower endpoint cannot point down from there."""
    with pytest.raises(ParameterBoundsError):
        ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e3, zeta_low_rad=math.radians(120.0))


@pytest.mark.level0
def test_column_spec_rejects_zenith_outside_pi() -> None:
    with pytest.raises(ParameterBoundsError, match=r"outside \[0, π\]"):
        ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e3, zeta_low_rad=4.0)


# ---------------------------------------------------------------------------
# LevelArmSpec
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_level_arm_spec_basics() -> None:
    arm = LevelArmSpec(altitude_m=3.0e3, length_m=1.0e4)
    assert arm.kind == "level_arm"
    assert LevelArmSpec(altitude_m=0.0, length_m=0.0).length_m == 0.0


@pytest.mark.level0
@pytest.mark.parametrize(
    ("altitude_m", "length_m"),
    [(-1.0, 1.0e3), (0.0, -1.0e3)],
)
def test_level_arm_spec_rejects_negatives(altitude_m: float, length_m: float) -> None:
    with pytest.raises(ParameterBoundsError, match="negative"):
        LevelArmSpec(altitude_m=altitude_m, length_m=length_m)


@pytest.mark.level0
def test_level_arm_spec_rejects_non_finite() -> None:
    with pytest.raises(ParameterBoundsError, match="not finite"):
        LevelArmSpec(altitude_m=0.0, length_m=float("inf"))


# ---------------------------------------------------------------------------
# SegmentQuantities
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_quantities_round_trip_directions() -> None:
    q = _quantities()
    np.testing.assert_array_equal(q.radiance_toward("toward_upper"), q.L_toward_upper)
    np.testing.assert_array_equal(q.radiance_toward("toward_lower"), q.L_toward_lower)


@pytest.mark.level0
def test_quantities_rejects_unknown_direction() -> None:
    with pytest.raises(ParameterBoundsError, match="unknown direction"):
        _quantities().radiance_toward("sideways")  # type: ignore[arg-type]


@pytest.mark.level0
def test_quantities_rejects_tau_outside_unit_interval() -> None:
    lam = _grid()
    with pytest.raises(ParameterBoundsError, match=r"out of \[0, 1\]"):
        _quantities(tau=np.full_like(lam, 1.5))


@pytest.mark.level0
def test_quantities_rejects_negative_radiance() -> None:
    lam = _grid()
    with pytest.raises(ParameterBoundsError, match="negative values"):
        _quantities(L_toward_lower=np.full_like(lam, -1.0))


@pytest.mark.level0
def test_quantities_rejects_shape_mismatch() -> None:
    with pytest.raises(ParameterBoundsError, match="does not match"):
        _quantities(tau=np.full(5, 0.5))


@pytest.mark.level0
def test_quantities_accepts_exact_vacuum_and_exact_opacity() -> None:
    """The two physical extremes are inside the contract, not on its edge."""
    lam = _grid()
    vac = _quantities(
        tau=np.ones_like(lam),
        L_toward_upper=np.zeros_like(lam),
        L_toward_lower=np.zeros_like(lam),
    )
    assert np.all(vac.tau == 1.0)
    opaque = _quantities(tau=np.zeros_like(lam))
    assert np.all(opaque.tau == 0.0)


# ---------------------------------------------------------------------------
# validate_wavelength_grid
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize(
    ("grid", "match"),
    [
        (np.array([[1.0, 2.0]]), "must be 1-D"),
        (np.array([1.0]), "≥ 2 samples"),
        (np.array([2.0, 1.0]), "strictly ascending"),
        (np.array([0.0, 1.0]), "strictly positive"),
    ],
)
def test_validate_wavelength_grid_rejects(grid: np.ndarray, match: str) -> None:
    with pytest.raises(ParameterBoundsError, match=match):
        validate_wavelength_grid(grid, "unit-test")


@pytest.mark.level0
def test_validate_wavelength_grid_returns_float64() -> None:
    out = validate_wavelength_grid(np.array([1, 2, 3], dtype=np.int64), "unit-test")
    assert out.dtype == np.float64


# ---------------------------------------------------------------------------
# Coupling with the Phase-1 geometry horizon guard
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_column_ceiling_abuts_the_geometry_hard_horizon_guard() -> None:
    """The two independently-defined thresholds must coincide exactly.

    ``viewing_triangle.GUARD_HARD_RAD`` (0.5° either side of horizontal, the
    endpoint-minimum hard guard) and ``protocol.ZENITH_CEILING_RAD`` (89.5°,
    the column airmass ceiling) are declared in different modules but must
    meet edge to edge: 89.5° is the last zenith BOTH accept, and everything
    past it is refused by the atmosphere and — for an endpoint-minimum path
    — by the geometry too.  If one moved without the other, a band would
    open where geometry admits a path the column silently mis-integrates
    (a gap) or where nothing is expressible at all (an overlap).
    """
    from radiant.core.viewing_triangle import GUARD_HARD_RAD, horizon_band_action

    assert pytest.approx(math.pi / 2.0 - GUARD_HARD_RAD, abs=1e-11) == ZENITH_CEILING_RAD
    # 89.5° exactly: accepted by the column spec, and only "warn" in geometry.
    action, _band = horizon_band_action(ZENITH_CEILING_RAD)
    assert action == "warn"
    ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e3, zeta_low_rad=ZENITH_CEILING_RAD)
    # Just past it: geometry's endpoint-minimum guard raises, and so does the
    # column spec — no band where one admits and the other does not.
    just_past = math.radians(89.51)
    assert horizon_band_action(just_past)[0] == "raise"
    with pytest.raises(ParameterBoundsError):
        ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e3, zeta_low_rad=just_past)
