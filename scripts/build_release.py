"""Build the RADIANT release: typeset manuals + scenario suite, in the wheel and as artifacts.

Support_Documentation_Plan §9 Phase 5 / ruling Q1: the four PDF volumes ship **both**
inside the wheel (``radiant/manuals/``) and as standalone release artifacts; the repo
never commits a PDF (Rule 26 — they are regenerable). Owner direction 2026-09-17 folded
the scenario suite into the same step: the manuals document all 51 scenarios, so a
pip-installed RADIANT carries the suite the manuals point at (``radiant/scenarios/``),
and a standalone zip is attached alongside.

One command::

    export PATH="$PATH:/Library/TeX/texbin"     # macOS MacTeX, if not already on PATH
    python scripts/build_release.py

What it does, in order:

1. Checks the toolchain (pandoc, xelatex, the ``build`` frontend) and that the tree is
   clean — a release stamp must not read ``-dirty`` (``--allow-dirty`` overrides).
2. Builds every populated volume as PDF via ``scripts/build_manual.py --all``.
3. Stages ``build/manuals/*.pdf`` into ``src/radiant/manuals/`` and every **git-tracked**
   file under ``scenarios/`` into ``src/radiant/scenarios/``. Tracked-only is deliberate:
   a glob would sweep in gitignored MODTRAN artifacts, result workbooks and ``__pycache__``.
   Both staging trees are ephemeral — created here, removed at the end (``--keep`` skips
   the cleanup for debugging) — and gitignored so they can never be committed.
4. Builds the sdist and the wheel (``python -m build``; the wheel is built *from* the
   sdist, so this exercises the ``MANIFEST.in`` path as well as ``package-data``).
5. **Verifies the wheel** by reading it as a zip: the expected PDF count under
   ``radiant/manuals/``, a scenario file count that matches the tracked set exactly, no
   ``__pycache__``/``.pyc``, no ``__init__.py`` anywhere in the staged scenario tree (the
   scenario ``.py`` files are data, not a subpackage), and spot keys present.
6. Assembles ``build/release/``: the four PDFs, ``radiant_scenarios_<version>.zip`` built
   from the same tracked set, the wheel and the sdist — with sizes and the version stamp.

Any mismatch exits nonzero. The script writes nothing outside ``build/``, ``dist/`` and
the two ephemeral staging directories.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_manual import VOLUMES, package_version, version_string  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
BUILD = REPO / "build"
MANUAL_BUILD = BUILD / "manuals"
RELEASE = BUILD / "release"
DIST = REPO / "dist"
PACKAGE = REPO / "src" / "radiant"
STAGED_MANUALS = PACKAGE / "manuals"
STAGED_SCENARIOS = PACKAGE / "scenarios"

#: Repo-relative prefix of the canonical scenario suite. Its single home stays
#: ``scenarios/`` (plan §9); the staged copy under the package is a build product.
SCENARIO_PREFIX = "scenarios/"

#: Where the staged trees land inside the wheel.
WHEEL_MANUALS = "radiant/manuals/"
WHEEL_SCENARIOS = "radiant/scenarios/"

#: Files whose presence in the wheel is asserted by name — a count alone would not
#: catch a staging bug that dropped the suite's own entry point documentation.
SPOT_KEYS = (
    "radiant/scenarios/README.md",
    "radiant/manuals/radiant_theory.pdf",
)


# --------------------------------------------------------------------------------------
# Pure helpers (unit-tested in scripts/test_build_release.py — no subprocess, no I/O)
# --------------------------------------------------------------------------------------


def parse_tracked_files(stdout: str) -> list[str]:
    """Parse ``git ls-files -z`` output into repo-relative POSIX paths.

    NUL-separated rather than newline-separated on purpose: git quotes (and escapes)
    paths containing spaces or non-ASCII bytes in its newline form, which would silently
    corrupt a path on the way to ``shutil.copy2``. ``-z`` emits them verbatim.
    """
    return [entry for entry in stdout.split("\0") if entry]


def staging_targets(
    tracked: Sequence[str], repo: Path, staged_root: Path, *, prefix: str = SCENARIO_PREFIX
) -> list[tuple[Path, Path]]:
    """Map tracked scenario paths to ``(source, destination)`` pairs, preserving layout.

    ``scenarios/01_sarah/1.1_foo/run.py`` stages at ``<staged_root>/01_sarah/1.1_foo/run.py``.

    Raises
    ------
    ValueError
        If an entry is outside *prefix* or escapes the tree (``..``) — either means the
        caller listed something other than the scenario suite, and copying it would write
        outside the staging directory.
    """
    pairs: list[tuple[Path, Path]] = []
    for entry in tracked:
        if not entry.startswith(prefix):
            raise ValueError(f"tracked entry {entry!r} is outside {prefix!r}")
        rel = PurePosixPath(entry[len(prefix) :])
        if not rel.parts or ".." in rel.parts or rel.is_absolute():
            raise ValueError(f"tracked entry {entry!r} does not name a file inside {prefix!r}")
        pairs.append((repo / PurePosixPath(entry), staged_root / rel))
    return pairs


def verify_wheel_names(
    names: Sequence[str],
    *,
    scenario_count: int,
    pdf_count: int,
    spot_keys: Sequence[str] = SPOT_KEYS,
) -> list[str]:
    """Return one problem string per defect in a wheel's member-name list (empty = good).

    Pure so the predicate is testable against a synthetic name list; the caller reads the
    real names out of the built wheel with :mod:`zipfile`.
    """
    problems: list[str] = []

    manuals = [n for n in names if n.startswith(WHEEL_MANUALS)]
    pdfs = [n for n in manuals if n.endswith(".pdf")]
    if len(pdfs) != pdf_count:
        problems.append(
            f"expected {pdf_count} PDF(s) under {WHEEL_MANUALS}, found {len(pdfs)}: {sorted(pdfs)}"
        )
    strays = sorted(set(manuals) - set(pdfs))
    if strays:
        problems.append(f"non-PDF file(s) staged under {WHEEL_MANUALS}: {strays}")

    scenarios = [n for n in names if n.startswith(WHEEL_SCENARIOS)]
    if len(scenarios) != scenario_count:
        problems.append(
            f"expected {scenario_count} scenario file(s) under {WHEEL_SCENARIOS} "
            f"(the git-tracked count), found {len(scenarios)}"
        )

    polluted = sorted(n for n in names if "__pycache__" in PurePosixPath(n).parts)
    if polluted:
        problems.append(f"__pycache__ entries in the wheel: {polluted[:5]}")
    compiled = sorted(n for n in names if n.endswith((".pyc", ".pyo")))
    if compiled:
        problems.append(f"compiled bytecode in the wheel: {compiled[:5]}")

    # The scenario .py files are DATA. An __init__.py anywhere under the staged tree would
    # turn them into importable subpackages of radiant and put scenario code on the import
    # path — the opposite of what shipping the suite means.
    inits = sorted(n for n in scenarios if PurePosixPath(n).name == "__init__.py")
    if inits:
        problems.append(
            f"__init__.py in the staged scenario tree (it is data, not a package): {inits}"
        )

    missing = [key for key in spot_keys if key not in set(names)]
    if missing:
        problems.append(f"expected file(s) absent from the wheel: {missing}")
    return problems


def human_size(num_bytes: int) -> str:
    """Format a byte count as a short human-readable string (``1.4 MB``)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    raise AssertionError("unreachable")  # pragma: no cover


# --------------------------------------------------------------------------------------
# Preconditions
# --------------------------------------------------------------------------------------


def check_tools() -> int:
    """Verify pandoc, xelatex and the ``build`` frontend are available. 0 when they are."""
    if shutil.which("pandoc") is None:
        print(
            "error: pandoc not found on PATH.\n"
            "  why: the manuals are single-sourced from Markdown; pandoc does the conversion.\n"
            "  action: install pandoc (https://pandoc.org/installing.html) and re-run.",
            file=sys.stderr,
        )
        return 1
    if shutil.which("xelatex") is None:
        print(
            "error: xelatex not found on PATH.\n"
            "  why: the release ships typeset PDFs; XeLaTeX does the typesetting.\n"
            "  action: install TeX Live / MacTeX, and put it on PATH for this shell —\n"
            '          macOS: export PATH="$PATH:/Library/TeX/texbin"\n'
            "          (this script checks PATH only; it never guesses install locations).",
            file=sys.stderr,
        )
        return 1
    try:
        import build as _build  # noqa: F401
    except ImportError:
        print(
            "error: the `build` frontend is not installed.\n"
            "  why: the wheel and sdist are built with `python -m build`.\n"
            "  action: pip install build",
            file=sys.stderr,
        )
        return 1
    return 0


def git_output(args: list[str]) -> str:
    """Run a git command in the repo and return stdout; raises on failure."""
    result = subprocess.run(
        ["git", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


def check_clean(*, allow_dirty: bool) -> int:
    """Refuse to stamp a release from a dirty tree unless explicitly allowed."""
    if shutil.which("git") is None:
        print(
            "error: git not found on PATH.\n"
            "  why: the release stamp and the scenario file list both come from git.\n"
            "  action: install git, or run inside a checkout with git available.",
            file=sys.stderr,
        )
        return 1
    dirty = git_output(["status", "--porcelain"]).strip()
    if dirty and not allow_dirty:
        shown = "\n".join(f"      {line}" for line in dirty.splitlines()[:10])
        print(
            "error: the working tree is not clean.\n"
            "  why: every cover page carries `git describe --dirty`; a released PDF that\n"
            "       reads '-dirty' cannot be traced back to a commit.\n"
            "  action: commit or stash the changes below, then re-run "
            "(or pass --allow-dirty for a test build):\n" + shown,
            file=sys.stderr,
        )
        return 1
    if dirty:
        print("warning: building from a dirty tree — the version stamp will read '-dirty'.")
    return 0


# --------------------------------------------------------------------------------------
# Build steps
# --------------------------------------------------------------------------------------


def build_manuals() -> int:
    """Run the manual builder for every populated volume."""
    print("[1/5] building manuals ...")
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build_manual.py"), "--all"],
        cwd=REPO,
        check=False,
    )
    if result.returncode != 0:
        print(
            "error: the manual build failed (see output above).\n"
            "  why: the release cannot ship volumes that do not typeset.\n"
            "  action: fix the reported chapter, then re-run.",
            file=sys.stderr,
        )
        return result.returncode
    return 0


def stage_manuals(expected: int) -> tuple[list[Path], int]:
    """Copy the built PDFs into the package staging directory. Returns ``(pdfs, status)``."""
    pdfs = sorted(MANUAL_BUILD.glob("radiant_*.pdf"))
    if len(pdfs) != expected:
        print(
            f"error: expected {expected} built volume PDF(s) in "
            f"{MANUAL_BUILD.relative_to(REPO).as_posix()}, found {len(pdfs)}.\n"
            "  why: the wheel's manual set is the suite; a partial set is not a release.\n"
            "  action: remove build/manuals/ and re-run so every volume is rebuilt.",
            file=sys.stderr,
        )
        return [], 1
    STAGED_MANUALS.mkdir(parents=True, exist_ok=True)
    for pdf in pdfs:
        shutil.copy2(pdf, STAGED_MANUALS / pdf.name)
    return pdfs, 0


def tracked_scenarios() -> list[str]:
    """Every git-tracked file under ``scenarios/``, repo-relative, sorted."""
    return sorted(parse_tracked_files(git_output(["ls-files", "-z", SCENARIO_PREFIX])))


def stage_scenarios(tracked: Sequence[str]) -> int:
    """Copy the tracked scenario suite into the package staging directory."""
    for source, destination in staging_targets(tracked, REPO, STAGED_SCENARIOS):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return 0


def clear_staging() -> None:
    """Remove both ephemeral staging trees (idempotent)."""
    for tree in (STAGED_MANUALS, STAGED_SCENARIOS):
        if tree.exists():
            shutil.rmtree(tree)


def build_distributions(*, no_isolation: bool) -> tuple[Path, Path, int]:
    """Build the sdist and wheel. Returns ``(wheel, sdist, status)``."""
    print("[3/5] building sdist + wheel ...")
    if DIST.exists():
        shutil.rmtree(DIST)
    cmd = [sys.executable, "-m", "build"]
    if no_isolation:
        cmd.append("--no-isolation")
    result = subprocess.run(cmd, cwd=REPO, check=False)
    if result.returncode != 0:
        print(
            "error: `python -m build` failed (see output above).\n"
            "  why: the wheel and sdist are the release's installable artifacts.\n"
            "  action: fix the reported packaging error; if the failure is a network\n"
            "          timeout fetching the build backend, re-run with --no-isolation\n"
            "          (uses the setuptools already installed in this environment).",
            file=sys.stderr,
        )
        return Path(), Path(), result.returncode

    wheels = sorted(DIST.glob("*.whl"))
    sdists = sorted(DIST.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        print(
            f"error: expected exactly one wheel and one sdist in dist/, found "
            f"{len(wheels)} wheel(s) and {len(sdists)} sdist(s).\n"
            "  why: the verification and artifact steps address one of each by name.\n"
            "  action: remove dist/ and re-run.",
            file=sys.stderr,
        )
        return Path(), Path(), 1
    return wheels[0], sdists[0], 0


def verify_wheel(wheel: Path, *, scenario_count: int, pdf_count: int) -> int:
    """Open the built wheel and check what actually landed inside it."""
    print("[4/5] verifying wheel contents ...")
    with zipfile.ZipFile(wheel) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
    names = [info.filename for info in infos]
    problems = verify_wheel_names(names, scenario_count=scenario_count, pdf_count=pdf_count)
    if problems:
        print(f"error: {wheel.name} failed verification:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "  why: shipping the manuals and the scenario suite IS the Phase 5 capability;\n"
            "       a wheel missing them installs a documentation-less RADIANT.\n"
            "  action: check [tool.setuptools.package-data] and MANIFEST.in, then re-run.",
            file=sys.stderr,
        )
        return 1

    sizes = {info.filename: info.file_size for info in infos}
    manual_bytes = sum(v for k, v in sizes.items() if k.startswith(WHEEL_MANUALS))
    scenario_bytes = sum(v for k, v in sizes.items() if k.startswith(WHEEL_SCENARIOS))
    print(f"  wheel                  {wheel.name}  ({human_size(wheel.stat().st_size)} on disk)")
    print(f"  members                {len(names)}")
    print(f"  radiant/manuals/       {pdf_count} PDFs, {human_size(manual_bytes)} uncompressed")
    print(
        f"  radiant/scenarios/     {scenario_count} files, "
        f"{human_size(scenario_bytes)} uncompressed"
    )
    print("  __pycache__ / *.pyc    none")
    print("  scenario __init__.py   none (the suite ships as data)")
    print(f"  spot keys              {len(SPOT_KEYS)}/{len(SPOT_KEYS)} present")
    return 0


def write_scenario_zip(tracked: Sequence[str], version: str) -> Path:
    """Zip the same tracked scenario set as a standalone release artifact."""
    out = RELEASE / f"radiant_scenarios_{version}.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in tracked:
            archive.write(REPO / PurePosixPath(entry), arcname=entry)
    return out


def assemble_release(
    pdfs: Sequence[Path], wheel: Path, sdist: Path, tracked: Sequence[str], version: str
) -> list[Path]:
    """Collect every shipped artifact under ``build/release/`` and return the list."""
    print("[5/5] assembling release artifacts ...")
    if RELEASE.exists():
        shutil.rmtree(RELEASE)
    RELEASE.mkdir(parents=True)
    artifacts = [shutil.copy2(pdf, RELEASE / pdf.name) for pdf in pdfs]
    collected = [Path(a) for a in artifacts]
    collected.append(write_scenario_zip(tracked, version))
    collected.append(Path(shutil.copy2(wheel, RELEASE / wheel.name)))
    collected.append(Path(shutil.copy2(sdist, RELEASE / sdist.name)))
    return collected


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="build_release.py",
        description=(
            "Build the RADIANT release: four typeset manuals + the scenario suite, "
            "staged into the wheel and assembled as standalone artifacts."
        ),
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="build from a dirty tree (the version stamp will read '-dirty')",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the ephemeral src/radiant/{manuals,scenarios} staging trees for debugging",
    )
    parser.add_argument(
        "--no-isolation",
        action="store_true",
        help="pass --no-isolation to `python -m build` (offline / no PyPI access)",
    )
    args = parser.parse_args(argv)

    # The build steps are subprocesses that write straight to this stdout. Without line
    # buffering here, the step markers are flushed at exit and the captured log reads as
    # if pandoc ran before the script started.
    sys.stdout.reconfigure(line_buffering=True)

    status = check_tools()
    if status != 0:
        return status
    status = check_clean(allow_dirty=args.allow_dirty)
    if status != 0:
        return status

    pdf_count = sum(1 for volume in VOLUMES.values() if volume.chapters)
    version = package_version()

    clear_staging()
    try:
        status = build_manuals()
        if status != 0:
            return status

        print("[2/5] staging manuals + scenario suite into the package ...")
        pdfs, status = stage_manuals(pdf_count)
        if status != 0:
            return status
        tracked = tracked_scenarios()
        if not tracked:
            print(
                "error: git lists no tracked files under scenarios/.\n"
                "  why: the scenario suite is half the Phase 5 payload.\n"
                "  action: run from a full checkout (not a sparse or partial clone).",
                file=sys.stderr,
            )
            return 1
        stage_scenarios(tracked)
        print(f"  staged {len(pdfs)} PDF(s) and {len(tracked)} scenario file(s)")

        wheel, sdist, status = build_distributions(no_isolation=args.no_isolation)
        if status != 0:
            return status
        status = verify_wheel(wheel, scenario_count=len(tracked), pdf_count=pdf_count)
        if status != 0:
            return status
        artifacts = assemble_release(pdfs, wheel, sdist, tracked, version)
    finally:
        if args.keep:
            print("note: --keep — staging trees left in place under src/radiant/ (gitignored).")
        else:
            clear_staging()

    print(f"\nRADIANT release {version_string()}")
    print(f"artifacts in {RELEASE.relative_to(REPO).as_posix()}/:")
    for artifact in artifacts:
        print(f"  {artifact.name:<48} {human_size(artifact.stat().st_size):>10}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
