"""Import a scenario ``run_*.py`` as a module to reach its config factory.

Every scenario runner exposes its configuration at module scope (a
``make_config``/``build_sensor``/``build_config`` factory, or bare constants).
Importing the file yields that validated config factory — the basis for
deriving a GUI-loadable YAML that cannot drift from the backend-validated
inputs.

**Two runner shapes.** ~17 runners guard their work behind ``if __name__ ==
"__main__":`` — importing them only defines the factory. The other ~20 run
their whole analysis at *module scope* (no guard), so importing them would
re-run the sweep and, worse, ``savefig`` over committed figures. To stay
side-effect-free, :func:`import_runner` executes the module inside a hermetic
context that no-ops figure/workbook writes and silences stdout. The analysis
still *computes* (unavoidable without the guard) but writes nothing and prints
nothing; only the factory functions and constants it leaves behind are used.

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


class _StopModuleExec(Exception):
    """Raised to halt an unguarded runner's module-level analysis at import.

    The factory functions and constants a baseline needs are defined *above*
    the analysis; the first chain execution is where the expensive (and
    useless-to-us) sweep begins. Making that first ``evaluate``/``run`` raise
    this stops the module early with everything we need already bound.
    """


@contextlib.contextmanager
def _hermetic() -> Iterator[None]:
    """Neutralise the side effects an unguarded runner performs at import.

    Patches figure/workbook writers to no-ops, makes the first chain execution
    raise :class:`_StopModuleExec` (so an unguarded sweep halts instead of
    running to completion), and silences stdout/stderr — then restores
    everything. Never suppresses *other* exceptions: a genuine failure in a
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

    def _halt(*_args: object, **_kwargs: object) -> None:
        raise _StopModuleExec

    try:
        from radiant.api.sensor import Sensor
        from radiant.api.session import RadiantSession

        _patch(Sensor, "evaluate", _halt)
        _patch(RadiantSession, "run", _halt)
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

    Whether or not the runner is ``__main__``-guarded, importing it writes no
    files and prints nothing (see :func:`_hermetic`); the returned module
    carries the factory functions and constants used to build a baseline.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"scenario runner not found: {path}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"could not build import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    # _StopModuleExec is how an unguarded runner's module-level analysis halts at
    # its first chain execution; the factory + constants above it are already bound.
    with _hermetic(), contextlib.suppress(_StopModuleExec):
        spec.loader.exec_module(module)
    return module
