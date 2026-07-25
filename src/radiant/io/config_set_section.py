"""The ``configurations:`` structured YAML section (ADR-0010 D-D).

One study is one config file: today's shared parameter document plus a
``configurations:`` section carrying the per-configuration state of a
:class:`~radiant.api.config_set.ConfigurationSet`. The section rides the
ADR-0009 structured-section mechanism (``_SECTION_KEYS`` in
:mod:`radiant.io.config`) exactly as ``optical_elements:`` does, so **a config
file with no section is byte-for-byte today's format** — backward compatibility
is structural, not a migration.

Document form::

    configurations:
      names: [MWIR, LWIR]
      active: MWIR                  # GUI resume state
      baseline: MWIR                # delta reference
      wavelength_points:            # optional; omitted names use
        LWIR: 300                   #   _radiant.wavelength_points
      parameters:                   # dot-path -> list aligned with `names`
        spectral_integration.filter_min_um: [3.95, 8.0]
        spectral_integration.filter_max_um: [4.45, 12.0]
        detector.qe_value: [0.75, 0.62]

Binding rules, all enforced here at **load** time with a
:class:`~radiant.io.config.ConfigError` naming the config file, the
configuration, and the parameter:

- ``names``: 1 … *max_configurations* unique, non-empty strings.
- ``active`` / ``baseline``: optional, each must name a member; both default to
  the first name.
- ``wavelength_points``: optional mapping of member name → ``int >= 2``.
- ``parameters``: optional mapping of dot-path → list. Every list length equals
  ``len(names)`` — **dense** by construction (ADR-0010 D-A); a mismatch is an
  error, never padded. Dot-paths validate against the schema (alias-aware, with
  the existing did-you-mean suggestion).
- A dot-path may appear in the shared body **or** in ``parameters``, never both
  (the ADR-0010 D-B single-store invariant, checked at load).
- ``is_file_path`` values inside the section relativize on save and resolve on
  load against the config file's own directory, exactly like shared values
  (CU-177 — the same :mod:`radiant.io.config` helpers).

This module owns only the section's syntax and its cross-field invariants; the
values' type / bounds / enum validation is the ordinary parameter path inside
``ConfigurationSet`` (there is no second validation authority).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from radiant.core.parameters import ParameterSet
from radiant.io.config import ConfigError, relativize_file_value, resolve_file_value

__all__ = [
    "SECTION_KEY",
    "ConfigurationsSection",
    "parse_configurations_section",
    "serialize_configurations_section",
]

# Top-level key of the section (registered in radiant.io.config._SECTION_KEYS).
SECTION_KEY = "configurations"

# Recognised keys inside the section — anything else is a typo or a newer
# format, and is an error rather than a silent drop (Rule 17).
_ALLOWED_KEYS = frozenset({"names", "active", "baseline", "wavelength_points", "parameters"})

# Fallback cardinality cap. The single source of truth is
# ``ConfigurationSet.MAX_CONFIGS`` (ADR-0010 D-E), which the api layer passes in;
# this default only applies to a bare io-level call.
_DEFAULT_MAX_CONFIGURATIONS = 8


@dataclass(frozen=True)
class ConfigurationsSection:
    """Parsed, validated contents of a ``configurations:`` section.

    Attributes
    ----------
    names:
        Configuration names in document order (the column order of
        *parameters*).
    active, baseline:
        Member names — the displayed configuration and the delta reference.
    wavelength_points:
        Member name → spectral grid point count, for members that override the
        shared ``_radiant.wavelength_points``. Members without an override are
        absent.
    parameters:
        Canonical dot-path → one value per configuration, in **input units**,
        aligned with *names*.
    """

    names: tuple[str, ...]
    active: str
    baseline: str
    wavelength_points: Mapping[str, int] = field(default_factory=dict)
    parameters: Mapping[str, tuple[Any, ...]] = field(default_factory=dict)


def parse_configurations_section(
    raw: Any,
    params: ParameterSet,
    *,
    shared_inputs: Mapping[str, Any] | None = None,
    path: str | Path | None = None,
    base_dir: Path | None = None,
    max_configurations: int = _DEFAULT_MAX_CONFIGURATIONS,
) -> ConfigurationsSection:
    """Validate a raw ``configurations:`` mapping into a :class:`ConfigurationsSection`.

    Parameters
    ----------
    raw:
        The section as read from YAML (the value of the ``configurations`` key).
    params:
        A :class:`~radiant.core.parameters.ParameterSet` used **only** as the
        schema authority — dot-path canonicalization, did-you-mean suggestions,
        and ``is_file_path`` lookups. Its values are neither read nor written.
    shared_inputs:
        The explicit inputs of the shared body (``Sensor.inputs()``). A dot-path
        present in both stores violates the ADR-0010 D-B single-store invariant
        and raises.
    path:
        Config file path, reported in every error.
    base_dir:
        Directory the config file lives in. When given, ``is_file_path`` values
        inside the section resolve against it (CU-177 parity with shared values).
    max_configurations:
        Cardinality cap (ADR-0010 D-E); the api layer passes
        ``ConfigurationSet.MAX_CONFIGS``.

    Raises
    ------
    ConfigError
        On any violation of the binding rules in this module's docstring. Every
        message names the config file, and the offending configuration and/or
        parameter.
    """
    if not isinstance(raw, Mapping):
        raise ConfigError(
            f"'{SECTION_KEY}' must be a mapping with a 'names' list "
            f"(and optional 'active', 'baseline', 'wavelength_points', 'parameters'), "
            f"got {type(raw).__name__}.",
            path=path,
        )
    unknown = sorted(set(raw) - _ALLOWED_KEYS)
    if unknown:
        keys = ", ".join(f"'{k}'" for k in unknown)
        raise ConfigError(
            f"'{SECTION_KEY}' has unknown key(s) {keys}; recognised keys are "
            f"{sorted(_ALLOWED_KEYS)}. Per-configuration parameter values belong "
            f"under '{SECTION_KEY}.parameters'.",
            path=path,
        )

    names = _parse_names(raw, path=path, max_configurations=max_configurations)
    active = _parse_member(raw, "active", names, path=path)
    baseline = _parse_member(raw, "baseline", names, path=path)
    wavelength_points = _parse_wavelength_points(raw.get("wavelength_points"), names, path=path)
    parameters = _parse_parameters(
        raw.get("parameters"),
        params,
        names,
        shared_inputs=shared_inputs or {},
        path=path,
        base_dir=base_dir,
    )
    return ConfigurationsSection(
        names=names,
        active=active,
        baseline=baseline,
        wavelength_points=wavelength_points,
        parameters=parameters,
    )


def serialize_configurations_section(
    section: ConfigurationsSection,
    params: ParameterSet,
    *,
    relative_to: Path | None = None,
) -> dict[str, Any]:
    """Render a :class:`ConfigurationsSection` as the YAML section mapping.

    The inverse of :func:`parse_configurations_section`. ``relative_to`` (the
    directory the config file will live in) rewrites absolute ``is_file_path``
    values to relative form, exactly as the shared body's values are written
    (CU-177); ``None`` leaves them as stored, matching ``Sensor.to_yaml``.

    Optional keys are omitted when empty, so a set with no configured parameters
    and no per-configuration grids writes just ``names``/``active``/``baseline``.
    """
    _check_dense(section, path=None)
    defs = params.parameter_defs()
    out: dict[str, Any] = {
        "names": list(section.names),
        "active": section.active,
        "baseline": section.baseline,
    }
    if section.wavelength_points:
        out["wavelength_points"] = {
            name: int(n) for name, n in sorted(section.wavelength_points.items())
        }
    if section.parameters:
        table: dict[str, list[Any]] = {}
        for dotpath, values in sorted(section.parameters.items()):
            pdef = defs.get(dotpath)
            if pdef is not None and pdef.is_file_path and relative_to is not None:
                table[dotpath] = [relativize_file_value(v, relative_to) for v in values]
            else:
                table[dotpath] = list(values)
        out["parameters"] = table
    return out


# ---------------------------------------------------------------------------
# Field parsers
# ---------------------------------------------------------------------------


def _parse_names(
    raw: Mapping[str, Any],
    *,
    path: str | Path | None,
    max_configurations: int,
) -> tuple[str, ...]:
    if "names" not in raw:
        raise ConfigError(
            f"'{SECTION_KEY}' is missing the required 'names' list — it declares the "
            "configurations of the study and the column order every "
            f"'{SECTION_KEY}.parameters' list follows. "
            "Add e.g. names: [MWIR, LWIR].",
            path=path,
        )
    raw_names = raw["names"]
    if isinstance(raw_names, str) or not isinstance(raw_names, Sequence):
        raise ConfigError(
            f"'{SECTION_KEY}.names' must be a list of configuration names, "
            f"got {type(raw_names).__name__}. Write it as names: [MWIR, LWIR].",
            path=path,
        )
    names = list(raw_names)
    if not names:
        raise ConfigError(
            f"'{SECTION_KEY}.names' is empty — a configuration set holds at least one "
            "configuration (the single-configuration set is the ordinary "
            "single-model config file). Name at least one configuration, or remove "
            f"the '{SECTION_KEY}' section entirely.",
            path=path,
        )
    if len(names) > max_configurations:
        raise ConfigError(
            f"'{SECTION_KEY}.names' holds {len(names)} configurations; the maximum is "
            f"{max_configurations} (ADR-0010 D-E — the cap bounds the always-on "
            "evaluate-all pass and keeps the side-by-side comparison readable). "
            f"Drop {len(names) - max_configurations} configuration(s), or split the "
            "study into two config files.",
            path=path,
        )
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(
                f"'{SECTION_KEY}.names' contains {name!r}, which is not a non-empty "
                "string. A configuration name is its user-visible identity in "
                "selectors, comparison columns, and provenance.",
                path=path,
            )
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        dup = ", ".join(f"'{d}'" for d in duplicates)
        raise ConfigError(
            f"'{SECTION_KEY}.names' repeats configuration {dup}; names must be unique — "
            f"they key the value columns of every '{SECTION_KEY}.parameters' entry. "
            "Give each configuration a distinct name.",
            path=path,
        )
    return tuple(names)


def _parse_member(
    raw: Mapping[str, Any],
    key: str,
    names: tuple[str, ...],
    *,
    path: str | Path | None,
) -> str:
    """Parse ``active``/``baseline``: optional, defaulting to the first name."""
    value = raw.get(key)
    if value is None:
        return names[0]
    if not isinstance(value, str) or value not in names:
        raise ConfigError(
            f"'{SECTION_KEY}.{key}' names configuration {value!r}, which is not in "
            f"'{SECTION_KEY}.names' ({list(names)}). Set it to one of those names, or "
            f"omit '{key}' to default to {names[0]!r}.",
            path=path,
        )
    return value


def _parse_wavelength_points(
    raw: Any,
    names: tuple[str, ...],
    *,
    path: str | Path | None,
) -> dict[str, int]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ConfigError(
            f"'{SECTION_KEY}.wavelength_points' must be a mapping of configuration name "
            f"to point count, got {type(raw).__name__}. Configurations without an entry "
            "use the shared '_radiant.wavelength_points'.",
            path=path,
        )
    out: dict[str, int] = {}
    for name, value in raw.items():
        if name not in names:
            raise ConfigError(
                f"'{SECTION_KEY}.wavelength_points' names configuration {name!r}, which "
                f"is not in '{SECTION_KEY}.names' ({list(names)}). Only a member of the "
                "set can carry a per-configuration spectral grid.",
                path=path,
            )
        if not isinstance(value, int) or isinstance(value, bool) or value < 2:
            raise ConfigError(
                f"'{SECTION_KEY}.wavelength_points.{name}' must be an integer >= 2, got "
                f"{value!r} — the spectral evaluation grid of configuration {name!r} "
                "needs at least two points to span a band (the RADIANT default is 500).",
                path=path,
            )
        out[str(name)] = int(value)
    return out


def _parse_parameters(
    raw: Any,
    params: ParameterSet,
    names: tuple[str, ...],
    *,
    shared_inputs: Mapping[str, Any],
    path: str | Path | None,
    base_dir: Path | None,
) -> dict[str, tuple[Any, ...]]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ConfigError(
            f"'{SECTION_KEY}.parameters' must be a mapping of parameter dot-path to a "
            f"list of one value per configuration, got {type(raw).__name__}.",
            path=path,
        )
    out: dict[str, tuple[Any, ...]] = {}
    seen: dict[str, str] = {}
    defs = params.parameter_defs()
    for dotpath, values in raw.items():
        canonical = _canonical_dotpath(str(dotpath), params, path=path)
        if canonical in seen:
            raise ConfigError(
                f"'{SECTION_KEY}.parameters' configures parameter '{canonical}' twice "
                f"(as '{seen[canonical]}' and '{dotpath}'). A configured parameter has "
                "exactly one row of values.",
                path=path,
            )
        seen[canonical] = str(dotpath)
        if canonical in shared_inputs:
            raise ConfigError(
                f"parameter '{canonical}' appears both in the shared body (value "
                f"{shared_inputs[canonical]!r}) and in '{SECTION_KEY}.parameters' "
                f"(configurations {list(names)}). A parameter is shared **or** "
                "configured, never both (ADR-0010 D-B) — the shared value would be "
                "silently shadowed by the per-configuration column. Delete whichever "
                "of the two the study does not mean.",
                path=path,
            )
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise ConfigError(
                f"'{SECTION_KEY}.parameters.{canonical}' must be a list of "
                f"{len(names)} values (one per configuration, in the order "
                f"{list(names)}), got {type(values).__name__} {values!r}.",
                path=path,
            )
        column = list(values)
        if len(column) != len(names):
            raise ConfigError(
                f"'{SECTION_KEY}.parameters.{canonical}' has {len(column)} value(s) but "
                f"the set holds {len(names)} configurations {list(names)}. Configured "
                "parameters are dense — every configuration carries a value, so a short "
                "list is never padded (ADR-0010 D-A). Give one value per configuration, "
                "in that order.",
                path=path,
            )
        pdef = defs.get(canonical)
        if pdef is not None and pdef.is_file_path and base_dir is not None:
            column = [resolve_file_value(v, base_dir) for v in column]
        out[canonical] = tuple(column)
    return out


def _canonical_dotpath(dotpath: str, params: ParameterSet, *, path: str | Path | None) -> str:
    """Canonical schema name for *dotpath*, or a ConfigError with did-you-mean."""
    try:
        return params.parameter_def(dotpath).name
    except KeyError as exc:
        detail = str(exc).strip("'\"")
        raise ConfigError(
            f"'{SECTION_KEY}.parameters' names unknown parameter '{dotpath}': {detail}",
            path=path,
        ) from exc


def _check_dense(section: ConfigurationsSection, *, path: str | Path | None) -> None:
    """Guard the density invariant on the way out (never write a corrupt section)."""
    for dotpath, values in section.parameters.items():
        if len(values) != len(section.names):
            raise ConfigError(
                f"'{SECTION_KEY}.parameters.{dotpath}' has {len(values)} value(s) for "
                f"{len(section.names)} configurations {list(section.names)} — refusing to "
                "write a sparse configuration table (ADR-0010 D-A).",
                path=path,
            )
