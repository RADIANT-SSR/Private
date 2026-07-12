"""ChainResult archive serialization (Gap 67).

Saves a completed chain run to a single zip archive and reloads it with
full fidelity. Archive layout::

    manifest.json   # format version, encoded ChainState tree, provenance
                    # record (frozen at save time), unserialized-path list
    arrays.npz      # every numpy array in the tree, dtype-preserving

The codec round-trips: JSON primitives, non-finite floats, numpy arrays
(any non-object dtype), tuples vs lists, str-keyed mappings, and enums
and dataclasses defined inside the ``radiant`` package (encoded by
qualified name, reconstructed via their constructors so all
construction-time validation re-runs). Any other value is recorded in
the manifest (dotted path + type name) with a ``UserWarning`` at save
time and becomes an :class:`UnserializedValue` placeholder on reload —
never silently dropped (Rule 17).

Decode only instantiates classes from the ``radiant`` package; an
archive naming any other module is rejected (no arbitrary-code-execution
path, unlike pickle). ``arrays.npz`` is loaded with
``allow_pickle=False``.
"""

from __future__ import annotations

import dataclasses
import importlib
import io
import json
import warnings
import zipfile
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any, cast

import numpy as np

from radiant.core.chain import ChainState
from radiant.core.exceptions import RadiantError

FORMAT_VERSION = 1
_ARCHIVE_KIND = "radiant-chain-result"


class ResultArchiveError(RadiantError):
    """Raised when a ChainResult archive cannot be written or read.

    Carries the Rule 15 actionable-error payload in its message: what
    failed, why, and what to do about it.
    """


@dataclasses.dataclass(frozen=True)
class UnserializedValue:
    """Placeholder for a value that could not be archived.

    ``type_name`` records the original type. The dotted paths of all
    such values are listed in the archive manifest and in
    ``load_result_archive``'s return value.
    """

    type_name: str


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------


class _EncodeContext:
    def __init__(self) -> None:
        self.arrays: dict[str, np.ndarray[Any, Any]] = {}
        self.skipped: list[dict[str, str]] = []

    def add_array(self, arr: np.ndarray[Any, Any]) -> str:
        key = f"a{len(self.arrays)}"
        self.arrays[key] = arr
        return key


def _class_spec(cls: type) -> str:
    return f"{cls.__module__}:{cls.__qualname__}"


def _is_radiant_class(cls: type) -> bool:
    mod = cls.__module__
    return mod == "radiant" or mod.startswith("radiant.")


def _encode(obj: Any, path: str, ctx: _EncodeContext) -> Any:
    """Recursively encode *obj* into a JSON-safe tree."""
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, int) and not isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if np.isfinite(obj):
            return obj
        return {"__t": "float", "v": repr(obj)}
    if isinstance(obj, np.ndarray):
        if obj.dtype == object:
            ctx.skipped.append({"path": path, "type": "ndarray[object]"})
            return {"__t": "skipped", "type": "ndarray[object]"}
        return {"__t": "ndarray", "k": ctx.add_array(obj)}
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return _encode(float(obj), path, ctx)
    if isinstance(obj, Enum):
        if not _is_radiant_class(type(obj)):
            ctx.skipped.append({"path": path, "type": _class_spec(type(obj))})
            return {"__t": "skipped", "type": _class_spec(type(obj))}
        return {"__t": "enum", "cls": _class_spec(type(obj)), "v": obj.value}
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        cls = type(obj)
        if not _is_radiant_class(cls):
            ctx.skipped.append({"path": path, "type": _class_spec(cls)})
            return {"__t": "skipped", "type": _class_spec(cls)}
        fields = {
            f.name: _encode(getattr(obj, f.name), f"{path}.{f.name}", ctx)
            for f in dataclasses.fields(obj)
            if f.init
        }
        return {"__t": "dc", "cls": _class_spec(cls), "f": fields}
    if isinstance(obj, tuple):
        return {"__t": "tuple", "v": [_encode(v, f"{path}[{i}]", ctx) for i, v in enumerate(obj)]}
    if isinstance(obj, list):
        return {"__t": "list", "v": [_encode(v, f"{path}[{i}]", ctx) for i, v in enumerate(obj)]}
    if isinstance(obj, Mapping):
        if not all(isinstance(k, str) for k in obj):
            ctx.skipped.append({"path": path, "type": f"{type(obj).__name__}[non-str keys]"})
            return {"__t": "skipped", "type": f"{type(obj).__name__}[non-str keys]"}
        return {"__t": "map", "v": {k: _encode(v, f"{path}.{k}", ctx) for k, v in obj.items()}}
    ctx.skipped.append({"path": path, "type": _class_spec(type(obj))})
    return {"__t": "skipped", "type": _class_spec(type(obj))}


# ---------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------


def _resolve_radiant_class(spec: str) -> type:
    mod_name, _, qual = spec.partition(":")
    if not (mod_name == "radiant" or mod_name.startswith("radiant.")):
        raise ResultArchiveError(
            f"Archive references class '{spec}' outside the radiant package. "
            "Only radiant-defined classes are reconstructed (this guards "
            "against archives that try to import arbitrary code). "
            "The archive is corrupt or was not written by RADIANT."
        )
    try:
        obj: Any = importlib.import_module(mod_name)
        for part in qual.split("."):
            obj = getattr(obj, part)
    except (ImportError, AttributeError) as exc:
        raise ResultArchiveError(
            f"Archive references '{spec}', which does not exist in this "
            f"RADIANT installation ({exc}). The archive was written by an "
            "incompatible RADIANT version; re-run the analysis or load the "
            "archive with the version that wrote it."
        ) from exc
    if not isinstance(obj, type):
        raise ResultArchiveError(
            f"Archive reference '{spec}' resolved to {type(obj).__name__}, not a class."
        )
    return obj


def _decode(node: Any, arrays: Mapping[str, np.ndarray[Any, Any]]) -> Any:
    if node is None or isinstance(node, (bool, int, str)):
        return node
    if isinstance(node, float):
        return node
    if isinstance(node, list):
        # Bare lists never appear in encoded output (lists are tagged),
        # but tolerate them for forward compatibility.
        return [_decode(v, arrays) for v in node]
    if isinstance(node, dict):
        tag = node.get("__t")
        if tag is None:
            return {k: _decode(v, arrays) for k, v in node.items()}
        if tag == "float":
            return float(node["v"])
        if tag == "ndarray":
            return arrays[node["k"]]
        if tag == "enum":
            enum_cls = _resolve_radiant_class(node["cls"])
            return enum_cls(node["v"])
        if tag == "dc":
            cls = _resolve_radiant_class(node["cls"])
            kwargs = {k: _decode(v, arrays) for k, v in node["f"].items()}
            return cls(**kwargs)
        if tag == "tuple":
            return tuple(_decode(v, arrays) for v in node["v"])
        if tag == "list":
            return [_decode(v, arrays) for v in node["v"]]
        if tag == "map":
            return {k: _decode(v, arrays) for k, v in node["v"].items()}
        if tag == "skipped":
            return UnserializedValue(type_name=node["type"])
        raise ResultArchiveError(
            f"Archive contains unknown node tag '{tag}'. The archive was "
            "written by a newer RADIANT format revision; upgrade RADIANT "
            "to read it."
        )
    raise ResultArchiveError(f"Archive contains undecodable node of type {type(node).__name__}.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_STATE_FIELDS = (
    "wavelength_um",
    "frames",
    "stage_outputs",
    "noise_terms",
    "mtf_terms",
    "spatial_freq_cycles_per_mrad",
    "metrics",
    "history",
    "run_id",
)


def save_result_archive(
    path: str | Path,
    state: ChainState,
    provenance: dict[str, Any],
) -> Path:
    """Write *state* (+ its frozen provenance record) to a zip archive.

    Emits a ``UserWarning`` naming every value that could not be encoded
    (none, for states produced by the shipped chain — all stage outputs
    are radiant dataclasses, arrays, or primitives).
    """
    ctx = _EncodeContext()
    encoded_state = {name: _encode(getattr(state, name), name, ctx) for name in _STATE_FIELDS}

    if ctx.skipped:
        paths = ", ".join(f"{s['path']} ({s['type']})" for s in ctx.skipped)
        warnings.warn(
            f"ChainResult archive: {len(ctx.skipped)} value(s) could not be "
            f"serialized and will reload as UnserializedValue placeholders: {paths}",
            UserWarning,
            stacklevel=2,
        )

    manifest = {
        "kind": _ARCHIVE_KIND,
        "format_version": FORMAT_VERSION,
        "provenance": provenance,
        "unserialized": ctx.skipped,
        "state": encoded_state,
    }

    npz_buf = io.BytesIO()
    np.savez_compressed(npz_buf, **cast("dict[str, Any]", ctx.arrays))

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=1))
        zf.writestr("arrays.npz", npz_buf.getvalue())
    return out


def load_result_archive(path: str | Path) -> tuple[ChainState, dict[str, Any]]:
    """Read an archive written by :func:`save_result_archive`.

    Returns
    -------
    (state, provenance):
        The reconstructed :class:`ChainState` and the provenance record
        exactly as frozen at save time (re-rendering provenance after
        reload would misattribute the run to the loading environment).
    """
    src = Path(path)
    if not src.exists():
        raise ResultArchiveError(
            f"Result archive not found: {src}. Check the path, or produce "
            "one with ChainResult.save(path)."
        )
    try:
        with zipfile.ZipFile(src) as zf:
            manifest = json.loads(zf.read("manifest.json"))
            npz_buf = io.BytesIO(zf.read("arrays.npz"))
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise ResultArchiveError(
            f"File {src} is not a RADIANT result archive ({exc}). Expected "
            "a zip containing manifest.json and arrays.npz, written by "
            "ChainResult.save()."
        ) from exc

    if manifest.get("kind") != _ARCHIVE_KIND:
        raise ResultArchiveError(
            f"File {src} is a zip but not a RADIANT result archive "
            f"(kind = {manifest.get('kind')!r})."
        )
    version = manifest.get("format_version")
    if version != FORMAT_VERSION:
        raise ResultArchiveError(
            f"Result archive {src} has format version {version}; this "
            f"RADIANT reads version {FORMAT_VERSION}. Re-save the result "
            "with this version, or upgrade RADIANT."
        )

    with np.load(npz_buf, allow_pickle=False) as npz:
        arrays = {k: npz[k] for k in npz.files}

    kwargs = {name: _decode(manifest["state"][name], arrays) for name in _STATE_FIELDS}
    state = ChainState(**kwargs)
    provenance: dict[str, Any] = manifest["provenance"]
    return state, provenance
