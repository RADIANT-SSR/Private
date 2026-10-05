"""Substrate absorption figure — alpha(lambda) and n(lambda) on a log axis (Gap 142 §9).

An analyst choosing a substrate is choosing an **absorption spectrum**, and that is the
one property of the library they cannot read off the name. Germanium's alpha spans a
factor 8 across its window; calcium fluoride's rises **4500x** between 2.7 and 10.6 µm,
climbing its multiphonon edge. On a linear axis that is not a curve, it is a flat line
with a wall at one end: the whole transparent region collapses onto zero. So the alpha
panel defaults to a **log y axis**, and the caller may override it only deliberately.

The second panel carries n(lambda) on a linear axis, because n is a percent-level
variation and a log axis would flatten *it*.

The evaluation band is shaded against the material's **whole published window**, which
is the comparison that matters at the moment of choosing: a material whose window does
not cover the band is refused by the library rather than extrapolated, and seeing the
band sit near an edge is the warning that no error message will give you.

One computation, one module (Rule 19): this module owns the library-to-curves assembly
and its own figure, because the substrate is not an element — it has no entry in the
element document and no R/T/eps — so it does not belong in
:mod:`radiant.api.coating_detail`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from radiant.api.errors import ApiValidationError
from radiant.api.substrate import substrate_label
from radiant.data.substrate import SubstrateError, SubstrateLibrary

if TYPE_CHECKING:
    from matplotlib.figure import Figure

__all__ = ["plot_substrate_absorption"]

#: alpha below this is treated as the floor of the published data rather than a value
#: to put on a log axis. A published alpha can legitimately be ~1e-5 cm^-1, but an
#: exact zero is a table artefact (a transparency-window null), not a measurement.
_ALPHA_FLOOR_PER_M: float = 1.0e-9


def plot_substrate_absorption(
    name: str,
    *,
    band_um: tuple[float, float] | None = None,
    log_alpha: bool = True,
    library: SubstrateLibrary | None = None,
    **kwargs: Any,
) -> Figure:
    """Plot one library substrate's ``alpha(lambda)`` and ``n(lambda)``.

    Parameters
    ----------
    name:
        Canonical substrate name or a declared alias (``"germanium"``, ``"Ge"``).
    band_um:
        Evaluation band to shade, ``(min, max)`` [µm]. Omitted, nothing is shaded.
    log_alpha:
        Log y axis on the alpha panel (default). ``False`` only when a caller has a
        reason — on a linear axis a transparency window reads as identically zero.
    library:
        Override library, for tests.
    **kwargs:
        Passed to ``ax.plot()`` for both curves.

    Returns
    -------
    Figure
        Two stacked panels: alpha [1/m] over n [-], sharing the wavelength axis.

    Raises
    ------
    ApiValidationError
        If no substrate of that name exists, or matplotlib is not installed.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - exercised only without matplotlib
        raise ApiValidationError(
            "plotting requires matplotlib. Install it with: pip install matplotlib"
        ) from exc

    try:
        material = (library or SubstrateLibrary()).material(name)
    except SubstrateError as exc:
        raise ApiValidationError(str(exc)) from exc

    wavelength = np.asarray(material.wavelength_um, dtype=np.float64)
    alpha = np.maximum(np.asarray(material.alpha_per_m, dtype=np.float64), _ALPHA_FLOOR_PER_M)
    n_refr = np.asarray(material.n_refr, dtype=np.float64)

    figure, (ax_alpha, ax_n) = plt.subplots(2, 1, sharex=True, figsize=(7.0, 5.2))
    ax_alpha.plot(wavelength, alpha, **kwargs)
    if log_alpha:
        ax_alpha.set_yscale("log")
    ax_alpha.set_ylabel("α [1/m]")
    ax_alpha.grid(True, which="both", alpha=0.3)

    ax_n.plot(wavelength, n_refr, **kwargs)
    ax_n.set_ylabel("n [-]")
    ax_n.set_xlabel("wavelength [µm]")
    ax_n.grid(True, alpha=0.3)

    if band_um is not None:
        low, high = float(band_um[0]), float(band_um[1])
        for axis in (ax_alpha, ax_n):
            axis.axvspan(low, high, alpha=0.15, zorder=0)

    tier_note = "class-typical α" if material.tier.upper() == "B" else "measured anchors"
    subtitle = (
        f"window {material.window_um[0]:g}–{material.window_um[1]:g} µm · "
        f"α at {material.reference_temperature_K:g} K · tier {material.tier} ({tier_note})"
    )
    label = substrate_label(
        display_name=material.display_name, name=material.name, formula=material.formula
    )
    ax_alpha.set_title(f"{label} — {subtitle}", fontsize=10)
    figure.tight_layout()
    return figure
