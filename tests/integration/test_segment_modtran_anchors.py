"""Integration: real-MODTRAN truth anchors for the Phase-2 path-segment products.

Every numerical claim the segment core makes is pinned here against the real
MODTRAN 6 run set staged under ``modtran/real_runs/`` — the up-looking K block
(ground-to-air partial-column ladder, ``midlat_summer``), the horizontal L
block (5×5 altitude × range grid, same profile), and the H block (up-looking
full-column sky, ``us_standard`` and ``tropical``).  These are the runs the
Geometry-Flexibility plan §4 Phase 2 designates as the up-path truth anchors,
delivered by the owner 2026-07-26.

Both sides are pinned in every test: the MODTRAN reference number (a stable
golden) and the model/MODTRAN ratio envelope.  A change in either direction —
a regression, or an unexplained improvement — fails loud and forces this
record to be updated with it.

The runs are gitignored until the committed fixture subset lands (plan §7.1),
so the whole module is ``skipif``-guarded and is a no-op in CI.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.level_arm import evaluate_level_arm
from radiant.atmosphere.modtran import Tape7Reader
from radiant.atmosphere.segment_simple import evaluate_column_segment
from radiant.atmosphere.segments import ColumnSegmentSpec, LevelArmSpec
from radiant.atmosphere.simple import PROFILE_PWV_CM, SimpleAtmosphere
from radiant.atmosphere.sky_radiance import sky_radiance_along_los

_REAL_RUNS = Path(__file__).resolve().parents[2] / "modtran" / "real_runs"

pytestmark = pytest.mark.skipif(
    not _REAL_RUNS.exists(),
    reason="real MODTRAN run set not staged (modtran/real_runs/ is gitignored "
    "until the fixture subset is committed — plan §7.1)",
)

# The K and L blocks were all run on this profile / aerosol / visibility
# (docs/plans/modtran_run_matrix.csv rows K1–K7, L1–L25).
_K_L_PROFILE = "midlat_summer"


def _read(run: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(wavelength_um, total_transmittance, path_thermal_radiance)``.

    The thermal component is read separately from the scattered one so the
    graybody anchors are not contaminated by MODTRAN's multiple-scatter solar
    term (``IMULT = 1`` on these decks).  Units: µm, dimensionless,
    W/m²/sr/µm — the ``ν²`` factor is the same Jacobian
    ``Tape7Reader.to_radiant_units`` applies.
    """
    native = Tape7Reader(_REAL_RUNS / f"{run}.tp7").parse()
    nu = native.wavenumber_cm1
    keep = nu > 0.0
    nu = nu[keep]
    lam = 1.0e4 / nu
    order = np.argsort(lam)
    return (
        lam[order],
        native.total_transmittance[keep][order],
        (native.path_thermal_radiance[keep] * nu**2)[order],
    )


def _band_integral(lam: np.ndarray, values: np.ndarray, lo_um: float, hi_um: float) -> float:
    """Band integral over [lo, hi] µm — units of ``values`` × µm."""
    band = (lam >= lo_um) & (lam <= hi_um)
    return float(np.trapezoid(values[band], lam[band]))


def _band_mean(lam: np.ndarray, values: np.ndarray, lo_um: float, hi_um: float) -> float:
    """Band-mean of ``values`` over [lo, hi] µm — units of ``values``."""
    return _band_integral(lam, values, lo_um, hi_um) / (hi_um - lo_um)


def _k_l_atmosphere() -> SimpleAtmosphere:
    return SimpleAtmosphere(
        standard_atmosphere=_K_L_PROFILE,
        precipitable_water_cm=PROFILE_PWV_CM[_K_L_PROFILE],
        visibility_km=23.0,
        aerosol_type="rural",
    )


# ---------------------------------------------------------------------------
# Truth Anchor 1 — column-segment transmittance vs the K ladder
# ---------------------------------------------------------------------------


@pytest.mark.level2
def test_column_segment_tau_vs_k_ladder() -> None:
    """Up-looking partial-column τ, 0 → 1/3/5/10/20 km vertical (K1–K5).

    Measured 2026-07-26, band-mean transmittance (MODTRAN | model) —

        8–12 µm: 0.781|0.889  0.670|0.731  0.648|0.664  0.631|0.612  0.601|0.591
        3–5  µm: 0.581|0.755  0.478|0.624  0.450|0.566  0.428|0.503  0.420|0.462

    The model is systematically transparent for the shallowest columns —
    the CU-161 water/gas calibration was fit to full columns, so a 1 km
    column carries too little of the near-surface continuum — and converges
    to within 2 % (LWIR) by 10–20 km.  The MWIR bias is the documented
    CU-161 region-flat spectral-shape fragility.
    """
    atm = _k_l_atmosphere()
    cases = [
        # (run, h_high_m, LWIR MODTRAN golden, MWIR MODTRAN golden)
        ("K1", 1.0e3, 0.7811, 0.5813),
        ("K2", 3.0e3, 0.6698, 0.4777),
        ("K3", 5.0e3, 0.6481, 0.4499),
        ("K4", 1.0e4, 0.6307, 0.4284),
        ("K5", 2.0e4, 0.6014, 0.4196),
    ]
    for run, h_high_m, lwir_ref, mwir_ref in cases:
        lam, tau_mod, _ = _read(run)
        assert _band_mean(lam, tau_mod, 8.0, 12.0) == pytest.approx(lwir_ref, rel=0.01)
        assert _band_mean(lam, tau_mod, 3.0, 5.0) == pytest.approx(mwir_ref, rel=0.01)

        q = evaluate_column_segment(
            atm, lam, ColumnSegmentSpec(h_low_m=0.0, h_high_m=h_high_m, zeta_low_rad=0.0)
        )
        lwir_ratio = _band_mean(lam, q.tau, 8.0, 12.0) / lwir_ref
        mwir_ratio = _band_mean(lam, q.tau, 3.0, 5.0) / mwir_ref
        assert 0.95 < lwir_ratio < 1.16, f"{run} LWIR τ ratio {lwir_ratio:.3f}"
        assert 0.99 < mwir_ratio < 1.35, f"{run} MWIR τ ratio {mwir_ratio:.3f}"

    # Deepest columns must be the most accurate — the convergence claim.
    lam, tau_mod, _ = _read("K5")
    q = evaluate_column_segment(atm, lam, ColumnSegmentSpec(0.0, 2.0e4, 0.0))
    assert _band_mean(lam, q.tau, 8.0, 12.0) / 0.6014 == pytest.approx(0.983, abs=0.02)


@pytest.mark.level2
def test_column_segment_tau_vs_slant_k_runs() -> None:
    """Slant columns at 45°, including an ELEVATED lower endpoint (K6, K7).

    K6 is 0 → 10 km at 45° (pairs with K4's vertical column); K7 is
    5 → 15 km at 45°, the first deck whose lower endpoint is off the
    ground, which is what validates the lower-endpoint airmass keying
    (ADR-0011 decision 3 / CU-065).

    Measured 2026-07-26, band-mean τ (MODTRAN | model):
        K6  8–12 µm 0.5378 | 0.5007   3–5 µm 0.3705 | 0.3863
        K7  8–12 µm 0.9153 | 0.9041   3–5 µm 0.6808 | 0.7027
    """
    atm = _k_l_atmosphere()
    zeta = math.radians(45.0)
    cases = [
        ("K6", ColumnSegmentSpec(0.0, 1.0e4, zeta), 0.5378, 0.3705, 0.93, 1.05),
        ("K7", ColumnSegmentSpec(5.0e3, 1.5e4, zeta), 0.9153, 0.6808, 0.99, 1.04),
    ]
    for run, spec, lwir_ref, mwir_ref, lwir_ratio_ref, mwir_ratio_ref in cases:
        lam, tau_mod, _ = _read(run)
        assert _band_mean(lam, tau_mod, 8.0, 12.0) == pytest.approx(lwir_ref, rel=0.01)
        assert _band_mean(lam, tau_mod, 3.0, 5.0) == pytest.approx(mwir_ref, rel=0.01)

        q = evaluate_column_segment(atm, lam, spec)
        assert _band_mean(lam, q.tau, 8.0, 12.0) / lwir_ref == pytest.approx(
            lwir_ratio_ref, abs=0.04
        )
        assert _band_mean(lam, q.tau, 3.0, 5.0) / mwir_ref == pytest.approx(
            mwir_ratio_ref, abs=0.05
        )


# ---------------------------------------------------------------------------
# Truth Anchor 2 — up-path (toward-lower) radiance vs the K ladder
# ---------------------------------------------------------------------------


@pytest.mark.level2
def test_toward_lower_radiance_vs_k_ladder() -> None:
    """The NEW up-path product against MODTRAN's up-looking path radiance.

    A K-block deck has ``H1 = 0`` (ground) and ``H2 = h_target``, so its
    reported path radiance is what arrives at the GROUND observer — exactly
    ``SegmentQuantities.L_toward_lower``.  This is the first time this
    product has a direct truth anchor.

    Measured 2026-07-26, repinned 2026-08-02 (CU-321).  Band-integrated
    (MODTRAN | model) [W/m²/sr] on the height-resolved emission temperature:

        8–12 µm:  7.084|3.649  10.337|8.338  10.863|10.101  11.135|11.259
                  11.320|11.689
        3–5  µm:  0.648|0.232   0.774|0.358   0.795|0.399    0.802|0.439
                  0.803|0.470

    The shallow-column deficit is the same τ deficit as Anchor 1 (too little
    absorbing column ⇒ too little emitting column).  The deep-column LWIR
    excess this record carried before CU-321 (1.05/1.18/1.23×) *was* the
    one-temperature graybody's warm bias, and resolving the emission
    temperature in altitude removes it (0.93/1.01/1.03×).  The MWIR fell with
    it (0.65/0.78/0.87 → 0.50/0.55/0.59): the warm bias had been partly
    cancelling the CU-161 region-flat spectral-shape deficit in this direction.
    """
    atm = _k_l_atmosphere()
    cases = [
        # (run, h_high_m, LWIR ref, MWIR ref, LWIR ratio, MWIR ratio)
        ("K1", 1.0e3, 7.084, 0.6476, 0.52, 0.36),
        ("K2", 3.0e3, 10.337, 0.7736, 0.81, 0.46),
        ("K3", 5.0e3, 10.863, 0.7950, 0.93, 0.50),
        ("K4", 1.0e4, 11.135, 0.8022, 1.01, 0.55),
        ("K5", 2.0e4, 11.320, 0.8027, 1.03, 0.59),
    ]
    for run, h_high_m, lwir_ref, mwir_ref, lwir_ratio, mwir_ratio in cases:
        lam, _tau, l_thermal = _read(run)
        assert _band_integral(lam, l_thermal, 8.0, 12.0) == pytest.approx(lwir_ref, rel=0.01)
        assert _band_integral(lam, l_thermal, 3.0, 5.0) == pytest.approx(mwir_ref, rel=0.01)

        q = evaluate_column_segment(
            atm, lam, ColumnSegmentSpec(0.0, h_high_m, 0.0), theta_s_rad=None
        )
        assert _band_integral(lam, q.L_toward_lower, 8.0, 12.0) / lwir_ref == pytest.approx(
            lwir_ratio, abs=0.06
        )
        assert _band_integral(lam, q.L_toward_lower, 3.0, 5.0) / mwir_ref == pytest.approx(
            mwir_ratio, abs=0.06
        )


# ---------------------------------------------------------------------------
# Truth Anchor 3 — sky radiance along a LOS vs the H-block up-looking runs
# ---------------------------------------------------------------------------


@pytest.mark.level2
def test_sky_radiance_vs_uplooking_h_runs() -> None:
    """π·L_sky(0 m, 48.2°) against the CU-155 H-run geometry.

    The H runs are the ground-up-looking decks at the 48.2° diffusivity
    angle that the CU-155 downwelling calibration was fit against.  Here
    they anchor the *directional* sky radiance, which is a different product
    from the hemispheric ``E_sky_thermal`` flux those constants were fit
    through (that path is untouched and unchanged — zero drift).

    Measured 2026-07-26, repinned 2026-08-02 (CU-321) and 2026-08-30 (CU-324
    item 2).  Band-integrated π·L (MODTRAN thermal | model) [W/m²]:

        H2 us_standard   8–12 µm  20.85 | 23.36  (1.12×)   3–5 µm  1.82 | 1.37  (0.76×)
        H4 tropical      8–12 µm  66.75 | 70.07  (1.05×)   3–5 µm  3.65 | 2.75  (0.75×)

    Before CU-321 these read 1.59/1.16 and 1.22/1.04: the whole 100 km column
    emitted at near-surface temperature.  Resolving the emission temperature in
    altitude cuts the LWIR over-prediction by two thirds and turns the MWIR from
    a small over-prediction into a ~25 % under-prediction — the CU-161
    region-flat spectral-shape deficit, which the retired warm bias had been
    masking here.

    CU-324 item 2 (the O₃ placement split) then took the LWIR the rest of the
    way: 1.26 → 1.12 on H2 and 1.08 → 1.05 on H4.  A ground observer looking up
    through a full column sees the 9.6 µm band emitted from the 25 km ozone
    layer instead of from 4 km of near-surface air, and the over-prediction
    that remained was largely that.  The MWIR is untouched (0.76 → 0.76,
    0.75 → 0.75): the split moves only 9.4–9.9 µm.

    Emissivity is still ``1 − τ`` on the segment's *own* slant transmittance
    (Kirchhoff, Rule 5).  The hemispheric flux product raises its transmittance
    to a diffusivity exponent — ``sec 48.2°`` since CU-324, the fitted
    ``D = 1.1`` before it — alongside its own emission-height offset; a
    directional product cannot inherit that without decoupling its emissivity
    from its own transmittance, which the segment contract forbids.
    """
    zeta = math.radians(48.2)
    cases = [
        # (run, profile, LWIR π·L ref, MWIR π·L ref, LWIR ratio, MWIR ratio)
        ("H2", "us_standard", 20.85, 1.820, 1.12, 0.76),
        ("H4", "tropical", 66.75, 3.651, 1.05, 0.75),
    ]
    for run, profile, lwir_ref, mwir_ref, lwir_ratio, mwir_ratio in cases:
        lam, _tau, l_thermal = _read(run)
        assert math.pi * _band_integral(lam, l_thermal, 8.0, 12.0) == pytest.approx(
            lwir_ref, rel=0.01
        )
        assert math.pi * _band_integral(lam, l_thermal, 3.0, 5.0) == pytest.approx(
            mwir_ref, rel=0.01
        )

        atm = SimpleAtmosphere(
            standard_atmosphere=profile,
            precipitable_water_cm=PROFILE_PWV_CM[profile],
        )
        sky = sky_radiance_along_los(atm, lam, 0.0, zeta, theta_s_rad=None)
        model_lwir = math.pi * _band_integral(lam, sky, 8.0, 12.0)
        model_mwir = math.pi * _band_integral(lam, sky, 3.0, 5.0)
        assert model_lwir / lwir_ref == pytest.approx(lwir_ratio, abs=0.06), (
            f"{run}/{profile}: LWIR π·L_sky {model_lwir:.2f} W/m² vs MODTRAN "
            f"{lwir_ref:.2f} W/m² — if the segment thermal model changed, update "
            "this record and the module docstring together."
        )
        assert model_mwir / mwir_ref == pytest.approx(mwir_ratio, abs=0.06)


# ---------------------------------------------------------------------------
# Truth Anchor 4 — level-arm transmittance vs the horizontal 5×5 grid
# ---------------------------------------------------------------------------


@pytest.mark.level2
def test_level_arm_tau_vs_horizontal_grid() -> None:
    """Constant-altitude arms against the L-block 5×5 altitude × range grid.

    Measured 2026-07-26, band-mean τ over 8–12 µm (MODTRAN | model):

        L6  (3 km, 5 km)   0.8194 | 0.8421     L7  (3 km, 10 km)  0.7054 | 0.7151
        L12 (5 km, 10 km)  0.8829 | 0.8565     L17 (10 km, 10 km) 0.9521 | 0.9409
        L22 (15 km, 10 km) 0.9456 | 0.9674

    The analytic arm holds to ±3.5 % in the LWIR across the altitude sweep,
    which is the regime the air-to-air and ground-to-air scene classes need.
    """
    atm = _k_l_atmosphere()
    cases = [
        # (run, altitude_m, length_m, LWIR MODTRAN golden, allowed ratio band)
        ("L6", 3.0e3, 5.0e3, 0.8194, (1.00, 1.06)),
        ("L7", 3.0e3, 1.0e4, 0.7054, (0.98, 1.05)),
        ("L12", 5.0e3, 1.0e4, 0.8829, (0.94, 1.00)),
        ("L17", 1.0e4, 1.0e4, 0.9521, (0.96, 1.02)),
        ("L22", 1.5e4, 1.0e4, 0.9456, (1.00, 1.05)),
    ]
    for run, altitude_m, length_m, lwir_ref, (lo, hi) in cases:
        lam, tau_mod, _ = _read(run)
        assert _band_mean(lam, tau_mod, 8.0, 12.0) == pytest.approx(lwir_ref, rel=0.01)

        q = evaluate_level_arm(atm, lam, LevelArmSpec(altitude_m, length_m))
        ratio = _band_mean(lam, q.tau, 8.0, 12.0) / lwir_ref
        assert lo < ratio < hi, f"{run} LWIR arm τ ratio {ratio:.3f} outside [{lo}, {hi}]"


@pytest.mark.level2
def test_level_arm_exponential_divergence_from_the_band_model_is_bounded() -> None:
    """Quantify — do not hide — where ``τ(2L) = τ(L)²`` costs accuracy.

    Along the 3 km row of the L grid the model/MODTRAN LWIR ratio degrades
    monotonically with range as the analytic exponential outruns MODTRAN's
    sub-exponential band saturation: measured 1.03, 1.01, 0.95, 0.87, 0.82
    at 5, 10, 25, 50, 100 km.  The MWIR is far worse (1.09, 0.88, 0.43,
    0.11, 0.01) — the documented reason the simple arm is not for
    quantitative long-range MWIR horizontal work.
    """
    atm = _k_l_atmosphere()
    row = [
        ("L6", 5.0e3, 1.03),
        ("L7", 1.0e4, 1.01),
        ("L8", 2.5e4, 0.95),
        ("L9", 5.0e4, 0.87),
        ("L10", 1.0e5, 0.82),
    ]
    ratios: list[float] = []
    for run, length_m, expected in row:
        lam, tau_mod, _ = _read(run)
        q = evaluate_level_arm(atm, lam, LevelArmSpec(3.0e3, length_m))
        ratio = _band_mean(lam, q.tau, 8.0, 12.0) / _band_mean(lam, tau_mod, 8.0, 12.0)
        assert ratio == pytest.approx(expected, abs=0.03), f"{run}: {ratio:.3f}"
        ratios.append(ratio)
    # Monotone degradation with range — the signature of the model difference.
    assert all(a >= b - 1e-9 for a, b in zip(ratios[:-1], ratios[1:], strict=True))


# ---------------------------------------------------------------------------
# Reciprocity — the same column read from either direction
# ---------------------------------------------------------------------------


@pytest.mark.level2
def test_transmittance_is_reciprocal_across_k4_and_j1() -> None:
    """K4 (ground → 10 km, up-looking) and J1 (10 km → ground, nadir) share
    one column, so MODTRAN's own τ must agree — the designated Phase-2
    reciprocity fixture (run-matrix K4 note).  The segment model has one τ
    per segment by construction, so this pins the *reference* side of the
    reciprocity claim the contract encodes.
    """
    if not (_REAL_RUNS / "J1.tp7").exists():
        pytest.skip("J1 not staged")
    lam_k, tau_k, _ = _read("K4")
    lam_j, tau_j, _ = _read("J1")
    np.testing.assert_allclose(lam_k, lam_j, rtol=1e-12)
    assert _band_mean(lam_k, tau_k, 8.0, 12.0) == pytest.approx(
        _band_mean(lam_j, tau_j, 8.0, 12.0), rel=0.02
    )
