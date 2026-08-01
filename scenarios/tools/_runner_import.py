"""Import a scenario ``run_*.py`` as a module to reach its config factory.

Every scenario runner exposes its configuration at module scope (a
``make_config``/``build_sensor``/``build_config`` factory, or bare constants).
Importing the file yields that validated config factory — the basis for
deriving a GUI-loadable YAML that cannot drift from the backend-validated
inputs.

**Every runner is guarded.** Each ``run_*.py`` keeps only imports, constants,
input loading and its config factories at module scope, with the imperative
analysis behind ``if __name__ == "__main__": main()`` (CU-164), so importing
one defines the factory and runs no analysis. The historical ``_StopModuleExec``
halt — which made the first ``Sensor.evaluate`` raise, to stop an *unguarded*
runner's module-level sweep partway — is retired with the last unguarded runner.
Verified by importing every ``scenarios/*/*/scripts/run_*.py`` with plain
``importlib`` (no hermetic context): nothing printed, no file under
``scenarios/`` created or modified.

:func:`import_runner` still executes the module inside a hermetic context that
no-ops figure/workbook writes and silences stdout/stderr. That is now a
belt-and-braces guard rather than the mechanism: it keeps a runner that prints
or plots while loading its inputs (or one that regresses to module-scope
analysis) from writing over committed artifacts or polluting tool output.

This lives under ``scenarios/tools`` (parallel to each scenario's
``scripts/``), not in the ``radiant`` package.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType


@contextlib.contextmanager
def _hermetic() -> Iterator[None]:
    """Neutralise any side effect a runner might perform at import.

    Patches figure/workbook writers to no-ops and silences stdout/stderr — then
    restores everything. Never suppresses exceptions: a genuine failure in a
    runner's module-level code still propagates so the caller can report it.
    """
    os.environ.setdefault("MPLBACKEND", "Agg")
    patches: list[tuple[object, str, object]] = []

    def _patch(obj: object, name: str, value: object) -> None:
        if obj is not None and hasattr(obj, name):
            patches.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)

    def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.figure
        import matplotlib.pyplot as plt

        _patch(plt, "show", _noop)
        _patch(plt, "savefig", _noop)
        _patch(matplotlib.figure.Figure, "savefig", _noop)
    except Exception:  # noqa: BLE001 — matplotlib is optional at import time
        pass

    try:
        import openpyxl

        _patch(openpyxl.Workbook, "save", _noop)
    except Exception:  # noqa: BLE001
        pass

    try:
        import pandas

        _patch(pandas.DataFrame, "to_excel", _noop)
    except Exception:  # noqa: BLE001
        pass

    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            yield
    finally:
        for obj, name, original in reversed(patches):
            setattr(obj, name, original)


def import_runner(path: Path, module_name: str) -> ModuleType:
    """Import ``path`` as ``module_name`` (side-effect-free) and return it.

    Every runner is ``__main__``-guarded, so importing it runs no analysis; the
    hermetic context additionally guarantees it writes no files and prints
    nothing (see :func:`_hermetic`). The returned module carries the factory
    functions and constants used to build a baseline.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"scenario runner not found: {path}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"could not build import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    with _hermetic():
        spec.loader.exec_module(module)
    return module
