"""Tests for radiant.optics.aperture.

Category B validation for 2B.3: geometric area formulas, the
``(D, f, f/#)`` consistency group, the ``Ω ≈ π / (4 · f/#²)``
approximation, and boundary/failure modes.
"""

from __future__ import annotations

import math

import pytest

from radiant.optics.aperture import CircularAperture
from radiant.optics.fnumber import FNUMBER_CONSISTENCY_RTOL, resolve_fnumber_group

# ---------------------------------------------------------------------------
# Areas
# ---------------------------------------------------------------------------


def test_unobscured_area_equals_pi_d_squared_over_four() -> None:
    d = 0.5
    ap = CircularAperture(aperture_diameter_m=d)
    assert ap.primary_area_m2 == pytest.approx(math.pi * (d / 2) ** 2, rel=1e-12)
    assert ap.clear_area_m2 == pytest.approx(math.pi * (d / 2) ** 2, rel=1e-12)


def test_obscured_area_matches_analytic_formula() -> None:
    d = 1.0
    eps = 0.3
    ap = CircularAperture(aperture_diameter_m=d, obscuration_ratio=eps)
    expected = (math.pi / 4.0) * d * d * (1.0 - eps * eps)
    assert ap.clear_area_m2 == pytest.approx(expected, rel=1e-12)
    # Primary area is unchanged by obscuration.
    assert ap.primary_area_m2 == pytest.approx(math.pi * (d / 2) ** 2, rel=1e-12)


def test_area_equivalent_to_pi_over_4_d_squared_minus_d2_squared() -> None:
    """``A = π/4 · (D² − d²)`` with ``d = ε·D``."""
    d = 0.8
    eps = 0.25
    ap = CircularAperture(aperture_diameter_m=d, obscuration_ratio=eps)
    d_secondary = eps * d
    expected = (math.pi / 4.0) * (d**2 - d_secondary**2)
    assert ap.clear_area_m2 == pytest.approx(expected, rel=1e-12)


# ---------------------------------------------------------------------------
# Solid angle
# ---------------------------------------------------------------------------


def test_solid_angle_at_f_one_is_pi_over_four() -> None:
    ap = CircularAperture(aperture_diameter_m=1.0)
    # f/# = 1 means focal_length_m == aperture_diameter_m
    omega = ap.solid_angle_at_focal_length(1.0)
    assert omega == pytest.approx(math.pi / 4.0, rel=1e-12)


def test_solid_angle_decreases_with_slow_system() -> None:
    ap = CircularAperture(aperture_diameter_m=0.1)
    om_fast = ap.solid_angle_at_focal_length(0.1)  # f/1
    om_slow = ap.solid_angle_at_focal_length(10.0)  # f/100
    assert om_fast > om_slow > 0.0
    # f/100 should yield π/(4*10000)
    assert om_slow == pytest.approx(math.pi / (4 * 100.0**2), rel=1e-12)


def test_solid_angle_tends_to_zero_for_very_slow_systems() -> None:
    ap = CircularAperture(aperture_diameter_m=0.1)
    om = ap.solid_angle_at_focal_length(1e6)
    assert om > 0.0
    assert om < 1e-12


def test_solid_angle_rejects_non_positive_focal_length() -> None:
    ap = CircularAperture(aperture_diameter_m=0.5)
    with pytest.raises(ValueError, match="focal_length_m"):
        ap.solid_angle_at_focal_length(0.0)
    with pytest.raises(ValueError, match="focal_length_m"):
        ap.solid_angle_at_focal_length(-1.0)


# ---------------------------------------------------------------------------
# Constructor failure modes
# ---------------------------------------------------------------------------


def test_negative_diameter_rejected() -> None:
    with pytest.raises(ValueError, match="aperture_diameter_m"):
        CircularAperture(aperture_diameter_m=-0.5)


def test_zero_diameter_rejected() -> None:
    with pytest.raises(ValueError, match="aperture_diameter_m"):
        CircularAperture(aperture_diameter_m=0.0)


def test_obscuration_ratio_at_one_rejected() -> None:
    with pytest.raises(ValueError, match="obscuration_ratio"):
        CircularAperture(aperture_diameter_m=0.5, obscuration_ratio=1.0)


def test_obscuration_ratio_above_one_rejected() -> None:
    with pytest.raises(ValueError, match="obscuration_ratio"):
        CircularAperture(aperture_diameter_m=0.5, obscuration_ratio=1.2)


def test_negative_obscuration_ratio_rejected() -> None:
    with pytest.raises(ValueError, match="obscuration_ratio"):
        CircularAperture(aperture_diameter_m=0.5, obscuration_ratio=-0.1)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_aperture_to_dict_from_dict_round_trip() -> None:
    ap = CircularAperture(aperture_diameter_m=0.8, obscuration_ratio=0.25, name="primary")
    d = ap.to_dict()
    assert d["kind"] == "circular"
    ap2 = CircularAperture.from_dict(d)
    assert ap2 == ap


def test_aperture_from_dict_rejects_wrong_kind() -> None:
    with pytest.raises(ValueError, match="kind"):
        CircularAperture.from_dict({"kind": "slit", "aperture_diameter_m": 0.1})


# ---------------------------------------------------------------------------
# resolve_fnumber_group — two-of-three
# ---------------------------------------------------------------------------


def test_resolve_fnumber_derive_f_number() -> None:
    d, f, fn = resolve_fnumber_group(aperture_diameter_m=0.25, focal_length_m=2.0, f_number=None)
    assert fn == pytest.approx(8.0, rel=1e-12)
    assert d == 0.25 and f == 2.0


def test_resolve_fnumber_derive_focal_length() -> None:
    d, f, fn = resolve_fnumber_group(aperture_diameter_m=0.1, focal_length_m=None, f_number=5.0)
    assert f == pytest.approx(0.5, rel=1e-12)
    assert d == 0.1 and fn == 5.0


def test_resolve_fnumber_derive_diameter() -> None:
    d, f, fn = resolve_fnumber_group(aperture_diameter_m=None, focal_length_m=3.0, f_number=12.0)
    assert d == pytest.approx(0.25, rel=1e-12)
    assert f == 3.0 and fn == 12.0


# ---------------------------------------------------------------------------
# resolve_fnumber_group — three-input consistency
# ---------------------------------------------------------------------------


def test_resolve_fnumber_three_consistent_inputs_accepted() -> None:
    d, f, fn = resolve_fnumber_group(aperture_diameter_m=0.5, focal_length_m=2.5, f_number=5.0)
    assert (d, f, fn) == (0.5, 2.5, 5.0)


def test_resolve_fnumber_three_inputs_within_tolerance_accepted() -> None:
    # 0.5 * 4.999 ≈ 2.4995 vs stated 2.5 → rel err 2e-4, < 1e-3
    d, f, fn = resolve_fnumber_group(aperture_diameter_m=0.5, focal_length_m=2.5, f_number=4.999)
    assert (d, f, fn) == (0.5, 2.5, 4.999)


def test_resolve_fnumber_inconsistent_inputs_rejected() -> None:
    with pytest.raises(ValueError, match="over-specified and inconsistent"):
        # f/# should be 5.0, but user says 6.0
        resolve_fnumber_group(aperture_diameter_m=0.5, focal_length_m=2.5, f_number=6.0)


def test_resolve_fnumber_discrepancy_at_exactly_tolerance_boundary() -> None:
    """Values just above the tolerance must fail."""
    d = 0.5
    f = 2.5  # implies f/# = 5.0
    bad_fn = 5.0 * (1.0 + 2.0 * FNUMBER_CONSISTENCY_RTOL)
    with pytest.raises(ValueError, match="over-specified and inconsistent"):
        resolve_fnumber_group(aperture_diameter_m=d, focal_length_m=f, f_number=bad_fn)


# ---------------------------------------------------------------------------
# resolve_fnumber_group — failure modes
# ---------------------------------------------------------------------------


def test_resolve_fnumber_fewer_than_two_inputs_rejected() -> None:
    with pytest.raises(ValueError, match="at least two"):
        resolve_fnumber_group(aperture_diameter_m=0.5, focal_length_m=None, f_number=None)


def test_resolve_fnumber_none_inputs_rejected() -> None:
    with pytest.raises(ValueError, match="at least two"):
        resolve_fnumber_group(aperture_diameter_m=None, focal_length_m=None, f_number=None)


def test_resolve_fnumber_negative_value_rejected() -> None:
    with pytest.raises(ValueError, match="aperture_diameter_m"):
        resolve_fnumber_group(aperture_diameter_m=-0.1, focal_length_m=2.0, f_number=None)


def test_resolve_fnumber_nan_rejected() -> None:
    with pytest.raises(ValueError, match="focal_length_m"):
        resolve_fnumber_group(aperture_diameter_m=0.5, focal_length_m=float("nan"), f_number=None)
