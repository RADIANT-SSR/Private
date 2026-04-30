"""Round-2 R9 verification harness — render + thumbnail every canonical view.

PLAN_v2_remediation_round2.md §10 step 2 calls for a verification harness
at this path that:
  * iterates the 9 canonical view fixtures,
  * renders each at 1920×1080 with the off-screen renderer,
  * saves the PNG to ``tests/golden/round2/<view>.png``,
  * saves a thumbnail (480×270) to ``tests/golden/round2/thumbs/<view>.png``,
  * returns a structured result the agent (or a human) can iterate over.

The actual rendering is delegated to ``audit_round2.render_canonical_views``
so the canonical-view → SceneState mapping has one source of truth.
This module adds the thumbnail step and exposes ``verify_all`` so a
caller can drive the inspection loop.

C7 holds: no Qt imports here — PyVista off-screen + PIL.
"""

from __future__ import annotations

import dataclasses
import pathlib
from typing import Iterable

from PIL import Image

from dev_tools.geometry_gui_v2.tests.audit_round2.render_canonical_views import (
    CANONICAL_VIEWS,
    render_view,
)


THUMBNAIL_SIZE = (480, 270)


@dataclasses.dataclass(frozen=True)
class VerificationResult:
    """One row in the verification harness output."""

    view: str
    png_path: pathlib.Path
    thumbnail_path: pathlib.Path


def _save_thumbnail(src: pathlib.Path, dst: pathlib.Path) -> None:
    img = Image.open(src)
    img.thumbnail(THUMBNAIL_SIZE)
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst)


def verify_view(
    view: str,
    out_dir: pathlib.Path,
    thumb_dir: pathlib.Path | None = None,
) -> VerificationResult:
    """Render one view + thumbnail. Returns the resulting paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / f"{view}.png"
    render_view(view, png)

    thumb_dir = thumb_dir or (out_dir / "thumbs")
    thumb = thumb_dir / f"{view}.png"
    _save_thumbnail(png, thumb)

    return VerificationResult(view=view, png_path=png, thumbnail_path=thumb)


def verify_all(
    out_dir: pathlib.Path,
    views: Iterable[str] = CANONICAL_VIEWS,
) -> list[VerificationResult]:
    return [verify_view(v, out_dir) for v in views]


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=pathlib.Path("dev_tools/geometry_gui_v2/tests/golden/round2"),
        help="Output directory for full-size PNGs (thumbs go in <out>/thumbs).",
    )
    parser.add_argument(
        "--views",
        nargs="*",
        default=list(CANONICAL_VIEWS),
        help="Subset of canonical views to render (default: all 9).",
    )
    args = parser.parse_args()
    results = verify_all(args.out, args.views)
    for r in results:
        print(f"  wrote {r.png_path} + {r.thumbnail_path}")


if __name__ == "__main__":
    main()
