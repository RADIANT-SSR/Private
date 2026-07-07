"""ADC quantization (minimum form).

Implements the quantization-only slice of noise term #11
("quantization_noise") from ``docs/architecture/RADIANT_Detector_Complete.md`` §4
for the 2B.4 cut::

    σ_quant = LSB / √12   [e⁻ RMS]

where ``LSB = gain_e_per_dn`` (one least-significant bit in electrons).
Gain computation, two-stage saturation, and nonlinearity are deferred
to later tasks.

The ``√12`` factor is the RMS of a uniform distribution on ``[−LSB/2,
+LSB/2]`` — the standard result for quantization noise under the
"LSB much smaller than the signal variance" assumption.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

# Pre-computed for clarity and to keep the √12 out of every call site.
_SQRT_12: float = math.sqrt(12.0)


@dataclass(frozen=True)
class AnalogToDigital:
    """ADC configuration (gain + bit depth).

    Parameters
    ----------
    gain_e_per_dn:
        System conversion gain in electrons per digital number. One
        LSB corresponds to ``gain_e_per_dn`` electrons at the sense
        node. Must be ``> 0``.
    n_bits:
        ADC bit depth (integer, ``≥ 1``). Drives the maximum digital
        count ``2ⁿ − 1`` and, together with the gain, the analog
        full-scale that the ADC can represent.
    name:
        Optional human-readable label.
    """

    gain_e_per_dn: float
    n_bits: int = 16
    name: str = "adc"

    def __post_init__(self) -> None:
        if not math.isfinite(self.gain_e_per_dn) or self.gain_e_per_dn <= 0.0:
            raise ValueError(
                f"AnalogToDigital '{self.name}': gain_e_per_dn = "
                f"{self.gain_e_per_dn} is invalid. Must be a positive "
                "finite number of electrons per DN."
            )
        if not isinstance(self.n_bits, int) or self.n_bits < 1:
            raise ValueError(
                f"AnalogToDigital '{self.name}': n_bits = {self.n_bits} must be a positive integer."
            )

    # ------------------------------------------------------------------
    # Derived quantities
    # ------------------------------------------------------------------

    @property
    def max_dn(self) -> int:
        """Maximum digital number (``2ⁿ − 1``)."""
        return (1 << self.n_bits) - 1

    @property
    def full_scale_e(self) -> float:
        """Analog full-scale in electrons (``max_dn · gain_e_per_dn``)."""
        return self.max_dn * self.gain_e_per_dn

    def quantization_noise_e(self) -> float:
        """Quantization noise ``LSB / √12`` [e⁻ RMS]."""
        return self.gain_e_per_dn / _SQRT_12

    def e_to_dn(self, electrons: float) -> float:
        """Convert an analog electron count to a digital number (clipped).

        Parameters
        ----------
        electrons:
            Non-negative electron count to digitize. Must be finite.

        Returns
        -------
        float
            ``min(electrons / gain, max_dn)`` — saturation at the ADC
            ceiling is a hard clip. The caller can detect clipping by
            comparing to :attr:`max_dn`.
        """
        if not math.isfinite(electrons) or electrons < 0.0:
            raise ValueError(
                f"AnalogToDigital '{self.name}': electrons = {electrons} is "
                "invalid. The caller must resolve NaN/inf and sign errors "
                "before quantising."
            )
        dn = electrons / self.gain_e_per_dn
        return min(dn, float(self.max_dn))

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "name": self.name,
            "gain_e_per_dn": float(self.gain_e_per_dn),
            "n_bits": int(self.n_bits),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AnalogToDigital:
        """Deserialize from a dict produced by :meth:`to_dict`."""
        return cls(
            gain_e_per_dn=float(d["gain_e_per_dn"]),
            n_bits=int(d.get("n_bits", 16)),
            name=str(d.get("name", "adc")),
        )
