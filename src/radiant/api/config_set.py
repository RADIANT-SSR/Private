"""Configuration sets — one study holding up to eight named configurations.

Implements the core model of ADR-0010 (CODE V zoom-configuration semantics):
a **shared base** :class:`~radiant.api.sensor.Sensor` plus a **dense configured
table** mapping a parameter dot-path to one value per configuration.

Model (ADR-0010 D-A/D-B)
-----------------------
- A parameter is **shared** by default: it lives in the base sensor's explicit
  inputs and has one value for every configuration.
- :meth:`ConfigurationSet.configure` promotes a parameter to **configured**: it
  moves out of the base and carries one value per configuration — dense by
  construction, never sparse.
- **Single-store invariant:** a dot-path is in the base's explicit inputs *or*
  in the configured table, never both. A parameter that should be *derived* (a
  consistency-group member) is simply absent from both, exactly as today.

Evaluation (ADR-0010 D-C) is defined as, and only as, materialization::

    sensor_for(name) = base.clone()
                        .set(p, values[p][i], source="config:<name>")  # for each configured p
                        [with that configuration's wavelength_points when set]

Validation, bounds, enums, consistency groups, and defaults therefore all run
per configuration inside the existing ``ParameterSet.resolve()`` — there is no
second resolution engine and ``radiant.core`` is not modified.

Optical elements (Gap 103 v1.1, owner-ratified 2026-09-02 in live review) follow
the *same* model rather than a parallel one: a **row** of the shared
``optical_elements`` document can be **configured**, and then carries one
complete entry per configuration — dense, every member present, exactly like a
configured parameter's value list. Row identity is **positional**: the row count
and order are shared by every configuration, and the entry's ``name`` configures
with the row. The single-store invariant holds by construction — a configured
row's entries live only in the per-configuration table, never also in the base's
shared document (:meth:`ConfigurationSet.configure_element`).

Persistence (ADR-0010 D-D) is one file per study: the shared base serialized
exactly as ``Sensor.save`` writes it — with each configured element row written
in place as ``- configured: {member: entry, ...}``
(:mod:`radiant.io.configured_elements`) — plus a ``configurations:`` structured
section carrying names, active/baseline, per-configuration ``wavelength_points``
and the configured table (:mod:`radiant.io.config_set_section`). A config file
with no section is byte-for-byte today's format, and loading a section-bearing
file through bare ``Sensor.load`` raises with a "load it with
``ConfigurationSet.load``" message rather than dropping the study.

Example::

    from radiant.api import ConfigurationSet, Sensor

    cs = ConfigurationSet(Sensor.from_yaml("examples/mwir_leo_minimal.yaml"),
                          names=["MWIR", "LWIR"])
    cs.configure("spectral_integration.filter_min_um", [3.95, 8.0])
    cs.configure("spectral_integration.filter_max_um", [4.45, 12.0])
    run = cs.evaluate_all()
    print(cs.compare(run).to_table())
"""

from __future__ import annotations

import copy as _copy
import logging
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar

from radiant.api._param_registry import build_parameter_set
from radiant.api._progress import CancelFn, ProgressFn, check_cancel
from radiant.api._warning_capture import capture_warnings
from radiant.api.compare import ComparisonResult, compare_configs
from radiant.api.config_io import normalize_element_document
from radiant.api.sensor import Sensor
from radiant.core.exceptions import RadiantError
from radiant.core.parameters import ParameterSet, Provenance
from radiant.io.config import ConfigError
from radiant.io.config_set_section import (
    SECTION_KEY,
    ConfigurationsSection,
    parse_configurations_section,
    serialize_configurations_section,
)
from radiant.io.configured_elements import (
    ElementDocument,
    configured_rows_need_a_configuration_set,
    merge_element_document,
    resolve_element_document,
    split_element_document,
)
from radiant.io.results import ChainResult

logger = logging.getLogger(__name__)

__all__ = ["ConfigRun", "ConfigSetError", "ConfigSetRunResult", "ConfigurationSet"]

# Name given to the single configuration of a freshly built set.
_DEFAULT_NAME = "Configuration 1"

# Metrics shown, in this order, on a :meth:`ConfigSetRunResult.summary` line.
# Deliberately short — a summary is a triage line, not the comparison matrix
# (that is :meth:`ConfigurationSet.compare`). A metric a configuration did not
# compute is omitted from its line, never zero-filled (Rule 17). Units are read
# from the metric registry via ``ChainResult.metric_records()``, never spelled
# out here, so a registry unit change cannot desynchronize this rendering.
_HEADLINE_METRICS: tuple[str, ...] = ("snr", "nedt_K", "niirs", "gsd_geometric_mean_m")


def _format_warning(record: warnings.WarningMessage) -> str:
    """One captured warning as a single display string (category + message).

    Matches the format the GUI evaluation worker
    (``radiant.gui.workers._format_warning``) already shows in its warning
    strip, so a warning reads identically whether it reached the user through
    a single-sensor GUI run or through :meth:`ConfigurationSet.evaluate_all`.
    """
    return f"{record.category.__name__}: {record.message}"


class ConfigSetError(RadiantError):
    """A configuration set rejected an operation or a configured value.

    Follows the Rule 15 actionable-error contract: carries a structured
    ``what / why / action / context`` payload so the CLI and GUI can render
    each field independently. Every error raised on behalf of one
    configuration names that configuration in ``what`` and in
    ``context["configuration"]``.

    Inherits :class:`~radiant.core.exceptions.RadiantError` only (no
    built-in co-inheritance) — the recommendation for new error classes.
    """

    def __init__(
        self,
        what: str,
        why: str = "",
        action: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        self.what: str = what
        self.why: str = why
        self.action: str = action
        self.context: dict[str, Any] = dict(context) if context is not None else {}

        parts: list[str] = [what]
        if why:
            parts.append(f"Why: {why}")
        if action:
            parts.append(f"Action: {action}")
        super().__init__(" | ".join(parts))


@dataclass(frozen=True)
class ConfigRun:
    """One configuration's outcome from :meth:`ConfigurationSet.evaluate_all`.

    Exactly one of *result* / *error* is populated (Rule 17: a failed
    configuration is recorded data, never a silent drop or a zero-fill).

    Attributes
    ----------
    name:
        The configuration this outcome belongs to.
    result:
        The completed :class:`~radiant.io.results.ChainResult`, or ``None``
        when this configuration failed.
    error:
        The recorded :class:`~radiant.core.exceptions.RadiantError`, or
        ``None`` when this configuration succeeded.
    warnings:
        Python warnings raised **while this configuration evaluated**, each
        formatted ``"<Category>: <message>"``. Attribution is exact: the
        capture window opens and closes around one configuration's
        materialization + ``evaluate()``, so a warning raised by
        configuration X appears on X's entry and on no other. Present (and
        possibly non-empty) on failed configurations too — a chain often
        warns before it raises.
    """

    name: str
    result: ChainResult | None
    error: RadiantError | None
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """True when this configuration evaluated successfully."""
        return self.error is None


@dataclass(frozen=True)
class ConfigSetRunResult:
    """Result of evaluating every configuration in a set.

    Attributes
    ----------
    entries:
        One :class:`ConfigRun` per configuration, in **evaluation order** —
        the active configuration first, then the remaining configurations in
        set order (so a GUI's displayed views refresh first).
    baseline:
        The set's baseline configuration name at evaluation time; the delta
        reference :meth:`ConfigurationSet.compare` uses.
    """

    entries: tuple[ConfigRun, ...]
    baseline: str

    @property
    def names(self) -> tuple[str, ...]:
        """Configuration names in evaluation order (active first)."""
        return tuple(entry.name for entry in self.entries)

    @property
    def n_failed(self) -> int:
        """Number of configurations whose evaluation raised a ``RadiantError``."""
        return sum(1 for entry in self.entries if entry.error is not None)

    @property
    def failures(self) -> dict[str, RadiantError]:
        """Configuration name → the error it failed with (empty when all passed)."""
        return {e.name: e.error for e in self.entries if e.error is not None}

    @property
    def warnings(self) -> dict[str, tuple[str, ...]]:
        """Configuration name → the warnings raised while it evaluated.

        Only configurations that warned appear (an empty dict means the whole
        pass was quiet). Each configuration's warnings are exactly the ones
        its own evaluation raised — see :attr:`ConfigRun.warnings`.
        """
        return {e.name: e.warnings for e in self.entries if e.warnings}

    @property
    def n_warnings(self) -> int:
        """Total number of warnings captured across every configuration."""
        return sum(len(e.warnings) for e in self.entries)

    def entry_for(self, name: str) -> ConfigRun:
        """The :class:`ConfigRun` for configuration *name*.

        Raises :class:`ConfigSetError` when the run holds no such
        configuration (e.g. the set was edited after the run).
        """
        for entry in self.entries:
            if entry.name == name:
                return entry
        raise ConfigSetError(
            what=f"this run holds no configuration named {name!r}",
            why=f"the run covers {list(self.names)}",
            action="Re-run evaluate_all() after editing the set, or ask for one of "
            f"{list(self.names)}.",
            context={"configuration": name, "available": list(self.names)},
        )

    def result_for(self, name: str) -> ChainResult:
        """The :class:`~radiant.io.results.ChainResult` for configuration *name*.

        Raises :class:`ConfigSetError` when that configuration failed — its
        recorded error is chained so the physics cause is never lost.
        """
        entry = self.entry_for(name)
        if entry.result is None:
            raise ConfigSetError(
                what=f"configuration {name!r} has no result — its evaluation failed",
                why=str(entry.error),
                action=f"Fix the parameters of configuration {name!r}, or read "
                "`run.failures` to inspect the recorded error.",
                context={"configuration": name},
            ) from entry.error
        return entry.result

    def summary(self) -> str:
        """A plain-text triage view of the pass — one line per configuration.

        Lines follow **evaluation order** (active configuration first), which
        is the order :attr:`entries` holds. Each line is::

            <name>  ok      snr = 964.8 [dimensionless]; nedt_K = 0.0289 [K]   (1 warning)
            <name>  FAILED  <the error's what-line>

        Every number carries the unit the metric registry declares for it
        (project hard rule: no bare numbers in output). A headline metric a
        configuration did not compute is simply absent from its line — never
        shown as zero (Rule 17). Failed configurations show their error's
        ``what`` line; the full error stays in :attr:`failures`. Warnings are
        counted, not quoted — :attr:`warnings` holds their text.

        This is a summary, not the comparison surface: for aligned metric ×
        configuration values with deltas use
        :meth:`ConfigurationSet.compare`.
        """
        width = max((len(e.name) for e in self.entries), default=0)
        lines: list[str] = []
        for entry in self.entries:
            note = ""
            if entry.warnings:
                n = len(entry.warnings)
                note = f"   ({n} warning{'s' if n != 1 else ''})"
            if entry.error is not None:
                what = getattr(entry.error, "what", None) or str(entry.error)
                body = f"FAILED  {what}"
            elif entry.result is None:
                # Not reachable through evaluate_all (which always records one
                # or the other); a hand-built ConfigRun says so rather than
                # rendering an empty metric line.
                body = "ok      (no result recorded)"
            else:
                body = f"ok      {_headline(entry.result)}"
            marker = " *" if entry.name == self.baseline else "  "
            lines.append(f"{entry.name.ljust(width)}{marker}  {body}{note}")
        lines.append(
            f"(* = baseline: {self.baseline!r}; {self.n_failed} of "
            f"{len(self.entries)} configuration(s) failed)"
        )
        return "\n".join(lines)


def _headline(result: ChainResult) -> str:
    """Headline metrics of one result as ``name = value [unit]``, semicolon-joined.

    Reads units from the result's own metric records, so every rendered number
    carries the registry's unit for that metric. A configuration missing a
    headline metric contributes nothing for it (Rule 17 — absent, not zero).
    """
    records = {rec.name: rec for rec in result.metric_records()}
    parts = [
        f"{name} = {records[name].value:.4g} [{records[name].unit}]"
        for name in _HEADLINE_METRICS
        if name in records
    ]
    if not parts:
        return f"no headline metric computed ({len(records)} metric(s) available)"
    return "; ".join(parts)


class ConfigurationSet:
    """Up to eight named configurations of one modeling problem (ADR-0010).

    Parameters
    ----------
    base:
        The shared :class:`~radiant.api.sensor.Sensor`. It is **owned** by the
        set: every parameter that is not configured lives in it with one value
        for all configurations, and editing it (``cs.base.set(...)``) edits the
        shared value. Not copied on construction — pass ``sensor.clone()`` if
        the caller wants to keep an independent handle.
    names:
        Ordered, unique configuration names (1 … :attr:`MAX_CONFIGS`).
        Defaults to a single ``"Configuration 1"``, which makes the set
        observably identical to the bare *base* sensor.

    Notes
    -----
    A set with one configuration and an empty configured table behaves exactly
    like a bare ``Sensor`` — that degenerate case is today's single-model app.
    """

    MAX_CONFIGS: ClassVar[int] = 8

    def __init__(self, base: Sensor, names: Sequence[str] | None = None) -> None:
        if not isinstance(base, Sensor):
            raise ConfigSetError(
                what=f"ConfigurationSet base must be a Sensor, got {type(base).__name__}",
                why="the base holds the shared parameters every configuration starts from",
                action="Pass a Sensor, e.g. ConfigurationSet(Sensor.from_yaml(path)).",
            )
        chosen = tuple(names) if names is not None else (_DEFAULT_NAME,)
        self._check_name_list(chosen)
        self._base: Sensor = base
        self._names: list[str] = list(chosen)
        self._configured: dict[str, tuple[Any, ...]] = {}
        # Configured element rows: position in the FULL element document ->
        # configuration name -> that configuration's complete entry (dense).
        # The shared rows stay on the base sensor's document; a configured row
        # is absent from it (single store).
        self._element_rows: dict[int, dict[str, dict[str, Any]]] = {}
        self._wl_points: dict[str, int] = {}
        self._shared_wl_points: int | None = None
        self._baseline: str = self._names[0]
        self._active: str = self._names[0]

    def __repr__(self) -> str:
        return (
            f"ConfigurationSet(names={self._names!r}, configured="
            f"{sorted(self._configured)!r}, active={self._active!r}, "
            f"baseline={self._baseline!r})"
        )

    # ------------------------------------------------------------------
    # Shared base and membership
    # ------------------------------------------------------------------

    @property
    def base(self) -> Sensor:
        """The shared base sensor (owned, not a copy — edits land on the set)."""
        return self._base

    def names(self) -> tuple[str, ...]:
        """Configuration names in set order."""
        return tuple(self._names)

    def __len__(self) -> int:
        return len(self._names)

    def __contains__(self, name: object) -> bool:
        return name in self._names

    @property
    def baseline(self) -> str:
        """The delta-reference configuration used by :meth:`compare`."""
        return self._baseline

    @baseline.setter
    def baseline(self, name: str) -> None:
        self._index(name, "baseline")
        self._baseline = name

    @property
    def active(self) -> str:
        """The displayed configuration (GUI state; evaluated first)."""
        return self._active

    @active.setter
    def active(self, name: str) -> None:
        self._index(name, "active")
        self._active = name

    def clone(self) -> ConfigurationSet:
        """Return an independent copy of this set — base, table, and designations.

        The copy owns ``base.clone()``, its own configured table, its own
        wavelength-point overrides, its own configured element rows, and the same
        ``active`` / ``baseline`` designations. Nothing is shared: editing either
        set afterwards leaves the other untouched.

        This is the set-level counterpart of :meth:`Sensor.clone` and exists for
        the same reason — **thread isolation**. The GUI hands its evaluation
        worker a private snapshot taken on the GUI thread, so a parameter edit
        that lands mid-run cannot race the worker's read of the same object.
        Hand-rolling a snapshot out of the public accessors is possible but not
        equivalent: it would have to re-apply the configured table, both kinds of
        ``wavelength_points`` state (:meth:`wavelength_points`), and both
        designations without dropping one, and a copy that missed the spectral
        overrides would silently evaluate a loaded study on the wrong grid.
        """
        copy = ConfigurationSet(self._base.clone(), names=tuple(self._names))
        copy._configured = dict(self._configured)
        copy._element_rows = _copy.deepcopy(self._element_rows)
        copy._wl_points = dict(self._wl_points)
        copy._shared_wl_points = self._shared_wl_points
        copy._baseline = self._baseline
        copy._active = self._active
        return copy

    # ------------------------------------------------------------------
    # Configuration CRUD
    # ------------------------------------------------------------------

    def add(self, name: str, *, copy_from: str | None = None) -> None:
        """Append a configuration named *name*.

        Every configured parameter **and every configured element row** gains an
        entry in the new configuration (density, D-A): copied from *copy_from*
        when given — the duplicate route — otherwise from the **first**
        configuration, matching the D-6 "configuration #1 is the reference"
        convention.

        The wavelength-point override is the one piece of per-configuration state
        that is *not* dense: it is copied from *copy_from* when it has one, and is
        otherwise absent, so the new configuration inherits the shared grid. That
        asymmetry is the model's, not an omission — a configured parameter or a
        configured element row has no shared value to fall back on, while an
        un-overridden grid density does.
        """
        self._check_name(name)
        if name in self._names:
            raise ConfigSetError(
                what=f"a configuration named {name!r} already exists",
                why="configuration names are the user-visible identity of a column and "
                "must be unique",
                action=f"Pick a different name, or rename the existing {name!r} first.",
                context={"configuration": name, "existing": list(self._names)},
            )
        if len(self._names) >= self.MAX_CONFIGS:
            raise ConfigSetError(
                what=f"cannot add configuration {name!r}: the set already holds "
                f"{len(self._names)} of at most {self.MAX_CONFIGS}",
                why=f"a set is capped at {self.MAX_CONFIGS} configurations so the always-on "
                "evaluate-all pass and the side-by-side comparison stay bounded (ADR-0010 D-E)",
                action="Remove a configuration you no longer need, or split the study "
                "into two sets.",
                context={
                    "configuration": name,
                    "count": len(self._names),
                    "max": self.MAX_CONFIGS,
                },
            )
        seed_index = 0 if copy_from is None else self._index(copy_from, "add")
        seed_name = self._names[seed_index]
        self._names.append(name)
        for dotpath, values in list(self._configured.items()):
            self._configured[dotpath] = (*values, values[seed_index])
        for entries in self._element_rows.values():
            entries[name] = _copy.deepcopy(entries[seed_name])
        if copy_from is not None and copy_from in self._wl_points:
            self._wl_points[name] = self._wl_points[copy_from]

    def remove(self, name: str) -> None:
        """Remove configuration *name* and drop its column of configured values.

        The last remaining configuration cannot be removed (a set always holds
        at least one). Removing the active or baseline configuration reassigns
        that designation to the first remaining configuration.
        """
        index = self._index(name, "remove")
        if len(self._names) == 1:
            raise ConfigSetError(
                what=f"cannot remove {name!r}: it is the only configuration in the set",
                why="a configuration set always holds at least one configuration — the "
                "single-configuration set is the ordinary single-model session",
                action="Add another configuration first, or discard the whole set.",
                context={"configuration": name},
            )
        del self._names[index]
        for dotpath, values in list(self._configured.items()):
            self._configured[dotpath] = values[:index] + values[index + 1 :]
        for entries in self._element_rows.values():
            entries.pop(name, None)
        self._wl_points.pop(name, None)
        if self._active == name:
            self._active = self._names[0]
        if self._baseline == name:
            self._baseline = self._names[0]

    def rename(self, old: str, new: str) -> None:
        """Rename configuration *old* to *new*, keeping its position and values."""
        index = self._index(old, "rename")
        self._check_name(new)
        if new != old and new in self._names:
            raise ConfigSetError(
                what=f"cannot rename {old!r} to {new!r}: that name is already taken",
                why="configuration names must be unique within a set",
                action=f"Pick a name not in {list(self._names)}.",
                context={"configuration": old, "new": new, "existing": list(self._names)},
            )
        self._names[index] = new
        for row, entries in list(self._element_rows.items()):
            # Re-key, keeping the entries in names() order (D-A alignment).
            self._element_rows[row] = {
                member: entries[old] if member == new else entries[member] for member in self._names
            }
        if old in self._wl_points:
            self._wl_points[new] = self._wl_points.pop(old)
        if self._active == old:
            self._active = new
        if self._baseline == old:
            self._baseline = new

    def reorder(self, names: Sequence[str]) -> None:
        """Reorder the configurations; *names* must be a permutation of the current ones.

        Every configured parameter's value column is permuted with the names, so
        value/configuration alignment is preserved. Configured element rows are
        keyed by configuration name, so they need only re-ordering to match.
        """
        wanted = list(names)
        if sorted(wanted) != sorted(self._names):
            raise ConfigSetError(
                what=f"reorder needs a permutation of the current configurations, got {wanted}",
                why="reordering may not add, drop, or rename configurations — it only "
                "changes their order (values move with their names)",
                action=f"Pass exactly {list(self._names)} in the desired order; use "
                "add()/remove()/rename() to change membership.",
                context={"requested": wanted, "existing": list(self._names)},
            )
        permutation = [self._names.index(name) for name in wanted]
        self._names = wanted
        for dotpath, values in list(self._configured.items()):
            self._configured[dotpath] = tuple(values[i] for i in permutation)
        for row, entries in list(self._element_rows.items()):
            self._element_rows[row] = {member: entries[member] for member in wanted}

    # ------------------------------------------------------------------
    # Configured parameters
    # ------------------------------------------------------------------

    def configured(self) -> Mapping[str, tuple[Any, ...]]:
        """Read-only view of the configured table: dot-path → one value per configuration.

        Values are in the parameter's **input units**, aligned with
        :meth:`names` order.
        """
        return MappingProxyType(self._configured)

    def is_configured(self, dotpath: str) -> bool:
        """True when *dotpath* carries one value per configuration."""
        return self._canonical(dotpath) in self._configured

    def configure(
        self,
        dotpath: str,
        values: Sequence[Any] | None = None,
        *,
        unit: str | None = None,
    ) -> None:
        """Promote *dotpath* to a configured parameter (one value per configuration).

        With *values*, they are used directly (length must equal the number of
        configurations — dense, never padded). Without, all configurations are
        seeded from the parameter's current **shared** value: the base's
        explicit input when it has one, otherwise its resolved default.

        With ``unit``, **every** supplied value is read in the caller's unit and
        converted at this boundary (Rule 2), exactly as :meth:`set_values` does;
        one unit applies to the whole column, because a configured parameter has
        one schema entry and therefore one dimension. It is only meaningful
        alongside explicit *values* — a seeded column is already in input units —
        and passing it without them is refused rather than silently ignored.
        This is what lets a caller promote a parameter **and** set its
        per-configuration values in one atomic call, in whatever unit the user
        typed (the GUI's *Configure across configurations…* flow, §4.2c).

        Every seeded or supplied value is validated through the schema
        immediately (type, bounds, enum — the same checks ``Sensor.set``
        values face at resolve time), so an out-of-bounds configured value is
        rejected at edit time with the offending configuration named.

        The single-store invariant (ADR-0010 D-B) is enforced by *moving* the
        parameter: its explicit input is removed from the base, so it can
        never be in both stores.
        """
        name = self._canonical(dotpath)
        if name in self._configured:
            raise ConfigSetError(
                what=f"parameter {name!r} is already configured",
                why="a configured parameter already carries one value per configuration",
                action=f"Use set_values({name!r}, ...) to change its values, or "
                f"unconfigure({name!r}) first.",
                context={"param": name},
            )
        if values is None:
            if unit is not None:
                raise ConfigSetError(
                    what=f"configure({name!r}, unit={unit!r}) was given a unit but no values",
                    why="a seeded column is taken from the parameter's current shared "
                    "value, which is already in its input unit — there is nothing to "
                    "convert",
                    action=f"Pass the values you mean, e.g. configure({name!r}, "
                    f"[...], unit={unit!r}), or drop the unit to seed from the "
                    "shared value.",
                    context={"param": name, "unit": unit},
                )
            seed = self._shared_seed(name)
            column = [seed] * len(self._names)
        else:
            column = list(values)
            self._check_column_length(name, column)
        validated = tuple(
            self._validated(name, value, config, unit=unit)
            for value, config in zip(column, self._names, strict=True)
        )
        # Move, never copy: clearing the base input is what makes the
        # single-store invariant unrepresentable-to-violate through the API.
        self._base.reset(name)
        self._configured[name] = validated

    def unconfigure(self, dotpath: str, *, keep: str | None = None) -> None:
        """Collapse a configured parameter back to a single shared value.

        *keep* names the configuration whose value survives as the shared
        value. The default — and what the GUI uses — is **configuration #1**
        (ADR-0010 D-6); ``keep=<name>`` is a scripting-only override.
        """
        name = self._canonical(dotpath)
        if name not in self._configured:
            raise ConfigSetError(
                what=f"parameter {name!r} is not configured",
                why="only a configured parameter (one value per configuration) can be "
                "collapsed back to a shared value",
                action=f"Configured parameters are {sorted(self._configured)}.",
                context={"param": name, "configured": sorted(self._configured)},
            )
        index = 0 if keep is None else self._index(keep, "unconfigure")
        kept = self._configured.pop(name)[index]
        self._base.set(name, kept)

    def set_value(
        self,
        dotpath: str,
        config: str,
        value: Any,
        *,
        unit: str | None = None,
    ) -> None:
        """Set one configuration's value of a configured parameter.

        With ``unit``, *value* is converted from the caller's native unit at
        this boundary (Rule 2), exactly as ``Sensor.set(..., unit=...)`` does;
        the stored value is always in the parameter's input unit.
        """
        name = self._require_configured(dotpath, "set_value")
        index = self._index(config, "set_value")
        validated = self._validated(name, value, config, unit=unit)
        column = list(self._configured[name])
        column[index] = validated
        self._configured[name] = tuple(column)

    def set_values(
        self,
        dotpath: str,
        values: Sequence[Any],
        *,
        unit: str | None = None,
    ) -> None:
        """Replace every configuration's value of a configured parameter.

        *values* must have one entry per configuration, in :meth:`names` order.

        With ``unit``, **every** supplied value is read in the caller's unit and
        converted at this boundary (Rule 2), exactly as
        :meth:`set_value` and ``Sensor.set(..., unit=...)`` do; one unit applies
        to the whole column, because a configured parameter has one schema entry
        and therefore one dimension. The stored values are always in the
        parameter's input unit, so :meth:`configured` reads back in input units
        whatever unit was typed.

        Whole-column atomicity holds with or without ``unit``: every value is
        validated (and converted) *before* the column is replaced, so a rejected
        value leaves the set exactly as it was — never half-written.
        """
        name = self._require_configured(dotpath, "set_values")
        column = list(values)
        self._check_column_length(name, column)
        self._configured[name] = tuple(
            self._validated(name, value, config, unit=unit)
            for value, config in zip(column, self._names, strict=True)
        )

    # ------------------------------------------------------------------
    # Spectral grid
    # ------------------------------------------------------------------

    def wavelength_points(self, config: str | None = None) -> int | None:
        """Read the spectral grid point count — the shared default or one override.

        Mirrors :meth:`set_wavelength_points`'s argument shape (CU-210):

        * ``config=None`` returns the **shared default in force** — the set-level
          default when one was set, otherwise the base sensor's own point count.
          Always an ``int``: some grid density is always in force.
        * ``config=<name>`` returns that configuration's **override**, or ``None``
          when it carries none and therefore uses the shared default. The
          ``None`` is the distinction a display surface needs — "inherits" is not
          the same statement as "happens to equal the default".

        Raises :class:`ConfigSetError` when *config* names no configuration.
        """
        if config is None:
            if self._shared_wl_points is not None:
                return self._shared_wl_points
            return self._base.wavelength_points
        self._index(config, "wavelength_points")
        return self._wl_points.get(config)

    def set_wavelength_points(self, config: str | None, n: int | None) -> None:
        """Set (or clear) the spectral grid point count for one configuration.

        ``config=None`` sets the default every configuration without its own
        override uses; a name sets that configuration's override. The grid
        *span* is already per configuration for free — each materialized
        sensor spans its own resolved ``filter_min_um``/``filter_max_um``
        (ADR-0010 D-F).

        ``n=None`` **clears** rather than sets: a named configuration goes back to
        the shared default, and ``config=None, n=None`` drops the set-level
        default so the base sensor's own point count is the shared default again.
        Clearing exists because the setting is user-editable and every editable
        setting needs a way back — without it, an undone edit could not restore an
        override that was not there before.

        Read the current state back with :meth:`wavelength_points`.
        """
        if n is None:
            if config is None:
                self._shared_wl_points = None
            else:
                self._index(config, "set_wavelength_points")
                self._wl_points.pop(config, None)
            return
        if not isinstance(n, int) or isinstance(n, bool) or n < 2:
            raise ConfigSetError(
                what=f"wavelength_points must be an integer >= 2, got {n!r}",
                why="the spectral evaluation grid needs at least two points to span a band",
                action="Pass an integer >= 2 (the RADIANT default is 500).",
                context={"configuration": config, "value": n},
            )
        if config is None:
            self._shared_wl_points = n
            return
        self._index(config, "set_wavelength_points")
        self._wl_points[config] = n

    # ------------------------------------------------------------------
    # Configured optical-element rows (Gap 103 v1.1)
    # ------------------------------------------------------------------

    def element_count(self) -> int:
        """Number of rows in the shared element document (shared + configured).

        ``0`` when the base carries no ``optical_elements`` document. The row
        count and row order are shared by every configuration — configuring a
        row changes *what is at that position*, never how many positions there
        are — so this is the index domain of every ``*_element`` method.
        """
        return len(self._shared_element_rows()) + len(self._element_rows)

    def configured_element_indices(self) -> tuple[int, ...]:
        """Positions of the configured element rows, ascending."""
        return tuple(sorted(self._element_rows))

    def is_element_configured(self, index: int) -> bool:
        """True when element row *index* carries one entry per configuration."""
        return self._element_index(index, "is_element_configured") in self._element_rows

    def configure_element(self, index: int) -> None:
        """Promote element row *index* to a configured row (one entry per configuration).

        Every configuration is seeded with a copy of the row's current **shared**
        entry, so the promotion changes no result — exactly what
        :meth:`configure` does for a parameter with no explicit values. Edit one
        configuration's entry afterwards with :meth:`set_element_for`.

        The single-store invariant (the element analog of ADR-0010 D-B) is
        enforced by *moving* the row: its entry is removed from the base
        sensor's shared document, so a row is shared **or** configured and can
        never be both. Row identity is **positional**: the entry's ``name``
        moves into the per-configuration table with the rest of the entry, so a
        configuration may name this row differently (owner-ratified 2026-09-02).

        Raises :class:`ConfigSetError` when the base has no element document,
        when *index* is not a row of it, or when the row is already configured.
        """
        position = self._element_index(index, "configure_element")
        if position in self._element_rows:
            raise ConfigSetError(
                what=f"element row {position} is already configured",
                why="a configured row already carries one complete entry per configuration",
                action=f"Edit a configuration's entry with set_element_for({position}, config, "
                f"entry), or unconfigure_element({position}) first.",
                context={"element_row": position},
            )
        shared = self._shared_element_rows()
        entry = shared.pop(self._shared_position(position))
        self._store_shared_element_rows(shared)
        self._element_rows[position] = {name: _copy.deepcopy(entry) for name in self._names}

    def unconfigure_element(self, index: int, *, keep: str | None = None) -> None:
        """Collapse a configured element row back to one shared entry.

        *keep* names the configuration whose entry survives as the shared entry.
        The default — and what the GUI uses — is **configuration #1** (ADR-0010
        D-6, the same convention :meth:`unconfigure` follows); ``keep=<name>`` is
        a scripting-only override. The row returns to the base document at its
        own position, so the document's length and order are unchanged.
        """
        position = self._require_configured_element(index, "unconfigure_element")
        member = (
            self._names[0]
            if keep is None
            else self._names[self._index(keep, "unconfigure_element")]
        )
        kept = self._element_rows[position][member]
        shared = self._shared_element_rows()
        slot = self._shared_position(position)
        del self._element_rows[position]
        shared.insert(slot, kept)
        self._store_shared_element_rows(shared)

    def element_for(self, index: int, config: str) -> dict[str, Any]:
        """Configuration *config*'s complete entry for configured row *index* (a copy).

        Raises :class:`ConfigSetError` when the row is not configured — a shared
        row has one entry, read from ``cs.base.optical_elements()`` — or when
        *config* names no configuration.
        """
        position = self._require_configured_element(index, "element_for")
        self._index(config, "element_for")
        return _copy.deepcopy(self._element_rows[position][config])

    def set_element_for(
        self,
        index: int,
        config: str,
        entry: Mapping[str, Any],
        *,
        base_dir: str | Path | None = None,
    ) -> None:
        """Set one configuration's entry of configured element row *index*.

        *entry* is a **complete** element entry — the same entry dict the
        ``optical_elements:`` document carries — not a patch: there is no
        field-level merge, so no patch-resolution semantics (the reason
        ADR-0010 D-A rejected sparse overlays for parameters applies here).

        The entry is validated immediately through the io element parser — the
        single validation authority, Kirchhoff included (Rule 5) — and
        normalized, so relative spectral-file references under *base_dir*
        (default: the current directory, as ``Sensor.set_optical_elements``)
        become absolute and the stored entry survives a save from any directory.
        A rejected entry stores nothing.
        """
        position = self._require_configured_element(index, "set_element_for")
        self._index(config, "set_element_for")
        try:
            normalized = normalize_element_document([dict(entry)], base_dir=base_dir)
        except RadiantError as exc:
            raise ConfigSetError(
                what=f"configuration {config!r}: element row {position} is not a valid "
                "optical-element entry",
                why=str(exc),
                action=f"Fix the entry and set it again; configuration {config!r} keeps the "
                "entry it had until the new one validates.",
                context={"configuration": config, "element_row": position},
            ) from exc
        self._element_rows[position][config] = normalized[0]

    def effective_optical_elements(self, name: str) -> list[dict[str, Any]] | None:
        """The element document configuration *name* actually evaluates with.

        The shared document in document order, with every configured row
        resolved to this configuration's entry — what :meth:`sensor_for`
        attaches. ``None`` when the set carries no element document at all.

        The read surface a display layer needs: rendering a configuration's
        train must not go through :meth:`sensor_for`, which resolves the whole
        parameter set and can raise for reasons that have nothing to do with the
        optics.

        Raises :class:`ConfigSetError` when the base's shared document was
        replaced behind the set's back (``cs.base.set_optical_elements(...)``)
        by a shorter one, leaving a configured row with no position — reachable
        only that way, exactly like the parameter-store clash
        :meth:`sensor_for` checks. Evaluating a train the study does not
        describe would be a silent failure (Rule 17).
        """
        self._index(name, "effective_optical_elements")
        self._check_element_positions(name)
        shared = self._shared_element_rows()
        if not shared and not self._element_rows:
            return None
        return resolve_element_document(shared, self._element_rows, name)

    # ------------------------------------------------------------------
    # Materialization and evaluation
    # ------------------------------------------------------------------

    def sensor_for(self, name: str) -> Sensor:
        """Materialize configuration *name* as an isolated :class:`Sensor`.

        The returned sensor is ``base.clone()`` with this configuration's
        configured values applied (provenance ``source="config:<name>"``, so
        ``resolved()``/``explain()`` name the owning configuration) and its
        wavelength point count in force. It is fully independent: later edits
        to the set do not reach it, and edits to it do not reach the set.

        When the set carries configured element rows, this configuration's
        :meth:`effective_optical_elements` document is attached through the
        ordinary ``Sensor.set_optical_elements`` — the one attachment path, so
        the resolved train is parsed, injected, and persisted exactly as a
        shared one. With no configured row the cloned base's document (which is
        then the whole train) is left untouched.

        The parameter set is resolved here, so an over-constrained consistency
        group or an unsatisfiable requirement inside this configuration raises
        a :class:`ConfigSetError` naming the configuration, chained to the
        underlying actionable error.
        """
        index = self._index(name, "sensor_for")
        self._check_single_store(name)
        n_points = self._wl_points.get(name, self._shared_wl_points)
        sensor = (
            self._base.clone() if n_points is None else self._base.with_wavelength_points(n_points)
        )
        for dotpath, values in self._configured.items():
            sensor.set(dotpath, values[index], source=f"config:{name}")
        if self._element_rows:
            effective = self.effective_optical_elements(name)
            try:
                sensor.set_optical_elements(effective)
            except RadiantError as exc:
                raise ConfigSetError(
                    what=f"configuration {name!r}: its optical-element train does not attach",
                    why=str(exc),
                    action=f"Fix the entry of configuration {name!r} on the offending row "
                    f"(cs.set_element_for(row, {name!r}, entry)), or unconfigure the row to go "
                    "back to one shared entry.",
                    context={"configuration": name},
                ) from exc
        try:
            sensor.resolve()
        except RadiantError as exc:
            raise ConfigSetError(
                what=f"configuration {name!r} does not resolve",
                why=str(exc),
                action=f"Fix the parameters of configuration {name!r} — configured values "
                f"are {sorted(self._configured)}, everything else is shared on the base.",
                context={"configuration": name},
            ) from exc
        return sensor

    def validate_all(self) -> dict[str, RadiantError | None]:
        """Resolve every configuration and report per-configuration status.

        Resolution only — no physics runs. Returns a dict in set order mapping
        each configuration name to ``None`` (resolves cleanly) or the
        :class:`~radiant.core.exceptions.RadiantError` it fails with, so a GUI
        can show a per-row status without any configuration's failure hiding
        another's.

        Because it goes through :meth:`sensor_for`, each configuration's
        **effective** optical-element document is attached and parsed here too:
        a configuration whose entry on a configured row no longer parses, or
        whose configured rows no longer have positions in the base's shared
        document, reports under its own name.
        """
        status: dict[str, RadiantError | None] = {}
        for name in self._names:
            try:
                self.sensor_for(name)
            except RadiantError as exc:
                status[name] = exc
            else:
                status[name] = None
        return status

    def evaluate_all(
        self,
        *,
        progress: ProgressFn | None = None,
        cancel: CancelFn | None = None,
    ) -> ConfigSetRunResult:
        """Evaluate every configuration, active first.

        Evaluation order is the **active** configuration followed by the
        remaining configurations in set order, so a GUI's displayed views
        refresh at single-model latency. A configuration whose evaluation
        raises a :class:`~radiant.core.exceptions.RadiantError` becomes a
        recorded failure (Rule 17 — never dropped, never zero-filled) and the
        remaining configurations still run; any other exception is a
        programming bug and propagates.

        Warning capture and attribution
        -------------------------------
        Each configuration is evaluated inside its own
        :func:`~radiant.api._warning_capture.capture_warnings` window, and the
        warnings raised on **this thread** in that window are
        recorded on that configuration's :attr:`ConfigRun.warnings`. Because
        the window spans exactly one configuration's materialization and
        ``evaluate()``, **a warning raised by configuration X is attributed to
        X and to no other configuration** — which is the point: in a
        one-window-for-the-whole-pass design a saturation warning from the
        LWIR configuration would read as a property of the study.
        ``simplefilter("always")`` makes the capture independent of the
        ambient filter state (nothing is deduplicated away by the
        once-per-location registry, and a ``filterwarnings=error`` setting
        cannot convert a chain warning into an exception inside the window).

        **Captured warnings are not re-raised into the caller's warning
        filters.** They are recorded on the result *and* re-emitted to the
        logging machinery (``logger.warning``), so nothing is dropped: a
        script that ignores :attr:`ConfigRun.warnings` still sees them in the
        log, and a GUI reads them per configuration. This is not the Rule 17
        silent-failure pattern — that rule forbids *discarding* a signal
        (``except Exception: pass``, a warning logged and forgotten, a value
        clipped with no notice). Here the signal is promoted from a
        process-global side channel to named, per-configuration data on the
        object the caller already inspects, which is the same treatment
        :attr:`failures` gives errors. A caller that wants Python-level
        warnings instead can evaluate configurations itself via
        :meth:`sensor_for`.

        **Capture is thread-local (CU-110).** The capture list belongs to the
        calling thread, so two concurrent evaluations — the GUI main window's
        worker plus any of the sweep / solve / evaluate-all dialog workers,
        which are not serialised against it — each record only their own
        warnings, and a warning raised on a thread with no capture open still
        reaches the ambient ``showwarning`` handler instead of being swallowed
        into somebody else's window. The only process-global state left is the
        ``"always"`` filter action, which every concurrent capture wants
        identically and which is reference-counted under a lock, so one
        evaluation's exit can no longer clobber another's filter state. See
        :mod:`radiant.api._warning_capture`.

        Parameters
        ----------
        progress:
            ``progress(done, total)`` called after each configuration (Gap 72).
        cancel:
            ``cancel() -> bool`` polled before each configuration; True aborts
            with :class:`~radiant.api._progress.OperationCancelledError`.
        """
        order = self._evaluation_order()
        total = len(order)
        entries: list[ConfigRun] = []
        for done, name in enumerate(order):
            check_cancel(cancel, "ConfigurationSet.evaluate_all", done, total)
            entries.append(self._evaluate_one(name))
            if progress is not None:
                progress(done + 1, total)
        return ConfigSetRunResult(entries=tuple(entries), baseline=self._baseline)

    def _evaluate_one(self, name: str) -> ConfigRun:
        """Evaluate configuration *name*, capturing its warnings and its failure.

        The capture window is per configuration — that is what makes warning
        attribution exact (see :meth:`evaluate_all`).
        """
        result: ChainResult | None = None
        error: RadiantError | None = None
        with capture_warnings() as captured:
            try:
                result = self.sensor_for(name).evaluate()
            except RadiantError as exc:
                error = exc
            messages = tuple(_format_warning(record) for record in captured)
        # Outside the window, with the ambient filters restored: nothing that
        # was captured is dropped — every warning reaches the log as well as
        # the returned ConfigRun.
        for message in messages:
            logger.warning("Configuration %r warned: %s", name, message)
        if error is not None:
            logger.warning("Configuration %r failed to evaluate: %s", name, error)
        return ConfigRun(name=name, result=result, error=error, warnings=messages)

    def compare(self, run: ConfigSetRunResult) -> ComparisonResult:
        """Adapt a run into the :func:`~radiant.api.compare.compare_configs` matrix.

        Columns follow **set order** (not evaluation order), so the comparison
        is stable when the active configuration changes, and the delta
        reference is this set's :attr:`baseline`.

        Every configuration must have evaluated successfully: a failed one
        raises :class:`ConfigSetError` naming it rather than quietly losing a
        column (Rule 17). Fewer than two configurations raises the usual
        ``ComparisonError``.

        The rejected alternative was to drop failed configurations and compare
        the survivors. It was rejected because it silently breaks the
        column ↔ configuration correspondence this method promises:
        ``result.labels`` would no longer equal :meth:`names`, and a reader who
        did not check :attr:`ConfigSetRunResult.n_failed` would read a
        four-column matrix as the whole study. Raising keeps the failure in
        front of the caller, and the escape hatch is one line — call
        :func:`~radiant.api.compare.compare_configs` on the subset:
        ``compare_configs([(n, run.result_for(n)) for n in run.names if
        run.entry_for(n).ok])``. :meth:`ConfigSetRunResult.summary` renders a
        partially-failed pass without raising.
        """
        failed = [name for name in self._names if not run.entry_for(name).ok]
        if failed:
            raise ConfigSetError(
                what=f"cannot compare: configuration(s) {failed} failed to evaluate",
                why="a comparison matrix with a silently missing column would misreport the "
                "study (Rule 17)",
                action="Fix the failing configuration(s) and re-run evaluate_all(), or call "
                "compare_configs() directly on the subset you want to compare; "
                "`run.failures` holds each recorded error.",
                context={"configuration": failed[0], "failed": failed},
            )
        items = [(name, run.result_for(name)) for name in self._names]
        return compare_configs(items, baseline=self._names.index(self._baseline))

    # ------------------------------------------------------------------
    # Persistence (ADR-0010 D-D)
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> ConfigurationSet:
        """Load a configuration set from a config file written by :meth:`save`.

        The shared body loads exactly as ``Sensor.load`` loads it (parameters,
        tolerances, ``_radiant.wavelength_points``, the ``optical_elements``
        document); the ``configurations:`` section then supplies the names,
        ``active``/``baseline``, per-configuration ``wavelength_points``, and the
        configured table. An ``optical_elements`` document holding **configured
        rows** (``- configured: {member: entry, ...}``) is split here: its shared
        rows attach to the base, its configured rows become this set's
        per-configuration element table (:mod:`radiant.io.configured_elements`).

        A config file **without** the section is a valid input: it loads as the
        degenerate one-configuration set (named ``"Configuration 1"``), which is
        observably the bare ``Sensor`` it contains.

        Raises :class:`~radiant.io.config.ConfigError` — naming the config file,
        the configuration, and the parameter or element row — for every
        violation: a value list whose length is not the configuration count,
        duplicate or empty names, more than :attr:`MAX_CONFIGS` names, an unknown
        dot-path (with did-you-mean), a dot-path present in both the shared body
        and the section (ADR-0010 D-B), an ``active``/``baseline`` that names no
        member, any configured value the schema rejects, and any configured
        element row that is not dense over the configuration names, names a
        non-member, or holds an entry the io element parser rejects (Kirchhoff
        included).
        """
        src = Path(path)
        sections: dict[str, Any] = {}
        base = Sensor.load(src, sections_out=sections)
        raw = sections.get(SECTION_KEY)
        # Present only when the element document holds configured rows: a plain
        # document is attached by ``Sensor.load`` itself (api/sensor.py).
        raw_elements = sections.get("optical_elements")
        if raw is None:
            if raw_elements is not None:
                raise configured_rows_need_a_configuration_set(src)
            # Plain config file: the single-configuration set == the bare Sensor.
            return cls(base)
        section = parse_configurations_section(
            raw,
            build_parameter_set(),
            shared_inputs=base.inputs(),
            path=src,
            base_dir=src.parent,
            max_configurations=cls.MAX_CONFIGS,
        )
        element_doc: ElementDocument | None = None
        if raw_elements is not None:
            element_doc = split_element_document(
                raw_elements,
                member_names=section.names,
                path=src,
                base_dir=src.parent,
            )
            # The shared rows take the attach path they always take, so their
            # relative spectral-file references resolve against the config file's
            # own directory (CU-177); the configured entries were resolved by the
            # splitter for the same reason.
            base.set_optical_elements(list(element_doc.shared) or None, base_dir=src.parent)
        try:
            cs = cls(base, names=section.names)
            for dotpath, values in section.parameters.items():
                cs.configure(dotpath, values)
            for name, n_points in section.wavelength_points.items():
                cs.set_wavelength_points(name, n_points)
            if element_doc is not None:
                cs._element_rows = {
                    index: dict(entries) for index, entries in element_doc.configured.items()
                }
            cs.active = section.active
            cs.baseline = section.baseline
        except ConfigSetError as exc:
            # Surface a rejected configured value as a config-file error naming
            # the file, rather than as a bare model error (Rule 15).
            raise ConfigError(f"'{SECTION_KEY}' section: {exc}", path=src) from exc
        return cs

    def save(self, path: str | Path) -> Path:
        """Write this set to *path* as one study config file. Returns the path.

        The document is exactly what ``Sensor.save`` writes for the shared base —
        explicit inputs in input units, the ``_radiant`` meta block
        (``wavelength_points`` = the shared point count, tolerances), and the
        ``optical_elements`` document when one is attached — plus the
        ``configurations:`` section. A configured element row is written **in
        place**, at its own position in that document, as
        ``- configured: {member: entry, ...}``. :meth:`load` restores names and
        order, the configured table, ``active``/``baseline``, every wavelength
        point count, and every configured element row.

        The section is written even for a single-configuration set with an empty
        configured table: the file then differs from ``Sensor.save`` output by
        the section alone, and the configuration's **name** survives the round
        trip (omitting it would silently rename it on reload).

        ``is_file_path`` values inside the section — and the spectral-file
        references inside a configured element entry — are written relative to
        the destination directory, exactly like shared file-path values (CU-177).
        """
        out = Path(path)
        sensor, sections = self._output_document(relative_to=out.parent)
        return sensor.save(out, extra_sections=sections, validate=False)

    def to_yaml(self, *, relative_to: str | Path | None = None) -> str:
        """Serialize this set to a YAML **string** — the in-memory twin of :meth:`save`.

        ``relative_to`` names the directory the YAML is destined for, so
        file-path values (shared and configured alike) are written relative to
        it; omitted, paths are left as stored, matching ``Sensor.to_yaml``.

        There is no ``scope="resolved"`` export: writing every resolved value of
        the base would put configured dot-paths in the shared body as well, and
        the resulting file would violate the single-store invariant it is meant
        to persist (ADR-0010 D-B).
        """
        rel = Path(relative_to) if relative_to is not None else None
        sensor, sections = self._output_document(relative_to=rel)
        return sensor.to_yaml(
            scope="inputs",
            relative_to=rel,
            extra_sections=sections,
            validate=False,
        )

    def _output_document(self, *, relative_to: Path | None) -> tuple[Sensor, dict[str, Any]]:
        """The sensor to serialize, and the structured sections to write beside it.

        With no configured element row the base serializes its own element
        document, exactly as it always has. With one, the merged document
        (shared rows plus ``configured:`` rows in place) is written as an explicit
        section and the serializing sensor's own document is detached — a
        ``Sensor`` may not hold a configured row (it has no configurations), and
        writing both would state the shared rows twice.
        """
        sensor = self._document_sensor()
        sections: dict[str, Any] = {SECTION_KEY: self._section_document(relative_to=relative_to)}
        if self._element_rows:
            sections["optical_elements"] = merge_element_document(
                self._shared_element_rows(), self._element_rows, relative_to=relative_to
            )
            sensor = sensor.clone().set_optical_elements(None)
        return sensor, sections

    def _document_sensor(self) -> Sensor:
        """The base as it should be serialized — carrying the shared point count.

        ``set_wavelength_points(None, n)`` sets the set-level shared default,
        which persists as ``_radiant.wavelength_points`` (there is only one such
        field). When it is unset, the base's own point count is already the
        shared default and the base serializes directly.
        """
        if self._shared_wl_points is None:
            return self._base
        return self._base.with_wavelength_points(self._shared_wl_points)

    def _section_document(self, *, relative_to: Path | None) -> dict[str, Any]:
        """This set's state as the ``configurations:`` section mapping."""
        section = ConfigurationsSection(
            names=tuple(self._names),
            active=self._active,
            baseline=self._baseline,
            wavelength_points=dict(self._wl_points),
            parameters=dict(self._configured),
        )
        return serialize_configurations_section(
            section, build_parameter_set(), relative_to=relative_to
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _evaluation_order(self) -> list[str]:
        """Configuration names, active first, then set order."""
        return [self._active, *[n for n in self._names if n != self._active]]

    def _index(self, name: str, operation: str) -> int:
        """Position of configuration *name*, or an actionable error."""
        try:
            return self._names.index(name)
        except ValueError as exc:
            raise ConfigSetError(
                what=f"{operation}: no configuration named {name!r} in this set",
                why=f"the set holds {list(self._names)}",
                action=f"Use one of {list(self._names)}, or add({name!r}) first.",
                context={"configuration": name, "existing": list(self._names)},
            ) from exc

    # -- configured element rows ---------------------------------------

    def _shared_element_rows(self) -> list[dict[str, Any]]:
        """The base sensor's element document as a mutable list (``[]`` when none).

        These are the document's **shared** rows only: a configured row has been
        moved out of the base (single store), so this list is shorter than
        :meth:`element_count` by the number of configured rows.
        """
        return self._base.optical_elements() or []

    def _store_shared_element_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        """Write the shared rows back to the base sensor.

        An empty list attaches ``None``, not ``[]``: a document with **every**
        row configured has no shared rows, and an empty ``optical_elements``
        document is not a legal element document (the io parser requires a
        non-empty list).
        """
        self._base.set_optical_elements([dict(row) for row in rows] or None)

    def _shared_position(self, index: int) -> int:
        """Where full-document row *index* sits in the shared-rows list."""
        return sum(1 for i in range(index) if i not in self._element_rows)

    def _element_index(self, index: int, operation: str) -> int:
        """Validate *index* against the element document, or an actionable error."""
        if not isinstance(index, int) or isinstance(index, bool):
            raise ConfigSetError(
                what=f"{operation}: element row index must be an int, got {index!r}",
                why="element rows are addressed by position — the row identity of a "
                "configured element document (Gap 103 v1.1)",
                action=f"Pass a row index in 0 … {max(self.element_count() - 1, 0)}.",
                context={"element_row": index},
            )
        count = self.element_count()
        if count == 0:
            raise ConfigSetError(
                what=f"{operation}: this set has no 'optical_elements' document",
                why="an element row can only be configured inside a shared element document; "
                "with no document there is no row to configure",
                action="Attach the shared train first with cs.base.set_optical_elements([...]).",
                context={"element_row": index},
            )
        if index < 0 or index >= count:
            raise ConfigSetError(
                what=f"{operation}: element row {index} is outside the document "
                f"(it has {count} row(s))",
                why="row identity is positional and the row count is shared by every "
                "configuration — no configuration adds or removes a row",
                action=f"Pass a row index in 0 … {count - 1}.",
                context={"element_row": index, "count": count},
            )
        return index

    def _require_configured_element(self, index: int, operation: str) -> int:
        """Validate *index* and require that the row is configured."""
        position = self._element_index(index, operation)
        if position not in self._element_rows:
            raise ConfigSetError(
                what=f"{operation}: element row {position} is not configured",
                why="only a configured row carries a per-configuration entry; a shared row has "
                "one entry, read from cs.base.optical_elements()",
                action=f"Call configure_element({position}) first, or edit the shared row with "
                "cs.base.set_optical_elements([...]).",
                context={
                    "element_row": position,
                    "configured_rows": list(self.configured_element_indices()),
                },
            )
        return position

    def _check_element_positions(self, name: str) -> None:
        """Catch a configured row left position-less by an edit to the base document.

        The set's own API moves rows between the two stores and always preserves
        the document length, so it cannot create this state. Replacing the base's
        document behind the set's back (``cs.base.set_optical_elements(...)``)
        with a shorter one can — and the configured row would then have no
        position in the train. Caught here rather than ignored (Rule 17), exactly
        like the parameter clash :meth:`_check_single_store` catches.
        """
        if not self._element_rows:
            return
        total = len(self._shared_element_rows()) + len(self._element_rows)
        stray = sorted(i for i in self._element_rows if i >= total)
        if stray:
            raise ConfigSetError(
                what=f"configuration {name!r}: configured element row(s) {stray} are outside the "
                f"element document, which now has {total} row(s)",
                why="the base sensor's 'optical_elements' document was replaced by a shorter one "
                "after the row was configured; a configured row with no position has nothing to "
                "resolve, and dropping it would evaluate a train the study does not describe",
                action="Re-attach a shared document with at least "
                f"{max(stray) + 1 - len(self._element_rows)} shared row(s), or "
                f"unconfigure_element({stray[0]}) first.",
                context={"configuration": name, "element_rows": stray, "count": total},
            )

    def _check_single_store(self, name: str) -> None:
        """Enforce ADR-0010 D-B: no dot-path in both the base and the configured table.

        The set's own API moves parameters between the two stores, so it can
        never create the double state. Editing the owned base sensor directly
        (``cs.base.set(p, ...)`` on an already-configured *p*) can — and the
        shared value would then be silently shadowed by the configured column.
        That is caught here rather than ignored (Rule 17).
        """
        shared = self._base.inputs()
        clashes = sorted(p for p in self._configured if p in shared)
        if clashes:
            raise ConfigSetError(
                what=f"configuration {name!r}: parameter(s) {clashes} are configured but the "
                "base also holds a shared value for them",
                why="a configured parameter lives only in the per-configuration table "
                "(ADR-0010 D-B); a shared value set on the base afterwards would be "
                "silently shadowed by the configured column",
                action=f"Set per-configuration values with set_values({clashes[0]!r}, [...]) "
                f"or set_value({clashes[0]!r}, config, v), or unconfigure({clashes[0]!r}) "
                "first to go back to one shared value.",
                context={"configuration": name, "params": clashes},
            )

    def _canonical(self, dotpath: str) -> str:
        """Canonical schema name for *dotpath* (alias-aware, did-you-mean preserved)."""
        return self._base.parameter_def(dotpath).name

    def _require_configured(self, dotpath: str, operation: str) -> str:
        name = self._canonical(dotpath)
        if name not in self._configured:
            raise ConfigSetError(
                what=f"{operation}: parameter {name!r} is not configured",
                why="only a configured parameter carries a per-configuration value to set; a "
                "shared parameter has exactly one value, edited on the base sensor",
                action=f"Call configure({name!r}) first, or set the shared value with "
                f"cs.base.set({name!r}, ...).",
                context={"param": name, "configured": sorted(self._configured)},
            )
        return name

    def _check_column_length(self, name: str, column: list[Any]) -> None:
        if len(column) != len(self._names):
            raise ConfigSetError(
                what=f"parameter {name!r} needs exactly {len(self._names)} values "
                f"(one per configuration), got {len(column)}",
                why="configured parameters are dense by construction — every configuration "
                "carries a value, so a short list is never padded (ADR-0010 D-A)",
                action=f"Pass one value per configuration, in the order {list(self._names)}.",
                context={"param": name, "expected": len(self._names), "got": len(column)},
            )

    def _shared_seed(self, name: str) -> Any:
        """The current shared value of *name*, for seeding all configurations.

        The base's explicit input when it has one; otherwise the parameter's
        schema default; otherwise the value the base derives for it (a
        consistency-group member). The default is preferred over a base
        resolve because the base on its own need not be resolvable — once a
        *required* parameter is configured, it has left the base's inputs.
        """
        explicit = self._base.inputs().get(name)
        if explicit is not None:
            return explicit
        default = self._base.parameter_def(name).default
        if default is not None:
            return default
        try:
            return self._base.get_input(name)
        except RadiantError as exc:
            raise ConfigSetError(
                what=f"cannot seed configured values for {name!r}: it has no shared value",
                why=f"the base neither sets {name!r} nor resolves it ({exc})",
                action=f"Pass explicit values, e.g. configure({name!r}, [v1, ...]), or set a "
                "shared value on the base first.",
                context={"param": name},
            ) from exc

    def _validated(
        self,
        name: str,
        value: Any,
        config: str,
        *,
        unit: str | None = None,
    ) -> Any:
        """Validate *value* for parameter *name* and return it in input units.

        Runs the value through a single-parameter ``ParameterSet`` — the same
        type/enum/bounds/unit-conversion code path an input takes inside
        ``ParameterSet.resolve()`` — so a bad configured value is rejected at
        edit time with the owning configuration named, instead of surfacing
        later from a materialized sensor.
        """
        pdef = self._base.parameter_def(name)
        probe = ParameterSet([pdef])
        try:
            probe.set(pdef.name, value, Provenance.USER_SET, f"config:{config}", unit=unit)
            probe.resolve()
        except RadiantError as exc:
            raise ConfigSetError(
                what=f"configuration {config!r}: {pdef.name} = {value!r} is not a valid value",
                why=str(exc),
                action=f"Give configuration {config!r} a value of type "
                f"{pdef.dtype.__name__} within the parameter's declared domain "
                f"({pdef.input_unit or 'dimensionless'}).",
                context={"configuration": config, "param": pdef.name, "value": value},
            ) from exc
        return probe.get_input(pdef.name)

    def _check_name(self, name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ConfigSetError(
                what=f"configuration name {name!r} is not a non-empty string",
                why="a configuration name is its user-visible identity in selectors, "
                "comparison columns, provenance, and the saved study",
                action="Pass a short, non-empty name such as 'MWIR'.",
                context={"configuration": name},
            )

    def _check_name_list(self, names: Sequence[str]) -> None:
        if not names:
            raise ConfigSetError(
                what="a configuration set needs at least one configuration, got none",
                why="the single-configuration set is the ordinary single-model session",
                action="Pass names=['Configuration 1'] or omit names entirely.",
            )
        if len(names) > self.MAX_CONFIGS:
            raise ConfigSetError(
                what=f"a configuration set holds at most {self.MAX_CONFIGS} configurations, "
                f"got {len(names)}",
                why="the cap bounds the always-on evaluate-all pass and keeps the "
                "side-by-side comparison surface readable (ADR-0010 D-E)",
                action=f"Pass at most {self.MAX_CONFIGS} names, or split the study into two sets.",
                context={"count": len(names), "max": self.MAX_CONFIGS},
            )
        for name in names:
            self._check_name(name)
        duplicates = sorted({n for n in names if list(names).count(n) > 1})
        if duplicates:
            raise ConfigSetError(
                what=f"duplicate configuration name(s) {duplicates}",
                why="configuration names must be unique — they key values, columns, and provenance",
                action="Give every configuration a distinct name.",
                context={"duplicates": duplicates},
            )
