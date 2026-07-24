"""Lint the physics packages for in-module unit conversions and magic constants.

Enforces CLAUDE.md Rule 2 (convert units at boundaries only — a ``* pi/180`` or
``* 1e4`` inside a physics module is a red flag) and Rule 13 (physical constants
come from ``radiant.core.constants``, never hardcoded digit strings). Track C of
the 2026-07 assurance audit confirmed the nine physics packages are currently
clean; this makes that a CI tripwire so a future conversion or magic constant
fails the build instead of shipping silently (audit unenforced-risk #2, R2.2).

Scanned packages (Rule 11's physics stages)::

    geometry source atmosphere optics platform spectral_integration
    detector readout performance

What is flagged (on code tokens only — strings and comments are ignored, so
docstrings and prose are never matched):
  * Degree/radian arithmetic coupled to pi: ``pi / 180``, ``180 / pi``,
    ``* 180 / pi`` and the ``np.pi`` variants. Use ``math.radians`` /
    ``math.degrees`` (sanctioned display/threshold conversions) or convert at
    ``params.set()``.
  * The MODTRAN radiance factor ``* 1e4`` / ``* 1e-4`` (W/cm²·µm ⇄ W/m²·µm) —
    that conversion belongs in the file reader (``radiant.io`` / atmosphere
    loaders), not a physics computation.
  * Hardcoded fundamental constants — the digit strings of h, c, k_B, q, and
    σ_SB (CODATA 2018). Import them from ``radiant.core.constants`` instead.

What is NOT flagged: ``math.radians(...)`` / ``math.degrees(...)`` (the
sanctioned conversions, used for display and threshold definitions), and any
number that also appears in ``radiant/core/constants.py`` reached via import.

Suppression: a genuine at-boundary conversion of a datasheet-unit argument
(e.g. an ``r0a_ohm_cm2`` parameter converted cm²→m² at the point of use) is
allowed with a trailing ``# units-ok: <reason>`` comment on the same line. The
reason is mandatory — it turns an implicit unit assumption into an explicit,
reviewable one. Unannotated conversions fail.

Exit 0 = clean; exit 1 = violations printed with file:line. Runs in the CI
``static`` job alongside ruff / mypy / import-linter / check_org_rules.
"""

from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src" / "radiant"

PHYSICS_PACKAGES = (
    "geometry",
    "source",
    "atmosphere",
    "optics",
    "platform",
    "spectral_integration",
    "detector",
    "readout",
    "performance",
)

# Forbidden fundamental-constant digit strings (CODATA 2018). Matched against the
# text of NUMBER tokens only. Values live in radiant.core.constants.
_CONSTANT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"6\.62[0-9]{0,7}e-?34", "Planck constant h — import `h` from radiant.core.constants"),
    (r"6\.62607015", "Planck constant h — import `h` from radiant.core.constants"),
    (r"1\.380649", "Boltzmann constant k_B — import `k_B` from radiant.core.constants"),
    (r"1\.38[0-9]{0,4}e-?23", "Boltzmann constant k_B — import `k_B` from radiant.core.constants"),
    (r"2\.99792458", "speed of light c — import `c` from radiant.core.constants"),
    (r"2\.998e8", "speed of light c — import `c` from radiant.core.constants"),
    (r"1\.602176[0-9]*", "elementary charge q — import `q` from radiant.core.constants"),
    (r"1\.602e-?19", "elementary charge q — import `q` from radiant.core.constants"),
    (r"5\.6703[0-9]*e-?8", "Stefan–Boltzmann σ — import `sigma_sb` from radiant.core.constants"),
    (r"5\.67e-?8", "Stefan–Boltzmann σ — import `sigma_sb` from radiant.core.constants"),
)
_CONSTANT_RES = tuple((re.compile(p), msg) for p, msg in _CONSTANT_PATTERNS)

# Degree↔radian arithmetic coupled to pi (on the reconstructed code line).
_DEGREE_RES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?:math\.|np\.)?pi\s*/\s*180"),
        "pi/180 degree→radian conversion — use math.radians or convert at params.set()",
    ),
    (
        re.compile(r"180\s*/\s*(?:math\.|np\.)?pi"),
        "180/pi radian→degree conversion — use math.degrees or convert at the boundary",
    ),
)

# MODTRAN radiance-unit factor (W/cm² ⇄ W/m²). Belongs in the file reader.
_FACTOR_RE = re.compile(r"\*\s*1\.?0?e-?4\b|\b1\.?0?e-?4\s*\*")

# Trailing opt-out for a documented at-boundary conversion. The reason text is
# required (see module docstring); a bare marker still counts as suppression but
# reviewers should reject one without a reason.
_SUPPRESS_RE = re.compile(r"#\s*units-ok\b")


def _code_only_lines(path: Path) -> dict[int, str]:
    """Return {lineno: reconstructed code text} with strings/comments blanked.

    Uses ``tokenize`` so docstrings, comments, and string literals never trip a
    pattern — only executable tokens are reassembled per physical line.
    """
    src = path.read_text(encoding="utf-8")
    lines: dict[int, str] = {}
    try:
        tokens = tokenize.generate_tokens(io.StringIO(src).readline)
        for tok in tokens:
            if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.FSTRING_MIDDLE):
                continue
            if tok.type in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
                continue
            text = tok.string
            if not text.strip():
                continue
            lines[tok.start[0]] = lines.get(tok.start[0], "") + " " + text
    except (tokenize.TokenError, IndentationError):
        # Fall back to raw text for a file tokenize cannot parse (should not
        # happen for tracked source, but never silently skip it).
        for i, raw in enumerate(src.splitlines(), start=1):
            lines[i] = raw
    return lines


def _check_file(path: Path) -> list[str]:
    violations: list[str] = []
    rel = path.relative_to(REPO)
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    for lineno, code in sorted(_code_only_lines(path).items()):
        raw = raw_lines[lineno - 1] if 0 < lineno <= len(raw_lines) else ""
        if _SUPPRESS_RE.search(raw):
            continue  # documented at-boundary conversion (# units-ok: <reason>)
        for rx, msg in _DEGREE_RES:
            if rx.search(code):
                violations.append(f"{rel}:{lineno}: {msg}")
        if _FACTOR_RE.search(code):
            violations.append(
                f"{rel}:{lineno}: '* 1e-4/1e4' unit factor — MODTRAN W/cm²↔W/m² "
                "conversion belongs in the file reader (radiant.io / atmosphere loaders)"
            )
        for rx, msg in _CONSTANT_RES:
            if rx.search(code):
                violations.append(f"{rel}:{lineno}: hardcoded {msg}")
                break  # one constant report per line (patterns can overlap)
    return violations


def main() -> int:
    violations: list[str] = []
    for pkg in PHYSICS_PACKAGES:
        pkg_dir = SRC / pkg
        if not pkg_dir.is_dir():
            print(f"WARNING: physics package not found: {pkg_dir}", file=sys.stderr)
            continue
        for path in sorted(pkg_dir.rglob("*.py")):
            if "/tests/" in path.as_posix():
                continue  # tests legitimately use literal anchors
            violations.extend(_check_file(path))

    if violations:
        print("Physics-module conversion/constant lint FAILED:\n")
        for v in violations:
            print(f"  {v}")
        print(
            f"\n{len(violations)} violation(s). Convert units at boundaries only (Rule 2) "
            "and import physical constants from radiant.core.constants (Rule 13)."
        )
        return 1
    print(f"Physics-module conversion/constant lint: clean ({len(PHYSICS_PACKAGES)} packages).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
