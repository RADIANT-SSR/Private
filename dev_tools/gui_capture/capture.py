"""Deterministic offscreen captures of the RADIANT GUI and its figures.

The generator behind every before/after contact sheet in
``docs/reports/gui_visual_finish_2026-10/`` (Gap 143, Rule 26): it loads a config
or study, evaluates it, walks every stage view and every visible tab, and saves
the main window as PNG in the requested theme(s) — plus every ``result.plot.*``
figure rendered headlessly at a fixed size. Two runs on the same commit, config,
size and theme produce the same files, so a capture made before a change and
one made after it are a fair pair for blind comparison.

Usage (from the repo root, macOS or Windows)::

    python dev_tools/gui_capture/capture.py --config examples/mwir_leo_minimal.yaml \\
        --config src/radiant/data/examples/landsat_oli2_all_bands.yaml \\
        --out .impeccable/captures/baseline --theme both --welcome

Output layout: ``<out>/<config-stem>/<theme>_<stage>[_<tab>].png``,
``<out>/<config-stem>/figures/<theme>_<plot>.png``, ``<out>/welcome/<theme>.png``,
and one ``capture.json`` sidecar per config recording the environment the
pixels came from (RADIANT version and commit, Qt version, platform plugin,
resolved font families, window size), because an offscreen render is only
comparable to another offscreen render made under the same conditions.

The window is driven through its public surface plus two private hooks
(``_evaluate_now`` and ``_on_toggle_theme``) that the GUI's own tests also use;
this is a dev tool, not library code, and it is not imported by ``src/``.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# The platform plugin must be chosen before PySide6 is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, qVersion  # noqa: E402
from PySide6.QtWidgets import QApplication, QTabWidget  # noqa: E402

from radiant.api.build_info import build_info  # noqa: E402
from radiant.api.config_set import ConfigurationSet  # noqa: E402
from radiant.api.inspect import ResultPlotNamespace  # noqa: E402
from radiant.api.plot import plot_theme  # noqa: E402
from radiant.api.plot_style import MONO_STACK, SANS_STACK, resolve_stack  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.settings_store import SettingsStore  # noqa: E402
from radiant.gui.themes import tokens  # noqa: E402
from radiant.gui.themes.stylesheet import apply_theme  # noqa: E402

#: Stage namespaces in strip order — the fallback when the strip exposes none.
STAGES: tuple[str, ...] = (
    "geometry",
    "source",
    "atmosphere",
    "optics",
    "platform",
    "spectral_integration",
    "detector",
    "readout",
    "calibration",
    "performance",
)

#: Figure size every ``result.plot.*`` figure is rendered at (inches) and its DPI.
FIGURE_SIZE_IN: tuple[float, float] = (7.5, 4.6)
FIGURE_DPI: int = 130

_EVALUATE_TIMEOUT_S: float = 180.0


def _slug(text: str) -> str:
    """A filesystem-safe lowercase slug for a tab label or plot name."""
    text = text.replace("&&", "and").replace("+", "plus")
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "tab"


def _pump(app: QApplication, turns: int = 60, pause_s: float = 0.005) -> None:
    """Process *turns* event-loop iterations with a short pause between them."""
    for _ in range(turns):
        app.processEvents()
        time.sleep(pause_s)


def _wait_for_result(app: QApplication, window: RADIANTMainWindow) -> bool:
    """Block until the window holds a result and no evaluation is pending."""
    deadline = time.monotonic() + _EVALUATE_TIMEOUT_S
    while time.monotonic() < deadline:
        if window.last_result is not None and not window.evaluation_scheduled:
            _pump(app, 80)
            return True
        app.processEvents()
        time.sleep(0.02)
    return False


def _environment(theme_name: str, size: tuple[int, int], config: Path | None) -> dict[str, Any]:
    """The sidecar record: everything that could change the pixels."""
    info = build_info()
    return {
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "radiant_version": info.version,
        "git_commit": info.git_sha,
        "git_dirty": info.git_dirty,
        "qt_version": qVersion(),
        "platform_plugin": os.environ.get("QT_QPA_PLATFORM"),
        "python": sys.version.split()[0],
        "os": platform.platform(),
        "theme": theme_name,
        "window_size": list(size),
        "config": str(config) if config is not None else None,
        "fonts": {
            "sans": resolve_stack(SANS_STACK)[0],
            "mono": resolve_stack(MONO_STACK)[0],
        },
        "figure_size_in": list(FIGURE_SIZE_IN),
        "figure_dpi": FIGURE_DPI,
    }


def _new_settings(scratch: Path, label: str) -> SettingsStore:
    """A settings store isolated to this run so the operator's preferences stay untouched."""
    ini = scratch / f"settings_{label}.ini"
    if ini.exists():
        ini.unlink()
    return SettingsStore(QSettings(str(ini), QSettings.Format.IniFormat))


def _stage_namespaces(window: RADIANTMainWindow) -> tuple[str, ...]:
    """Namespaces from the live strip, falling back to the documented order."""
    found: list[str] = []
    for chip in window.stage_strip.chips:
        namespace = getattr(chip, "namespace", None)
        if isinstance(namespace, str):
            found.append(namespace)
    return tuple(found) or STAGES


def _visible_tab_widgets(window: RADIANTMainWindow) -> list[QTabWidget]:
    """Tab widgets currently on screen in the stage view (hidden stages are skipped)."""
    return [tw for tw in window.central_canvas.findChildren(QTabWidget) if tw.isVisible()]


def _capture_window(
    app: QApplication,
    window: RADIANTMainWindow,
    out: Path,
    theme_name: str,
    files: list[str],
) -> None:
    """Walk every stage and every visible tab, saving one PNG per view."""
    for namespace in _stage_namespaces(window):
        window.central_canvas.select_stage(namespace)
        _pump(app, 80)
        name = f"{theme_name}_{namespace}.png"
        window.grab().save(str(out / name))
        files.append(name)
        for tab_widget in _visible_tab_widgets(window):
            start = tab_widget.currentIndex()
            for index in range(tab_widget.count()):
                if index == start:
                    continue
                tab_widget.setCurrentIndex(index)
                _pump(app, 80)
                tab_name = f"{theme_name}_{namespace}_{_slug(tab_widget.tabText(index))}.png"
                window.grab().save(str(out / tab_name))
                files.append(tab_name)
            tab_widget.setCurrentIndex(start)
            _pump(app, 20)


def _capture_figures(
    result: Any, out: Path, theme_name: str, dark: bool, files: list[str], errors: dict[str, str]
) -> None:
    """Render every public ``result.plot.*`` figure headlessly at the fixed size."""
    out.mkdir(parents=True, exist_ok=True)
    namespace = ResultPlotNamespace(result)
    names = sorted(
        n for n in dir(namespace) if not n.startswith("_") and callable(getattr(namespace, n))
    )
    with plot_theme(dark=dark):
        for name in names:
            try:
                figure = getattr(namespace, name)()
            except Exception as exc:  # noqa: BLE001 — a figure that cannot render is a finding, recorded
                errors[name] = f"{type(exc).__name__}: {exc}"
                continue
            figure.set_size_inches(*FIGURE_SIZE_IN)
            file_name = f"{theme_name}_{name}.png"
            figure.savefig(out / file_name, dpi=FIGURE_DPI)
            files.append(f"figures/{file_name}")


def capture_config(
    app: QApplication,
    config: Path,
    out_root: Path,
    themes: tuple[str, ...],
    size: tuple[int, int],
    scratch: Path,
    figures: bool,
) -> None:
    """Capture one config or study in every requested theme."""
    out = out_root / config.stem
    out.mkdir(parents=True, exist_ok=True)
    sidecar: dict[str, Any] = {"runs": []}
    for theme_name in themes:
        dark = theme_name == "dark"
        apply_theme(app, tokens.LIGHT)
        settings = _new_settings(scratch, f"{config.stem}_{theme_name}")
        window = RADIANTMainWindow(
            config_set=ConfigurationSet.load(config), path=str(config), settings=settings
        )
        window.resize(*size)
        window.show()
        _pump(app)
        window._evaluate_now()
        evaluated = _wait_for_result(app, window)
        if dark:
            window._on_toggle_theme()
            _pump(app, 80)
        files: list[str] = []
        errors: dict[str, str] = {}
        _capture_window(app, window, out, theme_name, files)
        if figures and window.last_result is not None:
            _capture_figures(window.last_result, out / "figures", theme_name, dark, files, errors)
        run = _environment(theme_name, size, config)
        run.update({"evaluated": evaluated, "files": files, "figure_errors": errors})
        sidecar["runs"].append(run)
        window.close()
        _pump(app, 20)
        print(f"{config.stem} [{theme_name}]: {len(files)} files, {len(errors)} figure errors")
    (out / "capture.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")


def capture_welcome(
    app: QApplication, out_root: Path, themes: tuple[str, ...], size: tuple[int, int], scratch: Path
) -> None:
    """Capture the no-config welcome screen in every requested theme."""
    out = out_root / "welcome"
    out.mkdir(parents=True, exist_ok=True)
    sidecar: dict[str, Any] = {"runs": []}
    for theme_name in themes:
        apply_theme(app, tokens.LIGHT)
        settings = _new_settings(scratch, f"welcome_{theme_name}")
        window = RADIANTMainWindow(None, settings=settings)
        window.resize(*size)
        window.show()
        _pump(app, 80)
        if theme_name == "dark":
            window._on_toggle_theme()
            _pump(app, 80)
        name = f"{theme_name}.png"
        window.grab().save(str(out / name))
        run = _environment(theme_name, size, None)
        run["files"] = [name]
        sidecar["runs"].append(run)
        window.close()
        _pump(app, 20)
        print(f"welcome [{theme_name}]: 1 file")
    (out / "capture.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")


def _parse_size(text: str) -> tuple[int, int]:
    width, _, height = text.lower().partition("x")
    return int(width), int(height)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--config", action="append", default=[], type=Path, help="config or study (repeatable)"
    )
    parser.add_argument("--out", required=True, type=Path, help="output root")
    parser.add_argument("--theme", choices=("light", "dark", "both"), default="both")
    parser.add_argument("--size", default="1600x1000", help="window size WxH (default 1600x1000)")
    parser.add_argument("--welcome", action="store_true", help="also capture the welcome screen")
    parser.add_argument("--no-figures", action="store_true", help="skip headless figure renders")
    args = parser.parse_args(argv)

    themes: tuple[str, ...] = ("light", "dark") if args.theme == "both" else (args.theme,)
    size = _parse_size(args.size)
    out_root: Path = args.out
    out_root.mkdir(parents=True, exist_ok=True)
    scratch = out_root / "_settings"
    scratch.mkdir(exist_ok=True)

    app = QApplication.instance() or QApplication([])
    for config in args.config:
        capture_config(app, config, out_root, themes, size, scratch, figures=not args.no_figures)
    if args.welcome:
        capture_welcome(app, out_root, themes, size, scratch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
