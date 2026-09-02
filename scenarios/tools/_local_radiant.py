"""Make every ``scenarios/tools`` entry point import *this* checkout's ``radiant``.

CU-338. Each tool in this directory imports ``radiant`` — directly, or through
``gui_baselines`` — to rebuild and re-evaluate scenario baselines. Plain
``python`` resolves that import through the editable install's ``.pth``, which
points at whichever checkout last ran ``pip install -e .``, normally the primary
tree. Run from a git worktree, the tools therefore compose the *primary* tree's
physics into the worktree's committed baselines and print ``[ ok ]`` doing it.
That is not hypothetical: it happened twice in two days (2026-08-30/31), each
time caught only after 15 baselines had been rewritten with foreign numbers.
``PYTHONPATH=./src`` was the workaround, and nothing enforced it.

:func:`ensure_local_radiant` closes it from the inside, so no caller has to
remember the prefix:

1. it prepends ``<repo root>/src`` to ``sys.path`` ahead of site-packages, and
2. it imports ``radiant`` and **refuses loudly** if ``radiant.__file__`` still
   lands outside this tree.

Step 2 is the load-bearing half. Step 1 wins against a plain path-line ``.pth``
(the flavour ``pip install -e .`` writes here) but cannot win against a
``radiant`` that some earlier import already bound, nor against the strict
editable flavour that installs a ``MetaPathFinder`` — and ``sys.meta_path`` is
consulted before ``sys.path``. Only a check on the *imported* module can prove
which tree's physics is about to be written into a baseline, so that is what
the guard checks.

This lives under ``scenarios/tools`` (parallel to ``_runner_import.py``), not in
the ``radiant`` package: it is tooling policy about which ``radiant`` to import,
which the package itself cannot state about its own callers.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

#: This checkout's root — ``scenarios/tools/_local_radiant.py`` -> repo root.
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

#: The import root the tools must resolve ``radiant`` from.
SRC_ROOT: Path = REPO_ROOT / "src"


class ForeignRadiantError(RuntimeError):
    """``radiant`` resolved to a checkout other than the invoking one."""


def _refusal(resolved: str) -> str:
    """The actionable message (Rule 15): what, why it is fatal, and the fix."""
    return (
        f"scenarios/tools resolved `radiant` to {resolved}, which is outside the "
        f"checkout being invoked ({SRC_ROOT}).\n"
        "  Why this is fatal rather than a warning: these tools rebuild and re-evaluate "
        "the committed scenario baselines. Composing another checkout's physics into "
        "this tree's baselines writes numbers that look clean in the diff and are wrong "
        "(CU-338 — it corrupted 15 baselines twice on 2026-08-30/31, both times "
        "reporting `[ ok ]`).\n"
        "  Cause: `pip install -e .` pins `radiant` to whichever checkout ran it, and an "
        "already-imported `radiant` cannot be displaced afterwards.\n"
        "  Fix: run the tool from the root of the tree you are editing, as\n"
        f"    PYTHONPATH={SRC_ROOT} python scenarios/tools/<tool>.py ...\n"
        "  or, if you are driving these tools from your own script, call "
        "ensure_local_radiant() before the first `import radiant`."
    )


def ensure_local_radiant() -> Path:
    """Import ``radiant`` from this checkout, or refuse. Returns its ``__init__.py``.

    Idempotent: safe to call from every entry point and again from any module
    they import. Under ``pytest`` the work is already done — ``pythonpath =
    ["src", "."]`` in ``pyproject.toml`` is rootdir-relative — and this call
    then degenerates into the check.
    """
    src = str(SRC_ROOT)
    if not sys.path or sys.path[0] != src:
        while src in sys.path:
            sys.path.remove(src)
        sys.path.insert(0, src)

    import radiant

    return _assert_local(radiant)


def _assert_local(module: ModuleType) -> Path:
    """Raise unless ``module`` was loaded from this checkout's ``src/``."""
    module_file = getattr(module, "__file__", None)
    if module_file is None:
        # A namespace package, or a module stitched together without a file:
        # unprovable provenance, which for this guard is the same as foreign.
        raise ForeignRadiantError(_refusal("a module with no __file__ (namespace package?)"))
    resolved = Path(module_file).resolve()
    if not resolved.is_relative_to(SRC_ROOT.resolve()):
        raise ForeignRadiantError(_refusal(str(resolved)))
    return resolved
