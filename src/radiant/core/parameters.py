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
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from radiant.core.exceptions import CoreStateError, CoreValidationError, RadiantError
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
    deprecated_aliases: frozenset[str] = frozenset()  # old names; warn + redirect
    # Dot-path of an alternative parameter that supersedes this one: when
    # that parameter is explicitly set (non-empty), this required
    # (default=None) parameter may stay unset and is left unresolved.
    # Example: detector.qe_value is required UNLESS detector.qe_table_path
    # is set (the spectral curve supersedes the scalar).
    required_unless: str | None = None

    def __post_init__(self) -> None:
        if self.dtype not in (float, int, str, bool):
            raise CoreValidationError(
                f"ParameterDef '{self.name}': dtype must be float, int, str, or bool"
            )
        if self.enum_values is not None and self.dtype is not str:
            raise CoreValidationError(f"ParameterDef '{self.name}': enum_values requires dtype=str")
        if self.bounds is not None and self.dtype not in (float, int):
            raise CoreValidationError(f"ParameterDef '{self.name}': bounds requires numeric dtype")
        if self.name in self.deprecated_aliases:
            raise CoreValidationError(f"ParameterDef '{self.name}': cannot alias itself")
        if self.required_unless is not None:
            if self.default is not None:
                raise CoreValidationError(
                    f"ParameterDef '{self.name}': required_unless only applies to "
                    f"required parameters (default=None); this one has a default."
                )
            if self.required_unless == self.name:
                raise CoreValidationError(
                    f"ParameterDef '{self.name}': required_unless cannot reference itself"
                )


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
        raise CoreValidationError(f"Unknown distribution: {d}")


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
        # Deprecated alias -> canonical name map (renames keep working
        # with a DeprecationWarning; see _canonical()).
        self._aliases: dict[str, str] = {}
        for pdef in schema:
            for alias in pdef.deprecated_aliases:
                if alias in self._defs:
                    raise CoreValidationError(
                        f"ParameterDef '{pdef.name}': deprecated alias '{alias}' "
                        "collides with a defined parameter name"
                    )
                if alias in self._aliases:
                    raise CoreValidationError(
                        f"ParameterDef '{pdef.name}': deprecated alias '{alias}' "
                        f"already maps to '{self._aliases[alias]}'"
                    )
                self._aliases[alias] = pdef.name
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
                    raise CoreValidationError(
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

    def _canonical(self, name: str) -> str:
        """Resolve a deprecated alias to its canonical name (with warning)."""
        if name in self._defs:
            return name
        canonical = self._aliases.get(name)
        if canonical is not None:
            warnings.warn(
                f"Parameter '{name}' is deprecated; use '{canonical}' instead. "
                "The old name will be removed in a future release.",
                DeprecationWarning,
                stacklevel=3,
            )
            return canonical
        return name

    # -- Input ---------------------------------------------------------------

    def set(
        self,
        name: str,
        value: Any,
        provenance: Provenance = Provenance.USER_SET,
        source: str = "user",
        *,
        unit: str | None = None,
    ) -> None:
        """Set a parameter value. Marks the set as unresolved.

        Without ``unit``, *value* is taken in the parameter's
        ``input_unit`` (historical behavior). With ``unit``, *value* is
        converted from the caller's native unit at this boundary
        (Rule 2 — the only place user-unit conversion happens), e.g.
        ``set("optics.aperture_diameter_m", 30.0, unit="cm")``.
        """
        name = self._canonical(name)
        if name not in self._defs:
            raise KeyError(self._suggest(name))
        if unit is not None:
            converted = self._convert_from_user_unit(name, value, unit)
            source = f"{source} [{value!r} {unit}]"
            value = converted
        self._inputs[name] = (value, provenance, source)
        self._resolved_flag = False

    def _convert_from_user_unit(self, name: str, value: Any, unit: str) -> float:
        """Convert *value* from a caller-supplied unit to the input_unit."""
        pdef = self._defs[name]
        if pdef.dtype not in (float, int):
            raise CoreValidationError(
                f"Parameter '{name}' is {pdef.dtype.__name__}-typed; the "
                "unit= argument applies only to numeric parameters. "
                "Pass the value without a unit."
            )
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise CoreValidationError(
                f"Parameter '{name}': cannot convert {value!r} from unit "
                f"'{unit}' — value must be numeric."
            ) from exc
        if unit == pdef.input_unit:
            return numeric
        try:
            canonical = convert(numeric, unit, pdef.canonical_unit)
            return inverse_convert(canonical, pdef.canonical_unit, pdef.input_unit)
        except KeyError as exc:
            raise CoreValidationError(
                f"Parameter '{name}': no registered conversion from "
                f"'{unit}' to '{pdef.canonical_unit or 'dimensionless'}'. "
                f"Native input unit is '{pdef.input_unit or 'dimensionless'}'; "
                "either pass the value in that unit (omit unit=) or register "
                "the conversion in radiant.core.units._CONVERSIONS."
            ) from exc

    def clear_input(self, name: str) -> bool:
        """Remove a set input so *name* reverts to its default (or is derived
        from a consistency group) on the next :meth:`resolve`.

        Owns the invalidation semantics: resolution is invalidated only when
        an input was actually removed. Callers (e.g. ``Sensor.reset()``) must
        use this instead of touching ``_inputs`` directly (CU-046).

        Returns
        -------
        bool
            ``True`` if an input was removed, ``False`` if none was set.

        Raises
        ------
        KeyError
            If *name* is not in the schema (with a did-you-mean suggestion).
        """
        name = self._canonical(name)
        if name not in self._defs:
            raise KeyError(self._suggest(name))
        if name not in self._inputs:
            return False
        del self._inputs[name]
        self._resolved_flag = False
        return True

    def set_tolerance(self, name: str, tol: Tolerance) -> None:
        name = self._canonical(name)
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
            raise CoreValidationError(
                f"Circular dependency detected: parameters {unresolvable} could not "
                f"be resolved after {max_passes} passes. Check consistency groups for "
                f"cycles (A derived from B, B derived from A)."
            )

        # Stage 3: apply defaults for unset, non-required parameters
        for name, pdef in self._defs.items():
            if name in self._resolved:
                continue
            if pdef.default is None:
                if pdef.required_unless is not None and self._alternative_is_set(
                    pdef.required_unless
                ):
                    # The superseding alternative is explicitly set — this
                    # parameter stays unresolved (get() raises if any code
                    # path reads it anyway, so nothing consumes a phantom).
                    continue
                unless_hint = (
                    f"  (or set '{pdef.required_unless}' instead, which supersedes it)\n"
                    if pdef.required_unless is not None
                    else ""
                )
                raise CoreValidationError(
                    f"Required parameter '{name}' is not set.\n"
                    f"  Description: {pdef.description}\n"
                    f"  Expected type: {pdef.dtype.__name__} in "
                    f"{pdef.input_unit or 'dimensionless'}\n"
                    f"  Set it via: params.set('{name}', value)\n" + unless_hint
                )
            self._resolved[name] = self._validate_and_convert(
                name,
                pdef.default,
                Provenance.DEFAULT,
                f"default: {pdef.default_justification or 'schema default'}",
            )

        self._resolved_flag = True

    def _alternative_is_set(self, name: str) -> bool:
        """True when the ``required_unless`` alternative is explicitly set.

        Checks the explicit-inputs store (not ``_resolved``) so the answer
        does not depend on schema iteration order during Stage 3.  An
        empty-string or None input does not count as "set" — e.g. an
        explicitly cleared ``detector.qe_table_path`` must not silence the
        requirement on ``detector.qe_value``.
        """
        canonical = self._canonical(name) if name not in self._inputs else name
        if canonical not in self._inputs:
            return False
        raw_value = self._inputs[canonical][0]
        return raw_value is not None and raw_value != ""

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
                raise CoreValidationError(
                    f"Parameter '{name}' expects float "
                    f"(unit: {pdef.input_unit or 'dimensionless'}), "
                    f"got {type(raw_value).__name__}: {raw_value!r}"
                ) from exc
        elif pdef.dtype is int:
            value = int(raw_value)
            if float(value) != float(raw_value):
                raise CoreValidationError(
                    f"Parameter '{name}' expects int, got non-integer {raw_value}"
                )
        elif pdef.dtype is bool:
            if not isinstance(raw_value, bool):
                raise CoreValidationError(
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
                raise CoreValidationError(
                    f"Parameter '{name}' = {value!r}; must be one of {list(pdef.enum_values)}"
                )

        # Bounds check (in input units)
        if pdef.bounds is not None:
            lo, hi = pdef.bounds
            if not (lo <= value <= hi):
                raise CoreValidationError(
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
                raise CoreValidationError(
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
                raise CoreValidationError(
                    f"Group '{group.name}': no derivation rule for '{missing}'"
                )
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

    # -- Schema introspection (Gap 70) ---------------------------------------

    def parameter_defs(self) -> Mapping[str, ParameterDef]:
        """Read-only view of the full schema, keyed by dot-path name.

        This is the public enumeration surface for GUIs, CLIs, and sweep
        tooling: every :class:`ParameterDef` carries dtype, units, bounds,
        enum values, default, description, and tags. The returned mapping
        is a live read-only view — it cannot be mutated, and the schema
        itself is fixed at construction.
        """
        return MappingProxyType(self._defs)

    def parameter_def(self, name: str) -> ParameterDef:
        """Return the :class:`ParameterDef` for *name*.

        Deprecated aliases resolve to their canonical definition (with a
        ``DeprecationWarning``). Unknown names raise ``KeyError`` with a
        did-you-mean suggestion.
        """
        name = self._canonical(name)
        if name not in self._defs:
            raise KeyError(self._suggest(name))
        return self._defs[name]

    def consistency_groups(self) -> tuple[ConsistencyGroup, ...]:
        """The registered consistency groups, in registration order."""
        return tuple(self._groups)

    def tolerances(self) -> Mapping[str, Tolerance]:
        """Read-only view of tolerances set via :meth:`set_tolerance`."""
        return MappingProxyType(self._tolerances)

    def inputs(self) -> Mapping[str, Any]:
        """Read-only snapshot of explicit inputs: name → raw input value.

        Only parameters actually passed to :meth:`set` (by the user or a
        config loader) appear here — defaults and derived values do not.
        Values are as supplied, in input units. This is the persistence
        surface: re-setting exactly these inputs on a fresh set and
        resolving reproduces this set's resolution, including provenance
        distinctions between explicit and defaulted parameters (Gap 67).
        """
        return MappingProxyType({name: val for name, (val, _prov, _src) in self._inputs.items()})

    @property
    def is_resolved(self) -> bool:
        """True when :meth:`resolve` has run and no input changed since."""
        return self._resolved_flag

    def copy(self) -> ParameterSet:
        """Return an unresolved copy sharing no mutable state with this set.

        Carries the schema, consistency groups, all explicit inputs (with
        their provenance and source), tolerances, and loaded-file records.
        The copy is returned unresolved; call :meth:`resolve` after any
        overrides. This is the supported way to build sweep/clone variants
        without touching private state.
        """
        new = ParameterSet(list(self._defs.values()), list(self._groups))
        for name, (val, prov, src) in self._inputs.items():
            new._inputs[name] = (val, prov, src)
        new._tolerances.update(self._tolerances)
        new._loaded_files.extend(self._loaded_files)
        return new

    # -- Access --------------------------------------------------------------

    def get(self, name: str) -> Any:
        """Return the canonical-unit value of a resolved parameter."""
        self._require_resolved()
        if name not in self._resolved:
            name = self._canonical(name)
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
            raise CoreStateError(
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
