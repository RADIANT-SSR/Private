"""CU-338: the scenario tools must import *this* checkout's ``radiant``, or refuse.

``scenarios/tools/emit_gui_yaml.py`` and its siblings rebuild the committed
scenario baselines. Under plain ``python`` their ``import radiant`` resolves
through the editable install's ``.pth``, which points at whichever checkout ran
``pip install -e .`` — normally the primary tree, not the worktree the tools are
being run from. The result is a baseline refresh that composes another tree's
physics into this tree's committed numbers and prints ``[ ok ]``; it happened
twice in two days (2026-08-30/31), each time caught only after 15 baselines had
been rewritten.

``scenarios/tools/_local_radiant.ensure_local_radiant`` closes it: prepend this
checkout's ``src`` and then *verify the imported module*, refusing loudly if it
still comes from elsewhere. Both halves are covered here — the subprocess test
proves a foreign ``sys.path`` entry loses in the real interpreter, and the
in-process test proves an already-bound foreign ``radiant`` (which no path
surgery can displace) raises instead of being silently used.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _REPO_ROOT / "scenarios" / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from _local_radiant import (  # noqa: E402
    SRC_ROOT,
    ForeignRadiantError,
    ensure_local_radiant,
)

#: Every ``scenarios/tools`` module that reaches ``radiant`` — the four command
#: line entry points plus the registry they all import.
_GUARDED_MODULES: tuple[str, ...] = (
    "emit_gui_yaml.py",
    "gen_gui_console.py",
    "verify_gui_yaml.py",
    "verify_gui_open.py",
    "gui_baselines.py",
)


@pytest.fixture(autouse=True)
def _restore_sys_path() -> object:
    """``ensure_local_radiant`` reorders ``sys.path``; put it back afterwards."""
    saved = list(sys.path)
    yield
    sys.path[:] = saved


# ---------------------------------------------------------------------------
# The happy path: the invoking tree wins
# ---------------------------------------------------------------------------


def test_the_guard_resolves_radiant_inside_this_checkout() -> None:
    """Normal invocation returns this tree's ``radiant/__init__.py``."""
    resolved = ensure_local_radiant()
    assert resolved.is_relative_to(SRC_ROOT.resolve())
    assert resolved.name == "__init__.py"


def test_the_guard_puts_this_checkouts_src_first_on_the_path() -> None:
    """``<repo>/src`` ends up at ``sys.path[0]``, ahead of site-packages.

    This is the half that makes the common case work silently instead of
    merely failing loudly: the editable install writes a plain path line into
    site-packages, and a path line loses to ``sys.path[0]``.
    """
    ensure_local_radiant()
    assert sys.path[0] == str(SRC_ROOT)
    assert sys.path.count(str(SRC_ROOT)) == 1


def test_a_foreign_src_earlier_on_the_path_still_loses(tmp_path: Path) -> None:
    """End-to-end in a real interpreter: a decoy ``radiant`` does not win.

    ``PYTHONPATH`` entries are inserted ahead of site-packages, so this decoy
    stands exactly where the editable install's ``.pth`` line stands — the
    CU-338 situation, reproduced. The guard must still hand back this
    checkout's module.
    """
    decoy = tmp_path / "decoy_site"
    (decoy / "radiant").mkdir(parents=True)
    (decoy / "radiant" / "__init__.py").write_text(
        "raise AssertionError('the decoy radiant was imported')\n", encoding="utf-8"
    )

    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(_TOOLS)!r})\n"
        "from _local_radiant import ensure_local_radiant\n"
        "print(ensure_local_radiant())\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(decoy)},
        cwd=str(tmp_path),
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().startswith(str(SRC_ROOT))


# ---------------------------------------------------------------------------
# The refusal path: an already-bound foreign ``radiant``
# ---------------------------------------------------------------------------


def _foreign_radiant(tmp_path: Path) -> ModuleType:
    """A stand-in ``radiant`` whose ``__file__`` is another checkout's ``src``."""
    module = ModuleType("radiant")
    module.__file__ = str(tmp_path / "other_checkout" / "src" / "radiant" / "__init__.py")
    return module


def test_a_foreign_already_imported_radiant_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The case ``sys.path`` cannot fix: ``radiant`` is already bound elsewhere.

    Prepending this tree's ``src`` does nothing once ``radiant`` is in
    ``sys.modules``, which is exactly the state a strict editable install (or
    any earlier import) leaves. Silently proceeding here is what wrote foreign
    numbers into 15 baselines, so the guard raises.
    """
    monkeypatch.setitem(sys.modules, "radiant", _foreign_radiant(tmp_path))
    with pytest.raises(ForeignRadiantError) as excinfo:
        ensure_local_radiant()
    message = str(excinfo.value)

    # Names the offending tree, this tree, the consequence, and the fix (R15).
    assert "other_checkout" in message
    assert str(SRC_ROOT) in message
    assert "CU-338" in message
    assert "PYTHONPATH=" in message
    assert "ensure_local_radiant()" in message


def test_a_radiant_without_a_file_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unprovable provenance is treated as foreign, not waved through.

    A namespace package has ``__file__ = None``; the guard cannot show it came
    from this checkout, and Rule 17 forbids assuming it did.
    """
    module = ModuleType("radiant")
    module.__file__ = None
    monkeypatch.setitem(sys.modules, "radiant", module)
    with pytest.raises(ForeignRadiantError, match="no __file__"):
        ensure_local_radiant()


# ---------------------------------------------------------------------------
# Every entry point is wired, not just the one the CU was filed against
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filename", _GUARDED_MODULES)
def test_every_radiant_importing_tool_calls_the_guard(filename: str) -> None:
    """Static sweep: the guard is called at module scope, before any use.

    The CU was filed against ``emit_gui_yaml.py``, but every tool here reaches
    ``radiant`` and every one of them can be run bare from a worktree. Parsed
    rather than grepped so a mention inside a docstring or a comment does not
    satisfy it.
    """
    tree = ast.parse((_TOOLS / filename).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ensure_local_radiant"
    ]
    assert calls, f"{filename} imports radiant but never calls ensure_local_radiant()"


def test_no_new_tool_imports_radiant_without_the_guard() -> None:
    """The sweep list stays complete as tools are added.

    A new ``scenarios/tools`` module that imports ``radiant`` and is not in
    ``_GUARDED_MODULES`` fails here, so the next tool cannot quietly reopen
    CU-338.
    """
    unguarded = []
    for path in sorted(_TOOLS.glob("*.py")):
        # The guard module's own `import radiant` *is* the guard.
        if path.name in _GUARDED_MODULES or path.name == "_local_radiant.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imports_radiant = (
                isinstance(node, ast.Import)
                and any(alias.name.split(".")[0] == "radiant" for alias in node.names)
            ) or (
                isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "radiant"
            )
            if imports_radiant:
                unguarded.append(path.name)
                break
    assert not unguarded, (
        f"{unguarded} import radiant but are not in _GUARDED_MODULES — add "
        "ensure_local_radiant() to them and list them here (CU-338)"
    )
