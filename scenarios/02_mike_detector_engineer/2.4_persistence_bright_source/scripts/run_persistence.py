#!/usr/bin/env python3
"""Scenario 2.4 — persistence characterization after a bright source.

Mike's Type-II superlattice LWIR detector shows image persistence: after
imaging a hot 800 K calibration source (150,000 e-), a residual ghost
signal lingers for several frames. He wants the residual signal and its
shot noise frame-by-frame, how many frames until the ghost clears below one
LSB, and how the persistence contaminates the current scene's SNR.

Uses the new multi-frame model
(`radiant.detector.persistence_sequence`): residual_e(n) =
prior · f · exp(−(n−1)·Δt/τ), with per-frame shot noise √residual_e.

Every printed number carries units; the model and the noise vs bias
distinction are explained inline (house rules).

Run from the repo root:
    python scenarios/02_mike_detector_engineer/2.4_persistence_bright_source/scripts/run_persistence.py
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.detector.persistence_sequence import (
    frames_to_clear,
    persistence_residual_sequence_e,
)

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
OUTPUTS = SCEN / "outputs"
OUTPUTS.mkdir(exist_ok=True)

# --- Config (mike_persistence.xlsx) -----------------------------------
PERSISTENCE_FRACTION = 0.015
TAU_S = 0.050
PRIOR_SIGNAL_E = 150_000.0
FRAME_RATE_HZ = 60.0
FRAME_INTERVAL_S = 1.0 / FRAME_RATE_HZ
SCENE_SIGNAL_E = 20_000.0
DARK_E_PER_S = 5.0e5
T_INT_S = 0.010
READ_NOISE_E = 300.0
GAIN_E_PER_DN = 100.0  # 1 LSB
N_FRAMES = 20


def main() -> None:
    print("=" * 74)
    print("SCENARIO 2.4 — IMAGE PERSISTENCE AFTER A BRIGHT SOURCE")
    print("=" * 74)
    print(
        f"Prior exposure {PRIOR_SIGNAL_E:,.0f} e- (800 K source); persistence "
        f"{PERSISTENCE_FRACTION*100:.1f}% after 1 frame, τ = {TAU_S*1e3:.0f} ms, "
        f"{FRAME_RATE_HZ:.0f} Hz (Δt = {FRAME_INTERVAL_S*1e3:.2f} ms)."
    )
    print(
        f"Current scene {SCENE_SIGNAL_E:,.0f} e-, t_int {T_INT_S*1e3:.0f} ms, "
        f"read noise {READ_NOISE_E:.0f} e-, 1 LSB = {GAIN_E_PER_DN:.0f} e-."
    )
    print()

    residual = persistence_residual_sequence_e(
        PRIOR_SIGNAL_E, PERSISTENCE_FRACTION, TAU_S, FRAME_INTERVAL_S, N_FRAMES
    )
    persistence_noise = np.sqrt(residual)  # shot noise on the released charge
    dark_e = DARK_E_PER_S * T_INT_S

    # Baseline (clean) noise and SNR for the current scene.
    noise_clean = np.sqrt(SCENE_SIGNAL_E + dark_e + READ_NOISE_E**2)
    snr_clean = SCENE_SIGNAL_E / noise_clean
    # Contaminated: the ghost adds shot noise (√residual) in quadrature.
    noise_contam = np.sqrt(SCENE_SIGNAL_E + dark_e + READ_NOISE_E**2 + residual)
    snr_contam = SCENE_SIGNAL_E / noise_contam

    print("-" * 74)
    print("FRAME-BY-FRAME PERSISTENCE (residual ghost signal + shot noise)")
    print("-" * 74)
    print(f"{'frame':>6}{'residual [e-]':>15}{'persist noise':>15}{'ghost [LSB]':>13}{'SNR':>9}")
    for n in range(N_FRAMES):
        if n < 8 or n % 4 == 0:
            print(
                f"{n+1:>6}{residual[n]:>15.1f}{persistence_noise[n]:>15.1f}"
                f"{residual[n]/GAIN_E_PER_DN:>13.1f}{snr_contam[n]:>9.1f}"
            )

    n_clear = frames_to_clear(
        PRIOR_SIGNAL_E, PERSISTENCE_FRACTION, TAU_S, FRAME_INTERVAL_S, GAIN_E_PER_DN
    )
    print(
        f"\n  Frames to clear below 1 LSB ({GAIN_E_PER_DN:.0f} e-): {n_clear} "
        f"(~{n_clear*FRAME_INTERVAL_S*1e3:.0f} ms of dead time)."
    )
    print(
        f"  Clean SNR (no persistence): {snr_clean:.1f}. In frame 1 the ghost "
        f"({residual[0]:.0f} e-, {residual[0]/GAIN_E_PER_DN:.0f} LSB) drops SNR to "
        f"{snr_contam[0]:.1f} ({(snr_contam[0]/snr_clean-1)*100:+.0f}%)."
    )
    print(
        "  Two effects: the residual is a BIAS (a ghost image at the LSB levels "
        "above) AND adds shot noise. The bias is the operational problem — a "
        f"{residual[0]/GAIN_E_PER_DN:.0f}-LSB false structure in frame 1 — and it "
        "does not average away frame-to-frame the way random noise does."
    )

    # ---------------------------------------------------------------
    # FIGURE 1 — residual + noise vs frame, with the 1-LSB floor.
    # ---------------------------------------------------------------
    frames = np.arange(1, N_FRAMES + 1)
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.semilogy(frames, residual, "o-", color="#7030A0", label="residual signal (ghost)")
    ax.semilogy(frames, persistence_noise, "s-", color="#C55A11", label="persistence shot noise")
    ax.axhline(GAIN_E_PER_DN, color="black", ls="--", lw=1.5, label=f"1 LSB = {GAIN_E_PER_DN:.0f} e-")
    ax.axvline(n_clear, color="green", ls=":", lw=1.5, label=f"cleared at frame {n_clear}")
    ax.set_xlabel("Frame number after bright exposure")
    ax.set_ylabel("Electrons")
    ax.set_title("Scenario 2.4 — persistence residual & noise decay")
    ax.legend()
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig1 = OUTPUTS / "fig1_persistence_decay.png"
    fig.savefig(fig1, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1.name}")

    # ---------------------------------------------------------------
    # FIGURE 2 — SNR clean vs contaminated per frame.
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(frames, snr_contam, "o-", color="#7030A0", label="SNR with persistence")
    ax.axhline(snr_clean, color="black", ls="--", lw=1.5, label=f"clean SNR = {snr_clean:.0f}")
    ax.set_xlabel("Frame number after bright exposure")
    ax.set_ylabel("Current-scene SNR")
    ax.set_title("Scenario 2.4 — scene SNR recovery after a bright exposure")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig2 = OUTPUTS / "fig2_snr_recovery.png"
    fig.savefig(fig2, dpi=130)
    plt.close(fig)
    print(f"Wrote {fig2.name}")

    print()
    print("=" * 74)
    print("DONE — see outputs/ for figures and MANIFEST.md.")
    print("=" * 74)


if __name__ == "__main__":
    main()
