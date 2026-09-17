"""Generate the manual's GUI figures by driving the real GUI offscreen.

Single-source rule (Support_Documentation_Plan §5): every GUI figure in the manual
suite is *generated* from the shipped GUI on a committed input config, never
hand-captured. A stale screenshot is then a one-command fix rather than an
archaeology project::

    python scripts/gen_gui_screenshots.py --all

Ruling Q7 (owner-ratified 2026-09-16): **all** figures are captured under
``QT_QPA_PLATFORM=offscreen``. Offscreen rendering paints Fusion-style chrome rather
than native macOS/Windows decorations, which makes the figures platform-neutral —
the same bytes regardless of who regenerates them. There are no native "hero shots".

How it works
------------
For each :class:`Capture` in :data:`CAPTURES` the generator builds the *real*
:class:`~radiant.gui.main_window.RADIANTMainWindow` on the named config, waits for the
auto-evaluation that the window schedules on load (``QTimer.singleShot(0,
_evaluate_now)`` → worker thread → ``evaluationFinished``), selects the requested stage
workspace, applies any per-figure dock geometry, and writes ``QWidget.grab()`` to
``docs/guides/figures/gui/<name>.png``. Captures therefore show an **evaluated** window
— populated KPI cards and plots — not an empty shell.

Two spike lessons (plan §5) are first-class registry fields: the default parameter-dock
width elides long parameter names, so a capture can widen it (``param_dock_width``), and
detail figures are made by grabbing a single child widget rather than the whole window
(``target``).

Usage::

    python scripts/gen_gui_screenshots.py --list             # capture names
    python scripts/gen_gui_screenshots.py optics_workspace   # one (or several)
    python scripts/gen_gui_screenshots.py --all              # everything
    python scripts/gen_gui_screenshots.py --all --out /tmp/x # smoke-test elsewhere

Requires the optional ``gui`` extra (``pip install -e ".[gui]"``). Every run also
rewrites ``MANIFEST.md`` next to the figures — the Rule 26(b) provenance record naming
this generator, each figure's input config and window size, and the current commit.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - import-time typing only
    from PySide6.QtWidgets import QWidget

# Headless Qt, pinned before anything can construct a QApplication (the GUI suite's
# conftest does the same). ``setdefault`` so a developer debugging a capture can run
# with a real display: ``QT_QPA_PLATFORM=cocoa python scripts/gen_gui_screenshots.py ...``
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The scripting console defaults to an in-process Jupyter kernel (CU-138); every window
# this script builds would pay that startup. The REPL fallback is the same backend the
# GUI suite pins, and the console is not in any figure.
os.environ.setdefault("RADIANT_CONSOLE_FORCE_REPL", "1")

REPO = Path(__file__).resolve().parents[1]
FIGURES = REPO / "docs" / "guides" / "figures" / "gui"
MANIFEST_NAME = "MANIFEST.md"

#: Default capture geometry (plan §5: 1440×900, the size the spike proved).
DEFAULT_WIDTH = 1440
DEFAULT_HEIGHT = 900

#: A capture name must be a safe, lowercase file stem — it *is* the PNG filename.
NAME_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")

#: How long to wait for the window's auto-evaluation before failing (seconds). The
#: GUI suite allows 15 s per window; a cold first run pays import + atmosphere load.
EVALUATION_TIMEOUT_S = 120.0


class ScreenshotError(RuntimeError):
    """A capture could not be produced. Carries an actionable message (Rule 15 style).

    Deliberately *not* a :class:`radiant.core.exceptions.RadiantError`: this is build
    tooling outside the library's error taxonomy, and the script must be importable in
    a checkout with no installed package.
    """


@dataclass(frozen=True)
class Capture:
    """One named figure: what to load, what to show, and how big to make it.

    Parameters
    ----------
    name:
        Capture name — also the PNG stem (``<name>.png``) and the CLI selector.
    config:
        Repo-relative path of the input config (an ``examples/`` YAML, a scenario
        baseline, or a GUI exercise baseline).
    stage:
        Stage namespace whose workspace to show (``"performance"``, ``"geometry"``, …),
        or ``None`` to capture the window as it opens.
    target:
        Dotted attribute path of a child widget to grab instead of the whole window
        (e.g. ``"parameter_panel"``, ``"central_canvas.stage_center"``). Panel-level
        grabs are how detail figures are made (plan §5 spike lesson).
    width, height:
        Window size in pixels before the grab.
    param_dock_width:
        Width in pixels to force on the left Parameters dock. The default proportions
        elide long parameter names (plan §5 spike lesson), so parameter-tree figures
        widen it.
    rail_dock_width:
        Width in pixels to force on the right rail dock.
    splitter_sizes:
        Pixel sizes to force on named splitters inside the window, keyed by Qt
        ``objectName`` (e.g. ``{"stagePanelSplit": (520, 380)}``). A figure that needs
        one pane of a stage workspace bigger sets this rather than the whole window.
    caption:
        One line describing what the figure shows — carried into the manifest.
    """

    name: str
    config: str
    stage: str | None = None
    target: str | None = None
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    param_dock_width: int | None = None
    rail_dock_width: int | None = None
    splitter_sizes: Mapping[str, tuple[int, ...]] = field(default_factory=dict)
    caption: str = ""

    @property
    def filename(self) -> str:
        """The PNG filename this capture writes."""
        return f"{self.name}.png"

    @property
    def config_path(self) -> Path:
        """Absolute path of the input config."""
        return REPO / self.config


_MINIMAL = "examples/mwir_leo_minimal.yaml"

#: The capture registry. Phase 0 ships the four workspaces the feasibility spike proved;
#: Phases 3–4 add definitions here (and only here) as the prose needs them.
CAPTURES: tuple[Capture, ...] = (
    Capture(
        name="performance_workspace",
        config=_MINIMAL,
        stage="performance",
        caption="Performance workspace on the minimal MWIR LEO example, after evaluation.",
    ),
    Capture(
        name="geometry_workspace",
        config=_MINIMAL,
        stage="geometry",
        caption="Geometry workspace — viewing schematic and derived ranges.",
    ),
    Capture(
        name="optics_workspace",
        config=_MINIMAL,
        stage="optics",
        caption="Optics workspace — PSF and MTF views.",
    ),
    Capture(
        name="detector_workspace",
        config=_MINIMAL,
        stage="detector",
        caption="Detector workspace — QE and noise-term breakdown.",
    ),
)


# -- pure helpers (unit-tested; no Qt) --------------------------------------------


def capture_by_name(name: str) -> Capture | None:
    """The registry entry called *name*, or ``None``."""
    for capture in CAPTURES:
        if capture.name == name:
            return capture
    return None


def validate_registry(captures: tuple[Capture, ...] = CAPTURES) -> list[str]:
    """Problems with the capture registry, one message per problem (empty when sound).

    Checked: unique names, filename-safe names, input configs that exist, positive
    window sizes, dock widths that fit inside the window, and splitter sizes that are
    a non-empty run of positive pixel sizes.
    """
    problems: list[str] = []
    seen: set[str] = set()
    for capture in captures:
        if capture.name in seen:
            problems.append(f"duplicate capture name: {capture.name}")
        seen.add(capture.name)
        if not NAME_RE.match(capture.name):
            problems.append(
                f"capture name is not a safe file stem: {capture.name!r} "
                "(lowercase letters, digits, single underscores)"
            )
        if not capture.config_path.is_file():
            problems.append(f"{capture.name}: input config not found: {capture.config}")
        if capture.width <= 0 or capture.height <= 0:
            problems.append(
                f"{capture.name}: window size must be positive, got "
                f"{capture.width}x{capture.height}"
            )
        for label, dock_width in (
            ("param_dock_width", capture.param_dock_width),
            ("rail_dock_width", capture.rail_dock_width),
        ):
            if dock_width is not None and not 0 < dock_width < capture.width:
                problems.append(
                    f"{capture.name}: {label}={dock_width} does not fit in a "
                    f"{capture.width}px-wide window"
                )
        for object_name, sizes in capture.splitter_sizes.items():
            if not sizes or any(size <= 0 for size in sizes):
                problems.append(
                    f"{capture.name}: splitter_sizes[{object_name!r}]={tuple(sizes)} must be "
                    "a non-empty run of positive pixel sizes"
                )
    return problems


def git_commit() -> str:
    """``git rev-parse --short HEAD``, or ``"unknown"`` when git or the history is absent."""
    if shutil.which("git") is None:
        return "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError:
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def png_dimensions(path: Path) -> tuple[int, int]:
    """``(width, height)`` read straight out of a PNG's IHDR chunk.

    Header-only, so verifying a generated figure needs no image library (Rule: no new
    dependencies). Raises :class:`ScreenshotError` if the file is not a PNG.
    """
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ScreenshotError(
            f"not a PNG file: {path}\n"
            "  why: the figure verifier reads width/height from the PNG IHDR chunk.\n"
            "  action: delete the file and re-run the generator for that capture."
        )
    width, height = struct.unpack(">II", header[16:24])
    return int(width), int(height)


def render_manifest(
    captures: tuple[Capture, ...] = CAPTURES,
    *,
    commit: str = "unknown",
    generated_on: str = "",
) -> str:
    """The provenance record for the figure set (Rule 26(b)).

    Names the generator, every figure's input config, capture name, window size and
    the commit the figures were generated from. Rendered from the whole registry, not
    from the subset a partial run regenerated, so the file does not churn with the CLI
    selection.
    """
    stamp = generated_on or date.today().isoformat()
    lines = [
        "# GUI Figure Manifest",
        "",
        "Status: Generated — do not hand-edit.",
        "",
        "Every figure in this folder is produced by `scripts/gen_gui_screenshots.py`,",
        "which drives the real `RADIANTMainWindow` under `QT_QPA_PLATFORM=offscreen` on a",
        "committed input config and grabs the window (or a named panel) after the window's",
        "auto-evaluation completes. Offscreen rendering uses platform-neutral Fusion chrome",
        "(Support_Documentation_Plan §10, ruling Q7), so the figures do not depend on who",
        "regenerated them.",
        "",
        "Regenerate the whole set with:",
        "",
        "```",
        "python scripts/gen_gui_screenshots.py --all",
        "```",
        "",
        "- Generator: `scripts/gen_gui_screenshots.py`",
        f"- Commit: `{commit}`",
        f"- Generated: {stamp}",
        f"- Figures: {len(captures)}",
        "",
        "| Figure | Capture | Input config | Workspace | Target | Window |",
        "|---|---|---|---|---|---|",
    ]
    for capture in captures:
        target = f"`{capture.target}`" if capture.target else "full window"
        stage = f"`{capture.stage}`" if capture.stage else "as opened"
        lines.append(
            f"| `{capture.filename}` | `{capture.name}` | `{capture.config}` | "
            f"{stage} | {target} | {capture.width}×{capture.height} |"
        )
    lines.append("")
    captioned = [c for c in captures if c.caption]
    if captioned:
        lines.append("## Captions")
        lines.append("")
        for capture in captioned:
            lines.append(f"- `{capture.filename}` — {capture.caption}")
        lines.append("")
    return "\n".join(lines)


def write_manifest(out_dir: Path, *, commit: str | None = None) -> Path:
    """Write :func:`render_manifest` into *out_dir*. Returns the manifest path."""
    path = out_dir / MANIFEST_NAME
    path.write_text(
        render_manifest(commit=commit if commit is not None else git_commit()),
        encoding="utf-8",
    )
    return path


# -- Qt driving ------------------------------------------------------------------


def require_pyside() -> None:
    """Fail with an actionable message when the optional ``gui`` extra is absent."""
    try:
        import PySide6  # noqa: F401
    except ImportError as exc:
        raise ScreenshotError(
            "PySide6 is not installed, so the GUI cannot be driven.\n"
            "  why: the manual's GUI figures are captured from the real RADIANT GUI,\n"
            "       which ships in the optional 'gui' extra.\n"
            '  action: pip install -e ".[gui]" and re-run.'
        ) from exc


def _resolve_target(window: object, dotted: str) -> QWidget:
    """Resolve a dotted attribute path against *window*, e.g. ``central_canvas.stage_center``."""
    current: Any = window
    walked: list[str] = []
    for part in dotted.split("."):
        walked.append(part)
        if not hasattr(current, part):
            raise ScreenshotError(
                f"capture target {dotted!r} does not resolve: no attribute "
                f"{'.'.join(walked)!r} on the main window.\n"
                "  why: panel-level figures grab a child widget by its public accessor.\n"
                "  action: name an accessor that exists on RADIANTMainWindow "
                "(e.g. parameter_panel, central_canvas, right_rail, stage_strip)."
            )
        current = getattr(current, part)
    return current  # type: ignore[no-any-return]


def _wait_for_evaluation(app: Any, window: Any, timeout_s: float) -> None:
    """Block until the window's auto-evaluation has produced a run, or fail loudly.

    The window schedules its first evaluation with ``QTimer.singleShot(0,
    _evaluate_now)`` and runs it on a worker thread, so the result only appears once
    the event loop has turned. This pumps the loop and polls ``last_run`` — the same
    completion signal the GUI tests await via ``evaluationFinished`` — never sleeping
    blindly and never hanging (Rule 17: no silent failure).
    """
    from PySide6.QtCore import QEventLoop

    deadline = time.monotonic() + timeout_s
    while window.last_run is None:
        if time.monotonic() > deadline:
            raise ScreenshotError(
                f"the GUI did not finish evaluating within {timeout_s:.0f} s.\n"
                "  why: figures must show populated metrics, so the capture waits for the\n"
                "       window's auto-evaluation (RADIANTMainWindow.last_run) to complete.\n"
                "  action: check that the input config resolves — run\n"
                "          `radiant run <config>` — then re-run this generator."
            )
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    # One more turn so the result-driven repaint (KPI cards, figures) has been applied.
    _settle(app, turns=5)


def _settle(app: Any, *, turns: int = 3) -> None:
    """Pump the event loop a few times so pending layout/paint work is applied."""
    from PySide6.QtCore import QEventLoop

    for _ in range(turns):
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)


def _apply_geometry(window: Any, capture: Capture) -> None:
    """Apply the capture's dock widths and named splitter sizes.

    Called **after** the window is shown, evaluated and switched to the capture's
    stage: the per-stage composites (and their splitters) are built on selection, and
    the dock split is renegotiated by the swap, so an earlier application would be
    overwritten — or would look for a widget that does not exist yet.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDockWidget, QSplitter

    docks: list[QDockWidget] = []
    widths: list[int] = []
    for object_name, wanted in (
        ("parameterDock", capture.param_dock_width),
        ("rightRailDock", capture.rail_dock_width),
    ):
        if wanted is None:
            continue
        dock = window.findChild(QDockWidget, object_name)
        if dock is None:
            raise ScreenshotError(
                f"{capture.name}: dock {object_name!r} not found on the main window.\n"
                "  why: the capture asks for a non-default dock width.\n"
                "  action: the GUI's dock objectNames changed — update this generator."
            )
        docks.append(dock)
        widths.append(wanted)
    if docks:
        window.resizeDocks(docks, widths, Qt.Orientation.Horizontal)

    for object_name, sizes in capture.splitter_sizes.items():
        # Several stage composites build a splitter with the *same* objectName (e.g.
        # "stagePanelSplit" per stage panel), and the unselected ones stay in the tree
        # as hidden pages — so a bare findChild would silently size the wrong, invisible
        # one. Only the visible matches (the ones in the figure) are touched.
        matches = window.findChildren(QSplitter, object_name)
        visible = [s for s in matches if s.isVisible()]
        if not visible:
            raise ScreenshotError(
                f"{capture.name}: no visible splitter named {object_name!r} in this "
                f"workspace ({len(matches)} hidden match(es)).\n"
                "  why: the capture asks for non-default splitter sizes, and the pane it\n"
                "       names is either absent from this workspace or has been renamed.\n"
                "  action: check the objectName against the stage's widget "
                "(src/radiant/gui/widgets/), or drop the splitter_sizes entry."
            )
        for splitter in visible:
            splitter.setSizes(list(sizes))


def _release(app: Any, window: Any) -> None:
    """Close and actually delete a captured window (the CU-212 accumulation fix).

    ``close()`` only hides; without the ``deleteLater`` + deferred-delete drain, every
    window a multi-capture run builds stays in the live widget tree that
    ``QApplication.setStyleSheet`` walks.

    Teardown-only, so it swallows the one error class it can provoke: pumping the loop
    after a delete can deliver a timer whose target C++ object is already gone
    (shiboken's ``Internal C++ object already deleted``). Letting that escape a
    ``finally`` would *replace* the real capture failure with teardown noise — which is
    exactly how the actionable message for a bad capture definition got masked. Nothing
    else is suppressed, and a genuine capture error still propagates from the caller.
    """
    import contextlib

    from PySide6.QtCore import QEvent

    with contextlib.suppress(RuntimeError):
        window.close()
        window.setParent(None)
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        _settle(app, turns=2)


def _qapplication(settings_dir: Path) -> Any:
    """The process-wide :class:`QApplication`, themed light and sandboxed from user prefs.

    The light theme is pinned rather than read from ``QSettings`` so the figures do not
    depend on whether the developer regenerating them last used dark mode; redirecting
    the INI path keeps the run from reading *or writing* the real user's GUI
    preferences (the same sandbox the GUI suite's conftest installs).
    """
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from radiant.gui.themes import LIGHT, apply_theme

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_dir))

    app = QApplication.instance() or QApplication([])
    apply_theme(app, LIGHT)
    return app


def capture_one(app: Any, capture: Capture, out_dir: Path) -> Path:
    """Build the window for *capture*, wait for its evaluation, grab it, write the PNG."""
    from radiant.api.sensor import Sensor
    from radiant.gui.main_window import RADIANTMainWindow
    from radiant.gui.settings_store import SettingsStore

    if not capture.config_path.is_file():
        raise ScreenshotError(
            f"{capture.name}: input config not found: {capture.config}\n"
            "  why: every figure is generated from a committed config.\n"
            "  action: fix the capture's `config` field in scripts/gen_gui_screenshots.py."
        )

    sensor = Sensor.load(capture.config_path)
    window = RADIANTMainWindow(sensor, path=str(capture.config_path), settings=SettingsStore())
    try:
        # Size first (the layout the window realizes must be the captured one), then
        # show, evaluate, select the stage, and only then apply the fine geometry.
        window.resize(capture.width, capture.height)
        window.show()
        _settle(app)
        _wait_for_evaluation(app, window, EVALUATION_TIMEOUT_S)

        if capture.stage is not None:
            window.stage_strip.stageClicked.emit(capture.stage)
            _settle(app, turns=5)
        _apply_geometry(window, capture)
        _settle(app, turns=3)

        widget = _resolve_target(window, capture.target) if capture.target else window
        pixmap = widget.grab()
        if pixmap.isNull():
            raise ScreenshotError(
                f"{capture.name}: QWidget.grab() produced an empty pixmap.\n"
                "  why: an unrealized or zero-sized widget cannot be rendered.\n"
                "  action: check the capture's target and window size."
            )
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / capture.filename
        if not pixmap.save(str(path), "PNG"):
            raise ScreenshotError(
                f"{capture.name}: could not write {path}.\n"
                "  why: Qt refused to encode or write the PNG.\n"
                "  action: check the output directory is writable and has free space."
            )
        return path
    finally:
        _release(app, window)


def run_captures(captures: list[Capture], out_dir: Path) -> int:
    """Capture every entry in *captures* into *out_dir*, then refresh the manifest."""
    require_pyside()
    with tempfile.TemporaryDirectory(prefix="radiant-shots-") as settings_dir:
        app = _qapplication(Path(settings_dir))
        for capture in captures:
            path = capture_one(app, capture, out_dir)
            width, height = png_dimensions(path)
            size_kb = path.stat().st_size / 1024
            print(
                f"wrote {path.relative_to(REPO) if path.is_relative_to(REPO) else path} "
                f"({width}x{height} px, {size_kb:.0f} kB)"
            )
    manifest = write_manifest(out_dir)
    print(f"wrote {manifest.relative_to(REPO) if manifest.is_relative_to(REPO) else manifest}")
    return 0


# -- CLI ---------------------------------------------------------------------------


def resolve_captures(names: list[str], *, capture_all: bool) -> tuple[list[Capture], int]:
    """Turn the CLI selection into a capture list. Returns ``(captures, status)``."""
    known = ", ".join(c.name for c in CAPTURES)
    if capture_all:
        return list(CAPTURES), 0
    if not names:
        print(
            "error: no capture named, and --all not given.\n"
            f"  why: the generator needs to know what to capture. Known: {known}\n"
            "  action: pass one or more capture names, --all, or --list.",
            file=sys.stderr,
        )
        return [], 2
    selected: list[Capture] = []
    for name in names:
        capture = capture_by_name(name)
        if capture is None:
            print(
                f"error: unknown capture: {name}\n"
                f"  why: only registered captures can be generated. Known: {known}\n"
                "  action: run with --list, or add the capture to CAPTURES in this script.",
                file=sys.stderr,
            )
            return [], 2
        selected.append(capture)
    return selected, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gen_gui_screenshots.py",
        description="Generate the manual's GUI figures by driving the GUI offscreen.",
    )
    parser.add_argument(
        "captures",
        nargs="*",
        metavar="NAME",
        help="capture name(s) to generate (see --list)",
    )
    parser.add_argument("--all", action="store_true", help="generate every registered capture")
    parser.add_argument("--list", action="store_true", help="list capture names and exit")
    parser.add_argument(
        "--out",
        metavar="DIR",
        default=None,
        help=f"output directory (default: {FIGURES.relative_to(REPO).as_posix()})",
    )
    args = parser.parse_args(argv)

    problems = validate_registry()
    if problems:
        for problem in problems:
            print(f"error: capture registry: {problem}", file=sys.stderr)
        return 1

    if args.list:
        for capture in CAPTURES:
            target = capture.target or "full window"
            print(
                f"{capture.name:<24} {capture.config:<32} "
                f"stage={capture.stage or '-':<12} target={target}"
            )
        return 0

    if args.all and args.captures:
        print(
            "error: --all and an explicit capture list are mutually exclusive.\n"
            "  why: the two say different things about what to generate.\n"
            "  action: pass --all, or name the captures, not both.",
            file=sys.stderr,
        )
        return 2

    captures, status = resolve_captures(args.captures, capture_all=args.all)
    if status != 0:
        return status

    out_dir = Path(args.out).expanduser().resolve() if args.out else FIGURES
    try:
        return run_captures(captures, out_dir)
    except ScreenshotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
