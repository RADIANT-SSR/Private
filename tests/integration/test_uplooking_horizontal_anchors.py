"""Integration: MODTRAN ITYPE=1 deck wiring + the delivered up-looking / horizontal anchors.

This module owns the **MODTRAN-boundary** half of Geometry-Flexibility Phase 2:
what RADIANT *writes* into a deck for the newly-reachable path types, and what
the owner's delivered batch-1 runs say about them.  Its companion,
``tests/integration/test_segment_modtran_anchors.py``, owns the segment
*physics* anchors; where the two touch the same runs they pin different things
(here: the deck, the run-to-run identities, and the full 5×5 grid sweep).

The batch-1 runs (``docs/plans/modtran_run_matrix.csv``, delivered
2026-07-26) are:

``K1``–``K7``
    Ground-to-air up-looking partial-column ladder, ``midlat_summer``.  K6 is
    the 45° slant twin of K4; **K7** is the first deck with an *elevated*
    lower endpoint looking up (5 → 15 km at 45°) — the CU-065 convention
    closure.
``L1``–``L25``
    Horizontal constant-altitude 5×5 grid — altitude {0, 3, 5, 10, 15} km ×
    range {5, 10, 25, 50, 100} km — run with ITYPE=1 and Card-3 RANGE
    (``hrange_km``) set.  These are the runs the ``hrange_km`` wiring under
    test makes regenerable.

The runs are gitignored until the committed fixture subset lands (plan §7.1),
so the whole module is ``skipif``-guarded and is a no-op in CI, following
``tests/integration/test_modtran_real_runs.py``.

Every measured number below was taken 2026-07-26 from the delivered files and
is pinned on **both** sides — the MODTRAN reference (a stable golden) and the
model/MODTRAN ratio — so a regression and an unexplained improvement both fail
loud and force this record to be updated with the change.
"""

from __future__ import annotations

import csv
import math
import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.level_arm import evaluate_level_arm
from radiant.atmosphere.modtran import (
    ModtranAtmosphere,
    ModtranConfig,
    Tape7Import,
    Tape7Reader,
    render_tape5,
)
from radiant.atmosphere.protocol import AtmosphericGeometry
from radiant.atmosphere.segment_simple import evaluate_column_segment
from radiant.atmosphere.segments import ColumnSegmentSpec, LevelArmSpec
from radiant.atmosphere.simple import PROFILE_PWV_CM, SimpleAtmosphere

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_RUNS = _REPO_ROOT / "modtran" / "real_runs"
_MATRIX_CSV = _REPO_ROOT / "docs" / "plans" / "modtran_run_matrix.csv"

pytestmark = pytest.mark.skipif(
    not _REAL_RUNS.exists(),
    reason="real MODTRAN run set not staged (modtran/real_runs/ is gitignored "
    "until the fixture subset is committed — plan §7.1)",
)

# The K and L blocks were all run on this profile / aerosol / visibility.
_K_L_PROFILE = "midlat_summer"
_K_L_VISIBILITY_KM = 23.0

# Card-3 echo line index in a delivered MODTRAN 6 tape7 (0-based): the header
# block is CARD1 / CARD2 / (2 scaling lines) / model name / CARD3.
_CARD3_ECHO_LINE = 5
# Card-3 field index in the rendered tape5 deck (0-based line 4).
_CARD3_DECK_LINE = 4


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _read(run: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(wavelength_um, total_transmittance, path_thermal_radiance)``.

    The thermal component is taken separately from the scattered one so the
    graybody comparisons are not contaminated by MODTRAN's multiple-scatter
    solar term (``IMULT = 1`` on these decks).  Units: µm, dimensionless,
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
    """Band mean of ``values`` over [lo, hi] µm — units of ``values``."""
    return _band_integral(lam, values, lo_um, hi_um) / (hi_um - lo_um)


def _card3_echo(run: str) -> list[float]:
    """``[H1, H2, ANGLE, RANGE, ...]`` [km, km, deg, km] from a tape7 echo."""
    line = (_REAL_RUNS / f"{run}.tp7").read_text(encoding="utf-8").splitlines()[_CARD3_ECHO_LINE]
    return [float(tok) for tok in line.split()]


def _matrix_rows() -> dict[str, dict[str, str]]:
    with _MATRIX_CSV.open(encoding="utf-8") as handle:
        return {row["run_id"]: row for row in csv.DictReader(handle)}


def _k_l_atmosphere() -> SimpleAtmosphere:
    return SimpleAtmosphere(
        standard_atmosphere=_K_L_PROFILE,
        precipitable_water_cm=PROFILE_PWV_CM[_K_L_PROFILE],
        visibility_km=_K_L_VISIBILITY_KM,
        aerosol_type="rural",
    )


def _render_row(row: dict[str, str]) -> str:
    """Render one run-matrix row's tape5 deck (the ``render_modtran_decks`` map)."""
    vis = float(row["vis_km"]) if row["vis_km"].strip() else None
    hrange_km = float(row["hrange_km"]) if row["hrange_km"].strip() else 0.0
    itype = int(row["itype"])
    zenith_str = row["path_zenith_deg_radiant"].strip()
    # ITYPE=1 carries no column zenith — see render_tape5's horizontal branch.
    zenith_rad = 0.0 if (itype == 1 or not zenith_str) else math.radians(float(zenith_str))
    config = ModtranConfig(
        atmosphere_profile=row["profile"],
        aerosol_model=row["aerosol"],
        h2o_scale=float(row["h2o_scale"]),
        o3_scale=float(row["o3_scale"]),
        visibility_km=vis,
        itype=itype,
        iemsct=int(row["iemsct"]),
        hrange_km=hrange_km,
        spectral_resolution_cm1=float(row["dv_cm1"]),
        v1_cm1=float(row["v1_cm1"]),
        v2_cm1=float(row["v2_cm1"]),
    )
    geometry = AtmosphericGeometry(
        sensor_altitude_m=float(row["h1_sensor_km"]) * 1000.0,
        target_altitude_m=float(row["h2_target_km"]) * 1000.0,
        path_zenith_rad=zenith_rad,
        solar_zenith_rad=math.radians(float(row["solar_zenith_deg"])),
        solar_azimuth_rad=math.radians(float(row["solar_azimuth_deg"])),
    )
    return render_tape5(config, geometry)


# ---------------------------------------------------------------------------
# 1. Deck wiring — what RADIANT writes vs what the delivered runs echo back
# ---------------------------------------------------------------------------


@pytest.mark.level2
def test_l_block_decks_reproduce_the_delivered_horizontal_card3() -> None:
    """ITYPE=1 regenerability: all 25 L decks now render truthfully.

    Before the ``hrange_km`` wiring, Card-3 RANGE was the hardcoded literal
    ``0.000`` and the L decks had to be hand-edited before running (the
    ``phase2_range_wiring`` caveat in the run matrix).  With the field wired,
    the rendered deck must reproduce the delivered tape7's Card-3 echo in all
    four geometry fields — H1 [km], H2 [km], ANGLE [deg], RANGE [km].

    This is the ITYPE=1 extension of the CU-065 three-way agreement
    (``render_tape5`` == the matrix's hand-worked column == the delivered
    card echo), which previously covered only the slant blocks.
    """
    rows = _matrix_rows()
    l_ids = [f"L{i}" for i in range(1, 26)]
    assert all(rid in rows for rid in l_ids), "run matrix lost an L row"

    for run_id in l_ids:
        row = rows[run_id]
        assert row["deck_builder_support"] == "current", (
            f"{run_id}: deck_builder_support still says "
            f"{row['deck_builder_support']!r} — the ITYPE=1 wiring makes this "
            "row renderable, so the matrix must say so."
        )
        deck_fields = [
            float(tok) for tok in _render_row(row).splitlines()[_CARD3_DECK_LINE].split()[:4]
        ]
        echo_fields = _card3_echo(run_id)[:4]
        assert deck_fields == pytest.approx(echo_fields, abs=1.0e-6), (
            f"{run_id}: deck Card 3 {deck_fields} != delivered echo {echo_fields} "
            "(H1 km, H2 km, ANGLE deg, RANGE km)"
        )
        # The grid's defining pair really is (altitude, range).
        assert deck_fields[0] == deck_fields[1]  # constant altitude [km]
        assert deck_fields[2] == pytest.approx(90.0, abs=1e-9)  # horizontal [deg]
        assert deck_fields[3] == pytest.approx(float(row["hrange_km"]), abs=1e-9)


@pytest.mark.level2
def test_slant_block_decks_still_match_their_delivered_card3() -> None:
    """Zero drift on the deck side, measured against the delivered runs.

    Every non-ITYPE=1 row of the matrix that has a staged tape7 must still
    render the H1 / H2 / ANGLE its delivered Card-3 echo reports — the
    pre-existing CU-065 three-way agreement, re-asserted after the RANGE
    field was wired.  (Byte-identity of the *whole* card image against the
    pre-wiring builder is pinned separately, at Level 0, by
    ``test_card3_byte_image_unchanged_by_hrange_wiring`` in
    ``src/radiant/atmosphere/tests/test_modtran.py``.)

    RANGE is *not* compared here: for a slant path MODTRAN derives it (K7's
    echo reports the 14.132 km spherical slant range for a deck that wrote
    0.000), which is exactly why ``ModtranConfig`` refuses a user-supplied
    ``hrange_km`` outside ITYPE=1.
    """
    rows = _matrix_rows()
    checked = 0
    for run_id, row in rows.items():
        if int(row["itype"]) == 1 or not (_REAL_RUNS / f"{run_id}.tp7").exists():
            continue
        deck_fields = [
            float(tok) for tok in _render_row(row).splitlines()[_CARD3_DECK_LINE].split()[:3]
        ]
        assert deck_fields == pytest.approx(_card3_echo(run_id)[:3], abs=1.0e-6), run_id
        checked += 1
    assert checked >= 60, f"only {checked} slant runs compared — staged set shrank?"


@pytest.mark.level2
def test_k7_card3_echo_closes_the_elevated_lower_endpoint_convention() -> None:
    """CU-065 closure: ANGLE is measured at H1 even when H1 is off the ground.

    Before K7 the up-looking half of the Card-3 convention (``ANGLE = zenith``
    unchanged when the sensor is the path's lower endpoint) was confirmed only
    at ``H1 = 0`` (the H and K1–K6 decks), where "at H1" and "at the ground"
    are indistinguishable.  K7 separates them: 5 km → 15 km at 45°.

    The delivered echo reads ``H1 5.000  H2 15.000  ANGLE 45.000``, and two
    further fields close the argument independently:

    * ``PHI = 135.083°`` — MODTRAN's zenith angle at the *other* endpoint
      (H2).  It is 180° − 45° plus 0.083° of Earth curvature over the path,
      i.e. the supplement of ANGLE, which it can only be if ANGLE belongs to
      H1.  Had ANGLE been the at-H2 angle, the two would be swapped.
    * ``RANGE = 14.132 km`` — MODTRAN's own derived slant range.  The
      flat-Earth value is 10 km / cos 45° = 14.142 km; the spherical-Earth
      path between the same two altitudes at 45° at the lower endpoint is
      slightly *shorter* because the ray's zenith angle decreases along the
      climb.  14.132 km is that value, not the at-H2 alternative.
    """
    h1_km, h2_km, angle_deg, range_km = _card3_echo("K7")[:4]
    phi_deg = _card3_echo("K7")[7]

    assert h1_km == pytest.approx(5.0, abs=1e-6)
    assert h2_km == pytest.approx(15.0, abs=1e-6)
    assert angle_deg == pytest.approx(45.0, abs=1e-6)
    assert phi_deg == pytest.approx(135.083, abs=1e-3)
    assert angle_deg + phi_deg == pytest.approx(180.0, abs=0.09)
    # Shorter than the flat-Earth chord, and by less than 0.1 %.
    flat_earth_km = 10.0 / math.cos(math.radians(45.0))
    assert range_km == pytest.approx(14.132, abs=1e-3)
    assert 0.999 < range_km / flat_earth_km < 1.0

    # And the deck RADIANT renders for that geometry agrees field-for-field.
    deck_h1, deck_h2, deck_angle = (
        float(tok) for tok in _render_row(_matrix_rows()["K7"]).splitlines()[4].split()[:3]
    )
    assert (deck_h1, deck_h2) == (5.0, 15.0)
    assert deck_angle == pytest.approx(45.0, abs=1e-9)


# ---------------------------------------------------------------------------
# 2. Reciprocity — transmittance is direction-free, path radiance is not
# ---------------------------------------------------------------------------


@pytest.mark.level2
def test_transmittance_reciprocity_uplooking_vs_downlooking() -> None:
    """ADR-0011 decision 3's premise, measured on three independent columns.

    Each pair is the *same* air column (same profile, aerosol, visibility,
    scale factors, same two altitudes, vertical) run in opposite directions:

        K2 (0 → 3 km, up)   vs  F2 (3 km → 0, nadir)
        K4 (0 → 10 km, up)  vs  J1 (10 km → 0, nadir)
        K5 (0 → 20 km, up)  vs  J2 (20 km → 0, nadir)

    A segment carries **one** τ precisely because transmittance is reciprocal;
    these are the runs that say MODTRAN agrees.

    MEASURED 2026-07-26 — the agreement is far tighter than the
    "band-model round-off" the run-matrix note anticipated.  Band-mean τ
    ratios (up/down) are 1.000000 to six figures in LWIR (8–12 µm), MWIR
    (3–5 µm) and VIS/NIR (0.5–0.9 µm) for all three pairs.  The largest
    *per-wavelength* disagreement anywhere in the 0.37–14.4 µm grid is
    Δτ = 9.9e-5 (K4/J1, at 0.746 µm, τ ≈ 0.79 — a 1.3e-4 relative
    difference), and it sits in the ozone Chappuis band where the two decks'
    differing solar-path bookkeeping is largest.  The tolerances below are
    read off those measurements with ~5× margin; they are deliberately
    *tight* — this identity is exact physics, so loosening it to pass would
    be hiding a real defect.

    Path radiance is NOT reciprocal and is not compared here: the up-looking
    K deck's radiance arrives at the ground observer and the down-looking
    partner's arrives at the aircraft.  Those are the segment product's two
    distinct ``L_toward_lower`` / ``L_toward_upper`` fields.
    """
    pairs = [("K2", "F2", "0–3 km"), ("K4", "J1", "0–10 km"), ("K5", "J2", "0–20 km")]
    bands = {"LWIR": (8.0, 12.0), "MWIR": (3.0, 5.0), "VIS/NIR": (0.5, 0.9)}

    for up_run, down_run, label in pairs:
        if not (_REAL_RUNS / f"{down_run}.tp7").exists():
            pytest.skip(f"{down_run} not staged")
        lam_up, tau_up, l_up = _read(up_run)
        lam_dn, tau_dn, l_dn = _read(down_run)
        np.testing.assert_allclose(lam_up, lam_dn, rtol=1e-12)

        for band_name, (lo, hi) in bands.items():
            ratio = _band_mean(lam_up, tau_up, lo, hi) / _band_mean(lam_dn, tau_dn, lo, hi)
            assert ratio == pytest.approx(1.0, abs=5.0e-5), (
                f"{up_run}/{down_run} ({label}) {band_name}: band-mean τ ratio "
                f"{ratio:.7f} — transmittance must be reciprocal (ADR-0011 "
                "decision 3 / RADIANT_Atmosphere.md §4.4)."
            )
        # Spectrally resolved, not just band-averaged.
        assert float(np.max(np.abs(tau_up - tau_dn))) < 5.0e-4, (
            f"{up_run}/{down_run}: max per-wavelength |Δτ| exceeds the measured 9.9e-5"
        )

        # Direction-specific products genuinely differ: the up-looking deck
        # sees a warm near-surface column, the nadir deck the same column
        # from above.  Guards against the pair being accidentally identical
        # runs (which would make the τ assertion vacuous).
        lwir_up = _band_integral(lam_up, l_up, 8.0, 12.0)
        lwir_dn = _band_integral(lam_dn, l_dn, 8.0, 12.0)
        assert abs(lwir_up - lwir_dn) / lwir_dn > 0.01, (
            f"{up_run}/{down_run}: path radiance is identical in both "
            f"directions ({lwir_up:.4f} vs {lwir_dn:.4f} W/m²/sr) — the pair "
            "cannot be two directions of one column."
        )


# ---------------------------------------------------------------------------
# 3. K-ladder characterization — simple-model segments vs the delivered runs
# ---------------------------------------------------------------------------

# (run, h_low [m], h_high [m], ζ_low [rad],
#  MODTRAN τ LWIR, MODTRAN τ MWIR,          [dimensionless band means]
#  MODTRAN L_toward_lower LWIR, MWIR,       [W/m²/sr, band integrals]
#  model/MODTRAN τ ratios (LWIR, MWIR),
#  model/MODTRAN L ratios (LWIR, MWIR))
_K_LADDER: list[
    tuple[
        str,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        tuple[float, float],
        tuple[float, float],
    ]
] = [  # noqa: E501
    ("K1", 0.0, 1.0e3, 0.0, 0.7811, 0.5813, 7.084, 0.6476, (1.138, 1.299), (0.526, 0.366)),
    ("K2", 0.0, 3.0e3, 0.0, 0.6698, 0.4777, 10.337, 0.7736, (1.092, 1.306), (0.880, 0.551)),
    ("K3", 0.0, 5.0e3, 0.0, 0.6481, 0.4499, 10.863, 0.7950, (1.024, 1.259), (1.050, 0.651)),
    ("K4", 0.0, 1.0e4, 0.0, 0.6307, 0.4284, 11.135, 0.8022, (0.971, 1.173), (1.182, 0.779)),
    ("K5", 0.0, 2.0e4, 0.0, 0.6014, 0.4196, 11.320, 0.8027, (0.983, 1.100), (1.226, 0.867)),
]


@pytest.mark.level2
def test_k_ladder_segment_characterization() -> None:
    """CHARACTERIZATION of the simple-model column segment against K1–K5.

    This is a pinned record, not a claim of agreement.  Both sides are
    asserted: the MODTRAN band values (stable goldens read straight off the
    delivered tape7s) and the model/MODTRAN ratio at each rung.  Units:
    τ is a dimensionless band mean over the window; ``L_toward_lower`` is a
    band integral in **W/m²/sr**.

    What the numbers say (measured 2026-07-26):

    * **τ** — the model is *too transparent* for shallow columns (LWIR 1.14×
      at 1 km) and converges to within 3 % by 10–20 km.  The CU-161 water and
      gas-floor calibration was fit to whole columns, so a 1 km slice carries
      too little of the near-surface continuum.  MWIR stays 1.10–1.31× high
      throughout — the documented CU-161 region-flat spectral-shape
      limitation.
    * **L_toward_lower** — the new up-path product runs from 0.53× at 1 km to
      1.23× at 20 km in the LWIR: the shallow deficit is the τ deficit
      (Kirchhoff — too little absorbing column means too little emitting
      column), and the deep excess is the single-temperature graybody's warm
      bias (a 20 km column emits partly from cold air aloft).  MWIR is low
      everywhere (0.37→0.87×), the same spectral-shape limitation seen in τ.

    The tolerances are ±0.04 on τ ratios and ±0.06 on radiance ratios — the
    band the measured values sit in with margin for grid/interpolation noise,
    not a band chosen to make a disagreement pass.  A move outside them means
    the segment model changed and this record must change with it.
    """
    atm = _k_l_atmosphere()
    for (
        run,
        h_low,
        h_high,
        zeta,
        tau_lwir_ref,
        tau_mwir_ref,
        rad_lwir_ref,
        rad_mwir_ref,
        (tau_lwir_ratio, tau_mwir_ratio),
        (rad_lwir_ratio, rad_mwir_ratio),
    ) in _K_LADDER:
        lam, tau_mod, l_mod = _read(run)

        # Side 1 — the MODTRAN goldens.
        assert _band_mean(lam, tau_mod, 8.0, 12.0) == pytest.approx(tau_lwir_ref, rel=0.005)
        assert _band_mean(lam, tau_mod, 3.0, 5.0) == pytest.approx(tau_mwir_ref, rel=0.005)
        assert _band_integral(lam, l_mod, 8.0, 12.0) == pytest.approx(rad_lwir_ref, rel=0.005)
        assert _band_integral(lam, l_mod, 3.0, 5.0) == pytest.approx(rad_mwir_ref, rel=0.005)

        # Side 2 — the model/MODTRAN ratio.
        q = evaluate_column_segment(
            atm, lam, ColumnSegmentSpec(h_low, h_high, zeta), theta_s_rad=None
        )
        got_tau_lwir = _band_mean(lam, q.tau, 8.0, 12.0) / tau_lwir_ref
        got_tau_mwir = _band_mean(lam, q.tau, 3.0, 5.0) / tau_mwir_ref
        got_rad_lwir = _band_integral(lam, q.L_toward_lower, 8.0, 12.0) / rad_lwir_ref
        got_rad_mwir = _band_integral(lam, q.L_toward_lower, 3.0, 5.0) / rad_mwir_ref

        assert got_tau_lwir == pytest.approx(tau_lwir_ratio, abs=0.04), f"{run} τ LWIR"
        assert got_tau_mwir == pytest.approx(tau_mwir_ratio, abs=0.04), f"{run} τ MWIR"
        assert got_rad_lwir == pytest.approx(rad_lwir_ratio, abs=0.06), f"{run} L LWIR"
        assert got_rad_mwir == pytest.approx(rad_mwir_ratio, abs=0.06), f"{run} L MWIR"

    # The ladder's shape, not just its points: MODTRAN's τ falls monotonically
    # with column depth and its up-path radiance rises monotonically — the
    # model must reproduce both orderings even where its magnitude is off.
    ladder = [_read(entry[0]) for entry in _K_LADDER]
    taus = [_band_mean(lam, tau, 8.0, 12.0) for lam, tau, _ in ladder]
    rads = [_band_integral(lam, rad, 8.0, 12.0) for lam, _, rad in ladder]
    assert taus == sorted(taus, reverse=True), taus
    assert rads == sorted(rads), rads


# ---------------------------------------------------------------------------
# 4. Horizontal 5×5 grid — the analytic level arm against all 25 runs
# ---------------------------------------------------------------------------

_L_ALTITUDES_KM = (0, 3, 5, 10, 15)
_L_RANGES_KM = (5, 10, 25, 50, 100)

# (altitude km, range km) -> (run, MODTRAN band-mean τ 8–12 µm, model/MODTRAN
# ratio), measured 2026-07-26 over all 25 delivered horizontal runs.
_L_GRID_LWIR: dict[tuple[int, int], tuple[str, float, float]] = {
    (0, 5): ("L1", 0.2719, 1.263),
    (0, 10): ("L2", 0.0916, 1.290),
    (0, 25): ("L3", 0.0052, 0.931),
    (0, 50): ("L4", 0.0001, 0.314),
    (0, 100): ("L5", 0.0000, 0.018),
    (3, 5): ("L6", 0.8194, 1.028),
    (3, 10): ("L7", 0.7054, 1.014),
    (3, 25): ("L8", 0.4766, 0.951),
    (3, 50): ("L9", 0.2673, 0.873),
    (3, 100): ("L10", 0.0952, 0.815),
    (5, 5): ("L11", 0.9304, 0.992),
    (5, 10): ("L12", 0.8829, 0.970),
    (5, 25): ("L13", 0.7769, 0.893),
    (5, 50): ("L14", 0.6554, 0.781),
    (5, 100): ("L15", 0.4988, 0.638),
    (10, 5): ("L16", 0.9725, 0.996),
    (10, 10): ("L17", 0.9521, 0.988),
    (10, 25): ("L18", 0.9064, 0.954),
    (10, 50): ("L19", 0.8567, 0.885),
    (10, 100): ("L20", 0.7950, 0.756),
    (15, 5): ("L21", 0.9663, 1.017),
    (15, 10): ("L22", 0.9456, 1.023),
    (15, 25): ("L23", 0.9082, 1.018),
    (15, 50): ("L24", 0.8733, 0.984),
    (15, 100): ("L25", 0.8319, 0.901),
}


@pytest.mark.level2
def test_level_arm_vs_the_full_horizontal_grid() -> None:
    """Analytic constant-altitude arm τ against all 25 delivered L runs.

    The arm is Beer-Lambert at the local extinction coefficient over the true
    chord length; MODTRAN is a correlated-k band model.  The whole 5×5 sweep
    is pinned so the *shape* of the disagreement is a regression target, not
    just one convenient cell.  Units: dimensionless band-mean τ over
    8–12 µm; altitudes km; ranges km.

    Measured 2026-07-26.  Read down a column and the model degrades with
    range; read across a row and it improves with altitude.  The extreme is
    the sea-level row, where by 50–100 km MODTRAN's τ has fallen to 1e-4 and
    below and the two models are comparing near-zeros (ratio 0.31 → 0.018) —
    that cell is a *documented breakdown*, not a usable operating point, and
    it is pinned here so nobody mistakes it for one.  Above 3 km the LWIR arm
    holds within ~±3 % out to 25 km range, which is the ground-to-air and
    air-to-air regime the scene classes need.
    """
    atm = _k_l_atmosphere()
    rows = _matrix_rows()
    for altitude_km in _L_ALTITUDES_KM:
        for range_km in _L_RANGES_KM:
            run, tau_ref, ratio_ref = _L_GRID_LWIR[(altitude_km, range_km)]
            # The pinned cell really is the matrix's (altitude, range) cell.
            assert float(rows[run]["h1_sensor_km"]) == altitude_km
            assert float(rows[run]["hrange_km"]) == range_km

            lam, tau_mod, _ = _read(run)
            measured_ref = _band_mean(lam, tau_mod, 8.0, 12.0)
            assert measured_ref == pytest.approx(tau_ref, abs=5.0e-5), run

            q = evaluate_level_arm(atm, lam, LevelArmSpec(altitude_km * 1.0e3, range_km * 1.0e3))
            if measured_ref < 1.0e-3:
                # Near-total extinction: the ratio is a ratio of noise floors.
                # Assert the physically meaningful statement instead — both
                # models agree the path is opaque.
                assert _band_mean(lam, q.tau, 8.0, 12.0) < 1.0e-3, run
                continue
            ratio = _band_mean(lam, q.tau, 8.0, 12.0) / measured_ref
            assert ratio == pytest.approx(ratio_ref, abs=0.03), (
                f"{run} (altitude {altitude_km} km, range {range_km} km): "
                f"LWIR arm τ ratio {ratio:.3f} vs pinned {ratio_ref:.3f}"
            )

    # Structure of the disagreement, asserted independently of the pins.
    # Beyond the 5 km cell the arm's exponential outruns MODTRAN's
    # sub-exponential band saturation monotonically in every altitude row.
    # The 5 km cell itself is *not* part of the monotone run — at 15 km
    # altitude it sits below its 10 km neighbour (1.017 vs 1.023), because
    # over so short an arm the ratio is dominated by the model's own
    # extinction-coefficient offset rather than by path-length saturation.
    for altitude_km in _L_ALTITUDES_KM:
        ratios = [_L_GRID_LWIR[(altitude_km, r)][2] for r in _L_RANGES_KM]
        assert all(a >= b for a, b in zip(ratios[1:-1], ratios[2:], strict=True)), (
            f"{altitude_km} km row: model/MODTRAN must degrade monotonically "
            f"with range beyond 10 km, got {ratios}"
        )
        assert ratios[-1] < ratios[0], f"{altitude_km} km row: {ratios}"


@pytest.mark.level2
def test_band_model_non_exponentiality_measured_on_the_l_grid() -> None:
    """Quantify the one identity the analytic arm cannot share with MODTRAN.

    **What this measures.**  For a single absorption coefficient, Beer-Lambert
    gives τ(2L) = τ(L)² exactly, and the analytic level arm obeys that by
    construction.  A *band-averaged* transmittance does not, because the
    absorption coefficient varies across the averaging window: by Jensen's
    inequality ⟨e^{−2kL}⟩ ≥ ⟨e^{−kL}⟩², with equality only if k is constant
    over the band.  The measured excess of τ(2L)/τ(L)² above 1 is therefore a
    direct measure of the **spectral inhomogeneity of the absorption
    coefficient within the band** — strong lines saturate first and the
    remaining flux leaks through the windows between them, so a doubled path
    attenuates less than the square.  It is not a MODTRAN error and not a
    grid artefact; it is the reason a single scalar τ cannot be exponentiated
    in path length once it has been band-averaged.

    Measured 2026-07-26 from the delivered L grid, τ(50 km)/τ(25 km)²:

        altitude   8–12 µm   3–5 µm
        ----------------------------
         0 km       2.7725    3.8543
         3 km       1.1768    2.2232
         5 km       1.0859    1.6798
        10 km       1.0427    1.3002
        15 km       1.0587    1.1930

    The effect shrinks with altitude (thinner, more uniform absorption) and is
    far larger in the MWIR, whose 3–5 µm window is cut by the CO₂ 4.3 µm band
    and dense H₂O lines, than in the smoother LWIR window.  The pinned
    headline value is the **10 km LWIR cell, 1.0427** — a 4.3 % super-
    multiplicativity over a doubled 25 km arm at cruise altitude.

    A cross-check on the same cell at MODTRAN's own 1 cm⁻¹ resolution: the
    per-bin ratio has median 1.0012 but mean 1.0305, i.e. most bins are nearly
    exponential and a minority of line-dominated bins carry the whole effect —
    exactly the inhomogeneity signature, seen one level down.
    """
    expected = {
        0: (2.7725, 3.8543),
        3: (1.1768, 2.2232),
        5: (1.0859, 1.6798),
        10: (1.0427, 1.3002),
        15: (1.0587, 1.1930),
    }
    for altitude_km, (lwir_ref, mwir_ref) in expected.items():
        run_25 = _L_GRID_LWIR[(altitude_km, 25)][0]
        run_50 = _L_GRID_LWIR[(altitude_km, 50)][0]
        lam, tau_25, _ = _read(run_25)
        _, tau_50, _ = _read(run_50)
        for band, ref in (((8.0, 12.0), lwir_ref), ((3.0, 5.0), mwir_ref)):
            t25 = _band_mean(lam, tau_25, *band)
            t50 = _band_mean(lam, tau_50, *band)
            ratio = t50 / t25**2
            assert ratio == pytest.approx(ref, rel=0.01), (
                f"{altitude_km} km, {band} µm: τ(50 km)/τ(25 km)² = {ratio:.4f} vs pinned {ref:.4f}"
            )
            # Jensen's inequality is one-sided — never below 1.
            assert ratio > 1.0 - 1e-9

    # The analytic arm is exactly multiplicative — the other side of the
    # comparison, asserted rather than asserted-by-docstring.
    atm = _k_l_atmosphere()
    lam, _, _ = _read("L18")
    q25 = evaluate_level_arm(atm, lam, LevelArmSpec(1.0e4, 2.5e4))
    q50 = evaluate_level_arm(atm, lam, LevelArmSpec(1.0e4, 5.0e4))
    np.testing.assert_allclose(q50.tau, q25.tau**2, rtol=1e-12, atol=1e-15)


# ---------------------------------------------------------------------------
# 5. Up-looking tape7 import path
# ---------------------------------------------------------------------------


@pytest.mark.level2
def test_uplooking_tape7_import_end_to_end_k4() -> None:
    """An up-looking run (H1 < H2) imports and serves through the MODTRAN
    boundary with no down-looking assumption in the way.

    K4 is the ground → 10 km vertical up-looking deck.  Three things are
    checked, in the order the data flows:

    1. ``AtmosphericGeometry`` accepts the up-looking altitude pair.  Its
       ``path_zenith_rad`` is the **lower-endpoint** zenith (ADR-0011
       decision 3), which for this geometry is 0 — the sensor is the lower
       endpoint — so the up-looking case needs no special handling and no
       widened bound.
    2. ``render_tape5`` reproduces K4's delivered Card 3 (``0.000 10.000
       0.000``): the up-looking branch writes ANGLE unchanged because the
       sensor *is* H1.
    3. ``Tape7Import`` + ``ModtranAtmosphere.build_state`` serve that run's
       transmittance and path radiance on a chain wavelength grid.
       ``Tape7Import`` is geometry-agnostic by contract, so nothing about the
       file's direction reaches it; the resampled band values must reproduce
       the native-grid ones to interpolation accuracy.

    Scope note: the *chain-level* up-looking scene (``Sensor.run`` with
    ``h_sensor < h_tgt``) is still refused at ``AtmosphereStage`` with the
    Phase-1 "Phase 2 pending" error (``test_uplooking_phase1.py``); that
    refusal is a topology-layer decision above this boundary, and it is
    deliberately not bypassed here.
    """
    geometry = AtmosphericGeometry(
        sensor_altitude_m=0.0,
        target_altitude_m=10_000.0,
        path_zenith_rad=0.0,  # zenith at the LOWER endpoint = the ground sensor
        solar_zenith_rad=math.radians(30.0),
        solar_azimuth_rad=0.0,
    )
    assert geometry.target_altitude_m > geometry.sensor_altitude_m

    deck_fields = [
        float(tok)
        for tok in render_tape5(ModtranConfig(atmosphere_profile=_K_L_PROFILE), geometry)
        .splitlines()[_CARD3_DECK_LINE]
        .split()[:3]
    ]
    assert deck_fields == pytest.approx(_card3_echo("K4")[:3], abs=1e-6)

    imported = Tape7Import.from_file(_REAL_RUNS / "K4.tp7")
    assert imported.wavelength_um[0] < imported.wavelength_um[-1]
    # SURREF = 0 on the K decks and the path never touches the ground.
    assert float(np.max(imported.ground_reflected)) == 0.0

    atmosphere = ModtranAtmosphere(
        ModtranConfig(binary_path=Path("/nonexistent"), allow_fallback=False),
        tape7_import=imported,
    )
    wavelength_um = np.linspace(3.0, 14.0, 3000)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        state = atmosphere.build_state(wavelength_um, geometry)

    tau = np.asarray(state.transmittance.values, dtype=np.float64)
    l_path = np.asarray(state.path_radiance.values, dtype=np.float64)
    assert tau.shape == wavelength_um.shape
    assert np.all((tau >= 0.0) & (tau <= 1.0))
    assert np.all(np.isfinite(l_path)) and np.all(l_path >= 0.0)

    # Native-grid truth anchors (K4, from the delivered file itself).
    lam_native, tau_native, _ = _read("K4")
    assert _band_mean(lam_native, tau_native, 8.0, 12.0) == pytest.approx(0.6307, abs=5e-4)

    band = (wavelength_um >= 8.0) & (wavelength_um <= 12.0)
    assert float(tau[band].mean()) == pytest.approx(0.6307, abs=3e-3)
    # Path radiance is the up-looking (toward-the-ground-observer) column.
    assert _band_integral(wavelength_um, l_path, 8.0, 12.0) == pytest.approx(11.14, rel=0.02)


# ---------------------------------------------------------------------------
# K6 — the up-looking zenith-coupling holdout
# ---------------------------------------------------------------------------


def test_k6_uplooking_zenith_coupling_characterization() -> None:
    """Characterize the sec-law prediction of K6 from the shipped vertical family.

    This is the measurement behind a *refusal*.  The shipped
    ``midlat_summer_uplooking_ladder`` family is vertical-only, and
    ``InterpolatedAtmosphere.uplooking_column_product`` refuses an
    off-vertical query rather than mapping it through airmass ``sec(ζ)``
    space the way the down-looking ``midlat_summer_boost_offnadir`` family
    does.  K6 (0 → 10 km at 45°, the slant twin of K4) is what says how
    wrong that mapping would have been.

    Method: interpolate the shipped family to the 10 km rung, raise it to the
    spherical-corrected airmass ``AtmosphericGeometry.air_mass()`` at 45°
    (= sec 45° = √2 to 12 digits at this altitude), and compare band-mean τ
    against the delivered K6 tape7.

    Result (measured 2026-07-26): the sec-law **under-predicts** τ by 0.14 %
    (VIS) to 2.16 % (LWIR).  Beer's law is exact for a monochromatic optical
    depth but not for a *band-averaged* transmittance: within a band the
    strong lines saturate, so ⟨τ^m⟩ > ⟨τ⟩^m by Jensen's inequality, and the
    gap grows with the band's line-strength spread — hence VIS (aerosol/
    Rayleigh, smooth) ≪ LWIR (water continuum + line structure).  Same
    effect the L-grid non-exponentiality test measures on horizontal paths.

    Pinned on both sides: the MODTRAN reference and the ratio.  An
    unexplained improvement fails too, and forces this record to be updated.
    """
    from radiant.atmosphere.interpolated import (
        UPLOOKING_RADIANCE_KEY,
        GeometryPoint,
        InterpolatedAtmosphere,
    )
    from radiant.core.los_geometry import LineOfSightGeometry
    from radiant.core.spectral import SpectralData

    family_dir = (
        _REPO_ROOT
        / "src"
        / "radiant"
        / "data"
        / "tables"
        / "atmospheres"
        / "midlat_summer_uplooking_ladder"
    )
    if not family_dir.exists():
        pytest.skip("shipped up-looking family not present")

    points = []
    for npz_file in sorted(family_dir.glob("*.npz")):
        with np.load(npz_file, allow_pickle=True) as data:
            coords = data["geometry"].item()
            wl = np.asarray(data["wavelength_um"], dtype=np.float64)
            tau = np.asarray(data["transmittance"], dtype=np.float64)
            l_down = np.asarray(data[UPLOOKING_RADIANCE_KEY], dtype=np.float64)
        points.append(
            GeometryPoint(
                coordinates=coords,
                transmittance=SpectralData(
                    name="tau",
                    wavelength_um=wl.copy(),
                    values=tau,
                    unit="",
                    source=str(npz_file),
                ),
                path_radiance=SpectralData(
                    name="L_toward_lower",
                    wavelength_um=wl.copy(),
                    values=l_down,
                    unit="W/m²/sr/µm",
                    source=str(npz_file),
                ),
                atm_emission_down=SpectralData(
                    name="unused",
                    wavelength_um=wl.copy(),
                    values=np.zeros_like(wl),
                    unit="W/m²/sr/µm",
                    source=str(npz_file),
                ),
            )
        )
    family = InterpolatedAtmosphere(points, axes=["target_altitude_m"], family_direction="up")

    vertical = family.uplooking_column_product(
        family.wavelength_um,
        LineOfSightGeometry(theta_o=math.pi, h_tgt=10_000.0, h_sensor=0.0),
    )

    # The off-vertical query the family cannot serve — the reason this
    # characterization exists.
    from radiant.atmosphere.errors import AtmosphereValidationError

    with pytest.raises(AtmosphereValidationError, match="VERTICAL"):
        family.uplooking_column_product(
            family.wavelength_um,
            LineOfSightGeometry(theta_o=math.pi - math.radians(45.0), h_tgt=10_000.0, h_sensor=0.0),
        )

    air_mass = AtmosphericGeometry(
        sensor_altitude_m=0.0,
        target_altitude_m=10_000.0,
        path_zenith_rad=math.radians(45.0),
    ).air_mass()
    assert air_mass == pytest.approx(math.sqrt(2.0), rel=1e-9)

    predicted = np.clip(vertical.tau, 1e-30, 1.0) ** air_mass
    lam_k6, tau_k6, _ = _read("K6")

    # band -> (MODTRAN band-mean τ, sec-law prediction, signed relative
    # deviation of MODTRAN from the prediction), measured 2026-07-26.
    expected = {
        (0.5, 0.7): (0.604537, 0.603699, +0.001385),
        (1.0, 1.7): (0.573398, 0.563072, +0.018008),
        (3.5, 4.1): (0.729172, 0.718795, +0.014232),
        (8.0, 12.0): (0.537798, 0.526207, +0.021553),
    }
    for (lo, hi), (tau_ref, pred_ref, rel_ref) in expected.items():
        tau_modtran = _band_mean(lam_k6, tau_k6, lo, hi)
        tau_pred = _band_mean(vertical.wavelength_um, predicted, lo, hi)
        rel = (tau_modtran - tau_pred) / tau_modtran
        assert tau_modtran == pytest.approx(tau_ref, abs=1e-4), f"K6 τ moved over {lo}–{hi} µm"
        assert tau_pred == pytest.approx(pred_ref, abs=1e-4), f"sec-law τ moved over {lo}–{hi} µm"
        assert rel == pytest.approx(rel_ref, abs=2e-4), (
            f"coupling deviation moved over {lo}–{hi} µm"
        )
        # Direction is physics, not a fit: saturation makes MODTRAN's
        # band-mean τ HIGHER than the sec-law prediction, always.
        assert rel > 0.0
