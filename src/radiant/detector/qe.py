"""Quantum efficiency — scalar and tabulated.

RADIANT specifies detector QE in one of two ways:

- ``QuantumEfficiency.constant(value)`` — a single scalar ``QE ∈ (0, 1]``
  that applies uniformly across the band.
- ``QuantumEfficiency.from_spectral(data)`` — a tabulated ``QE(λ)`` curve
  wrapped around an existing :class:`~radiant.core.spectral.SpectralData`
  table. Out-of-range evaluation raises rather than silently
  extrapolating (CLAUDE.md Rule 17).

``QuantumEfficiency`` is a small immutable container that evaluates
``QE(λ)`` on an arbitrary ascending wavelength grid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from radiant.core.spectral import SpectralData


@dataclass(frozen=True)
class QuantumEfficiency:
    """Wavelength-dependent quantum efficiency ``QE(λ)``.

    QE is bounded in ``[0, 1]`` — a photon either generates an electron
    or it does not. RADIANT treats ``QE > 1`` as a configuration error
    rather than allowing it as a stand-in for avalanche gain (gain
    lives elsewhere in the readout chain).

    Use one of the two factory classmethods; direct construction is
    only for internal state composition.

    Parameters
    ----------
    table:
        Tabulated ``QE(λ)`` in a :class:`SpectralData`. Values bounded
        in ``[0, 1]``, dimensionless unit. For a scalar QE this is a
        two-point flat table spanning a wide wavelength interval.
    name:
        Human-readable identifier.
    mode:
        One of ``"constant"`` or ``"spectral"`` — purely informational,
        stored for provenance.
    """

    table: SpectralData
    name: str = "qe"
    mode: str = "spectral"
    _tag: str = field(default="qe", init=False, repr=False)

    def __post_init__(self) -> None:
        vals = self.table.values
        if vals.ndim != 1 or vals.size < 2:
            raise ValueError(
                f"QuantumEfficiency '{self.name}': table must be 1-D with at "
                f"least 2 samples, got shape {vals.shape}."
            )
        if np.any(vals < 0.0) or np.any(vals > 1.0):
            raise ValueError(
                f"QuantumEfficiency '{self.name}': values out of [0, 1] "
                f"(min={float(vals.min()):g}, max={float(vals.max()):g}). QE "
                "is a dimensionless fraction — photodetector gain lives in "
                "the readout chain, not in QE."
            )

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def constant(
        cls,
        value: float,
        lam_min_um: float = 0.1,
        lam_max_um: float = 30.0,
        name: str = "qe_constant",
    ) -> QuantumEfficiency:
        """Build a flat (wavelength-independent) QE of magnitude ``value``.

        The result is a two-point :class:`SpectralData` table spanning
        ``[lam_min_um, lam_max_um]`` with both samples set to ``value``.
        The span is deliberately wide (0.1–30 µm by default) so that
        any reasonable evaluation grid falls inside the table without
        tripping the out-of-range check in :meth:`evaluate`.

        Parameters
        ----------
        value:
            Scalar QE, ``0 < value ≤ 1``.
        lam_min_um, lam_max_um:
            Wavelength span of the stored table (µm). Both ``> 0``,
            with ``lam_min_um < lam_max_um``. Defaults span 0.1–30 µm.
        name:
            Optional human-readable label.
        """
        if not (0.0 < value <= 1.0):
            raise ValueError(f"QuantumEfficiency.constant: value = {value} must be in (0, 1].")
        if lam_min_um <= 0.0 or lam_max_um <= 0.0:
            raise ValueError(
                f"QuantumEfficiency.constant: lam_min_um = {lam_min_um} and "
                f"lam_max_um = {lam_max_um} must be positive."
            )
        if lam_min_um >= lam_max_um:
            raise ValueError(
                f"QuantumEfficiency.constant: lam_min_um ({lam_min_um}) must "
                f"be strictly less than lam_max_um ({lam_max_um})."
            )

        lam = np.array([float(lam_min_um), float(lam_max_um)], dtype=np.float64)
        vals = np.array([float(value), float(value)], dtype=np.float64)
        table = SpectralData(
            name=name,
            wavelength_um=lam,
            values=vals,
            unit="",
            source=f"QuantumEfficiency.constant(value={value})",
            source_parameters={
                "value": float(value),
                "lam_min_um": float(lam_min_um),
                "lam_max_um": float(lam_max_um),
            },
        )
        return cls(table=table, name=name, mode="constant")

    @classmethod
    def from_spectral(cls, data: SpectralData, name: str | None = None) -> QuantumEfficiency:
        """Wrap an existing :class:`SpectralData` QE table."""
        return cls(
            table=data,
            name=name if name is not None else data.name,
            mode="spectral",
        )

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, wavelength_um: np.ndarray) -> np.ndarray:
        """Interpolate ``QE(λ)`` onto ``wavelength_um``.

        Linear interpolation. Out-of-range grids raise — QE is a
        measured material property and extrapolation would be a
        silent failure per CLAUDE.md Rule 17.
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)
        if lam.ndim != 1 or lam.size < 1:
            raise ValueError(
                f"QuantumEfficiency '{self.name}': wavelength_um must be a "
                f"non-empty 1-D array, got shape {lam.shape}."
            )
        src_lam = self.table.wavelength_um
        if lam[0] < src_lam[0] - 1e-12 or lam[-1] > src_lam[-1] + 1e-12:
            raise ValueError(
                f"QuantumEfficiency '{self.name}': requested range "
                f"[{float(lam[0]):.4f}, {float(lam[-1]):.4f}] µm extends "
                f"outside the QE table range "
                f"[{float(src_lam[0]):.4f}, {float(src_lam[-1]):.4f}] µm. "
                "Extend the QE table or trim the evaluation grid."
            )
        return np.asarray(np.interp(lam, src_lam, self.table.values), dtype=np.float64)

    # ------------------------------------------------------------------
    # Derived quantities
    # ------------------------------------------------------------------

    @property
    def peak_qe(self) -> float:
        """Maximum of the stored QE curve."""
        return float(self.table.values.max())

    def band_averaged_qe(self, lam_min_um: float, lam_max_um: float) -> float:
        """Simple trapezoidal band-averaged QE over ``[lam_min, lam_max]``.

        Useful as a scalar figure of merit when computing an electron
        rate under an extended broadband source where the exact
        spectral integral is not needed.
        """
        if lam_max_um <= lam_min_um:
            raise ValueError(
                f"band_averaged_qe: lam_max_um ({lam_max_um}) must be > lam_min_um ({lam_min_um})."
            )
        grid = np.linspace(lam_min_um, lam_max_um, 257)
        vals = self.evaluate(grid)
        numerator = float(np.trapezoid(vals, grid))
        return numerator / (lam_max_um - lam_min_um)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "name": self.name,
            "mode": self.mode,
            "table": self.table.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> QuantumEfficiency:
        """Deserialize from a dict produced by :meth:`to_dict`."""
        return cls(
            table=SpectralData.from_dict(d["table"]),
            name=str(d.get("name", "qe")),
            mode=str(d.get("mode", "spectral")),
        )


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def photon_energy_joules(wavelength_um: np.ndarray) -> np.ndarray:
    """Return the photon energy ``E = h·c / λ`` [J] for each wavelength.

    Centralised here so the shot-noise and signal-rate code does not
    have to re-derive the ``h·c / λ`` factor every time.
    """
    from radiant.core.constants import hc

    lam_m = np.asarray(wavelength_um, dtype=np.float64) * 1.0e-6
    if np.any(lam_m <= 0.0):
        raise ValueError(
            f"photon_energy_joules: wavelength_um contains non-positive "
            f"entries (min={float(np.asarray(wavelength_um).min())} µm)."
        )
    return np.asarray(hc / lam_m, dtype=np.float64)
