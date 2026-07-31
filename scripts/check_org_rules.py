"""Mechanical enforcement of docs/OPERATING_MODEL.md placement and naming rules.

Checks (CLAUDE.md Rules 23/25 + OPERATING_MODEL §1/§5.3/§6):
  1. docs/ top level is a closed set: index.md, OPERATING_MODEL.md + the nine folders.
  2. Repo root markdown/config files are a closed set.
  3. docs/tracking/ holds exactly Cleanup_Backlog.md, gaps.md and Findings_Log.md.
  4. No project-management markdown inside Python packages (src/, dev_tools/<tool>/):
     tool roots may keep only README/ARCHITECTURE/CONTRIBUTING.
  5. Prohibited names (§5.3) anywhere in tracked files: misc*, temp*, scratch*,
     untitled*, stuff*, output<N>.<img>, spaces in filenames.
  6. Registry IDs are unique (Rules 21/22/25).
  7. Every commit SHA the registries cite is an ancestor of HEAD (Rule 22, CU-279).
  8. Every Resolved backlog heading carries the canonical closure record (Rule 22, CU-282).
  9. Every gap marked closed cites a commit SHA (Rule 22, CU-281).
 10. Every trailer-closed backlog heading has a `CU-Closes: NNN` commit in HEAD's
     ancestry (Rule 22, two-tier tracking ratification 2026-07-31).

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

TRACKING_ALLOWED = {"Cleanup_Backlog.md", "gaps.md", "Findings_Log.md"}

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


# --- Resolved-entry format (Rule 22, CU-282) ---------------------------------
#
# Check 7 validates the SHAs that are *present*. It cannot see a closure whose SHA
# is absent or phrased unusually, which is how the registry accumulated a dozen
# heading dialects: the record sat in the heading for older entries and in the
# `**Status**:` line for newer ones. The canonical shape is documented in the
# registry header; this is its enforcement.

#: Disposition vocabulary. Nuance ("closed as not a defect") belongs in the Status
#: line — the heading is the machine-readable index, so it carries one word.
#: ACCEPTED / FOLDED / DEMOTED added by the 2026-07-31 two-tier ratification:
#: ACCEPTED = owner ratifies living with the behavior (clause carries the
#: limitation one-liner); FOLDED = becomes a checklist item on a family head;
#: DEMOTED = re-tested below CU grade, one-liner moved to Findings_Log.md.
_DISPOSITIONS = ("RESOLVED", "CLOSED", "DECLINED", "SUPERSEDED", "ACCEPTED", "FOLDED", "DEMOTED")

#: A closure written on a branch has no honest hash to write: OPERATING_MODEL §2
#: stamps the SHA *after* the merge lands, because writing one and then
#: `--amend`ing rewrites the hash and staleness is immediate. An in-flight
#: closure therefore parks a placeholder in the heading, the merging agent
#: replaces it with the real SHA, and this check refuses the placeholder — so a
#: branch that forgets the stamp cannot merge, rather than merging with a
#: transitional token that silently becomes permanent. That escape hatch existed
#: briefly during CU-282's own closure and was removed in the same merge.
_RESOLVED_HEADING = re.compile(
    rf"^### CU-\d+ — .+ — (?:{'|'.join(_DISPOSITIONS)}) \d{{4}}-\d{{2}}-\d{{2}} "
    rf"\((?:commits? `[0-9a-f]{{{_MIN_ABBREV},40}}`(?:, `[0-9a-f]{{{_MIN_ABBREV},40}}`)*"
    rf"|commit trailer"
    rf"|no commit — [^)]+)\)\s*$"
)

#: A trailer-closed heading: closure evidence is a `CU-Closes: NNN` line in the
#: closing commit's message rather than a SHA embedded in the heading (Rule 22,
#: 2026-07-31). Check 10 verifies the trailer commit exists in HEAD's ancestry.
_TRAILER_HEADING = re.compile(r"^### (CU-\d+) — .+ \(commit trailer\)\s*$")

#: A `CU-Closes:` trailer line in a commit message body. Numbers are bare and
#: comma-separated (`CU-Closes: 296` / `CU-Closes: 295, 297`).
_TRAILER_LINE = re.compile(r"^CU-Closes:\s*(?P<nums>\d+(?:\s*,\s*\d+)*)\s*$", re.MULTILINE)


def trailer_closed_ids() -> frozenset[str]:
    """Every ``CU-NNN`` named by a ``CU-Closes:`` trailer in HEAD's ancestry.

    One ``git log`` over all reachable commit messages — same single-subprocess
    budget as :func:`ancestor_index`, and shallow clones get the same skip.
    """
    out = subprocess.run(
        ["git", "log", "--format=%B"], capture_output=True, text=True, cwd=REPO, check=True
    ).stdout
    ids: set[str] = set()
    for match in _TRAILER_LINE.finditer(out):
        ids.update(f"CU-{n.strip()}" for n in match.group("nums").split(","))
    return frozenset(ids)


def check_trailer_closures(text: str, trailers: frozenset[str]) -> list[str]:
    """Errors for every trailer-closed heading with no ``CU-Closes`` commit on HEAD."""
    errors: list[str] = []
    if "\n## Resolved\n" not in text:
        return errors
    for line in text.split("\n## Resolved\n", 1)[1].splitlines():
        match = _TRAILER_HEADING.match(line)
        if match and match.group(1) not in trailers:
            errors.append(
                f"{match.group(1)} is closed '(commit trailer)' but no commit in HEAD's "
                f"ancestry carries a 'CU-Closes: {match.group(1).removeprefix('CU-')}' "
                "message trailer (Rule 22). Close the CU in the same commit as the fix, "
                "with the trailer in that commit's message; or cite an explicit "
                "(commit `sha`) if the closing commit already exists."
            )
    return errors


#: Frozen grandfather set: entries closed before the registry carried commit links
#: at all (CU-001/002/010/014, 2026-04-24), one whose closure cites a SHA *range*
#: that cannot be rewritten as a list without changing what it claims (CU-176),
#: one owner decline with no commit (CU-103), and one closed "across four
#: approaches" whose four SHAs are per-approach rather than one closure link
#: (CU-166). Every one of these is a real Rule-22 hole, recorded rather than
#: papered over. **This list must never grow** — a new closure has a SHA or it is
#: not a closure.
_UNLINKED_RESOLVED = frozenset(
    {"CU-001", "CU-002", "CU-010", "CU-014", "CU-103", "CU-166", "CU-176"}
)


def check_resolved_headings(text: str) -> list[str]:
    """Errors for every Resolved-section heading that is not in canonical form."""
    if "\n## Resolved\n" not in text:
        return ["Cleanup_Backlog.md has no '## Resolved' section (Rule 22)"]
    resolved = text.split("\n## Resolved\n", 1)[1]
    errors: list[str] = []
    for line in resolved.splitlines():
        if not line.startswith("### CU-"):
            continue
        cu = line.split(" ", 1)[1].split(" ")[0].rstrip("—").strip()
        if cu in _UNLINKED_RESOLVED:
            continue
        if not _RESOLVED_HEADING.match(line):
            errors.append(
                f"Resolved entry {cu} heading is not in canonical form (Rule 22, CU-282). "
                "Expected '### CU-NNN — <title> — <DISPOSITION> <YYYY-MM-DD> "
                "(commit `sha`)', disposition one of "
                f"{', '.join(_DISPOSITIONS)}; use 'no commit — <reason>' when there "
                "genuinely is none. See the format block in the registry header. "
                f"Got: {line[:120]}"
            )
    return errors


# --- Gap closures cite a commit (Rule 22, CU-281) -----------------------------
#
# OPERATING_MODEL §2 says gap closures are "marked closed in place w/ commit SHA".
# Nothing checked that a gap marked closed *had* a SHA at all — check 7 only
# validates ancestry of SHAs already present, so a SHA-less closure was invisible
# to it. Same failure shape as CU-279, one level up: presence, not resolvability.

#: Status words that mean the gap is closed and therefore owes a commit link.
#: DEFERRED / OPEN / WORKAROUND are not closures. NARROWED / PARTIALLY RESOLVED
#: describe a gap still partly open, so they are not closures either.
_GAP_CLOSED = re.compile(
    r"^\|\s*\*{0,2}Status\*{0,2}\s*\|\s*\*{0,2}(FIXED|CLOSED|RESOLVED|DELIVERED)\b",
    re.IGNORECASE | re.MULTILINE,
)

#: Frozen grandfather set: the closed gaps that cite no commit at all as of
#: 2026-07-30 — **64 of the 84 closed entries**, i.e. three quarters of the gap
#: registry's closures cannot be verified against history. Recorded by name
#: rather than silently tolerated. Note that this is not purely a legacy
#: problem: Gaps 107–111 were closed 2026-07-26/27, so the convention was still
#: not being followed the week this check landed. SHA archaeology for the set is
#: tracked separately. **This list must never grow** — a new closure has a SHA
#: or it is not a closure.
_UNLINKED_GAPS = frozenset(
    f"Gap {n}"
    for n in (
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        19,
        20,
        22,
        23,
        24,
        25,
        26,
        27,
        28,
        29,
        30,
        31,
        32,
        33,
        34,
        35,
        36,
        37,
        39,
        41,
        42,
        43,
        44,
        45,
        46,
        47,
        48,
        49,
        50,
        51,
        52,
        53,
        54,
        57,
        65,
        66,
        80,
        87,
        89,
        90,
        91,
        107,
        108,
        109,
        110,
        111,
    )
)


def check_gap_closures(text: str) -> list[str]:
    """Errors for every closed gap entry that cites no commit SHA."""
    errors: list[str] = []
    blocks = re.split(r"^## (Gap \d+)\b", text, flags=re.MULTILINE)
    for gid, body in zip(blocks[1::2], blocks[2::2], strict=True):
        if gid in _UNLINKED_GAPS or not _GAP_CLOSED.search(body):
            continue
        # A backticked hash anywhere in the entry counts as the link. Decimal
        # literals are excluded the same way check 7 excludes them.
        if not any(re.search(r"[a-f]", s) for s in re.findall(r"`([0-9a-f]{7,40})`", body)):
            errors.append(
                f"{gid} is marked closed but cites no commit SHA (Rule 22, "
                "OPERATING_MODEL §2: a gap closure is marked closed in place with the "
                "commit SHA). Add the commit that closed it, in backticks."
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
        # 8/9. Closure records are present and in one shape. Unlike check 7 these
        # need no history, so they run in a shallow clone too.
        # 10. Trailer-closed entries resolve to a CU-Closes commit. Needs
        # history, so it shares check 7's shallow-clone skip.
        if path.name == "Cleanup_Backlog.md":
            errors.extend(check_resolved_headings(text))
            if not shallow:
                errors.extend(check_trailer_closures(text, trailer_closed_ids()))
        else:
            errors.extend(check_gap_closures(text))

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
