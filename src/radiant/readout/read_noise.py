"""Read noise — Gaussian 1σ stub.

Implements the minimum form of noise term #9 ("read_noise") from
``docs/RADIANT_Detector_Complete.md`` §4: a single per-pixel read
noise in electrons RMS. The full readout noise model (kTC, flicker,
CDS interaction, post-CDS scaling) is deferred to later tasks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReadNoise:
    """Per-read Gaussian read noise ``σ_read`` [e⁻ RMS].

    The stored value is always the *effective per-frame* read noise
    delivered to the signal path. The CDS convention
    (``read_noise_is_post_cds`` in the full design) is deferred to the
    readout-chain task; this 2B.4 stub accepts a single scalar.

    Parameters
    ----------
    sigma_e_rms:
        Read noise in electrons RMS. Must be ``≥ 0``.
    name:
        Optional human-readable label.
    """

    sigma_e_rms: float
    name: str = "read_noise"

    def __post_init__(self) -> None:
        if not math.isfinite(self.sigma_e_rms) or self.sigma_e_rms < 0.0:
            raise ValueError(
                f"ReadNoise '{self.name}': sigma_e_rms = {self.sigma_e_rms} "
                "is invalid. Read noise is a non-negative Gaussian RMS."
            )

    def contribution_e(self) -> float:
        """Return the per-pixel read-noise contribution [e⁻ RMS]."""
        return float(self.sigma_e_rms)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {"name": self.name, "sigma_e_rms": float(self.sigma_e_rms)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReadNoise:
        """Deserialize from a dict produced by :meth:`to_dict`."""
        return cls(
            sigma_e_rms=float(d["sigma_e_rms"]),
            name=str(d.get("name", "read_noise")),
        )
