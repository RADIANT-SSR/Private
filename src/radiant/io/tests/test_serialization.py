"""Tests for radiant.io.serialization — ChainResult archive codec (Gap 67).

Codec-level round trips use hand-built values (Level 0); the full-chain
round trip lives in tests/integration/test_persistence_roundtrip.py.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.radiometry import NoiseTerm, RadiometricFrame
from radiant.core.regime import RadiometricRegime
from radiant.io.serialization import (
    FORMAT_VERSION,
    ResultArchiveError,
    UnserializedValue,
    load_result_archive,
    save_result_archive,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WL = np.linspace(3.0, 5.0, 8)


def _state(**stage_outputs_inner: object) -> ChainState:
    """Minimal valid ChainState with the given source stage outputs."""
    return ChainState(
        wavelength_um=_WL,
        frames={
            "at_aperture": RadiometricFrame(
                name="at_aperture",
                wavelength_um=_WL,
                spectral_radiance=np.ones_like(_WL),
            ),
            "photoelectrons": RadiometricFrame(
                name="photoelectrons",
                wavelength_um=_WL,
                in_band_value=1234.5,
                in_band_unit="e-",
            ),
        },
        stage_outputs={"source": dict(stage_outputs_inner)},
        noise_terms=(
            NoiseTerm(
                name="signal_shot",
                value_e=35.1,
                origin_frame="photoelectrons",
                physical_basis="Poisson",
            ),
        ),
        mtf_terms={"optics": np.linspace(1.0, 0.0, 16)},
        spatial_freq_cycles_per_mrad=np.linspace(0.0, 10.0, 16),
        metrics={"snr": 35.2, "nedt_K": 0.021},
        history=("source", "optics"),
        run_id="test-run-0001",
    )


def _roundtrip(state: ChainState, tmp_path: Path) -> ChainState:
    p = save_result_archive(tmp_path / "r.radiant", state, {"run_id": state.run_id})
    loaded, _prov = load_result_archive(p)
    return loaded


# ---------------------------------------------------------------------------
# Round trips
# ---------------------------------------------------------------------------


@pytest.mark.level0
class TestRoundTrip:
    def test_primitives(self, tmp_path: Path) -> None:
        st = _state(
            a_none=None,
            a_bool=True,
            an_int=42,
            a_float=3.25,
            a_str="hello",
        )
        out = _roundtrip(st, tmp_path).stage_outputs["source"]
        assert out["a_none"] is None
        assert out["a_bool"] is True
        assert out["an_int"] == 42
        assert out["a_float"] == 3.25
        assert out["a_str"] == "hello"

    def test_nonfinite_floats(self, tmp_path: Path) -> None:
        st = _state(nan=float("nan"), pinf=float("inf"), ninf=float("-inf"))
        out = _roundtrip(st, tmp_path).stage_outputs["source"]
        assert np.isnan(out["nan"])
        assert out["pinf"] == float("inf")
        assert out["ninf"] == float("-inf")

    def test_ndarray_dtypes_preserved(self, tmp_path: Path) -> None:
        st = _state(
            f64=np.array([1.0, 2.0]),
            i32=np.array([1, 2], dtype=np.int32),
            b=np.array([True, False]),
            c128=np.array([1 + 2j]),
            two_d=np.eye(3),
        )
        out = _roundtrip(st, tmp_path).stage_outputs["source"]
        assert out["f64"].dtype == np.float64
        assert out["i32"].dtype == np.int32
        assert out["b"].dtype == np.bool_
        assert out["c128"].dtype == np.complex128
        np.testing.assert_array_equal(out["two_d"], np.eye(3))

    def test_tuple_vs_list_distinction(self, tmp_path: Path) -> None:
        st = _state(a_tuple=(1, 2, "x"), a_list=[1, 2, "x"])
        out = _roundtrip(st, tmp_path).stage_outputs["source"]
        assert out["a_tuple"] == (1, 2, "x")
        assert isinstance(out["a_tuple"], tuple)
        assert out["a_list"] == [1, 2, "x"]
        assert isinstance(out["a_list"], list)

    def test_nested_map(self, tmp_path: Path) -> None:
        st = _state(nested={"inner": {"deep": [1.5, (2, 3)]}})
        out = _roundtrip(st, tmp_path).stage_outputs["source"]
        assert out["nested"] == {"inner": {"deep": [1.5, (2, 3)]}}

    def test_radiant_enum(self, tmp_path: Path) -> None:
        st = _state(regime=RadiometricRegime.POINT_SOURCE)
        out = _roundtrip(st, tmp_path).stage_outputs["source"]
        assert out["regime"] is RadiometricRegime.POINT_SOURCE

    def test_radiant_dataclass_revalidates(self, tmp_path: Path) -> None:
        term = NoiseTerm(
            name="dark_shot",
            value_e=8.5,
            origin_frame="photoelectrons",
            physical_basis="Poisson",
            contributes_to=("total", "detector"),
        )
        st = _state(term=term)
        out = _roundtrip(st, tmp_path).stage_outputs["source"]
        assert out["term"] == term
        assert isinstance(out["term"], NoiseTerm)

    def test_frames_noise_mtf_metrics_history(self, tmp_path: Path) -> None:
        st = _state()
        loaded = _roundtrip(st, tmp_path)
        assert loaded.frames["photoelectrons"].in_band_value == 1234.5
        np.testing.assert_array_equal(
            loaded.frames["at_aperture"].spectral_radiance,
            st.frames["at_aperture"].spectral_radiance,
        )
        assert loaded.noise_terms == st.noise_terms
        np.testing.assert_array_equal(loaded.mtf_terms["optics"], st.mtf_terms["optics"])
        assert dict(loaded.metrics) == {"snr": 35.2, "nedt_K": 0.021}
        assert loaded.history == ("source", "optics")
        assert loaded.run_id == "test-run-0001"

    def test_loaded_state_is_frozen(self, tmp_path: Path) -> None:
        loaded = _roundtrip(_state(), tmp_path)
        with pytest.raises(TypeError):
            loaded.metrics["snr"] = 0.0  # type: ignore[index]

    def test_provenance_preserved_verbatim(self, tmp_path: Path) -> None:
        prov = {"run_id": "x", "git_commit": "abc1234", "parameter_set": {"a": 1}}
        p = save_result_archive(tmp_path / "r.radiant", _state(), prov)
        _loaded, prov_back = load_result_archive(p)
        assert prov_back == prov


# ---------------------------------------------------------------------------
# Skip handling
# ---------------------------------------------------------------------------


class _NotSerializable:
    pass


@pytest.mark.level0
class TestSkips:
    def test_foreign_object_warns_and_placeholders(self, tmp_path: Path) -> None:
        st = _state(alien=_NotSerializable())
        with pytest.warns(UserWarning, match="could not be serialized"):
            p = save_result_archive(tmp_path / "r.radiant", st, {})
        loaded, _ = load_result_archive(p)
        val = loaded.stage_outputs["source"]["alien"]
        assert isinstance(val, UnserializedValue)
        assert "_NotSerializable" in val.type_name

    def test_skips_recorded_in_manifest(self, tmp_path: Path) -> None:
        st = _state(alien=_NotSerializable())
        with pytest.warns(UserWarning):
            p = save_result_archive(tmp_path / "r.radiant", st, {})
        with zipfile.ZipFile(p) as zf:
            manifest = json.loads(zf.read("manifest.json"))
        assert manifest["unserialized"] == [
            {
                "path": "stage_outputs.source.alien",
                "type": f"{_NotSerializable.__module__}:{_NotSerializable.__qualname__}",
            }
        ]

    def test_object_dtype_array_skipped(self, tmp_path: Path) -> None:
        st = _state(obj_arr=np.array([object()], dtype=object))
        with pytest.warns(UserWarning, match="could not be serialized"):
            p = save_result_archive(tmp_path / "r.radiant", st, {})
        loaded, _ = load_result_archive(p)
        assert isinstance(loaded.stage_outputs["source"]["obj_arr"], UnserializedValue)


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


@pytest.mark.level0
class TestFailureModes:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ResultArchiveError, match="not found"):
            load_result_archive(tmp_path / "nope.radiant")

    def test_not_a_zip(self, tmp_path: Path) -> None:
        p = tmp_path / "junk.radiant"
        p.write_text("not a zip")
        with pytest.raises(ResultArchiveError, match="not a RADIANT result archive"):
            load_result_archive(p)

    def test_wrong_kind(self, tmp_path: Path) -> None:
        p = tmp_path / "other.radiant"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("manifest.json", json.dumps({"kind": "something-else"}))
            zf.writestr("arrays.npz", b"")
        with pytest.raises(ResultArchiveError, match="kind"):
            load_result_archive(p)

    def test_future_format_version(self, tmp_path: Path) -> None:
        p = save_result_archive(tmp_path / "r.radiant", _state(), {})
        with zipfile.ZipFile(p) as zf:
            manifest = json.loads(zf.read("manifest.json"))
            arrays = zf.read("arrays.npz")
        manifest["format_version"] = FORMAT_VERSION + 1
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("arrays.npz", arrays)
        with pytest.raises(ResultArchiveError, match="format version"):
            load_result_archive(p)

    def test_non_radiant_class_rejected(self, tmp_path: Path) -> None:
        """An archive naming a class outside radiant.* must not import it."""
        p = save_result_archive(tmp_path / "r.radiant", _state(), {})
        with zipfile.ZipFile(p) as zf:
            manifest = json.loads(zf.read("manifest.json"))
            arrays = zf.read("arrays.npz")
        manifest["state"]["run_id"] = {
            "__t": "dc",
            "cls": "subprocess:Popen",
            "f": {"args": "echo pwned"},
        }
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("arrays.npz", arrays)
        with pytest.raises(ResultArchiveError, match="outside the radiant package"):
            load_result_archive(p)

    def test_radiantoid_module_prefix_rejected(self, tmp_path: Path) -> None:
        """'radiantevil' must not pass the radiant.* module check."""
        p = save_result_archive(tmp_path / "r.radiant", _state(), {})
        with zipfile.ZipFile(p) as zf:
            manifest = json.loads(zf.read("manifest.json"))
            arrays = zf.read("arrays.npz")
        manifest["state"]["run_id"] = {"__t": "enum", "cls": "radiantevil:X", "v": 1}
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("arrays.npz", arrays)
        with pytest.raises(ResultArchiveError, match="outside the radiant package"):
            load_result_archive(p)

    def test_unknown_class_in_archive(self, tmp_path: Path) -> None:
        p = save_result_archive(tmp_path / "r.radiant", _state(), {})
        with zipfile.ZipFile(p) as zf:
            manifest = json.loads(zf.read("manifest.json"))
            arrays = zf.read("arrays.npz")
        manifest["state"]["run_id"] = {
            "__t": "dc",
            "cls": "radiant.core.radiometry:DoesNotExist",
            "f": {},
        }
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("arrays.npz", arrays)
        with pytest.raises(ResultArchiveError, match="does not exist"):
            load_result_archive(p)

    def test_unknown_tag(self, tmp_path: Path) -> None:
        p = save_result_archive(tmp_path / "r.radiant", _state(), {})
        with zipfile.ZipFile(p) as zf:
            manifest = json.loads(zf.read("manifest.json"))
            arrays = zf.read("arrays.npz")
        manifest["state"]["run_id"] = {"__t": "hologram", "v": 1}
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("arrays.npz", arrays)
        with pytest.raises(ResultArchiveError, match="unknown node tag"):
            load_result_archive(p)
