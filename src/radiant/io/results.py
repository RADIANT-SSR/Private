"""ChainResult — read-only wrapper over the final ChainState.

Exposes raw frames, noise_terms, stage_outputs, history, metrics,
backward-propagation query methods for expressing signal and noise at
any reference frame, and a provenance record (per
RADIANT_Master_Architecture.md §C13).
"""

from __future__ import annotations

import copy
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.provenance import (
    dependency_versions,
    git_commit,
    python_version_string,
)
from radiant.core.quantity import (
    ChainQuantity,
    ReferenceFrame,
)
from radiant.core.quantity import noise_at as _quantity_noise_at
from radiant.core.quantity import signal_at as _quantity_signal_at
from radiant.core.radiometry import NoiseTerm, RadiometricFrame


@dataclass(frozen=True)
class MetricRecord:
    """One computed metric joined with its registry metadata (Gap 71).

    ``unit`` is always a non-empty human-readable string; ``kind`` is
    "float", "flag" (0/1 boolean), or "code" (enumeration encoded as a
    float — the description names the levels).
    """

    name: str
    value: float
    unit: str
    description: str
    kind: str


class ChainResult:
    """Read-only view over a completed chain run.

    Parameters
    ----------
    state:
        The final :class:`ChainState` produced by
        :meth:`ChainRunner.run`.
    params:
        The resolved :class:`ParameterSet` used for the run. Optional
        for back-compat with callers that construct a ``ChainResult``
        directly from a state. When omitted,
        :meth:`to_provenance_record` reports an empty ``parameter_set``
        and ``input_file_hashes`` block.
    """

    def __init__(
        self,
        state: ChainState,
        params: ParameterSet | None = None,
        *,
        saved_provenance: dict[str, Any] | None = None,
    ) -> None:
        self._state = state
        self._params = params
        # Set only by load(): the provenance record frozen at save time.
        # A reloaded result reports the run that produced it, not the
        # environment that loaded it.
        self._saved_provenance = saved_provenance

    @property
    def state(self) -> ChainState:
        """The underlying ChainState (read-only access)."""
        return self._state

    @property
    def wavelength_um(self) -> npt.NDArray[np.float64]:
        """The common spectral grid [µm]."""
        return self._state.wavelength_um

    @property
    def frames(self) -> Mapping[str, RadiometricFrame]:
        """All registered radiometric frames (read-only mapping)."""
        return self._state.frames

    @property
    def noise_terms(self) -> tuple[NoiseTerm, ...]:
        """All noise contributions."""
        return self._state.noise_terms

    @property
    def stage_outputs(self) -> Mapping[str, Mapping[str, Any]]:
        """Per-stage metadata (read-only nested mapping)."""
        return self._state.stage_outputs

    @property
    def history(self) -> tuple[str, ...]:
        """Ordered tuple of stage names that executed."""
        return self._state.history

    @property
    def metrics(self) -> Mapping[str, float]:
        """Computed performance metrics (read-only mapping).

        Bare name → value. For unit-labelled access use
        :meth:`metric_records` (Gap 71 — every displayed value carries
        units).
        """
        return self._state.metrics

    def metric_records(self) -> tuple[MetricRecord, ...]:
        """All computed metrics with units and descriptions (Gap 71).

        One :class:`MetricRecord` per ``metrics`` entry, in sorted-name
        order, joining each value with its registry metadata
        (:mod:`radiant.performance.registry`). Raises ``KeyError`` if a
        metric key has no registry entry — that is a registry-drift bug
        (CU-078); the reconciliation integration test catches it before
        release.
        """
        from radiant.performance.registry import metric_info

        records = []
        for name in sorted(self._state.metrics):
            spec = metric_info(name)  # KeyError on drift — deliberate
            records.append(
                MetricRecord(
                    name=name,
                    value=float(self._state.metrics[name]),
                    unit=spec.unit,
                    description=spec.description,
                    kind=spec.kind,
                )
            )
        return tuple(records)

    # ------------------------------------------------------------------
    # Backward propagation queries
    # ------------------------------------------------------------------

    def signal_at(
        self,
        frame: ReferenceFrame | str,
    ) -> ChainQuantity:
        """Get the in-band signal expressed at a target reference frame.

        The returned value is **derived**, not stored: the post-integration
        signal is propagated backward to *frame* through the chain's
        transfer factors. For pre-integration frames (``at_target``,
        ``at_aperture``, ``post_optics``) the corresponding
        ``result.frames[...]`` object intentionally carries
        ``in_band_value = None`` — those frames are spectral-only by
        design (Rule 8: spectral integration happens exactly once), so
        this accessor is the *only* way to read an in-band scalar there
        (CU-049). The two access paths differing is the documented
        contract, not a bug.

        Parameters
        ----------
        frame:
            Target reference frame (enum or string like "at_aperture").

        Returns
        -------
        ChainQuantity
            In-band signal value derived at the requested frame.
        """
        if isinstance(frame, str):
            frame = ReferenceFrame(frame)
        return _quantity_signal_at(self._state, frame)

    def noise_at(
        self,
        frame: ReferenceFrame | str,
        term_name: str | None = None,
    ) -> ChainQuantity:
        """Get noise (total or specific term) at a target reference frame.

        Parameters
        ----------
        frame:
            Target reference frame.
        term_name:
            If provided, return only the named noise term.
            If None, return total noise (RSS).

        Returns
        -------
        ChainQuantity
            Noise value at the requested frame.
        """
        if isinstance(frame, str):
            frame = ReferenceFrame(frame)
        return _quantity_noise_at(self._state, frame, term_name)

    # ------------------------------------------------------------------
    # Deprecated aliases (CU-NEW-03 — to be removed after 0.2.0)
    # ------------------------------------------------------------------

    def signal_at_frame(
        self,
        frame: ReferenceFrame | str,
    ) -> ChainQuantity:
        """Deprecated alias for :meth:`signal_at`. Issues DeprecationWarning."""
        warnings.warn(
            "ChainResult.signal_at_frame() is deprecated; use signal_at() instead. "
            "The old name will be removed in RADIANT 0.2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.signal_at(frame)

    def noise_at_frame(
        self,
        frame: ReferenceFrame | str,
        term_name: str | None = None,
    ) -> ChainQuantity:
        """Deprecated alias for :meth:`noise_at`. Issues DeprecationWarning."""
        warnings.warn(
            "ChainResult.noise_at_frame() is deprecated; use noise_at() instead. "
            "The old name will be removed in RADIANT 0.2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.noise_at(frame, term_name)

    # ------------------------------------------------------------------
    # Performance metric convenience accessors
    # ------------------------------------------------------------------

    def snr(self) -> float:
        """Signal-to-noise ratio (dimensionless). Reads ``metrics['snr']``.

        Raises
        ------
        KeyError
            If SNR was not computed for this run (e.g., scenario routed through
            a metric mode that did not populate ``metrics['snr']``). Inspect
            ``self.metrics`` to see what was actually computed.
        """
        return float(self._state.metrics["snr"])

    def nedt(self) -> float:
        """Noise-equivalent delta-temperature in kelvin. Reads ``metrics['nedt_K']``.

        Raises
        ------
        KeyError
            If NEDT was not computed for this run.
        """
        return float(self._state.metrics["nedt_K"])

    def niirs(self) -> float:
        """National Imagery Interpretability Rating Scale value. Reads ``metrics['niirs']``.

        Raises
        ------
        KeyError
            If NIIRS was not computed for this run.
        """
        return float(self._state.metrics["niirs"])

    # ------------------------------------------------------------------
    # Persistence (Gap 67)
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> Path:
        """Save this result to a single-file archive (zip: JSON + npz).

        The archive holds the full :class:`ChainState` — frames, noise
        terms, stage outputs, MTF terms, metrics, history — plus the
        provenance record frozen at save time. Reload with
        :meth:`ChainResult.load`. Values that cannot be encoded (none,
        for states produced by the shipped chain) are recorded in the
        archive manifest with a ``UserWarning`` here.
        """
        from radiant.io.serialization import save_result_archive

        return save_result_archive(path, self._state, self.to_provenance_record())

    @classmethod
    def load(cls, path: str | Path) -> ChainResult:
        """Reload a result saved with :meth:`save`.

        The reloaded result has no attached :class:`ParameterSet` (the
        run's resolved parameters live in the provenance record, which
        is preserved exactly as frozen at save time and returned by
        :meth:`to_provenance_record`). All state accessors — metrics,
        frames, noise terms, MTF terms, ``signal_at``/``noise_at`` —
        work as on the original.
        """
        from radiant.io.serialization import load_result_archive

        state, provenance = load_result_archive(path)
        return cls(state, None, saved_provenance=provenance)

    # ------------------------------------------------------------------
    # Provenance (RADIANT_Master_Architecture.md §C13)
    # ------------------------------------------------------------------

    def to_provenance_record(self) -> dict[str, Any]:
        """Return the complete provenance record for this run.

        Implements the contract from RADIANT_Master_Architecture.md §C13.
        The returned dict has the following keys:

        - ``run_id`` — UUID4 string assigned at chain-runtime
          (:func:`radiant.core.provenance.new_run_id`). ``None`` if
          this result was constructed from a synthetic state without
          going through :meth:`ChainRunner.run`.
        - ``radiant_version`` — ``radiant.__version__``.
        - ``git_commit`` — short SHA of the working-tree HEAD;
          ``"unknown"`` if not in a git repo.
        - ``python_version`` — ``MAJOR.MINOR.PATCH``.
        - ``dependency_versions`` — ``{name: version}`` for the declared
          runtime dependencies (numpy, scipy, pyyaml, click).
        - ``parameter_set`` — ``{dotpath: ResolvedValue.to_dict()}``
          for every resolved parameter (per-parameter provenance,
          values, units). Empty if no ParameterSet was attached.
        - ``input_file_hashes`` — ordered list of
          ``[{"path": str, "sha256": str}, ...]`` for every config
          file consumed via :func:`radiant.io.config.load_config`.
          Empty if no ParameterSet was attached.
        - ``active_models`` — ordered list of stage names that ran;
          mirrors :attr:`history`.

        The result is JSON-serialisable: ``ResolvedValue.to_dict()``
        flattens enums, timestamps are isoformat strings, and there are
        no numpy arrays in the record.
        """
        from radiant import __version__ as _radiant_version

        if self._saved_provenance is not None:
            # Reloaded result: report the record frozen at save time.
            return copy.deepcopy(self._saved_provenance)

        if self._params is not None:
            try:
                resolved = self._params.all_resolved()
            except RuntimeError:
                # Params provided but not resolved — leave parameter_set empty
                # rather than crashing the provenance render.
                resolved = {}
            parameter_set = {name: rv.to_dict() for name, rv in resolved.items()}
            input_file_hashes = [{"path": p, "sha256": h} for p, h in self._params.loaded_files]
        else:
            parameter_set = {}
            input_file_hashes = []

        return {
            "run_id": self._state.run_id,
            "radiant_version": _radiant_version,
            "git_commit": git_commit(),
            "python_version": python_version_string(),
            "dependency_versions": dependency_versions(),
            "parameter_set": parameter_set,
            "input_file_hashes": input_file_hashes,
            "active_models": list(self._state.history),
        }
