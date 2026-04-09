"""Quantum efficiency — parametric and tabulated.

Implements the ``CUSTOM`` and ``FILE`` QE input modes from
``docs/RADIANT_Detector_Complete.md`` §3.1 for the 2B.4 cut. The
built-in ``LIBRARY`` mode (Si, HgCdTe MWIR/LWIR, InSb, InGaAs, T2SL
curves warped by user-supplied cutoff) is deferred until the
``data/detectors/`` tables are added; see ``notes/blocked.md``.

``QuantumEfficiency`` is a small immutable container that evaluates
``QE(λ)`` on an arbitrary ascending wavelength grid. Two constructors:

- ``QuantumEfficiency.parametric(peak, cuton_um, cutoff_um, ...)`` —
  symmetric Fermi-edge response bounded above by ``peak``.
- ``QuantumEfficiency.from_spectral(data)`` — wrap a
  :class:`~radiant.core.spectral.SpectralData` table. Out-of-range
  evaluation raises rather than silently extrapolating (CLAUDE.md
  Rule 17).
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
        Tabulated QE(λ) in a :class:`SpectralData`. Values bounded in
        ``[0, 1]``, dimensionless unit.
    name:
        Human-readable identifier.
    mode:
        One of ``"parametric"`` or ``"spectral"`` — purely
        informational, stored for provenance.
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
    def parametric(
        cls,
        peak: float,
        cuton_um: float,
        cutoff_um: float,
        rolloff_um: float = 0.05,
        n_samples: int = 401,
        name: str = "qe_parametric",
    ) -> QuantumEfficiency:
        """Build a parametric Fermi-edge QE curve.

        The model has a plateau of height ``peak`` between ``cuton_um``
        and ``cutoff_um``, with symmetric Fermi roll-offs of width
        ``rolloff_um`` at each edge::

            QE(λ) = peak · σ((λ − cuton) / w) · σ((cutoff − λ) / w)

        where ``σ(x) = 1 / (1 + exp(−x))`` and ``w = rolloff_um``.

        Parameters
        ----------
        peak:
            Peak QE value, ``0 < peak ≤ 1``.
        cuton_um, cutoff_um:
            Short and long wavelength edges of the plateau (µm).
            ``cuton_um < cutoff_um``; both ``> 0``.
        rolloff_um:
            Fermi-edge roll-off width (µm), ``> 0``. Default 0.05 µm.
        n_samples:
            Number of wavelength samples (≥ 16). Default 401.
        name:
            Optional human-readable label.
        """
        if not (0.0 < peak <= 1.0):
            raise ValueError(f"QuantumEfficiency.parametric: peak = {peak} must be in (0, 1].")
        if cuton_um <= 0.0 or cutoff_um <= 0.0:
            raise ValueError(
                f"QuantumEfficiency.parametric: cuton_um = {cuton_um} and "
                f"cutoff_um = {cutoff_um} must be positive."
            )
        if cuton_um >= cutoff_um:
            raise ValueError(
                f"QuantumEfficiency.parametric: cuton_um ({cuton_um}) must "
                f"be strictly less than cutoff_um ({cutoff_um})."
            )
        if rolloff_um <= 0.0:
            raise ValueError(
                f"QuantumEfficiency.parametric: rolloff_um = {rolloff_um} must be positive."
            )
        if n_samples < 16:
            raise ValueError(
                f"QuantumEfficiency.parametric: n_samples = {n_samples} is "
                "too small; use ≥ 16 to resolve the Fermi edges."
            )

        pad = 8.0 * rolloff_um
        lam = np.linspace(max(1e-6, cuton_um - pad), cutoff_um + pad, int(n_samples))
        short_edge = 1.0 / (1.0 + np.exp(-(lam - cuton_um) / rolloff_um))
        long_edge = 1.0 / (1.0 + np.exp(-(cutoff_um - lam) / rolloff_um))
        qe = peak * short_edge * long_edge
        # Numerical floor: the tails are ~0 but clamp to non-negative.
        qe = np.clip(qe, 0.0, 1.0)

        table = SpectralData(
            name=name,
            wavelength_um=lam,
            values=qe,
            unit="",
            source=(
                f"QuantumEfficiency.parametric(peak={peak}, cuton_um={cuton_um}, "
                f"cutoff_um={cutoff_um}, rolloff_um={rolloff_um})"
            ),
            source_parameters={
                "peak": float(peak),
                "cuton_um": float(cuton_um),
                "cutoff_um": float(cutoff_um),
                "rolloff_um": float(rolloff_um),
            },
        )
        return cls(table=table, name=name, mode="parametric")

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
