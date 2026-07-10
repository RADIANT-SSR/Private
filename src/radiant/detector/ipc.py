"""Inter-pixel capacitance (IPC) kernel and MTF.

IPC is an electrical coupling between adjacent pixels in the detector
readout that spreads signal from a pixel to its neighbours. It is
modelled as a 3×3 convolution kernel:

    [[0,   α, 0],
     [α, 1-4α, α],
     [0,   α, 0]]

where α is the nearest-neighbour coupling fraction (typically 0.01–0.05).

The MTF of this kernel is computed via FFT. For the symmetric 4-neighbour
case, the analytic form is:

    MTF_IPC(fx, fy) = (1 - 4α) + 2α·cos(2π·fx·p) + 2α·cos(2π·fy·p)

where p is the pixel pitch and f is spatial frequency.

See RADIANT_Detector_Complete.md §11.10 and RADIANT_Spatial_Complete.md §9.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from radiant.detector.errors import DetectorValidationError


def ipc_kernel(coupling: float) -> npt.NDArray[np.float64]:
    """Generate a 3×3 IPC kernel.

    Parameters
    ----------
    coupling:
        Nearest-neighbour coupling fraction α. Must be in [0, 0.25).

    Returns
    -------
    ndarray of shape (3, 3)
        Normalised IPC kernel (sums to 1.0).

    Raises
    ------
    ValueError
        If coupling is out of bounds.
    """
    if not (0.0 <= coupling < 0.25):
        raise DetectorValidationError(f"IPC coupling must be in [0, 0.25), got {coupling}")

    kernel = np.zeros((3, 3), dtype=np.float64)
    kernel[1, 1] = 1.0 - 4.0 * coupling
    kernel[0, 1] = coupling
    kernel[2, 1] = coupling
    kernel[1, 0] = coupling
    kernel[1, 2] = coupling

    return kernel


def ipc_mtf_analytic(
    freq_x: npt.NDArray[np.float64],
    freq_y: npt.NDArray[np.float64],
    coupling: float,
    pixel_pitch_m: float,
) -> npt.NDArray[np.float64]:
    """Compute the 2-D IPC MTF analytically.

    For the symmetric 4-neighbour kernel:
        MTF(fx, fy) = (1-4α) + 2α·cos(2π·fx·p) + 2α·cos(2π·fy·p)

    Parameters
    ----------
    freq_x:
        Spatial frequencies in x [cycles/m]. Can be 1-D or 2-D meshgrid.
    freq_y:
        Spatial frequencies in y [cycles/m]. Same shape as freq_x.
    coupling:
        Nearest-neighbour coupling fraction α.
    pixel_pitch_m:
        Pixel pitch [m].

    Returns
    -------
    ndarray
        MTF values (same shape as freq_x).
    """
    if coupling < 0.0 or coupling >= 0.25:
        raise DetectorValidationError(f"IPC coupling must be in [0, 0.25), got {coupling}")
    if pixel_pitch_m <= 0.0:
        raise DetectorValidationError(f"pixel_pitch_m must be positive, got {pixel_pitch_m}")

    if coupling == 0.0:
        return np.ones_like(freq_x)

    return (
        (1.0 - 4.0 * coupling)
        + 2.0 * coupling * np.cos(2.0 * math.pi * freq_x * pixel_pitch_m)
        + 2.0 * coupling * np.cos(2.0 * math.pi * freq_y * pixel_pitch_m)
    )


def ipc_mtf_1d(
    freq: npt.NDArray[np.float64],
    coupling: float,
    pixel_pitch_m: float,
    axis: str = "x",
) -> npt.NDArray[np.float64]:
    """Compute the 1-D IPC MTF along one axis.

    Evaluates the 2-D MTF with the other axis frequency set to zero.

    Parameters
    ----------
    freq:
        Spatial frequencies [cycles/m].
    coupling:
        Nearest-neighbour coupling fraction α.
    pixel_pitch_m:
        Pixel pitch [m].
    axis:
        ``"x"`` or ``"y"``.

    Returns
    -------
    ndarray
        MTF values at the given frequencies.
    """
    zero = np.zeros_like(freq)
    if axis == "x":
        return ipc_mtf_analytic(freq, zero, coupling, pixel_pitch_m)
    if axis == "y":
        return ipc_mtf_analytic(zero, freq, coupling, pixel_pitch_m)
    raise DetectorValidationError(f"axis must be 'x' or 'y', got {axis!r}")
