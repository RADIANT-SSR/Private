"""CLI output-stream encoding (CU-385, Rule 30).

The Windows failure is reproducible on any platform by handing Python a
cp1252 stdout through ``PYTHONIOENCODING``: that is precisely what a default
Windows console gives it. These tests fail on the pre-CU-385 code (measured:
``radiant schema --stage detector`` exits 1 with ``UnicodeEncodeError`` under
cp1252), so they are not vacuous.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys

import pytest

from radiant.cli._encoding import force_utf8_streams


def _run_cli_under(encoding: str, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Invoke the CLI in a subprocess whose stdio encoding is *encoding*."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = encoding
    repo_src = os.pathsep.join([str(_SRC), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    env["PYTHONPATH"] = repo_src
    return subprocess.run(
        [sys.executable, "-m", "radiant.cli.main", *args],
        capture_output=True,
        env=env,
        check=False,
    )


_SRC = __import__("pathlib").Path(__file__).resolve().parents[3]


class TestNonAsciiUnderLegacyConsole:
    """A cp1252 console must not break commands that print unit symbols."""

    @pytest.mark.parametrize("stage", ["detector", "platform", "spectral_integration"])
    def test_schema_survives_cp1252(self, stage: str) -> None:
        # Each of these stages has a schema description carrying non-ASCII
        # (detector: alpha/Omega/subscript-zero; platform and
        # spectral_integration: micro sign).
        result = _run_cli_under("cp1252", "schema", "--stage", stage)
        assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
        assert b"UnicodeEncodeError" not in result.stderr

    def test_version_survives_cp1252(self) -> None:
        # --version is an eager callback: it echoes during parsing, before the
        # group body runs, so it needs its own reconfiguration call.
        result = _run_cli_under("cp1252", "--version")
        assert result.returncode == 0, result.stderr.decode("utf-8", "replace")

    def test_schema_output_round_trips_as_utf8(self) -> None:
        result = _run_cli_under("cp1252", "schema", "--stage", "spectral_integration")
        assert result.returncode == 0
        # The micro sign survives as UTF-8 rather than being folded away.
        assert "µ".encode() in result.stdout


class TestForceUtf8Streams:
    """The helper itself: idempotent, and a no-op on streams it cannot touch."""

    def test_idempotent(self) -> None:
        force_utf8_streams()
        force_utf8_streams()
        # Nothing to assert beyond "did not raise": pytest has already
        # replaced sys.stdout with a capture object here, which is one of the
        # legitimately non-reconfigurable cases.

    def test_no_op_on_stringio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # io.StringIO has no reconfigure() at all.
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        monkeypatch.setattr(sys, "stderr", io.StringIO())
        force_utf8_streams()

    def test_no_op_on_detached_stream(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A stream whose reconfigure() raises must be left alone, not crash.
        class Hostile(io.StringIO):
            def reconfigure(self, **_kwargs: object) -> None:
                raise ValueError("detached")

        monkeypatch.setattr(sys, "stdout", Hostile())
        force_utf8_streams()

    def test_tolerates_none_streams(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Under pythonw.exe on Windows sys.stdout can be None.
        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "stderr", None)
        force_utf8_streams()
