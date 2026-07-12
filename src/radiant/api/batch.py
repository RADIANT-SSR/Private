"""Batch matrix execution — run one evaluation per cell of a labeled grid.

Implements the ``BatchRunner`` named in the architecture's ``api/``
layout (scenario 4.1 prerequisite: N targets × M atmospheres × K sensors
program-review matrices). The runner owns the mechanical part —
cartesian product of labeled axes, per-cell parameter overrides, and
per-cell failure capture — while the caller supplies the physics in an
``evaluate`` callback (a plain :meth:`Sensor.evaluate`, a
:meth:`Sensor.solve_for`, or any custom search).

Failure policy (Rule 17): a cell whose evaluation raises a
:class:`~radiant.core.exceptions.RadiantError` becomes a row with a
populated ``error`` column — recorded data, never silently dropped.
Any other exception is a programming bug and propagates.

Example::

    axes = [
        ("target", {"tank": {"source.target.temperature": 310.0}, ...}),
        ("atmosphere", {"clear": {"atmosphere.visibility_km": 50.0}, ...}),
    ]
    result = BatchRunner(base_config, axes).run(
        lambda sensor, labels: {"snr": sensor.evaluate().metrics["snr"]}
    )
    result.pivot("snr", rows="target", cols="atmosphere")
"""

from __future__ import annotations

import itertools
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from radiant.api._progress import CancelFn, ProgressFn, check_cancel
from radiant.core.exceptions import RadiantError

logger = logging.getLogger(__name__)

__all__ = ["BatchResult", "BatchRunner", "BatchRunnerError"]

_RESERVED_COLUMNS = frozenset({"error"})

Axes = Sequence[tuple[str, Mapping[str, Mapping[str, Any]]]]
EvaluateFn = Callable[[Any, dict[str, str]], Mapping[str, Any]]


class BatchRunnerError(RadiantError):
    """Raised for invalid batch construction or result queries."""


@dataclass(frozen=True)
class BatchResult:
    """Tidy result table from a :class:`BatchRunner` run.

    Attributes
    ----------
    axes:
        ``(axis_name, (label, ...))`` pairs in run order.
    rows:
        One dict per cell: the axis labels, the evaluate outputs, and an
        ``error`` key (``None`` on success, the failure message
        otherwise).
    """

    axes: tuple[tuple[str, tuple[str, ...]], ...]
    rows: tuple[dict[str, Any], ...]

    @property
    def n_failed(self) -> int:
        """Number of cells whose evaluation raised a RadiantError."""
        return sum(1 for r in self.rows if r.get("error") is not None)

    def pivot(
        self,
        value: str,
        *,
        rows: str,
        cols: str,
    ) -> dict[str, dict[str, Any]]:
        """Pivot one output into ``{row_label: {col_label: value}}``.

        Cells that failed (or lack *value*) appear as ``None``. Rows not
        matching a unique (rows, cols) pair are averaged-free: the last
        matching row wins — pass a fully-crossed grid for unambiguous
        pivots.
        """
        axis_names = {name for name, _ in self.axes}
        for key in (rows, cols):
            if key not in axis_names:
                raise BatchRunnerError(
                    f"pivot: {key!r} is not an axis (axes: {sorted(axis_names)})."
                )
        row_labels = dict(self.axes)[rows]
        col_labels = dict(self.axes)[cols]
        table: dict[str, dict[str, Any]] = {r: dict.fromkeys(col_labels) for r in row_labels}
        for row in self.rows:
            cell = None if row.get("error") is not None else row.get(value)
            table[row[rows]][row[cols]] = cell
        return table


class BatchRunner:
    """Run an evaluation over the cartesian product of labeled axes.

    Parameters
    ----------
    base_config:
        Nested config dict for :meth:`Sensor.from_dict` — the common
        sensor every cell starts from.
    axes:
        Ordered ``(axis_name, {label: {dotpath: value, ...}})`` pairs.
        The last axis varies fastest. Axis names become result columns,
        so ``"error"`` is reserved.
    sensor_factory:
        Test seam: callable building the per-cell sensor from
        *base_config*. Defaults to :meth:`radiant.api.Sensor.from_dict`.
    """

    def __init__(
        self,
        base_config: Mapping[str, Any],
        axes: Axes,
        *,
        sensor_factory: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        if not axes:
            raise BatchRunnerError("BatchRunner needs at least one axis; got an empty sequence.")
        seen: set[str] = set()
        for name, labels in axes:
            if name in _RESERVED_COLUMNS:
                raise BatchRunnerError(f"axis name {name!r} is reserved for the result table.")
            if name in seen:
                raise BatchRunnerError(f"duplicate axis name {name!r}.")
            seen.add(name)
            if not labels:
                raise BatchRunnerError(f"axis {name!r} has no labels.")
        self._base_config = dict(base_config)
        self._axes = [(name, dict(labels)) for name, labels in axes]
        self._sensor_factory = sensor_factory

    def run(
        self,
        evaluate: EvaluateFn,
        *,
        progress: ProgressFn | None = None,
        cancel: CancelFn | None = None,
    ) -> BatchResult:
        """Evaluate every cell and return the tidy result table.

        Parameters
        ----------
        evaluate:
            ``evaluate(sensor, labels) -> mapping`` producing the cell's
            output columns. *sensor* has the base config plus this
            cell's overrides already applied; *labels* maps axis name →
            label. A raised :class:`RadiantError` marks the cell failed
            (``error`` column); other exceptions propagate.
        progress:
            Optional ``progress(done, total)`` callback, called after
            each cell (Gap 72). ``total`` is the full grid size.
        cancel:
            Optional ``cancel() -> bool`` poll; True aborts with
            :class:`~radiant.api._progress.OperationCancelledError`.
        """
        factory = self._sensor_factory
        if factory is None:  # pragma: no cover - exercised via scenarios
            from radiant.api.sensor import Sensor

            factory = Sensor.from_dict

        names = [name for name, _ in self._axes]
        label_sets = [list(labels.keys()) for _, labels in self._axes]
        rows: list[dict[str, Any]] = []

        combos = list(itertools.product(*label_sets))
        total = len(combos)
        for i_cell, combo in enumerate(combos):
            check_cancel(cancel, "BatchRunner.run", i_cell, total)
            labels = dict(zip(names, combo, strict=True))
            sensor = factory(self._base_config)
            for (_name, axis_labels), label in zip(self._axes, combo, strict=True):
                for dotpath, value in axis_labels[label].items():
                    sensor.set(dotpath, value)
            row: dict[str, Any] = dict(labels)
            try:
                outputs = evaluate(sensor, labels)
            except RadiantError as exc:
                row["error"] = str(exc)
                logger.warning("Batch cell %s failed: %s", labels, exc)
            else:
                row.update(outputs)
                row["error"] = None
            rows.append(row)
            if progress is not None:
                progress(i_cell + 1, total)

        paired = zip(names, label_sets, strict=True)
        return BatchResult(
            axes=tuple((name, tuple(labels)) for name, labels in paired),
            rows=tuple(rows),
        )
