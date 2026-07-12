"""Sensor — high-level scripting API for RADIANT.

Wraps :class:`~radiant.api.session.RadiantSession` with a fluent
interface for loading configs, setting parameters, evaluating the
signal chain, and running trade studies (sweeps, Monte Carlo,
sensitivity analysis).

Usage::

    from radiant.api.sensor import Sensor

    s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
    result = s.evaluate()
    print(result.metrics)
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from radiant.api._param_registry import build_parameter_set
from radiant.api.errors import ApiValidationError
from radiant.api.sensitivity import SensitivityResult, sensitivity
from radiant.api.session import RadiantSession
from radiant.api.solve import SolveResult, solve_for
from radiant.api.sweep import Sweep2DResult, SweepResult, sweep, sweep_2d
from radiant.api.tolerance import MonteCarloResult, monte_carlo
from radiant.core.parameters import ParameterDef, ParameterSet, Provenance, Tolerance
from radiant.io.config import load_config, read_radiant_meta, save_config
from radiant.io.results import ChainResult

logger = logging.getLogger(__name__)

# Default number of wavelength grid points.
_DEFAULT_WL_POINTS: int = 500


class Sensor:
    """High-level entry point for RADIANT trade studies.

    Wraps :class:`RadiantSession` and :class:`ParameterSet`, exposing a
    simple API for loading configs, setting parameters, and running
    analyses.

    Parameters
    ----------
    wavelength_points:
        Number of points in the spectral evaluation grid.  The grid
        spans from ``spectral_integration.filter_min_um`` to
        ``spectral_integration.filter_max_um`` (set via config or
        :meth:`set`).
    """

    def __init__(self, *, wavelength_points: int = _DEFAULT_WL_POINTS) -> None:
        self._params: ParameterSet = build_parameter_set()
        self._wl_points: int = wavelength_points
        # Non-scalar pre-chain injections (Gap 68): group -> key -> object,
        # forwarded to RadiantSession.run(extra_stage_outputs=...) on every
        # evaluation, including trade studies. Not serialized by save().
        self._extra_stage_outputs: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        *,
        wavelength_points: int = _DEFAULT_WL_POINTS,
    ) -> Sensor:
        """Load a YAML configuration file.

        Parameters
        ----------
        path:
            Path to a RADIANT YAML config file.
        wavelength_points:
            Number of spectral grid points.

        Returns
        -------
        Sensor
            A new Sensor with the config applied (not yet resolved).
        """
        sensor = cls(wavelength_points=wavelength_points)
        load_config(Path(path), sensor._params)
        return sensor

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        wavelength_points: int = _DEFAULT_WL_POINTS,
    ) -> Sensor:
        """Create a Sensor from a nested configuration dict.

        Parameters
        ----------
        data:
            Nested dict matching the YAML structure (e.g.,
            ``{"optics": {"aperture_diameter_m": 0.3}}``).
        wavelength_points:
            Number of spectral grid points.

        Returns
        -------
        Sensor
            A new Sensor with the config applied.
        """
        sensor = cls(wavelength_points=wavelength_points)
        load_config(data, sensor._params)
        return sensor

    # ------------------------------------------------------------------
    # Persistence (Gap 67)
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> Sensor:
        """Load a Sensor saved with :meth:`save` (or any RADIANT YAML).

        Restores parameters, tolerance distributions, and the spectral
        grid size from the file's ``_radiant`` metadata block when
        present; plain configs load exactly as with :meth:`from_yaml`.
        """
        meta = read_radiant_meta(path)
        wl_points = meta.get("wavelength_points", _DEFAULT_WL_POINTS)
        if not isinstance(wl_points, int) or wl_points < 2:
            raise ApiValidationError(
                f"Sensor.load: '_radiant.wavelength_points' must be an "
                f"integer >= 2, got {wl_points!r} in {path}."
            )
        return cls.from_yaml(path, wavelength_points=wl_points)

    def save(self, path: str | Path) -> Path:
        """Save this Sensor to a YAML config that :meth:`load` restores.

        Writes the explicitly-set inputs (input units) plus a
        ``_radiant`` metadata block carrying ``wavelength_points`` and
        any tolerance distributions. Reloading reproduces this Sensor
        exactly: defaults re-apply, consistency groups re-derive, and
        provenance distinctions between explicit and defaulted
        parameters survive. The file is a normal RADIANT config: it
        also loads via :meth:`from_yaml` or the CLI.
        """
        self._ensure_resolved()
        meta: dict[str, Any] = {
            "format": 1,
            "wavelength_points": self._wl_points,
        }
        tolerances = {
            name: {"distribution": tol.distribution, "params": dict(tol.params)}
            for name, tol in self._params.tolerances().items()
        }
        if tolerances:
            meta["tolerances"] = tolerances
        return save_config(
            self._params,
            Path(path),
            header="# RADIANT config — written by Sensor.save()\n",
            meta=meta,
            scope="inputs",
        )

    # ------------------------------------------------------------------
    # Parameter access
    # ------------------------------------------------------------------

    def set(self, dotpath: str, value: Any, *, unit: str | None = None) -> Sensor:
        """Set a parameter by dot-path.

        With ``unit``, the value is converted from the caller's native
        unit at this boundary (Gap 6), e.g.
        ``sensor.set("optics.aperture_diameter_m", 30.0, unit="cm")``.

        Returns ``self`` for method chaining.
        """
        self._params.set(dotpath, value, Provenance.USER_SET, "Sensor.set", unit=unit)
        return self

    def set_many(self, overrides: dict[str, Any]) -> Sensor:
        """Set multiple parameters at once.

        Parameters
        ----------
        overrides:
            Dict mapping dot-path → value.

        Returns ``self`` for method chaining.
        """
        for dotpath, value in overrides.items():
            self._params.set(dotpath, value, Provenance.USER_SET, "Sensor.set_many")
        return self

    def get(self, dotpath: str) -> Any:
        """Get a resolved parameter value (in canonical units).

        Resolves the parameter set if needed.
        """
        self._ensure_resolved()
        return self._params.get(dotpath)

    def get_input(self, dotpath: str) -> Any:
        """Get a resolved parameter value in input (display) units."""
        self._ensure_resolved()
        return self._params.get_input(dotpath)

    def parameter_defs(self) -> Mapping[str, ParameterDef]:
        """Read-only view of the full parameter schema, keyed by dot-path.

        Passthrough to :meth:`ParameterSet.parameter_defs` (Gap 70): each
        :class:`ParameterDef` carries dtype, canonical/input units, bounds,
        enum values, default, description, and tags — the enumeration
        surface GUI panels and tooling generate from.
        """
        return self._params.parameter_defs()

    def parameter_def(self, dotpath: str) -> ParameterDef:
        """Return the :class:`ParameterDef` for one parameter.

        Raises ``KeyError`` (with a did-you-mean suggestion) for unknown
        names; deprecated aliases resolve with a ``DeprecationWarning``.
        """
        return self._params.parameter_def(dotpath)

    def reset(self, dotpath: str) -> Sensor:
        """Reset a parameter to its default value.

        Removes the user-set input so that the parameter reverts to
        its schema default (or is derived from a consistency group)
        on the next resolve.

        Returns ``self`` for method chaining.
        """
        self._params.clear_input(dotpath)
        return self

    def set_tolerance(
        self,
        dotpath: str,
        distribution: str,
        **kwargs: float,
    ) -> Sensor:
        """Set a tolerance distribution for Monte Carlo / sensitivity.

        Parameters
        ----------
        dotpath:
            Parameter dot-path.
        distribution:
            Distribution name: ``"gaussian"``, ``"uniform"``,
            ``"truncated_gaussian"``, ``"log_normal"``.
        **kwargs:
            Distribution parameters (e.g., ``std=0.01``).

        Returns ``self`` for method chaining.
        """
        tol = Tolerance(distribution=distribution, params=dict(kwargs))
        self._params.set_tolerance(dotpath, tol)
        return self

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def set_stage_output(self, group: str, key: str, value: Any) -> Sensor:
        """Attach a non-scalar pre-chain input (Gap 68 interim seam).

        Stores *value* under ``stage_outputs[group][key]`` for every
        subsequent evaluation — ``evaluate`` and all trade studies
        (sweep, sweep_2d, monte_carlo, sensitivity, solve_for). This is
        the Rule 6 injection route for element lists, Zernike/OPD
        wavefronts, spectral curves, and filter stacks::

            s.set_stage_output("optics_config", "element_list", elements)
            s.set_stage_output("optics_config", "wavefront_error", wfe)

        Pass ``None`` as *value* to remove a previously set injection.
        Injections are session state, not parameters: they are carried
        by :meth:`clone` but **not** written by :meth:`save` (arbitrary
        objects have no YAML form — rebuild them when reloading).

        Returns ``self`` for method chaining.
        """
        if value is None:
            self._extra_stage_outputs.get(group, {}).pop(key, None)
            if group in self._extra_stage_outputs and not self._extra_stage_outputs[group]:
                del self._extra_stage_outputs[group]
        else:
            self._extra_stage_outputs.setdefault(group, {})[key] = value
        return self

    def _merged_extras(
        self,
        extra: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]] | None:
        """Sensor-held injections with one-off *extra* merged on top."""
        if not self._extra_stage_outputs and not extra:
            return None
        merged: dict[str, dict[str, Any]] = {
            group: dict(values) for group, values in self._extra_stage_outputs.items()
        }
        for group, values in (extra or {}).items():
            merged.setdefault(group, {}).update(values)
        return merged

    def _make_run_fn(self, session: RadiantSession) -> Callable[[ParameterSet], ChainResult]:
        """Session runner carrying the sensor-held injections (Gap 68)."""
        extras = self._merged_extras()
        if extras is None:
            return session.run

        def _run(ps: ParameterSet) -> ChainResult:
            return session.run(ps, extra_stage_outputs=extras)

        return _run

    def evaluate(
        self,
        *,
        extra_stage_outputs: dict[str, dict[str, Any]] | None = None,
    ) -> ChainResult:
        """Run the full signal chain and return the result.

        Parameters
        ----------
        extra_stage_outputs:
            One-off non-scalar pre-chain injections (Gap 68), merged over
            any set via :meth:`set_stage_output`, e.g.
            ``{"optics_config": {"element_list": elements}}``.
        """
        self._ensure_resolved()
        session = self._build_session()
        merged = self._merged_extras(extra_stage_outputs)
        if merged is None:
            return session.run(self._params)
        return session.run(self._params, extra_stage_outputs=merged)

    # ------------------------------------------------------------------
    # Trade studies
    # ------------------------------------------------------------------

    def sweep(
        self,
        param: str,
        values: Sequence[float] | npt.NDArray[np.float64],
        *,
        metric: str | Callable[[ChainResult], float] = "snr",
        keep_results: bool = True,
        n_workers: int = 1,
        progress: Callable[[int, int], None] | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> SweepResult:
        """Run a 1-D parameter sweep.

        Parameters
        ----------
        param:
            Dot-path of the parameter to sweep.
        values:
            Array of parameter values.
        metric:
            Metric key string (looked up in ``result.metrics``) or a
            callable ``(ChainResult) -> float``.
        keep_results:
            Store full ChainResult at each point.
        n_workers:
            Parallel workers (1 = sequential).
        progress:
            ``progress(done, total)`` callback per completed point (Gap 72).
        cancel:
            ``cancel() -> bool`` poll; True aborts with
            :class:`~radiant.api._progress.OperationCancelledError`.
        """
        self._ensure_resolved()
        session = self._build_session()
        metric_fn, metric_name = self._resolve_metric(metric)
        return sweep(
            self._make_run_fn(session),
            self._params,
            param,
            values,
            metric=metric_fn,
            metric_name=metric_name,
            keep_results=keep_results,
            n_workers=n_workers,
            progress=progress,
            cancel=cancel,
        )

    def solve_for(
        self,
        param: str,
        target: float,
        *,
        bounds: tuple[float, float],
        metric: str | Callable[[ChainResult], float] = "snr",
        rtol: float = 1e-6,
    ) -> SolveResult:
        """Find the parameter value that makes *metric* equal *target* (Gap 10).

        Brent root-finding on the forward model over the *bounds*
        bracket (input units). Example::

            res = sensor.solve_for(
                "optics.aperture_diameter_m", 50.0,
                bounds=(0.05, 1.0), metric="snr",
            )
            res.solution   # aperture [m] giving SNR = 50

        Raises :class:`~radiant.api.solve.SolveBracketError` (with both
        endpoint metric values) when the target is not bracketed.
        """
        self._ensure_resolved()
        session = self._build_session()
        metric_fn, metric_name = self._resolve_metric(metric)
        return solve_for(
            self._make_run_fn(session),
            self._params,
            param,
            target,
            bounds,
            metric=metric_fn,
            metric_name=metric_name,
            rtol=rtol,
        )

    def sweep_2d(
        self,
        param1: str,
        values1: Sequence[float] | npt.NDArray[np.float64],
        param2: str,
        values2: Sequence[float] | npt.NDArray[np.float64],
        *,
        metric: str | Callable[[ChainResult], float] = "snr",
        progress: Callable[[int, int], None] | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> Sweep2DResult:
        """Run a 2-D parameter sweep.

        Parameters
        ----------
        param1, param2:
            Dot-paths of the two swept parameters.
        values1, values2:
            Arrays of values for each axis.
        metric:
            Metric key string or callable.
        progress:
            ``progress(done, total)`` callback per grid cell (Gap 72).
        cancel:
            ``cancel() -> bool`` poll; True aborts with
            :class:`~radiant.api._progress.OperationCancelledError`.
        """
        self._ensure_resolved()
        session = self._build_session()
        metric_fn, metric_name = self._resolve_metric(metric)
        return sweep_2d(
            self._make_run_fn(session),
            self._params,
            param1,
            values1,
            param2,
            values2,
            metric=metric_fn,
            metric_name=metric_name,
            progress=progress,
            cancel=cancel,
        )

    def monte_carlo(
        self,
        n_trials: int = 1000,
        seed: int = 42,
        *,
        metric_names: tuple[str, ...] | None = None,
        keep_results: bool = False,
        progress: Callable[[int, int], None] | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> MonteCarloResult:
        """Run Monte Carlo tolerance analysis.

        Requires at least one tolerance set via :meth:`set_tolerance`.

        Parameters
        ----------
        n_trials:
            Number of MC trials.
        seed:
            Random seed for reproducibility.
        metric_names:
            Metric keys to record. Auto-detected if None.
        keep_results:
            Store full ChainResult per trial.
        progress:
            ``progress(done, total)`` callback per trial (Gap 72).
        cancel:
            ``cancel() -> bool`` poll; True aborts with
            :class:`~radiant.api._progress.OperationCancelledError`.
        """
        self._ensure_resolved()
        session = self._build_session()
        return monte_carlo(
            self._make_run_fn(session),
            self._params,
            n_trials=n_trials,
            seed=seed,
            metric_names=metric_names,
            keep_results=keep_results,
            progress=progress,
            cancel=cancel,
        )

    def sensitivity(
        self,
        *,
        metric: str | Callable[[ChainResult], float] = "snr",
        param_names: Sequence[str] | None = None,
        delta_fraction: float = 0.01,
        progress: Callable[[int, int], None] | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> SensitivityResult:
        """Run one-at-a-time sensitivity analysis.

        Parameters
        ----------
        metric:
            Metric key string or callable.
        param_names:
            Parameters to perturb. If None, uses toleranced or all
            float parameters.
        delta_fraction:
            Fractional perturbation (0.01 = ±1%).
        progress:
            ``progress(done, total)`` callback per perturbed parameter (Gap 72).
        cancel:
            ``cancel() -> bool`` poll; True aborts with
            :class:`~radiant.api._progress.OperationCancelledError`.
        """
        self._ensure_resolved()
        session = self._build_session()
        metric_fn, metric_name = self._resolve_metric(metric)
        return sensitivity(
            self._make_run_fn(session),
            self._params,
            metric=metric_fn,
            metric_name=metric_name,
            param_names=list(param_names) if param_names is not None else None,
            delta_fraction=delta_fraction,
            progress=progress,
            cancel=cancel,
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def clone(self) -> Sensor:
        """Return a deep copy of this Sensor."""
        return copy.deepcopy(self)

    def summary(self) -> str:
        """Return a human-readable summary of all resolved parameters."""
        self._ensure_resolved()
        resolved = self._params.all_resolved()
        lines: list[str] = ["RADIANT Sensor — Parameter Summary", "=" * 50]
        # Group by namespace prefix
        groups: dict[str, list[str]] = {}
        for name, rv in sorted(resolved.items()):
            prefix = name.split(".")[0]
            groups.setdefault(prefix, [])
            unit_str = f" {rv.input_unit}" if rv.input_unit else ""
            prov_str = rv.provenance.value
            groups[prefix].append(f"  {name} = {rv.input_value}{unit_str}  [{prov_str}]")
        for prefix in sorted(groups):
            lines.append(f"\n[{prefix}]")
            lines.extend(groups[prefix])
        return "\n".join(lines)

    def explain(self, dotpath: str | None = None) -> str:
        """Return a human-readable explanation.

        Parameters
        ----------
        dotpath:
            If provided, explain that parameter's provenance and value.
            If None, return a chain walkthrough with intermediate values
            from the most recent evaluation.
        """
        self._ensure_resolved()
        if dotpath is not None:
            return self._params.explain(dotpath)
        # Chain walkthrough — evaluate and describe the stages
        result = self.evaluate()
        lines: list[str] = ["RADIANT Chain Walkthrough", "=" * 50]
        for stage_name in result.history:
            lines.append(f"\n--- {stage_name} ---")
            outputs = result.stage_outputs.get(stage_name, {})
            for key, val in sorted(outputs.items()):
                lines.append(f"  {key}: {_format_value(val)}")
        lines.append("\n--- Metrics ---")
        for name, val in sorted(result.metrics.items()):
            lines.append(f"  {name}: {val:.6g}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_resolved(self) -> None:
        """Resolve the ParameterSet if it is not already resolved."""
        if not self._params.is_resolved:
            self._params.resolve()

    def _build_session(self) -> RadiantSession:
        """Build a RadiantSession with the appropriate wavelength grid."""
        fmin: float = self._params.get("spectral_integration.filter_min_um")
        fmax: float = self._params.get("spectral_integration.filter_max_um")
        wl = np.linspace(fmin, fmax, self._wl_points)
        return RadiantSession(wavelength_um=wl)

    @staticmethod
    def _resolve_metric(
        metric: str | Callable[[ChainResult], float],
    ) -> tuple[Callable[[ChainResult], float], str]:
        """Convert a string metric key to a metric function + name."""
        if callable(metric):
            name = getattr(metric, "__name__", "metric")
            return metric, name
        metric_key = metric

        def _extract(result: ChainResult) -> float:
            val = result.metrics.get(metric_key)
            if val is None:
                raise ApiValidationError(
                    f"Metric '{metric_key}' not found in result.metrics. "
                    f"Available: {list(result.metrics.keys())}"
                )
            return float(val)

        return _extract, metric_key


def _format_value(val: Any) -> str:
    """Format a value for display in explain() output."""
    if isinstance(val, np.ndarray):
        if val.size <= 4:
            return repr(val)
        return f"ndarray shape={val.shape} dtype={val.dtype}"
    if isinstance(val, float):
        return f"{val:.6g}"
    return repr(val)
