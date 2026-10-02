"""What scaling each noise term received, and why (Gap 133).

CU-381 was invisible for two releases for one reason: the co-added 1/f number
was simply *smaller than it should be*, with nothing in the output to say what
had been applied to it. The scaling a term receives depends on a correlation
judgement — is this the same fluctuation in every frame, or an independent draw?
— and that judgement was made in code and reported nowhere. The person best
placed to notice it is wrong is the analyst reading the budget, and they could
not see it.

So this module reports, per term, **the factor applied on each axis and the
correlation class that chose it**.

Why the factors are measured, not described
-------------------------------------------
Each reported factor is obtained by pushing ``1.0`` through the *same* scaling
helper the stage applies to the real value. It is therefore the factor actually
applied, not a second implementation of the rule that could drift from it —
which matters, because a drifting report of a correlation class is worse than
no report. ``test_noise_scaling_record`` pins the reconciliation for every
multiplicative term: ``reported_factor × raw == scaled``.

The 1/f exception, which is the point
-------------------------------------
``flicker_1f`` has **no co-add factor at all**, and reporting one would be a
lie. Since CU-381 its co-add behaviour is the Dirichlet comb inside
:mod:`radiant.readout.flicker_transfer` — a frequency-dependent crossover from
coherent (``K²`` in variance) below ``1/T_total`` to incoherent (``K``) far
above, whose effective exponent on K measured 0.921 for one case. No single
exponent is correct, so none is applied, and this record says so in words
instead of inventing a number. That is exactly the honesty Gap 133 asked for.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from radiant.core.noise_budget import SPATIAL_TERMS
from radiant.readout.binning_offchip import offchip_scale_read_noise, offchip_scale_shot_noise
from radiant.readout.binning_onchip import onchip_scale_read_noise, onchip_scale_shot_noise
from radiant.readout.coadds import CoaddMode, coadd_scale_fpn, coadd_scale_temporal_noise
from radiant.readout.tdi_scaling import tdi_scale_fpn, tdi_scale_read_noise, tdi_scale_shot_noise

__all__ = ["NoiseScaling", "CORRELATION_CLASSES", "describe_noise_scaling"]

#: The correlation classes a term can fall into, and what each means.
CORRELATION_CLASSES: Final[dict[str, str]] = {
    "shot": "independent draw per sample on every axis — adds in quadrature",
    "read_like": "injected once per read, so TDI and on-chip binning do not multiply it",
    "spatial": "a fixed pattern: the same systematic in every frame, so it adds coherently",
    "transfer_function": "no per-axis factor on the co-add axis — the correlation is "
    "frequency-dependent and lives in the measurement's transfer function (CU-381)",
    "post_conversion": "computed at the accumulated-charge level, where n_counts already "
    "carries TDI and on-chip binning — so only the post-conversion axes apply",
}

_READ_LIKE: Final[frozenset[str]] = frozenset({"read_noise", "ktc_reset", "quantization"})

#: The Gap-117 counting terms. These do NOT go through the stage's generic
#: per-term scaling: they are computed at the final accumulated charge level,
#: where n_counts already reflects TDI and on-chip binning, so only the
#: post-conversion axes apply. Reporting a TDI or on-chip factor for them
#: would double-count — the reconciliation test caught exactly that mistake
#: in this module's first version.
_COUNTING_POST_CONVERSION: Final[frozenset[str]] = frozenset(
    {"counting_quantization", "packet_reset"}
)


@dataclass(frozen=True, slots=True)
class NoiseScaling:
    """The scaling one noise term received, per axis, with its class.

    A ``None`` factor means *no factor was applied on that axis* — which is not
    the same as a factor of 1.0, and the distinction is the whole content of the
    1/f case.
    """

    term: str
    correlation_class: str
    tdi_factor: float | None
    onchip_factor: float | None
    offchip_factor: float | None
    coadd_factor: float | None
    note: str = ""

    def __str__(self) -> str:
        def fmt(value: float | None) -> str:
            return "—" if value is None else f"x{value:.4g}"

        return (
            f"{self.term:<24} {self.correlation_class:<18} "
            f"TDI {fmt(self.tdi_factor):>10}  bin {fmt(self.onchip_factor):>8}"
            f"/{fmt(self.offchip_factor):<8} coadd {fmt(self.coadd_factor):>10}"
            + (f"  [{self.note}]" if self.note else "")
        )


def describe_noise_scaling(
    term_name: str,
    *,
    n_tdi: int,
    tdi_digital: bool,
    mx_on: int,
    my_on: int,
    px_off: int,
    py_off: int,
    n_coadds: int,
    coadd_mode: CoaddMode,
) -> NoiseScaling:
    """The per-axis factors applied to ``term_name``, measured not described.

    Every factor comes from pushing 1.0 through the same helper the stage uses,
    so this cannot report a rule the stage does not follow.
    """
    if term_name == "flicker_1f":
        # TDI and binning still apply; the co-add axis does not (CU-381).
        tdi = tdi_scale_fpn(1.0, n_tdi) if tdi_digital else tdi_scale_shot_noise(1.0, n_tdi)
        return NoiseScaling(
            term=term_name,
            correlation_class="transfer_function",
            tdi_factor=tdi,
            onchip_factor=onchip_scale_shot_noise(1.0, mx_on, my_on),
            offchip_factor=offchip_scale_shot_noise(1.0, px_off, py_off),
            coadd_factor=None,
            note=(
                "co-add correlation is the Dirichlet comb in flicker_transfer, not a "
                "factor: coherent below 1/T_total, incoherent far above, so no single "
                "exponent is correct. TDI is x sqrt(N) on analog (independent pixels) "
                "and x N on digital (same pixel re-read)."
            ),
        )

    if term_name in SPATIAL_TERMS:
        is_scene_correlated = term_name == "clutter"
        tdi = (
            tdi_scale_fpn(1.0, n_tdi)
            if (tdi_digital or is_scene_correlated)
            else tdi_scale_shot_noise(1.0, n_tdi)
        )
        note = (
            "scene-correlated: the same ground point in every TDI stage, so x N regardless of mode"
            if is_scene_correlated
            else (
                "same pixel re-read under digital TDI, so x N"
                if tdi_digital
                else "different physical pixels per analog TDI stage, so x sqrt(N)"
            )
        )
        return NoiseScaling(
            term=term_name,
            correlation_class="spatial",
            tdi_factor=tdi,
            onchip_factor=onchip_scale_shot_noise(1.0, mx_on, my_on),
            offchip_factor=offchip_scale_shot_noise(1.0, px_off, py_off),
            coadd_factor=coadd_scale_fpn(1.0, n_coadds, coadd_mode),
            note=note,
        )

    if term_name in _COUNTING_POST_CONVERSION:
        return NoiseScaling(
            term=term_name,
            correlation_class="post_conversion",
            tdi_factor=None,
            onchip_factor=None,
            offchip_factor=offchip_scale_read_noise(1.0, px_off, py_off),
            coadd_factor=coadd_scale_temporal_noise(1.0, n_coadds, coadd_mode),
            note=(
                "n_counts already reflects TDI and on-chip binning, so neither axis "
                "is applied again — a factor there would double-count"
            ),
        )

    if term_name in _READ_LIKE:
        return NoiseScaling(
            term=term_name,
            correlation_class="read_like",
            tdi_factor=tdi_scale_read_noise(1.0, n_tdi, digital=tdi_digital),
            onchip_factor=onchip_scale_read_noise(1.0),
            offchip_factor=offchip_scale_read_noise(1.0, px_off, py_off),
            coadd_factor=coadd_scale_temporal_noise(1.0, n_coadds, coadd_mode),
            note="injected once after TDI and on-chip binning",
        )

    return NoiseScaling(
        term=term_name,
        correlation_class="shot",
        tdi_factor=tdi_scale_shot_noise(1.0, n_tdi),
        onchip_factor=onchip_scale_shot_noise(1.0, mx_on, my_on),
        offchip_factor=offchip_scale_shot_noise(1.0, px_off, py_off),
        coadd_factor=coadd_scale_temporal_noise(1.0, n_coadds, coadd_mode),
    )
