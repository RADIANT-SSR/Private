"""Generate / verify the SHA-256 manifest for the staged MODTRAN run set (CU-174).

The real MODTRAN 6 deliveries under ``modtran/real_runs/`` are license-gated and
locally irreplaceable (no MODTRAN binary on this machine), so the directory is
gitignored — nothing in it is committed. That leaves the precious data protected
by nothing but an ignore rule, and a partial or corrupted re-staging would be
detectable only where a golden happens to pin a band mean.

This script commits the *checksums* (not the data): a manifest of ``<sha256>  <name>``
lines, one per staged data file, written to a **sibling** path
``modtran/real_runs_MANIFEST.sha256`` (outside the ignored directory, so the strong
dir+symlink ignore that CU-174 depends on stays intact).

Usage
-----
    python scripts/gen_modtran_manifest.py            # (re)generate the manifest
    python scripts/gen_modtran_manifest.py --check     # verify staged files vs manifest

``--check`` exits 0 when every manifested file is present and matches, and non-zero
(with a per-file report) on any missing file or checksum mismatch. It is a no-op
success when the staged directory is absent (a cold clone / CI), mirroring the
skipif guard on ``tests/integration/test_modtran_manifest.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

# Repo-root-relative locations (this file lives in ``scripts/``).
_REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_RUNS_DIR = _REPO_ROOT / "modtran" / "real_runs"
MANIFEST_PATH = _REPO_ROOT / "modtran" / "real_runs_MANIFEST.sha256"

# Only the irreplaceable data files are checksummed; documentation (``*.md``) may
# legitimately change and is excluded so an edited README never fails the gate.
_DATA_SUFFIXES = (".tp7", ".csv")


def _sha256(path: Path) -> str:
    """Streaming SHA-256 hex digest of ``path`` (binary; large-file safe)."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _staged_data_files() -> list[Path]:
    """Staged data files (``*.tp7``/``*.csv``), sorted by name for determinism."""
    return sorted(
        (p for p in REAL_RUNS_DIR.iterdir() if p.is_file() and p.suffix.lower() in _DATA_SUFFIXES),
        key=lambda p: p.name,
    )


def _parse_manifest(text: str) -> dict[str, str]:
    """Parse ``<sha256>  <name>`` lines into a ``{name: hash}`` map."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, name = line.partition("  ")
        if not name:
            raise ValueError(f"malformed manifest line: {line!r}")
        out[name] = digest
    return out


def generate() -> int:
    """Write the manifest from the current staged files. Returns process exit code."""
    if not REAL_RUNS_DIR.exists():
        print(f"error: staged run set not found at {REAL_RUNS_DIR} — nothing to hash.")
        return 1
    files = _staged_data_files()
    if not files:
        print(f"error: no *.tp7 / *.csv data files under {REAL_RUNS_DIR}.")
        return 1
    lines = [
        "# SHA-256 manifest for the staged MODTRAN 6 run set (CU-174).",
        "# Regenerate: python scripts/gen_modtran_manifest.py",
        "# Verify:     python scripts/gen_modtran_manifest.py --check",
        f"# {len(files)} data files (*.tp7, *.csv); the data itself is gitignored.",
    ]
    lines += [f"{_sha256(p)}  {p.name}" for p in files]
    MANIFEST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {MANIFEST_PATH.relative_to(_REPO_ROOT)} ({len(files)} files).")
    return 0


def check() -> int:
    """Verify staged files against the committed manifest. Returns exit code."""
    if not MANIFEST_PATH.exists():
        print(f"error: manifest not found at {MANIFEST_PATH} — run without --check first.")
        return 1
    if not REAL_RUNS_DIR.exists():
        print(f"skip: staged run set not present at {REAL_RUNS_DIR} (cold clone / CI).")
        return 0
    expected = _parse_manifest(MANIFEST_PATH.read_text(encoding="utf-8"))
    missing: list[str] = []
    mismatched: list[str] = []
    for name, want in sorted(expected.items()):
        path = REAL_RUNS_DIR / name
        if not path.is_file():
            missing.append(name)
        elif _sha256(path) != want:
            mismatched.append(name)
    extra = sorted(p.name for p in _staged_data_files() if p.name not in expected)
    for name in missing:
        print(f"  MISSING    {name}")
    for name in mismatched:
        print(f"  MISMATCH   {name}")
    for name in extra:
        print(f"  UNMANIFEST {name} (staged but not in manifest — regenerate?)")
    if missing or mismatched:
        print(
            f"FAIL: {len(missing)} missing, {len(mismatched)} mismatched "
            f"of {len(expected)} manifested files."
        )
        return 1
    note = f" ({len(extra)} extra unmanifested)" if extra else ""
    print(f"OK: {len(expected)} staged files match the manifest{note}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify staged files against the manifest instead of regenerating it",
    )
    args = parser.parse_args(argv)
    return check() if args.check else generate()


if __name__ == "__main__":
    sys.exit(main())
