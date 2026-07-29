"""Filesystem-path picker helpers for schema parameters (CU-220).

Two small functions shared by every surface that edits a path parameter: the
single-value :class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`
row and the per-configuration rows of
:class:`~radiant.gui.widgets.per_configuration_values.PerConfigurationValues`.

They lived in ``parameter_editor_dialog`` until CU-220 needed them on both sides;
importing the dialog from the per-configuration block would have closed an import
cycle (the dialog embeds that block), so they moved here — one home, no duplicate
(the CU's own "moves without duplication").
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["default_browse_dir", "path_picker_kind"]

# ``src/radiant/data/tables`` — the bundled reference-data tree. This module sits at
# ``src/radiant/gui/``, one level shallower than the dialog it moved out of, so the
# parent index is 1 rather than 2 (CU-220: the move silently broke the resolution
# until the browse-start tests caught it).
_REPO_DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "tables"

_BROWSE_START_SUBDIR: dict[str, str] = {
    "atmosphere": "atmospheres",
    "detector": "detectors",
    "source": "emissivity",
}


def default_browse_dir(dotpath: str) -> Path | None:
    """The default directory the Browse… picker opens in for *dotpath*, or None.

    The parameter's namespace maps to its shipped data family under the bundled
    ``src/radiant/data/tables/`` tree; an unmapped namespace falls back to the data
    root. Returns None when neither exists — the caller then falls back to the
    working directory.
    """
    namespace = dotpath.split(".", 1)[0]
    subdir = _BROWSE_START_SUBDIR.get(namespace)
    if subdir is not None and (_REPO_DATA_ROOT / subdir).is_dir():
        return _REPO_DATA_ROOT / subdir
    if _REPO_DATA_ROOT.is_dir():
        return _REPO_DATA_ROOT
    return None


def path_picker_kind(dotpath: str) -> str | None:
    """``"dir"`` / ``"file"`` when the dot-path leaf names a filesystem path, else None.

    The parameter schema types paths as plain ``str``; what marks them as paths is the
    binding naming convention (Parameter System doc): the leaf ends in ``_path`` or
    ``_file`` for files, ``_dir`` for directories. Every ``*_path``/``*_file``/``*_dir``
    parameter in the schema today is a real filesystem path (audited 2026-07-18), so the
    editor can safely offer a native picker for them — the "need a link" owner request.
    """
    leaf = dotpath.rsplit(".", 1)[-1]
    if leaf.endswith("_dir"):
        return "dir"
    if leaf.endswith(("_path", "_file")):
        return "file"
    return None
