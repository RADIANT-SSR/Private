"""ChainQuantity — a value with its reference frame and unit.

Implements backward propagation per ``docs/architecture/RADIANT_Signal_Chain_Architecture.md`` §5.

A ``ChainQuantity`` represents a physical value at a specific reference
frame in the signal chain. The ``to()`` method propagates the value
forward or backward through the chain using cumulative transfer factors
stored in stage_outputs.

Reference frames (ordered along the chain):

    at_target → at_aperture → post_optics → photoelectrons → post_readout → dn

The transfer factors between adjacent frames are:

    at_target → at_aperture:   × τ_atm(λ)  (spectral, band-averaged)
    at_aperture → post_optics: × τ_opt(λ) × A_collect × Ω_pixel  (spectral)
    post_optics → photoelectrons: × QE × (λ/hc) × Δλ × t_int  (spectral→scalar)
    photoelectrons → post_readout: × N_TDI × N_bin × N_coadd
    post_readout → dn:         ÷ gain_e_per_dn

For backward propagation (e.g., expressing noise at the aperture):
    divide by the forward factor instead of multiplying.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from radiant.core.chain import ChainState


class ReferenceFrame(enum.Enum):
    """Named positions in the signal chain."""

    AT_TARGET = "at_target"
    AT_APERTURE = "at_aperture"
    POST_OPTICS = "post_optics"
    PHOTOELECTRONS = "photoelectrons"
    POST_READOUT = "post_readout"
    DN = "dn"


# Ordered list for determining direction of propagation.
_FRAME_ORDER: list[ReferenceFrame] = [
    ReferenceFrame.AT_TARGET,
    ReferenceFrame.AT_APERTURE,
    ReferenceFrame.POST_OPTICS,
    ReferenceFrame.PHOTOELECTRONS,
    ReferenceFrame.POST_READOUT,
    ReferenceFrame.DN,
]

# Units at each reference frame for an extended-scene signal.
FRAME_UNITS: dict[ReferenceFrame, str] = {
    ReferenceFrame.AT_TARGET: "W/m²/sr/µm",
    ReferenceFrame.AT_APERTURE: "W/m²/sr/µm",
    ReferenceFrame.POST_OPTICS: "W/m²/sr/µm",
    ReferenceFrame.PHOTOELECTRONS: "e-",
    ReferenceFrame.POST_READOUT: "e-",
    ReferenceFrame.DN: "DN",
}


def _compute_transfer_factors(state: ChainState) -> dict[str, float]:
    """Extract cumulative transfer factors from stage_outputs.

    Returns a dict of forward factors between adjacent frames.
    Each factor converts from the left frame to the right frame
    by multiplication.
    """
    factors: dict[str, float] = {}

    # at_target → at_aperture: band-averaged atmospheric transmittance
    atm_out = state.stage_outputs.get("atmosphere", {})
    tau_atm = atm_out.get("tau_atm")
    if tau_atm is not None:
        import numpy as np

        tau_arr = np.asarray(tau_atm)
        factors["at_target->at_aperture"] = float(np.mean(tau_arr))

    # at_aperture → post_optics: band-averaged optical transmittance
    optics_out = state.stage_outputs.get("optics", {})
    tau_opt = optics_out.get("tau_opt")
    if tau_opt is not None:
        import numpy as np

        tau_arr = np.asarray(tau_opt)
        factors["at_aperture->post_optics"] = float(np.mean(tau_arr))

    # post_optics → photoelectrons: the integrated responsivity
    # The full factor includes A_collect, Ω_pixel, QE, ∫(λ/hc)dλ, t_int.
    # Rather than recomputing each term, we extract the composite factor
    # from the ratio signal_e / L_at_aperture_mean. This inherently
    # includes QE because signal_e was computed with QE in the forward pass.
    si_out = state.stage_outputs.get("spectral_integration", {})
    signal_e = si_out.get("signal_e")
    # For backward propagation, the key factor is:
    #   photoelectrons = L_at_aperture × τ_opt × A_collect × Ω_pixel × QE × (λ/hc) × Δλ × t_int
    # We store the composite factor.
    if signal_e is not None and signal_e > 0.0:
        # Get at-aperture mean radiance from the frame
        at_aperture_frame = state.frames.get("at_aperture")
        if at_aperture_frame is not None and at_aperture_frame.spectral_radiance is not None:
            import numpy as np

            L_mean = float(np.mean(at_aperture_frame.spectral_radiance))
            if L_mean > 0.0:
                # Total factor from at_aperture radiance to electrons
                factors["at_aperture->photoelectrons"] = signal_e / L_mean
                # Component factors
                tau_opt_mean = factors.get("at_aperture->post_optics", 1.0)
                if tau_opt_mean > 0.0:
                    factors["post_optics->photoelectrons"] = signal_e / (L_mean * tau_opt_mean)

    # photoelectrons → post_readout: TDI × binning × coadd
    ro_out = state.stage_outputs.get("readout", {})
    signal_e_final = ro_out.get("signal_e_final")
    det_out = state.stage_outputs.get("detector", {})
    det_signal_e = det_out.get("signal_e")
    if signal_e_final is not None and det_signal_e is not None and det_signal_e > 0.0:
        factors["photoelectrons->post_readout"] = signal_e_final / det_signal_e

    # post_readout → dn: ÷ gain
    signal_dn = ro_out.get("signal_dn_final")
    if signal_dn is not None and signal_e_final is not None and signal_e_final > 0.0:
        factors["post_readout->dn"] = signal_dn / signal_e_final

    return factors


def _get_forward_factor(
    source: ReferenceFrame,
    target: ReferenceFrame,
    factors: dict[str, float],
) -> float | None:
    """Compute the cumulative forward factor from source to target.

    Returns None if any intermediate factor is missing.
    """
    src_idx = _FRAME_ORDER.index(source)
    tgt_idx = _FRAME_ORDER.index(target)

    if src_idx == tgt_idx:
        return 1.0

    # Build list of steps
    if src_idx < tgt_idx:
        # Forward propagation
        cumulative = 1.0
        for i in range(src_idx, tgt_idx):
            left = _FRAME_ORDER[i]
            right = _FRAME_ORDER[i + 1]
            key = f"{left.value}->{right.value}"

            # Try direct key first
            if key in factors:
                cumulative *= factors[key]
            else:
                # Try composite key (skip intermediate frames)
                found = False
                for j in range(i + 1, tgt_idx + 1):
                    composite_right = _FRAME_ORDER[j]
                    composite_key = f"{left.value}->{composite_right.value}"
                    if composite_key in factors:
                        cumulative *= factors[composite_key]
                        # Skip intermediate frames covered by composite
                        # We can only do this cleanly for single-hop composites
                        found = True
                        break
                if not found:
                    return None
        return cumulative
    # Backward: get forward factor and invert
    fwd = _get_forward_factor(target, source, factors)
    if fwd is None or fwd == 0.0:
        return None
    return 1.0 / fwd


@dataclass(frozen=True)
class ChainQuantity:
    """A physical value at a specific reference frame.

    Parameters
    ----------
    value:
        The quantity value (scalar).
    frame:
        The reference frame where the value is expressed.
    unit:
        The physical unit of the value.
    name:
        Optional label (e.g., "read_noise", "signal").
    """

    value: float
    frame: ReferenceFrame
    unit: str
    name: str = ""

    def to(
        self,
        target_frame: ReferenceFrame,
        state: ChainState,
    ) -> ChainQuantity:
        """Propagate this quantity to a different reference frame.

        Parameters
        ----------
        target_frame:
            The target reference frame.
        state:
            The ChainState containing transfer factors.

        Returns
        -------
        ChainQuantity
            The value expressed at ``target_frame``.

        Raises
        ------
        ValueError
            If the transfer factor between frames is not available.
        """
        if target_frame == self.frame:
            return self

        factors = _compute_transfer_factors(state)
        factor = _get_forward_factor(self.frame, target_frame, factors)

        if factor is None:
            raise ValueError(
                f"Cannot propagate from {self.frame.value} to "
                f"{target_frame.value}: missing transfer factor(s). "
                f"Available factors: {list(factors.keys())}"
            )

        return ChainQuantity(
            value=self.value * factor,
            frame=target_frame,
            unit=FRAME_UNITS.get(target_frame, self.unit),
            name=self.name,
        )


def signal_at(
    state: ChainState,
    target_frame: ReferenceFrame,
) -> ChainQuantity:
    """Get the signal expressed at a target reference frame.

    Reads the signal from the ``photoelectrons`` frame and propagates
    to the target frame.
    """
    pe_frame = state.frames.get("photoelectrons")
    if pe_frame is None or pe_frame.in_band_value is None:
        raise ValueError(
            "signal_at: no 'photoelectrons' frame with in_band_value. "
            "Run SpectralIntegrationStage first."
        )

    signal_e = ChainQuantity(
        value=pe_frame.in_band_value,
        frame=ReferenceFrame.PHOTOELECTRONS,
        unit="e-",
        name="signal",
    )
    return signal_e.to(target_frame, state)


def noise_at(
    state: ChainState,
    target_frame: ReferenceFrame,
    term_name: str | None = None,
) -> ChainQuantity:
    """Get noise (total or a specific term) at a target reference frame.

    Parameters
    ----------
    state:
        Completed ChainState.
    target_frame:
        Frame in which to express the noise.
    term_name:
        If provided, return only the named noise term. If None, return
        the total noise (RSS of all terms).
    """
    import math

    if term_name is not None:
        matches = [nt for nt in state.noise_terms if nt.name == term_name]
        if not matches:
            raise ValueError(
                f"noise_at: no noise term named '{term_name}'. "
                f"Available: {[nt.name for nt in state.noise_terms]}"
            )
        nt = matches[0]
        origin = ReferenceFrame(nt.origin_frame)
        qty = ChainQuantity(
            value=nt.value_e,
            frame=origin,
            unit="e-",
            name=nt.name,
        )
        return qty.to(target_frame, state)

    # Total noise: RSS of all terms
    if len(state.noise_terms) == 0:
        raise ValueError("noise_at: no noise terms in ChainState.")

    # Verify all noise terms share the same origin frame.
    origins = {nt.origin_frame for nt in state.noise_terms}
    if len(origins) != 1:
        raise ValueError(
            f"noise_at: cannot RSS noise terms with mixed origin frames "
            f"{origins}. All terms must share one origin frame."
        )
    origin_frame = ReferenceFrame(origins.pop())

    noise_sq = sum(nt.value_e**2 for nt in state.noise_terms)
    total_noise = math.sqrt(noise_sq)

    qty = ChainQuantity(
        value=total_noise,
        frame=origin_frame,
        unit="e-",
        name="total_noise",
    )
    return qty.to(target_frame, state)
