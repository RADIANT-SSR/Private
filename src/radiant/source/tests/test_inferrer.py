"""Tests for the Stage-2 back-compat descriptor inferrer.

Covers three layers of the Category B deliverable:

1. **Per-scenario inference** — every YAML listed in
   ``tests/integration/snapshots/option_c_baseline.yaml`` passes through
   ``infer_descriptors`` and the descriptors match the expected values
   keyed by the scenario's known intent (matrix §3.2).
2. **Snapshot regression** — serialise each scenario's descriptors to
   YAML under ``src/radiant/source/tests/snapshots/`` and assert
   round-trip equality (regenerated YAML equals on-disk YAML).  Future
   PRs that accidentally move a descriptor value will flip the snapshot
   and fail CI with a clear diff.
3. **Failure modes & round-trip** — matrix §7 must-raise combinations
   and the lossy round-trip subset.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from radiant.api._param_registry import build_parameter_set
from radiant.core.descriptors import (
    AtApertureBackground,
    GroundBackground,
    T2Reflective,
    T3Mixed,
    T5AtAperture,
    UserSpectralBackground,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.spectral import SpectralData
from radiant.io.config import load_config
from radiant.source._inferrer import (
    _infer_scene_type,
    _infer_target_location_and_subcase,
    descriptors_to_params,
    infer_descriptors,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
SNAPSHOT_YAML = REPO_ROOT / "tests" / "integration" / "snapshots" / "option_c_baseline.yaml"
SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_snapshot() -> dict[str, Any]:
    with open(SNAPSHOT_YAML, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _scenario_paths() -> list[tuple[str, Path]]:
    """Return ``(name, absolute_path)`` pairs for every snapshot scenario."""
    snap = _load_snapshot()
    out: list[tuple[str, Path]] = []
    for name in sorted(snap["scenarios"].keys()):
        abs_path = REPO_ROOT / name
        assert abs_path.exists(), f"Scenario YAML missing on disk: {abs_path}"
        out.append((name, abs_path))
    return out


def _wavelength_grid(yaml_path: Path) -> np.ndarray:
    """Build a representative wavelength grid for a scenario.

    Uses the scenario's own filter band rather than the fixed 11-point
    snapshot grid because the inferrer's grey-lift SpectralData needs a
    non-trivial (>= 2-point) grid.
    """
    with open(yaml_path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    si = cfg.get("spectral_integration", {})
    lo = float(si.get("filter_min_um", 0.5))
    hi = float(si.get("filter_max_um", 13.0))
    return np.linspace(lo, hi, 11)


def _load_params(yaml_path: Path) -> ParameterSet:
    """Build a full-schema ParameterSet loaded from a YAML."""
    params = build_parameter_set()
    load_config(yaml_path, params)
    params.resolve()
    return params


def _descriptor_to_yaml_dict(obj: Any) -> Any:
    """Serialise a descriptor (or None) to a YAML-safe dict.

    Walks the dataclass tree manually (rather than using
    ``dataclasses.asdict`` which eagerly recursion-copies everything
    into native types but loses the SpectralData ``to_dict`` path
    because it sees the inner numpy arrays first).
    """
    if obj is None:
        return None
    if isinstance(obj, SpectralData):
        return {"__spectraldata__": obj.to_dict()}
    if isinstance(obj, LineOfSightGeometry):
        return {"__los__": obj.to_dict()}
    # Descriptor dataclass — walk fields manually, tag type.
    if hasattr(obj, "__dataclass_fields__"):
        out: dict[str, Any] = {"__type__": type(obj).__name__}
        for fname in obj.__dataclass_fields__:
            out[fname] = _descriptor_to_yaml_dict(getattr(obj, fname))
        return out
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, dict):
        return {k: _descriptor_to_yaml_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_descriptor_to_yaml_dict(v) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# Scenario coverage table: every YAML in the Stage-0 snapshot must classify
# per matrix §3.2.  The expected outcome is keyed by scenario path.
# ---------------------------------------------------------------------------

# (scene_type, target_location, subcase, target_variant_name, bg_variant_name_or_None)
ScenarioExpectation = tuple[str, str, str, str, str | None]

_EXPECTED: dict[str, ScenarioExpectation] = {
    # LWIR thermal extended terrestrial (Cell 28 family) — simple atmosphere
    "examples/templates/lwir_aerial_survey.yaml": (
        "extended",
        "terrestrial",
        "",
        "T1Thermal",
        None,
    ),
    "examples/templates/lwir_geo.yaml": (
        "extended",
        "terrestrial",
        "",
        "T1Thermal",
        None,
    ),
    "examples/templates/lwir_leo_sounder.yaml": (
        "extended",
        "terrestrial",
        "",
        "T1Thermal",
        None,
    ),
    # Ground truth MWIR: exo atmosphere, extended → no_atmosphere(space)
    "examples/ground_truth_mwir.yaml": (
        "extended",
        "no_atmosphere",
        "space",
        "T1Thermal",
        "ColdSpaceBackground",
    ),
    # MWIR minimal + aerial flir + pushbroom + starer + ground test: simple atm, extended
    "examples/mwir_leo_minimal.yaml": (
        "extended",
        "terrestrial",
        "",
        "T1Thermal",
        None,
    ),
    "examples/templates/mwir_aerial_flir.yaml": (
        "extended",
        "terrestrial",
        "",
        "T1Thermal",
        None,
    ),
    "examples/templates/mwir_ground_test.yaml": (
        "extended",
        "terrestrial",
        "",
        "T1Thermal",
        None,
    ),
    "examples/templates/mwir_leo_pushbroom.yaml": (
        "extended",
        "terrestrial",
        "",
        "T1Thermal",
        None,
    ),
    "examples/templates/mwir_leo_starer.yaml": (
        "extended",
        "terrestrial",
        "",
        "T1Thermal",
        None,
    ),
    # SWIR LEO: simple atm, extended
    "examples/templates/swir_aerial_gas.yaml": (
        "extended",
        "terrestrial",
        "",
        "T1Thermal",
        None,
    ),
    "examples/templates/swir_leo.yaml": (
        "extended",
        "terrestrial",
        "",
        "T1Thermal",
        None,
    ),
    # VNIR: simple atm, extended
    "examples/templates/vnir_aerial.yaml": (
        "extended",
        "terrestrial",
        "",
        "T1Thermal",
        None,
    ),
    "examples/templates/vnir_leo_highres.yaml": (
        "extended",
        "terrestrial",
        "",
        "T1Thermal",
        None,
    ),
    "examples/templates/vnir_leo_multispectral.yaml": (
        "extended",
        "terrestrial",
        "",
        "T1Thermal",
        None,
    ),
}


# ---------------------------------------------------------------------------
# Tests 1: per-scenario inference
# ---------------------------------------------------------------------------


class TestScenarioInference:
    """Confirm every snapshot scenario produces expected descriptors."""

    @pytest.mark.level1
    @pytest.mark.parametrize("scenario_name,path", _scenario_paths())
    def test_expected_variants(self, scenario_name: str, path: Path) -> None:
        assert scenario_name in _EXPECTED, (
            f"Scenario {scenario_name} is in the Stage-0 snapshot but missing "
            f"from the Stage-2 inferrer expectation table.  Add an entry to "
            f"_EXPECTED in test_inferrer.py."
        )
        expected_scene, expected_loc, expected_sub, expected_tgt, expected_bg = _EXPECTED[
            scenario_name
        ]

        params = _load_params(path)
        wl = _wavelength_grid(path)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, bg, los = infer_descriptors(params, wl)

        assert target.scene_type == expected_scene
        assert target.target_location == expected_loc
        actual_sub = target.no_atmosphere_subcase or ""
        assert actual_sub == expected_sub
        assert type(target).__name__ == expected_tgt

        if expected_bg is None:
            assert bg is None, f"{scenario_name}: expected no background, got {bg!r}"
        else:
            assert bg is not None
            assert type(bg).__name__ == expected_bg

        # LOS is None only for at_aperture, which no snapshot cell uses today.
        assert los is not None


# ---------------------------------------------------------------------------
# Tests 2: snapshot regression
# ---------------------------------------------------------------------------


class TestSnapshotRegression:
    """YAML-based descriptor snapshot regression test.

    Each scenario's inferred descriptors are serialised to a YAML file
    under ``snapshots/<scenario_stem>.yaml``.  The test asserts the
    freshly-inferred serialisation equals the on-disk file (via YAML
    text round-trip, which normalises numpy lists and float precision
    consistently on both sides).

    To refresh a snapshot after a deliberate change, set the
    ``RADIANT_REFRESH_DESCRIPTOR_SNAPSHOTS`` environment variable and
    re-run; the test will overwrite the YAML and pass.
    """

    @pytest.mark.level1
    @pytest.mark.parametrize("scenario_name,path", _scenario_paths())
    def test_snapshot_matches(self, scenario_name: str, path: Path) -> None:
        import os

        params = _load_params(path)
        wl = _wavelength_grid(path)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, bg, los = infer_descriptors(params, wl)

        payload = {
            "scenario": scenario_name,
            "wavelength_um": wl.tolist(),
            "target": _descriptor_to_yaml_dict(target),
            "background": _descriptor_to_yaml_dict(bg),
            "los_geometry": _descriptor_to_yaml_dict(los),
        }
        # Normalise via YAML round-trip to avoid float/list mismatches
        # between freshly-computed Python objects and YAML-loaded data.
        payload_text = yaml.safe_dump(payload, sort_keys=True)
        payload_normalised = yaml.safe_load(payload_text)

        stem = path.stem
        snapshot_path = SNAPSHOT_DIR / f"{stem}.yaml"
        refresh = os.environ.get("RADIANT_REFRESH_DESCRIPTOR_SNAPSHOTS") == "1"

        if refresh or not snapshot_path.exists():
            SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(payload_text, encoding="utf-8")
            if not refresh:
                # Fresh creation: fail loud so the reviewer notices a new
                # scenario added without explicit intent.
                pytest.fail(
                    f"Snapshot file was missing and has now been created at "
                    f"{snapshot_path}.  Re-run the test to assert against it.",
                )
            return

        stored_text = snapshot_path.read_text(encoding="utf-8")
        stored = yaml.safe_load(stored_text)

        assert payload_normalised == stored, (
            f"Descriptor snapshot drift for {scenario_name}.\n"
            f"Set RADIANT_REFRESH_DESCRIPTOR_SNAPSHOTS=1 and re-run to "
            f"refresh intentionally; otherwise debug the divergence."
        )


# ---------------------------------------------------------------------------
# Tests 3: user overrides win
# ---------------------------------------------------------------------------


class TestExplicitOverrides:
    @pytest.mark.level1
    def test_explicit_scene_type_overrides_inference(self) -> None:
        params = build_parameter_set()
        load_config(
            REPO_ROOT / "examples" / "templates" / "lwir_aerial_survey.yaml",
            params,
        )
        params.set("source.scene_type", "sub_pixel")
        params.set("source.target.fill_fraction", 0.5)
        params.resolve()
        wl = np.linspace(8.0, 13.0, 11)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, bg, _ = infer_descriptors(params, wl)
        assert target.scene_type == "sub_pixel"
        # Sub-pixel terrestrial ⇒ GroundBackground placeholder.
        assert isinstance(bg, GroundBackground)

    @pytest.mark.level1
    def test_explicit_target_location_overrides_inference(self) -> None:
        params = build_parameter_set()
        load_config(
            REPO_ROOT / "examples" / "ground_truth_mwir.yaml",  # atmosphere.model=exo
            params,
        )
        # Override: user insists on 'at_aperture' with extended, overriding
        # the exo→no_atmosphere(space) inference.
        params.set("source.target_location", "at_aperture")
        params.set("source.scene_type", "extended")
        params.resolve()
        wl = np.linspace(3.0, 5.0, 11)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, bg, los = infer_descriptors(params, wl)
        # The inferrer builds a T1Thermal regardless of target_location in
        # Stage 2 (T5AtAperture support is Stage 7); so we only assert the
        # axis override made it through.
        assert target.target_location == "at_aperture"
        assert target.h_tgt is None
        assert los is None
        assert isinstance(bg, AtApertureBackground)

    @pytest.mark.level1
    def test_explicit_subcase_honored_with_auto_location(self) -> None:
        params = build_parameter_set()
        load_config(
            REPO_ROOT / "examples" / "ground_truth_mwir.yaml",  # exo → space
            params,
        )
        # User leaves location='auto' (inferred: no_atmosphere,space) but
        # sets the subcase explicitly to space (which is the inferred
        # value).  Confirm inferrer honors it.
        params.set("source.no_atmosphere_subcase", "space")
        params.resolve()
        wl = np.linspace(3.0, 5.0, 11)
        target, _, _ = infer_descriptors(params, wl)
        assert target.target_location == "no_atmosphere"
        assert target.no_atmosphere_subcase == "space"


# ---------------------------------------------------------------------------
# Tests 4: failure modes (Category B)
# ---------------------------------------------------------------------------


class TestFailureModes:
    @pytest.mark.level1
    def test_no_atmosphere_without_subcase_raises(self) -> None:
        """Matrix §7: target_location='no_atmosphere' requires a subcase."""
        params = build_parameter_set()
        load_config(
            REPO_ROOT / "examples" / "templates" / "lwir_aerial_survey.yaml",
            params,
        )
        params.set("source.target_location", "no_atmosphere")
        # Leave subcase at default ""
        params.resolve()
        wl = np.linspace(8.0, 13.0, 11)
        with pytest.raises(ParameterBoundsError, match="no_atmosphere"):
            infer_descriptors(params, wl)

    @pytest.mark.level1
    def test_at_aperture_plus_sub_pixel_raises(self) -> None:
        """Matrix §7: at_aperture is extended-only."""
        params = build_parameter_set()
        load_config(
            REPO_ROOT / "examples" / "templates" / "lwir_aerial_survey.yaml",
            params,
        )
        params.set("source.target_location", "at_aperture")
        params.set("source.scene_type", "sub_pixel")
        params.resolve()
        wl = np.linspace(8.0, 13.0, 11)
        with pytest.raises(ParameterBoundsError, match="at_aperture"):
            infer_descriptors(params, wl)

    @pytest.mark.level1
    def test_terrestrial_sub_pixel_placeholder_warns(self) -> None:
        """Stage 2 placeholder warning: terrestrial+sub_pixel → grey GroundBackground."""
        params = build_parameter_set()
        load_config(
            REPO_ROOT / "examples" / "templates" / "lwir_aerial_survey.yaml",
            params,
        )
        params.set("source.scene_type", "sub_pixel")
        params.set("source.target.fill_fraction", 0.5)
        params.resolve()
        wl = np.linspace(8.0, 13.0, 11)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            target, bg, _ = infer_descriptors(params, wl)
        assert isinstance(bg, GroundBackground)
        msgs = [str(w.message) for w in caught if issubclass(w.category, UserWarning)]
        assert any("Stage-2 GroundBackground placeholder" in m for m in msgs), (
            f"Expected Stage-2 placeholder warning, got: {msgs}"
        )

    @pytest.mark.level1
    def test_ground_test_subcase_raises_in_stage_2(self) -> None:
        """Stage 2 has no UserSpectralBackground path; ground_test must raise."""
        params = build_parameter_set()
        load_config(
            REPO_ROOT / "examples" / "templates" / "lwir_aerial_survey.yaml",
            params,
        )
        params.set("source.target_location", "no_atmosphere")
        params.set("source.no_atmosphere_subcase", "ground_test")
        params.resolve()
        wl = np.linspace(8.0, 13.0, 11)
        with pytest.raises(ParameterBoundsError, match="UserSpectralBackground"):
            infer_descriptors(params, wl)


# ---------------------------------------------------------------------------
# Tests 5: round-trip (Category B)
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """scenario YAML → descriptors → re-derived params → equality on subset."""

    @pytest.mark.parametrize(
        "scenario_name",
        [
            # LWIR thermal extended terrestrial
            "examples/templates/lwir_aerial_survey.yaml",
            # VIS reflective extended terrestrial (represented as T1Thermal
            # today because Stage-2 inferrer only synthesises T1)
            "examples/templates/vnir_aerial.yaml",
            # Space sub-case
            "examples/ground_truth_mwir.yaml",
        ],
    )
    @pytest.mark.level1
    def test_round_trip_subset(self, scenario_name: str) -> None:
        path = REPO_ROOT / scenario_name
        params = _load_params(path)
        wl = _wavelength_grid(path)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, bg, los = infer_descriptors(params, wl)
        rederived = descriptors_to_params(target, bg, los)

        # Lossy subset for thermal/material payload: these round-trip
        # verbatim because the descriptors carry them directly.  The
        # matrix-axis keys (scene_type, target_location, subcase) do not
        # round-trip to the user-provided value when the user left them
        # at "auto" — instead they round-trip to the *inferred* value
        # the descriptor now holds.  That is the Stage-2 contract: the
        # inferrer resolves 'auto' to a concrete cell; subsequent stages
        # see the resolved cell, not the sentinel.
        payload_keys = [
            "source.target.temperature",
            "source.target.emissivity",
        ]
        for key in payload_keys:
            if key in rederived:
                original = params.get(key)
                assert rederived[key] == pytest.approx(original, rel=1e-12, abs=1e-12), (
                    f"Round-trip mismatch for {key}: "
                    f"original={original!r}, rederived={rederived[key]!r}"
                )

        # Matrix-axis keys: the round-trip reflects the inferred value
        # when the user left 'auto'.  When the user set an explicit
        # value, the round-trip must match exactly.
        axis_keys = [
            "source.scene_type",
            "source.target_location",
            "source.no_atmosphere_subcase",
        ]
        for key in axis_keys:
            user_value = params.get(key)
            rederived_value = rederived.get(key)
            assert rederived_value is not None, (
                f"Matrix-axis key {key} missing from round-trip dict"
            )
            # Sentinel sentinels for "user left at default":
            if user_value in ("auto", ""):
                # Any concrete resolved value is acceptable; just assert
                # the sentinel was *not* echoed back (i.e., the inferrer
                # resolved it).  'no_atmosphere_subcase' can legitimately
                # remain "" for terrestrial/at_aperture/airborne cells.
                if key == "source.no_atmosphere_subcase":
                    # "" is a valid resolved value for non-no_atmosphere
                    # targets; no further check needed.
                    continue
                assert rederived_value != "auto", (
                    f"{key}: inferrer left the 'auto' sentinel unresolved"
                )
            else:
                assert rederived_value == user_value, (
                    f"Round-trip mismatch for {key}: "
                    f"user_value={user_value!r}, rederived={rederived_value!r}"
                )


# ---------------------------------------------------------------------------
# Tests 6: helper-level unit tests
# ---------------------------------------------------------------------------


class TestInfererHelpers:
    @pytest.mark.level1
    def test_infer_scene_type_extended_default(self) -> None:
        params = build_parameter_set()
        load_config(
            REPO_ROOT / "examples" / "templates" / "lwir_aerial_survey.yaml",
            params,
        )
        params.resolve()
        result = _infer_scene_type(
            params,
            pixel_pitch_m=params.get("detector.pixel_pitch_x_um"),
            focal_length_m=params.get("optics.focal_length_m"),
        )
        assert result == "extended"

    @pytest.mark.level1
    def test_infer_scene_type_fill_fraction_forces_subpixel(self) -> None:
        params = build_parameter_set()
        load_config(
            REPO_ROOT / "examples" / "templates" / "lwir_aerial_survey.yaml",
            params,
        )
        params.set("source.target.fill_fraction", 0.3)
        params.resolve()
        result = _infer_scene_type(
            params,
            pixel_pitch_m=params.get("detector.pixel_pitch_x_um"),
            focal_length_m=params.get("optics.focal_length_m"),
        )
        assert result == "sub_pixel"

    @pytest.mark.level1
    def test_infer_target_location_exo_to_space(self) -> None:
        params = build_parameter_set()
        load_config(REPO_ROOT / "examples" / "ground_truth_mwir.yaml", params)
        params.resolve()
        loc, sub = _infer_target_location_and_subcase(params)
        assert loc == "no_atmosphere"
        assert sub == "space"

    @pytest.mark.level1
    def test_infer_target_location_simple_to_terrestrial(self) -> None:
        params = build_parameter_set()
        load_config(
            REPO_ROOT / "examples" / "templates" / "lwir_aerial_survey.yaml",
            params,
        )
        params.resolve()
        loc, sub = _infer_target_location_and_subcase(params)
        assert loc == "terrestrial"
        assert sub == ""


# ---------------------------------------------------------------------------
# Tests 7: smoke tests — no ImportError from atmosphere in inferrer module
# ---------------------------------------------------------------------------


@pytest.mark.level1
def test_inferrer_does_not_import_atmosphere_module() -> None:
    """Rule 11: source._inferrer must not import radiant.atmosphere.*"""
    import radiant.source._inferrer as infer_mod

    mod_file = Path(infer_mod.__file__).read_text(encoding="utf-8")
    # Allow the string "radiant.atmosphere" in docstrings / comments, but
    # not in an actual import line.
    for line in mod_file.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            assert "radiant.atmosphere" not in stripped, (
                f"Rule 11 violation: _inferrer.py has import line: {line!r}"
            )


# Reference the unused descriptor imports so the linter is happy.
_ = (T2Reflective, T3Mixed, T5AtAperture, UserSpectralBackground)
