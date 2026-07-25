"""Mechanical enforcement of docs/OPERATING_MODEL.md placement and naming rules.

Checks (CLAUDE.md Rules 23/25 + OPERATING_MODEL §1/§5.3/§6):
  1. docs/ top level is a closed set: index.md, OPERATING_MODEL.md + the nine folders.
  2. Repo root markdown/config files are a closed set.
  3. docs/tracking/ holds exactly Cleanup_Backlog.md and gaps.md.
  4. No project-management markdown inside Python packages (src/, dev_tools/<tool>/):
     tool roots may keep only README/ARCHITECTURE/CONTRIBUTING.
  5. Prohibited names (§5.3) anywhere in tracked files: misc*, temp*, scratch*,
     untitled*, stuff*, output<N>.<img>, spaces in filenames.

Exit 0 = compliant; exit 1 = violations printed. Runs in the CI `static` job.
Only git-tracked files are checked (untracked scratch is a working-tree concern).
"""

from __future__ import annotations

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
