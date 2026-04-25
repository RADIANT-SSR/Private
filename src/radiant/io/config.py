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
reserved for future configuration-inheritance features and are
silently ignored by this loader.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from radiant.core.exceptions import RadiantError
from radiant.core.parameters import ParameterSet, Provenance

logger = logging.getLogger(__name__)

# Keys reserved for future config-inheritance features.
_RESERVED_KEYS = frozenset({"_extends", "_imports", "_vars"})


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

    Returns
    -------
    ParameterSet
        The same *params* object, mutated in place (also returned for
        chaining convenience).

    Raises
    ------
    ConfigError
        On YAML parse failure, non-dict top-level, or unknown parameter
        names.
    """
    path: Path | None = None

    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise ConfigError(f"File not found: {path}", path=path)
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigError(
                f"YAML parse error: {exc}", path=path
            ) from exc
    elif isinstance(source, dict):
        raw = source
    else:
        raise ConfigError(
            f"Expected a file path or dict, got {type(source).__name__}."
        )

    if not isinstance(raw, dict):
        raise ConfigError(
            f"Top-level YAML must be a mapping, got {type(raw).__name__}.",
            path=path,
        )

    # Strip reserved keys.
    body = {k: v for k, v in raw.items() if k not in _RESERVED_KEYS}

    flat = _flatten(body)
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

    return params


def save_config(
    params: ParameterSet,
    dest: str | Path,
    *,
    header: str = "# RADIANT config — schema v1\n",
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

    Returns
    -------
    Path
        The written file path.
    """
    resolved = params.all_resolved()
    flat = {name: rv.input_value for name, rv in resolved.items()}
    nested = _unflatten(flat)

    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = header + yaml.dump(
        nested,
        default_flow_style=False,
        sort_keys=True,
        allow_unicode=True,
    )
    out.write_text(text, encoding="utf-8")
    return out
