#!/usr/bin/env python3
"""Scenario 6.5 — emissivity sensitivity for LWIR temperature retrieval.

Dr. Chen studies how an error in the *assumed* surface emissivity biases a
retrieved surface temperature. The true scene is T = 300 K, ε = 0.95; she
sweeps the assumed ε from 0.90 to 1.00 and asks what temperature the
retrieval returns, how the error grows, and how it compares to the sensor's
own NEDT floor.

Uses the new retrieval model (`radiant.performance.temperature_retrieval`):
the measured band radiance is `L = ε_true·B̄(T_true)`; retrieval inverts
`ε_assumed·B̄(T) = L` for T. The operating-point Jacobian
(∂L/∂ε = B̄(T), ∂L/∂T = ε·∫dB/dT) gives the first-order error law and the
NEDT-equivalent emissivity uncertainty.

Every printed number carries units; the model and the physics of the bias
are explained inline (house rules).

Run from the repo root:
    python scenarios/06_dr_chen_researcher/6.5_spectral_emissivity_sensitivity/scripts/run_emissivity_retrieval.py
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.performance.temperature_retrieval import (
    band_planck_radiance,
    emissivity_jacobian,
    retrieve_temperature_K,
    temperature_jacobian,
)

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
OUTPUTS = SCEN / "outputs"
OUTPUTS.mkdir(exist_ok=True)

# --- Config (chen_retrieval_config.xlsx) ------------------------------
T_TRUE_K = 300.0
EPS_TRUE = 0.95
EPS_MIN, EPS_MAX, EPS_STEP = 0.90, 1.00, 0.01
BAND = np.linspace(8.0, 12.0, 400)
NEDT_MK = 50.0


def main() -> None:
    print("=" * 74)
    print("SCENARIO 6.5 — EMISSIVITY SENSITIVITY FOR TEMPERATURE RETRIEVAL")
    print("=" * 74)
    print(
        f"True scene: T = {T_TRUE_K:.0f} K, ε = {EPS_TRUE}. LWIR "
        f"{BAND[0]:.0f}–{BAND[-1]:.0f} µm. System NEDT = {NEDT_MK:.0f} mK."
    )
    print(
        "Retrieval inverts ε_assumed·B̄(T) = L_measured for T; a wrong ε biases "
        "the retrieved temperature."
    )
    print()

    # Forward: the radiance the sensor actually measures.
    l_measured = EPS_TRUE * band_planck_radiance(T_TRUE_K, BAND)

    # --- Jacobian at the operating point -------------------------------
    dL_deps = emissivity_jacobian(T_TRUE_K, BAND)  # W/m²/sr per unit ε
    dL_dT = temperature_jacobian(T_TRUE_K, EPS_TRUE, BAND)  # W/m²/sr/K
    # First-order error law: ΔT ≈ −(∂L/∂ε / ∂L/∂T)·Δε.
    dT_deps = -dL_deps / dL_dT  # K per unit ε
    print("-" * 74)
    print("JACOBIAN AT THE OPERATING POINT (T=300 K, ε=0.95)")
    print("-" * 74)
    print(f"  ∂L/∂ε = B̄(T)        = {dL_deps:.4f} W/m²/sr per unit ε")
    print(f"  ∂L/∂T = ε·∫dB/dT dλ = {dL_dT:.5f} W/m²/sr/K")
    print(f"  dT/dε (first order) = {dT_deps:+.1f} K per unit ε "
          f"({dT_deps/100:+.2f} K per 0.01 ε)")
    print(
        "  A LOWER assumed ε implies the surface must be HOTTER to emit the same "
        "radiance → over-estimate; a higher assumed ε → under-estimate."
    )

    # --- Retrieval sweep -----------------------------------------------
    eps_assumed = np.arange(EPS_MIN, EPS_MAX + 0.5 * EPS_STEP, EPS_STEP)
    t_retrieved = np.array(
        [retrieve_temperature_K(l_measured, float(e), BAND) for e in eps_assumed]
    )
    t_error = t_retrieved - T_TRUE_K
    eps_error = eps_assumed - EPS_TRUE

    print()
    print("-" * 74)
    print("RETRIEVAL SWEEP (assumed ε → retrieved T)")
    print("-" * 74)
    print(f"{'assumed ε':>10}{'ε error':>10}{'retrieved T':>14}{'T error':>10}")
    for e, ee, tr, te in list(zip(eps_assumed, eps_error, t_retrieved, t_error))[::2]:
        print(f"{e:>10.2f}{ee:>+10.2f}{tr:>12.2f}K{te:>+9.2f}K")

    # NEDT-equivalent emissivity uncertainty: the ε error that biases T by
    # exactly the system NEDT (via the first-order law).
    nedt_k = NEDT_MK * 1e-3
    eps_uncert_for_nedt = abs(nedt_k / dT_deps)
    print(
        f"\n  NEDT-equivalent ε uncertainty: an ε error of "
        f"±{eps_uncert_for_nedt:.4f} biases the retrieved T by the system NEDT "
        f"({NEDT_MK:.0f} mK)."
    )
    print(
        "  Interpretation: emissivity must be known to ~"
        f"{eps_uncert_for_nedt*100:.2f}% for the retrieval bias to stay below the "
        "sensor's own temperature resolution. Beyond that, ε knowledge — not "
        "detector NEDT — limits retrieval accuracy."
    )
    worst = t_error[np.argmax(np.abs(t_error))]
    print(
        f"  Over the full ±0.05 ε sweep the retrieval bias reaches {worst:+.1f} K "
        f"— {abs(worst)/nedt_k:.0f}× the NEDT floor."
    )

    # ---------------------------------------------------------------
    # FIGURE 1 — retrieved T vs assumed ε.
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(eps_assumed, t_retrieved, "o-", color="#375623")
    ax.axhline(T_TRUE_K, color="black", ls="--", lw=1, label=f"true T = {T_TRUE_K:.0f} K")
    ax.axvline(EPS_TRUE, color="gray", ls=":", lw=1, label=f"true ε = {EPS_TRUE}")
    ax.fill_between(
        eps_assumed, T_TRUE_K - nedt_k, T_TRUE_K + nedt_k, color="green", alpha=0.12,
        label=f"±NEDT ({NEDT_MK:.0f} mK)",
    )
    ax.set_xlabel("Assumed emissivity")
    ax.set_ylabel("Retrieved temperature (K)")
    ax.set_title("Scenario 6.5 — retrieval bias from assumed-emissivity error")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig1 = OUTPUTS / "fig1_retrieved_temperature.png"
    fig.savefig(fig1, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1.name}")

    # ---------------------------------------------------------------
    # FIGURE 2 — T error vs ε error, with the first-order law overlaid.
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(eps_error, t_error, "o-", color="#C55A11", label="exact retrieval")
    ax.plot(eps_error, dT_deps * eps_error, "--", color="#2E75B6", label="first-order (Jacobian)")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xlabel("Emissivity error (assumed − true)")
    ax.set_ylabel("Temperature error (K)")
    ax.set_title("Scenario 6.5 — retrieval T-error vs ε-error")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig2 = OUTPUTS / "fig2_error_vs_error.png"
    fig.savefig(fig2, dpi=130)
    plt.close(fig)
    print(f"Wrote {fig2.name}")

    print()
    print("=" * 74)
    print("DONE — see outputs/ for figures and MANIFEST.md.")
    print("=" * 74)


if __name__ == "__main__":
    main()
