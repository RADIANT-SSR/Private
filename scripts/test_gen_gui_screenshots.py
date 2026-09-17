"""Tests for the pure helpers in ``scripts/gen_gui_screenshots.py`` (plan §5).

Run with the rest of the tooling suite::

    pytest scripts/ -q

No test constructs a GUI. Building a ``RADIANTMainWindow`` and awaiting its
evaluation takes seconds per window, and the GUI itself is already covered by
``src/radiant/gui/tests/``; what can silently rot here is the **registry** — a capture
pointing at a config that moved, a name that is not a legal filename, two captures
writing the same PNG — plus the pure filename/manifest/PNG-header helpers. Those are
what is exercised, and the suite stays sub-second.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gen_gui_screenshots  # noqa: E402
from gen_gui_screenshots import (  # noqa: E402
    CAPTURES,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    MANIFEST_NAME,
    NAME_RE,
    REPO,
    Capture,
    ScreenshotError,
    capture_by_name,
    git_commit,
    png_dimensions,
    render_manifest,
    resolve_captures,
    validate_registry,
    write_manifest,
)

#: The four workspaces the feasibility spike proved (plan §5) — Phase 0's starter set.
_STARTER_STAGES = {"performance", "geometry", "optics", "detector"}


def _png_bytes(width: int, height: int) -> bytes:
    """The first 24 bytes of a PNG declaring *width* × *height* (enough for the reader)."""
    ihdr = struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)
    return b"\x89PNG\r\n\x1a\n" + ihdr


class TestRegistry:
    def test_registry_is_sound(self) -> None:
        """Every shipped capture passes its own validation (names, configs, sizes)."""
        assert validate_registry() == []

    def test_names_are_unique(self) -> None:
        names = [c.name for c in CAPTURES]
        assert len(names) == len(set(names))

    def test_names_are_filename_safe(self) -> None:
        for capture in CAPTURES:
            assert NAME_RE.match(capture.name), capture.name
            assert capture.filename == f"{capture.name}.png"
            # A name that needs escaping, a separator, or a parent hop is a defect.
            assert Path(capture.filename).name == capture.filename

    def test_input_configs_exist(self) -> None:
        for capture in CAPTURES:
            assert capture.config_path.is_file(), capture.config
            # Repo-relative, POSIX-spelled, and inside the repo (Rule 30).
            assert not Path(capture.config).is_absolute()
            assert capture.config_path.is_relative_to(REPO)

    def test_stages_are_real_chain_namespaces(self) -> None:
        """A capture may only name a stage the GUI's stage strip actually has."""
        pytest.importorskip("PySide6", reason="stage namespaces come from the gui extra")
        from radiant.gui.widgets.stage_strip import STAGE_NAMESPACES

        for capture in CAPTURES:
            if capture.stage is not None:
                assert capture.stage in STAGE_NAMESPACES, capture.stage

    def test_starter_set_covers_the_four_spike_workspaces(self) -> None:
        assert {c.stage for c in CAPTURES} >= _STARTER_STAGES

    def test_default_geometry_is_the_planned_size(self) -> None:
        assert (DEFAULT_WIDTH, DEFAULT_HEIGHT) == (1440, 900)
        assert all(
            (c.width, c.height) == (DEFAULT_WIDTH, DEFAULT_HEIGHT)
            for c in CAPTURES
            if c.target is None
        )

    def test_capture_by_name_round_trips(self) -> None:
        for capture in CAPTURES:
            assert capture_by_name(capture.name) is capture
        assert capture_by_name("no_such_capture") is None


class TestValidateRegistry:
    def test_duplicate_name_is_reported(self) -> None:
        one = CAPTURES[0]
        problems = validate_registry((one, one))
        assert any("duplicate capture name" in p for p in problems)

    def test_unsafe_name_is_reported(self) -> None:
        bad = Capture(name="../escape", config=CAPTURES[0].config)
        assert any("not a safe file stem" in p for p in validate_registry((bad,)))

    @pytest.mark.parametrize("name", ["Performance", "perf-view", "perf__view", "_perf", "perf "])
    def test_rejected_name_shapes(self, name: str) -> None:
        bad = Capture(name=name, config=CAPTURES[0].config)
        assert any("not a safe file stem" in p for p in validate_registry((bad,)))

    def test_missing_config_is_reported(self) -> None:
        bad = Capture(name="ghost", config="examples/does_not_exist.yaml")
        assert any("input config not found" in p for p in validate_registry((bad,)))

    def test_nonpositive_window_is_reported(self) -> None:
        bad = Capture(name="tiny", config=CAPTURES[0].config, width=0, height=-1)
        assert any("window size must be positive" in p for p in validate_registry((bad,)))

    def test_dock_width_wider_than_window_is_reported(self) -> None:
        bad = Capture(name="wide_dock", config=CAPTURES[0].config, width=800, param_dock_width=900)
        problems = validate_registry((bad,))
        assert any("param_dock_width=900" in p for p in problems)

    def test_empty_splitter_sizes_are_reported(self) -> None:
        bad = Capture(
            name="empty_split", config=CAPTURES[0].config, splitter_sizes={"stagePanelSplit": ()}
        )
        assert any("must be" in p for p in validate_registry((bad,)))

    def test_nonpositive_splitter_size_is_reported(self) -> None:
        bad = Capture(
            name="zero_split",
            config=CAPTURES[0].config,
            splitter_sizes={"stagePanelSplit": (600, 0)},
        )
        problems = validate_registry((bad,))
        assert any("splitter_sizes['stagePanelSplit']" in p for p in problems)

    def test_positive_splitter_sizes_are_accepted(self) -> None:
        good = Capture(
            name="split_ok",
            config=CAPTURES[0].config,
            splitter_sizes={"stagePanelSplit": (620, 380)},
        )
        assert validate_registry((good,)) == []

    def test_blank_tab_is_reported(self) -> None:
        bad = Capture(name="blank_tab", config=CAPTURES[0].config, stage="optics", tab="  ")
        assert any("visible tab label" in p for p in validate_registry((bad,)))

    def test_tab_without_a_stage_is_reported(self) -> None:
        """A tab belongs to a stage workspace, so naming one without a stage is a typo."""
        bad = Capture(name="orphan_tab", config=CAPTURES[0].config, tab="MTF")
        assert any("needs a stage" in p for p in validate_registry((bad,)))

    def test_tab_with_a_stage_is_accepted(self) -> None:
        good = Capture(name="tab_ok", config=CAPTURES[0].config, stage="optics", tab="MTF")
        assert validate_registry((good,)) == []

    def test_registry_tabs_are_titles_the_stage_spec_declares(self) -> None:
        """Every registered tab label must exist in that stage's sub-view composition.

        A tab is selected by its *visible label*, so a renamed tab breaks the capture at
        run time, minutes into a batch. The composition table is Qt-free data, so the
        check is cheap and runs with the rest of the registry validation.
        """
        pytest.importorskip("PySide6", reason="stage compositions import the gui package")
        from radiant.gui.stage_views import STAGE_COMPOSITIONS

        for capture in CAPTURES:
            if capture.tab is None:
                continue
            composition = STAGE_COMPOSITIONS[capture.stage]
            titles = [sub.title for sub in composition.subviews]
            assert capture.tab in titles, (capture.name, capture.tab, titles)

    def test_dock_width_inside_window_is_accepted(self) -> None:
        good = Capture(
            name="wide_dock",
            config=CAPTURES[0].config,
            width=1440,
            param_dock_width=520,
            rail_dock_width=300,
        )
        assert validate_registry((good,)) == []


class TestResolveCaptures:
    def test_all_selects_everything(self) -> None:
        captures, status = resolve_captures([], capture_all=True)
        assert status == 0
        assert captures == list(CAPTURES)

    def test_named_selection_preserves_order(self) -> None:
        names = [CAPTURES[1].name, CAPTURES[0].name]
        captures, status = resolve_captures(names, capture_all=False)
        assert status == 0
        assert [c.name for c in captures] == names

    def test_unknown_name_is_an_error(self) -> None:
        captures, status = resolve_captures(["nope"], capture_all=False)
        assert (captures, status) == ([], 2)

    def test_empty_selection_without_all_is_an_error(self) -> None:
        captures, status = resolve_captures([], capture_all=False)
        assert (captures, status) == ([], 2)


class TestPngDimensions:
    def test_reads_ihdr(self, tmp_path: Path) -> None:
        path = tmp_path / "f.png"
        path.write_bytes(_png_bytes(1440, 900))
        assert png_dimensions(path) == (1440, 900)

    def test_rejects_non_png(self, tmp_path: Path) -> None:
        path = tmp_path / "f.png"
        path.write_bytes(b"not an image at all, not even 24 bytes long......")
        with pytest.raises(ScreenshotError, match="not a PNG"):
            png_dimensions(path)

    def test_rejects_truncated_file(self, tmp_path: Path) -> None:
        path = tmp_path / "f.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        with pytest.raises(ScreenshotError, match="not a PNG"):
            png_dimensions(path)


class TestResolveTarget:
    """Panel-level figures name a child widget by dotted accessor path (plan §5)."""

    def test_walks_a_dotted_path(self) -> None:
        leaf = object()
        middle = SimpleNamespace(stage_center=leaf)
        window = SimpleNamespace(central_canvas=middle)
        assert gen_gui_screenshots._resolve_target(window, "central_canvas.stage_center") is leaf

    def test_single_segment(self) -> None:
        panel = object()
        window = SimpleNamespace(parameter_panel=panel)
        assert gen_gui_screenshots._resolve_target(window, "parameter_panel") is panel

    def test_missing_accessor_is_actionable(self) -> None:
        window = SimpleNamespace(central_canvas=SimpleNamespace())
        with pytest.raises(ScreenshotError, match="does not resolve") as excinfo:
            gen_gui_screenshots._resolve_target(window, "central_canvas.nope")
        message = str(excinfo.value)
        assert "central_canvas.nope" in message
        assert "action:" in message  # Rule-15-style guidance, not a bare failure


class TestManifest:
    def test_names_generator_and_commit(self) -> None:
        text = render_manifest(commit="abc1234", generated_on="2026-09-16")
        assert "scripts/gen_gui_screenshots.py" in text
        assert "`abc1234`" in text
        assert "2026-09-16" in text

    def test_lists_every_capture_with_provenance(self) -> None:
        text = render_manifest(commit="abc1234", generated_on="2026-09-16")
        for capture in CAPTURES:
            assert f"`{capture.filename}`" in text
            assert f"`{capture.config}`" in text
            assert f"{capture.width}×{capture.height}" in text

    def test_records_the_selected_tab(self) -> None:
        """A tabbed capture's provenance row must say which tab it photographed."""
        tabbed = Capture(
            name="tab_row", config=CAPTURES[0].config, stage="optics", tab="MTF", caption="x"
        )
        text = render_manifest((tabbed,), commit="abc1234", generated_on="2026-09-16")
        assert "`optics` → MTF" in text

    def test_records_the_offscreen_ruling(self) -> None:
        """The provenance record must say the figures are offscreen/platform-neutral (Q7)."""
        text = render_manifest(commit="abc1234")
        assert "offscreen" in text
        assert "Q7" in text

    def test_write_manifest_writes_utf8_markdown(self, tmp_path: Path) -> None:
        path = write_manifest(tmp_path, commit="deadbee")
        assert path == tmp_path / MANIFEST_NAME
        assert "`deadbee`" in path.read_text(encoding="utf-8")

    def test_manifest_is_deterministic_for_a_fixed_stamp(self) -> None:
        first = render_manifest(commit="abc1234", generated_on="2026-09-16")
        second = render_manifest(commit="abc1234", generated_on="2026-09-16")
        assert first == second


class TestGitCommit:
    def test_returns_a_short_sha_or_unknown(self) -> None:
        commit = git_commit()
        assert commit == "unknown" or commit.isalnum()
        assert "\n" not in commit


class TestEnvironment:
    def test_offscreen_platform_is_pinned_at_import(self) -> None:
        """Ruling Q7: every figure is captured offscreen, so the plugin is set on import."""
        import os

        assert os.environ["QT_QPA_PLATFORM"] == "offscreen"
        assert os.environ["RADIANT_CONSOLE_FORCE_REPL"] == "1"

    def test_output_dir_is_the_documented_figure_folder(self) -> None:
        assert gen_gui_screenshots.FIGURES == REPO / "docs" / "guides" / "figures" / "gui"


class TestCli:
    def test_list_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert gen_gui_screenshots.main(["--list"]) == 0
        out = capsys.readouterr().out
        for capture in CAPTURES:
            assert capture.name in out

    def test_all_plus_names_is_rejected(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert gen_gui_screenshots.main(["--all", CAPTURES[0].name]) == 2
        assert "mutually exclusive" in capsys.readouterr().err

    def test_unknown_capture_is_rejected(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert gen_gui_screenshots.main(["not_a_capture"]) == 2
        assert "unknown capture" in capsys.readouterr().err
