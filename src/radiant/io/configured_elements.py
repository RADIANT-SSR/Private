"""Configured rows inside the shared ``optical_elements`` document (Gap 103 v1.1).

An element **row** of the shared ``optical_elements:`` document (``RADIANT_Config_Format.md``
§1.8) may be **configured**, exactly as a parameter may be configured (ADR-0010 D-A): it then
carries one **complete** entry per configuration — dense, every member present — instead of one
shared entry. Owner-ratified 2026-09-02 (live review), superseding the replace-by-name override
model that never merged.

Document form — **in-place positional**: the shared list stays the skeleton, and a configured
row is written *at its position* as a one-key mapping::

    optical_elements:
    - {name: M1, transfer_mode: REFLECTIVE, reflectance: 0.97, temperature_K: 293.0}
    - configured:                       # row 1 is configured: one entry per configuration
        B1: {name: filter_b1, transfer_mode: REFRACTIVE, kind: FILTER,
             transmittance: data/filter_b01.csv, temperature_K: 240.0}
        B2: {name: filter_b2, transfer_mode: REFRACTIVE, kind: FILTER,
             transmittance: data/filter_b02.csv, temperature_K: 240.0}

    configurations:
      names: [B1, B2]

Binding rules, all enforced here at **load** time with a
:class:`~radiant.io.config.ConfigError` naming the config file, the row position, and the
configuration:

- **Row identity is positional.** The row count and row order are shared by every
  configuration; a configured row changes only *what is at that position*. The ``name`` is part
  of the entry and therefore configures with the row — a configuration may name row 4
  differently (owner-ratified consequence). No configuration adds or removes a row.
- **Single store.** A configured row's entries live **only** under its ``configured:`` mapping;
  the row has no shared entry to be shadowed by. This is the element analog of ADR-0010 D-B.
- **Dense.** The ``configured:`` key set must equal the configuration names exactly — no
  missing member (never defaulted) and no stray key (never dropped, Rule 17).
- **A configured row carries nothing else.** ``configured`` is the row's only key; a sibling
  field would be a shared/configured hybrid with no defined meaning.
- **Every entry is re-validated** through :func:`radiant.io.element_config.validate_element_entry`
  — the single validation authority, Kirchhoff included (Rule 5) — so a bad entry fails at load
  naming the member, never at evaluation.
- Spectral-file references inside an entry
  (:data:`radiant.io.element_config.SPECTRAL_FILE_KEYS`) resolve on load and relativize on save
  against the config file's own directory, exactly as configured parameter values do (CU-177).

This module owns only that syntax — splitting a raw document into its shared skeleton plus the
configured rows, resolving one member's train from them, and writing the merged form back. The
model-level operations (configure a row, set one member's entry, unconfigure) live on
:class:`~radiant.api.config_set.ConfigurationSet`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from radiant.core.exceptions import RadiantError
from radiant.io.config import ConfigError, relativize_file_value, resolve_file_value
from radiant.io.element_config import SPECTRAL_FILE_KEYS, validate_element_entry

__all__ = [
    "CONFIGURED_KEY",
    "ElementDocument",
    "configured_rows_need_a_configuration_set",
    "has_configured_rows",
    "is_configured_row",
    "merge_element_document",
    "resolve_element_document",
    "split_element_document",
]

# The single key that marks an ``optical_elements`` row as configured.
CONFIGURED_KEY = "configured"

# Where in the document an error happened, for messages.
_WHERE = "optical_elements"


@dataclass(frozen=True)
class ElementDocument:
    """A parsed ``optical_elements`` document split into its two stores.

    Attributes
    ----------
    shared:
        The rows that are **not** configured, in document order. These are the
        entries a :class:`~radiant.api.sensor.Sensor` attaches.
    configured:
        Position in the **full** document (0-indexed) → configuration name → that
        configuration's complete entry for the row. Dense: every configuration is
        present in every configured row.

    The full document has :attr:`length` rows; walking it means taking the next
    *shared* row at every position that is not a key of *configured*.
    """

    shared: tuple[dict[str, Any], ...]
    configured: Mapping[int, Mapping[str, dict[str, Any]]]

    @property
    def length(self) -> int:
        """Number of rows in the full document (shared + configured)."""
        return len(self.shared) + len(self.configured)


def is_configured_row(entry: Any) -> bool:
    """True when *entry* is a configured element row (``{configured: {...}}``)."""
    return isinstance(entry, Mapping) and CONFIGURED_KEY in entry


def has_configured_rows(entries: Any) -> bool:
    """True when an ``optical_elements`` document holds at least one configured row.

    Tolerant of malformed input by design: it is the *dispatch* question ("can a
    plain ``Sensor`` attach this document?"), asked before the document has been
    validated. A non-list answers ``False`` and fails later in the ordinary parser.
    """
    if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
        return False
    return any(is_configured_row(entry) for entry in entries)


def configured_rows_need_a_configuration_set(path: str | Path | None) -> ConfigError:
    """The actionable refusal for a configured element row outside a study load.

    A configured row's members are the configurations of a set, so the document
    is only meaningful alongside a ``configurations:`` section. Every loader that
    cannot supply that context raises this rather than parsing the row as an
    ordinary element entry (whose error would name a missing ``name`` field and
    explain nothing).
    """
    return ConfigError(
        f"'{_WHERE}' has configured row(s) ('{CONFIGURED_KEY}:'), which carry one entry per "
        "configuration of a configuration set (ADR-0010 / Gap 103 v1.1). This config file is a "
        "study — load it with ConfigurationSet.load(path), which reads the shared body, the "
        f"'{_WHERE}' skeleton, and the 'configurations:' section together. Sensor.load() / "
        "Sensor.from_yaml() / Sensor.from_dict() load single-configuration config files only.",
        path=path,
    )


def split_element_document(
    entries: Any,
    *,
    member_names: Sequence[str] | None,
    path: str | Path | None = None,
    base_dir: Path | None = None,
) -> ElementDocument:
    """Split a raw ``optical_elements`` document into shared rows + configured rows.

    Parameters
    ----------
    entries:
        The document as read from YAML (the value of the ``optical_elements`` key).
    member_names:
        The configuration names, in set order — the exact key set every configured
        row must carry. ``None`` means the caller has no configuration set, and any
        configured row raises :func:`configured_rows_need_a_configuration_set`.
    path:
        Config file path, reported in every error.
    base_dir:
        Directory the config file lives in; relative spectral-file references inside
        a configured entry resolve against it (CU-177). Shared rows are left alone —
        they are resolved by ``Sensor.set_optical_elements(..., base_dir=...)``, the
        one path they have always taken.

    Raises
    ------
    ConfigError
        On any violation of this module's binding rules, naming the row position and
        (where it applies) the configuration.
    """
    if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
        raise ConfigError(
            f"'{_WHERE}' must be a list of element rows, got {type(entries).__name__}.",
            path=path,
        )
    shared: list[dict[str, Any]] = []
    configured: dict[int, Mapping[str, dict[str, Any]]] = {}
    for index, row in enumerate(entries):
        if not is_configured_row(row):
            if not isinstance(row, Mapping):
                raise ConfigError(
                    f"'{_WHERE}' row {index} must be a mapping (one element entry, or a "
                    f"'{CONFIGURED_KEY}:' row), got {type(row).__name__}.",
                    path=path,
                )
            shared.append(dict(row))
            continue
        if member_names is None:
            raise configured_rows_need_a_configuration_set(path)
        configured[index] = _parse_configured_row(
            row, index, member_names=member_names, path=path, base_dir=base_dir
        )
    return ElementDocument(shared=tuple(shared), configured=configured)


def resolve_element_document(
    shared: Sequence[Mapping[str, Any]],
    configured: Mapping[int, Mapping[str, Mapping[str, Any]]],
    member: str,
) -> list[dict[str, Any]]:
    """The full element document one configuration evaluates with.

    The skeleton in document order, with every configured row resolved to
    *member*'s entry — what ``ConfigurationSet.sensor_for`` attaches. Entries are
    copies, so the caller cannot reach back into the stores.

    Raises :class:`KeyError` when a configured row holds no entry for *member*;
    the density invariant makes that unreachable through the public API, and the
    caller (``ConfigurationSet``) checks membership first.
    """
    return [dict(row) for row in _walk(shared, configured, member=member)]


def merge_element_document(
    shared: Sequence[Mapping[str, Any]],
    configured: Mapping[int, Mapping[str, Mapping[str, Any]]],
    *,
    relative_to: Path | None = None,
) -> list[dict[str, Any]]:
    """Render the two stores back as the YAML ``optical_elements`` document.

    The inverse of :func:`split_element_document`: shared rows at their positions,
    a ``{"configured": {member: entry}}`` row at every configured position.
    ``relative_to`` (the directory the config file will live in) rewrites the
    spectral-file references of **configured** entries to relative form (CU-177);
    ``None`` leaves them as stored, matching ``Sensor.to_yaml``. Shared rows pass
    through exactly as ``Sensor.save`` writes them today.
    """
    out: list[dict[str, Any]] = []
    shared_iter = iter(shared)
    total = len(shared) + len(configured)
    for index in range(total):
        row = configured.get(index)
        if row is None:
            out.append(dict(next(shared_iter)))
            continue
        out.append(
            {
                CONFIGURED_KEY: {
                    member: _relativize_entry(entry, relative_to) for member, entry in row.items()
                }
            }
        )
    return out


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _walk(
    shared: Sequence[Mapping[str, Any]],
    configured: Mapping[int, Mapping[str, Mapping[str, Any]]],
    *,
    member: str,
) -> Iterator[Mapping[str, Any]]:
    """Yield the full document's rows in order, configured rows already resolved."""
    shared_iter = iter(shared)
    for index in range(len(shared) + len(configured)):
        row = configured.get(index)
        yield next(shared_iter) if row is None else row[member]


def _parse_configured_row(
    row: Mapping[str, Any],
    index: int,
    *,
    member_names: Sequence[str],
    path: str | Path | None,
    base_dir: Path | None,
) -> dict[str, dict[str, Any]]:
    """Validate one ``{configured: {...}}`` row into member → entry (dense, ordered)."""
    where = f"'{_WHERE}' row {index}"
    extra = sorted(set(row) - {CONFIGURED_KEY})
    if extra:
        keys = ", ".join(f"'{k}'" for k in extra)
        raise ConfigError(
            f"{where} is a configured row and carries sibling key(s) {keys}. A configured row's "
            f"only key is '{CONFIGURED_KEY}' — its entries are complete and per configuration, so "
            "a field beside them would be a shared/configured hybrid with no defined meaning. "
            f"Move {keys} into each configuration's entry.",
            path=path,
        )
    body = row[CONFIGURED_KEY]
    if not isinstance(body, Mapping):
        raise ConfigError(
            f"{where}: '{CONFIGURED_KEY}' must be a mapping of configuration name to a complete "
            f"element entry, got {type(body).__name__}. Write one entry per configuration "
            f"{list(member_names)}.",
            path=path,
        )
    expected = list(member_names)
    missing = [name for name in expected if name not in body]
    stray = sorted(str(key) for key in body if key not in expected)
    if missing or stray:
        detail: list[str] = []
        if missing:
            detail.append(f"missing {missing}")
        if stray:
            detail.append(f"unknown {stray}")
        raise ConfigError(
            f"{where}: '{CONFIGURED_KEY}' must hold exactly one entry per configuration "
            f"{expected} — {'; '.join(detail)}. A configured element row is dense, like a "
            "configured parameter (ADR-0010 D-A): a missing configuration is never defaulted "
            "and an unknown key is never dropped. Give every configuration its entry, or "
            "remove the row's configured form.",
            path=path,
        )
    parsed: dict[str, dict[str, Any]] = {}
    for member in expected:
        entry = body[member]
        if not isinstance(entry, Mapping):
            raise ConfigError(
                f"{where}, configuration '{member}': the entry must be a mapping (one complete "
                f"element entry), got {type(entry).__name__}.",
                path=path,
            )
        resolved = _resolve_entry(entry, base_dir)
        # Single validation authority: the same parser (Kirchhoff included) the
        # shared rows face. A bad entry fails here, at load, naming the member.
        try:
            validate_element_entry(resolved, base_dir=base_dir)
        except RadiantError as exc:
            raise ConfigError(
                f"{where}, configuration '{member}': not a valid optical element: {exc}",
                path=path,
            ) from exc
        parsed[member] = resolved
    return parsed


def _resolve_entry(entry: Mapping[str, Any], base_dir: Path | None) -> dict[str, Any]:
    """One entry with its relative spectral-file references resolved (CU-177)."""
    out = dict(entry)
    if base_dir is None:
        return out
    for key in SPECTRAL_FILE_KEYS:
        if key in out:
            out[key] = resolve_file_value(out[key], base_dir)
    return out


def _relativize_entry(entry: Mapping[str, Any], relative_to: Path | None) -> dict[str, Any]:
    """One entry with its spectral-file references made relative (CU-177).

    ``relative_to=None`` copies the entry unchanged (paths as stored). Inline
    spectral tables and scalars are not strings and pass through
    :func:`~radiant.io.config.relativize_file_value` untouched.
    """
    out = dict(entry)
    if relative_to is None:
        return out
    for key in SPECTRAL_FILE_KEYS:
        if key in out:
            out[key] = relativize_file_value(out[key], relative_to)
    return out
