#!/usr/bin/env python3
"""Grading harness for the PROPOSED substrate library (study section 8).

Three tiers, all run against the SHIPPED `radiant.optics.cavity_model.CavityModel`:

  Tier 1  -- material-data grading. Push the proposed n(lambda)/alpha(lambda) through
             the shipped cavity model for an UNCOATED window and compare T_sys and
             R_sys against each vendor page's published reflection loss. This grades
             the data product with no free parameters.
  Tier 2  -- emissivity grading. The absorptance A = 1 - T_sys - R_sys from Tier 1 IS
             the Kirchhoff emissivity. Compare it against the shipped `eps_eff`.
  Tier 3  -- warm-optics / cold-shield budget for a refractive MWIR head, computed
             both ways, against the published class figure for a real camera.

Run from the repo root with the worktree's own library on the path:
    PYTHONPATH=./src python docs/plans/substrate_data_proposed/grade_substrate_data.py
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import numpy as np

from radiant.core.constants import c, h, k_B
from radiant.core.spectral import SpectralData
from radiant.optics.cavity_model import CavityModel
from radiant.optics.etendue_cone import etendue_cone_solid_angle_sr

HERE = Path(__file__).resolve().parent
TABLES = HERE / "tables"


def load(name: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with (TABLES / f"{name}.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    lam = np.array([float(r["wavelength_um"]) for r in rows])
    n = np.array([float(r["n_refr"]) for r in rows])
    a = np.array([float(r["alpha_cm_inv"]) for r in rows])
    return lam, n, a


def sd(name: str, lam: np.ndarray, v: np.ndarray) -> SpectralData:
    return SpectralData(name=name, wavelength_um=lam, values=v, unit="", source="substrate study")


def planck(lam_um: np.ndarray, T: float) -> np.ndarray:
    """Spectral radiance [W/m^2/sr/um]."""
    lam = lam_um * 1e-6
    return (2.0 * h * c**2 / lam**5) / np.expm1(h * c / (lam * k_B * T)) * 1e-6


def eps_kirchhoff(R1: np.ndarray, R2: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Directional emissivity out of surface 2 = side-2 absorptance (study section 7.3)."""
    D = 1.0 - R1 * R2 * b * b
    return (1.0 - R2) * (1.0 - b) * (1.0 + R1 * b) / D


def fresnel(n: np.ndarray) -> np.ndarray:
    return ((n - 1.0) / (n + 1.0)) ** 2


def at(lam: np.ndarray, v: np.ndarray, lam0: float) -> float:
    return float(np.interp(lam0, lam, v))


# ---------------------------------------------------------------------------
# Tier 1 + 2
# ---------------------------------------------------------------------------
# (material, lambda_um, published n, published 2-surface reflection loss %)
PUBLISHED = [
    ("germanium", 10.6, 4.0021, 53.0),
    ("silicon", 5.0, 3.4223, 46.2),
    ("zinc_selenide", 10.6, 2.4028, 29.1),
    ("zinc_sulphide_ms", 10.0, 2.20084, 24.7),
    ("sapphire", 1.06, 1.75449, 14.0),
    ("calcium_fluoride", 5.0, 1.39908, 5.4),
    ("barium_fluoride", 5.0, 1.45, 6.5),
    ("fused_silica", 0.4, 1.47012, 7.0),
]


def tier12() -> None:
    print("=" * 100)
    print("TIER 1 -- uncoated-window grading against published reflection loss")
    print("         (Fresnel R from the proposed n, through the SHIPPED CavityModel)")
    print("=" * 100)
    print(
        f"{'material':<18} {'lam[um]':>8} {'n_pub':>8} {'n_prop':>8} {'dn':>9} "
        f"{'RL_pub[%]':>10} {'RL_model[%]':>12} {'resid[%]':>9}"
    )
    print("-" * 100)
    for name, lam0, n_pub, rl_pub in PUBLISHED:
        lam, n, a_cm = load(name)
        R = fresnel(n)
        cav = CavityModel(
            R1=sd("R1", lam, R),
            T1=sd("T1", lam, 1.0 - R),
            R2=sd("R2", lam, R),
            T2=sd("T2", lam, 1.0 - R),
            alpha=sd("alpha", lam, a_cm * 100.0),
            n_refr=sd("n", lam, n),
            thickness_m=0.003,  # 3 mm -- vendor reflection loss is quoted for a
            # thin window, where bulk absorption is negligible
        )
        n_prop = at(lam, n, lam0)
        rl_model = 100.0 * at(lam, cav.R_sys.values, lam0)
        print(
            f"{name:<18} {lam0:8.2f} {n_pub:8.4f} {n_prop:8.4f} {n_prop - n_pub:+9.4f} "
            f"{rl_pub:10.1f} {rl_model:12.2f} {rl_model - rl_pub:+9.2f}"
        )

    print()
    print("=" * 100)
    print("TIER 2 -- emissivity grading: AR-coated element (R1=R2=0.01), d = 8 mm")
    print("         eps_shipped = T2 n^2 (1-b)/D   vs   eps_correct = T2 (1-b)(1+R1 b)/D = A")
    print("=" * 100)
    print(
        f"{'material':<18} {'lam[um]':>8} {'a[1/cm]':>10} {'A':>9} {'eps_ship':>10} "
        f"{'eps_corr':>10} {'ratio':>8} {'clip?':>6}"
    )
    print("-" * 100)
    for name, lam0, _n_pub, _rl in PUBLISHED:
        lam, n, a_cm = load(name)
        R = np.full_like(lam, 0.01)
        cav = CavityModel(
            R1=sd("R1", lam, R),
            T1=sd("T1", lam, 1.0 - R),
            R2=sd("R2", lam, R),
            T2=sd("T2", lam, 1.0 - R),
            alpha=sd("alpha", lam, a_cm * 100.0),
            n_refr=sd("n", lam, n),
            thickness_m=0.008,
        )
        A = 1.0 - cav.T_sys.values - cav.R_sys.values
        es = cav.eps_eff.values
        ec = eps_kirchhoff(R, R, cav.beer)
        print(
            f"{name:<18} {lam0:8.2f} {at(lam, a_cm, lam0):10.2e} {at(lam, A, lam0):9.5f} "
            f"{at(lam, es, lam0):10.4f} {at(lam, ec, lam0):10.5f} "
            f"{at(lam, es, lam0) / at(lam, ec, lam0):8.2f} "
            f"{'YES' if at(lam, es, lam0) > 1.0 else '-':>6}"
        )


# ---------------------------------------------------------------------------
# Tier 3 -- warm-optics / cold-shield budget
# ---------------------------------------------------------------------------
def tier3(
    band: tuple[float, float] = (3.0, 5.0),
    f_number: float = 2.5,
    T_optics: float = 300.0,
    T_scene: float = 300.0,
    pitch_um: float = 15.0,
    t_int_s: float = 2.0e-3,
    qe: float = 0.75,
    train: list[tuple[str, float]] | None = None,
    label: str = "cooled MWIR head",
) -> tuple[float, float, float, float, float, float]:
    print()
    print("=" * 100)
    print(f"TIER 3 -- warm-optics / cold-shield budget, {label}")
    print("=" * 100)
    # Si / Ge / Si triplet, 5 mm each, AR-coated R = 0.01 per surface.
    if train is None:
        train = [("silicon", 5.0e-3), ("germanium", 5.0e-3), ("silicon", 5.0e-3)]
    R_coat = 0.01

    lam = np.arange(band[0], band[1] + 1e-9, 0.01)
    omega = etendue_cone_solid_angle_sr(f_number)
    B_opt = planck(lam, T_optics)
    B_scene = planck(lam, T_scene)

    # Per-element cavity quantities on the common band grid.
    elems = []
    for name, d_m in train:
        lam_m, n_m, a_m = load(name)
        n = np.interp(lam, lam_m, n_m)
        a = np.interp(lam, lam_m, a_m) * 100.0
        R = np.full_like(lam, R_coat)
        cav = CavityModel(
            R1=sd("R1", lam, R),
            T1=sd("T1", lam, 1.0 - R),
            R2=sd("R2", lam, R),
            T2=sd("T2", lam, 1.0 - R),
            alpha=sd("alpha", lam, a),
            n_refr=sd("n", lam, n),
            thickness_m=d_m,
        )
        elems.append((name, cav, R))

    tau_total = np.ones_like(lam)
    for _, cav, _ in elems:
        tau_total = tau_total * cav.T_sys.values

    def budget(mode: str) -> tuple[np.ndarray, list[tuple[str, float]]]:
        """Near-field irradiance at the FPA [W/m^2/um]; mode in {shipped, correct}."""
        E = np.zeros_like(lam)
        per: list[tuple[str, float]] = []
        for i, (name, cav, R) in enumerate(elems):
            eps = (
                np.clip(cav.eps_eff.values, 0.0, 1.0)
                if mode == "shipped"
                else eps_kirchhoff(R, R, cav.beer)
            )
            tau_down = np.ones_like(lam)
            for _, cav_j, _ in elems[i + 1 :]:
                tau_down = tau_down * cav_j.T_sys.values
            contrib = omega * eps * B_opt * tau_down
            E = E + contrib
            per.append((f"{name} #{i + 1}", float(np.trapezoid(contrib, lam))))
        return E, per

    A_pix = (pitch_um * 1e-6) ** 2
    E_scene = omega * B_scene * tau_total
    I_scene = float(np.trapezoid(E_scene, lam))

    def to_e(E_band: np.ndarray) -> float:
        """Band-integrated irradiance -> electrons per pixel per integration."""
        lam_m = lam * 1e-6
        ph = E_band * lam_m / (h * c)  # photons/s/m^2/um
        return float(np.trapezoid(ph, lam)) * A_pix * qe * t_int_s

    print(
        f"band {band[0]}-{band[1]} um, f/{f_number}, Omega_cone = {omega:.4f} sr, "
        f"optics {T_optics:.0f} K, scene {T_scene:.0f} K"
    )
    print(
        "train: "
        + " + ".join(f"{nm} {d * 1e3:.0f} mm" for nm, d in train)
        + f", AR R = {R_coat} per surface"
    )
    tau_mean = float(np.trapezoid(tau_total, lam)) / (band[1] - band[0])
    print(f"net in-band transmission tau = {tau_mean:.4f}")
    print(f"pixel {pitch_um:.0f} um, QE {qe}, t_int {t_int_s * 1e3:.1f} ms")
    print()
    print(f"{'term':<28} {'shipped':>16} {'correct':>16} {'ratio':>8}")
    print("-" * 72)
    E_s, per_s = budget("shipped")
    E_c, per_c = budget("correct")
    for (n1, v1), (_n2, v2) in zip(per_s, per_c, strict=True):
        print(f"  {n1:<26} {v1:16.5e} {v2:16.5e} {v1 / v2:8.2f}")
    I_s, I_c = float(np.trapezoid(E_s, lam)), float(np.trapezoid(E_c, lam))
    print(f"  {'TOTAL warm optics [W/m2]':<26} {I_s:16.5e} {I_c:16.5e} {I_s / I_c:8.2f}")
    print(f"  {'scene through train [W/m2]':<26} {I_scene:16.5e} {I_scene:16.5e} {1.0:8.2f}")
    print(f"  {'optics / scene':<26} {I_s / I_scene:16.3f} {I_c / I_scene:16.3f}")
    print()
    e_scene = to_e(E_scene)
    e_s, e_c = to_e(E_s), to_e(E_c)
    print(f"{'electrons per pixel per frame':<28} {'shipped':>16} {'correct':>16}")
    print("-" * 62)
    print(f"  {'scene':<26} {e_scene:16.4e} {e_scene:16.4e}")
    print(f"  {'warm optics':<26} {e_s:16.4e} {e_c:16.4e}")
    print(f"  {'total':<26} {e_scene + e_s:16.4e} {e_scene + e_c:16.4e}")
    print()
    # Shot-noise-limited NETD: dL/dT of the scene term, propagated.
    dT = 0.01
    dscene = (
        to_e(omega * planck(lam, T_scene + dT) * tau_total)
        - to_e(omega * planck(lam, T_scene - dT) * tau_total)
    ) / (2 * dT)
    netds: list[float] = []
    for tag, e_opt in (("shipped", e_s), ("correct", e_c)):
        netd = math.sqrt(e_scene + e_opt) / abs(dscene)
        netds.append(netd)
        print(
            f"  shot-limited NETD ({tag:<7}) = {netd * 1e3:8.2f} mK   "
            f"[signal slope {dscene:.3e} e-/K]"
        )
    return I_s / I_scene, I_c / I_scene, netds[0], netds[1], e_s, e_c


if __name__ == "__main__":
    tier12()
    _LWIR: dict[str, Any] = {
        "band": (8.0, 12.0),
        "f_number": 2.0,
        "pitch_um": 20.0,
        "t_int_s": 1.0e-3,
        "qe": 0.7,
    }
    _GE_DOUBLET = [("germanium", 8.0e-3), ("germanium", 8.0e-3)]
    cases: list[dict[str, Any]] = [
        {"label": "cooled MWIR head, 300 K scene (the benign case)"},
        {"label": "cooled MWIR head, 230 K cloud-top scene", "T_scene": 230.0},
        {
            "label": "cooled LWIR head, Ge doublet, 300 K scene",
            "train": _GE_DOUBLET,
            **_LWIR,
        },
        {
            "label": "cooled LWIR head, Ge doublet, 230 K cloud-top scene",
            "train": _GE_DOUBLET,
            "T_scene": 230.0,
            **_LWIR,
        },
        {
            "label": "space-looking LWIR, ZnS dome + Ge doublet, 50 K background",
            "train": [("zinc_sulphide_ms", 6.0e-3), *_GE_DOUBLET],
            "T_scene": 50.0,
            **_LWIR,
        },
    ]
    summary = [(str(kw["label"]), tier3(**kw)) for kw in cases]

    print()
    print("=" * 100)
    print("TIER 3 SUMMARY -- where the n^2 defect is results-affecting")
    print("=" * 100)
    print(
        f"{'case':<52} {'opt/scene ship':>14} {'opt/scene corr':>14} "
        f"{'opt e- ship':>12} {'opt e- corr':>12} {'NETD err':>9}"
    )
    print("-" * 118)
    for lbl, (rs, rc, ns, nc, es, ec) in summary:
        netd_err = f"{ns / nc - 1.0:+.1%}" if rc < 100.0 else "n/a (*)"
        print(f"{lbl[:51]:<52} {rs:14.3g} {rc:14.3g} {es:12.3e} {ec:12.3e} {netd_err:>9}")
    print()
    print("(*) the space-looking case has no scene signal to normalise NETD against:")
    print("    the warm optics ARE the background. Compare the optics electron columns.")
