"""T10 acceptance — every user-facing label resolves through the glossary.

The visual-remediation T10 sweep replaced every hardcoded subscript
literal (``"A_t"``, ``"alpha_t"``, ``"theta_off"``, ...) with a call to
``viewport_label()`` (3D viewport, VTK math-text) or ``panel_label()``
(Qt panel, HTML ``<sub>``). This test pins that contract so a future
PR cannot reintroduce a raw subscript literal in the swept modules.

The sweep covers:
  * ``scene/labels/_anchors.py`` — every viewport label
  * ``app/panels/readouts.py`` — every Qt panel row label

The status bar (``app/status_bar_text.py``) renders into Qt's plain-text
``QStatusBar.showMessage`` channel, where ``<sub>`` would not render.
The literal ``A_t`` there is the correct plain-text form and is
covered by ``test_phase6_appshell.py::test_status_bar_right_text_*``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# The forbidden literals — every concept that has a glossary entry whose
# rendered form is a subscript. Each entry is the Python string the sweep
# is replacing; finding one of these inside a Python literal in a swept
# module is a regression.
_FORBIDDEN_LITERALS = (
    "A_t",
    "n_B",
    "s_t",
    "s_B",
    "alpha_t",
    "theta_off",
    "theta_s",
)

_SWEPT_MODULES = (
    "dev_tools/geometry_gui_v2/scene/labels/_anchors.py",
    "dev_tools/geometry_gui_v2/app/panels/readouts.py",
)


def _repo_root() -> Path:
    # This test file: dev_tools/geometry_gui_v2/tests/test_typography_sweep.py
    # Repo root is four parents up.
    return Path(__file__).resolve().parents[3]


def _string_literals(source: str) -> list[str]:
    """Return every single- or double-quoted string literal in ``source``.

    Crude but sufficient: the swept modules don't use multi-line triple
    quoted strings for label content, only for module / function
    docstrings (which we deliberately allow — docstrings reference
    symbol names like ``A_t`` for human readers).
    """
    pattern = re.compile(r'"([^"\n]*)"|\'([^\'\n]*)\'')
    out: list[str] = []
    for m in pattern.finditer(source):
        out.append(m.group(1) if m.group(1) is not None else m.group(2))
    return out


@pytest.mark.parametrize("rel_path", _SWEPT_MODULES)
def test_swept_module_has_no_raw_subscript_literal(rel_path: str) -> None:
    src = (_repo_root() / rel_path).read_text()
    literals = _string_literals(src)
    offenders: list[tuple[str, str]] = []
    for lit in literals:
        # f-string interpolations like ``{sym_theta_off}`` are local
        # variable references that already came out of the typography
        # helper — strip them before scanning for hardcoded literals.
        scrubbed = re.sub(r"\{[^}]*\}", "", lit)
        for forbidden in _FORBIDDEN_LITERALS:
            # Word-boundary match so ``A_t`` doesn't fire on ``A_total``
            # and ``theta_s`` doesn't fire on ``theta_sun``.
            if re.search(rf"\b{re.escape(forbidden)}\b", scrubbed):
                offenders.append((forbidden, lit))
    assert not offenders, (
        f"{rel_path}: hardcoded subscript literal(s) reintroduced. "
        f"Route through viewport_label() / panel_label(). Offenders: {offenders}"
    )


def test_anchors_imports_viewport_label() -> None:
    """The anchor-collection module must import the typography helper."""
    src = (_repo_root() / _SWEPT_MODULES[0]).read_text()
    assert "from dev_tools.geometry_gui_v2.scene.labels.typography import" in src
    assert "viewport_label" in src


def test_readouts_panel_imports_panel_label() -> None:
    """The Qt readouts panel must import the typography helper."""
    src = (_repo_root() / _SWEPT_MODULES[1]).read_text()
    assert "from dev_tools.geometry_gui_v2.scene.labels.typography import" in src
    assert "panel_label" in src
