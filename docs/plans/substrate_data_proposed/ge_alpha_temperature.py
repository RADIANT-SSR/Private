#!/usr/bin/env python3
"""Does germanium's alpha(lambda, T) force a temperature axis in v1? (study section 7.2)

Builds a physically-decomposed alpha_Ge(lambda, T) from the one measured anchor
(alpha = 0.027 cm^-1 at 10.6 um, 293 K, optical grade) and asks what the
temperature dependence does to the EMITTED RADIANCE eps*B -- which is the only
thing RADIANT consumes.

    alpha_Ge(lam, T) = alpha_mp(lam) * f_mp(T) + alpha_FC(lam, T)

  alpha_mp  multiphonon lattice absorption. An N-phonon SUM process scales as
            (1 + nbar)^N with nbar(T) the Bose occupation of the zone-centre
            optical phonon (Ge: 301 cm^-1 = 433 K). N = ceil(nu_tilde / 301).
  alpha_FC  Drude free-carrier absorption,
                alpha_FC = e^3 lam^2 N_c / (4 pi^2 eps0 c^3 n m*^2 mu)
            with carriers = ionised donors (set by the room-temperature
            resistivity that optical Ge is specified by) plus the intrinsic
            pair density n_i(T), and lattice-limited mobilities.

Run from the repo root:
    PYTHONPATH=./src python docs/plans/substrate_data_proposed/ge_alpha_temperature.py
"""

from __future__ import annotations

import numpy as np
from scipy.constants import electron_mass as m_e
from scipy.constants import epsilon_0 as eps_0

from radiant.core.constants import c, h, k_B
from radiant.core.constants import q as e

# NOTE: `radiant.core.constants` carries no vacuum permittivity and no electron
# mass -- it is a radiometry constants module. If alpha(lambda, T) is ever
# implemented in the library, Rule 13 requires adding eps_0 and m_e there
# rather than importing them from scipy inside a physics module. Recorded in
# the study's open items; this script is study evidence, not library code.

KB_EV = k_B / e  # eV/K
N_OPT = 4.00  # Ge optical index across the LWIR (flat to 1e-3)
PHONON_CM = 301.0  # Ge zone-centre optical phonon [cm^-1]
PHONON_K = PHONON_CM * h * c * 1e2 / k_B  # [K]

# Measured anchor (Crystran, optical-grade Ge, manufacturer typical).
LAM_ANCHOR = 10.6
ALPHA_ANCHOR_300 = 0.027  # [1/cm]


def eg_ge(T: np.ndarray) -> np.ndarray:
    """Varshni bandgap of Ge [eV]."""
    return 0.7437 - 4.774e-4 * T**2 / (T + 235.0)


def n_i_ge(T: np.ndarray) -> np.ndarray:
    """Intrinsic carrier density [1/m^3] from the effective-DOS expression."""
    mde, mdh = 0.56 * m_e, 0.29 * m_e
    nc = 2.0 * (2.0 * np.pi * mde * k_B * T / h**2) ** 1.5
    nv = 2.0 * (2.0 * np.pi * mdh * k_B * T / h**2) ** 1.5
    return np.sqrt(nc * nv) * np.exp(-eg_ge(T) / (2.0 * KB_EV * T))


def mobilities(T: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Lattice-limited mobilities [m^2/Vs]: Ge mu_e ~ T^-1.66, mu_h ~ T^-2.33."""
    return 0.3900 * (T / 300.0) ** -1.66, 0.1900 * (T / 300.0) ** -2.33


def alpha_fc(lam_um: float, T: np.ndarray, rho_300_ohm_cm: float) -> np.ndarray:
    """Drude free-carrier absorption [1/cm]."""
    mu_e300 = float(mobilities(np.array(300.0))[0])
    n_d = 1.0 / (rho_300_ohm_cm * 1e-2 * e * mu_e300)  # ionised donors [1/m^3]
    ni = n_i_ge(T)
    n_e = n_d + ni
    n_h = ni**2 / n_e
    mu_e, mu_h = mobilities(T)
    mce, mch = 0.12 * m_e, 0.29 * m_e
    pref = e**3 * (lam_um * 1e-6) ** 2 / (4.0 * np.pi**2 * eps_0 * c**3 * N_OPT)
    return pref * (n_e / (mce**2 * mu_e) + n_h / (mch**2 * mu_h)) / 100.0


def nbar(T: np.ndarray) -> np.ndarray:
    """Bose occupation of the Ge optical phonon."""
    return 1.0 / np.expm1(PHONON_K / T)


def alpha_ge(lam_um: float, T: np.ndarray, rho_300_ohm_cm: float = 40.0) -> np.ndarray:
    """alpha_Ge(lam, T) [1/cm], anchored to the 293 K measurement at 10.6 um."""
    n_phonon = float(np.ceil(1.0e4 / lam_um / PHONON_CM))
    # Calibrate the multiphonon level at 300 K from the measured anchor.
    a_mp_300 = ALPHA_ANCHOR_300 - float(alpha_fc(LAM_ANCHOR, np.array(300.0), rho_300_ohm_cm))
    # Reuse the measured anchor's spectral level (this routine is used at 10.6 um
    # only; lambda enters alpha_FC's lambda^2 and the phonon order).
    f_mp = ((1.0 + nbar(T)) / (1.0 + nbar(np.array(300.0)))) ** n_phonon
    return a_mp_300 * f_mp + alpha_fc(lam_um, T, rho_300_ohm_cm)


def eps_slab(alpha_cm: np.ndarray, d_cm: float, r1: float = 0.01, r2: float = 0.01) -> np.ndarray:
    """Correct directional emissivity out of surface 2 (study section 7.3)."""
    b = np.exp(-alpha_cm * d_cm)
    return (1.0 - r2) * (1.0 - b) * (1.0 + r1 * b) / (1.0 - r1 * r2 * b * b)


def planck(lam_um: float, T: np.ndarray) -> np.ndarray:
    lam = lam_um * 1e-6
    return (2.0 * h * c**2 / lam**5) / np.expm1(h * c / (lam * k_B * T)) * 1e-6


def main() -> None:
    print(f"Ge optical phonon: {PHONON_CM:.0f} cm^-1 = {PHONON_K:.0f} K")
    print(f"n_i(Ge, 300 K) computed = {float(n_i_ge(np.array(300.0))) / 1e6:.2e} cm^-3")
    print("  literature anchor      = 2.4e13 cm^-3  (DOS-mass uncertainty, factor ~1.4)")
    print()
    print("=" * 96)
    print("alpha_Ge at 10.6 um vs T, decomposed (40 ohm.cm optical grade)")
    print("=" * 96)
    ts = np.array([80.0, 120.0, 180.0, 230.0, 250.0, 273.0, 293.0, 300.0, 320.0, 350.0, 400.0])
    a_fc = alpha_fc(10.6, ts, 40.0)
    a_tot = alpha_ge(10.6, ts, 40.0)
    a_mp = a_tot - a_fc
    print(f"{'T[K]':>7} {'a_mp':>10} {'a_FC':>10} {'a_tot':>10} {'a/a(300K)':>11} {'FC share':>9}")
    print("-" * 62)
    a300 = float(alpha_ge(10.6, np.array(300.0), 40.0))
    for i, t in enumerate(ts):
        print(
            f"{t:7.0f} {a_mp[i]:10.5f} {a_fc[i]:10.5f} {a_tot[i]:10.5f} "
            f"{a_tot[i] / a300:11.3f} {a_fc[i] / a_tot[i]:9.1%}"
        )

    print()
    print("=" * 96)
    print("Resistivity grade sensitivity at 300 K and at 350 K (10.6 um)")
    print("=" * 96)
    print(f"{'rho(300K)[ohm.cm]':>18} {'a_FC(300K)':>12} {'a_FC(350K)':>12} {'a_FC(400K)':>12}")
    for rho in [1.0, 5.0, 20.0, 40.0]:
        print(
            f"{rho:18.0f} {float(alpha_fc(10.6, np.array(300.0), rho)):12.5f} "
            f"{float(alpha_fc(10.6, np.array(350.0), rho)):12.5f} "
            f"{float(alpha_fc(10.6, np.array(400.0), rho)):12.5f}"
        )

    print()
    print("=" * 96)
    print("THE DECIDING TABLE -- error in EMITTED RADIANCE from using alpha(300 K)")
    print("for a Ge element actually at T.  d = 8 mm, AR R = 0.01, lambda = 10.6 um.")
    print("=" * 96)
    print(
        f"{'T[K]':>7} {'a(T)':>9} {'eps(a(T))':>11} {'eps(a300)':>11} "
        f"{'B(T)':>10} {'L_true':>11} {'L_ref':>11} {'radiance err':>13}"
    )
    print("-" * 92)
    eps_ref = float(eps_slab(np.array(a300), 0.8))
    for t in ts:
        a_t = float(alpha_ge(10.6, np.array(t), 40.0))
        e_t = float(eps_slab(np.array(a_t), 0.8))
        b = float(planck(10.6, np.array(t)))
        print(
            f"{t:7.0f} {a_t:9.5f} {e_t:11.6f} {eps_ref:11.6f} {b:10.4f} "
            f"{e_t * b:11.6f} {eps_ref * b:11.6f} {eps_ref / e_t - 1.0:+12.1%}"
        )
    print()
    print("=" * 96)
    print("Phonon-order sensitivity: is the multiphonon T-scaling a modelling artefact?")
    print("=" * 96)
    nb300 = float(nbar(np.array(300.0)))
    print(f"{'T[K]':>7} " + " ".join(f"{'N=' + str(n):>9}" for n in (3, 4, 5)))
    for t in (80.0, 230.0, 300.0, 350.0):
        nb = float(nbar(np.array(t)))
        row = " ".join(f"{((1 + nb) / (1 + nb300)) ** n:9.3f}" for n in (3, 4, 5))
        print(f"{t:7.0f} {row}")
    print("  -> the N choice moves a_mp(T)/a_mp(300 K) by about +/-10 %; the effect")
    print("     itself (0.66x at 230 K, 1.17x at 320 K) is robust to it.")
    print()
    print("READING (study section 7.2):")
    print("  The radiance-error column is the only thing RADIANT consumes. From a")
    print("  300 K reference alpha it is +4.9 % at 293 K, +19 % at 273 K, +54 % at")
    print("  230 K and -38 % at 350 K. So the T dependence is REAL -- not negligible")
    print("  -- but it is second order next to the n^2 defect (+1586 % for Ge).")
    print("  Below ~200 K the fractional error grows while B(T) collapses, so the")
    print("  absolute error vanishes; above 350 K free carriers take over and the")
    print("  reference value is wrong by more than the term it computes.")


if __name__ == "__main__":
    main()
