"""ChainResult inspector — tree-formatted view of stage outputs.

Provides :func:`inspect_result` for printing a formatted tree of all
stage outputs, noise terms, MTF terms, and metrics from a
:class:`~radiant.io.results.ChainResult`.

Usage::

    from radiant.api.inspect import inspect_result

    result = sensor.evaluate()
    print(inspect_result(result))          # full tree
    print(inspect_result(result, "optics"))  # single stage
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import numpy as np

from radiant.api.errors import ApiValidationError
from radiant.io.results import ChainResult

logger = logging.getLogger(__name__)


def inspect_result(
    result: ChainResult,
    stage: str | None = None,
) -> str:
    """Format a ChainResult as a readable tree.

    Parameters
    ----------
    result:
        A completed :class:`ChainResult`.
    stage:
        If provided, show only the named stage's outputs.
        If None, show all stages, metrics, noise, and MTF.

    Returns
    -------
    str
        Formatted tree string.
    """
    if stage is not None:
        return _format_stage(result, stage)
    return _format_full(result)


def _format_full(result: ChainResult) -> str:
    """Format the full ChainResult tree."""
    lines: list[str] = ["ChainResult"]

    # Metrics
    lines.append("\u251c\u2500\u2500 metrics")
    metrics = dict(result.metrics)
    metric_items = sorted(metrics.items())
    for i, (name, val) in enumerate(metric_items):
        connector = "\u2502   \u2514" if i == len(metric_items) - 1 else "\u2502   \u251c"
        lines.append(f"{connector}\u2500\u2500 {name}: {_fmt(val)}")

    # Noise terms
    if result.noise_terms:
        lines.append("\u251c\u2500\u2500 noise_terms")
        for i, nt in enumerate(result.noise_terms):
            connector = "\u2502   \u2514" if i == len(result.noise_terms) - 1 else "\u2502   \u251c"
            lines.append(f"{connector}\u2500\u2500 {nt.name}: {nt.value_e:.4f} e- RMS")

    # MTF terms
    mtf_terms = dict(result.state.mtf_terms)
    if mtf_terms:
        lines.append("\u251c\u2500\u2500 mtf_terms")
        mtf_items = sorted(mtf_terms.items())
        for i, (name, arr) in enumerate(mtf_items):
            connector = "\u2502   \u2514" if i == len(mtf_items) - 1 else "\u2502   \u251c"
            lines.append(f"{connector}\u2500\u2500 {name}: {_fmt(arr)}")

    # Frames
    frames = dict(result.frames)
    if frames:
        lines.append("\u251c\u2500\u2500 frames")
        frame_items = sorted(frames.keys())
        for i, fname in enumerate(frame_items):
            connector = "\u2502   \u2514" if i == len(frame_items) - 1 else "\u2502   \u251c"
            lines.append(f"{connector}\u2500\u2500 {fname}")

    # Stage outputs
    stages = dict(result.stage_outputs)
    stage_items = sorted(stages.items())
    for si, (sname, outputs) in enumerate(stage_items):
        is_last_stage = si == len(stage_items) - 1
        connector = "\u2514" if is_last_stage else "\u251c"
        lines.append(f"{connector}\u2500\u2500 stage: {sname}")
        output_items = sorted(outputs.items())
        for oi, (key, val) in enumerate(output_items):
            prefix = "    " if is_last_stage else "\u2502   "
            oconn = "\u2514" if oi == len(output_items) - 1 else "\u251c"
            lines.append(f"{prefix}{oconn}\u2500\u2500 {key}: {_fmt(val)}")

    return "\n".join(lines)


def _format_stage(result: ChainResult, stage: str) -> str:
    """Format a single stage's outputs."""
    outputs = result.stage_outputs.get(stage)
    if outputs is None:
        available = list(result.stage_outputs.keys())
        return f"Stage '{stage}' not found in result.\nAvailable stages: {available}"
    lines: list[str] = [f"stage: {stage}"]
    output_items = sorted(outputs.items())
    for i, (key, val) in enumerate(output_items):
        connector = "\u2514" if i == len(output_items) - 1 else "\u251c"
        lines.append(f"{connector}\u2500\u2500 {key}: {_fmt(val)}")
    return "\n".join(lines)


class ResultPlotNamespace:
    """Namespace for result plot accessors.

    Construct with a :class:`ChainResult`::

        plots = ResultPlotNamespace(result)
        plots.psf(); plots.noise_budget(); plots.mtf(); plots.mtf_budget()

    (``ChainResult`` lives in ``radiant.io`` which may not import the API
    layer, so the namespace is constructed here rather than attached as a
    ``result.plot`` property.) Lazily imports matplotlib — raises a
    helpful error if not installed.
    """

    def __init__(self, result: ChainResult) -> None:
        self._result = result

    def psf(self, **kwargs: Any) -> Any:
        """Plot the effective PSF as a 2D image."""
        from radiant.api.plot import plot_psf

        psf_data = self._result.stage_outputs.get("optics", {}).get("effective_psf")
        if psf_data is None:
            raise ApiValidationError("No effective PSF found in result stage_outputs['optics'].")
        return plot_psf(psf_data, **kwargs)

    def noise_budget(self, **kwargs: Any) -> Any:
        """Plot the noise budget as a horizontal bar chart."""
        from radiant.api.plot import plot_noise_budget

        return plot_noise_budget(self._result.noise_terms, **kwargs)

    def mtf(self, **kwargs: Any) -> Any:
        """Plot all MTF terms."""
        from radiant.api.plot import plot_mtf_terms

        return plot_mtf_terms(
            dict(self._result.state.mtf_terms),
            self._result.state.spatial_freq_cycles_per_mrad,
            **kwargs,
        )

    def mtf_budget(self, **kwargs: Any) -> Any:
        """Plot the per-contributor MTF-at-Nyquist budget (Gap 19)."""
        from radiant.api.plot import plot_mtf_budget

        budget = self._result.stage_outputs.get("performance", {}).get("mtf_budget")
        if budget is None:
            raise ApiValidationError(
                "No MTF budget found in result stage_outputs['performance'] — "
                "the chain must run PerformanceStage with an MTF product path."
            )
        return plot_mtf_budget(budget, **kwargs)


def _fmt(val: Any) -> str:
    """Format a value for tree display."""
    if isinstance(val, np.ndarray):
        if val.size <= 4:
            return repr(val)
        return f"ndarray(shape={val.shape}, dtype={val.dtype})"
    if isinstance(val, float):
        return f"{val:.6g}"
    if isinstance(val, Mapping):
        return f"dict({len(val)} keys)"
    return repr(val)
