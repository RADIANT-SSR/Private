"""Parameter system for RADIANT.

Implements the design from RADIANT_Parameter_System.md:
  - ParameterDef: schema definition (immutable)
  - ResolvedValue: a parameter value with provenance
  - ConsistencyGroup: linked parameters (e.g., f/# = f/D)
  - Tolerance: statistical distribution for Monte Carlo
  - ParameterSet: the resolver and accessor

Scalar parameters only. Spectral arrays live in radiant.core.spectral.
"""

from __future__ import annotations

import datetime as _dt
import difflib
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from radiant.core.exceptions import RadiantError
from radiant.core.units import convert, inverse_convert

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ParameterBoundsError(RadiantError, ValueError):
    """A user-controlled parameter is out of its valid physical domain.

    Follows the actionable-error contract from RADIANT_Master_Architecture.md
    Rule 15: carries a structured ``what / why / action / context`` payload so
    downstream tooling (CLI, GUI, logs) can surface each field independently.
    Co-inherits from :class:`ValueError` for back-compat with the
    ``pytest.raises(ValueError, ...)`` patterns already used elsewhere in
    the codebase; :class:`RadiantError` is the canonical base.

    Parameters
    ----------
    what:
        One-line description of what is wrong ("h_tgt = -100.0 m is negative").
    why:
        Physical reason it is wrong ("altitude must be above mean sea level").
    action:
        What the user should do to fix it ("set h_tgt ≥ 0").
    context:
        Optional dict of diagnostic fields (parameter name, current value,
        declared bounds, etc.).  Preserved as a structured record so tools
        can render it without parsing the message string.
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


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


class Provenance(Enum):
    USER_SET = "user_set"
    CONFIG_FILE = "config_file"
    DEFAULT = "default"
    DERIVED = "derived"
    SAMPLED = "sampled"


# ---------------------------------------------------------------------------
# Schema definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParameterDef:
    """Immutable schema definition for a parameter."""

    name: str  # dot-path: "sensor.optics.aperture_diameter"
    description: str
    dtype: type  # float, int, str, bool
    canonical_unit: str  # internal unit
    input_unit: str  # user-facing unit
    default: Any | None = None  # in input_unit; None means required
    bounds: tuple[float, float] | None = None  # in input_unit
    enum_values: tuple[str, ...] | None = None
    group: str | None = None  # consistency group name
    tags: frozenset[str] = frozenset()
    default_justification: str = ""

    def __post_init__(self) -> None:
        if self.dtype not in (float, int, str, bool):
            raise ValueError(f"ParameterDef '{self.name}': dtype must be float, int, str, or bool")
        if self.enum_values is not None and self.dtype is not str:
            raise ValueError(f"ParameterDef '{self.name}': enum_values requires dtype=str")
        if self.bounds is not None and self.dtype not in (float, int):
            raise ValueError(f"ParameterDef '{self.name}': bounds requires numeric dtype")


# ---------------------------------------------------------------------------
# Tolerance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tolerance:
    """Statistical distribution for Monte Carlo / sensitivity analysis.

    Distributions and required params:
      gaussian:           {"std": float}            (absolute, in input_unit)
                          {"std_fraction": float}   (fractional, of nominal)
      uniform:            {"low": float, "high": float}
      truncated_gaussian: {"std": float, "low": float, "high": float}
      log_normal:         {"sigma": float}
    """

    distribution: str
    params: dict[str, float]

    def sample(self, nominal: float, rng: Any) -> float:
        """Draw a single sample given a nominal value and a numpy Generator."""
        d = self.distribution
        p = self.params
        if d == "gaussian":
            std = p.get("std", p.get("std_fraction", 0.0) * nominal)
            return float(rng.normal(nominal, std))
        if d == "uniform":
            return float(rng.uniform(p["low"], p["high"]))
        if d == "truncated_gaussian":
            std = p.get("std", p.get("std_fraction", 0.0) * nominal)
            lo, hi = p["low"], p["high"]
            for _ in range(100):
                x = float(rng.normal(nominal, std))
                if lo <= x <= hi:
                    return x
            return max(lo, min(hi, nominal))
        if d == "log_normal":
            return float(rng.lognormal(mean=0.0, sigma=p["sigma"])) * nominal
        raise ValueError(f"Unknown distribution: {d}")


# ---------------------------------------------------------------------------
# Consistency group
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConsistencyGroup:
    """A set of N parameters linked by a constraint equation.

    Given any N-1 user-set values, the Nth is derived. If all N are set,
    the constraint is checked for self-consistency within tolerance.
    """

    name: str
    parameters: tuple[str, ...]
    constraint: str
    derivations: dict[str, Callable[[dict[str, float]], float]]
    tolerance: float = 1e-9  # relative tolerance for over-specification check


# ---------------------------------------------------------------------------
# Resolved value
# ---------------------------------------------------------------------------


@dataclass
class ResolvedValue:
    """A parameter value after resolution, carrying full provenance."""

    name: str
    value: Any  # canonical unit
    input_value: Any  # input unit (as user provided / display)
    canonical_unit: str
    input_unit: str
    provenance: Provenance
    source: str  # human-readable origin
    derived_from: dict[str, Any] | None = None
    timestamp: str = field(default_factory=lambda: _dt.datetime.now(_dt.UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "canonical_unit": self.canonical_unit,
            "input_value": self.input_value,
            "input_unit": self.input_unit,
            "provenance": self.provenance.value,
            "source": self.source,
            "derived_from": self.derived_from,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Parameter set / resolver
# ---------------------------------------------------------------------------


class ParameterSet:
    """Holds a registered schema and resolves a set of inputs.

    Workflow:
        schema = [ParameterDef(...), ...]
        groups = [ConsistencyGroup(...), ...]
        ps = ParameterSet(schema, groups)
        ps.set("sensor.optics.aperture_diameter", 0.3)
        ps.set("sensor.optics.focal_length", 1.2)
        ps.resolve()
        f_no = ps.get("sensor.optics.f_number")  # derived = 4.0

    The resolved set is immutable. Mutating any input requires re-calling
    resolve(), which re-runs validation, consistency, and derivation.
    """

    def __init__(
        self,
        schema: list[ParameterDef],
        groups: list[ConsistencyGroup] | None = None,
    ) -> None:
        self._defs: dict[str, ParameterDef] = {p.name: p for p in schema}
        self._groups: list[ConsistencyGroup] = groups or []
        self._inputs: dict[str, tuple[Any, Provenance, str]] = {}
        self._tolerances: dict[str, Tolerance] = {}
        self._resolved: dict[str, ResolvedValue] = {}
        self._resolved_flag: bool = False
        # Per RADIANT_Master_Architecture.md §C13, the provenance record
        # must include input file hashes. Loaders (radiant.io.config)
        # populate this via record_loaded_file() so ChainResult can
        # surface the list at provenance-render time.
        self._loaded_files: list[tuple[str, str]] = []

        # Validate consistency groups reference real parameters
        for g in self._groups:
            for p in g.parameters:
                if p not in self._defs:
                    raise ValueError(
                        f"ConsistencyGroup '{g.name}' references unknown parameter '{p}'"
                    )

    def record_loaded_file(self, path: str, sha256: str) -> None:
        """Record that a config file with the given SHA-256 was loaded.

        Loaders (e.g. :func:`radiant.io.config.load_config`) call this so
        that :meth:`ChainResult.to_provenance_record` can surface the
        full set of files this run consumed. Duplicate (path, hash)
        tuples are deduped; same path with a new hash appends a fresh
        record (a config that was reloaded after edit).
        """
        entry = (path, sha256)
        if entry not in self._loaded_files:
            self._loaded_files.append(entry)

    @property
    def loaded_files(self) -> tuple[tuple[str, str], ...]:
        """Tuples of ``(path, sha256)`` for every config file loaded."""
        return tuple(self._loaded_files)

    def _suggest(self, name: str) -> str:
        """Build a 'did you mean?' suggestion for an unknown parameter name."""
        matches = difflib.get_close_matches(name, self._defs.keys(), n=3, cutoff=0.5)
        if matches:
            suggestions = ", ".join(f"'{m}'" for m in matches)
            return f"Unknown parameter: '{name}'. Did you mean: {suggestions}?"
        return f"Unknown parameter: '{name}'"

    # -- Input ---------------------------------------------------------------

    def set(
        self,
        name: str,
        value: Any,
        provenance: Provenance = Provenance.USER_SET,
        source: str = "user",
    ) -> None:
        """Set a parameter value (in its input_unit). Marks the set as unresolved."""
        if name not in self._defs:
            raise KeyError(self._suggest(name))
        self._inputs[name] = (value, provenance, source)
        self._resolved_flag = False

    def set_tolerance(self, name: str, tol: Tolerance) -> None:
        if name not in self._defs:
            raise KeyError(self._suggest(name))
        self._tolerances[name] = tol
        self._resolved_flag = False

    def load_dict(
        self,
        data: dict[str, Any],
        provenance: Provenance = Provenance.CONFIG_FILE,
        source: str = "config",
    ) -> None:
        """Load a flat dot-path dict into the parameter set."""
        for name, value in data.items():
            self.set(name, value, provenance, source)

    # -- Resolution ----------------------------------------------------------

    def resolve(self) -> None:
        """Validate inputs, resolve consistency groups, and apply defaults.

        Uses a fixed-point iteration over consistency groups so that chained
        groups (group 2 needs a value derived by group 1) resolve correctly
        regardless of their declared order. Raises ValueError on validation
        failure, under/over-specification, or circular dependency.
        """
        self._resolved.clear()

        # Stage 1: collect explicit inputs (validate type, bounds, enum)
        for name, (raw_value, prov, src) in self._inputs.items():
            self._resolved[name] = self._validate_and_convert(name, raw_value, prov, src)

        # Stage 2: fixed-point iteration over consistency groups
        # Repeat until no new values are derived or max passes reached.
        max_passes = 10
        for _pass_num in range(max_passes):
            resolved_before = set(self._resolved)
            for group in self._groups:
                self._resolve_group(group)
            resolved_after = set(self._resolved)
            if resolved_after == resolved_before:
                # Stable — no new values derived this pass
                break
        else:
            # Max passes reached but still making progress — shouldn't normally happen.
            # Fall through to the circular dependency check below.
            pass

        # Check for circular dependencies: if any group still has exactly one
        # unresolved member after the fixed-point loop, something is cyclic.
        # Also check for fully-unresolved groups where all parameters are required
        # (no default) — these indicate a cycle with no entry point.
        unresolvable: list[str] = []
        for group in self._groups:
            unset = [p for p in group.parameters if p not in self._resolved]
            n_unset = len(unset)
            n_total = len(group.parameters)
            if n_unset == 1:
                # One missing after stable fixed-point — suspect cycle
                unresolvable.extend(unset)
            elif n_unset == n_total:
                # Completely unresolved — cycle with no entry point if all required
                all_required = all(self._defs[p].default is None for p in unset)
                if all_required:
                    unresolvable.extend(unset)
        if unresolvable:
            raise ValueError(
                f"Circular dependency detected: parameters {unresolvable} could not "
                f"be resolved after {max_passes} passes. Check consistency groups for "
                f"cycles (A derived from B, B derived from A)."
            )

        # Stage 3: apply defaults for unset, non-required parameters
        for name, pdef in self._defs.items():
            if name in self._resolved:
                continue
            if pdef.default is None:
                raise ValueError(
                    f"Required parameter '{name}' is not set.\n"
                    f"  Description: {pdef.description}\n"
                    f"  Expected type: {pdef.dtype.__name__} in "
                    f"{pdef.input_unit or 'dimensionless'}\n"
                    f"  Set it via: params.set('{name}', value)"
                )
            self._resolved[name] = self._validate_and_convert(
                name,
                pdef.default,
                Provenance.DEFAULT,
                f"default: {pdef.default_justification or 'schema default'}",
            )

        self._resolved_flag = True

    def _validate_and_convert(
        self,
        name: str,
        raw_value: Any,
        provenance: Provenance,
        source: str,
    ) -> ResolvedValue:
        pdef = self._defs[name]

        # Type coercion (value holds float | int | bool | str depending on dtype)
        value: Any
        if pdef.dtype is float:
            try:
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Parameter '{name}' expects float "
                    f"(unit: {pdef.input_unit or 'dimensionless'}), "
                    f"got {type(raw_value).__name__}: {raw_value!r}"
                ) from exc
        elif pdef.dtype is int:
            value = int(raw_value)
            if float(value) != float(raw_value):
                raise ValueError(f"Parameter '{name}' expects int, got non-integer {raw_value}")
        elif pdef.dtype is bool:
            if not isinstance(raw_value, bool):
                raise ValueError(
                    f"Parameter '{name}' expects bool, "
                    f"got {type(raw_value).__name__}: {raw_value!r}"
                )
            value = raw_value
        else:  # str
            value = str(raw_value)

        # Enum check (enum_values only exists on str parameters — validated in ParameterDef)
        if pdef.enum_values is not None:
            str_value = str(value)
            if str_value not in pdef.enum_values:
                raise ValueError(
                    f"Parameter '{name}' = {value!r}; must be one of {list(pdef.enum_values)}"
                )

        # Bounds check (in input units)
        if pdef.bounds is not None:
            lo, hi = pdef.bounds
            if not (lo <= value <= hi):
                raise ValueError(
                    f"Parameter '{name}' = {value} out of bounds [{lo}, {hi}] ({pdef.input_unit})"
                )

        # Unit conversion to canonical
        if pdef.dtype in (float, int) and pdef.input_unit != pdef.canonical_unit:
            canonical_value = convert(float(value), pdef.input_unit, pdef.canonical_unit)
        else:
            canonical_value = value

        return ResolvedValue(
            name=name,
            value=canonical_value,
            input_value=value,
            canonical_unit=pdef.canonical_unit,
            input_unit=pdef.input_unit,
            provenance=provenance,
            source=source,
        )

    def _resolve_group(self, group: ConsistencyGroup) -> None:
        """Process a consistency group: derive missing, validate over-specified."""
        set_params = [p for p in group.parameters if p in self._resolved]
        unset_params = [p for p in group.parameters if p not in self._resolved]
        n_set = len(set_params)
        n_total = len(group.parameters)

        if n_set == n_total:
            # Over-specified — validate consistency
            free = group.parameters[0]
            known = {p: self._resolved[p].value for p in group.parameters if p != free}
            try:
                computed = group.derivations[free](known)
            except KeyError:
                return
            actual = self._resolved[free].value
            if abs(computed - actual) > group.tolerance * max(abs(actual), 1.0):
                raise ValueError(
                    f"Consistency group '{group.name}' is over-constrained:\n"
                    f"  Constraint: {group.constraint}\n"
                    f"  User-specified '{free}' = {actual}\n"
                    f"  Computed '{free}' from other parameters = {computed}\n"
                    f"  Relative discrepancy: "
                    f"{abs(computed - actual) / max(abs(actual), 1.0):.3e} "
                    f"(tolerance: {group.tolerance:.3e})\n"
                    f"  Fix: either remove '{free}' from inputs and let it be "
                    f"derived, or correct the inconsistent value."
                )
            return

        if n_set == n_total - 1:
            # Derive the missing one
            missing = unset_params[0]
            known = {p: self._resolved[p].value for p in set_params}
            if missing not in group.derivations:
                raise ValueError(f"Group '{group.name}': no derivation rule for '{missing}'")
            derived_value = group.derivations[missing](known)
            pdef = self._defs[missing]
            input_value = (
                inverse_convert(derived_value, pdef.canonical_unit, pdef.input_unit)
                if pdef.input_unit != pdef.canonical_unit
                else derived_value
            )
            self._resolved[missing] = ResolvedValue(
                name=missing,
                value=derived_value,
                input_value=input_value,
                canonical_unit=pdef.canonical_unit,
                input_unit=pdef.input_unit,
                provenance=Provenance.DERIVED,
                source=f"derived: {group.constraint}",
                derived_from={p: self._resolved[p].value for p in set_params},
            )
            return

        if n_set < n_total - 1:
            # Under-specified — defer; defaults may fill in, then re-check
            return

    # -- Access --------------------------------------------------------------

    def get(self, name: str) -> Any:
        """Return the canonical-unit value of a resolved parameter."""
        self._require_resolved()
        if name not in self._resolved:
            if name in self._defs:
                raise KeyError(f"Parameter '{name}' is not resolved")
            raise KeyError(self._suggest(name))
        return self._resolved[name].value

    def get_resolved(self, name: str) -> ResolvedValue:
        """Return the full ResolvedValue with provenance."""
        self._require_resolved()
        return self._resolved[name]

    def get_input(self, name: str) -> Any:
        """Return the value in input (display) units."""
        self._require_resolved()
        return self._resolved[name].input_value

    def all_resolved(self) -> dict[str, ResolvedValue]:
        self._require_resolved()
        return dict(self._resolved)

    def _require_resolved(self) -> None:
        if not self._resolved_flag:
            raise RuntimeError(
                "ParameterSet not resolved. Call .resolve() before accessing values."
            )

    # -- Explainability ------------------------------------------------------

    def explain(self, name: str) -> str:
        """Return a human-readable explanation of why a parameter has its value."""
        self._require_resolved()
        if name not in self._resolved:
            return f"Parameter '{name}' is not resolved."
        rv = self._resolved[name]
        pdef = self._defs[name]
        lines = [
            f"{name} = {rv.input_value} {rv.input_unit} "
            f"(canonical: {rv.value} {rv.canonical_unit})",
            f"  Description: {pdef.description}",
            f"  Provenance: {rv.provenance.value}",
            f"  Source: {rv.source}",
        ]
        if rv.derived_from:
            lines.append("  Derived from:")
            for k, v in rv.derived_from.items():
                lines.append(f"    {k} = {v}")
        if pdef.default_justification and rv.provenance is Provenance.DEFAULT:
            lines.append(f"  Justification: {pdef.default_justification}")
        return "\n".join(lines)

    # -- Provenance audit ----------------------------------------------------

    def to_provenance_record(self, radiant_version: str) -> dict[str, Any]:
        self._require_resolved()
        return {
            "radiant_version": radiant_version,
            "resolved_at": _dt.datetime.now(_dt.UTC).isoformat(),
            "parameters": {name: rv.to_dict() for name, rv in self._resolved.items()},
        }

    # -- Monte Carlo support -------------------------------------------------

    def sample(self, rng: Any) -> ParameterSet:
        """Return a new ParameterSet with toleranced parameters resampled."""
        self._require_resolved()
        new = ParameterSet(list(self._defs.values()), self._groups)
        # Carry forward all original inputs
        for name, (val, prov, src) in self._inputs.items():
            new.set(name, val, prov, src)
        # Resample toleranced parameters
        for name, tol in self._tolerances.items():
            nominal = self._resolved[name].input_value
            sampled = tol.sample(float(nominal), rng)
            new.set(name, sampled, Provenance.SAMPLED, f"mc:{tol.distribution}")
        new.resolve()
        return new
