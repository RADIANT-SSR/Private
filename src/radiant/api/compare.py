"""Compare a predicted MTF curve against measured data (Gap 30).

:func:`compare_mtf` interpolates the RADIANT-predicted MTF (PSF-path
curves stored in ``result.stage_outputs["performance"]``, cycles/m on
the focal plane) onto the frequency points of a
:class:`~radiant.io.measurement.MeasuredCurve` and reports residual
statistics. Measured frequencies may be in any unit supported by
:func:`radiant.performance.frequency_units.convert_spatial_frequency`
(``cy/m``, ``cy/mm``, ``cy/mrad``, ``cy/pixel``).

Measured points outside the predicted frequency grid are excluded (no
extrapolation — extrapolated MTF is not physics) and counted in
``MtfComparisonResult.n_excluded``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.core.exceptions import RadiantError
from radiant.io.measurement import MeasuredCurve
from radiant.io.results import ChainResult
from radiant.performance.frequency_units import (
    FrequencyUnit,
    convert_spatial_frequency,
)

__all__ = ["MtfComparisonError", "MtfComparisonResult", "compare_mtf"]


class MtfComparisonError(RadiantError):
    """Raised when a measured-vs-predicted MTF comparison cannot be made."""


@dataclass(frozen=True)
class MtfComparisonResult:
    """Residuals between measured MTF points and the predicted curve.

    All frequencies are in cycles/m on the focal plane; MTF values and
    residuals are dimensionless (modulation, 0–1).

    Attributes
    ----------
    freq_cy_m:
        Measured frequency points that fall inside the predicted grid
        [cycles/m], ascending.
    measured:
        Measured MTF at those points [dimensionless].
    predicted:
        Predicted MTF interpolated onto those points [dimensionless].
    residual:
        ``measured − predicted`` [dimensionless].
    rms_residual:
        Root-mean-square of ``residual`` [dimensionless].
    max_abs_residual:
        Largest ``|residual|`` [dimensionless].
    n_compared:
        Number of measured points used.
    n_excluded:
        Number of measured points outside the predicted frequency grid
        (excluded, never extrapolated).
    """

    freq_cy_m: npt.NDArray[np.float64]
    measured: npt.NDArray[np.float64]
    predicted: npt.NDArray[np.float64]
    residual: npt.NDArray[np.float64]
    rms_residual: float
    max_abs_residual: float
    n_compared: int
    n_excluded: int

    def table(self, max_rows: int = 20) -> str:
        """Formatted text summary of the comparison.

        Parameters
        ----------
        max_rows:
            Maximum number of per-point rows to print; the middle of
            the curve is elided beyond that.
        """
        lines = [
            "MTF comparison — measured vs predicted",
            f"  points compared : {self.n_compared}",
            f"  points excluded : {self.n_excluded} (outside predicted frequency grid)",
            f"  RMS residual    : {self.rms_residual:.4g} [dimensionless MTF]",
            f"  max |residual|  : {self.max_abs_residual:.4g} [dimensionless MTF]",
            "",
            f"  {'freq [cy/m]':>14}  {'measured [-]':>12}  {'predicted [-]':>13}  "
            f"{'residual [-]':>12}",
        ]
        n = self.freq_cy_m.size
        if n <= max_rows:
            indices: list[int] = list(range(n))
        else:
            head = max_rows // 2
            tail = max_rows - head
            indices = list(range(head)) + [-1] + list(range(n - tail, n))
        for i in indices:
            if i == -1:
                lines.append(f"  {'...':>14}")
                continue
            lines.append(
                f"  {self.freq_cy_m[i]:>14.6g}  {self.measured[i]:>12.4f}  "
                f"{self.predicted[i]:>13.4f}  {self.residual[i]:>+12.4f}"
            )
        return "\n".join(lines)


def compare_mtf(
    result: ChainResult,
    measured: MeasuredCurve,
    *,
    axis: str = "x",
    frequency_unit: FrequencyUnit = "cy/m",
    pixel_pitch_m: float | None = None,
    focal_length_m: float | None = None,
) -> MtfComparisonResult:
    """Compare measured MTF data against a RADIANT-predicted MTF curve.

    Parameters
    ----------
    result:
        A completed chain run. The predicted curve is read from
        ``result.stage_outputs["performance"]["mtf_freq_<axis>"]``
        (cycles/m) and ``["mtf_<axis>"]``.
    measured:
        Measured curve whose x is spatial frequency in *frequency_unit*
        and whose y is MTF [dimensionless].
    axis:
        ``"x"`` (cross-track) or ``"y"`` (along-track).
    frequency_unit:
        Unit of ``measured.x``: ``"cy/m"``, ``"cy/mm"``, ``"cy/mrad"``,
        or ``"cy/pixel"``.
    pixel_pitch_m:
        Detector pixel pitch [m]; required when *frequency_unit* is
        ``"cy/pixel"``.
    focal_length_m:
        Effective focal length [m]; required when *frequency_unit* is
        ``"cy/mrad"``.

    Returns
    -------
    MtfComparisonResult
        Residual statistics over the overlapping frequency range.

    Raises
    ------
    MtfComparisonError
        If *axis* is invalid, the performance stage outputs are
        missing, or no measured point falls inside the predicted grid.
    radiant.performance.frequency_units.FrequencyUnitError
        If *frequency_unit* is unknown or needs missing context
        (pitch / focal length).
    """
    if axis not in ("x", "y"):
        raise MtfComparisonError(
            f"compare_mtf: axis must be 'x' or 'y', got {axis!r}. "
            "'x' is cross-track, 'y' is along-track."
        )

    perf = result.stage_outputs.get("performance")
    freq_key = f"mtf_freq_{axis}"
    mtf_key = f"mtf_{axis}"
    if perf is None or freq_key not in perf or mtf_key not in perf:
        available = sorted(perf.keys()) if perf is not None else []
        raise MtfComparisonError(
            f"compare_mtf: predicted MTF outputs '{freq_key}'/'{mtf_key}' not "
            "found in result.stage_outputs['performance']. Run the full chain "
            "(PerformanceStage must execute) before comparing. Available "
            f"performance keys: {available}."
        )

    pred_freq = np.asarray(perf[freq_key], dtype=np.float64)
    pred_mtf = np.asarray(perf[mtf_key], dtype=np.float64)
    if pred_freq.size < 2:
        raise MtfComparisonError(
            f"compare_mtf: predicted grid '{freq_key}' has {pred_freq.size} "
            "point(s); at least 2 are needed to interpolate. The chain run "
            "produced a degenerate MTF curve — inspect the run."
        )
    # np.interp requires ascending sample points; sort defensively.
    if not np.all(np.diff(pred_freq) > 0.0):
        order = np.argsort(pred_freq)
        pred_freq = pred_freq[order]
        pred_mtf = pred_mtf[order]

    meas_freq_cy_m = np.asarray(
        convert_spatial_frequency(
            measured.x,
            frequency_unit,
            "cy/m",
            pixel_pitch_m=pixel_pitch_m,
            focal_length_m=focal_length_m,
        ),
        dtype=np.float64,
    )

    inside = (meas_freq_cy_m >= pred_freq[0]) & (meas_freq_cy_m <= pred_freq[-1])
    n_excluded = int(np.count_nonzero(~inside))
    n_compared = int(np.count_nonzero(inside))
    if n_compared == 0:
        raise MtfComparisonError(
            "compare_mtf: no overlap between the measured frequency points "
            f"({meas_freq_cy_m.min():.6g}–{meas_freq_cy_m.max():.6g} cy/m after "
            f"conversion from '{frequency_unit}') and the predicted grid "
            f"({pred_freq[0]:.6g}–{pred_freq[-1]:.6g} cy/m). Check the "
            "frequency_unit — a wrong unit typically shifts the measured "
            "range by orders of magnitude."
        )

    freq_used = meas_freq_cy_m[inside]
    meas_used = np.asarray(measured.y, dtype=np.float64)[inside]
    pred_interp = np.interp(freq_used, pred_freq, pred_mtf)
    residual = meas_used - pred_interp

    return MtfComparisonResult(
        freq_cy_m=freq_used,
        measured=meas_used,
        predicted=pred_interp,
        residual=residual,
        rms_residual=float(np.sqrt(np.mean(residual**2))),
        max_abs_residual=float(np.max(np.abs(residual))),
        n_compared=n_compared,
        n_excluded=n_excluded,
    )


# ---------------------------------------------------------------------------
# Multi-config comparison (Gap 79 / Tier-2 FW-A)
# ---------------------------------------------------------------------------


class ComparisonError(RadiantError):
    """Raised when a multi-config comparison cannot be built (Gap 79)."""


@dataclass(frozen=True)
class ComparisonColumn:
    """One compared configuration: its label and evaluated result."""

    label: str
    result: ChainResult


@dataclass(frozen=True)
class ComparisonRow:
    """One metric across every compared configuration.

    ``values`` aligns with the parent result's ``labels`` order; a config
    missing this metric carries ``None`` (shown as absent, never zero-filled
    — Rule 17). ``deltas`` are ``value − baseline_value`` (None where either
    side is absent); ``best_index`` marks the best value under ``sense``
    ("higher" / "lower" / None when the registry declares no preference or
    fewer than two values exist).
    """

    name: str
    unit: str
    description: str
    values: tuple[float | None, ...]
    deltas: tuple[float | None, ...]
    best_index: int | None


@dataclass(frozen=True)
class ComparisonResult:
    """Aligned metric matrix over N evaluated configurations (Gap 79).

    Build with :func:`compare_configs`. ``rows`` cover the union of metric
    names across all results (sorted), each with units from the metric
    registry; ``baseline_index`` names the delta reference column.
    """

    labels: tuple[str, ...]
    rows: tuple[ComparisonRow, ...]
    baseline_index: int

    def row(self, name: str) -> ComparisonRow:
        """The row for metric *name* (KeyError if absent)."""
        for r in self.rows:
            if r.name == name:
                return r
        raise KeyError(f"ComparisonResult: no metric {name!r}; have {[r.name for r in self.rows]}")

    def to_table(self) -> str:
        """A plain-text aligned table (console/report convenience)."""
        header = ["metric", "unit", *self.labels]
        body: list[list[str]] = []
        for r in self.rows:
            cells = [r.name, r.unit]
            for i, v in enumerate(r.values):
                text = "—" if v is None else f"{v:.6g}"
                if r.best_index is not None and i == r.best_index:
                    text = f"*{text}"
                cells.append(text)
            body.append(cells)
        widths = [max(len(row[i]) for row in [header, *body]) for i in range(len(header))]
        lines = ["  ".join(c.ljust(w) for c, w in zip(header, widths, strict=True))]
        lines += ["  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)) for row in body]
        return "\n".join(lines)


# Metrics where smaller is better; everything else defaults to higher-is-better
# except flags/codes, which carry no preference. Kept deliberately small and
# conservative — a wrong "best" mark is worse than none.
_LOWER_IS_BETTER: frozenset[str] = frozenset({"nedt", "nedt_mk", "gsd_m", "fwhm_m", "fwhm_urad"})


def _row_best_index(name: str, kind: str, values: tuple[float | None, ...]) -> int | None:
    present = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(present) < 2 or kind in ("flag", "code"):
        return None
    lower = any(name == key or name.startswith(key) for key in _LOWER_IS_BETTER)
    chooser = min if lower else max
    return chooser(present, key=lambda pair: pair[1])[0]


def compare_configs(
    items: Sequence[tuple[str, ChainResult]],
    *,
    baseline: int = 0,
) -> ComparisonResult:
    """Compare N evaluated configurations as an aligned metric matrix (Gap 79).

    Parameters
    ----------
    items:
        ``(label, ChainResult)`` pairs — **pre-evaluated** results, so the
        caller controls when chains run (the GUI never re-evaluates behind
        the user's back; a script may pass ``(name, sensor.evaluate())``).
    baseline:
        Index of the delta-reference column (default: the first).

    Returns
    -------
    ComparisonResult
        Union-of-metrics rows (a metric absent from a config shows ``None``,
        never a zero), units/descriptions from the metric registry via
        ``metric_records()``, per-row deltas vs the baseline column, and a
        conservative best-per-metric mark (higher-is-better default;
        NEDT/GSD/FWHM lower-is-better; flags/codes unmarked).
    """
    if len(items) < 2:
        raise ComparisonError(
            f"compare_configs needs at least 2 configurations, got {len(items)}. "
            "Pass two or more (label, ChainResult) pairs."
        )
    if not (0 <= baseline < len(items)):
        raise ComparisonError(
            f"baseline index {baseline} out of range for {len(items)} configurations. "
            f"Pass 0 <= baseline < {len(items)}."
        )

    labels = tuple(label for label, _ in items)
    per_config = [{rec.name: rec for rec in result.metric_records()} for _label, result in items]
    names = sorted(set().union(*(set(records) for records in per_config)))

    rows: list[ComparisonRow] = []
    for name in names:
        somewhere = next(records[name] for records in per_config if name in records)
        values = tuple((records[name].value if name in records else None) for records in per_config)
        base = values[baseline]
        deltas = tuple((None if (v is None or base is None) else v - base) for v in values)
        rows.append(
            ComparisonRow(
                name=name,
                unit=somewhere.unit,
                description=somewhere.description,
                values=values,
                deltas=deltas,
                best_index=_row_best_index(name, somewhere.kind, values),
            )
        )
    return ComparisonResult(labels=labels, rows=tuple(rows), baseline_index=baseline)
