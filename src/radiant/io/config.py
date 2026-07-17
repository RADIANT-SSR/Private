"""YAML configuration I/O for RADIANT.

Provides ``load_config`` to read a YAML file (or dict) into a
:class:`~radiant.core.parameters.ParameterSet`, and ``save_config``
to serialise a resolved ``ParameterSet`` back to YAML.

The YAML structure uses nested keys that map directly to dot-path
parameter names::

    source:
      target:
        temperature: 300      # → "source.target.temperature"
    optics:
      aperture_diameter_m: 0.30  # → "optics.aperture_diameter_m"

Special top-level keys (``_extends``, ``_imports``, ``_vars``) are
reserved for future configuration-inheritance features
(``RADIANT_Config_Format.md`` §1.3–1.5, currently design targets).
This loader raises :class:`ConfigError` when they are present — a
config relying on them would otherwise load with the directive
silently ignored and produce physics from a different parameter set
than the user intended (CU-050).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from radiant.core.exceptions import RadiantError
from radiant.core.parameters import ParameterSet, Provenance, Tolerance
from radiant.core.provenance import hash_file

logger = logging.getLogger(__name__)

# Keys reserved for future config-inheritance features. Present in a config,
# they are an error (not implemented) — never silently stripped (CU-050).
_RESERVED_KEYS = frozenset({"_extends", "_imports", "_vars"})

# Structured document sections (ADR-0009 D4): top-level keys that carry a
# declarative document, not parameters. They are parsed by their own io
# loaders (e.g. ``optical_elements`` -> element_config.parse_element_entries)
# and attached by the API layer (Sensor.from_yaml / Sensor.load). A bare
# load_config caller must opt in via ``sections_out``; otherwise the section
# raises rather than being silently dropped (Rule 17 — skipping it would
# silently change the physics the config describes).
_SECTION_KEYS = frozenset({"optical_elements"})

# Top-level metadata block written by Sensor.save() (Gap 67):
# format marker, wavelength_points, and tolerance distributions.
_META_KEY = "_radiant"


class ConfigError(RadiantError):
    """Raised when a YAML configuration file is invalid.

    Attributes
    ----------
    path:
        File path that triggered the error (``None`` for in-memory dicts).
    detail:
        Human-readable description of the problem.
    """

    def __init__(self, detail: str, *, path: str | Path | None = None) -> None:
        self.path = path
        self.detail = detail
        loc = f" in {path}" if path else ""
        super().__init__(f"ConfigError{loc}: {detail}")


# ---------------------------------------------------------------------------
# Flatten / unflatten helpers
# ---------------------------------------------------------------------------


def _flatten(
    nested: dict[str, Any],
    prefix: str = "",
    out: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Flatten a nested dict into dot-path keys.

    >>> _flatten({"optics": {"aperture_diameter_m": 0.3}})
    {'optics.aperture_diameter_m': 0.3}
    """
    if out is None:
        out = {}
    for key, value in nested.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            _flatten(value, full_key, out)
        else:
            out[full_key] = value
    return out


def _unflatten(flat: dict[str, Any]) -> dict[str, Any]:
    """Expand a dot-path dict into a nested dict.

    >>> _unflatten({"optics.aperture_diameter_m": 0.3})
    {'optics': {'aperture_diameter_m': 0.3}}
    """
    nested: dict[str, Any] = {}
    for dotpath, value in sorted(flat.items()):
        parts = dotpath.split(".")
        node = nested
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return nested


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(
    source: str | Path | dict[str, Any],
    params: ParameterSet,
    *,
    provenance: Provenance = Provenance.CONFIG_FILE,
    sections_out: dict[str, Any] | None = None,
) -> ParameterSet:
    """Load a YAML config file (or nested dict) into *params*.

    Parameters
    ----------
    source:
        Path to a ``.yaml`` file, or an already-parsed nested dict.
    params:
        A :class:`ParameterSet` (typically from
        ``RadiantSession.default_params()``). Values are set via
        ``params.set()``; the caller must call ``params.resolve()``
        afterward.
    provenance:
        Provenance tag applied to every loaded value.
    sections_out:
        Structured-section opt-in (ADR-0009). When a dict is passed,
        any structured document section present (``optical_elements``)
        is popped into it for the caller to parse and attach. When
        ``None`` (default), a config carrying a section raises — a bare
        loader must never silently drop a section that changes physics
        (Rule 17). ``Sensor.from_yaml`` / ``Sensor.load`` opt in and
        attach the sections.

    Returns
    -------
    ParameterSet
        The same *params* object, mutated in place (also returned for
        chaining convenience).

    Raises
    ------
    ConfigError
        On YAML parse failure, non-dict top-level, unknown parameter
        names, or a structured section without ``sections_out``.
    """
    path: Path | None = None

    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise ConfigError(f"File not found: {path}", path=path)
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigError(f"YAML parse error: {exc}", path=path) from exc
        # Per RADIANT_Master_Architecture.md §C13, provenance must record
        # the SHA-256 of every input file consumed by the run.
        params.record_loaded_file(str(path), hash_file(path))
    elif isinstance(source, dict):
        raw = source
    else:
        raise ConfigError(f"Expected a file path or dict, got {type(source).__name__}.")

    if not isinstance(raw, dict):
        raise ConfigError(
            f"Top-level YAML must be a mapping, got {type(raw).__name__}.",
            path=path,
        )

    reserved_present = sorted(_RESERVED_KEYS & raw.keys())
    if reserved_present:
        keys = ", ".join(f"'{k}'" for k in reserved_present)
        raise ConfigError(
            f"Reserved directive(s) {keys} are not implemented "
            "(RADIANT_Config_Format.md §1.3–1.5 are design targets). "
            "Inline the parent/imported values into a single complete config "
            "and re-run; do not rely on substitution, inheritance, or imports.",
            path=path,
        )

    # Split off structured document sections (ADR-0009). With sections_out
    # the caller takes them; without it a section-bearing config is an
    # error, never a silent skip (Rule 17).
    raw = dict(raw)
    sections_present = sorted(_SECTION_KEYS & raw.keys())
    if sections_present:
        if sections_out is None:
            keys = ", ".join(f"'{k}'" for k in sections_present)
            raise ConfigError(
                f"Config carries structured section(s) {keys}, which this "
                "loader does not attach. Load the file with Sensor.load() / "
                "Sensor.from_yaml() (which parse and attach sections), or "
                "remove the section for parameter-only loading.",
                path=path,
            )
        for key in sections_present:
            sections_out[key] = raw.pop(key)

    # Split off the Sensor.save() metadata block (Gap 67). Tolerances are
    # applied here; wavelength_points is session-level and consumed by
    # Sensor.load() (read_radiant_meta) — a bare load_config ignores it.
    meta = raw.pop(_META_KEY, None)
    if meta is not None and not isinstance(meta, dict):
        raise ConfigError(
            f"'{_META_KEY}' must be a mapping (written by Sensor.save()), "
            f"got {type(meta).__name__}.",
            path=path,
        )

    flat = _flatten(raw)
    source_label = str(path) if path else "dict"

    errors: list[str] = []
    for dotpath, value in flat.items():
        try:
            params.set(dotpath, value, provenance, source_label)
        except KeyError:
            errors.append(f"Unknown parameter: '{dotpath}'")

    if errors:
        raise ConfigError(
            "Schema violations:\n  " + "\n  ".join(errors),
            path=path,
        )

    if meta is not None:
        _apply_meta_tolerances(meta, params, path)

    return params


def _apply_meta_tolerances(
    meta: dict[str, Any],
    params: ParameterSet,
    path: Path | None,
) -> None:
    """Apply the ``_radiant.tolerances`` block to *params*."""
    tolerances = meta.get("tolerances", {})
    if not isinstance(tolerances, dict):
        raise ConfigError(
            f"'{_META_KEY}.tolerances' must be a mapping of dot-path to "
            f"{{distribution, params}}, got {type(tolerances).__name__}.",
            path=path,
        )
    for dotpath, spec in tolerances.items():
        if (
            not isinstance(spec, dict)
            or "distribution" not in spec
            or not isinstance(spec.get("params"), dict)
        ):
            raise ConfigError(
                f"'{_META_KEY}.tolerances.{dotpath}' must be a mapping with "
                "'distribution' (str) and 'params' (mapping) keys, "
                f"got {spec!r}.",
                path=path,
            )
        try:
            params.set_tolerance(
                dotpath,
                Tolerance(
                    distribution=str(spec["distribution"]),
                    params={str(k): float(v) for k, v in spec["params"].items()},
                ),
            )
        except KeyError as exc:
            raise ConfigError(
                f"'{_META_KEY}.tolerances' names unknown parameter '{dotpath}': {exc}",
                path=path,
            ) from exc


def read_radiant_meta(path: str | Path) -> dict[str, Any]:
    """Return the ``_radiant`` metadata block of a config file (or {}).

    Used by ``Sensor.load()`` to recover session-level settings
    (``wavelength_points``) before constructing the Sensor. Raises
    :class:`ConfigError` on unreadable YAML, mirroring ``load_config``.
    """
    src = Path(path)
    if not src.exists():
        raise ConfigError(f"File not found: {src}", path=src)
    try:
        raw = yaml.safe_load(src.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML parse error: {exc}", path=src) from exc
    if not isinstance(raw, dict):
        return {}
    meta = raw.get(_META_KEY)
    return dict(meta) if isinstance(meta, dict) else {}


def save_config(
    params: ParameterSet,
    dest: str | Path,
    *,
    header: str = "# RADIANT config — schema v1\n",
    meta: dict[str, Any] | None = None,
    scope: str = "resolved",
    sections: dict[str, Any] | None = None,
) -> Path:
    """Serialise a resolved ParameterSet to a YAML file.

    Parameters
    ----------
    params:
        A resolved :class:`ParameterSet`.
    dest:
        Output file path.
    header:
        Comment prepended to the file.
    meta:
        Optional ``_radiant`` metadata block (Gap 67 — written by
        ``Sensor.save()``: format marker, wavelength_points, tolerance
        distributions). ``load_config`` re-applies tolerances from it.
    scope:
        ``"resolved"`` (default, historical behavior) writes every
        resolved parameter — defaults and derived values included — as
        a fully-specified documentation export. ``"inputs"`` writes
        only the explicitly-set inputs, so reloading reproduces the
        original resolution exactly: defaults re-apply, consistency
        groups re-derive, and provenance-sensitive logic (e.g. the
        source inferrer's mutual-exclusivity checks) sees the same
        explicit/defaulted split as the original (Gap 67 round-trip).
    sections:
        Optional structured document sections (ADR-0009 D4) written as
        top-level keys, e.g. ``{"optical_elements": [...]}``. Keys must
        be registered section keys; ``load_config`` hands them back via
        ``sections_out`` on reload.

    Returns
    -------
    Path
        The written file path.
    """
    if scope not in ("resolved", "inputs"):
        raise ConfigError(f"save_config: scope must be 'resolved' or 'inputs', got {scope!r}.")
    if sections is not None:
        unknown = sorted(set(sections) - _SECTION_KEYS)
        if unknown:
            keys = ", ".join(f"'{k}'" for k in unknown)
            raise ConfigError(
                f"save_config: unknown structured section(s) {keys}; "
                f"registered sections: {sorted(_SECTION_KEYS)}."
            )
    text = serialize_config(params, header=header, meta=meta, scope=scope, sections=sections)
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Rule 30: explicit encoding; newline="\n" keeps the YAML byte-stable across platforms.
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return out


def serialize_config(
    params: ParameterSet,
    *,
    header: str = "# RADIANT config — schema v1\n",
    meta: dict[str, Any] | None = None,
    scope: str = "resolved",
    sections: dict[str, Any] | None = None,
) -> str:
    """Serialise a resolved ParameterSet to a YAML **string** (Gap 88).

    The in-memory twin of :func:`save_config` (which delegates here) — same
    scopes, same ``_radiant`` meta block, same structured sections. This is
    the surface ``Sensor.to_yaml`` exposes so the GUI's YAML tab no longer
    needs a temp-file round trip.
    """
    if scope not in ("resolved", "inputs"):
        raise ConfigError(f"serialize_config: scope must be 'resolved' or 'inputs', got {scope!r}.")
    if sections is not None:
        unknown = sorted(set(sections) - _SECTION_KEYS)
        if unknown:
            keys = ", ".join(f"'{k}'" for k in unknown)
            raise ConfigError(
                f"serialize_config: unknown structured section(s) {keys}; "
                f"registered sections: {sorted(_SECTION_KEYS)}."
            )
    if scope == "inputs":
        flat = dict(params.inputs())
    else:
        resolved = params.all_resolved()
        flat = {name: rv.input_value for name, rv in resolved.items()}
    nested = _unflatten(flat)
    if sections is not None:
        nested.update(sections)
    if meta is not None:
        nested[_META_KEY] = meta
    return header + yaml.dump(
        nested,
        default_flow_style=False,
        sort_keys=True,
        allow_unicode=True,
    )
