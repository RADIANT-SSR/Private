"""Mechanical enforcement of docs/OPERATING_MODEL.md placement and naming rules.

Checks (CLAUDE.md Rules 23/25 + OPERATING_MODEL §1/§5.3/§6):
  1. docs/ top level is a closed set: index.md, OPERATING_MODEL.md + the nine folders.
  2. Repo root markdown/config files are a closed set.
  3. docs/tracking/ holds exactly Cleanup_Backlog.md and gaps.md.
  4. No project-management markdown inside Python packages (src/, dev_tools/<tool>/):
     tool roots may keep only README/ARCHITECTURE/CONTRIBUTING.
  5. Prohibited names (§5.3) anywhere in tracked files: misc*, temp*, scratch*,
     untitled*, stuff*, output<N>.<img>, spaces in filenames.
  6. Registry IDs are unique (Rules 21/22/25).
  7. Every commit SHA the registries cite is an ancestor of HEAD (Rule 22, CU-279).

Exit 0 = compliant; exit 1 = violations printed. Runs in the CI `static` job.
Only git-tracked files are checked (untracked scratch is a working-tree concern).
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DOCS_TOP_ALLOWED = {
    "index.md",
    "OPERATING_MODEL.md",
    "architecture",
    "adr",
    "guides",
    "theory",
    "validation",
    "tracking",
    "plans",
    "reports",
    "archive",
}

ROOT_ALLOWED = {
    "README.md",
    "DEVELOPMENT.md",
    "CHANGELOG.md",
    "CLAUDE.md",
    "LICENSE",
    "pyproject.toml",
    "MANIFEST.in",  # sdist data-inclusion manifest (bundled reference data → wheel)
    "mkdocs.yml",
    ".gitignore",
    ".gitattributes",
    ".pre-commit-config.yaml",
}

TRACKING_ALLOWED = {"Cleanup_Backlog.md", "gaps.md"}

# Markdown allowed at a dev_tools/<tool>/ package root (OPERATING_MODEL §6).
TOOL_ROOT_MD_ALLOWED = {"README.md", "ARCHITECTURE.md", "CONTRIBUTING.md"}

# The stem words are prohibited only as whole words within the basename
# ("temp_data.csv", "temp.py", "temp2.md" — but not "templates.py").
PROHIBITED_NAME = re.compile(
    r"(^|/)(misc|temp|tmp|scratch|untitled|stuff)(\d*)([._]|$)|(^|/)output\d*\.(png|jpg|jpeg|gif|svg)$",
    re.IGNORECASE,
)

# --- Cited-commit ancestry (Rule 22, CU-279) ---------------------------------
#
# Rule 22 requires every closure to carry a linked commit SHA, and until CU-279
# nothing checked that the link resolved to anything. Of the 221 hashes the
# backlog cited, four were real objects but *not* ancestors of `main`: three were
# deliberate provenance references (pre-cherry-pick source objects), and one — the
# sole SHA on CU-213 — was a genuinely broken link, a pre-amend twin whose work
# landed under a different hash, reachable only until the next `git gc`. A closure
# SHA that cannot be resolved is a closure that cannot be verified, which is the
# failure Rule 22 exists to prevent; it just fails one level down, at the link
# rather than the entry.
#
# The check is deliberately *object-agnostic*: `git cat-file -t` passes on all
# four of those hashes, so existence proves nothing. Only ancestry does.

#: Escape hatch. A hash that is *deliberately* not on `main` — the pre-cherry-pick
#: source object a resolution cites for provenance, or a dead hash an audit entry
#: quotes as its own evidence — is marked in the prose it appears in::
#:
#:     original commit `452cccd` (not on main)
#:
#: The marker is next to the claim rather than in an allowlist here, so a reader
#: of the entry learns the hash is unverifiable at the point they read it.
_OFF_MAIN_MARKER = " (not on main)"

#: Shortest abbreviation git will hand out, and the prefix width the ancestor
#: index is keyed on. A citation shorter than this is not matched at all.
_MIN_ABBREV = 7

#: Any backticked abbreviated-or-full hex hash, plus the marker if it follows.
#: Matched everywhere in the registry rather than only after the literal word
#: "commit", because the citation forms in use include bare lists
#: (``commits `a`, `b`, `c``), phase labels between hashes, and "cherry-picked
#: `x` as `y`" prose — a word-anchored regex checks the first hash of a list and
#: silently skips the rest, which is how the CU-047 instance went unnoticed.
_CITED_SHA = re.compile(
    rf"`(?P<sha>[0-9a-f]{{{_MIN_ABBREV},40}})`(?P<exempt>{re.escape(_OFF_MAIN_MARKER)})?"
)


def is_shallow() -> bool:
    """True if this clone lacks the history the ancestry check needs.

    A depth-1 CI checkout knows one commit, which would report all 200+ cited
    hashes as non-ancestors. The check declines to run rather than lie; CI's
    ``static`` job sets ``fetch-depth: 0`` so it does run there.
    """
    out = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=True,
    ).stdout
    return out.strip() == "true"


def ancestor_index() -> dict[str, list[str]]:
    """Map ``sha[:7] -> [full ancestor hashes]`` for every ancestor of ``HEAD``.

    One ``git rev-list`` (≈1150 commits, single-digit ms) instead of one
    ``git merge-base --is-ancestor`` subprocess per cited hash — the registry
    cites 200+, and a gate that every contributor runs cannot cost seconds.
    """
    out = subprocess.run(
        ["git", "rev-list", "HEAD"], capture_output=True, text=True, cwd=REPO, check=True
    ).stdout
    index: dict[str, list[str]] = {}
    for full in out.split():
        index.setdefault(full[:_MIN_ABBREV], []).append(full)
    return index


def check_cited_shas(text: str, index: dict[str, list[str]], label: str) -> list[str]:
    """Errors for every hash in *text* that is not an ancestor in *index*.

    Hashes with no ``[a-f]`` digit are skipped: a backticked decimal literal
    (``999999999999``, a bounds-test value the backlog quotes) is not a SHA.
    Hashes followed by :data:`_OFF_MAIN_MARKER` are skipped by declaration.
    Each distinct offender is reported once.
    """
    errors: list[str] = []
    seen: set[str] = set()
    for match in _CITED_SHA.finditer(text):
        sha = match.group("sha")
        if match.group("exempt") or sha in seen or not re.search(r"[a-f]", sha):
            continue
        if not any(full.startswith(sha) for full in index.get(sha[:_MIN_ABBREV], ())):
            seen.add(sha)
            errors.append(
                f"cited commit `{sha}` in {label} is not an ancestor of HEAD (Rule 22: a "
                "closure SHA that cannot be resolved is a closure that cannot be verified). "
                "Find the commit that actually carries the change "
                f"(`git log --all --grep=...`, `git diff <sha> <candidate>`) and cite that; "
                f"or, if the hash is deliberately off-`main` (a cherry-pick source, an audit "
                f'quoting a dead hash), mark it in the prose: "`{sha}`{_OFF_MAIN_MARKER}".'
            )
    return errors


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=REPO, check=True
    ).stdout
    return out.splitlines()


def main() -> int:
    files = tracked_files()
    errors: list[str] = []

    # 1. docs/ top level is closed.
    for f in files:
        parts = f.split("/")
        if parts[0] == "docs" and len(parts) == 2 and parts[1] not in DOCS_TOP_ALLOWED:
            errors.append(f"docs/ top level is a closed set (OPERATING_MODEL §1): {f}")
        if parts[0] == "docs" and len(parts) > 2 and parts[1] not in DOCS_TOP_ALLOWED:
            errors.append(f"unknown docs/ folder (OPERATING_MODEL §1): docs/{parts[1]}/")

    # 2. Repo root is closed (tracked files only; dirs are governed elsewhere).
    for f in files:
        if "/" not in f and f not in ROOT_ALLOWED:
            errors.append(f"repo root is a closed set (OPERATING_MODEL §1): {f}")

    # 3. tracking/ holds exactly two files.
    tracking = {f.split("/")[-1] for f in files if f.startswith("docs/tracking/")}
    if tracking != TRACKING_ALLOWED:
        errors.append(
            f"docs/tracking/ must hold exactly {sorted(TRACKING_ALLOWED)} (Rule 25); "
            f"found {sorted(tracking)}"
        )

    # 4. No PM markdown inside packages.
    for f in files:
        parts = f.split("/")
        if not f.endswith(".md"):
            continue
        # Carve-out: the bundled reference-data tree ships inside the package
        # (src/radiant/data/tables/), and Rule 26 requires each generated-artifact
        # family to keep its generator manifest (MANIFEST.md / README.md) *beside*
        # the data it describes. These are data manifests, not project-management
        # markdown. (OPERATING_MODEL §6 carve-out; data-in-wheel packaging fix.)
        if f.startswith("src/radiant/data/tables/"):
            continue
        if parts[0] == "src" and len(parts) > 1:
            errors.append(f"no markdown inside src/ packages (OPERATING_MODEL §6): {f}")
        if parts[0] == "dev_tools" and len(parts) == 3 and parts[2] not in TOOL_ROOT_MD_ALLOWED:
            errors.append(
                f"tool package roots keep only {sorted(TOOL_ROOT_MD_ALLOWED)} "
                f"(OPERATING_MODEL §6): {f}"
            )

    # 5. Prohibited names (skip archive/ — historical names are frozen).
    for f in files:
        if f.startswith("docs/archive/"):
            continue
        if " " in f:
            errors.append(f"no spaces in file names (OPERATING_MODEL §5.1): {f}")
        if PROHIBITED_NAME.search(f):
            errors.append(f"prohibited name pattern (OPERATING_MODEL §5.3): {f}")

    # 6. Registry IDs are unique (Rules 21/22/25 — never reuse a CU or Gap
    # number; closure MOVES an entry, never copies it). Guards the
    # concurrent-session minting collision of 2026-07-27: two sessions took
    # "next available" from the same base while one held its numbers on an
    # unpushed branch. Leading-ID extraction only — headings may legitimately
    # cite other CU/Gap numbers in their titles.
    # 7. Every commit SHA a registry cites is an ancestor of HEAD (Rule 22,
    # CU-279 — see the ancestry block above). A shallow clone cannot answer the
    # question; say so out loud rather than pass or fail on no evidence.
    shallow = is_shallow()
    index = {} if shallow else ancestor_index()
    for path, pattern in (
        (REPO / "docs" / "tracking" / "Cleanup_Backlog.md", r"^### (CU-\d+)[ —]"),
        (REPO / "docs" / "tracking" / "gaps.md", r"^## (Gap \d+)\b"),
    ):
        text = path.read_text(encoding="utf-8")
        ids = re.findall(pattern, text, re.MULTILINE)
        seen: set[str] = set()
        for rid in ids:
            if rid in seen:
                errors.append(
                    f"duplicate registry ID {rid} in {path.name} (Rules 21/22/25: "
                    "IDs are never reused; closure moves an entry, never copies it)"
                )
            seen.add(rid)
        if not shallow:
            errors.extend(check_cited_shas(text, index, path.name))

    if shallow:
        print(
            "check_org_rules: NOTE — shallow clone; the cited-commit ancestry check "
            "(Rule 22, CU-279) was skipped. Run `git fetch --unshallow` to enable it."
        )

    # CU-229: the RADIANT_File_Tree.md per-package counts are generated, not
    # maintained by hand — a hand-kept count of a growing tree drifts by
    # construction (11 of 13 headings were wrong when this gate landed). Checked
    # here so it rides the gate battery every contributor already runs.
    from check_file_tree_counts import check as _check_file_tree_counts

    errors.extend(_check_file_tree_counts())

    if errors:
        print(f"check_org_rules: {len(errors)} violation(s)\n")
        for e in errors:
            print(f"  - {e}")
        print("\nSee docs/OPERATING_MODEL.md for the placement and naming rules.")
        return 1
    print("check_org_rules: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
