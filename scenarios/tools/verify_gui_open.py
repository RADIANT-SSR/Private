"""Widget-level gate: open each scenario in the *real* GUI, offscreen.

``verify_gui_yaml.py`` proves the YAML reloads through the API. This goes one
level deeper and drives the actual PySide6 widgets (the same code path a user
exercises), with no display, via the Qt ``offscreen`` platform. For each
scenario it:

1. constructs :class:`~radiant.gui.main_window.RADIANTMainWindow` and opens
   ``inputs/<slug>.gui.yaml`` through ``File -> Open`` (``_open_path`` ->
   ``Sensor.load``), then evaluates — the main-view path, and
2. binds the loaded sensor into the window's real
   :class:`~radiant.gui.widgets.scripting_console.ScriptingConsole` and runs
   the generated ``scripts/gui_console_<slug>.py`` inside it — the scripting
   window path — asserting no traceback reaches the transcript.

This is the headless proxy for "exercise the GUI through the GUI". A human
still runs the manual checklist in ``GUI_EXERCISE_INDEX.md`` for the bespoke
per-scenario widgets (importers, sliders, matrix builders) this cannot drive.

Usage (from repo root)::

    QT_QPA_PLATFORM=offscreen python scenarios/tools/verify_gui_open.py
    QT_QPA_PLATFORM=offscreen python scenarios/tools/verify_gui_open.py 1.1

The script sets ``QT_QPA_PLATFORM=offscreen`` itself if unset.
"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _local_radiant import ensure_local_radiant  # noqa: E402

ensure_local_radiant()  # CU-338: this checkout's radiant, or refuse

from gui_baselines import REGISTRY, GuiScenario  # noqa: E402

_TRACEBACK_MARKER = "Traceback (most recent call last)"


def _open_and_run(scen: GuiScenario, window: object) -> tuple[bool, str]:
    if not scen.yaml_path.is_file():
        return False, "YAML missing (run emit_gui_yaml.py)"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            window._open_path(str(scen.yaml_path))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            return False, f"File->Open raised {type(exc).__name__}: {exc}"
        sensor = getattr(window, "_sensor", None)
        if sensor is None:
            return False, "window opened no sensor"
        try:
            snr = sensor.evaluate().metrics.get("snr")
        except Exception as exc:  # noqa: BLE001
            return False, f"main-view evaluate raised {type(exc).__name__}: {exc}"

        if not scen.gui_script_path.is_file():
            return False, f"console script missing (run gen_gui_console.py); main-view SNR={snr}"
        console = window.console  # type: ignore[attr-defined]
        console.bind_sensor(sensor)
        source = scen.gui_script_path.read_text(encoding="utf-8")
        try:
            console.run_script(source, label=scen.id)
        except Exception as exc:  # noqa: BLE001
            return False, f"console.run_script raised {type(exc).__name__}: {exc}"
        transcript = console.output_text()
    if _TRACEBACK_MARKER in transcript:
        tail = transcript.strip().splitlines()[-1][:90]
        return False, f"console script raised in-window: ...{tail}"
    snr_str = f"{snr:.4g}" if isinstance(snr, (int, float)) else "—"
    return True, f"opened + console script ran clean (main-view SNR={snr_str})"


def main(argv: list[str]) -> int:
    from PySide6.QtWidgets import QApplication  # noqa: E402 — Qt import after platform set

    from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402

    wanted = set(argv[1:])
    scenarios = [s for s in REGISTRY if not wanted or s.id in wanted]
    if not scenarios:
        print(f"no registered scenarios match {sorted(wanted)}", file=sys.stderr)
        return 2

    app = QApplication.instance() or QApplication([])  # noqa: F841 — keep alive
    n_pass = 0
    for scen in scenarios:
        window = RADIANTMainWindow()
        ok, msg = _open_and_run(scen, window)
        window.close()
        tag = "PASS" if ok else "FAIL"
        print(f"[{tag}] {scen.id:>4}  {scen.slug}")
        print(f"        {msg}")
        n_pass += ok
    total = len(scenarios)
    print(f"\n{n_pass}/{total} scenarios open + run clean in the real GUI (offscreen)")
    return 0 if n_pass == total else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
