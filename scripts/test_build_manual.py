"""Tests for the pure helpers in ``scripts/build_manual.py`` (Support_Documentation_Plan §8).

Run with the rest of the tooling suite::

    pytest scripts/ -q

No test invokes pandoc: the builder's value that can silently rot is the *source
scanning* — header stripping, the raw-HTML / display-math / image checks, and the volume
registry pointing at files that exist. Those are what is exercised here. The three
architecture specs Volume III binds in Phase 2 are stripped for real, so a reformat of
their metadata headers fails here rather than in a manual six months from now.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_manual  # noqa: E402  (path insert must precede the import)
from build_manual import (  # noqa: E402
    ARCHITECTURE,
    DEFAULTS_FILE,
    DOCS,
    HEADER_FILE,
    VOLUMES,
    Volume,
    count_display_math,
    latex_escape,
    package_version,
    scan_images,
    scan_raw_html,
    strip_persona_line,
    strip_spec_header,
    unmapped_risk_chars,
    validate_chapter,
    validate_volume,
    version_string,
    write_appendix_marker,
)

#: The three specs Volume III Part 3 binds verbatim (plan §6) — the real consumers of
#: the ruling-Q2 header strip.
BOUND_SPECS = (
    "RADIANT_Signal_Chain_Architecture.md",
    "RADIANT_Parameter_System.md",
    "RADIANT_Testing_Validation.md",
)


# --- Header stripping (ruling Q2) ----------------------------------------------------


def test_strip_spec_header_synthetic() -> None:
    """The metadata block, its blank lines, and the closing rule all go."""
    text = (
        "# A Spec\n"
        "\n"
        "**Date:** 2026-04-07  \n"
        "**Status:** Accepted  \n"
        "**Depends on:** Other.md  \n"
        "**Scope:** What this covers.\n"
        "\n"
        "---\n"
        "\n"
        "## 1. First Section\n"
        "\n"
        "Body text.\n"
    )
    assert strip_spec_header(text) == "# A Spec\n\n## 1. First Section\n\nBody text.\n"


def test_strip_spec_header_without_closing_rule() -> None:
    """A spec whose header is not followed by a thematic break strips just the block."""
    text = "# A Spec\n\n**Status:** Accepted\n\nBody text.\n"
    assert strip_spec_header(text) == "# A Spec\n\nBody text.\n"


def test_strip_spec_header_leaves_ordinary_chapters_alone() -> None:
    """A theory chapter (no metadata block) is returned byte-identical."""
    text = "# Noise Model\n\nSome prose.\n\n**Bold lead-in** is not a metadata key.\n"
    assert strip_spec_header(text) == text


def test_strip_spec_header_no_h1_is_identity() -> None:
    text = "**Date:** 2026-04-07\n\nA fragment with no heading.\n"
    assert strip_spec_header(text) == text


def test_strip_spec_header_does_not_eat_body_bold() -> None:
    """Only the block *immediately* after the H1 is metadata."""
    text = "# A Spec\n\nIntro paragraph.\n\n**Note:** this is body text.\n"
    assert strip_spec_header(text) == text


@pytest.mark.parametrize("name", BOUND_SPECS)
def test_strip_spec_header_on_real_specs(name: str) -> None:
    """Every spec Volume III binds loses its header and keeps its H1 and body."""
    path = ARCHITECTURE / name
    text = path.read_text(encoding="utf-8")
    stripped = strip_spec_header(text)

    assert stripped != text, f"{name}: metadata header was not recognised"
    lines = stripped.splitlines()
    assert lines[0].startswith("# "), f"{name}: H1 must survive the strip"
    assert lines[0] == text.splitlines()[0]
    assert "**Date:**" not in stripped
    assert "**Status:**" not in stripped
    assert "**Depends on:**" not in stripped
    # The first real content line is a heading, not a stray rule or blank run.
    assert lines[2].startswith("#"), f"{name}: unexpected first body line {lines[2]!r}"
    # Nothing on disk changed.
    assert path.read_text(encoding="utf-8") == text


# --- Raw-HTML scan -------------------------------------------------------------------


def test_scan_raw_html_finds_block_tags() -> None:
    found = scan_raw_html('Intro.\n\n<div class="note">careful</div>\n')
    assert [lineno for lineno, _ in found] == [3, 3]
    assert found[0][1] == '<div class="note">'


def test_scan_raw_html_ignores_fenced_code() -> None:
    text = "Prose.\n\n```html\n<div>shown as an example</div>\n```\n\nMore prose.\n"
    assert scan_raw_html(text) == []


def test_scan_raw_html_ignores_tilde_fences() -> None:
    text = "Prose.\n\n~~~\n<span>example</span>\n~~~\n"
    assert scan_raw_html(text) == []


def test_scan_raw_html_ignores_inline_code_spans() -> None:
    assert scan_raw_html("Write `<sub>` as math instead.\n") == []


def test_scan_raw_html_ignores_autolinks_and_math() -> None:
    """Autolinks and comparison operators are not tags (the false-positive guard)."""
    text = (
        "See <https://pandoc.org/MANUAL.html> and mail <docs@example.com>.\n"
        "Bounds: $a < b$ and $f < f_{Nyq}$.\n"
    )
    assert scan_raw_html(text) == []


def test_scan_raw_html_detects_self_closing_and_void_tags() -> None:
    found = scan_raw_html("Line one.<br/>\nLine two.<br>\n")
    assert [tag for _, tag in found] == ["<br/>", "<br>"]


def test_theory_chapters_carry_no_raw_html() -> None:
    """The bound Volume I chapters are Pandoc-subset clean today (§5.4 rule 2)."""
    for chapter in VOLUMES["theory"].sources:
        text = (DOCS / chapter).read_text(encoding="utf-8")
        assert scan_raw_html(text) == [], f"{chapter} has raw HTML"


# --- Display-math balance ------------------------------------------------------------


def test_count_display_math_counts_pairs() -> None:
    assert count_display_math("$$\na = b\n$$\n") == 2
    assert count_display_math("$$a = b$$\n") == 2


def test_count_display_math_ignores_code_fences() -> None:
    assert count_display_math("```\n$$ not math $$\n```\n") == 0


def test_count_display_math_flags_odd_count() -> None:
    assert count_display_math("$$\na = b\n") % 2 == 1


@pytest.mark.parametrize("chapter", VOLUMES["theory"].sources)
def test_theory_chapters_have_balanced_display_math(chapter: str) -> None:
    text = (DOCS / chapter).read_text(encoding="utf-8")
    assert count_display_math(text) % 2 == 0, f"{chapter} has an unpaired $$"


# --- Image scan ----------------------------------------------------------------------


def test_scan_images_returns_local_destinations() -> None:
    text = "![A figure](figures/psf.png)\n\n![Remote](https://example.com/x.png)\n"
    assert scan_images(text) == [(1, "figures/psf.png")]


def test_scan_images_ignores_fenced_examples() -> None:
    assert scan_images("```\n![x](y.png)\n```\n") == []


def test_scan_images_sees_wrapped_caption() -> None:
    # A caption wrapped across source lines split the reference across lines; the
    # per-line scan missed it and a missing figure sailed through (Phase 4 review).
    text = "Intro prose.\n\n![A caption that wraps to\nthe next line.](figures/gui/x.png)\n"
    assert scan_images(text) == [(3, "figures/gui/x.png")]


def test_scan_images_wrapped_remote_still_ignored() -> None:
    text = "![Wrapped remote\ncaption](https://example.com/x.png)\n"
    assert scan_images(text) == []


def test_validate_chapter_flags_missing_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A referenced figure that does not exist fails the build with an actionable message."""
    chapter = tmp_path / "chapter.md"
    chapter.write_text("# C\n\n![Missing](figures/nope.png)\n", encoding="utf-8")
    monkeypatch.setattr(build_manual, "REPO", tmp_path)

    problems = validate_chapter(chapter)
    assert len(problems) == 1
    assert "figures/nope.png" in problems[0]
    assert "action:" in problems[0]


def test_validate_chapter_accepts_resolvable_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "psf.png").write_bytes(b"")
    chapter = tmp_path / "chapter.md"
    chapter.write_text("# C\n\n![There](figures/psf.png)\n", encoding="utf-8")
    monkeypatch.setattr(build_manual, "REPO", tmp_path)

    assert validate_chapter(chapter) == []


# --- Volume registry -----------------------------------------------------------------


def test_registry_declares_the_four_volumes() -> None:
    assert list(VOLUMES) == ["theory", "users_guide", "tech_ref", "examples"]
    for key, volume in VOLUMES.items():
        assert volume.key == key
        assert volume.title and volume.subtitle
        assert volume.phase_note


def test_theory_volume_binds_the_phase_1_toc() -> None:
    """Volume I v1.0 order (plan §4): front matter, intro, geometry BEFORE radiometry."""
    assert VOLUMES["theory"].front_matter == ("theory/notation.md",)
    assert VOLUMES["theory"].back_matter == ("theory/references.md",)
    assert VOLUMES["theory"].chapters == (
        "theory/introduction.md",
        "theory/geometry.md",
        "theory/radiometric_chain.md",
        "theory/atmosphere_models.md",
        "theory/spatial_model.md",
        "theory/noise_model.md",
        "theory/calibration_model.md",
        "theory/performance_metrics.md",
    )
    assert VOLUMES["theory"].appendices == ("theory/radiometric_model_mixed_train.md",)


def test_appendices_default_to_empty() -> None:
    """A volume that declares no appendices stages no marker (the field is optional)."""
    plain = Volume(key="v", title="T", subtitle="S", chapters=("theory/notation.md",))
    assert plain.appendices == ()
    assert plain.sources == ("theory/notation.md",)


def test_sources_orders_chapters_then_appendices() -> None:
    volume = Volume(
        key="v",
        title="T",
        subtitle="S",
        chapters=("theory/notation.md", "theory/introduction.md"),
        appendices=("theory/references.md",),
    )
    assert volume.sources == (
        "theory/notation.md",
        "theory/introduction.md",
        "theory/references.md",
    )


@pytest.mark.parametrize("key", list(VOLUMES))
def test_every_bound_chapter_exists(key: str) -> None:
    for chapter in VOLUMES[key].sources:
        assert (DOCS / chapter).is_file(), f"volume '{key}' binds a missing file: {chapter}"


def test_validate_volume_reports_a_missing_appendix() -> None:
    """Registry integrity covers appendices, not just chapters."""
    ghost = Volume(
        key="ghost",
        title="T",
        subtitle="S",
        chapters=("theory/notation.md",),
        appendices=("theory/nope.md",),
    )
    problems = validate_volume(ghost)
    assert len(problems) == 1
    assert "theory/nope.md" in problems[0]


# --- Appendix marker -----------------------------------------------------------------


def test_appendix_marker_is_a_raw_latex_block(tmp_path: Path) -> None:
    """The staged marker is exactly a ``{=latex}`` fence holding ``\\appendix``."""
    path = write_appendix_marker(tmp_path)

    assert path.parent == tmp_path
    text = path.read_text(encoding="utf-8")
    assert text == "```{=latex}\n\\appendix\n```\n"
    # It is raw LaTeX, so the prose scans must see nothing at all in it.
    assert scan_raw_html(text) == []
    assert count_display_math(text) == 0


def test_appendix_marker_is_written_into_the_staging_directory(tmp_path: Path) -> None:
    """Nothing is written under docs/ — the marker is a build artifact (Rule 26)."""
    staged = tmp_path / "stage"
    staged.mkdir()
    path = write_appendix_marker(staged)

    assert path.is_file()
    assert list(staged.iterdir()) == [path]


@pytest.mark.parametrize("key", list(VOLUMES))
def test_populated_volumes_validate_clean(key: str) -> None:
    assert validate_volume(VOLUMES[key]) == []


def test_validate_volume_reports_a_missing_chapter() -> None:
    ghost = Volume(key="ghost", title="T", subtitle="S", chapters=("theory/nope.md",))
    problems = validate_volume(ghost)
    assert len(problems) == 1
    assert "theory/nope.md" in problems[0]
    assert "action:" in problems[0]


# --- Cover metadata ------------------------------------------------------------------


def test_package_version_matches_the_package() -> None:
    assert package_version() == "0.1.0"


def test_version_string_is_latex_safe() -> None:
    text = version_string()
    assert text.startswith("v0.1.0")
    assert not set(text) & set("\\{}$&#%_^~")


def test_version_string_drops_a_git_describe_that_repeats_the_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On the release tag itself, git describe echoes the version — CU-370 X-02."""
    monkeypatch.setattr(build_manual, "package_version", lambda: "0.1.0")
    monkeypatch.setattr(build_manual, "git_describe", lambda: "v0.1.0")
    assert version_string() == "v0.1.0"
    monkeypatch.setattr(build_manual, "git_describe", lambda: "0.1.0")
    assert version_string() == "v0.1.0"


def test_version_string_keeps_a_git_describe_that_adds_information(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(build_manual, "package_version", lambda: "0.1.0")
    monkeypatch.setattr(build_manual, "git_describe", lambda: "v0.1.0-3-gabc1234")
    assert version_string() == "v0.1.0 (v0.1.0-3-gabc1234)"


def test_latex_escape_handles_specials() -> None:
    assert latex_escape("Examples & Validation") == r"Examples \& Validation"
    assert latex_escape("a_b") == r"a\_b"


# --- Persona-line strip --------------------------------------------------------------


def test_strip_persona_line_removes_leading_tag() -> None:
    text = "# Spatial Model\n\n*Persona: Tom (optical designer)*\n\nPSF construction.\n"
    assert strip_persona_line(text) == "# Spatial Model\n\nPSF construction.\n"


def test_strip_persona_line_ignores_deep_mentions() -> None:
    text = "# X\n\nProse one.\n\nProse two.\n\nProse three.\n\n*Persona: deep*\n"
    assert strip_persona_line(text) == text


def test_strip_persona_line_noop_without_tag() -> None:
    text = "# X\n\nNo tag here.\n"
    assert strip_persona_line(text) == text


def test_every_theory_chapter_persona_tag_is_stripped() -> None:
    for chapter in VOLUMES["theory"].sources:
        text = (DOCS / chapter).read_text(encoding="utf-8")
        assert "*Persona:" not in strip_persona_line(text)


# --- Wrong-glyph guard (CU-370 X-01) --------------------------------------------------


def test_every_wrong_glyph_risk_char_is_mapped_in_the_preamble() -> None:
    """The companion of the missing-glyph log check, which cannot see substitutions.

    ``°`` inside a math span reached the math font, whose T1 slot 0xB0 holds ``ř``, and
    XeLaTeX reported nothing — dozens of corrupted numeric anchors shipped in three
    volumes. The mapping is what fixes it, so its removal must fail loudly.
    """
    assert unmapped_risk_chars(HEADER_FILE.read_text(encoding="utf-8")) == []


def test_unmapped_risk_chars_reports_a_preamble_without_the_mapping() -> None:
    assert unmapped_risk_chars("% no mappings here\n") == list(build_manual._WRONG_GLYPH_RISK_CHARS)


def test_degree_mapping_is_math_aware() -> None:
    """The mapping must survive math mode, where the bug lived, and leave prose alone."""
    preamble = HEADER_FILE.read_text(encoding="utf-8")
    assert r"\newunicodechar{°}{\ifmmode^{\circ}\else\textdegree\fi}" in preamble


# --- Pandoc reader extensions (CU-370 X-11 / X-12) ------------------------------------


def test_reader_enables_smart_punctuation_and_implicit_figures() -> None:
    defaults = DEFAULTS_FILE.read_text(encoding="utf-8")
    reader = next(
        line.split(":", 1)[1].strip() for line in defaults.splitlines() if line.startswith("from:")
    )
    assert "+smart" in reader
    assert "+implicit_figures" in reader
