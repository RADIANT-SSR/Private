r"""User-tabulated refractive-index structure constant profile $C_n^2(h)$.

One computation, one module (Rule 19): interpolation of a measured or
externally-modelled $C_n^2$ table onto arbitrary altitudes.  It is consumed
through the :class:`~radiant.atmosphere.cn2_profiles.Cn2Profile` contract by
:mod:`radiant.atmosphere.r0_path`, which owns the path integral.

Interpolation convention
------------------------
$C_n^2$ spans ten or more decades across a real profile, so a straight linear
interpolant between two nodes is dominated by the larger one and understates
the interval badly.  This module therefore interpolates **linearly in
$\log C_n^2$ against altitude** — i.e. exponential inside each interval, the
shape every analytic profile (Hufnagel-Valley, SLC, submarine-laser-com fits)
actually has.

A table is allowed to contain exact zeros (a slab with no measured
turbulence).  A log interpolant cannot span a zero, so an interval with a zero
endpoint falls back to **linear** interpolation, which is exact at both nodes
and reaches zero at the zero endpoint.  The two rules agree at every node, so
the interpolant is continuous everywhere.

Outside the table
-----------------
The table's endpoints are where the data stops.  Outside ``[h_min, h_max]``
this profile returns **zero** — RADIANT will not extrapolate a power law it
was not given.  The consumer (:mod:`radiant.atmosphere.r0_path`) compares the
integration limits against :attr:`coverage_m` and emits a ``UserWarning``
quantifying how much of the path is uncovered, so the choice is never silent
(Rule 17).

File format (loaded pre-chain per Rule 6)
-----------------------------------------
``atmosphere.cn2_tabulated_file`` names a two-column CSV,
``altitude_m,cn2_m^-2/3``, ascending in altitude, ``#`` comments allowed; see
:func:`radiant.atmosphere.loaders.build_cn2_profile`.  The parsed profile is
injected at ``stage_outputs["atmosphere_config"]["cn2_profile"]``, the same
route the atmosphere model itself takes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.core.parameters import ParameterBoundsError

__all__ = ["TabulatedCn2Profile"]


@dataclass(frozen=True)
class TabulatedCn2Profile:
    """A $C_n^2(h)$ profile defined by (altitude, $C_n^2$) samples.

    Parameters
    ----------
    altitude_m:
        Sample altitudes [m above MSL].  Must be 1-D, finite, non-negative
        and **strictly increasing**, with at least two entries.
    cn2_m23:
        Structure constant at each altitude [m^(-2/3)].  Must be the same
        length, finite and **non-negative**.
    label:
        Free-text provenance tag (file name, model name) used in
        :meth:`describe`.
    """

    altitude_m: npt.NDArray[np.float64]
    cn2_m23: npt.NDArray[np.float64]
    label: str = "tabulated"

    def __post_init__(self) -> None:
        h = np.asarray(self.altitude_m, dtype=np.float64)
        c = np.asarray(self.cn2_m23, dtype=np.float64)
        object.__setattr__(self, "altitude_m", h)
        object.__setattr__(self, "cn2_m23", c)

        if h.ndim != 1 or c.ndim != 1:
            raise ParameterBoundsError(
                what=(
                    f"TabulatedCn2Profile: altitude_m has {h.ndim} dimension(s) and "
                    f"cn2_m23 has {c.ndim}; both must be 1-D"
                ),
                why="A Cn² profile is a sequence of (altitude, Cn²) samples.",
                action="Flatten both arrays to 1-D of equal length.",
                context={"altitude_ndim": int(h.ndim), "cn2_ndim": int(c.ndim)},
            )
        if h.size != c.size:
            raise ParameterBoundsError(
                what=(
                    f"TabulatedCn2Profile: altitude_m has {h.size} entries but cn2_m23 has {c.size}"
                ),
                why="Each altitude needs exactly one Cn² sample.",
                action="Supply arrays of equal length.",
                context={"n_altitude": int(h.size), "n_cn2": int(c.size)},
            )
        if h.size < 2:
            raise ParameterBoundsError(
                what=f"TabulatedCn2Profile: only {h.size} sample(s) supplied",
                why=(
                    "A single sample defines no interval, so the path integral over "
                    "the profile is undefined."
                ),
                action="Supply at least two (altitude, Cn²) samples.",
                context={"n_samples": int(h.size)},
            )
        if not np.all(np.isfinite(h)) or not np.all(np.isfinite(c)):
            raise ParameterBoundsError(
                what="TabulatedCn2Profile: the table contains non-finite values",
                why="A NaN/inf sample propagates into the r0 path integral.",
                action="Remove or repair the offending rows.",
                context={
                    "n_bad_altitude": int(np.count_nonzero(~np.isfinite(h))),
                    "n_bad_cn2": int(np.count_nonzero(~np.isfinite(c))),
                },
            )
        if np.any(h < 0.0):
            raise ParameterBoundsError(
                what=f"TabulatedCn2Profile: minimum altitude {float(h.min())} m is negative",
                why="RADIANT altitudes are metres above mean sea level.",
                action="Set every tabulated altitude >= 0 m.",
                context={"h_min_m": float(h.min())},
            )
        if not np.all(np.diff(h) > 0.0):
            bad = int(np.argmin(np.diff(h)))
            raise ParameterBoundsError(
                what=(
                    "TabulatedCn2Profile: altitudes are not strictly increasing "
                    f"(altitude_m[{bad}] = {float(h[bad])} m, "
                    f"altitude_m[{bad + 1}] = {float(h[bad + 1])} m)"
                ),
                why=(
                    "The interpolant locates an altitude by binary search, which "
                    "requires a monotone axis; a repeated or out-of-order altitude "
                    "makes the profile ambiguous at that point."
                ),
                action="Sort the table by altitude and remove duplicate altitudes.",
                context={"index": bad, "h_lo": float(h[bad]), "h_hi": float(h[bad + 1])},
            )
        if np.any(c < 0.0):
            bad = int(np.argmin(c))
            raise ParameterBoundsError(
                what=(
                    f"TabulatedCn2Profile: cn2_m23[{bad}] = {float(c[bad])} m^(-2/3) is negative"
                ),
                why=(
                    "Cn² is the variance of refractive-index fluctuations; it cannot "
                    "be negative.  A negative entry would drive the r0 path integral "
                    "toward zero and report an implausibly good seeing."
                ),
                action="Correct the table (use 0 for a turbulence-free slab).",
                context={"index": bad, "cn2_m23": float(c[bad])},
            )

    # -- Cn2Profile contract ------------------------------------------------

    @property
    def coverage_m(self) -> tuple[float, float] | None:
        """Altitude interval the table actually covers [m]."""
        return (float(self.altitude_m[0]), float(self.altitude_m[-1]))

    @property
    def breakpoints_m(self) -> tuple[float, ...]:
        """The table altitudes — forced quadrature nodes (the interpolant kinks there)."""
        return tuple(float(x) for x in self.altitude_m)

    def cn2(self, altitude_m: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Evaluate $C_n^2$ [m^(-2/3)] at each altitude [m above MSL].

        Log-linear inside intervals whose both endpoints are positive, linear
        where an endpoint is zero, and exactly zero outside the table.
        """
        h = np.asarray(altitude_m, dtype=np.float64)
        if not np.all(np.isfinite(h)):
            raise ParameterBoundsError(
                what="TabulatedCn2Profile.cn2: altitude_m contains non-finite values",
                why="Cn² is evaluated pointwise; a NaN/inf altitude has no profile value.",
                action="Pass finite altitudes in metres above mean sea level.",
                context={"n_bad": int(np.count_nonzero(~np.isfinite(h)))},
            )

        h_tab = self.altitude_m
        c_tab = self.cn2_m23
        n = h_tab.size

        idx = np.clip(np.searchsorted(h_tab, h, side="right") - 1, 0, n - 2)
        h0 = h_tab[idx]
        h1 = h_tab[idx + 1]
        c0 = c_tab[idx]
        c1 = c_tab[idx + 1]
        t = (h - h0) / (h1 - h0)

        linear = c0 + t * (c1 - c0)
        both_positive = (c0 > 0.0) & (c1 > 0.0)
        # np.log is only evaluated on a sanitized copy so the "linear" branch
        # never triggers a divide-by-zero warning.
        c0_safe = np.where(both_positive, c0, 1.0)
        c1_safe = np.where(both_positive, c1, 1.0)
        log_interp = np.exp(np.log(c0_safe) + t * (np.log(c1_safe) - np.log(c0_safe)))

        out = np.where(both_positive, log_interp, linear)
        outside = (h < h_tab[0]) | (h > h_tab[-1])
        result: npt.NDArray[np.float64] = np.where(outside, 0.0, out)
        return result

    def describe(self) -> str:
        """One-line provenance string."""
        return (
            f"tabulated Cn² profile '{self.label}': {self.altitude_m.size} samples over "
            f"{float(self.altitude_m[0]):.0f}–{float(self.altitude_m[-1]):.0f} m MSL"
        )
