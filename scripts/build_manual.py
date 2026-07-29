"""Build the RADIANT theory manual as a single typeset PDF (or .tex) via Pandoc.

Single-source rule (OPERATING_MODEL §5.4): the Markdown chapters under ``docs/theory/``
are the canonical text; this script *generates* the typeset output. The PDF is a
regenerable artifact (Rule 26) — gitignored, never hand-edited, never forked to ``.tex``.

Usage:
    python scripts/build_manual.py            # PDF via xelatex -> build/radiant_theory_manual.pdf
    python scripts/build_manual.py --tex      # emit standalone .tex instead (no LaTeX install needed)

Requires ``pandoc`` on PATH; PDF output additionally requires ``xelatex`` (e.g. TeX Live
or MacTeX). Missing tools raise an actionable error rather than a stack trace.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
THEORY = REPO / "docs" / "theory"
BUILD = REPO / "build"

# Manual order: signal-chain order, references last. radiometric_model_mixed_train.md is a
# specialized supplement and is deliberately not part of the bound manual.
CHAPTERS: list[str] = [
    "radiometric_chain.md",
    "geometry.md",
    "spatial_model.md",
    "noise_model.md",
    "performance_metrics.md",
    "references.md",
]

METADATA: list[str] = [
    "--metadata",
    "title=RADIANT Theory Manual",
    "--metadata",
    "subtitle=Physics Reference for the RADIANT EO Sensor Performance Model",
    "--metadata",
    "author=RADIANT Project",
]

PANDOC_ARGS: list[str] = [
    "--from",
    "gfm+tex_math_dollars",
    "--toc",
    "--toc-depth=2",
    "--number-sections",
    "-V",
    "geometry:margin=1in",
    "-V",
    "mainfont=Helvetica Neue",
    "-V",
    "monofont=Menlo",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tex", action="store_true", help="emit standalone .tex (no xelatex needed)"
    )
    args = parser.parse_args()

    if shutil.which("pandoc") is None:
        print(
            "error: pandoc not found on PATH.\n"
            "  why: the manual is single-sourced from Markdown; pandoc performs the conversion.\n"
            "  action: install pandoc (https://pandoc.org/installing.html) and re-run.",
            file=sys.stderr,
        )
        return 1
    if not args.tex and shutil.which("xelatex") is None:
        print(
            "error: xelatex not found on PATH (needed for PDF output).\n"
            "  why: XeLaTeX handles the manual's Unicode (µ, °, ²) natively.\n"
            "  action: install TeX Live / MacTeX (or BasicTeX + `tlmgr install xetex`),\n"
            "          or run with --tex to emit a .tex file without typesetting.",
            file=sys.stderr,
        )
        return 1

    missing = [c for c in CHAPTERS if not (THEORY / c).is_file()]
    if missing:
        print(
            f"error: missing chapter file(s) under docs/theory/: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    BUILD.mkdir(exist_ok=True)
    out = BUILD / ("radiant_theory_manual.tex" if args.tex else "radiant_theory_manual.pdf")
    cmd = [
        "pandoc",
        *[str(THEORY / c) for c in CHAPTERS],
        *METADATA,
        *PANDOC_ARGS,
        *([] if args.tex else ["--pdf-engine=xelatex"]),
        *(["--standalone"] if args.tex else []),
        "-o",
        str(out),
    ]
    result = subprocess.run(cmd, cwd=REPO, check=False)
    if result.returncode != 0:
        print("error: pandoc failed (see output above).", file=sys.stderr)
        return result.returncode
    print(f"built {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
