"""Integration: parse-level anchors for the promoted batch-2 MODTRAN fixtures.

The run matrix marks five batch-2 rows ``test_fixture + shipped_library`` — M1,
N4, N9, O1, P1.  ``tests/integration/fixtures/modtran/MANIFEST.md`` records the
promotion (and why the bytes are not copied: they are tracked in git under
``modtran/real_runs/`` since 2026-08-02, so a second copy would be duplicated
committed data).  This module is the promotion's teeth.

What is pinned: **full-resolution** band-mean total transmittance and the two
path-radiance components MODTRAN reports separately (thermal and scattered),
straight off the parser.  These are deliberately *not* the slit-degraded library
values — the library's own goldens live in
``test_shipped_atmosphere_library.py`` and in
``test_batch2_atmosphere_families.py``.  A parser regression, a re-staging
accident, or a swapped run therefore fails here first, at the boundary, before
any interpolation can average it away.

Every expectation was read off the delivered file on 2026-08-02 with the
band-mean definition below (a trapezoid integral over the band divided by its
width, in µm) — hand-derived from the tape7, never computed by a RADIANT
atmosphere model.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.modtran import Tape7Reader

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_RUNS = _REPO_ROOT / "modtran" / "real_runs"
_MATRIX_CSV = _REPO_ROOT / "docs" / "plans" / "modtran_run_matrix.csv"
_FIXTURE_MANIFEST = _REPO_ROOT / "tests" / "integration" / "fixtures" / "modtran" / "MANIFEST.md"

#: Run matrix rows promoted to fixtures (``destination`` = test_fixture + …).
_PROMOTED = ("M1", "N4", "N9", "O1", "P1")

#: run -> band [µm] -> (total τ, thermal path radiance, scattered path radiance)
#: [–, W/m²/sr/µm, W/m²/sr/µm], measured 2026-08-02 from the delivered tape7s.
_ANCHORS: dict[str, dict[tuple[float, float], tuple[float, float, float]]] = {
    "M1": {
        (0.5, 0.7): (0.663890, 3.567647e-25, 1.156627e02),
        (3.5, 4.1): (0.779188, 4.827541e-02, 4.907478e-02),
        (8.0, 12.0): (0.582553, 2.869921e00, 4.059390e-04),
    },
    "N4": {
        (0.5, 0.7): (0.586558, 4.891194e-25, 2.520987e02),
        (3.5, 4.1): (0.717442, 6.641847e-02, 1.704368e-01),
        (8.0, 12.0): (0.520694, 3.642793e00, 1.128885e-03),
    },
    "N9": {
        (0.5, 0.7): (0.492641, 6.031937e-25, 1.999640e02),
        (3.5, 4.1): (0.655133, 8.237745e-02, 9.203124e-02),
        (8.0, 12.0): (0.433470, 4.335199e00, 6.987200e-04),
    },
    "O1": {
        (0.5, 0.7): (0.879283, 2.873184e-25, 4.655177e00),
        (3.5, 4.1): (0.910128, 2.518881e-02, 1.282389e-03),
        (8.0, 12.0): (0.781067, 1.760190e00, 9.341033e-06),
    },
    "P1": {
        (0.5, 0.7): (0.655601, 1.160998e-25, 1.848943e02),
        (3.5, 4.1): (0.780110, 3.901047e-02, 9.093696e-02),
        (8.0, 12.0): (0.632870, 2.204335e00, 6.515039e-04),
    },
}


def _components(run: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """``(wavelength_um, tau_total, L_thermal, L_scattered)``, ascending in λ.

    Units: µm, dimensionless, W/m²/sr/µm.  The ``ν²`` factor is the same
    per-cm⁻¹ → per-µm Jacobian ``Tape7Reader.to_radiant_units`` applies; the
    components are read separately so a thermal pin is not contaminated by the
    multiple-scatter solar term (``IMULT = 1`` on these decks).
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
        (native.path_scattered_radiance[keep] * nu**2)[order],
    )


def _band_mean(lam: np.ndarray, values: np.ndarray, lo: float, hi: float) -> float:
    band = (lam >= lo) & (lam <= hi)
    return float(np.trapezoid(values[band], lam[band]) / (hi - lo))


def _matrix_row(run: str) -> dict[str, str]:
    with _MATRIX_CSV.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["run_id"] == run:
                return row
    raise AssertionError(f"{run} is not a run-matrix row")


@pytest.mark.level2
def test_the_promoted_set_is_exactly_what_the_matrix_marks_as_a_fixture() -> None:
    """The fixture list is derived from the matrix, not typed twice."""
    with _MATRIX_CSV.open(encoding="utf-8") as handle:
        batch2_fixtures = sorted(
            row["run_id"]
            for row in csv.DictReader(handle)
            if row["run_id"][0] in "MNOPQ"
            and row["run_id"][1:].isdigit()
            and row["destination"].strip() == "test_fixture + shipped_library"
        )
    assert batch2_fixtures == sorted(_PROMOTED)


@pytest.mark.level2
def test_the_promotion_manifest_records_every_promoted_run() -> None:
    """Rule 26: a committed artifact names its generator and its inputs."""
    text = _FIXTURE_MANIFEST.read_text(encoding="utf-8")
    for run in _PROMOTED:
        assert f"`{run}`" in text, run
    assert "modtran/real_runs" in text
    assert "real_runs_MANIFEST.sha256" in text


@pytest.mark.level2
@pytest.mark.parametrize("run", _PROMOTED)
def test_promoted_fixture_band_anchors(run: str) -> None:
    """Band-mean τ and both radiance components, full resolution.

    Tolerances are absolute and tight: τ to 1e-4 (the parser is exact
    arithmetic on the file, so any movement is a real change), radiance to
    0.2 % relative.  The VIS thermal column is ~1e-25 W/m²/sr/µm — MODTRAN's
    numerical zero for a 0.5–0.7 µm thermal term — and is pinned by order of
    magnitude only, since it carries no physics.
    """
    lam, tau, thermal, scattered = _components(run)
    for (lo, hi), (tau_ref, thermal_ref, scattered_ref) in _ANCHORS[run].items():
        assert _band_mean(lam, tau, lo, hi) == pytest.approx(tau_ref, abs=1e-4), (
            f"{run}: band-mean τ moved over {lo}–{hi} µm"
        )
        got_thermal = _band_mean(lam, thermal, lo, hi)
        if thermal_ref < 1.0e-12:
            assert got_thermal == pytest.approx(thermal_ref, rel=0.5), f"{run} {lo}-{hi} thermal"
            assert got_thermal < 1.0e-20  # numerically zero VIS thermal emission
        else:
            assert got_thermal == pytest.approx(thermal_ref, rel=2e-3), f"{run} {lo}-{hi} thermal"
        assert _band_mean(lam, scattered, lo, hi) == pytest.approx(scattered_ref, rel=2e-3), (
            f"{run}: band-mean scattered radiance moved over {lo}–{hi} µm"
        )


@pytest.mark.level2
@pytest.mark.parametrize("run", _PROMOTED)
def test_promoted_fixtures_are_physical(run: str) -> None:
    lam, tau, thermal, scattered = _components(run)
    assert np.all(np.diff(lam) > 0.0)
    assert np.all((tau >= 0.0) & (tau <= 1.0 + 1e-9))
    assert np.all(thermal >= 0.0)
    assert np.all(scattered >= 0.0)
    assert lam[0] < 0.45 and lam[-1] > 14.0


@pytest.mark.level2
def test_the_up_looking_pair_brackets_the_down_looking_partner() -> None:
    """Cross-fixture physics: more air mass ⇒ less transmittance.

    N4 (0 → 10 km at sec 1.4999) and N9 (the same column at sec 2.0) are the
    same air read at two zeniths; O1 (1 km → ground, nadir) is a *shorter*
    column and must be the most transmissive of the three.  This is the only
    check here that compares runs, and it is the one a swapped file fails.
    """
    band = (8.0, 12.0)
    tau = {}
    for run in ("N4", "N9", "O1"):
        lam, total, _t, _s = _components(run)
        tau[run] = _band_mean(lam, total, *band)
    assert tau["O1"] > tau["N4"] > tau["N9"]
    # And the sec ratio is what drives it: ln τ scales roughly with air mass.
    ratio = math.log(tau["N9"]) / math.log(tau["N4"])
    assert 1.1 < ratio < 1.5, ratio


@pytest.mark.level2
@pytest.mark.parametrize("run", _PROMOTED)
def test_promoted_fixture_geometry_matches_its_matrix_row(run: str) -> None:
    """The file really is the row it is pinned as (Card-3 echo vs the matrix)."""
    row = _matrix_row(run)
    echo_line = (_REAL_RUNS / f"{run}.tp7").read_text(encoding="utf-8").splitlines()[5]
    echo = [float(token) for token in echo_line.split()]
    assert echo[0] == pytest.approx(float(row["h1_sensor_km"]), abs=1e-6)
    assert echo[1] == pytest.approx(float(row["h2_target_km"]), abs=1e-6)
    assert echo[2] == pytest.approx(float(row["modtran_angle_at_h1_deg"]), abs=1e-6)
