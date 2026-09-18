"""Build the RADIANT manual suite as typeset PDFs (or ``.tex``) via Pandoc + XeLaTeX.

Single-source rule (OPERATING_MODEL §5.4): the Markdown chapters under ``docs/`` are the
canonical text; this script *generates* the typeset output. The PDFs are regenerable
artifacts (Rule 26) — gitignored, never hand-edited, never forked to ``.tex`` sources.

The suite is defined by :data:`VOLUMES` (Support_Documentation_Plan §8). Each volume names
its title, subtitle and an ordered chapter list of paths relative to ``docs/``; a chapter
may live under ``theory/``, ``guides/`` or ``architecture/``. Volumes whose chapter list is
still empty are content that lands in a later phase of that plan: ``--all`` skips them with
a printed note, and asking for one by name is an error.

Usage::

    python scripts/build_manual.py theory              # -> build/manuals/radiant_theory.pdf
    python scripts/build_manual.py theory --tex        # -> build/manuals/radiant_theory.tex
    python scripts/build_manual.py --all               # every volume that has chapters
    python scripts/build_manual.py --all --tex         # conversion-only (no TeX install)

Requires ``pandoc`` on PATH; PDF output additionally requires ``xelatex`` (TeX Live or
MacTeX). Missing tools raise an actionable error rather than a stack trace.

Before invoking pandoc the builder validates the bound sources (chapters exist, referenced
local images resolve, no raw HTML in manual-class Markdown, balanced ``$$``). This is a
build-time check, not a merge gate — the process-machinery moratorium stands.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
ARCHITECTURE = DOCS / "architecture"
ASSETS = Path(__file__).resolve().parent / "manual_assets"
DEFAULTS_FILE = ASSETS / "manual.yaml"
HEADER_FILE = ASSETS / "manual_header.tex"
TABLE_FILTER = ASSETS / "wide_tables.lua"
HEADING_FILTER = ASSETS / "heading_numbers.lua"
BUILD = REPO / "build" / "manuals"

#: Author line on every cover page (ruling Q6 — minimal cover identity).
AUTHOR = "RADIANT Project"


@dataclass(frozen=True)
class Volume:
    """One bound volume of the suite.

    ``chapters`` are paths relative to ``docs/``, in binding order. An empty tuple means
    the volume is registered but its content has not been written yet.

    ``appendices`` are chapters bound *after* a LaTeX ``\\appendix`` marker, so they are
    lettered rather than numbered. They are ordinary Markdown sources — validated,
    staged, and resource-pathed exactly like chapters.
    """

    key: str
    title: str
    subtitle: str
    chapters: tuple[str, ...]
    appendices: tuple[str, ...] = ()

    @property
    def phase_note(self) -> str:
        """Which plan phase writes this volume's chapters (used in the skip/error text)."""
        return _PHASE_NOTES[self.key]

    @property
    def sources(self) -> tuple[str, ...]:
        """Every bound source in binding order — chapters then appendices."""
        return (*self.chapters, *self.appendices)


#: Which Support_Documentation_Plan §9 phase populates each volume. Kept beside the
#: registry so the "not yet written" message names the work item rather than shrugging.
_PHASE_NOTES: dict[str, str] = {
    "theory": "Phase 1 (Theory Manual v1.0)",
    "users_guide": "Phase 3 (User's Guide v1.0)",
    "tech_ref": "Phase 2 (Technical Reference v1.0)",
    "examples": "Phase 4 (Examples & Validation v1.0)",
}

#: The four-volume suite (Support_Documentation_Plan §3). Volume I is bound in the plan's
#: §4 TOC order: front-matter notation, introduction, then geometry BEFORE the radiometric
#: chain (the geometry-first ordering of ADR-0006), the atmosphere, spatial, noise,
#: calibration and metric chapters, the mixed-train appendix, and references last.
VOLUMES: dict[str, Volume] = {
    "theory": Volume(
        key="theory",
        title="RADIANT Theory Manual",
        subtitle="Physics Reference for the RADIANT EO Sensor Performance Model",
        chapters=(
            "theory/notation.md",
            "theory/introduction.md",
            "theory/geometry.md",
            "theory/radiometric_chain.md",
            "theory/atmosphere_models.md",
            "theory/spatial_model.md",
            "theory/noise_model.md",
            "theory/calibration_model.md",
            "theory/performance_metrics.md",
        ),
        appendices=(
            "theory/radiometric_model_mixed_train.md",
            "theory/references.md",
        ),
    ),
    "users_guide": Volume(
        key="users_guide",
        title="RADIANT User's Guide",
        subtitle="Installation, Concepts, and GUI Operation",
        chapters=(
            # Batch 1 — orientation and the scene side (ch. 1–6)
            "guides/ug_introduction.md",
            "guides/ug_installation.md",
            "guides/ug_quickstart_tour.md",
            "guides/ug_core_concepts.md",
            "guides/ug_main_window.md",
            "guides/ug_defining_scene.md",
            # Batch 2 — the sensor side and the workflows around it (ch. 7–12)
            "guides/ug_defining_sensor.md",
            "guides/ug_configuration_sets.md",
            "guides/ug_running_results.md",
            "guides/ug_sweeps_trades.md",
            "guides/ug_yaml_roundtrip.md",
            "guides/ug_troubleshooting.md",
        ),
        # Appendix A — bound behind the \appendix break so it numbers A, not 13.
        appendices=("guides/ug_menu_reference.md",),
    ),
    "tech_ref": Volume(
        key="tech_ref",
        title="RADIANT Technical Reference",
        subtitle="Scripting API, Configuration, Parameters, and Architecture",
        chapters=(
            # Part 1 — Orientation (distilled)
            "guides/tech_overview.md",
            "guides/tech_conventions.md",
            # Part 2 — Reference (reused guides + generated content)
            "guides/scripting.md",
            "guides/tech_cli.md",
            "guides/configuration.md",
            "guides/parameter_reference.md",  # generated by gen_param_reference.py
            "guides/tech_errors.md",
            "guides/tech_data_libraries.md",
            "guides/tech_external_data.md",
            # Part 3 — Internals (the three architecture specs bound verbatim,
            # ruling Q2; prepare_chapter strips their metadata headers).
            "guides/tech_internals_preface.md",
            "architecture/RADIANT_Signal_Chain_Architecture.md",
            "architecture/RADIANT_Parameter_System.md",
            "architecture/RADIANT_Testing_Validation.md",
            "guides/tech_extending.md",
        ),
    ),
    # Volume IV is written in plan order (Support_Documentation_Plan §7): Part A
    # (ch. 1–2, GUI-driven), Part B (ch. 3, scripted), then Part C (the eight full-depth
    # persona case studies and the scenario digest compendium) and Part D (flagship
    # validation, the trade-study cookbook, the scenario index appendix). The order of
    # the tuple *is* the binding order, so new chapters go on the end rather than
    # anywhere convenient.
    "examples": Volume(
        key="examples",
        title="RADIANT Worked Examples & Validation",
        subtitle="Case Studies, Scenario Digests, and Validation Evidence",
        chapters=(
            # Part A — driving RADIANT from the GUI
            "guides/examples_running.md",
            "guides/examples_gui.md",
            # Part B — driving RADIANT from scripts
            "guides/examples_scripting.md",
            # Part C — tier-1 full-depth persona case studies, in plan §7 order:
            # three GUI-led (1.1, 2.1, 3.1), then the four script-led (4.1, 5.1,
            # 6.1, 7.1), then the closing GUI-led 10.2.
            "guides/examples_case_maritime_mwir.md",
            "guides/examples_case_detector_shootout.md",
            "guides/examples_case_pass_planning.md",
            "guides/examples_case_detection_matrix.md",
            "guides/examples_case_wfe_budget.md",
            "guides/examples_case_datasheet_benchmark.md",
            "guides/examples_case_nedt_reconciliation.md",
            "guides/examples_case_irst_level_arm.md",
            # Part C tier 2 — the scenario digest compendium (plan §7, owner ruling Q3:
            # every scenario appears; the ~40 not covered at full depth get 1-2 page
            # digests, grouped by persona in catalog order).
            "guides/examples_digests.md",
            # Part D — the flagship-mission validation chapter and the trade-study
            # cookbook, in plan §7 order (ch. 13, 14). The scenario index binds as the
            # volume's appendix below, after the \appendix marker.
            "guides/examples_validation.md",
            "guides/examples_cookbook.md",
        ),
        appendices=("guides/examples_scenario_index.md",),
    ),
}


# --------------------------------------------------------------------------------------
# Source scanning helpers (pure functions — unit-tested in scripts/test_build_manual.py)
# --------------------------------------------------------------------------------------

#: A fenced-code delimiter: up to three leading spaces, then 3+ backticks or tildes.
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")

#: An inline code span. Blanked before scanning so a ``<div>`` *shown* as code is not
#: mistaken for raw HTML.
_INLINE_CODE_RE = re.compile(r"`+[^`\n]*`+")

#: An opening or closing HTML tag. The ``(?=[\s/>])`` lookahead is what keeps Markdown
#: autolinks out of the match: ``<https://example.com>`` has ``:`` after the name and
#: ``<user@example.com>`` has ``@``, so neither can match.
_TAG_RE = re.compile(r"</?([A-Za-z][A-Za-z0-9]*)(?=[\s/>])[^<>]*>")

#: Tag names the raw-HTML scan reports. An allowlist rather than "any tag-shaped thing",
#: so prose such as ``$a <b>$`` in grandfathered Unicode math cannot fail a build.
_HTML_TAGS = frozenset(
    {
        "a", "b", "big", "blockquote", "br", "center", "code", "details", "div", "em",
        "figcaption", "figure", "font", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i",
        "iframe", "img", "kbd", "li", "mark", "ol", "p", "pre", "script", "small",
        "span", "strong", "style", "sub", "summary", "sup", "table", "tbody", "td",
        "tfoot", "th", "thead", "tr", "u", "ul",
    }
)  # fmt: skip

#: A Markdown image. Captures the destination, tolerating pointy-bracket destinations.
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)>\s]+)>?")

#: XeLaTeX's log line for a glyph the font cannot supply, e.g.
#: ``Missing character: There is no ⁻ (U+207B) in font ...``. Captures the character.
_MISSING_CHAR_RE = re.compile(r"Missing character: There is no (\S+) \(U\+[0-9A-Fa-f]+\)")

#: Destinations the image check does not try to resolve on disk.
_REMOTE_PREFIXES = ("http://", "https://", "data:", "ftp://", "mailto:", "//")

#: ``**Key:**`` at the start of a line — the metadata block form the ``architecture/``
#: specs use under their H1 (``**Date:**``, ``**Status:**``, ``**Depends on:**``,
#: ``**Scope:**``). Ruling Q2 strips this block when a spec is bound as a chapter.
_META_LINE_RE = re.compile(r"^\*\*[A-Za-z][A-Za-z0-9 _/&'\-]*:\*\*")

#: A thematic break closing the metadata block.
_RULE_RE = re.compile(r"^ {0,3}(-{3,}|\*{3,}|_{3,})\s*$")


def content_lines(text: str) -> list[tuple[int, str]]:
    """Return ``(line_number, line)`` for prose lines only.

    Fenced code blocks are dropped whole and inline code spans are blanked, so the
    scans below see only text that pandoc will typeset as prose. Line numbers are
    1-based and refer to the original file.
    """
    out: list[tuple[int, str]] = []
    fence: str | None = None
    for lineno, raw in enumerate(text.splitlines(), start=1):
        match = _FENCE_RE.match(raw)
        marker = match.group(1)[0] if match else None
        if fence is None:
            if marker is not None:
                fence = marker
            else:
                out.append((lineno, _INLINE_CODE_RE.sub(" ", raw)))
        elif marker == fence:
            fence = None
    return out


def scan_raw_html(text: str) -> list[tuple[int, str]]:
    """Return ``(line_number, tag)`` for every raw HTML tag outside code (§5.4 rule 2)."""
    found: list[tuple[int, str]] = []
    for lineno, line in content_lines(text):
        for match in _TAG_RE.finditer(line):
            if match.group(1).lower() in _HTML_TAGS:
                found.append((lineno, match.group(0)))
    return found


def count_display_math(text: str) -> int:
    """Return the number of ``$$`` delimiters outside code; an odd count is unbalanced."""
    return sum(line.count("$$") for _, line in content_lines(text))


def scan_images(text: str) -> list[tuple[int, str]]:
    """Return ``(line_number, destination)`` for every local Markdown image.

    Prose lines are joined paragraph-wise before matching, because an image whose
    caption wraps across source lines (``![long caption\\n...](dest)``) is invisible
    to a per-line regex — that hole let a missing figure through the Phase 0
    validator. The reported line number is the paragraph's first line.
    """
    found: list[tuple[int, str]] = []
    para_start: int | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal para_start, buffer
        if buffer and para_start is not None:
            joined = " ".join(buffer)
            for match in _IMAGE_RE.finditer(joined):
                dest = match.group(1)
                if not dest.lower().startswith(_REMOTE_PREFIXES):
                    found.append((para_start, dest))
        para_start, buffer = None, []

    for lineno, line in content_lines(text):
        if line.strip():
            if para_start is None:
                para_start = lineno
            buffer.append(line)
        else:
            flush()
    flush()
    return found


#: An emphasized ``*Persona: ...*`` audience tag near a chapter's top. Repo-internal
#: metadata (the RADIANT_Personas.md user model) that orients repo readers and agents;
#: meaningless to a manual reader, so the builder drops it at build time (sources keep
#: their tags — owner-flagged on the first render review, 2026-09-17).
_PERSONA_LINE_RE = re.compile(r"^\*Persona:.*\*\s*$")


def strip_persona_line(text: str) -> str:
    """Drop a leading ``*Persona: ...*`` tag line (and its trailing blank line).

    Only a line within the first few lines of the chapter is considered, so a
    literal mention of the word deeper in prose is never touched. Text without
    such a line is returned unchanged.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines[:6]):
        if _PERSONA_LINE_RE.match(line):
            tail = i + 1
            while tail < len(lines) and not lines[tail].strip():
                tail += 1
            kept = [*lines[:i], *lines[tail:]]
            return "\n".join(kept) + ("\n" if text.endswith("\n") else "")
    return text


def strip_spec_header(text: str) -> str:
    """Drop the leading ``**Key:**`` metadata block of an ``architecture/`` spec.

    Ruling Q2: the three Part-3 specs are bound verbatim, minus their
    Date/Status/Depends-on/Scope header, which is repository bookkeeping rather than
    manual content. The block is the run of ``**Key:**`` lines immediately after the H1;
    a thematic break that closes it is removed with it. Files on disk are never modified
    — the stripped text goes to a temp file.

    Text that does not open with an H1 followed by such a block is returned unchanged.
    """
    lines = text.splitlines()
    head = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    if head is None:
        return text

    cursor = head + 1
    while cursor < len(lines) and not lines[cursor].strip():
        cursor += 1
    if cursor >= len(lines) or not _META_LINE_RE.match(lines[cursor].rstrip()):
        return text
    while cursor < len(lines) and _META_LINE_RE.match(lines[cursor].rstrip()):
        cursor += 1

    tail = cursor
    while tail < len(lines) and not lines[tail].strip():
        tail += 1
    if tail < len(lines) and _RULE_RE.match(lines[tail]):
        tail += 1
        while tail < len(lines) and not lines[tail].strip():
            tail += 1

    kept = [*lines[: head + 1], "", *lines[tail:]]
    return "\n".join(kept) + ("\n" if text.endswith("\n") else "")


# --------------------------------------------------------------------------------------
# Build-time validation
# --------------------------------------------------------------------------------------


def validate_chapter(path: Path) -> list[str]:
    """Return one problem string per defect found in the chapter at *path*."""
    problems: list[str] = []
    rel = path.relative_to(REPO).as_posix()
    text = path.read_text(encoding="utf-8")

    for lineno, tag in scan_raw_html(text):
        problems.append(
            f"{rel}:{lineno}: raw HTML tag `{tag}` in a manual-class chapter\n"
            f"    why: OPERATING_MODEL §5.4 keeps manual sources in the Pandoc subset; "
            f"raw HTML is dropped or mis-typeset by the LaTeX writer.\n"
            f"    action: rewrite as Markdown (pipe table, fenced block, or `$...$` math)."
        )

    delimiters = count_display_math(text)
    if delimiters % 2 != 0:
        problems.append(
            f"{rel}: unbalanced display math — {delimiters} `$$` delimiters outside code\n"
            f"    why: an unclosed `$$` swallows the rest of the chapter into math mode.\n"
            f"    action: find the unpaired `$$` and close it."
        )

    for lineno, dest in scan_images(text):
        target = (path.parent / dest).resolve()
        if not target.is_file():
            problems.append(
                f"{rel}:{lineno}: image `{dest}` does not resolve to a file\n"
                f"    why: pandoc emits a missing-image warning and the figure is lost.\n"
                f"    action: fix the relative path, or generate the figure before building."
            )
    return problems


def validate_volume(volume: Volume) -> list[str]:
    """Return one problem string per defect in *volume*'s bound sources (appendices too)."""
    problems: list[str] = []
    for chapter in volume.sources:
        path = DOCS / chapter
        if not path.is_file():
            problems.append(
                f"docs/{chapter}: chapter file is missing\n"
                f"    why: volume '{volume.key}' binds it; pandoc cannot open it.\n"
                f"    action: restore the file, or drop it from VOLUMES in this script."
            )
            continue
        problems.extend(validate_chapter(path))
    return problems


# --------------------------------------------------------------------------------------
# Version and cover-page metadata
# --------------------------------------------------------------------------------------

#: Anything outside this set is replaced in the version string — it lands in LaTeX.
_VERSION_SAFE_RE = re.compile(r"[^A-Za-z0-9.+\- ]")


def package_version() -> str:
    """``__version__`` read out of ``src/radiant/__init__.py``.

    Read rather than imported: the builder must work in a checkout with no installed
    package (the CI conversion tripwire installs pandoc only).
    """
    init = REPO / "src" / "radiant" / "__init__.py"
    try:
        text = init.read_text(encoding="utf-8")
    except OSError:
        return "unknown"
    match = re.search(r"^__version__\s*=\s*[\"']([^\"']+)[\"']", text, re.MULTILINE)
    return match.group(1) if match else "unknown"


def git_describe() -> str:
    """``git describe --always --dirty``, or ``""`` when git or the history is absent."""
    if shutil.which("git") is None:
        return ""
    try:
        result = subprocess.run(
            ["git", "describe", "--always", "--dirty"],
            cwd=REPO,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def version_string() -> str:
    """The cover-page version line, e.g. ``v0.1.0 (776e1c9d-dirty)``."""
    version = _VERSION_SAFE_RE.sub("-", package_version())
    described = _VERSION_SAFE_RE.sub("-", git_describe())
    return f"v{version} ({described})" if described else f"v{version}"


def latex_escape(text: str) -> str:
    """Escape the LaTeX specials that can appear in a volume title."""
    out = text.replace("\\", r"\textbackslash{}")
    for char in "&%$#_{}":
        out = out.replace(char, "\\" + char)
    return out.replace("~", r"\textasciitilde{}").replace("^", r"\textasciicircum{}")


def write_metadata_file(volume: Volume, tmpdir: Path, built_on: str) -> Path:
    """Write the per-build Pandoc metadata (cover page) file and return its path."""
    path = tmpdir / "metadata.yaml"
    path.write_text(
        "---\n"
        f"title: {json.dumps(volume.title)}\n"
        f"subtitle: {json.dumps(volume.subtitle)}\n"
        f"author: {json.dumps(AUTHOR)}\n"
        "date: |\n"
        f"  {version_string()}\\\n"
        f"  Built {built_on}\n"
        "---\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def write_volume_header(volume: Volume, tmpdir: Path) -> Path:
    """Write the per-build LaTeX snippet carrying the running-head text."""
    path = tmpdir / "volume_header.tex"
    path.write_text(
        "% Generated per build by scripts/build_manual.py — do not edit.\n"
        f"\\newcommand{{\\radiantrunninghead}}{{{latex_escape(volume.title)}}}\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


# --------------------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------------------


def prepare_chapter(chapter: str, tmpdir: Path, index: int) -> Path:
    """Return the path pandoc should read for *chapter*.

    Usually the source itself. For an ``architecture/`` spec whose metadata header is
    stripped (ruling Q2), a temp copy of the stripped text.
    """
    source = DOCS / chapter
    text = source.read_text(encoding="utf-8")
    stripped = strip_persona_line(text)
    if ARCHITECTURE in source.parents:
        stripped = strip_spec_header(stripped)
    if stripped == text:
        return source
    staged = tmpdir / f"{index:02d}_{source.name}"
    staged.write_text(stripped, encoding="utf-8", newline="\n")
    return staged


def write_appendix_marker(tmpdir: Path) -> Path:
    """Write the generated source that opens the appendix run, and return its path.

    A raw-LaTeX block carrying ``\\appendix``: everything pandoc emits after it is
    lettered rather than numbered. It is a generated staging file, never a repository
    source — the marker belongs to the binding, not to any chapter's text. Passing it
    through needs ``raw_attribute`` in the reader's format (``manual.yaml``), which
    admits fenced ``{=latex}`` blocks and nothing else, so ordinary prose is unaffected.
    """
    path = tmpdir / "00_appendix_marker.md"
    path.write_text(
        "```{=latex}\n\\appendix\n```\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def build_volume(volume: Volume, *, as_tex: bool) -> int:
    """Build one volume. Returns 0 on success, nonzero on failure."""
    problems = validate_volume(volume)
    if problems:
        print(f"error: volume '{volume.key}' failed source validation:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    BUILD.mkdir(parents=True, exist_ok=True)
    out = BUILD / f"radiant_{volume.key}.{'tex' if as_tex else 'pdf'}"

    with tempfile.TemporaryDirectory(prefix="radiant-manual-") as tmpname:
        tmpdir = Path(tmpname)
        sources = [
            prepare_chapter(chapter, tmpdir, i)
            for i, chapter in enumerate(volume.chapters, start=1)
        ]
        if volume.appendices:
            sources.append(write_appendix_marker(tmpdir))
            sources.extend(
                prepare_chapter(chapter, tmpdir, i)
                for i, chapter in enumerate(volume.appendices, start=len(volume.chapters) + 1)
            )
        metadata = write_metadata_file(volume, tmpdir, date.today().isoformat())
        volume_header = write_volume_header(volume, tmpdir)
        resource_dirs = [str(REPO), *dict.fromkeys(str((DOCS / c).parent) for c in volume.sources)]

        cmd = [
            "pandoc",
            "--defaults",
            str(DEFAULTS_FILE),
            "--metadata-file",
            str(metadata),
            "--resource-path",
            os.pathsep.join(resource_dirs),
            "--include-in-header",
            str(volume_header),
            "--include-in-header",
            str(HEADER_FILE),
            # The gfm reader assigns no column widths, so wide tables overflow the
            # page; this filter replicates the markdown reader's width heuristic.
            "--lua-filter",
            str(TABLE_FILTER),
            # Hand-numbered headings ("## 3. Foo") would double up against
            # --number-sections; the literal ordinal is dropped at build time only.
            "--lua-filter",
            str(HEADING_FILTER),
            *[str(p) for p in sources],
            "-o",
            str(out),
        ]
        result = subprocess.run(
            cmd, cwd=REPO, check=False, capture_output=True, text=True, encoding="utf-8"
        )

    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        print(
            f"error: pandoc failed while building volume '{volume.key}' (see output above).\n"
            f"  why: the Markdown sources did not convert.\n"
            f"  action: fix the reported construct in the chapter pandoc names, then re-run.",
            file=sys.stderr,
        )
        return result.returncode

    # XeTeX drops a glyph the font lacks SILENTLY in the PDF and only mentions it in
    # a log warning — "e⁻" typesetting as "e" is a correctness defect, not cosmetics.
    # The shared preamble maps the known grandfathered characters to LaTeX; anything
    # NOT covered by that list fails the build here rather than shipping dropped text.
    missing = sorted(set(_MISSING_CHAR_RE.findall(result.stderr)))
    if missing:
        sys.stderr.write(result.stderr)
        print(
            f"error: volume '{volume.key}' typeset with dropped glyphs: {' '.join(missing)}\n"
            "  why: the selected fonts lack these characters; XeTeX omits them from the\n"
            "       PDF silently, so text like 'e⁻' would print as 'e'.\n"
            "  action: add a \\newunicodechar mapping for each to\n"
            "          scripts/manual_assets/manual_header.tex (see the existing block).",
            file=sys.stderr,
        )
        return 1
    print(f"built {out.relative_to(REPO).as_posix()}  ({volume.title})")
    return 0


def check_tools(*, as_tex: bool) -> int:
    """Verify the external toolchain is present. Returns 0 when it is."""
    if shutil.which("pandoc") is None:
        print(
            "error: pandoc not found on PATH.\n"
            "  why: the manuals are single-sourced from Markdown; pandoc does the conversion.\n"
            "  action: install pandoc (https://pandoc.org/installing.html) and re-run.",
            file=sys.stderr,
        )
        return 1
    if not as_tex and shutil.which("xelatex") is None:
        print(
            "error: xelatex not found on PATH (needed for PDF output).\n"
            "  why: XeLaTeX handles the manuals' Unicode (µ, °, ²) and the TeX Gyre /\n"
            "       DejaVu OpenType faces the shared template selects.\n"
            "  action: install TeX Live / MacTeX (or BasicTeX + `tlmgr install xetex`),\n"
            "          or run with --tex to emit .tex without typesetting.",
            file=sys.stderr,
        )
        return 1
    for asset in (DEFAULTS_FILE, HEADER_FILE, TABLE_FILTER, HEADING_FILTER):
        if not asset.is_file():
            print(
                f"error: shared manual template asset missing: "
                f"{asset.relative_to(REPO).as_posix()}\n"
                "  why: every volume is typeset from one template; there is no per-volume fork.\n"
                "  action: restore the file from git (scripts/manual_assets/).",
                file=sys.stderr,
            )
            return 1
    return 0


def resolve_volumes(names: list[str], *, build_all: bool) -> tuple[list[Volume], int]:
    """Turn CLI selection into the list of volumes to build. Returns ``(volumes, status)``."""
    known = ", ".join(VOLUMES)
    if build_all:
        selected: list[Volume] = []
        for volume in VOLUMES.values():
            if volume.chapters:
                selected.append(volume)
            else:
                print(
                    f"note: skipping volume '{volume.key}' ({volume.title}) — no chapters "
                    f"bound yet; content lands in {volume.phase_note}."
                )
        return selected, 0

    if not names:
        print(
            "error: no volume selected.\n"
            f"  why: the suite has four volumes ({known}); the builder does not guess.\n"
            "  action: name one or more volumes, or pass --all.",
            file=sys.stderr,
        )
        return [], 2

    selected = []
    for name in names:
        volume = VOLUMES.get(name)
        if volume is None:
            print(
                f"error: unknown volume '{name}'.\n"
                f"  why: the suite is a closed set defined by VOLUMES in this script.\n"
                f"  action: choose one of: {known} (or pass --all).",
                file=sys.stderr,
            )
            return [], 2
        if not volume.chapters:
            print(
                f"error: volume '{name}' ({volume.title}) has no chapters bound yet.\n"
                f"  why: its content is written in {volume.phase_note} of "
                f"docs/plans/Support_Documentation_Plan.md.\n"
                f"  action: build a populated volume (--all skips the empty ones), or add "
                f"its chapters to VOLUMES first.",
                file=sys.stderr,
            )
            return [], 1
        selected.append(volume)
    return selected, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="build_manual.py",
        description="Build one or more volumes of the RADIANT manual suite.",
    )
    parser.add_argument(
        "volumes",
        nargs="*",
        metavar="VOLUME",
        help=f"volume key(s) to build: {', '.join(VOLUMES)}",
    )
    parser.add_argument("--all", action="store_true", help="build every populated volume")
    parser.add_argument(
        "--tex", action="store_true", help="emit standalone .tex (no xelatex needed)"
    )
    args = parser.parse_args(argv)

    if args.all and args.volumes:
        print(
            "error: --all and an explicit volume list are mutually exclusive.\n"
            "  why: the two say different things about what to build.\n"
            "  action: pass --all, or name the volumes, not both.",
            file=sys.stderr,
        )
        return 2

    volumes, status = resolve_volumes(args.volumes, build_all=args.all)
    if status != 0:
        return status
    if not volumes:
        print("note: nothing to build — no volume has chapters bound yet.")
        return 0

    status = check_tools(as_tex=args.tex)
    if status != 0:
        return status

    failures = [v.key for v in volumes if build_volume(v, as_tex=args.tex) != 0]
    if failures:
        print(f"error: {len(failures)} volume(s) failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
