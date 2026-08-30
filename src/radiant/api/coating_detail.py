"""Single-element coating detail figure — native-grid assembly (Gap 116).

The all-element overlay (``ResultPlotNamespace.coating_spectra``) draws every
element resampled onto the active run's chain grid, on one fixed [0, 1] axis —
correct for "what did the chain use", but structurally unable to show a single
coating's model: the run grid clips the curve to the evaluation band and the
shared axis flattens percent-level dispersion.

:func:`plot_coating_detail` is the inspection view: **one** element from the
sensor's attached ADR-0009 element document, its R/T/ε curves on their
**native source grid** (spectral file / inline table full extent), one
autoscaled panel per quantity, with the evaluation band shaded for context.
Scalar-valued properties have no native grid and are drawn flat across the
evaluation band instead.

One computation, one module (Rule 19): this module owns the document-to-curves
assembly; the figure rendering lives with every other renderer in
:mod:`radiant.api.plot` (:func:`~radiant.api.plot.plot_element_coating`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

from radiant.api.errors import ApiValidationError
from radiant.io.element_config import parse_element_entries
from radiant.optics.errors import OpticsValidationError

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from radiant.api.sensor import Sensor

#: Points used to draw a scalar (grid-less) property across the evaluation band.
_FALLBACK_POINTS = 2


def plot_coating_detail(
    sensor: Sensor,
    element_name: str,
    *,
    entries: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> Figure:
    """Plot one element's coating model (R/T/ε) on its native source grid.

    Parameters
    ----------
    sensor:
        The sensor whose element document and evaluation band to read. The
        band (``spectral_integration.filter_min_um`` / ``filter_max_um``,
        resolved [µm]) is shaded on the figure and is the drawing span for
        scalar-valued properties.
    element_name:
        The ``name`` field of one document entry.
    entries:
        Optional document override — the same entry dicts
        ``Sensor.optical_elements()`` returns. The GUI element editor passes
        its in-progress (possibly unapplied) table here so a draft row can be
        inspected before Apply; scripting callers normally omit it and the
        sensor's attached document is read.
    **kwargs:
        Passed to ``ax.plot()`` for every curve.

    Returns
    -------
    Figure
        A matplotlib Figure, one autoscaled panel per non-zero quantity.

    Raises
    ------
    ApiValidationError
        When no element document is available or *element_name* is not in it.
    radiant.io.element_config.ElementConfigError
        When the entry itself is invalid (the io parser is the single
        validation authority; its errors are already actionable).
    """
    from radiant.api.plot import plot_element_coating

    document = entries if entries is not None else sensor.optical_elements()
    if not document:
        raise ApiValidationError(
            "No optical element document is attached to this sensor — "
            "coating detail reads the declarative ADR-0009 document. Attach "
            "one with Sensor.set_optical_elements(...) (or the GUI Elements "
            "tab) first."
        )
    matches = [e for e in document if e.get("name") == element_name]
    if not matches:
        names = ", ".join(repr(e.get("name", "<unnamed>")) for e in document)
        raise ApiValidationError(
            f"No element named {element_name!r} in the document — available elements: {names}."
        )

    lam_min = float(sensor.get("spectral_integration.filter_min_um"))
    lam_max = float(sensor.get("spectral_integration.filter_max_um"))

    entry = matches[0]
    try:
        # Native-grid parse: spectral properties (files / inline tables) keep
        # their full stored extent. Raises only when a property is a scalar,
        # which has no grid of its own.
        element = parse_element_entries([entry], None, source_label="plot_coating_detail")[0]
        native = True
    except OpticsValidationError:
        # At least one property is scalar-valued — broadcast onto the
        # evaluation band, and say so in the figure subtitle.
        grid = np.linspace(lam_min, lam_max, _FALLBACK_POINTS)
        element = parse_element_entries([entry], grid, source_label="plot_coating_detail")[0]
        native = False

    series: dict[str, tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]] = {}
    for symbol, curve in (
        ("R", element.reflectance),
        ("T", element.transmittance),
        ("ε", element.emissivity),
    ):
        # Same convention as the overlay plot: an identically-zero curve
        # carries no coating information (a mirror has T ≡ 0, a simple
        # refractive ε ≡ 0) and would only add a dead panel.
        if not np.any(curve.values):
            continue
        series[symbol] = (curve.wavelength_um, curve.values)
    if not series:
        raise ApiValidationError(
            f"Element {element_name!r} carries no non-zero coating spectra "
            "to plot (all R/T/ε curves are identically zero)."
        )
    return plot_element_coating(
        series,
        element_name=element_name,
        eval_span_um=(lam_min, lam_max),
        native_grid=native,
        **kwargs,
    )
