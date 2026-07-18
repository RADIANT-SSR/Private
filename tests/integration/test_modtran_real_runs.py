"""Integration: physics cross-checks over the real 2026-07-17 MODTRAN 6 run set.

These assert relationships *between* runs in the 39-run matrix
(`docs/plans/modtran_run_matrix.csv`) that no single-file parse test can
cover — the mutual consistency of the two altitude ladders, and the
airmass behaviour that confirms the Card-3 ANGLE convention (CU-065).

The runs live gitignored under ``modtran/real_runs/`` until the committed
fixture subset lands (plan §7.1), so every test here is ``skipif``-guarded
on their presence and is a no-op in CI. They are the real-data analogue of
the plan §4 "free integration test requiring no extra runs".
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.modtran import Tape7Reader

_REAL_RUNS = Path(__file__).resolve().parents[2] / "modtran" / "real_runs"

pytestmark = pytest.mark.skipif(
    not _REAL_RUNS.exists(),
    reason="real MODTRAN run set not staged (modtran/real_runs/ is gitignored "
    "until the fixture subset is committed — plan §7.1)",
)


def _band_mean_transmittance(run: str, lo_um: float, hi_um: float) -> float:
    """Mean total transmittance of ``run`` over a wavelength window [µm]."""
    wl, trans, _, _ = Tape7Reader(_REAL_RUNS / f"{run}.tp7").to_radiant_units()
    band = (wl >= lo_um) & (wl <= hi_um)
    return float(trans[band].mean())


@pytest.mark.level2
def test_cross_ladder_consistency_C_vs_G() -> None:
    """Plan §4 cross-ladder identity: transmittance is multiplicative along
    a nadir path, so τ(100→h) / τ(35→h) must be constant across target
    altitude h — namely τ(100→35 km), the shared upper column. Block C
    (midlat_summer, 35 km sensor) and Block G (same, 100 km sensor)
    therefore validate each other with no extra runs.
    """
    # (h_tgt km, Block-C run [35 km sensor], Block-G run [100 km sensor]).
    # h=0 uses A3 for the space ladder (the plan's designated G h_tgt=0 anchor).
    pairs = [
        (0, "C1", "A3"),
        (1, "C2", "G1"),
        (5, "C3", "G2"),
        (10, "C4", "G3"),
        (20, "C5", "G4"),
        (29, "C6", "G5"),
    ]
    ratios = []
    for _h, c_run, g_run in pairs:
        tau_c = _band_mean_transmittance(c_run, 10.0, 11.0)  # LWIR window
        tau_g = _band_mean_transmittance(g_run, 10.0, 11.0)
        ratios.append(tau_g / tau_c)
    ratios_arr = np.array(ratios)
    # The ratio is the 35→100 km column transmittance: near-unity in the
    # LWIR window (thin upper atmosphere) and, crucially, constant.
    assert ratios_arr.std() < 1.0e-3, (
        f"cross-ladder ratio not constant: {ratios_arr}"
    )
    assert np.all(ratios_arr < 1.0)  # extra column only attenuates
    assert ratios_arr.mean() == pytest.approx(0.998, abs=3.0e-3)


@pytest.mark.level2
def test_airmass_monotonicity_confirms_angle_convention() -> None:
    """CU-065 physics: the B-block zenith fan (us_standard full column at
    increasing off-nadir angle) must show transmittance *decreasing* with
    off-nadir angle — proving ANGLE=180 is the shortest (nadir) path, not
    grazing. An inverted convention would reverse the ordering.
    """
    # (run, off-nadir deg) — A1 nadir (ANGLE 180), B1/B2/B3 = 30/45/60 off.
    fan = [("A1", 0.0), ("B1", 30.0), ("B2", 45.0), ("B3", 60.0)]
    taus = [_band_mean_transmittance(run, 10.0, 12.0) for run, _ in fan]
    assert taus == sorted(taus, reverse=True), (
        f"transmittance not decreasing with off-nadir angle: {taus}"
    )
    # Beer's-law airmass cross-check at 45° off-nadir (airmass = √2):
    # τ(45°) ≈ τ_nadir**(1/cos45°) = τ_nadir**√2.
    tau_nadir, tau_45 = taus[0], taus[2]
    assert tau_45 == pytest.approx(tau_nadir**np.sqrt(2.0), rel=0.02)
