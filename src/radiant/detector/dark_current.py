"""Dark-current model.

Implements noise term #5 ("dark_shot") from
``docs/architecture/RADIANT_Detector_Complete.md`` §4 in its minimum form: a
constant dark rate ``J_dark`` [e⁻/s/pixel] with Poisson statistics.
The optional Arrhenius temperature scaling is exposed as a helper so
cooled-IR users can propagate a measured ``J(T_ref)`` to a different
operating temperature without re-running MODTRAN-style tools.

``dark_signal_e = J_dark · t_int`` per pixel
``dark_shot_e   = √(J_dark · t_int)``
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from radiant.core.constants import k_B
from radiant.detector.errors import DetectorValidationError


@dataclass(frozen=True)
class DarkCurrent:
    """Constant-rate dark current with optional Arrhenius scaling.

    Parameters
    ----------
    rate_e_per_s:
        Dark generation rate in electrons per second per pixel at
        ``reference_temperature_K``. Must be ``≥ 0``.
    reference_temperature_K:
        The temperature at which ``rate_e_per_s`` was measured.
        Defaults to 300 K ("room temperature" for an uncooled sensor).
        Must be ``> 0``.
    activation_energy_eV:
        Arrhenius activation energy in electron-volts used by
        :meth:`at_temperature`. ``0`` means "no temperature scaling"
        (recommended when the user already has J(T) at the operating
        temperature). Default ``0.0``.
    name:
        Optional human-readable label.
    """

    rate_e_per_s: float
    reference_temperature_K: float = 300.0
    activation_energy_eV: float = 0.0
    name: str = "dark_current"

    def __post_init__(self) -> None:
        if not math.isfinite(self.rate_e_per_s) or self.rate_e_per_s < 0.0:
            raise DetectorValidationError(
                f"DarkCurrent '{self.name}': rate_e_per_s = "
                f"{self.rate_e_per_s} is invalid. Dark rate is a "
                "non-negative electron count per second per pixel."
            )
        if not math.isfinite(self.reference_temperature_K) or self.reference_temperature_K <= 0.0:
            raise DetectorValidationError(
                f"DarkCurrent '{self.name}': reference_temperature_K = "
                f"{self.reference_temperature_K} K must be > 0."
            )
        if not math.isfinite(self.activation_energy_eV) or self.activation_energy_eV < 0.0:
            raise DetectorValidationError(
                f"DarkCurrent '{self.name}': activation_energy_eV = "
                f"{self.activation_energy_eV} must be ≥ 0."
            )

    # ------------------------------------------------------------------
    # Derived quantities
    # ------------------------------------------------------------------

    def electrons_accumulated(self, integration_time_s: float) -> float:
        """Dark electrons accumulated over ``integration_time_s`` [e⁻]."""
        if not math.isfinite(integration_time_s) or integration_time_s < 0.0:
            raise DetectorValidationError(
                f"DarkCurrent '{self.name}': integration_time_s = "
                f"{integration_time_s} is invalid. Must be a non-negative "
                "finite number in seconds."
            )
        return self.rate_e_per_s * integration_time_s

    def shot_noise_e(self, integration_time_s: float) -> float:
        """Dark-shot noise RMS after ``integration_time_s`` [e⁻]."""
        return math.sqrt(self.electrons_accumulated(integration_time_s))

    def at_temperature(self, temperature_K: float) -> DarkCurrent:
        """Return a new :class:`DarkCurrent` scaled to ``temperature_K``.

        If ``activation_energy_eV`` is zero the returned object is a
        straight copy — the caller is telling us the rate is
        independent of temperature for their purposes. Otherwise the
        standard Arrhenius form is applied::

            J(T) = J(T_ref) · exp(−Eₐ · (1/(kT) − 1/(kT_ref)) )

        Note the **negative** exponent on the inner bracket: higher
        ``T`` means higher dark rate (``kT > 0`` always), which is the
        physics for thermally activated carrier generation in a
        semiconductor.
        """
        if not math.isfinite(temperature_K) or temperature_K <= 0.0:
            raise DetectorValidationError(
                f"DarkCurrent '{self.name}': temperature_K = {temperature_K} K must be > 0."
            )
        if self.activation_energy_eV == 0.0:
            return DarkCurrent(
                rate_e_per_s=self.rate_e_per_s,
                reference_temperature_K=temperature_K,
                activation_energy_eV=0.0,
                name=self.name,
            )
        # Activation energy eV → J: multiply by the elementary charge.
        # Keep dependency on constants.py rather than hardcoding q.
        from radiant.core.constants import q

        ea_joules = self.activation_energy_eV * q
        factor = math.exp(
            -ea_joules / k_B * (1.0 / temperature_K - 1.0 / self.reference_temperature_K)
        )
        return DarkCurrent(
            rate_e_per_s=self.rate_e_per_s * factor,
            reference_temperature_K=temperature_K,
            activation_energy_eV=self.activation_energy_eV,
            name=self.name,
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "name": self.name,
            "rate_e_per_s": float(self.rate_e_per_s),
            "reference_temperature_K": float(self.reference_temperature_K),
            "activation_energy_eV": float(self.activation_energy_eV),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DarkCurrent:
        """Deserialize from a dict produced by :meth:`to_dict`."""
        return cls(
            rate_e_per_s=float(d["rate_e_per_s"]),
            reference_temperature_K=float(d.get("reference_temperature_K", 300.0)),
            activation_energy_eV=float(d.get("activation_energy_eV", 0.0)),
            name=str(d.get("name", "dark_current")),
        )
