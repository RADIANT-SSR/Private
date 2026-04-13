"""Radiometric frame and noise term — chain-state value objects.

These two frozen dataclasses are the value containers that flow through
``ChainState`` (see :mod:`radiant.core.chain`). They live in
``radiant.core`` because every physics stage produces or consumes them
and the import-linter forbids cross-stage physics imports — the only
shared place is core.

``RadiometricFrame``
    A snapshot of a radiometric quantity at one named reference point
    in the chain (``"at_target"``, ``"at_aperture"``, ``"post_optics"``,
    ``"photoelectrons"``, ...). A frame holds **either** spectral
    arrays **or** an in-band scalar — never both, per CLAUDE.md Rule 8
    (spectral integration happens exactly once).

``NoiseTerm``
    A single noise contribution. Each term carries the frame in which
    it was generated (its ``origin_frame``) so a later "noise referred
    to frame X" query can propagate forward/backward by the chain
    forward factors. ``NoiseTerm.value_e`` is always non-negative —
    sigma in electrons RMS at the origin frame.

Both classes are frozen and validated at construction time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class RadiometricFrame:
    """Spectral / scalar radiometric snapshot at one reference point.

    Parameters
    ----------
    name:
        The reference-frame name (``"at_target"``, ``"at_aperture"``,
        ``"post_optics"``, ``"photoelectrons"``, ...). Free-form string;
        the chain wires it to a known set.
    wavelength_um:
        1-D ascending wavelength grid (µm). The frame is evaluated on
        this exact grid; no resampling is done downstream.
    spectral_radiance:
        Optional ``L(λ)`` in W/m²/sr/µm. Same length as ``wavelength_um``.
    spectral_irradiance:
        Optional ``E(λ)`` in W/m²/µm. Same length as ``wavelength_um``.
    photon_rate:
        Optional photon rate in photons/s/pixel/µm (or equivalent).
        Same length as ``wavelength_um``.
    in_band_value:
        Post-spectral-integration scalar (e.g., e- per pixel per
        integration). When set, the frame holds **no** spectral arrays;
        when unset, at least one spectral array must be set. This XOR
        is enforced at construction.
    in_band_unit:
        Free-form unit string for ``in_band_value`` (e.g. ``"e-"``).
    notes:
        Optional human-readable annotation.

    Notes
    -----
    Frames are immutable. They are created once by the producing stage
    and consumed read-only thereafter.
    """

    name: str
    wavelength_um: npt.NDArray[np.float64]
    spectral_radiance: npt.NDArray[np.float64] | None = None
    spectral_irradiance: npt.NDArray[np.float64] | None = None
    photon_rate: npt.NDArray[np.float64] | None = None
    in_band_value: float | None = None
    in_band_unit: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        wl = np.asarray(self.wavelength_um, dtype=np.float64)
        if wl.ndim != 1 or wl.size < 2:
            raise ValueError(
                f"RadiometricFrame '{self.name}': wavelength_um must be a 1-D "
                f"array with at least 2 samples, got shape {wl.shape}."
            )
        object.__setattr__(self, "wavelength_um", wl)

        spectral_arrays: list[tuple[str, npt.NDArray[np.float64] | None]] = [
            ("spectral_radiance", self.spectral_radiance),
            ("spectral_irradiance", self.spectral_irradiance),
            ("photon_rate", self.photon_rate),
        ]

        for field_name, arr in spectral_arrays:
            if arr is None:
                continue
            a = np.asarray(arr, dtype=np.float64)
            if a.shape != wl.shape:
                raise ValueError(
                    f"RadiometricFrame '{self.name}': {field_name} has shape "
                    f"{a.shape} but wavelength_um has shape {wl.shape}. "
                    "Spectral arrays must align with the wavelength grid."
                )
            object.__setattr__(self, field_name, a)

        any_spectral = any(arr is not None for _, arr in spectral_arrays)
        has_scalar = self.in_band_value is not None

        if any_spectral and has_scalar:
            raise ValueError(
                f"RadiometricFrame '{self.name}': cannot hold both spectral "
                "arrays and an in_band_value. Per CLAUDE.md Rule 8, spectral "
                "integration happens exactly once — a frame is either pre- "
                "or post-integration, never both."
            )
        if not any_spectral and not has_scalar:
            raise ValueError(
                f"RadiometricFrame '{self.name}': must set either at least "
                "one spectral array (spectral_radiance, spectral_irradiance, "
                "or photon_rate) or in_band_value."
            )

        if has_scalar:
            v = float(self.in_band_value)  # type: ignore[arg-type]
            if not math.isfinite(v):
                raise ValueError(
                    f"RadiometricFrame '{self.name}': in_band_value = {v} "
                    "is not finite."
                )
            object.__setattr__(self, "in_band_value", v)


@dataclass(frozen=True)
class NoiseTerm:
    """A single noise contribution at a named origin frame.

    Parameters
    ----------
    name:
        Identifier — ``"shot"``, ``"dark_shot"``, ``"read"``,
        ``"quantization"``, ...
    value_e:
        Sigma in electrons RMS at ``origin_frame``. Non-negative finite.
    origin_frame:
        Name of the :class:`RadiometricFrame` in which this noise was
        generated. Used by backward-propagation queries to refer the
        noise to other frames.
    physical_basis:
        Short tag for the physical mechanism (``"Poisson"``,
        ``"Gaussian"``, ``"ADC LSB/sqrt(12)"``, ...). Provenance only.
    contributes_to:
        Tuple of budget names this term should be summed into. Default
        ``("total",)``.
    """

    name: str
    value_e: float
    origin_frame: str
    physical_basis: str
    contributes_to: tuple[str, ...] = ("total",)

    def __post_init__(self) -> None:
        if not math.isfinite(self.value_e):
            raise ValueError(
                f"NoiseTerm '{self.name}': value_e = {self.value_e} is not "
                "finite."
            )
        if self.value_e < 0.0:
            raise ValueError(
                f"NoiseTerm '{self.name}': value_e = {self.value_e} is "
                "negative. Noise sigmas are non-negative RMS values."
            )
        if not self.origin_frame:
            raise ValueError(
                f"NoiseTerm '{self.name}': origin_frame must be a non-empty "
                "string naming the frame where this noise was generated."
            )
