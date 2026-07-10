"""Pixel geometry container.

Implements the pixel-geometry slice of
``docs/architecture/RADIANT_Detector_Complete.md`` §3.3 for the 2B.4 cut. Holds the
x/y pitch, fill factor, and (optional) charge-diffusion length.
Pixel-aperture MTF and charge-diffusion MTF are deferred to the
spatial module per the design document.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from radiant.detector.errors import DetectorValidationError


@dataclass(frozen=True)
class PixelGeometry:
    """Immutable pixel geometry descriptor.

    Parameters
    ----------
    pitch_x_m:
        Pixel pitch along the x (cross-track) axis in metres. ``> 0``.
    pitch_y_m:
        Pixel pitch along the y (along-track) axis in metres. ``> 0``.
        If equal to ``pitch_x_m``, the pixel is square.
    fill_factor:
        Dimensionless fraction of the pixel cell that is photosensitive.
        Must satisfy ``0 < fill_factor ≤ 1``. Default ``1.0``.
    charge_diffusion_length_m:
        RMS charge diffusion length in metres (``≥ 0``). Zero means no
        diffusion (the default). Only used by the spatial module for
        the charge-diffusion MTF term; does not affect the
        area/aperture calculations here.
    name:
        Optional human-readable label.
    """

    pitch_x_m: float
    pitch_y_m: float
    fill_factor: float = 1.0
    charge_diffusion_length_m: float = 0.0
    name: str = "pixel"

    def __post_init__(self) -> None:
        for attr in ("pitch_x_m", "pitch_y_m"):
            val = getattr(self, attr)
            if not math.isfinite(val) or val <= 0.0:
                raise DetectorValidationError(
                    f"PixelGeometry '{self.name}': {attr} = {val} is "
                    "invalid. Pitch must be a positive finite number in metres."
                )
        if not (0.0 < self.fill_factor <= 1.0):
            raise DetectorValidationError(
                f"PixelGeometry '{self.name}': fill_factor = {self.fill_factor} is outside (0, 1]."
            )
        if (
            not math.isfinite(self.charge_diffusion_length_m)
            or self.charge_diffusion_length_m < 0.0
        ):
            raise DetectorValidationError(
                f"PixelGeometry '{self.name}': charge_diffusion_length_m = "
                f"{self.charge_diffusion_length_m} is invalid. Must be ≥ 0."
            )

    # ------------------------------------------------------------------
    # Derived
    # ------------------------------------------------------------------

    @property
    def cell_area_m2(self) -> float:
        """Full pixel cell area ``pitch_x · pitch_y`` [m²]."""
        return self.pitch_x_m * self.pitch_y_m

    @property
    def photosensitive_area_m2(self) -> float:
        """Effective photosensitive area ``cell × fill_factor`` [m²]."""
        return self.cell_area_m2 * self.fill_factor

    @property
    def is_square(self) -> bool:
        """Whether ``pitch_x == pitch_y``."""
        return math.isclose(self.pitch_x_m, self.pitch_y_m, rel_tol=0.0, abs_tol=0.0)

    def ifov_rad(self, focal_length_m: float) -> tuple[float, float]:
        """Instantaneous field of view ``(ifov_x, ifov_y)`` [rad].

        ``IFOV = pitch / focal_length``. Raises if
        ``focal_length_m ≤ 0``.
        """
        if not math.isfinite(focal_length_m) or focal_length_m <= 0.0:
            raise DetectorValidationError(
                f"PixelGeometry '{self.name}': focal_length_m = "
                f"{focal_length_m} must be positive and finite."
            )
        return (self.pitch_x_m / focal_length_m, self.pitch_y_m / focal_length_m)

    def solid_angle_sr(self, focal_length_m: float) -> float:
        """Single-pixel solid angle ``pitch_x · pitch_y / f²`` [sr].

        Small-angle approximation appropriate for the extended-scene
        signal equation (``L(λ) · A_collect · Ω_pixel``). For large
        field angles a proper ``tan`` form would be needed, but the
        simple 2B sensor model is Nyquist-pixel accurate.
        """
        if not math.isfinite(focal_length_m) or focal_length_m <= 0.0:
            raise DetectorValidationError(
                f"PixelGeometry '{self.name}': focal_length_m = "
                f"{focal_length_m} must be positive and finite."
            )
        return self.cell_area_m2 / (focal_length_m * focal_length_m)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "name": self.name,
            "pitch_x_m": float(self.pitch_x_m),
            "pitch_y_m": float(self.pitch_y_m),
            "fill_factor": float(self.fill_factor),
            "charge_diffusion_length_m": float(self.charge_diffusion_length_m),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PixelGeometry:
        """Deserialize from a dict produced by :meth:`to_dict`."""
        return cls(
            pitch_x_m=float(d["pitch_x_m"]),
            pitch_y_m=float(d["pitch_y_m"]),
            fill_factor=float(d.get("fill_factor", 1.0)),
            charge_diffusion_length_m=float(d.get("charge_diffusion_length_m", 0.0)),
            name=str(d.get("name", "pixel")),
        )
