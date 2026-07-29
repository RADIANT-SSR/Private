"""Provenance contract tests (CU-NEW-04 / RADIANT_Master_Architecture.md §C13).

Pins five surfaces:

1. :mod:`radiant.core.provenance` helpers behave per spec — pure
   functions, no exceptions on edge cases except :func:`hash_file` on
   missing files.
2. :class:`ChainState` carries ``run_id`` and :class:`ChainRunner`
   mints a fresh UUID4 when the caller doesn't supply one.
3. :class:`ParameterSet.record_loaded_file` and the ``loaded_files``
   property record + dedupe loaded config files.
4. :func:`radiant.io.config.load_config` records the SHA-256 of every
   YAML it consumes onto the ``ParameterSet``.
5. :meth:`ChainResult.to_provenance_record` returns a complete
   JSON-serialisable record matching every field in §C13.

Lives in [tests/](../tests/) (not under any package boundary) because
the integration test imports from :mod:`radiant.api`,
:mod:`radiant.io`, and :mod:`radiant.core` simultaneously.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pytest

from radiant.core.chain import ChainRunner, ChainState
from radiant.core.parameters import (
    ParameterDef,
    ParameterSet,
    Provenance,
)
from radiant.core.provenance import (
    _RUNTIME_DEPENDENCIES,
    dependency_versions,
    git_commit,
    hash_file,
    new_run_id,
    python_version_string,
)

# ---------------------------------------------------------------------------
# core/provenance.py helper unit tests
# ---------------------------------------------------------------------------


@pytest.mark.level0
class TestNewRunId:
    """`new_run_id` mints a unique UUID4 string per call."""

    def test_returns_uuid4_string_shape(self) -> None:
        rid = new_run_id()
        # UUID4 canonical form: 8-4-4-4-12 hex with version nibble = 4.
        assert re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            rid,
        ), f"not a UUID4: {rid}"

    def test_distinct_across_calls(self) -> None:
        ids = {new_run_id() for _ in range(100)}
        assert len(ids) == 100, "UUID4 collision in 100 draws — generator is broken"


@pytest.mark.level0
class TestGitCommit:
    """`git_commit` returns a short SHA inside a repo, ``"unknown"`` otherwise."""

    def test_returns_short_sha_in_repo(self) -> None:
        sha = git_commit()
        # In CI / dev this repo always has a HEAD. "unknown" only on a
        # missing git binary or non-repo working tree, neither of which
        # apply here.
        assert sha != "unknown"
        assert re.fullmatch(r"[0-9a-f]{7,12}", sha), f"not a short SHA: {sha}"

    def test_returns_unknown_outside_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Outside any git repo, the helper degrades gracefully."""
        monkeypatch.chdir(tmp_path)
        # `git rev-parse` exits non-zero outside a repo; helper returns
        # the sentinel string rather than raising.
        sha = git_commit()
        assert sha == "unknown"

    def test_returns_unknown_when_git_binary_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If the ``git`` binary is unavailable, helper returns ``"unknown"``."""

        def _raise(*_a: object, **_kw: object) -> None:
            raise FileNotFoundError("git not installed")

        monkeypatch.setattr(subprocess, "run", _raise)
        assert git_commit() == "unknown"


@pytest.mark.level0
class TestPythonVersionString:
    def test_format_is_major_minor_patch(self) -> None:
        v = python_version_string()
        assert re.fullmatch(r"\d+\.\d+\.\d+", v), f"bad format: {v}"


@pytest.mark.level0
class TestDependencyVersions:
    def test_returns_all_declared_deps(self) -> None:
        versions = dependency_versions()
        # Every declared runtime dep must appear in the record (even
        # if only as "unknown") — so the provenance record never has
        # missing keys.
        assert set(versions.keys()) == set(_RUNTIME_DEPENDENCIES)

    def test_known_deps_have_real_versions(self) -> None:
        """numpy/scipy are installed in the dev env; should resolve to PEP 440 strings."""
        versions = dependency_versions()
        for name in ("numpy", "scipy"):
            v = versions[name]
            assert v != "unknown", f"{name} version missing"
            assert re.match(r"\d+\.\d+", v), f"{name} version not PEP 440-ish: {v}"


@pytest.mark.level0
class TestHashFile:
    def test_known_content_known_digest(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.txt"
        f.write_bytes(b"hello world\n")
        # SHA-256("hello world\n") — verified independently via
        # `python -c 'import hashlib; print(hashlib.sha256(b"hello world\n").hexdigest())'`.
        assert hash_file(f) == ("a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447")

    def test_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "blob.bin"
        f.write_bytes(b"\x00\x01\x02" * 10_000)
        assert hash_file(f) == hash_file(f)

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.write_bytes(b"alpha")
        b.write_bytes(b"beta")
        assert hash_file(a) != hash_file(b)

    def test_handles_large_file_in_chunks(self, tmp_path: Path) -> None:
        """Files larger than the 64 KiB chunk size hash correctly."""
        f = tmp_path / "big.bin"
        # 200 KiB — exercises the chunked-read loop more than once.
        f.write_bytes(b"x" * 200_000)
        digest = hash_file(f)
        assert re.fullmatch(r"[0-9a-f]{64}", digest)

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            hash_file(tmp_path / "does-not-exist.txt")


# ---------------------------------------------------------------------------
# ChainState.run_id + ChainRunner UUID-mint behaviour
# ---------------------------------------------------------------------------


@pytest.mark.level0
class TestChainStateRunId:
    def test_default_run_id_is_none(self) -> None:
        s = ChainState(wavelength_um=np.array([3.0, 5.0]))
        assert s.run_id is None

    def test_caller_supplied_run_id_round_trips(self) -> None:
        s = ChainState(wavelength_um=np.array([3.0, 5.0]), run_id="rid-explicit")
        assert s.run_id == "rid-explicit"


@pytest.mark.level0
class TestChainRunnerMintsRunId:
    """`ChainRunner.run` mints a UUID4 when the caller doesn't supply one."""

    def test_mints_run_id_when_none_passed(self) -> None:
        runner = ChainRunner([])  # empty stage list is legal — just minimum chain
        params = ParameterSet(schema=[])
        params.resolve()
        state = runner.run(params, np.array([3.0, 5.0]))
        assert state.run_id is not None
        # Shape should match `new_run_id()` output.
        assert re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            state.run_id,
        )

    def test_caller_supplied_run_id_passed_through(self) -> None:
        runner = ChainRunner([])
        params = ParameterSet(schema=[])
        params.resolve()
        state = runner.run(params, np.array([3.0, 5.0]), run_id="explicit-rid")
        assert state.run_id == "explicit-rid"

    def test_distinct_run_ids_across_runs(self) -> None:
        runner = ChainRunner([])
        params = ParameterSet(schema=[])
        params.resolve()
        a = runner.run(params, np.array([3.0, 5.0]))
        b = runner.run(params, np.array([3.0, 5.0]))
        assert a.run_id != b.run_id


# ---------------------------------------------------------------------------
# ParameterSet.record_loaded_file / loaded_files
# ---------------------------------------------------------------------------


@pytest.mark.level0
class TestParameterSetLoadedFiles:
    def _empty_params(self) -> ParameterSet:
        return ParameterSet(schema=[])

    def test_default_empty(self) -> None:
        assert self._empty_params().loaded_files == ()

    def test_record_appends(self) -> None:
        p = self._empty_params()
        p.record_loaded_file("a.yaml", "hash_a")
        p.record_loaded_file("b.yaml", "hash_b")
        assert p.loaded_files == (("a.yaml", "hash_a"), ("b.yaml", "hash_b"))

    def test_dedupes_identical_entries(self) -> None:
        p = self._empty_params()
        p.record_loaded_file("a.yaml", "hash_a")
        p.record_loaded_file("a.yaml", "hash_a")
        assert p.loaded_files == (("a.yaml", "hash_a"),)

    def test_same_path_new_hash_appends(self) -> None:
        """A reloaded-after-edit config should appear as a fresh record."""
        p = self._empty_params()
        p.record_loaded_file("a.yaml", "hash_old")
        p.record_loaded_file("a.yaml", "hash_new")
        assert p.loaded_files == (
            ("a.yaml", "hash_old"),
            ("a.yaml", "hash_new"),
        )


@pytest.mark.level0
class TestLoadConfigRecordsFileHash:
    """`load_config` writes (path, sha256) onto the ParameterSet."""

    def test_yaml_load_records_hash(self, tmp_path: Path) -> None:
        from radiant.io.config import load_config

        schema = [
            ParameterDef(
                name="source.target.temperature",
                description="test temp",
                dtype=float,
                canonical_unit="K",
                input_unit="K",
                default=300.0,
            ),
        ]
        params = ParameterSet(schema=schema)

        cfg = tmp_path / "tiny.yaml"
        cfg.write_text("source:\n  target:\n    temperature: 250.0\n")

        load_config(cfg, params)

        assert len(params.loaded_files) == 1
        path_str, sha = params.loaded_files[0]
        assert path_str == str(cfg)
        assert sha == hash_file(cfg)

    def test_dict_source_records_nothing(self) -> None:
        """Loading from an in-memory dict doesn't get a file hash (no path)."""
        from radiant.io.config import load_config

        schema = [
            ParameterDef(
                name="source.target.temperature",
                description="test temp",
                dtype=float,
                canonical_unit="K",
                input_unit="K",
                default=300.0,
            ),
        ]
        params = ParameterSet(schema=schema)
        load_config({"source": {"target": {"temperature": 280.0}}}, params)
        assert params.loaded_files == ()


# ---------------------------------------------------------------------------
# ChainResult.to_provenance_record — full §C13 contract
# ---------------------------------------------------------------------------


C13_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "run_id",
        "radiant_version",
        "git_commit",
        "python_version",
        "dependency_versions",
        "parameter_set",
        "input_file_hashes",
        "active_models",
    }
)


@pytest.mark.level1
class TestChainResultProvenanceFromState:
    """Synthetic ChainState (no params) — keys present, parameter_set empty."""

    def test_keys_match_c13_contract(self) -> None:
        from radiant.io.results import ChainResult

        state = ChainState(wavelength_um=np.array([3.0, 5.0]), run_id="rid-X")
        record = ChainResult(state).to_provenance_record()
        assert set(record.keys()) == C13_REQUIRED_KEYS

    def test_empty_parameter_set_when_params_omitted(self) -> None:
        from radiant.io.results import ChainResult

        state = ChainState(wavelength_um=np.array([3.0, 5.0]), run_id="rid-X")
        record = ChainResult(state).to_provenance_record()
        assert record["parameter_set"] == {}
        assert record["input_file_hashes"] == []

    def test_record_is_json_serialisable(self) -> None:
        from radiant.io.results import ChainResult

        state = ChainState(wavelength_um=np.array([3.0, 5.0]), run_id="rid-X")
        record = ChainResult(state).to_provenance_record()
        json.dumps(record)  # must not raise


@pytest.mark.level2
class TestChainResultProvenanceEndToEnd:
    """Full chain run from YAML → ChainResult → provenance record."""

    @pytest.fixture()
    def result(self) -> object:
        from radiant.api.session import RadiantSession
        from radiant.io.config import load_config

        yaml_path = Path(__file__).parent.parent / "examples" / "mwir_leo_minimal.yaml"
        wl = np.linspace(3.5, 5.0, 200)
        session = RadiantSession(wavelength_um=wl)
        params = session.default_params()
        load_config(yaml_path, params)
        params.resolve()
        return session.run(params)

    def test_all_c13_fields_populated(self, result: object) -> None:
        record = result.to_provenance_record()
        assert set(record.keys()) == C13_REQUIRED_KEYS

    def test_run_id_is_uuid4(self, result: object) -> None:
        record = result.to_provenance_record()
        assert re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            record["run_id"],
        )

    def test_radiant_version_matches_package(self, result: object) -> None:
        from radiant import __version__

        assert result.to_provenance_record()["radiant_version"] == __version__

    def test_dependency_versions_complete(self, result: object) -> None:
        deps = result.to_provenance_record()["dependency_versions"]
        assert set(deps.keys()) == set(_RUNTIME_DEPENDENCIES)

    def test_input_file_hashes_recorded(self, result: object) -> None:
        hashes = result.to_provenance_record()["input_file_hashes"]
        assert len(hashes) == 1
        entry = hashes[0]
        assert set(entry.keys()) == {"path", "sha256"}
        assert entry["path"].endswith("mwir_leo_minimal.yaml")
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])

    def test_parameter_set_has_resolved_values(self, result: object) -> None:
        ps = result.to_provenance_record()["parameter_set"]
        # Non-trivial: full schema has 100+ params after default + load.
        assert len(ps) > 50
        # Every entry is the ResolvedValue.to_dict() shape — must have at
        # least 'value' and 'provenance' keys.
        sample = next(iter(ps.values()))
        assert "value" in sample
        assert "provenance" in sample

    def test_active_models_mirrors_history(self, result: object) -> None:
        record = result.to_provenance_record()
        assert tuple(record["active_models"]) == result.history
        assert len(record["active_models"]) == 9  # full chain (geometry-first, ADR-0006)

    def test_json_serialisable_end_to_end(self, result: object) -> None:
        record = result.to_provenance_record()
        json.dumps(record)  # no numpy arrays, no enums, no datetimes raw


@pytest.mark.level0
class TestProvenanceUnresolvedParams:
    """If `params` is attached but never resolved, parameter_set is empty (no crash)."""

    def test_unresolved_params_yield_empty_set(self) -> None:
        from radiant.io.results import ChainResult

        params = ParameterSet(
            schema=[
                ParameterDef(
                    name="source.target.temperature",
                    description="test temp",
                    dtype=float,
                    canonical_unit="K",
                    input_unit="K",
                    default=300.0,
                ),
            ]
        )
        # NOT resolved — `all_resolved()` raises RuntimeError.
        params.set("source.target.temperature", 270.0, Provenance.USER_SET, "test")

        state = ChainState(wavelength_um=np.array([3.0, 5.0]), run_id="rid-X")
        record = ChainResult(state, params=params).to_provenance_record()
        # Per the docstring contract: empty parameter_set, not a crash.
        assert record["parameter_set"] == {}
