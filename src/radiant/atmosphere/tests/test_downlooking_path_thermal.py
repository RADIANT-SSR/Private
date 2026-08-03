"""Down-looking path-radiance thermal emission — Level-0 anchors (CU-224).

Before this change ``SimpleAtmosphere.evaluate``'s ``L_path_up`` /
``L_path_full`` carried the single-scatter **solar** term only, so a
pure-thermal LWIR down-looking scene had ``L_path_up ≡ 0`` exactly while the
up-looking segment evaluators carried the Kirchhoff term ``(1 − τ)·B(T_eff)``
on the very same air.  The four tests below pin the fix:

a. the down-looking column emits ``(1 − τ_up)·B(λ, T_eff)`` with the Planck
   curve evaluated from first principles (``2hc²/λ⁵ / (exp(hc/λk_BT) − 1)``),
   not from any other RADIANT helper;
b. the reciprocal transmittances are untouched — the new term is additive on
   radiance only, and ``τ_up`` stays bit-identical to the column segment's τ;
c. the up/down thermal-path-radiance asymmetry on one reference column drops
   from three-to-four orders of magnitude to the near-unity band the paired
   MODTRAN O-block runs show;
d. the sun-below-horizon branch (formerly ``np.zeros_like(lam)``) carries the
   thermal term instead of exact zero.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.segment_simple import (
    column_segment_optical_depth,
    evaluate_column_segment,
)
from radiant.atmosphere.segments import ColumnSegmentSpec
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.core.constants import c, h, k_B
from radiant.core.los_geometry import LineOfSightGeometry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _atm() -> SimpleAtmosphere:
    return SimpleAtmosphere(
        visibility_km=23.0,
        aerosol_type="rural",
        precipitable_water_cm=2.92,
        standard_atmosphere="midlat_summer",
    )


def _lwir_grid() -> np.ndarray:
    return np.linspace(8.0, 12.0, 41)


def _column_t_eff(
    atm: SimpleAtmosphere,
    lam: np.ndarray,
    h_low_m: float,
    h_high_m: float,
    zeta_rad: float,
    escape: str,
) -> np.ndarray:
    """The CU-321 height-resolved T_eff(λ) for a plain column [K]."""
    _od, _am, _lengths, species_od = column_segment_optical_depth(
        atm, lam, ColumnSegmentSpec(h_low_m=h_low_m, h_high_m=h_high_m, zeta_low_rad=zeta_rad)
    )
    return atm._segment_emission_temperature_K(
        lam,
        h_low_m=h_low_m,
        h_high_m=h_high_m,
        od_slant_mol=species_od["mol"],
        od_slant_aer=species_od["aer"],
        od_slant_h2o=species_od["h2o"],
        od_slant_gas=species_od["gas"],
        escape=escape,
    )


def _planck_from_constants(lam_um: np.ndarray, t_K: np.ndarray | float) -> np.ndarray:
    """B(λ, T) [W/m²/sr/µm] from the Planck law written out longhand.

    Independent of ``radiant.core.blackbody`` on purpose (Rule 18): the test
    must fail if the emission term is ever wired to something that is not a
    blackbody.
    """
    lam_m = lam_um * 1.0e-6
    numerator = 2.0 * h * c**2 / lam_m**5
    denominator = np.expm1(h * c / (lam_m * k_B * t_K))
    # per-metre → per-micrometre
    return numerator / denominator * 1.0e-6


# ---------------------------------------------------------------------------
# (a) The emission term itself
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_pure_thermal_downlooking_column_emits_kirchhoff_graybody() -> None:
    """Sun below the horizon ⇒ ``L_path_up == (1 − τ_up)·B(λ, T_eff(λ))``.

    ``T_eff(λ)`` is the CU-321 height-resolved emission temperature of the
    ``[h_tgt, h_sensor]`` column, escaping at the SENSOR end — the same model,
    evaluated on the same column, that the up-looking segment evaluators use
    with ``escape="lower"``.  Emissivity is still ``1 − τ`` on the column's own
    transmittance (Kirchhoff, Rule 5).
    """
    lam = _lwir_grid()
    atm = _atm()
    los = LineOfSightGeometry(
        h_tgt=0.0,
        h_sensor=1.0e4,
        theta_o=math.radians(30.0),
        theta_s=math.pi / 2.0,  # sun exactly on the horizon: no scattered term
        delta_phi=0.0,
    )
    q = atm.evaluate(lam, los, params=None)  # type: ignore[arg-type]

    t_eff = _column_t_eff(atm, lam, 0.0, 1.0e4, math.radians(30.0), "upper")
    expected = (1.0 - q.tau_up) * _planck_from_constants(lam, t_eff)
    np.testing.assert_allclose(q.L_path_up, expected, rtol=1e-12, atol=0.0)
    # h_tgt == 0 ⇒ the full-column product is the same column.
    np.testing.assert_allclose(q.L_path_full, expected, rtol=1e-12, atol=0.0)

    # …and the value really is height-resolved: strictly colder than the
    # near-surface air the pre-CU-321 model used for the whole column, and
    # inside the column's own temperature range.  This is the assertion that
    # fails on the old code.
    t_ground = 294.15  # midlat_summer sea level, ICAO
    t_top = 294.15 - 6.5e-3 * 1.0e4
    assert np.all(t_eff < t_ground - 1.0)
    assert np.all(t_eff > t_top)
    # It is also genuinely spectral — an opaque channel and a window channel
    # emit from different altitudes.
    assert float(np.max(t_eff) - np.min(t_eff)) > 1.0


@pytest.mark.level0
def test_full_column_thermal_uses_the_ground_as_its_lower_endpoint() -> None:
    """For an elevated target ``L_path_full`` spans the deeper column.

    ``L_path_up`` spans ``[h_tgt, h_sensor]`` and ``L_path_full`` spans
    ``[0, h_sensor]``, so the two carry different emission temperatures — each
    the CU-321 model over its own column, both escaping at the sensor end.
    Nothing new is invented for the down-looking direction (Rule 27).
    """
    lam = _lwir_grid()
    atm = _atm()
    los = LineOfSightGeometry(
        h_tgt=3.0e3,
        h_sensor=1.0e4,
        theta_o=0.0,
        theta_s=math.pi / 2.0,
        delta_phi=0.0,
    )
    q = atm.evaluate(lam, los, params=None)  # type: ignore[arg-type]

    t_up = _column_t_eff(atm, lam, 3.0e3, 1.0e4, 0.0, "upper")
    t_full = _column_t_eff(atm, lam, 0.0, 1.0e4, 0.0, "upper")
    # The ground-rooted column reaches into warmer air than the 3 km one.
    assert np.all(t_full > t_up)

    np.testing.assert_allclose(
        q.L_path_up, (1.0 - q.tau_up) * _planck_from_constants(lam, t_up), rtol=1e-12, atol=0.0
    )
    np.testing.assert_allclose(
        q.L_path_full,
        (1.0 - q.tau_full_up) * _planck_from_constants(lam, t_full),
        rtol=1e-12,
        atol=0.0,
    )


# ---------------------------------------------------------------------------
# (b) Reciprocity: the term touches radiance only
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("zeta_deg", [0.0, 30.0, 48.2, 60.0])
def test_tau_up_bit_identical_to_up_looking_segment(zeta_deg: float) -> None:
    """The direction pair shares one τ, bit for bit, after the fix.

    This is the reciprocity half of the CU-224 anchor: MODTRAN's O-block
    upwelling runs reproduce their up-looking partners' transmittance to
    ≤ 1.2e-2 relative; RADIANT's two directions must agree *exactly*, because
    they call the identical column integral.
    """
    lam = _lwir_grid()
    atm = _atm()
    zeta = math.radians(zeta_deg)
    los = LineOfSightGeometry(
        h_tgt=0.0,
        h_sensor=1.0e4,
        theta_o=zeta,
        theta_s=math.radians(30.0),
        delta_phi=0.0,
    )
    down = atm.evaluate(lam, los, params=None)  # type: ignore[arg-type]
    up = evaluate_column_segment(
        atm,
        lam,
        ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e4, zeta_low_rad=zeta),
        theta_s_rad=math.radians(30.0),
        delta_phi_rad=0.0,
    )
    np.testing.assert_array_equal(down.tau_up, up.tau)


# ---------------------------------------------------------------------------
# (c) The direction asymmetry the CU filed
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_up_down_thermal_asymmetry_is_order_unity() -> None:
    """One 0 → 10 km column read both ways now differs by ~1×, not ~1e5×.

    Filed symptom (CU-224, MWIR 3.5–5 µm, vertical 0–10 km air): up-looking
    ``L`` ∈ [6.7e-2, 2.0] vs down-looking ``L_path_up`` ∈ [2.6e-5, 3.3e-4] —
    three to four orders of magnitude apart for the same air.  The paired
    MODTRAN runs (K1/O1 … H5/O5) put the true band-mean thermal asymmetry at
    1.006–2.34.  The model must land in that neighbourhood; the tolerance
    below is deliberately loose (0.5–3×) because the one-temperature graybody
    under-states the true directional spread — it is an order-of-magnitude
    gate, which is what the defect was.
    """
    lam = np.linspace(3.5, 5.0, 31)
    atm = _atm()
    los = LineOfSightGeometry(
        h_tgt=0.0,
        h_sensor=1.0e4,
        theta_o=0.0,
        theta_s=math.pi / 2.0,
        delta_phi=0.0,
    )
    down = atm.evaluate(lam, los, params=None)  # type: ignore[arg-type]
    up = evaluate_column_segment(
        atm,
        lam,
        ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e4, zeta_low_rad=0.0),
        theta_s_rad=None,
    )
    ratio = float(np.mean(up.L_toward_lower) / np.mean(down.L_path_up))
    assert 0.5 < ratio < 3.0, f"up/down thermal asymmetry {ratio:g} is not order unity"


# ---------------------------------------------------------------------------
# (d) The sun-below-horizon branch
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_sun_below_horizon_branch_is_thermal_not_zero() -> None:
    """Night down-looking path radiance is the emission term, not exact zero."""
    lam = _lwir_grid()
    atm = _atm()
    night = LineOfSightGeometry(
        h_tgt=0.0,
        h_sensor=1.0e4,
        theta_o=0.0,
        theta_s=math.radians(120.0),  # sun well below the horizon
        delta_phi=0.0,
    )
    q = atm.evaluate(lam, night, params=None)  # type: ignore[arg-type]
    assert np.all(q.L_path_up > 0.0)
    assert np.all(q.L_path_full > 0.0)

    t_eff = _column_t_eff(atm, lam, 0.0, 1.0e4, 0.0, "upper")
    np.testing.assert_allclose(
        q.L_path_up,
        (1.0 - q.tau_up) * _planck_from_constants(lam, t_eff),
        rtol=1e-12,
        atol=0.0,
    )


@pytest.mark.level0
def test_vacuum_limit_still_gives_zero_path_radiance() -> None:
    """A collapsed column emits nothing: τ_up → 1 ⇒ (1 − τ_up)·B → 0."""
    lam = _lwir_grid()
    atm = _atm()
    los = LineOfSightGeometry(
        h_tgt=9.9e4,
        h_sensor=9.9e4 + 1.0,
        theta_o=0.0,
        theta_s=math.pi / 2.0,
        delta_phi=0.0,
    )
    q = atm.evaluate(lam, los, params=None)  # type: ignore[arg-type]
    assert float(np.max(q.L_path_up)) < 1.0e-9
