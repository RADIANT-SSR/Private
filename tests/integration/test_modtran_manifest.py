"""Integration: the staged MODTRAN run set matches its committed checksum manifest (CU-174).

The real MODTRAN 6 deliveries under ``modtran/real_runs/`` are gitignored and
locally irreplaceable, so a partial or corrupted re-staging would otherwise be
detectable only where a golden happens to pin a band mean. ``scripts/gen_modtran_manifest.py``
commits their SHA-256 checksums (not the data) to ``modtran/real_runs_MANIFEST.sha256``;
this test verifies the staged files against that manifest.

Like ``test_modtran_real_runs.py`` it is ``skipif``-guarded on the presence of the
staged directory, so it is a no-op in CI / a cold clone. When the data IS staged,
it fails fast on any missing file or checksum mismatch.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_RUNS = _REPO_ROOT / "modtran" / "real_runs"
_MANIFEST = _REPO_ROOT / "modtran" / "real_runs_MANIFEST.sha256"

pytestmark = pytest.mark.skipif(
    not _REAL_RUNS.exists(),
    reason="real MODTRAN run set not staged (modtran/real_runs/ is gitignored "
    "until the fixture subset is committed — plan §7.1)",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_entries() -> dict[str, str]:
    """Parse the committed manifest into ``{filename: sha256}``."""
    entries: dict[str, str] = {}
    for line in _MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, name = line.partition("  ")
        entries[name] = digest
    return entries


def test_manifest_is_committed() -> None:
    """The manifest itself must be committed (it lives outside the ignored dir)."""
    assert _MANIFEST.is_file(), (
        f"{_MANIFEST} missing — regenerate with "
        "`python scripts/gen_modtran_manifest.py`"
    )
    assert _manifest_entries(), "manifest has no checksum entries"


# The manifest is committed (outside the ignored dir), so it is present in every
# checkout and safe to parametrize over at collection time. The module-level
# skipif above no-ops these when the *data* isn't staged.
@pytest.mark.parametrize("name", sorted(_manifest_entries()))
def test_staged_file_matches_manifest(name: str) -> None:
    """Each manifested data file is present and byte-identical to its checksum."""
    path = _REAL_RUNS / name
    assert path.is_file(), (
        f"{name} is in the manifest but missing from {_REAL_RUNS} — "
        "the staged delivery is incomplete."
    )
    expected = _manifest_entries()[name]
    assert _sha256(path) == expected, (
        f"{name} checksum mismatch: staged file differs from the committed "
        "manifest (corrupted or replaced re-staging)."
    )
